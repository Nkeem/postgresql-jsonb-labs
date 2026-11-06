SELECT count(*) AS total_startups,
       count(*) FILTER (WHERE jsonb_array_length(data -> 'founders') = 0)
           AS founders_unknown,
       count(*) FILTER (WHERE data #>> '{raised_money,amount}' IS NULL)
           AS funding_unknown
FROM lab2.startups_json;
