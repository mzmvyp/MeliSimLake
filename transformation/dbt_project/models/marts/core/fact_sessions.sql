-- marts/core/fact_sessions.sql
-- Fato sessões — sessionização por user_id com gap de 30 minutos

WITH events AS (
    SELECT * FROM {{ ref('stg_events') }}
),

with_prev AS (
    SELECT
        event_id,
        user_id,
        session_id                                      AS raw_session_id,
        event_ts,
        event_type,
        product_id,
        LAG(event_ts) OVER (PARTITION BY user_id ORDER BY event_ts) AS prev_event_ts
    FROM events
    WHERE user_id IS NOT NULL
),

with_new_session_flag AS (
    SELECT
        *,
        CASE
            WHEN prev_event_ts IS NULL THEN 1
            WHEN DATE_DIFF('minute', prev_event_ts, event_ts) > 30 THEN 1
            ELSE 0
        END AS is_new_session
    FROM with_prev
),

with_session_num AS (
    SELECT
        *,
        SUM(is_new_session) OVER (PARTITION BY user_id ORDER BY event_ts) AS session_num
    FROM with_new_session_flag
),

session_agg AS (
    SELECT
        user_id,
        session_num,
        COALESCE(MIN(raw_session_id), CONCAT(user_id, '_', CAST(session_num AS VARCHAR))) AS session_id,
        MIN(event_ts)                                   AS session_start,
        MAX(event_ts)                                   AS session_end,
        COUNT(*)                                        AS event_count,
        COUNT(DISTINCT product_id)                      AS distinct_products_viewed,
        SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS purchases,
        SUM(CASE WHEN event_type = 'cart'     THEN 1 ELSE 0 END) AS cart_actions,
        ARRAY_AGG(product_id ORDER BY event_ts)        AS product_sequence
    FROM with_session_num
    GROUP BY user_id, session_num
),

final AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['session_id']) }} AS session_sk,
        session_id,
        user_id,
        session_start,
        session_end,
        DATE_DIFF('second', session_start, session_end) AS duration_seconds,
        event_count,
        distinct_products_viewed,
        purchases,
        cart_actions,
        CASE WHEN purchases > 0 THEN TRUE ELSE FALSE END AS converted,
        product_sequence
    FROM session_agg
)

SELECT * FROM final
