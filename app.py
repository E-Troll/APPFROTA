"""
Vehicle Mileage Tracking Web Application (App Veículo)
Main Flask application routing, API endpoints, file uploads and report exports.
"""

import os
import io
import csv
import hmac
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify, send_from_directory,
    Response, abort, make_response, redirect
)

import database
from services.image_service import (
    process_and_save_odometer_photo, allowed_file,
    DEFAULT_UPLOAD_FOLDER
)
from services.export_excel import generate_trips_excel, parse_dt
from services.export_pdf import generate_trips_pdf
from services.supabase_storage import delete_photos, is_configured as storage_is_configured, signed_photo_url, store_photo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Initialize database on startup
database.init_db()


# ---------------------------------------------------------
# Web Pages & Static Serving
# ---------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serves uploaded odometer photos securely."""
    if storage_is_configured():
        return redirect(signed_photo_url(filename))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ---------------------------------------------------------
# API Endpoints: Trips & Flow
# ---------------------------------------------------------

@app.route('/api/active-trip', methods=['GET'])
def api_active_trip():
    """Returns currently active trip if one exists."""
    trip = database.get_active_trip()
    return jsonify({'success': True, 'trip': trip})


@app.route('/api/trips/start', methods=['POST'])
def api_start_trip():
    """Starts a new trip (Saída)."""
    try:
        plate = request.form.get('vehicle_plate', '').strip().upper()
        driver = request.form.get('driver_name', '').strip()
        model = request.form.get('vehicle_model', '').strip()
        purpose = request.form.get('purpose', '').strip()
        origin_city = request.form.get('origin_city', '').strip()
        origin_br = request.form.get('origin_br', '').strip()
        action_type = request.form.get('action_type', '').strip()
        start_km_raw = request.form.get('start_km', '').strip().replace(',', '.')
        start_time = request.form.get('start_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Validation
        if not plate:
            return jsonify({'success': False, 'error': 'O recurso (sigla) é obrigatório.'}), 400
        if not origin_city:
            return jsonify({'success': False, 'error': 'A cidade de origem é obrigatória.'}), 400
        if not origin_br:
            return jsonify({'success': False, 'error': 'A BR de origem é obrigatória.'}), 400
        if not start_km_raw:
            return jsonify({'success': False, 'error': 'A quilometragem inicial é obrigatória.'}), 400

        try:
            start_km = float(start_km_raw)
            if start_km < 0:
                raise ValueError()
        except ValueError:
            return jsonify({'success': False, 'error': 'Quilometragem inicial inválida.'}), 400

        # Check if there is already an active trip
        active = database.get_active_trip()
        if active:
            return jsonify({
                'success': False,
                'error': f"Já existe uma viagem em andamento (Recurso: {active['vehicle_plate']}, ID #{active['id']}). Finalize-a antes de iniciar outra."
            }), 400

        # Photo validation
        if 'photo' not in request.files or not request.files['photo'].filename:
            return jsonify({'success': False, 'error': 'A foto do odômetro de saída é obrigatória.'}), 400

        photo_file = request.files['photo']
        if not allowed_file(photo_file.filename):
            return jsonify({'success': False, 'error': 'Formato de imagem inválido. Use JPG, PNG ou WEBP.'}), 400

        # Process and watermark image
        saved_filename = process_and_save_odometer_photo(
            file_storage=photo_file,
            stage_label='SAÍDA',
            km_value=start_km,
            plate=plate,
            driver_name=driver,
            timestamp_str=start_time,
            upload_folder=app.config['UPLOAD_FOLDER']
        )
        saved_filename = store_photo(saved_filename, app.config['UPLOAD_FOLDER'])

        trip_id = database.create_trip({
            'vehicle_plate': plate,
            'vehicle_model': model,
            'driver_name': driver,
            'purpose': purpose,
            'start_time': start_time,
            'start_km': start_km,
            'start_photo': saved_filename,
            'origin_city': origin_city,
            'origin_br': origin_br,
            'action_type': action_type
        })

        return jsonify({
            'success': True,
            'trip_id': trip_id,
            'message': 'Viagem iniciada com sucesso!'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>/stop', methods=['POST'])
def api_add_stop(trip_id):
    """Registers a stop/pause during an active trip."""
    try:
        trip = database.get_trip_by_id(trip_id)
        if not trip:
            return jsonify({'success': False, 'error': 'Viagem não encontrada.'}), 404
        if trip['status'] != 'EM_ANDAMENTO':
            return jsonify({'success': False, 'error': 'Apenas viagens em andamento aceitam registro de parada.'}), 400

        stop_km_raw = request.form.get('stop_km', '').strip().replace(',', '.')
        reason = request.form.get('reason', '').strip()
        stop_time = request.form.get('stop_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if not stop_km_raw:
            return jsonify({'success': False, 'error': 'A quilometragem no momento da parada é obrigatória.'}), 400

        try:
            stop_km = float(stop_km_raw)
        except ValueError:
            return jsonify({'success': False, 'error': 'Quilometragem da parada inválida.'}), 400

        start_km = float(trip['start_km'])
        if stop_km < start_km:
            return jsonify({
                'success': False,
                'error': f"Quilometragem da parada ({stop_km} km) não pode ser menor que a inicial ({start_km} km)."
            }), 400

        # Check against previous stops
        if trip.get('stops'):
            max_prev_stop = max(float(s['stop_km']) for s in trip['stops'])
            if stop_km < max_prev_stop:
                return jsonify({
                    'success': False,
                    'error': f"Quilometragem da parada ({stop_km} km) não pode ser menor que a parada anterior ({max_prev_stop} km)."
                }), 400

        # Photo validation
        if 'photo' not in request.files or not request.files['photo'].filename:
            return jsonify({'success': False, 'error': 'A foto do odômetro na parada é obrigatória.'}), 400

        photo_file = request.files['photo']
        if not allowed_file(photo_file.filename):
            return jsonify({'success': False, 'error': 'Formato de imagem inválido. Use JPG, PNG ou WEBP.'}), 400

        saved_filename = process_and_save_odometer_photo(
            file_storage=photo_file,
            stage_label='PARADA',
            km_value=stop_km,
            plate=trip['vehicle_plate'],
            driver_name=trip['driver_name'],
            extra_text=f"MOTIVO: {reason}" if reason else "",
            timestamp_str=stop_time,
            upload_folder=app.config['UPLOAD_FOLDER']
        )
        saved_filename = store_photo(saved_filename, app.config['UPLOAD_FOLDER'])

        stop_id = database.add_stop_to_trip(trip_id, {
            'stop_time': stop_time,
            'stop_km': stop_km,
            'reason': reason,
            'photo': saved_filename
        })

        return jsonify({
            'success': True,
            'stop_id': stop_id,
            'message': 'Parada registrada com sucesso!'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>/finish', methods=['POST'])
def api_finish_trip(trip_id):
    """Encerrar viagem (Chegada)."""
    try:
        trip = database.get_trip_by_id(trip_id)
        if not trip:
            return jsonify({'success': False, 'error': 'Viagem não encontrada.'}), 404
        if trip['status'] != 'EM_ANDAMENTO':
            return jsonify({'success': False, 'error': 'Esta viagem já foi finalizada ou cancelada.'}), 400

        end_km_raw = request.form.get('end_km', '').strip().replace(',', '.')
        end_time = request.form.get('end_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dest_city = request.form.get('dest_city', '').strip()
        dest_br = request.form.get('dest_br', '').strip()

        if not dest_city or not dest_br:
            return jsonify({'success': False, 'error': 'A cidade e a BR de destino são obrigatórias.'}), 400
        if not end_km_raw:
            return jsonify({'success': False, 'error': 'A quilometragem final é obrigatória.'}), 400

        try:
            end_km = float(end_km_raw)
        except ValueError:
            return jsonify({'success': False, 'error': 'Quilometragem final inválida.'}), 400

        start_km = float(trip['start_km'])
        if end_km < start_km:
            return jsonify({
                'success': False,
                'error': f"Quilometragem final ({end_km} km) não pode ser menor que a inicial ({start_km} km)."
            }), 400

        # Check stops
        if trip.get('stops'):
            max_stop = max(float(s['stop_km']) for s in trip['stops'])
            if end_km < max_stop:
                return jsonify({
                    'success': False,
                    'error': f"Quilometragem final ({end_km} km) não pode ser menor que a última parada ({max_stop} km)."
                }), 400

        # Photo validation
        if 'photo' not in request.files or not request.files['photo'].filename:
            return jsonify({'success': False, 'error': 'A foto de chegada do odômetro é obrigatória.'}), 400

        photo_file = request.files['photo']
        if not allowed_file(photo_file.filename):
            return jsonify({'success': False, 'error': 'Formato de imagem inválido. Use JPG, PNG ou WEBP.'}), 400

        saved_filename = process_and_save_odometer_photo(
            file_storage=photo_file,
            stage_label='CHEGADA',
            km_value=end_km,
            plate=trip['vehicle_plate'],
            driver_name=trip['driver_name'],
            timestamp_str=end_time,
            upload_folder=app.config['UPLOAD_FOLDER']
        )
        saved_filename = store_photo(saved_filename, app.config['UPLOAD_FOLDER'])

        total_km = database.finish_trip(trip_id, {
            'end_time': end_time,
            'end_km': end_km,
            'end_photo': saved_filename,
            'dest_city': dest_city,
            'dest_br': dest_br
        })

        return jsonify({
            'success': True,
            'total_km': total_km,
            'message': f'Viagem finalizada com sucesso! Total percorrido: {total_km} km.'
        })

    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>/cancel', methods=['POST'])
def api_cancel_trip(trip_id):
    """Cancela uma viagem ativa."""
    try:
        trip = database.get_trip_by_id(trip_id)
        if not trip:
            return jsonify({'success': False, 'error': 'Viagem não encontrada.'}), 404
        database.cancel_trip(trip_id)
        return jsonify({'success': True, 'message': 'Viagem cancelada com sucesso.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>', methods=['DELETE'])
def api_delete_trip(trip_id):
    """Exclui uma viagem e remove suas fotos do servidor."""
    try:
        photos = database.delete_trip(trip_id)
        delete_photos(photos, upload_folder=app.config['UPLOAD_FOLDER'])
        return jsonify({'success': True, 'message': 'Viagem excluída com sucesso.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips', methods=['GET'])
def api_list_trips():
    """Lists trips with optional filters and summary stats."""
    month = request.args.get('month')
    search = request.args.get('search')
    status = request.args.get('status')

    trips = database.list_trips(month=month, search=search, status=status)
    stats = database.get_summary_stats(month=month)
    available_months = database.get_available_months()

    return jsonify({
        'success': True,
        'trips': trips,
        'stats': stats,
        'available_months': available_months
    })


@app.route('/api/trips/<int:trip_id>', methods=['GET'])
def api_get_trip_details(trip_id):
    """Returns details of a specific trip."""
    trip = database.get_trip_by_id(trip_id)
    if not trip:
        return jsonify({'success': False, 'error': 'Viagem não encontrada.'}), 404
    return jsonify({'success': True, 'trip': trip})


# ---------------------------------------------------------
# Export Endpoints: Excel, PDF, CSV
# ---------------------------------------------------------

@app.route('/api/export/excel', methods=['GET'])
def export_excel():
    """Generates and serves Excel report (.xlsx)."""
    month = request.args.get('month')
    search = request.args.get('search')
    status = request.args.get('status')

    trips = database.list_trips(month=month, search=search, status=status)
    base_url = request.host_url.rstrip('/')

    xlsx_bytes = generate_trips_excel(trips, month_filter=month, base_url=base_url)

    filename_suffix = month if month else 'geral'
    filename = f"relatorio_viagens_{filename_suffix}.xlsx"

    response = make_response(xlsx_bytes)
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@app.route('/api/export/pdf', methods=['GET'])
def export_pdf():
    """Generates and serves PDF report."""
    month = request.args.get('month')
    search = request.args.get('search')
    status = request.args.get('status')

    trips = database.list_trips(month=month, search=search, status=status)
    base_url = request.host_url.rstrip('/')

    pdf_bytes = generate_trips_pdf(trips, month_filter=month, base_url=base_url)

    filename_suffix = month if month else 'geral'
    filename = f"relatorio_viagens_{filename_suffix}.pdf"

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Generates and serves CSV report formatted for Brazilian Excel."""
    month = request.args.get('month')
    search = request.args.get('search')
    status = request.args.get('status')

    trips = database.list_trips(month=month, search=search, status=status)
    base_url = request.host_url.rstrip('/')

    output = io.StringIO()
    # Write UTF-8 BOM so Excel opens with proper accented characters
    output.write('\ufeff')

    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        'Dia', 'Recurso (SIGLA)', 'Cidade Origem', 'Origem BR', 'Origem KM', 'Hora Saída',
        'Cidade Destino', 'Destino BR', 'Destino KM', 'Hora Chegada', 'Tipo de Ação',
        'Distância', 'Tempo de Deslocamento'
    ])

    def fmt_km(value):
        return str(value).replace('.', ',') if value is not None else ''

    for t in sorted(trips, key=lambda item: (item.get('start_time') or '', item.get('id') or 0)):
        start = parse_dt(t.get('start_time'))
        end = parse_dt(t.get('end_time'))
        same_br = t.get('origin_br') and t.get('origin_br') == t.get('dest_br')
        distance = ''
        if same_br and t.get('end_km') is not None:
            distance = fmt_km(round(float(t['end_km']) - float(t['start_km']), 2))
        elapsed = ''
        if start and end:
            minutes = int(((end - start).total_seconds() // 60) % 1440)
            elapsed = f"{minutes // 60}:{minutes % 60:02d}"
        writer.writerow([
            start.strftime('%d/%m/%Y') if start else '',
            t.get('vehicle_plate', ''),
            t.get('origin_city') or '',
            t.get('origin_br') or '',
            fmt_km(t.get('start_km')),
            start.strftime('%H:%M') if start else '',
            t.get('dest_city') or '',
            t.get('dest_br') or '',
            fmt_km(t.get('end_km')),
            end.strftime('%H:%M') if end else '',
            t.get('action_type') or '',
            distance,
            elapsed
        ])

    csv_data = output.getvalue().encode('utf-8-sig')
    filename_suffix = month if month else 'geral'
    filename = f"relatorio_viagens_{filename_suffix}.csv"

    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@app.route('/api/cron/cleanup', methods=['GET'])
def api_cleanup_expired_trips():
    secret = os.environ.get('CRON_SECRET')
    if not secret:
        return jsonify({'success': False, 'error': 'CRON_SECRET não configurado.'}), 503
    if not hmac.compare_digest(request.headers.get('Authorization', ''), f'Bearer {secret}'):
        return jsonify({'success': False, 'error': 'Não autorizado.'}), 401
    deleted_trips, photos = database.delete_expired_trips(days=45)
    delete_photos(photos, upload_folder=app.config['UPLOAD_FOLDER'])
    return jsonify({'success': True, 'deleted_trips': deleted_trips, 'deleted_photos': len(photos)})


if __name__ == '__main__':
    print("Iniciando Servidor de Controle de Quilometragem...")
    print("Acesse no navegador: http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, debug=True)
