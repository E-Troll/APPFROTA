import logging
import os

from flask import Flask, jsonify

logger = logging.getLogger(__name__)
app = Flask(__name__)
DATABASE_ENV_VARS = (
    "DATABASE_URL",
    "POSTGRES_URL",
    "SUPABASE_DB_URL",
    "SUPABASE_DATABASE_URL",
    "POSTGRES_URL_NON_POOLING",
    "POSTGRES_PRISMA_URL",
)


@app.get("/api/health")
@app.get("/")
def health():
    database_url = next((os.environ[name] for name in DATABASE_ENV_VARS if os.environ.get(name)), None)
    if not database_url:
        return jsonify({"status": "error", "code": "database_url_missing"}), 503

    try:
        import psycopg

        with psycopg.connect(database_url, connect_timeout=5) as connection:
            connection.execute("SELECT 1")
    except Exception:
        logger.exception("APPFROTA database health check failed")
        return jsonify({"status": "error", "code": "database_connection_failed"}), 503

    return jsonify({"status": "ok", "database": "connected"})
