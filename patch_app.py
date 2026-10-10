import re

with open('app.py', 'r') as f:
    content = f.read()

# Replace start trip
content = re.sub(
    r"start_time = request.form.get\('start_time'\) or datetime.now\(\).strftime\('%Y-%m-%d %H:%M:%S'\)",
    "start_time = request.form.get('start_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')\n        lat = request.form.get('lat')\n        lng = request.form.get('lng')",
    content
)

content = re.sub(
    r"saved_filename = process_and_save_odometer_photo\(\n\s*file_storage=photo_file, stage_label='SAÍDA', km_value=start_km,\n\s*plate=plate, driver_name=driver, timestamp_str=start_time,\n\s*upload_folder=app.config\['UPLOAD_FOLDER'\]\n\s*\)",
    """geo_str = f"GPS: {lat}, {lng}" if lat and lng else ""
        saved_filename = process_and_save_odometer_photo(
            file_storage=photo_file, stage_label='SAÍDA', km_value=start_km,
            plate=plate, driver_name=driver, timestamp_str=start_time,
            extra_text=geo_str, upload_folder=app.config['UPLOAD_FOLDER']
        )""",
    content
)

content = re.sub(
    r"'purpose': purpose, 'start_time': start_time, 'start_km': start_km,\n\s*'start_photo': saved_filename\n\s*\}\)",
    "'purpose': purpose, 'start_time': start_time, 'start_km': start_km,\n            'start_photo': saved_filename, 'lat': lat, 'lng': lng\n        })",
    content
)

# Replace add_stop
content = re.sub(
    r"stop_time = request.form.get\('stop_time'\) or datetime.now\(\).strftime\('%Y-%m-%d %H:%M:%S'\)",
    "stop_time = request.form.get('stop_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')\n        lat = request.form.get('lat')\n        lng = request.form.get('lng')",
    content
)

content = re.sub(
    r"saved_filename = process_and_save_odometer_photo\(\n\s*file_storage=photo_file, stage_label='PARADA', km_value=stop_km,\n\s*plate=trip\['vehicle_plate'\], driver_name=trip\['driver_name'\],\n\s*extra_text=f\"MOTIVO: \{reason\}\" if reason else \"\", timestamp_str=stop_time,\n\s*upload_folder=app.config\['UPLOAD_FOLDER'\]\n\s*\)",
    """geo_str = f"GPS: {lat}, {lng}" if lat and lng else ""
        extra_info = f"MOTIVO: {reason} | {geo_str}" if reason else geo_str
        saved_filename = process_and_save_odometer_photo(
            file_storage=photo_file, stage_label='PARADA', km_value=stop_km,
            plate=trip['vehicle_plate'], driver_name=trip['driver_name'],
            extra_text=extra_info.strip(' |'), timestamp_str=stop_time,
            upload_folder=app.config['UPLOAD_FOLDER']
        )""",
    content
)

content = re.sub(
    r"'stop_time': stop_time, 'stop_km': stop_km, 'reason': reason, 'photo': saved_filename\n\s*\}\)",
    "'stop_time': stop_time, 'stop_km': stop_km, 'reason': reason, 'photo': saved_filename, 'lat': lat, 'lng': lng\n        })",
    content
)


# Replace finish_trip
content = re.sub(
    r"end_time = request.form.get\('end_time'\) or datetime.now\(\).strftime\('%Y-%m-%d %H:%M:%S'\)",
    "end_time = request.form.get('end_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')\n        lat = request.form.get('lat')\n        lng = request.form.get('lng')",
    content
)

content = re.sub(
    r"saved_filename = process_and_save_odometer_photo\(\n\s*file_storage=photo_file, stage_label='CHEGADA', km_value=end_km,\n\s*plate=trip\['vehicle_plate'\], driver_name=trip\['driver_name'\],\n\s*timestamp_str=end_time, upload_folder=app.config\['UPLOAD_FOLDER'\]\n\s*\)",
    """geo_str = f"GPS: {lat}, {lng}" if lat and lng else ""
        saved_filename = process_and_save_odometer_photo(
            file_storage=photo_file, stage_label='CHEGADA', km_value=end_km,
            plate=trip['vehicle_plate'], driver_name=trip['driver_name'],
            extra_text=geo_str, timestamp_str=end_time, upload_folder=app.config['UPLOAD_FOLDER']
        )""",
    content
)

content = re.sub(
    r"'end_time': end_time, 'end_km': end_km, 'end_photo': saved_filename\n\s*\}\)",
    "'end_time': end_time, 'end_km': end_km, 'end_photo': saved_filename, 'lat': lat, 'lng': lng\n        })",
    content
)


with open('app.py', 'w') as f:
    f.write(content)

