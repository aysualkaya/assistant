# app/core/intent_classifier.py
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
- 🔥 NEW: expected_count for ranking queries
"""

from typing import Dict, Optional
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
        # 1) RANKING (TOP / BOTTOM) - 🔥 EXPECTED_COUNT ADDED
        # ------------------------------------------------------------
        if self._contains(q, [
            "en çok", "en cok", "top", "best", "highest",
            "most selling", "top seller", "top selling",
            "best performing"
        ]):
            # Kullanıcı sayı belirtmiş mi kontrol et
            explicit_count = self._extract_explicit_count(q)
            return self._intent(
                query_type="ranking",
                complexity=5,
                order="desc",
                expected_count=explicit_count or 5  # "en çok" için default 5
            )

        if self._contains(q, [
            "en az", "least", "bottom", "worst", "lowest",
            "least selling", "worst performing"
        ]):
            # 🔥 "en az" için expected_count = 1 (tek ürün)
            explicit_count = self._extract_explicit_count(q)
            return self._intent(
                query_type="ranking",
                complexity=5,
                order="asc",
                expected_count=explicit_count or 1  # "en az" → 1 ürün
            )

        # Detect: "top 5", "top 10 products"
        if re.search(r"\btop\s+\d+\b", q):
            explicit_count = self._extract_explicit_count(q)
            return self._intent(
                query_type="ranking",
                complexity=5,
                order="desc",
                expected_count=explicit_count or 5
            )

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
        if self._contains(q, ["online satış", "online satis", "online", "e-commerce"]):
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

    # 🔥 NEW: Extract explicit count from question
    def _extract_explicit_count(self, q: str) -> Optional[int]:
        """
        Kullanıcı sorusundan açık sayı çıkar.
        Örnekler:
        - "en çok satan 5 ürün" → 5
        - "top 10 products" → 10
        - "en az satan 3 kategori" → 3
        - "en az satan ürün" → None
        """
        patterns = [
            r"(?:top|en çok|en cok|en az)\s+(\d+)",
            r"(\d+)\s+(?:ürün|urun|product|kategori|category|store|mağaza|magaza)",
            r"ilk\s+(\d+)",
            r"first\s+(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, q)
            if match:
                try:
                    count = int(match.group(1))
                    if 1 <= count <= 100:
                        return count
                except (ValueError, IndexError):
                    continue

        return None

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
        comparison_type: str = "none",
        expected_count: Optional[int] = None
    ) -> Dict:

        intent: Dict = {
            "query_type": query_type,
            "complexity": complexity,
            "order_direction": order,
            "time_dimension": time_dimension,
            "time_granularity": granularity,
            "comparison_type": comparison_type,
            "confidence": 0.95,
        }

        if expected_count is not None:
            intent["expected_count"] = expected_count

        return intent

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
