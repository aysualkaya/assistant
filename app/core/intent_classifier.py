"""
Advanced Intent Classifier (2025 – Multilingual, Rule-Based)
------------------------------------------------------------
NO LLM REQUIRED.
Understands:
- TR + EN ranking intent
- trend queries (monthly, weekly, quarterly, yearly)
- aggregation intent
- comparison (store vs online)
- time dimension detection
- complexity scoring
"""

from typing import Dict
import re
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IntentClassifier:

    # ============================================================
    # PUBLIC METHOD
    # ============================================================
    def classify(self, question: str) -> Dict:
        q = question.lower().strip()

        # ============================================
        # 1) RANKING INTENT (TOP / BOTTOM)
        # ============================================
        ranking_top_keywords = [
            "en çok", "en cok", "top", "best", "highest",
            "most selling", "best performing", "top seller", "top selling"
        ]

        ranking_bottom_keywords = [
            "en az", "lowest", "bottom", "least", "worst",
            "least selling", "worst performing"
        ]

        if any(k in q for k in ranking_top_keywords):
            return self._intent("ranking", 5, order="desc")

        if any(k in q for k in ranking_bottom_keywords):
            return self._intent("ranking", 5, order="asc")

        # Detect TOP X pattern (e.g. “top 10 products”)
        if re.search(r"\btop\s+\d+\b", q):
            return self._intent("ranking", 5, order="desc")

        # ============================================
        # 2) STORE VS ONLINE COMPARISON
        # ============================================
        if any(k in q for k in ["store vs online", "mağaza vs online", "magaza vs online"]):
            return self._intent("comparison", 6, comparison_type="store_vs_online")

        # Generic comparison
        if any(k in q for k in ["karşı", "karsi", "compare", "vs", "versus"]):
            return self._intent("comparison", 6)

        # ============================================
        # 3) TREND (Monthly, Weekly, Quarterly, Yearly)
        # ============================================
        trend_keywords = [
            "trend", "aylık", "aylik", "monthly",
            "quarterly", "çeyrek", "haftalık", "weekly",
            "yearly", "yıllık", "yillik"
        ]

        if any(k in q for k in trend_keywords):
            return self._intent(
                "trend",
                6,
                time_dimension=True,
                granularity=self._detect_granularity(q)
            )

        # ============================================
        # 4) AGGREGATION (sum, total, revenue, count...)
        # ============================================
        agg_keywords = [
            "toplam", "sum", "total", "revenue", "ciro",
            "ortalama", "avg", "count", "kaç adet", "how many"
        ]

        if any(k in q for k in agg_keywords):
            return self._intent(
                "aggregation",
                3,
                time_dimension=self._has_time_dimension(q),
                granularity=self._detect_granularity(q)
            )

        # ============================================
        # DEFAULT → aggregation
        # ============================================
        return self._intent(
            "aggregation",
            4,
            time_dimension=self._has_time_dimension(q),
            granularity=self._detect_granularity(q)
        )

    # ============================================================
    # INTENT BUILDER
    # ============================================================
    def _intent(
        self,
        query_type: str,
        complexity: int,
        order: str = "none",
        time_dimension: bool = False,
        granularity: str = "none",
        comparison_type: str = "none"
    ) -> Dict:

        return {
            "query_type": query_type,
            "complexity": complexity,
            "order_direction": order,
            "time_dimension": time_dimension,
            "time_granularity": granularity,
            "comparison_type": comparison_type,
            "confidence": 0.92
        }

    # ============================================================
    # TIME DETECTORS
    # ============================================================
    def _has_time_dimension(self, q: str) -> bool:
        return any(t in q for t in [
            "2007", "2008", "2009", "2010",
            "yıl", "year", "ay", "month", "hafta", "week", "quarter"
        ])

    def _detect_granularity(self, q: str) -> str:
        if any(k in q for k in ["ay", "month"]):
            return "month"
        if any(k in q for k in ["hafta", "week"]):
            return "week"
        if any(k in q for k in ["çeyrek", "quarter"]):
            return "quarter"
        if any(k in q for k in ["yıl", "year"]):
            return "year"
        return "none"
