-- marts/analytics/churn_features.sql
-- Features para modelo de churn + label

WITH orders AS (
    SELECT * FROM {{ ref('fact_orders') }}
    WHERE is_completed = TRUE
),

user_metrics AS (
    SELECT
        user_id,
        COUNT(DISTINCT order_id)                                              AS total_orders,
        SUM(total_amount)                                                     AS total_revenue,
        AVG(total_amount)                                                     AS avg_order_value,
        MIN(CAST(created_at AS DATE))                                        AS first_order_date,
        MAX(CAST(created_at AS DATE))                                        AS last_order_date,
        DATE_DIFF('day', MAX(CAST(created_at AS DATE)), CURRENT_DATE)        AS days_since_last_order,
        COUNT(CASE WHEN CAST(created_at AS DATE) >= DATE_ADD(CURRENT_DATE, -30 * 1) THEN 1 END) AS orders_last_30d,
        COUNT(CASE WHEN CAST(created_at AS DATE) >= DATE_ADD(CURRENT_DATE, -90 * 1) THEN 1 END) AS orders_last_90d,
        AVG(items_count)                                                      AS avg_items_per_order
    FROM orders
    GROUP BY user_id
),

churn_label AS (
    -- Churn: sem compra nos últimos 30 dias E sem compra nos próximos 30
    -- (na prática usamos os últimos 60 dias para label histórico)
    SELECT
        user_id,
        CASE
            WHEN days_since_last_order > 60 THEN 1
            ELSE 0
        END AS churn_label
    FROM user_metrics
),

final AS (
    SELECT
        m.user_id,
        m.total_orders,
        m.total_revenue,
        m.avg_order_value,
        m.first_order_date,
        m.last_order_date,
        m.days_since_last_order,
        m.orders_last_30d,
        m.orders_last_90d,
        m.avg_items_per_order,
        DATE_DIFF('day', m.first_order_date, m.last_order_date)  AS customer_tenure_days,
        CASE WHEN m.orders_last_30d > 0 THEN m.orders_last_30d * 1.0 / m.total_orders ELSE 0 END AS recency_ratio,
        c.churn_label
    FROM user_metrics m
    JOIN churn_label c USING (user_id)
)

SELECT * FROM final
