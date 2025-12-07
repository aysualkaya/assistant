# app/llm/template_router.py
"""
TemplateRouter (2025 – Production Edition)

Amaç:
- Intent + natural language → DOĞRU hazır SQL template'ine route etmek
- LLM kullanımını minimuma indirmek
- Deterministik, hatasız, okunabilir SQL üretmek

Kullandığı kaynaklar:
- app.llm.templates içindeki tüm template_* fonksiyonları
- IntentClassifier çıktısı (query_type, order_direction, vs.)
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
        Ana giriş noktası.

        Args:
            question: Kullanıcı sorusu (TR/EN)
            intent: IntentClassifier çıktısı, örn:
                {
                  "query_type": "ranking" | "aggregation" | "trend" | "comparison" | ...
                  "order_direction": "asc" | "desc" | ...
                  "complexity": 5,
                  ...
                }

        Returns:
            str (SQL) veya None (LLM'e bırak)
        """
        q = question.lower()
        years = self._extract_years(q)
        year = years[0] if years else None
        limit = self._infer_limit(q, default=5)

        query_type = intent.get("query_type", "aggregation") or "aggregation"
        direction = (intent.get("order_direction") or "desc").lower()

        logger.info(
            f"📦 TemplateRouter: type={query_type}, dir={direction}, year={year}, limit={limit}"
        )

        # 1) RANKING (sıralama) soruları
        if query_type == "ranking":
            sql = self._route_ranking(q, direction, year, limit)
            if sql:
                return sql

        # 2) TREND soruları (aylık, haftalık, günlük, çeyrek vb.)
        if query_type == "trend":
            sql = self._route_trend(q, year)
            if sql:
                return sql

        # 3) BASİT / TOPLAM / KPI soruları
        if query_type == "aggregation":
            sql = self._route_aggregation(q, years, year)
            if sql:
                return sql

        # 4) KARŞILAŞTIRMA soruları (store vs online, yıllar arası vb.)
        if query_type == "comparison":
            sql = self._route_comparison(q, years, year)
            if sql:
                return sql

        # 5) Diğer/karmaşık durumlar için fallback pattern'ler
        sql = self._route_fallback_patterns(q, years, year, direction, limit)
        if sql:
            return sql

        # Template bulunamadı → LLM devreye girsin
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
        limit: int,
    ) -> Optional[str]:
        """
        En çok / en az satan:
        - ürün
        - mağaza
        - online ürünler
        - bölge / kategori bazlı sıralamalar
        """
        is_online = self._has_any(q, ["online", "web", "internet"])
        is_store = self._has_any(q, ["mağaza", "magaza", "store"])
        is_category = self._has_any(q, ["kategori", "category"])
        is_region = self._has_any(q, ["bölge", "region", "ülke", "country"])
        is_quantity = self._is_quantity_question(q)

        # 1) Online ürün ranking
        if is_online and self._has_any(q, ["ürün", "urun", "product"]):
            if direction == "asc":
                return T.template_bottom_online_products(limit=limit, year=year)
            return T.template_top_online_products(limit=limit, year=year)

        # 2) Mağaza ranking
        if is_store:
            if direction == "asc":
                return T.template_worst_stores(limit=limit, year=year)
            return T.template_best_stores(limit=limit, year=year)

        # 3) Bölge bazlı ranking
        if is_region:
            # Şimdilik total sales DESC, direction'dan bağımsız
            return T.template_region_sales(year=year)

        # 4) Kategori bazında ranking
        if is_category:
            # Daha ileri seviye: spesifik category_name parse edilebilir
            return T.template_category_sales(year=year)

        # 5) Genel ürün ranking (default path)
        if self._has_any(q, ["ürün", "urun", "product"]):
            if direction == "asc":
                # En az satan ürün → adet mi, tutar mı?
                if is_quantity:
                    return T.template_bottom_products_by_quantity(limit=limit, year=year)
                return T.template_bottom_products(limit=limit, year=year)
            else:
                # En çok satan ürün
                return T.template_top_products(limit=limit, year=year)

        return None

    # ============================================================
    #  TREND ROUTES
    # ============================================================
    def _route_trend(self, q: str, year: Optional[int]) -> Optional[str]:
        """
        Aylık, haftalık, günlük, çeyreklik trend soruları.
        """
        # Online kanal trendleri
        if self._has_any(q, ["online", "web", "internet"]):
            if self._has_any(q, ["aylık", "aylik", "monthly", "her ay"]):
                if year is None:
                    return None
                return T.template_online_monthly_trend(year=year)

        # Genel trendler
        if self._has_any(q, ["çeyrek", "quarter", "quarterly"]):
            if year is None:
                return None
            return T.template_quarterly_trend(year=year)

        if self._has_any(q, ["hafta", "haftalık", "weekly", "week"]):
            if year is None:
                return None
            return T.template_weekly_trend(year=year)

        if self._has_any(q, ["günlük", "daily", "her gün"]):
            # Günlük trend → year varsa, year kullan; yoksa tüm tarih
            return T.template_daily_trend(year=year)

        # Default: aylık trend
        if self._has_any(q, ["aylık", "aylik", "monthly", "her ay"]):
            if year is None:
                return None
            return T.template_monthly_trend(year=year)

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
        """
        Toplam satış, kâr, iade oranı, müşteri geliri vb. metrikler.
        """
        # 1) Toplam satış (ciro)
        if self._has_any(q, ["toplam satış", "toplam satis", "total sales", "ciro", "revenue"]):
            return T.template_total_sales(year=year)

        # 2) Kâr / kârlılık
        if self._has_any(q, ["kâr", "kar", "profit", "marj", "margin"]):
            return T.template_profit_margin_by_product(year=year)

        # 3) İade oranı
        if self._has_any(q, ["iade", "return rate", "return ratio"]):
            return T.template_return_rate_by_category(year=year)

        # 4) Müşteri segmenti gelirleri
        if self._has_any(
            q,
            [
                "müşteri segment",
                "musteri segment",
                "segment",
                "education",
                "income",
            ],
        ):
            return T.template_customer_segment_revenue(year=year)

        # 5) Müşteri başına ortalama gelir
        if self._has_any(
            q,
            [
                "müşteri başına",
                "musteri basina",
                "per customer",
                "average revenue",
            ],
        ):
            return T.template_avg_revenue_per_customer(year=year)

        # 6) ABC analizi
        if self._has_any(q, ["abc analizi", "abc analysis"]):
            return T.template_abc_analysis()

        # 7) Son N gün satışları
        if self._has_any(q, ["son", "last"]) and self._has_any(
            q, ["gün", "gun", "day", "days"]
        ):
            days = self._extract_last_n_days(q) or 30
            return T.template_last_n_days_sales(days=days)

        # 8) Kategori / alt kategori bazlı toplamlar
        if self._has_any(q, ["kategori", "category"]):
            if self._has_any(q, ["alt kategori", "subcategory"]):
                return T.template_subcategory_sales(year=year)
            return T.template_category_sales(year=year)

        # 9) Bölge bazında toplamlar
        if self._has_any(q, ["bölge", "region", "ülke", "country"]):
            return T.template_region_sales(year=year)

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
        """
        Mağaza vs online, yıl karşılaştırmaları vb.
        """
        # 1) Mağaza vs Online
        if self._has_any(q, ["mağaza", "magaza", "store"]) and self._has_any(
            q, ["online", "web", "internet"]
        ):
            # Bölge de geçiyorsa → region_store_vs_online
            if self._has_any(q, ["bölge", "region", "ülke", "country"]):
                if year is None:
                    return None
                return T.template_region_store_vs_online(year=year)

            if year is None:
                return None
            return T.template_store_vs_online(year=year)

        # 2) Yıl karşılaştırması (2 yıl verilmişse)
        if len(years) >= 2:
            y1, y2 = years[0], years[1]
            if self._has_any(q, ["büyüme", "artış", "increase", "growth", "yoy"]):
                return T.template_yoy_growth(start_year=y1, end_year=y2)
            return T.template_yearly_comparison(year1=y1, year2=y2)

        # 3) Tek yıl + "geçen yıl" / "previous year"
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
        limit: int,
    ) -> Optional[str]:
        """
        Intent yanlış sınıflanmış bile olsa yakalamaya çalıştığımız
        genel, sık sorulan pattern'ler.
        """
        # Genel "en çok / en az satan ürün" fallback'i
        if self._has_any(
            q,
            ["en çok satan", "en cok satan", "top seller", "most sold", "top selling"],
        ):
            return T.template_top_products(limit=limit, year=year)

        if self._has_any(
            q,
            ["en az satan", "least sold", "worst selling", "lowest selling"],
        ):
            if self._is_quantity_question(q):
                return T.template_bottom_products_by_quantity(limit=limit, year=year)
            return T.template_bottom_products(limit=limit, year=year)

        # "yıllara göre büyüme" gibi ama intent yanlış sınıflanmış olabilir
        if self._has_any(q, ["büyüme", "growth", "artış", "increase"]) and len(years) >= 2:
            return T.template_yoy_growth(start_year=years[0], end_year=years[-1])

        return None

    # ============================================================
    #  HELPERS
    # ============================================================
    def _extract_years(self, text: str) -> List[int]:
        years = re.findall(r"(20\d{2})", text)
        return [int(y) for y in years]

    def _infer_limit(self, text: str, default: int = 5) -> int:
        """
        Soru cümlesinden '5', 'ilk 10', 'top 3' gibi sayıları çek.
        İlk gördüğün sayıyı al, yoksa default.
        """
        m = re.search(r"\b(\d+)\b", text)
        if not m:
            return default
        try:
            val = int(m.group(1))
            return max(1, min(val, 100))  # uç değerleri kısıtla
        except ValueError:
            return default

    def _has_any(self, text: str, keywords: List[str]) -> bool:
        return any(k in text for k in keywords)

    def _is_quantity_question(self, q: str) -> bool:
        """
        Kullanıcının adet bazlı mı yoksa ciro bazlı mı sorduğunu tahmin eder.
        """
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
        # Belirsizse default: value-based
        return False

    def _extract_last_n_days(self, q: str) -> Optional[int]:
        """
        'son 30 gün', 'last 7 days' gibi kalıplardan N'i çekmeye çalışır.
        """
        # TR: "son 30 gün"
        m = re.search(r"son\s+(\d+)\s+g[üu]n", q)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

        # EN: "last 30 days"
        m = re.search(r"last\s+(\d+)\s+day", q)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

        return None
