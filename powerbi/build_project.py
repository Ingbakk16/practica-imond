"""Build the editable Power BI project from the repository's CSV contract.

Open EcoBottle_AR.pbip in Power BI Desktop, Refresh, then Save As PBIX.
Only Python's standard library is required. Raw data is never modified.
"""
from pathlib import Path
import json
import re
import uuid

ROOT = Path(__file__).resolve().parent
DW = ROOT.parent / 'dw'
REPORT = ROOT / 'EcoBottle_AR.Report'
MODEL = ROOT / 'EcoBottle_AR.SemanticModel'
SCHEMA = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def literal(value):
    if isinstance(value, bool):
        value = str(value).lower()
    elif isinstance(value, str):
        value = "'" + value.replace("'", "''") + "'"
    else:
        value = str(value) + 'D'
    return {'expr': {'Literal': {'Value': value}}}


def color(value):
    return {'solid': {'color': literal(value)}}


def field(table, name, measure=False):
    return {('Measure' if measure else 'Column'): {
        'Expression': {'SourceRef': {'Entity': table}}, 'Property': name}}


def projection(table, name, measure=False):
    return {'field': field(table, name, measure), 'queryRef': table + '.' + name,
            'nativeQueryRef': name}


contracts = re.findall(r'fnCsv\("([^"]+)", (.*?)\)\s*```', (ROOT / 'README.md').read_text(encoding='utf-8'), re.S)
tables = []
for name, contract in contracts:
    types = re.findall(r'\{"([^"]+)", ([^}]+)\}', contract)
    columns = []
    for col, typ in types:
        dt = {'Int64.Type': 'int64', 'Currency.Type': 'decimal', 'type date': 'dateTime',
              'type datetime': 'dateTime', 'type logical': 'boolean', 'type text': 'string'}[typ]
        c = {'name': col, 'dataType': dt, 'sourceColumn': col, 'summarizeBy': 'none'}
        if col.endswith(('_id', '_key')):
            c['isHidden'] = True
        if typ == 'Currency.Type':
            c['formatString'] = '"$" #,0.00;("$" #,0.00);"$" 0.00'
        if typ == 'type date':
            c['formatString'] = 'dd/MM/yyyy'
        if name == 'dim_date' and col == 'month_name':
            c['sortByColumn'] = 'month'
        columns.append(c)
    if name == 'dim_date':
        columns += [
            {'name': 'Año mes', 'dataType': 'string', 'type': 'calculated',
             'expression': 'FORMAT(dim_date[date_value], "yyyy-MM")', 'summarizeBy': 'none'}]
    tables.append({'name': name, 'columns': columns, 'partitions': [{
        'name': name, 'mode': 'import', 'source': {'type': 'm',
            'expression': f'''let
    Archivo = RutaDW & "\\{name}.csv",
    Origen = Csv.Document(File.Contents(Archivo), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Nulos = Table.ReplaceValue(Encabezados, "", null, Replacer.ReplaceValue, Table.ColumnNames(Encabezados)),
    Tipada = Table.TransformColumnTypes(Nulos, {contract}, "en-US")
in
    Tipada'''}}]})

assert len(tables) == 10, 'Expected ten CSV table contracts'
measure_text = re.sub(r'//[^\n]*', '', (ROOT / 'medidas.dax').read_text(encoding='utf-8')).strip()
measures = []
for block in re.split(r'\n\s*\n', measure_text):
    name, expression = block.split('=', 1)
    name = name.strip()
    fmt = '"$" #,0.00;("$" #,0.00);"$" 0.00' if 'ARS' in name else ('0.0' if name in ['NPS', 'Duracion Media (s)'] else '#,0')
    measures.append({'name': name, 'expression': expression.strip(), 'formatString': fmt})
measures += [
    {'name': 'Pasivos', 'expression': 'CALCULATE([Respuestas NPS], fact_nps_response[score] >= 7, fact_nps_response[score] <= 8)', 'formatString': '#,0'},
    {'name': 'Unidades vendidas', 'expression': 'CALCULATE(SUM(fact_sales_order_item[quantity]), fact_sales_order_item[es_venta] = TRUE())', 'formatString': '#,0'},
    {'name': 'Porcentaje anónimas', 'expression': 'DIVIDE([Sesiones Anonimas], [Sesiones])', 'formatString': '0.0%'}]
tables[0]['measures'] = measures
MT = tables[0]['name']
relationships = []
for t in tables:
    if not t['name'].startswith('fact_'):
        continue
    for c in t['columns']:
        if c['name'].endswith('_key'):
            dim = 'dim_' + c['name'][:-4]
            relationships.append({'name': str(uuid.uuid5(uuid.NAMESPACE_URL, t['name'] + c['name'])),
                'fromTable': t['name'], 'fromColumn': c['name'], 'toTable': dim,
                'toColumn': c['name'], 'fromCardinality': 'many', 'toCardinality': 'one',
                'crossFilteringBehavior': 'oneDirection', 'isActive': True})
