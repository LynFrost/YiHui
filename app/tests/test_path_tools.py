import sys
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import create_instance, get_connection, init_db
from backend.path_tools import (
    apply_path_replacement,
    backup_database,
    preview_path_replacement,
)


def make_db(tmp_path: Path):
    db_path = tmp_path / "app.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    create_instance(
        conn,
        {
            "prompt": "path case",
            "mode": "text_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": r"C:\old\out.png",
            "input_image_paths": [r"C:\old\in.png", r"D:\keep\x.png"],
            "tags": [],
        },
    )
    create_instance(
        conn,
        {
            "prompt": "input only case",
            "mode": "image_to_image",
            "source": "manual",
            "provider": None,
            "generation_path": "",
            "output_image_path": r"D:\keep\out.png",
            "input_image_paths": [r"C:\old\ref.png"],
            "tags": [],
        },
    )
    return db_path, conn


def test_preview_counts_matching_instances_paths_and_examples(tmp_path):
    db_path, conn = make_db(tmp_path)

    preview = preview_path_replacement(conn, r"C:\old", r"D:\new")

    assert preview["matched_instances"] == 2
    assert preview["matched_paths"] == 3
    assert preview["examples"][0] == {
        "table": "instances",
        "id": "1",
        "before": r"C:\old\out.png",
        "after": r"D:\new\out.png",
    }
    assert preview["examples"][1]["before"] == r"C:\old\in.png"
    assert preview["examples"][1]["after"] == r"D:\new\in.png"
    assert db_path.exists()
    conn.close()


def test_preview_rejects_empty_find_text(tmp_path):
    _, conn = make_db(tmp_path)

    with pytest.raises(ValueError, match="查找内容不能为空"):
        preview_path_replacement(conn, "", r"D:\new")

    conn.close()


def test_apply_replaces_database_paths_and_creates_backup_without_touching_files(tmp_path):
    db_path, conn = make_db(tmp_path)
    backup_dir = tmp_path / "backups"
    real_image = tmp_path / "real-image.png"
    real_image.write_bytes(b"image bytes")

    result = apply_path_replacement(conn, db_path, backup_dir, r"C:\old", r"D:\new")

    assert result["matched_instances"] == 2
    assert result["matched_paths"] == 3
    backup_path = Path(result["backup_path"])
    assert backup_path.parent == backup_dir
    assert backup_path.exists()
    backup_conn = sqlite3.connect(backup_path)
    backup_row = backup_conn.execute(
        "SELECT output_image_path FROM instances WHERE id = 1"
    ).fetchone()
    assert backup_row[0] == r"C:\old\out.png"
    backup_conn.close()
    rows = conn.execute(
        "SELECT id, output_image_path FROM instances ORDER BY id"
    ).fetchall()
    assert [row["output_image_path"] for row in rows] == [
        r"D:\new\out.png",
        r"D:\keep\out.png",
    ]
    input_rows = [
        row["path"]
        for row in conn.execute("SELECT path FROM input_images ORDER BY id")
    ]
    assert input_rows == [r"D:\new\in.png", r"D:\keep\x.png", r"D:\new\ref.png"]
    assert real_image.read_bytes() == b"image bytes"
    conn.close()


def test_backup_database_never_overwrites_when_timestamp_collides(tmp_path):
    db_path, conn = make_db(tmp_path)
    conn.close()
    backup_dir = tmp_path / "backups"
    fixed_now = datetime(2026, 4, 30, 12, 0, 0, 123456)

    with patch("backend.path_tools.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        first_backup = backup_database(db_path, backup_dir)
        first_backup.write_bytes(b"first backup sentinel")
        second_backup = backup_database(db_path, backup_dir)

    assert first_backup != second_backup
    assert first_backup.read_bytes() == b"first backup sentinel"
    assert second_backup.exists()




