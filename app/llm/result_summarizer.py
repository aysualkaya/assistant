# app/llm/result_summarizer.py
"""
Executive Business Summary Generator (2025)
- Supports both English and Turkish summaries
- ORDER BY direction detection for accurate ranking interpretation
- Professional BI-style executive summaries
SQL → Insight → Interpretation → Strategic Impact → Actions
"""

from typing import Dict, List, Optional
import json

from app.llm.ollama_client import OllamaClient
from app.llm.openai_client import OpenAIClient
from app.llm.prompt_manager import PromptManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


# -------------------------------------------------------------------------
# EXECUTIVE SUMMARY PROMPT (English - Legacy for backward compatibility)
# -------------------------------------------------------------------------
EXECUTIVE_SUMMARY_PROMPT_EN = """
You are an AI Business Analyst generating an EXECUTIVE SUMMARY 
for C-Level leaders (CEO, CFO, COO).

Your writing MUST be:
- clear, fluent, and fully in English
- concise and business-oriented
- strictly based on the SQL results (do NOT invent numbers)
- strategic and actionable

Avoid:
- technical descriptions (SQL, fields, joins, tables)
- academic tone
- redundant explanations
- mixed languages
- storytelling or fictional assumptions

STRUCTURE:
1. Key Insight  
   - State the main outcome directly.

2. Business Interpretation  
   - What does this tell us about performance, customers, profitability, or operations?

3. Strategic Impact  
   - How does this insight influence business decisions, growth, or competitive advantage?

4. Recommended Actions  
   - Provide 2–4 realistic, high-impact actions executives can take.

Your entire response must remain strictly within this structure 
and must not make up any data beyond what is in the result preview.
"""


