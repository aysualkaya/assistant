"""
Executive Business Summary Generator (2025, Final Production Edition)

Enhancements:
✔ Uses PromptManager public detect_language()
✔ ORDER BY ASC/DESC integrated for both TR + EN
✔ OpenAI fallback for high-quality summaries
✔ Cleaner prompts and consistent formatting
✔ Safe fallback summaries
"""

from typing import Dict, List, Optional
import json

from app.llm.ollama_client import OllamaClient
from app.llm.openai_client import OpenAIClient
from app.llm.prompt_manager import PromptManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


# -------------------------------------------------------------------
# English Executive Prompt
# -------------------------------------------------------------------
EXEC_SUMMARY_PROMPT_EN = """
You are an AI Business Analyst generating an EXECUTIVE SUMMARY
for senior decision-makers.

Your writing must be:
- fully in English
- business-oriented
- based only on the provided data
- concise (max 150 words)
- actionable and insight-driven

STRUCTURE:
1. Key Insight  
2. Business Interpretation  
3. Strategic Impact  
4. Recommended Actions  

Avoid:
- mentioning SQL or technical operations  
- inventing numbers  
- unjustified speculation  
"""


class ResultSummarizer:

    def __init__(self):
        self.ollama = OllamaClient()
        self.openai = OpenAIClient()
        self.prompt_manager = PromptManager()

    # ---------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------
    def _is_valid(self, text: Optional[str]) -> bool:
        if not text:
            return False
        t = text.strip()
        if len(t) < 40:
            return False
        if "error" in t.lower():
            return False
        return True

    # ---------------------------------------------------------------
    # Fallback
    # ---------------------------------------------------------------
    def _fallback(self, results: List[Dict], lang: str) -> str:
        sample = results[0] if results else {}

        if lang == "tr":
            return f"""
📊 İş Özeti (Yedek)
Sistem detaylı bir özet üretemedi.

İlk veri satırı:
{json.dumps(sample, indent=2, ensure_ascii=False)}
""".strip()

        return f"""
📊 Executive Summary (Fallback)
The system could not generate a detailed summary.

First result row:
{json.dumps(sample, indent=2, ensure_ascii=False)}
""".strip()

    # ---------------------------------------------------------------
    # MAIN ENTRY
    # ---------------------------------------------------------------
    def summarize(
        self,
        user_question: str,
        sql_query: str,
        query_results: List[Dict],
        intent: Optional[Dict] = None,
        execution_time: Optional[float] = None,
        language: Optional[str] = None
    ) -> str:

        logger.info("📊 Starting summary generation")

        if not query_results:
            return "❌ Sonuç bulunamadı." if language == "tr" else "❌ No results found."

        # Language auto-detection
        language = language or self.prompt_manager.detect_language(user_question)
        logger.info(f"🌐 Summary language resolved as: {language.upper()}")

        if language == "tr":
            return self._summary_tr(
                user_question, sql_query, query_results, intent, execution_time
            )

        return self._summary_en(
            user_question, sql_query, query_results, intent, execution_time
        )

    # ---------------------------------------------------------------
    # TURKISH SUMMARY
    # ---------------------------------------------------------------
    def _summary_tr(
        self,
        question: str,
        sql: str,
        results: List[Dict],
        intent: Optional[Dict],
        exec_time: Optional[float],
    ) -> str:

        logger.info("🇹🇷 Generating Turkish summary...")

        # Build TR summary prompt via PromptManager
        prompt = self.prompt_manager.build_summary_prompt(
            question=question,
            sql=sql,
            results=results,
            intent=intent
        )

        summary = self.ollama.generate_summary(prompt)

        # OpenAI fallback
        if not self._is_valid(summary):
            logger.warning("⚠️ Ollama TR summary weak → OpenAI fallback...")
            if self.openai.enabled:
                summary = self.openai.generate(prompt)

        if not self._is_valid(summary):
            logger.error("❌ TR summary failed — fallback applied.")
            return self._fallback(results, "tr")

        if exec_time:
            summary += f"\n\n⏱️ Sorgu süresi: {exec_time:.2f} saniye"

        return summary.strip()

    # ---------------------------------------------------------------
    # ENGLISH SUMMARY
    # ---------------------------------------------------------------
    def _summary_en(
        self,
        question: str,
        sql: str,
        results: List[Dict],
        intent: Optional[Dict],
        exec_time: Optional[float],
    ) -> str:

        logger.info("🇬🇧 Generating English executive summary...")

        # ORDER BY direction from PromptManager (public-safe)
        direction = self.prompt_manager._detect_order_direction(sql)
        ranking_hint = ""

        if intent and intent.get("query_type") == "ranking":
            if direction == "ASC":
                ranking_hint = "\nNOTE: These results represent the LOWEST performers.\n"
            elif direction == "DESC":
                ranking_hint = "\nNOTE: These results represent the TOP performers.\n"

        preview = json.dumps(results[:10], indent=2, ensure_ascii=False)

        # EXECUTIVE PROMPT
        prompt = (
            EXEC_SUMMARY_PROMPT_EN
            + ranking_hint
            + "\nUser Question:\n"
            + question
            + "\n\nData Preview:\n"
            + preview
            + "\n\nGenerate the summary now:"
        )

        summary = self.ollama.generate_summary(prompt)

        # OpenAI fallback
        if not self._is_valid(summary):
            logger.warning("⚠️ Ollama EN summary weak → OpenAI fallback...")
            if self.openai.enabled:
                summary = self.openai.generate(prompt)

        if not self._is_valid(summary):
            logger.error("❌ EN summary failed — fallback applied.")
            return self._fallback(results, "en")

        if exec_time:
            summary += f"\n\n⏱️ Execution Time: {exec_time:.2f} seconds"

        return summary.strip()


# Singleton
_summarizer = None

def get_result_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = ResultSummarizer()
    return _summarizer
