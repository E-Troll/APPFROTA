"""Database access for the vehicle mileage tracking application.

Uses SQLite for local development and tests, and Supabase PostgreSQL in production.
"""

import os
import sqlite3
from datetime import datetime, timedelta

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'odometro.db')


INSPECTION_COLUMNS = ('origin_city', 'origin_br', 'dest_city', 'dest_br', 'action_type')


def get_db(db_path=None):
    """Open a local SQLite connection or a Supabase PostgreSQL connection."""
    database_url = os.environ.get('DATABASE_URL')
    if db_path is None and database_url:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(database_url, row_factory=dict_row)

    if db_path is None and os.environ.get('VERCEL') == '1':
        raise RuntimeError('DATABASE_URL is required on Vercel. Configure the Supabase PostgreSQL connection string.')

    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def _is_postgres(conn):
    return conn.__class__.__module__.startswith('psycopg')


def _execute(conn, query, params=()):
    if _is_postgres(conn):
        query = query.replace('?', '%s')
    return conn.execute(query, params)


def _last_insert_id(conn, cursor):
    if _is_postgres(conn):
        return _execute(conn, 'SELECT LASTVAL() AS id').fetchone()['id']
    return cursor.lastrowid


def init_db(db_path=None):
    """Create the tables and indexes if they do not already exist."""
    conn = get_db(db_path)
    postgres = _is_postgres(conn)
    trip_schema = """
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
        )
    """
    stops_schema = """
        CREATE TABLE IF NOT EXISTS trip_stops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
            stop_time TEXT NOT NULL,
            stop_km REAL NOT NULL,
            reason TEXT,
            photo TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """
    if postgres:
        trip_schema = trip_schema.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY')
        stops_schema = stops_schema.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY')
        stops_schema = stops_schema.replace('trip_id INTEGER NOT NULL', 'trip_id BIGINT NOT NULL')

    with conn:
        _execute(conn, trip_schema)
        _execute(conn, stops_schema)
        _execute(conn, 'CREATE INDEX IF NOT EXISTS idx_trips_start_time ON trips(start_time)')
        _execute(conn, 'CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status)')
        _execute(conn, 'CREATE INDEX IF NOT EXISTS idx_trips_plate ON trips(vehicle_plate)')
        _execute(conn, 'CREATE INDEX IF NOT EXISTS idx_stops_trip_id ON trip_stops(trip_id)')
        for column in INSPECTION_COLUMNS:
            if postgres:
                _execute(conn, f'ALTER TABLE trips ADD COLUMN IF NOT EXISTS {column} TEXT')
            else:
                existing = {row['name'] for row in _execute(conn, 'PRAGMA table_info(trips)').fetchall()}
                if column not in existing:
                    _execute(conn, f'ALTER TABLE trips ADD COLUMN {column} TEXT')
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
        cursor = _execute(conn, """
            INSERT INTO trips (
                vehicle_plate, vehicle_model, driver_name, purpose,
                start_time, start_km, start_photo, origin_city, origin_br, action_type,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'EM_ANDAMENTO', ?, ?)
        """, (
            data['vehicle_plate'].strip().upper(),
            data.get('vehicle_model', '').strip(),
            data['driver_name'].strip(),
            data.get('purpose', '').strip(),
            start_time,
            float(data['start_km']),
            data['start_photo'],
            data.get('origin_city', '').strip(),
            data.get('origin_br', '').strip(),
            data.get('action_type', '').strip(),
            now,
            now
        ))
        trip_id = _last_insert_id(conn, cursor)
    conn.close()
    return trip_id


