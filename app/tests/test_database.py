import sys
import sqlite3
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.database as database
from backend.database import (
    add_instance_tags,
    batch_add_tags,
    batch_delete_instances,
    batch_move_instances,
    batch_remove_tags,
    clear_instance_tags,
    create_generation_history,
    create_instance,
    create_node,
    delete_node,
    delete_instance,
    finish_generation_history,
    get_connection,
    get_instance,
    init_db,
    list_generation_history,
    list_instances,
    list_nodes,
    move_instance_to_node,
    remove_instance_tags,
    reorder_nodes,
    schema_version,
    prepare_instance_for_generation,
    update_instance_generation_status,
    update_instance,
    update_instance_output_image,
)


def make_db(tmp_path: Path):
    db_path = tmp_path / "app.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    return conn


def create_test_instance(
    conn,
    prompt: str,
    *,
    tags: list[str] | None = None,
    input_image_paths: list[str] | None = None,
    output_image_path: str = "",
    source: str = "manual",
    node_id: int | None = None,
    generation_status: str = "ready",
):
    return create_instance(
        conn,
        {
            "prompt": prompt,
            "mode": "unspecified",
            "source": source,
            "provider": None,
            "generation_path": "",
            "output_image_path": output_image_path,
            "input_image_paths": input_image_paths or [],
            "tags": tags or [],
            "node_id": node_id,
            "generation_status": generation_status,
        },
    )


def test_connection_uses_busy_timeout_and_wal_for_parallel_generation(tmp_path):
    conn = make_db(tmp_path)

    busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

    assert busy_timeout == 30000
    assert journal_mode.lower() == "wal"


def test_init_db_records_schema_version_metadata(tmp_path):
    conn = make_db(tmp_path)

    assert schema_version(conn) == 5
    metadata = {
        row["key"]: row["value"]
        for row in conn.execute("SELECT key, value FROM app_metadata")
    }
    assert metadata["schema_version"] == "5"
    assert metadata["app_version"] == "V0.67"
    assert metadata["last_migration_at"]


def test_v029_schema_adds_nodes_and_instance_node_id(tmp_path):
    conn = make_db(tmp_path)

    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    instance_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(instances)")
    }
    indexes = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    }

    assert "nodes" in tables
    assert "node_id" in instance_columns
    assert "idx_nodes_parent_position" in indexes
    assert "idx_instances_node_id" in indexes


def test_create_and_get_manual_instance(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "极简产品海报",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": ["C:\\in\\a.png", "C:\\in\\b.png"],
            "tags": ["产品", "海报"],
        },
    )

    item = get_instance(conn, instance_id)

    assert item["prompt"] == "极简产品海报"
    assert item["output_image_path"] == ""
    assert item["generation_status"] == "ready"
    assert item["generation_task_id"] == ""
    assert item["generation_output_index"] == 1
    assert item["generation_error"] == ""
    assert item["generation_size"] == ""
    assert item["input_image_paths"] == ["C:\\in\\a.png", "C:\\in\\b.png"]
    assert item["tags"] == ["产品", "海报"]


def test_update_instance_output_image_only_updates_output_path(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "预创建实例",
            "mode": "text_to_image",
            "source": "generated",
            "provider": "aiapis_gpt_image_2",
            "generation_path": "D:\\out",
            "generation_size": "1024x1024",
            "generation_params": {"n": 2},
            "output_image_path": "",
            "input_image_paths": ["C:\\in\\one.png"],
            "tags": ["安全"],
        },
    )

    update_instance_output_image(conn, instance_id, "D:\\out\\one.png")

    item = get_instance(conn, instance_id)
    assert item["prompt"] == "预创建实例"
    assert item["output_image_path"] == "D:\\out\\one.png"
    assert item["input_image_paths"] == ["C:\\in\\one.png"]
    assert item["tags"] == ["安全"]
    assert item["generation_params"]["n"] == 2


