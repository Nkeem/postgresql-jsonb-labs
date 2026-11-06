-- Этап 3: проверочные SELECT, данные не изменяются.
SET bookings.lang = 'ru';

-- Число документов должно совпасть с числом исходных броней.
SELECT (SELECT count(*) FROM bookings.bookings) AS source_bookings,
       count(*) AS json_bookings,
       count(*) FILTER (WHERE COALESCE(data ->> 'notes', '') <> '') AS with_notes
FROM bookings.bookings_json;

-- Обязательные поля, типы и номер брони. Ожидается 0.
SELECT count(*) AS invalid_documents
FROM bookings.bookings_json
WHERE NOT (data ?& ARRAY['booking_number', 'status', 'passengers'])
   OR jsonb_typeof(data -> 'booking_number') IS DISTINCT FROM 'string'
   OR data ->> 'booking_number' IS DISTINCT FROM booking_id::text
   OR jsonb_typeof(data -> 'status') IS DISTINCT FROM 'string'
   OR jsonb_typeof(data -> 'passengers') IS DISTINCT FROM 'array';

-- Состав пассажиров сравниваем с исходной таблицей в обоих направлениях.
-- Ожидается 0: ни пропущенных, ни выдуманных пассажиров.
WITH source_passengers AS (
    SELECT DISTINCT book_ref::text AS booking_id, passenger_id, passenger_name
    FROM bookings.tickets
), json_passengers AS (
    SELECT bj.booking_id::text AS booking_id,
           p ->> 'id' AS passenger_id, p ->> 'name' AS passenger_name
    FROM bookings.bookings_json AS bj
    CROSS JOIN LATERAL jsonb_array_elements(bj.data -> 'passengers') AS p
), differences AS (
    (SELECT * FROM source_passengers EXCEPT SELECT * FROM json_passengers)
    UNION ALL
    (SELECT * FROM json_passengers EXCEPT SELECT * FROM source_passengers)
)
SELECT count(*) AS passenger_differences FROM differences;

-- Независимо проверяем рейсы: превращаем вылет и прилёт в строки.
-- Здесь сравниваем интервалы напрямую, без перевода в часы.
WITH qualifying_flights AS (
    SELECT DISTINCT f.flight_id
    FROM bookings.flights AS f
    CROSS JOIN LATERAL (
        VALUES (f.departure_airport, f.scheduled_departure),
               (f.arrival_airport, f.scheduled_arrival)
    ) AS endpoint(airport_code, flight_time)
    JOIN bookings.airports_data AS a ON a.airport_code = endpoint.airport_code
    WHERE (endpoint.flight_time AT TIME ZONE a.timezone) -
          (endpoint.flight_time AT TIME ZONE 'Europe/Moscow') > interval '6 hours'
       OR (endpoint.flight_time AT TIME ZONE a.timezone) -
          (endpoint.flight_time AT TIME ZONE 'Europe/Moscow') < interval '-6 hours'
), expected AS (
    SELECT DISTINCT t.book_ref
    FROM bookings.tickets AS t
    JOIN bookings.ticket_flights AS tf ON tf.ticket_no = t.ticket_no
    JOIN qualifying_flights AS q ON q.flight_id = tf.flight_id
), actual AS (
    SELECT booking_id
    FROM bookings.bookings_json
    WHERE position(
        'Бронирование содержит рейс в/из аэропорта с разницей во времени относительно Москвы более 6 часов.'
        IN COALESCE(data ->> 'notes', '')
    ) > 0
)
SELECT (SELECT count(*) FROM expected) AS expected_comments,
       (SELECT count(*) FROM actual) AS actual_comments,
       (SELECT count(*) FROM (SELECT book_ref FROM expected
                              EXCEPT SELECT booking_id FROM actual) AS missing) AS missing_comments,
       (SELECT count(*) FROM (SELECT booking_id FROM actual
                              EXCEPT SELECT book_ref FROM expected) AS extra) AS extra_comments;

-- Граничные случаи: ровно 6 не подходит, 7 и 9 подходят.
WITH examples(zone, expected_hours, expected_match) AS (
    VALUES ('Asia/Tokyo', 6, false),
           ('Asia/Vladivostok', 7, true),
           ('Asia/Kamchatka', 9, true),
           ('America/Los_Angeles', 10, true)
), calculated AS (
    SELECT *, abs(extract(epoch FROM (
        (timestamptz '2017-08-15 12:00:00+00' AT TIME ZONE zone) -
        (timestamptz '2017-08-15 12:00:00+00' AT TIME ZONE 'Europe/Moscow')
    )) / 3600) AS difference_hours
    FROM examples
)
SELECT zone, difference_hours, difference_hours > 6 AS matches,
       difference_hours = expected_hours AND
       (difference_hours > 6) = expected_match AS passed
FROM calculated;

-- Пары рейс–аэропорт с разницей больше 6 часов в реальных данных.
WITH endpoints AS (
    SELECT f.flight_id, e.airport_code, e.flight_time
    FROM bookings.flights AS f
    CROSS JOIN LATERAL (
        VALUES (f.departure_airport, f.scheduled_departure),
               (f.arrival_airport, f.scheduled_arrival)
    ) AS e(airport_code, flight_time)
)
SELECT DISTINCT a.airport_code, a.city, a.timezone,
       abs(extract(epoch FROM (
           (e.flight_time AT TIME ZONE a.timezone) -
           (e.flight_time AT TIME ZONE 'Europe/Moscow')
       )) / 3600) AS difference_hours
FROM endpoints AS e
JOIN bookings.airports AS a ON a.airport_code = e.airport_code
WHERE abs(extract(epoch FROM (
    (e.flight_time AT TIME ZONE a.timezone) -
    (e.flight_time AT TIME ZONE 'Europe/Moscow')
)) / 3600) > 6
ORDER BY difference_hours, a.airport_code;

SELECT booking_id, jsonb_pretty(data) AS booking_json
FROM bookings.bookings_json
WHERE COALESCE(data ->> 'notes', '') <> ''
ORDER BY booking_id
LIMIT 2;
