-- staging/stg_orders.sql

SELECT
    order_id,
    user_id,
    status,
    CAST(total_amount AS DOUBLE) AS total_amount,
    currency,
    payment_method,
    shipping_address_id,
    created_at,
    updated_at,
    completed_at,
    items_count
FROM {{ source('silver', 'orders') }}
WHERE order_id IS NOT NULL
