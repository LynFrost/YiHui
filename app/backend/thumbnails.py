from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from backend.backup import size_label


THUMBNAIL_MAX_EDGE = 384
THUMBNAIL_QUALITY = 80
THUMBNAIL_FORMAT = "WEBP"
THUMBNAIL_SUFFIX = ".webp"
THUMBNAIL_VERSION = "v1-webp-384"


def thumbnail_cache_dir(default_root: Path) -> Path:
    cache_dir = Path(default_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def source_signature(source_path: Path) -> str:
    stat = source_path.stat()
    raw = "\n".join(
        [
            str(source_path.resolve()),
            str(stat.st_size),
            str(stat.st_mtime_ns),
            THUMBNAIL_VERSION,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def thumbnail_path_for_source(source_path: str | Path, cache_dir: str | Path) -> Path:
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError("图片未找到")
    return thumbnail_cache_dir(Path(cache_dir)) / f"{source_signature(source)}{THUMBNAIL_SUFFIX}"


def create_thumbnail(source_path: Path, destination: Path) -> None:
    from PIL import Image, ImageOps

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.tmp.{os.getpid()}")
    try:
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(temporary, THUMBNAIL_FORMAT, quality=THUMBNAIL_QUALITY)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def get_or_create_thumbnail(source_path: str | Path, cache_dir: str | Path) -> Path:
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError("图片未找到")
    destination = thumbnail_path_for_source(source, cache_dir)
    if destination.is_file():
        return destination
    create_thumbnail(source, destination)
    return destination


def thumbnail_cache_stats(cache_dir: str | Path) -> dict[str, Any]:
    directory = thumbnail_cache_dir(Path(cache_dir))
    files = [path for path in directory.iterdir() if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in files)
    return {
        "file_count": len(files),
        "size_bytes": total_bytes,
        "size_label": size_label(total_bytes),
        "path": str(directory),
    }


def clear_thumbnail_cache(cache_dir: str | Path) -> dict[str, Any]:
    directory = thumbnail_cache_dir(Path(cache_dir))
    deleted_count = 0
    deleted_bytes = 0
    failed_count = 0
    for path in list(directory.iterdir()):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
            path.unlink()
        except OSError:
            failed_count += 1
            continue
        deleted_count += 1
        deleted_bytes += size
    return {
        "deleted_count": deleted_count,
        "deleted_bytes": deleted_bytes,
        "deleted_size_label": size_label(deleted_bytes),
        "failed_count": failed_count,
        **thumbnail_cache_stats(directory),
    }
