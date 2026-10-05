"""PDF export in the "REGISTRO DE INSPEÇÕES" layout (landscape A4)."""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.export_excel import _reference_label, parse_dt

NAVY = colors.HexColor('#002060')
COMPANY = colors.HexColor('#FFF2CC')
CALC = colors.HexColor('#D0CECE')


def _km(value):
    if value is None or value == '':
        return ''
    text = f'{float(value):.1f}'
    return text.rstrip('0').rstrip('.').replace('.', ',') if '.' in text else text


def generate_trips_pdf(trips, month_filter=None, base_url=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm, title='Registro de Inspeções'
    )
    small = ParagraphStyle('small', fontName='Helvetica', fontSize=8, alignment=1)
    org = ParagraphStyle('org', fontName='Helvetica-Bold', fontSize=10, leading=12)
    title = ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=18, alignment=1, leading=22)
    sub = ParagraphStyle('sub', fontName='Helvetica', fontSize=10, alignment=1)

    story = [
        Paragraph('DEPARTAMENTO NACIONAL DE INFRAESTRUTURA E TRANSPORTES<br/>'
                  'SUPERINTENDÊNCIA REGIONAL NO ESTADO DA BAHIA', org),
        Spacer(1, 4 * mm),
        Paragraph('REGISTRO DE INSPEÇÕES', title),
        Paragraph(_reference_label(trips, month_filter), sub),
        Spacer(1, 3 * mm),
    ]

    head1 = ['Dia', 'Recurso (SIGLA)', 'Cidade', 'Origem', '', '', 'Cidade', 'Destino', '', '',
             'Tipo de Ação', 'Distância', 'Tempo de Deslocamento']
    head2 = ['', '', '', 'BR', 'KM', 'Hora Saída', '', 'BR', 'KM', 'Hora Chegada', '', '', '']
    data = [
        ['EMPRESA: CONSÓRCIO OPERAÇÃO RODOVIÁRIA I'] + [''] * 12,
        head1, head2,
    ]
    for t in sorted(trips, key=lambda item: (item.get('start_time') or '', item.get('id') or 0)):
        start = parse_dt(t.get('start_time'))
        end = parse_dt(t.get('end_time'))
        same_br = t.get('origin_br') and t.get('origin_br') == t.get('dest_br')
        distance = ''
        if same_br and t.get('end_km') is not None:
            distance = f"{round(float(t['end_km']) - float(t['start_km']), 2):.2f}".replace('.', ',')
        elapsed = ''
        if start and end:
            minutes = int(((end - start).total_seconds() // 60) % 1440)
            elapsed = f'{minutes // 60}:{minutes % 60:02d}'
        data.append([
            start.strftime('%d/%m/%Y') if start else '',
            t.get('vehicle_plate') or '',
            Paragraph(t.get('origin_city') or '', small),
            t.get('origin_br') or '',
            _km(t.get('start_km')),
            start.strftime('%H:%M') if start else '',
            Paragraph(t.get('dest_city') or '', small),
            t.get('dest_br') or '',
            _km(t.get('end_km')),
            end.strftime('%H:%M') if end else '',
            Paragraph(t.get('action_type') or '', small),
            distance,
            elapsed,
        ])

    widths = [22, 24, 38, 14, 18, 18, 38, 14, 18, 18, 36, 18, 22]
    scale = (doc.width) / sum(widths)
    table = Table(data, colWidths=[w * scale for w in widths], repeatRows=3)
    style = [
        ('SPAN', (0, 0), (-1, 0)),
        ('SPAN', (0, 1), (0, 2)), ('SPAN', (1, 1), (1, 2)), ('SPAN', (2, 1), (2, 2)),
        ('SPAN', (3, 1), (5, 1)), ('SPAN', (6, 1), (6, 2)), ('SPAN', (7, 1), (9, 1)),
        ('SPAN', (10, 1), (10, 2)), ('SPAN', (11, 1), (11, 2)), ('SPAN', (12, 1), (12, 2)),
        ('BACKGROUND', (0, 0), (-1, 0), COMPANY),
        ('BACKGROUND', (0, 1), (-1, 2), NAVY),
        ('TEXTCOLOR', (0, 1), (-1, 2), colors.white),
        ('BACKGROUND', (11, 3), (12, -1), CALC),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.black),
    ]
    table.setStyle(TableStyle(style))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()
