-- staging/stg_events.sql

SELECT
    event_id,
    event_type,
    user_id,
    session_id,
    product_id,
    payload,
    ts          AS event_ts,
    event_date
FROM {{ source('silver', 'events') }}
WHERE event_id IS NOT NULL
  AND ts IS NOT NULL
