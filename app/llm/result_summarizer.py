# app/llm/result_summarizer.py
"""
Executive Business Summary Generator (2025, Final Production Edition)

Enhancements:
✔ TR/EN full auto-detection (via PromptManager public API)
✔ ORDER BY ASC/DESC direction included in both languages
✔ OpenAI fallback for both TR + EN
✔ Strong validation
✔ More informative fallback summaries
"""

from typing import Dict, List, Optional
import json

from app.llm.ollama_client import OllamaClient
from app.llm.openai_client import OpenAIClient
from app.llm.prompt_manager import PromptManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


# -------------------------------------------------------------------
# Executive BI Prompt (English)
# -------------------------------------------------------------------
EXEC_SUMMARY_PROMPT_EN = """
You are an AI Business Analyst generating a concise EXECUTIVE SUMMARY
for senior business leaders.

Your writing MUST be:
- fully in English
- based ONLY on the query results
- business-oriented
- max 150 words
- insightful and actionable

STRUCTURE:
1. Key Insight  
2. Business Interpretation  
3. Strategic Impact  
4. Recommended Actions

Do NOT:
- mention SQL or technical details
- invent numbers
- speculate beyond the results
"""


class ResultSummarizer:

    def __init__(self):
        self.ollama = OllamaClient()
        self.openai = OpenAIClient()
        self.prompt_manager = PromptManager()

    # ---------------------------------------------------------------
    # VALIDATION
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
    # FALLBACK SUMMARY (IMPROVED)
    # ---------------------------------------------------------------
    def _fallback(self, results: List[Dict], lang: str) -> str:
        sample = results[0] if results else {}

        if lang == "tr":
            return f"""
📊 İş Özeti (Yedek)
Sistem detaylı bir özet üretemedi. 
Aşağıda ilk veri satırı bulunmaktadır:

{json.dumps(sample, indent=2, ensure_ascii=False)}
""".strip()

        return f"""
📊 Executive Summary (Fallback)
The system could not produce a full summary.
Below is the first data row for reference:

{json.dumps(sample, indent=2, ensure_ascii=False)}
""".strip()

    # ---------------------------------------------------------------
    # MAIN ENTRY POINT
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

        # Determine language
        if language is None:
            language = self.prompt_manager.detect_language(user_question)

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
        exec_time: Optional[float]
    ) -> str:

        logger.info("🇹🇷 Generating Turkish summary...")

        prompt = self.prompt_manager.build_summary_prompt(
            question=question,
            sql=sql,
            results=results,
            intent=intent
        )

        summary = self.ollama.generate_summary(prompt)

        if not self._is_valid(summary):
            logger.warning("⚠️ Ollama TR summary weak → trying OpenAI fallback...")
            if self.openai.enabled:
                summary = self.openai.generate(prompt)

        if not self._is_valid(summary):
            logger.error("❌ Turkish summary failed — fallback used")
            return self._fallback(results, "tr")

        if exec_time:
            summary += f"\n\n⏱️ Sorgu süresi: {exec_time:.2f} saniye"

        return summary.strip()

    # ---------------------------------------------------------------
    # ENGLISH SUMMARY (EXECUTIVE + ORDER-BY LOGIC)
    # ---------------------------------------------------------------
    def _summary_en(
        self,
        question: str,
        sql: str,
        results: List[Dict],
        intent: Optional[Dict],
        exec_time: Optional[float]
    ) -> str:

        logger.info("🇬🇧 Generating English executive summary...")

        # Determine ranking direction
        order_dir = self.prompt_manager._detect_order_direction(sql)
        ranking_hint = ""

        if intent and intent.get("query_type") == "ranking":
            if order_dir == "ASC":
                ranking_hint = "\nNOTE: These results represent the LOWEST performers.\n"
            elif order_dir == "DESC":
                ranking_hint = "\nNOTE: These results represent the TOP performers.\n"

        preview = json.dumps(results[:10], indent=2, ensure_ascii=False)

        prompt = (
            EXEC_SUMMARY_PROMPT_EN
            + ranking_hint
            + "\nUser Question:\n"
            + question
            + "\n\nResult Preview:\n"
            + preview
            + "\n\nGenerate the executive summary now:"
        )

        summary = self.ollama.generate_summary(prompt)

        if not self._is_valid(summary):
            logger.warning("⚠️ Ollama EN summary weak → trying OpenAI fallback...")
            if self.openai.enabled:
                summary = self.openai.generate(prompt)

        if not self._is_valid(summary):
            logger.error("❌ English summary failed — fallback used")
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
