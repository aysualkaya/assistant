# app/memory/query_logger.py
"""
Query Logger - Learning System
Logs all queries for pattern mining and few-shot learning
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from app.core.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryLogger:
    """
    Logs queries for learning and pattern analysis
    """
    
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path or Config.QUERY_HISTORY_PATH)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for current session
        self.session_queries = []
    
    def log_query(
        self,
        question: str,
        sql: Optional[str],
        intent: Dict,
        strategy: str,
        success: bool,
        execution_time: Optional[float] = None,
        error: Optional[str] = None,
        results_count: Optional[int] = None
    ):
        """
        Log a query attempt
        
        Args:
            question: User's question
            sql: Generated SQL (None if generation failed)
            intent: Intent classification
            strategy: Generation strategy used
            success: Whether query was successful
            execution_time: Query execution time in seconds
            error: Error message if failed
            results_count: Number of results returned
        """
        if not Config.ENABLE_QUERY_LOGGING:
            return
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "sql": sql,
            "intent": {
                "query_type": intent.get("query_type"),
                "complexity": intent.get("complexity"),
                "confidence": intent.get("confidence"),
                "tables_needed": intent.get("tables_needed", [])
            },
            "strategy": strategy,
            "success": success,
            "execution_time": execution_time,
            "results_count": results_count,
            "error": error
        }
        
        # Add to session cache
        self.session_queries.append(log_entry)
        
        # Append to file (JSONL format - one JSON per line)
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            logger.debug(f"📝 Query logged: {question[:50]}...")
            
        except Exception as e:
            logger.error(f"Failed to log query: {e}")
    
    def find_similar_queries(
        self,
        question: str,
        limit: int = 3,
        min_similarity: float = 0.3
    ) -> List[Dict]:
        """
        Find similar successful queries for few-shot learning
        
        Args:
            question: Current question
            limit: Maximum number of examples
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of similar query examples
        """
        # Load all successful queries
        successful_queries = self._load_successful_queries()
        
        if not successful_queries:
            logger.debug("No successful queries in history")
            return []
        
        # Calculate similarity scores
        scored_queries = []
        for query in successful_queries:
            similarity = self._calculate_similarity(question, query['question'])
            if similarity >= min_similarity:
                scored_queries.append((similarity, query))
        
        # Sort by similarity and return top N
        scored_queries.sort(key=lambda x: x[0], reverse=True)
        similar = [q for _, q in scored_queries[:limit]]
        
        logger.debug(f"Found {len(similar)} similar queries for: {question[:50]}...")
        
        return similar
    
    def _load_successful_queries(self) -> List[Dict]:
        """Load all successful queries from log"""
        if not self.log_path.exists():
            return []
        
        successful = []
        
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get('success') and entry.get('sql'):
                            successful.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to load query history: {e}")
        
        return successful
    
    def _calculate_similarity(self, q1: str, q2: str) -> float:
        """
        Calculate simple similarity between two questions
        Uses word overlap and common patterns
        
        Args:
            q1: First question
            q2: Second question
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Simple word-based similarity
        q1_lower = q1.lower()
        q2_lower = q2.lower()
        
        # Tokenize
        words1 = set(q1_lower.split())
        words2 = set(q2_lower.split())
        
        # Remove common stop words
        stop_words = {'ve', 'veya', 'için', 'ile', 'bir', 'bu', 'şu', 'o',
                      'and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to'}
        words1 = words1 - stop_words
        words2 = words2 - stop_words
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        jaccard = intersection / union if union > 0 else 0.0
        
        # Boost if key patterns match
        patterns = [
            r'en (çok|fazla|az|düşük)',  # Top/bottom
            r'toplam|total',              # Aggregation
            r'karşılaştır|vs',           # Comparison
            r'trend|aylık|yıllık',       # Trend
            r'\d{4}'                      # Year
        ]
        
        import re
        pattern_matches = sum(
            1 for p in patterns 
            if re.search(p, q1_lower) and re.search(p, q2_lower)
        )
        
        pattern_bonus = pattern_matches * 0.1
        
        return min(1.0, jaccard + pattern_bonus)
    
    def get_statistics(self) -> Dict:
        """
        Get query statistics
        
        Returns:
            Dictionary with statistics
        """
        queries = self._load_all_queries()
        
        if not queries:
            return {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "success_rate": 0.0
            }
        
        total = len(queries)
        successful = sum(1 for q in queries if q.get('success'))
        failed = total - successful
        
        # Strategy breakdown
        strategies = {}
        for q in queries:
            strat = q.get('strategy', 'unknown')
            strategies[strat] = strategies.get(strat, 0) + 1
        
        # Query type breakdown
        query_types = {}
        for q in queries:
            qtype = q.get('intent', {}).get('query_type', 'unknown')
            query_types[qtype] = query_types.get(qtype, 0) + 1
        
        # Average complexity
        complexities = [q.get('intent', {}).get('complexity', 0) for q in queries]
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0
        
        return {
            "total_queries": total,
            "successful_queries": successful,
            "failed_queries": failed,
            "success_rate": successful / total if total > 0 else 0.0,
            "strategies": strategies,
            "query_types": query_types,
            "avg_complexity": avg_complexity
        }
    
    def _load_all_queries(self) -> List[Dict]:
        """Load all queries from log"""
        if not self.log_path.exists():
            return []
        
        queries = []
        
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        queries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to load query history: {e}")
        
        return queries
    
    def clear_history(self):
        """Clear query history"""
        if self.log_path.exists():
            self.log_path.unlink()
        self.session_queries.clear()
        logger.info("🗑️ Query history cleared")


# Initialize __init__.py files
# app/memory/__init__.py