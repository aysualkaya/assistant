# app/llm/result_summarizer.py
"""
Auto-Language Executive BI Result Summarizer
Produces highly professional business summaries based on LLM output.
- Detects user question language (TR/EN)
- Generates 4-part Executive Summary
- Adds BI tone and structure (McKinsey/BCG style)
- Works for any result set (comparison, ranking, trend, aggregate, etc.)
"""

from typing import Dict, List, Optional
import json
from app.llm.ollama_client import OllamaClient
from app.llm.prompt_manager import PromptManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResultSummarizer:
    def __init__(self):
        self.llm = OllamaClient()
        self.prompt_manager = PromptManager()

    # -------------------------------------------------------------
    # LANGUAGE DETECTION
    # -------------------------------------------------------------
    def _detect_language(self, text: str) -> str:
        """
        Very lightweight language detection:
        - If text contains Turkish-specific characters -> TR
        - Else -> EN (default)
        """
        turkish_chars = "ğĞüÜşŞıİöÖçÇ"
        if any(c in text for c in turkish_chars):
            return "TR"
        return "EN"

    # -------------------------------------------------------------
    # MAIN SUMMARIZE FUNCTION
    # -------------------------------------------------------------
    def summarize(
        self,
        user_question: str,
        sql_query: str,
        query_results: List[Dict],
        intent: Optional[Dict] = None,
        execution_time: Optional[float] = None
    ) -> str:
        logger.info("📊 Generating executive business summary...")

        # Handle empty or error
        if isinstance(query_results, dict) and "error" in query_results:
            return f"❌ SQL Error: {query_results['error']}"
        if not query_results:
            return "❌ No results found for this query."

        # Detect language
        lang = self._detect_language(user_question)

        # Build BI executive prompt
        prompt = self._build_executive_prompt(
            question=user_question,
            sql_query=sql_query,
            results=query_results,
            intent=intent,
            lang=lang
        )

        # Run LLM
        try:
            response = self.llm.generate_summary(prompt)

            if not response or len(response.strip()) < 25:
                logger.warning("⚠️ Weak summary from LLM, using fallback.")
                return self._fallback_summary(query_results, lang)

            # Add execution time
            if execution_time:
                if lang == "TR":
                    response += f"\n\n⏱️ Sorgu süresi: {execution_time:.2f} saniye"
                else:
                    response += f"\n\n⏱️ Execution time: {execution_time:.2f} seconds"

            return response.strip()

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return self._fallback_summary(query_results, lang)

    # -------------------------------------------------------------
    # EXECUTIVE PROMPT BUILDER
    # -------------------------------------------------------------
    def _build_executive_prompt(
        self,
        question: str,
        sql_query: str,
        results: List[Dict],
        intent: Dict,
        lang: str
    ) -> str:

        results_preview = json.dumps(results[:5], indent=2, ensure_ascii=False)

        if lang == "TR":
            return f"""
Sen bir **Business Intelligence Executive Analyst** olarak davranıyorsun.

Görevin: SQL sorgusunun sonuçlarını üst düzey yöneticilere sunulan bir rapor gibi analiz etmek.

Aşağıdaki formatı KESİNLİKLE kullan:

1. **Ana Bulgular**
2. **Yorumlama**
3. **İş Etkisi**
4. **Önerilen Aksiyonlar**

Kurumsal ve profesyonel Türkçe kullan.
Abartılı cümle yok, sade ve iş odaklı.

Soru:
{question}

SQL:
{sql_query}

Sonuç Önizlemesi:
{results_preview}

Lütfen yalnızca profesyonel özet üret:
"""

        else:  # English
            return f"""
You are acting as a **Business Intelligence Executive Analyst**.

Your task is to interpret SQL query results and generate an executive-level summary.

STRICT FORMAT (mandatory):

1. **Key Findings**
2. **Interpretation**
3. **Business Impact**
4. **Recommended Actions**

Use clear, concise, corporate English (McKinsey/BCG style).

Question:
{question}

SQL:
{sql_query}

Result Preview:
{results_preview}

Generate ONLY the executive summary:
"""

    # -------------------------------------------------------------
    # FALLBACK SUMMARY (IF LLM FAILS)
    # -------------------------------------------------------------
    def _fallback_summary(self, results: List[Dict], lang: str) -> str:
        first = results[0]

        if lang == "TR":
            return f"""
📊 **Özet Bilgi (Fallback)**  
İlk satır örneği: {first}

LLM özeti üretilemediği için temel önizleme sunulmuştur.
"""
        else:
            return f"""
📊 **Basic Summary (Fallback)**  
Sample row: {first}

LLM summary failed; showing basic preview.
"""


# Singleton
_summarizer_instance = None

def get_result_summarizer() -> ResultSummarizer:
    global _summarizer_instance
    if _summarizer_instance is None:
        _summarizer_instance = ResultSummarizer()
    return _summarizer_instance
