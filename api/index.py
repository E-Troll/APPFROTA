import os
import sys
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import database

DATABASE_ENV_VARS = (
    "DATABASE_URL",
    "POSTGRES_URL",
    "SUPABASE_DB_URL",
    "SUPABASE_DATABASE_URL",
    "POSTGRES_URL_NON_POOLING",
    "POSTGRES_PRISMA_URL",
)
LIBPQ_PARAMS = {"sslmode", "connect_timeout", "application_name", "options", "target_session_attrs"}


def normalize_database_url(url):
    # Vercel/Supabase URLs carry extra params (supa, pgbouncer) that libpq rejects.
    parts = urlsplit(url)
    if parts.scheme == "postgres":
        parts = parts._replace(scheme="postgresql")
    query = [(k, v) for k, v in parse_qsl(parts.query) if k in LIBPQ_PARAMS]
    if not any(k == "sslmode" for k, _ in query):
        query.append(("sslmode", "require"))
    return urlunsplit(parts._replace(query=urlencode(query)))


if os.environ.get("VERCEL") == "1":
    database_url = next((os.environ[n] for n in DATABASE_ENV_VARS if os.environ.get(n)), None)
    if database_url:
        os.environ["DATABASE_URL"] = normalize_database_url(database_url)
    if not os.environ.get("SUPABASE_URL") and os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    if not os.environ.get("SUPABASE_SERVICE_ROLE_KEY") and os.environ.get("SUPABASE_SECRET_KEY"):
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = os.environ["SUPABASE_SECRET_KEY"]
    database.DEFAULT_DB_PATH = os.path.join(tempfile.gettempdir(), "appfrota.db")

    # Supabase poolers in transaction mode do not support prepared statements.
    import psycopg

    _connect = psycopg.connect

    def _connect_no_prepare(*args, **kwargs):
        kwargs.setdefault("prepare_threshold", None)
        kwargs.setdefault("connect_timeout", 10)
        return _connect(*args, **kwargs)

    psycopg.connect = _connect_no_prepare

# Defer schema creation to the first request so import never fails.
_real_init_db = database.init_db
database.init_db = lambda *a, **k: None

from app import app

database.init_db = _real_init_db

if os.environ.get("VERCEL") == "1":
    upload_folder = os.path.join(tempfile.gettempdir(), "appfrota-uploads")
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder

from flask import jsonify, request

_state = {"ready": False}


def _init_once():
    if not _state["ready"]:
        _real_init_db()
        _state["ready"] = True


@app.route("/api/health")
def api_health():
    try:
        _init_once()
    except Exception as exc:
        app.logger.exception("Database init failed")
        return jsonify({
            "status": "error",
            "error_type": type(exc).__name__,
            "detail": str(exc).splitlines()[0][:200] if str(exc) else "",
            "url_configured": bool(os.environ.get("DATABASE_URL")),
        }), 503
    return jsonify({"status": "ok", "database": "connected"})


@app.before_request
def _ensure_db():
    if request.endpoint in ("index", "api_health", "static"):
        return None
    try:
        _init_once()
    except Exception:
        app.logger.exception("Database init failed")
        return jsonify({"success": False, "error": "Banco de dados indisponível."}), 503
    return None
