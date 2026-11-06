-- Лабораторная №1. Выполнять в базе demo версии от 15.08.2017.
-- Этап 1: таблица и JSON-документ для каждого бронирования.
BEGIN;

CREATE TABLE IF NOT EXISTS bookings.bookings_json (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    booking_id char(6) NOT NULL UNIQUE
               REFERENCES bookings.bookings(book_ref),
    data       jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(data) = 'object'),
    CHECK (data ?& ARRAY['booking_number', 'status', 'passengers']),
    CHECK (jsonb_typeof(data -> 'passengers') = 'array')
);

-- Один пассажир может иметь несколько билетов: сначала убираем повторы.
WITH unique_passengers AS (
    SELECT DISTINCT book_ref, passenger_id, passenger_name
    FROM bookings.tickets
), passenger_lists AS (
    SELECT book_ref,
           jsonb_agg(
               jsonb_build_object('id', passenger_id, 'name', passenger_name)
               ORDER BY passenger_id, passenger_name
           ) AS passengers
    FROM unique_passengers
    GROUP BY book_ref
)
INSERT INTO bookings.bookings_json (booking_id, data)
SELECT b.book_ref,
       jsonb_build_object(
           'booking_number', b.book_ref,
           -- Условный статус: в исходной таблице статуса брони нет.
           'status', 'confirmed',
           'passengers', COALESCE(p.passengers, '[]'::jsonb),
           'notes', ''
       )
FROM bookings.bookings AS b
LEFT JOIN passenger_lists AS p ON p.book_ref = b.book_ref
-- Повторный запуск сохраняет уже созданные документы и их notes.
ON CONFLICT (booking_id) DO NOTHING;

COMMIT;

SELECT (SELECT count(*) FROM bookings.bookings) AS source_bookings,
       count(*) AS json_bookings
FROM bookings.bookings_json;

SELECT booking_id, jsonb_pretty(data) AS booking_json
FROM bookings.bookings_json
ORDER BY booking_id
LIMIT 2;


-- Этап 2: добавить комментарий для рейсов в/из аэропортов,
-- отличающихся от Москвы СТРОГО больше чем на 6 часов.
BEGIN;

WITH comment_text AS (
    SELECT 'Бронирование содержит рейс в/из аэропорта с разницей во времени относительно Москвы более 6 часов.'::text AS note
), affected_bookings AS (
    SELECT DISTINCT t.book_ref
    FROM bookings.tickets AS t
    JOIN bookings.ticket_flights AS tf ON tf.ticket_no = t.ticket_no
    JOIN bookings.flights AS f ON f.flight_id = tf.flight_id
    JOIN bookings.airports_data AS dep ON dep.airport_code = f.departure_airport
    JOIN bookings.airports_data AS arr ON arr.airport_code = f.arrival_airport
    WHERE
        -- Время одного и того же момента в двух поясах, на дату вылета.
        abs(extract(epoch FROM (
            (f.scheduled_departure AT TIME ZONE dep.timezone) -
            (f.scheduled_departure AT TIME ZONE 'Europe/Moscow')
        )) / 3600) > 6
        OR
        -- Для прилёта используем дату и время прилёта.
        abs(extract(epoch FROM (
            (f.scheduled_arrival AT TIME ZONE arr.timezone) -
            (f.scheduled_arrival AT TIME ZONE 'Europe/Moscow')
        )) / 3600) > 6
)
UPDATE bookings.bookings_json AS bj
SET data = jsonb_set(
    bj.data,
    '{notes}',
    to_jsonb(concat_ws(E'\n', NULLIF(bj.data ->> 'notes', ''), c.note)),
    true
)
FROM affected_bookings AS ab
CROSS JOIN comment_text AS c
WHERE bj.booking_id = ab.book_ref
  -- Не добавляем ту же фразу ещё раз при повторном запуске.
  AND position(c.note IN COALESCE(bj.data ->> 'notes', '')) = 0;

COMMIT;

SELECT count(*) AS bookings_with_comment
FROM bookings.bookings_json
WHERE position(
    'Бронирование содержит рейс в/из аэропорта с разницей во времени относительно Москвы более 6 часов.'
    IN COALESCE(data ->> 'notes', '')
) > 0;

SELECT booking_id, data ->> 'notes' AS notes
FROM bookings.bookings_json
WHERE COALESCE(data ->> 'notes', '') <> ''
ORDER BY booking_id
LIMIT 5;


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