assert len(relationships) == 16
save(MODEL / 'definition.pbism', {'version': '1.0', 'settings': {}})
save(MODEL / 'model.bim', {'name': 'EcoBottle_AR', 'compatibilityLevel': 1567,
    'model': {'culture': 'es-AR', 'defaultPowerBIDataSourceVersion': 'powerBI_V3',
        'sourceQueryCulture': 'en-US', 'tables': tables, 'relationships': relationships,
        'expressions': [
            {'name': 'RutaDW', 'kind': 'm', 'expression': json.dumps(str(DW), ensure_ascii=False).replace('\\\\', '\\') + ' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]', 'annotations': [{'name': 'PBI_ResultType', 'value': 'Text'}]}],
        'annotations': [{'name': 'PBI_QueryOrder', 'value': json.dumps(['RutaDW'] + [t['name'] for t in tables])},
                        {'name': '__PBI_TimeIntelligenceEnabled', 'value': '0'}]}})
save(ROOT / 'EcoBottle_AR.pbip', {'version': '1.0', 'artifacts': [{'report': {'path': 'EcoBottle_AR.Report'}}], 'settings': {'enableAutoRecovery': True}})
save(REPORT / 'definition.pbir', {'version': '4.0', 'datasetReference': {'byPath': {'path': '../EcoBottle_AR.SemanticModel'}}})
save(REPORT / 'definition/version.json', {'$schema': SCHEMA + 'versionMetadata/1.0.0/schema.json', 'version': '2.0.0'})
save(REPORT / 'definition/report.json', {'$schema': SCHEMA + 'report/1.0.0/schema.json', 'themeCollection': {}, 'layoutOptimization': 'None'})

pages = []
visual_count = 0


def visual(page, kind, title, x, y, w, h, roles=None, objects=None):
    global visual_count
    visual_count += 1
    name = f'visual{visual_count:04}'
    v = {'visualType': kind, 'drillFilterOtherVisuals': True,
         'visualContainerObjects': {
             'title': [{'properties': {'show': literal(bool(title)), 'text': literal(title), 'fontSize': literal(12), 'fontColor': color('#173F35'), 'fontFamily': literal('Segoe UI Semibold')}}],
             'background': [{'properties': {'show': literal(True), 'color': color('#FFFFFF'), 'transparency': literal(0)}}],
             'border': [{'properties': {'show': literal(True), 'color': color('#DDE8E2'), 'radius': literal(8)}}]}}
    if roles:
        v['query'] = {'queryState': {role: {'projections': [projection(*f) for f in fs]} for role, fs in roles.items()}}
    if objects:
        v['objects'] = objects
    save(REPORT / 'definition/pages' / page / 'visuals' / name / 'visual.json', {
        '$schema': SCHEMA + 'visualContainer/2.4.0/schema.json', 'name': name,
        'position': {'x': x, 'y': y, 'z': visual_count, 'height': h, 'width': w, 'tabOrder': visual_count}, 'visual': v})
    return name


def text(page, content, x, y, w, h, size=12, ink='#536C62'):
    return visual(page, 'textbox', '', x, y, w, h, objects={
        'general': [{'properties': {'paragraphs': [{'textRuns': [{'value': content, 'textStyle': {'fontFamily': 'Segoe UI', 'fontSize': f'{size}pt', 'color': ink}}]}]}}]})


def card(page, name, x, y=174, w=284):
    return visual(page, 'card', name, x, y, w, 100, {'Values': [(MT, name, True)]}, {
        'labels': [{'properties': {'color': color('#136A50'), 'fontSize': literal(25), 'labelDisplayUnits': literal(1)}}],
        'categoryLabels': [{'properties': {'show': literal(False)}}]})


def slicer(page, table, col, title, x, w=228):
    return visual(page, 'slicer', title, x, 66, w, 96, {'Values': [(table, col)]}, {
        'data': [{'properties': {'mode': literal('Dropdown')}}]})


def chart(page, kind, title, category, metrics, x, y, w, h):
    return visual(page, kind, title, x, y, w, h,
                  {'Category': [category], 'Y': [(MT, m, True) for m in metrics]})


def page(name, title, subtitle, filters):
    pid = f'page{len(pages)+1:02}'
    pages.append(pid)
    save(REPORT / 'definition/pages' / pid / 'page.json', {
        '$schema': SCHEMA + 'page/2.0.0/schema.json', 'name': pid, 'displayName': name,
        'displayOption': 'FitToPage', 'width': 1280, 'height': 800,
        'objects': {'background': [{'properties': {'color': color('#F2F6F3'), 'transparency': literal(0)}}]}})
    text(pid, 'EcoBottle AR  /  ' + title, 24, 14, 1232, 48, 24, '#173F35')
    for i, f in enumerate(filters):
        slicer(pid, *f, 24 + i * 248)
    text(pid, subtitle + '  •  Corte: 30/09/2025  •  Importes en ARS', 24, 752, 1232, 32, 10)
    return pid


