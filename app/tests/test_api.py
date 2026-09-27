import sys
import json
import sqlite3
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from backend import api as api_module
from backend.image_providers.base import ImageGenerationResult


def make_client(tmp_path: Path):
    app = create_app(db_file=tmp_path / "test.sqlite", config_file=tmp_path / "config.json")
    app.config.update(TESTING=True)
    return app.test_client()


def tag_management_items(client):
    resp = client.get("/api/tag-management")
    assert resp.status_code == 200
    return resp.get_json()["items"]


def tag_id_from_management(client, name: str) -> int:
    for item in tag_management_items(client):
        if item["name"] == name:
            return item["id"]
    raise AssertionError(f"tag not found: {name}")


def insert_raw_tag(client, name: str) -> None:
    db_file = Path(client.application.config["DB_FILE"])
    with sqlite3.connect(db_file) as conn:
        conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))


def instance_by_id(client, instance_id: int) -> dict:
    items = client.get("/api/instances?sort=created_asc&per_page=50").get_json()["items"]
    for item in items:
        if item["id"] == instance_id:
            return item
    raise AssertionError(f"instance not found: {instance_id}")


def fake_shared_script_result(output_paths, *, assert_context=None):
    output_paths = [Path(path) for path in output_paths]

    def fake_run_custom_script(script, context, timeout_seconds=None):
        assert "OpenAI" in script
        assert "required_value" in script
        if assert_context:
            assert_context(context)
        for path in output_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"image")
        return ImageGenerationResult(
            output_paths=[str(path) for path in output_paths],
            provider="shared_script",
        )

    return fake_run_custom_script


