-- marts/analytics/customer_rfm.sql
-- RFM: Recency, Frequency, Monetary por usuário

WITH orders AS (
    SELECT * FROM {{ ref('fact_orders') }}
    WHERE is_completed = TRUE
),

rfm_raw AS (
    SELECT
        user_id,
        DATE_DIFF('day', MAX(CAST(created_at AS DATE)), CURRENT_DATE) AS recency_days,
        COUNT(DISTINCT order_id)                                        AS frequency,
        SUM(total_amount)                                               AS monetary
    FROM orders
    GROUP BY user_id
),

rfm_scores AS (
    SELECT
        user_id,
        recency_days,
        frequency,
        monetary,
        -- Score 1-5: menor recência = score maior
        NTILE(5) OVER (ORDER BY recency_days DESC)  AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC)      AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC)       AS m_score
    FROM rfm_raw
),

final AS (
    SELECT
        user_id,
        recency_days,
        frequency,
        monetary,
        r_score,
        f_score,
        m_score,
        (r_score + f_score + m_score)           AS rfm_total,
        CONCAT(CAST(r_score AS VARCHAR),
               CAST(f_score AS VARCHAR),
               CAST(m_score AS VARCHAR))        AS rfm_cell,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score < 2  THEN 'Recent Customers'
            WHEN r_score < 2 AND f_score >= 3  THEN 'At Risk'
            WHEN r_score < 2 AND f_score < 2   THEN 'Lost'
            ELSE 'Potential Loyalists'
        END                                     AS rfm_segment
    FROM rfm_scores
)

SELECT * FROM final
