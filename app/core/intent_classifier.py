"""
Advanced Intent Classifier (2025 – Multilingual, Production Edition)
-------------------------------------------------------------------
NO LLM REQUIRED.

Understands:
- TR + EN ranking intent (top / bottom / best / worst)
- trend queries (monthly, weekly, quarterly, yearly)
- aggregation & metrics (total, sum, revenue, avg, count, quantity)
- comparison queries (store vs online, region vs region, year vs year)
- category-based queries
- geography queries (bölge, ülke, region, country)
- online-channel queries
- profitability / return rate detection
- time detection (year, month, week)
- Extracts complexity score
"""

from typing import Dict
import re
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IntentClassifier:

    # ======================================================================
    # PUBLIC
    # ======================================================================
    def classify(self, question: str) -> Dict:
        q = question.lower().strip()

        # ------------------------------------------------------------
        # 1) RANKING (TOP / BOTTOM)
        # ------------------------------------------------------------
        if self._contains(q, [
            "en çok", "en cok", "top", "best", "highest",
            "most selling", "top seller", "top selling",
            "best performing"
        ]):
            return self._intent("ranking", 5, order="desc")

        if self._contains(q, [
            "en az", "least", "bottom", "worst", "lowest",
            "least selling", "worst performing"
        ]):
            return self._intent("ranking", 5, order="asc")

        # Detect: "top 5", "top 10 products"
        if re.search(r"\btop\s+\d+\b", q):
            return self._intent("ranking", 5, order="desc")

        # ------------------------------------------------------------
        # 2) CATEGORY-BASED
        # ------------------------------------------------------------
        if self._contains(q, ["kategori", "category", "sub category", "alt kategori"]):
            return self._intent(
                query_type="category_analysis",
                complexity=6,
                time_dimension=self._has_time_dimension(q),
                granularity=self._detect_granularity(q)
            )

        # ------------------------------------------------------------
        # 3) GEOGRAPHY / REGION
        # ------------------------------------------------------------
        if self._contains(q, ["bölge", "bolge", "region", "country", "ülke"]):
            return self._intent(
                query_type="geography",
                complexity=6,
                time_dimension=self._has_time_dimension(q),
                granularity=self._detect_granularity(q)
            )

        # ------------------------------------------------------------
        # 4) STORE vs ONLINE comparison
        # ------------------------------------------------------------
        if self._contains(q, ["store vs online", "mağaza vs online", "magaza vs online"]):
            return self._intent("comparison", 6, comparison_type="store_vs_online")

        # Generic comparison queries
        if self._contains(q, ["karşı", "karsi", "compare", "vs", "versus"]):
            return self._intent("comparison", 6)

        # ------------------------------------------------------------
        # 5) ONLINE CHANNEL detection
        # ------------------------------------------------------------
        if self._contains(q, ["online satış", "online satic", "online", "e-commerce"]):
            return self._intent(
                query_type="online_channel",
                complexity=6,
                time_dimension=self._has_time_dimension(q),
                granularity=self._detect_granularity(q)
            )

        # ------------------------------------------------------------
        # 6) TREND
        # ------------------------------------------------------------
        if self._contains(q, [
            "trend", "aylık", "aylik", "monthly",
            "weekly", "haftalık", "çeyrek", "quarterly",
            "yearly", "yıllık", "yillik"
        ]):
            return self._intent(
                query_type="trend",
                complexity=6,
                time_dimension=True,
                granularity=self._detect_granularity(q)
            )

        # ------------------------------------------------------------
        # 7) PROFITABILITY
        # ------------------------------------------------------------
        if self._contains(q, ["kâr", "kar", "profit", "margin", "karlılık"]):
            return self._intent(
                query_type="profit",
                complexity=7,
                time_dimension=self._has_time_dimension(q)
            )

        # ------------------------------------------------------------
        # 8) RETURN RATE / RETURNS
        # ------------------------------------------------------------
        if self._contains(q, ["iade", "return rate", "refund"]):
            return self._intent(
                query_type="returns",
                complexity=6,
                time_dimension=self._has_time_dimension(q)
            )

        # ------------------------------------------------------------
        # 9) AGGREGATION
        # ------------------------------------------------------------
        if self._contains(q, [
            "toplam", "sum", "total", "revenue", "ciro",
            "ortalama", "avg", "count", "kaç adet", "how many",
            "adet", "quantity"
        ]):
            return self._intent(
                query_type="aggregation",
                complexity=4,
                time_dimension=self._has_time_dimension(q),
                granularity=self._detect_granularity(q)
            )

        # ------------------------------------------------------------
        # 10) DEFAULT → Generic aggregation
        # ------------------------------------------------------------
        return self._intent(
            query_type="aggregation",
            complexity=4,
            time_dimension=self._has_time_dimension(q),
            granularity=self._detect_granularity(q)
        )

    # ======================================================================
    # INTERNAL HELPERS
    # ======================================================================
    def _contains(self, q: str, words: list) -> bool:
        return any(w in q for w in words)

    # ======================================================================
    # INTENT BUILDER
    # ======================================================================
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
            "confidence": 0.95
        }

    # ======================================================================
    # TIME DETECTORS
    # ======================================================================
    def _has_time_dimension(self, q: str) -> bool:
        return any(t in q for t in [
            "2007", "2008", "2009", "2010", "2011",
            "yıl", "year", "ay", "month", "hafta", "week",
            "çeyrek", "quarter"
        ])

    def _detect_granularity(self, q: str) -> str:
        if "ay" in q or "month" in q:
            return "month"
        if "hafta" in q or "week" in q:
            return "week"
        if "çeyrek" in q or "quarter" in q:
            return "quarter"
        if "yıl" in q or "year" in q:
            return "year"
        return "none"