def run_mock_openai_server():
    requests: list[dict] = []
    png_base64 = base64.b64encode(b"mock-image").decode("ascii")

    class Handler(BaseHTTPRequestHandler):
        def _read_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(length) if length else b""

        def _json(self, status, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            body = self._read_body()
            requests.append({
                "path": self.path,
                "user_agent": self.headers.get("User-Agent", ""),
                "content_type": self.headers.get("Content-Type", ""),
                "body": body.decode("utf-8", "replace"),
            })
            if str(self.headers.get("Content-Type", "")).startswith("application/json"):
                payload = json.loads(body.decode("utf-8")) if body else {}
                count = int(payload.get("n") or 1)
            else:
                count = 1
            self._json(200, {"data": [{"b64_json": png_base64} for _ in range(count)]})

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, requests


def run_retrying_mock_openai_server(*, failures: int = 2):
    requests: list[dict] = []
    png_base64 = base64.b64encode(b"mock-image").decode("ascii")

    class Handler(BaseHTTPRequestHandler):
        def _read_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(length) if length else b""

        def _json(self, status, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            body = self._read_body()
            requests.append({
                "path": self.path,
                "user_agent": self.headers.get("User-Agent", ""),
                "content_type": self.headers.get("Content-Type", ""),
                "body": body.decode("utf-8", "replace"),
            })
            if len(requests) <= failures:
                self._json(
                    502,
                    {
                        "title": "Error 502: Bad gateway",
                        "status": 502,
                        "detail": "origin_bad_gateway",
                        "retryable": True,
                        "retry_after": 0,
                    },
                )
                return
            self._json(200, {"data": [{"b64_json": png_base64}]})

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, requests


def insert_history(
    client,
    *,
    status: str = "success",
    prompt: str = "",
    mode: str = "text_to_image",
    provider_key: str = "",
    call_method: str = "",
    resolved_size: str = "1024x1024",
    started_at: str = "2026-05-01T10:00:00",
    output_paths: list[str] | None = None,
    params: dict | None = None,
    error_message: str = "",
    tags: list[str] | None = None,
) -> int:
    db_file = Path(client.application.config["DB_FILE"])
    output_paths = output_paths or []
    params = params or {"provider_key": provider_key, "openai_call_method": call_method}
    tags = tags or []
    with sqlite3.connect(db_file) as conn:
        cur = conn.execute(
            """
            INSERT INTO generation_history(
              status, prompt, mode, provider_key, adapter, openai_call_method,
              generation_path, resolved_size, params_json, input_image_paths_json,
              output_image_paths_json, tags_json, error_message, custom_script_used,
              started_at, finished_at, duration_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                status,
                prompt,
                mode,
                provider_key,
                "openai",
                call_method,
                "",
                resolved_size,
                json.dumps(params, ensure_ascii=False),
                "[]",
                json.dumps(output_paths, ensure_ascii=False),
                json.dumps(tags, ensure_ascii=False),
                error_message,
                0,
                started_at,
                started_at,
                100,
            ),
        )
        return int(cur.lastrowid)


def test_create_list_update_delete_instance(tmp_path):
    client = make_client(tmp_path)

    create_resp = client.post(
        "/api/instances",
        json={
            "prompt": "产品海报",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["产品"],
        },
    )
    assert create_resp.status_code == 201
    instance_id = create_resp.get_json()["item"]["id"]

    list_resp = client.get(
        "/api/instances?q=产品&tags=产品&sort=created_desc&per_page=50&page=1"
    )
    assert list_resp.status_code == 200
    assert list_resp.get_json()["total"] == 1

    update_resp = client.put(
        f"/api/instances/{instance_id}",
        json={
            "prompt": "更新后的产品海报",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "C:\\out\\one.png",
            "input_image_paths": ["C:\\in\\one.png"],
            "tags": ["产品", "海报"],
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.get_json()["item"]["tags"] == ["产品", "海报"]

    delete_resp = client.delete(f"/api/instances/{instance_id}")
    assert delete_resp.status_code == 204

    after_delete_resp = client.get("/api/instances?q=产品")
    assert after_delete_resp.get_json()["total"] == 0
    assert client.get("/api/generation-history").get_json()["total"] == 0


def test_single_instance_tag_add_remove_endpoints_do_not_require_full_update(tmp_path):
    client = make_client(tmp_path)
    create_resp = client.post(
        "/api/instances",
        json={
            "prompt": "标签即时操作",
            "mode": "text_to_image",
            "source": "manual",
            "provider": "外部",
            "generation_path": "",
            "output_image_path": "C:\\out\\one.png",
            "input_image_paths": ["C:\\in\\one.png"],
            "tags": ["旧"],
        },
    )
    instance_id = create_resp.get_json()["item"]["id"]

    add_resp = client.post(
        f"/api/instances/{instance_id}/tags/add",
        json={"tags": ["新", "__untagged__", "新"]},
    )
    remove_resp = client.post(
        f"/api/instances/{instance_id}/tags/remove",
        json={"tags": ["旧", "__untagged__"]},
    )

    assert add_resp.status_code == 200
    assert add_resp.get_json()["item"]["tags"] == ["旧", "新"]
    assert remove_resp.status_code == 200
    item = remove_resp.get_json()["item"]
    assert item["prompt"] == "标签即时操作"
    assert item["output_image_path"] == "C:\\out\\one.png"
    assert item["input_image_paths"] == ["C:\\in\\one.png"]
    assert item["tags"] == ["新"]


def test_v038_tag_management_lists_only_used_real_tags(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/instances", json={"prompt": "一", "tags": ["风景", "通用"]})
    client.post("/api/instances", json={"prompt": "二", "tags": ["风景"]})
    client.post(
        "/api/instances",
        json={
            "prompt": "生成中",
            "generation_status": "running",
            "generation_task_id": "task-tag",
            "tags": ["生成中标签"],
        },
    )
    insert_raw_tag(client, "未使用")
    insert_raw_tag(client, "__untagged__")

    payload = client.get("/api/tag-management?q=风").get_json()
    assert payload["total"] == 1
    assert payload["items"] == [
        {"id": tag_id_from_management(client, "风景"), "name": "风景", "usage_count": 2}
    ]

    names = [item["name"] for item in tag_management_items(client)]
    assert names == ["风景", "通用"]
    assert "无" not in names
    assert "__untagged__" not in names
    assert "未使用" not in names
    assert "生成中标签" not in names


def test_v038_tag_management_renames_used_tag_and_rejects_implicit_merge(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/instances", json={"prompt": "一", "tags": ["旧名"]})
    client.post("/api/instances", json={"prompt": "二", "tags": ["已有"]})
    old_id = tag_id_from_management(client, "旧名")

    duplicate_resp = client.patch(
        f"/api/tag-management/{old_id}/rename",
        json={"name": "已有"},
    )
    invalid_resp = client.patch(
        f"/api/tag-management/{old_id}/rename",
        json={"name": "__untagged__"},
    )
    rename_resp = client.patch(
        f"/api/tag-management/{old_id}/rename",
        json={"name": "新名"},
    )

    assert duplicate_resp.status_code == 400
    assert invalid_resp.status_code == 400
    assert rename_resp.status_code == 200
    assert rename_resp.get_json()["item"]["name"] == "新名"
    assert "新名" in rename_resp.get_json()["tags"]
    assert client.get("/api/instances?tags=新名").get_json()["total"] == 1
    assert client.get("/api/instances?tags=旧名").get_json()["total"] == 0


def test_v038_tag_management_merges_tags_without_touching_image_paths(tmp_path):
    client = make_client(tmp_path)
    first = client.post(
        "/api/instances",
        json={
            "prompt": "一",
            "output_image_path": "C:\\out\\one.png",
            "input_image_paths": ["C:\\in\\one.png"],
            "tags": ["源", "目标"],
        },
    ).get_json()["item"]["id"]
    second = client.post(
        "/api/instances",
        json={
            "prompt": "二",
            "output_image_path": "C:\\out\\two.png",
            "tags": ["源"],
        },
    ).get_json()["item"]["id"]
    client.post("/api/instances", json={"prompt": "三", "tags": ["另一个源"]})
    source_id = tag_id_from_management(client, "源")
    other_source_id = tag_id_from_management(client, "另一个源")
    target_id = tag_id_from_management(client, "目标")

    bad_resp = client.post(
        "/api/tag-management/merge",
        json={"source_tag_ids": [source_id, target_id], "target_tag_id": target_id},
    )
    merge_resp = client.post(
        "/api/tag-management/merge",
        json={"source_tag_ids": [source_id, other_source_id], "target_tag_id": target_id},
    )

    assert bad_resp.status_code == 400
    assert merge_resp.status_code == 200
    payload = merge_resp.get_json()
    assert payload["target"]["name"] == "目标"
    assert sorted(payload["removed_source_ids"]) == sorted([source_id, other_source_id])
    names = [item["name"] for item in tag_management_items(client)]
    assert names == ["目标"]
    first_item = instance_by_id(client, first)
    second_item = instance_by_id(client, second)
    assert first_item["tags"] == ["目标"]
    assert first_item["output_image_path"] == "C:\\out\\one.png"
    assert first_item["input_image_paths"] == ["C:\\in\\one.png"]
    assert second_item["tags"] == ["目标"]


def test_v039_generation_history_filters_run_on_backend(tmp_path):
    client = make_client(tmp_path)
    insert_history(
        client,
        status="success",
        prompt="sunset poster",
        provider_key="Provider A",
        call_method="gpt-image-2",
        started_at="2026-05-01T23:59:59",
    )
    insert_history(
        client,
        status="failed",
        prompt="cat error",
        provider_key="",
        call_method="",
        started_at="2026-05-02T10:00:00",
    )
    insert_history(
        client,
        status="queued",
        prompt="other task",
        provider_key="Provider B",
        call_method="response",
        started_at="2026-05-03T09:00:00",
    )

    combined = client.get(
        "/api/generation-history?"
        "q=sunset&status=success&provider=Provider+A&call_method=gpt-image-2"
        "&start_date=2026-05-01&end_date=2026-05-01"
    )
    empty_provider = client.get("/api/generation-history?provider=__empty__")
    empty_call_method = client.get("/api/generation-history?call_method=__empty__")
    other_status = client.get("/api/generation-history?status=other")
    invalid_dates = client.get("/api/generation-history?start_date=2026-05-04&end_date=2026-05-01")

    assert combined.status_code == 200
    assert [item["prompt"] for item in combined.get_json()["items"]] == ["sunset poster"]
    assert empty_provider.get_json()["items"][0]["prompt"] == "cat error"
    assert empty_call_method.get_json()["items"][0]["prompt"] == "cat error"
    assert other_status.get_json()["items"][0]["status"] == "queued"
    assert invalid_dates.status_code == 400


def test_v039_generation_history_filter_options_use_history_values(tmp_path):
    client = make_client(tmp_path)
    insert_history(client, provider_key="Provider B", call_method="response")
    insert_history(client, provider_key="Provider A", call_method="gpt-image-2")
    insert_history(client, provider_key="", call_method="")

    resp = client.get("/api/generation-history/filter-options")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["providers"] == ["__empty__", "Provider A", "Provider B"]
    assert payload["call_methods"] == ["__empty__", "gpt-image-2", "response"]
    assert {"running", "success", "failed", "other"}.issubset(set(payload["statuses"]))


def test_v039_generation_history_cleanup_does_not_delete_instances_or_files(tmp_path):
    client = make_client(tmp_path)
    output_file = tmp_path / "failed-output.png"
    output_file.write_bytes(b"image")
    client.post(
        "/api/instances",
        json={
            "prompt": "失败实例保留",
            "output_image_path": str(output_file),
            "tags": ["保留"],
        },
    )
    insert_history(
        client,
        status="failed",
        prompt="失败历史",
        output_paths=[str(output_file)],
        started_at="2026-05-02T10:00:00",
    )
    insert_history(client, status="success", prompt="成功历史", started_at="2026-05-02T11:00:00")

    preview = client.post("/api/generation-history/cleanup/preview", json={"type": "failed"})
    cleanup = client.post("/api/generation-history/cleanup/failed", json={})

    assert preview.status_code == 200
    assert preview.get_json()["matched_count"] == 1
    assert preview.get_json()["will_delete_instances"] is False
    assert preview.get_json()["will_delete_image_files"] is False
    assert cleanup.status_code == 200
    assert cleanup.get_json()["deleted"] == 1
    assert client.get("/api/generation-history").get_json()["total"] == 1
    assert client.get("/api/instances").get_json()["total"] == 1
    assert output_file.exists()


def test_v039_generation_history_cleanup_before_date_keeps_running_records(tmp_path):
    client = make_client(tmp_path)
    insert_history(client, status="success", prompt="旧成功", started_at="2026-04-01T08:00:00")
    insert_history(client, status="running", prompt="旧生成中", started_at="2026-04-01T09:00:00")
    insert_history(client, status="success", prompt="新成功", started_at="2026-05-02T08:00:00")

    preview = client.post(
        "/api/generation-history/cleanup/preview",
        json={"type": "before_date", "before_date": "2026-05-01"},
    )
    cleanup = client.post(
        "/api/generation-history/cleanup/before-date",
        json={"before_date": "2026-05-01"},
    )
    remaining = client.get("/api/generation-history?per_page=10").get_json()["items"]

    assert preview.status_code == 200
    assert preview.get_json()["matched_count"] == 1
    assert cleanup.status_code == 200
    assert cleanup.get_json()["deleted"] == 1
    assert [item["prompt"] for item in remaining] == ["新成功", "旧生成中"]


def test_v0502_generation_history_groups_retry_attempts_by_parent_history(tmp_path):
    client = make_client(tmp_path)
    parent_id = insert_history(
        client,
        status="success",
        prompt="合并尝试",
        provider_key="Provider A",
        call_method="gpt-image-2",
        started_at="2026-05-02T10:00:00",
    )
    insert_history(
        client,
        status="failed",
        prompt="合并尝试",
        provider_key="Provider A",
        call_method="gpt-image-2",
        started_at="2026-05-02T09:58:00",
        params={"parent_history_id": parent_id, "retry_attempt": 1},
        error_message="第一次失败\n原因 A",
    )
    insert_history(
        client,
        status="failed",
        prompt="合并尝试",
        provider_key="Provider A",
        call_method="gpt-image-2",
        started_at="2026-05-02T09:59:00",
        params={"parent_history_id": parent_id, "retry_attempt": 2},
        error_message="第二次失败\n原因 B",
    )
    insert_history(
        client,
        status="failed",
        prompt="无关联失败",
        provider_key="Provider A",
        call_method="gpt-image-2",
        started_at="2026-05-02T08:00:00",
        params={"retry_attempt": 1},
        error_message="不能误合并",
    )

    payload = client.get("/api/generation-history?per_page=10").get_json()

    assert payload["total"] == 2
    grouped = payload["items"][0]
    assert grouped["id"] == parent_id
    assert grouped["retry_count"] == 2
    assert [item["params"]["retry_attempt"] for item in grouped["retry_records"]] == [1, 2]
    assert [item["error_message"] for item in grouped["retry_records"]] == [
        "第一次失败\n原因 A",
        "第二次失败\n原因 B",
    ]
    assert payload["items"][1]["prompt"] == "无关联失败"
    assert payload["items"][1].get("retry_records", []) == []


def test_v051_instances_filter_and_sort_by_provider_on_backend(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/instances",
        json={"prompt": "Beta prompt", "provider": "beta_provider", "tags": []},
    )
    client.post(
        "/api/instances",
        json={"prompt": "Alpha prompt", "provider": "alpha_provider", "tags": []},
    )
    client.post(
        "/api/instances",
        json={"prompt": "No provider prompt", "provider": "", "tags": []},
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "Running beta",
            "provider": "beta_provider",
            "generation_status": "running",
            "generation_task_id": "task-v051-provider",
            "tags": [],
        },
    )

    filtered = client.get("/api/instances?provider=beta_provider&sort=created_asc&per_page=50")
    empty_provider = client.get("/api/instances?provider=__empty__&sort=created_asc&per_page=50")
    asc = client.get("/api/instances?sort=provider_asc&per_page=50")
    desc = client.get("/api/instances?sort=provider_desc&per_page=50")

    assert filtered.status_code == 200
    assert filtered.get_json()["total"] == 2
    assert [item["prompt"] for item in filtered.get_json()["items"]] == [
        "Beta prompt",
        "Running beta",
    ]
    assert empty_provider.get_json()["total"] == 1
    assert empty_provider.get_json()["items"][0]["prompt"] == "No provider prompt"
    assert [item["provider"] for item in asc.get_json()["items"][:3]] == [
        "",
        "alpha_provider",
        "beta_provider",
    ]
    assert [item["provider"] for item in desc.get_json()["items"][:3]] == [
        "beta_provider",
        "beta_provider",
        "alpha_provider",
    ]
    assert [item["provider"] for item in desc.get_json()["items"][-3:]] == [
        "beta_provider",
        "alpha_provider",
        "",
    ]
    assert [item["display_index"] for item in asc.get_json()["items"][:3]] == [1, 2, 3]


def test_v051_generation_history_filters_model_size_mode_and_maps_save_index(tmp_path):
    client = make_client(tmp_path)
    older = client.post(
        "/api/instances",
        json={
            "prompt": "older save item",
            "provider": "alpha_provider",
            "generation_size": "1024x1024",
            "tags": [],
        },
    ).get_json()["item"]
    newer = client.post(
        "/api/instances",
        json={
            "prompt": "newer save item",
            "provider": "beta_provider",
            "generation_size": "2048x2048",
            "tags": [],
        },
    ).get_json()["item"]
    insert_history(
        client,
        status="success",
        prompt="history older",
        provider_key="alpha_provider",
        call_method="gpt-image-2",
        resolved_size="1024x1024",
        started_at="2026-05-01T10:00:00",
        params={
            "provider_key": "alpha_provider",
            "openai_call_method": "gpt-image-2",
            "model": "gpt-image-2",
            "resolved_size": "1024x1024",
            "primary_instance_id": older["id"],
        },
    )
    insert_history(
        client,
        status="success",
        prompt="history newer",
        provider_key="beta_provider",
        call_method="response",
        resolved_size="2048x2048",
        started_at="2026-05-02T10:00:00",
        params={
            "provider_key": "beta_provider",
            "openai_call_method": "response",
            "model": "gpt-image-2-pro",
            "resolved_size": "2048x2048",
            "primary_instance_id": newer["id"],
        },
    )
    insert_history(
        client,
        status="failed",
        prompt="history image edit",
        provider_key="beta_provider",
        call_method="gpt-image-2",
        mode="image_to_image",
        resolved_size="2048x2048",
        started_at="2026-05-03T10:00:00",
        params={
            "provider_key": "beta_provider",
            "openai_call_method": "gpt-image-2",
            "model": "gpt-image-2",
            "resolved_size": "2048x2048",
        },
    )
    filtered = client.get(
        "/api/generation-history?"
        "model=gpt-image-2-pro&size=2048x2048&mode=text_to_image&save_sort=created_desc"
    )
    image_mode = client.get("/api/generation-history?mode=image_to_image&save_sort=created_desc")
    created_asc_index = client.get("/api/generation-history?save_sort=created_asc&per_page=10")

    assert filtered.status_code == 200
    payload = filtered.get_json()
    assert [item["prompt"] for item in payload["items"]] == ["history newer"]
    assert payload["items"][0]["instance_number"] == 2
    assert image_mode.get_json()["items"][0]["prompt"] == "history image edit"
    assert "save_display_index" not in image_mode.get_json()["items"][0]
    asc_items = created_asc_index.get_json()["items"]
    newer_history = next(item for item in asc_items if item["prompt"] == "history newer")
    older_history = next(item for item in asc_items if item["prompt"] == "history older")
    assert older_history["instance_number"] == 1
    assert newer_history["instance_number"] == 2


def test_v067_instances_expose_fixed_number_and_statuses_query(tmp_path):
    client = make_client(tmp_path)
    first = client.post("/api/instances", json={"prompt": "prepared"}).get_json()["item"]
    second = client.post(
        "/api/instances",
        json={"prompt": "generated", "output_image_path": "C:\\out.png"},
    ).get_json()["item"]
    failed = client.post(
        "/api/instances",
        json={"prompt": "failed", "generation_status": "failed"},
    ).get_json()["item"]
    running = client.post(
        "/api/instances",
        json={"prompt": "running", "generation_status": "running", "generation_task_id": "task"},
    ).get_json()["item"]

    filtered = client.get("/api/instances?statuses=running&statuses=failed&sort=number_asc&per_page=50")
    number_desc = client.get("/api/instances?sort=number_desc&per_page=50")

    assert first["instance_number"] == 1
    assert first["instance_number_label"] == "#0001"
    assert second["instance_number"] == 2
    assert failed["instance_number"] == 3
    assert running["instance_number"] == 4
    assert [item["prompt"] for item in filtered.get_json()["items"]] == ["failed", "running"]
    assert [item["instance_number"] for item in number_desc.get_json()["items"]] == [4, 3, 2, 1]


def test_v067_generation_history_uses_instance_fixed_number_not_save_sort_index(tmp_path):
    client = make_client(tmp_path)
    older = client.post("/api/instances", json={"prompt": "older"}).get_json()["item"]
    newer = client.post("/api/instances", json={"prompt": "newer"}).get_json()["item"]
    insert_history(
        client,
        prompt="linked newer",
        started_at="2026-05-03T10:00:00",
        params={"primary_instance_id": newer["id"]},
    )
    insert_history(
        client,
        prompt="unlinked old history",
        started_at="2026-05-02T10:00:00",
        params={},
    )

    payload = client.get("/api/generation-history?save_sort=created_asc&per_page=10").get_json()
    linked = next(item for item in payload["items"] if item["prompt"] == "linked newer")
    unlinked = next(item for item in payload["items"] if item["prompt"] == "unlinked old history")

    assert older["instance_number"] == 1
    assert newer["instance_number"] == 2
    assert linked["instance_number"] == 2
    assert linked["instance_number_label"] == "#0002"
    assert "save_display_index" not in linked
    assert "instance_number" not in unlinked
    assert unlinked["display_index"] >= 1


def test_v068_generation_history_number_type_filter_uses_instance_link(tmp_path):
    client = make_client(tmp_path)
    linked = client.post("/api/instances", json={"prompt": "linked save"}).get_json()["item"]
    insert_history(
        client,
        prompt="linked history",
        started_at="2026-05-03T10:00:00",
        params={"primary_instance_id": linked["id"]},
    )
    insert_history(
        client,
        prompt="local history",
        started_at="2026-05-02T10:00:00",
        params={},
    )

    instance_number = client.get("/api/generation-history?number_type=%23&per_page=10")
    local_number = client.get("/api/generation-history?number_type=H&per_page=10")

    assert instance_number.status_code == 200
    assert local_number.status_code == 200
    assert instance_number.get_json()["total"] == 1
    assert instance_number.get_json()["items"][0]["prompt"] == "linked history"
    assert instance_number.get_json()["items"][0]["instance_number_label"] == "#0001"
    assert local_number.get_json()["total"] == 1
    assert local_number.get_json()["items"][0]["prompt"] == "local history"
    assert "instance_number" not in local_number.get_json()["items"][0]


def test_v069_generation_history_h_numbers_are_global_and_stable(tmp_path):
    client = make_client(tmp_path)
    linked = client.post("/api/instances", json={"prompt": "linked save"}).get_json()["item"]
    older_id = insert_history(
        client,
        prompt="older local history",
        started_at="2026-05-01T09:00:00",
        params={},
    )
    middle_id = insert_history(
        client,
        prompt="middle local history",
        started_at="2026-05-02T09:00:00",
        params={},
    )
    insert_history(
        client,
        prompt="linked history",
        started_at="2026-05-03T09:00:00",
        params={"primary_instance_id": linked["id"]},
    )
    newer_id = insert_history(
        client,
        prompt="newer local history",
        started_at="2026-05-04T09:00:00",
        params={},
    )

    all_records = client.get("/api/generation-history?per_page=10").get_json()
    h_only = client.get("/api/generation-history?number_type=H&per_page=10").get_json()
    filtered_middle = client.get("/api/generation-history?number_type=H&q=middle&per_page=10").get_json()

    all_by_id = {item["id"]: item for item in all_records["items"]}
    assert all_by_id[newer_id]["history_number"] == 3
    assert all_by_id[newer_id]["history_number_label"] == "H0003"
    assert all_by_id[middle_id]["history_number"] == 2
    assert all_by_id[middle_id]["history_number_label"] == "H0002"
    assert [(item["id"], item["history_number_label"]) for item in h_only["items"]] == [
        (newer_id, "H0003"),
        (middle_id, "H0002"),
        (older_id, "H0001"),
    ]
    assert filtered_middle["total"] == 1
    assert filtered_middle["items"][0]["id"] == middle_id
    assert filtered_middle["items"][0]["history_number_label"] == "H0002"
    assert "history_number" not in client.get("/api/generation-history?number_type=%23&per_page=10").get_json()["items"][0]


def test_v051_generation_history_filter_options_include_model_size_and_mode(tmp_path):
    client = make_client(tmp_path)
    insert_history(
        client,
        provider_key="Provider B",
        call_method="response",
        mode="image_to_image",
        resolved_size="2048x2048",
        params={
            "provider_key": "Provider B",
            "openai_call_method": "response",
            "model": "z-model",
            "resolved_size": "2048x2048",
        },
    )
    insert_history(
        client,
        provider_key="Provider A",
        call_method="gpt-image-2",
        resolved_size="1024x1024",
        params={
            "provider_key": "Provider A",
            "openai_call_method": "gpt-image-2",
            "model": "a-model",
            "resolved_size": "1024x1024",
        },
    )
    resp = client.get("/api/generation-history/filter-options")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["models"] == ["a-model", "z-model"]
    assert payload["sizes"] == ["1024x1024", "2048x2048"]
    assert payload["modes"] == ["image_to_image", "text_to_image"]


def test_v052_instances_filter_status_size_call_method_and_model_on_backend(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/instances",
        json={
            "prompt": "ready 1k gpt",
            "provider": "alpha_provider",
            "generation_size": "1024x1024",
            "generation_params": {
                "openai_call_method": "gpt-image-2",
                "model": "model-a",
                "resolved_size": "1024x1024",
            },
            "tags": ["产品"],
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "failed 2k response",
            "provider": "beta_provider",
            "generation_status": "failed",
            "generation_size": "2048x2048",
            "generation_params": {
                "openai_call_method": "response",
                "model": "model-b",
                "resolved_size": "2048x2048",
            },
            "tags": [],
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "running response",
            "provider": "beta_provider",
            "generation_status": "running",
            "generation_task_id": "task-v052-running",
            "generation_size": "2048x2048",
            "generation_params": {
                "openai_call_method": "response",
                "model": "model-b",
                "resolved_size": "2048x2048",
            },
            "tags": [],
        },
    )

    failed = client.get("/api/instances?status=failed&per_page=50")
    running = client.get("/api/instances?status=running&per_page=50")
    size = client.get("/api/instances?size=2048x2048&sort=created_asc&per_page=50")
    call_method = client.get("/api/instances?call_method=response&sort=created_asc&per_page=50")
    model = client.get("/api/instances?model=model-b&sort=created_asc&per_page=50")
    options = client.get("/api/instances/filter-options")

    assert failed.status_code == 200
    assert [item["prompt"] for item in failed.get_json()["items"]] == ["failed 2k response"]
    assert running.status_code == 200
    assert [item["prompt"] for item in running.get_json()["items"]] == ["running response"]
    assert [item["prompt"] for item in size.get_json()["items"]] == ["failed 2k response", "running response"]
    assert [item["prompt"] for item in call_method.get_json()["items"]] == ["failed 2k response", "running response"]
    assert [item["prompt"] for item in model.get_json()["items"]] == ["failed 2k response", "running response"]
    assert options.status_code == 200
    filter_options = options.get_json()
    assert filter_options["statuses"] == ["running", "prepared", "failed", "generated", "other"]
    assert filter_options["sizes"] == ["1024x1024", "2048x2048"]
    assert filter_options["call_methods"] == ["gpt-image-2", "response"]
    assert filter_options["models"] == ["model-a", "model-b"]


def test_v064_instances_source_filter_uses_current_state_not_raw_source(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/instances",
        json={
            "prompt": "old generated without output is prepared",
            "source": "generated",
            "generation_status": "ready",
            "output_image_path": "",
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "manual with output is generated",
            "source": "manual",
            "generation_status": "ready",
            "output_image_path": "D:\\out\\manual.png",
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "failed manual is failed",
            "source": "manual",
            "generation_status": "failed",
            "output_image_path": "",
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "running generated is excluded from semantic source",
            "source": "generated",
            "generation_status": "running",
            "generation_task_id": "task-v064-running",
            "output_image_path": "",
        },
    )

    generated = client.get("/api/instances?status=generated&sort=created_asc&per_page=50")
    prepared = client.get("/api/instances?status=prepared&sort=created_asc&per_page=50")
    failed = client.get("/api/instances?status=failed&sort=created_asc&per_page=50")

    assert generated.status_code == 200
    assert [item["prompt"] for item in generated.get_json()["items"]] == [
        "manual with output is generated",
    ]
    assert [item["prompt"] for item in prepared.get_json()["items"]] == [
        "old generated without output is prepared",
    ]
    assert [item["prompt"] for item in failed.get_json()["items"]] == [
        "failed manual is failed",
    ]


def test_v065_instances_status_filter_uses_current_state_semantics_and_ignores_old_source(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/instances",
        json={
            "prompt": "old generated without output is prepared",
            "source": "generated",
            "generation_status": "ready",
            "output_image_path": "",
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "manual with output is generated",
            "source": "manual",
            "generation_status": "ready",
            "output_image_path": "D:\\out\\manual.png",
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "failed manual is failed",
            "source": "manual",
            "generation_status": "failed",
            "output_image_path": "",
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "running generated is running",
            "source": "generated",
            "generation_status": "running",
            "generation_task_id": "task-v065-running",
            "output_image_path": "",
        },
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "queued without output is other",
            "source": "generated",
            "generation_status": "queued",
            "output_image_path": "D:\\out\\queued.png",
        },
    )
    db_file = Path(client.application.config["DB_FILE"])
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            "UPDATE instances SET generation_status = 'queued' WHERE prompt = ?",
            ("queued without output is other",),
        )

    prepared = client.get("/api/instances?status=prepared&source=generated&sort=created_asc&per_page=50")
    generated = client.get("/api/instances?status=generated&source=prepared&sort=created_asc&per_page=50")
    failed = client.get("/api/instances?status=failed&sort=created_asc&per_page=50")
    running = client.get("/api/instances?status=running&sort=created_asc&per_page=50")
    other = client.get("/api/instances?status=other&sort=created_asc&per_page=50")
    options = client.get("/api/instances/filter-options")

    assert prepared.status_code == 200
    assert [item["prompt"] for item in prepared.get_json()["items"]] == [
        "old generated without output is prepared",
    ]
    assert [item["prompt"] for item in generated.get_json()["items"]] == [
        "manual with output is generated",
        "queued without output is other",
    ]
    assert [item["prompt"] for item in failed.get_json()["items"]] == [
        "failed manual is failed",
    ]
    assert [item["prompt"] for item in running.get_json()["items"]] == [
        "running generated is running",
    ]
    assert [item["prompt"] for item in other.get_json()["items"]] == []
    assert options.get_json()["statuses"] == ["running", "prepared", "failed", "generated", "other"]


def test_v052_generation_history_tag_filter_options_and_h_number_fallback(tmp_path):
    client = make_client(tmp_path)
    linked = client.post(
        "/api/instances",
        json={"prompt": "linked save", "tags": ["产品"]},
    ).get_json()["item"]
    insert_history(
        client,
        prompt="linked history",
        tags=["产品"],
        started_at="2026-05-02T10:00:00",
        params={"primary_instance_id": linked["id"]},
    )
    insert_history(
        client,
        prompt="old tagged history",
        tags=["参考"],
        started_at="2026-05-01T10:00:00",
    )
    insert_history(
        client,
        prompt="old untagged history",
        started_at="2026-04-30T10:00:00",
    )

    tagged = client.get("/api/generation-history?tags=参考&per_page=10")
    untagged = client.get("/api/generation-history?tags=__untagged__&per_page=10")
    options = client.get("/api/generation-history/filter-options")

    assert tagged.status_code == 200
    tagged_item = tagged.get_json()["items"][0]
    assert tagged_item["prompt"] == "old tagged history"
    assert tagged_item["display_index"] == 1
    assert "save_display_index" not in tagged_item
    assert untagged.get_json()["items"][0]["prompt"] == "old untagged history"
    assert options.status_code == 200
    assert options.get_json()["tags"] == ["__untagged__", "产品", "参考"]


def test_v054_generation_history_accepts_repeated_and_comma_separated_tags(tmp_path):
    client = make_client(tmp_path)
    insert_history(client, prompt="产品海报", tags=["产品", "海报"])
    insert_history(client, prompt="产品摄影", tags=["产品"])
    insert_history(client, prompt="参考摄影", tags=["参考"])
    insert_history(client, prompt="无标签")

    repeated_resp = client.get("/api/generation-history?tags=产品&tags=海报&per_page=20")
    comma_resp = client.get("/api/generation-history?tags=产品,海报&per_page=20")
    untagged_mixed = client.get("/api/generation-history?tags=__untagged__&tags=产品&per_page=20")

    assert repeated_resp.status_code == 200
    assert [item["prompt"] for item in repeated_resp.get_json()["items"]] == ["产品海报"]
    assert comma_resp.status_code == 200
    assert [item["prompt"] for item in comma_resp.get_json()["items"]] == ["产品海报"]
    assert untagged_mixed.status_code == 200
    assert [item["prompt"] for item in untagged_mixed.get_json()["items"]] == ["无标签"]


def test_v029_single_instance_tag_clear_endpoint_persists_empty_tags(tmp_path):
    client = make_client(tmp_path)
    create_resp = client.post(
        "/api/instances",
        json={
            "prompt": "标签清空",
            "mode": "text_to_image",
            "source": "manual",
            "provider": "外部",
            "generation_path": "",
            "output_image_path": "C:\\out\\one.png",
            "input_image_paths": ["C:\\in\\one.png"],
            "tags": ["旧", "保留名称"],
        },
    )
    instance_id = create_resp.get_json()["item"]["id"]

    clear_resp = client.post(f"/api/instances/{instance_id}/tags/clear", json={})

    assert clear_resp.status_code == 200
    payload = clear_resp.get_json()
    assert payload["item"]["tags"] == []
    assert payload["item"]["prompt"] == "标签清空"
    assert payload["item"]["output_image_path"] == "C:\\out\\one.png"
    assert client.get("/api/instances").get_json()["items"][0]["tags"] == []


def test_v029_nodes_api_creates_tree_and_rejects_reserved_names(tmp_path):
    client = make_client(tmp_path)

    root_resp = client.post("/api/nodes", json={"name": "人像", "parent_id": None})
    child_resp = client.post(
        "/api/nodes",
        json={"name": "写实", "parent_id": root_resp.get_json()["item"]["id"]},
    )
    reserved_resp = client.post("/api/nodes", json={"name": "全部", "parent_id": None})
    tree_resp = client.get("/api/nodes")

    assert root_resp.status_code == 201
    assert child_resp.status_code == 201
    assert reserved_resp.status_code == 400
    tree = tree_resp.get_json()["items"]
    assert tree[0]["name"] == "人像"
    assert tree[0]["children"][0]["name"] == "写实"


def test_v030_delete_node_api_promotes_instances_and_children(tmp_path):
    client = make_client(tmp_path)
    root_id = client.post("/api/nodes", json={"name": "人像", "parent_id": None}).get_json()["item"]["id"]
    child_id = client.post("/api/nodes", json={"name": "写实", "parent_id": root_id}).get_json()["item"]["id"]
    leaf_id = client.post("/api/nodes", json={"name": "女性", "parent_id": child_id}).get_json()["item"]["id"]
    direct = client.post("/api/instances", json={"prompt": "直属", "node_id": root_id}).get_json()["item"]["id"]
    child_instance = client.post("/api/instances", json={"prompt": "子级", "node_id": child_id}).get_json()["item"]["id"]
    leaf_instance = client.post("/api/instances", json={"prompt": "叶子", "node_id": leaf_id}).get_json()["item"]["id"]

    resp = client.delete(f"/api/nodes/{child_id}")

    assert resp.status_code == 200
    items = client.get(f"/api/instances?node_filter_type=all&node_id={root_id}&sort=prompt_asc").get_json()["items"]
    assert [item["prompt"] for item in items] == ["叶子", "子级", "直属"]
    tree = client.get("/api/nodes").get_json()["items"]
    assert tree[0]["children"][0]["name"] == "女性"


def test_v056_reorder_nodes_api_reorders_only_same_parent(tmp_path):
    client = make_client(tmp_path)
    first_id = client.post("/api/nodes", json={"name": "第一"}).get_json()["item"]["id"]
    second_id = client.post("/api/nodes", json={"name": "第二"}).get_json()["item"]["id"]
    third_id = client.post("/api/nodes", json={"name": "第三"}).get_json()["item"]["id"]
    child_id = client.post("/api/nodes", json={"name": "子级", "parent_id": first_id}).get_json()["item"]["id"]

    resp = client.post("/api/nodes/reorder", json={"parent_id": None, "node_ids": [third_id, first_id, second_id]})
    invalid_resp = client.post("/api/nodes/reorder", json={"parent_id": None, "node_ids": [first_id, child_id]})

    assert resp.status_code == 200
    assert [node["id"] for node in resp.get_json()["items"]] == [third_id, first_id, second_id]
    assert invalid_resp.status_code == 400
    assert "同一层级" in invalid_resp.get_json()["error"]
    assert [node["id"] for node in client.get("/api/nodes").get_json()["items"]] == [third_id, first_id, second_id]


def test_v029_instance_move_and_batch_move_api(tmp_path):
    client = make_client(tmp_path)
    node_id = client.post("/api/nodes", json={"name": "项目"}).get_json()["item"]["id"]
    first_id = client.post("/api/instances", json={"prompt": "第一条"}).get_json()["item"]["id"]
    second_id = client.post("/api/instances", json={"prompt": "第二条"}).get_json()["item"]["id"]
    running_id = client.post(
        "/api/instances",
        json={
            "prompt": "生成中",
            "generation_status": "running",
            "generation_task_id": "task-1",
        },
    ).get_json()["item"]["id"]

    move_resp = client.post(f"/api/instances/{first_id}/move", json={"node_id": node_id})
    running_resp = client.post(f"/api/instances/{running_id}/move", json={"node_id": node_id})
    batch_resp = client.post(
        "/api/instances/batch/move",
        json={"ids": [second_id, running_id], "node_id": node_id},
    )
    filtered = client.get(f"/api/instances?node_filter_type=all&node_id={node_id}&sort=created_asc")

    assert move_resp.status_code == 200
    assert move_resp.get_json()["item"]["node_id"] == node_id
    assert running_resp.status_code == 400
    assert "生成中实例不能移动节点" in running_resp.get_json()["error"]
    assert batch_resp.status_code == 200
    assert batch_resp.get_json()["updated"] == 1
    assert [item["id"] for item in filtered.get_json()["items"]] == [first_id, second_id]


def test_v063_instances_endpoint_keeps_running_database_instances_in_formal_pagination(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/instances",
        json={"prompt": "正式实例", "generation_status": "ready"},
    )
    client.post(
        "/api/instances",
        json={
            "prompt": "生成中实例",
            "generation_status": "running",
            "generation_task_id": "task-1",
        },
    )

    payload = client.get("/api/instances?sort=created_desc&page=1&per_page=50").get_json()

    assert payload["total"] == 2
    formal_items = [item for item in payload["items"] if item["generation_status"] != "running"]
    running_items = [item for item in payload["items"] if item["generation_status"] == "running"]
    assert [item["display_index"] for item in running_items] == [1]
    assert [item["display_index"] for item in formal_items] == [2]


def test_settings_round_trip(tmp_path):
    client = make_client(tmp_path)

    get_resp = client.get("/api/settings")
    assert get_resp.status_code == 200
    config = get_resp.get_json()["settings"]
    config["default_output_dir"] = "D:\\AIOutput"

    save_resp = client.put("/api/settings", json=config)
    assert save_resp.status_code == 200

    after_resp = client.get("/api/settings")
    assert after_resp.get_json()["settings"]["default_output_dir"] == "D:\\AIOutput"


def test_settings_put_normalizes_partial_config(tmp_path):
    client = make_client(tmp_path)

    resp = client.put("/api/settings", json={"default_output_dir": "D:\\AIOutput"})

    assert resp.status_code == 200
    settings = resp.get_json()["settings"]
    assert settings["default_output_dir"] == "D:\\AIOutput"
    assert settings["active_provider"] == "aiapis_gpt_image_2"
    assert settings["default_size"] == "1024x1024"
    assert settings["default_resolution"] == "1K"
    assert settings["default_aspect_ratio"] == "1:1"
    assert settings["default_clarity"] == "1K"
    assert settings["custom_generation_sizes"] == []
    assert "aiapis_gpt_image_2" in settings["providers"]
    assert settings["providers"]["aiapis_gpt_image_2"]["adapter"] == "openai"
    assert settings["providers"]["aiapis_gpt_image_2"]["openai_call_method"] == "gpt-image-2"
    assert settings["providers"]["aiapis_gpt_image_2"]["quality"] == "high"
    assert settings["providers"]["aiapis_gpt_image_2"]["output_format"] == "png"


def test_v060_settings_put_preserves_blank_new_provider_connection_fields(tmp_path):
    client = make_client(tmp_path)

    settings = client.get("/api/settings").get_json()["settings"]
    settings["providers"]["provider_0002"] = {
        "display_name": "",
        "adapter": "openai",
        "base_url": "",
        "api_key": "",
        "api_key_env": "",
        "model": "",
        "user_agent": "",
        "proxy_url": "",
        "openai_call_method": "gpt-image-2",
        "openai_example_mode": "text_to_image",
    }
    resp = client.put("/api/settings", json=settings)

    assert resp.status_code == 200
    provider = resp.get_json()["settings"]["providers"]["provider_0002"]
    assert provider["display_name"] == ""
    assert provider["base_url"] == ""
    assert provider["api_key"] == ""
    assert provider["api_key_env"] == ""
    assert provider["model"] == ""
    assert provider["user_agent"] == ""
    assert provider["proxy_url"] == ""


def test_settings_put_normalizes_default_resolution(tmp_path):
    client = make_client(tmp_path)

    valid_resp = client.put("/api/settings", json={"default_resolution": "2K"})
    invalid_resp = client.put("/api/settings", json={"default_resolution": "8K"})

    assert valid_resp.status_code == 200
    assert valid_resp.get_json()["settings"]["default_resolution"] == "2K"
    assert invalid_resp.status_code == 200
    assert invalid_resp.get_json()["settings"]["default_resolution"] == "1K"


def test_settings_put_normalizes_v012_generation_defaults(tmp_path):
    client = make_client(tmp_path)

    resp = client.put(
        "/api/settings",
        json={
            "default_aspect_ratio": "16:9",
            "default_clarity": "custom",
            "default_size": "1234x567",
            "custom_generation_sizes": ["1234x567", "bad", "1234x567"],
        },
    )

    assert resp.status_code == 200
    settings = resp.get_json()["settings"]
    assert settings["default_aspect_ratio"] == "16:9"
    assert settings["default_clarity"] == "custom"
    assert settings["default_resolution"] == "custom"
    assert settings["default_size"] == "1234x567"
    assert settings["custom_generation_sizes"] == ["1234x567"]


def test_settings_put_recovers_invalid_providers_shape(tmp_path):
    client = make_client(tmp_path)

    resp = client.put("/api/settings", json={"providers": []})

    assert resp.status_code == 200
    settings = resp.get_json()["settings"]
    assert isinstance(settings["providers"], dict)
    assert "aiapis_gpt_image_2" in settings["providers"]


def test_settings_get_returns_real_api_key(tmp_path):
    client = make_client(tmp_path)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["providers"]["aiapis_gpt_image_2"]["api_key"] = "real-secret-key"

    save_resp = client.put("/api/settings", json=settings)
    get_resp = client.get("/api/settings")

    assert save_resp.status_code == 200
    provider = get_resp.get_json()["settings"]["providers"][
        "aiapis_gpt_image_2"
    ]
    assert provider["api_key"] == "real-secret-key"


def test_settings_put_overwrites_api_key_directly(tmp_path):
    config_file = tmp_path / "config.json"
    app = create_app(db_file=tmp_path / "test.sqlite", config_file=config_file)
    app.config.update(TESTING=True)
    client = app.test_client()

    settings = client.get("/api/settings").get_json()["settings"]
    settings["providers"]["aiapis_gpt_image_2"]["api_key"] = "real-secret-key"
    client.put("/api/settings", json=settings)

    overwrite_settings = client.get("/api/settings").get_json()["settings"]
    overwrite_settings["providers"]["aiapis_gpt_image_2"]["api_key"] = "new-secret-key"
    overwrite_resp = client.put("/api/settings", json=overwrite_settings)

    stored = json.loads(config_file.read_text(encoding="utf-8"))
    assert overwrite_resp.status_code == 200
    assert app.config["APP_CONFIG"]["providers"]["aiapis_gpt_image_2"]["api_key"] == (
        "new-secret-key"
    )
    assert stored["providers"]["aiapis_gpt_image_2"]["api_key"] == "new-secret-key"


def test_settings_put_empty_api_key_clears_stored_key(tmp_path):
    config_file = tmp_path / "config.json"
    app = create_app(db_file=tmp_path / "test.sqlite", config_file=config_file)
    app.config.update(TESTING=True)
    client = app.test_client()

    settings = client.get("/api/settings").get_json()["settings"]
    settings["providers"]["aiapis_gpt_image_2"]["api_key"] = "real-secret-key"
    client.put("/api/settings", json=settings)

    clear_settings = client.get("/api/settings").get_json()["settings"]
    clear_settings["providers"]["aiapis_gpt_image_2"]["api_key"] = ""
    clear_resp = client.put("/api/settings", json=clear_settings)

    stored = json.loads(config_file.read_text(encoding="utf-8"))
    provider = clear_resp.get_json()["settings"]["providers"][
        "aiapis_gpt_image_2"
    ]
    assert clear_resp.status_code == 200
    assert provider["api_key"] == ""


def test_v042_openai_script_examples_endpoint_reads_shared_scripts(tmp_path):
    client = make_client(tmp_path)

    resp = client.get("/api/openai-script-examples")

    assert resp.status_code == 200
    payload = resp.get_json()
    text_script = (Path(__file__).resolve().parents[2] / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")
    image_script = (Path(__file__).resolve().parents[2] / "files" / "openai_image_to_image.py").read_text(encoding="utf-8")
    assert payload["text_to_image"] == text_script
    assert payload["image_to_image"] == image_script
    assert "sk-" not in payload["text_to_image"]
    assert "sk-" not in payload["image_to_image"]


def test_settings_page_payload_preserves_hidden_defaults_and_saves_layout(tmp_path):
    config_file = tmp_path / "config.json"
    app = create_app(db_file=tmp_path / "test.sqlite", config_file=config_file)
    app.config.update(TESTING=True)
    client = app.test_client()

    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_size"] = "768x1024"
    settings["default_resolution"] = "2K"
    settings["default_output_dir"] = "D:\\AIOutput"
    settings["save_layout"] = "single"
    client.put("/api/settings", json=settings)

    settings_page_payload = client.get("/api/settings").get_json()["settings"]
    settings_page_payload.pop("default_size", None)
    settings_page_payload.pop("default_resolution", None)
    settings_page_payload.pop("default_output_dir", None)
    settings_page_payload["save_layout"] = "double"

    resp = client.put("/api/settings", json=settings_page_payload)

    stored = json.loads(config_file.read_text(encoding="utf-8"))
    assert resp.status_code == 200
    assert resp.get_json()["settings"]["default_size"] == "768x1024"
    assert resp.get_json()["settings"]["default_resolution"] == "2K"
    assert resp.get_json()["settings"]["default_output_dir"] == "D:\\AIOutput"
    assert resp.get_json()["settings"]["save_layout"] == "double"
    assert stored["save_layout"] == "double"
    assert stored["default_resolution"] == "2K"
    assert stored["default_output_dir"] == "D:\\AIOutput"


def test_choose_directory_returns_mocked_path(tmp_path):
    client = make_client(tmp_path)

    with patch("backend.api.choose_directory", return_value="D:\\AIOutput") as choose:
        resp = client.post("/api/dialogs/directory", json={"initial_dir": "D:\\Start"})

    assert resp.status_code == 200
    assert resp.get_json() == {"path": "D:\\AIOutput"}
    choose.assert_called_once_with("D:\\Start")


def test_choose_images_returns_mocked_paths(tmp_path):
    client = make_client(tmp_path)

    with patch(
        "backend.api.choose_images",
        return_value=["D:\\Images\\one.png", "D:\\Images\\two.png"],
    ):
        resp = client.post("/api/dialogs/images", json={})

    assert resp.status_code == 200
    assert resp.get_json() == {
        "paths": ["D:\\Images\\one.png", "D:\\Images\\two.png"]
    }


def test_bulk_create_instances_returns_created_items(tmp_path):
    client = make_client(tmp_path)

    resp = client.post(
        "/api/instances/bulk",
        json={
            "items": [
                {"prompt": "新实例", "source": "manual", "tags": ["one"]},
                {"prompt": "新实例", "source": "manual", "tags": ["two"]},
            ]
        },
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert [item["prompt"] for item in data["items"]] == ["新实例", "新实例"]
    assert [item["tags"] for item in data["items"]] == [["one"], ["two"]]


def test_image_route_serves_existing_file(tmp_path):
    client = make_client(tmp_path)
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    resp = client.get("/api/image", query_string={"path": str(image)})

    assert resp.status_code == 200
    assert resp.data == b"\x89PNG\r\n\x1a\n"


def test_image_route_returns_404_for_missing_file(tmp_path):
    client = make_client(tmp_path)

    resp = client.get("/api/image", query_string={"path": str(tmp_path / "missing.png")})

    assert resp.status_code == 404


def test_clipboard_image_paths_endpoint_returns_original_paths(tmp_path):
    client = make_client(tmp_path)
    image_paths = ["D:\\Images\\one.png", "M:\\Refs\\two.webp"]

    with patch("backend.api.clipboard_image_paths", return_value=image_paths):
        resp = client.get("/api/clipboard/image-paths")

    assert resp.status_code == 200
    assert resp.get_json() == {"paths": image_paths}


def test_clipboard_image_paths_endpoint_reports_empty_clipboard(tmp_path):
    client = make_client(tmp_path)

    with patch("backend.api.clipboard_image_paths", return_value=[]):
        resp = client.get("/api/clipboard/image-paths")

    assert resp.status_code == 400
    assert "剪贴板中没有可用的本地图片路径" in resp.get_json()["error"]


def test_favicon_request_does_not_log_browser_404(tmp_path):
    client = make_client(tmp_path)

    resp = client.get("/favicon.ico")

    assert resp.status_code == 204


def test_choose_directory_failure_returns_json_error(tmp_path):
    client = make_client(tmp_path)

    with patch("backend.api.choose_directory", side_effect=RuntimeError("boom")):
        resp = client.post("/api/dialogs/directory", json={})

    assert resp.status_code == 500
    assert resp.get_json() == {"error": "无法打开文件选择窗口：boom"}


def test_choose_images_failure_returns_json_error(tmp_path):
    client = make_client(tmp_path)

    with patch("backend.api.choose_images", side_effect=RuntimeError("boom")):
        resp = client.post("/api/dialogs/images", json={})

    assert resp.status_code == 500
    assert resp.get_json() == {"error": "无法打开文件选择窗口：boom"}


def test_list_accepts_repeated_and_comma_separated_tags(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/instances", json={"prompt": "产品海报", "tags": ["产品", "海报"]})
    client.post("/api/instances", json={"prompt": "产品摄影", "tags": ["产品"]})

    repeated_resp = client.get("/api/instances?tags=产品&tags=海报")
    comma_resp = client.get("/api/instances?tags=产品,海报")

    assert repeated_resp.status_code == 200
    assert repeated_resp.get_json()["total"] == 1
    assert comma_resp.status_code == 200
    assert comma_resp.get_json()["total"] == 1


def test_create_instance_allows_empty_prompt(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/api/instances", json={"prompt": "   "})

    assert resp.status_code == 201
    assert resp.get_json()["item"]["prompt"] == ""


def test_empty_json_object_creates_blank_manual_instance(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/api/instances", json={})

    assert resp.status_code == 201
    item = resp.get_json()["item"]
    assert item["prompt"] == ""
    assert item["source"] == "manual"


def test_update_instance_allows_empty_prompt(tmp_path):
    client = make_client(tmp_path)
    instance = client.post("/api/instances", json={"prompt": "原提示词"}).get_json()["item"]

    resp = client.put(
        f"/api/instances/{instance['id']}",
        json={
            "prompt": "   ",
            "mode": "unspecified",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": [],
        },
    )

    assert resp.status_code == 200
    assert resp.get_json()["item"]["prompt"] == ""


def test_manual_instance_provider_round_trip_accepts_free_text_and_empty_value(tmp_path):
    client = make_client(tmp_path)
    create_resp = client.post(
        "/api/instances",
        json={
            "prompt": "外部收藏",
            "mode": "unspecified",
            "source": "manual",
            "provider": "Midjourney 收藏",
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": [],
        },
    )

    assert create_resp.status_code == 201
    item = create_resp.get_json()["item"]
    assert item["provider"] == "Midjourney 收藏"

    update_resp = client.put(
        f"/api/instances/{item['id']}",
        json={
            "prompt": "外部收藏",
            "mode": "unspecified",
            "source": "manual",
            "provider": "",
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": [],
        },
    )

    assert update_resp.status_code == 200
    assert update_resp.get_json()["item"]["provider"] == ""


def test_malformed_json_returns_json_object_error(tmp_path):
    client = make_client(tmp_path)
    resp = client.post(
        "/api/instances",
        data="{",
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert resp.get_json() == {"error": "请求体必须是 JSON 对象"}


def test_update_missing_instance_returns_404(tmp_path):
    client = make_client(tmp_path)
    resp = client.put(
        "/api/instances/999",
        json={
            "prompt": "missing",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": [],
        },
    )

    assert resp.status_code == 404
    assert "实例不存在" in resp.get_json()["error"]


def test_delete_missing_instance_returns_404(tmp_path):
    client = make_client(tmp_path)
    resp = client.delete("/api/instances/999")

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "实例不存在"}


def test_path_replace_apply_failure_returns_json_500(tmp_path):
    client = make_client(tmp_path)

    with patch("backend.api.apply_path_replacement", side_effect=OSError("boom")):
        resp = client.post(
            "/api/paths/replace/apply",
            json={"find": r"C:\old", "replace": r"D:\new"},
        )

    assert resp.status_code == 500
    assert resp.get_json() == {"error": "路径替换失败：boom"}


def test_generate_creates_generated_instance_without_live_api_call(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "fake.png"
    input_image = tmp_path / "input.png"
    input_image.write_bytes(b"image")
    expected_output_dir = str(output_dir)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"]["user_agent"] = (
        "Mozilla/5.0 PowerShell/7.4"
    )
    client.put("/api/settings", json=settings)

    def assert_context(context):
        assert context["output_dir"] == expected_output_dir
        assert context["mode"] == "image_to_image"
        assert context["input_images"] == [str(input_image)]
        assert context["resolved_size"] == "3840x2160"
        assert context["n"] == 2

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result([output_image], assert_context=assert_context),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "image_to_image",
                "input_image_paths": [str(input_image)],
                "tags": ["产品", "海报"],
                "options": {"ratio": "16:9", "resolution_level": "4K", "n": 2},
            },
        )

    assert resp.status_code == 201
    item = resp.get_json()["item"]
    assert item["prompt"] == "产品海报"
    assert item["mode"] == "image_to_image"
    assert item["source"] == "generated"
    assert item["input_image_paths"] == [str(input_image)]
    assert item["tags"] == ["产品", "海报"]
    assert item["generation_path"] == str(output_dir)
    assert item["generation_size"] == "3840x2160"
    assert item["generation_params"]["provider_key"] == "aiapis_gpt_image_2"
    assert item["generation_params"]["adapter"] == "openai"
    assert item["generation_params"]["openai_call_method"] == "gpt-image-2"
    assert item["generation_params"]["model"] == "gpt-image-2"
    assert item["generation_params"]["ratio"] == "16:9"
    assert item["generation_params"]["resolution_level"] == "4K"
    assert item["generation_params"]["resolved_size"] == "3840x2160"
    assert item["generation_params"]["n"] == 2
    assert item["generation_params"]["user_agent"] == "Mozilla/5.0 PowerShell/7.4"
    assert item["generation_params"]["proxy_mode"] == "system"
    assert item["generation_params"]["allow_untrusted_proxy_certificate"] is True
    assert item["provider"] == "aiapis_gpt_image_2"
    assert item["output_image_path"] == str(output_image)

    history_resp = client.get("/api/generation-history")
    history = history_resp.get_json()
    assert history_resp.status_code == 200
    assert history["total"] == 1
    assert history["items"][0]["status"] == "success"
    assert history["items"][0]["prompt"] == "产品海报"
    assert history["items"][0]["output_image_paths"] == [str(output_image)]
    assert history["items"][0]["params"]["user_agent"] == (
        "Mozilla/5.0 PowerShell/7.4"
    )
    assert history["items"][0]["params"]["proxy_mode"] == "system"
    assert history["items"][0]["params"]["allow_untrusted_proxy_certificate"] is True


def test_v044_generate_retries_retryable_errors_and_records_each_failure(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "retry-success.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)
    calls = []

    class Retryable502(Exception):
        status_code = 502

    def fake_run_custom_script(script, context, timeout_seconds=None):
        calls.append(context)
        if len(calls) < 3:
            raise Retryable502("Error code: 502 - origin_bad_gateway retryable true")
        output_image.parent.mkdir(parents=True, exist_ok=True)
        output_image.write_bytes(b"image")
        return ImageGenerationResult(output_paths=[str(output_image)], provider="shared_script")

    with patch("backend.api.GENERATION_RETRY_DELAYS", [0, 0, 0]), patch(
        "backend.api.run_custom_script",
        side_effect=fake_run_custom_script,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "重试测试",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 201
    assert len(calls) == 3
    item = resp.get_json()["item"]
    assert item["generation_status"] == "ready"
    assert item["output_image_path"] == str(output_image)
    history = client.get("/api/generation-history?per_page=10").get_json()
    assert history["total"] == 1
    grouped = history["items"][0]
    assert grouped["status"] == "success"
    assert grouped["retry_count"] == 2
    failed = grouped["retry_records"]
    assert [record["params"]["retry_attempt"] for record in failed] == [1, 2]
    assert all("502" in record["error_message"] for record in failed)
    assert all(record["params"]["retryable"] is True for record in failed)


def test_v0451_cancel_stops_before_next_retry_attempt(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)
    calls = []

    class Retryable502(Exception):
        status_code = 502

    def fake_run_custom_script(script, context, timeout_seconds=None):
        calls.append(context)
        raise Retryable502("Error code: 502 - origin_bad_gateway retryable true")

    def fake_sleep(task_id, delay_seconds):
        client.post("/api/generate/cancel", json={"generation_task_id": task_id})

    with patch("backend.api.GENERATION_RETRY_DELAYS", [0, 0, 0]), patch(
        "backend.api.sleep_for_retry",
        side_effect=fake_sleep,
    ), patch(
        "backend.api.run_custom_script",
        side_effect=fake_run_custom_script,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "取消重试",
                "mode": "text_to_image",
                "generation_task_id": "cancel-before-retry",
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "生成已取消"
    assert len(calls) == 1
    item = client.get("/api/instances").get_json()["items"][0]
    assert item["generation_status"] == "failed"
    assert item["generation_error"] == "生成已取消"


def test_v0501_cancel_endpoint_does_not_finalize_running_instance_before_task_finishes(tmp_path):
    client = make_client(tmp_path)
    instance_id = client.post(
        "/api/instances",
        json={
            "prompt": "取消中先不落最终状态",
            "generation_status": "running",
            "generation_task_id": "cancel-visible-task",
        },
    ).get_json()["item"]["id"]

    resp = client.post("/api/generate/cancel", json={"generation_task_id": "cancel-visible-task"})

    assert resp.status_code == 200
    assert resp.get_json()["cancelled"] is True
    assert resp.get_json()["updated"] == 0
    item = instance_by_id(client, instance_id)
    assert item["generation_status"] == "running"
    assert item["generation_error"] == ""


def test_v0451_cancel_during_request_error_does_not_enter_retry_wait(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)
    calls = []
    sleep_calls = []

    class Retryable502(Exception):
        status_code = 502

    def fake_run_custom_script(script, context, timeout_seconds=None):
        calls.append(context)
        client.post("/api/generate/cancel", json={"generation_task_id": "cancel-during-request"})
        raise Retryable502("Error code: 502 - origin_bad_gateway retryable true")

    def fake_sleep(task_id, delay_seconds):
        sleep_calls.append((task_id, delay_seconds))

    with patch("backend.api.GENERATION_RETRY_DELAYS", [0, 0, 0]), patch(
        "backend.api.sleep_for_retry",
        side_effect=fake_sleep,
    ), patch(
        "backend.api.run_custom_script",
        side_effect=fake_run_custom_script,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "请求途中取消",
                "mode": "text_to_image",
                "generation_task_id": "cancel-during-request",
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "生成已取消"
    assert len(calls) == 1
    assert sleep_calls == []
    item = client.get("/api/instances").get_json()["items"][0]
    assert item["generation_status"] == "failed"
    assert item["generation_error"] == "生成已取消"


def test_v0451_retryable_errors_stop_after_default_attempt_limit(tmp_path):
    assert api_module.GENERATION_RETRY_MAX_ATTEMPTS > 0
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)
    calls = []

    class Retryable502(Exception):
        status_code = 502

    def fake_run_custom_script(script, context, timeout_seconds=None):
        calls.append(context)
        raise Retryable502("Error code: 502 - origin_bad_gateway retryable true")

    with patch("backend.api.GENERATION_RETRY_DELAYS", [0, 0, 0, 0, 0, 0]), patch(
        "backend.api.run_custom_script",
        side_effect=fake_run_custom_script,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "持续失败重试",
                "mode": "text_to_image",
                "generation_task_id": "retry-limit",
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 500
    assert len(calls) == api_module.GENERATION_RETRY_MAX_ATTEMPTS
    item = client.get("/api/instances").get_json()["items"][0]
    assert item["generation_status"] == "failed"
    assert "502" in item["generation_error"]
    history = client.get("/api/generation-history?per_page=20").get_json()
    assert history["total"] == 1
    grouped = history["items"][0]
    assert grouped["status"] == "failed"
    assert grouped["retry_count"] == api_module.GENERATION_RETRY_MAX_ATTEMPTS - 1
    retry_records = grouped["retry_records"]
    assert len(retry_records) == api_module.GENERATION_RETRY_MAX_ATTEMPTS - 1
    assert all(record["params"].get("retryable") is True for record in retry_records)
    assert all("502" in record["error_message"] for record in [*retry_records, grouped])


def test_v044_generate_records_retry_events_reported_by_shared_script(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "script-retry-success.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)

    def fake_run_custom_script(script, context, timeout_seconds=None):
        output_image.parent.mkdir(parents=True, exist_ok=True)
        output_image.write_bytes(b"image")
        return ImageGenerationResult(
            output_paths=[str(output_image)],
            provider="shared_script",
            retry_events=[
                {
                    "attempt": 1,
                    "delay_seconds": 60,
                    "error": "Error code: 502 - origin_bad_gateway",
                }
            ],
        )

    with patch("backend.api.run_custom_script", side_effect=fake_run_custom_script):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "脚本内部重试",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 201
    history = client.get("/api/generation-history?per_page=10").get_json()
    assert history["total"] == 1
    grouped = history["items"][0]
    failed = grouped["retry_records"]
    assert grouped["status"] == "success"
    assert grouped["retry_count"] == 1
    assert len(failed) == 1
    assert failed[0]["params"]["retry_attempt"] == 1
    assert failed[0]["params"]["retry_delay_seconds"] == 60


def test_v044_shared_text_script_retries_via_backend_and_records_each_http_502(tmp_path, monkeypatch):
    server, requests = run_retrying_mock_openai_server(failures=2)
    try:
        monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
        monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
        client = make_client(tmp_path)
        output_dir = tmp_path / "generated"
        settings = client.get("/api/settings").get_json()["settings"]
        settings["default_output_dir"] = str(output_dir)
        provider = settings["providers"]["aiapis_gpt_image_2"]
        provider["adapter"] = "openai"
        provider["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
        provider["api_key"] = "test-key"
        provider["api_key_env"] = ""
        provider["openai_call_method"] = "gpt-image-2"
        provider["output_format"] = "png"
        provider["user_agent"] = "Mozilla/5.0 PowerShell/7.4"
        provider["custom_scripts"] = {}
        client.put("/api/settings", json=settings)

        with patch("backend.api.GENERATION_RETRY_DELAYS", [0, 0, 0]), patch(
            "backend.api.generate_image",
        ) as generate_image:
            resp = client.post(
                "/api/generate",
                json={
                    "prompt": "脚本后端重试",
                    "mode": "text_to_image",
                    "input_image_paths": [],
                    "tags": [],
                    "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
                },
            )

        assert resp.status_code == 201
        generate_image.assert_not_called()
        assert len(requests) == 3
        payload = resp.get_json()
        assert Path(payload["output_image_paths"][0]).read_bytes() == b"mock-image"
        history = client.get("/api/generation-history?per_page=10").get_json()
        assert history["total"] == 1
        grouped = history["items"][0]
        failed = grouped["retry_records"]
        success = [grouped] if grouped["status"] == "success" else []
        assert len(failed) == 2
        assert len(success) == 1
        assert [record["params"]["retry_attempt"] for record in failed] == [1, 2]
        assert all(record["params"]["retryable"] is True for record in failed)
        assert all("502" in record["error_message"] for record in failed)
    finally:
        server.shutdown()
        server.server_close()
    assert "502" in failed[0]["error_message"]


def test_generate_accepts_custom_size_and_count(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "fake.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)

    def assert_context(context):
        assert context["resolved_size"] == "1234x567"
        assert context["n"] == 3

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result([output_image], assert_context=assert_context),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {
                    "size": "1234x567",
                    "ratio": "custom",
                    "resolution_level": "custom",
                    "n": 3,
                },
            },
        )

    assert resp.status_code == 201
    assert resp.get_json()["item"]["output_image_path"] == str(output_image)
    payload = resp.get_json()
    assert len(payload["items"]) == 3
    assert [item["output_image_path"] for item in payload["items"]] == [
        str(output_image),
        "",
        "",
    ]
    assert client.get("/api/instances").get_json()["total"] == 3


def test_generate_saves_response_call_method_in_generation_params(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "fake.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"]["openai_call_method"] = "response"
    client.put("/api/settings", json=settings)

    def fake_generate_image(provider, mode, prompt, input_images, output_dir, options):
        output_image.parent.mkdir(parents=True, exist_ok=True)
        output_image.write_bytes(b"image")
        return ImageGenerationResult(
            output_path=str(output_image),
            provider=provider.name,
        )

    with patch("backend.api.generate_image", side_effect=fake_generate_image):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 2},
            },
        )

    assert resp.status_code == 201
    params = resp.get_json()["item"]["generation_params"]
    assert params["openai_call_method"] == "response"
    assert params["model"] == "response"
    assert params["n"] == 2


def test_failed_generation_history_params_keep_provider_snapshot(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["active_provider"] = "google_proxy"
    settings["providers"]["google_proxy"] = {
        "display_name": "Google Proxy",
        "adapter": "google",
        "base_url": "https://google.example/v1",
        "api_key": "key",
        "api_key_env": "",
        "user_agent": "UA",
        "openai_call_method": "gpt-image-2",
    }
    client.put("/api/settings", json=settings)

    resp = client.post(
        "/api/generate",
        json={
            "prompt": "产品海报",
            "mode": "text_to_image",
            "input_image_paths": [],
            "tags": [],
            "options": {"ratio": "16:9", "resolution_level": "4K", "n": 2},
        },
    )

    assert resp.status_code == 400
    history = client.get("/api/generation-history").get_json()
    assert history["total"] == 1
    item = history["items"][0]
    assert item["status"] == "failed"
    assert item["provider_key"] == "google_proxy"
    assert item["adapter"] == "google"
    assert item["openai_call_method"] == "gpt-image-2"
    assert item["params"]["provider_key"] == "google_proxy"
    assert item["params"]["adapter"] == "google"
    assert item["params"]["openai_call_method"] == "gpt-image-2"
    assert item["params"]["model"] == "gpt-image-2"


def test_v040_generation_history_saves_submitted_tags_snapshot(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "tagged.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result([output_image]),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "带标签历史",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": ["产品", "__untagged__", "", "海报"],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 201
    history = client.get("/api/generation-history").get_json()
    assert history["total"] == 1
    assert history["items"][0]["tags"] == ["产品", "海报"]


def test_generate_multiple_outputs_creates_one_instance_per_output(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    input_image = tmp_path / "input.png"
    input_image.write_bytes(b"image")
    output_paths = [
        output_dir / "one.png",
        output_dir / "two.png",
        output_dir / "three.png",
    ]
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result(output_paths),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "image_to_image",
                "input_image_paths": [str(input_image)],
                "tags": ["产品"],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 3},
            },
        )

    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["output_image_paths"] == [str(path) for path in output_paths]
    assert [item["output_image_path"] for item in payload["items"]] == [
        str(path) for path in output_paths
    ]
    assert payload["item"]["output_image_path"] == str(output_paths[-1])
    assert all(item["input_image_paths"] == [str(input_image)] for item in payload["items"])
    assert all(item["tags"] == ["产品"] for item in payload["items"])
    assert all(item["generation_params"]["n"] == 3 for item in payload["items"])


def test_generate_text_to_image_n_gt_one_preserves_count_and_history_outputs(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_paths = [
        output_dir / "one.png",
        output_dir / "two.png",
        output_dir / "three.png",
    ]
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)

    def assert_context(context):
        assert context["mode"] == "text_to_image"
        assert context["n"] == 3

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result(output_paths, assert_context=assert_context),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": ["多图"],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 3},
            },
        )

    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["output_image_paths"] == [str(path) for path in output_paths]
    assert len(payload["items"]) == 3
    assert all(item["generation_params"]["n"] == 3 for item in payload["items"])
    assert payload["item"]["output_image_path"] == str(output_paths[-1])

    instances = client.get("/api/instances").get_json()
    assert instances["total"] == 3
    history = client.get("/api/generation-history").get_json()
    assert history["total"] == 1
    assert history["items"][0]["output_image_paths"] == [str(path) for path in output_paths]
    assert history["items"][0]["params"]["n"] == 3


def test_v062_target_instance_n_gt_one_stays_one_instance_with_multiple_outputs(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_paths = [
        output_dir / "one.png",
        output_dir / "two.png",
        output_dir / "three.png",
    ]
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)

    draft_resp = client.post(
        "/api/instances",
        json={
            "prompt": "准备态多图",
            "mode": "text_to_image",
            "source": "manual",
            "provider": "aiapis_gpt_image_2",
            "generation_path": str(output_dir),
            "generation_size": "1024x1024",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["多图"],
            "generation_params": {
                "provider_key": "aiapis_gpt_image_2",
                "openai_call_method": "gpt-image-2",
                "ratio": "1:1",
                "resolution_level": "1K",
                "resolved_size": "1024x1024",
                "n": 3,
            },
        },
    )
    assert draft_resp.status_code == 201
    draft_id = draft_resp.get_json()["item"]["id"]

    def assert_context(context):
        assert context["mode"] == "text_to_image"
        assert context["n"] == 3

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result(output_paths, assert_context=assert_context),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "target_instance_id": draft_id,
                "generation_task_id": "task-v062-target",
                "provider_key": "aiapis_gpt_image_2",
                "prompt": "准备态多图",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": ["多图"],
                "generation_path": str(output_dir),
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 3},
            },
        )

    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["output_image_paths"] == [str(path) for path in output_paths]
    assert len(payload["items"]) == 1
    assert payload["item"]["id"] == draft_id
    assert payload["item"]["output_image_path"] == str(output_paths[0])
    assert payload["item"]["output_image_paths"] == [str(path) for path in output_paths]
    assert payload["item"]["generation_params"]["n"] == 3
    assert payload["item"]["generation_params"]["output_image_paths"] == [str(path) for path in output_paths]

    instances = client.get("/api/instances").get_json()
    assert instances["total"] == 1
    assert instances["items"][0]["id"] == draft_id
    assert instances["items"][0]["output_image_paths"] == [str(path) for path in output_paths]

    history = client.get("/api/generation-history").get_json()
    assert history["total"] == 1
    assert history["items"][0]["output_image_paths"] == [str(path) for path in output_paths]
    assert history["items"][0]["params"]["n"] == 3
    assert history["items"][0]["params"]["instance_ids"] == [draft_id]


def test_generate_provider_failure_preserves_precreated_empty_instances(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)

    with patch("backend.api.run_custom_script", side_effect=RuntimeError("provider down")):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "失败也要保留",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": ["失败保留"],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 2},
            },
        )

    assert resp.status_code == 500
    instances = client.get("/api/instances").get_json()
    assert instances["total"] == 2
    assert [item["prompt"] for item in instances["items"]] == ["失败也要保留", "失败也要保留"]
    assert [item["output_image_path"] for item in instances["items"]] == ["", ""]
    assert [item["generation_status"] for item in instances["items"]] == ["failed", "failed"]
    assert all("provider down" in item["generation_error"] for item in instances["items"])
    assert all(item["tags"] == ["失败保留"] for item in instances["items"])
    history = client.get("/api/generation-history").get_json()
    assert history["total"] == 1
    assert history["items"][0]["status"] == "failed"
    assert "provider down" in history["items"][0]["error_message"]


def test_retry_failed_generation_updates_same_instance_without_creating_duplicate(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "retry.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)

    with patch("backend.api.run_custom_script", side_effect=RuntimeError("provider down")):
        failed_resp = client.post(
            "/api/generate",
            json={
                "generation_task_id": "task-failed",
                "prompt": "失败后原位重跑",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": ["失败"],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert failed_resp.status_code == 500
    failed_item = client.get("/api/instances").get_json()["items"][0]
    assert failed_item["generation_status"] == "failed"

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result([output_image]),
    ):
        retry_resp = client.post(
            "/api/generate",
            json={
                "retry_instance_id": failed_item["id"],
                "generation_task_id": "task-retry",
                "prompt": "失败后原位重跑",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": ["失败"],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert retry_resp.status_code == 201
    payload = retry_resp.get_json()
    assert payload["item"]["id"] == failed_item["id"]
    assert payload["item"]["generation_status"] == "ready"
    assert payload["item"]["output_image_path"] == str(output_image)
    instances = client.get("/api/instances").get_json()
    assert instances["total"] == 1
    assert instances["items"][0]["id"] == failed_item["id"]


def test_v029_generate_accepts_node_id_for_precreated_instances_and_failed_retry(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    first_output = output_dir / "node-one.png"
    retry_output = output_dir / "node-retry.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    client.put("/api/settings", json=settings)
    first_node = client.post("/api/nodes", json={"name": "第一节点"}).get_json()["item"]["id"]
    second_node = client.post("/api/nodes", json={"name": "第二节点"}).get_json()["item"]["id"]

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result([first_output]),
    ):
        first_resp = client.post(
            "/api/generate",
            json={
                "prompt": "节点生成",
                "mode": "text_to_image",
                "node_id": first_node,
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert first_resp.status_code == 201
    assert first_resp.get_json()["item"]["node_id"] == first_node

    with patch("backend.api.run_custom_script", side_effect=RuntimeError("provider down")):
        failed_resp = client.post(
            "/api/generate",
            json={
                "prompt": "失败节点",
                "mode": "text_to_image",
                "node_id": first_node,
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )
    failed_item = client.get("/api/instances?sort=created_desc").get_json()["items"][0]
    assert failed_resp.status_code == 500
    assert failed_item["generation_status"] == "failed"
    assert failed_item["node_id"] == first_node

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result([retry_output]),
    ):
        retry_resp = client.post(
            "/api/generate",
            json={
                "retry_instance_id": failed_item["id"],
                "prompt": "失败节点",
                "mode": "text_to_image",
                "node_id": second_node,
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert retry_resp.status_code == 201
    assert retry_resp.get_json()["item"]["id"] == failed_item["id"]
    assert retry_resp.get_json()["item"]["node_id"] == second_node


def test_generate_text_to_image_uses_custom_script_and_creates_multiple_instances(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"]["user_agent"] = "Custom-UA"
    settings["providers"]["aiapis_gpt_image_2"]["custom_scripts"] = {
        "gpt-image-2": {
            "text_to_image": """
from pathlib import Path
import json

first = Path(output_path)
second = first.with_name(first.stem + "_2" + first.suffix)
first.write_text(user_agent, encoding="utf-8")
second.write_bytes(b"two")
Path(result_json_path).write_text(
    json.dumps({"output_paths": [str(first), str(second)]}),
    encoding="utf-8",
)
"""
        }
    }
    client.put("/api/settings", json=settings)

    with patch("backend.api.generate_image") as generate_image:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": ["脚本"],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 2},
            },
        )

    assert resp.status_code == 201
    generate_image.assert_not_called()
    payload = resp.get_json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["generation_params"]["custom_script_used"] is True
    assert payload["items"][0]["generation_params"]["n"] == 2
    assert [Path(path).read_text(encoding="utf-8") if index == 0 else Path(path).read_bytes() for index, path in enumerate(payload["output_image_paths"])] == [
        "Custom-UA",
        b"two",
    ]


def test_generate_openai_gpt_image_2_defaults_to_shared_text_script(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_file = output_dir / "shared-script.png"
    shared_script = tmp_path / "openai_text_to_image.py"
    shared_script.write_text("# shared text script sentinel", encoding="utf-8")
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"]["adapter"] = "openai"
    settings["providers"]["aiapis_gpt_image_2"]["openai_call_method"] = "gpt-image-2"
    settings["providers"]["aiapis_gpt_image_2"]["model"] = "custom-text-model"
    settings["providers"]["aiapis_gpt_image_2"]["proxy_mode"] = "custom"
    settings["providers"]["aiapis_gpt_image_2"]["proxy_url"] = "http://127.0.0.1:7890"
    settings["providers"]["aiapis_gpt_image_2"]["allow_untrusted_proxy_certificate"] = False
    settings["providers"]["aiapis_gpt_image_2"]["custom_scripts"] = {}
    client.put("/api/settings", json=settings)

    def fake_run_custom_script(script, context, timeout_seconds=None):
        assert script == "# shared text script sentinel"
        assert context["operation_prompt"] == "产品海报"
        assert context["mode"] == "text_to_image"
        assert context["resolved_size"] == "1024x1024"
        assert context["model"] == "custom-text-model"
        assert context["use_system_proxy"] is True
        assert context["system_proxy"] == "http://127.0.0.1:7890"
        assert context["allow_untrusted_proxy_certificate"] is False
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"image")
        return ImageGenerationResult(output_path=str(output_file), provider="shared_script")

    with (
        patch("backend.api.default_openai_script_for_generation", return_value=shared_script),
        patch("backend.api.run_custom_script", side_effect=fake_run_custom_script) as run_script,
        patch("backend.api.generate_image") as generate_image,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 201
    run_script.assert_called_once()
    generate_image.assert_not_called()
    assert resp.get_json()["output_image_paths"] == [str(output_file)]


def test_generate_openai_gpt_image_2_defaults_to_shared_image_script(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    input_one = tmp_path / "input-one.png"
    input_two = tmp_path / "input-two.png"
    output_file = output_dir / "shared-edit.png"
    shared_script = tmp_path / "openai_image_to_image.py"
    input_one.write_bytes(b"one")
    input_two.write_bytes(b"two")
    shared_script.write_text("# shared image script sentinel", encoding="utf-8")
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"]["adapter"] = "openai"
    settings["providers"]["aiapis_gpt_image_2"]["openai_call_method"] = "gpt-image-2"
    settings["providers"]["aiapis_gpt_image_2"]["model"] = "custom-image-model"
    settings["providers"]["aiapis_gpt_image_2"]["proxy_mode"] = "none"
    settings["providers"]["aiapis_gpt_image_2"]["proxy_url"] = "http://ignored.local:7890"
    settings["providers"]["aiapis_gpt_image_2"]["custom_scripts"] = {}
    client.put("/api/settings", json=settings)

    def fake_run_custom_script(script, context, timeout_seconds=None):
        assert script == "# shared image script sentinel"
        assert context["mode"] == "image_to_image"
        assert context["input_images"] == [str(input_one), str(input_two)]
        assert context["n"] == 3
        assert context["model"] == "custom-image-model"
        assert context["use_system_proxy"] is False
        assert context["system_proxy"] == ""
        assert context["allow_untrusted_proxy_certificate"] is True
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"image")
        return ImageGenerationResult(output_path=str(output_file), provider="shared_script")

    with (
        patch("backend.api.default_openai_script_for_generation", return_value=shared_script),
        patch("backend.api.run_custom_script", side_effect=fake_run_custom_script) as run_script,
        patch("backend.api.generate_image") as generate_image,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "按两张图生成",
                "mode": "image_to_image",
                "input_image_paths": [str(input_one), str(input_two)],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 3},
            },
        )

    assert resp.status_code == 201
    run_script.assert_called_once()
    generate_image.assert_not_called()
    payload = resp.get_json()
    assert payload["output_image_paths"] == [str(output_file)]
    assert payload["item"]["input_image_paths"] == [str(input_one), str(input_two)]


def test_v058_generate_openai_google_defaults_to_shared_text_script(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_file = output_dir / "google-text.png"
    shared_script = tmp_path / "google_b2_text_to_image_xiaoyun.py"
    shared_script.write_text("# openai-google text sentinel", encoding="utf-8")
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    provider = settings["providers"]["aiapis_gpt_image_2"]
    provider.update(
        {
            "adapter": "openai-google",
            "base_url": "https://www.xiaoyunapi.com/v1",
            "api_key": "direct-key",
            "api_key_env": "XIAOYUN_API_KEY",
            "model": "gemini-3.1-flash-image-preview",
            "google_role": "user",
            "google_max_tokens": 4096,
            "google_temperature": "0.7",
            "google_top_p": "0.9",
            "google_stream": False,
            "google_stop": "END",
            "google_presence_penalty": "0.1",
            "google_frequency_penalty": "0.2",
            "google_logit_bias": "{\"42\": 1}",
            "google_user": "operator",
            "google_response_format": "{\"type\":\"json_object\"}",
            "google_seen": "scene-a",
            "google_tools": "[{\"type\":\"function\"}]",
            "google_tool_choice": "auto",
            "proxy_mode": "none",
            "custom_scripts": {},
        }
    )
    client.put("/api/settings", json=settings)

    def fake_run_custom_script(script, context, timeout_seconds=None):
        assert script == "# openai-google text sentinel"
        assert context["operation_prompt"] == "画10只鱼"
        assert context["mode"] == "text_to_image"
        assert context["input_images"] == []
        assert context["base_url"] == "https://www.xiaoyunapi.com/v1"
        assert context["api_key"] == "direct-key"
        assert context["model"] == "gemini-3.1-flash-image-preview"
        assert context["google_role"] == "user"
        assert context["google_max_tokens"] == 4096
        assert context["google_temperature"] == "0.7"
        assert context["google_top_p"] == "0.9"
        assert context["google_stream"] is False
        assert context["google_stop"] == "END"
        assert context["google_presence_penalty"] == "0.1"
        assert context["google_frequency_penalty"] == "0.2"
        assert context["google_logit_bias"] == "{\"42\": 1}"
        assert context["google_user"] == "operator"
        assert context["google_response_format"] == "{\"type\":\"json_object\"}"
        assert context["google_seen"] == "scene-a"
        assert context["google_tools"] == "[{\"type\":\"function\"}]"
        assert context["google_tool_choice"] == "auto"
        assert context["use_system_proxy"] is False
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"image")
        return ImageGenerationResult(output_path=str(output_file), provider="shared_script")

    with (
        patch("backend.api.default_shared_script_for_generation", return_value=shared_script),
        patch("backend.api.run_custom_script", side_effect=fake_run_custom_script) as run_script,
        patch("backend.api.generate_image") as generate_image,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "画10只鱼",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 201
    run_script.assert_called_once()
    generate_image.assert_not_called()
    payload = resp.get_json()
    assert payload["output_image_paths"] == [str(output_file)]
    assert payload["item"]["generation_params"]["adapter"] == "openai-google"
    assert payload["item"]["generation_params"]["shared_script_used"] is True
    assert payload["item"]["generation_params"]["google_max_tokens"] == 4096
    assert payload["item"]["generation_params"]["google_temperature"] == "0.7"


def test_v059_openai_google_records_empty_size_and_shared_path_history(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    old_dir = tmp_path / "old-generated"
    output_file = output_dir / "google-text.png"
    shared_script = tmp_path / "google_b2_text_to_image_xiaoyun.py"
    shared_script.write_text("# openai-google text sentinel", encoding="utf-8")
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["generation_path_history"] = [str(old_dir)]
    provider = settings["providers"]["aiapis_gpt_image_2"]
    provider["adapter"] = "openai-google"
    provider["custom_scripts"] = {}
    client.put("/api/settings", json=settings)

    def fake_run_custom_script(script, context, timeout_seconds=None):
        assert script == "# openai-google text sentinel"
        assert context["resolved_size"] == ""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"image")
        return ImageGenerationResult(output_path=str(output_file), provider="shared_script")

    with (
        patch("backend.api.default_shared_script_for_generation", return_value=shared_script),
        patch("backend.api.run_custom_script", side_effect=fake_run_custom_script),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "画10只鱼",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "generation_path": str(output_dir),
                "options": {"ratio": "", "resolution_level": "", "size": "", "n": 1},
            },
        )

    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["item"]["generation_size"] == ""
    assert payload["item"]["generation_params"]["resolved_size"] == ""
    assert payload["item"]["generation_params"]["adapter"] == "openai-google"

    db_file = Path(client.application.config["DB_FILE"])
    with sqlite3.connect(db_file) as conn:
        row = conn.execute(
            "SELECT resolved_size, params_json FROM generation_history ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row[0] == ""
    assert json.loads(row[1])["resolved_size"] == ""

    history_resp = client.get("/api/generation-path-history")
    assert history_resp.status_code == 200
    assert history_resp.get_json()["paths"][:2] == [str(output_dir), str(old_dir)]


def test_v059_generation_path_history_merges_shared_config_and_successful_instances(tmp_path):
    client = make_client(tmp_path)
    config_path = Path(client.application.config["CONFIG_FILE"])
    first = tmp_path / "shared-first"
    second = tmp_path / "success-second"
    failed = tmp_path / "failed-third"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["generation_path_history"] = [str(first)]
    client.put("/api/settings", json=settings)
    with sqlite3.connect(client.application.config["DB_FILE"]) as conn:
        conn.execute(
            """
            INSERT INTO instances(
              prompt, mode, source, provider, generation_path, generation_size,
              generation_params_json, output_image_path, generation_status,
              generation_task_id, generation_output_index, generation_error,
              generation_started_at, generation_finished_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "成功路径",
                "text_to_image",
                "generated",
                "aiapis_gpt_image_2",
                str(second),
                "",
                "{}",
                str(second / "out.png"),
                "ready",
                "",
                1,
                "",
                "",
                "",
                "2026-05-17T10:00:00",
                "2026-05-17T10:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO instances(
              prompt, mode, source, provider, generation_path, generation_size,
              generation_params_json, output_image_path, generation_status,
              generation_task_id, generation_output_index, generation_error,
              generation_started_at, generation_finished_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "失败路径",
                "text_to_image",
                "generated",
                "aiapis_gpt_image_2",
                str(failed),
                "",
                "{}",
                "",
                "failed",
                "",
                1,
                "失败",
                "",
                "",
                "2026-05-17T11:00:00",
                "2026-05-17T11:00:00",
            ),
        )

    get_resp = client.get("/api/generation-path-history")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["paths"] == [str(first), str(second)]

    post_resp = client.post("/api/generation-path-history", json={"path": str(second)})
    assert post_resp.status_code == 200
    assert post_resp.get_json()["paths"][:2] == [str(second), str(first)]
    stored = json.loads(config_path.read_text(encoding="utf-8"))
    assert stored["generation_path_history"][:2] == [str(second), str(first)]
    assert str(failed) not in post_resp.get_json()["paths"]


def test_v061_provider_field_history_merges_config_providers_and_successful_generation(tmp_path):
    client = make_client(tmp_path)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["provider_field_history"] = {
        "api_key_env": ["SHARED_KEY"],
        "model": ["shared-model"],
        "user_agent": ["Shared-UA"],
        "api_key": ["must-not-return"],
    }
    settings["providers"]["aiapis_gpt_image_2"].update(
        {
            "api_key_env": "IMG_API_KEY",
            "model": "gpt-image-2-standard",
            "user_agent": "Provider-UA",
            "api_key": "secret-key",
        }
    )
    settings["providers"]["provider_b"] = {
        "display_name": "Provider B",
        "adapter": "openai",
        "base_url": "https://example.test/v1",
        "api_key_env": "B_KEY",
        "model": "model-b",
        "user_agent": "UA-B",
    }
    client.put("/api/settings", json=settings)

    resp = client.get("/api/provider-field-history")

    assert resp.status_code == 200
    payload = resp.get_json()["history"]
    assert payload["api_key_env"][:3] == ["SHARED_KEY", "IMG_API_KEY", "B_KEY"]
    assert payload["model"][:3] == ["shared-model", "gpt-image-2-standard", "model-b"]
    assert payload["user_agent"][:3] == ["Shared-UA", "Provider-UA", "UA-B"]
    assert "api_key" not in payload
    assert "secret-key" not in json.dumps(payload, ensure_ascii=False)


def test_v061_successful_generation_records_provider_field_history(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "success.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"].update(
        {
            "api_key_env": "SUCCESS_KEY",
            "model": "success-model",
            "user_agent": "Success-UA",
            "api_key": "secret-success",
        }
    )
    client.put("/api/settings", json=settings)

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result([output_image]),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "记录历史",
                "mode": "text_to_image",
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
            },
        )

    assert resp.status_code == 201
    stored = json.loads(Path(client.application.config["CONFIG_FILE"]).read_text(encoding="utf-8"))
    history = stored["provider_field_history"]
    assert history["api_key_env"][0] == "SUCCESS_KEY"
    assert history["model"][0] == "success-model"
    assert history["user_agent"][0] == "Success-UA"
    assert "api_key" not in history
    assert "secret-success" not in json.dumps(history, ensure_ascii=False)


