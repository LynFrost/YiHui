import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from backend.backup import (
    AUTO_BACKUP_KEEP,
    create_backup,
    list_backups,
    prune_auto_backups,
)
from backend.config import load_config
from backend.database import create_generation_history, create_instance, create_node, get_connection, init_db


def wait_export_task(client, task_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    last_payload = {}
    while time.monotonic() < deadline:
        resp = client.get(f"/api/exports/tasks/{task_id}")
        assert resp.status_code == 200
        last_payload = resp.get_json()
        if last_payload.get("status") != "running":
            return last_payload
        time.sleep(0.05)
    raise AssertionError(f"export task did not finish: {last_payload}")


def write_jsonl_export_package(path: Path, manifest: dict, settings: dict, tables: dict[str, list[dict]]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("export_manifest.json", json.dumps(manifest, ensure_ascii=False))
        archive.writestr("settings.json", json.dumps(settings, ensure_ascii=False))
        for table in [
            "nodes",
            "instances",
            "input_images",
            "tags",
            "instance_tags",
            "generation_history",
            "app_metadata",
        ]:
            rows = tables.get(table, [])
            archive.writestr(
                f"tables/{table}.jsonl",
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            )


def make_app(tmp_path: Path):
    app = create_app(
        db_file=tmp_path / "data" / "test.sqlite",
        config_file=tmp_path / "config" / "config.json",
        backup_dir=tmp_path / "backup",
        export_dir=tmp_path / "export",
        auto_backup=False,
    )
    app.config.update(TESTING=True)
    return app


def test_create_backup_writes_zip_with_sqlite_config_and_metadata(tmp_path):
    db_file = tmp_path / "data.sqlite"
    config_file = tmp_path / "config.json"
    backup_dir = tmp_path / "backup"
    conn = get_connection(db_file)
    init_db(conn)
    create_instance(conn, {"prompt": "备份测试", "tags": ["安全"]})
    conn.close()
    config_file.write_text(
        json.dumps({"active_provider": "aiapis_gpt_image_2"}, ensure_ascii=False),
        encoding="utf-8",
    )

    backup = create_backup(db_file, config_file, backup_dir, "V0.23", "manual")

    assert backup["backup_type"] == "manual"
    assert backup["app_version"] == "V0.23"
    zip_path = Path(backup["path"])
    assert zip_path.is_file()
    assert zip_path.name.startswith("AIImageManager_backup_manual_V0.23_")
    with zipfile.ZipFile(zip_path) as archive:
        assert set(archive.namelist()) == {
            "AIImageManager.data.sqlite",
            "AIImageManager.config.json",
            "backup_metadata.json",
        }
        metadata = json.loads(archive.read("backup_metadata.json").decode("utf-8"))
        assert metadata["schema_version"] == 5
        assert metadata["image_files_included"] is False
        extracted_db = tmp_path / "extracted.sqlite"
        extracted_db.write_bytes(archive.read("AIImageManager.data.sqlite"))
    check_conn = sqlite3.connect(extracted_db)
    try:
        assert check_conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert check_conn.execute("SELECT prompt FROM instances").fetchone()[0] == "备份测试"
    finally:
        check_conn.close()


def test_list_backups_reads_metadata_and_size(tmp_path):
    db_file = tmp_path / "data.sqlite"
    config_file = tmp_path / "config.json"
    backup_dir = tmp_path / "backup"
    conn = get_connection(db_file)
    init_db(conn)
    conn.close()
    load_config(config_file)

    create_backup(db_file, config_file, backup_dir, "V0.23", "manual")
    items = list_backups(backup_dir)

    assert len(items) == 1
    assert items[0]["backup_type"] == "manual"
    assert items[0]["size_bytes"] > 0
    assert items[0]["size_label"].endswith(("B", "KB", "MB"))


def test_prune_auto_backups_keeps_recent_auto_only(tmp_path):
    db_file = tmp_path / "data.sqlite"
    config_file = tmp_path / "config.json"
    backup_dir = tmp_path / "backup"
    conn = get_connection(db_file)
    init_db(conn)
    conn.close()
    load_config(config_file)

    manual = create_backup(db_file, config_file, backup_dir, "V0.23", "manual")
    for _ in range(AUTO_BACKUP_KEEP + 2):
        create_backup(db_file, config_file, backup_dir, "V0.23", "auto")

    prune_auto_backups(backup_dir, AUTO_BACKUP_KEEP)
    items = list_backups(backup_dir)

    assert Path(manual["path"]).is_file()
    assert sum(1 for item in items if item["backup_type"] == "auto") == AUTO_BACKUP_KEEP
    assert sum(1 for item in items if item["backup_type"] == "manual") == 1


def test_export_json_endpoint_includes_database_and_settings_without_images(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    conn = get_connection(Path(app.config["DB_FILE"]))
    node_id = create_node(conn, None, "导出节点")
    conn.close()
    client.post(
        "/api/instances",
        json={
            "prompt": "导出测试",
            "input_image_paths": ["C:\\Images\\input.png"],
            "output_image_path": "C:\\Images\\output.png",
            "tags": ["导出"],
            "node_id": node_id,
        },
    )

    resp = client.post("/api/exports/json")

    assert resp.status_code == 200
    export_path = Path(resp.get_json()["path"])
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["app_version"] == "V0.67"
    assert payload["image_files_included"] is False
    assert payload["settings"]["active_provider"] == "aiapis_gpt_image_2"
    assert payload["database"]["instances"][0]["prompt"] == "导出测试"
    assert payload["database"]["instances"][0]["node_id"] == node_id
    assert payload["database"]["nodes"][0]["name"] == "导出节点"
    assert payload["database"]["input_images"][0]["path"] == "C:\\Images\\input.png"
    assert payload["database"]["tags"][0]["name"] == "导出"
    assert payload["database"]["instances"][0]["instance_number"] == 1


def test_v067_restore_old_json_without_instance_numbers_backfills_fixed_numbers(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    restore_json = tmp_path / "restore-old.json"
    restore_json.write_text(
        json.dumps(
            {
                "app_name": "AIImageManager",
                "app_version": "V0.67",
                "schema_version": 4,
                "settings": {},
                "database": {
                    "nodes": [],
                    "instances": [
                        {
                            "id": 10,
                            "prompt": "later",
                            "mode": "text_to_image",
                            "source": "manual",
                            "provider": "",
                            "node_id": None,
                            "generation_path": "",
                            "generation_size": "",
                            "generation_params_json": "{}",
                            "output_image_path": "",
                            "generation_status": "ready",
                            "generation_task_id": "",
                            "generation_output_index": 1,
                            "generation_error": "",
                            "generation_started_at": "",
                            "generation_finished_at": "",
                            "created_at": "2026-05-02T10:00:00",
                            "updated_at": "2026-05-02T10:00:00",
                        },
                        {
                            "id": 20,
                            "prompt": "earlier",
                            "mode": "text_to_image",
                            "source": "manual",
                            "provider": "",
                            "node_id": None,
                            "generation_path": "",
                            "generation_size": "",
                            "generation_params_json": "{}",
                            "output_image_path": "",
                            "generation_status": "ready",
                            "generation_task_id": "",
                            "generation_output_index": 1,
                            "generation_error": "",
                            "generation_started_at": "",
                            "generation_finished_at": "",
                            "created_at": "2026-05-01T10:00:00",
                            "updated_at": "2026-05-01T10:00:00",
                        },
                    ],
                    "input_images": [],
                    "tags": [],
                    "instance_tags": [],
                    "generation_history": [],
                    "app_metadata": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resp = client.post("/api/restore", json={"path": str(restore_json), "confirmed": True})

    assert resp.status_code == 200
    items = client.get("/api/instances?sort=number_asc&per_page=50").get_json()["items"]
    assert [item["prompt"] for item in items] == ["earlier", "later"]
    assert [item["instance_number"] for item in items] == [1, 2]


def test_v037_export_task_writes_zip_jsonl_package_with_manifest_and_snapshots(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    config_path = Path(app.config["CONFIG_FILE"])
    config_path.write_text(
        json.dumps(
            {
                "active_provider": "aiapis_gpt_image_2",
                "providers": {
                    "aiapis_gpt_image_2": {
                        "display_name": "AIAPIS",
                        "adapter": "openai",
                        "quality": "high",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    conn = get_connection(Path(app.config["DB_FILE"]))
    node_id = create_node(conn, None, "导出节点")
    create_instance(
        conn,
        {
            "prompt": "批量导出",
            "input_image_paths": ["C:\\Images\\input.png"],
            "output_image_path": "C:\\Images\\output.png",
            "tags": ["导出"],
            "node_id": node_id,
            "generation_params": {"provider_key": "aiapis_gpt_image_2", "adapter": "openai"},
        },
    )
    create_generation_history(
        conn,
        {
            "status": "success",
            "prompt": "批量导出",
            "mode": "text_to_image",
            "provider_key": "aiapis_gpt_image_2",
            "adapter": "openai",
            "params": {"provider_key": "aiapis_gpt_image_2", "quality": "high"},
            "output_image_paths": ["C:\\Images\\output.png"],
        },
    )
    conn.close()

    start_resp = client.post("/api/exports")

    assert start_resp.status_code == 202
    result = wait_export_task(client, start_resp.get_json()["task_id"])
    assert result["status"] == "success"
    assert result["message"] == "导出完成"
    export_path = Path(result["path"])
    assert export_path.name.startswith("AIImageManager_export_V0.67_")
    assert export_path.suffix == ".zip"
    assert result["summary"]["instance_count"] == 1
    assert result["summary"]["input_image_count"] == 1
    assert result["summary"]["output_image_count"] == 1
    assert result["summary"]["tag_count"] == 1
    assert result["summary"]["node_count"] == 1
    assert result["summary"]["generation_history_count"] == 1
    assert result["summary"]["provider_count"] == 1
    with zipfile.ZipFile(export_path) as archive:
        assert {
            "export_manifest.json",
            "settings.json",
            "tables/nodes.jsonl",
            "tables/instances.jsonl",
            "tables/input_images.jsonl",
            "tables/tags.jsonl",
            "tables/instance_tags.jsonl",
            "tables/generation_history.jsonl",
            "tables/app_metadata.jsonl",
        }.issubset(set(archive.namelist()))
        manifest = json.loads(archive.read("export_manifest.json").decode("utf-8"))
        settings = json.loads(archive.read("settings.json").decode("utf-8"))
        instance_rows = [
            json.loads(line)
            for line in archive.read("tables/instances.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
        history_rows = [
            json.loads(line)
            for line in archive.read("tables/generation_history.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
    assert manifest["export_format"] == "zip-jsonl"
    assert manifest["thumbnail_cache_included"] is False
    assert manifest["image_files_included"] is False
    assert manifest["summary"]["provider_count"] == 1
    assert settings["providers"]["aiapis_gpt_image_2"]["adapter"] == "openai"
    assert json.loads(instance_rows[0]["generation_params_json"])["adapter"] == "openai"
    assert json.loads(history_rows[0]["params_json"])["quality"] == "high"
    assert not list(export_path.parent.glob("*.zip.zip.tmp"))


def test_v037_export_temp_file_uses_documented_zip_tmp_name_and_chinese_progress(tmp_path):
    app = make_app(tmp_path)
    progress_events = []
    from backend.backup import export_data_package

    export_data_package(
        Path(app.config["DB_FILE"]),
        Path(app.config["CONFIG_FILE"]),
        Path(app.config["EXPORT_DIR"]),
        "V0.67",
        progress_callback=lambda **event: progress_events.append(event),
    )

    messages = [event.get("message", "") for event in progress_events]
    assert "正在导出实例" in messages
    assert "正在导出节点" in messages
    assert "正在导出标签" in messages
    assert "正在导出历史记录" in messages
    assert not list(Path(app.config["EXPORT_DIR"]).glob("*.zip.zip.tmp"))


def test_v037_export_task_rejects_duplicate_running_task(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    client = app.test_client()
    blocker = tmp_path / "blocker"
    blocker.write_text("wait", encoding="utf-8")

    import backend.backup as backup_module

    original_iter = backup_module.iter_table_rows

    def slow_iter(*args, **kwargs):
        while blocker.exists():
            time.sleep(0.02)
        yield from original_iter(*args, **kwargs)

    monkeypatch.setattr(backup_module, "iter_table_rows", slow_iter)
    first = client.post("/api/exports")
    second = client.post("/api/exports")
    blocker.unlink()

    assert first.status_code == 202
    assert second.status_code == 409
    result = wait_export_task(client, first.get_json()["task_id"])
    assert result["status"] == "success"


def test_restore_endpoint_requires_confirmation(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    resp = client.post("/api/restore", json={"path": str(tmp_path / "missing.zip")})

    assert resp.status_code == 400
    assert "确认" in resp.get_json()["error"]


def test_restore_endpoint_replaces_database_and_config_after_pre_restore_backup(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    client.post("/api/instances", json={"prompt": "当前数据", "tags": ["当前"]})
    source_backup = client.post("/api/backups", json={"backup_type": "manual"}).get_json()
    client.post(
        "/api/instances",
        json={"prompt": "恢复前新增数据", "tags": ["恢复前"]},
    )

    resp = client.post(
        "/api/restore",
        json={"path": source_backup["path"], "confirmed": True},
    )

    assert resp.status_code == 200
    after = client.get("/api/instances").get_json()
    assert after["total"] == 1
    assert after["items"][0]["prompt"] == "当前数据"
    backups = client.get("/api/backups").get_json()["items"]
    assert any(item["backup_type"] == "pre_restore" for item in backups)


def test_restore_endpoint_accepts_json_export_and_restores_nodes_then_instances(tmp_path):
    source_app = make_app(tmp_path / "source")
    source_client = source_app.test_client()
    source_conn = get_connection(Path(source_app.config["DB_FILE"]))
    node_id = create_node(source_conn, None, "人像")
    source_conn.close()
    source_client.post(
        "/api/instances",
        json={
            "prompt": "JSON恢复测试",
            "tags": ["恢复"],
            "node_id": node_id,
        },
    )
    export_path = Path(source_client.post("/api/exports/json").get_json()["path"])

    target_app = make_app(tmp_path / "target")
    target_client = target_app.test_client()
    target_client.post("/api/instances", json={"prompt": "旧数据", "tags": ["旧"]})

    resp = target_client.post(
        "/api/restore",
        json={"path": str(export_path), "confirmed": True},
    )

    assert resp.status_code == 200
    payload = target_client.get("/api/instances").get_json()
    assert payload["total"] == 1
    assert payload["items"][0]["prompt"] == "JSON恢复测试"
    assert payload["items"][0]["node_id"] == 1
    backups = target_client.get("/api/backups").get_json()["items"]
    assert any(item["backup_type"] == "pre_restore" for item in backups)


def test_restore_json_sets_missing_instance_node_to_null(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    export_dir = tmp_path / "json"
    export_dir.mkdir(parents=True, exist_ok=True)
    restore_json = export_dir / "restore.json"
    restore_json.write_text(
        json.dumps(
            {
                "app_name": "AIImageManager",
        "app_version": "V0.39",
                "exported_at": "2026-05-06T00:00:00",
                "schema_version": 3,
                "image_files_included": False,
                "settings": {"active_provider": "aiapis_gpt_image_2"},
                "database": {
                    "nodes": [],
                    "instances": [
                        {
                            "id": 1,
                            "prompt": "缺失节点",
                            "mode": "text_to_image",
                            "source": "generated",
                            "provider": "test",
                            "node_id": 999,
                            "generation_path": "",
                            "generation_size": "",
                            "generation_params_json": "{}",
                            "output_image_path": "",
                            "generation_status": "ready",
                            "generation_task_id": "",
                            "generation_output_index": 1,
                            "generation_error": "",
                            "generation_started_at": "",
                            "generation_finished_at": "",
                            "created_at": "2026-05-06T00:00:00",
                            "updated_at": "2026-05-06T00:00:00",
                        }
                    ],
                    "input_images": [],
                    "tags": [],
                    "instance_tags": [],
                    "generation_history": [],
                    "app_metadata": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resp = client.post(
        "/api/restore",
        json={"path": str(restore_json), "confirmed": True},
    )

    assert resp.status_code == 200
    payload = client.get("/api/instances").get_json()
    assert payload["total"] == 1
    assert payload["items"][0]["node_id"] is None


def test_v037_restore_preview_reads_zip_jsonl_export_summary(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    export_path = tmp_path / "restore.zip"
    manifest = {
        "app_name": "AIImageManager",
        "app_version": "V0.39",
        "export_format": "zip-jsonl",
        "export_format_version": 1,
        "schema_version": 3,
        "image_files_included": False,
        "thumbnail_cache_included": False,
        "summary": {
            "instance_count": 2,
            "input_image_count": 3,
            "output_image_count": 1,
            "tag_count": 4,
            "node_count": 5,
            "generation_history_count": 6,
            "provider_count": 1,
        },
    }
    write_jsonl_export_package(export_path, manifest, {"providers": {"p": {}}}, {})

    resp = client.post("/api/restore/preview", json={"path": str(export_path)})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["valid"] is True
    assert payload["type"] == "zip_export"
    assert payload["app_version"] == "V0.39"
    assert payload["summary"]["instance_count"] == 2
    assert payload["summary"]["provider_count"] == 1
    assert payload["thumbnail_cache_included"] is False


def test_v037_restore_zip_jsonl_repairs_bad_references_and_reports_summary(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    client.post("/api/instances", json={"prompt": "恢复前数据", "tags": ["旧"]})
    export_path = tmp_path / "restore.zip"
    manifest = {
        "app_name": "AIImageManager",
        "app_version": "V0.39",
        "export_format": "zip-jsonl",
        "export_format_version": 1,
        "schema_version": 3,
        "image_files_included": False,
        "thumbnail_cache_included": False,
        "summary": {},
    }
    write_jsonl_export_package(
        export_path,
        manifest,
        {"active_provider": "provider-a", "providers": {"provider-a": {"adapter": "openai"}}},
        {
            "nodes": [
                {
                    "id": 10,
                    "parent_id": 999,
                    "name": "孤儿节点",
                    "position": 1,
                    "created_at": "2026-05-08T00:00:00",
                    "updated_at": "2026-05-08T00:00:00",
                }
            ],
            "instances": [
                {
                    "id": 20,
                    "prompt": "恢复实例",
                    "mode": "text_to_image",
                    "source": "generated",
                    "provider": "provider-a",
                    "node_id": 888,
                    "generation_path": "C:\\out",
                    "generation_size": "1024x1024",
                    "generation_params_json": json.dumps({"adapter": "openai"}),
                    "output_image_path": "C:\\out\\one.png",
                    "generation_status": "ready",
                    "generation_task_id": "",
                    "generation_output_index": 1,
                    "generation_error": "",
                    "generation_started_at": "",
                    "generation_finished_at": "",
                    "created_at": "2026-05-08T00:00:00",
                    "updated_at": "2026-05-08T00:00:00",
                }
            ],
            "input_images": [
                {"id": 30, "instance_id": 20, "path": "C:\\in\\ok.png", "position": 0},
                {"id": 31, "instance_id": 999, "path": "C:\\in\\bad.png", "position": 0},
            ],
            "tags": [{"id": 40, "name": "恢复"}],
            "instance_tags": [
                {"instance_id": 20, "tag_id": 40},
                {"instance_id": 999, "tag_id": 40},
                {"instance_id": 20, "tag_id": 999},
            ],
            "generation_history": [
                {
                    "id": 50,
                    "status": "success",
                    "prompt": "历史",
                    "mode": "text_to_image",
                    "provider_key": "provider-a",
                    "adapter": "openai",
                    "openai_call_method": "gpt-image-2",
                    "generation_path": "C:\\out",
                    "resolved_size": "1024x1024",
                    "params_json": json.dumps({"provider_key": "provider-a"}),
                    "input_image_paths_json": "[]",
                    "output_image_paths_json": "[]",
                    "error_message": "",
                    "custom_script_used": 0,
                    "started_at": "2026-05-08T00:00:00",
                    "finished_at": "2026-05-08T00:00:01",
                    "duration_ms": 1000,
                }
            ],
            "app_metadata": [{"key": "schema_version", "value": "3"}],
        },
    )

    resp = client.post("/api/restore", json={"path": str(export_path), "confirmed": True})

    assert resp.status_code == 200
    result = resp.get_json()
    assert result["summary"]["instance_count"] == 1
    assert result["summary"]["input_image_count"] == 1
    assert result["summary"]["tag_count"] == 1
    assert result["summary"]["generation_history_count"] == 1
    assert result["reference_fixes"] == {
        "instances_node_missing_set_null": 1,
        "instances_instance_number_repaired": 1,
        "input_images_skipped_missing_instance": 1,
        "instance_tags_skipped_missing_instance": 1,
        "instance_tags_skipped_missing_tag": 1,
        "nodes_parent_missing_set_null": 1,
    }
    assert result["pre_restore_backup"]["backup_type"] == "pre_restore"
    after = client.get("/api/instances").get_json()
    assert after["total"] == 1
    assert after["items"][0]["prompt"] == "恢复实例"
    assert after["items"][0]["node_id"] is None
    assert after["items"][0]["input_image_paths"] == ["C:\\in\\ok.png"]
    assert after["items"][0]["tags"] == ["恢复"]
    assert client.get("/api/generation-history").get_json()["total"] == 1


def test_v037_backup_metadata_and_list_include_summary_and_integrity(tmp_path):
    db_file = tmp_path / "data.sqlite"
    config_file = tmp_path / "config.json"
    backup_dir = tmp_path / "backup"
    conn = get_connection(db_file)
    init_db(conn)
    create_instance(
        conn,
        {
            "prompt": "摘要",
            "input_image_paths": ["C:\\in.png"],
            "output_image_path": "C:\\out.png",
            "tags": ["安全"],
        },
    )
    conn.close()
    config_file.write_text(
        json.dumps({"providers": {"p1": {"adapter": "openai"}, "p2": {"adapter": "other"}}}, ensure_ascii=False),
        encoding="utf-8",
    )

    backup = create_backup(db_file, config_file, backup_dir, "V0.39", "manual")
    items = list_backups(backup_dir)

    with zipfile.ZipFile(backup["path"]) as archive:
        metadata = json.loads(archive.read("backup_metadata.json").decode("utf-8"))
    assert metadata["integrity_check"] == "ok"
    assert metadata["summary"]["instance_count"] == 1
    assert metadata["summary"]["input_image_count"] == 1
    assert metadata["summary"]["output_image_count"] == 1
    assert metadata["summary"]["tag_count"] == 1
    assert metadata["summary"]["provider_count"] == 2
    assert items[0]["summary"]["instance_count"] == 1
    assert items[0]["integrity_check"] == "ok"


def test_v037_restore_json_skips_bad_input_images_and_tags(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    restore_json = tmp_path / "restore.json"
    restore_json.write_text(
        json.dumps(
            {
                "app_name": "AIImageManager",
                "app_version": "V0.39",
                "schema_version": 3,
                "settings": {},
                "database": {
                    "nodes": [{"id": 1, "parent_id": 999, "name": "节点", "position": 1, "created_at": "", "updated_at": ""}],
                    "instances": [
                        {
                            "id": 1,
                            "prompt": "旧JSON坏引用",
                            "mode": "text_to_image",
                            "source": "generated",
                            "provider": "p",
                            "node_id": 999,
                            "generation_path": "",
                            "generation_size": "",
                            "generation_params_json": "{}",
                            "output_image_path": "",
                            "generation_status": "ready",
                            "generation_task_id": "",
                            "generation_output_index": 1,
                            "generation_error": "",
                            "generation_started_at": "",
                            "generation_finished_at": "",
                            "created_at": "2026-05-08T00:00:00",
                            "updated_at": "2026-05-08T00:00:00",
                        }
                    ],
                    "input_images": [{"id": 1, "instance_id": 999, "path": "C:\\bad.png", "position": 0}],
                    "tags": [{"id": 1, "name": "保留"}],
                    "instance_tags": [
                        {"instance_id": 1, "tag_id": 1},
                        {"instance_id": 999, "tag_id": 1},
                        {"instance_id": 1, "tag_id": 999},
                    ],
                    "generation_history": [],
                    "app_metadata": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resp = client.post("/api/restore", json={"path": str(restore_json), "confirmed": True})

    assert resp.status_code == 200
    result = resp.get_json()
    assert result["reference_fixes"]["input_images_skipped_missing_instance"] == 1
    assert result["reference_fixes"]["instance_tags_skipped_missing_instance"] == 1
    assert result["reference_fixes"]["instance_tags_skipped_missing_tag"] == 1
    assert result["reference_fixes"]["nodes_parent_missing_set_null"] == 1
    item = client.get("/api/instances").get_json()["items"][0]
    assert item["input_image_paths"] == []
    assert item["tags"] == ["保留"]


def test_v066_session_restore_inserts_nodes_parent_before_child_for_duplicate_names(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    snapshot = {
        "app_name": "AIImageManager",
        "app_version": "V0.67",
        "schema_version": 3,
        "settings": {},
        "database": {
            "nodes": [
                {
                    "id": 2,
                    "parent_id": 1,
                    "name": "同名",
                    "position": 1,
                    "created_at": "2026-05-24T10:00:00",
                    "updated_at": "2026-05-24T10:00:00",
                },
                {
                    "id": 1,
                    "parent_id": None,
                    "name": "项目",
                    "position": 1,
                    "created_at": "2026-05-24T10:00:00",
                    "updated_at": "2026-05-24T10:00:00",
                },
                {
                    "id": 3,
                    "parent_id": None,
                    "name": "同名",
                    "position": 2,
                    "created_at": "2026-05-24T10:00:00",
                    "updated_at": "2026-05-24T10:00:00",
                },
            ],
            "instances": [
                {
                    "id": 10,
                    "prompt": "恢复到子节点",
                    "mode": "text_to_image",
                    "source": "manual",
                    "provider": "",
                    "node_id": 2,
                    "generation_path": "",
                    "generation_size": "",
                    "generation_params_json": "{}",
                    "output_image_path": "",
                    "generation_status": "ready",
                    "generation_task_id": "",
                    "generation_output_index": 1,
                    "generation_error": "",
                    "generation_started_at": "",
                    "generation_finished_at": "",
                    "created_at": "2026-05-24T10:00:00",
                    "updated_at": "2026-05-24T10:00:00",
                }
            ],
            "input_images": [],
            "tags": [],
            "instance_tags": [],
            "generation_history": [],
            "app_metadata": [],
        },
    }

    resp = client.post("/api/session-restore", json={"snapshot": snapshot})

    assert resp.status_code == 200
    tree = client.get("/api/nodes").get_json()["items"]
    assert [node["name"] for node in tree] == ["项目", "同名"]
    assert tree[0]["children"][0]["name"] == "同名"
    item = client.get("/api/instances").get_json()["items"][0]
    assert item["prompt"] == "恢复到子节点"
    assert item["node_id"] == 2


def test_v066_session_restore_rolls_back_when_node_snapshot_has_true_sibling_duplicate(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    client.post("/api/instances", json={"prompt": "恢复失败后保留"})
    snapshot = {
        "app_name": "AIImageManager",
        "app_version": "V0.67",
        "schema_version": 3,
        "settings": {},
        "database": {
            "nodes": [
                {"id": 1, "parent_id": None, "name": "项目", "position": 1, "created_at": "", "updated_at": ""},
                {"id": 2, "parent_id": 1, "name": "重复", "position": 1, "created_at": "", "updated_at": ""},
                {"id": 3, "parent_id": 1, "name": "重复", "position": 2, "created_at": "", "updated_at": ""},
            ],
            "instances": [],
            "input_images": [],
            "tags": [],
            "instance_tags": [],
            "generation_history": [],
            "app_metadata": [],
        },
    }

    resp = client.post("/api/session-restore", json={"snapshot": snapshot})

    assert resp.status_code == 400
    assert "节点恢复失败" in resp.get_json()["error"]
    after = client.get("/api/instances").get_json()
    assert after["total"] == 1
    assert after["items"][0]["prompt"] == "恢复失败后保留"


def test_restore_rejects_invalid_zip_without_replacing_current_data(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    client.post("/api/instances", json={"prompt": "不能丢"})
    invalid_zip = tmp_path / "bad.zip"
    with zipfile.ZipFile(invalid_zip, "w") as archive:
        archive.writestr("not_metadata.txt", "bad")

    resp = client.post("/api/restore", json={"path": str(invalid_zip), "confirmed": True})

    assert resp.status_code == 400
    after = client.get("/api/instances").get_json()
    assert after["total"] == 1
    assert after["items"][0]["prompt"] == "不能丢"














