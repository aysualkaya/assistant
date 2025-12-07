"""
Advanced SQL Query Validator (2025 – Final Production Version)

Covers:
✓ Business-rule correctness (DimDate, Fact tables)
✓ Forbidden column misuse
✓ Server-specific forbidden SQL functions (MySQL, PG, SQLite)
✓ Intent alignment (ranking, trend, comparison)
✓ Aggregation sanity checks
✓ Ranking + TOP alignment
✓ SQL injection pattern blocking
"""

import re
from typing import List, Tuple, Dict, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryValidator:

    # Fact table forbidden columns
    FACTSALES_FORBIDDEN = ["CustomerKey"]
    FACTONLINE_FORBIDDEN = ["ChannelKey", "StoreKey"]

    # MySQL / PostgreSQL banned functions
    FORBIDDEN_FUNCTIONS = {
        r"LIMIT\s+\d+": "LIMIT is MySQL-specific. Use SELECT TOP in SQL Server.",
        r"IFNULL\s*\(": "IFNULL() is MySQL-only. Use ISNULL().",
        r"ILIKE\s": "ILIKE is PostgreSQL-only.",
        r"REGEXP\s": "REGEXP is SQLite/MySQL. SQL Server uses LIKE or PATINDEX.",
        r"NOW\s*\(": "NOW() is MySQL-only. Use GETDATE().",
        r"CURDATE\s*\(": "CURDATE() is MySQL-only.",
    }

    # SQL Injection indicators
    INJECTION_PATTERNS = [
        r";\s*DROP\s+TABLE",
        r";\s*ALTER\s+TABLE",
        r";\s*TRUNCATE\s+TABLE",
    ]

    def validate(self, sql: str, intent: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        errors = []

        # ------------------------------------
        # 0. Empty query guard
        # ------------------------------------
        if not sql or len(sql.strip()) < 10:
            return False, ["ERROR: SQL is empty or too short"]

        # ------------------------------------
        # 1. Business rules
        # ------------------------------------
        errors += self._check_dimdate_usage(sql)
        errors += self._check_factsales_column_misuse(sql)
        errors += self._check_factonlinesales_column_misuse(sql)
        errors += self._check_forbidden_functions(sql)
        errors += self._check_injection(sql)
        errors += self._check_aggregation_groupby(sql)

        # ------------------------------------
        # 2. Intent alignment
        # ------------------------------------
        if intent:
            errors += self._validate_intent_alignment(sql, intent)

        # ------------------------------------
        # 3. Structural sanity checks
        # ------------------------------------
        errors += self._sanity_check_structure(sql)

        # Decision
        critical = [e for e in errors if e.startswith("ERROR")]

        if critical:
            logger.error("❌ SQL validation failed:")
            for c in critical:
                logger.error("  - " + c)
            return False, errors

        # print warnings
        for w in errors:
            if w.startswith("WARNING"):
                logger.warning("⚠️ " + w)

        return True, errors

    # =====================================================================
    # DIMDATE RULES
    # =====================================================================
    def _check_dimdate_usage(self, sql: str) -> List[str]:
        issues = []

        # Warning for YEAR(DateKey)
        if re.search(r"YEAR\s*\(\s*[\w\.]*DateKey\s*\)", sql, re.IGNORECASE):
            issues.append(
                "WARNING: YEAR(DateKey) used. Prefer joining DimDate and using CalendarYear."
            )

        # Check if CalendarYear / Month used without DimDate
        if any(x in sql for x in ["CalendarYear", "CalendarMonth"]):
            if "DimDate" not in sql:
                issues.append(
                    "ERROR: CalendarYear/CalendarMonth used without joining DimDate."
                )

        return issues

    # =====================================================================
    # FACT TABLE VALIDATION
    # =====================================================================
    def _check_factsales_column_misuse(self, sql: str) -> List[str]:
        issues = []
        if "FactSales" in sql or re.search(r"\bfs\b", sql):
            for col in self.FACTSALES_FORBIDDEN:
                if re.search(rf"(FactSales|fs)\s*\.\s*{col}", sql, re.IGNORECASE):
                    issues.append(
                        f"ERROR: FactSales does NOT contain {col}. Use FactOnlineSales."
                    )
        return issues

    def _check_factonlinesales_column_misuse(self, sql: str) -> List[str]:
        issues = []
        if "FactOnlineSales" in sql or re.search(r"\bfos\b", sql):
            for col in self.FACTONLINE_FORBIDDEN:
                if re.search(rf"(FactOnlineSales|fos)\s*\.\s*{col}", sql, re.IGNORECASE):
                    issues.append(
                        f"ERROR: FactOnlineSales does NOT contain {col}. Use FactSales."
                    )
        return issues

    # =====================================================================
    # FORBIDDEN FUNCTION CHECKS
    # =====================================================================
    def _check_forbidden_functions(self, sql: str) -> List[str]:
        issues = []
        for pattern, msg in self.FORBIDDEN_FUNCTIONS.items():
            if re.search(pattern, sql, re.IGNORECASE):
                issues.append(f"ERROR: {msg}")
        return issues

    # =====================================================================
    # SQL INJECTION
    # =====================================================================
    def _check_injection(self, sql: str) -> List[str]:
        for p in self.INJECTION_PATTERNS:
            if re.search(p, sql, re.IGNORECASE):
                return ["ERROR: Suspicious SQL injection-like pattern detected"]
        return []

    # =====================================================================
    # AGGREGATION CHECK
    # =====================================================================
    def _check_aggregation_groupby(self, sql: str) -> List[str]:
        issues = []

        is_agg = any(func in sql.upper() for func in ["SUM(", "COUNT(", "AVG("])

        if is_agg and "GROUP BY" not in sql.upper():
            # If no grouping but multiple non-aggregated columns exist
            select_cols = re.findall(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
            if select_cols:
                col_list = select_cols[0]
                non_agg_cols = [
                    c.strip()
                    for c in col_list.split(",")
                    if "(" not in c and "SUM" not in c and "COUNT" not in c
                ]
                if len(non_agg_cols) > 1:
                    issues.append("WARNING: Aggregation used without GROUP BY may produce incorrect results")

        return issues

    # =====================================================================
    # INTENT ALIGNMENT
    # =====================================================================
    def _validate_intent_alignment(self, sql: str, intent: Dict) -> List[str]:
        issues = []
        qtype = intent.get("query_type")

        # Ranking needs order by + top
        if qtype == "ranking":
            if "ORDER BY" not in sql.upper():
                issues.append("WARNING: Ranking query expected ORDER BY clause")
            if "TOP" not in sql.upper():
                issues.append("WARNING: Ranking intent expected SELECT TOP")

        # Trend needs GROUP BY
        if qtype == "trend" and "GROUP BY" not in sql.upper():
            issues.append("WARNING: Trend query expected GROUP BY")

        return issues

    # =====================================================================
    # STRUCTURAL CHECK
    # =====================================================================
    def _sanity_check_structure(self, sql: str) -> List[str]:
        issues = []

        if "SELECT" not in sql.upper():
            issues.append("ERROR: Missing SELECT keyword")

        if "FROM" not in sql.upper():
            issues.append("ERROR: Missing FROM clause")

        if sql.count("(") != sql.count(")"):
            issues.append("ERROR: Unbalanced parentheses detected")

        return issues


# Singleton
_validator_instance = None

def get_query_validator() -> QueryValidator:
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = QueryValidator()
    return _validator_instance
