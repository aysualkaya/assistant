# app/llm/sql_generator.py 
"""
Dynamic SQL Generator — FINAL PRODUCTION VERSION (2025)

Features:
- Template engine (TR + EN question shortcuts)
- Schema-aware LLM SQL generation (Ollama → OpenAI fallback)
- LangChain SQL tools (list_tables, get_schema, check_sql)
- Custom SQL validator
- SQL normalizer with fuzzy-table correction
- Self-correction with schema preservation
"""

from typing import Dict, Optional, List, Any
import re

from app.core.intent_classifier import IntentClassifier
from app.core.config import Config
from app.llm.ollama_client import OllamaClient
from app.llm.openai_client import OpenAIClient
from app.llm.prompt_manager import PromptManager
from app.database.query_validator import QueryValidator
from app.database.sql_normalizer import get_sql_normalizer
from app.memory.query_logger import QueryLogger
from app.utils.logger import get_logger

# TEMPLATE ENGINE
from app.llm.templates import (
    template_top_products,
    template_bottom_products,
    template_total_sales,
    template_monthly_trend,
    template_store_vs_online,
)

# LangChain-based SQL tools
from app.tools.sql_tools import (
    list_tables,
    get_schema,
    check_sql,
)

logger = get_logger(__name__)


class SQLGenerationError(Exception):
    pass


