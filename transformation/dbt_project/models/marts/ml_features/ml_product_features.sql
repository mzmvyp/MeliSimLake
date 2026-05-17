-- marts/ml_features/ml_product_features.sql

WITH metrics AS (
    SELECT * FROM {{ ref('product_metrics_daily') }}
),

products AS (
    SELECT * FROM {{ ref('dim_products') }}
),

agg AS (
    SELECT
        product_id,
        SUM(impressions)     AS total_impressions_30d,
        SUM(orders)          AS total_orders_30d,
        SUM(revenue)         AS total_revenue_30d,
        AVG(conversion_rate) AS avg_conversion_rate_30d
    FROM metrics
    WHERE event_date >= DATE_ADD(CURRENT_DATE, -30 * 1)
    GROUP BY product_id
),

final AS (
    SELECT
        p.product_id,
        CURRENT_TIMESTAMP                            AS feature_timestamp,
        p.price,
        p.stock_quantity,
        p.brand,
        p.category_id,
        COALESCE(a.total_impressions_30d, 0)         AS total_impressions_30d,
        COALESCE(a.total_orders_30d, 0)              AS total_orders_30d,
        COALESCE(a.total_revenue_30d, 0)             AS total_revenue_30d,
        COALESCE(a.avg_conversion_rate_30d, 0)       AS avg_conversion_rate_30d
    FROM products p
    LEFT JOIN agg a USING (product_id)
)

SELECT * FROM final
