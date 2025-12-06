# app/core/schema_builder.py - HYBRID LLM-OPTIMIZED VERSION
"""
Dynamic Schema Builder (REAL-TIME INFORMATION_SCHEMA)
-----------------------------------------------------

UPGRADED FOR HYBRID LLM SYSTEM:
✔ Ollama → detailed, long-form schema (old behavior preserved)
✔ OpenAI → compact, bullet-style, LLM-friendly schema
✔ Adds consistent formatting for JOIN paths
✔ Adds ranked importance for columns (key columns first)
✔ Maintains backward compatibility
"""

from typing import List
from app.database.db_client import get_db_client
from app.utils.logger import get_logger
from app.core.config import Config

logger = get_logger(__name__)


class DynamicSchemaBuilder:

    def __init__(self):
        self.db = get_db_client()

    # ------------------------------------------------------------------
    # PUBLIC API (Dual Mode Output)
    # ------------------------------------------------------------------
    def build_schema_context(self, tables_needed: List[str], mode: str = "ollama") -> str:
        """
        mode = "ollama" → long detailed schema
        mode = "openai" → compact SQL-friendly schema
        """
        all_tables = self.db.get_all_tables()
        table_map = {t.lower(): t for t in all_tables}

        real_tables = []
        for t in tables_needed:
            key = t.lower()
            if key in table_map:
                real_tables.append(table_map[key])

        if not real_tables:
            return "NO VALID TABLES FOUND IN DATABASE."

        # Two different schema formats depending on model type
        if mode == "openai":
            return self._build_compact_schema(real_tables)
        else:
            return self._build_detailed_schema(real_tables)

    # ==================================================================
    # 1) OPENAI MODE → Compact SQL-Friendly schema (NEW)
    # ==================================================================
    def _build_compact_schema(self, tables: List[str]) -> str:
        """
        Much shorter version optimized for OpenAI.
        - Key columns first
        - No long explanations
        - Simple JOIN maps
        """
        text = "=== COMPACT SCHEMA (OPENAI MODE) ===\n\n"

        for table in tables:
            cols = self.db.get_table_columns(table)

            # Sort columns → keys first (helps LLM produce correct joins)
            sorted_cols = sorted(
                cols,
                key=lambda c: (0 if "key" in c["name"].lower() else 1, c["name"])
            )

            text += f"{table}:\n"
            for col in sorted_cols:
                text += f"  - {col['name']} ({col['type']})\n"
            text += "\n"

        # concise relationship rules
        text += self._compact_relationship_rules()

        return text

    # ==================================================================
    # 2) OLLAMA MODE → Full detailed schema (old behavior)
    # ==================================================================
    def _build_detailed_schema(self, tables: List[str]) -> str:
        text = "═══════════════════════════════════════════\n"
        text += "📘 CONTOSO DATABASE SCHEMA (DETAILED)\n"
        text += "═══════════════════════════════════════════\n\n"

        for table in tables:
            text += self._format_table(table)

        text += self._critical_rules()
        text += self._relationship_rules()

        return text

    # ==================================================================
    # FORMATTING FUNCTIONS
    # ==================================================================
    def _format_table(self, table: str) -> str:
        schema = f"TABLE: {table}\nCOLUMNS:\n"

        try:
            cols = self.db.get_table_columns(table)
        except Exception:
            return f"TABLE: {table}\n  (ERROR FETCHING COLUMNS)\n"

        # SHOW KEYS FIRST
        sorted_cols = sorted(
            cols,
            key=lambda c: (0 if "key" in c["name"].lower() else 1, c["name"])
        )

        for col in sorted_cols:
            schema += f"  • {col['name']} ({col['type']})\n"

        schema += "\n" + ("─" * 60) + "\n\n"
        return schema

    # ==================================================================
    # BUSINESS RULES (UNTOUCHED)
    # ==================================================================
    def _critical_rules(self) -> str:
        return """
══════════════════════════════════════════════════════
⚠️ CRITICAL CONTOSO BUSINESS RULES
══════════════════════════════════════════════════════
1. ALWAYS JOIN DimDate using DateKey — never use YEAR(DateKey).
2. Use dd.CalendarYear, CalendarMonth, CalendarQuarter for filtering.
3. Use SUM(SalesAmount) for revenue metrics.
4. FactSales vs FactOnlineSales have different keys.
"""

    # ==================================================================
    # DETAILED RELATIONSHIPS (OLLAMA MODE)
    # ==================================================================
    def _relationship_rules(self) -> str:
        return """
══════════════════════════════════════════════════════
🔗 CONTOSO TABLE RELATIONSHIPS (DETAILED)
══════════════════════════════════════════════════════
FactSales:
  - DateKey → DimDate.DateKey
  - ProductKey → DimProduct.ProductKey
  - StoreKey → DimStore.StoreKey

FactOnlineSales:
  - DateKey → DimDate.DateKey
  - ProductKey → DimProduct.ProductKey
  - CustomerKey → DimCustomer.CustomerKey

Product Hierarchy:
  DimProduct → DimProductSubcategory → DimProductCategory

Geography:
  DimStore → DimGeography
  DimCustomer → DimGeography
"""

    # ==================================================================
    # COMPACT RELATIONSHIPS (OPENAI MODE) — NEW
    # ==================================================================
    def _compact_relationship_rules(self) -> str:
        return """
JOIN RULES (IMPORTANT):
- FactSales.DateKey = DimDate.DateKey
- FactSales.ProductKey = DimProduct.ProductKey
- FactSales.StoreKey = DimStore.StoreKey

- FactOnlineSales.DateKey = DimDate.DateKey
- FactOnlineSales.CustomerKey = DimCustomer.CustomerKey

PRODUCT PATH:
DimProduct → DimProductSubcategory → DimProductCategory

These are the ONLY valid join paths.
"""
