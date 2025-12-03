# app/llm/prompt_manager.py
"""
Prompt Manager for SQL Generation

- Uses DynamicSchemaBuilder to send ONLY relevant Contoso tables/columns
- Adds critical business rules & join hints to the prompt
- Enforces output format: SQL first, then EXPLANATION:
"""

from typing import Dict, List, Optional
from app.core.schema_builder import DynamicSchemaBuilder
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ------------------------------------------------------------
# CONSTANT: OUTPUT FORMAT (SQL FIRST, THEN EXPLANATION)
# ------------------------------------------------------------
OUTPUT_FORMAT_INSTRUCTION = """
CRITICAL OUTPUT FORMAT (YOU MUST FOLLOW THIS EXACTLY):

1) First, output ONLY the final T-SQL query (no backticks, no markdown, no comments).
2) Then, on a new line, start with: EXPLANATION:
   and write a short explanation in natural language.

Example:

SELECT
    dd.CalendarYear,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
INNER JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear = 2008
GROUP BY dd.CalendarYear
ORDER BY dd.CalendarYear;

EXPLANATION: This query returns total sales for 2008 by summing SalesAmount in FactSales joined with DimDate.

Now produce ONLY ONE final SQL query followed by EXPLANATION: as shown.
"""


class PromptManager:
    """
    Builds LLM prompts for SQL generation & correction.
    Integrates DynamicSchemaBuilder to provide REAL schema from ContosoRetailDW.
    """

    def __init__(self) -> None:
        self.schema_builder = DynamicSchemaBuilder()
        self.logger = get_logger(__name__)

    # --------------------------------------------------------
    # PUBLIC MAIN ENTRY
    # --------------------------------------------------------
    def build_sql_prompt(
        self,
        question: str,
        intent: Dict,
        strategy: str,
        examples: Optional[List[Dict]] = None,
        error_context: Optional[str] = None,
    ) -> str:
        """
        Build the full prompt for the LLM based on:
        - user question
        - inferred intent
        - chosen strategy (direct / few_shot / chain_of_thought / correction)
        - similar examples (for few_shot)
        - error context (for correction)
        """

        query_type = intent.get("query_type", "aggregation")
        complexity = intent.get("complexity", 5)
        confidence = intent.get("confidence", 0.7)

        # 1) Infer which tables are likely needed, then build schema text
        tables_needed = self._infer_tables(question, intent)
        schema_context = self.schema_builder.build_schema_context(tables_needed)

        # 2) High-level system role
        header = f"""
You are an expert BI developer working with the Microsoft ContosoRetailDW SQL Server data warehouse (star schema).

Your job:
- Convert a business question into a SINGLE valid T-SQL query.
- Use ONLY real tables and columns from the provided CONTOSO SCHEMA.
- Strictly follow Contoso business rules and join patterns.

User question (in Turkish or English):
"{question}"

Detected intent:
- Type: {query_type}
- Complexity: {complexity}/10
- Confidence: {confidence:.2f}

IMPORTANT:
- Database: SQL Server (T-SQL)
- Use SELECT ... FROM ..., INNER JOIN, LEFT JOIN, etc.
- Use SELECT TOP N ... ORDER BY ... instead of LIMIT.
- NEVER use YEAR(DateKey) or similar functions directly on DateKey.
- ALWAYS join DimDate and filter via dd.CalendarYear, dd.CalendarMonth, etc.

Below is the relevant part of the Contoso schema and business rules:
{schema_context}
"""

        # 3) Strategy-specific part
        if strategy == "direct":
            body = self._build_direct_instructions()
        elif strategy == "few_shot":
            body = self._build_few_shot_instructions(examples)
        elif strategy == "chain_of_thought":
            body = self._build_chain_of_thought_instructions()
        elif strategy == "correction":
            body = self._build_correction_instructions(error_context)
        else:
            # Fallback to direct
            body = self._build_direct_instructions()

        # 4) Add output format contract
        prompt = header + "\n" + body + "\n" + OUTPUT_FORMAT_INSTRUCTION + "\n"
        return prompt

    # --------------------------------------------------------
    # STRATEGY SUB-PROMPTS
    # --------------------------------------------------------
    def _build_direct_instructions(self) -> str:
        return """
STRATEGY: DIRECT SQL GENERATION

Generate a single, clean T-SQL query that answers the question.
- Prefer simple, readable SQL.
- Use correct joins based on the schema and rules.
- Use GROUP BY whenever you select non-aggregated columns together with aggregates.
- Use ORDER BY when returning rankings or top-N results.
"""

    def _build_few_shot_instructions(self, examples: Optional[List[Dict]]) -> str:
        text = """
STRATEGY: FEW-SHOT SQL GENERATION

Generate a T-SQL query inspired by the style of previous successful queries.
Re-use patterns like:
- FactSales/FactOnlineSales + DimDate for time filtering
- DimProduct + DimProductSubcategory + DimProductCategory for product/category analysis
- DimStore / DimGeography for store and region analysis

Previous successful examples (for STYLE ONLY, do NOT copy table/column names that don't exist in the schema):
"""

        if examples:
            for i, ex in enumerate(examples, start=1):
                q = ex.get("question", "").strip()
                sql = (ex.get("sql", "") or "").strip()
                if not q or not sql:
                    continue
                text += f"""
Example {i}:
Q: {q}
SQL:
{sql}
"""
        else:
            text += "\n(No previous examples found, just follow the schema and rules.)\n"

        return text

    def _build_chain_of_thought_instructions(self) -> str:
        return """
STRATEGY: CHAIN-OF-THOUGHT (DEEP REASONING)

You may think step-by-step INTERNALLY, but in the final answer you MUST:
- Output ONLY the final SQL query
- Then output EXPLANATION: on a new line

When reasoning about the query:
- Choose the correct fact table(s) based on the question (FactSales vs FactOnlineSales)
- Join DimDate, DimProduct, DimCustomer, DimStore, DimGeography, etc. as needed
- For comparisons (store vs online, 2007 vs 2008), use either:
    • UNION ALL with matching column lists, OR
    • a single query with conditional aggregation (preferred)
- For top-N products or stores, use:
    SELECT TOP N ... ORDER BY <metric> DESC
"""

    def _build_correction_instructions(self, error_context: Optional[str]) -> str:
        base = """
STRATEGY: SQL CORRECTION

You are given a previous SQL attempt and its validation errors.
Your job is to FIX the SQL so that:
- It uses only valid tables/columns from the schema
- It respects Contoso business rules and join patterns
- It is syntactically valid T-SQL for SQL Server
- It correctly answers the original business question

DO NOT explain the error in the SQL itself.
"""

        if error_context:
            base += f"""

Here is the previous attempt and the validation feedback:
{error_context}

Now generate a NEW corrected SQL query (do NOT just patch small pieces).
"""
        return base

    # --------------------------------------------------------
    # TABLE INFERENCE (WHICH TABLES TO SHOW TO LLM)
    # --------------------------------------------------------
    def _infer_tables(self, question: str, intent: Dict) -> List[str]:
        """
        Heuristic: choose a small set of relevant tables to reduce LLM confusion.
        """

        q = (question or "").lower()
        qtype = intent.get("query_type", "aggregation")

        # Always include the core facts & DimDate
        tables: List[str] = [
            "FactSales",
            "FactOnlineSales",
            "DimDate",
        ]

        # Product-related?
        if any(k in q for k in ["ürün", "urun", "product", "kategori", "category", "subkategori", "subcategory"]):
            tables += [
                "DimProduct",
                "DimProductSubcategory",
                "DimProductCategory",
            ]

        # Store / geography related?
        if any(k in q for k in ["mağaza", "magaza", "store", "bölge", "bolge", "region", "ülke", "ulke", "city"]):
            tables += [
                "DimStore",
                "DimGeography",
            ]

        # Customer related?
        if any(k in q for k in ["müşteri", "musteri", "customer", "online"]):
            tables += [
                "DimCustomer",
                "DimGeography",
            ]

        # Time-series / trend questions (we already have DimDate, but ensure)
        if qtype == "trend":
            if "DimDate" not in tables:
                tables.append("DimDate")

        # Remove duplicates while preserving order
        seen: set = set()
        unique_tables: List[str] = []
        for t in tables:
            if t not in seen:
                unique_tables.append(t)
                seen.add(t)

        logger.info(f"🧠 SchemaBuilder will include tables: {unique_tables}")
        return unique_tables
