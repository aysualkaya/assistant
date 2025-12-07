"""
SQL Table Validator (2025)
- Extracts table names from SQL queries
- Compares detected vs expected tables
- Used by test_scenarios runner
"""

import re


def extract_tables_from_sql(sql: str):
    """
    Extract table names from generated SQL.
    Detects tables used in:
    - FROM table
    - JOIN table
    - LEFT JOIN table
    - INNER JOIN table

    Ignores aliases.
    """

    pattern = r"\bFROM\s+([A-Za-z0-9_]+)|\bJOIN\s+([A-Za-z0-9_]+)"
    matches = re.findall(pattern, sql, flags=re.IGNORECASE)

    tables = set()

    for m in matches:
        table = m[0] if m[0] else m[1]
        tables.add(table)

    return list(tables)


def compare_expected_vs_detected(expected: list, detected: list):
    """
    Checks if the SQL query contains all required tables.
    Returns list of missing tables.
    """
    missing = [t for t in expected if t not in detected]
    return missing
