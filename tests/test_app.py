"""
Comprehensive Test Suite for Vehicle Mileage Tracking Application
Tests:
- Database schema and integrity
- Photo upload and Pillow watermark stamping
- Start trip (Saída) workflow and validations
- Stop trip (Parada) workflow and validations
- Finish trip (Chegada) workflow, distance calculations, and validations
- Month filters and search queries
- Report exports: Excel (.xlsx), PDF, and CSV
- Trip deletion and image cleanup
"""

import io
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

import app as flask_app
import database
from services.image_service import process_and_save_odometer_photo, allowed_file
import openpyxl


def create_dummy_image_stream(width=400, height=300, color=(100, 150, 200)):
    """Creates an in-memory JPEG image stream for testing uploads."""
    img = Image.new('RGB', (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf


class DummyFileStorage:
    """Simulates Werkzeug FileStorage for unit testing image processing."""
    def __init__(self, stream, filename='test_odometer.jpg'):
        self.stream = stream
        self.filename = filename


class TestMileageApp(unittest.TestCase):

    def setUp(self):
        # Create unique temporary directory for test DB and uploads
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, 'test_odometro.db')
        self.test_upload_folder = os.path.join(self.test_dir, 'uploads')
        os.makedirs(self.test_upload_folder, exist_ok=True)

        # Configure app for testing
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['UPLOAD_FOLDER'] = self.test_upload_folder
        database.DEFAULT_DB_PATH = self.test_db_path

        # Initialize test DB
        database.init_db(self.test_db_path)

        self.client = flask_app.app.test_client()

    def tearDown(self):
        # Clean up temporary test files
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1. Image Service & Watermark Tests
    # -------------------------------------------------------------

    def test_allowed_file(self):
        self.assertTrue(allowed_file('photo.jpg'))
        self.assertTrue(allowed_file('photo.jpeg'))
        self.assertTrue(allowed_file('photo.png'))
        self.assertTrue(allowed_file('photo.webp'))
        self.assertFalse(allowed_file('photo.pdf'))
        self.assertFalse(allowed_file('photo.exe'))
        self.assertFalse(allowed_file('noextension'))

    def test_image_watermarking(self):
        stream = create_dummy_image_stream(600, 450)
        file_storage = DummyFileStorage(stream)

        filename = process_and_save_odometer_photo(
            file_storage=file_storage,
            stage_label='SAÍDA',
            km_value=12500.5,
            plate='BRA2E19',
            driver_name='Carlos Alberto',
            upload_folder=self.test_upload_folder
        )

        saved_path = os.path.join(self.test_upload_folder, filename)
        self.assertTrue(os.path.exists(saved_path))

        # Inspect resulting image
        with Image.open(saved_path) as img:
            self.assertEqual(img.format, 'JPEG')
            self.assertEqual(img.size, (600, 450))

    # -------------------------------------------------------------
    # 2. Trip Start (Saída) Tests
    # -------------------------------------------------------------

    def test_start_trip_missing_fields(self):
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': '',
            'driver_name': 'Carlos',
            'start_km': '1000'
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn('O recurso (sigla) é obrigatório', data['error'])

    def test_start_trip_missing_photo(self):
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'ABC-1234',
            'origin_city': 'Salvador',
            'origin_br': '324',
            'driver_name': 'Carlos',
            'start_km': '1000'
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn('foto do odômetro de saída', data['error'])

    def test_start_trip_rejects_origin_city_and_br_mismatch(self):
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'ABC-1234',
            'origin_city': 'Salvador',
            'origin_br': '116',
            'start_km': '1000'
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('não corresponde', res.get_json()['error'])

    def test_start_trip_success_and_prevent_duplicate_active(self):
        img_buf = create_dummy_image_stream()
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'abc-1234',
            'vehicle_model': 'Fiat Strada',
            'driver_name': 'Carlos Alberto',
            'purpose': 'Entrega de Peças',
            'origin_city': 'Salvador',
            'origin_br': '324',
            'start_km': '10500.0',
            'start_time': '2026-10-01T08:00',
            'photo': (img_buf, 'odometro_saida.jpg')
        }, content_type='multipart/form-data')

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        trip_id = data['trip_id']
        self.assertIsInstance(trip_id, int)

        # Check DB status
        trip = database.get_trip_by_id(trip_id, self.test_db_path)
        self.assertIsNotNone(trip)
        self.assertEqual(trip['vehicle_plate'], 'ABC-1234')  # Uppercase
        self.assertEqual(trip['status'], 'EM_ANDAMENTO')
        self.assertEqual(trip['start_km'], 10500.0)
        self.assertEqual(trip['start_time'], '2026-10-01T08:00')
        self.assertRegex(trip['start_photo'], r'^saida_20261001_080000_[a-f0-9]{8}\.jpg$')
        self.assertTrue(os.path.exists(os.path.join(self.test_upload_folder, trip['start_photo'])))

        # Attempt to start a 2nd trip while 1st is still EM_ANDAMENTO
        img_buf2 = create_dummy_image_stream()
        res2 = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'XYZ-9999',
            'driver_name': 'Outro Motorista',
            'origin_city': 'Antônio Cardoso',
            'origin_br': '116',
            'start_km': '20000.0',
            'photo': (img_buf2, 'odometro_saida2.jpg')
        }, content_type='multipart/form-data')

        self.assertEqual(res2.status_code, 400)
        data2 = res2.get_json()
        self.assertIn('Já existe uma viagem em andamento', data2['error'])

    def test_start_trip_cleans_up_photo_when_database_save_fails(self):
        with patch.object(database, 'create_trip', side_effect=RuntimeError('database unavailable')):
            res = self.client.post('/api/trips/start', data={
                'vehicle_plate': 'ABC-1234',
                'origin_city': 'Salvador',
                'origin_br': '324',
                'start_km': '1000',
                'start_time': '2026-10-01T08:15',
                'photo': (create_dummy_image_stream(), 'start.jpg')
            }, content_type='multipart/form-data')

        self.assertEqual(res.status_code, 500)
        self.assertIn('database unavailable', res.get_json()['error'])
        self.assertEqual(os.listdir(self.test_upload_folder), [])

    # -------------------------------------------------------------
    # 3. Trip Stops (Parada) Tests
    # -------------------------------------------------------------

    def test_trip_stop_workflow_and_validations(self):
        # Start trip
        img_buf = create_dummy_image_stream()
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'ABC-1234',
            'driver_name': 'Carlos',
            'origin_city': 'Feira de Santana',
            'origin_br': '324',
            'start_km': '1000.0',
            'photo': (img_buf, 'start.jpg')
        }, content_type='multipart/form-data')
        trip_id = res.get_json()['trip_id']

        # Invalid stop KM < start KM
        img_stop_buf = create_dummy_image_stream()
        res_invalid = self.client.post(f'/api/trips/{trip_id}/stop', data={
            'stop_km': '950.0',
            'reason': 'Almoço',
            'photo': (img_stop_buf, 'stop1.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(res_invalid.status_code, 400)
        self.assertIn('não pode ser menor', res_invalid.get_json()['error'])

        # Valid 1st stop
        img_stop1 = create_dummy_image_stream()
        res_stop1 = self.client.post(f'/api/trips/{trip_id}/stop', data={
            'stop_km': '1050.0',
            'reason': 'Almoço em Campinas',
            'stop_time': '2026-10-01T12:30',
            'photo': (img_stop1, 'stop1.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(res_stop1.status_code, 200)

        # Valid 2nd stop
        img_stop2 = create_dummy_image_stream()
        res_stop2 = self.client.post(f'/api/trips/{trip_id}/stop', data={
            'stop_km': '1120.0',
            'reason': 'Abastecimento',
            'photo': (img_stop2, 'stop2.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(res_stop2.status_code, 200)

        # Invalid 3rd stop: KM < 2nd stop KM
        img_stop3 = create_dummy_image_stream()
        res_invalid_stop = self.client.post(f'/api/trips/{trip_id}/stop', data={
            'stop_km': '1100.0',
            'reason': 'Pedágio',
            'photo': (img_stop3, 'stop3.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(res_invalid_stop.status_code, 400)
        self.assertIn('não pode ser menor que a parada anterior', res_invalid_stop.get_json()['error'])

        # Verify DB stops
        trip = database.get_trip_by_id(trip_id, self.test_db_path)
        self.assertEqual(len(trip['stops']), 2)
        self.assertEqual(trip['stops'][0]['stop_km'], 1050.0)
        self.assertEqual(trip['stops'][1]['stop_km'], 1120.0)
        self.assertEqual(trip['stops'][0]['stop_time'], '2026-10-01T12:30')
        self.assertRegex(trip['stops'][0]['photo'], r'^parada_20261001_123000_[a-f0-9]{8}\.jpg$')
        self.assertTrue(os.path.exists(os.path.join(self.test_upload_folder, trip['stops'][0]['photo'])))

    # -------------------------------------------------------------
    # 4. Trip Finish (Chegada) Tests
    # -------------------------------------------------------------

    def test_finish_trip_and_distance_calculation(self):
        # Start trip at 5000.0 km
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'DEF-5678',
            'driver_name': 'Mariana Souza',
            'origin_city': 'Jequié',
            'origin_br': '116',
            'start_km': '5000.0',
            'photo': (create_dummy_image_stream(), 'start.jpg')
        }, content_type='multipart/form-data')
        trip_id = res.get_json()['trip_id']

        # Add a stop at 5100.0 km
        self.client.post(f'/api/trips/{trip_id}/stop', data={
            'stop_km': '5100.0',
            'reason': 'Pausa descanso',
            'photo': (create_dummy_image_stream(), 'stop.jpg')
        }, content_type='multipart/form-data')

        # Invalid end KM < stop KM
        res_inv = self.client.post(f'/api/trips/{trip_id}/finish', data={
            'end_km': '5080.0',
            'dest_city': 'Feira de Santana',
            'dest_br': '324',
            'photo': (create_dummy_image_stream(), 'end.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(res_inv.status_code, 400)
        self.assertIn('não pode ser menor que a última parada', res_inv.get_json()['error'])

        # Valid finish at 5250.5 km
        res_finish = self.client.post(f'/api/trips/{trip_id}/finish', data={
            'end_km': '5250.5',
            'end_time': '2026-10-01T18:30',
            'dest_city': 'Feira de Santana',
            'dest_br': '324',
            'photo': (create_dummy_image_stream(), 'end.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(res_finish.status_code, 200)
        finish_data = res_finish.get_json()
        self.assertEqual(finish_data['total_km'], 250.5)

        # Verify DB
        trip = database.get_trip_by_id(trip_id, self.test_db_path)
        self.assertEqual(trip['status'], 'FINALIZADA')
        self.assertEqual(trip['end_km'], 5250.5)
        self.assertEqual(trip['total_km'], 250.5)
        self.assertEqual(trip['end_time'], '2026-10-01T18:30')
        self.assertRegex(trip['end_photo'], r'^chegada_20261001_183000_[a-f0-9]{8}\.jpg$')
        self.assertTrue(os.path.exists(os.path.join(self.test_upload_folder, trip['end_photo'])))

    # -------------------------------------------------------------
    # 5. Export Tests (Excel, PDF, CSV)
    # -------------------------------------------------------------

    def test_exports_excel_pdf_and_csv(self):
        # Create a completed trip in 2026-10
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'GHI-9012',
            'driver_name': 'Roberto Silva',
            'origin_city': 'Salvador',
            'origin_br': '324',
            'start_km': '1000.0',
            'start_time': '2026-10-02 09:00:00',
            'photo': (create_dummy_image_stream(), 's.jpg')
        }, content_type='multipart/form-data')
        t_id = res.get_json()['trip_id']

        self.client.post(f'/api/trips/{t_id}/stop', data={
            'stop_km': '1050.0',
            'reason': 'Almoço',
            'photo': (create_dummy_image_stream(), 'p.jpg')
        }, content_type='multipart/form-data')

        self.client.post(f'/api/trips/{t_id}/finish', data={
            'end_km': '1200.0',
            'end_time': '2026-10-02 17:00:00',
            'dest_city': 'Feira de Santana',
            'dest_br': '324',
            'photo': (create_dummy_image_stream(), 'c.jpg')
        }, content_type='multipart/form-data')

        # 5.1 Test Excel Export
        res_excel = self.client.get('/api/export/excel?month=2026-10')
        self.assertEqual(res_excel.status_code, 200)
        self.assertEqual(
            res_excel.headers['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertTrue(len(res_excel.data) > 1000)

        # Verify valid openpyxl workbook
        wb = openpyxl.load_workbook(io.BytesIO(res_excel.data))
        ws = wb.active
        self.assertEqual(ws.title, 'RELATÓRIO INSPEÇÃO')
        self.assertEqual(ws['A4'].value, 'REGISTRO DE INSPEÇÕES')
        # Check that plate appears in table
        found_plate = any('GHI-9012' in str(cell.value) for row in ws.rows for cell in row)
        self.assertTrue(found_plate)

        # 5.2 Test PDF Export
        res_pdf = self.client.get('/api/export/pdf?month=2026-10')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers['Content-Type'], 'application/pdf')
        # Check PDF magic header %PDF-
        self.assertTrue(res_pdf.data.startswith(b'%PDF-'))
        self.assertTrue(len(res_pdf.data) > 1500)

        # 5.3 Test CSV Export
        res_csv = self.client.get('/api/export/csv?month=2026-10')
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn('text/csv', res_csv.headers['Content-Type'])
        csv_text = res_csv.data.decode('utf-8-sig')
        self.assertIn('GHI-9012', csv_text)
        self.assertIn('Salvador', csv_text)
        self.assertIn('Feira de Santana', csv_text)
        self.assertIn('200,0', csv_text)  # Total KM formatted

    # -------------------------------------------------------------
    # 6. Delete Trip & Image Cleanup Test
    # -------------------------------------------------------------

    def test_delete_trip_and_cleanup_files(self):
        # Start and finish a trip
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'DEL-1111',
            'driver_name': 'Tester',
            'origin_city': 'Salvador',
            'origin_br': '324',
            'start_km': '100.0',
            'photo': (create_dummy_image_stream(), 's.jpg')
        }, content_type='multipart/form-data')
        t_id = res.get_json()['trip_id']

        trip = database.get_trip_by_id(t_id, self.test_db_path)
        start_photo = trip['start_photo']
        photo_path = os.path.join(self.test_upload_folder, start_photo)
        self.assertTrue(os.path.exists(photo_path))

        # Delete trip via API
        del_res = self.client.delete(f'/api/trips/{t_id}')
        self.assertEqual(del_res.status_code, 200)

        # Trip should be gone from DB
        self.assertIsNone(database.get_trip_by_id(t_id, self.test_db_path))

        # Photo should be removed from disk
        self.assertFalse(os.path.exists(photo_path))

    # -------------------------------------------------------------
    # 7. UI Route & Image Serving Tests
    # -------------------------------------------------------------

    def test_index_route(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Controle de KM COR', res.data)
        self.assertIn(b'Registrar Sa\xc3\xadda (Nova Viagem)', res.data)

    def test_serve_uploaded_image(self):
        img_buf = create_dummy_image_stream(200, 200)
        res = self.client.post('/api/trips/start', data={
            'vehicle_plate': 'IMG-1234',
            'driver_name': 'Tester',
            'origin_city': 'Salvador',
            'origin_br': '324',
            'start_km': '10.0',
            'photo': (img_buf, 'test.jpg')
        }, content_type='multipart/form-data')
        trip_id = res.get_json()['trip_id']
        trip = database.get_trip_by_id(trip_id, self.test_db_path)

        res_img = self.client.get(f"/uploads/{trip['start_photo']}")
        self.assertEqual(res_img.status_code, 200)
        self.assertEqual(res_img.headers['Content-Type'], 'image/jpeg')
        res_img.close()


if __name__ == '__main__':
    unittest.main()
