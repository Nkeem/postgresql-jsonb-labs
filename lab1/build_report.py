from pathlib import Path
import json
import textwrap
from xml.sax.saxutils import escape

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'pdf'
TMP = ROOT / 'tmp' / 'pdfs'
OUT.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)
DEST = OUT / 'report.pdf'

for family, filename in [('TimesRU', 'times.ttf'), ('TimesRUB', 'timesbd.ttf'),
                         ('TimesRUI', 'timesi.ttf'), ('CodeRU', 'consola.ttf')]:
    pdfmetrics.registerFont(TTFont(family, str(Path('C:/Windows/Fonts') / filename)))
pdfmetrics.registerFontFamily('TimesRU', normal='TimesRU', bold='TimesRUB', italic='TimesRUI')

W, H = A4
LEFT, RIGHT, TOP, BOTTOM = 76, 43, 52, 52
WIDTH = W - LEFT - RIGHT
BODY = ParagraphStyle('body', fontName='TimesRU', fontSize=12,
                      leading=17, alignment=TA_JUSTIFY, spaceAfter=8)
SMALL = ParagraphStyle('small', parent=BODY, fontSize=10.5, leading=14, alignment=TA_LEFT)
HEADING = ParagraphStyle('heading', parent=BODY, fontName='TimesRUB', fontSize=14,
                         leading=18, alignment=TA_LEFT, spaceAfter=12)
SUB = ParagraphStyle('sub', parent=BODY, fontName='TimesRUB', fontSize=12,
                     leading=16, alignment=TA_LEFT, spaceAfter=7)
CELL = ParagraphStyle('cell', parent=SMALL, fontSize=10.6, leading=13)
CELL_HEAD = ParagraphStyle('cellhead', parent=CELL, fontName='TimesRUB')

c = canvas.Canvas(str(DEST), pagesize=A4, pageCompression=1)
c.setTitle('Отчет к работе 1. JSONB в PostgreSQL')
c.setAuthor('')
c.setCreator('ReportLab')
c.setSubject('Нереляционные базы данных. Создание JSONB-документов и обновление notes')
page = 1
y = H - TOP
page_info = []

def paragraph(text, style=BODY, x=LEFT, width=WIDTH, after=None):
    global y
    p = Paragraph(text, style)
    _, height = p.wrap(width, H)
    if y - height < BOTTOM:
        raise RuntimeError(f'Overflow page {page}: {text[:90]} at y={y}, height={height}')
    p.drawOn(c, x, y - height)
    y -= height + (style.spaceAfter if after is None else after)

def title(text):
    paragraph(text, HEADING)

def sub(text):
    paragraph(text, SUB)

def gap(points=6):
    global y
    y -= points

