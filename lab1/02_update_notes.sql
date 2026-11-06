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
