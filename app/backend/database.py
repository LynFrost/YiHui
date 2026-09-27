from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


SORTS = {
    "created_desc": "created_at DESC, id DESC",
    "created_asc": "created_at ASC, id ASC",
    "number_asc": "instance_number ASC, id ASC",
    "number_desc": "instance_number DESC, id DESC",
    "prompt_asc": "prompt ASC, id ASC",
    "prompt_desc": "prompt DESC, id DESC",
}
PER_PAGE_OPTIONS = {10, 20, 50, 100, 200}
UNTAGGED_FILTER = "__untagged__"
APP_SCHEMA_VERSION = 5
APP_VERSION = "V0.73"
RESERVED_NODE_NAMES = {"全部", "其他", "新建"}
INSTANCE_SIZE_EXPR = (
    "COALESCE(NULLIF(generation_size, ''), "
    "json_extract(generation_params_json, '$.resolved_size'), "
    "json_extract(generation_params_json, '$.size'), '')"
)
INSTANCE_CALL_METHOD_EXPR = "COALESCE(json_extract(generation_params_json, '$.openai_call_method'), '')"
INSTANCE_MODEL_EXPR = "COALESCE(json_extract(generation_params_json, '$.model'), '')"
INSTANCE_HAS_OUTPUT_EXPR = "COALESCE(output_image_path, '') <> ''"
HISTORY_SIZE_EXPR = (
    "COALESCE(NULLIF(resolved_size, ''), "
    "json_extract(params_json, '$.resolved_size'), "
    "json_extract(params_json, '$.size'), '')"
)
HISTORY_MODEL_EXPR = "COALESCE(json_extract(params_json, '$.model'), '')"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def instance_sort_sql(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    sort = str(filters.get("sort") or "created_desc").strip()
    if sort in {"provider_asc", "provider_desc"}:
        direction = "DESC" if sort == "provider_desc" else "ASC"
        provider_order = filters.get("provider_sort_order")
        if isinstance(provider_order, list):
            ordered_keys = [str(key or "") for key in provider_order]
        else:
            ordered_keys = []
        if ordered_keys:
            cases = " ".join(
                f"WHEN COALESCE(provider, '') = ? THEN {index}"
                for index, _ in enumerate(ordered_keys)
            )
            return (
                f"CASE {cases} ELSE {len(ordered_keys)} END {direction}, "
                f"COALESCE(provider, '') COLLATE NOCASE {direction}, id {direction}",
                ordered_keys,
            )
        return f"COALESCE(provider, '') COLLATE NOCASE {direction}, id {direction}", []
    return SORTS.get(sort, SORTS["created_desc"]), []


def instance_state_where(status: Any) -> str:
    value = str(status or "all").strip()
    if value in {"generated", "success"}:
        return f"{INSTANCE_HAS_OUTPUT_EXPR} AND generation_status <> 'running'"
    if value in {"prepared", "ready"}:
        return f"COALESCE(output_image_path, '') = '' AND generation_status NOT IN ('failed', 'running')"
    if value == "failed":
        return "generation_status = 'failed'"
    if value == "running":
        return "generation_status = 'running'"
    if value == "other":
        return (
            "NOT ("
            f"{INSTANCE_HAS_OUTPUT_EXPR} AND generation_status <> 'running'"
            ") AND NOT ("
            "COALESCE(output_image_path, '') = '' AND generation_status NOT IN ('failed', 'running')"
            ") AND generation_status <> 'failed' AND generation_status <> 'running'"
        )
    return ""


def normalize_instance_status_filters(statuses: Any, legacy_status: Any = "all") -> list[str]:
    raw_values = statuses if isinstance(statuses, list) else []
    result: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        clean = str(value or "").strip()
        if clean in {"", "all"}:
            continue
        if clean == "success":
            clean = "generated"
        if clean not in {"running", "prepared", "failed", "generated", "other"}:
            continue
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    if result:
        return result
    legacy = str(legacy_status or "all").strip()
    if legacy == "success":
        legacy = "generated"
    if legacy and legacy != "all" and legacy in {"running", "prepared", "failed", "generated", "other"}:
        return [legacy]
    return []


def instance_statuses_where(statuses: Any, legacy_status: Any = "all") -> str:
    clauses = [
        instance_state_where(status)
        for status in normalize_instance_status_filters(statuses, legacy_status)
    ]
    clauses = [clause for clause in clauses if clause]
    if not clauses:
        return ""
    return "(" + " OR ".join(f"({clause})" for clause in clauses) + ")"


def instance_number_label(value: Any) -> str:
    number = safe_int(value, 0)
    if number <= 0:
        return ""
    return f"#{number:04d}"


def end_date_filter_value(value: str) -> tuple[str, str]:
    if len(value) == 10:
        try:
            next_day = datetime.fromisoformat(value).date() + timedelta(days=1)
            return "<", next_day.isoformat()
        except ValueError:
            pass
    return "<=", value


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS instances (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          instance_number INTEGER,
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
        CREATE TABLE IF NOT EXISTS input_images (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          instance_id INTEGER NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
          path TEXT NOT NULL,
          position INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tags (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS instance_tags (
          instance_id INTEGER NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
          tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
          PRIMARY KEY (instance_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS nodes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          parent_id INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
          name TEXT NOT NULL,
          position INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS generation_history (
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
        CREATE TABLE IF NOT EXISTS app_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        """
    )
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(instances)").fetchall()
    }
    if "generation_size" not in columns:
        conn.execute(
            "ALTER TABLE instances ADD COLUMN generation_size TEXT NOT NULL DEFAULT ''"
        )
    if "generation_params_json" not in columns:
        conn.execute(
            "ALTER TABLE instances ADD COLUMN generation_params_json TEXT NOT NULL DEFAULT '{}'"
        )
    if "node_id" not in columns:
        conn.execute("ALTER TABLE instances ADD COLUMN node_id INTEGER REFERENCES nodes(id) ON DELETE SET NULL")
    if "instance_number" not in columns:
        conn.execute("ALTER TABLE instances ADD COLUMN instance_number INTEGER")
    generation_columns = {
        "generation_status": "TEXT NOT NULL DEFAULT 'ready'",
        "generation_task_id": "TEXT NOT NULL DEFAULT ''",
        "generation_output_index": "INTEGER NOT NULL DEFAULT 1",
        "generation_error": "TEXT NOT NULL DEFAULT ''",
        "generation_started_at": "TEXT NOT NULL DEFAULT ''",
        "generation_finished_at": "TEXT NOT NULL DEFAULT ''",
    }
    for column, definition in generation_columns.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE instances ADD COLUMN {column} {definition}")
    history_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(generation_history)").fetchall()
    }
    if "tags_json" not in history_columns:
        conn.execute(
            "ALTER TABLE generation_history ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'"
        )
    conn.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_root_name
          ON nodes(name) WHERE parent_id IS NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_parent_name
          ON nodes(parent_id, name) WHERE parent_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_nodes_parent_position ON nodes(parent_id, position, id);
        CREATE INDEX IF NOT EXISTS idx_instances_created_at ON instances(created_at);
        CREATE INDEX IF NOT EXISTS idx_instances_prompt ON instances(prompt);
        CREATE INDEX IF NOT EXISTS idx_instances_source ON instances(source);
        CREATE INDEX IF NOT EXISTS idx_instances_output_image_path ON instances(output_image_path);
        CREATE INDEX IF NOT EXISTS idx_instances_node_id ON instances(node_id);
        CREATE INDEX IF NOT EXISTS idx_input_images_instance_id ON input_images(instance_id);
        CREATE INDEX IF NOT EXISTS idx_input_images_instance_position ON input_images(instance_id, position);
        CREATE INDEX IF NOT EXISTS idx_instance_tags_tag ON instance_tags(tag_id);
        CREATE INDEX IF NOT EXISTS idx_generation_history_started_at ON generation_history(started_at);
        CREATE INDEX IF NOT EXISTS idx_generation_history_status ON generation_history(status);
        CREATE INDEX IF NOT EXISTS idx_generation_history_provider ON generation_history(provider_key);
        CREATE INDEX IF NOT EXISTS idx_generation_history_call_method ON generation_history(openai_call_method);
        """
    )
    repair_instance_numbers(conn)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_instances_instance_number ON instances(instance_number)"
    )
    write_metadata(conn, "schema_version", str(APP_SCHEMA_VERSION))
    write_metadata(conn, "app_version", APP_VERSION)
    write_metadata(conn, "last_migration_at", now_iso())
    conn.commit()


def write_metadata(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_metadata(key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT value FROM app_metadata WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.Error:
        return 0
    if row is None:
        return 0
    return safe_int(row["value"], 0)


def normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        name = str(tag).strip()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def normalize_real_tag_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValueError("TAG 名称不能为空")
    if name in {"无", UNTAGGED_FILTER}:
        raise ValueError("不能使用系统保留 TAG")
    return name


def normalize_instance_ids(ids: Any) -> list[int]:
    if not isinstance(ids, list):
        return []
    seen: set[int] = set()
    result: list[int] = []
    for value in ids:
        try:
            instance_id = int(value)
        except (TypeError, ValueError):
            continue
        if instance_id > 0 and instance_id not in seen:
            seen.add(instance_id)
            result.append(instance_id)
    return result


def existing_instance_ids(conn: sqlite3.Connection, ids: list[int]) -> list[int]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id FROM instances WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    existing = {int(row["id"]) for row in rows}
    return [instance_id for instance_id in ids if instance_id in existing]


def normalize_node_id(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        node_id = int(value)
    except (TypeError, ValueError):
        raise ValueError("节点无效") from None
    if node_id <= 0:
        raise ValueError("节点无效")
    return node_id


def validate_node_exists(conn: sqlite3.Connection, node_id: int | None) -> int | None:
    if node_id is None:
        return None
    row = conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if row is None:
        raise ValueError("节点不存在")
    return node_id


def repair_instance_numbers(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT id, instance_number
        FROM instances
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()
    used: set[int] = set()
    next_number = 1
    repaired = 0
    for row in rows:
        instance_id = int(row["id"])
        current = safe_int(row["instance_number"], 0)
        if current > 0 and current not in used:
            used.add(current)
            next_number = max(next_number, current + 1)
            continue
        while next_number in used:
            next_number += 1
        conn.execute(
            "UPDATE instances SET instance_number = ? WHERE id = ?",
            (next_number, instance_id),
        )
        used.add(next_number)
        next_number += 1
        repaired += 1
    return {
        "instances_instance_number_repaired": repaired,
    }


def next_instance_number(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(instance_number), 0) + 1 AS next_number FROM instances"
    ).fetchone()
    return int(row["next_number"] or 1)


def normalize_node_name(name: Any) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("节点名称不能为空")
    if normalized in RESERVED_NODE_NAMES:
        raise ValueError("节点名称是保留名称")
    return normalized


def next_node_position(conn: sqlite3.Connection, parent_id: int | None) -> int:
    if parent_id is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS position FROM nodes WHERE parent_id IS NULL"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS position FROM nodes WHERE parent_id = ?",
            (parent_id,),
        ).fetchone()
    return int(row["position"])


def hydrate_node_tree(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    node_map: dict[int, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []
    for row in rows:
        node = {
            "id": int(row["id"]),
            "parent_id": int(row["parent_id"]) if row["parent_id"] is not None else None,
            "name": str(row["name"]),
            "position": int(row["position"]),
            "children": [],
        }
        node_map[node["id"]] = node
    for node in node_map.values():
        parent_id = node["parent_id"]
        if parent_id is None or parent_id not in node_map:
            roots.append(node)
        else:
            node_map[parent_id]["children"].append(node)
    return roots


def list_nodes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, parent_id, name, position
        FROM nodes
        ORDER BY parent_id IS NOT NULL, parent_id, position, id
        """
    ).fetchall()
    return hydrate_node_tree(rows)


def create_node(conn: sqlite3.Connection, parent_id: Any, name: Any) -> int:
    normalized_parent_id = validate_node_exists(conn, normalize_node_id(parent_id))
    normalized_name = normalize_node_name(name)
    timestamp = now_iso()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO nodes(parent_id, name, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    normalized_parent_id,
                    normalized_name,
                    next_node_position(conn, normalized_parent_id),
                    timestamp,
                    timestamp,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("节点名称已存在") from exc
    return int(cur.lastrowid)


def reorder_nodes(conn: sqlite3.Connection, parent_id: Any, node_ids: Any) -> list[dict[str, Any]]:
    normalized_parent_id = validate_node_exists(conn, normalize_node_id(parent_id))
    if not isinstance(node_ids, list):
        raise ValueError("节点顺序必须是列表")

    normalized_ids: list[int] = []
    seen: set[int] = set()
    for value in node_ids:
        node_id = normalize_node_id(value)
        if node_id is None:
            raise ValueError("节点无效")
        if node_id in seen:
            raise ValueError("节点顺序不能重复")
        normalized_ids.append(node_id)
        seen.add(node_id)

    if not normalized_ids:
        raise ValueError("节点顺序不能为空")

    placeholders = ",".join("?" for _ in normalized_ids)
    rows = conn.execute(
        f"SELECT id, parent_id FROM nodes WHERE id IN ({placeholders})",
        normalized_ids,
    ).fetchall()
    if len(rows) != len(normalized_ids):
        raise ValueError("节点不存在")
    for row in rows:
        row_parent_id = int(row["parent_id"]) if row["parent_id"] is not None else None
        if row_parent_id != normalized_parent_id:
            raise ValueError("节点必须属于同一层级")

    if normalized_parent_id is None:
        sibling_rows = conn.execute(
            "SELECT id FROM nodes WHERE parent_id IS NULL ORDER BY position, id"
        ).fetchall()
    else:
        sibling_rows = conn.execute(
            "SELECT id FROM nodes WHERE parent_id = ? ORDER BY position, id",
            (normalized_parent_id,),
        ).fetchall()
    sibling_ids = [int(row["id"]) for row in sibling_rows]
    if set(sibling_ids) != set(normalized_ids):
        raise ValueError("节点排序必须包含当前层级所有节点")

    timestamp = now_iso()
    with conn:
        for position, node_id in enumerate(normalized_ids, start=1):
            conn.execute(
                "UPDATE nodes SET position = ?, updated_at = ? WHERE id = ?",
                (position, timestamp, node_id),
            )
    return list_nodes(conn)


def rename_node(conn: sqlite3.Connection, node_id: Any, name: Any) -> dict[str, Any]:
    normalized_node_id = validate_node_exists(conn, normalize_node_id(node_id))
    normalized_name = normalize_node_name(name)
    try:
        with conn:
            conn.execute(
                """
                UPDATE nodes
                SET name = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized_name, now_iso(), normalized_node_id),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("节点名称已存在") from exc
    row = conn.execute("SELECT * FROM nodes WHERE id = ?", (normalized_node_id,)).fetchone()
    return dict(row)


def delete_node(conn: sqlite3.Connection, node_id: Any) -> dict[str, Any]:
    normalized_node_id = validate_node_exists(conn, normalize_node_id(node_id))
    row = conn.execute(
        "SELECT id, parent_id FROM nodes WHERE id = ?",
        (normalized_node_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"Node {normalized_node_id} not found")
    parent_id = int(row["parent_id"]) if row["parent_id"] is not None else None

    subtree_rows = conn.execute(
        """
        WITH RECURSIVE subtree(id) AS (
          SELECT ?
          UNION ALL
          SELECT nodes.id
          FROM nodes
          JOIN subtree ON nodes.parent_id = subtree.id
        )
        SELECT id FROM subtree
        """,
        (normalized_node_id,),
    ).fetchall()
    subtree_ids = [int(item["id"]) for item in subtree_rows]
    child_rows = conn.execute(
        "SELECT id FROM nodes WHERE parent_id = ? ORDER BY position, id",
        (normalized_node_id,),
    ).fetchall()
    child_ids = [int(item["id"]) for item in child_rows]
    placeholders = ",".join("?" for _ in subtree_ids)

    with conn:
        if subtree_ids:
            conn.execute(
                f"UPDATE instances SET node_id = ?, updated_at = ? WHERE node_id IN ({placeholders})",
                [parent_id, now_iso(), *subtree_ids],
            )
        if parent_id is None:
            position_row = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS position FROM nodes WHERE parent_id IS NULL AND id <> ?",
                (normalized_node_id,),
            ).fetchone()
        else:
            position_row = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS position FROM nodes WHERE parent_id = ? AND id <> ?",
                (parent_id, normalized_node_id),
            ).fetchone()
        next_position = int(position_row["position"])
        for child_id in child_ids:
            conn.execute(
                "UPDATE nodes SET parent_id = ?, position = ?, updated_at = ? WHERE id = ?",
                (parent_id, next_position, now_iso(), child_id),
            )
            next_position += 1
        conn.execute("DELETE FROM nodes WHERE id = ?", (normalized_node_id,))

    return {
        "deleted_node_id": normalized_node_id,
        "parent_id": parent_id,
    }


def set_input_images(conn: sqlite3.Connection, instance_id: int, paths: list[str]) -> None:
    conn.execute("DELETE FROM input_images WHERE instance_id = ?", (instance_id,))
    for index, path in enumerate(paths):
        if path:
            conn.execute(
                "INSERT INTO input_images(instance_id, path, position) VALUES (?, ?, ?)",
                (instance_id, path, index),
            )


def tag_id(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    return int(row["id"])


def set_tags(conn: sqlite3.Connection, instance_id: int, tags: list[str]) -> None:
    conn.execute("DELETE FROM instance_tags WHERE instance_id = ?", (instance_id,))
    for name in normalize_tags(tags):
        conn.execute(
            "INSERT INTO instance_tags(instance_id, tag_id) VALUES (?, ?)",
            (instance_id, tag_id(conn, name)),
        )


def generation_params_json(payload: dict[str, Any]) -> str:
    params = payload.get("generation_params")
    if params is None:
        raw = payload.get("generation_params_json")
        if isinstance(raw, str) and raw.strip():
            try:
                params = json.loads(raw)
            except json.JSONDecodeError:
                params = {}
    if not isinstance(params, dict):
        params = {}
    return json.dumps(params, ensure_ascii=False, sort_keys=True)


def parse_generation_params(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def json_object(value: Any) -> str:
    return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=False, sort_keys=True)


def json_list(value: Any) -> str:
    return json.dumps(value if isinstance(value, list) else [], ensure_ascii=False)


def json_tag_list(value: Any) -> str:
    if not isinstance(value, list):
        return "[]"
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        tag = str(item or "").strip()
        if not tag or tag == UNTAGGED_FILTER or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return json.dumps(normalized, ensure_ascii=False)


def parse_json_list(value: Any) -> list[Any]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def duration_ms(started_at: str, finished_at: str) -> int:
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return 0
    return max(0, int((finished - started).total_seconds() * 1000))


def normalize_history_status(status: Any) -> str:
    text = str(status or "").strip()
    return text if text in {"running", "success", "failed"} else "running"


def normalize_generation_status(status: Any) -> str:
    text = str(status or "").strip()
    return text if text in {"ready", "running", "failed"} else "ready"


def create_generation_history(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    started_at = str(payload.get("started_at") or now_iso())
    status = normalize_history_status(payload.get("status") or "running")
    with conn:
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
                str(payload.get("prompt") or ""),
                str(payload.get("mode") or ""),
                str(payload.get("provider_key") or ""),
                str(payload.get("adapter") or ""),
                str(payload.get("openai_call_method") or ""),
                str(payload.get("generation_path") or ""),
                str(payload.get("resolved_size") or ""),
                json_object(payload.get("params")),
                json_list(payload.get("input_image_paths")),
                json_list(payload.get("output_image_paths")),
                json_tag_list(payload.get("tags")),
                str(payload.get("error_message") or ""),
                1 if payload.get("custom_script_used") else 0,
                started_at,
                str(payload.get("finished_at") or ""),
                safe_int(payload.get("duration_ms"), 0),
            ),
        )
    return int(cur.lastrowid)


def finish_generation_history(
    conn: sqlite3.Connection,
    history_id: int | None,
    payload: dict[str, Any],
) -> None:
    if not history_id:
        return
    row = conn.execute(
        "SELECT started_at, params_json FROM generation_history WHERE id = ?",
        (history_id,),
    ).fetchone()
    if row is None:
        return
    finished_at = str(payload.get("finished_at") or now_iso())
    elapsed = payload.get("duration_ms")
    if elapsed is None:
        elapsed = duration_ms(str(row["started_at"]), finished_at)
    with conn:
        conn.execute(
            """
            UPDATE generation_history
            SET status = ?,
                resolved_size = COALESCE(NULLIF(?, ''), resolved_size),
                params_json = ?,
                output_image_paths_json = ?,
                error_message = ?,
                custom_script_used = ?,
                finished_at = ?,
                duration_ms = ?
            WHERE id = ?
            """,
            (
                normalize_history_status(payload.get("status")),
                str(payload.get("resolved_size") or ""),
                json_object(payload.get("params"))
                if "params" in payload
                else str(row["params_json"] or "{}"),
                json_list(payload.get("output_image_paths")),
                str(payload.get("error_message") or ""),
                1 if payload.get("custom_script_used") else 0,
                finished_at,
                safe_int(elapsed, 0),
                history_id,
            ),
        )


def hydrate_generation_history(
    row: sqlite3.Row,
    display_index: int | None = None,
) -> dict[str, Any]:
    item = dict(row)
    item["params"] = parse_generation_params(item.get("params_json"))
    item["input_image_paths"] = [
        str(path) for path in parse_json_list(item.get("input_image_paths_json"))
    ]
    item["output_image_paths"] = [
        str(path) for path in parse_json_list(item.get("output_image_paths_json"))
    ]
    item["tags"] = [
        str(tag)
        for tag in parse_json_list(item.get("tags_json"))
        if str(tag).strip() and str(tag).strip() != UNTAGGED_FILTER
    ]
    item["custom_script_used"] = bool(item.get("custom_script_used"))
    if display_index is not None:
        item["display_index"] = display_index
    item.setdefault("retry_records", [])
    item.setdefault("retry_count", 0)
    return item


def history_retry_parent_id(item: dict[str, Any]) -> int | None:
    params = item.get("params")
    if not isinstance(params, dict):
        return None
    parent_id = safe_int(params.get("parent_history_id"), 0)
    retry_attempt = safe_int(params.get("retry_attempt"), 0)
    return parent_id if parent_id > 0 and retry_attempt > 0 else None


def attach_retry_history_records(
    conn: sqlite3.Connection,
    items: list[dict[str, Any]],
) -> None:
    if not items:
        return
    ids = [safe_int(item.get("id"), 0) for item in items]
    ids = [item_id for item_id in ids if item_id > 0]
    if not ids:
        return
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT *
        FROM generation_history
        WHERE CAST(json_extract(params_json, '$.parent_history_id') AS INTEGER) IN ({placeholders})
          AND CAST(json_extract(params_json, '$.retry_attempt') AS INTEGER) > 0
        ORDER BY CAST(json_extract(params_json, '$.retry_attempt') AS INTEGER) ASC, started_at ASC, id ASC
        """,
        ids,
    ).fetchall()
    retries_by_parent: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        retry = hydrate_generation_history(row)
        parent_id = history_retry_parent_id(retry)
        if parent_id:
            retries_by_parent.setdefault(parent_id, []).append(retry)
    for item in items:
        item_id = safe_int(item.get("id"), 0)
        retry_records = retries_by_parent.get(item_id, [])
        item["retry_records"] = retry_records
        item["retry_count"] = len(retry_records)


def parse_history_date(value: Any, label: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(f"{text}T00:00:00")
    except ValueError:
        raise ValueError(f"{label} 格式无效") from None


def history_date_bounds(filters: dict[str, Any]) -> tuple[str | None, str | None]:
    start = parse_history_date(filters.get("start_date"), "开始日期")
    end = parse_history_date(filters.get("end_date"), "结束日期")
    if start and end and start > end:
        raise ValueError("开始日期不能晚于结束日期")
    start_iso = start.isoformat() if start else None
    end_iso = (end + timedelta(days=1)).isoformat() if end else None
    return start_iso, end_iso


def history_number_type_condition(number_type: Any) -> str:
    clean = str(number_type or "all").strip()
    if clean in {"#", "instance"}:
        return (
            "EXISTS ("
            "SELECT 1 FROM instances i WHERE i.id IN ("
            "CAST(json_extract(params_json, '$.primary_instance_id') AS INTEGER), "
            "CAST(json_extract(params_json, '$.instance_id') AS INTEGER), "
            "CAST(json_extract(params_json, '$.target_instance_id') AS INTEGER), "
            "CAST(json_extract(params_json, '$.retry_instance_id') AS INTEGER)"
            ") OR EXISTS ("
            "SELECT 1 FROM json_each(COALESCE(json_extract(params_json, '$.instance_ids'), '[]')) "
            "WHERE i.id = CAST(value AS INTEGER)"
            "))"
        )
    if clean in {"H", "history"}:
        return (
            "NOT EXISTS ("
            "SELECT 1 FROM instances i WHERE i.id IN ("
            "CAST(json_extract(params_json, '$.primary_instance_id') AS INTEGER), "
            "CAST(json_extract(params_json, '$.instance_id') AS INTEGER), "
            "CAST(json_extract(params_json, '$.target_instance_id') AS INTEGER), "
            "CAST(json_extract(params_json, '$.retry_instance_id') AS INTEGER)"
            ") OR EXISTS ("
            "SELECT 1 FROM json_each(COALESCE(json_extract(params_json, '$.instance_ids'), '[]')) "
            "WHERE i.id = CAST(value AS INTEGER)"
            "))"
        )
    return ""


def generation_history_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    where = []
    params: list[Any] = []

    query = str(filters.get("q") or "").strip()
    if query:
        where.append("prompt LIKE ?")
        params.append(f"%{query}%")

    status = str(filters.get("status") or "all").strip()
    if status in {"running", "success", "failed"}:
        where.append("status = ?")
        params.append(status)
    elif status == "other":
        where.append("status NOT IN ('running', 'success', 'failed')")

    provider = str(filters.get("provider") or "all").strip()
    if provider == "__empty__":
        where.append("provider_key = ''")
    elif provider and provider != "all":
        where.append("provider_key = ?")
        params.append(provider)

    call_method = str(filters.get("call_method") or "all").strip()
    if call_method == "__empty__":
        where.append("openai_call_method = ''")
    elif call_method and call_method != "all":
        where.append("openai_call_method = ?")
        params.append(call_method)

    mode = str(filters.get("mode") or "all").strip()
    if mode == "__empty__":
        where.append("mode = ''")
    elif mode == "other":
        where.append("mode NOT IN ('text_to_image', 'image_to_image', '')")
    elif mode and mode != "all":
        where.append("mode = ?")
        params.append(mode)

    tag_filters = normalize_tags(filters.get("tags", []))
    if UNTAGGED_FILTER in tag_filters:
        where.append(
            """
            NOT EXISTS (
              SELECT 1
              FROM json_each(COALESCE(NULLIF(tags_json, ''), '[]'))
              WHERE TRIM(CAST(value AS TEXT)) <> ''
                AND CAST(value AS TEXT) <> ?
            )
            """
        )
        params.append(UNTAGGED_FILTER)
    else:
        for tag in tag_filters:
            where.append(
                """
                EXISTS (
                  SELECT 1
                  FROM json_each(COALESCE(NULLIF(tags_json, ''), '[]'))
                  WHERE CAST(value AS TEXT) = ?
                )
                """
            )
            params.append(tag)

    model = str(filters.get("model") or "all").strip()
    if model == "__empty__":
        where.append(f"{HISTORY_MODEL_EXPR} = ''")
    elif model and model != "all":
        where.append(f"{HISTORY_MODEL_EXPR} = ?")
        params.append(model)

    size = str(filters.get("size") or "all").strip()
    if size == "__empty__":
        where.append(f"{HISTORY_SIZE_EXPR} = ''")
    elif size and size != "all":
        where.append(f"{HISTORY_SIZE_EXPR} = ?")
        params.append(size)

    number_type_sql = history_number_type_condition(filters.get("number_type"))
    if number_type_sql:
        where.append(number_type_sql)

    start_iso, end_iso = history_date_bounds(filters)
    if start_iso:
        where.append("started_at >= ?")
        params.append(start_iso)
    if end_iso:
        where.append("started_at < ?")
        params.append(end_iso)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return where_sql, params


def generation_history_top_level_where(where_sql: str) -> str:
    retry_child_sql = (
        "COALESCE(CAST(json_extract(params_json, '$.parent_history_id') AS INTEGER), 0) > 0 "
        "AND COALESCE(CAST(json_extract(params_json, '$.retry_attempt') AS INTEGER), 0) > 0"
    )
    top_level_sql = f"NOT ({retry_child_sql})"
    if where_sql:
        return f"{where_sql} AND {top_level_sql}"
    return f"WHERE {top_level_sql}"


def history_primary_instance_id(item: dict[str, Any]) -> int | None:
    params = item.get("params")
    if not isinstance(params, dict):
        return None
    for key in ("primary_instance_id", "instance_id", "target_instance_id", "retry_instance_id"):
        instance_id = safe_int(params.get(key), 0)
        if instance_id > 0:
            return instance_id
    instance_ids = params.get("instance_ids")
    if isinstance(instance_ids, list):
        for value in instance_ids:
            instance_id = safe_int(value, 0)
            if instance_id > 0:
                return instance_id
    return None


def attach_instance_numbers_to_history(
    conn: sqlite3.Connection,
    items: list[dict[str, Any]],
) -> None:
    instance_ids = []
    for item in items:
        instance_id = history_primary_instance_id(item)
        if instance_id:
            item["_primary_instance_id"] = instance_id
            instance_ids.append(instance_id)
        for retry in item.get("retry_records", []) or []:
            retry_instance_id = history_primary_instance_id(retry)
            if retry_instance_id:
                retry["_primary_instance_id"] = retry_instance_id
                instance_ids.append(retry_instance_id)
    instance_ids = sorted(set(instance_ids))
    if not instance_ids:
        return
    placeholders = ",".join("?" for _ in instance_ids)
    rows = conn.execute(
        f"""
        SELECT id, instance_number
        FROM instances
        WHERE id IN ({placeholders})
        """,
        instance_ids,
    ).fetchall()
    numbers = {
        int(row["id"]): safe_int(row["instance_number"], 0)
        for row in rows
    }

    def attach(item: dict[str, Any]) -> None:
        instance_id = item.pop("_primary_instance_id", None)
        number = numbers.get(instance_id)
        if number:
            item["instance_number"] = number
            item["instance_number_label"] = instance_number_label(number)

    for item in items:
        attach(item)
        for retry in item.get("retry_records", []) or []:
            attach(retry)


def unlinked_history_number_map(conn: sqlite3.Connection) -> dict[int, int]:
    rows = conn.execute(
        f"""
        SELECT id
        FROM generation_history
        WHERE {history_number_type_condition("H")}
        ORDER BY started_at ASC, id ASC
        """
    ).fetchall()
    return {int(row["id"]): index + 1 for index, row in enumerate(rows)}


def attach_history_numbers_to_unlinked_items(
    conn: sqlite3.Connection,
    items: list[dict[str, Any]],
) -> None:
    if not items:
        return
    numbers = unlinked_history_number_map(conn)

    def attach(item: dict[str, Any]) -> None:
        if item.get("instance_number"):
            return
        number = numbers.get(safe_int(item.get("id"), 0))
        if number:
            item["history_number"] = number
            item["history_number_label"] = f"H{number:04d}"

    for item in items:
        attach(item)
        for retry in item.get("retry_records", []) or []:
            attach(retry)


def list_generation_history(
    conn: sqlite3.Connection,
    filters: dict[str, Any],
) -> dict[str, Any]:
    where_sql, params = generation_history_where(filters)
    top_level_where_sql = generation_history_top_level_where(where_sql)

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM generation_history {top_level_where_sql}",
        params,
    ).fetchone()
    total = int(count_row["total"])

    page = max(1, safe_int(filters.get("page") or 1, 1))
    per_page = safe_int(filters.get("per_page") or 50, 50)
    if per_page not in PER_PAGE_OPTIONS:
        per_page = 50
    offset = (page - 1) * per_page

    rows = conn.execute(
        f"""
        SELECT * FROM generation_history
        {top_level_where_sql}
        ORDER BY started_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, per_page, offset],
    ).fetchall()
    items = [
        hydrate_generation_history(row, display_index=offset + index + 1)
        for index, row in enumerate(rows)
    ]
    attach_retry_history_records(conn, items)
    attach_instance_numbers_to_history(conn, items)
    attach_history_numbers_to_unlinked_items(conn, items)
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def filter_value_list(rows: list[sqlite3.Row]) -> list[str]:
    values = [str(row["value"] or "") for row in rows]
    has_empty = any(value == "" for value in values)
    non_empty = sorted({value for value in values if value}, key=str.casefold)
    return (["__empty__"] if has_empty else []) + non_empty


def history_filter_values(conn: sqlite3.Connection, expression: str, *, allow_expression: bool = False) -> list[str]:
    if not allow_expression and expression not in {"provider_key", "openai_call_method", "mode", "resolved_size"}:
        raise ValueError("历史筛选字段无效")
    value_expression = expression if allow_expression else expression
    rows = conn.execute(
        f"""
        SELECT DISTINCT {value_expression} AS value
        FROM generation_history
        ORDER BY value COLLATE NOCASE ASC
        """
    ).fetchall()
    return filter_value_list(rows)


def history_tag_filter_values(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT CAST(value AS TEXT) AS value
        FROM generation_history, json_each(COALESCE(NULLIF(tags_json, ''), '[]'))
        WHERE TRIM(CAST(value AS TEXT)) <> ''
          AND CAST(value AS TEXT) <> ?
        ORDER BY value COLLATE NOCASE ASC
        """,
        (UNTAGGED_FILTER,),
    ).fetchall()
    empty_row = conn.execute(
        """
        SELECT 1
        FROM generation_history
        WHERE NOT EXISTS (
          SELECT 1
          FROM json_each(COALESCE(NULLIF(tags_json, ''), '[]'))
          WHERE TRIM(CAST(value AS TEXT)) <> ''
            AND CAST(value AS TEXT) <> ?
        )
        LIMIT 1
        """,
        (UNTAGGED_FILTER,),
    ).fetchone()
    values = [str(row["value"] or "") for row in rows]
    return (["__untagged__"] if empty_row else []) + sorted(set(values), key=str.casefold)


def list_generation_history_filter_options(conn: sqlite3.Connection) -> dict[str, list[str]]:
    return {
        "providers": history_filter_values(conn, "provider_key"),
        "call_methods": history_filter_values(conn, "openai_call_method"),
        "models": history_filter_values(conn, HISTORY_MODEL_EXPR, allow_expression=True),
        "sizes": history_filter_values(conn, HISTORY_SIZE_EXPR, allow_expression=True),
        "modes": history_filter_values(conn, "mode"),
        "statuses": ["running", "success", "failed", "other"],
        "tags": history_tag_filter_values(conn),
    }


def generation_history_cleanup_where(payload: dict[str, Any]) -> tuple[str, list[Any]]:
    cleanup_type = str(payload.get("type") or "").strip()
    if cleanup_type == "failed":
        return "WHERE status = ?", ["failed"]
    if cleanup_type == "before_date":
        before = parse_history_date(payload.get("before_date"), "清理日期")
        if before is None:
            raise ValueError("请选择清理日期")
        return "WHERE started_at < ? AND status <> ?", [before.isoformat(), "running"]
    raise ValueError("清理类型无效")


def preview_generation_history_cleanup(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
) -> dict[str, Any]:
    where_sql, params = generation_history_cleanup_where(payload)
    row = conn.execute(
        f"SELECT COUNT(*) AS total FROM generation_history {where_sql}",
        params,
    ).fetchone()
    return {
        "matched_count": int(row["total"]),
        "will_delete_instances": False,
        "will_delete_image_files": False,
    }


def cleanup_generation_history(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
) -> dict[str, Any]:
    where_sql, params = generation_history_cleanup_where(payload)
    with conn:
        cur = conn.execute(
            f"DELETE FROM generation_history {where_sql}",
            params,
        )
    return {
        "deleted": int(cur.rowcount if cur.rowcount is not None else 0),
        "will_delete_instances": False,
        "will_delete_image_files": False,
    }


def hydrate_instance(
    conn: sqlite3.Connection, row: sqlite3.Row, display_index: int | None = None
) -> dict[str, Any]:
    input_paths = [
        r["path"]
        for r in conn.execute(
            "SELECT path FROM input_images WHERE instance_id = ? ORDER BY position",
            (row["id"],),
        )
    ]
    tags = [
        r["name"]
        for r in conn.execute(
            """
            SELECT tags.name
            FROM tags
            JOIN instance_tags ON instance_tags.tag_id = tags.id
            WHERE instance_tags.instance_id = ?
            ORDER BY instance_tags.rowid
            """,
            (row["id"],),
        )
    ]
    item = dict(row)
    item["generation_params"] = parse_generation_params(
        item.get("generation_params_json")
    )
    output_paths = [
        str(path)
        for path in item["generation_params"].get("output_image_paths", [])
        if str(path or "").strip()
    ] if isinstance(item["generation_params"].get("output_image_paths"), list) else []
    if not output_paths and str(item.get("output_image_path") or "").strip():
        output_paths = [str(item.get("output_image_path") or "")]
    item["output_image_paths"] = output_paths
    item["input_image_paths"] = input_paths
    item["tags"] = tags
    item["instance_number"] = safe_int(item.get("instance_number"), 0)
    item["instance_number_label"] = instance_number_label(item["instance_number"])
    if display_index is not None:
        item["display_index"] = display_index
    return item


def create_instance(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    prompt = str(payload.get("prompt", "")).strip()

    timestamp = now_iso()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO instances(
              instance_number, prompt, mode, source, provider, node_id, generation_path, generation_size,
              generation_params_json, output_image_path, generation_status,
              generation_task_id, generation_output_index, generation_error,
              generation_started_at, generation_finished_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                next_instance_number(conn),
                prompt,
                payload.get("mode", "unspecified"),
                payload.get("source", "manual"),
                payload.get("provider"),
                validate_node_exists(conn, normalize_node_id(payload.get("node_id"))),
                payload.get("generation_path", ""),
                payload.get("generation_size", ""),
                generation_params_json(payload),
                payload.get("output_image_path", ""),
                normalize_generation_status(payload.get("generation_status")),
                str(payload.get("generation_task_id") or ""),
                max(1, safe_int(payload.get("generation_output_index"), 1)),
                str(payload.get("generation_error") or ""),
                str(payload.get("generation_started_at") or ""),
                str(payload.get("generation_finished_at") or ""),
                timestamp,
                timestamp,
            ),
        )
        instance_id = int(cur.lastrowid)
        set_input_images(conn, instance_id, payload.get("input_image_paths", []))
        set_tags(conn, instance_id, payload.get("tags", []))
    return instance_id


def update_instance(conn: sqlite3.Connection, instance_id: int, payload: dict[str, Any]) -> None:
    prompt = str(payload.get("prompt", "")).strip()

    with conn:
        cur = conn.execute(
            """
            UPDATE instances
            SET prompt = ?,
                mode = ?,
                source = ?,
                provider = ?,
                node_id = ?,
                generation_path = ?,
                output_image_path = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                prompt,
                payload.get("mode", "unspecified"),
                payload.get("source", "manual"),
                payload.get("provider"),
                validate_node_exists(conn, normalize_node_id(payload.get("node_id"))),
                payload.get("generation_path", ""),
                payload.get("output_image_path", ""),
                now_iso(),
                instance_id,
            ),
        )
        if cur.rowcount == 0:
            raise KeyError(f"Instance {instance_id} not found")
        if (
            "generation_params" in payload
            or "generation_params_json" in payload
        ):
            conn.execute(
                """
                UPDATE instances
                SET generation_params_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (generation_params_json(payload), now_iso(), instance_id),
            )
        if "generation_size" in payload:
            conn.execute(
                """
                UPDATE instances
                SET generation_size = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (str(payload.get("generation_size") or ""), now_iso(), instance_id),
            )
        set_input_images(conn, instance_id, payload.get("input_image_paths", []))
        set_tags(conn, instance_id, payload.get("tags", []))


def update_instance_output_image(
    conn: sqlite3.Connection,
    instance_id: int,
    output_image_path: str,
    output_image_paths: list[str] | None = None,
) -> None:
    paths = [
        str(path)
        for path in (output_image_paths or [])
        if str(path or "").strip()
    ]
    with conn:
        cur = conn.execute(
            """
            UPDATE instances
            SET output_image_path = ?,
                generation_params_json = CASE
                  WHEN ? IS NULL THEN generation_params_json
                  ELSE json_set(generation_params_json, '$.output_image_paths', json(?))
                END,
                generation_status = 'ready',
                generation_error = '',
                generation_finished_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                str(output_image_path or ""),
                json.dumps(paths, ensure_ascii=False) if paths else None,
                json.dumps(paths, ensure_ascii=False) if paths else "[]",
                now_iso(),
                now_iso(),
                instance_id,
            ),
        )
        if cur.rowcount == 0:
            raise KeyError(f"Instance {instance_id} not found")


def update_instance_generation_status(
    conn: sqlite3.Connection,
    instance_id: int,
    status: str,
    *,
    task_id: str | None = None,
    output_index: int | None = None,
    error: str = "",
    started_at: str = "",
    finished_at: str = "",
) -> None:
    updates = [
        "generation_status = ?",
        "generation_error = ?",
        "updated_at = ?",
    ]
    params: list[Any] = [
        normalize_generation_status(status),
        str(error or ""),
        now_iso(),
    ]
    if task_id is not None:
        updates.append("generation_task_id = ?")
        params.append(str(task_id or ""))
    if output_index is not None:
        updates.append("generation_output_index = ?")
        params.append(max(1, safe_int(output_index, 1)))
    if started_at:
        updates.append("generation_started_at = ?")
        params.append(str(started_at))
    if finished_at:
        updates.append("generation_finished_at = ?")
        params.append(str(finished_at))
    params.append(instance_id)
    with conn:
        cur = conn.execute(
            f"UPDATE instances SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        if cur.rowcount == 0:
            raise KeyError(f"Instance {instance_id} not found")


def prepare_instance_for_generation(
    conn: sqlite3.Connection,
    instance_id: int,
    payload: dict[str, Any],
    *,
    task_id: str,
    output_index: int = 1,
    started_at: str = "",
) -> None:
    timestamp = started_at or now_iso()
    prompt = str(payload.get("prompt", "")).strip()
    with conn:
        cur = conn.execute(
            """
            UPDATE instances
            SET prompt = ?,
                mode = ?,
                source = ?,
                provider = ?,
                node_id = ?,
                generation_path = ?,
                generation_size = ?,
                generation_params_json = ?,
                output_image_path = '',
                generation_status = 'running',
                generation_task_id = ?,
                generation_output_index = ?,
                generation_error = '',
                generation_started_at = ?,
                generation_finished_at = '',
                updated_at = ?
            WHERE id = ?
            """,
            (
                prompt,
                payload.get("mode", "unspecified"),
                payload.get("source", "generated"),
                payload.get("provider"),
                validate_node_exists(conn, normalize_node_id(payload.get("node_id"))),
                payload.get("generation_path", ""),
                payload.get("generation_size", ""),
                generation_params_json(payload),
                str(task_id or ""),
                max(1, safe_int(output_index, 1)),
                timestamp,
                timestamp,
                instance_id,
            ),
        )
        if cur.rowcount == 0:
            raise KeyError(f"Instance {instance_id} not found")
        set_input_images(conn, instance_id, payload.get("input_image_paths", []))
        set_tags(conn, instance_id, payload.get("tags", []))


def get_instance(conn: sqlite3.Connection, instance_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
    if row is None:
        return None
    return hydrate_instance(conn, row)


def delete_instance(conn: sqlite3.Connection, instance_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM instances WHERE id = ?", (instance_id,))


def batch_add_tags(conn: sqlite3.Connection, ids: list[int], tags: list[str]) -> int:
    instance_ids = existing_instance_ids(conn, normalize_instance_ids(ids))
    tag_names = [
        tag
        for tag in normalize_tags(tags)
        if tag != UNTAGGED_FILTER
    ]
    if not instance_ids or not tag_names:
        return 0
    with conn:
        for instance_id in instance_ids:
            for name in tag_names:
                conn.execute(
                    "INSERT OR IGNORE INTO instance_tags(instance_id, tag_id) VALUES (?, ?)",
                    (instance_id, tag_id(conn, name)),
                )
    return len(instance_ids)


def add_instance_tags(conn: sqlite3.Connection, instance_id: int, tags: list[str]) -> int:
    if not existing_instance_ids(conn, [instance_id]):
        raise KeyError(f"Instance {instance_id} not found")
    tag_names = [
        tag
        for tag in normalize_tags(tags)
        if tag != UNTAGGED_FILTER
    ]
    if not tag_names:
        return 0
    added = 0
    with conn:
        for name in tag_names:
            current_tag_id = tag_id(conn, name)
            exists = conn.execute(
                """
                SELECT 1
                FROM instance_tags
                WHERE instance_id = ? AND tag_id = ?
                """,
                (instance_id, current_tag_id),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO instance_tags(instance_id, tag_id) VALUES (?, ?)",
                (instance_id, current_tag_id),
            )
            added += 1
    return added


def batch_remove_tags(conn: sqlite3.Connection, ids: list[int], tags: list[str]) -> int:
    instance_ids = existing_instance_ids(conn, normalize_instance_ids(ids))
    tag_names = [
        tag
        for tag in normalize_tags(tags)
        if tag != UNTAGGED_FILTER
    ]
    if not instance_ids or not tag_names:
        return 0
    instance_placeholders = ",".join("?" for _ in instance_ids)
    tag_placeholders = ",".join("?" for _ in tag_names)
    rows = conn.execute(
        f"""
        SELECT DISTINCT instance_tags.instance_id
        FROM instance_tags
        JOIN tags ON tags.id = instance_tags.tag_id
        WHERE instance_tags.instance_id IN ({instance_placeholders})
          AND tags.name IN ({tag_placeholders})
        """,
        [*instance_ids, *tag_names],
    ).fetchall()
    updated = len(rows)
    with conn:
        conn.execute(
            f"""
            DELETE FROM instance_tags
            WHERE instance_id IN ({instance_placeholders})
              AND tag_id IN (
                SELECT id FROM tags WHERE name IN ({tag_placeholders})
              )
            """,
            [*instance_ids, *tag_names],
        )
    return updated


def remove_instance_tags(conn: sqlite3.Connection, instance_id: int, tags: list[str]) -> int:
    if not existing_instance_ids(conn, [instance_id]):
        raise KeyError(f"Instance {instance_id} not found")
    tag_names = [
        tag
        for tag in normalize_tags(tags)
        if tag != UNTAGGED_FILTER
    ]
    if not tag_names:
        return 0
    placeholders = ",".join("?" for _ in tag_names)
    rows = conn.execute(
        f"""
        SELECT tags.id
        FROM tags
        JOIN instance_tags ON instance_tags.tag_id = tags.id
        WHERE instance_tags.instance_id = ?
          AND tags.name IN ({placeholders})
        """,
        [instance_id, *tag_names],
    ).fetchall()
    if not rows:
        return 0
    tag_ids = [int(row["id"]) for row in rows]
    tag_placeholders = ",".join("?" for _ in tag_ids)
    with conn:
        conn.execute(
            f"""
            DELETE FROM instance_tags
            WHERE instance_id = ?
              AND tag_id IN ({tag_placeholders})
            """,
            [instance_id, *tag_ids],
        )
    return len(tag_ids)


def clear_instance_tags(conn: sqlite3.Connection, instance_id: int) -> int:
    if not existing_instance_ids(conn, [instance_id]):
        raise KeyError(f"Instance {instance_id} not found")
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM instance_tags WHERE instance_id = ?",
        (instance_id,),
    ).fetchone()
    total = int(row["total"])
    with conn:
        conn.execute("DELETE FROM instance_tags WHERE instance_id = ?", (instance_id,))
    return total


def batch_delete_instances(conn: sqlite3.Connection, ids: list[int]) -> int:
    instance_ids = existing_instance_ids(conn, normalize_instance_ids(ids))
    if not instance_ids:
        return 0
    placeholders = ",".join("?" for _ in instance_ids)
    with conn:
        conn.execute(f"DELETE FROM instances WHERE id IN ({placeholders})", instance_ids)
    return len(instance_ids)


def move_instance_to_node(
    conn: sqlite3.Connection,
    instance_id: int,
    node_id: Any,
) -> dict[str, Any]:
    normalized_node_id = validate_node_exists(conn, normalize_node_id(node_id))
    item = get_instance(conn, instance_id)
    if item is None:
        raise KeyError(f"Instance {instance_id} not found")
    if item.get("generation_status") == "running":
        raise ValueError("生成中实例不能移动节点")
    with conn:
        conn.execute(
            """
            UPDATE instances
            SET node_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (normalized_node_id, now_iso(), instance_id),
        )
    moved = get_instance(conn, instance_id)
    if moved is None:
        raise KeyError(f"Instance {instance_id} not found")
    return moved


def batch_move_instances(
    conn: sqlite3.Connection,
    ids: list[int],
    node_id: Any,
) -> int:
    instance_ids = existing_instance_ids(conn, normalize_instance_ids(ids))
    normalized_node_id = validate_node_exists(conn, normalize_node_id(node_id))
    if not instance_ids:
        return 0
    placeholders = ",".join("?" for _ in instance_ids)
    rows = conn.execute(
        f"""
        SELECT id
        FROM instances
        WHERE id IN ({placeholders})
          AND generation_status <> 'running'
        """,
        instance_ids,
    ).fetchall()
    movable_ids = [int(row["id"]) for row in rows]
    if not movable_ids:
        return 0
    movable_placeholders = ",".join("?" for _ in movable_ids)
    with conn:
        conn.execute(
            f"""
            UPDATE instances
            SET node_id = ?,
                updated_at = ?
            WHERE id IN ({movable_placeholders})
            """,
            [normalized_node_id, now_iso(), *movable_ids],
        )
    return len(movable_ids)


def list_instances(conn: sqlite3.Connection, filters: dict[str, Any]) -> dict[str, Any]:
    where = []
    params: list[Any] = []

    node_filter_type = str(filters.get("node_filter_type") or "").strip()
    if node_filter_type:
        node_id = normalize_node_id(filters.get("node_id"))
        if node_filter_type == "unassigned" and node_id is None:
            where.append("instances.node_id IS NULL")
        elif node_filter_type == "unassigned":
            validate_node_exists(conn, node_id)
            where.append("instances.node_id = ?")
            params.append(node_id)
        elif node_filter_type in {"all", "node"} and node_id is not None:
            validate_node_exists(conn, node_id)
            where.append(
                """
                instances.node_id IN (
                  WITH RECURSIVE subtree(id) AS (
                    SELECT ?
                    UNION ALL
                    SELECT nodes.id
                    FROM nodes
                    JOIN subtree ON nodes.parent_id = subtree.id
                  )
                  SELECT id FROM subtree
                )
                """
            )
            params.append(node_id)

    q = str(filters.get("q", "")).strip()
    if q:
        where.append("prompt LIKE ?")
        params.append(f"%{q}%")

    provider = str(filters.get("provider") or "all").strip()
    if provider == "__empty__":
        where.append("COALESCE(provider, '') = ''")
    elif provider and provider != "all":
        where.append("provider = ?")
        params.append(provider)

    status_where = instance_statuses_where(
        filters.get("statuses", []),
        filters.get("status", "all"),
    )
    if status_where:
        where.append(status_where)

    size = str(filters.get("size") or "all").strip()
    if size == "__empty__":
        where.append(f"{INSTANCE_SIZE_EXPR} = ''")
    elif size and size != "all":
        where.append(f"{INSTANCE_SIZE_EXPR} = ?")
        params.append(size)

    call_method = str(filters.get("call_method") or "all").strip()
    if call_method == "__empty__":
        where.append(f"{INSTANCE_CALL_METHOD_EXPR} = ''")
    elif call_method and call_method != "all":
        where.append(f"{INSTANCE_CALL_METHOD_EXPR} = ?")
        params.append(call_method)

    model = str(filters.get("model") or "all").strip()
    if model == "__empty__":
        where.append(f"{INSTANCE_MODEL_EXPR} = ''")
    elif model and model != "all":
        where.append(f"{INSTANCE_MODEL_EXPR} = ?")
        params.append(model)

    start_date = str(filters.get("start_date", "")).strip()
    if start_date:
        where.append("created_at >= ?")
        params.append(start_date)

    end_date = str(filters.get("end_date", "")).strip()
    if end_date:
        operator, end_value = end_date_filter_value(end_date)
        where.append(f"created_at {operator} ?")
        params.append(end_value)

    tag_filters = normalize_tags(filters.get("tags", []))
    if UNTAGGED_FILTER in tag_filters:
        where.append(
            """
            NOT EXISTS (
              SELECT 1
              FROM instance_tags
              WHERE instance_tags.instance_id = instances.id
            )
            """
        )
    else:
        for tag in tag_filters:
            where.append(
                """
                EXISTS (
                  SELECT 1
                  FROM instance_tags
                  JOIN tags ON tags.id = instance_tags.tag_id
                  WHERE instance_tags.instance_id = instances.id AND tags.name = ?
                )
                """
            )
            params.append(tag)

    mode_filter = str(filters.get("mode_filter", "all") or "all").strip()
    if mode_filter == "text_to_image":
        where.append(
            """
            NOT EXISTS (
              SELECT 1 FROM input_images
              WHERE input_images.instance_id = instances.id
            )
            """
        )
    elif mode_filter == "image_to_image":
        where.append(
            """
            EXISTS (
              SELECT 1 FROM input_images
              WHERE input_images.instance_id = instances.id
            )
            """
        )
    elif mode_filter == "has_output":
        where.append("COALESCE(output_image_path, '') <> '' AND generation_status <> 'running'")
    elif mode_filter == "no_output":
        where.append("COALESCE(output_image_path, '') = '' AND generation_status <> 'running'")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sort_sql, sort_params = instance_sort_sql(filters)

    formal_where_sql = where_sql
    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM instances {formal_where_sql}", params
    ).fetchone()
    total = int(count_row["total"])

    page = max(1, safe_int(filters.get("page") or 1, 1))
    per_page = safe_int(filters.get("per_page") or 50, 50)
    if per_page not in PER_PAGE_OPTIONS:
        per_page = 50
    offset = (page - 1) * per_page

    rows = conn.execute(
        f"SELECT * FROM instances {formal_where_sql} ORDER BY {sort_sql} LIMIT ? OFFSET ?",
        [*params, *sort_params, per_page, offset],
    ).fetchall()
    items = [
        hydrate_instance(conn, row, display_index=offset + index + 1)
        for index, row in enumerate(rows)
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def instance_filter_values(conn: sqlite3.Connection, expression: str, *, allow_expression: bool = False) -> list[str]:
    allowed = {"provider", "generation_status", "generation_size"}
    if not allow_expression and expression not in allowed:
        raise ValueError("保存区筛选字段无效")
    rows = conn.execute(
        f"""
        SELECT DISTINCT {expression} AS value
        FROM instances
        ORDER BY value COLLATE NOCASE ASC
        """
    ).fetchall()
    return filter_value_list(rows)


def list_successful_generation_paths(conn: sqlite3.Connection, limit: int = 20) -> list[str]:
    rows = conn.execute(
        """
        SELECT generation_path, MAX(updated_at) AS last_used_at, MAX(id) AS last_id
        FROM instances
        WHERE generation_status = 'ready'
          AND COALESCE(output_image_path, '') <> ''
          AND TRIM(COALESCE(generation_path, '')) <> ''
        GROUP BY generation_path
        ORDER BY last_used_at DESC, last_id DESC
        LIMIT ?
        """,
        (max(1, safe_int(limit, 20)),),
    ).fetchall()
    return [
        str(row["generation_path"] or "").strip()
        for row in rows
        if str(row["generation_path"] or "").strip()
    ]


def list_instance_filter_options(conn: sqlite3.Connection) -> dict[str, list[str]]:
    return {
        "providers": instance_filter_values(conn, "provider"),
        "sizes": instance_filter_values(conn, INSTANCE_SIZE_EXPR, allow_expression=True),
        "call_methods": instance_filter_values(conn, INSTANCE_CALL_METHOD_EXPR, allow_expression=True),
        "models": instance_filter_values(conn, INSTANCE_MODEL_EXPR, allow_expression=True),
        "statuses": ["running", "prepared", "failed", "generated", "other"],
    }


def list_tags(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT tags.name, COUNT(*) AS usage_count
        FROM tags
        JOIN instance_tags ON instance_tags.tag_id = tags.id
        JOIN instances ON instances.id = instance_tags.instance_id
        WHERE instances.generation_status <> 'running'
        GROUP BY tags.id, tags.name
        ORDER BY usage_count DESC, tags.name COLLATE NOCASE ASC
        """
    ).fetchall()
    return [row["name"] for row in rows]


def list_used_tags_with_counts(conn: sqlite3.Connection, query: str = "") -> list[dict[str, Any]]:
    where = [
        "instances.generation_status <> 'running'",
        "TRIM(tags.name) <> ''",
        "tags.name <> ?",
    ]
    params: list[Any] = [UNTAGGED_FILTER]
    search = str(query or "").strip()
    if search:
        where.append("LOWER(tags.name) LIKE LOWER(?)")
        params.append(f"%{search}%")
    rows = conn.execute(
        f"""
        SELECT tags.id, tags.name, COUNT(DISTINCT instances.id) AS usage_count
        FROM tags
        JOIN instance_tags ON instance_tags.tag_id = tags.id
        JOIN instances ON instances.id = instance_tags.instance_id
        WHERE {" AND ".join(where)}
        GROUP BY tags.id, tags.name
        HAVING usage_count > 0
        ORDER BY usage_count DESC, tags.name COLLATE NOCASE ASC
        """,
        params,
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "name": row["name"],
            "usage_count": int(row["usage_count"]),
        }
        for row in rows
    ]


def used_tag_with_count(conn: sqlite3.Connection, tag_id_value: Any) -> dict[str, Any]:
    try:
        current_tag_id = int(tag_id_value)
    except (TypeError, ValueError):
        raise ValueError("TAG 不存在") from None
    row = conn.execute(
        """
        SELECT tags.id, tags.name, COUNT(DISTINCT instances.id) AS usage_count
        FROM tags
        JOIN instance_tags ON instance_tags.tag_id = tags.id
        JOIN instances ON instances.id = instance_tags.instance_id
        WHERE tags.id = ?
          AND instances.generation_status <> 'running'
          AND TRIM(tags.name) <> ''
          AND tags.name <> ?
        GROUP BY tags.id, tags.name
        HAVING usage_count > 0
        """,
        (current_tag_id, UNTAGGED_FILTER),
    ).fetchone()
    if row is None:
        raise ValueError("TAG 不存在或未被使用")
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "usage_count": int(row["usage_count"]),
    }


def tag_name_exists(conn: sqlite3.Connection, name: str, exclude_tag_id: int | None = None) -> bool:
    params: list[Any] = [name]
    where = "name = ? COLLATE NOCASE"
    if exclude_tag_id is not None:
        where += " AND id <> ?"
        params.append(exclude_tag_id)
    row = conn.execute(f"SELECT 1 FROM tags WHERE {where} LIMIT 1", params).fetchone()
    return row is not None


def rename_used_tag(conn: sqlite3.Connection, tag_id_value: Any, new_name_value: Any) -> dict[str, Any]:
    new_name = normalize_real_tag_name(new_name_value)
    current = used_tag_with_count(conn, tag_id_value)
    current_tag_id = int(current["id"])
    if current["name"] == new_name:
        return current
    if tag_name_exists(conn, new_name, exclude_tag_id=current_tag_id):
        raise ValueError("TAG 名称已存在，请使用合并功能")
    with conn:
        conn.execute(
            "UPDATE tags SET name = ? WHERE id = ?",
            (new_name, current_tag_id),
        )
    return used_tag_with_count(conn, current_tag_id)


def merge_used_tags(
    conn: sqlite3.Connection,
    source_tag_ids_value: Any,
    target_tag_id_value: Any,
) -> dict[str, Any]:
    if not isinstance(source_tag_ids_value, list):
        raise ValueError("source_tag_ids 必须是列表")
    source_tag_ids = []
    for value in source_tag_ids_value:
        try:
            source_tag_id = int(value)
        except (TypeError, ValueError):
            continue
        if source_tag_id > 0 and source_tag_id not in source_tag_ids:
            source_tag_ids.append(source_tag_id)
    if not source_tag_ids:
        raise ValueError("请至少选择一个要合并的 TAG")
    try:
        target_tag_id = int(target_tag_id_value)
    except (TypeError, ValueError):
        raise ValueError("目标 TAG 不存在") from None
    if target_tag_id in source_tag_ids:
        raise ValueError("目标 TAG 不能同时作为来源 TAG")

    used_tag_with_count(conn, target_tag_id)
    for source_tag_id in source_tag_ids:
        used_tag_with_count(conn, source_tag_id)

    source_placeholders = ",".join("?" for _ in source_tag_ids)
    with conn:
        for source_tag_id in source_tag_ids:
            conn.execute(
                """
                INSERT OR IGNORE INTO instance_tags(instance_id, tag_id)
                SELECT instance_id, ? FROM instance_tags WHERE tag_id = ?
                """,
                (target_tag_id, source_tag_id),
            )
        conn.execute(
            f"DELETE FROM instance_tags WHERE tag_id IN ({source_placeholders})",
            source_tag_ids,
        )
        conn.execute(
            f"DELETE FROM tags WHERE id IN ({source_placeholders})",
            source_tag_ids,
        )

    return {
        "target": used_tag_with_count(conn, target_tag_id),
        "removed_source_ids": source_tag_ids,
    }












