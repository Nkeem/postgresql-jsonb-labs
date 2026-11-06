WITH expanded AS (
    SELECT DISTINCT s.id,
           s.data ->> 'country' AS country,
           btrim(x.sector) AS sector,
           s.data #>> '{raised_money,currency_label}' AS currency_label,
           (s.data #>> '{raised_money,amount}')::numeric AS amount
    FROM lab2.startups_json AS s
    CROSS JOIN LATERAL
         jsonb_array_elements_text(s.data -> 'sectors') AS x(sector)
    WHERE btrim(x.sector) <> ''
)
SELECT country, sector, currency_label,
       count(*) AS startups_count,
       count(amount) AS known_funding_count,
       sum(amount) AS total_reported_amount,
       round(avg(amount), 2) AS average_reported_amount
FROM expanded
GROUP BY country, sector, currency_label
HAVING count(*) >= 2
ORDER BY country, sector, currency_label NULLS LAST;
