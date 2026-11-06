# PostgreSQL JSONB Labs

[![Validate labs](https://github.com/Nkeem/postgresql-jsonb-labs/actions/workflows/validate.yml/badge.svg)](https://github.com/Nkeem/postgresql-jsonb-labs/actions/workflows/validate.yml)

Две лабораторные работы по дисциплине «Нереляционные базы данных»: преобразование
реляционных данных в JSONB и сбор HTML-данных с последующим анализом в PostgreSQL.

*Two database labs: relational-to-JSONB transformation, reproducible HTML extraction,
and SQL analytics with independent Python verification.*

**Стек:** PostgreSQL 18 · SQL / JSONB · Python 3.10+ · Docker Compose · GitHub Actions.

## Работы

| Работа | Задача | Результат | Материалы |
|---|---|---|---|
| **ЛР1 — Бронирования** | Собрать документы из нескольких таблиц и добавить заметки по часовым поясам аэропортов | 262 788 JSONB-документов, 18 799 отмеченных бронирований | [Описание и SQL](lab1/README.md) · [PDF](lab1/output/pdf/report.pdf) |
| **ЛР2 — Стартапы, вариант 14** | Извлечь карточки из HTML, очистить данные и выполнить пять SQL-запросов | 363 компании, 37 стран, 24 проверки | [Описание и SQL](lab2/README.md) · [PDF](lab2/output/pdf/report.pdf) |

## Что демонстрирует проект

- Создание JSONB-документов: `jsonb_build_object`, `jsonb_agg`, дедупликация и ограничения целостности.
- Обновление вложенных данных через `jsonb_set` с сохранением существующих заметок.
- Соединения таблиц, CTE, `LATERAL`, оконная функция `ROW_NUMBER` и агрегаты с `NULL`.
- Сравнение часовых поясов на дату рейса через `AT TIME ZONE`.
- Сбор HTML стандартной библиотекой Python, нормализация строк и стабильные идентификаторы.
- Проверка всех строк SQL-результатов независимым расчётом в Python и безопасный повторный запуск.

## Быстрый запуск

Нужны Git, Python 3.10+ и Docker с Compose v2. Сторонние Python-пакеты для запуска
работ и проверок не требуются. Команды выполняются из корня репозитория.

```sh
git clone https://github.com/Nkeem/postgresql-jsonb-labs.git
cd postgresql-jsonb-labs
docker compose up -d --wait
python scripts/prepare_demo.py
python scripts/run_labs.py --backend docker
python scripts/verify_labs.py --backend docker
```

`prepare_demo.py` скачивает официальный архив `demo-small` от 15.08.2017,
проверяет SHA-256 и убирает две несовместимые или лишние команды из SQL-дампа.
Архив и распакованный SQL остаются локальными и исключены из Git.
Первый запуск импортирует демобазу; последующие запуски сохраняют уже созданные документы.

Подключение из pgAdmin: `127.0.0.1:55432`, база `demo`, пользователь `postgres`,
учебный пароль `jsonb-labs-local`. Для своего пароля задайте `POSTGRES_PASSWORD`
перед первым запуском Compose. Для другого порта задайте `PGPORT`.
Остановить контейнер, сохранив данные: `docker compose down`.

Только вторая работа, без скачивания демобазы:

```sh
python scripts/run_labs.py --backend docker --lab 2
python scripts/verify_labs.py --backend docker --lab 2
```

Эти команды предназначены для отдельного учебного экземпляра PostgreSQL.
Если сначала запускалась только ЛР2, для ЛР1 используйте свежий экземпляр:
в уже существующую пустую `demo` демобаза автоматически не импортируется.

## PostgreSQL без Docker

Запустите отдельный сервер PostgreSQL 18 с кодировкой UTF-8 и сортировкой `C`
или `C.UTF-8`. Добавьте `psql` в `PATH`; на Windows также автоматически находится
`C:\Program Files\PostgreSQL\18\bin\psql.exe`.

```sh
python scripts/prepare_demo.py
python scripts/run_labs.py
python scripts/verify_labs.py
```

Настройки подключения берутся из `PGHOST` (по умолчанию `127.0.0.1`),
`PGPORT` (`55432`), `PGUSER` (`postgres`). При необходимости задайте `PGPASSWORD`
или настройте `.pgpass`; путь к клиенту можно задать через `PSQL`.
Скрипты работают с базой `demo`; для её первого создания нужны соответствующие права.

## Структура

```text
lab1/                  SQL-преобразование, проверки и PDF-отчёт
lab2/                  Парсер, JSON-данные, пять запросов и PDF-отчёт
  data/                Набор данных, JSON Schema и статистика сбора
  source/              HTML-снимки и manifest с URL, датами и SHA-256
  queries/             Отдельные файлы Q1–Q5 для pgAdmin
  results/             Сохранённые результаты и протокол проверок
scripts/               Подготовка демобазы, запуск и общая проверка
.github/workflows/     Проверка обеих работ на свежем PostgreSQL 18
compose.yaml           Отдельный учебный сервер
```

PDF-отчёты оформлены с нейтральными титульными листами. Скрипты `lab*/build_report.py` служат для
их повторной сборки на Windows: им нужны `reportlab`, `pypdf` и шрифты
Times New Roman / Consolas. Эти зависимости не нужны для SQL и парсера.

## Проверки и источники

CI импортирует демобазу, запускает обе работы, проверяет целостность JSON,
состав пассажиров и часовые пояса, повторяет импорт и сравнивает все пять
SQL-результатов ЛР2 с независимыми вычислениями в Python.
Проверки не перезаписывают сохранённые результаты.

Данные ЛР1 взяты из [демобазы Postgres Professional](https://postgrespro.ru/education/demodb).
Данные ЛР2 — учебный снимок [каталога Failory](https://www.failory.com/startups)
от 02.11.2026. Описание источников и ограничений: [DATA_SOURCES.md](DATA_SOURCES.md).
