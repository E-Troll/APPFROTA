"""
Excel Export Service for Vehicle Mileage Tracking
Generates styled, professional .xlsx workbooks with summary cards,
hyperlinks to odometer photos, and automatic formulas using openpyxl.
"""

import io
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def format_datetime(iso_str):
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


def generate_trips_excel(trips, month_filter=None, base_url="http://localhost:5000"):
    """
    Builds an in-memory .xlsx file and returns bytes.
    trips: list of dicts with trip data and nested stops.
    month_filter: 'YYYY-MM' or None
    base_url: server base URL for clickable photo links
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Relatório de Viagens"
    ws.views.sheetView[0].showGridLines = True

    # Styling definitions
    font_title = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    font_sub = Font(name="Calibri", size=10, italic=True, color="475569")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=10, color="0F172A")
    font_bold = Font(name="Calibri", size=10, bold=True, color="0F172A")
    font_link = Font(name="Calibri", size=10, underline="single", color="2563EB")

    fill_title = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")     # Deep blue
    fill_sub = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")       # Light gray
    fill_header = PatternFill(start_color="334155", end_color="334155", fill_type="solid")    # Dark slate
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")     # Subtle alternating
    fill_total = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")     # Soft indigo total

    thin_border_side = Side(border_style="thin", color="CBD5E1")
    border_all = Border(
        left=thin_border_side, right=thin_border_side,
        top=thin_border_side, bottom=thin_border_side
    )
    border_total = Border(
        top=Side(border_style="thin", color="64748B"),
        bottom=Side(border_style="double", color="1E3A8A")
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    num_format_km = "#,##0.0"

    # Row 1: Main Title
    period_label = f"Mês: {month_filter}" if month_filter else "Todos os Períodos"
    ws.merge_cells("A1:O1")
    title_cell = ws["A1"]
    title_cell.value = "RELATÓRIO DE CONTROLE DE QUILOMETRAGEM - VEÍCULOS"
    title_cell.font = font_title
    title_cell.fill = fill_title
    title_cell.alignment = align_center
    ws.row_dimensions[1].height = 36

    # Row 2: Subtitle
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    ws.merge_cells("A2:O2")
    sub_cell = ws["A2"]
    sub_cell.value = f"Período: {period_label}   |   Gerado em: {now_str}   |   Total de Registros: {len(trips)}"
    sub_cell.font = font_sub
    sub_cell.fill = fill_sub
    sub_cell.alignment = align_center
    ws.row_dimensions[2].height = 22

    # Row 3 is an empty spacing row
    ws.row_dimensions[3].height = 8

    # Row 4: Headers
    headers = [
        ("ID", align_center),
        ("Data Início", align_center),
        ("Placa", align_center),
        ("Modelo Veículo", align_left),
        ("Condutor", align_left),
        ("Finalidade / Rota", align_left),
        ("KM Inicial", align_right),
        ("Foto Saída", align_center),
        ("Qtd. Paradas", align_center),
        ("Resumo Paradas", align_left),
        ("Data Término", align_center),
        ("KM Final", align_right),
        ("Foto Chegada", align_center),
        ("Total KM", align_right),
        ("Status", align_center)
    ]

    header_row_idx = 4
    ws.row_dimensions[header_row_idx].height = 26

    for col_idx, (header_text, alignment) in enumerate(headers, start=1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.value = header_text
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = alignment
        cell.border = border_all

    # Rows 5+: Data
    current_row = 5
    for i, trip in enumerate(trips):
        is_zebra = (i % 2 == 1)
        row_fill = fill_zebra if is_zebra else None

        # Build stops summary text
        stops = trip.get('stops', [])
        stops_count = len(stops)
        stops_summary_parts = []
        for s_idx, s in enumerate(stops, start=1):
            time_part = format_datetime(s.get('stop_time')).split()[-1]
            reason_part = f" ({s.get('reason')})" if s.get('reason') else ""
            stops_summary_parts.append(f"P{s_idx}: {s.get('stop_km')} km às {time_part}{reason_part}")
        stops_summary_text = " | ".join(stops_summary_parts) if stops_summary_parts else "-"

        # Status text
        status_text = trip.get('status', '')

        # Set values
        cells = [
            (1, trip.get('id'), align_center, None),
            (2, format_datetime(trip.get('start_time')), align_center, None),
            (3, trip.get('vehicle_plate', ''), align_center, None),
            (4, trip.get('vehicle_model') or "-", align_left, None),
            (5, trip.get('driver_name', ''), align_left, None),
            (6, trip.get('purpose') or "-", align_left, None),
            (7, trip.get('start_km'), align_right, num_format_km),
            (8, "Ver Foto", align_center, "LINK_START"),
            (9, stops_count, align_center, None),
            (10, stops_summary_text, align_left, None),
            (11, format_datetime(trip.get('end_time')), align_center, None),
            (12, trip.get('end_km') if trip.get('end_km') is not None else "-", align_right, num_format_km if trip.get('end_km') is not None else None),
            (13, "Ver Foto" if trip.get('end_photo') else "-", align_center, "LINK_END"),
            (14, trip.get('total_km') if trip.get('total_km') is not None else "-", align_right, num_format_km if trip.get('total_km') is not None else None),
            (15, status_text, align_center, None)
        ]

        ws.row_dimensions[current_row].height = 22

        for col_idx, val, alignment, special in cells:
            cell = ws.cell(row=current_row, column=col_idx)
            cell.alignment = alignment
            cell.border = border_all
            if row_fill:
                cell.fill = row_fill

            if special == "LINK_START" and trip.get('start_photo'):
                photo_url = f"{base_url}/uploads/{trip.get('start_photo')}"
                cell.value = "📸 Foto Saída"
                cell.hyperlink = photo_url
                cell.font = font_link
            elif special == "LINK_END" and trip.get('end_photo'):
                photo_url = f"{base_url}/uploads/{trip.get('end_photo')}"
                cell.value = "📸 Foto Chegada"
                cell.hyperlink = photo_url
                cell.font = font_link
            else:
                cell.value = val
                cell.font = font_data
                if special:
                    cell.number_format = special

        current_row += 1

    # Totals Row
    total_row = current_row
    ws.row_dimensions[total_row].height = 26

    # Merge A to M for label
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=13)
    lbl_cell = ws.cell(row=total_row, column=1)
    lbl_cell.value = "TOTAL KM PERCORRIDO NO PERÍODO:"
    lbl_cell.font = font_bold
    lbl_cell.alignment = Alignment(horizontal="right", vertical="center")
    lbl_cell.fill = fill_total

    for c in range(1, 14):
        ws.cell(row=total_row, column=c).border = border_total
        ws.cell(row=total_row, column=c).fill = fill_total

    # Formula for Total KM
    km_cell = ws.cell(row=total_row, column=14)
    if len(trips) > 0:
        km_cell.value = f"=SUM(N5:N{total_row - 1})"
    else:
        km_cell.value = 0.0
    km_cell.font = font_bold
    km_cell.alignment = align_right
    km_cell.number_format = num_format_km
    km_cell.fill = fill_total
    km_cell.border = border_total

    # Empty cell for status in total row
    status_total_cell = ws.cell(row=total_row, column=15)
    status_total_cell.value = ""
    status_total_cell.fill = fill_total
    status_total_cell.border = border_total

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Skip title row and total merged row
            if cell.row in (1, 2, total_row):
                continue
            if cell.value:
                val_str = str(cell.value)
                if len(val_str) > max_len:
                    max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # Specific minimum widths for better layout
    ws.column_dimensions["A"].width = 8   # ID
    ws.column_dimensions["B"].width = 18  # Data Início
    ws.column_dimensions["C"].width = 13  # Placa
    ws.column_dimensions["D"].width = 20  # Modelo
    ws.column_dimensions["E"].width = 22  # Condutor
    ws.column_dimensions["F"].width = 24  # Destino
    ws.column_dimensions["G"].width = 14  # KM Inicial
    ws.column_dimensions["H"].width = 16  # Link Saída
    ws.column_dimensions["I"].width = 13  # Qtd Paradas
    ws.column_dimensions["J"].width = 32  # Resumo Paradas
    ws.column_dimensions["K"].width = 18  # Data Término
    ws.column_dimensions["L"].width = 14  # KM Final
    ws.column_dimensions["M"].width = 16  # Link Chegada
    ws.column_dimensions["N"].width = 15  # Total KM
    ws.column_dimensions["O"].width = 16  # Status

    # Write to memory buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
