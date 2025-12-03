# app/database/query_validator.py
"""
Advanced SQL Query Validator - COMPLETE WORKING VERSION
Validates SQL queries against schema and business rules
"""

import re
from typing import List, Tuple, Dict, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryValidator:
    """
    Validates SQL queries for syntax, schema compliance, and business rules
    """
    
    # Phantom columns that don't exist but LLMs often hallucinate
    PHANTOM_COLUMNS = [
        'OnlineSales', 'PhysicalSales', 'StoreSales', 'WebSales',
        'RetailSales', 'ShopSales', 'ChannelSales'
    ]
    
    # Valid tables in ContosoRetailDW
    VALID_TABLES = [
        'FactSales', 'FactOnlineSales',
        'DimProduct', 'DimProductSubcategory', 'DimProductCategory',
        'DimDate', 'DimCustomer', 'DimStore', 'DimGeography',
        'DimChannel', 'DimCurrency', 'DimPromotion'
    ]
    
    # Table-specific column rules
    TABLE_COLUMN_RULES = {
        'FactSales': {
            'has': ['channelKey', 'StoreKey', 'SalesAmount', 'SalesQuantity'],
            'not_has': ['CustomerKey', 'SalesOrderNumber']
        },
        'FactOnlineSales': {
            'has': ['CustomerKey', 'StoreKey', 'SalesAmount', 'SalesQuantity'],
            'not_has': ['channelKey']
        }
    }
    
    def validate(self, sql: str, intent: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        """
        Validate SQL query
        
        Args:
            sql: SQL query to validate
            intent: Optional intent classification for context-aware validation
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not sql or len(sql.strip()) < 10:
            return False, ["SQL query is empty or too short"]
        
        # Run all validation checks
        errors.extend(self._check_phantom_columns(sql))
        errors.extend(self._check_date_filtering(sql))
        errors.extend(self._check_table_column_usage(sql))
        errors.extend(self._check_union_syntax(sql))
        errors.extend(self._check_invalid_functions(sql))
        errors.extend(self._check_table_existence(sql))
        
        # Intent-based validation
        if intent:
            errors.extend(self._validate_against_intent(sql, intent))
        
        # General SQL syntax checks
        errors.extend(self._check_basic_syntax(sql))
        
        # Separate critical vs warnings
        critical_errors = [e for e in errors if e.startswith("ERROR")]
        warnings = [e for e in errors if e.startswith("WARNING")]
        
        is_valid = len(critical_errors) == 0
        
        if is_valid:
            if warnings:
                logger.warning(f"⚠️ SQL validation passed with {len(warnings)} warning(s)")
                for w in warnings:
                    logger.warning(f"  - {w}")
            else:
                logger.info("✅ SQL validation passed")
        else:
            logger.error(f"❌ SQL validation failed with {len(critical_errors)} error(s)")
            for error in critical_errors:
                logger.error(f"  - {error}")
        
        return is_valid, errors
    
    def _check_phantom_columns(self, sql: str) -> List[str]:
        """Check for non-existent phantom columns"""
        errors = []
        
        for phantom in self.PHANTOM_COLUMNS:
            if re.search(rf'\b{phantom}\b', sql, re.IGNORECASE):
                errors.append(
                    f"ERROR: Column '{phantom}' does not exist. "
                    f"Use 'SalesAmount' instead for sales values."
                )
        
        return errors
    
    def _check_date_filtering(self, sql: str) -> List[str]:
        """Check for incorrect date filtering patterns"""
        errors = []
        
        # Check for YEAR(DateKey) usage
        if re.search(r'YEAR\s*\(\s*\w*\.?DateKey\s*\)', sql, re.IGNORECASE):
            errors.append(
                "ERROR: Using YEAR(DateKey) causes type clash error. "
                "DateKey is datetime type. "
                "Use: INNER JOIN DimDate dd ON [table].DateKey = dd.DateKey "
                "WHERE dd.CalendarYear = [year]"
            )
        
        # Check for GETDATE() with limited date range
        if re.search(r'GETDATE\(\)', sql, re.IGNORECASE):
            errors.append(
                "WARNING: Database only contains years 2007-2009. "
                "Don't use GETDATE(). Specify year explicitly (2007, 2008, or 2009)."
            )
        
        return errors
    
    def _check_table_column_usage(self, sql: str) -> List[str]:
        """Check for invalid table-column combinations"""
        errors = []
        
        # Check FactSales column usage
        if re.search(r'\bFactSales\b', sql, re.IGNORECASE):
            if re.search(r'FactSales.*CustomerKey|fs\.CustomerKey', sql, re.IGNORECASE):
                errors.append(
                    "ERROR: FactSales does not have CustomerKey column. "
                    "CustomerKey only exists in FactOnlineSales."
                )
        
        # Check FactOnlineSales column usage
        if re.search(r'\bFactOnlineSales\b', sql, re.IGNORECASE):
            if re.search(r'FactOnlineSales.*channelKey|fos\.channelKey', sql, re.IGNORECASE):
                errors.append(
                    "ERROR: FactOnlineSales does not have channelKey column. "
                    "channelKey only exists in FactSales."
                )
        
        return errors
    
    def _check_union_syntax(self, sql: str) -> List[str]:
        """Check UNION ALL syntax for common errors"""
        errors = []
        
        if 'UNION ALL' in sql.upper():
            union_parts = re.split(r'UNION\s+ALL', sql, flags=re.IGNORECASE)
            
            for i, part in enumerate(union_parts[:-1]):
                if 'ORDER BY' in part.upper():
                    if not re.search(r'\(\s*SELECT.*ORDER BY.*\)\s*$', part, re.IGNORECASE | re.DOTALL):
                        errors.append(
                            "WARNING: UNION ALL with ORDER BY in subqueries may need parentheses"
                        )
                        break
        
        return errors
    
    def _check_invalid_functions(self, sql: str) -> List[str]:
        """Check for SQL Server incompatible functions"""
        errors = []
        
        invalid_patterns = [
            (r'DATE\(', "DATE() function - use CAST(DateKey AS DATE) instead"),
            (r'CURDATE\(\)', "CURDATE() - use GETDATE() or specify year (2007-2009)"),
            (r'NOW\(\)', "NOW() - use GETDATE() or specify year (2007-2009)"),
        ]
        
        for pattern, message in invalid_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                errors.append(f"WARNING: Using {message}")
        
        return errors
    
    def _check_table_existence(self, sql: str) -> List[str]:
        """Check if all referenced tables exist"""
        errors = []
        
        table_pattern = r'(?:FROM|JOIN)\s+(\w+)'
        tables_in_query = re.findall(table_pattern, sql, re.IGNORECASE)
        
        for table in tables_in_query:
            if table.upper() not in [t.upper() for t in self.VALID_TABLES]:
                if len(table) > 4:  # Likely not an alias
                    errors.append(
                        f"WARNING: Table '{table}' may not exist in ContosoRetailDW"
                    )
        
        return errors
    
    def _validate_against_intent(self, sql: str, intent: Dict) -> List[str]:
        """Validate SQL against user intent"""
        errors = []
        
        query_type = intent.get('query_type')
        
        # Check TOP N queries
        if query_type == 'ranking':
            if 'ORDER BY' not in sql.upper():
                errors.append("WARNING: Ranking query should have ORDER BY clause")
        
        # Check comparison queries
        if query_type == 'comparison':
            comparison_type = intent.get('comparison_type')
            if comparison_type == 'store_vs_online':
                if 'UNION ALL' not in sql.upper():
                    errors.append("WARNING: Store vs online comparison should use UNION ALL")
        
        # Check trend queries
        if query_type == 'trend':
            if 'GROUP BY' not in sql.upper():
                errors.append("WARNING: Trend query should have GROUP BY for time dimension")
        
        return errors
    
    def _check_basic_syntax(self, sql: str) -> List[str]:
        """Basic SQL syntax checks"""
        errors = []
        
        if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
            errors.append("ERROR: SQL must contain SELECT statement")
        
        if not re.search(r'\bFROM\b', sql, re.IGNORECASE):
            errors.append("ERROR: SQL must contain FROM clause")
        
        # Check for unmatched parentheses
        open_parens = sql.count('(')
        close_parens = sql.count(')')
        if open_parens != close_parens:
            errors.append(
                f"ERROR: Unmatched parentheses (open: {open_parens}, close: {close_parens})"
            )
        
        return errors


# Singleton instance
_validator_instance = None

def get_query_validator() -> QueryValidator:
    """Get singleton validator instance"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = QueryValidator()
    return _validator_instance