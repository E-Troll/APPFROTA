"""
Database Module for Vehicle Mileage Tracking Application
Uses SQLite with foreign keys and index optimization.
"""

import os
import sqlite3
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'odometro.db')


def get_db(db_path=None):
    target_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=None):
    conn = get_db(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_plate TEXT NOT NULL,
                vehicle_model TEXT,
                driver_name TEXT NOT NULL,
                purpose TEXT,
                start_time TEXT NOT NULL,
                start_km REAL NOT NULL,
                start_photo TEXT NOT NULL,
                end_time TEXT,
                end_km REAL,
                end_photo TEXT,
                total_km REAL,
                status TEXT NOT NULL DEFAULT 'EM_ANDAMENTO',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS trip_stops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                stop_time TEXT NOT NULL,
                stop_km REAL NOT NULL,
                reason TEXT,
                photo TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_start_time ON trips(start_time);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_plate ON trips(vehicle_plate);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stops_trip_id ON trip_stops(trip_id);")

        # Safely add geolocation columns if they don't exist
        try: conn.execute("ALTER TABLE trips ADD COLUMN start_lat REAL;")
        except sqlite3.OperationalError: pass
        try: conn.execute("ALTER TABLE trips ADD COLUMN start_lng REAL;")
        except sqlite3.OperationalError: pass
        try: conn.execute("ALTER TABLE trips ADD COLUMN end_lat REAL;")
        except sqlite3.OperationalError: pass
        try: conn.execute("ALTER TABLE trips ADD COLUMN end_lng REAL;")
        except sqlite3.OperationalError: pass
        
        try: conn.execute("ALTER TABLE trip_stops ADD COLUMN stop_lat REAL;")
        except sqlite3.OperationalError: pass
        try: conn.execute("ALTER TABLE trip_stops ADD COLUMN stop_lng REAL;")
        except sqlite3.OperationalError: pass

    conn.close()


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def create_trip(data, db_path=None):
    now = datetime.now().isoformat()
    start_time = data.get('start_time') or now
    conn = get_db(db_path)
    with conn:
        cursor = conn.execute("""
            INSERT INTO trips (
                vehicle_plate, vehicle_model, driver_name, purpose,
                start_time, start_km, start_photo,
                start_lat, start_lng,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'EM_ANDAMENTO', ?, ?)
        """, (
            data['vehicle_plate'].strip().upper(),
            data.get('vehicle_model', '').strip(),
            data['driver_name'].strip(),
            data.get('purpose', '').strip(),
            start_time,
            float(data['start_km']),
            data['start_photo'],
            data.get('lat'),
            data.get('lng'),
            now,
            now
        ))
        trip_id = cursor.lastrowid
    conn.close()
    return trip_id


def get_trip_by_id(trip_id, db_path=None):
    conn = get_db(db_path)
    trip_row = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if not trip_row:
        conn.close()
        return None

    trip = row_to_dict(trip_row)
    stops_rows = conn.execute(
        "SELECT * FROM trip_stops WHERE trip_id = ? ORDER BY stop_km ASC, stop_time ASC",
        (trip_id,)
    ).fetchall()
    trip['stops'] = [row_to_dict(s) for s in stops_rows]
    conn.close()
    return trip


def get_active_trip(db_path=None):
    conn = get_db(db_path)
    row = conn.execute("""
        SELECT * FROM trips
        WHERE status = 'EM_ANDAMENTO'
        ORDER BY id DESC LIMIT 1
    """).fetchone()

    if not row:
        conn.close()
        return None

    trip = row_to_dict(row)
    stops_rows = conn.execute(
        "SELECT * FROM trip_stops WHERE trip_id = ? ORDER BY stop_km ASC, stop_time ASC",
        (trip['id'],)
    ).fetchall()
    trip['stops'] = [row_to_dict(s) for s in stops_rows]
    conn.close()
    return trip


def add_stop_to_trip(trip_id, data, db_path=None):
    now = datetime.now().isoformat()
    stop_time = data.get('stop_time') or now
    conn = get_db(db_path)
    with conn:
        cursor = conn.execute("""
            INSERT INTO trip_stops (
                trip_id, stop_time, stop_km, reason, photo,
                stop_lat, stop_lng, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trip_id,
            stop_time,
            float(data['stop_km']),
            data.get('reason', '').strip(),
            data['photo'],
            data.get('lat'),
            data.get('lng'),
            now
        ))
        stop_id = cursor.lastrowid
        conn.execute("UPDATE trips SET updated_at = ? WHERE id = ?", (now, trip_id))
    conn.close()
    return stop_id


def finish_trip(trip_id, data, db_path=None):
    conn = get_db(db_path)
    trip_row = conn.execute("SELECT start_km, status FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if not trip_row:
        conn.close()
        raise ValueError("Viagem não encontrada.")
    if trip_row['status'] != 'EM_ANDAMENTO':
        conn.close()
        raise ValueError("Esta viagem não está em andamento.")

    start_km = float(trip_row['start_km'])
    end_km = float(data['end_km'])
    if end_km < start_km:
        conn.close()
        raise ValueError(f"Quilometragem final ({end_km} km) não pode ser menor que a inicial ({start_km} km).")

    highest_stop = conn.execute("SELECT MAX(stop_km) as max_km FROM trip_stops WHERE trip_id = ?", (trip_id,)).fetchone()
    if highest_stop and highest_stop['max_km'] is not None:
        if end_km < float(highest_stop['max_km']):
            conn.close()
            raise ValueError(f"Quilometragem final ({end_km} km) não pode ser menor que a parada ({highest_stop['max_km']} km).")

    total_km = round(end_km - start_km, 2)
    now = datetime.now().isoformat()
    end_time = data.get('end_time') or now

    with conn:
        conn.execute("""
            UPDATE trips
            SET end_time = ?, end_km = ?, end_photo = ?,
                end_lat = ?, end_lng = ?,
                total_km = ?, status = 'FINALIZADA', updated_at = ?
            WHERE id = ?
        """, (
            end_time,
            end_km,
            data['end_photo'],
            data.get('lat'),
            data.get('lng'),
            total_km,
            now,
            trip_id
        ))
    conn.close()
    return total_km


def cancel_trip(trip_id, db_path=None):
    now = datetime.now().isoformat()
    conn = get_db(db_path)
    with conn:
        conn.execute("UPDATE trips SET status = 'CANCELADA', updated_at = ? WHERE id = ?", (now, trip_id))
    conn.close()
    return True


def delete_trip(trip_id, db_path=None):
    conn = get_db(db_path)
    trip = conn.execute("SELECT start_photo, end_photo FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if not trip:
        conn.close()
        return []

    photos = []
    if trip['start_photo']: photos.append(trip['start_photo'])
    if trip['end_photo']: photos.append(trip['end_photo'])

    stops = conn.execute("SELECT photo FROM trip_stops WHERE trip_id = ?", (trip_id,)).fetchall()
    for s in stops:
        if s['photo']: photos.append(s['photo'])

    with conn:
        conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    conn.close()
    return photos


def list_trips(month=None, search=None, status=None, db_path=None):
    conn = get_db(db_path)
    query = """
        SELECT t.*, COUNT(s.id) as stops_count
        FROM trips t
        LEFT JOIN trip_stops s ON t.id = s.trip_id
        WHERE 1=1
    """
    params = []

    if month and month.strip():
        query += " AND t.start_time LIKE ?"
        params.append(f"{month.strip()}%")

    if status and status.strip():
        query += " AND t.status = ?"
        params.append(status.strip())

    if search and search.strip():
        search_term = f"%{search.strip()}%"
        query += " AND (t.vehicle_plate LIKE ? OR t.driver_name LIKE ? OR t.purpose LIKE ?)"
        params.extend([search_term, search_term, search_term])

    query += " GROUP BY t.id ORDER BY t.start_time DESC, t.id DESC"

    rows = conn.execute(query, params).fetchall()
    trips = []

    for r in rows:
        t = row_to_dict(r)
        stops_rows = conn.execute(
            "SELECT * FROM trip_stops WHERE trip_id = ? ORDER BY stop_km ASC, stop_time ASC",
            (t['id'],)
        ).fetchall()
        t['stops'] = [row_to_dict(s) for s in stops_rows]
        trips.append(t)

    conn.close()
    return trips


def get_available_months(db_path=None):
    conn = get_db(db_path)
    rows = conn.execute("""
        SELECT DISTINCT substr(start_time, 1, 7) as month
        FROM trips
        WHERE start_time IS NOT NULL AND length(start_time) >= 7
        ORDER BY month DESC
    """).fetchall()
    conn.close()
    return [r['month'] for r in rows if r['month']]


def get_summary_stats(month=None, db_path=None):
    conn = get_db(db_path)
    query = "SELECT * FROM trips WHERE 1=1"
    params = []

    if month and month.strip():
        query += " AND start_time LIKE ?"
        params.append(f"{month.strip()}%")

    rows = conn.execute(query, params).fetchall()
    conn.close()

    total_trips = len(rows)
    finished_trips = sum(1 for r in rows if r['status'] == 'FINALIZADA')
    active_trips = sum(1 for r in rows if r['status'] == 'EM_ANDAMENTO')
    total_km = sum(float(r['total_km'] or 0) for r in rows if r['status'] == 'FINALIZADA' and r['total_km'])
    avg_km = round(total_km / finished_trips, 2) if finished_trips > 0 else 0.0
    unique_vehicles = len(set(r['vehicle_plate'] for r in rows if r['vehicle_plate']))

    return {
        'total_trips': total_trips,
        'finished_trips': finished_trips,
        'active_trips': active_trips,
        'total_km': round(total_km, 2),
        'avg_km': avg_km,
        'unique_vehicles': unique_vehicles
    }
