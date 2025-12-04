# app/llm/templates.py
"""
SQL TEMPLATE ENGINE (Production Version)
Kapsam:
- 24+ adet yüksek doğruluklu, rule-based SQL şablonu
- ContosoRetailDW (SQL Server) veri ambarı için optimize edildi
- FactSales + FactOnlineSales + DimDate + DimProduct + DimStore + DimGeography + DimCustomer vb.
"""

# -------------------------------------------------------------------
# Yardımcı fonksiyonlar
# -------------------------------------------------------------------


def _escape_literal(value: str) -> str:
    """
    SQL string literal güvenliği için tek tırnakları escape eder.
    Örn: O'Reilly -> O''Reilly
    """
    if value is None:
        return ""
    return str(value).replace("'", "''")


# ================================================================
# 1) BASİT / ORTA SEVİYE AGGREGATION & TREND TEMPLATE'LERİ
# ================================================================


def template_total_sales(year: int | None = None):
    """
    Toplam satış tutarı.
    Örn: 2008 yılında toplam satış nedir?
    """
    sql = """
SELECT
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    return sql.strip()


def template_top_products(limit: int = 5, year: int | None = None):
    """
    En çok satan ürünler (tutar bazlı).
    Örn: En çok satan 5 ürün hangisi?
    """
    sql = f"""
SELECT TOP {limit}
    dp.ProductName,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dp.ProductName
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_bottom_products(limit: int = 3, year: int | None = None):
    """
    En az satan ürünler.
    Örn: En az satan 3 ürün hangisi?
    """
    sql = f"""
SELECT TOP {limit}
    dp.ProductName,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dp.ProductName
ORDER BY TotalSales ASC
"""
    return sql.strip()


def template_monthly_trend(year: int):
    """
    Aylık satış trendi.
    Örn: 2009 yılı aylık satış trendi.
    """
    return f"""
SELECT
    dd.CalendarMonthLabel AS Month,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}
GROUP BY dd.CalendarMonthLabel
ORDER BY dd.CalendarMonthLabel
""".strip()


def template_daily_trend(year: int | None = None, month: int | None = None):
    """
    Günlük satış trendi.
    Örn: 2008 yılında günlük satışlar; veya 2008 Mart ayı günlük satışlar.
    DimDate.FullDateLabel üzerinden gruplanır.
    """
    sql = """
SELECT
    dd.FullDateLabel AS [Date],
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    filters = []
    if year:
        filters.append(f"dd.CalendarYear = {year}")
    if month:
        filters.append(f"dd.CalendarMonth = {month}")

    if filters:
        sql += "WHERE " + " AND ".join(filters) + "\n"

    sql += """
GROUP BY dd.FullDateLabel
ORDER BY MIN(dd.DateKey)
"""
    return sql.strip()


def template_weekly_trend(year: int):
    """
    Haftalık satış trendi (CalendarWeek bazlı).
    Örn: 2008 yılı haftalık satış trendi.
    """
    return f"""
SELECT
    dd.CalendarWeek AS WeekNumber,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}
GROUP BY dd.CalendarWeek
ORDER BY dd.CalendarWeek
""".strip()


def template_store_vs_online(year: int):
    """
    Mağaza vs Online satış karşılaştırması.
    Örn: 2007'de mağaza vs online satış karşılaştırması.
    """
    return f"""
SELECT 'Store' AS Channel, SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}

UNION ALL

SELECT 'Online' AS Channel, SUM(fos.SalesAmount) AS TotalSales
FROM FactOnlineSales fos
JOIN DimDate dd ON fos.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}
""".strip()


def template_yearly_comparison(year1: int, year2: int):
    """
    İki yılın toplam satış karşılaştırması.
    Örn: 2007 ve 2008 yıl karşılaştırması.
    """
    return f"""
SELECT
    dd.CalendarYear AS [Year],
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear IN ({year1}, {year2})
GROUP BY dd.CalendarYear
ORDER BY dd.CalendarYear
""".strip()


# ================================================================
# 2) KATEGORİ & ÜRÜN BAZLI TEMPLATE'LER
# ================================================================


def template_category_sales(year: int | None = None):
    """
    Kategori bazında satış analizi.
    Örn: Kategori bazında satış analizi.
    """
    sql = """
SELECT
    dpc.ProductCategoryName,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dpc.ProductCategoryName
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_subcategory_sales(year: int | None = None):
    """
    Alt kategori (ProductSubcategory) bazlı satış analizi.
    """
    sql = """
SELECT
    dps.ProductSubcategoryName,
    dpc.ProductCategoryName,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dps.ProductSubcategoryName, dpc.ProductCategoryName
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_category_monthly_heatmap(year: int | None = None):
    """
    Kategori × Ay bazında satış matrisi (heatmap için).
    Örn: 2008 yılında, kategori bazında aylık satışlar.
    """
    sql = """
