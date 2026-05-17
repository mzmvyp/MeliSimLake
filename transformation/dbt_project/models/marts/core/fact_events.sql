-- marts/core/fact_events.sql
-- Fato eventos comportamentais — grain: 1 linha por evento

WITH events AS (
    SELECT * FROM {{ ref('stg_events') }}
),

dim_users AS (
    SELECT user_sk, user_id FROM {{ ref('dim_users') }}
),

dim_products AS (
    SELECT product_sk, product_id FROM {{ ref('dim_products') }}
),

dim_date AS (
    SELECT date_sk, full_date FROM {{ ref('dim_date') }}
),

final AS (
    SELECT
        e.event_id,
        e.event_type,
        e.session_id,
        COALESCE(u.user_sk, 'unknown')         AS user_sk,
        e.user_id,
        COALESCE(p.product_sk, 'unknown')      AS product_sk,
        e.product_id,
        COALESCE(d.date_sk,
            CAST(DATE_FORMAT(e.event_ts, '%Y%m%d') AS INTEGER)
        )                                       AS event_date_sk,
        e.event_ts,
        e.event_date,
        e.payload
    FROM events e
    LEFT JOIN dim_users    u ON e.user_id    = u.user_id
    LEFT JOIN dim_products p ON e.product_id = p.product_id
    LEFT JOIN dim_date     d ON CAST(DATE_FORMAT(e.event_ts, '%Y%m%d') AS INTEGER) = d.date_sk
)

SELECT * FROM final
