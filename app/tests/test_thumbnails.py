import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from backend.thumbnails import clear_thumbnail_cache, get_or_create_thumbnail


def make_app(tmp_path: Path):
    app = create_app(
        db_file=tmp_path / "data" / "test.sqlite",
        config_file=tmp_path / "config" / "config.json",
        backup_dir=tmp_path / "backup",
        export_dir=tmp_path / "export",
        thumbnail_cache_dir=tmp_path / "cache" / "thumbnails",
        auto_backup=False,
    )
    app.config.update(TESTING=True)
    return app


def write_png(path: Path, color=(255, 0, 0)) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 320), color)
    image.save(path)


def test_thumbnail_endpoint_creates_and_reuses_cache(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    source = tmp_path / "images" / "source.png"
    write_png(source)

    first_resp = client.get("/api/thumbnail", query_string={"path": str(source)})
    cached_files = list((tmp_path / "cache" / "thumbnails").glob("*.webp"))
    second_resp = client.get("/api/thumbnail", query_string={"path": str(source)})

    assert first_resp.status_code == 200
    assert first_resp.mimetype == "image/webp"
    assert len(cached_files) == 1
    assert second_resp.status_code == 200
    assert list((tmp_path / "cache" / "thumbnails").glob("*.webp")) == cached_files


def test_thumbnail_cache_key_changes_when_source_changes(tmp_path):
    app = make_app(tmp_path)
    source = tmp_path / "images" / "source.png"
    write_png(source, (255, 0, 0))

    with app.app_context():
        first_thumb = get_or_create_thumbnail(source, Path(app.config["THUMBNAIL_CACHE_DIR"]))
        write_png(source, (0, 255, 0))
        second_thumb = get_or_create_thumbnail(source, Path(app.config["THUMBNAIL_CACHE_DIR"]))

    assert first_thumb.is_file()
    assert second_thumb.is_file()
    assert first_thumb != second_thumb


def test_thumbnail_endpoint_does_not_serve_stale_cache_when_original_missing(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    source = tmp_path / "images" / "source.png"
    write_png(source)

    assert client.get("/api/thumbnail", query_string={"path": str(source)}).status_code == 200
    cached_files = list((tmp_path / "cache" / "thumbnails").glob("*.webp"))
    source.unlink()
    missing_resp = client.get("/api/thumbnail", query_string={"path": str(source)})

    assert cached_files
    assert missing_resp.status_code == 404
    assert missing_resp.get_json()["error"] == "图片未找到"


def test_clear_thumbnail_cache_removes_only_cache_files(tmp_path):
    app = make_app(tmp_path)
    source = tmp_path / "images" / "source.png"
    write_png(source)

    with app.app_context():
        thumb = get_or_create_thumbnail(source, Path(app.config["THUMBNAIL_CACHE_DIR"]))
        result = clear_thumbnail_cache(Path(app.config["THUMBNAIL_CACHE_DIR"]))

    assert source.is_file()
    assert not thumb.exists()
    assert result["deleted_count"] == 1
    assert result["deleted_bytes"] > 0


def test_thumbnail_clear_endpoint_reports_cache_stats(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    source = tmp_path / "images" / "source.png"
    write_png(source)
    client.get("/api/thumbnail", query_string={"path": str(source)})

    stats_before = client.get("/api/thumbnails/stats").get_json()
    clear_resp = client.post("/api/thumbnails/clear")
    stats_after = client.get("/api/thumbnails/stats").get_json()

    assert stats_before["file_count"] == 1
    assert clear_resp.status_code == 200
    assert clear_resp.get_json()["deleted_count"] == 1
    assert source.is_file()
    assert stats_after["file_count"] == 0




