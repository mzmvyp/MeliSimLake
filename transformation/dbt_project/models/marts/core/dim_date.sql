-- marts/core/dim_date.sql
-- Dimensão calendário 2020-2030 com flags BR

WITH date_spine AS (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2020-01-01' as date)",
        end_date="cast('2030-12-31' as date)"
    ) }}
),

feriados_nacionais AS (
    -- Feriados nacionais brasileiros fixos (dia/mês)
    SELECT day_of_month, month_of_year
    FROM (VALUES
        (1, 1),   -- Confraternização Universal
        (21, 4),  -- Tiradentes
        (1, 5),   -- Dia do Trabalho
        (7, 9),   -- Independência
        (12, 10), -- N. Sra. Aparecida
        (2, 11),  -- Finados
        (15, 11), -- Proclamação da República
        (25, 12)  -- Natal
    ) AS t(day_of_month, month_of_year)
),

final AS (
    SELECT
        CAST(DATE_FORMAT(date_day, '%Y%m%d') AS INTEGER)            AS date_sk,
        date_day                                                      AS full_date,
        YEAR(date_day)                                               AS year,
        MONTH(date_day)                                              AS month_of_year,
        DAY(date_day)                                                AS day_of_month,
        WEEK(date_day)                                               AS week_of_year,
        DAYOFWEEK(date_day)                                          AS day_of_week,
        DATE_FORMAT(date_day, '%A')                                  AS day_name,
        DATE_FORMAT(date_day, '%B')                                  AS month_name,
        QUARTER(date_day)                                            AS quarter,
        CASE WHEN DAYOFWEEK(date_day) IN (1, 7) THEN TRUE ELSE FALSE END AS is_weekend,
        -- Black Friday: última sexta de novembro
        CASE
            WHEN MONTH(date_day) = 11
             AND DAYOFWEEK(date_day) = 6
             AND DAY(date_day) BETWEEN 23 AND 29
            THEN TRUE
            ELSE FALSE
        END                                                          AS is_black_friday,
        -- Feriado nacional fixo
        CASE
            WHEN EXISTS (
                SELECT 1 FROM feriados_nacionais f
                WHERE f.day_of_month = DAY(date_day)
                  AND f.month_of_year = MONTH(date_day)
            ) THEN TRUE
            ELSE FALSE
        END                                                          AS is_national_holiday
    FROM date_spine
)

SELECT * FROM final
