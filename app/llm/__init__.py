# app/llm/__init__.py
"""
LLM Package
-----------
Provides lazy-loaded access to all LLM-related components:

Components:
- OllamaClient        → Primary LLM (SQL + Summary)
- DynamicSQLGenerator → Core SQL generation engine
- ResultSummarizer    → TR/EN business summary generator
- PromptManager       → Unified prompt templates & rules

Lazy imports avoid circular dependencies and reduce import overhead.
"""

__all__ = [
    "get_ollama_client",
    "get_sql_generator",
    "get_result_summarizer",
    "get_prompt_manager",
]


# -------------------------------------------------------------------
# LAZY IMPORT HELPERS
# -------------------------------------------------------------------
def get_ollama_client():
    """Return OllamaClient class lazily."""
    from app.llm.ollama_client import OllamaClient
    return OllamaClient


def get_sql_generator():
    """Return SQL Generator class lazily."""
    from app.llm.sql_generator import DynamicSQLGenerator
    return DynamicSQLGenerator


def get_result_summarizer():
    """Return summarizer class lazily."""
    from app.llm.result_summarizer import ResultSummarizer
    return ResultSummarizer


def get_prompt_manager():
    """Return PromptManager class lazily."""
    from app.llm.prompt_manager import PromptManager
    return PromptManager
