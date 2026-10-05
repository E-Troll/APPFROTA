import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import database

if os.environ.get("VERCEL") == "1":
    database_url = next((
        os.environ[name]
        for name in (
            "DATABASE_URL",
            "POSTGRES_URL",
            "SUPABASE_DB_URL",
            "SUPABASE_DATABASE_URL",
            "POSTGRES_URL_NON_POOLING",
            "POSTGRES_PRISMA_URL",
        )
        if os.environ.get(name)
    ), None)
    if database_url:
        os.environ.setdefault("DATABASE_URL", database_url)
    database.DEFAULT_DB_PATH = os.path.join(tempfile.gettempdir(), "appfrota.db")

from app import app

if os.environ.get("VERCEL") == "1":
    upload_folder = os.path.join(tempfile.gettempdir(), "appfrota-uploads")
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder
