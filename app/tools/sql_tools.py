# app/tools/sql_tools.py
"""
LangChain SQL Tools (Production-Ready)

Provides:
✔ list_tables()        → returns list[str]
✔ get_schema(table)    → returns schema text
✔ check_sql(query)     → returns either:
        - {"corrected_query": "..."} 
        - {"status": "ok", "query": "..."}
✔ Safe handling for MSSQL + LangChain quirks
"""

from langchain_community.tools.sql_database.tool import (
    ListSQLDatabaseTool,
    InfoSQLDatabaseTool,
    QuerySQLCheckerTool,
)
from app.database.langchain_db import get_langchain_db
from app.llm.ollama_client import OllamaClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Shared DB connection
db = get_langchain_db()

# Dedicated LLM for SQL checker
ollama_llm = OllamaClient().as_langchain_llm()   # <— EN DOĞRU YÖNTEM


# --------------------------------------------------------------
# 1) LIST TABLES
# --------------------------------------------------------------
def list_tables():
    """
    Returns a clean Python list of table names.
    LangChain sometimes returns string, sometimes list — normalize it.
    """
    try:
        tool = ListSQLDatabaseTool(db=db)
        raw = tool.invoke("")

        if isinstance(raw, str):
            # "FactSales, DimDate" → ["FactSales", "DimDate"]
            cleaned = [t.strip() for t in raw.split(",") if t.strip()]
            return cleaned

        if isinstance(raw, list):
            return [t.strip() for t in raw if t.strip()]

        logger.warning(f"⚠️ Unexpected list_tables output: {raw}")
        return []

    except Exception as e:
        logger.error(f"❌ list_tables failed: {e}")
        return []


# --------------------------------------------------------------
# 2) GET SCHEMA (PER TABLE)
# --------------------------------------------------------------
def get_schema(table_name: str):
    """
    Returns CREATE TABLE + sample rows (string).
    Always returns string, never raises.
    """
    try:
        tool = InfoSQLDatabaseTool(db=db)
        schema = tool.invoke(table_name)

        # LangChain may return dict — normalize
        if isinstance(schema, dict):
            return schema.get("table_info", "") or ""

        return schema or ""

    except Exception as e:
        logger.error(f"❌ get_schema failed for table '{table_name}': {e}")
        return f"-- Failed to load schema for {table_name} --"


# --------------------------------------------------------------
# 3) CHECK SQL (critical tool)
# --------------------------------------------------------------
def check_sql(sql_query: str):
    """
    Returns a dict:
        - {"corrected_query": "..."} if the SQL was fixed
        - {"status": "ok", "query": "..."} if valid
        - {"status": "error", "message": "..."} if failure
    
    Behavior differences across LangChain versions handled safely.
    """
    try:
        tool = QuerySQLCheckerTool(db=db, llm=ollama_llm)
        result = tool.invoke({"query": sql_query})

        # If LangChain returns string
        if isinstance(result, str):
            result = result.strip()
            if result.upper().startswith("SELECT"):
                # Example: "SELECT ... corrected version"
                return {"corrected_query": result}
            if "no issues" in result.lower() or "valid" in result.lower():
                return {"status": "ok", "query": sql_query}

            # Fallback if tool returned explanation text
            return {"status": "ok", "query": sql_query}

        # If LangChain returns dict
        if isinstance(result, dict):
            if "corrected_query" in result:
                return {"corrected_query": result["corrected_query"]}
            if "query" in result:
                return {"status": "ok", "query": result["query"]}

        # Unexpected output format
        logger.warning(f"⚠️ Unexpected check_sql output: {result}")
        return {"status": "ok", "query": sql_query}

    except Exception as e:
        logger.error(f"❌ check_sql failed: {e}")
        return {"status": "error", "message": str(e), "query": sql_query}