def table(headers, rows, widths):
    global y
    data = [[Paragraph(escape(str(v)), CELL_HEAD) for v in headers]]
    data += [[Paragraph(escape(str(v)), CELL) for v in row] for row in rows]
    t = Table(data, colWidths=widths, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
        ('GRID', (0, 0), (-1, -1), .45, colors.HexColor('#666666')),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    _, ht = t.wrap(WIDTH, H)
    if y - ht < BOTTOM:
        raise RuntimeError(f'Table overflow page {page}, height={ht}, y={y}')
    t.drawOn(c, LEFT, y - ht)
    y -= ht + 12

def wrap_code(text, size, width=WIDTH-16):
    # Preserve source characters; wraps in the PDF are only visual.
    text = text.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    lines = []
    for line in text.replace('\t', '    ').splitlines():
        if not line:
            lines.append('')
            continue
        current = line
        while pdfmetrics.stringWidth(current, 'CodeRU', size) > width:
            n = len(current)
            while pdfmetrics.stringWidth(current[:n], 'CodeRU', size) > width:
                n -= 1
            split_at = current.rfind(' ', 0, n+1)
            if split_at <= len(current) - len(current.lstrip()) + 5:
                split_at = n
                lines.append(current[:split_at])
                current = '    ' + current[split_at:]
            else:
                lines.append(current[:split_at])
                current = '    ' + current[split_at+1:]
        lines.append(current)
    return lines

def code_lines(lines, size=9, leading=11, numbers=None):
    global y
    height = len(lines) * leading + 14
    if y-height < BOTTOM:
        raise RuntimeError(f'Code overflow page {page}: {len(lines)} lines at y={y}')
    c.setFillColor(colors.HexColor('#f6f6f6'))
    c.rect(LEFT, y-height, WIDTH, height, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont('CodeRU', size)
    for i, line in enumerate(lines):
        c.drawString(LEFT+8, y-10-size-i*leading, line)
    y -= height + 10

def code(text, size=9, leading=11):
    code_lines(wrap_code(text, size), size, leading)

def end_page():
    global page, y
    page_info.append({'page': page, 'bottom_used': round(y, 1)})
    if page > 1:
        c.setFont('TimesRU', 11)
        c.drawCentredString(W/2, 28, str(page))
    c.showPage()
    page += 1
    y = H-TOP

def at_center(text, top, size=12, bold=False, width=WIDTH):
    sty = ParagraphStyle('cover', fontName='TimesRUB' if bold else 'TimesRU',
                         fontSize=size, leading=size*1.22, alignment=TA_CENTER)
    p = Paragraph(text, sty)
    _, ht = p.wrap(width, H)
    p.drawOn(c, LEFT+(WIDTH-width)/2, H-top-ht)

# Neutral cover for the public report.
at_center('POSTGRESQL / JSONB', 120, 11)
at_center('ОТЧЕТ К РАБОТЕ № 1', 245, 22, True)
at_center('Создание и изменение<br/>JSONB-документов', 313, 18)
at_center('Бронирования авиаперевозок', 405, 13)
at_center('Реляционные данные, JSONB и часовые пояса', 439, 11)
c.setFont('TimesRU', 11)
c.drawCentredString(LEFT+WIDTH/2, 58, '2026')
end_page()

title('1. Цель и постановка задачи')
paragraph('Цель работы - освоить создание, чтение и изменение JSONB-документов '
          'средствами SQL в PostgreSQL на основе реляционных данных базы «Авиаперевозки».')
sub('Общее задание')
paragraph('Создать таблицу bookings_json с первичным ключом id, внешним ключом '
          'booking_id, полем data типа JSONB и временем создания created_at. '
          'Для каждого бронирования сформировать документ с обязательными полями '
          'booking_number, status и массивом passengers с полями id и name. '
          'Номер брони и сведения о пассажирах получить из исходной базы.')
sub('Индивидуальное задание')
paragraph('Для броней, содержащих рейсы в/из аэропортов, часовой пояс которых '
          'отличается от московского более чем на 6 часов, добавить комментарий в notes. '
          'Проверяются оба аэропорта каждого рейса. Достаточно одного подходящего рейса '
          'в бронировании; разница ровно 6 часов условию не соответствует.')
sub('Средства и исходные данные')
paragraph('Использованы PostgreSQL 18, SQL, утилита psql для загрузки и выполнения '
          'скриптов и pgAdmin 4 для просмотра результатов. Источник - официальная '
          'демобаза demo-small от 15.08.2017 [1]. База загружена из SQL-дампа; '
          'исходные таблицы не изменялись. В копии дампа исключены команда удаления '
          'базы и устаревшая настройка default_with_oids.')
table(['Исходная таблица', 'Назначение'], [
    ['bookings', 'Номер бронирования book_ref'],
    ['tickets', 'Связь с бронью, passenger_id и passenger_name'],
    ['ticket_flights', 'Связь билета ticket_no с рейсом flight_id'],
    ['flights', 'Аэропорты и плановое время вылета и прилета'],
    ['airports_data', 'Код аэропорта и его часовой пояс timezone'],
], [135, WIDTH-135])
paragraph('Все исходные таблицы находятся в схеме bookings базы demo. '
          'Каждая строка новой таблицы соответствует одному бронированию.', SMALL)
end_page()

title('2. Создание и заполнение JSON-документов')
paragraph('Первый этап реализован файлом 01_create_and_fill.sql '
          '(полный текст приведен в приложении А).')
table(['Поле новой таблицы', 'Тип и ограничения'], [
    ['id', 'bigint; автоматически формируемый первичный ключ'],
    ['booking_id', 'char(6); NOT NULL, UNIQUE; ссылка на bookings.book_ref'],
    ['data', 'jsonb; NOT NULL; объект с обязательными ключами'],
    ['created_at', 'timestamptz; по умолчанию CURRENT_TIMESTAMP'],
], [135, WIDTH-135])
paragraph('Ограничения CHECK проверяют, что data является объектом, содержит '
          'booking_number, status и passengers, а passengers имеет тип массива. '
          'Уникальность booking_id обеспечивает один документ на бронь.')
paragraph('Сначала SELECT DISTINCT получает уникальные сочетания номера брони, '
          'идентификатора и имени пассажира из tickets. Затем jsonb_build_object '
          'создает объект пассажира, а jsonb_agg собирает такие объекты в массив '
          'для каждой группы book_ref. Порядок элементов задается ORDER BY.')
code("jsonb_agg(\n"
     "    jsonb_build_object('id', passenger_id,\n"
     "                       'name', passenger_name)\n"
     "    ORDER BY passenger_id, passenger_name\n"
     ") AS passengers", 9.5, 12)
paragraph('Бронирования соединяются с массивами пассажиров через LEFT JOIN. '
          'Функция jsonb_build_object формирует итоговый документ; COALESCE '
          'подставляет пустой массив при отсутствии пассажиров. Номер брони '
          'сохраняется и во внешнем ключе, и внутри JSON.')
code("jsonb_build_object(\n"
     "    'booking_number', b.book_ref,\n"
     "    'status', 'confirmed',\n"
     "    'passengers', COALESCE(p.passengers, '[]'::jsonb),\n"
     "    'notes', ''\n"
     ")", 9.5, 12)
paragraph('Статус confirmed задан условно, поскольку исходная таблица бронирований '
          'не содержит статуса; это допускается заданием. notes первоначально пуст. '
          'ON CONFLICT (booking_id) DO NOTHING сохраняет существующие документы '
          'при повторном запуске. Получено 262 788 JSON-документов.')
end_page()

title('3. Выполнение индивидуального задания')
paragraph('Обновление реализовано файлом 02_update_notes.sql (приложение Б). '
          'Через JOIN строится цепочка tickets → ticket_flights → flights → '
          'airports_data. Таблица аэропортов присоединяется дважды: для вылета '
          '(dep) и прилета (arr). SELECT DISTINCT оставляет уникальные номера броней.')
paragraph('Для вылета вычисляется разница местного времени аэропорта и московского '
          'в один и тот же момент scheduled_departure. Аналогичная проверка прилета '
          'использует scheduled_arrival. Это учитывает смещение пояса на дату рейса.')
code("abs(extract(epoch FROM (\n"
     "    (f.scheduled_departure AT TIME ZONE dep.timezone) -\n"
     "    (f.scheduled_departure AT TIME ZONE 'Europe/Moscow')\n"
     ")) / 3600) > 6", 9.4, 12)
paragraph('EXTRACT(EPOCH FROM ...) переводит интервал в секунды, деление на 3600 '
          'дает часы, ABS учитывает опережение и отставание. Проверки вылета и '
          'прилета соединены через OR. Аэропорты не сравниваются друг с другом: '
          'каждый из них сравнивается с Москвой.')
paragraph('UPDATE находит соответствующий документ по booking_id = book_ref. '
          'Функция jsonb_set изменяет только ключ notes. Старый текст сохраняется '
          'и объединяется с новым комментарием через перевод строки. Проверка '
          'POSITION предотвращает повторное добавление той же фразы.')
table(['Аэропорт', 'Город', 'Разница, ч'], [
    ['KHV', 'Хабаровск', '7'],
    ['KXK', 'Комсомольск-на-Амуре', '7'],
    ['VVO', 'Владивосток', '7'],
    ['GDX', 'Магадан', '8'],
    ['UUS', 'Южно-Сахалинск', '8'],
    ['DYR', 'Анадырь', '9'],
    ['PKC', 'Петропавловск-Камчатский', '9'],
], [70, WIDTH-160, 90])
paragraph('В реальных рейсах демобазы условию соответствуют перечисленные '
          'аэропорты. Комментарий добавлен к 18 799 бронированиям. Например, '
          'бронь 00000F содержит рейсы Москва - Южно-Сахалинск и обратно; '
          'разница относительно Москвы составляет 8 часов.')
end_page()

title('4. Запросы для демонстрации результата')
paragraph('После выполнения двух SQL-файлов итоговая таблица просматривается '
          'тремя самостоятельными запросами.')
sub('Общее количество JSON-документов')
code('SELECT count(*) AS total_bookings\nFROM bookings.bookings_json;', 9.5, 12)
paragraph('Результат: 262 788. COUNT(*) подсчитывает строки таблицы; каждая строка '
          'содержит один JSON-документ.')
sub('Количество документов с непустой заметкой')
code("SELECT count(*) AS bookings_with_notes\n"
     "FROM bookings.bookings_json\n"
     "WHERE COALESCE(data ->> 'notes', '') <> '';", 9.5, 12)
paragraph('Результат: 18 799. Оператор ->> извлекает текст, COALESCE заменяет '
          'отсутствующее значение пустой строкой, а <> исключает пустые заметки. '
          'В данном наборе непустые notes содержат добавленный комментарий.')
sub('Просмотр первых 20 документов')
code("SELECT booking_id,\n"
     "       data ->> 'booking_number' AS booking_number,\n"
     "       data ->> 'status' AS status,\n"
     "       data -> 'passengers' AS passengers,\n"
     "       data ->> 'notes' AS notes\n"
     "FROM bookings.bookings_json\n"
     "ORDER BY booking_id\n"
     "LIMIT 20;", 9.5, 12)
paragraph('Поля JSON выводятся отдельными столбцами. Оператор -> сохраняет '
          'массив пассажиров в формате JSONB. ORDER BY задает сортировку по номеру '
          'брони, LIMIT ограничивает только вывод, не изменяя таблицу.')
sub('Пример структуры: бронь 00000F')
table(['Поле', 'Значение'], [
    ['booking_number', '00000F'],
    ['status', 'confirmed'],
    ['passengers[0].id', '1708 262537'],
    ['passengers[0].name', 'PASSENGER_001'],
], [155, WIDTH-155])
paragraph('Имя пассажира в иллюстрации заменено условным обозначением.<br/>'
          'notes: «Бронирование содержит рейс в/из аэропорта с разницей во времени '
          'относительно Москвы более 6 часов».', SMALL)
end_page()

title('5. Вывод')
paragraph('В ходе лабораторной работы создана таблица bookings_json и заполнена '
          'на основе исходных бронирований и билетов. Освоено построение JSONB '
          'с помощью jsonb_build_object и jsonb_agg, извлечение значений '
          'операторами -> и ->>, а также изменение отдельного ключа через jsonb_set.')
paragraph('Сформировано 262 788 JSON-документов. Индивидуальное задание выполнено: '
          'для 18 799 броней, включающих рейсы '
          'в/из аэропортов с разницей относительно московского времени строго '
          'более 6 часов, добавлен комментарий в notes. Три запроса демонстрируют '
          'общее количество документов, количество документов с непустой заметкой '
          'и содержимое первых 20 записей. Повторное выполнение основных файлов '
          'не создает дубликатов документов и комментариев.')
gap(12)
title('Список использованных источников')
paragraph('1. Postgres Professional. Демонстрационная база данных «Авиаперевозки», '
          'версия от 15.08.2017.<br/>'
          '<link href="https://postgrespro.ru/education/demodb" color="#222222">'
          'https://postgrespro.ru/education/demodb</link>', SMALL)
paragraph('2. PostgreSQL. Документация: JSON Functions and Operators.<br/>'
          '<link href="https://www.postgresql.org/docs/18/functions-json.html" color="#222222">'
          'https://www.postgresql.org/docs/18/functions-json.html</link>', SMALL)
paragraph('3. PostgreSQL. Документация: Date/Time Functions and Operators.<br/>'
          '<link href="https://www.postgresql.org/docs/18/functions-datetime.html" color="#222222">'
          'https://www.postgresql.org/docs/18/functions-datetime.html</link>', SMALL)
gap(15)
sub('Состав приложений')
paragraph('Приложение А - полный текст 01_create_and_fill.sql.<br/>'
          'Приложение Б - полный текст 02_update_notes.sql.<br/>'
          'Три запроса для просмотра результата приведены в разделе 4.<br/>'
          'Длинные строки листингов перенесены только для размещения на странице.', SMALL)
end_page()

# Full, current SQL source listings, without logical edits.
for letter, filename in [('А', '01_create_and_fill.sql'),
                         ('Б', '02_update_notes.sql')]:
    text = (ROOT / filename).read_text(encoding='utf-8-sig').strip()
    # Font width is measured, so Cyrillic comments and long SQL literals fit.
    lines = wrap_code(text, 8.5)
    first = True
    while lines:
        title(f'Приложение {letter}' + ('' if first else ' (продолжение)'))
        paragraph(escape(filename), SMALL)
        available = int((y-BOTTOM-24) // 10.1)
        take = min(available, len(lines))
        # Prefer a blank-line boundary when it avoids splitting a logical block.
        if len(lines) > take:
            for candidate in range(take, max(take-10, take//2), -1):
                if lines[candidate-1] == '':
                    take = candidate
                    break
        code_lines(lines[:take], 8.5, 10.1)
        lines = lines[take:]
        while lines and lines[0] == '':
            lines.pop(0)
        end_page()
        first = False

c.save()
reader = PdfReader(str(DEST))
texts = [p.extract_text() or '' for p in reader.pages]
required = ['ОТЧЕТ К РАБОТЕ № 1', '262 788', '18 799',
            '01_create_and_fill.sql', '02_update_notes.sql',
            'AS total_bookings', 'AS bookings_with_notes', 'LIMIT 20;']
all_text = '\n'.join(texts)
assert '03_check.sql' not in all_text, 'Unrequested check script remains in PDF'
assert 'Приложение В' not in all_text, 'Unrequested appendix remains in PDF'
for value in required:
    assert value in all_text, f'Missing PDF text: {value}'
assert all(len(text.strip()) > 150 for text in texts), 'Empty page detected'
(TMP / 'report_text.txt').write_text(all_text, encoding='utf-8')
(TMP / 'layout.json').write_text(json.dumps(page_info, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'pdf': str(DEST), 'pages': len(reader.pages), 'layout': page_info}, ensure_ascii=False))