SELECT
    dpc.ProductCategoryName,
    dd.CalendarMonthLabel AS Month,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dpc.ProductCategoryName, dd.CalendarMonthLabel
ORDER BY dpc.ProductCategoryName, dd.CalendarMonthLabel
"""
    return sql.strip()


def template_top_product_each_category():
    """
    Her kategoride en çok satan ürünü getirir.
    Örn: Her kategoride en çok satan ürün hangisi?
    """
    return """
WITH CategorySales AS (
    SELECT
        dpc.ProductCategoryName,
        dp.ProductName,
        SUM(fs.SalesAmount) AS TotalSales,
        ROW_NUMBER() OVER (
            PARTITION BY dpc.ProductCategoryName
            ORDER BY SUM(fs.SalesAmount) DESC
        ) AS rn
    FROM FactSales fs
    JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
    JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
    JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
    GROUP BY dpc.ProductCategoryName, dp.ProductName
)
SELECT
    ProductCategoryName,
    ProductName,
    TotalSales
FROM CategorySales
WHERE rn = 1
ORDER BY ProductCategoryName
""".strip()


def template_top_products_in_category(
    category_name: str,
    limit: int = 5,
    year: int | None = None,
):
    """
    Belirli bir kategoride en çok satan ürünler.
    Örn: Laptop kategorisinde en çok satan 5 ürün hangisi?
    """
    cat = _escape_literal(category_name)
    sql = f"""
SELECT TOP {limit}
    dp.ProductName,
    dpc.ProductCategoryName,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dpc.ProductCategoryName = '{cat}'
"""
    if year:
        sql += f"  AND dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dp.ProductName, dpc.ProductCategoryName
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_top_product_details():
    """
    En çok satan ürünün detaylı bilgileri.
    Örn: En çok satan ürünün detaylı bilgileri.
    """
    return """
WITH Ranked AS (
    SELECT
        dp.ProductKey,
        dp.ProductName,
        SUM(fs.SalesAmount) AS TotalSales,
        ROW_NUMBER() OVER (ORDER BY SUM(fs.SalesAmount) DESC) AS rn
    FROM FactSales fs
    JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
    GROUP BY dp.ProductKey, dp.ProductName
)
SELECT
    r.ProductName,
    r.TotalSales,
    dps.ProductSubcategoryName,
    dpc.ProductCategoryName
FROM Ranked r
JOIN DimProduct dp ON r.ProductKey = dp.ProductKey
JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
WHERE r.rn = 1
""".strip()


def template_best_stores(limit: int = 5, year: int | None = None):
    """
    En iyi performans gösteren mağazalar.
    Örn: En iyi performans gösteren 5 mağaza.
    """
    sql = f"""
SELECT TOP {limit}
    st.StoreName,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimStore st ON fs.StoreKey = st.StoreKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY st.StoreName
ORDER BY TotalSales DESC
"""
    return sql.strip()


# ================================================================
# 3) COĞRAFİ & MÜŞTERİ BAZLI TEMPLATE'LER
# ================================================================


def template_region_sales(year: int | None = None):
    """
    Bölge bazında satış performansı (ülke/bölge seviyesinde).
    Örn: Bölge bazında satış performansı.
    """
    sql = """
SELECT
    geo.RegionCountryName,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimStore st ON fs.StoreKey = st.StoreKey
JOIN DimGeography geo ON st.GeographyKey = geo.GeographyKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY geo.RegionCountryName
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_region_store_vs_online(year: int):
    """
    Bölge bazında mağaza vs online satış karşılaştırması.
    """
    return f"""
SELECT
    geo.RegionCountryName,
    'Store' AS Channel,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimStore st ON fs.StoreKey = st.StoreKey
JOIN DimGeography geo ON st.GeographyKey = geo.GeographyKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}
GROUP BY geo.RegionCountryName

UNION ALL

SELECT
    geo.RegionCountryName,
    'Online' AS Channel,
    SUM(fos.SalesAmount) AS TotalSales
FROM FactOnlineSales fos
JOIN DimCustomer dc ON fos.CustomerKey = dc.CustomerKey
JOIN DimGeography geo ON dc.GeographyKey = geo.GeographyKey
JOIN DimDate dd ON fos.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}
GROUP BY geo.RegionCountryName
""".strip()


def template_customer_segment_revenue(year: int | None = None):
    """
    Müşteri segmenti bazında gelir (örnek segment: Education).
    Örn: Eğitim seviyesine göre toplam online satış.
    """
    sql = """
SELECT
    dc.Education,
    SUM(fos.SalesAmount) AS TotalSales
FROM FactOnlineSales fos
JOIN DimCustomer dc ON fos.CustomerKey = dc.CustomerKey
JOIN DimDate dd ON fos.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dc.Education
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_avg_revenue_per_customer(year: int | None = None):
    """
    Müşteri başına ortalama gelir (online kanal).
    """
    sql = """