def get_trip_by_id(trip_id, db_path=None):
    conn = get_db(db_path)
    trip_row = _execute(conn, 'SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not trip_row:
        conn.close()
        return None
    trip = row_to_dict(trip_row)
    stops = _execute(conn,
        'SELECT * FROM trip_stops WHERE trip_id = ? ORDER BY stop_km ASC, stop_time ASC',
        (trip_id,)
    ).fetchall()
    trip['stops'] = [row_to_dict(stop) for stop in stops]
    conn.close()
    return trip


def get_active_trip(db_path=None):
    conn = get_db(db_path)
    row = _execute(conn, """
        SELECT * FROM trips WHERE status = 'EM_ANDAMENTO'
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    if not row:
        conn.close()
        return None
    trip = row_to_dict(row)
    stops = _execute(conn,
        'SELECT * FROM trip_stops WHERE trip_id = ? ORDER BY stop_km ASC, stop_time ASC',
        (trip['id'],)
    ).fetchall()
    trip['stops'] = [row_to_dict(stop) for stop in stops]
    conn.close()
    return trip


def add_stop_to_trip(trip_id, data, db_path=None):
    now = datetime.now().isoformat()
    stop_time = data.get('stop_time') or now
    conn = get_db(db_path)
    with conn:
        cursor = _execute(conn, """
            INSERT INTO trip_stops (trip_id, stop_time, stop_km, reason, photo, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            trip_id, stop_time, float(data['stop_km']),
            data.get('reason', '').strip(), data['photo'], now
        ))
        stop_id = _last_insert_id(conn, cursor)
        _execute(conn, 'UPDATE trips SET updated_at = ? WHERE id = ?', (now, trip_id))
    conn.close()
    return stop_id


def finish_trip(trip_id, data, db_path=None):
    conn = get_db(db_path)
    trip = _execute(conn, 'SELECT start_km, status FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not trip:
        conn.close()
        raise ValueError('Viagem não encontrada.')
    if trip['status'] != 'EM_ANDAMENTO':
        conn.close()
        raise ValueError('Esta viagem não está em andamento.')

    start_km = float(trip['start_km'])
    end_km = float(data['end_km'])
    if end_km < start_km:
        conn.close()
        raise ValueError(f'Quilometragem final ({end_km} km) não pode ser menor que a inicial ({start_km} km).')

    highest_stop = _execute(conn,
        'SELECT MAX(stop_km) AS max_km FROM trip_stops WHERE trip_id = ?', (trip_id,)
    ).fetchone()
    if highest_stop and highest_stop['max_km'] is not None and end_km < float(highest_stop['max_km']):
        conn.close()
        raise ValueError(f"Quilometragem final ({end_km} km) não pode ser menor que a parada ({highest_stop['max_km']} km).")

    total_km = round(end_km - start_km, 2)
    now = datetime.now().isoformat()
    with conn:
        _execute(conn, """
            UPDATE trips
            SET end_time = ?, end_km = ?, end_photo = ?, total_km = ?, dest_city = ?, dest_br = ?,
                status = 'FINALIZADA', updated_at = ?
            WHERE id = ?
        """, (
            data.get('end_time') or now, end_km, data['end_photo'], total_km,
            data.get('dest_city', '').strip(), data.get('dest_br', '').strip(), now, trip_id
        ))
    conn.close()
    return total_km


def cancel_trip(trip_id, db_path=None):
    now = datetime.now().isoformat()
    conn = get_db(db_path)
    with conn:
        _execute(conn, "UPDATE trips SET status = 'CANCELADA', updated_at = ? WHERE id = ?", (now, trip_id))
    conn.close()
    return True


def delete_trip(trip_id, db_path=None):
    conn = get_db(db_path)
    trip = _execute(conn, 'SELECT start_photo, end_photo FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not trip:
        conn.close()
        return []
    photos = [photo for photo in (trip['start_photo'], trip['end_photo']) if photo]
    stops = _execute(conn, 'SELECT photo FROM trip_stops WHERE trip_id = ?', (trip_id,)).fetchall()
    photos.extend(stop['photo'] for stop in stops if stop['photo'])
    with conn:
        _execute(conn, 'DELETE FROM trips WHERE id = ?', (trip_id,))
    conn.close()
    return photos


def delete_expired_trips(days=45, db_path=None):
    """Delete trips older than the retention period and return their photo keys."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_db(db_path)
    rows = _execute(conn, """
        SELECT t.id, t.start_photo, t.end_photo, s.photo AS stop_photo
        FROM trips AS t
        LEFT JOIN trip_stops AS s ON s.trip_id = t.id
        WHERE t.created_at < ?
    """, (cutoff,)).fetchall()
    trip_ids = {row['id'] for row in rows}
    photos = list(dict.fromkeys(
        photo for row in rows
        for photo in (row['start_photo'], row['end_photo'], row['stop_photo'])
        if photo
    ))
    if trip_ids:
        placeholders = ', '.join('?' for _ in trip_ids)
        with conn:
            _execute(conn, f'DELETE FROM trips WHERE id IN ({placeholders})', tuple(trip_ids))
    conn.close()
    return len(trip_ids), photos


def list_trips(month=None, search=None, status=None, db_path=None):
    conn = get_db(db_path)
    query = """
        SELECT t.*, COUNT(s.id) AS stops_count
        FROM trips t LEFT JOIN trip_stops s ON t.id = s.trip_id
        WHERE 1=1
    """
    params = []
    if month and month.strip():
        query += ' AND t.start_time LIKE ?'
        params.append(f'{month.strip()}%')
    if status and status.strip():
        query += ' AND t.status = ?'
        params.append(status.strip())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += ' AND (t.vehicle_plate LIKE ? OR t.origin_city LIKE ? OR t.dest_city LIKE ? OR t.action_type LIKE ? OR t.driver_name LIKE ?)'
        params.extend([term] * 5)
    query += ' GROUP BY t.id ORDER BY t.start_time DESC, t.id DESC'

    trips = []
    for row in _execute(conn, query, params).fetchall():
        trip = row_to_dict(row)
        stops = _execute(conn,
            'SELECT * FROM trip_stops WHERE trip_id = ? ORDER BY stop_km ASC, stop_time ASC',
            (trip['id'],)
        ).fetchall()
        trip['stops'] = [row_to_dict(stop) for stop in stops]
        trips.append(trip)
    conn.close()
    return trips


def get_available_months(db_path=None):
    conn = get_db(db_path)
    rows = _execute(conn, """
        SELECT DISTINCT substr(start_time, 1, 7) AS month
        FROM trips WHERE start_time IS NOT NULL AND length(start_time) >= 7
        ORDER BY month DESC
    """).fetchall()
    conn.close()
    return [row['month'] for row in rows if row['month']]


def get_summary_stats(month=None, db_path=None):
    conn = get_db(db_path)
    query = 'SELECT * FROM trips WHERE 1=1'
    params = []
    if month and month.strip():
        query += ' AND start_time LIKE ?'
        params.append(f'{month.strip()}%')
    rows = _execute(conn, query, params).fetchall()
    conn.close()

    total_trips = len(rows)
    finished = sum(1 for row in rows if row['status'] == 'FINALIZADA')
    total_km = sum(float(row['total_km'] or 0) for row in rows if row['status'] == 'FINALIZADA' and row['total_km'])
    return {
        'total_trips': total_trips,
        'finished_trips': finished,
        'active_trips': sum(1 for row in rows if row['status'] == 'EM_ANDAMENTO'),
        'total_km': round(total_km, 2),
        'avg_km': round(total_km / finished, 2) if finished else 0.0,
        'unique_vehicles': len({row['vehicle_plate'] for row in rows if row['vehicle_plate']})
    }
