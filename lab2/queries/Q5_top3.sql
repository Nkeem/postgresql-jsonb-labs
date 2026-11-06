WITH amounts AS (
    SELECT id, data ->> 'name' AS name,
           data ->> 'country' AS country,
           data #>> '{raised_money,currency_label}' AS currency_label,
           (data #>> '{raised_money,amount}')::numeric AS amount
    FROM lab2.startups_json
    WHERE data #>> '{raised_money,amount}' IS NOT NULL
      AND data #>> '{raised_money,currency_label}' IS NOT NULL
), ranked AS (
    SELECT *, row_number() OVER (
        PARTITION BY country, currency_label
        ORDER BY amount DESC, name, id
    ) AS funding_rank
    FROM amounts
)
SELECT country, currency_label, funding_rank, name, amount
FROM ranked
WHERE funding_rank <= 3
ORDER BY country, currency_label, funding_rank, name, id;
