# app/llm/ollama_client.py
"""
Enhanced Ollama Client with Streaming, Caching, and Performance Tracking
IMPROVEMENTS:
- Streaming support for better UX
- Response caching for repeated queries
- Performance metrics tracking
- Better error handling and retry logic
- Token counting estimation
- FIXED: Improved SQL extraction from explanatory text
"""

import requests
import json
import time
import re
import hashlib
from typing import Optional, Dict, Callable
from app.utils.logger import get_logger
from app.core.config import Config

logger = get_logger(__name__)


class OllamaClient:
    """
    Enhanced Ollama API client with caching and monitoring
    """
    
    def __init__(
        self,
        model_name: str = None,
        base_url: str = None,
        timeout: int = None,
        enable_cache: bool = None
    ):
        self.model = model_name or Config.OLLAMA_MODEL
        self.base_url = base_url or Config.OLLAMA_HOST + "/api/generate"
        self.timeout = timeout or Config.OLLAMA_TIMEOUT
        self.max_retries = 2
        self.retry_delay = 2.0
        self.enable_cache = enable_cache if enable_cache is not None else Config.ENABLE_CACHING
        
        # Cache for repeated queries
        self.response_cache = {}
        
        # Performance tracking
        self.metrics = {
            "total_calls": 0,
            "cache_hits": 0,
            "total_tokens_estimated": 0,
            "total_time_seconds": 0.0,
            "errors": 0
        }
    
    # ---------------------------
    # Low-level Ollama call
    # ---------------------------
    def _call_ollama(
        self, 
        prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        Makes HTTP request to Ollama API with retry logic and optional streaming
        
        Args:
            prompt: The prompt to send to LLM
            stream_callback: Optional callback for streaming response chunks
            
        Returns:
            LLM response text or None on failure
        """
        self.metrics["total_calls"] += 1
        start_time = time.time()
        
        # Check cache
        if self.enable_cache:
            cache_key = self._get_cache_key(prompt)
            if cache_key in self.response_cache:
                logger.info("💾 Using cached response")
                self.metrics["cache_hits"] += 1
                return self.response_cache[cache_key]
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True  # Enable streaming for better UX
        }

        for attempt in range(1, self.max_retries + 2):
            try:
                logger.info(f"🔗 Sending request to Ollama (attempt {attempt}/{self.max_retries + 1})...")
                
                response = requests.post(
                    self.base_url,
                    json=payload,
                    timeout=self.timeout,
                    stream=True  # Enable streaming
                )
                response.raise_for_status()
                
            except requests.exceptions.Timeout:
                logger.error(f"⏱️ Timeout on attempt {attempt} (timeout: {self.timeout}s)")
                self.metrics["errors"] += 1
                if attempt <= self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                return None
                
            except Exception as e:
                logger.error(f"❌ Connection error attempt {attempt}: {e}")
                self.metrics["errors"] += 1
                if attempt <= self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                return None

            # Parse streaming response
            final_text = ""
            try:
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line.decode('utf-8'))
                        chunk = data.get("response", "") or data.get("text", "")
                        
                        if chunk:
                            final_text += chunk
                            
                            # Call stream callback if provided
                            if stream_callback:
                                stream_callback(chunk)
                                
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON decode error (non-critical): {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Stream processing error: {e}")
                self.metrics["errors"] += 1
                if attempt <= self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                return None

            # Clean and validate response
            cleaned = self._clean_response(final_text.strip())
            
            if cleaned:
                # Update metrics
                elapsed = time.time() - start_time
                self.metrics["total_time_seconds"] += elapsed
                self.metrics["total_tokens_estimated"] += self._estimate_tokens(prompt + cleaned)
                
                logger.info(f"✅ Response received ({elapsed:.2f}s, ~{len(cleaned)} chars)")
                
                # Cache the response
                if self.enable_cache:
                    cache_key = self._get_cache_key(prompt)
                    self.response_cache[cache_key] = cleaned
                
                return cleaned
            else:
                logger.warning(f"⚠️ Empty response on attempt {attempt}")
                if attempt <= self.max_retries:
                    time.sleep(self.retry_delay)
                    continue

        return None

    # ---------------------------
    # Post-processing
    # ---------------------------
    def _clean_response(self, text: str) -> str:
        """
        Removes markdown artifacts and SQL prefixes
        IMPROVED: Now extracts SQL from explanatory text
        
        Removes:
        - Explanatory text before SQL
        - Leading 'SQL'
        - Markdown code blocks (```sql, ```)
        - Trailing 'GO' (SQL Server batch separator)
        - Extra whitespace
        """
        if not text:
            return ""
            
        cleaned = text.strip()
        
        # NEW: Look for SQL keywords and extract from that point
        # This handles cases where LLM adds explanation before SQL
        sql_keywords = [
            'SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE', 
            'CREATE', 'DROP', 'ALTER', 'DECLARE'
        ]
        
        # Find the first SQL keyword
        first_sql_pos = len(cleaned)  # Default to end if not found
        found_keyword = None
        
        for keyword in sql_keywords:
            # Look for keyword at word boundary
            pattern = r'\b' + keyword + r'\b'
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match and match.start() < first_sql_pos:
                first_sql_pos = match.start()
                found_keyword = keyword
        
        # If we found a SQL keyword, take everything from that point
        if found_keyword:
            cleaned = cleaned[first_sql_pos:]
            logger.debug(f"Extracted SQL starting from keyword: {found_keyword}")

        # Remove markdown code blocks
        cleaned = re.sub(r"^```sql\s*", "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()
        cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
        cleaned = re.sub(r"\s*```\s*$", "", cleaned, flags=re.MULTILINE).strip()

        # Remove lone "SQL" at beginning
        cleaned = re.sub(r"^SQL\s*", "", cleaned, flags=re.IGNORECASE).strip()
        
        # Remove "GO" at the end (SQL Server batch separator)
        cleaned = re.sub(r"\s*GO\s*;?\s*$", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^\s*GO\s*$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()

        # Remove extra blank lines
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
        
        return cleaned.strip()
    
    # ---------------------------
    # Caching
    # ---------------------------
    def _get_cache_key(self, prompt: str) -> str:
        """Generate cache key from prompt"""
        return hashlib.md5(prompt.encode()).hexdigest()
    
    def clear_cache(self):
        """Clear response cache"""
        self.response_cache.clear()
        logger.info("🗑️ Cache cleared")
    
    # ---------------------------
    # Metrics
    # ---------------------------
    def _estimate_tokens(self, text: str) -> int:
        """Rough token count estimation (1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def get_metrics(self) -> Dict:
        """Get performance metrics"""
        metrics = self.metrics.copy()
        
        if metrics["total_calls"] > 0:
            metrics["cache_hit_rate"] = metrics["cache_hits"] / metrics["total_calls"]
            metrics["avg_time_per_call"] = metrics["total_time_seconds"] / metrics["total_calls"]
        else:
            metrics["cache_hit_rate"] = 0.0
            metrics["avg_time_per_call"] = 0.0
        
        return metrics
    
    def log_metrics(self):
        """Log current metrics"""
        metrics = self.get_metrics()
        logger.info("📊 Ollama Client Metrics:")
        logger.info(f"  Total calls: {metrics['total_calls']}")
        logger.info(f"  Cache hits: {metrics['cache_hits']} ({metrics['cache_hit_rate']:.1%})")
        logger.info(f"  Total time: {metrics['total_time_seconds']:.2f}s")
        logger.info(f"  Avg time/call: {metrics['avg_time_per_call']:.2f}s")
        logger.info(f"  Est. tokens: {metrics['total_tokens_estimated']:,}")
        logger.info(f"  Errors: {metrics['errors']}")

    # ---------------------------
    # Public API
    # ---------------------------
    def run(
        self, 
        prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        Generic LLM invocation method
        
        Args:
            prompt: The prompt to send
            stream_callback: Optional callback for streaming
            
        Returns:
            LLM response
        """
        logger.info("🔗 Sending prompt to Ollama...")
        return self._call_ollama(prompt, stream_callback)

    def generate_sql(
        self, 
        prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        Specialized method for SQL generation
        
        Args:
            prompt: SQL generation prompt
            stream_callback: Optional streaming callback
            
        Returns:
            Generated SQL query
        """
        logger.info("🔍 Generating SQL via OllamaClient.generate_sql()")
        return self.run(prompt, stream_callback)

    def generate_summary(
        self, 
        prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        Specialized method for result summarization
        
        Args:
            prompt: Summarization prompt
            stream_callback: Optional streaming callback
            
        Returns:
            Business summary text
        """
        logger.info("📊 Generating summary via OllamaClient.generate_summary()")
        return self.run(prompt, stream_callback)

    def summarize_results(self, sql_query: str, dataframe_json: str) -> Optional[str]:
        """
        Legacy method for backward compatibility
        Generates business summary from SQL results
        
        Args:
            sql_query: The SQL query that was executed
            dataframe_json: JSON representation of results
            
        Returns:
            Business summary in Turkish
        """
        logger.info("📊 Generating business summary (legacy method)...")

        prompt = f"""
You are a business analyst. Summarize these SQL results in Turkish (max 150 words).

SQL Query:
{sql_query}

Query Results (JSON):
{dataframe_json}

Business Summary:
"""
        return self.run(prompt)


# Singleton instance for easy access
_client_instance = None

def get_ollama_client() -> OllamaClient:
    """Get singleton Ollama client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = OllamaClient()
    return _client_instance


if __name__ == "__main__":
    # Test the client
    client = OllamaClient()
    
    # Test basic call
    response = client.run("What is 2+2?")
    print(f"Response: {response}")
    
    # Show metrics
    client.log_metrics()