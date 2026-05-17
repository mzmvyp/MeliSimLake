-- marts/core/dim_products.sql

WITH source AS (
    SELECT * FROM {{ ref('stg_products') }}
),

final AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['product_id']) }} AS product_sk,
        product_id,
        title,
        description,
        category_id,
        brand,
        sku,
        price,
        stock_quantity,
        CASE
            WHEN stock_quantity > 0 THEN 'in_stock'
            ELSE 'out_of_stock'
        END AS stock_status,
        status,
        created_at,
        updated_at,
        valid_from AS scd_valid_from,
        row_hash
    FROM source
)

SELECT * FROM final