date_filter = ('dim_date', 'Año mes', 'Período')
channel_filter = ('dim_channel', 'code', 'Canal')
p = page('Resumen', 'Visión del negocio', 'Ventas = pedidos PAID y FULFILLED; incluyen IVA y envío.', [date_filter, channel_filter])
for n, x in zip(['Ventas ARS', 'Pedidos', 'Ticket Promedio ARS', 'Clientes Compradores'], [24, 336, 648, 960]):
    card(p, n, x, w=296)
chart(p, 'lineChart', 'Evolución mensual de ventas', ('dim_date', 'Año mes'), ['Ventas ARS'], 24, 280, 780, 450)
chart(p, 'clusteredColumnChart', 'Ventas por canal', ('dim_channel', 'code'), ['Ventas ARS'], 820, 280, 436, 450)

p = page('Ventas', 'Desempeño comercial', 'Producto filtra solo las líneas; sus importes excluyen IVA y envío.', [date_filter, channel_filter, ('dim_province', 'name', 'Provincia'), ('dim_product', 'name', 'Producto')])
for n, x in zip(['Ventas ARS', 'Ventas por Producto ARS', 'Unidades vendidas', 'Pedidos'], [24, 336, 648, 960]):
    card(p, n, x, w=296)
chart(p, 'barChart', 'Ventas por provincia de destino', ('dim_province', 'name'), ['Ventas ARS'], 24, 280, 600, 220)
chart(p, 'barChart', 'Ventas por tienda · Sin tienda = online', ('dim_store', 'name'), ['Ventas ARS'], 640, 280, 616, 220)
visual(p, 'tableEx', 'Ranking mensual por producto · sin IVA ni envío', 24, 516, 1232, 214, {'Values': [
    ('dim_date', 'Año mes'), ('dim_product', 'name'), (MT, 'Ventas por Producto ARS', True), (MT, 'Ranking Producto', True)]})

p = page('Clientes', 'Clientes y actividad digital', 'Compradores y usuarios web son actividades distintas; estado del cliente al corte.', [date_filter, ('dim_customer', 'status', 'Estado de la cuenta')])
card(p, 'Clientes Compradores', 24, w=392)
card(p, 'Usuarios Activos', 436, w=400)
card(p, 'Sesiones Anonimas', 856, w=400)
chart(p, 'lineChart', 'Compradores y usuarios identificados por mes', ('dim_date', 'Año mes'), ['Clientes Compradores', 'Usuarios Activos'], 24, 280, 1232, 450)

p = page('Adquisición web', 'Tráfico y adquisición', 'Anónimas son sesiones, no personas únicas. Duración media excluye sesiones sin cierre.', [date_filter, ('fact_web_session', 'source', 'Fuente'), ('fact_web_session', 'device', 'Dispositivo')])
for n, x in zip(['Sesiones', 'Usuarios Activos', 'Porcentaje anónimas', 'Duracion Media (s)'], [24, 336, 648, 960]):
    card(p, n, x, w=296)
chart(p, 'clusteredColumnChart', 'Sesiones por fuente', ('fact_web_session', 'source'), ['Sesiones'], 24, 280, 600, 450)
chart(p, 'barChart', 'Sesiones por dispositivo', ('fact_web_session', 'device'), ['Sesiones'], 640, 280, 616, 450)

p = page('Satisfacción', 'Experiencia del cliente', 'NPS en puntos; se analiza por fecha de respuesta, no por fecha de compra.', [date_filter, channel_filter])
for n, x in zip(['NPS', 'Respuestas NPS', 'Promotores', 'Detractores'], [24, 336, 648, 960]):
    card(p, n, x, w=296)
chart(p, 'lineChart', 'Evolución del NPS', ('dim_date', 'Año mes'), ['NPS'], 24, 280, 780, 260)
chart(p, 'clusteredColumnChart', 'NPS por canal', ('dim_channel', 'code'), ['NPS'], 820, 280, 436, 260)
chart(p, 'clusteredColumnChart', 'Promotores, pasivos y detractores por canal', ('dim_channel', 'code'), ['Promotores', 'Pasivos', 'Detractores'], 24, 556, 1232, 174)
save(REPORT / 'definition/pages/pages.json', {'$schema': SCHEMA + 'pagesMetadata/1.0.0/schema.json', 'pageOrder': pages, 'activePageName': pages[0]})
print(f'Created {len(tables)} tables, {len(relationships)} relationships, {len(measures)} measures, {len(pages)} pages and {visual_count} visuals.')