def test_init_db_adds_generation_size_to_legacy_database(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE instances (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          prompt TEXT NOT NULL,
          mode TEXT NOT NULL,
          source TEXT NOT NULL,
          provider TEXT,
          generation_path TEXT NOT NULL DEFAULT '',
          output_image_path TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    conn = get_connection(db_path)
    init_db(conn)

    columns = [row["name"] for row in conn.execute("PRAGMA table_info(instances)")]
    assert "generation_size" in columns
    assert "generation_params_json" in columns
    assert "generation_status" in columns
    assert "generation_task_id" in columns
    assert "generation_output_index" in columns
    assert "generation_error" in columns
    assert "generation_started_at" in columns
    assert "generation_finished_at" in columns


def test_update_instance_generation_status_marks_running_failed_and_ready(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "生成中",
            "mode": "text_to_image",
            "source": "generated",
            "provider": "aiapis_gpt_image_2",
            "generation_path": "D:\\out",
            "generation_size": "1024x1024",
            "generation_params": {"n": 1},
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["过程"],
            "generation_status": "running",
            "generation_task_id": "task-1",
            "generation_output_index": 1,
            "generation_started_at": "2026-05-06T12:00:00",
        },
    )

    running = get_instance(conn, instance_id)
    assert running["generation_status"] == "running"
    assert running["generation_task_id"] == "task-1"
    assert running["generation_output_index"] == 1

    update_instance_generation_status(
        conn,
        instance_id,
        "failed",
        error="provider down",
        finished_at="2026-05-06T12:00:05",
    )
    failed = get_instance(conn, instance_id)
    assert failed["generation_status"] == "failed"
    assert failed["generation_error"] == "provider down"
    assert failed["generation_finished_at"] == "2026-05-06T12:00:05"

    update_instance_output_image(conn, instance_id, "D:\\out\\one.png")
    ready = get_instance(conn, instance_id)
    assert ready["generation_status"] == "ready"
    assert ready["generation_error"] == ""
    assert ready["output_image_path"] == "D:\\out\\one.png"


def test_v063_prepare_existing_instance_for_generation_preserves_created_at(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "准备态",
            "mode": "text_to_image",
            "source": "manual",
            "provider": "aiapis_gpt_image_2",
            "generation_path": "D:\\out",
            "generation_size": "1024x1024",
            "generation_params": {"n": 1},
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["草稿"],
        },
    )
    conn.execute(
        "UPDATE instances SET created_at = ?, updated_at = ? WHERE id = ?",
        ("2026-05-01T08:00:00", "2026-05-01T08:00:00", instance_id),
    )
    conn.commit()

    prepare_instance_for_generation(
        conn,
        instance_id,
        {
            "prompt": "准备态提交",
            "mode": "text_to_image",
            "source": "generated",
            "provider": "aiapis_gpt_image_2",
            "generation_path": "D:\\out",
            "generation_size": "1024x1024",
            "generation_params": {"n": 3},
            "input_image_paths": [],
            "tags": ["提交"],
        },
        task_id="task-v063",
        output_index=1,
        started_at="2026-05-24T13:00:00",
    )

    item = get_instance(conn, instance_id)
    assert item["created_at"] == "2026-05-01T08:00:00"
    assert item["updated_at"] == "2026-05-24T13:00:00"
    assert item["generation_started_at"] == "2026-05-24T13:00:00"
    assert item["generation_status"] == "running"
    assert item["generation_task_id"] == "task-v063"


def test_single_instance_tag_helpers_ignore_untagged_and_preserve_other_fields(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
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

    assert add_instance_tags(conn, instance_id, ["新", "__untagged__", "新"]) == 1
    item = get_instance(conn, instance_id)
    assert item["prompt"] == "标签即时操作"
    assert item["output_image_path"] == "C:\\out\\one.png"
    assert item["input_image_paths"] == ["C:\\in\\one.png"]
    assert item["tags"] == ["旧", "新"]

    assert remove_instance_tags(conn, instance_id, ["旧", "__untagged__"]) == 1
    assert get_instance(conn, instance_id)["tags"] == ["新"]


def test_v029_clear_instance_tags_removes_only_current_instance_links(tmp_path):
    conn = make_db(tmp_path)
    first_id = create_test_instance(conn, "第一条", tags=["常用", "保留"])
    second_id = create_test_instance(conn, "第二条", tags=["常用"])

    assert clear_instance_tags(conn, first_id) == 2

    assert get_instance(conn, first_id)["tags"] == []
    assert get_instance(conn, second_id)["tags"] == ["常用"]
    assert database.list_tags(conn) == ["常用"]


def test_generated_instance_saves_generation_size(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "生成海报",
            "mode": "text_to_image",
            "source": "generated",
            "provider": "aiapis_gpt_image_2",
            "generation_path": "D:\\out",
            "generation_size": "768x1024",
            "generation_params": {
                "provider_key": "aiapis_gpt_image_2",
                "adapter": "openai",
                "model": "gpt-image-2",
                "ratio": "3:4",
                "resolution_level": "1K",
                "resolved_size": "768x1024",
                "quality": "high",
                "output_format": "png",
                "background": "auto",
                "moderation": "low",
                "n": 1,
            },
            "output_image_path": "D:\\out\\one.png",
            "input_image_paths": [],
            "tags": [],
        },
    )

    item = get_instance(conn, instance_id)

    assert item["generation_size"] == "768x1024"
    assert item["generation_params"]["adapter"] == "openai"
    assert item["generation_params"]["resolved_size"] == "768x1024"


def test_manual_instance_has_empty_generation_params(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "手动收藏",
            "mode": "unspecified",
            "source": "manual",
            "provider": "",
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": [],
        },
    )

    item = get_instance(conn, instance_id)

    assert item["generation_params"] == {}


def test_update_instance_preserves_generation_size(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "old",
            "mode": "text_to_image",
            "source": "generated",
            "provider": "aiapis_gpt_image_2",
            "generation_path": "D:\\out",
            "generation_size": "1024x768",
            "generation_params": {
                "provider_key": "aiapis_gpt_image_2",
                "adapter": "openai",
                "resolved_size": "1024x768",
            },
            "output_image_path": "D:\\out\\one.png",
            "input_image_paths": [],
            "tags": ["旧"],
        },
    )

    update_instance(
        conn,
        instance_id,
        {
            "prompt": "new",
            "mode": "text_to_image",
            "source": "generated",
            "provider": "aiapis_gpt_image_2",
            "generation_path": "D:\\out",
            "output_image_path": "D:\\out\\two.png",
            "input_image_paths": [],
            "tags": ["新"],
        },
    )

    item = get_instance(conn, instance_id)
    assert item["generation_size"] == "1024x768"
    assert item["generation_params"]["adapter"] == "openai"
    assert item["generation_params"]["resolved_size"] == "1024x768"


def test_init_db_adds_generation_params_json_to_existing_generation_size_database(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE instances (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          prompt TEXT NOT NULL,
          mode TEXT NOT NULL,
          source TEXT NOT NULL,
          provider TEXT,
          generation_path TEXT NOT NULL DEFAULT '',
          generation_size TEXT NOT NULL DEFAULT '',
          output_image_path TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    conn = get_connection(db_path)
    init_db(conn)

    columns = [row["name"] for row in conn.execute("PRAGMA table_info(instances)")]
    assert "generation_params_json" in columns


def test_create_instance_stores_generation_params_as_json(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "生成海报",
            "mode": "text_to_image",
            "source": "generated",
            "provider": "aiapis_gpt_image_2",
            "generation_path": "D:\\out",
            "generation_size": "3840x2160",
            "generation_params": {
                "provider_key": "aiapis_gpt_image_2",
                "adapter": "openai",
                "ratio": "16:9",
                "resolution_level": "4K",
                "resolved_size": "3840x2160",
                "n": 2,
            },
            "output_image_path": "D:\\out\\one.png",
            "input_image_paths": [],
            "tags": [],
        },
    )

    row = conn.execute(
        "SELECT generation_params_json FROM instances WHERE id = ?",
        (instance_id,),
    ).fetchone()

    assert json.loads(row["generation_params_json"])["ratio"] == "16:9"
    assert get_instance(conn, instance_id)["generation_params"]["n"] == 2


def test_update_instance_replaces_images_and_tags(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "old",
            "mode": "unspecified",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["旧"],
        },
    )

    update_instance(
        conn,
        instance_id,
        {
            "prompt": "new prompt",
            "mode": "image_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "C:\\out\\one.png",
            "input_image_paths": ["C:\\in\\one.png"],
            "tags": ["新", "参考"],
        },
    )

    item = get_instance(conn, instance_id)
    assert item["prompt"] == "new prompt"
    assert item["output_image_path"] == "C:\\out\\one.png"
    assert item["input_image_paths"] == ["C:\\in\\one.png"]
    assert item["tags"] == ["新", "参考"]