def test_v058_generate_openai_google_defaults_to_shared_image_script(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    input_one = tmp_path / "input-one.png"
    input_two = tmp_path / "input-two.png"
    output_file = output_dir / "google-image.png"
    shared_script = tmp_path / "google_b2_image_to_image_xiaoyun.py"
    input_one.write_bytes(b"one")
    input_two.write_bytes(b"two")
    shared_script.write_text("# openai-google image sentinel", encoding="utf-8")
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    provider = settings["providers"]["aiapis_gpt_image_2"]
    provider["adapter"] = "openai-google"
    provider["custom_scripts"] = {}
    client.put("/api/settings", json=settings)

    def fake_run_custom_script(script, context, timeout_seconds=None):
        assert script == "# openai-google image sentinel"
        assert context["mode"] == "image_to_image"
        assert context["input_images"] == [str(input_one), str(input_two)]
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"image")
        return ImageGenerationResult(output_path=str(output_file), provider="shared_script")

    with (
        patch("backend.api.default_shared_script_for_generation", return_value=shared_script),
        patch("backend.api.run_custom_script", side_effect=fake_run_custom_script) as run_script,
        patch("backend.api.generate_image") as generate_image,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "在图1和图2上添加10只鱼",
                "mode": "image_to_image",
                "input_image_paths": [str(input_one), str(input_two)],
                "tags": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 3},
            },
        )

    assert resp.status_code == 201
    run_script.assert_called_once()
    generate_image.assert_not_called()
    payload = resp.get_json()
    assert payload["output_image_paths"] == [str(output_file)]
    assert payload["item"]["input_image_paths"] == [str(input_one), str(input_two)]


