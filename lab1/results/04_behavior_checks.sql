-- Техническая проверка с откатом: итоговая база не меняется.
BEGIN;

CREATE TEMP TABLE before_test AS
SELECT booking_id, data
FROM bookings.bookings_json
WHERE booking_id IN ('00000F', '000012');

-- У подходящей брони имитируем ранее записанный комментарий.
UPDATE bookings.bookings_json
SET data = jsonb_set(data, '{notes}', to_jsonb('Ранее записанный комментарий'::text))
WHERE booking_id = '00000F';

-- У неподходящей брони заметка также должна остаться без изменений.
UPDATE bookings.bookings_json
SET data = jsonb_set(data, '{notes}', to_jsonb('Обычная заметка'::text))
WHERE booking_id = '000012';

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


-- После первого обновления ожидаем один новый комментарий,
-- после второго — ни одного (это видно по строкам UPDATE в журнале).
SELECT data ->> 'notes' =
       E'Ранее записанный комментарий\nБронирование содержит рейс в/из аэропорта с разницей во времени относительно Москвы более 6 часов.'
       AS old_note_preserved_and_no_duplicate
FROM bookings.bookings_json WHERE booking_id = '00000F';

SELECT data ->> 'notes' = 'Обычная заметка' AS unrelated_note_preserved
FROM bookings.bookings_json WHERE booking_id = '000012';

SELECT bool_and((bj.data - 'notes') = (b.data - 'notes')) AS other_json_fields_preserved
FROM bookings.bookings_json AS bj JOIN before_test AS b USING (booking_id);

-- Turn the original demonstration checks into assertions for local runs and CI.
DO $checks$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM bookings.bookings_json
        WHERE booking_id = '00000F'
          AND data ->> 'notes' = E'Ранее записанный комментарий\nБронирование содержит рейс в/из аэропорта с разницей во времени относительно Москвы более 6 часов.'
    ) THEN
        RAISE EXCEPTION 'Existing note was lost or the added note was duplicated';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM bookings.bookings_json
        WHERE booking_id = '000012' AND data ->> 'notes' = 'Обычная заметка'
    ) THEN
        RAISE EXCEPTION 'An unrelated booking note was changed';
    END IF;
    IF EXISTS (
        SELECT 1 FROM bookings.bookings_json AS bj JOIN before_test AS b USING (booking_id)
        WHERE (bj.data - 'notes') IS DISTINCT FROM (b.data - 'notes')
    ) THEN
        RAISE EXCEPTION 'A JSON field other than notes was changed';
    END IF;
END
$checks$;

ROLLBACK;