def test_manual_instance_provider_accepts_arbitrary_text_and_can_be_cleared(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "外部收藏",
            "mode": "unspecified",
            "source": "manual",
            "provider": "朋友分享渠道",
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": [],
        },
    )

    assert get_instance(conn, instance_id)["provider"] == "朋友分享渠道"

    update_instance(
        conn,
        instance_id,
        {
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

    assert get_instance(conn, instance_id)["provider"] == ""


def test_list_filters_by_prompt_and_tags_with_and_logic(tmp_path):
    conn = make_db(tmp_path)
    create_instance(
        conn,
        {
            "prompt": "产品海报",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["产品", "海报"],
        },
    )
    create_instance(
        conn,
        {
            "prompt": "产品摄影",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["产品"],
        },
    )

    result = list_instances(
        conn,
        {
            "q": "产品",
            "tags": ["产品", "海报"],
            "source": "all",
            "sort": "created_desc",
            "page": 1,
            "per_page": 50,
        },
    )

    assert result["total"] == 1
    assert result["items"][0]["prompt"] == "产品海报"
    assert result["items"][0]["display_index"] == 1


def test_v067_instances_get_fixed_numbers_and_sort_without_renumbering(tmp_path):
    conn = make_db(tmp_path)
    first_id = create_instance(conn, {"prompt": "first"})
    second_id = create_instance(conn, {"prompt": "second"})
    third_id = create_instance(conn, {"prompt": "third"})

    created_desc = list_instances(conn, {"sort": "created_desc", "page": 1, "per_page": 50})["items"]
    assert [item["instance_number"] for item in created_desc] == [3, 2, 1]
    assert [item["instance_number_label"] for item in created_desc] == ["#0003", "#0002", "#0001"]

    delete_instance(conn, second_id)
    fourth_id = create_instance(conn, {"prompt": "fourth"})
    number_asc = list_instances(conn, {"sort": "number_asc", "page": 1, "per_page": 50})["items"]
    assert [item["id"] for item in number_asc] == [first_id, third_id, fourth_id]
    assert [item["instance_number"] for item in number_asc] == [1, 3, 4]

    number_desc = list_instances(conn, {"sort": "number_desc", "page": 1, "per_page": 50})["items"]
    assert [item["instance_number"] for item in number_desc] == [4, 3, 1]


def test_v067_old_database_migrates_instance_numbers_by_created_order(tmp_path):
    db_path = tmp_path / "old.sqlite"
    raw = sqlite3.connect(db_path)
    raw.executescript(
        """
        CREATE TABLE instances (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          prompt TEXT NOT NULL,
          mode TEXT NOT NULL,
          source TEXT NOT NULL,
          provider TEXT,
          generation_path TEXT NOT NULL DEFAULT '',
          generation_size TEXT NOT NULL DEFAULT '',
          generation_params_json TEXT NOT NULL DEFAULT '{}',
          output_image_path TEXT NOT NULL DEFAULT '',
          generation_status TEXT NOT NULL DEFAULT 'ready',
          generation_task_id TEXT NOT NULL DEFAULT '',
          generation_output_index INTEGER NOT NULL DEFAULT 1,
          generation_error TEXT NOT NULL DEFAULT '',
          generation_started_at TEXT NOT NULL DEFAULT '',
          generation_finished_at TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE input_images (id INTEGER PRIMARY KEY AUTOINCREMENT, instance_id INTEGER NOT NULL, path TEXT NOT NULL, position INTEGER NOT NULL);
        CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
        CREATE TABLE instance_tags (instance_id INTEGER NOT NULL, tag_id INTEGER NOT NULL, PRIMARY KEY (instance_id, tag_id));
        CREATE TABLE nodes (id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER, name TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE generation_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          status TEXT NOT NULL,
          prompt TEXT NOT NULL DEFAULT '',
          mode TEXT NOT NULL DEFAULT '',
          provider_key TEXT NOT NULL DEFAULT '',
          adapter TEXT NOT NULL DEFAULT '',
          openai_call_method TEXT NOT NULL DEFAULT '',
          generation_path TEXT NOT NULL DEFAULT '',
          resolved_size TEXT NOT NULL DEFAULT '',
          params_json TEXT NOT NULL DEFAULT '{}',
          input_image_paths_json TEXT NOT NULL DEFAULT '[]',
          output_image_paths_json TEXT NOT NULL DEFAULT '[]',
          tags_json TEXT NOT NULL DEFAULT '[]',
          error_message TEXT NOT NULL DEFAULT '',
          custom_script_used INTEGER NOT NULL DEFAULT 0,
          started_at TEXT NOT NULL,
          finished_at TEXT NOT NULL DEFAULT '',
          duration_ms INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    raw.executemany(
        """
        INSERT INTO instances(prompt, mode, source, provider, created_at, updated_at)
        VALUES (?, 'text_to_image', 'manual', '', ?, ?)
        """,
        [
            ("middle", "2026-05-02T10:00:00", "2026-05-02T10:00:00"),
            ("earliest", "2026-05-01T10:00:00", "2026-05-01T10:00:00"),
            ("latest", "2026-05-03T10:00:00", "2026-05-03T10:00:00"),
        ],
    )
    raw.commit()
    raw.close()

    conn = get_connection(db_path)
    init_db(conn)
    items = list_instances(conn, {"sort": "number_asc", "page": 1, "per_page": 50})["items"]

    assert [item["prompt"] for item in items] == ["earliest", "middle", "latest"]
    assert [item["instance_number"] for item in items] == [1, 2, 3]


def test_v067_status_filter_accepts_multiple_states_with_or_semantics(tmp_path):
    conn = make_db(tmp_path)
    create_instance(conn, {"prompt": "prepared"})
    create_instance(conn, {"prompt": "generated", "output_image_path": "C:\\out.png"})
    create_instance(conn, {"prompt": "failed", "generation_status": "failed"})
    create_instance(conn, {"prompt": "running", "generation_status": "running", "generation_task_id": "task"})

    result = list_instances(
        conn,
        {"statuses": ["running", "failed"], "sort": "number_asc", "page": 1, "per_page": 50},
    )
    legacy = list_instances(
        conn,
        {"status": "failed", "sort": "number_asc", "page": 1, "per_page": 50},
    )

    assert [item["prompt"] for item in result["items"]] == ["failed", "running"]
    assert [item["prompt"] for item in legacy["items"]] == ["failed"]


def test_list_tags_returns_only_tags_still_used_by_instances(tmp_path):
    conn = make_db(tmp_path)
    first_id = create_instance(
        conn,
        {
            "prompt": "角色海报",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["角色", "海报"],
        },
    )
    second_id = create_instance(
        conn,
        {
            "prompt": "参考图",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": ["参考"],
        },
    )

    delete_instance(conn, second_id)

    assert database.list_tags(conn) == ["海报", "角色"]


def test_v029_list_tags_orders_by_usage_count_and_excludes_running(tmp_path):
    conn = make_db(tmp_path)
    create_test_instance(conn, "海报 1", tags=["海报", "角色"])
    create_test_instance(conn, "海报 2", tags=["海报"])
    create_test_instance(conn, "产品 1", tags=["产品"])
    create_test_instance(conn, "产品 2", tags=["产品"])
    create_test_instance(conn, "过程", tags=["过程"], generation_status="running")

    assert database.list_tags(conn) == ["产品", "海报", "角色"]


def test_list_date_only_end_date_includes_whole_day(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "same day",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": [],
        },
    )
    conn.execute(
        "UPDATE instances SET created_at = ?, updated_at = ? WHERE id = ?",
        ("2026-04-30T12:00:00", "2026-04-30T12:00:00", instance_id),
    )
    conn.commit()

    result = list_instances(conn, {"end_date": "2026-04-30"})

    assert result["total"] == 1
    assert result["items"][0]["prompt"] == "same day"


def test_list_invalid_pagination_strings_default_safely(tmp_path):
    conn = make_db(tmp_path)
    create_instance(
        conn,
        {
            "prompt": "pagination",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "",
            "input_image_paths": [],
            "tags": [],
        },
    )

    result = list_instances(conn, {"page": "abc", "per_page": "abc"})

    assert result["page"] == 1
    assert result["per_page"] == 50
    assert result["total"] == 1


def test_list_accepts_10_and_20_per_page_options(tmp_path):
    conn = make_db(tmp_path)
    for index in range(25):
        create_instance(
            conn,
            {
                "prompt": f"pagination {index}",
                "mode": "text_to_image",
                "source": "manual",
                "provider": None,
                "generation_path": "",
                "output_image_path": "",
                "input_image_paths": [],
                "tags": [],
            },
        )

    ten = list_instances(conn, {"page": 1, "per_page": 10})
    twenty = list_instances(conn, {"page": 1, "per_page": 20})
    invalid = list_instances(conn, {"page": 1, "per_page": 11})

    assert ten["per_page"] == 10
    assert len(ten["items"]) == 10
    assert twenty["per_page"] == 20
    assert len(twenty["items"]) == 20
    assert invalid["per_page"] == 50


def test_delete_removes_record_without_touching_paths(tmp_path):
    conn = make_db(tmp_path)
    instance_id = create_instance(
        conn,
        {
            "prompt": "x",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": "C:\\out\\x.png",
            "input_image_paths": ["C:\\in\\x.png"],
            "tags": [],
        },
    )

    delete_instance(conn, instance_id)

    assert get_instance(conn, instance_id) is None


def test_generation_history_create_finish_and_list(tmp_path):
    conn = make_db(tmp_path)
    history_id = create_generation_history(
        conn,
        {
            "prompt": "产品海报",
            "mode": "text_to_image",
            "provider_key": "aiapis_gpt_image_2",
            "adapter": "openai",
            "openai_call_method": "gpt-image-2",
            "generation_path": "D:\\out",
            "resolved_size": "1024x1024",
            "params": {
                "ratio": "1:1",
                "resolution_level": "1K",
                "n": 2,
                "user_agent": "Mozilla/5.0 PowerShell/7.4",
            },
            "input_image_paths": ["D:\\in\\one.png"],
            "tags": ["产品", "__untagged__", "", "海报"],
            "custom_script_used": False,
        },
    )

    finish_generation_history(
        conn,
        history_id,
        {
            "status": "success",
            "output_image_paths": ["D:\\out\\one.png", "D:\\out\\two.png"],
        },
    )

    result = list_generation_history(conn, {"page": 1, "per_page": 10})
    item = result["items"][0]

    assert result["total"] == 1
    assert item["display_index"] == 1
    assert item["status"] == "success"
    assert item["prompt"] == "产品海报"
    assert item["params"]["user_agent"] == "Mozilla/5.0 PowerShell/7.4"
    assert item["input_image_paths"] == ["D:\\in\\one.png"]
    assert item["output_image_paths"] == ["D:\\out\\one.png", "D:\\out\\two.png"]
    assert item["tags"] == ["产品", "海报"]
    assert item["duration_ms"] >= 0


def test_v040_generation_history_tags_json_migrates_old_database(tmp_path):
    db_path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE generation_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          status TEXT NOT NULL,
          prompt TEXT NOT NULL DEFAULT '',
          mode TEXT NOT NULL DEFAULT '',
          provider_key TEXT NOT NULL DEFAULT '',
          adapter TEXT NOT NULL DEFAULT '',
          openai_call_method TEXT NOT NULL DEFAULT '',
          generation_path TEXT NOT NULL DEFAULT '',
          resolved_size TEXT NOT NULL DEFAULT '',
          params_json TEXT NOT NULL DEFAULT '{}',
          input_image_paths_json TEXT NOT NULL DEFAULT '[]',
          output_image_paths_json TEXT NOT NULL DEFAULT '[]',
          error_message TEXT NOT NULL DEFAULT '',
          custom_script_used INTEGER NOT NULL DEFAULT 0,
          started_at TEXT NOT NULL,
          finished_at TEXT NOT NULL DEFAULT '',
          duration_ms INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        INSERT INTO generation_history(
          status, prompt, started_at
        ) VALUES ('success', '旧历史', '2026-05-01T00:00:00')
        """
    )
    conn.commit()
    conn.close()

    conn = get_connection(db_path)
    init_db(conn)

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(generation_history)")}
    result = list_generation_history(conn, {"page": 1, "per_page": 10})

    assert "tags_json" in columns
    assert result["items"][0]["tags"] == []
    assert schema_version(conn) == 5


def test_generation_history_failed_status_and_filter(tmp_path):
    conn = make_db(tmp_path)
    success_id = create_generation_history(conn, {"prompt": "ok"})
    failed_id = create_generation_history(conn, {"prompt": "bad"})
    finish_generation_history(conn, success_id, {"status": "success"})
    finish_generation_history(
        conn,
        failed_id,
        {"status": "failed", "error_message": "缺少 API Key"},
    )

    result = list_generation_history(conn, {"status": "failed"})

    assert result["total"] == 1
    assert result["items"][0]["prompt"] == "bad"
    assert result["items"][0]["error_message"] == "缺少 API Key"


def test_v027_list_instances_supports_untagged_and_mode_filters(tmp_path):
    conn = make_db(tmp_path)
    text_no_output = create_test_instance(conn, "文生图无输出", tags=[])
    text_with_output = create_test_instance(
        conn,
        "文生图有输出",
        tags=["海报"],
        output_image_path="D:\\out\\text.png",
    )
    image_with_output = create_test_instance(
        conn,
        "图生图有输出",
        tags=["参考"],
        input_image_paths=["D:\\in\\one.png"],
        output_image_path="D:\\out\\image.png",
    )
    image_no_output = create_test_instance(
        conn,
        "图生图无输出",
        input_image_paths=["D:\\in\\two.png"],
    )

    untagged = list_instances(conn, {"tags": ["__untagged__"], "sort": "created_asc"})
    text_to_image = list_instances(conn, {"mode_filter": "text_to_image", "sort": "created_asc"})
    image_to_image = list_instances(conn, {"mode_filter": "image_to_image", "sort": "created_asc"})
    has_output = list_instances(conn, {"mode_filter": "has_output", "sort": "created_asc"})
    no_output = list_instances(conn, {"mode_filter": "no_output", "sort": "created_asc"})

    assert [item["id"] for item in untagged["items"]] == [text_no_output, image_no_output]
    assert [item["id"] for item in text_to_image["items"]] == [text_no_output, text_with_output]
    assert [item["id"] for item in image_to_image["items"]] == [image_with_output, image_no_output]
    assert [item["id"] for item in has_output["items"]] == [text_with_output, image_with_output]
    assert [item["id"] for item in no_output["items"]] == [text_no_output, image_no_output]


def test_v027_batch_add_and_remove_tags_without_duplicates(tmp_path):
    conn = make_db(tmp_path)
    first_id = create_test_instance(conn, "第一条", tags=["产品"])
    second_id = create_test_instance(conn, "第二条", tags=["参考"])

    added = batch_add_tags(conn, [first_id, second_id], ["精选", "产品", "精选"])
    removed = batch_remove_tags(conn, [first_id, second_id], ["参考", "不存在"])

    assert added == 2
    assert removed == 1
    assert get_instance(conn, first_id)["tags"] == ["产品", "精选"]
    assert get_instance(conn, second_id)["tags"] == ["精选", "产品"]


def test_v027_batch_delete_instances_cascades_records_without_touching_files(tmp_path):
    conn = make_db(tmp_path)
    input_file = tmp_path / "input.png"
    output_file = tmp_path / "output.png"
    input_file.write_bytes(b"input")
    output_file.write_bytes(b"output")
    first_id = create_test_instance(
        conn,
        "要批量删除 1",
        tags=["产品"],
        input_image_paths=[str(input_file)],
        output_image_path=str(output_file),
    )
    second_id = create_test_instance(conn, "要批量删除 2", tags=["参考"])

    deleted = batch_delete_instances(conn, [first_id, second_id])

    assert deleted == 2
    assert get_instance(conn, first_id) is None
    assert get_instance(conn, second_id) is None
    assert conn.execute("SELECT COUNT(*) FROM input_images").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM instance_tags").fetchone()[0] == 0
    assert input_file.exists()
    assert output_file.exists()


def test_v029_nodes_can_be_created_listed_and_validate_names(tmp_path):
    conn = make_db(tmp_path)

    root_id = create_node(conn, None, "人像")
    child_id = create_node(conn, root_id, "写实")
    tree = list_nodes(conn)

    assert tree == [
        {
            "id": root_id,
            "parent_id": None,
            "name": "人像",
            "position": 1,
            "children": [
                {
                    "id": child_id,
                    "parent_id": root_id,
                    "name": "写实",
                    "position": 1,
                    "children": [],
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="节点名称已存在"):
        create_node(conn, None, "人像")
    for reserved in ["全部", "其他", "新建", "  全部  "]:
        with pytest.raises(ValueError, match="保留"):
            create_node(conn, root_id, reserved)


def test_v029_instances_can_move_to_nodes_and_root_other(tmp_path):
    conn = make_db(tmp_path)
    root_id = create_node(conn, None, "项目")
    instance_id = create_test_instance(conn, "要移动")

    moved = move_instance_to_node(conn, instance_id, root_id)
    moved_back = move_instance_to_node(conn, instance_id, None)

    assert moved["node_id"] == root_id
    assert moved_back["node_id"] is None


def test_v029_running_instances_cannot_move_and_batch_skips_them(tmp_path):
    conn = make_db(tmp_path)
    node_id = create_node(conn, None, "节点")
    ready_id = create_test_instance(conn, "正常")
    running_id = create_test_instance(conn, "生成中", generation_status="running")

    with pytest.raises(ValueError, match="生成中实例不能移动节点"):
        move_instance_to_node(conn, running_id, node_id)

    assert batch_move_instances(conn, [ready_id, running_id], node_id) == 1
    assert get_instance(conn, ready_id)["node_id"] == node_id
    assert get_instance(conn, running_id)["node_id"] is None


def test_v029_node_filters_cover_root_other_node_all_and_node_other(tmp_path):
    conn = make_db(tmp_path)
    root_id = create_node(conn, None, "项目")
    child_id = create_node(conn, root_id, "子项目")
    root_other_id = create_test_instance(conn, "根层其他", node_id=None)
    direct_id = create_test_instance(conn, "项目直属", node_id=root_id)
    child_id_instance = create_test_instance(conn, "子项目实例", node_id=child_id)

    root_other = list_instances(
        conn,
        {
            "node_filter_type": "unassigned",
            "node_id": None,
            "sort": "created_asc",
        },
    )
    node_all = list_instances(
        conn,
        {
            "node_filter_type": "all",
            "node_id": root_id,
            "sort": "created_asc",
        },
    )
    node_other = list_instances(
        conn,
        {
            "node_filter_type": "unassigned",
            "node_id": root_id,
            "sort": "created_asc",
        },
    )

    assert [item["id"] for item in root_other["items"]] == [root_other_id]
    assert [item["id"] for item in node_all["items"]] == [
        direct_id,
        child_id_instance,
    ]
    assert [item["id"] for item in node_other["items"]] == [direct_id]


def test_v029_node_filter_stacks_with_existing_filters(tmp_path):
    conn = make_db(tmp_path)
    node_id = create_node(conn, None, "项目")
    child_id = create_node(conn, node_id, "子项目")
    create_test_instance(
        conn,
        "产品海报",
        tags=["产品", "海报"],
        source="generated",
        output_image_path="D:\\out\\one.png",
        node_id=child_id,
    )
    create_test_instance(
        conn,
        "产品摄影",
        tags=["产品"],
        source="generated",
        node_id=child_id,
    )
    create_test_instance(conn, "根层产品海报", tags=["产品", "海报"], node_id=None)

    result = list_instances(
        conn,
        {
            "node_filter_type": "all",
            "node_id": node_id,
            "q": "产品",
            "tags": ["产品", "海报"],
            "source": "generated",
            "mode_filter": "has_output",
            "sort": "prompt_asc",
            "page": 1,
            "per_page": 10,
        },
    )

    assert result["total"] == 1
    assert result["items"][0]["prompt"] == "产品海报"


def test_v030_delete_node_promotes_children_and_moves_subtree_instances_to_parent(tmp_path):
    conn = make_db(tmp_path)
    root_id = create_node(conn, None, "人像")
    child_id = create_node(conn, root_id, "写实")
    leaf_id = create_node(conn, child_id, "女性")
    direct_id = create_test_instance(conn, "人像直属", node_id=root_id)
    child_instance_id = create_test_instance(conn, "写实实例", node_id=child_id)
    leaf_instance_id = create_test_instance(conn, "女性实例", node_id=leaf_id)

    deleted = delete_node(conn, child_id)
    tree = database.list_nodes(conn)

    assert deleted["deleted_node_id"] == child_id
    assert get_instance(conn, direct_id)["node_id"] == root_id
    assert get_instance(conn, child_instance_id)["node_id"] == root_id
    assert get_instance(conn, leaf_instance_id)["node_id"] == root_id


def test_v056_reorder_nodes_only_allows_same_parent_and_persists_position(tmp_path):
    conn = make_db(tmp_path)
    first_id = create_node(conn, None, "第一")
    second_id = create_node(conn, None, "第二")
    third_id = create_node(conn, None, "第三")
    child_id = create_node(conn, first_id, "子级")

    tree = reorder_nodes(conn, None, [third_id, first_id, second_id])

    assert [node["id"] for node in tree] == [third_id, first_id, second_id]
    assert [node["id"] for node in list_nodes(conn)] == [third_id, first_id, second_id]
    assert list_nodes(conn)[1]["children"][0]["id"] == child_id
    with pytest.raises(ValueError, match="同一层级"):
        reorder_nodes(conn, None, [first_id, child_id])














