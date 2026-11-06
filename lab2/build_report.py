"""Generate the lab 2 report from the collected data and the five actual SQL queries."""
from pathlib import Path
from collections import Counter
import json
import re
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
W, H = A4
LEFT, RIGHT, TOP, BOTTOM = 76, 43, 52, 52
WIDTH = W - LEFT - RIGHT
DEST = OUT / 'report.pdf'

for family, filename in [('TimesRU', 'times.ttf'), ('TimesRUB', 'timesbd.ttf'),
                         ('TimesRUI', 'timesi.ttf'), ('CodeRU', 'consola.ttf')]:
    pdfmetrics.registerFont(TTFont(family, str(Path('C:/Windows/Fonts') / filename)))
pdfmetrics.registerFontFamily('TimesRU', normal='TimesRU', bold='TimesRUB', italic='TimesRUI')
BODY = ParagraphStyle('body', fontName='TimesRU', fontSize=12, leading=17,
                      alignment=TA_JUSTIFY, spaceAfter=8)
SMALL = ParagraphStyle('small', parent=BODY, fontSize=10.5, leading=14, alignment=TA_LEFT)
HEADING = ParagraphStyle('heading', parent=BODY, fontName='TimesRUB', fontSize=14,
                         leading=18, alignment=TA_LEFT, spaceAfter=12)
SUB = ParagraphStyle('sub', parent=BODY, fontName='TimesRUB', fontSize=12,
                     leading=16, alignment=TA_LEFT, spaceAfter=7)
CELL = ParagraphStyle('cell', parent=SMALL, fontSize=10.2, leading=13)
CELL_HEAD = ParagraphStyle('cellhead', parent=CELL, fontName='TimesRUB')
c = None
page = 1
y = H-TOP
layout = []

def paragraph(text, style=BODY):
    global y
    p = Paragraph(text, style)
    _, h = p.wrap(WIDTH, H)
    if y-h < BOTTOM:
        raise RuntimeError(f'Paragraph overflow on page {page}: {text[:70]}')
    p.drawOn(c, LEFT, y-h)
    y -= h+style.spaceAfter

def title(text):
    paragraph(text, HEADING)

def sub(text):
    paragraph(text, SUB)

def table(headers, rows, widths):
    global y
    data = [[Paragraph(escape(str(x)), CELL_HEAD) for x in headers]]
    data += [[Paragraph(escape(str(x)), CELL) for x in row] for row in rows]
    t = Table(data, colWidths=widths, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#eeeeee')),
        ('GRID', (0,0), (-1,-1), .45, colors.HexColor('#666666')),
        ('LEFTPADDING', (0,0), (-1,-1), 7), ('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING', (0,0),(-1,-1),5), ('BOTTOMPADDING',(0,0),(-1,-1),5),
    ]))
    _, h = t.wrap(WIDTH,H)
    if y-h < BOTTOM:
        raise RuntimeError(f'Table overflow on page {page}: h={h}, y={y}')
    t.drawOn(c, LEFT,y-h)
    y -= h+12

def wrap_code(text, size):
    text = text.replace('\u2011','-').replace('\u2013','-').replace('\u2014','-')
    lines=[]
    for line in text.replace('\t','    ').splitlines():
        while pdfmetrics.stringWidth(line,'CodeRU',size)>WIDTH-16:
            n=len(line)
            while pdfmetrics.stringWidth(line[:n],'CodeRU',size)>WIDTH-16:
                n-=1
            space=line.rfind(' ',0,n+1)
            if space<=len(line)-len(line.lstrip())+4:
                space=n
                lines.append(line[:space])
                line='    '+line[space:]
            else:
                lines.append(line[:space])
                line='    '+line[space+1:]
        lines.append(line)
    return lines

def code(text,size=9,leading=11):
    global y
    lines=wrap_code(text.strip(),size)
    h=len(lines)*leading+14
    if y-h<BOTTOM:
        raise RuntimeError(f'Code overflow on page {page}: {len(lines)} lines, y={y}')
    c.setFillColor(colors.HexColor('#f6f6f6'))
    c.rect(LEFT,y-h,WIDTH,h,stroke=0,fill=1)
    c.setFillColor(colors.black)
    c.setFont('CodeRU',size)
    for i,line in enumerate(lines):
        c.drawString(LEFT+8,y-10-size-i*leading,line)
    y-=h+10

