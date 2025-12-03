# app/llm/__init__.py
"""
LLM Package - SQL Generation, Summarization, Ollama Client

Keep imports lazy to avoid circular dependencies
"""

# No imports here - all lazy loaded

__all__ = []

# Lazy imports
def get_ollama_client():
    """Lazy import"""
    from app.llm.ollama_client import OllamaClient
    return OllamaClient

def get_sql_generator():
    """Lazy import"""
    from app.llm.sql_generator import DynamicSQLGenerator
    return DynamicSQLGenerator

def get_result_summarizer():
    """Lazy import"""
    from app.llm.result_summarizer import ResultSummarizer
    return ResultSummarizer

def get_prompt_manager():
    """Lazy import"""
    from app.llm.prompt_manager import PromptManager
    return PromptManager