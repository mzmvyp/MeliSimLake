-- staging/stg_users.sql
-- View sobre Silver users — apenas registros correntes

SELECT
    user_id,
    email,
    name,
    phone,
    document_type,
    document_number,
    birth_date,
    gender,
    status,
    created_at,
    updated_at,
    valid_from,
    row_hash
FROM {{ source('silver', 'users') }}
WHERE is_current = true
  AND user_id IS NOT NULL