SELECT
    COUNT(DISTINCT fos.CustomerKey) AS CustomerCount,
    SUM(fos.SalesAmount) AS TotalSales,
    CASE
        WHEN COUNT(DISTINCT fos.CustomerKey) = 0 THEN NULL
        ELSE SUM(fos.SalesAmount) * 1.0 / COUNT(DISTINCT fos.CustomerKey)
    END AS AvgRevenuePerCustomer
FROM FactOnlineSales fos
JOIN DimDate dd ON fos.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    return sql.strip()


# ================================================================
# 4) FİNANSAL & KPI TEMPLATE'LERİ
# ================================================================


def template_profit_margin_by_product(year: int | None = None):
    """
    Ürün bazında yaklaşık kâr analizi.
    Kâr ≈ (UnitPrice - UnitCost) * SalesQuantity - DiscountAmount - ReturnAmount
    """
    sql = """
SELECT
    dp.ProductName,
    SUM(fs.SalesAmount) AS Revenue,
    SUM((fs.UnitPrice - fs.UnitCost) * fs.SalesQuantity
        - fs.DiscountAmount
        - fs.ReturnAmount) AS ApproxProfit
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dp.ProductName
ORDER BY ApproxProfit DESC
"""
    return sql.strip()


def template_return_rate_by_category(year: int | None = None):
    """
    Kategori bazında iade oranı (ReturnQuantity / SalesQuantity).
    """
    sql = """
SELECT
    dpc.ProductCategoryName,
    SUM(fs.SalesQuantity) AS TotalQty,
    SUM(fs.ReturnQuantity) AS ReturnQty,
    CASE
        WHEN SUM(fs.SalesQuantity) = 0 THEN NULL
        ELSE SUM(fs.ReturnQuantity) * 1.0 / SUM(fs.SalesQuantity)
    END AS ReturnRate
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dpc.ProductCategoryName
ORDER BY ReturnRate DESC
"""
    return sql.strip()


def template_yoy_growth(start_year: int, end_year: int):
    """
    Yıllık satış ve yıl bazında büyüme oranı (YoY Growth %).
    """
    return f"""
WITH Yearly AS (
    SELECT
        dd.CalendarYear AS [Year],
        SUM(fs.SalesAmount) AS TotalSales
    FROM FactSales fs
    JOIN DimDate dd ON fs.DateKey = dd.DateKey
    WHERE dd.CalendarYear BETWEEN {start_year} AND {end_year}
    GROUP BY dd.CalendarYear
)
SELECT
    y.[Year],
    y.TotalSales,
    LAG(y.TotalSales) OVER (ORDER BY y.[Year]) AS PreviousYearSales,
    CASE
        WHEN LAG(y.TotalSales) OVER (ORDER BY y.[Year]) IS NULL THEN NULL
        WHEN LAG(y.TotalSales) OVER (ORDER BY y.[Year]) = 0 THEN NULL
        ELSE (y.TotalSales - LAG(y.TotalSales) OVER (ORDER BY y.[Year]))
             * 100.0
             / NULLIF(LAG(y.TotalSales) OVER (ORDER BY y.[Year]), 0)
    END AS YoYGrowthPercent
FROM Yearly y
ORDER BY y.[Year]
""".strip()


def template_last_n_days_sales(days: int = 30):
    """
    Son N gündeki satış performansı.
    DimDate içindeki en güncel tarihe göre geri gider.
    """
    return f"""
SELECT
    dd.FullDateLabel AS [Date],
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.FullDateLabel >= (
    SELECT DATEADD(DAY, -{days}, MAX(dd2.FullDateLabel))
    FROM DimDate dd2
)
GROUP BY dd.FullDateLabel
ORDER BY MIN(dd.DateKey)
""".strip()


def template_abc_analysis():
    """
    ABC analizi: ürünleri ciroya göre sıralayıp kümülatif yüzde hesaplar.
    A: ilk ~%80, B: sonraki ~%15, C: son ~%5 (yorumlama istemci tarafında yapılabilir).
    """
    return """
WITH ProductRevenue AS (
    SELECT
        dp.ProductName,
        SUM(fs.SalesAmount) AS TotalSales
    FROM FactSales fs
    JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
    GROUP BY dp.ProductName
),
OrderedRevenue AS (
    SELECT
        ProductName,
        TotalSales,
        SUM(TotalSales) OVER () AS GrandTotal,
        SUM(TotalSales) OVER (ORDER BY TotalSales DESC) AS RunningTotal
    FROM ProductRevenue
)
SELECT
    ProductName,
    TotalSales,
    GrandTotal,
    RunningTotal,
    CASE
        WHEN GrandTotal = 0 THEN NULL
        ELSE RunningTotal * 100.0 / GrandTotal
    END AS CumulativeSharePercent
FROM OrderedRevenue
ORDER BY TotalSales DESC
""".strip()
