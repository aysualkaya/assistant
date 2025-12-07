# app/database/__init__.py
"""
Database Package
----------------
Provides:
- get_db_client(): Singleton database client instance
- DatabaseClient:  Direct class access (optional)
"""

from app.database.db_client import DatabaseClient, get_db_client

__all__ = [
    "DatabaseClient",
    "get_db_client",
]