def end_page():
    global page,y
    layout.append({'page':page,'bottom_used':round(y,1)})
    if page>1:
        c.setFont('TimesRU',11)
        c.drawCentredString(W/2,28,str(page))
    c.showPage()
    page+=1
    y=H-TOP

def center(text,top,size=12,bold=False):
    sty=ParagraphStyle('cover',fontName='TimesRUB' if bold else 'TimesRU',fontSize=size,
                       leading=size*1.22,alignment=TA_CENTER)
    p=Paragraph(text,sty)
    _,h=p.wrap(WIDTH,H)
    p.drawOn(c,LEFT,H-top-h)

def cover():
    center('POSTGRESQL / JSONB',120,11)
    center('ОТЧЕТ К РАБОТЕ № 2',245,22,True)
    center('Сбор данных<br/>и аналитика JSONB',313,18)
    center('Каталог стартапов - вариант 14',405,13)
    center('HTML, очистка данных и SQL-запросы',439,11)
    c.setFont('TimesRU',11)
    c.drawCentredString(LEFT+WIDTH/2,58,'2026')
    end_page()

def read_inputs():
    startups=json.loads((ROOT/'data/startups.json').read_text(encoding='utf-8-sig'))
    summary=json.loads((ROOT/'data/collection_summary.json').read_text(encoding='utf-8-sig'))
    manifest=json.loads((ROOT/'source/manifest.json').read_text(encoding='utf-8-sig'))
    queries=(ROOT/'02_queries.sql').read_text(encoding='utf-8-sig')
    return startups,summary,manifest,queries

def source_section(startups, source_count):
    title('1. Цель, задание и источник данных')
    paragraph('Цель работы - исследовать слабоструктурированный веб-источник, '
              'извлечь сведения о стартапах, очистить их и представить в формате JSON. '
              'Для варианта 14 требуется более 300 записей с названием, временем '
              'основания, страной, сайтом, отраслью, основателями и привлеченными средствами.')
    paragraph('Источник - каталог Failory Startups [1]. Использованы подробные '
              'карточки первых компаний в страновых подборках. Они размещены в '
              'обычном HTML и содержат заголовки, ссылки, теги и пары «поле - значение». '
              'Извлечение выполняется непосредственно из сохраненного HTML.')
    paragraph('Примеры страниц:<br/>'
              '<link href="https://www.failory.com/startups/united-states">'
              'https://www.failory.com/startups/united-states</link><br/>'
              '<link href="https://www.failory.com/startups/india">'
              'https://www.failory.com/startups/india</link><br/>'
              '<link href="https://www.failory.com/startups/germany">'
              'https://www.failory.com/startups/germany</link>',SMALL)
    table(['Элемент HTML-карточки','Исходный формат'],[
        ['Заголовок и ссылка','Название компании и URL ее сайта'],
        ['Отраслевые теги','Несколько строковых категорий'],
        ['Headquarters','Текстовое местоположение и страна'],
        ['Year Founded','Четырехзначный год'],
        ['Founders','Перечень имен или обозначение пропуска'],
        ['Funding Amount','Текст: знак валюты, число, суффикс k/M/B'],
        ['Дополнительные поля','Размер команды, стадия финансирования, инвесторы'],
    ],[155,WIDTH-155])
    paragraph(f'В итоговом наборе {len(startups)} уникальных записей. '
              f'Для воспроизводимости сохранены {source_count} HTML-страниц и manifest.json '
              'с данными об источниках. Набор является срезом каталога Failory, '
              'а не полной переписью стартапов мира.')
    examples=[next(x for x in startups if x['name']==name)
              for name in ('Anthropic','DeepL','Zepto')]
    table(['Компания','Страна','Год','Funding Amount'],[
        [x['name'],x['country'],x['founded_year'],x['raised_money']['raw']]
        for x in examples
    ],[110,140,55,WIDTH-305])
    paragraph('Подробные карточки выделяются по h3.failory-card-title; поля '
              'извлекаются из table.info-table, а отрасли - из failory-badge. '
              'Компактные таблицы остальных компаний не используются, поскольку '
              'в них отсутствует часть требуемых полей.',SMALL)
    end_page()