class ResultSummarizer:

    def __init__(self):
        self.ollama = OllamaClient()
        self.openai = OpenAIClient()
        self.prompt_manager = PromptManager()  # NEW: For Turkish summaries with ORDER BY detection

    # ------------------------------------------------------------------
    # Language Detection
    # ------------------------------------------------------------------
    def _detect_language(self, question: str) -> str:
        """
        Detect if question is in Turkish or English
        
        Args:
            question: User's question
            
        Returns:
            'tr' for Turkish, 'en' for English
        """
        # Turkish-specific characters and common words
        turkish_indicators = [
            'ü', 'ğ', 'ş', 'ı', 'ö', 'ç',  # Special characters
            'nedir', 'hangisi', 'kaç', 'toplam', 'satış', 'ürün',  # Common words
            'mağaza', 'müşteri', 'yıl', 'ay', 'karşılaştırma'
        ]
        
        question_lower = question.lower()
        
        # Count Turkish indicators
        turkish_count = sum(1 for indicator in turkish_indicators if indicator in question_lower)
        
        # If 2+ Turkish indicators found, assume Turkish
        return 'tr' if turkish_count >= 2 else 'en'

    # ------------------------------------------------------------------
    # Summary validation
    # ------------------------------------------------------------------
    def _is_valid_summary(self, text: Optional[str]) -> bool:
        if not text:
            return False
        clean = text.strip()
        if len(clean) < 40:
            return False
        if "error" in clean.lower():
            return False
        # Don't reject if "sql" appears in context (e.g., "SQL results show...")
        return True

    # ------------------------------------------------------------------
    # Fallback summary
    # ------------------------------------------------------------------
    def _fallback_summary(self, results: List[Dict], language: str = 'en') -> str:
        """
        Generate a simple fallback summary when LLM fails
        
        Args:
            results: Query results
            language: 'en' or 'tr'
            
        Returns:
            Simple summary string
        """
        sample = results[0] if results else {}
        
        if language == 'tr':
            return f"""
📊 İş Özeti (Yedek)

Sistem tam özet oluşturamadı.  
İlk satır verisi:

{json.dumps(sample, indent=2, ensure_ascii=False)}
"""
        else:
            return f"""
📊 Executive Summary (Fallback)

The system could not generate a full summary.  
Here is a preview of the first row of data:

{json.dumps(sample, indent=2, ensure_ascii=False)}
"""

    # ------------------------------------------------------------------
    # Main Summary Function
    # ------------------------------------------------------------------
    def summarize(
        self,
        user_question: str,
        sql_query: str,
        query_results: List[Dict],
        intent: Optional[Dict] = None,
        execution_time: Optional[float] = None,
        language: Optional[str] = None  # NEW: Optional language override
    ) -> str:
        """
        Generate executive business summary with ORDER BY detection
        
        Args:
            user_question: User's original question
            sql_query: Executed SQL query
            query_results: Query results
            intent: Intent classification (includes query_type)
            execution_time: Query execution time
            language: Force language ('en' or 'tr'), auto-detect if None
            
        Returns:
            Executive summary text
        """
        logger.info("📊 Generating executive business summary...")

        if not query_results:
            return "❌ Sonuç bulunamadı." if language == 'tr' else "❌ No results found."

        # Auto-detect language if not specified
        if language is None:
            language = self._detect_language(user_question)
            logger.info(f"🌐 Auto-detected language: {language.upper()}")

        # Use PromptManager for Turkish summaries (with ORDER BY detection)
        if language == 'tr':
            return self._generate_turkish_summary(
                user_question, sql_query, query_results, intent, execution_time
            )
        else:
            return self._generate_english_summary(
                user_question, sql_query, query_results, intent, execution_time
            )

    # ------------------------------------------------------------------
    # Turkish Summary (uses PromptManager with ORDER BY detection)
    # ------------------------------------------------------------------
    def _generate_turkish_summary(
        self,
        user_question: str,
        sql_query: str,
        query_results: List[Dict],
        intent: Optional[Dict],
        execution_time: Optional[float]
    ) -> str:
        """
        Generate Turkish summary using PromptManager (includes ORDER BY detection)
        """
        logger.info("🇹🇷 Generating Turkish summary with ORDER BY detection...")

        # Use PromptManager to build summary prompt (handles ORDER BY detection)
        prompt = self.prompt_manager.build_summary_prompt(
            question=user_question,
            sql=sql_query,
            results=query_results,
            intent=intent
        )

        # Call Ollama
        result = self.ollama.generate_summary(prompt)

        # Validate
        if not self._is_valid_summary(result):
            logger.warning("⚠️ Ollama Turkish summary weak → trying OpenAI fallback...")
            if self.openai.enabled:
                result = self.openai.generate(prompt)

        # If both fail → fallback
        if not self._is_valid_summary(result):
            logger.error("❌ Turkish summary failed → Using fallback.")
            return self._fallback_summary(query_results, language='tr')

        # Add execution time footer
        if execution_time:
            result += f"\n\n⏱️ Sorgu süresi: {execution_time:.2f} saniye"

        return result.strip()

    # ------------------------------------------------------------------
    # English Summary (Legacy executive style)
    # ------------------------------------------------------------------
    def _generate_english_summary(
        self,
        user_question: str,
        sql_query: str,
        query_results: List[Dict],
        intent: Optional[Dict],
        execution_time: Optional[float]
    ) -> str:
        """
        Generate English executive summary (legacy style)
        """
        logger.info("🇬🇧 Generating English executive summary...")

        # Create preview for the LLM
        preview = json.dumps(query_results[:5], indent=2, ensure_ascii=False)

        # Build final prompt
        final_prompt = (
            EXECUTIVE_SUMMARY_PROMPT_EN
            + "\n\nUser Question:\n"
            + user_question
            + "\n\nResult Preview:\n"
            + preview
            + "\n\nGenerate the executive summary now:"
        )

        # Call Ollama
        result = self.ollama.generate_summary(final_prompt)

        # If needed → fallback to OpenAI
        if not self._is_valid_summary(result):
            logger.warning("⚠️ Ollama English summary weak → trying OpenAI fallback...")
            if self.openai.enabled:
                result = self.openai.generate(final_prompt)

        # If both fail → fallback summary
        if not self._is_valid_summary(result):
            logger.error("❌ English summary failed → Using fallback.")
            return self._fallback_summary(query_results, language='en')

        # Add execution time footer
        if execution_time:
            result += f"\n\n⏱️ Execution Time: {execution_time:.2f} seconds"

        return result.strip()


# Singleton accessor
_summarizer = None

def get_result_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = ResultSummarizer()
    return _summarizer