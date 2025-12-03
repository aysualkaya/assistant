# app/core/config.py
"""
Configuration management for the assistant
"""

import os
from typing import Dict, Any


class Config:
    """Application configuration"""
    
    # Database
    DB_SERVER = os.getenv("DB_SERVER", "Aysu-HUMA")
    DB_NAME = os.getenv("DB_NAME", "ContosoRetailDW")
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    
    # LLM
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
    
    # Application
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_QUERY_LOGGING = os.getenv("ENABLE_QUERY_LOGGING", "true").lower() == "true"
    ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    
    # Strategy selection thresholds
    COMPLEXITY_THRESHOLD_DIRECT = 3      # <= 3: Direct generation
    COMPLEXITY_THRESHOLD_FEW_SHOT = 7    # <= 7: Few-shot learning
    # > 7: Chain-of-thought
    
    # Paths
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    QUERY_HISTORY_PATH = os.path.join(DATA_DIR, "query_history.jsonl")
    SCHEMA_CACHE_PATH = os.path.join(DATA_DIR, "schema_cache.json")
    
    @classmethod
    def get_db_connection_string(cls) -> str:
        """Get database connection string"""
        return (
            f"DRIVER={{{cls.DB_DRIVER}}};"
            f"SERVER={cls.DB_SERVER};"
            f"DATABASE={cls.DB_NAME};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
    
    @classmethod
    def ensure_data_dir(cls):
        """Ensure data directory exists"""
        os.makedirs(cls.DATA_DIR, exist_ok=True)


# Initialize data directory on import
Config.ensure_data_dir()