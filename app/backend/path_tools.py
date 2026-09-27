from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


PathMatch = tuple[str, int, str, int]


def normalize_replacement(find_text: str, replace_text: str) -> tuple[str, str]:
    normalized_find = "" if find_text is None else str(find_text)
    normalized_replace = "" if replace_text is None else str(replace_text)
    if not normalized_find:
        raise ValueError("查找内容不能为空")
    return normalized_find, normalized_replace


def matching_paths(conn: sqlite3.Connection, find_text: str) -> list[PathMatch]:
    rows: list[PathMatch] = []
    for row in conn.execute(
        "SELECT id, output_image_path FROM instances ORDER BY id"
    ).fetchall():
        path = row["output_image_path"]
        if path and find_text in path:
            rows.append(("instances", int(row["id"]), path, int(row["id"])))

    for row in conn.execute(
        "SELECT id, instance_id, path FROM input_images ORDER BY id"
    ).fetchall():
        path = row["path"]
        if path and find_text in path:
            rows.append(("input_images", int(row["id"]), path, int(row["instance_id"])))
    return rows


def replacement_examples(
    paths: list[PathMatch], find_text: str, replace_text: str
) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for table_name, row_id, path, _instance_id in paths[:8]:
        examples.append(
            {
                "table": table_name,
                "id": str(row_id),
                "before": path,
                "after": path.replace(find_text, replace_text),
            }
        )
    return examples


def preview_path_replacement(
    conn: sqlite3.Connection, find_text: str, replace_text: str
) -> dict[str, Any]:
    find_text, replace_text = normalize_replacement(find_text, replace_text)

    rows = matching_paths(conn, find_text)
    return {
        "matched_instances": len({instance_id for *_rest, instance_id in rows}),
        "matched_paths": len(rows),
        "examples": replacement_examples(rows, find_text, replace_text),
    }


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backup_dir / f"AIImageManager-backup-{stamp}.sqlite"
    suffix = 1
    while backup_path.exists():
        backup_path = backup_dir / f"AIImageManager-backup-{stamp}-{suffix}.sqlite"
        suffix += 1
    source_conn = sqlite3.connect(db_path)
    backup_conn = sqlite3.connect(backup_path)
    try:
        source_conn.backup(backup_conn)
    finally:
        backup_conn.close()
        source_conn.close()
    return backup_path


def apply_path_replacement(
    conn: sqlite3.Connection,
    db_path: Path,
    backup_dir: Path,
    find_text: str,
    replace_text: str,
) -> dict[str, Any]:
    find_text, replace_text = normalize_replacement(find_text, replace_text)
    preview = preview_path_replacement(conn, find_text, replace_text)
    backup_path = backup_database(db_path, backup_dir)
    rows = matching_paths(conn, find_text)

    with conn:
        for table_name, row_id, path, instance_id in rows:
            replaced_path = path.replace(find_text, replace_text)
            if table_name == "instances":
                conn.execute(
                    """
                    UPDATE instances
                    SET output_image_path = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (replaced_path, datetime.now().replace(microsecond=0).isoformat(), row_id),
                )
            else:
                conn.execute(
                    "UPDATE input_images SET path = ? WHERE id = ?",
                    (replaced_path, row_id),
                )
                conn.execute(
                    "UPDATE instances SET updated_at = ? WHERE id = ?",
                    (datetime.now().replace(microsecond=0).isoformat(), instance_id),
                )

    return {**preview, "backup_path": str(backup_path)}
