# app/memory/pattern_miner.py
"""
Pattern Miner - Discovers common query patterns from history
"""

from typing import Dict, List, Tuple, Optional
from collections import Counter
import re
from app.memory.query_logger import QueryLogger
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PatternMiner:
    """
    Mines patterns from query history to identify common queries
    """
    
    def __init__(self):
        self.query_logger = QueryLogger()
    
    def mine_patterns(self, min_frequency: int = 3) -> List[Dict]:
        """
        Mine common patterns from query history
        
        Args:
            min_frequency: Minimum occurrences to be considered a pattern
            
        Returns:
            List of discovered patterns
        """
        queries = self.query_logger._load_successful_queries()
        
        if len(queries) < min_frequency:
            logger.info("Not enough queries to mine patterns")
            return []
        
        patterns = []
        
        # Pattern 1: Common query types with similar structure
        type_groups = self._group_by_query_type(queries)
        for qtype, group in type_groups.items():
            if len(group) >= min_frequency:
                pattern = self._extract_pattern_from_group(qtype, group)
                if pattern:
                    patterns.append(pattern)
        
        # Pattern 2: Frequently used table combinations
        table_combos = self._find_common_table_combinations(queries, min_frequency)
        patterns.extend(table_combos)
        
        # Pattern 3: Common filters (years, categories, etc.)
        common_filters = self._find_common_filters(queries, min_frequency)
        patterns.extend(common_filters)
        
        logger.info(f"📊 Mined {len(patterns)} patterns from {len(queries)} queries")
        
        return patterns
    
    def _group_by_query_type(self, queries: List[Dict]) -> Dict[str, List[Dict]]:
        """Group queries by their type"""
        groups = {}
        for query in queries:
            qtype = query.get('intent', {}).get('query_type', 'unknown')
            if qtype not in groups:
                groups[qtype] = []
            groups[qtype].append(query)
        return groups
    
    def _extract_pattern_from_group(self, qtype: str, group: List[Dict]) -> Optional[Dict]:
        """Extract common pattern from a group of similar queries"""
        if not group:
            return None
        
        # Find common words in questions
        all_words = []
        for query in group:
            words = set(query['question'].lower().split())
            all_words.append(words)
        
        # Find intersection
        if all_words:
            common_words = set.intersection(*all_words) if len(all_words) > 1 else all_words[0]
            
            # Find most common SQL structure
            sql_examples = [q['sql'] for q in group[:3]]  # Top 3 examples
            
            return {
                "type": "query_type_pattern",
                "query_type": qtype,
                "frequency": len(group),
                "common_keywords": list(common_words),
                "sql_examples": sql_examples,
                "avg_complexity": sum(q.get('intent', {}).get('complexity', 0) for q in group) / len(group)
            }
        
        return None
    
    def _find_common_table_combinations(
        self, 
        queries: List[Dict], 
        min_frequency: int
    ) -> List[Dict]:
        """Find frequently used table combinations"""
        table_combos = Counter()
        
        for query in queries:
            tables = tuple(sorted(query.get('intent', {}).get('tables_needed', [])))
            if tables:
                table_combos[tables] += 1
        
        patterns = []
        for combo, count in table_combos.most_common():
            if count >= min_frequency:
                patterns.append({
                    "type": "table_combination",
                    "tables": list(combo),
                    "frequency": count,
                    "percentage": count / len(queries) * 100
                })
        
        return patterns
    
    def _find_common_filters(
        self, 
        queries: List[Dict], 
        min_frequency: int
    ) -> List[Dict]:
        """Find common filter patterns (years, categories, etc.)"""
        filters = {
            "years": Counter(),
            "keywords": Counter()
        }
        
        for query in queries:
            question = query['question'].lower()
            
            # Extract years
            years = re.findall(r'20[0-9]{2}', question)
            for year in years:
                filters["years"][year] += 1
            
            # Extract key business terms
            business_terms = [
                'satış', 'sales', 'ürün', 'product', 'kategori', 'category',
                'müşteri', 'customer', 'mağaza', 'store', 'online'
            ]
            for term in business_terms:
                if term in question:
                    filters["keywords"][term] += 1
        
        patterns = []
        
        # Year patterns
        for year, count in filters["years"].most_common():
            if count >= min_frequency:
                patterns.append({
                    "type": "common_filter",
                    "filter_type": "year",
                    "value": year,
                    "frequency": count
                })
        
        # Keyword patterns
        for keyword, count in filters["keywords"].most_common(5):
            if count >= min_frequency:
                patterns.append({
                    "type": "common_keyword",
                    "keyword": keyword,
                    "frequency": count
                })
        
        return patterns
    
    def suggest_template_candidates(self) -> List[Dict]:
        """
        Suggest queries that should be converted to templates
        
        Returns:
            List of candidate patterns for template creation
        """
        patterns = self.mine_patterns(min_frequency=5)  # Higher threshold
        
        candidates = []
        for pattern in patterns:
            if pattern.get('type') == 'query_type_pattern':
                if pattern['frequency'] >= 5:  # Frequently asked
                    candidates.append({
                        "query_type": pattern['query_type'],
                        "frequency": pattern['frequency'],
                        "reason": f"Asked {pattern['frequency']} times",
                        "sql_example": pattern['sql_examples'][0] if pattern['sql_examples'] else None
                    })
        
        logger.info(f"💡 Found {len(candidates)} template candidates")
        return candidates


# Singleton
_miner_instance = None

def get_pattern_miner() -> PatternMiner:
    """Get singleton pattern miner instance"""
    global _miner_instance
    if _miner_instance is None:
        _miner_instance = PatternMiner()
    return _miner_instance