def algorithm_section():
    title('2. Алгоритм извлечения и очистки')
    paragraph('Обработка выполнена Python-скриптом. HTML-страницы сохраняются локально; '
              'повторный разбор возможен без изменения исходного среза. PostgreSQL '
              'используется для хранения JSONB и выполнения аналитических запросов.')
    table(['Шаг','Операция'],[
        ['1. Получение','Загрузить страновые страницы и записать исходный HTML.'],
        ['2. Выделение','Найти подробные карточки компаний, их названия, ссылки и поля.'],
        ['3. Извлечение','Получить год, местоположение, отрасли, основателей и сумму.'],
        ['4. Нормализация','Убрать лишние пробелы, привести массивы и числовые значения.'],
        ['5. Проверка','Проверить допустимость года, URL и неотрицательность суммы.'],
        ['6. Дедупликация','Не допускать повторов одной компании в итоговом наборе.'],
        ['7. Выгрузка','Записать JSON и сводку сбора, затем загрузить документы в JSONB.'],
    ],[100,WIDTH-100])
    sub('Правила очистки')
    paragraph('HTML-сущности декодируются; неразрывные и повторные пробелы '
              'нормализуются. Пустые имена и отраслевые теги удаляются, повторы '
              'в массивах исключаются. Отсутствующие сведения не придумываются: '
              'основатели представлены пустым массивом, неизвестные суммы - null.')
    paragraph('Страна извлекается из Headquarters, а не из названия подборки. '
              'URL проверяется на схему http/https и наличие имени хоста; '
              'фрагменты, ref и utm-параметры удаляются. Ссылка-заглушка '
              'превращается в null, исходное значение остается в website_raw.')
    paragraph('Для идентификации используется нормализованное имя и домен сайта '
              'без www.; при отсутствии сайта - страна. Идентификатор образуется '
              'из SHA-256 этого сочетания. При повторе сохраняется первая запись '
              'и объединяются ссылки; возможные конфликты фиксируются отдельно.')
    paragraph('Источник сообщает только Year Founded. Поэтому хранится год '
              'с точностью до года, без выдуманной даты 1 января. Значения k, M и B '
              'означают множители 1 000, 1 000 000 и 1 000 000 000. Исходная '
              'строка суммы сохраняется для проверки преобразования.')
    paragraph('Обозначение валюты сохраняется буквально: $, €, A$, CN¥, R$, ¥. '
              'Знак $ не объявляется автоматически кодом USD. Курсы пересчета '
              'не используются; суммы с разными обозначениями валют не складываются '
              'и не ранжируются в одной группе.')
    end_page()

def contract_section():
    title('3. Формат вывода и типы полей JSON')
    paragraph('Файл startups.json содержит массив объектов: один объект на одну '
              'уникальную компанию. В PostgreSQL каждый объект сохраняется в поле '
              'data типа JSONB таблицы lab2.startups_json. Полный контракт полей:')
    table(['Поле','JSON-тип и назначение'],[
        ['id','string: стабильный идентификатор компании'],
        ['name','string: название компании'],
        ['founded_year','integer | null: известный год основания'],
        ['foundation_date','null: точная календарная дата источником не сообщается'],
        ['foundation_precision','string: year либо unknown'],
        ['country','string: страна из поля Headquarters'],
        ['headquarters','string | null: местоположение как в источнике'],
        ['website','string | null: очищенный URL сайта'],
        ['website_raw','string | null: исходная ссылка для проверки'],
        ['sectors','array<string>: уникальные отраслевые теги'],
        ['founders','array<string>: имена основателей; [] при отсутствии'],
        ['raised_money','object: amount (number | null), currency_label '
                        '(string | null), raw (string | null)'],
        ['funding_stage','string | null: указанная стадия финансирования'],
        ['team_size_raw','string | null: исходное описание размера команды'],
        ['investors','array<string>: перечисленные инвесторы'],
        ['source_urls','array<string>: ссылки на исходные страницы и карточки'],
        ['retrieved_at','string: время получения страницы в формате ISO 8601'],
    ],[135,WIDTH-135])
    paragraph('JSON не имеет отдельного типа date: даты и время передаются строками '
              'по явно указанному формату. Значение null отличается от нуля; '
              'пустой массив основателей означает отсутствие сведений в выбранном '
              'источнике, а не отсутствие основателей у компании.',SMALL)
    end_page()

