-- marts/core/dim_users.sql
-- Dimensão usuários — chave surrogate + atributos correntes

WITH source AS (
    SELECT * FROM {{ ref('stg_users') }}
),

final AS (
    SELECT
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['user_id']) }} AS user_sk,
        user_id,
        email,
        name,
        phone,
        document_type,
        CASE
            WHEN gender = 'F' THEN 'Feminino'
            WHEN gender = 'M' THEN 'Masculino'
            WHEN gender = 'NB' THEN 'Não-binário'
            ELSE 'Não informado'
        END                                                  AS gender,
        status,
        CAST(birth_date AS DATE)                             AS birth_date,
        DATE_DIFF('year', CAST(birth_date AS DATE), CURRENT_DATE) AS age,
        created_at,
        updated_at,
        valid_from                                           AS scd_valid_from,
        row_hash
    FROM source
)

SELECT * FROM final
