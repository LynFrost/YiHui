from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path

from flask import Flask, send_from_directory

from backend.backup import create_backup, create_daily_auto_backup
from backend.api import api
from backend.config import load_config
from backend.database import get_connection, init_db


APP_ROOT = Path(__file__).resolve().parent
ROOT = APP_ROOT
SOFTWARE_ROOT = APP_ROOT.parent
FRONTEND = APP_ROOT / "frontend"
CONFIG_DIR = Path(os.getenv("AI_IMAGE_MANAGER_CONFIG_DIR", str(SOFTWARE_ROOT / "config")))
DATA_DIR = Path(os.getenv("AI_IMAGE_MANAGER_DATA_DIR", str(SOFTWARE_ROOT / "data")))
BACKUP_DIR = Path(os.getenv("AI_IMAGE_MANAGER_BACKUP_DIR", str(SOFTWARE_ROOT / "backup")))
EXPORT_DIR = Path(os.getenv("AI_IMAGE_MANAGER_EXPORT_DIR", str(SOFTWARE_ROOT / "export")))
THUMBNAIL_CACHE_DIR = Path(os.getenv("AI_IMAGE_MANAGER_THUMBNAIL_CACHE_DIR", str(SOFTWARE_ROOT / "cache" / "thumbnails")))
CONFIG_FILE = CONFIG_DIR / "AIImageManager.config.json"
DB_FILE = DATA_DIR / "AIImageManager.data.sqlite"
DEFAULT_GENERATED_ROOT = SOFTWARE_ROOT / "generated"
APP_VERSION = "V0.67"


def db_needs_schema_migration(db_file: Path) -> bool:
    if not db_file.is_file():
        return False
    conn = get_connection(db_file)
    try:
        try:
            row = conn.execute(
                "SELECT value FROM app_metadata WHERE key = 'schema_version'"
            ).fetchone()
        except Exception:
            return True
        if row is None:
            return True
        try:
            current_version = int(row[0])
        except (TypeError, ValueError):
            return True
        return current_version < 5
    finally:
        conn.close()


def create_app(
    db_file: Path | None = None,
    config_file: Path | None = None,
    backup_dir: Path | None = None,
    export_dir: Path | None = None,
    thumbnail_cache_dir: Path | None = None,
    auto_backup: bool | None = None,
) -> Flask:
    app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="/static")

    resolved_config_file = config_file or CONFIG_FILE
    resolved_db_file = db_file or DB_FILE
    resolved_backup_dir = backup_dir or BACKUP_DIR
    resolved_export_dir = export_dir or EXPORT_DIR
    resolved_thumbnail_cache_dir = thumbnail_cache_dir or THUMBNAIL_CACHE_DIR
    app.config["APP_CONFIG"] = load_config(resolved_config_file)
    app.config["CONFIG_FILE"] = resolved_config_file
    app.config["BACKUP_DIR"] = resolved_backup_dir
    app.config["EXPORT_DIR"] = resolved_export_dir
    app.config["THUMBNAIL_CACHE_DIR"] = resolved_thumbnail_cache_dir
    app.config["APP_VERSION"] = APP_VERSION
    resolved_db_file.parent.mkdir(parents=True, exist_ok=True)
    resolved_backup_dir.mkdir(parents=True, exist_ok=True)
    resolved_export_dir.mkdir(parents=True, exist_ok=True)
    resolved_thumbnail_cache_dir.mkdir(parents=True, exist_ok=True)
    if db_needs_schema_migration(resolved_db_file):
        create_backup(
            resolved_db_file,
            resolved_config_file,
            resolved_backup_dir,
            APP_VERSION,
            "pre_migration",
        )
    conn = get_connection(resolved_db_file)
    init_db(conn)
    conn.close()
    app.config["DB_FILE"] = resolved_db_file
    should_auto_backup = (
        auto_backup
        if auto_backup is not None
        else db_file is None and config_file is None
    )
    if should_auto_backup:
        try:
            create_daily_auto_backup(
                resolved_db_file,
                resolved_config_file,
                resolved_backup_dir,
                APP_VERSION,
            )
        except Exception as exc:
            app.config["AUTO_BACKUP_ERROR"] = str(exc)

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND, "index.html")

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    app.register_blueprint(api)

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Image Manager local web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    app = create_app()
    url = f"http://{args.host}:{args.port}/"
    print(f"Serving {url}")
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())