class DynamicSQLGenerator:

    def __init__(self):
        self.ollama = OllamaClient()
        self.openai = OpenAIClient()

        self.intent_classifier = IntentClassifier()
        self.prompt_manager = PromptManager()
        self.validator = QueryValidator()
        self.normalizer = get_sql_normalizer()
        self.query_logger = QueryLogger()

    # =====================================================================
    # FAST PATH TEMPLATE ENGINE
    # =====================================================================
    def _infer_limit(self, question: str, default: int = 5) -> int:
        q = question.lower()
        m = re.search(r"\b(\d+)\b", q)
        if m:
            return int(m.group(1))
        return default

    def _extract_year(self, q: str) -> Optional[int]:
        m = re.search(r"(20\d{2})", q)
        return int(m.group(1)) if m else None

    def _template_shortcuts(self, question: str) -> Optional[str]:
        """
        Fast deterministic answers, covering both Turkish + English wording.
        """
        q = question.lower()

        # TOP PRODUCTS
        if any(k in q for k in ["en çok satan", "en cok satan", "top seller", "most sold", "top selling"]):
            return template_top_products(limit=self._infer_limit(question))

        # BOTTOM PRODUCTS
        if any(k in q for k in ["en az satan", "least selling", "worst sellers", "lowest selling"]):
            return template_bottom_products(limit=self._infer_limit(question))

        # TOTAL SALES
        if any(k in q for k in ["toplam satış", "toplam satis", "total sales"]):
            return template_total_sales(self._extract_year(q))

        # MONTHLY TREND
        if any(k in q for k in ["aylık", "aylik", "monthly trend"]):
            year = self._extract_year(q)
            if year:
                return template_monthly_trend(year)

        # STORE vs ONLINE
        if any(k in q for k in ["mağaza", "magaza", "store"]) and "online" in q:
            return template_store_vs_online(self._extract_year(q))

        return None

    # =====================================================================
    # MAIN SQL GENERATION PIPELINE
    # =====================================================================
    def generate_sql(
        self,
        question: str,
        max_attempts: int = 2,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:

        logger.info(f"🔍 Generating SQL for: {question}")

        # 1) TEMPLATE ENGINE
        t = self._template_shortcuts(question)
        if t:
            logger.info("⚡ Using TEMPLATE ENGINE")
            return t

        # 2) INTENT
        if user_context and "intent" in user_context:
            intent = user_context["intent"]
            logger.info("🎯 Using intent from user_context")
        else:
            intent = self.intent_classifier.classify(question)
            logger.info(f"🎯 Classified intent: {intent}")

        strategy = self._select_strategy(intent)

        # 3) LangChain schema
        logger.info("📘 Fetching LangChain schema...")
        tables_list, schema_info = self._load_langchain_schema()

        # 4) Primary LLM Loop (Ollama → OpenAI fallback)
        last_sql = None
        last_errors = []

        for attempt in range(max_attempts):
            logger.info(f"📌 LLM attempt {attempt+1}/{max_attempts}")

            prompt = self.prompt_manager.build_sql_prompt(
                question=question,
                intent=intent,
                strategy=strategy,
                llm_mode="ollama",
                examples=None,
                error_context=None,
                extra_schema=schema_info  # unified schema injection
            )

            # Try Ollama first
            raw = self.ollama.generate_sql(prompt)
            if not raw:
                logger.warning("⚠️ Ollama empty response → try OpenAI")
                raw = self.openai.generate_sql(prompt)

            if not raw:
                continue

            sql = self._extract_sql(raw)
            sql = self.normalizer.normalize(sql)

            # LangChain validation
            sql = self._apply_check_sql(sql)

            ok, errors = self.validator.validate(sql, intent)
            critical = [e for e in errors if e.startswith("ERROR")]

            last_sql = sql
            last_errors = critical or errors

            if not critical:
                logger.info("✅ VALID SQL")
                self.query_logger.log_query(question, sql, intent, "llm", True)
                return sql

            logger.warning(f"⚠️ SQL invalid: {errors}")

        # 5) Self-correction stage
        logger.warning("🔁 Entering self-correction...")
        corrected = self._self_correct(question, last_sql, last_errors, intent, schema_info)

        if corrected:
            return corrected

        raise SQLGenerationError("Unable to generate valid SQL.")

    # =====================================================================
    # LangChain Schema Loader
    # =====================================================================
    def _load_langchain_schema(self):
        try:
            tables_raw = list_tables()
            if isinstance(tables_raw, str):
                tables = [t.strip() for t in tables_raw.split(",") if t.strip()]
            else:
                tables = list(tables_raw)

            chunks = []
            for t in tables:
                try:
                    chunks.append(get_schema(t))
                except Exception:
                    pass

            return tables, "\n".join(chunks)

        except Exception as e:
            logger.error(f"Schema load failed: {e}")
            return [], ""

    # =====================================================================
    # Apply LangChain check_sql
    # =====================================================================
    def _apply_check_sql(self, sql: str) -> str:
        try:
            res = check_sql(sql)

            if isinstance(res, dict):
                if "corrected_query" in res:
                    return self.normalizer.normalize(res["corrected_query"])
                if "query" in res:
                    return self.normalizer.normalize(res["query"])

            if isinstance(res, str) and "SELECT" in res.upper():
                return self.normalizer.normalize(res)

            return sql

        except Exception as e:
            logger.warning(f"check_sql failed: {e}")
            return sql

    # =====================================================================
    # SQL Extraction
    # =====================================================================
    def _extract_sql(self, text: str) -> str:
        if "EXPLANATION:" in text:
            text = text.split("EXPLANATION:", 1)[0]

        m = re.search(r"(SELECT[\s\S]*)", text, re.IGNORECASE)
        return m.group(1).strip() if m else text.strip()

    # =====================================================================
    # Self-correction
    # =====================================================================
    def _self_correct(self, question, sql, errors, intent, schema_info):
        if not sql:
            return None

        error_context = (
            f"Original SQL:\n{sql}\n\n"
            "Validation Errors:\n"
            + "\n".join(f"- {e}" for e in errors)
        )

        # LLM selection
        client = self.openai if self.openai.enabled else self.ollama
        llm_mode = "openai" if self.openai.enabled else "ollama"

        prompt = self.prompt_manager.build_sql_prompt(
            question=question,
            intent=intent,
            strategy="correction",
            error_context=error_context,
            llm_mode=llm_mode,
            extra_schema=schema_info
        )

        raw = client.generate_sql(prompt)
        if not raw:
            return None

        corrected = self._extract_sql(raw)
        corrected = self.normalizer.normalize(corrected)

        ok, new_errors = self.validator.validate(corrected, intent)
        if any(e.startswith("ERROR") for e in new_errors):
            return None

        logger.info("🔧 Self-correction succeeded.")
        self.query_logger.log_query(question, corrected, intent, "self_correct", True)
        return corrected

    # =====================================================================
    # Strategy selection
    # =====================================================================
    def _select_strategy(self, intent: Dict) -> str:
        c = intent.get("complexity", 5)
        if c <= getattr(Config, "COMPLEXITY_THRESHOLD_DIRECT", 3):
            return "direct"
        if c <= getattr(Config, "COMPLEXITY_THRESHOLD_FEW_SHOT", 6):
            return "few_shot"
        return "chain_of_thought"
