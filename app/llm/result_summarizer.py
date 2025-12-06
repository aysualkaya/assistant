# app/llm/result_summarizer.py
"""
Executive-Only Business Summary Generator (2025)
Always produces C-Level English summaries.
SQL → Insight → Interpretation → Strategic Impact → Actions
"""

from typing import Dict, List, Optional
import json

from app.llm.ollama_client import OllamaClient
from app.llm.openai_client import OpenAIClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


# -------------------------------------------------------------------------
# GLOBAL EXECUTIVE SUMMARY PROMPT (ALWAYS ENGLISH)
# -------------------------------------------------------------------------
EXECUTIVE_SUMMARY_PROMPT = """
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
        if "sql" in clean.lower():
            return False
        return True

    # ------------------------------------------------------------------
    # Fallback summary
    # ------------------------------------------------------------------
    def _fallback_summary(self, results: List[Dict]) -> str:
        sample = results[0]
        return f"""
📊 Executive Summary (Fallback)

The system could not generate a full summary.  
Here is a preview of the first row of data:

{sample}
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
        execution_time: Optional[float] = None
    ) -> str:

        logger.info("📊 Generating executive business summary (EN-only)...")

        if not query_results:
            return "❌ No results found."

        # Create preview for the LLM
        preview = json.dumps(query_results[:5], indent=2, ensure_ascii=False)

        # Build final prompt
        final_prompt = (
            EXECUTIVE_SUMMARY_PROMPT
            + "\n\nUser Question:\n"
            + user_question
            + "\n\nResult Preview:\n"
            + preview
            + "\n\nGenerate the executive summary now:"
        )

        # Call Ollama
        result = self.ollama.generate_summary(final_prompt)

        # If needed → fallback to OpenAI (disabled when no key)
        if not self._is_valid_summary(result):
            logger.warning("⚠️ Ollama summary weak → trying OpenAI fallback...")
            if self.openai.enabled:
                result = self.openai.generate(final_prompt)

        # If both fail → fallback summary
        if not self._is_valid_summary(result):
            logger.error("❌ Summary failed → Using fallback.")
            return self._fallback_summary(query_results)

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
