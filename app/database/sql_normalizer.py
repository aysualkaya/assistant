# app/database/sql_normalizer.py - FINAL PRODUCTION VERSION
"""
SQL Normalizer with Intelligent Fuzzy Table Name Correction

FEATURES:
- Dynamic table list from database (INFORMATION_SCHEMA)
- Case-insensitive exact matching (factonlinesales → FactOnlineSales)
- Fuzzy matching with Levenshtein + similarity ratio
- Alias & schema (dbo.) preservation
- Phantom column cleanup (SELECT bölümünde)
- MSSQL keyword normalization
"""

import re
import difflib
from typing import List, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SQLNormalizer:
    """
    Production-grade SQL normalizer with fuzzy table correction
    """

    def __init__(self, valid_tables: Optional[List[str]] = None):
        """
        Initialize normalizer

        Args:
            valid_tables: List of valid table names (from DB)
                          If None, will be populated dynamically
        """
        self.valid_tables: List[str] = valid_tables or []

        # Lowercase → canonical name map (case-insensitive eşleşme için)
        self._table_lc_map = {
            t.lower(): t for t in self.valid_tables
        }

        # Phantom columns (LLM'in uydurabileceği kolonlar)
        # Bunları sadece SELECT kısmında SalesAmount'a eşleyeceğiz.
        self.phantom_columns = [
            "OnlineSales", "PhysicalSales", "StoreSales", "RetailSales",
            "ChannelSales", "WebSales", "TotalRevenue"
        ]

        # Valid MSSQL keywords (normalize edilecek)
        self.valid_keywords = [
            # Single-word
            "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "INNER",
            "JOIN", "LEFT", "RIGHT", "FULL", "OUTER", "ON", "TOP",
            "HAVING", "UNION", "ALL", "EXISTS", "DISTINCT",
            "CASE", "WHEN", "THEN", "END", "OVER", "PARTITION",

            # Multi-word common patterns
            "GROUP BY", "ORDER BY", "INNER JOIN",
            "LEFT JOIN", "RIGHT JOIN", "FULL JOIN",
            "LEFT OUTER JOIN", "RIGHT OUTER JOIN", "FULL OUTER JOIN",
            "PARTITION BY"
        ]

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def set_valid_tables(self, tables: List[str]):
        """Update valid table list (from database)"""
        self.valid_tables = tables or []
        self._table_lc_map = {t.lower(): t for t in self.valid_tables}
        logger.info(f"📋 Normalizer loaded {len(self.valid_tables)} valid tables")

    def normalize(self, sql: str) -> str:
        """
        Main normalization pipeline

        Args:
            sql: Raw SQL (LLM output)

        Returns:
            Cleaned & normalized SQL
        """
        if not sql:
            return ""

        original_sql = sql
        sql = sql.strip()

        sql = self._remove_markdown(sql)
        sql = self._remove_explanations(sql)
        sql = self._strip_sql_prefix(sql)
        sql = self._remove_phantom_columns(sql)
        sql = self._fix_table_names_fuzzy(sql)   # ✅ fuzzy + case-insensitive
        sql = self._fix_alias_spacing(sql)
        sql = self._fix_limit(sql)
        sql = self._fix_order_by(sql)
        sql = self._fix_lowercase_keywords(sql)
        sql = self._remove_trailing_semicolons(sql)
        sql = self._fix_unbalanced_parentheses(sql)
        sql = self._final_cleanup(sql)

        logger.info("🧼 SQL normalized successfully.")
        logger.debug(f"--- SQL BEFORE NORMALIZATION ---\n{original_sql}\n\n"
                     f"--- SQL AFTER NORMALIZATION ---\n{sql}")

        return sql

    # ------------------------------------------------------------------
    # FUZZY TABLE NAME CORRECTION
    # ------------------------------------------------------------------
    def _fix_table_names_fuzzy(self, sql: str) -> str:
        """
        Intelligent fuzzy matching for table names

        Handles:
        - FactONlineSales → FactOnlineSales
        - factonlinesales  → FactOnlineSales
        - DimProdcut       → DimProduct
        - DimProductCateg  → DimProductCategory
        and keeps:
        - schema (dbo.)
        - alias (fs, fos, dp, ...)
        """

        if not self.valid_tables:
            # No valid tables loaded, skip fuzzy matching
            return sql

        # FROM / JOIN [schema.]TableName [AS] [Alias]
        # Örnekler:
        #   FROM dbo.FactSales fs
        #   JOIN DimProduct dp
        #   JOIN dbo.DimProduct AS dp
        table_pattern = r'\b(FROM|JOIN)\s+((?:\w+\.)?)(\w+)(?:\s+AS\s+|\s+)?(\w+)?'

        def replace_table(match):
            keyword = match.group(1)     # FROM / JOIN
            schema = match.group(2) or ""   # e.g. "dbo."
            table_name = match.group(3)     # raw table
            alias = match.group(4) or ""    # e.g. "fs" / "dp" / "fos"

            if alias:
                alias = f" {alias}"  # leading space

            lc_name = table_name.lower()

            # 1) Case-insensitive exact match (factonlinesales → FactOnlineSales)
            if lc_name in self._table_lc_map:
                canonical = self._table_lc_map[lc_name]
                if canonical != table_name:
                    logger.info(f"🔧 Canonical table normalization: {table_name} → {canonical}")
                return f"{keyword} {schema}{canonical}{alias}"

            # 2) Fuzzy match (DimProdcut → DimProduct, FactONlineSales → FactOnlineSales ...)
            corrected = self._fuzzy_match_table(table_name)

            if corrected and corrected != table_name:
                logger.info(f"🔧 Fuzzy table correction: {table_name} → {corrected}")
                return f"{keyword} {schema}{corrected}{alias}"

            # 3) No change
            return match.group(0)

        return re.sub(table_pattern, replace_table, sql, flags=re.IGNORECASE)

    def _fuzzy_match_table(self, table_name: str) -> Optional[str]:
        """
        Find closest matching table name using:
        - Levenshtein distance
        - Similarity ratio (difflib.SequenceMatcher)

        Arg:
            table_name: Potentially incorrect table name

        Returns:
            Corrected table name or None if no safe match
        """
        if not self.valid_tables:
            return None

        target = table_name.lower()

        best_match = None
        best_ratio = 0.0
        best_distance = None

        for valid in self.valid_tables:
            v_lower = valid.lower()

            # Quick skip: çok alakasız uzunluktakileri at
            if abs(len(v_lower) - len(target)) > max(4, len(v_lower) // 2):
                continue

            distance = self._levenshtein_distance(target, v_lower)
            ratio = difflib.SequenceMatcher(None, target, v_lower).ratio()

            if ratio > best_ratio or (ratio == best_ratio and (best_distance is None or distance < best_distance)):
                best_ratio = ratio
                best_distance = distance
                best_match = valid

        if best_match is None or best_distance is None:
            return None

        # Güvenlik eşikleri:
        # - similarity ratio >= 0.85
        # - distance <= max(2, len(name) // 4)
        max_allowed_distance = max(2, len(best_match) // 4)

        if best_ratio >= 0.85 and best_distance <= max_allowed_distance:
            return best_match

        # Güvenli değilse düzeltme yapma
        return None

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings
        """
        if len(s1) < len(s2):
            return SQLNormalizer._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))

        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    # ------------------------------------------------------------------
    # MARKDOWN & COMMENTS
    # ------------------------------------------------------------------
    def _remove_markdown(self, sql: str) -> str:
        sql = re.sub(r"```sql", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"```", "", sql)
        return sql.strip()

    def _remove_explanations(self, sql: str) -> str:
        """
        Remove natural language explanations the LLM might add
        (e.g. 'Here is the query:', 'Reasoning:', 'Explanation:')
        """
        cleaned_lines = []
        for line in sql.split("\n"):
            stripped = line.strip()

            # Çok bariz açıklama satırlarını at
            if re.search(r"[A-Za-z]{4,}\s*:", stripped) and not stripped.upper().startswith("SELECT"):
                # Örn: "Explanation:", "Reasoning:", "Açıklama:"
                if not stripped.upper().startswith("WITH "):  # CTE name gibi durumları bozma
                    continue
            if "reasoning" in stripped.lower():
                continue
            if stripped.lower().startswith("here is") and "query" in stripped.lower():
                continue
            if stripped.lower().startswith("below") and "query" in stripped.lower():
                continue

            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    def _strip_sql_prefix(self, sql: str) -> str:
        return re.sub(r"^SQL\s*:", "", sql, flags=re.IGNORECASE).strip()

    # ------------------------------------------------------------------
    # PHANTOM COLUMNS
    # ------------------------------------------------------------------
    def _remove_phantom_columns(self, sql: str) -> str:
        """
        Replace hallucinated column names with valid ones (SalesAmount),
        but only in the SELECT kısmı. FROM/JOIN bölümlerine dokunmuyoruz.
        """

        # SELECT ... FROM ... yapısını ayır
        upper_sql = sql.upper()
        from_match = upper_sql.find(" FROM ")

        if from_match == -1:
            # Çok basit / bozuk bir query ise tümünde uygula (eski davranış)
            cleaned = sql
            for col in self.phantom_columns:
                pattern = re.compile(rf"\b{col}\b", re.IGNORECASE)
                if pattern.search(cleaned):
                    logger.info(f"🩹 Phantom column normalized (global): {col} → SalesAmount")
                cleaned = pattern.sub("SalesAmount", cleaned)
            return cleaned

        select_part = sql[:from_match]
        rest_part = sql[from_match:]

        cleaned_select = select_part
        for col in self.phantom_columns:
            pattern = re.compile(rf"\b{col}\b", re.IGNORECASE)
            if pattern.search(cleaned_select):
                logger.info(f"🩹 Phantom column normalized (SELECT): {col} → SalesAmount")
            cleaned_select = pattern.sub("SalesAmount", cleaned_select)

        return cleaned_select + rest_part

    # ------------------------------------------------------------------
    # ALIAS & SPACING
    # ------------------------------------------------------------------
    def _fix_alias_spacing(self, sql: str) -> str:
        """
        Normalize alias spacing: fs . SalesAmount → fs.SalesAmount
        """
        sql = re.sub(r"(\w+)\s*\.\s*(\w+)", r"\1.\2", sql)
        return sql

    # ------------------------------------------------------------------
    # LIMIT → TOP
    # ------------------------------------------------------------------
    def _fix_limit(self, sql: str) -> str:
        """
        Convert MySQL-style LIMIT to MSSQL TOP
        """
        limit_match = re.search(r"LIMIT\s+(\d+)", sql, flags=re.IGNORECASE)
        if limit_match:
            n = limit_match.group(1)
            # Sadece ilk SELECT'i TOP ile değiştir
            sql = re.sub(r"\bSELECT\b", f"SELECT TOP {n}", sql, count=1, flags=re.IGNORECASE)
            sql = re.sub(r"LIMIT\s+\d+", "", sql, flags=re.IGNORECASE)
        return sql

    # ------------------------------------------------------------------
    # ORDER BY / GROUP BY
    # ------------------------------------------------------------------
    def _fix_order_by(self, sql: str) -> str:
        sql = re.sub(r"order\s+by", "ORDER BY", sql, flags=re.IGNORECASE)
        sql = re.sub(r"group\s+by", "GROUP BY", sql, flags=re.IGNORECASE)
        return sql

    # ------------------------------------------------------------------
    # UPPERCASE KEYWORDS
    # ------------------------------------------------------------------
    def _fix_lowercase_keywords(self, sql: str) -> str:
        """
        Normalize common SQL keywords to uppercase for readability
        and consistency.
        Handles both single-word and multi-word keywords.
        """
        # Önce multi-word patternleri işleyelim ki "GROUP BY" → "GROUP BY" olur,
        # sonra tek tek GROUP / BY'yi bozmamış oluruz.
        multi = [kw for kw in self.valid_keywords if " " in kw]
        single = [kw for kw in self.valid_keywords if " " not in kw]

        # Multi-word
        for kw in multi:
            pattern = re.compile(re.escape(kw), re.IGNORECASE)
            sql = pattern.sub(kw.upper(), sql)

        # Single-word (kelime sınırı ile)
        for kw in single:
            pattern = re.compile(rf"\b{kw}\b", re.IGNORECASE)
            sql = pattern.sub(kw.upper(), sql)

        return sql

    # ------------------------------------------------------------------
    # FINAL CLEANUPS
    # ------------------------------------------------------------------
    def _remove_trailing_semicolons(self, sql: str) -> str:
        return re.sub(r";+\s*$", "", sql).strip()

    def _fix_unbalanced_parentheses(self, sql: str) -> str:
        """
        Balance parentheses in a conservative way.
        (Sadece açık kalan parantezleri kapatıyoruz.)
        """
        open_count = sql.count("(")
        close_count = sql.count(")")
        diff = open_count - close_count
        if diff > 0:
            sql += ")" * diff
        elif diff < 0:
            sql = "(" * abs(diff) + sql
        return sql

    def _final_cleanup(self, sql: str) -> str:
        sql = re.sub(r"\n{2,}", "\n", sql)
        sql = sql.strip()
        return sql


# =====================================================================
# SINGLETON WITH DYNAMIC TABLE LOADING
# =====================================================================

_normalizer_instance: Optional[SQLNormalizer] = None


def get_sql_normalizer() -> SQLNormalizer:
    """
    Get singleton normalizer instance.
    On first call, dynamically load table list from database.
    """
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = SQLNormalizer()

        # Load valid tables from database dynamically
        try:
            from app.database.db_client import get_db_client
            db_client = get_db_client()
            valid_tables = db_client.get_all_tables()
            _normalizer_instance.set_valid_tables(valid_tables)
        except Exception as e:
            logger.warning(f"Could not load tables from database for normalizer: {e}")

    return _normalizer_instance
