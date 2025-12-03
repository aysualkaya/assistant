# app/llm/sql_generator.py - FINAL VERSION WITH TEMPLATE ENGINE
"""
Dynamic SQL Generator with:
- Template Engine (LLM bypass for common queries)
- SQL-first extraction
- Normalizer for safe SQL
- Self-correction
"""

from typing import Dict, Optional, List
import re

from app.core.intent_classifier import IntentClassifier
from app.core.schema_builder import DynamicSchemaBuilder
from app.core.config import Config
from app.llm.ollama_client import OllamaClient
from app.llm.prompt_manager import PromptManager
from app.database.query_validator import QueryValidator
from app.database.sql_normalizer import get_sql_normalizer
from app.memory.query_logger import QueryLogger
from app.utils.logger import get_logger

# TEMPLATE ENGINE IMPORTS
from app.llm.templates import (
    template_top_products,
    template_bottom_products,
    template_total_sales,
    template_monthly_trend,
    template_store_vs_online
)

logger = get_logger(__name__)


class DynamicSQLGenerator:

    def __init__(self):
        self.llm = OllamaClient()
        self.intent_classifier = IntentClassifier()
        self.schema_builder = DynamicSchemaBuilder()
        self.prompt_manager = PromptManager()
        self.validator = QueryValidator()
        self.normalizer = get_sql_normalizer()
        self.query_logger = QueryLogger()

    # -------------------------------------------------------------
    # YEAR EXTRACTOR
    # -------------------------------------------------------------
    def _extract_year(self, question: str):
        match = re.search(r"(20\d{2})", question)
        return int(match.group(1)) if match else None

    # -------------------------------------------------------------
    # TEMPLATE ENGINE — BYPASS LLM FOR KNOWN PATTERNS
    # -------------------------------------------------------------
    def _template_shortcuts(self, question: str):
        q = question.lower()

        # En çok satan ürünler
        if "en çok satan" in q or "en cok satan" in q:
            return template_top_products(limit=5)

        # En az satan ürünler
        if "en az satan" in q:
            return template_bottom_products(limit=5)

        # Toplam satış
        if "toplam satış" in q or "toplam satis" in q:
            year = self._extract_year(question)
            return template_total_sales(year)

        # Aylık trend
        if "aylık" in q or "aylik" in q:
            year = self._extract_year(question)
            if year:
                return template_monthly_trend(year)

        # Mağaza vs online
        if ("mağaza" in q or "magaza" in q) and "online" in q:
            year = self._extract_year(question)
            if year:
                return template_store_vs_online(year)

        return None  # Not a template case

    # -------------------------------------------------------------
    # MAIN GENERATION LOGIC
    # -------------------------------------------------------------
    def generate_sql(
        self,
        question: str,
        max_attempts: int = 3,
        user_context: Optional[Dict] = None
    ) -> str:

        logger.info(f"🔍 Generating SQL for: {question}")

        # 1. TRY TEMPLATE ENGINE FIRST
        template_sql = self._template_shortcuts(question)
        if template_sql:
            logger.info("⚡ Using TEMPLATE ENGINE (LLM bypass)")
            return template_sql

        # 2. CLASSIFY INTENT
        intent = self.intent_classifier.classify(question)
        logger.info(
            f"🎯 Intent: {intent['query_type']} "
            f"(complexity: {intent['complexity']}/10, confidence: {intent['confidence']:.2f})"
        )

        # 3. SELECT STRATEGY
        strategy = self._select_strategy(intent)
        logger.info(f"📋 Selected strategy: {strategy}")

        # 4. FEW-SHOT EXAMPLES
        examples = None
        if strategy == "few_shot":
            examples = self.query_logger.find_similar_queries(question, limit=3)
            if examples:
                logger.info(f"📚 Found {len(examples)} similar examples")

        # ---------------------------------------------------------
        # LLM GENERATION LOOP
        # ---------------------------------------------------------
        for attempt in range(max_attempts):
            logger.info(f"⚙️ Generation attempt {attempt+1}/{max_attempts}")

            # Build prompt
            prompt = self.prompt_manager.build_sql_prompt(
                question=question,
                intent=intent,
                strategy=strategy,
                examples=examples
            )

            # LLM call
            response = self.llm.generate_sql(prompt)
            if not response:
                logger.warning("⚠️ Empty LLM response — retrying...")
                continue

            # Extract SQL
            sql = self._extract_sql(response)
            logger.info(f"🧽 Extracted SQL:\n{sql}")

            # Normalize
            sql = self.normalizer.normalize(sql)
            logger.info(f"🧼 Normalized SQL:\n{sql}")

            # Validate
            is_valid, errors = self.validator.validate(sql, intent)
            critical = [e for e in errors if e.startswith("ERROR")]

            if not critical:
                logger.info("✅ VALID SQL")
                self.query_logger.log_query(
                    question=question, sql=sql, intent=intent,
                    strategy=strategy, success=True
                )
                return sql

            # Final attempt → try correction
            if attempt == max_attempts - 1:
                corrected = self._self_correct(question, sql, critical, intent)
                corrected = self.normalizer.normalize(corrected)

                is_valid, new_errors = self.validator.validate(corrected, intent)
                if not any(e.startswith("ERROR") for e in new_errors):
                    logger.info("🔧 Self-correction succeeded")
                    return corrected

        raise RuntimeError("❌ Failed to generate valid SQL after retries")

    # -------------------------------------------------------------
    # SQL EXTRACTION
    # -------------------------------------------------------------
    def _extract_sql(self, response: str) -> str:
        text = response.strip()

        # Main rule: split before EXPLANATION
        if "EXPLANATION:" in text:
            sql = text.split("EXPLANATION:")[0]
            return self._final_clean_sql(sql)

        # Fallback: first SELECT block
        match = re.search(r"(SELECT[\s\S]*)", text, re.IGNORECASE)
        if match:
            return self._final_clean_sql(match.group(1))

        return self._final_clean_sql(text)

    def _final_clean_sql(self, sql: str) -> str:
        sql = sql.strip()
        sql = re.sub(r"```sql|```", "", sql)
        sql = re.sub(r"^SQL\s*:", "", sql, flags=re.IGNORECASE)
        sql = re.split(r"(Explanation:|Note that|This query)", sql, flags=re.IGNORECASE)[0]

        if not sql.endswith(";"):
            sql += ";"
        return sql

    # -------------------------------------------------------------
    # SELF CORRECTION
    # -------------------------------------------------------------
    def _self_correct(self, question: str, sql: str, errors: List[str], intent: Dict) -> str:

        error_context = (
            f"Original SQL:\n{sql}\n\n"
            "Validation Errors:\n" +
            "\n".join(f"- {e}" for e in errors)
        )

        prompt = self.prompt_manager.build_sql_prompt(
            question=question,
            intent=intent,
            strategy="correction",
            error_context=error_context
        )

        response = self.llm.generate_sql(prompt)
        return self._extract_sql(response)

    # -------------------------------------------------------------
    # STRATEGY SELECTION
    # -------------------------------------------------------------
    def _select_strategy(self, intent: Dict) -> str:
        c = intent.get("complexity", 5)
        conf = intent.get("confidence", 0.5)

        if c <= Config.COMPLEXITY_THRESHOLD_DIRECT and conf > 0.7:
            return "direct"
        elif c <= Config.COMPLEXITY_THRESHOLD_FEW_SHOT:
            return "few_shot"

        return "chain_of_thought"
