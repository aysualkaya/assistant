# app/core/schema_builder.py - FINAL DYNAMIC + RELATIONSHIP-AWARE VERSION
"""
Dynamic Schema Builder (REAL-TIME INFORMATION_SCHEMA)
-----------------------------------------------------

✔ Tables & columns come directly from the database
✔ Completely removes static hard-coded schema
✔ Adds intelligent business hints + relationship rules
✔ Sends only the relevant tables to the LLM
✔ Prevents JOIN mistakes, alias errors, and invalid paths
"""

from typing import List, Dict, Set
from app.database.db_client import get_db_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DynamicSchemaBuilder:
    """
    Fully dynamic schema builder:
    - Queries INFORMATION_SCHEMA.COLUMNS
    - Generates compact schema text for LLM
    - Includes Contoso-critical rules + table relationships
    """

    def __init__(self):
        self.db = get_db_client()

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def build_schema_context(self, tables_needed: List[str]) -> str:
        """
        Create intelligent schema content including:
        ✔ Dynamic columns
        ✔ Critical business rules
        ✔ Relationship rules (NEW)
        """

        all_tables = self.db.get_all_tables()
        table_map = {t.lower(): t for t in all_tables}

        # Resolve user’s requested tables
        real_tables = []
        for t in tables_needed:
            t_lc = t.lower()
            if t_lc in table_map:
                real_tables.append(table_map[t_lc])

        if not real_tables:
            return "NO MATCHING TABLE FOUND IN DATABASE SCHEMA."

        schema_text = "═════════════════════════════════════════════════════\n"
        schema_text += "📘 CONTOSO DATABASE SCHEMA (RELEVANT TABLES ONLY)\n"
        schema_text += "═════════════════════════════════════════════════════\n\n"

        # List relevant tables + columns dynamically
        for table in real_tables:
            schema_text += self._format_table(table)

        # Add business rules
        schema_text += self._critical_rules()

        # Add relationship rules (the most important part!)
        schema_text += self._relationship_rules()

        return schema_text

    # ------------------------------------------------------------------
    # FORMAT TABLE WITH DYNAMIC COLUMNS
    # ------------------------------------------------------------------
    def _format_table(self, table: str) -> str:
        schema = f"TABLE: {table}\nCOLUMNS:\n"

        try:
            cols = self.db.get_table_columns(table)
        except Exception:
            return f"TABLE: {table}\n  (ERROR FETCHING COLUMNS)\n"

        for col in cols:
            schema += f"  • {col['name']} ({col['type']})\n"

        schema += "\n" + ("─" * 60) + "\n\n"
        return schema

    # ------------------------------------------------------------------
    # CRITICAL BUSINESS RULES
    # ------------------------------------------------------------------
    def _critical_rules(self) -> str:
        return """
══════════════════════════════════════════════════════
⚠️ CRITICAL CONTOSO BUSINESS RULES
══════════════════════════════════════════════════════

1. DATE FILTERING:
   • NEVER use YEAR(DateKey) → type mismatch
   • ALWAYS join DimDate:
       INNER JOIN DimDate dd ON [fact].DateKey = dd.DateKey
   • Use: dd.CalendarYear, dd.CalendarMonth, dd.CalendarQuarter

2. SALES LOGIC:
   • Use SUM(SalesAmount) for revenue
   • Use SUM(SalesQuantity) for volume metrics

3. FACT SALES vs FACT ONLINE SALES:
   FactSales:
     - HAS: ChannelKey, StoreKey
     - DOES NOT HAVE: CustomerKey
   FactOnlineSales:
     - HAS: CustomerKey, StoreKey
     - DOES NOT HAVE: ChannelKey

4. COMPARISON LOGIC:
   For Store vs Online comparisons:
     SELECT ... FROM FactSales ...
     UNION ALL
     SELECT ... FROM FactOnlineSales ...

5. TIME SERIES:
   • Must GROUP BY dd.CalendarMonth or dd.CalendarYear
   • Must ORDER BY dd.CalendarMonth ASC
"""

    # ------------------------------------------------------------------
    # RELATIONSHIP RULES (THE MOST IMPORTANT PART)
    # ------------------------------------------------------------------
    def _relationship_rules(self) -> str:
        return """
══════════════════════════════════════════════════════
🔗 CONTOSO TABLE RELATIONSHIPS (VERY IMPORTANT)
══════════════════════════════════════════════════════

FACT TABLE RELATIONSHIPS
------------------------
FactSales:
  • FactSales.DateKey        → DimDate.DateKey
  • FactSales.ProductKey     → DimProduct.ProductKey
  • FactSales.StoreKey       → DimStore.StoreKey
  • FactSales.PromotionKey   → DimPromotion.PromotionKey
  • FactSales.ChannelKey     → DimChannel.ChannelKey

FactOnlineSales:
  • FactOnlineSales.DateKey      → DimDate.DateKey
  • FactOnlineSales.ProductKey   → DimProduct.ProductKey
  • FactOnlineSales.CustomerKey  → DimCustomer.CustomerKey


PRODUCT HIERARCHY
-----------------
DimProduct.ProductSubcategoryKey        → DimProductSubcategory.ProductSubcategoryKey
DimProductSubcategory.ProductCategoryKey → DimProductCategory.ProductCategoryKey


GEOGRAPHY HIERARCHY
-------------------
FactSales.StoreKey        → DimStore.StoreKey → DimGeography.GeographyKey
FactOnlineSales.CustomerKey → DimCustomer.CustomerKey → DimGeography.GeographyKey


DATE HIERARCHY
--------------
DimDate.CalendarYear  
DimDate.CalendarMonth  
DimDate.CalendarQuarter

IMPORTANT:
• Fact tables must always JOIN through these relationships.
• Product → Subcategory → Category is the ONLY valid path.
• Do NOT invent new join paths or aliases.
• UNION should NOT be used unless column structures match exactly.
"""
