-- marts/analytics/product_metrics_daily.sql
-- Métricas diárias por produto: vendas, CTR, conversão

WITH events AS (
    SELECT * FROM {{ ref('fact_events') }}
),

orders AS (
    SELECT * FROM {{ ref('fact_orders') }}
    WHERE is_completed = TRUE
),

clicks_daily AS (
    SELECT
        event_date,
        product_id,
        COUNT(*)                AS impressions,
        COUNT(DISTINCT user_id) AS unique_users
    FROM events
    WHERE event_type = 'clicks'
      AND product_id IS NOT NULL
    GROUP BY event_date, product_id
),

purchases_daily AS (
    SELECT
        CAST(DATE_FORMAT(created_at, '%Y-%m-%d') AS DATE) AS event_date,
        -- product_id vem de order_items — aqui simplificado via fact_events
        p.product_id,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(o.total_amount)        AS revenue
    FROM orders o
    JOIN events p ON p.event_type = 'purchase' AND p.user_id = o.user_id
    WHERE p.product_id IS NOT NULL
    GROUP BY 1, 2
),

final AS (
    SELECT
        c.event_date,
        c.product_id,
        c.impressions,
        c.unique_users,
        COALESCE(p.order_count, 0)                              AS orders,
        COALESCE(p.revenue, 0)                                  AS revenue,
        CASE
            WHEN c.impressions > 0
            THEN COALESCE(p.order_count, 0) * 1.0 / c.impressions
            ELSE 0
        END                                                     AS conversion_rate
    FROM clicks_daily c
    LEFT JOIN purchases_daily p
           ON c.event_date  = p.event_date
          AND c.product_id  = p.product_id
)

SELECT * FROM final
