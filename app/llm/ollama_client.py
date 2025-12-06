# app/llm/ollama_client.py
"""
OllamaClient - Final Production Version (2025)

Supports:
- SQL model (Config.OLLAMA_SQL_MODEL)
- Summary model (Config.OLLAMA_SUMMARY_MODEL)
- Streaming for SQL
- Non-streaming for Summary
- Retry + Timeout
- Caching
- Advanced SQL extraction
- OpenAI fallback (for both SQL + Summary)
"""

import json
import time
import re
import hashlib
from typing import Optional, Callable, Dict, Any

import requests

from app.utils.logger import get_logger
from app.core.config import Config
from app.llm.openai_client import OpenAIClient

logger = get_logger(__name__)


class OllamaClient:
    """
    High-level client used by:
    - DynamicSQLGenerator (generate_sql)
    - ResultSummarizer (generate_summary)
    """

    def __init__(
        self,
        sql_model: Optional[str] = None,
        summary_model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        enable_cache: Optional[bool] = None,
    ):
        # Models (from Config)
        self.sql_model = sql_model or Config.OLLAMA_SQL_MODEL
        self.summary_model = summary_model or Config.OLLAMA_SUMMARY_MODEL

        # Base URL
        self.base_url = (base_url or Config.OLLAMA_HOST).rstrip("/")

        # Timeouts
        self.timeout = timeout or Config.OLLAMA_TIMEOUT

        # Cache settings
        self.enable_cache = (
            enable_cache if enable_cache is not None else Config.ENABLE_CACHING
        )

        # Retries
        self.max_retries = 2
        self.retry_delay = 1.2

        # OpenAI fallback
        self.enable_openai_fallback = Config.ENABLE_OPENAI_FALLBACK
        self.openai_client = (
            OpenAIClient() if self.enable_openai_fallback else None
        )

        # Cache for model-level results
        self._cache: Dict[str, str] = {}

        logger.info(
            f"🤖 OllamaClient initialized "
            f"(sql_model={self.sql_model}, summary_model={self.summary_model}, "
            f"fallback={'ON' if self.enable_openai_fallback else 'OFF'})"
        )

    # ======================================================
    # PUBLIC API
    # ======================================================
    def generate_sql(self, prompt: str, stream_callback=None) -> Optional[str]:
        """
        Main SQL generator:
         1) Try Ollama (SQL model)
         2) If empty/failed → OpenAI fallback
        """
        logger.info("🔍 Generating SQL using primary Ollama model...")

        sql_text = self._generate(
            model=self.sql_model,
            prompt=prompt,
            stream=True,
            stream_callback=stream_callback,
            clean_sql=True,
        )

        if sql_text:
            return sql_text

        # OpenAI fallback
        if self.enable_openai_fallback and self.openai_client:
            logger.warning("⚠️ Ollama SQL failed → switching to OpenAI fallback...")
            try:
                fallback_sql = self.openai_client.generate_sql(prompt)
                if fallback_sql:
                    logger.info("✅ OpenAI SQL fallback succeeded.")
                    return fallback_sql
            except Exception as e:
                logger.error(f"❌ OpenAI SQL fallback failed: {e}")

        logger.error("❌ SQL generation failed in both Ollama and OpenAI.")
        return None

    def generate_summary(self, prompt: str, stream_callback=None) -> Optional[str]:
        """
        Summary generator:
         1) Try Ollama small model
         2) If empty/failed → OpenAI fallback
        """
        logger.info("📊 Generating summary using summary model...")

        summary = self._generate(
            model=self.summary_model,
            prompt=prompt,
            stream=False,
            clean_sql=False,
        )

        if summary:
            return summary.strip()

        if self.enable_openai_fallback and self.openai_client:
            logger.warning("⚠️ Ollama summary failed → switching to OpenAI fallback...")
            try:
                fallback_summary = self.openai_client.generate(prompt)
                if fallback_summary:
                    logger.info("✅ OpenAI summary fallback succeeded.")
                    return fallback_summary.strip()
            except Exception as e:
                logger.error(f"❌ OpenAI summary fallback failed: {e}")

        logger.error("❌ Summary generation failed in both Ollama and OpenAI.")
        return None

    # ======================================================
    # CORE GENERATE
    # ======================================================
    def _generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        stream_callback=None,
        clean_sql: bool = False,
    ):
        self.metrics = getattr(self, "metrics", {"errors": 0})
        cache_key = self._make_cache_key(model, prompt)

        # Cache
        if self.enable_cache and cache_key in self._cache:
            logger.info(f"💾 Cache hit (model={model})")
            return self._cache[cache_key]

        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": stream}

        for attempt in range(1, self.max_retries + 2):
            try:
                logger.info(
                    f"🔗 Calling Ollama (model={model}, attempt={attempt}, stream={stream})"
                )

                resp = requests.post(
                    url, json=payload, timeout=self.timeout, stream=stream
                )
                resp.raise_for_status()

                if stream:
                    raw = self._parse_streaming_response(resp, stream_callback)
                else:
                    raw = self._parse_non_streaming(resp)

                if not raw:
                    logger.warning("⚠️ Ollama returned empty → retrying...")
                    continue

                cleaned = self._postprocess(raw, clean_sql)
                if cleaned:
                    if self.enable_cache:
                        self._cache[cache_key] = cleaned
                    return cleaned

            except Exception as e:
                logger.error(
                    f"❌ Ollama error on attempt {attempt}: {e}", exc_info=False
                )
                self.metrics["errors"] += 1
                if attempt <= self.max_retries:
                    time.sleep(self.retry_delay)

        return None

    # ======================================================
    # RESPONSE PARSING
    # ======================================================
    def _parse_streaming_response(self, resp, stream_callback):
        final = ""
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
            except:
                continue

            chunk = data.get("response") or data.get("text") or ""
            if chunk:
                final += chunk
                if stream_callback:
                    stream_callback(chunk)

        return final.strip()

    def _parse_non_streaming(self, resp):
        try:
            data = resp.json()
        except:
            return ""
        return (data.get("response") or data.get("text") or "").strip()

    # ======================================================
    # POSTPROCESS
    # ======================================================
    def _postprocess(self, text: str, clean_sql: bool) -> str:
        if not text:
            return ""
        if clean_sql:
            return self._clean_sql(text)
        return text.strip()

    def _clean_sql(self, raw: str) -> str:
        """Extracts real SQL from LLM output."""
        txt = raw.strip()

        # Remove ```sql fences
        txt = re.sub(r"```sql|```", "", txt, flags=re.IGNORECASE)

        # Keep only the part starting with SELECT/WITH/UPDATE/etc
        match = re.search(
            r"(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE)[\s\S]*", txt, re.IGNORECASE
        )
        if match:
            txt = match.group(0)

        # Remove GO
        txt = re.sub(r"\bGO\b", "", txt, flags=re.IGNORECASE)

        return txt.strip()

    # ======================================================
    # UTILITIES
    # ======================================================
    def _make_cache_key(self, model, prompt):
        return hashlib.md5(f"{model}||{prompt}".encode()).hexdigest()


# Singleton helper
_OLLAMA_SINGLETON = None


def get_default_ollama_client():
    global _OLLAMA_SINGLETON
    if _OLLAMA_SINGLETON is None:
        _OLLAMA_SINGLETON = OllamaClient()
    return _OLLAMA_SINGLETON
