from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import normalize_config, save_config
from backend.database import get_connection, init_db, repair_instance_numbers


APP_NAME = "AIImageManager"
BACKUP_DB_NAME = "AIImageManager.data.sqlite"
BACKUP_CONFIG_NAME = "AIImageManager.config.json"
BACKUP_METADATA_NAME = "backup_metadata.json"
SUPPORTED_BACKUP_TYPES = {"manual", "auto", "pre_restore", "pre_migration"}
AUTO_BACKUP_KEEP = 30
EXPORT_FORMAT_VERSION = 1
EXPORT_TABLES = [
    "nodes",
    "instances",
    "input_images",
    "tags",
    "instance_tags",
    "generation_history",
    "app_metadata",
]
EXPORT_TABLE_LABELS = {
    "nodes": "节点",
    "instances": "实例",
    "input_images": "输入图",
    "tags": "标签",
    "instance_tags": "标签关联",
    "generation_history": "历史记录",
    "app_metadata": "元数据",
}
REFERENCE_FIX_KEYS = {
    "instances_node_missing_set_null": 0,
    "instances_instance_number_repaired": 0,
    "input_images_skipped_missing_instance": 0,
    "instance_tags_skipped_missing_instance": 0,
    "instance_tags_skipped_missing_tag": 0,
    "nodes_parent_missing_set_null": 0,
}


def read_config_file(config_file: Path) -> dict[str, Any]:
    config_file = Path(config_file)
    if not config_file.is_file():
        return {}
    try:
        parsed = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def provider_count_from_config(config: dict[str, Any]) -> int:
    providers = config.get("providers")
    return len(providers) if isinstance(providers, dict) else 0


def sqlite_integrity_check(db_file: Path) -> str:
    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0] if row else "")
    finally:
        conn.close()


