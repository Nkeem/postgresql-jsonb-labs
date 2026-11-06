SELECT data ->> 'name' AS name,
       (data ->> 'founded_year')::integer AS founded_year,
       data ->> 'country' AS country,
       data ->> 'website' AS website
FROM lab2.startups_json
WHERE data ->> 'country' = 'India'
  AND (data ->> 'founded_year')::integer >= 2015
ORDER BY founded_year DESC, name, id;
