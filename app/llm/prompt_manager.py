# app/llm/prompt_manager.py 
"""
Prompt Manager — 2025 Production Edition
Multilingual (TR + EN)
SQL-only output enforced
Schema-aware (OpenAI = compact, Ollama = detailed)
Direct / Few-shot / Correction strategies
ORDER BY direction detection
"""

from typing import Dict, List, Optional
from app.core.schema_builder import DynamicSchemaBuilder
from app.utils.logger import get_logger
import re
import json

logger = get_logger(__name__)


class PromptManager:

    def __init__(self):
        # Schema builder used for LLM-side schema hints
        self.schema_builder = DynamicSchemaBuilder()

    # ============================================================
    #  PUBLIC LANGUAGE DETECTION (required by ResultSummarizer)
    # ============================================================
    def detect_language(self, text: str) -> str:
        """Public wrapper so summarizer can call it safely."""
        return self._detect_language(text)

    # INTERNAL LANGUAGE DETECTION
    def _detect_language(self, text: str) -> str:
        if not text:
            return "en"

        t = text.lower()
        tr_markers = [
            "ş", "ı", "ğ", "ü", "ö", "ç",
            "hangi", "neden", "ürün", "urun",
            "mağaza", "magaza", "müşteri", "musteri",
            "satış", "satis", "ciro"
        ]
        return "tr" if any(m in t for m in tr_markers) else "en"

    # ============================================================
    # MAIN SQL PROMPT BUILDER
    # ============================================================
    def build_sql_prompt(
        self,
        question: str,
        intent: Dict,
        strategy: str,
        examples: Optional[List[Dict]] = None,
        error_context: Optional[str] = None,
        llm_mode: str = "ollama",
        extra_schema: Optional[str] = None,
    ) -> str:

        # LLM-specific schema mode
        schema_mode = "openai" if llm_mode == "openai" else "ollama"

        # TemplateRouter → Intent-first pipeline ile gelen intent’e göre tablo çıkarımı
        tables = self._infer_tables(question, intent)

        # Schema extraction
        schema_text = self.schema_builder.build_schema_context(
            tables_needed=tables,
            mode=schema_mode,
        )

        if extra_schema:
            schema_text += f"\n\n{extra_schema}"

        lang = self.detect_language(question)

        if lang == "tr":
            system_block = """
Uzman bir SQL Server mühendisisin.
Kullanıcı sorusunu TEK bir geçerli SQL sorgusuna dönüştür.

KURALLAR:
- Yalnızca şemada verilen tabloları ve kolonları kullan.
- Tarih filtrelerinde DimDate üzerinden CalendarYear/Month kullan.
- YEAR(DateKey) kullanma.
- LIMIT kullanma (SQL Server desteklemez).
- Sıralama sorularında SELECT TOP N + ORDER BY kullan.
- ÇIKTI yalnızca SQL olacak.
"""
        else:
            system_block = """
You are an expert SQL Server engineer.
Convert the user question into ONE valid SQL query.

RULES:
- Use ONLY the schema provided.
- Always join DimDate for year/month filtering.
- Never use YEAR(DateKey).
- Never use LIMIT (not supported in SQL Server).
- Ranking queries REQUIRE SELECT TOP N + ORDER BY.
- Output MUST be SQL only.
"""

        strategy_block = self._strategy_block(
            strategy=strategy,
            examples=examples,
            error_context=error_context,
        )

        query_type = intent.get("query_type", "aggregation")
        complexity = intent.get("complexity", 5)

        prompt = (
            system_block
            + "\n\nUSER QUESTION:\n"
            + question
            + "\n\nINTENT:\n"
            + f"- type: {query_type}\n- complexity: {complexity}\n\n"
            + "SCHEMA CONTEXT:\n"
            + schema_text
            + "\n\n"
            + strategy_block
            + "\n\nRETURN ONLY SQL."
        )

        return prompt

    # ============================================================
    # STRATEGY BLOCK BUILDER
    # ============================================================
    def _strategy_block(self, strategy: str, examples, error_context):
        if strategy == "direct":
            return "STRATEGY: Generate a final SQL query only."

        if strategy == "few_shot":
            txt = "STRATEGY: Follow the example SQL patterns below. Return ONLY SQL.\n"
            if examples:
                for ex in examples:
                    if ex.get("sql"):
                        txt += f"\nExample SQL:\n{ex['sql']}\n"
            return txt

        if strategy == "correction":
            return (
                "STRATEGY: Correct the SQL entirely. Output a valid T-SQL query.\n\n"
                f"ERROR CONTEXT:\n{error_context or ''}"
            )

        return "STRATEGY: Produce a single final SQL query."

    # ============================================================
    # TABLE INFERENCE
    # ============================================================
    def _infer_tables(self, question: str, intent: Dict) -> List[str]:
        q = question.lower()
        tables = ["FactSales", "DimDate"]

        if any(k in q for k in ["online", "web", "internet"]):
            tables.append("FactOnlineSales")

        if any(k in q for k in ["ürün", "urun", "product", "kategori", "category"]):
            tables += ["DimProduct", "DimProductSubcategory", "DimProductCategory"]

        if any(k in q for k in ["mağaza", "magaza", "store"]):
            tables.append("DimStore")

        if any(k in q for k in ["müşteri", "musteri", "customer"]):
            tables.append("DimCustomer")

        return list(dict.fromkeys(tables))

    # ============================================================
    # ORDER BY DETECTION
    # ============================================================
    def _detect_order_direction(self, sql: str) -> str:
        m = re.search(r"ORDER\s+BY\s+\S+\s+(ASC|DESC)", sql, re.IGNORECASE)
        if m:
            return m.group(1).upper()

        if "ORDER BY" in sql.upper():
            return "ASC"

        return "UNKNOWN"

    # ============================================================
    # SUMMARY PROMPT BUILDER
    # ============================================================
    def build_summary_prompt(self, question, sql, results, intent=None):

        lang = self.detect_language(question)
        results_json = json.dumps(results[:10], indent=2, ensure_ascii=False)

        ranking_note = ""
        if intent and intent.get("query_type") == "ranking":
            direction = self._detect_order_direction(sql)
            if lang == "tr":
                ranking_note = (
                    "(Bu liste EN DÜŞÜK değerleri gösteriyor.)"
                    if direction == "ASC"
                    else "(Bu liste EN YÜKSEK değerleri gösteriyor.)"
                )
            else:
                ranking_note = (
                    "(This list shows LOWEST performers.)"
                    if direction == "ASC"
                    else "(This list shows TOP performers.)"
                )

        if lang == "tr":
            instructions = """
Türkçe profesyonel bir iş özeti yaz.
- En fazla 150 kelime
- Sayısal bulguları kullan
- İş etkisini açıkla
- Sıralama varsa (ASC/DESC) doğru yorumla
"""
        else:
            instructions = """
Write a professional business summary in English.
- Max 150 words
- Use numerical insights
- Explain business impact
- Use correct ranking interpretation
"""

        return f"""
USER QUESTION:
{question}

SQL EXECUTED:
{sql}

RESULTS (first 10 rows):
{results_json}

{ranking_note}

{instructions}

Write the summary now:
"""
