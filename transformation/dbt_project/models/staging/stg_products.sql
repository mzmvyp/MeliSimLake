-- staging/stg_products.sql

SELECT
    product_id,
    title,
    description,
    category_id,
    brand,
    sku,
    price,
    stock_quantity,
    status,
    created_at,
    updated_at,
    valid_from,
    row_hash
FROM {{ source('silver', 'products') }}
WHERE is_current = true
  AND product_id IS NOT NULL
