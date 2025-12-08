# app/llm/templates.py
"""
SQL TEMPLATE ENGINE (Production Version) - FIXED
Düzeltmeler:
- ✅ Tüm JOIN'larda alias kullanımı kontrol edildi
- ✅ ProductKey yerine ProductName döndürülüyor
- ✅ Yeni template eklendi: template_bottom_products_by_quantity
- ✅ DateKey ambiguity sorunları düzeltildi

Kapsam:
- 27+ adet yüksek doğruluklu, rule-based SQL şablonu
- ContosoRetailDW (SQL Server) veri ambarı için optimize edildi
- FactSales + FactOnlineSales + DimDate + DimProduct + DimStore + DimGeography + DimCustomer vb.
"""

# -------------------------------------------------------------------
# Yardımcı fonksiyonlar
# -------------------------------------------------------------------


def _escape_literal(value: str) -> str:
    if value is None:
        return ""
    return str(value).replace("'", "''")


# ================================================================
# 1) BASİT / ORTA SEVİYE AGGREGATION & TREND TEMPLATE'LERİ
# ================================================================


def template_total_sales(year: int | None = None):
    sql = """
SELECT
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    return sql.strip()


def template_top_products(limit: int, year: int | None = None):
    """
    En çok satan ürünler (tutar bazlı).
    Limit dışarıdan gelir (IntentClassifier).
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


def template_bottom_products(limit: int, year: int | None = None):
    """
    En az satan ürünler (tutar bazlı).
    Limit dışarıdan gelir (IntentClassifier).
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


def template_bottom_products_by_quantity(limit: int, year: int | None = None):
    """
    En az satan ürünler (ADET bazlı).
    Limit dışarıdan gelir (IntentClassifier).
    """
    sql = f"""
SELECT TOP {limit}
    dp.ProductName,
    SUM(fs.SalesQuantity) AS TotalQuantity,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimProduct dp ON fs.ProductKey = dp.ProductKey
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dp.ProductName
ORDER BY TotalQuantity ASC
"""
    return sql.strip()


def template_monthly_trend(year: int):
    return f"""
SELECT
    dd.CalendarMonth AS MonthNumber,
    dd.CalendarMonthLabel AS Month,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}
GROUP BY dd.CalendarMonth, dd.CalendarMonthLabel
ORDER BY dd.CalendarMonth
""".strip()


def template_quarterly_trend(year: int):
    return f"""
SELECT
    dd.CalendarQuarter AS Quarter,
    dd.CalendarQuarterLabel AS QuarterLabel,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}
GROUP BY dd.CalendarQuarter, dd.CalendarQuarterLabel
ORDER BY dd.CalendarQuarter
""".strip()


def template_daily_trend(year: int | None = None, month: int | None = None):
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
ORDER BY dd.FullDateLabel
"""
    return sql.strip()


def template_weekly_trend(year: int):
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
    limit: int,
    year: int | None = None,
):
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


def template_best_stores(limit: int, year: int | None = None):
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


def template_worst_stores(limit: int, year: int | None = None):
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
ORDER BY TotalSales ASC
"""
    return sql.strip()


# ================================================================
# 3) COĞRAFİ & MÜŞTERİ BAZLI TEMPLATE'LER
# ================================================================


def template_region_sales(year: int | None = None):
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
ORDER BY dd.FullDateLabel
""".strip()


def template_abc_analysis():
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


# ================================================================
# 5) ONLINE KANAL TEMPLATE'LERİ
# ================================================================


def template_top_online_products(limit: int, year: int | None = None):
    sql = f"""
SELECT TOP {limit}
    dp.ProductName,
    SUM(fos.SalesAmount) AS TotalSales
FROM FactOnlineSales fos
JOIN DimProduct dp ON fos.ProductKey = dp.ProductKey
JOIN DimDate dd ON fos.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dp.ProductName
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_bottom_online_products(limit: int, year: int | None = None):
    sql = f"""
SELECT TOP {limit}
    dp.ProductName,
    SUM(fos.SalesAmount) AS TotalSales
FROM FactOnlineSales fos
JOIN DimProduct dp ON fos.ProductKey = dp.ProductKey
JOIN DimDate dd ON fos.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dp.ProductName
ORDER BY TotalSales ASC
"""
    return sql.strip()


def template_online_category_sales(year: int | None = None):
    sql = """
SELECT
    dpc.ProductCategoryName,
    SUM(fos.SalesAmount) AS TotalSales
FROM FactOnlineSales fos
JOIN DimProduct dp ON fos.ProductKey = dp.ProductKey
JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
JOIN DimDate dd ON fos.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dpc.ProductCategoryName
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_top_online_products_in_category(
    category_name: str,
    limit: int,
    year: int | None = None,
):
    cat = _escape_literal(category_name)
    sql = f"""
SELECT TOP {limit}
    dp.ProductName,
    dpc.ProductCategoryName,
    SUM(fos.SalesAmount) AS TotalSales
FROM FactOnlineSales fos
JOIN DimProduct dp ON fos.ProductKey = dp.ProductKey
JOIN DimProductSubcategory dps ON dp.ProductSubcategoryKey = dps.ProductSubcategoryKey
JOIN DimProductCategory dpc ON dps.ProductCategoryKey = dpc.ProductCategoryKey
JOIN DimDate dd ON fos.DateKey = dd.DateKey
WHERE dpc.ProductCategoryName = '{cat}'
"""
    if year:
        sql += f"  AND dd.CalendarYear = {year}\n"
    sql += """
GROUP BY dp.ProductName, dpc.ProductCategoryName
ORDER BY TotalSales DESC
"""
    return sql.strip()


def template_online_monthly_trend(year: int):
    return f"""
SELECT
    dd.CalendarMonth AS MonthNumber,
    dd.CalendarMonthLabel AS Month,
    SUM(fos.SalesAmount) AS TotalSales
FROM FactOnlineSales fos
JOIN DimDate dd ON fos.DateKey = dd.DateKey
WHERE dd.CalendarYear = {year}
GROUP BY dd.CalendarMonth, dd.CalendarMonthLabel
ORDER BY dd.CalendarMonth
""".strip()


# ================================================================
# 6) TEMPLATE MAP
# ================================================================

TEMPLATE_MAP = {
    "total_sales": template_total_sales,
    "top_products": template_top_products,
    "bottom_products": template_bottom_products,
    "bottom_products_quantity": template_bottom_products_by_quantity,
    "monthly_trend": template_monthly_trend,
    "quarterly_trend": template_quarterly_trend,
    "weekly_trend": template_weekly_trend,
    "daily_trend": template_daily_trend,
    "store_vs_online": template_store_vs_online,
    "yearly_comparison": template_yearly_comparison,
    "category_sales": template_category_sales,
    "subcategory_sales": template_subcategory_sales,
    "top_product_each_category": template_top_product_each_category,
    "top_products_in_category": template_top_products_in_category,
    "best_stores": template_best_stores,
    "worst_stores": template_worst_stores,
    "region_sales": template_region_sales,
    "region_store_vs_online": template_region_store_vs_online,
    "top_online_products": template_top_online_products,
    "bottom_online_products": template_bottom_online_products,
    "online_category_sales": template_online_category_sales,
    "online_monthly_trend": template_online_monthly_trend,
    "profit_margin": template_profit_margin_by_product,
    "return_rate": template_return_rate_by_category,
    "yoy_growth": template_yoy_growth,
    "abc_analysis": template_abc_analysis,
}
