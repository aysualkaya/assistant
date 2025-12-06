# app/llm/sql_generator.py
"""
Dynamic SQL Generator — Clean Production Version (2025)

Final Pipeline:
1. Template Engine (fast path, no LLM cost)
2. Ollama LLM (primary SQL generation, schema-aware)
3. Self-correction via OpenAI 4o-mini (or Ollama) when SQL is invalid
4. Validation → Normalization → Output

- Hybrid LLM aware: PromptManager + DynamicSchemaBuilder use llm_mode
- Intent-aware prompting (direct / few-shot / chain-of-thought)
- Templates handle common Contoso questions without any LLM call
"""

from typing import Dict, Optional, List
import re

from app.core.intent_classifier import IntentClassifier
from app.core.schema_builder import DynamicSchemaBuilder
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

logger = get_logger(__name__)


class SQLGenerationError(Exception):
    """Custom error type for upstream callers (e.g., orchestrator)."""
    pass


class DynamicSQLGenerator:
    def __init__(self):
        # LLM clients
        self.ollama = OllamaClient()       # primary LLM
        self.openai = OpenAIClient()       # used only for self-correction

        # Core components
        self.intent_classifier = IntentClassifier()
        self.schema_builder = DynamicSchemaBuilder()  # used indirectly via PromptManager
        self.prompt_manager = PromptManager()
        self.validator = QueryValidator()
        self.normalizer = get_sql_normalizer()
        self.query_logger = QueryLogger()

    # -------------------------------------------------------------
    # LIMIT DETECTION
    # -------------------------------------------------------------
    def _infer_limit(self, question: str, default: int = 5) -> int:
        q = question.lower().strip()
        num_match = re.search(r"\b(\d+)\b", q)
        if num_match:
            return int(num_match.group(1))

        # “nedir / hangisi / tek ürün” → genelde tek satır
        if any(x in q for x in ["nedir", "hangisi", "tek ürün", "tek urun"]):
            return 1

        return default

    # -------------------------------------------------------------
    # YEAR DETECTION
    # -------------------------------------------------------------
    def _extract_year(self, question: str) -> Optional[int]:
        match = re.search(r"(20\d{2})", question)
        return int(match.group(1)) if match else None

    # -------------------------------------------------------------
    # TEMPLATE ENGINE LOGIC
    # -------------------------------------------------------------
    def _template_shortcuts(self, question: str) -> Optional[str]:
        """
        Fast path: common Contoso questions için hazır SQL şablonları.
        LLM maliyeti yok, tamamen deterministik.
        """
        q = question.lower()

        if "en çok satan" in q or "en cok satan" in q:
            return template_top_products(limit=self._infer_limit(question))

        if "en az satan" in q or "en az satılan" in q:
            return template_bottom_products(limit=self._infer_limit(question))

        if "toplam satış" in q or "toplam satis" in q:
            return template_total_sales(self._extract_year(question))

        if "aylık" in q or "aylik" in q:
            year = self._extract_year(question)
            if year:
                return template_monthly_trend(year)

        if ("mağaza" in q or "magaza" in q) and "online" in q:
            return template_store_vs_online(self._extract_year(question))

        return None

    # -------------------------------------------------------------
    # MAIN SQL GENERATION PIPELINE
    # -------------------------------------------------------------
    def generate_sql(
        self,
        question: str,
        max_attempts: int = 2,
        user_context: Optional[Dict] = None,
    ) -> str:
        """
        Main entrypoint:
        - Tries template engine first
        - Then Ollama-based SQL generation (with schema-aware prompt)
        - If validation fails, triggers self-correction stage
        """
        logger.info(f"🔍 Generating SQL for: {question}")

        # 1) TEMPLATE ENGINE
        template_sql = self._template_shortcuts(question)
        if template_sql:
            logger.info("⚡ Using TEMPLATE ENGINE (no LLM call)")
            return template_sql

        # 2) INTENT CLASSIFICATION
        intent = self.intent_classifier.classify(question)
        logger.info(
            "🎯 Intent: %s (complexity %s, conf %.2f)",
            intent.get("query_type"),
            intent.get("complexity"),
            intent.get("confidence", 0.0),
        )

        strategy = self._select_strategy(intent)

        examples = None
        if strategy == "few_shot":
            examples = self.query_logger.find_similar_queries(question, limit=3)

        last_sql: Optional[str] = None
        last_errors: List[str] = []

        # ---------------------------------------------------------
        # PRIMARY: LLM (Ollama, kendi iç fallbackleriyle)
        # ---------------------------------------------------------
        for attempt in range(max_attempts):
            logger.info("📌 LLM attempt %d/%d", attempt + 1, max_attempts)

            prompt = self.prompt_manager.build_sql_prompt(
                question=question,
                intent=intent,
                strategy=strategy,
                examples=examples,
                llm_mode="ollama",  # DynamicSchemaBuilder → detailed schema
            )

            response = self.ollama.generate_sql(prompt)

            if not response:
                logger.warning("⚠️ Empty LLM response — retrying...")
                continue

            sql = self._extract_sql(response)
            sql = self.normalizer.normalize(sql)

            ok, errors = self.validator.validate(sql, intent)
            critical = [e for e in errors if e.startswith("ERROR")]

            last_sql = sql
            last_errors = critical or errors

            if not critical:
                logger.info("✅ VALID SQL (LLM primary)")
                self.query_logger.log_query(question, sql, intent, "llm", True)
                return sql

            logger.warning("⚠️ SQL invalid on attempt %d: %s", attempt + 1, errors)

        # ---------------------------------------------------------
        # SELF-CORRECTION STAGE (OpenAI tercihli)
        # ---------------------------------------------------------
        logger.warning("🔁 Entering self-correction stage...")

        corrected = self._self_correct(
            question=question,
            sql=last_sql,
            errors=last_errors,
            intent=intent,
        )

        if corrected:
            return corrected

        # Yukarıya kadar hiçbir valid SQL üretilemediyse:
        msg = "Failed to generate valid SQL from LLM (after self-correction)."
        logger.error("❌ %s", msg)
        raise SQLGenerationError(msg)

    # -------------------------------------------------------------
    # SQL EXTRACTION
    # -------------------------------------------------------------
    def _extract_sql(self, response: str) -> str:
        """
        PromptManager OUTPUT_CONTRACT:
        - SQL
        - blank line
        - 'EXPLANATION:'
        - explanation text
        """
        if "EXPLANATION:" in response:
            response = response.split("EXPLANATION:")[0]

        match = re.search(r"(SELECT[\s\S]*)", response, re.IGNORECASE)
        return match.group(1).strip() if match else response.strip()

    # -------------------------------------------------------------
    # SELF-CORRECTION LOGIC
    # -------------------------------------------------------------
    def _self_correct(
        self,
        question: str,
        sql: Optional[str],
        errors: List[str],
        intent: Dict,
    ) -> Optional[str]:
        """
        Final rescue step:
        - Uses OpenAI 4o-mini (if enabled) to fix invalid SQL
        - Falls back to Ollama correction if OpenAI not available
        - Uses PromptManager with strategy="correction" + llm_mode
        """

        if not sql or not errors:
            logger.error("❌ Self-correction called without SQL or errors.")
            return None

        error_context = (
            f"Original SQL:\n{sql}\n\n"
            "Validation Errors:\n" +
            "\n".join(f"- {e}" for e in errors)
        )

        # Decide which LLM to use for correction
        if getattr(self.openai, "enabled", False):
            client = self.openai
            llm_mode = "openai"
            source = "openai_correction"
            logger.info("🧠 Using OpenAI for self-correction.")
        else:
            client = self.ollama
            llm_mode = "ollama"
            source = "ollama_correction"
            logger.info("🧠 Using Ollama for self-correction (OpenAI disabled).")

        # Build correction prompt
        prompt = self.prompt_manager.build_sql_prompt(
            question=question,
            intent=intent,
            strategy="correction",
            error_context=error_context,
            llm_mode=llm_mode,
        )

        # Call the chosen LLM
        try:
            response = client.generate_sql(prompt)
        except Exception as e:
            logger.error("❌ Self-correction LLM call failed: %s", e)
            return None

        if not response:
            logger.error("❌ Self-correction returned empty response.")
            return None

        corrected_sql = self._extract_sql(response)
        corrected_sql = self.normalizer.normalize(corrected_sql)

        ok, new_errors = self.validator.validate(corrected_sql, intent)
        critical = [e for e in new_errors if e.startswith("ERROR")]

        if critical:
            logger.error("❌ Self-correction SQL still invalid: %s", new_errors)
            return None

        logger.info("🔧 Self-correction succeeded.")
        self.query_logger.log_query(question, corrected_sql, intent, source, True)
        return corrected_sql

    # -------------------------------------------------------------
    # OPTIONAL PUBLIC FIX METHOD (DB runtime errors için)
    # -------------------------------------------------------------
    def fix_sql(
        self,
        question: str,
        faulty_sql: str,
        error_message: str,
        intent: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Orchestrator DB runtime hatalarını LLM'e geri beslemek için kullanabilir.
        - SQL syntactically valid olabilir ama DB tarafında patlayabilir
          (örn. yanlış kolon, join, vs.).
        """
        if intent is None:
            intent = self.intent_classifier.classify(question)

        error_context = (
            f"Original SQL (runtime error from DB):\n{faulty_sql}\n\n"
            "Database Error Message:\n"
            f"{error_message}\n"
        )

        # Tercihen yine OpenAI → yoksa Ollama
        if getattr(self.openai, "enabled", False):
            client = self.openai
            llm_mode = "openai"
            source = "openai_runtime_correction"
            logger.info("🧠 Using OpenAI for runtime SQL correction.")
        else:
            client = self.ollama
            llm_mode = "ollama"
            source = "ollama_runtime_correction"
            logger.info("🧠 Using Ollama for runtime SQL correction (OpenAI disabled).")

        prompt = self.prompt_manager.build_sql_prompt(
            question=question,
            intent=intent,
            strategy="correction",
            error_context=error_context,
            llm_mode=llm_mode,
        )

        try:
            response = client.generate_sql(prompt)
        except Exception as e:
            logger.error("❌ Runtime correction LLM call failed: %s", e)
            return None

        if not response:
            logger.error("❌ Runtime correction returned empty response.")
            return None

        corrected_sql = self._extract_sql(response)
        corrected_sql = self.normalizer.normalize(corrected_sql)

        ok, errors = self.validator.validate(corrected_sql, intent)
        critical = [e for e in errors if e.startswith("ERROR")]

        if critical:
            logger.error("❌ Runtime correction SQL still invalid: %s", errors)
            return None

        logger.info("🔧 Runtime correction succeeded.")
        self.query_logger.log_query(question, corrected_sql, intent, source, True)
        return corrected_sql

    # -------------------------------------------------------------
    # STRATEGY SELECTION
    # -------------------------------------------------------------
    def _select_strategy(self, intent: Dict) -> str:
        c = intent.get("complexity", 5)
        conf = intent.get("confidence", 0.0)

        if c <= Config.COMPLEXITY_THRESHOLD_DIRECT and conf > 0.7:
            return "direct"
        if c <= Config.COMPLEXITY_THRESHOLD_FEW_SHOT:
            return "few_shot"

        return "chain_of_thought"
