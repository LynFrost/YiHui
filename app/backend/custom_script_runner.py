from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from backend.image_providers.base import ImageGenerationResult


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
CUSTOM_SCRIPT_TIMEOUT_SECONDS = 3600


def output_suffix(output_format: Any) -> str:
    clean_format = str(output_format or "png").strip().lower()
    return {
        "png": ".png",
        "jpeg": ".jpeg",
        "jpg": ".jpg",
        "webp": ".webp",
    }.get(clean_format, ".png")


def ensure_inside_output_dir(path: Path, output_dir: Path) -> None:
    try:
        path.resolve().relative_to(output_dir.resolve())
    except ValueError as exc:
        raise ValueError("输出路径必须位于生成路径内") from exc


def validate_output_paths(paths: list[str], output_dir: Path) -> list[str]:
    validated: list[str] = []
    for item in paths:
        output_path = Path(str(item or "")).expanduser()
        ensure_inside_output_dir(output_path, output_dir)
        if output_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError("自定义代码输出文件必须是图片")
        if not output_path.is_file():
            raise ValueError("自定义代码没有生成图片")
        validated.append(str(output_path))
    if not validated:
        raise ValueError("自定义代码没有生成图片")
    return validated


def read_result_payload(result_json_path: Path) -> dict[str, Any] | None:
    if not result_json_path.exists():
        return None
    try:
        payload = json.loads(result_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("自定义代码 result_json_path 不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("自定义代码 result_json_path 必须是 JSON 对象")
    return payload


def declared_output_paths(payload: dict[str, Any]) -> list[str]:
    output_paths = payload.get("output_paths")
    if not isinstance(output_paths, list):
        raise ValueError("自定义代码 output_paths 必须是列表")
    return [str(path) for path in output_paths]


def declared_retry_events(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    events = payload.get("retry_events")
    if not isinstance(events, list):
        return []
    normalized = []
    for event in events:
        if isinstance(event, dict):
            normalized.append(dict(event))
    return normalized


def wrapper_code() -> str:
    return """
from pathlib import Path
import json
import runpy
import sys

context_path = Path(sys.argv[1])
script_path = Path(sys.argv[2])

context = json.loads(context_path.read_text(encoding="utf-8"))
globals().update(context)
globals()["Path"] = Path
globals()["json"] = json

code = compile(script_path.read_text(encoding="utf-8"), str(script_path), "exec")
exec(code, globals(), globals())
"""


def run_custom_script(
    script: str,
    context: dict[str, Any],
    timeout_seconds: int = CUSTOM_SCRIPT_TIMEOUT_SECONDS,
) -> ImageGenerationResult:
    if not str(script or "").strip():
        raise ValueError("自定义代码为空")

    output_dir = Path(str(context.get("output_dir") or "")).expanduser()
    if not output_dir:
        raise ValueError("输出目录不能为空")
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = output_suffix(context.get("output_format"))
    output_path_value = str(context.get("output_path") or "").strip()
    output_path = (
        Path(output_path_value).expanduser()
        if output_path_value
        else output_dir / f"{uuid.uuid4().hex}{suffix}"
    )
    ensure_inside_output_dir(output_path, output_dir)
    if output_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("自定义代码输出文件必须是图片")
    result_json_path_value = str(context.get("result_json_path") or "").strip()
    result_json_path = (
        Path(result_json_path_value).expanduser()
        if result_json_path_value
        else output_dir / f"{output_path.stem}.result.json"
    )
    ensure_inside_output_dir(result_json_path, output_dir)

    runtime_context = dict(context)
    runtime_context["output_dir"] = str(output_dir)
    runtime_context["output_path"] = str(output_path)
    runtime_context["result_json_path"] = str(result_json_path)

    with tempfile.TemporaryDirectory(prefix="ai-image-custom-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        context_path = temp_dir / "context.json"
        script_path = temp_dir / "custom_script.py"
        wrapper_path = temp_dir / "runner.py"
        context_path.write_text(
            json.dumps(runtime_context, ensure_ascii=False),
            encoding="utf-8",
        )
        script_path.write_text(str(script), encoding="utf-8")
        wrapper_path.write_text(wrapper_code(), encoding="utf-8")

        try:
            completed = subprocess.run(
                [sys.executable, str(wrapper_path), str(context_path), str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"自定义代码执行超时（{timeout_seconds} 秒）") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        message = f"自定义代码执行失败：{detail}" if detail else "自定义代码执行失败"
        raise ValueError(message)

    result_payload = read_result_payload(result_json_path)
    output_paths = declared_output_paths(result_payload) if result_payload is not None else [str(output_path)]
    validated_paths = validate_output_paths(output_paths, output_dir)
    retry_events = declared_retry_events(result_payload)
    result_json_path.unlink(missing_ok=True)

    return ImageGenerationResult(
        output_paths=validated_paths,
        provider="custom_script",
        retry_events=retry_events,
    )
