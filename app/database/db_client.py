# app/database/db_client.py - FINAL PRODUCTION VERSION (2025)
"""
Database Client with Dynamic Schema Discovery + Execution Time Support
- Returns: (rows, execution_time)
- Fast connection (MARS + 3s timeout)
- Full schema discovery
- Safe Decimal → float conversion
"""

import pyodbc
import decimal
import json
import time
from typing import List, Dict, Any, Optional
from app.utils.logger import get_logger
from app.core.config import Config

logger = get_logger(__name__)


# --------------------------------------------------------
# JSON ENCODER FOR DECIMAL
# --------------------------------------------------------
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


# --------------------------------------------------------
# DATABASE CLIENT
# --------------------------------------------------------
class DatabaseClient:
    """
    Full production SQL client
    Supports:
    ✔ Dynamic schema discovery
    ✔ Fast stable connections
    ✔ Accurate execution time reporting
    """

    def __init__(self, connection_string: Optional[str] = None):
        base = connection_string or Config.get_db_connection_string()

        # Add MARS + timeout
        extra = ";MARS_Connection=yes;Connection Timeout=3"

        if not base.endswith(";"):
            base += ";"

        self.conn_str = base + extra

        # Local caches
        self._tables_cache = None
        self._schema_cache = {}

        logger.debug(
            f"DatabaseClient initialized: server={Config.DB_SERVER}, db={Config.DB_NAME}"
        )

    # --------------------------------------------------------
    # FAST CONNECTION
    # --------------------------------------------------------
    def get_connection(self):
        """Open fast DB connection"""
        try:
            logger.info(f"Connecting fast DB server={Config.DB_SERVER}, db={Config.DB_NAME}")
            return pyodbc.connect(self.conn_str, timeout=3)
        except Exception as e:
            logger.error(f"❌ DB connection failed: {e}")
            raise e

    # --------------------------------------------------------
    # SCHEMA DISCOVERY
    # --------------------------------------------------------
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
            tables = [t for t in tables if not t.startswith("sys")]

            self._tables_cache = tables
            logger.info(f"📋 Found {len(tables)} tables")

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
            """, (table_name,))

            columns = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES"
                }
                for row in cursor.fetchall()
            ]

            self._schema_cache[table_name] = columns
            logger.debug(f"📋 Columns loaded: {table_name} ({len(columns)})")

            cursor.close()
            conn.close()
            return columns

        except Exception as e:
            logger.error(f"Failed to fetch schema for {table_name}: {e}")
            return []

    def get_full_schema(self, tables=None):
        if not tables:
            tables = self.get_all_tables()
        schema = {t: self.get_table_columns(t) for t in tables}
        logger.info(f"📋 Full schema loaded for {len(schema)} tables")
        return schema

    def clear_schema_cache(self):
        self._tables_cache = None
        self._schema_cache = {}
        logger.info("🗑️ Schema cache cleared")

    # --------------------------------------------------------
    # QUERY EXECUTION (UPDATED)
    # --------------------------------------------------------
    def execute_query(self, query: str):
        """
        Execute SQL with:
        ✔ execution time
        ✔ SELECT → list[dict]
        ✔ Non-select → affected rows
        Returns:
            (rows, exec_time)
        """
        conn = None
        cursor = None
        start = time.time()

        try:
            logger.info(f"Executing SQL: {query[:120]}...")
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(query)

            # SELECT
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                rows_raw = cursor.fetchall()

                rows = []
                for row in rows_raw:
                    item = {}
                    for i, col in enumerate(columns):
                        val = row[i]
                        if isinstance(val, decimal.Decimal):
                            val = float(val)
                        item[col] = val
                    rows.append(item)

                exec_time = time.time() - start
                logger.info(f"Query returned {len(rows)} rows in {exec_time:.2f}s")
                return rows, exec_time

            # Non-select queries
            conn.commit()
            affected = cursor.rowcount
            exec_time = time.time() - start

            logger.info(f"Non-select query affected {affected} rows in {exec_time:.2f}s")
            return [{"affected_rows": affected}], exec_time

        except Exception as e:
            exec_time = time.time() - start
            logger.error(f"❌ SQL error after {exec_time:.2f}s: {e}")
            return {"error": str(e)}, exec_time

        finally:
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            except Exception as e:
                logger.warning(f"Error closing DB connection: {e}")

    # --------------------------------------------------------
    # TEST CONNECTION
    # --------------------------------------------------------
    def test_connection(self):
        try:
            conn = self.get_connection()
            conn.close()
            logger.info("✅ DB connection test OK")
            return True
        except Exception as e:
            logger.error(f"❌ DB connection test failed: {e}")
            return False


# --------------------------------------------------------
# LEGACY HELPERS (STREAMLIT COMPATIBILITY)
# --------------------------------------------------------
def get_connection():
    return DatabaseClient().get_connection()


def execute_sql(query: str):
    return DatabaseClient().execute_query(query)


# --------------------------------------------------------
# SINGLETON ACCESSOR
# --------------------------------------------------------
_db_client = None

def get_db_client() -> DatabaseClient:
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client
