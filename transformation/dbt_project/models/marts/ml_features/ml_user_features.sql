-- marts/ml_features/ml_user_features.sql
-- Features de usuário para Feast feature store

WITH churn AS (
    SELECT * FROM {{ ref('churn_features') }}
),

rfm AS (
    SELECT * FROM {{ ref('customer_rfm') }}
),

final AS (
    SELECT
        c.user_id,
        CURRENT_TIMESTAMP                   AS feature_timestamp,
        c.total_orders,
        c.total_revenue,
        c.avg_order_value,
        c.days_since_last_order,
        c.orders_last_30d,
        c.orders_last_90d,
        c.avg_items_per_order,
        c.customer_tenure_days,
        c.recency_ratio,
        r.r_score,
        r.f_score,
        r.m_score,
        r.rfm_total,
        r.rfm_segment
    FROM churn c
    LEFT JOIN rfm r USING (user_id)
)

SELECT * FROM final
