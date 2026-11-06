SELECT data ->> 'name' AS name,
       data ->> 'country' AS country,
       data -> 'sectors' AS sectors
FROM lab2.startups_json
WHERE (data -> 'sectors') ? 'AI'
ORDER BY name, id;
