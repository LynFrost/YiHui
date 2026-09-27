import sys
import os
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


def test_runtime_paths_use_version_parent_as_shared_software_root():
    assert app.APP_ROOT == Path(app.__file__).resolve().parent
    assert app.SOFTWARE_ROOT == app.APP_ROOT.parent
    assert app.FRONTEND == app.APP_ROOT / "frontend"
    assert app.CONFIG_FILE == app.SOFTWARE_ROOT / "config" / "AIImageManager.config.json"
    assert app.DATA_DIR == app.SOFTWARE_ROOT / "data"
    assert app.DB_FILE == app.DATA_DIR / "AIImageManager.data.sqlite"
    assert app.DEFAULT_GENERATED_ROOT == app.SOFTWARE_ROOT / "generated"
    assert app.BACKUP_DIR == app.SOFTWARE_ROOT / "backup"
    assert app.EXPORT_DIR == app.SOFTWARE_ROOT / "export"


def test_local_server_starts_with_threaded_requests():
    source = Path(app.__file__).read_text(encoding="utf-8")

    assert "threaded=True" in source


def test_runtime_paths_can_be_overridden_by_environment(monkeypatch):
    software_root = app.SOFTWARE_ROOT
    monkeypatch.setenv("AI_IMAGE_MANAGER_DATA_DIR", str(software_root / "tmp-data"))
    monkeypatch.setenv("AI_IMAGE_MANAGER_CONFIG_DIR", str(software_root / "tmp-config"))
    monkeypatch.setenv("AI_IMAGE_MANAGER_BACKUP_DIR", str(software_root / "tmp-backup"))
    monkeypatch.setenv("AI_IMAGE_MANAGER_EXPORT_DIR", str(software_root / "tmp-export"))

    source = Path(app.__file__).read_text(encoding="utf-8")

    assert 'os.getenv("AI_IMAGE_MANAGER_DATA_DIR"' in source
    assert 'os.getenv("AI_IMAGE_MANAGER_CONFIG_DIR"' in source
    assert 'os.getenv("AI_IMAGE_MANAGER_BACKUP_DIR"' in source
    assert 'os.getenv("AI_IMAGE_MANAGER_EXPORT_DIR"' in source


def write_schema_version(db_file: Path, version: int) -> None:
    conn = sqlite3.connect(db_file)
    try:
        conn.execute("CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO app_metadata (key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )
        conn.commit()
    finally:
        conn.close()


def test_schema_v4_database_still_requires_pre_migration_backup(tmp_path):
    db_file = tmp_path / "schema-v4.sqlite"
    write_schema_version(db_file, 4)

    assert app.db_needs_schema_migration(db_file) is True


def test_current_schema_database_does_not_require_pre_migration_backup(tmp_path):
    db_file = tmp_path / "schema-v5.sqlite"
    write_schema_version(db_file, 5)

    assert app.db_needs_schema_migration(db_file) is False




