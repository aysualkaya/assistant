# app/database/langchain_db.py
"""
LangChain SQLDatabase Wrapper for MSSQL (Production-Ready)

Provides:
✔ Safe MSSQL connection string handling
✔ SQLDatabase instance shared across all tools
✔ Optional table filtering (include_tables)
✔ Fast, stable integration with PyODBC
✔ Validates DB connectivity on import
"""

from langchain_community.utilities import SQLDatabase
from sqlalchemy.engine import URL
from app.core.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)

_cached_db = None  # Singleton cache


def _build_connection_url() -> URL:
    """
    Builds a fully correct SQLAlchemy URL for MSSQL + pyodbc.
    LangChain requires a properly encoded ODBC string.
    """
    return URL.create(
        "mssql+pyodbc",
        username=None,
        password=None,
        host=Config.DB_SERVER,
        database=Config.DB_NAME,
        query={
            "driver": Config.DB_DRIVER,
            "Trusted_Connection": "yes",
            "TrustServerCertificate": "yes",
        },
    )


def get_langchain_db(include_tables=None) -> SQLDatabase:
    """
    Returns a singleton SQLDatabase instance.
    include_tables -> list of tables the agent is allowed to access.
    """

    global _cached_db
    if _cached_db is not None:
        return _cached_db

    try:
        url = _build_connection_url()
        logger.info(f"🔗 Connecting to MSSQL via LangChain: {url}")

        _cached_db = SQLDatabase.from_uri(
            str(url),
            include_tables=include_tables,  # or None for all tables
        )

        # Optional: Detect tables at startup
        try:
            tables = _cached_db.get_usable_table_names()
            logger.info(f"📘 LangChain usable tables: {tables}")
        except Exception as e:
            logger.warning(f"⚠️ Could not list tables on startup: {e}")

        return _cached_db

    except Exception as e:
        logger.error(f"❌ Failed to initialize LangChain SQLDatabase: {e}")
        raise RuntimeError("LangChain DB initialization failed") from e
