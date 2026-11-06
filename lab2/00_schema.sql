-- Run in the existing demo database. The lab1 tables are not modified.
CREATE SCHEMA IF NOT EXISTS lab2;
CREATE TABLE IF NOT EXISTS lab2.startups_json (
    id text PRIMARY KEY,
    data jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(data) = 'object'),
    CHECK (data ?& ARRAY['id','name','founded_year','foundation_date',
        'foundation_precision','country','website','sectors','founders',
        'raised_money','source_urls','retrieved_at']),
    CHECK ((data ->> 'id') IS NOT DISTINCT FROM id),
    CHECK (jsonb_typeof(data -> 'name') = 'string'),
    CHECK (length(btrim(data ->> 'name')) > 0),
    CHECK (jsonb_typeof(data -> 'sectors') = 'array'),
    CHECK (jsonb_typeof(data -> 'founders') = 'array'),
    CHECK (jsonb_typeof(data -> 'raised_money') = 'object'),
    CHECK ((data -> 'raised_money') ?& ARRAY['amount','currency_label','raw']),
    CHECK (jsonb_typeof(data #> '{raised_money,amount}') IN ('number','null')),
    CHECK ((data #>> '{raised_money,amount}')::numeric >= 0)
);
