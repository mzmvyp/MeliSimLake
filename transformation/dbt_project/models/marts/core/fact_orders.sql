-- marts/core/fact_orders.sql
-- Fato pedidos — grain: 1 linha por order (sem items)

WITH orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

dim_users AS (
    SELECT user_sk, user_id FROM {{ ref('dim_users') }}
),

dim_date AS (
    SELECT date_sk, full_date FROM {{ ref('dim_date') }}
),

final AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['o.order_id']) }} AS order_sk,
        o.order_id,
        COALESCE(u.user_sk, 'unknown')                         AS user_sk,
        o.user_id,
        COALESCE(
            d.date_sk,
            CAST(DATE_FORMAT(o.created_at, '%Y%m%d') AS INTEGER)
        )                                                       AS order_date_sk,
        o.status,
        o.total_amount,
        o.currency,
        o.payment_method,
        o.items_count,
        o.created_at,
        o.updated_at,
        o.completed_at,
        CASE
            WHEN o.status = 'completed' THEN TRUE
            ELSE FALSE
        END                                                     AS is_completed,
        DATE_DIFF('day', CAST(o.created_at AS DATE), CAST(o.completed_at AS DATE)) AS fulfillment_days
    FROM orders o
    LEFT JOIN dim_users u   ON o.user_id  = u.user_id
    LEFT JOIN dim_date  d   ON CAST(DATE_FORMAT(o.created_at, '%Y%m%d') AS INTEGER) = d.date_sk
)

SELECT * FROM final
