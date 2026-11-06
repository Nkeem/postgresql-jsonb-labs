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