def example_section(startups,summary):
    title('4. Пример документа и результат сбора')
    example=next((x for x in startups if x['name']=='DeepL'),startups[0])
    paragraph('Сокращенный пример документа; имена основателей в иллюстрации '
              'заменены условными обозначениями. Полный набор полей находится в JSON-файле.')
    mini={k:example[k] for k in ('id','name','founded_year','foundation_date',
                                'foundation_precision','country','website','sectors',
                                'founders','raised_money')}
    mini['founders'] = [f'FOUNDER_{index:03d}' for index in range(1, len(mini['founders']) + 1)]
    text=json.dumps(mini,ensure_ascii=False,indent=2)
    # Keep arrays compact without changing their values, to improve print readability.
    for key in ('sectors','founders'):
        expanded=json.dumps(mini[key],ensure_ascii=False,indent=2)
        compact=json.dumps(mini[key],ensure_ascii=False)
        pattern=r'"'+key+r'": \[.*?\]'
        text=re.sub(pattern,lambda m:'"'+key+'": '+compact,text,flags=re.S)
    code(text,9,11)
    table(['Показатель','Значение'],[
        ['Уникальные компании',summary['records']],
        ['Успешно обработанные страницы',summary['pages']],
        ['Страны в итоговых данных',summary['countries']],
        ['Основатели не указаны',summary['founders_unknown']],
        ['Сайт не указан или ссылка некорректна',summary['website_unknown']],
        ['Сумма финансирования неизвестна',summary['funding_unknown']],
        ['Год основания неизвестен',summary['foundation_year_unknown']],
    ],[WIDTH-110,110])
    paragraph('Число записей строго больше 300. Веб-страницы сохранены локально, '
              'а manifest.json фиксирует URL, время получения, число карточек '
              'и SHA-256 исходного HTML. Точные даты основания не выдумывались.',SMALL)
    end_page()

def query_parts(source):
    starts=list(re.finditer(r'^-- Q([1-5])\b.*$',source,re.M))
    assert len(starts)==5,'Expected exactly five actual SQL query blocks'
    result={}
    for i,m in enumerate(starts):
        stop=starts[i+1].start() if i+1<len(starts) else len(source)
        block=source[m.end():stop]
        result[int(m.group(1))]='\n'.join(line for line in block.splitlines()
                                       if not line.lstrip().startswith('--')).strip()
    return result

def simple_queries_section(queries,startups,results):
    title('5. Три простых запроса')
    sub('Q1. Объем набора и пропуски')
    code(queries[1],9,10.6)
    paragraph(f'Результат: total_startups = {len(startups)}; '
              f'founders_unknown = {sum(not x["founders"] for x in startups)}; '
              f'funding_unknown = {sum(x["raised_money"]["amount"] is None for x in startups)}. '
              'COUNT(*) считает все документы, FILTER отдельно подсчитывает пропуски.',SMALL)
    sub('Q2. Компании Индии, основанные с 2015 года')
    code(queries[2],9,10.6)
    q2=[x for x in startups if x['country']=='India' and x['founded_year'] is not None
        and x['founded_year']>=2015]
    paragraph(f'Найдено {len(q2)} компаний. Оператор ->> извлекает текст, '
              'приведение ::integer позволяет сравнивать год как число. '
              'Сортировка по имени и id делает порядок однозначным.',SMALL)
    table(['Первые результаты Q2','Год','Страна'],[
        [x['name'],x['founded_year'],x['country']] for x in results['Q2'][:3]
    ],[WIDTH-130,55,75])
    sub('Q3. Компании с точным отраслевым тегом AI')
    code(queries[3],9,10.6)
    q3=[x for x in startups if 'AI' in x['sectors']]
    paragraph(f'Найдено {len(q3)} компаний. Оператор ? проверяет наличие точной '
              'строки в JSONB-массиве. Он не ищет подстроку: тег Generative AI '
              'сам по себе не удовлетворяет условию AI.',SMALL)
    paragraph('Первые результаты Q3: '+', '.join(escape(x['name']) for x in results['Q3'][:3])+'.',SMALL)
    end_page()

