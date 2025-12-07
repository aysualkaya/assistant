"""
Query Logger (2025 – Final Production Edition)
----------------------------------------------
Features:
- Rotating JSONL logs
- Few-shot learning (similar query retrieval)
- Session memory buffer
- Full test-suite compatible statistics (NEW)
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from app.core.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryLogger:
    MAX_LOG_SIZE_MB = 5
    MAX_ROTATED_FILES = 3

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path or Config.QUERY_HISTORY_PATH)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory recent queries (for UI session)
        self.session_queries: List[Dict] = []

        self._rotate_if_needed()

    # ======================================================================
    # PUBLIC LOG ENTRY
    # ======================================================================
    def log_query(
        self,
        question: str,
        sql: Optional[str],
        intent: Dict,
        strategy: str,
        success: bool,
        execution_time: Optional[float] = None,
        model_used: Optional[str] = None,
        error: Optional[str] = None,
        results_count: Optional[int] = None,
        tables_needed: Optional[List[str]] = None,
        validator_warnings: Optional[List[str]] = None,
    ):
        if not Config.ENABLE_QUERY_LOGGING:
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "sql": sql,
            "success": success,
            "strategy": strategy,
            "execution_time": execution_time,
            "results_count": results_count,
            "error": error,
            "model_used": model_used,

            # intent frame
            "intent": {
                "type": intent.get("query_type"),
                "complexity": intent.get("complexity"),
                "order_direction": intent.get("order_direction"),
                "time_dimension": intent.get("time_dimension"),
                "time_granularity": intent.get("time_granularity"),
                "tables_needed": intent.get("tables_needed"),
            },

            "tables_needed": tables_needed or intent.get("tables_needed") or [],
            "validator_warnings": validator_warnings or [],
        }

        self.session_queries.append(log_entry)
        self._append_to_file(log_entry)

    # ======================================================================
    # FILE OPERATIONS
    # ======================================================================
    def _append_to_file(self, entry: Dict):
        """Write entry to JSONL with rotation."""
        try:
            self._rotate_if_needed()
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"❌ Failed to write log entry: {e}")

    def _rotate_if_needed(self):
        if not self.log_path.exists():
            return

        size = self.log_path.stat().st_size / (1024 * 1024)
        if size < self.MAX_LOG_SIZE_MB:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated = self.log_path.with_name(f"{self.log_path.stem}_{timestamp}.jsonl")
        self.log_path.rename(rotated)

        # cleanup
        logs = sorted(self.log_path.parent.glob(f"{self.log_path.stem}_*.jsonl"))
        if len(logs) > self.MAX_ROTATED_FILES:
            for old in logs[:-self.MAX_ROTATED_FILES]:
                old.unlink(missing_ok=True)

    # ======================================================================
    # LOAD HISTORY (RAW)
    # ======================================================================
    def _load_history(self) -> List[Dict]:
        if not self.log_path.exists():
            return []

        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except:
                    continue
        return entries

    def _load_successful_queries(self) -> List[Dict]:
        """Only successful SQL examples (for few-shot prompts)."""
        return [
            q for q in self._load_history()
            if q.get("success") and q.get("sql")
        ]

    # ======================================================================
    # FEW-SHOT SIMILARITY
    # ======================================================================
    def find_similar_queries(self, question: str, limit: int = 3) -> List[Dict]:
        examples = self._load_successful_queries()
        if not examples:
            return []

        scored = []
        for q in examples:
            sim = self._similarity(question, q["question"])
            if sim >= 0.25:
                scored.append((sim, q))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [pair[1] for pair in scored[:limit]]

    def _similarity(self, q1: str, q2: str) -> float:
        """Weighted Jaccard + keyword boost."""
        q1, q2 = q1.lower(), q2.lower()
        tokens1 = set(q1.split())
        tokens2 = set(q2.split())

        stopwords = {
            "ve","veya","için","ile","bir","bu",
            "and","or","the","a","an","in","on","at","to"
        }
        tokens1 -= stopwords
        tokens2 -= stopwords

        if not tokens1 or not tokens2:
            return 0.0

        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)

        groups = [
            (["top", "best", "highest", "en cok"], 0.20),
            (["worst", "lowest", "en az"], 0.20),
            (["trend", "aylık", "monthly"], 0.20),
            (["total", "toplam"], 0.15),
            (["compare", "vs", "karşı"], 0.15),
        ]

        bonus = 0
        for words, weight in groups:
            if any(w in q1 for w in words) and any(w in q2 for w in words):
                bonus += weight

        return min(1.0, jaccard + bonus)

    # ======================================================================
    # NEW — STATISTICS FOR STREAMLIT
    # ======================================================================
    def get_statistics(self) -> Dict:
        """
        Returns:
            - total_queries
            - success_rate
            - avg_complexity
            - intent_distribution
        Fully compatible with Streamlit UI.
        """
        history = self._load_history()

        if not history:
            return {
                "total_queries": 0,
                "success_rate": 0.0,
                "avg_complexity": 0.0,
                "intent_distribution": {},
            }

        total = len(history)
        successes = sum(1 for q in history if q.get("success"))

        complexities = [
            q.get("intent", {}).get("complexity", 0)
            for q in history
            if isinstance(q.get("intent"), dict)
        ]

        # distribution of query types
        dist = {}
        for q in history:
            intent_name = q.get("intent", {}).get("type", "unknown")
            dist[intent_name] = dist.get(intent_name, 0) + 1

        return {
            "total_queries": total,
            "success_rate": successes / total if total else 0.0,
            "avg_complexity": sum(complexities) / len(complexities) if complexities else 0.0,
            "intent_distribution": dist,
        }

    # ======================================================================
    # CLEAR HISTORY
    # ======================================================================
    def clear_history(self):
        if self.log_path.exists():
            self.log_path.unlink()
        self.session_queries.clear()
        logger.info("🗑️ Query history cleared.")
