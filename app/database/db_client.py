# app/database/db_client.py - Clean Production Version (2025)
"""
Database Client for Direct SQL Execution (pyodbc)
- Fast, robust connection handling
- Schema discovery for LLM + validator
- Unified execute_sql interface for FastAPI
"""

import pyodbc
import decimal
import time
from typing import List, Dict, Any, Optional

from app.utils.logger import get_logger
from app.core.config import Config

logger = get_logger(__name__)


# --------------------------------------------------------
# DECIMAL → FLOAT CONVERTER
# --------------------------------------------------------
def _convert_value(val):
    if isinstance(val, decimal.Decimal):
        return float(val)
    return val


# --------------------------------------------------------
# DATABASE CLIENT
# --------------------------------------------------------
class DatabaseClient:

    def __init__(self):
        self.conn_str = (
            f"DRIVER={{{Config.DB_DRIVER}}};"
            f"SERVER={Config.DB_SERVER};"
            f"DATABASE={Config.DB_NAME};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
            "MARS_Connection=yes;"
            "Connection Timeout=3;"
        )

        self._tables_cache = None
        self._schema_cache = {}

        logger.info(f"DatabaseClient initialized for server={Config.DB_SERVER}")

    # ----------------------------
    # CONNECTION
    # ----------------------------
    def get_connection(self):
        try:
            return pyodbc.connect(self.conn_str, timeout=3)
        except Exception as e:
            logger.error(f"❌ DB connection failed: {e}")
            raise

    # ----------------------------
    # SCHEMA DISCOVERY
    # ----------------------------
    def get_all_tables(self, refresh: bool = False) -> List[str]:
        if self._tables_cache and not refresh:
            return self._tables_cache

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA='dbo' AND TABLE_TYPE='BASE TABLE'
                ORDER BY TABLE_NAME
            """)

            tables = [row[0] for row in cursor.fetchall()]

            self._tables_cache = tables

            cursor.close()
            conn.close()
            return tables

        except Exception as e:
            logger.error(f"Failed to fetch table list: {e}")
            return []

    def get_table_columns(self, table_name: str):
        if table_name in self._schema_cache:
            return self._schema_cache[table_name]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?
                ORDER BY ORDINAL_POSITION
            """, table_name)

            columns = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                }
                for row in cursor.fetchall()
            ]

            self._schema_cache[table_name] = columns

            cursor.close()
            conn.close()
            return columns

        except Exception as e:
            logger.error(f"Failed to fetch schema for {table_name}: {e}")
            return []

    # ----------------------------
    # SQL EXECUTION (low-level)
    # ----------------------------
    def execute_query(self, query: str):
        """
        Low-level executor.
        Returns (rows, exec_time)
        """
        conn = None
        cursor = None
        start = time.time()

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query)

            # SELECT
            if cursor.description:
                cols = [c[0] for c in cursor.description]
                rows = []

                for row in cursor.fetchall():
                    rows.append({
                        cols[i]: _convert_value(row[i])
                        for i in range(len(cols))
                    })

                exec_time = time.time() - start
                return rows, exec_time

            # Non-select — UPDATE/INSERT/DELETE
            conn.commit()
            exec_time = time.time() - start
            return [{"affected_rows": cursor.rowcount}], exec_time

        except Exception as e:
            exec_time = time.time() - start
            logger.error(f"❌ SQL execution error: {e}")
            return [{"error": str(e)}], exec_time

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


# --------------------------------------------------------
# PUBLIC EXECUTE FUNCTION (API uses THIS)
# --------------------------------------------------------
_db_client = None

def get_db_client() -> DatabaseClient:
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client


def execute_sql(sql: str):
    """
    FastAPI expects ONLY the rows.
    Execution time is tracked by API itself.
    """
    client = get_db_client()
    rows, _ = client.execute_query(sql)
    return rows
