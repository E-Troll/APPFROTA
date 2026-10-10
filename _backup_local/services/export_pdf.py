"""
PDF Export Service for Vehicle Mileage Tracking
Uses ReportLab to produce clean, executive-ready Landscape A4 reports
with KPI summary cards, structured data tables, and odometer photo references.
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and display 'Página X de Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer rule
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 30, 841.89 - 36, 30)

        # Footer text
        left_text = "Sistema de Controle de Quilometragem Veicular  |  Relatório Oficial de Auditoria"
        right_text = f"Página {self._pageNumber} de {page_count}"
        self.drawString(36, 18, left_text)
        self.drawRightString(841.89 - 36, 18, right_text)

        self.restoreState()


def format_dt(iso_str):
    if not iso_str:
        return "-"
    try:
        clean = iso_str.replace('T', ' ')
        if len(clean) > 19:
            clean = clean[:19]
        dt = datetime.strptime(clean, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%d/%m/%Y %H:%M')
    except Exception:
        return iso_str


def generate_trips_pdf(trips, month_filter=None, base_url="http://localhost:5000"):
    """
    Generates an executive-ready Landscape A4 PDF report.
    Returns bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )

    th_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=1
    )

    td_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )

    td_center = ParagraphStyle(
        'TableCellCenter',
        parent=td_style,
        alignment=1
    )

    td_right = ParagraphStyle(
        'TableCellRight',
        parent=td_style,
        alignment=2
    )

    td_bold_right = ParagraphStyle(
        'TableCellBoldRight',
        parent=td_style,
        fontName='Helvetica-Bold',
        alignment=2
    )

    story = []

    # Title & Header
    period_str = f"Mês: {month_filter}" if month_filter else "Todos os Períodos"
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")

    story.append(Paragraph("RELATÓRIO DE CONTROLE DE QUILOMETRAGEM", title_style))
    story.append(Paragraph(
        f"<b>Período:</b> {period_str} &nbsp;|&nbsp; <b>Data de Emissão:</b> {now_str} &nbsp;|&nbsp; <b>Total de Viagens:</b> {len(trips)}",
        subtitle_style
    ))
    story.append(Spacer(1, 8))

    # Calculate summary metrics
    total_trips = len(trips)
    completed_trips = sum(1 for t in trips if t.get('status') == 'FINALIZADA')
    in_progress = sum(1 for t in trips if t.get('status') == 'EM_ANDAMENTO')
    total_km = sum(float(t.get('total_km') or 0) for t in trips if t.get('status') == 'FINALIZADA' and t.get('total_km'))
    avg_km = (total_km / completed_trips) if completed_trips > 0 else 0.0

    # Summary KPI Cards Table
    kpi_data = [
        [
            Paragraph("<b>TOTAL DE VIAGENS</b>", td_center),
            Paragraph("<b>CONCLUÍDAS</b>", td_center),
            Paragraph("<b>EM ANDAMENTO</b>", td_center),
            Paragraph("<b>KM TOTAL PERCORRIDO</b>", td_center),
            Paragraph("<b>MÉDIA KM / VIAGEM</b>", td_center)
        ],
        [
            Paragraph(f"<font size=14 color='#1E3A8A'><b>{total_trips}</b></font>", td_center),
            Paragraph(f"<font size=14 color='#16A34A'><b>{completed_trips}</b></font>", td_center),
            Paragraph(f"<font size=14 color='#EAB308'><b>{in_progress}</b></font>", td_center),
            Paragraph(f"<font size=14 color='#1E3A8A'><b>{total_km:,.1f} km</b></font>".replace(',', 'X').replace('.', ',').replace('X', '.'), td_center),
            Paragraph(f"<font size=14 color='#0284C7'><b>{avg_km:,.1f} km</b></font>".replace(',', 'X').replace('.', ',').replace('X', '.'), td_center)
        ]
    ]

    card_col_w = (841.89 - 72) / 5
    kpi_table = Table(kpi_data, colWidths=[card_col_w] * 5)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 14))

    # Main Trips Data Table
    table_headers = [
        Paragraph("ID", th_style),
        Paragraph("Data Início", th_style),
        Paragraph("Veículo / Placa", th_style),
        Paragraph("Condutor", th_style),
        Paragraph("BR Origem / Finalidade / Rota", th_style),
        Paragraph("KM Início", th_style),
        Paragraph("Paradas Registradas", th_style),
        Paragraph("KM Fim", th_style),
        Paragraph("Total KM", th_style),
        Paragraph("Status", th_style)
    ]

    table_rows = [table_headers]

    for t in trips:
        # Stops summary
        stops = t.get('stops', [])
        stops_count = len(stops)
        if stops_count == 0:
            stops_text = "Sem paradas"
        else:
            parts = []
            for idx, s in enumerate(stops, 1):
                t_str = format_dt(s.get('stop_time')).split()[-1]
                parts.append(f"{idx}ª: {s.get('stop_km')} km ({t_str})")
            stops_text = "<br/>".join(parts)

        # Status text styling
        status_val = t.get('status', '')
        if status_val == 'FINALIZADA':
            status_html = "<font color='#16A34A'><b>FINALIZADA</b></font>"
        elif status_val == 'EM_ANDAMENTO':
            status_html = "<font color='#EAB308'><b>EM ANDAMENTO</b></font>"
        else:
            status_html = f"<font color='#64748B'><b>{status_val}</b></font>"

        vehicle_label = f"<b>{t.get('vehicle_plate', '')}</b>"
        if t.get('vehicle_model'):
            vehicle_label += f"<br/><font size=7 color='#64748B'>{t.get('vehicle_model')}</font>"

        km_ini = f"{t.get('start_km', 0):,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        km_end = f"{t.get('end_km', 0):,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.') if t.get('end_km') is not None else "-"
        km_tot = f"{t.get('total_km', 0):,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.') if t.get('total_km') is not None else "-"

        row = [
            Paragraph(str(t.get('id')), td_center),
            Paragraph(format_dt(t.get('start_time')), td_center),
            Paragraph(vehicle_label, td_style),
            Paragraph(t.get('driver_name', ''), td_style),
            Paragraph(" · ".join(value for value in (t.get('br_origin'), t.get('purpose')) if value) or "-", td_style),
            Paragraph(km_ini, td_right),
            Paragraph(f"<font size=7>{stops_text}</font>", td_style),
            Paragraph(km_end, td_right),
            Paragraph(f"<b>{km_tot}</b>", td_bold_right),
            Paragraph(status_html, td_center)
        ]
        table_rows.append(row)

    # Total summary row at bottom of table
    total_km_fmt = f"{total_km:,.1f} km".replace(',', 'X').replace('.', ',').replace('X', '.')
    total_row = [
        Paragraph("<b>TOTAL GERAL</b>", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph(f"<b>{total_km_fmt}</b>", td_bold_right),
        Paragraph("", td_style)
    ]
    table_rows.append(total_row)

    # Column widths summing to 770 pt (841.89 - 72 = 769.89 pt)
    col_widths = [28, 65, 85, 85, 110, 56, 130, 56, 65, 90]

    trips_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
    
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#CBD5E1')),
        # Totals row styling
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E0E7FF')),
        ('SPAN', (0, -1), (7, -1)),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#1E3A8A')),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 6),
        ('TOPPADDING', (0, -1), (-1, -1), 6),
    ]

    # Alternating row colors
    for r_idx in range(1, len(trips) + 1):
        if r_idx % 2 == 0:
            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#F8FAFC')))

    trips_table.setStyle(TableStyle(t_style))
    story.append(trips_table)
    story.append(Spacer(1, 16))

    # Photo Reference Audit Section
    story.append(Paragraph("<b>REGISTRO E REFERÊNCIA DE FOTOS DO ODÔMETRO (AUDITORIA)</b>", ParagraphStyle(
        'AuditHead', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#1E3A8A'), spaceAfter=6
    )))

    audit_headers = [
        Paragraph("Viagem", th_style),
        Paragraph("Tipo de Registro", th_style),
        Paragraph("KM Odômetro", th_style),
        Paragraph("Data/Hora Carimbada", th_style),
        Paragraph("Arquivo da Imagem no Servidor", th_style)
    ]
    audit_rows = [audit_headers]

    for t in trips:
        # Start photo
        if t.get('start_photo'):
            audit_rows.append([
                Paragraph(f"#{t['id']} - {t['vehicle_plate']}", td_center),
                Paragraph("<font color='#2563EB'><b>SAÍDA</b></font>", td_center),
                Paragraph(f"{t['start_km']} km", td_right),
                Paragraph(format_dt(t['start_time']), td_center),
                Paragraph(f"<font size=7 color='#334155'>uploads/{t['start_photo']}</font>", td_style)
            ])
        # Stops photos
        for s in t.get('stops', []):
            if s.get('photo'):
                audit_rows.append([
                    Paragraph(f"#{t['id']} - {t['vehicle_plate']}", td_center),
                    Paragraph(f"<font color='#D97706'><b>PARADA</b></font> ({s.get('reason') or 'Pausa'})", td_center),
                    Paragraph(f"{s['stop_km']} km", td_right),
                    Paragraph(format_dt(s['stop_time']), td_center),
                    Paragraph(f"<font size=7 color='#334155'>uploads/{s['photo']}</font>", td_style)
                ])
        # End photo
        if t.get('end_photo'):
            audit_rows.append([
                Paragraph(f"#{t['id']} - {t['vehicle_plate']}", td_center),
                Paragraph("<font color='#16A34A'><b>CHEGADA</b></font>", td_center),
                Paragraph(f"{t['end_km']} km", td_right),
                Paragraph(format_dt(t['end_time']), td_center),
                Paragraph(f"<font size=7 color='#334155'>uploads/{t['end_photo']}</font>", td_style)
            ])

    audit_widths = [110, 130, 80, 110, 340]
    audit_table = Table(audit_rows, colWidths=audit_widths, repeatRows=1)
    a_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]
    for r_idx in range(1, len(audit_rows)):
        if r_idx % 2 == 0:
            a_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#F8FAFC')))
    audit_table.setStyle(TableStyle(a_style))

    story.append(audit_table)

    # Build document with custom canvas for page numbers
    doc.build(story, canvasmaker=NumberedCanvas)
    buf.seek(0)
    return buf.getvalue()
