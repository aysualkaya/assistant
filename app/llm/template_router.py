# app/llm/template_router.py
"""
TemplateRouter (2025 – Dynamic, Default-Free Edition)

Amaç:
- Intent + natural language → DOĞRU hazır SQL template'ine route etmek
- LLM kullanımını minimuma indirmek
- Deterministik, hatasız, okunabilir SQL üretmek
- 🔥 TOP N limit'i sadece IntentClassifier.expected_count üzerinden yönetilir
"""

from typing import Dict, Optional, List
import re

from app.llm import templates as T
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TemplateRouter:
    """
    Natural language + intent → template SQL

    Template uygun bulunamazsa:
      → None döner ve DynamicSQLGenerator LLM tarafına geçer.
    """

    # ============================================================
    # PUBLIC API
    # ============================================================
    def route(self, question: str, intent: Dict) -> Optional[str]:
        """
        Args:
            question: Kullanıcı sorusu (TR/EN)
            intent: IntentClassifier çıktısı, örn:
                {
                  "query_type": "ranking" | "aggregation" | "trend" | "comparison" | ...
                  "order_direction": "asc" | "desc" | ...
                  "complexity": 5,
                  "expected_count": 1 / 5 / 10 ...
                }
        """
        q = question.lower()
        years = self._extract_years(q)
        year = years[0] if years else None

        # 🔥 Limit sadece intent.expected_count'tan gelir
        limit: Optional[int] = intent.get("expected_count")

        query_type = intent.get("query_type", "aggregation") or "aggregation"
        direction = (intent.get("order_direction") or "desc").lower()

        logger.info(
            f"📦 TemplateRouter: type={query_type}, dir={direction}, year={year}, limit={limit}"
        )

        if query_type == "ranking":
            sql = self._route_ranking(q, direction, year, limit)
            if sql:
                return sql

        if query_type == "trend":
            sql = self._route_trend(q, year)
            if sql:
                return sql

        if query_type == "aggregation":
            sql = self._route_aggregation(q, years, year)
            if sql:
                return sql

        if query_type == "comparison":
            sql = self._route_comparison(q, years, year)
            if sql:
                return sql

        sql = self._route_fallback_patterns(q, years, year, direction, limit)
        if sql:
            return sql

        logger.info("ℹ️ TemplateRouter: uygun template bulunamadı, LLM'e devrediliyor.")
        return None

    # ============================================================
    #  RANKING ROUTES
    # ============================================================
    def _route_ranking(
        self,
        q: str,
        direction: str,
        year: Optional[int],
        limit: Optional[int],
    ) -> Optional[str]:
        """
        En çok / en az satan:
        - ürün
        - mağaza
        - online ürünler
        - bölge / kategori bazlı sıralamalar

        🔥 limit None ise → Intent tarafı eksik demektir, template çağrılmaz.
        """
        is_online = self._has_any(q, ["online", "web", "internet"])
        is_store = self._has_any(q, ["mağaza", "magaza", "store"])
        is_category = self._has_any(q, ["kategori", "category"])
        is_region = self._has_any(q, ["bölge", "region", "ülke", "country"])
        is_quantity = self._is_quantity_question(q)

        # Eğer ranking sorusuysa ve limit yoksa → geri çekil
        if limit is None and (is_online or is_store or self._has_any(q, ["ürün", "urun", "product"])):
            logger.warning("⚠️ Ranking intent detected but no expected_count provided.")
            return None

        # 1) Online ürün ranking
        if is_online and self._has_any(q, ["ürün", "urun", "product"]):
            if direction == "asc":
                return T.template_bottom_online_products(limit, year)
            return T.template_top_online_products(limit, year)

        # 2) Mağaza ranking
        if is_store:
            if direction == "asc":
                return T.template_worst_stores(limit, year)
            return T.template_best_stores(limit, year)

        # 3) Bölge bazlı (şu an TOP N kullanmıyoruz)
        if is_region:
            return T.template_region_sales(year)

        # 4) Kategori bazlı (TOP N yok)
        if is_category:
            return T.template_category_sales(year)

        # 5) Genel ürün ranking
        if self._has_any(q, ["ürün", "urun", "product"]):
            if direction == "asc":
                if is_quantity:
                    return T.template_bottom_products_by_quantity(limit, year)
                return T.template_bottom_products(limit, year)
            else:
                return T.template_top_products(limit, year)

        return None

    # ============================================================
    #  TREND ROUTES
    # ============================================================
    def _route_trend(self, q: str, year: Optional[int]) -> Optional[str]:
        if year is None:
            # Bazı trendler year'sız da olabilir ama şimdilik sıkı tutuyoruz
            logger.info("Trend query but no year detected.")
        # Online kanal trendleri
        if self._has_any(q, ["online", "web", "internet"]):
            if self._has_any(q, ["aylık", "aylik", "monthly", "her ay"]):
                if year is None:
                    return None
                return T.template_online_monthly_trend(year)

        if self._has_any(q, ["çeyrek", "quarter", "quarterly"]):
            if year is None:
                return None
            return T.template_quarterly_trend(year)

        if self._has_any(q, ["hafta", "haftalık", "weekly", "week"]):
            if year is None:
                return None
            return T.template_weekly_trend(year)

        if self._has_any(q, ["günlük", "daily", "her gün"]):
            return T.template_daily_trend(year)

        if self._has_any(q, ["aylık", "aylik", "monthly", "her ay"]):
            if year is None:
                return None
            return T.template_monthly_trend(year)

        return None

    # ============================================================
    #  AGGREGATION ROUTES
    # ============================================================
    def _route_aggregation(
        self,
        q: str,
        years: List[int],
        year: Optional[int],
    ) -> Optional[str]:
        if self._has_any(q, ["toplam satış", "toplam satis", "total sales", "ciro", "revenue"]):
            return T.template_total_sales(year)

        if self._has_any(q, ["kâr", "kar", "profit", "marj", "margin"]):
            return T.template_profit_margin_by_product(year)

        if self._has_any(q, ["iade", "return rate", "return ratio", "refund"]):
            return T.template_return_rate_by_category(year)

        if self._has_any(q, ["müşteri segment", "musteri segment", "segment", "education", "income"]):
            return T.template_customer_segment_revenue(year)

        if self._has_any(q, ["müşteri başına", "musteri basina", "per customer", "average revenue"]):
            return T.template_avg_revenue_per_customer(year)

        if self._has_any(q, ["abc analizi", "abc analysis"]):
            return T.template_abc_analysis()

        if self._has_any(q, ["son", "last"]) and self._has_any(q, ["gün", "gun", "day", "days"]):
            days = self._extract_last_n_days(q) or 30
            return T.template_last_n_days_sales(days)

        if self._has_any(q, ["kategori", "category"]):
            if self._has_any(q, ["alt kategori", "subcategory"]):
                return T.template_subcategory_sales(year)
            return T.template_category_sales(year)

        if self._has_any(q, ["bölge", "region", "ülke", "country"]):
            return T.template_region_sales(year)

        return None

    # ============================================================
    #  COMPARISON ROUTES
    # ============================================================
    def _route_comparison(
        self,
        q: str,
        years: List[int],
        year: Optional[int],
    ) -> Optional[str]:
        if self._has_any(q, ["mağaza", "magaza", "store"]) and self._has_any(
            q, ["online", "web", "internet"]
        ):
            if self._has_any(q, ["bölge", "region", "ülke", "country"]):
                if year is None:
                    return None
                return T.template_region_store_vs_online(year)
            if year is None:
                return None
            return T.template_store_vs_online(year)

        if len(years) >= 2:
            y1, y2 = years[0], years[1]
            if self._has_any(q, ["büyüme", "artış", "increase", "growth", "yoy"]):
                return T.template_yoy_growth(start_year=y1, end_year=y2)
            return T.template_yearly_comparison(year1=y1, year2=y2)

        if year is not None and self._has_any(
            q, ["geçen yıl", "gecen yil", "previous year", "last year"]
        ):
            start = year - 1
            end = year
            return T.template_yoy_growth(start_year=start, end_year=end)

        return None

    # ============================================================
    #  FALLBACK PATTERNS
    # ============================================================
    def _route_fallback_patterns(
        self,
        q: str,
        years: List[int],
        year: Optional[int],
        direction: str,
        limit: Optional[int],
    ) -> Optional[str]:
        # Eğer limit yoksa, ranking fallback uygulamıyoruz
        if limit is None:
            return None

        if self._has_any(
            q,
            ["en çok satan", "en cok satan", "top seller", "most sold", "top selling"],
        ):
            return T.template_top_products(limit, year)

        if self._has_any(
            q,
            ["en az satan", "least sold", "worst selling", "lowest selling"],
        ):
            if self._is_quantity_question(q):
                return T.template_bottom_products_by_quantity(limit, year)
            return T.template_bottom_products(limit, year)

        if self._has_any(q, ["büyüme", "growth", "artış", "increase"]) and len(years) >= 2:
            return T.template_yoy_growth(start_year=years[0], end_year=years[-1])

        return None

    # ============================================================
    #  HELPERS
    # ============================================================
    def _extract_years(self, text: str) -> List[int]:
        years = re.findall(r"(20\d{2})", text)
        return [int(y) for y in years]

    def _has_any(self, text: str, keywords: List[str]) -> bool:
        return any(k in text for k in keywords)

    def _is_quantity_question(self, q: str) -> bool:
        quantity_markers = [
            "adet",
            "miktar",
            "quantity",
            "units",
            "kaçar adet",
            "satış adedi",
            "satis adedi",
            "kaç tane",
            "kac tane",
        ]
        value_markers = [
            "ciro",
            "revenue",
            "tutar",
            "sales amount",
            "gelir",
        ]

        if self._has_any(q, quantity_markers):
            return True
        if self._has_any(q, value_markers):
            return False
        return False

    def _extract_last_n_days(self, q: str) -> Optional[int]:
        m = re.search(r"son\s+(\d+)\s+g[üu]n", q)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

        m = re.search(r"last\s+(\d+)\s+day", q)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

        return None
