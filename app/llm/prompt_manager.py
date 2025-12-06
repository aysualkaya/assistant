# app/llm/prompt_manager.py
"""
Unified Prompt Manager (2025)

Works with:
- Ollama (string prompt)
- OpenAI responses API (system + user role separation done in client)

Key features:
- Stable SQL-only output format
- Hybrid intent support
- Schema-aware prompting
"""

from typing import Dict, List, Optional
from app.core.schema_builder import DynamicSchemaBuilder
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ===============================================================
# STRICT OUTPUT FORMAT (SQL → EXPLANATION)
# ===============================================================
OUTPUT_CONTRACT = """
YOU MUST FOLLOW THIS OUTPUT FORMAT EXACTLY:

1) Write ONLY the final SQL query as plain text. No backticks. No markdown. No comments.
2) Then add a blank line.
3) Then write: EXPLANATION:
4) Then a short explanation in natural language.

Never write anything before the SQL query.
Never write markdown fences.
Never write multiple SQL queries.
"""


class PromptManager:

    def __init__(self):
        self.schema_builder = DynamicSchemaBuilder()
        self.logger = get_logger(__name__)

    # =======================================================================
    # PUBLIC FUNCTION — Build the unified prompt for the LLM
    # =======================================================================
    def build_sql_prompt(
        self,
        question: str,
        intent: Dict,
        strategy: str,
        examples: Optional[List[Dict]] = None,
        error_context: Optional[str] = None,
        llm_mode: str = "ollama",   # NEW: "ollama" or "openai"
    ) -> str:

        query_type = intent.get("query_type", "aggregation")
        complexity = intent.get("complexity", 5)
        confidence = intent.get("confidence", 0.5)

        # Infer which schema pieces to show
        tables = self._infer_tables(question, intent)

        # Decide schema mode based on LLM
        schema_mode = "openai" if llm_mode == "openai" else "ollama"
        schema_context = self.schema_builder.build_schema_context(
            tables_needed=tables,
            mode=schema_mode,
        )

        # ===================================================================
        # SYSTEM-STYLE ROLE (SAFE FOR BOTH OLLAMA + OPENAI)
        # ===================================================================
        system_block = f"""
You are a senior Business Intelligence engineer who writes perfect SQL Server (T-SQL) queries.
Your goal is to convert user questions into a SINGLE SQL query.

Rules you MUST follow:
- Use ONLY tables/columns shown in the schema context.
- Use correct ContosoRetailDW join paths.
- Use SELECT TOP N ... ORDER BY ... for ranking queries.
- NEVER use LIMIT (SQL Server does not support it).
- NEVER use functions directly on DateKey.
- ALWAYS join DimDate and filter via CalendarYear / CalendarMonth.
- Output format MUST follow the exact contract at the end.

User question:
"{question}"

Detected intent:
- Type: {query_type}
- Complexity: {complexity}
- Confidence: {confidence}

Relevant schema context:
{schema_context}
""".strip()

        # ===================================================================
        # STRATEGY BLOCK
        # ===================================================================
        if strategy == "direct":
            strategy_block = self._direct_block()

        elif strategy == "few_shot":
            strategy_block = self._few_shot_block(examples)

        elif strategy == "chain_of_thought":
            strategy_block = self._cot_block()

        elif strategy == "correction":
            strategy_block = self._correction_block(error_context)

        else:
            strategy_block = self._direct_block()

        # ===================================================================
        # FULL PROMPT (safe for both LLMs)
        # ===================================================================
        prompt = (
            system_block
            + "\n\n"
            + strategy_block
            + "\n\n"
            + OUTPUT_CONTRACT
        )

        return prompt

    # =======================================================================
    # STRATEGY SUBPROMPTS
    # =======================================================================
    def _direct_block(self):
        return """
STRATEGY: DIRECT SQL GENERATION
Write a single, correct, clean, production-quality SQL query.
""".strip()

    def _few_shot_block(self, examples: Optional[List[Dict]]):
        text = """
STRATEGY: FEW-SHOT SQL GENERATION
Use style patterns similar to previous correct queries.
Do NOT copy irrelevant columns; follow schema strictly.
""".strip()

        if examples:
            for ex in examples:
                q = ex.get("question", "").strip()
                sql = ex.get("sql", "").strip()
                if not q or not sql:
                    continue
                text += f"\n\nExample:\nQ: {q}\nSQL:\n{sql}"

        return text

    def _cot_block(self):
        return """
STRATEGY: CHAIN-OF-THOUGHT (internal reasoning allowed)
- Think step-by-step internally.
- Final output MUST follow the SQL → EXPLANATION format.
""".strip()

    def _correction_block(self, error_context: Optional[str]):
        block = """
STRATEGY: SQL CORRECTION
Fix the SQL so that it becomes valid, correct, and schema-compliant.
Replace the entire query with a new correct one.
""".strip()

        if error_context:
            block += f"\n\nPrevious attempt + validation errors:\n{error_context}"

        return block

    # =======================================================================
    # TABLE INFERENCE
    # =======================================================================
    def _infer_tables(self, question: str, intent: Dict) -> List[str]:
        q = question.lower()
        tables = ["FactSales", "FactOnlineSales", "DimDate"]

        if any(k in q for k in ["ürün", "urun", "product", "kategori"]):
            tables += ["DimProduct", "DimProductSubcategory", "DimProductCategory"]

        if any(k in q for k in ["mağaza", "magaza", "store", "city", "region"]):
            tables += ["DimStore", "DimGeography"]

        if any(k in q for k in ["müşteri", "musteri", "customer"]):
            tables += ["DimCustomer"]

        # Deduplicate
        seen = set()
        unique = []
        for t in tables:
            if t not in seen:
                unique.append(t)
                seen.add(t)

        return unique
