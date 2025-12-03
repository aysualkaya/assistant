# app/llm/templates.py
"""
SQL TEMPLATE ENGINE (Production Version)
Covers 12+ test scenarios with high-accuracy rule-based SQL.
"""

# ================================================================
# 1) SIMPLE AGGREGATION
# ================================================================
def template_total_sales(year=None):
    sql = """
SELECT SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
"""
    if year:
        sql += f"WHERE dd.CalendarYear = {year}\n"
    return sql.strip()


# ================================================================
# 2) TOP PRODUCTS
# ================================================================
def template_top_products(limit=5, year=None):
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


# ================================================================
# 3) BOTTOM PRODUCTS
# ================================================================
def template_bottom_products(limit=3, year=None):
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


# ================================================================
# 4) MONTHLY TREND
# ================================================================
def template_monthly_trend(year):
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


# ================================================================
# 5) STORE VS ONLINE COMPARISON
# ================================================================
def template_store_vs_online(year):
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


# ================================================================
# 6) CATEGORY SALES (Category Analysis)
# ================================================================
def template_category_sales(year=None):
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


# ================================================================
# 7) YEARLY COMPARISON (2007 vs 2008)
# ================================================================
def template_yearly_comparison(year1, year2):
    return f"""
SELECT
    dd.CalendarYear AS Year,
    SUM(fs.SalesAmount) AS TotalSales
FROM FactSales fs
JOIN DimDate dd ON fs.DateKey = dd.DateKey
WHERE dd.CalendarYear IN ({year1}, {year2})
GROUP BY dd.CalendarYear
ORDER BY dd.CalendarYear
""".strip()


# ================================================================
# 8) BEST STORES (Top Stores)
# ================================================================
def template_best_stores(limit=5, year=None):
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
# 9) PRODUCT DETAILS (Top-selling product details)
# ================================================================
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


# ================================================================
# 10) TOP PRODUCT IN EACH CATEGORY (Complex multi-table)
# ================================================================
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
SELECT ProductCategoryName, ProductName, TotalSales
FROM CategorySales
WHERE rn = 1
ORDER BY ProductCategoryName
""".strip()