def money(value):
    if value is None:
        return 'null'
    return f'{value:,.2f}'.replace(',',' ').removesuffix('.00')

def advanced_sections(queries,results):
    title('6. Расширенный запрос: статистика по секторам')
    paragraph('Q4 группирует компании по стране, отраслевому тегу и буквальному '
              'обозначению валюты. В отчет попадают группы не менее чем из двух '
              'компаний. Запрос возвращает количество компаний, число известных '
              'сумм, сумму и среднее финансирование по источнику.')
    code(queries[4],8.6,10.3)
    paragraph('CROSS JOIN LATERAL раскрывает массив отраслей. DISTINCT оставляет '
              'одну строку на сочетание компании и отрасли. COUNT(amount), SUM '
              'и AVG игнорируют null; при отсутствии известных сумм результат '
              'SUM/AVG остается null. Нулевые значения вместо пропусков не подставляются.')
    paragraph('Компания может относиться к нескольким секторам. Поэтому результаты '
              'разных секторных групп нельзя складывать для получения общего '
              'финансирования. Совпадающий маркер $ не доказывает совпадение '
              'международного кода валюты; расчет имеет описательный смысл '
              'только в пределах выбранной группы.',SMALL)
    sub(f'Результат Q4: {len(results["Q4"])} групп')
    country=results['Q4'][0]['country']
    paragraph('Пример первых групп ('+escape(country)+'):',SMALL)
    table(['Сектор','Метка','N / известно','Сумма','Среднее'],[
        [x['sector'],x['currency_label'],str(x['startups_count'])+' / '+str(x['known_funding_count']),
         money(x['total_reported_amount']),money(x['average_reported_amount'])]
        for x in results['Q4'][:3]
    ],[110,45,71,125,WIDTH-351])
    end_page()
    title('7. Расширенный запрос: лидеры финансирования')
    paragraph('Q5 выбирает не более трех компаний в каждой паре «страна - '
              'обозначение валюты». Записи с неизвестной суммой или валютным '
              'маркером исключаются до ранжирования.')
    code(queries[5],8.8,10.5)
    paragraph('ROW_NUMBER нумерует компании внутри группы. Основной критерий - '
              'убывание суммы; при равенстве используются название и стабильный id. '
              'Поэтому условие funding_rank &lt;= 3 возвращает максимум три компании, '
              'а в малых группах - меньше трех.')
    paragraph('Денежные значения извлекаются оператором #>> по вложенному пути '
              'и приводятся к numeric. Разные валютные обозначения не '
              'смешиваются. Это рейтинг по данным выбранного источника, '
              'не оценка стоимости компаний и не инвестиционная рекомендация.',SMALL)
    sub(f'Результат Q5: {len(results["Q5"])} строк')
    paragraph('Фрагмент фактического результата:',SMALL)
    table(['Страна','Метка','Место','Компания','Сумма'],[
        [x['country'],x['currency_label'],x['funding_rank'],x['name'],money(x['amount'])]
        for x in results['Q5'][:6]
    ],[90,45,45,145,WIDTH-325])
    end_page()

