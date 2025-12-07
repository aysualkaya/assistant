# app/core/config.py
"""
Harmony AI — Central Configuration (2025 Final Edition)
Robust, fault-tolerant, production-safe configuration.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Global system configuration"""

    # ============================================================
    # DATABASE (MSSQL)
    # ============================================================
    DB_SERVER = os.getenv("DB_SERVER", "localhost")
    DB_NAME = os.getenv("DB_NAME", "ContosoRetailDW")
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "5"))

    @classmethod
    def get_odbc_params(cls) -> dict:
        """Used by LangChain SQLDatabase URL builder."""
        return {
            "driver": cls.DB_DRIVER,
            "Trusted_Connection": "yes",
            "TrustServerCertificate": "yes",
        }

    # ============================================================
    # OLLAMA (Primary LLM system)
    # ============================================================
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # Normalize model names (auto-add :8b suffix)
    def _normalize_model(name: str, default_suffix=":8b"):
        if ":" not in name:
            return name + default_suffix
        return name

    OLLAMA_SQL_MODEL = _normalize_model(os.getenv("OLLAMA_SQL_MODEL", "llama3.1"))
    OLLAMA_SUMMARY_MODEL = _normalize_model(os.getenv("OLLAMA_SUMMARY_MODEL", "llama3.2"))

    # ============================================================
    # OPENAI FALLBACK (Optional)
    # ============================================================
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    ENABLE_OPENAI_FALLBACK = bool(OPENAI_API_KEY.strip()) if OPENAI_API_KEY else False

    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "60"))

    # ============================================================
    # LOGGING
    # ============================================================
    LOG_LEVEL = (os.getenv("LOG_LEVEL", "INFO") or "INFO").upper()

    ENABLE_FILE_LOGS = os.getenv("ENABLE_FILE_LOGS", "false").lower() == "true"

    # ============================================================
    # APP SETTINGS (Missing before)
    # ============================================================
    ENABLE_QUERY_LOGGING = os.getenv("ENABLE_QUERY_LOGGING", "true").lower() == "true"

    # ⭐ CRITICAL FIX — required by OllamaClient
    ENABLE_CACHING = os.getenv("ENABLE_CACHING", "false").lower() == "true"

    # Optional thresholds used in SQLGenerator
    COMPLEXITY_THRESHOLD_DIRECT = int(os.getenv("COMPLEXITY_THRESHOLD_DIRECT", "3"))
    COMPLEXITY_THRESHOLD_FEW_SHOT = int(os.getenv("COMPLEXITY_THRESHOLD_FEW_SHOT", "6"))

    # ============================================================
    # DATA & STORAGE
    # ============================================================
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    DATA_DIR = os.path.join(BASE_DIR, "data")
    QUERY_HISTORY_PATH = os.path.join(DATA_DIR, "query_history.jsonl")
    SCHEMA_CACHE_PATH = os.path.join(DATA_DIR, "schema_cache.json")

    @classmethod
    def ensure_dirs(cls):
        os.makedirs(cls.DATA_DIR, exist_ok=True)


Config.ensure_dirs()