def test_v071_new_adapters_route_to_expected_shared_scripts_and_context(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    input_one = tmp_path / "input-one.png"
    input_two = tmp_path / "input-two.png"
    input_one.write_bytes(b"one")
    input_two.write_bytes(b"two")
    sysrv_output = output_dir / "sysrv.png"
    apimart_output = output_dir / "apimart.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    provider = settings["providers"]["aiapis_gpt_image_2"]
    provider.update(
        {
            "adapter": "sysrv-google",
            "base_url": "https://sysrv.example",
            "api_key": "sysrv-key",
            "model": "gemini-image",
            "google_role": "user",
            "request_timeout_seconds": 222,
            "download_timeout_seconds": 111,
            "max_retry_attempts": 4,
            "custom_scripts": {},
        }
    )
    client.put("/api/settings", json=settings)

    def fake_sysrv_script(script, context, timeout_seconds=None):
        assert "generateContent" in script
        assert "google_b2_text_to_image_sysrv" in script or "responseModalities" in script
        assert context["mode"] == "text_to_image"
        assert context["operation_prompt"] == "sysrv 文生图"
        assert context["input_images"] == []
        assert context["base_url"] == "https://sysrv.example"
        assert context["api_key"] == "sysrv-key"
        assert context["model"] == "gemini-image"
        assert context["resolved_size"] == ""
        assert context["request_timeout_seconds"] == 222
        assert context["download_timeout_seconds"] == 111
        assert context["max_retry_attempts"] == 4
        assert context["n"] == 1
        assert context["google_role"] == "user"
        sysrv_output.parent.mkdir(parents=True, exist_ok=True)
        sysrv_output.write_bytes(b"image")
        return ImageGenerationResult(output_path=str(sysrv_output), provider="shared_script")

    with (
        patch("backend.api.run_custom_script", side_effect=fake_sysrv_script) as run_script,
        patch("backend.api.generate_image") as generate_image,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "sysrv 文生图",
                "mode": "text_to_image",
                "input_image_paths": [],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 2},
            },
        )

    assert resp.status_code == 201
    run_script.assert_called_once()
    generate_image.assert_not_called()
    payload = resp.get_json()
    assert payload["output_image_paths"] == [str(sysrv_output)]
    assert payload["item"]["generation_params"]["adapter"] == "sysrv-google"
    assert payload["item"]["generation_params"]["resolved_size"] == ""
    assert payload["item"]["generation_params"]["n"] == 1
    assert len(payload["items"]) == 1

    settings = client.get("/api/settings").get_json()["settings"]
    provider = settings["providers"]["aiapis_gpt_image_2"]
    provider.update(
        {
            "adapter": "apimart-openai",
            "base_url": "https://api.apimart.ai",
            "api_key": "apimart-key",
            "model": "gpt-image-2",
            "quality": "high",
            "output_format": "webp",
            "output_compression": 72,
            "background": "auto",
            "input_fidelity": "high",
            "mask_path": "",
            "apimart_task_timeout_seconds": 333,
            "apimart_task_poll_interval_seconds": 8,
            "request_timeout_seconds": 240,
            "download_timeout_seconds": 80,
            "max_retry_attempts": 5,
            "custom_scripts": {},
        }
    )
    client.put("/api/settings", json=settings)

    def fake_apimart_script(script, context, timeout_seconds=None):
        assert "APIMart" in script
        assert context["mode"] == "image_to_image"
        assert context["operation_prompt"] == "apimart 图生图"
        assert context["input_images"] == [str(input_one), str(input_two)]
        assert context["base_url"] == "https://api.apimart.ai/v1"
        assert context["api_key"] == "apimart-key"
        assert context["model"] == "gpt-image-2"
        assert context["resolved_size"] == "1024x1024"
        assert context["n"] == 3
        assert context["output_format"] == "webp"
        assert context["output_compression"] == 72
        assert context["input_fidelity"] == "high"
        assert context["mask_path"] == ""
        assert context["apimart_task_timeout_seconds"] == 333
        assert context["apimart_task_poll_interval_seconds"] == 8
        assert context["request_timeout_seconds"] == 240
        assert context["download_timeout_seconds"] == 80
        assert context["max_retry_attempts"] == 5
        apimart_output.parent.mkdir(parents=True, exist_ok=True)
        apimart_output.write_bytes(b"image")
        return ImageGenerationResult(output_paths=[str(apimart_output)], provider="shared_script")

    with (
        patch("backend.api.run_custom_script", side_effect=fake_apimart_script) as run_script,
        patch("backend.api.generate_image") as generate_image,
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "apimart 图生图",
                "mode": "image_to_image",
                "input_image_paths": [str(input_one), str(input_two)],
                "options": {"ratio": "1:1", "resolution_level": "1K", "n": 3},
            },
        )

    assert resp.status_code == 201
    run_script.assert_called_once()
    generate_image.assert_not_called()
    payload = resp.get_json()
    assert payload["output_image_paths"] == [str(apimart_output)]
    assert payload["item"]["generation_params"]["adapter"] == "apimart-openai"
    assert payload["item"]["generation_params"]["resolved_size"] == "1024x1024"
    assert payload["item"]["generation_params"]["apimart_task_timeout_seconds"] == 333


def test_generate_openai_gpt_image_2_executes_shared_text_script_against_http_api(tmp_path, monkeypatch):
    server, requests = run_mock_openai_server()
    try:
        monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
        monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
        client = make_client(tmp_path)
        output_dir = tmp_path / "generated"
        settings = client.get("/api/settings").get_json()["settings"]
        settings["default_output_dir"] = str(output_dir)
        provider = settings["providers"]["aiapis_gpt_image_2"]
        provider["adapter"] = "openai"
        provider["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
        provider["api_key"] = "test-key"
        provider["api_key_env"] = ""
        provider["openai_call_method"] = "gpt-image-2"
        provider["output_format"] = "png"
        provider["user_agent"] = "Mozilla/5.0 PowerShell/7.4"
        provider["custom_scripts"] = {}
        client.put("/api/settings", json=settings)

        with patch("backend.api.generate_image") as generate_image:
            resp = client.post(
                "/api/generate",
                json={
                    "prompt": "脚本真实执行",
                    "mode": "text_to_image",
                    "input_image_paths": [],
                    "tags": [],
                    "options": {"ratio": "1:1", "resolution_level": "1K", "n": 2},
                },
            )

        assert resp.status_code == 201
        generate_image.assert_not_called()
        payload = resp.get_json()
        assert len(payload["output_image_paths"]) == 2
        assert [Path(path).read_bytes() for path in payload["output_image_paths"]] == [
            b"mock-image",
            b"mock-image",
        ]
        assert [item["generation_params"]["shared_script_used"] for item in payload["items"]] == [True, True]
        assert requests
        assert requests[-1]["path"] == "/v1/images/generations"
        assert requests[-1]["user_agent"] == "Mozilla/5.0 PowerShell/7.4"
        request_payload = json.loads(requests[-1]["body"])
        assert request_payload["prompt"] == "脚本真实执行"
        assert request_payload["n"] == 2
        assert request_payload["size"] == "1024x1024"
        assert "output_compression" not in request_payload
    finally:
        server.shutdown()
        server.server_close()


def test_generate_openai_gpt_image_2_executes_shared_image_script_against_http_api(tmp_path, monkeypatch):
    server, requests = run_mock_openai_server()
    try:
        monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
        monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
        client = make_client(tmp_path)
        output_dir = tmp_path / "generated"
        input_one = tmp_path / "input-one.png"
        input_two = tmp_path / "input-two.png"
        input_one.write_bytes(b"one")
        input_two.write_bytes(b"two")
        settings = client.get("/api/settings").get_json()["settings"]
        settings["default_output_dir"] = str(output_dir)
        provider = settings["providers"]["aiapis_gpt_image_2"]
        provider["adapter"] = "openai"
        provider["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
        provider["api_key"] = "test-key"
        provider["api_key_env"] = ""
        provider["openai_call_method"] = "gpt-image-2"
        provider["output_format"] = "png"
        provider["user_agent"] = "Mozilla/5.0 PowerShell/7.4"
        provider["custom_scripts"] = {}
        client.put("/api/settings", json=settings)

        with patch("backend.api.generate_image") as generate_image:
            resp = client.post(
                "/api/generate",
                json={
                    "prompt": "两张参考图真实执行",
                    "mode": "image_to_image",
                    "input_image_paths": [str(input_one), str(input_two)],
                    "tags": [],
                    "options": {"ratio": "1:1", "resolution_level": "1K", "n": 4},
                },
            )

        assert resp.status_code == 201
        generate_image.assert_not_called()
        payload = resp.get_json()
        assert len(payload["output_image_paths"]) == 1
        assert Path(payload["output_image_paths"][0]).read_bytes() == b"mock-image"
        assert payload["item"]["generation_params"]["shared_script_used"] is True
        assert payload["item"]["input_image_paths"] == [str(input_one), str(input_two)]
        assert requests
        assert requests[-1]["path"] == "/v1/images/edits"
        assert requests[-1]["user_agent"] == "Mozilla/5.0 PowerShell/7.4"
        assert requests[-1]["content_type"].startswith("multipart/form-data")
        assert "两张参考图真实执行" in requests[-1]["body"]
        assert "input-one.png" in requests[-1]["body"]
        assert "input-two.png" in requests[-1]["body"]
    finally:
        server.shutdown()
        server.server_close()


def test_generate_custom_script_rejects_invalid_output_but_preserves_precreated_instances(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    outside = tmp_path / "outside.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"]["custom_scripts"] = {
        "gpt-image-2": {
            "text_to_image": f"""
from pathlib import Path
import json
Path(output_path).write_bytes(b"one")
Path({str(outside)!r}).write_bytes(b"bad")
Path(result_json_path).write_text(
    json.dumps({{"output_paths": [{str(outside)!r}]}}),
    encoding="utf-8",
)
"""
        }
    }
    client.put("/api/settings", json=settings)

    resp = client.post(
        "/api/generate",
        json={
            "prompt": "产品海报",
            "mode": "text_to_image",
            "input_image_paths": [],
            "tags": [],
            "options": {"ratio": "1:1", "resolution_level": "1K", "n": 2},
        },
    )

    assert resp.status_code == 400
    assert "输出路径必须位于生成路径内" in resp.get_json()["error"]
    instances = client.get("/api/instances").get_json()
    assert instances["total"] == 2
    assert [item["output_image_path"] for item in instances["items"]] == ["", ""]


def test_generate_google_adapter_returns_not_implemented_without_instance(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"]["adapter"] = "google"
    client.put("/api/settings", json=settings)

    resp = client.post(
        "/api/generate",
        json={
            "prompt": "产品海报",
            "mode": "text_to_image",
            "input_image_paths": [],
            "tags": [],
            "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Google adapter 暂未实现。"
    assert client.get("/api/instances").get_json()["total"] == 0


def test_generate_other_adapter_returns_not_implemented_without_instance(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["providers"]["aiapis_gpt_image_2"]["adapter"] = "other"
    client.put("/api/settings", json=settings)

    resp = client.post(
        "/api/generate",
        json={
            "prompt": "产品海报",
            "mode": "text_to_image",
            "input_image_paths": [],
            "tags": [],
            "options": {"ratio": "1:1", "resolution_level": "1K", "n": 1},
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Other adapter 暂未实现。"
    assert client.get("/api/instances").get_json()["total"] == 0


def test_generate_uses_global_default_size_when_options_omit_size(tmp_path):
    client = make_client(tmp_path)
    output_dir = tmp_path / "generated"
    output_image = output_dir / "fake.png"
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(output_dir)
    settings["default_aspect_ratio"] = "3:4"
    settings["default_resolution"] = "2K"
    settings["default_clarity"] = "2K"
    client.put("/api/settings", json=settings)

    def assert_context(context):
        assert context["resolved_size"] == "1536x2048"

    with patch(
        "backend.api.run_custom_script",
        side_effect=fake_shared_script_result([output_image], assert_context=assert_context),
    ):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
            },
        )

    assert resp.status_code == 201
    assert resp.get_json()["item"]["generation_size"] == "1536x2048"


def test_generate_rejects_invalid_size_without_calling_provider(tmp_path):
    client = make_client(tmp_path)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(tmp_path / "generated")
    client.put("/api/settings", json=settings)

    with patch("backend.api.generate_image") as generate:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {"size": "1024 x 1024"},
            },
        )

    assert resp.status_code == 400
    assert "尺寸格式" in resp.get_json()["error"]
    generate.assert_not_called()


def test_settings_page_payload_preserves_existing_global_default_size(tmp_path):
    config_file = tmp_path / "config.json"
    app = create_app(db_file=tmp_path / "test.sqlite", config_file=config_file)
    app.config.update(TESTING=True)
    client = app.test_client()

    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_size"] = "768x1024"
    settings["default_resolution"] = "4K"
    client.put("/api/settings", json=settings)

    settings_page_payload = client.get("/api/settings").get_json()["settings"]
    settings_page_payload.pop("default_size", None)
    settings_page_payload.pop("default_resolution", None)
    settings_page_payload["providers"]["aiapis_gpt_image_2"].pop("default_size", None)
    settings_page_payload["default_output_dir"] = "D:\\AIOutput"

    resp = client.put("/api/settings", json=settings_page_payload)

    stored = json.loads(config_file.read_text(encoding="utf-8"))
    assert resp.status_code == 200
    assert resp.get_json()["settings"]["default_size"] == "768x1024"
    assert resp.get_json()["settings"]["default_resolution"] == "4K"
    assert stored["default_size"] == "768x1024"
    assert stored["default_resolution"] == "4K"
    assert "default_size" not in stored["providers"]["aiapis_gpt_image_2"]


def test_generate_rejects_empty_resolution_without_calling_provider(tmp_path):
    client = make_client(tmp_path)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(tmp_path / "generated")
    client.put("/api/settings", json=settings)

    with patch("backend.api.generate_image") as generate:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {"resolution_level": "   "},
            },
        )

    assert resp.status_code == 400
    assert "清晰度" in resp.get_json()["error"]
    generate.assert_not_called()


def test_generate_rejects_invalid_count_without_calling_provider(tmp_path):
    client = make_client(tmp_path)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(tmp_path / "generated")
    client.put("/api/settings", json=settings)

    with patch("backend.api.generate_image") as generate:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
                "options": {"count": 0},
            },
        )

    assert resp.status_code == 400
    assert "生成数量必须是正整数" in resp.get_json()["error"]
    generate.assert_not_called()


def test_tags_endpoint_returns_used_tags_sorted(tmp_path):
    client = make_client(tmp_path)
    first = client.post(
        "/api/instances",
        json={"prompt": "角色海报", "tags": ["角色", "海报"]},
    ).get_json()["item"]
    unused = client.post(
        "/api/instances",
        json={"prompt": "临时", "tags": ["临时"]},
    ).get_json()["item"]
    client.delete(f"/api/instances/{unused['id']}")

    resp = client.get("/api/tags")

    assert resp.status_code == 200
    assert resp.get_json() == {"items": ["海报", "角色"]}


def test_generate_validation_error_returns_400_and_does_not_create_instance(tmp_path):
    client = make_client(tmp_path)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(tmp_path / "generated")
    client.put("/api/settings", json=settings)

    with patch("backend.api.generate_image", side_effect=ValueError("提示词不能为空")):
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "   ",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": ["产品"],
            },
        )

    assert resp.status_code == 400
    assert "提示词不能为空" in resp.get_json()["error"]
    list_resp = client.get("/api/instances")
    assert list_resp.get_json()["total"] == 0
    history = client.get("/api/generation-history").get_json()
    assert history["total"] == 1
    assert history["items"][0]["status"] == "failed"
    assert "提示词不能为空" in history["items"][0]["error_message"]


def test_generate_rejects_missing_output_dir_without_creating_instance(tmp_path):
    client = make_client(tmp_path)

    with patch("backend.api.generate_image") as generate:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
            },
        )

    assert resp.status_code == 400
    assert "输出目录不能为空" in resp.get_json()["error"]
    generate.assert_not_called()
    list_resp = client.get("/api/instances")
    assert list_resp.get_json()["total"] == 0
    history = client.get("/api/generation-history").get_json()
    assert history["total"] == 1
    assert history["items"][0]["status"] == "failed"
    assert "输出目录不能为空" in history["items"][0]["error_message"]


def test_generate_empty_prompt_takes_priority_over_missing_output_dir(tmp_path):
    client = make_client(tmp_path)

    with patch("backend.api.generate_image") as generate:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "   ",
                "mode": "text_to_image",
                "input_image_paths": [],
                "tags": [],
            },
        )

    assert resp.status_code == 400
    assert "提示词不能为空" in resp.get_json()["error"]
    generate.assert_not_called()
    list_resp = client.get("/api/instances")
    assert list_resp.get_json()["total"] == 0


def test_generate_image_to_image_requires_input_before_output_dir(tmp_path):
    client = make_client(tmp_path)

    with patch("backend.api.generate_image") as generate:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "image_to_image",
                "input_image_paths": [],
                "tags": [],
            },
        )

    assert resp.status_code == 400
    assert "图生图需要至少 1 张输入图" in resp.get_json()["error"]
    generate.assert_not_called()
    list_resp = client.get("/api/instances")
    assert list_resp.get_json()["total"] == 0


def test_generate_rejects_missing_image_to_image_input_path(tmp_path):
    client = make_client(tmp_path)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(tmp_path / "generated")
    client.put("/api/settings", json=settings)

    with patch("backend.api.generate_image") as generate:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "image_to_image",
                "input_image_paths": [str(tmp_path / "missing.png")],
                "tags": [],
            },
        )

    assert resp.status_code == 400
    assert "输入图片不存在" in resp.get_json()["error"]
    generate.assert_not_called()
    list_resp = client.get("/api/instances")
    assert list_resp.get_json()["total"] == 0


def test_generate_rejects_non_list_input_image_paths(tmp_path):
    client = make_client(tmp_path)
    settings = client.get("/api/settings").get_json()["settings"]
    settings["default_output_dir"] = str(tmp_path / "generated")
    client.put("/api/settings", json=settings)

    with patch("backend.api.generate_image") as generate:
        resp = client.post(
            "/api/generate",
            json={
                "prompt": "产品海报",
                "mode": "image_to_image",
                "input_image_paths": "C:\\in\\one.png",
                "tags": [],
            },
        )

    assert resp.status_code == 400
    assert "输入图片路径必须是列表" in resp.get_json()["error"]
    generate.assert_not_called()
    list_resp = client.get("/api/instances")
    assert list_resp.get_json()["total"] == 0


def test_v027_instances_endpoint_supports_untagged_and_mode_filter(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/instances", json={"prompt": "文生图无标签", "tags": []})
    client.post(
        "/api/instances",
        json={
            "prompt": "图生图有输出",
            "input_image_paths": ["D:\\in\\one.png"],
            "output_image_path": "D:\\out\\one.png",
            "tags": ["参考"],
        },
    )
    client.post(
        "/api/instances",
        json={"prompt": "文生图有输出", "output_image_path": "D:\\out\\two.png"},
    )

    untagged = client.get("/api/instances?tags=__untagged__&sort=created_asc")
    image_to_image = client.get("/api/instances?mode_filter=image_to_image")
    has_output = client.get("/api/instances?mode_filter=has_output")

    assert untagged.status_code == 200
    assert [item["prompt"] for item in untagged.get_json()["items"]] == [
        "文生图无标签",
        "文生图有输出",
    ]
    assert image_to_image.get_json()["total"] == 1
    assert image_to_image.get_json()["items"][0]["prompt"] == "图生图有输出"
    assert has_output.get_json()["total"] == 2


def test_v027_batch_tag_and_delete_endpoints_do_not_delete_files(tmp_path):
    client = make_client(tmp_path)
    input_file = tmp_path / "input.png"
    output_file = tmp_path / "output.png"
    input_file.write_bytes(b"input")
    output_file.write_bytes(b"output")
    first = client.post(
        "/api/instances",
        json={
            "prompt": "第一条",
            "input_image_paths": [str(input_file)],
            "output_image_path": str(output_file),
            "tags": ["产品"],
        },
    ).get_json()["item"]
    second = client.post(
        "/api/instances",
        json={"prompt": "第二条", "tags": ["参考"]},
    ).get_json()["item"]
    ids = [first["id"], second["id"]]

    add_resp = client.post(
        "/api/instances/batch/tags/add",
        json={"ids": ids, "tags": ["精选", "产品"]},
    )
    remove_resp = client.post(
        "/api/instances/batch/tags/remove",
        json={"ids": ids, "tags": ["参考"]},
    )
    delete_resp = client.post("/api/instances/batch/delete", json={"ids": ids})

    assert add_resp.status_code == 200
    assert add_resp.get_json() == {"updated": 2}
    assert remove_resp.status_code == 200
    assert remove_resp.get_json() == {"updated": 1}
    assert delete_resp.status_code == 200
    assert delete_resp.get_json() == {"deleted": 2}
    assert client.get("/api/instances").get_json()["total"] == 0
    assert input_file.exists()
    assert output_file.exists()