def database_summary(db_file: Path, config_file: Path) -> dict[str, int]:
    summary = {
        "instance_count": 0,
        "input_image_count": 0,
        "output_image_count": 0,
        "tag_count": 0,
        "node_count": 0,
        "generation_history_count": 0,
        "provider_count": provider_count_from_config(read_config_file(config_file)),
    }
    if not Path(db_file).is_file():
        return summary
    conn = sqlite3.connect(db_file)
    try:
        summary["instance_count"] = int(conn.execute("SELECT COUNT(*) FROM instances").fetchone()[0])
        summary["input_image_count"] = int(conn.execute("SELECT COUNT(*) FROM input_images").fetchone()[0])
        summary["output_image_count"] = int(
            conn.execute(
                "SELECT COUNT(*) FROM instances WHERE COALESCE(output_image_path, '') <> ''"
            ).fetchone()[0]
        )
        summary["tag_count"] = int(conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0])
        summary["node_count"] = int(conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
        summary["generation_history_count"] = int(
            conn.execute("SELECT COUNT(*) FROM generation_history").fetchone()[0]
        )
    except sqlite3.Error:
        return summary
    finally:
        conn.close()
    return summary


def table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def table_order_sql(table: str) -> str:
    if table == "instance_tags":
        return "instance_id, tag_id"
    if table == "app_metadata":
        return "key"
    return "id"


def iter_table_rows(conn: sqlite3.Connection, table: str, batch_size: int = 1000):
    cursor = conn.execute(f"SELECT * FROM {table} ORDER BY {table_order_sql(table)}")
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        for row in rows:
            yield dict(row)


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate = directory / f"{stem}{suffix}"
    index = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{index:02d}{suffix}"
        index += 1
    return candidate


def export_temp_path(final_path: Path) -> Path:
    return final_path.with_name(f"{final_path.stem}.zip.tmp")


def json_dumps_line(row: dict[str, Any]) -> bytes:
    return (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")


def now_stamp() -> tuple[str, str]:
    now = datetime.now().replace(microsecond=0)
    return now.isoformat(), now.strftime("%Y%m%d_%H%M%S")


def size_label(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(max(0, size_bytes))
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} B"
    return f"{value:.1f} {unit}"


def database_schema_version(db_file: Path) -> int:
    if not db_file.is_file():
        return 0
    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute(
            "SELECT value FROM app_metadata WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.Error:
        return 0
    finally:
        conn.close()
    try:
        return int(row[0]) if row else 0
    except (TypeError, ValueError):
        return 0


def backup_file_name(backup_type: str, app_version: str, stamp: str, backup_dir: Path) -> Path:
    base = f"{APP_NAME}_backup_{backup_type}_{app_version}_{stamp}"
    candidate = backup_dir / f"{base}.zip"
    index = 1
    while candidate.exists():
        candidate = backup_dir / f"{base}_{index:02d}.zip"
        index += 1
    return candidate


def sqlite_snapshot(db_file: Path, destination: Path) -> None:
    source = sqlite3.connect(db_file)
    try:
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def create_backup(
    db_file: Path,
    config_file: Path,
    backup_dir: Path,
    app_version: str,
    backup_type: str,
) -> dict[str, Any]:
    backup_type = str(backup_type or "").strip()
    if backup_type not in SUPPORTED_BACKUP_TYPES:
        raise ValueError("备份类型无效")
    db_file = Path(db_file)
    config_file = Path(config_file)
    backup_dir = Path(backup_dir)
    if not db_file.is_file():
        raise ValueError("数据库文件不存在，无法备份")

    backup_dir.mkdir(parents=True, exist_ok=True)
    created_at, stamp = now_stamp()
    final_zip = backup_file_name(backup_type, app_version, stamp, backup_dir)

    with tempfile.TemporaryDirectory(prefix="ai-image-backup-", dir=str(backup_dir)) as temp_name:
        temp_dir = Path(temp_name)
        temp_db = temp_dir / BACKUP_DB_NAME
        temp_config = temp_dir / BACKUP_CONFIG_NAME
        temp_metadata = temp_dir / BACKUP_METADATA_NAME
        temp_zip = temp_dir / "backup.zip"

        sqlite_snapshot(db_file, temp_db)
        if config_file.is_file():
            shutil.copy2(config_file, temp_config)
        else:
            temp_config.write_text("{}\n", encoding="utf-8")

        summary = database_summary(temp_db, temp_config)
        integrity_check = sqlite_integrity_check(temp_db)
        metadata = {
            "app_name": APP_NAME,
            "app_version": app_version,
            "backup_type": backup_type,
            "created_at": created_at,
            "schema_version": database_schema_version(temp_db) or 1,
            "database_file": BACKUP_DB_NAME,
            "config_file": BACKUP_CONFIG_NAME,
            "image_files_included": False,
            "thumbnail_cache_included": False,
            "summary": summary,
            "integrity_check": integrity_check,
        }
        temp_metadata.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_db, BACKUP_DB_NAME)
            archive.write(temp_config, BACKUP_CONFIG_NAME)
            archive.write(temp_metadata, BACKUP_METADATA_NAME)
        shutil.move(str(temp_zip), final_zip)

    return backup_info(final_zip)


def read_backup_metadata(zip_path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            raw = archive.read(BACKUP_METADATA_NAME)
    except (KeyError, zipfile.BadZipFile, FileNotFoundError) as exc:
        raise ValueError("备份文件无效：缺少 metadata") from exc
    try:
        metadata = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("备份文件 metadata 不是合法 JSON") from exc
    if not isinstance(metadata, dict) or metadata.get("app_name") != APP_NAME:
        raise ValueError("备份文件不是意绘备份")
    return metadata


def backup_info(zip_path: Path) -> dict[str, Any]:
    metadata = read_backup_metadata(zip_path)
    stat = zip_path.stat()
    return {
        "file_name": zip_path.name,
        "path": str(zip_path),
        "backup_type": str(metadata.get("backup_type") or ""),
        "app_version": str(metadata.get("app_version") or ""),
        "schema_version": int(metadata.get("schema_version") or 0),
        "created_at": str(metadata.get("created_at") or ""),
        "size_bytes": stat.st_size,
        "size_label": size_label(stat.st_size),
        "summary": metadata.get("summary") if isinstance(metadata.get("summary"), dict) else None,
        "integrity_check": str(metadata.get("integrity_check") or ""),
    }


def list_backups(backup_dir: Path) -> list[dict[str, Any]]:
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for zip_path in backup_dir.glob(f"{APP_NAME}_backup_*.zip"):
        try:
            items.append(backup_info(zip_path))
        except ValueError:
            continue
    return sorted(items, key=lambda item: (item["created_at"], item["file_name"]), reverse=True)


def prune_auto_backups(backup_dir: Path, keep: int = AUTO_BACKUP_KEEP) -> None:
    auto_items = [
        item for item in list_backups(backup_dir)
        if item.get("backup_type") == "auto"
    ]
    for item in auto_items[max(0, keep):]:
        Path(item["path"]).unlink(missing_ok=True)


def has_auto_backup_today(backup_dir: Path) -> bool:
    today = datetime.now().date().isoformat()
    return any(
        item.get("backup_type") == "auto"
        and str(item.get("created_at", "")).startswith(today)
        for item in list_backups(backup_dir)
    )


def create_daily_auto_backup(
    db_file: Path,
    config_file: Path,
    backup_dir: Path,
    app_version: str,
) -> dict[str, Any] | None:
    if has_auto_backup_today(backup_dir):
        return None
    backup = create_backup(db_file, config_file, backup_dir, app_version, "auto")
    prune_auto_backups(backup_dir, AUTO_BACKUP_KEEP)
    return backup


def export_json(
    db_file: Path,
    config_file: Path,
    export_dir: Path,
    app_version: str,
) -> dict[str, Any]:
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    exported_at, stamp = now_stamp()
    export_path = export_dir / f"{APP_NAME}_export_{app_version}_{stamp}.json"
    index = 1
    while export_path.exists():
        export_path = export_dir / f"{APP_NAME}_export_{app_version}_{stamp}_{index:02d}.json"
        index += 1

    payload = build_export_payload(db_file, config_file, app_version, exported_at)
    export_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"path": str(export_path)}


def export_data_package(
    db_file: Path,
    config_file: Path,
    export_dir: Path,
    app_version: str,
    *,
    batch_size: int = 1000,
    progress_callback=None,
) -> dict[str, Any]:
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    exported_at, stamp = now_stamp()
    stem = f"{APP_NAME}_export_{app_version}_{stamp}"
    export_path = unique_path(export_dir, stem, ".zip")
    temp_path = export_temp_path(export_path)
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    settings = read_config_file(config_file)
    try:
        table_counts = {table: table_count(conn, table) for table in EXPORT_TABLES}
        total_rows = sum(table_counts.values())
        summary = database_summary(db_file, config_file)
        manifest = {
            "app_name": APP_NAME,
            "app_version": app_version,
            "export_format": "zip-jsonl",
            "export_format_version": EXPORT_FORMAT_VERSION,
            "exported_at": exported_at,
            "schema_version": database_schema_version(db_file) or 1,
            "image_files_included": False,
            "thumbnail_cache_included": False,
            "tables": {table: {"count": table_counts[table]} for table in EXPORT_TABLES},
            "summary": summary,
        }
        processed_rows = 0
        if progress_callback:
            progress_callback(
                phase="准备导出",
                message="正在准备导出数据",
                processed_rows=0,
                total_rows=total_rows,
            )
        try:
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "export_manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                )
                archive.writestr(
                    "settings.json",
                    json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
                )
                for table in EXPORT_TABLES:
                    label = EXPORT_TABLE_LABELS.get(table, table)
                    if progress_callback:
                        progress_callback(
                            phase=table,
                            message=f"正在导出{label}",
                            processed_rows=processed_rows,
                            total_rows=total_rows,
                        )
                    with archive.open(f"tables/{table}.jsonl", "w") as handle:
                        for row in iter_table_rows(conn, table, batch_size=batch_size):
                            handle.write(json_dumps_line(row))
                            processed_rows += 1
                            if progress_callback and processed_rows % max(1, min(batch_size, 1000)) == 0:
                                progress_callback(
                                    phase=table,
                                    message=f"正在导出{label}",
                                    processed_rows=processed_rows,
                                    total_rows=total_rows,
                                )
                if progress_callback:
                    progress_callback(
                        phase="写入导出包",
                        message="正在写入导出包",
                        processed_rows=processed_rows,
                        total_rows=total_rows,
                    )
            os.replace(temp_path, export_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    finally:
        conn.close()
    return {"path": str(export_path), "summary": summary, "manifest": manifest}


def build_export_payload(
    db_file: Path,
    config_file: Path,
    app_version: str,
    exported_at: str | None = None,
) -> dict[str, Any]:
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        database: dict[str, list[dict[str, Any]]] = {}
        for table in [
            "nodes",
            "instances",
            "input_images",
            "tags",
            "instance_tags",
            "generation_history",
            "app_metadata",
        ]:
            database[table] = [
                dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()
            ]
    finally:
        conn.close()

    config = json.loads(config_file.read_text(encoding="utf-8")) if Path(config_file).is_file() else {}
    return {
        "app_name": APP_NAME,
        "app_version": app_version,
        "exported_at": exported_at or now_stamp()[0],
        "schema_version": database_schema_version(db_file) or 1,
        "image_files_included": False,
        "settings": config,
        "database": database,
    }


def validate_backup_archive(zip_path: Path, temp_dir: Path) -> tuple[Path, Path, dict[str, Any]]:
    metadata = read_backup_metadata(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        if BACKUP_DB_NAME not in names or BACKUP_CONFIG_NAME not in names:
            raise ValueError("备份文件缺少数据库或配置")
        archive.extract(BACKUP_DB_NAME, temp_dir)
        archive.extract(BACKUP_CONFIG_NAME, temp_dir)
    extracted_db = temp_dir / BACKUP_DB_NAME
    extracted_config = temp_dir / BACKUP_CONFIG_NAME
    conn = sqlite3.connect(extracted_db)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("备份数据库校验失败")
    finally:
        conn.close()
    try:
        raw_config = json.loads(extracted_config.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("备份配置不是合法 JSON") from exc
    normalized_config = normalize_config(raw_config if isinstance(raw_config, dict) else {})
    save_config(extracted_config, normalized_config)
    return extracted_db, extracted_config, metadata


def required_export_members() -> set[str]:
    return {
        "export_manifest.json",
        "settings.json",
        *{f"tables/{table}.jsonl" for table in EXPORT_TABLES},
    }


def read_jsonl_member(archive: zipfile.ZipFile, member: str) -> list[dict[str, Any]]:
    try:
        raw = archive.read(member).decode("utf-8")
    except KeyError as exc:
        raise ValueError(f"导出包缺少 {member}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{member} 第 {line_number} 行不是合法 JSON") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_data_package(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            missing = required_export_members() - names
            if missing:
                raise ValueError(f"导出包缺少文件：{', '.join(sorted(missing))}")
            manifest = json.loads(archive.read("export_manifest.json").decode("utf-8"))
            settings = json.loads(archive.read("settings.json").decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("app_name") != APP_NAME:
                raise ValueError("恢复文件不是意绘导出包")
            if manifest.get("export_format") != "zip-jsonl":
                raise ValueError("导出包格式不受支持")
            database = {
                table: read_jsonl_member(archive, f"tables/{table}.jsonl")
                for table in EXPORT_TABLES
            }
    except zipfile.BadZipFile as exc:
        raise ValueError("恢复文件不是合法 zip 文件") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("导出包 manifest 或 settings 不是合法 JSON") from exc
    if not isinstance(settings, dict):
        settings = {}
    return {
        "app_name": APP_NAME,
        "app_version": manifest.get("app_version", ""),
        "exported_at": manifest.get("exported_at", ""),
        "schema_version": manifest.get("schema_version", 0),
        "image_files_included": False,
        "thumbnail_cache_included": False,
        "settings": settings,
        "database": database,
        "manifest": manifest,
    }


def detect_restore_file_type(path: Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise ValueError("恢复文件不存在")
    if path.suffix.lower() == ".json":
        return "json_export"
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        raise ValueError("恢复文件不是合法 zip 或 JSON 文件") from None
    if "export_manifest.json" in names:
        return "zip_export"
    if BACKUP_DB_NAME in names:
        return "sqlite_backup"
    raise ValueError("恢复文件不是支持的备份或导出文件")


def summary_from_payload(payload: dict[str, Any]) -> dict[str, int]:
    manifest = payload.get("manifest")
    if isinstance(manifest, dict) and isinstance(manifest.get("summary"), dict):
        raw_summary = manifest["summary"]
        return {
            key: int(raw_summary.get(key) or 0)
            for key in [
                "instance_count",
                "input_image_count",
                "output_image_count",
                "tag_count",
                "node_count",
                "generation_history_count",
                "provider_count",
            ]
        }
    database = payload.get("database", {}) if isinstance(payload.get("database"), dict) else {}
    instances = database.get("instances", [])
    input_images = database.get("input_images", [])
    tags = database.get("tags", [])
    nodes = database.get("nodes", [])
    generation_history = database.get("generation_history", [])
    settings = payload.get("settings", {}) if isinstance(payload.get("settings"), dict) else {}
    output_count = sum(
        1
        for row in instances
        if isinstance(row, dict) and str(row.get("output_image_path") or "").strip()
    )
    return {
        "instance_count": len(instances) if isinstance(instances, list) else 0,
        "input_image_count": len(input_images) if isinstance(input_images, list) else 0,
        "output_image_count": output_count,
        "tag_count": len(tags) if isinstance(tags, list) else 0,
        "node_count": len(nodes) if isinstance(nodes, list) else 0,
        "generation_history_count": len(generation_history) if isinstance(generation_history, list) else 0,
        "provider_count": provider_count_from_config(settings),
    }


def preview_restore_file(path: Path) -> dict[str, Any]:
    restore_type = detect_restore_file_type(path)
    if restore_type == "zip_export":
        payload = load_data_package(path)
        manifest = payload.get("manifest", {})
        return {
            "valid": True,
            "type": "zip_export",
            "app_version": str(manifest.get("app_version") or ""),
            "schema_version": int(manifest.get("schema_version") or 0),
            "image_files_included": bool(manifest.get("image_files_included")),
            "thumbnail_cache_included": bool(manifest.get("thumbnail_cache_included")),
            "summary": summary_from_payload(payload),
            "warnings": [],
        }
    if restore_type == "json_export":
        payload = validate_export_json(path)
        return {
            "valid": True,
            "type": "json_export",
            "app_version": str(payload.get("app_version") or ""),
            "schema_version": int(payload.get("schema_version") or 0),
            "image_files_included": bool(payload.get("image_files_included")),
            "thumbnail_cache_included": False,
            "summary": summary_from_payload(payload),
            "warnings": ["旧 JSON 导出文件，可以恢复，但没有完整 manifest。"],
        }
    with tempfile.TemporaryDirectory(prefix="ai-image-preview-") as temp_name:
        extracted_db, extracted_config, metadata = validate_backup_archive(path, Path(temp_name))
        return {
            "valid": True,
            "type": "sqlite_backup",
            "app_version": str(metadata.get("app_version") or ""),
            "schema_version": int(metadata.get("schema_version") or database_schema_version(extracted_db) or 0),
            "image_files_included": bool(metadata.get("image_files_included")),
            "thumbnail_cache_included": bool(metadata.get("thumbnail_cache_included")),
            "summary": metadata.get("summary") if isinstance(metadata.get("summary"), dict) else database_summary(extracted_db, extracted_config),
            "warnings": [] if metadata.get("summary") else ["旧备份没有完整摘要，已临时扫描数据库。"],
        }


def validate_export_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("恢复文件不存在") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("恢复文件不是合法 JSON") from exc
    if not isinstance(payload, dict) or payload.get("app_name") != APP_NAME:
        raise ValueError("恢复文件不是意绘导出")
    database = payload.get("database")
    if not isinstance(database, dict):
        raise ValueError("恢复文件缺少 database 数据")
    return payload


def normalize_restore_row_id(value: Any) -> int | None:
    try:
        row_id = int(value)
    except (TypeError, ValueError):
        return None
    return row_id if row_id > 0 else None


def insert_restore_nodes(
    conn: sqlite3.Connection,
    nodes: list[dict[str, Any]],
    reference_fixes: dict[str, int],
) -> set[int]:
    rows_by_id: dict[int, dict[str, Any]] = {}
    for row in nodes:
        if not isinstance(row, dict):
            continue
        node_id = normalize_restore_row_id(row.get("id"))
        if node_id is None:
            continue
        rows_by_id[node_id] = row

    parent_by_id: dict[int, int | None] = {}
    for node_id, row in rows_by_id.items():
        parent_id = row.get("parent_id")
        normalized_parent_id = None
        if parent_id not in {None, ""}:
            normalized_parent_id = normalize_restore_row_id(parent_id)
            if normalized_parent_id not in rows_by_id:
                reference_fixes["nodes_parent_missing_set_null"] += 1
                normalized_parent_id = None
        parent_by_id[node_id] = normalized_parent_id

    inserted: set[int] = set()
    visiting: set[int] = set()

    def insert_one(node_id: int) -> None:
        if node_id in inserted:
            return
        if node_id in visiting:
            raise ValueError("节点恢复失败：节点父级引用存在循环")
        visiting.add(node_id)
        parent_id = parent_by_id.get(node_id)
        if parent_id is not None:
            insert_one(parent_id)
        row = rows_by_id[node_id]
        try:
            conn.execute(
                """
                INSERT INTO nodes(id, parent_id, name, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    parent_id,
                    row.get("name", ""),
                    row.get("position", 0),
                    row.get("created_at") or "",
                    row.get("updated_at") or "",
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"节点恢复失败：{exc}") from exc
        inserted.add(node_id)
        visiting.remove(node_id)

    for node_id in rows_by_id:
        insert_one(node_id)
    return inserted


def restore_export_json(
    db_file: Path,
    config_file: Path,
    backup_dir: Path,
    export_path: Path,
    app_version: str,
) -> dict[str, Any]:
    payload = validate_export_json(export_path)
    return restore_export_payload(
        db_file,
        config_file,
        backup_dir,
        payload,
        app_version,
        create_pre_restore=True,
        source_info={"path": str(export_path), "type": "json_export"},
    )


def restore_export_payload(
    db_file: Path,
    config_file: Path,
    backup_dir: Path,
    payload: dict[str, Any],
    app_version: str,
    *,
    create_pre_restore: bool,
    source_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    database = payload.get("database", {})
    settings = payload.get("settings", {})
    nodes = database.get("nodes", [])
    instances = database.get("instances", [])
    input_images = database.get("input_images", [])
    tags = database.get("tags", [])
    instance_tags = database.get("instance_tags", [])
    generation_history = database.get("generation_history", [])
    app_metadata = database.get("app_metadata", [])

    if not all(isinstance(section, list) for section in [nodes, instances, input_images, tags, instance_tags, generation_history, app_metadata]):
        raise ValueError("恢复文件结构不正确")

    reference_fixes = dict(REFERENCE_FIX_KEYS)
    pre_restore = create_backup(db_file, config_file, backup_dir, app_version, "pre_restore") if create_pre_restore else None
    conn = get_connection(Path(db_file))
    try:
        init_db(conn)
        valid_node_ids: set[int] = set()
        valid_instance_ids: set[int] = set()
        valid_tag_ids: set[int] = set()
        with conn:
            for table in ["instance_tags", "input_images", "tags", "instances", "nodes", "generation_history", "app_metadata"]:
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DROP INDEX IF EXISTS idx_instances_instance_number")

            valid_node_ids = insert_restore_nodes(conn, nodes, reference_fixes)

            for row in instances:
                if not isinstance(row, dict):
                    continue
                node_id = row.get("node_id")
                try:
                    normalized_node_id = int(node_id) if node_id not in {None, ""} else None
                except (TypeError, ValueError):
                    normalized_node_id = None
                if normalized_node_id is not None and normalized_node_id not in valid_node_ids:
                    reference_fixes["instances_node_missing_set_null"] += 1
                    normalized_node_id = None
                elif normalized_node_id is None and node_id not in {None, ""}:
                    reference_fixes["instances_node_missing_set_null"] += 1
                    node_id = None
                conn.execute(
                    """
                    INSERT INTO instances(
                      id, instance_number, prompt, mode, source, provider, node_id, generation_path, generation_size,
                      generation_params_json, output_image_path, generation_status, generation_task_id,
                      generation_output_index, generation_error, generation_started_at,
                      generation_finished_at, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("id"),
                        row.get("instance_number"),
                        row.get("prompt", ""),
                        row.get("mode", "unspecified"),
                        row.get("source", "manual"),
                        row.get("provider"),
                        normalized_node_id,
                        row.get("generation_path", ""),
                        row.get("generation_size", ""),
                        row.get("generation_params_json", "{}"),
                        row.get("output_image_path", ""),
                        row.get("generation_status", "ready"),
                        row.get("generation_task_id", ""),
                        row.get("generation_output_index", 1),
                        row.get("generation_error", ""),
                        row.get("generation_started_at", ""),
                        row.get("generation_finished_at", ""),
                        row.get("created_at", ""),
                        row.get("updated_at", ""),
                    ),
                )
                if row.get("id") is not None:
                    valid_instance_ids.add(int(row.get("id")))

            for row in input_images:
                if isinstance(row, dict):
                    try:
                        instance_id = int(row.get("instance_id"))
                    except (TypeError, ValueError):
                        instance_id = 0
                    if instance_id not in valid_instance_ids:
                        reference_fixes["input_images_skipped_missing_instance"] += 1
                        continue
                    conn.execute(
                        "INSERT INTO input_images(id, instance_id, path, position) VALUES (?, ?, ?, ?)",
                        (row.get("id"), instance_id, row.get("path", ""), row.get("position", 0)),
                    )

            for row in tags:
                if isinstance(row, dict):
                    tag_id = row.get("id")
                    if tag_id is None:
                        continue
                    conn.execute(
                        "INSERT INTO tags(id, name) VALUES (?, ?)",
                        (tag_id, row.get("name", "")),
                    )
                    valid_tag_ids.add(int(tag_id))

            for row in instance_tags:
                if isinstance(row, dict):
                    try:
                        instance_id = int(row.get("instance_id"))
                    except (TypeError, ValueError):
                        instance_id = 0
                    try:
                        tag_id = int(row.get("tag_id"))
                    except (TypeError, ValueError):
                        tag_id = 0
                    if instance_id not in valid_instance_ids:
                        reference_fixes["instance_tags_skipped_missing_instance"] += 1
                        continue
                    if tag_id not in valid_tag_ids:
                        reference_fixes["instance_tags_skipped_missing_tag"] += 1
                        continue
                    conn.execute(
                        "INSERT INTO instance_tags(instance_id, tag_id) VALUES (?, ?)",
                        (instance_id, tag_id),
                    )

            for row in generation_history:
                if isinstance(row, dict):
                    conn.execute(
                        """
                        INSERT INTO generation_history(
                          id, status, prompt, mode, provider_key, adapter, openai_call_method,
                          generation_path, resolved_size, params_json, input_image_paths_json,
                          output_image_paths_json, tags_json, error_message, custom_script_used,
                          started_at, finished_at, duration_ms
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row.get("id"),
                            row.get("status", "running"),
                            row.get("prompt", ""),
                            row.get("mode", ""),
                            row.get("provider_key", ""),
                            row.get("adapter", ""),
                            row.get("openai_call_method", ""),
                            row.get("generation_path", ""),
                            row.get("resolved_size", ""),
                            row.get("params_json", "{}"),
                            row.get("input_image_paths_json", "[]"),
                            row.get("output_image_paths_json", "[]"),
                            row.get("tags_json", "[]"),
                            row.get("error_message", ""),
                            row.get("custom_script_used", 0),
                            row.get("started_at", ""),
                            row.get("finished_at", ""),
                            row.get("duration_ms", 0),
                        ),
                    )

            for row in app_metadata:
                if isinstance(row, dict) and row.get("key") and row.get("value") is not None:
                    conn.execute(
                        "INSERT INTO app_metadata(key, value) VALUES (?, ?)",
                        (row.get("key"), row.get("value")),
                    )
            reference_fixes.update(repair_instance_numbers(conn))

        normalized_config = normalize_config(settings if isinstance(settings, dict) else {})
        save_config(config_file, normalized_config)
        init_db(conn)
        summary = database_summary(db_file, config_file)
    finally:
        conn.close()
    return {
        "restored": True,
        "backup": source_info or {"type": "json_export"},
        "pre_restore_backup": pre_restore,
        "summary": summary,
        "reference_fixes": reference_fixes,
        "metadata": {
            "app_version": payload.get("app_version", ""),
            "schema_version": payload.get("schema_version", 0),
            "source": source_info.get("type", "json_export") if source_info else "json_export",
        },
    }


def restore_data_package(
    db_file: Path,
    config_file: Path,
    backup_dir: Path,
    package_path: Path,
    app_version: str,
) -> dict[str, Any]:
    payload = load_data_package(package_path)
    return restore_export_payload(
        db_file,
        config_file,
        backup_dir,
        payload,
        app_version,
        create_pre_restore=True,
        source_info={"path": str(package_path), "type": "zip_export"},
    )


def replace_database_file(current_db: Path, replacement_db: Path) -> None:
    current_db.parent.mkdir(parents=True, exist_ok=True)
    temp_target = current_db.with_suffix(current_db.suffix + ".restore_tmp")
    shutil.copy2(replacement_db, temp_target)
    os.replace(temp_target, current_db)
    for suffix in ("-wal", "-shm"):
        current_db.with_name(current_db.name + suffix).unlink(missing_ok=True)


def restore_backup(
    db_file: Path,
    config_file: Path,
    backup_dir: Path,
    backup_path: Path,
    app_version: str,
) -> dict[str, Any]:
    backup_path = Path(backup_path)
    if not backup_path.is_file():
        raise ValueError("备份文件不存在")
    with tempfile.TemporaryDirectory(prefix="ai-image-restore-") as temp_name:
        temp_dir = Path(temp_name)
        extracted_db, extracted_config, metadata = validate_backup_archive(backup_path, temp_dir)
        pre_restore = create_backup(db_file, config_file, backup_dir, app_version, "pre_restore")
        summary = metadata.get("summary") if isinstance(metadata.get("summary"), dict) else database_summary(extracted_db, extracted_config)
        replace_database_file(Path(db_file), extracted_db)
        conn = get_connection(Path(db_file))
        try:
            init_db(conn)
        finally:
            conn.close()
        Path(config_file).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted_config, config_file)
    return {
        "restored": True,
        "backup": backup_info(backup_path),
        "pre_restore_backup": pre_restore,
        "summary": summary,
        "reference_fixes": dict(REFERENCE_FIX_KEYS),
        "metadata": metadata,
    }


def open_backup_folder(backup_dir: Path) -> None:
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(backup_dir))  # type: ignore[attr-defined]
        return
    raise RuntimeError("当前系统不支持打开文件夹")
