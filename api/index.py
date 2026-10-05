import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import database

if os.environ.get("VERCEL") == "1":
    database.DEFAULT_DB_PATH = os.path.join(tempfile.gettempdir(), "appfrota.db")

from app import app

if os.environ.get("VERCEL") == "1":
    upload_folder = os.path.join(tempfile.gettempdir(), "appfrota-uploads")
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder
