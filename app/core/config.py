# app/core/config.py
"""
Centralized configuration for Harmony AI Assistant (2025)
Supports:
- Dynamic multi-model LLM (SQL model + Summary model)
- OpenAI fallback
- DB fast connections with timeout + MARS
"""

import os


class Config:
    """Application configuration"""

    # ============================================================
    # DATABASE
    # ============================================================
    DB_SERVER = os.getenv("DB_SERVER", "localhost")
    DB_NAME = os.getenv("DB_NAME", "ContosoRetailDW")
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")

    @classmethod
    def get_db_connection_string(cls) -> str:
        """
        Final optimized SQL Server connection string:
        - Trusted connection
        - MARS enabled (multiple active result sets)
        - Fast 3-second connection timeout
        """
        return (
            f"DRIVER={{{cls.DB_DRIVER}}};"
            f"SERVER={cls.DB_SERVER};"
            f"DATABASE={cls.DB_NAME};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
            "MARS_Connection=yes;"
            "Connection Timeout=3;"
        )

    # ============================================================
    # OLLAMA (PRIMARY LLM SYSTEM)
    # ============================================================
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # 🔥 MULTI-MODEL SUPPORT
    OLLAMA_SQL_MODEL = os.getenv("OLLAMA_SQL_MODEL", "llama3.1:8b")
    OLLAMA_SUMMARY_MODEL = os.getenv("OLLAMA_SUMMARY_MODEL", "llama3.2:latest")

    # ============================================================
    # OPENAI FALLBACK (SECONDARY LLM)
    # ============================================================
    ENABLE_OPENAI_FALLBACK = (
        os.getenv("ENABLE_OPENAI_FALLBACK", "false").lower() == "true"
    )

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "60"))

    # No key → fallback disabled automatically
    if not OPENAI_API_KEY:
        ENABLE_OPENAI_FALLBACK = False

    # ============================================================
    # APPLICATION SETTINGS
    # ============================================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_QUERY_LOGGING = os.getenv("ENABLE_QUERY_LOGGING", "true").lower() == "true"
    ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"

    # Strategy thresholds
    COMPLEXITY_THRESHOLD_DIRECT = 3
    COMPLEXITY_THRESHOLD_FEW_SHOT = 7

    # ============================================================
    # PATHS
    # ============================================================
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    QUERY_HISTORY_PATH = os.path.join(DATA_DIR, "query_history.jsonl")
    SCHEMA_CACHE_PATH = os.path.join(DATA_DIR, "schema_cache.json")

    @classmethod
    def ensure_data_dir(cls):
        os.makedirs(cls.DATA_DIR, exist_ok=True)


# Ensure data directory exists on import
Config.ensure_data_dir()
