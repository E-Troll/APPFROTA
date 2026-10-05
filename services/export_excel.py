"""
Excel export in the "REGISTRO DE INSPEÇÕES" layout (DNIT - SR Bahia).
Columns: Dia, Recurso (SIGLA), Origem (Cidade, BR, KM, Hora Saída),
Destino (Cidade, BR, KM, Hora Chegada), Tipo de Ação, Distância, Tempo de Deslocamento.
"""

import base64
import io
import re
from datetime import datetime, date, time

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

MONTHS_PT = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]
MIN_DATA_ROWS = 83
FIRST_DATA_ROW = 10


def parse_dt(value):
    if not value:
        return None
    text = str(value).strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _number(value):
    if value in (None, ''):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _br(value):
    text = str(value or '').strip()
    match = re.search(r'\d+', text)
    return int(match.group()) if match else (text or None)


def _reference_label(trips, month_filter):
    month = (month_filter or '').strip()
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        first = parse_dt(trips[-1].get('start_time')) if trips else None
        first = first or datetime.now()
        month = first.strftime('%Y-%m')
    year, number = month.split('-')
    return f'Referencia: {MONTHS_PT[int(number) - 1]} {year}'


def _logo_image():
    try:
        import os
        from openpyxl.drawing.image import Image
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'img', 'logo.svg')
        with open(path, encoding='utf-8') as handle:
            match = re.search(r'base64,([A-Za-z0-9+/=]+)', handle.read())
        image = Image(io.BytesIO(base64.b64decode(match.group(1))))
        image.width = image.height = 52
        return image
    except Exception:
        return None


def generate_trips_excel(trips, month_filter=None, base_url=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'RELATÓRIO INSPEÇÃO'

    thin = Side(style='thin')
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    white = PatternFill('solid', start_color='FFFFFF')
    navy = PatternFill('solid', start_color='002060')
    company_fill = PatternFill('solid', start_color='FFF2CC')
    calc_fill = PatternFill('solid', start_color='D0CECE')
    center = Alignment(horizontal='center', vertical='center')
    head_font = Font(name='Arial', size=10, color='FFFFFF')
    body_font = Font(name='Arial', size=10)

    widths = {'A': 20.8, 'B': 16.8, 'C': 30.8, 'D': 16.8, 'E': 15.8, 'F': 16.8,
              'G': 30.8, 'H': 16.8, 'I': 15.8, 'J': 16.8, 'K': 16.7, 'L': 20.6, 'M': 20.1}
    for column, width in widths.items():
        ws.column_dimensions[column].width = width
    for row, height in {2: 35.4, 3: 20.4, 4: 26.4, 5: 18, 6: 18, 7: 18, 8: 14.4}.items():
        ws.row_dimensions[row].height = height

    for row in range(1, 8):
        for column in range(1, 14):
            ws.cell(row, column).fill = white

    ws.merge_cells('C2:K2')
    ws['C2'] = 'DEPARTAMENTO NACIONAL DE INFRAESTRUTURA E TRANSPORTES \nSUPERINTENDÊNCIA REGIONAL NO ESTADO DA BAHIA'
    ws['C2'].font = Font(name='Calibri Light', size=14, bold=True)
    ws['C2'].alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

    ws.merge_cells('A4:K4')
    ws['A4'] = 'REGISTRO DE INSPEÇÕES'
    ws['A4'].font = Font(name='Calibri Light', size=22, bold=True)
    ws['A4'].alignment = center

    ws.merge_cells('A5:K5')
    ws.merge_cells('G6:K6')
    ws['G6'] = _reference_label(trips, month_filter)
    ws['G6'].font = Font(name='Calibri Light', size=14)
    ws['G6'].alignment = center

    ws.merge_cells('A7:K7')
    ws['A7'] = 'EMPRESA: CONSÓRCIO OPERAÇÃO RODOVIÁRIA I'
    ws['A7'].font = Font(name='Calibri Light', size=14, bold=True)
    ws['A7'].alignment = center
    for column in range(1, 12):
        ws.cell(7, column).fill = company_fill
        ws.cell(7, column).border = box

    for cell in ('A8:A9', 'B8:B9', 'C8:C9', 'G8:G9', 'K8:K9', 'L8:L9', 'M8:M9', 'D8:F8', 'H8:J8'):
        ws.merge_cells(cell)
    labels = {
        'A8': 'Dia', 'B8': 'Recurso (SIGLA)', 'C8': 'Cidade', 'D8': 'Origem', 'G8': 'Cidade',
        'H8': 'Destino', 'K8': 'Tipo de Ação', 'L8': 'Distância', 'M8': 'Tempo de Deslocamento',
        'D9': 'BR', 'E9': 'KM', 'F9': 'Hora Saída', 'H9': 'BR', 'I9': 'KM', 'J9': 'Hora Chegada',
    }
    for column in range(1, 14):
        for row in (8, 9):
            cell = ws.cell(row, column)
            cell.fill = navy
            cell.font = head_font
            cell.alignment = center
            cell.border = box
    for coordinate, label in labels.items():
        ws[coordinate] = label

    logo = _logo_image()
    if logo:
        ws.add_image(logo, 'A2')

    rows = sorted(trips, key=lambda t: (t.get('start_time') or '', t.get('id') or 0))
    last_row = FIRST_DATA_ROW + max(len(rows), MIN_DATA_ROWS) - 1
    for index in range(last_row - FIRST_DATA_ROW + 1):
        row = FIRST_DATA_ROW + index
        ws.row_dimensions[row].height = 22.05
        trip = rows[index] if index < len(rows) else None
        start = parse_dt(trip.get('start_time')) if trip else None
        end = parse_dt(trip.get('end_time')) if trip else None
        values = [None] * 13
        if trip:
            values[0] = start.date() if start else None
            values[1] = trip.get('vehicle_plate')
            values[2] = trip.get('origin_city') or None
            values[3] = _br(trip.get('origin_br'))
            values[4] = _number(trip.get('start_km'))
            values[5] = start.time().replace(microsecond=0) if start else None
            values[6] = trip.get('dest_city') or None
            values[7] = _br(trip.get('dest_br'))
            values[8] = _number(trip.get('end_km'))
            values[9] = end.time().replace(microsecond=0) if end else None
            values[10] = trip.get('action_type') or None
        values[11] = f'=IF(AND(D{row}<>"",D{row}=H{row},E{row}<>"",I{row}<>""),I{row}-E{row},"")'
        values[12] = f'=IF(OR(F{row}="",J{row}=""),"",MOD(J{row}-F{row},1))'
        for column, value in enumerate(values, start=1):
            cell = ws.cell(row, column, value)
            cell.font = body_font
            cell.alignment = center
            cell.border = box
            cell.fill = calc_fill if column >= 12 else white
        ws.cell(row, 1).number_format = 'mm-dd-yy'
        ws.cell(row, 6).number_format = 'h:mm'
        ws.cell(row, 10).number_format = 'h:mm'
        ws.cell(row, 12).number_format = '0.00'
        ws.cell(row, 13).number_format = '[$-F400]h:mm:ss\\ AM/PM'

    ws.print_area = f'A1:M{last_row + 1}'
    ws.page_setup.orientation = 'landscape'
    ws.sheet_properties.pageSetUpPr = openpyxl.worksheet.properties.PageSetupProperties(fitToPage=True)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
