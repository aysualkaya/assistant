# app/database/query_validator.py
"""
Advanced SQL Query Validator - PRODUCTION VERSION (2025)
Fully compatible with:
- DynamicSchemaBuilder
- SQLNormalizer fuzzy correction
- OpenAI / Ollama hybrid SQL generation

Validator focuses ONLY on:
- Business-rule correctness
- Intent alignment
- Critical SQL errors
- Logical table/column misuse

Does NOT duplicate:
- Fuzzy table correction (SQLNormalizer handles it)
- Phantom column cleanup (SQLNormalizer handles it)
- Table existence logic (Normalizer ensures correct naming)
"""

import re
from typing import List, Tuple, Dict, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryValidator:
    """
    Lightweight but strict SQL validator.
    Normalizer fixes structure — validator checks logic.
    """

    # Columns that FactSales must NOT contain
    FACTSALES_FORBIDDEN = ["CustomerKey"]

    # Columns that FactOnlineSales must NOT contain
    FACTONLINE_FORBIDDEN = ["channelKey"]

    def validate(self, sql: str, intent: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        errors = []

        if not sql or len(sql.strip()) < 10:
            return False, ["ERROR: SQL query is empty or too short"]

        # -------------------------------
        # 1) Business-rule validations
        # -------------------------------
        errors.extend(self._check_date_filtering(sql))
        errors.extend(self._check_factsales_column_misuse(sql))
        errors.extend(self._check_factonlinesales_column_misuse(sql))
        errors.extend(self._check_union_syntax(sql))
        errors.extend(self._check_invalid_functions(sql))

        # -------------------------------
        # 2) Intent-based validation
        # -------------------------------
        if intent:
            errors.extend(self._validate_against_intent(sql, intent))

        # -------------------------------
        # 3) Basic SQL structural rules
        # -------------------------------
        errors.extend(self._check_basic_syntax(sql))

        # -------------------------------
        # FINAL RESULT
        # -------------------------------
        critical = [e for e in errors if e.startswith("ERROR")]

        if critical:
            logger.error("❌ SQL validation failed:")
            for e in critical:
                logger.error(f"  - {e}")
            return False, errors

        if errors:
            for w in errors:
                if w.startswith("WARNING"):
                    logger.warning(f"⚠️ {w}")

        logger.info("✅ SQL validation passed")
        return True, errors

    # =====================================================================
    # BUSINESS RULE CHECKS
    # =====================================================================

    def _check_date_filtering(self, sql: str) -> List[str]:
        errors = []

        # YEAR(DateKey) forbidden
        if re.search(r'YEAR\s*\(\s*[\w\.]*DateKey\s*\)', sql, re.IGNORECASE):
            errors.append(
                "ERROR: YEAR(DateKey) cannot be used. "
                "Join DimDate and filter with dd.CalendarYear."
            )

        # Avoid GETDATE()
        if "GETDATE()" in sql.upper():
            errors.append(
                "WARNING: GETDATE() is not recommended; data covers only years 2007–2009."
            )

        return errors

    def _check_factsales_column_misuse(self, sql: str) -> List[str]:
        """FactSales may NOT use CustomerKey."""
        errors = []

        if re.search(r'\bFactSales\b', sql, re.IGNORECASE):
            if re.search(r'(FactSales|fs|f)\s*\.\s*CustomerKey', sql, re.IGNORECASE):
                errors.append(
                    "ERROR: FactSales does NOT contain CustomerKey. "
                    "Use FactOnlineSales for CustomerKey."
                )

        return errors

    def _check_factonlinesales_column_misuse(self, sql: str) -> List[str]:
        """FactOnlineSales may NOT use channelKey."""
        errors = []

        if re.search(r'\bFactOnlineSales\b', sql, re.IGNORECASE):
            if re.search(r'(FactOnlineSales|fos|fo)\s*\.\s*channelKey', sql, re.IGNORECASE):
                errors.append(
                    "ERROR: FactOnlineSales does NOT contain channelKey. "
                    "Use FactSales for channelKey."
                )

        return errors

    # =====================================================================
    # SYNTAX CHECKS
    # =====================================================================

    def _check_union_syntax(self, sql: str) -> List[str]:
        errors = []

        if "UNION ALL" in sql.upper():
            parts = re.split(r'UNION\s+ALL', sql, flags=re.IGNORECASE)
            for p in parts[:-1]:
                if "ORDER BY" in p.upper():
                    errors.append(
                        "WARNING: ORDER BY inside UNION ALL subqueries may require parentheses"
                    )
        return errors

    def _check_invalid_functions(self, sql: str) -> List[str]:
        errors = []
        invalid_patterns = {
            r'DATE\(': "DATE() is a MySQL function. SQL Server uses CONVERT or CAST.",
            r'CURDATE\(\)': "CURDATE() is MySQL-only.",
            r'NOW\(\)': "NOW() is MySQL-only."
        }

        for pat, msg in invalid_patterns.items():
            if re.search(pat, sql, re.IGNORECASE):
                errors.append(f"WARNING: {msg}")

        return errors

    # =====================================================================
    # INTENT VALIDATION
    # =====================================================================

    def _validate_against_intent(self, sql: str, intent: Dict) -> List[str]:
        errors = []
        qtype = intent.get("query_type")

        if qtype == "ranking":
            if "ORDER BY" not in sql.upper():
                errors.append("WARNING: Ranking query should contain ORDER BY")

        if qtype == "comparison":
            if intent.get("comparison_type") == "store_vs_online":
                if "UNION ALL" not in sql.upper():
                    errors.append("WARNING: Store vs online comparison should use UNION ALL")

        if qtype == "trend":
            if "GROUP BY" not in sql.upper():
                errors.append("WARNING: Trend query should contain GROUP BY")

        return errors

    # =====================================================================
    # BASIC SQL SYNTAX
    # =====================================================================

    def _check_basic_syntax(self, sql: str) -> List[str]:
        errors = []

        if "SELECT" not in sql.upper():
            errors.append("ERROR: SQL must contain SELECT")

        if "FROM" not in sql.upper():
            errors.append("ERROR: SQL must contain FROM")

        # Parantez kontrolü
        if sql.count("(") != sql.count(")"):
            errors.append(
                "ERROR: Unbalanced parentheses detected"
            )

        return errors


# Singleton
_validator_instance = None

def get_query_validator() -> QueryValidator:
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = QueryValidator()
    return _validator_instance
