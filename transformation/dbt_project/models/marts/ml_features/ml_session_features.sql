-- marts/ml_features/ml_session_features.sql
-- Features de sessão para GRU4Rec / SASRec

WITH sessions AS (
    SELECT * FROM {{ ref('fact_sessions') }}
),

final AS (
    SELECT
        session_id,
        user_id,
        session_start,
        CURRENT_TIMESTAMP                       AS feature_timestamp,
        duration_seconds,
        event_count,
        distinct_products_viewed,
        cart_actions,
        converted,
        product_sequence,
        ARRAY_LENGTH(product_sequence)          AS sequence_length,
        HOUR(session_start)                     AS start_hour,
        DAYOFWEEK(session_start)                AS start_day_of_week
    FROM sessions
    WHERE ARRAY_LENGTH(product_sequence) >= 2   -- mínimo para treino sequencial
)

SELECT * FROM final
