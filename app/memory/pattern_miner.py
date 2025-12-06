# app/memory/pattern_miner.py
"""
Pattern Miner - Discovers common query patterns from history (PRODUCTION VERSION)

Features:
- Mines patterns from successful query history (via QueryLogger)
- Groups by query_type, table combinations, and common filters
- Caching with TTL to avoid re-mining on every UI refresh
- Suggests good candidates for template engine

Typical usage:
    from app.memory.pattern_miner import get_pattern_miner

    miner = get_pattern_miner()
    patterns = miner.mine_patterns()
    candidates = miner.suggest_template_candidates()
"""

from typing import Dict, List, Tuple, Optional
from collections import Counter
import re
import time

from app.memory.query_logger import QueryLogger
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PatternMiner:
    """
    Mines patterns from query history to identify common queries
    """

    # Cache lifetime in seconds (e.g. 5 minutes)
    CACHE_TTL_SECONDS = 300

    def __init__(self):
        self.query_logger = QueryLogger()
        # Simple cache structure:
        # {
        #   "timestamp": float,
        #   "min_frequency": int,
        #   "query_count": int,
        #   "patterns": List[Dict]
        # }
        self._cache: Optional[Dict] = None

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def mine_patterns(self, min_frequency: int = 3, force_refresh: bool = False) -> List[Dict]:
        """
        Mine common patterns from query history.

        Args:
            min_frequency: Minimum occurrences to be considered a pattern
            force_refresh: Ignore cache and recompute patterns

        Returns:
            List of discovered patterns (each pattern is a dict)
        """
        # 1) Load query history once
        queries = self._load_successful_queries()
        query_count = len(queries)

        if query_count < min_frequency:
            logger.info(
                f"⏳ Not enough queries to mine patterns "
                f"(have {query_count}, need at least {min_frequency})"
            )
            return []

        # 2) Use cache if still valid
        if not force_refresh and self._cache is not None:
            age = time.time() - self._cache["timestamp"]
            if (
                age <= self.CACHE_TTL_SECONDS
                and self._cache["min_frequency"] == min_frequency
                and self._cache["query_count"] == query_count
            ):
                logger.info(
                    f"📊 Using cached patterns "
                    f"(age={age:.1f}s, queries={query_count}, "
                    f"patterns={len(self._cache['patterns'])})"
                )
                return self._cache["patterns"]

        logger.info(
            f"🔎 Mining patterns from {query_count} queries "
            f"(min_freq={min_frequency})..."
        )

        patterns: List[Dict] = []

        # Pattern 1: Common query types with similar structure
        type_groups = self._group_by_query_type(queries)
        for qtype, group in type_groups.items():
            if len(group) >= min_frequency:
                pattern = self._extract_pattern_from_group(qtype, group)
                if pattern:
                    patterns.append(pattern)

        # Pattern 2: Frequently used table combinations
        patterns.extend(
            self._find_common_table_combinations(queries, min_frequency)
        )

        # Pattern 3: Common filters (years, keywords, etc.)
        patterns.extend(
            self._find_common_filters(queries, min_frequency)
        )

        logger.info(f"📊 Mined {len(patterns)} patterns from {query_count} queries")

        # 3) Cache result
        self._cache = {
            "timestamp": time.time(),
            "min_frequency": min_frequency,
            "query_count": query_count,
            "patterns": patterns,
        }

        return patterns

    def suggest_template_candidates(self, min_frequency: int = 5) -> List[Dict]:
        """
        Suggest queries that should be converted to templates.

        Args:
            min_frequency: Frequency threshold to consider a candidate

        Returns:
            List of candidate template definitions.
            Each item includes:
                - query_type
                - frequency
                - reason
                - sql_example
                - example_question
        """
        patterns = self.mine_patterns(min_frequency=min_frequency)
        candidates: List[Dict] = []

        for pattern in patterns:
            if pattern.get("type") != "query_type_pattern":
                continue

            freq = pattern.get("frequency", 0)
            if freq < min_frequency:
                continue

            sql_examples = pattern.get("sql_examples") or []
            question_examples = pattern.get("question_examples") or []

            candidates.append(
                {
                    "query_type": pattern.get("query_type"),
                    "frequency": freq,
                    "reason": f"Asked {freq} times (query_type={pattern.get('query_type')})",
                    "sql_example": sql_examples[0] if sql_examples else None,
                    "example_question": question_examples[0] if question_examples else None,
                }
            )

        logger.info(f"💡 Found {len(candidates)} template candidates")
        return candidates

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------
    def _load_successful_queries(self) -> List[Dict]:
        """
        Wrapper around QueryLogger's internal loader.

        Returns list of dict:
            {
                "question": str,
                "sql": str,
                "intent": dict,
                ...
            }
        """
        try:
            # Using internal helper is fine in our own package
            queries = self.query_logger._load_successful_queries()
        except Exception as e:
            logger.error(f"Failed to load queries from QueryLogger: {e}")
            return []

        # Filter out malformed ones
        cleaned = []
        for q in queries:
            if not isinstance(q, dict):
                continue
            if "question" not in q or "sql" not in q:
                continue
            cleaned.append(q)

        return cleaned

    def _group_by_query_type(self, queries: List[Dict]) -> Dict[str, List[Dict]]:
        """Group queries by their type (intent.query_type)"""
        groups: Dict[str, List[Dict]] = {}
        for query in queries:
            intent = query.get("intent") or {}
            qtype = intent.get("query_type", "unknown")
            groups.setdefault(qtype, []).append(query)
        return groups

    def _extract_pattern_from_group(self, qtype: str, group: List[Dict]) -> Optional[Dict]:
        """
        Extract common pattern from a group of similar queries:
        - common keywords in natural language question
        - representative SQL examples
        """
        if not group:
            return None

        # Collect word sets from questions
        all_word_sets: List[set] = []
        for query in group:
            question_text = (query.get("question") or "").lower()
            # Simple tokenization, filter out very short words
            words = {
                w
                for w in re.split(r"\W+", question_text)
                if len(w) >= 3
            }
            if words:
                all_word_sets.append(words)

        # Intersection of all word sets (if any)
        common_keywords: List[str] = []
        if all_word_sets:
            if len(all_word_sets) == 1:
                common_keywords = sorted(all_word_sets[0])
            else:
                common = set.intersection(*all_word_sets)
                common_keywords = sorted(common)

        # Example SQLs + example questions
        top_examples = group[:5]
        sql_examples = [q["sql"] for q in top_examples if q.get("sql")]
        question_examples = [q["question"] for q in top_examples if q.get("question")]

        # Average complexity
        total_complexity = 0.0
        for q in group:
            intent = q.get("intent") or {}
            total_complexity += float(intent.get("complexity", 0.0))
        avg_complexity = total_complexity / len(group)

        return {
            "type": "query_type_pattern",
            "query_type": qtype,
            "frequency": len(group),
            "common_keywords": common_keywords,
            "sql_examples": sql_examples,
            "question_examples": question_examples,
            "avg_complexity": avg_complexity,
        }

    def _find_common_table_combinations(
        self, queries: List[Dict], min_frequency: int
    ) -> List[Dict]:
        """Find frequently used table combinations via intent.tables_needed"""
        table_combos = Counter()

        for query in queries:
            intent = query.get("intent") or {}
            tables = intent.get("tables_needed") or []
            if not tables:
                continue
            combo = tuple(sorted(tables))
            table_combos[combo] += 1

        patterns: List[Dict] = []
        total_queries = len(queries)

        for combo, count in table_combos.most_common():
            if count < min_frequency:
                continue
            patterns.append(
                {
                    "type": "table_combination",
                    "tables": list(combo),
                    "frequency": count,
                    "percentage": (count / total_queries) * 100.0,
                }
            )

        return patterns

    def _find_common_filters(
        self, queries: List[Dict], min_frequency: int
    ) -> List[Dict]:
        """Find common filter patterns (years, business keywords, etc.)"""
        filters = {
            "years": Counter(),
            "keywords": Counter(),
        }

        business_terms = [
            "satış",
            "sales",
            "ürün",
            "product",
            "kategori",
            "category",
            "müşteri",
            "customer",
            "mağaza",
            "store",
            "online",
        ]

        for query in queries:
            question = (query.get("question") or "").lower()

            # Extract 20xx years from natural language question
            years = re.findall(r"20[0-9]{2}", question)
            for year in years:
                filters["years"][year] += 1

            # Business keywords
            for term in business_terms:
                if term in question:
                    filters["keywords"][term] += 1

        patterns: List[Dict] = []

        # Year patterns
        for year, count in filters["years"].most_common():
            if count < min_frequency:
                continue
            patterns.append(
                {
                    "type": "common_filter",
                    "filter_type": "year",
                    "value": year,
                    "frequency": count,
                }
            )

        # Keyword patterns (top 5)
        for keyword, count in filters["keywords"].most_common(5):
            if count < min_frequency:
                continue
            patterns.append(
                {
                    "type": "common_keyword",
                    "keyword": keyword,
                    "frequency": count,
                }
            )

        return patterns


# Singleton
_miner_instance: Optional[PatternMiner] = None


def get_pattern_miner() -> PatternMiner:
    """Get singleton pattern miner instance"""
    global _miner_instance
    if _miner_instance is None:
        _miner_instance = PatternMiner()
    return _miner_instance
