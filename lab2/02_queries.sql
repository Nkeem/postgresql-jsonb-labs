-- Three simple and two advanced queries. All are read-only.

-- Q1 (simple): total documents, missing founders, missing funding.
SELECT count(*) AS total_startups,
       count(*) FILTER (WHERE jsonb_array_length(data -> 'founders') = 0)
           AS founders_unknown,
       count(*) FILTER (WHERE data #>> '{raised_money,amount}' IS NULL)
           AS funding_unknown
FROM lab2.startups_json;

-- Q2 (simple): companies with headquarters in India, founded since 2015.
SELECT data ->> 'name' AS name,
       (data ->> 'founded_year')::integer AS founded_year,
       data ->> 'country' AS country,
       data ->> 'website' AS website
FROM lab2.startups_json
WHERE data ->> 'country' = 'India'
  AND (data ->> 'founded_year')::integer >= 2015
ORDER BY founded_year DESC, name, id;

-- Q3 (simple): exact AI tag, not a substring of another tag.
SELECT data ->> 'name' AS name,
       data ->> 'country' AS country,
       data -> 'sectors' AS sectors
FROM lab2.startups_json
WHERE (data -> 'sectors') ? 'AI'
ORDER BY name, id;

-- Q4 (advanced): statistics by country, sector and displayed currency label.
-- Duplicate sectors within a company are removed before aggregation.
-- A company may belong to several sectors: do not sum sector totals together.
-- $ stays $, not an assumed USD. No currency conversion is performed.
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

-- Q5 (advanced): at most three companies per country/currency-label group.
-- Unknown amounts are excluded; ties are resolved by name and stable id.
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