def final_section(summary,validation):
    title('8. Вывод и ограничения исследования')
    paragraph(f'Для варианта 14 «Стартапы» исследован HTML-каталог Failory. '
              f'Собран набор из {summary["records"]} уникальных компаний '
              f'по {summary["pages"]} сохраненным веб-страницам. Описаны '
              'исходная структура, типы полей, алгоритм извлечения и правила очистки. '
              'Результат представлен в JSON и пригоден для хранения в JSONB.')
    paragraph('Разработаны ровно пять запросов: три простых для подсчета пропусков '
              'и выборок, два расширенных для групповой статистики и ранжирования. '
              'Запросы работают с массивами отраслей и вложенным денежным объектом, '
              'учитывают пропуски и не объединяют разные валютные маркеры.')
    paragraph(f'Проверка реализации завершилась успешно: {validation["passed"]} '
              'проверки. Полные результаты всех пяти SQL-запросов сопоставлены '
              'с независимым расчетом Python, включая порядок строк, суммы, '
              'средние значения, пропуски и разрешение равенств при ранжировании.')
    sub('Ограничения')
    paragraph('Выборка включает подробные карточки в порядке страновых страниц '
              'каталога и не является случайной или репрезентативной. Данные '
              'отражают содержание сохраненных страниц, могут быть неполными '
              'и не проходили независимую финансовую проверку. Обозначение '
              'startup используется в смысле источника: каталог может включать '
              'давно основанные и уже крупные компании.')
    paragraph('Для части записей неизвестны основатели, сайт или финансирование. '
              'Год основания не заменяется полной датой. Буквальные валютные '
              'обозначения сохраняются без предположения, что любой знак $ означает USD.')
    sub('Использованные источники')
    paragraph('1. Failory. Каталог стартапов и страновые подборки.<br/>'
              '<link href="https://www.failory.com/startups">'
              'https://www.failory.com/startups</link>',SMALL)
    paragraph('2. PostgreSQL 18. JSON Functions and Operators.<br/>'
              '<link href="https://www.postgresql.org/docs/18/functions-json.html">'
              'https://www.postgresql.org/docs/18/functions-json.html</link>',SMALL)
    paragraph('3. PostgreSQL 18. Window Functions.<br/>'
              '<link href="https://www.postgresql.org/docs/18/functions-window.html">'
              'https://www.postgresql.org/docs/18/functions-window.html</link>',SMALL)
    paragraph('Воспроизводимые материалы: исходные HTML и manifest.json; '
              '01_collect.py; data/startups.json; data/collection_summary.json; '
              '00_schema.sql; 01_load_data.sql; 02_queries.sql; '
              'results/queries.json; results/validation.json.',SMALL)
    end_page()

def build():
    global c
    startups,summary,manifest,query_source=read_inputs()
    results=json.loads((ROOT/'results/queries.json').read_text(encoding='utf-8-sig'))
    validation=json.loads((ROOT/'results/validation.json').read_text(encoding='utf-8-sig'))
    if isinstance(startups,dict):
        startups=startups.get('startups',startups.get('records',startups.get('data')))
    assert isinstance(startups,list) and len(startups)>300
    OUT.mkdir(parents=True,exist_ok=True)
    TMP.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(DEST),pagesize=A4,pageCompression=1)
    c.setTitle('Отчет к работе 2. Каталог стартапов и JSONB')
    c.setAuthor('')
    c.setCreator('ReportLab')
    c.setSubject('Исследование веб-источника, очистка данных, JSON и пять SQL-запросов')
    cover()
    queries=query_parts(query_source)
    source_section(startups,len(manifest))
    algorithm_section()
    contract_section()
    example_section(startups,summary)
    simple_queries_section(queries,startups,results)
    advanced_sections(queries,results)
    final_section(summary,validation)
    c.save()
    pdf=PdfReader(str(DEST))
    all_text='\n'.join(p.extract_text() or '' for p in pdf.pages)
    for required in ('ОТЧЕТ К РАБОТЕ № 2','Вариант 14','ROW_NUMBER','CROSS JOIN LATERAL'):
        assert required.casefold() in all_text.casefold(),required
    (TMP/'report_text.txt').write_text(all_text,encoding='utf-8')
    (TMP/'layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pdf':str(DEST),'pages':len(pdf.pages),'layout':layout},ensure_ascii=True))

if __name__=='__main__':
    build()
