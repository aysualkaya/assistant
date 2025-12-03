# app/database/db_client.py - DYNAMIC SCHEMA VERSION
"""
Database Client with Dynamic Schema Discovery
NOW INCLUDES:
- get_all_tables() - Read tables from INFORMATION_SCHEMA
- get_table_columns() - Read columns for specific table
- get_full_schema() - Cache entire schema structure
"""

import pyodbc
import decimal
import json
from typing import List, Dict, Any, Optional
from app.utils.logger import get_logger
from app.core.config import Config

logger = get_logger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal objects"""
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


class DatabaseClient:
    """
    Enhanced Database client with dynamic schema discovery
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        if connection_string:
            self.conn_str = connection_string
        else:
            self.conn_str = Config.get_db_connection_string()
        
        # Cache for schema information
        self._tables_cache = None
        self._schema_cache = {}
        
        logger.debug(f"DatabaseClient initialized with server: {Config.DB_SERVER}")
    
    def get_connection(self):
        """Establishes database connection"""
        try:
            logger.info(f"Connecting to DB server={Config.DB_SERVER}, database={Config.DB_NAME}")
            return pyodbc.connect(self.conn_str)
        except Exception as e:
            logger.error(f"DB connection failed: {e}")
            raise e
    
    # ========================================
    # DYNAMIC SCHEMA DISCOVERY (NEW!)
    # ========================================
    
    def get_all_tables(self, refresh: bool = False) -> List[str]:
        """
        Get all table names from database
        
        Args:
            refresh: Force refresh cache
            
        Returns:
            List of table names
        """
        if self._tables_cache and not refresh:
            return self._tables_cache
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Query INFORMATION_SCHEMA
            query = """
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = 'dbo'
            AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
            """
            
            cursor.execute(query)
            tables = [row[0] for row in cursor.fetchall()]
            
            # Filter out system tables
            tables = [t for t in tables if not t.startswith('sys')]
            
            # Cache results
            self._tables_cache = tables
            
            logger.info(f"📋 Found {len(tables)} tables in database")
            
            cursor.close()
            conn.close()
            
            return tables
            
        except Exception as e:
            logger.error(f"Failed to get table list: {e}")
            # Return empty list on failure
            return []
    
    def get_table_columns(self, table_name: str) -> List[Dict[str, str]]:
        """
        Get columns for a specific table
        
        Args:
            table_name: Table name
            
        Returns:
            List of dicts with column info: {name, type, nullable}
        """
        # Check cache
        if table_name in self._schema_cache:
            return self._schema_cache[table_name]
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
            AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """
            
            cursor.execute(query, (table_name,))
            
            columns = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == 'YES'
                }
                for row in cursor.fetchall()
            ]
            
            # Cache results
            self._schema_cache[table_name] = columns
            
            logger.debug(f"📋 Table {table_name} has {len(columns)} columns")
            
            cursor.close()
            conn.close()
            
            return columns
            
        except Exception as e:
            logger.error(f"Failed to get columns for {table_name}: {e}")
            return []
    
    def get_full_schema(self, tables: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """
        Get full schema (all tables + columns)
        
        Args:
            tables: Optional list of tables to fetch (default: all)
            
        Returns:
            Dict mapping table_name -> column_list
        """
        if not tables:
            tables = self.get_all_tables()
        
        schema = {}
        for table in tables:
            schema[table] = self.get_table_columns(table)
        
        logger.info(f"📋 Retrieved full schema for {len(schema)} tables")
        return schema
    
    def clear_schema_cache(self):
        """Clear cached schema information"""
        self._tables_cache = None
        self._schema_cache = {}
        logger.info("🗑️ Schema cache cleared")
    
    # ========================================
    # QUERY EXECUTION (UNCHANGED)
    # ========================================
    
    def execute_query(self, query: str) -> Any:
        """
        Execute SQL query with automatic type conversion
        
        Args:
            query: SQL query string
            
        Returns:
            List of dicts for SELECT queries
            Dict with status for non-SELECT queries
            Dict with error if execution fails
        """
        conn = None
        cursor = None
        
        try:
            logger.info(f"Executing SQL: {query[:100]}...")
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            
            if cursor.description:
                # SELECT query - return results
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                result = []
                
                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Convert Decimal to float for JSON serialization
                        if isinstance(value, decimal.Decimal):
                            value = float(value)
                        row_dict[col] = value
                    result.append(row_dict)
                
                logger.info(f"Query returned {len(result)} rows")
                return result
            else:
                # INSERT / UPDATE / DELETE - commit and return status
                conn.commit()
                rowcount = cursor.rowcount
                logger.info(f"Query executed successfully, {rowcount} rows affected")
                return {
                    "message": "Query executed successfully",
                    "rowcount": rowcount
                }
                
        except pyodbc.Error as e:
            logger.error(f"SQL execution error: {e}")
            return {"error": str(e)}
            
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
            
        finally:
            # Always close resources
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
    
    def test_connection(self) -> bool:
        """
        Test database connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            conn = self.get_connection()
            conn.close()
            logger.info("✅ Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            return False


# ============================================================================
# LEGACY FUNCTIONS - Backward Compatibility
# ============================================================================

def get_connection():
    """Legacy function for backward compatibility"""
    try:
        conn_str = Config.get_db_connection_string()
        logger.info(f"Connecting to DB server={Config.DB_SERVER}, database={Config.DB_NAME}")
        return pyodbc.connect(conn_str)
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        raise e


def execute_sql(query: str) -> Any:
    """Legacy execute_sql function - Backward Compatible"""
    db = DatabaseClient()
    return db.execute_query(query)


# ============================================================================
# SINGLETON FOR GLOBAL ACCESS
# ============================================================================

_db_client_instance = None

def get_db_client() -> DatabaseClient:
    """Get singleton database client instance"""
    global _db_client_instance
    if _db_client_instance is None:
        _db_client_instance = DatabaseClient()
    return _db_client_instance


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test database connection and schema discovery
    print("Testing database connection and schema discovery...")
    
    db = get_db_client()
    
    if db.test_connection():
        print("✅ Connection successful!")
        
        # Test table discovery
        print("\n📋 Discovering tables...")
        tables = db.get_all_tables()
        print(f"Found {len(tables)} tables:")
        for table in tables[:10]:
            print(f"  - {table}")
        
        if len(tables) > 10:
            print(f"  ... and {len(tables) - 10} more")
        
        # Test column discovery
        if tables:
            test_table = tables[0]
            print(f"\n📋 Discovering columns for {test_table}...")
            columns = db.get_table_columns(test_table)
            print(f"Found {len(columns)} columns:")
            for col in columns[:5]:
                print(f"  - {col['name']} ({col['type']})")
    else:
        print("❌ Connection failed!")