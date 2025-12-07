# app/core/schema_builder.py - FINAL PRODUCTION VERSION (2025)
"""
Dynamic Schema Builder for Hybrid LLM SQL Generation
----------------------------------------------------

✔ OpenAI mode → compact, optimized, short & structured
✔ Ollama mode → detailed, descriptive, schema-rich
✔ Automatic table validation
✔ Critical join/business rules appended only once
✔ Prevents oversharing schema (token optimization)
✔ Compatible with PromptManager and SQLGenerator pipeline
"""

from typing import List, Optional
from app.database.db_client import get_db_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DynamicSchemaBuilder:

    def __init__(self):
        self.db = get_db_client()

    # PUBLIC API ---------------------------------------------------------
    def build_schema_context(
        self,
        tables_needed: Optional[List[str]],
        mode: str = "ollama"
    ) -> str:
        """
        tables_needed = list of table names required by intent classifier
        mode = "ollama" → long detailed schema (descriptive)
        mode = "openai" → compact SQL-friendly schema

        If tables_needed is None or empty → return compact overview.
        This prevents token explosion and unnecessary schema dump.
        """

        all_tables = self.db.get_all_tables()
        table_map = {t.lower(): t for t in all_tables}

        # Validate / fix table names
        valid_tables = []
        if tables_needed:
            for t in tables_needed:
                k = t.lower()
                if k in table_map:
                    valid_tables.append(table_map[k])

        # No valid tables? → return minimal fallback schema
        if not valid_tables:
            logger.warning("⚠ No valid tables detected, returning fallback schema.")
            return self._fallback_schema(mode)

        # Two modes: compact vs detailed
        if mode == "openai":
            return self._build_compact_schema(valid_tables)
        else:
            return self._build_detailed_schema(valid_tables)

    # -------------------------------------------------------------------
    # COMPACT SCHEMA FOR OPENAI (short, structured, join-hints)
    # -------------------------------------------------------------------
    def _build_compact_schema(self, tables: List[str]) -> str:
        text = "=== COMPACT SCHEMA ===\n\n"

        for table in tables:
            cols = self.db.get_table_columns(table)

            # Sort → keys first for better join accuracy
            sorted_cols = sorted(
                cols,
                key=lambda c: (0 if "key" in c["name"].lower() else 1, c["name"])
            )

            text += f"{table}:\n"
            for col in sorted_cols:
                text += f"  - {col['name']} ({col['type']})\n"
            text += "\n"

        # Append minimal join rules
        text += self._compact_relationship_rules()

        return text

    # -------------------------------------------------------------------
    # DETAILED SCHEMA FOR OLLAMA (rich, descriptive, full context)
    # -------------------------------------------------------------------
    def _build_detailed_schema(self, tables: List[str]) -> str:
        text = "═══════════════════════════════════════════\n"
        text += "📘 CONTOSO DATABASE SCHEMA (DETAILED)\n"
        text += "═══════════════════════════════════════════\n\n"

        for table in tables:
            text += self._format_table(table)

        # Add essential business rules only once
        text += self._critical_rules()
        text += self._relationship_rules()

        return text

    # -------------------------------------------------------------------
    # TABLE FORMATTING (detailed)
    # -------------------------------------------------------------------
    def _format_table(self, table: str) -> str:
        try:
            cols = self.db.get_table_columns(table)
        except Exception:
            return f"TABLE: {table}\n  (ERROR FETCHING COLUMNS)\n\n"

        schema = f"TABLE: {table}\nCOLUMNS:\n"

        sorted_cols = sorted(
            cols,
            key=lambda c: (0 if "key" in c["name"].lower() else 1, c["name"])
        )

        for col in sorted_cols:
            schema += f"  • {col['name']} ({col['type']})\n"

        schema += "\n" + ("─" * 60) + "\n\n"
        return schema

    # -------------------------------------------------------------------
    # CRITICAL BUSINESS RULES (always appended)
    # -------------------------------------------------------------------
    def _critical_rules(self) -> str:
        return """
══════════════════════════════════════════════════════
⚠️ CRITICAL CONTOSO BUSINESS RULES
══════════════════════════════════════════════════════
1. ALWAYS JOIN DimDate using DateKey — never use YEAR(DateKey).
2. Use CalendarYear, CalendarMonth, CalendarQuarter instead of date functions.
3. Use SUM(SalesAmount) for revenue metrics.
4. FactOnlineSales and FactSales have different dimension keys.
"""

    # -------------------------------------------------------------------
    # RELATIONSHIPS (detailed mode)
    # -------------------------------------------------------------------
    def _relationship_rules(self) -> str:
        return """
══════════════════════════════════════════════════════
🔗 CONTOSO TABLE RELATIONSHIPS
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

    # -------------------------------------------------------------------
    # COMPACT RELATIONSHIPS (OpenAI mode)
    # -------------------------------------------------------------------
    def _compact_relationship_rules(self) -> str:
        return """
JOIN RULES:
- FactSales.DateKey = DimDate.DateKey
- FactSales.ProductKey = DimProduct.ProductKey
- FactSales.StoreKey = DimStore.StoreKey

- FactOnlineSales.DateKey = DimDate.DateKey
- FactOnlineSales.ProductKey = DimProduct.ProductKey
- FactOnlineSales.CustomerKey = DimCustomer.CustomerKey

PRODUCT PATH:
DimProduct → DimProductSubcategory → DimProductCategory
"""

    # -------------------------------------------------------------------
    # FALLBACK SCHEMA (no recognized tables)
    # -------------------------------------------------------------------
    def _fallback_schema(self, mode: str) -> str:
        if mode == "openai":
            return (
                "=== MINIMAL SCHEMA ===\n"
                "Use correct Contoso table names.\n\n"
                "Common tables:\n"
                "- FactSales\n"
                "- FactOnlineSales\n"
                "- DimDate\n"
                "- DimProduct\n"
                "- DimStore\n"
            )
        else:
            return (
                "No valid tables recognized. Provide table names such as:\n"
                "FactSales, DimDate, DimProduct, DimStore, FactOnlineSales.\n"
            )
