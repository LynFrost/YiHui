from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import re
import subprocess
import time
import threading
import uuid

from flask import Blueprint, current_app, jsonify, request, send_file

from backend.backup import (
    build_export_payload,
    create_backup,
    detect_restore_file_type,
    export_data_package,
    export_json,
    list_backups,
    open_backup_folder,
    preview_restore_file,
    restore_backup,
    restore_data_package,
    restore_export_json,
    restore_export_payload,
)
from backend.config import (
    SIZE_MAP,
    aspect_ratio_for_size,
    load_config,
    normalize_config,
    save_config,
    size_for_aspect_ratio,
)
from backend.database import (
    add_instance_tags,
    batch_add_tags,
    batch_delete_instances,
    batch_move_instances,
    batch_remove_tags,
    cleanup_generation_history,
    clear_instance_tags,
    create_generation_history,
    create_instance,
    create_node,
    delete_node,
    delete_instance,
    finish_generation_history,
    get_connection,
    get_instance,
    list_generation_history,
    list_generation_history_filter_options,
    list_instance_filter_options,
    list_nodes,
    list_successful_generation_paths,
    list_tags,
    list_used_tags_with_counts,
    list_instances,
    merge_used_tags,
    move_instance_to_node,
    now_iso,
    prepare_instance_for_generation,
    preview_generation_history_cleanup,
    remove_instance_tags,
    rename_used_tag,
    rename_node,
    reorder_nodes,
    update_instance,
    update_instance_generation_status,
    update_instance_output_image,
)
from backend.file_dialogs import (
    choose_backup_file,
    choose_directory,
    choose_images,
    clipboard_image_paths,
)
from backend.custom_script_runner import CUSTOM_SCRIPT_TIMEOUT_SECONDS, run_custom_script
from backend.image_generation import (
    generate_image,
    provider_from_config,
    validate_adapter_supported,
)
from backend.path_tools import apply_path_replacement, preview_path_replacement
from backend.thumbnails import (
    clear_thumbnail_cache,
    get_or_create_thumbnail,
    thumbnail_cache_stats,
)


api = Blueprint("api", __name__, url_prefix="/api")
JSON_OBJECT_ERROR = "请求体必须是 JSON 对象"
SIZE_PATTERN = re.compile(r"^[1-9][0-9]*x[1-9][0-9]*$")
SHARED_FILES_DIR = Path(__file__).resolve().parents[2] / "files"
OPENAI_TEXT_SCRIPT = SHARED_FILES_DIR / "openai_text_to_image.py"
OPENAI_IMAGE_SCRIPT = SHARED_FILES_DIR / "openai_image_to_image.py"
GOOGLE_B2_TEXT_SCRIPT = SHARED_FILES_DIR / "google_b2_text_to_image_xiaoyun.py"
GOOGLE_B2_IMAGE_SCRIPT = SHARED_FILES_DIR / "google_b2_image_to_image_xiaoyun.py"
SYSRV_GOOGLE_TEXT_SCRIPT = SHARED_FILES_DIR / "google_b2_text_to_image_sysrv.py"
SYSRV_GOOGLE_IMAGE_SCRIPT = SHARED_FILES_DIR / "google_b2_image_to_image_sysrv.py"
APIMART_OPENAI_TEXT_SCRIPT = SHARED_FILES_DIR / "openai_text_to_image_apimart.py"
APIMART_OPENAI_IMAGE_SCRIPT = SHARED_FILES_DIR / "openai_image_to_image_apimart.py"
FALLBACK_SIZE = "1024x1024"
FALLBACK_RESOLUTION = "1K"
DATA_LOCK = threading.Lock()
RESTORE_IN_PROGRESS = False
ACTIVE_GENERATION_COUNT = 0
EXPORT_TASKS: dict[str, dict] = {}
EXPORT_TASK_LOCK = threading.Lock()
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
GENERATION_RETRY_DELAYS = [10, 30, 60, 120]
GENERATION_RETRY_MAX_ATTEMPTS = 4
CANCELLED_GENERATION_TASKS: set[str] = set()
CANCELLED_GENERATION_LOCK = threading.Lock()
GENERATION_PROVIDER_LOCKS: dict[str, threading.Lock] = {}
GENERATION_PROVIDER_LOCKS_LOCK = threading.Lock()


class JsonObjectError(ValueError):
    pass


def db():
    return get_connection(current_app.config["DB_FILE"])


def begin_generation() -> None:
    global ACTIVE_GENERATION_COUNT
    with DATA_LOCK:
        if RESTORE_IN_PROGRESS:
            raise RuntimeError("正在恢复备份，暂时不能生成")
        ACTIVE_GENERATION_COUNT += 1


def end_generation() -> None:
    global ACTIVE_GENERATION_COUNT
    with DATA_LOCK:
        ACTIVE_GENERATION_COUNT = max(0, ACTIVE_GENERATION_COUNT - 1)


def begin_restore() -> None:
    global RESTORE_IN_PROGRESS
    with DATA_LOCK:
        if RESTORE_IN_PROGRESS:
            raise RuntimeError("已有恢复任务正在进行")
        if ACTIVE_GENERATION_COUNT > 0:
            raise RuntimeError("当前有生成任务正在进行，不能恢复备份")
        RESTORE_IN_PROGRESS = True


def end_restore() -> None:
    global RESTORE_IN_PROGRESS
    with DATA_LOCK:
        RESTORE_IN_PROGRESS = False


def payload_json() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise JsonObjectError(JSON_OBJECT_ERROR)
    return data


def optional_payload_json() -> dict:
    if not request.get_data(cache=True):
        return {}
    return payload_json()


def requested_tags() -> list[str]:
    tags: list[str] = []
    for value in request.args.getlist("tags"):
        tags.extend(part.strip() for part in value.split(",") if part.strip())
    return tags


def requested_ids(data: dict) -> list[int]:
    ids = data.get("ids")
    if not isinstance(ids, list):
        raise ValueError("ids 必须是列表")
    normalized: list[int] = []
    seen: set[int] = set()
    for value in ids:
        try:
            instance_id = int(value)
        except (TypeError, ValueError):
            continue
        if instance_id > 0 and instance_id not in seen:
            seen.add(instance_id)
            normalized.append(instance_id)
    if not normalized:
        raise ValueError("请至少选择一个实例")
    return normalized


def requested_body_tags(data: dict) -> list[str]:
    tags = data.get("tags")
    if not isinstance(tags, list):
        raise ValueError("tags 必须是列表")
    normalized = [str(tag).strip() for tag in tags if str(tag).strip()]
    if not normalized:
        raise ValueError("请至少选择一个 TAG")
    return normalized


def optional_positive_int(value) -> int | None:
    if value in {None, ""}:
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def optional_node_id(value) -> int | None:
    if value in {None, ""}:
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise ValueError("节点无效") from None
    if normalized <= 0:
        raise ValueError("节点无效")
    return normalized


def public_config(config: dict) -> dict:
    return deepcopy(config)


def normalize_path_history(paths, limit: int = 20) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in paths if isinstance(paths, list) else []:
        path = str(item or "").strip()
        if not path or path in seen:
            continue
        normalized.append(path)
        seen.add(path)
        if len(normalized) >= limit:
            break
    return normalized


PROVIDER_FIELD_HISTORY_FIELDS = ("api_key_env", "model", "user_agent")


def normalize_provider_history_values(values, limit: int = 20) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values if isinstance(values, list) else []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
        if len(normalized) >= limit:
            break
    return normalized


def merge_provider_history_values(*sources, limit: int = 20) -> list[str]:
    merged: list[str] = []
    for source in sources:
        merged.extend(normalize_provider_history_values(source, limit=limit))
    return normalize_provider_history_values(merged, limit=limit)


def provider_config_field_values(field: str, config: dict | None = None) -> list[str]:
    if field not in PROVIDER_FIELD_HISTORY_FIELDS:
        return []
    app_config = config or current_app.config["APP_CONFIG"]
    values: list[str] = []
    for provider in (app_config.get("providers") or {}).values():
        if isinstance(provider, dict):
            values.append(provider.get(field, ""))
    return normalize_provider_history_values(values)


def shared_provider_field_history() -> dict[str, list[str]]:
    app_config = current_app.config["APP_CONFIG"]
    configured = app_config.get("provider_field_history") or {}
    return {
        field: merge_provider_history_values(
            configured.get(field, []) if isinstance(configured, dict) else [],
            provider_config_field_values(field, app_config),
        )
        for field in PROVIDER_FIELD_HISTORY_FIELDS
    }


def save_provider_field_history(history: dict[str, list[str]]) -> dict[str, list[str]]:
    with DATA_LOCK:
        config = load_current_config()
        existing = config.get("provider_field_history") or {}
        next_history: dict[str, list[str]] = {}
        for field in PROVIDER_FIELD_HISTORY_FIELDS:
            submitted = history.get(field, []) if isinstance(history, dict) else []
            current = existing.get(field, []) if isinstance(existing, dict) else []
            next_history[field] = merge_provider_history_values(submitted, current)
        config["provider_field_history"] = next_history
        config = normalize_config(config)
        save_config(current_app.config["CONFIG_FILE"], config)
        current_app.config["APP_CONFIG"] = config
    return shared_provider_field_history()


def record_successful_provider_field_history(provider_config: dict) -> None:
    if not isinstance(provider_config, dict):
        return
    current = current_app.config["APP_CONFIG"].get("provider_field_history", {})
    next_history: dict[str, list[str]] = {}
    for field in PROVIDER_FIELD_HISTORY_FIELDS:
        current_values = current.get(field, []) if isinstance(current, dict) else []
        next_history[field] = merge_provider_history_values([provider_config.get(field, "")], current_values)
    save_provider_field_history(next_history)


def merge_path_history(*sources, limit: int = 20) -> list[str]:
    merged: list[str] = []
    for source in sources:
        merged.extend(normalize_path_history(source, limit=limit))
    return normalize_path_history(merged, limit=limit)


def shared_generation_path_history(conn=None) -> list[str]:
    app_config = current_app.config["APP_CONFIG"]
    config_paths = normalize_path_history(app_config.get("generation_path_history", []))
    close_conn = False
    if conn is None:
        conn = db()
        close_conn = True
    try:
        instance_paths = list_successful_generation_paths(conn, limit=20)
    finally:
        if close_conn:
            conn.close()
    return merge_path_history(config_paths, instance_paths)


def save_generation_path_history(paths: list[str]) -> list[str]:
    with DATA_LOCK:
        config = load_current_config()
        config["generation_path_history"] = normalize_path_history(paths)
        config = normalize_config(config)
        save_config(current_app.config["CONFIG_FILE"], config)
        current_app.config["APP_CONFIG"] = config
    conn = db()
    try:
        return shared_generation_path_history(conn)
    finally:
        conn.close()


def record_successful_generation_path(path: str) -> None:
    clean_path = str(path or "").strip()
    if not clean_path:
        return
    current = current_app.config["APP_CONFIG"].get("generation_path_history", [])
    save_generation_path_history(merge_path_history([clean_path], current))


def backup_dir() -> Path:
    return Path(current_app.config["BACKUP_DIR"])


def export_dir() -> Path:
    return Path(current_app.config["EXPORT_DIR"])


def thumbnail_dir() -> Path:
    return Path(current_app.config["THUMBNAIL_CACHE_DIR"])


def app_version() -> str:
    return str(current_app.config.get("APP_VERSION") or "V0.73")


def _exception_text(exc: Exception) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(str(current))
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return "\n".join(part for part in parts if part)


def retry_after_seconds(exc: Exception) -> int | None:
    for attr in ("retry_after", "retry_after_seconds"):
        value = getattr(exc, attr, None)
        if value is None:
            continue
        try:
            seconds = int(float(value))
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return min(seconds, 600)

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        value = None
        try:
            value = headers.get("retry-after") or headers.get("Retry-After")
        except Exception:
            value = None
        if value:
            try:
                seconds = int(float(value))
            except (TypeError, ValueError):
                seconds = 0
            if seconds > 0:
                return min(seconds, 600)

    text = _exception_text(exc)
    match = re.search(r"['\"]?retry_after['\"]?\s*[:=]\s*([0-9]+)", text)
    if match:
        return min(int(match.group(1)), 600)
    return None


def retryable_status_code(exc: Exception) -> int | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for attr in ("status_code", "code"):
            value = getattr(current, attr, None)
            try:
                status_code = int(value)
            except (TypeError, ValueError):
                continue
            if status_code in RETRYABLE_STATUS_CODES:
                return status_code
        response = getattr(current, "response", None)
        value = getattr(response, "status_code", None)
        try:
            status_code = int(value)
        except (TypeError, ValueError):
            status_code = 0
        if status_code in RETRYABLE_STATUS_CODES:
            return status_code
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)

    text = _exception_text(exc).lower()
    for status_code in RETRYABLE_STATUS_CODES:
        if re.search(rf"\b{status_code}\b", text):
            return status_code
    return None


def is_retryable_generation_error(exc: Exception) -> bool:
    if isinstance(exc, subprocess.TimeoutExpired):
        return False
    if retryable_status_code(exc) is not None:
        return True
    text = _exception_text(exc).lower()
    if "自定义代码执行超时" in text:
        return False
    retryable_markers = [
        "retryable': true",
        '"retryable": true',
        "bad gateway",
        "origin_bad_gateway",
        "gateway timeout",
        "service unavailable",
        "too many requests",
        "rate limit",
        "timed out",
        "timeout",
        "connecttimeout",
        "readtimeout",
        "apiterror",
        "apitimeouterror",
        "connection error",
        "connection reset",
        "temporarily unavailable",
    ]
    return any(marker in text for marker in retryable_markers)


def retry_delay_for_attempt(attempt: int, exc: Exception) -> int:
    explicit = retry_after_seconds(exc)
    if explicit is not None:
        return explicit
    index = min(max(0, attempt - 1), len(GENERATION_RETRY_DELAYS) - 1)
    return GENERATION_RETRY_DELAYS[index]


def retry_error_message(exc: Exception) -> str:
    text = _exception_text(exc).strip()
    if not text:
        return type(exc).__name__
    return text[-4000:]


def cancel_generation_task(task_id: str) -> None:
    clean_id = str(task_id or "").strip()
    if not clean_id:
        return
    with CANCELLED_GENERATION_LOCK:
        CANCELLED_GENERATION_TASKS.add(clean_id)


def clear_cancelled_generation_task(task_id: str) -> None:
    clean_id = str(task_id or "").strip()
    if not clean_id:
        return
    with CANCELLED_GENERATION_LOCK:
        CANCELLED_GENERATION_TASKS.discard(clean_id)


def is_generation_task_cancelled(task_id: str) -> bool:
    clean_id = str(task_id or "").strip()
    if not clean_id:
        return False
    with CANCELLED_GENERATION_LOCK:
        return clean_id in CANCELLED_GENERATION_TASKS


def provider_generation_lock(provider_key: str) -> threading.Lock:
    clean_key = str(provider_key or "__default__").strip() or "__default__"
    with GENERATION_PROVIDER_LOCKS_LOCK:
        lock = GENERATION_PROVIDER_LOCKS.get(clean_key)
        if lock is None:
            lock = threading.Lock()
            GENERATION_PROVIDER_LOCKS[clean_key] = lock
        return lock


def sleep_for_retry(task_id: str, delay_seconds: int) -> None:
    remaining = max(0, int(delay_seconds))
    while remaining > 0:
        if is_generation_task_cancelled(task_id):
            raise ValueError("生成已取消")
        time.sleep(min(1, remaining))
        remaining -= 1


def serialize_export_task(task: dict) -> dict:
    payload = dict(task)
    payload.pop("thread", None)
    return payload


def active_export_task() -> dict | None:
    with EXPORT_TASK_LOCK:
        for task in EXPORT_TASKS.values():
            if task.get("status") == "running":
                return task
    return None


def update_export_task(task_id: str, **updates) -> None:
    with EXPORT_TASK_LOCK:
        task = EXPORT_TASKS.get(task_id)
        if task is None:
            return
        task.update(updates)
        processed = float(task.get("processed_rows") or 0)
        total = float(task.get("total_rows") or 0)
        task["progress"] = 0 if total <= 0 else min(1, processed / total)


def run_export_task(
    task_id: str,
    db_file: Path,
    config_file: Path,
    export_path_dir: Path,
    version: str,
) -> None:
    def progress_callback(**updates) -> None:
        update_export_task(task_id, **updates)

    try:
        result = export_data_package(
            db_file,
            config_file,
            export_path_dir,
            version,
            progress_callback=progress_callback,
        )
        update_export_task(
            task_id,
            status="success",
            phase="完成",
            message="导出完成",
            path=result.get("path", ""),
            summary=result.get("summary", {}),
            processed_rows=1,
            total_rows=1,
            progress=1,
        )
    except Exception as exc:
        update_export_task(
            task_id,
            status="failed",
            phase="失败",
            message="导出失败",
            error=f"导出失败：{exc}",
        )


def strip_provider_default_sizes(config: dict) -> dict:
    providers = config.get("providers", {})
    if isinstance(providers, dict):
        for provider in providers.values():
            if isinstance(provider, dict):
                provider.pop("default_size", None)
    return config


def default_generation_size(app_config: dict) -> str:
    provider_name = app_config.get("active_provider")
    providers = app_config.get("providers", {})
    provider = providers.get(provider_name, {}) if isinstance(providers, dict) else {}
    if not isinstance(provider, dict):
        provider = {}
    size = str(
        app_config.get("default_size")
        or provider.get("default_size")
        or FALLBACK_SIZE
    ).strip()
    return size if SIZE_PATTERN.fullmatch(size) else FALLBACK_SIZE


def default_generation_resolution(app_config: dict) -> str:
    resolution = str(app_config.get("default_resolution") or FALLBACK_RESOLUTION).strip()
    if resolution == "custom":
        return "custom"
    return resolution or FALLBACK_RESOLUTION


def default_generation_ratio(app_config: dict) -> str:
    ratio = str(app_config.get("default_aspect_ratio") or "").strip()
    if ratio in SIZE_MAP:
        return ratio
    size = default_generation_size(app_config)
    clarity = default_generation_resolution(app_config)
    ratio = aspect_ratio_for_size(size, clarity)
    return ratio if ratio in SIZE_MAP else "1:1"


def default_generation_count(app_config: dict) -> int:
    try:
        count = int(app_config.get("default_count", 1))
    except (TypeError, ValueError):
        return 1
    return count if count >= 1 else 1


def normalize_generation_count(value) -> int:
    text = str(value).strip()
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise ValueError("生成数量必须是正整数")
    return int(text)


def normalize_generation_options(options: dict, app_config: dict) -> tuple[dict, str]:
    normalized = deepcopy(options)
    if "size" in normalized:
        submitted_size = str(normalized.get("size") or "").strip()
        if submitted_size and not SIZE_PATTERN.fullmatch(submitted_size):
            raise ValueError("尺寸格式必须是数字x数字，例如 1024x1024")
    ratio = str(normalized.get("ratio") or default_generation_ratio(app_config)).strip()
    resolution_level = str(
        normalized.get("resolution_level")
        or normalized.get("clarity")
        or normalized.get("resolution")
        or ""
    ).strip()
    if "resolution_level" in normalized and not resolution_level:
        raise ValueError("请输入自定义清晰度")
    if not resolution_level:
        resolution_level = default_generation_resolution(app_config)
    if resolution_level in {"1K", "2K", "4K"}:
        if ratio not in SIZE_MAP:
            raise ValueError("分辨率只能选择已有宽高比")
        size = size_for_aspect_ratio(ratio, resolution_level)
        if not size:
            raise ValueError("无法换算生成尺寸")
    elif resolution_level == "custom":
        size = str(normalized.get("size") or default_generation_size(app_config)).strip()
        if not SIZE_PATTERN.fullmatch(size):
            raise ValueError("尺寸格式必须是数字x数字，例如 1024x1024")
        ratio = "custom"
    else:
        raise ValueError("清晰度只能是 1K、2K、4K 或自定义")
    count_value = normalized.get("n", normalized.get("count", default_generation_count(app_config)))
    count = normalize_generation_count(count_value)
    normalized["ratio"] = ratio
    normalized["resolution_level"] = resolution_level
    normalized["resolved_size"] = size
    normalized["size"] = size
    normalized.pop("resolution", None)
    normalized["count"] = count
    normalized["n"] = count
    return normalized, size


def normalize_openai_google_generation_options(options: dict, app_config: dict) -> tuple[dict, str]:
    normalized = deepcopy(options)
    count_value = normalized.get("n", normalized.get("count", default_generation_count(app_config)))
    count = normalize_generation_count(count_value)
    normalized["ratio"] = ""
    normalized["resolution_level"] = ""
    normalized["resolved_size"] = ""
    normalized["size"] = ""
    normalized.pop("resolution", None)
    normalized["count"] = count
    normalized["n"] = count
    return normalized, ""


def normalize_no_size_single_output_generation_options(options: dict, app_config: dict) -> tuple[dict, str]:
    normalized, generation_size = normalize_openai_google_generation_options(options, app_config)
    normalized["count"] = 1
    normalized["n"] = 1
    return normalized, generation_size


def validate_input_image_paths(value, mode: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("输入图片路径必须是列表")

    paths: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("输入图片路径必须是字符串")
        paths.append(item)

    if mode == "image_to_image":
        if not paths:
            raise ValueError("图生图需要至少 1 张输入图")
        for image_path in paths:
            if not Path(image_path).is_file():
                raise ValueError(f"输入图片不存在：{image_path}")
    return paths


def active_provider_config(app_config: dict) -> tuple[str, dict]:
    provider_key = str(app_config.get("active_provider") or "").strip()
    providers = app_config.get("providers", {})
    provider_config = providers.get(provider_key, {}) if isinstance(providers, dict) else {}
    if not isinstance(provider_config, dict):
        provider_config = {}
    return provider_key, provider_config


def requested_provider_config(app_config: dict, requested_provider_key: str = "") -> tuple[str, dict]:
    provider_key = str(requested_provider_key or "").strip()
    if not provider_key:
        return active_provider_config(app_config)
    providers = app_config.get("providers", {})
    provider_config = providers.get(provider_key) if isinstance(providers, dict) else None
    if provider_config is None:
        raise ValueError(f"未知图片生成 Provider：{provider_key}")
    if not isinstance(provider_config, dict):
        provider_config = {}
    return provider_key, provider_config


def provider_call_method(provider_config: dict) -> str:
    call_method = str(provider_config.get("openai_call_method") or "gpt-image-2").strip()
    return call_method if call_method in {"gpt-image-2", "response"} else "gpt-image-2"


def provider_script_method(provider_config: dict) -> str:
    adapter = str(provider_config.get("adapter") or "").strip()
    if adapter in {"openai-google", "sysrv-google", "apimart-openai"}:
        return adapter
    return provider_call_method(provider_config)


def is_openai_google_provider(provider_config: dict) -> bool:
    return str(provider_config.get("adapter") or "").strip() == "openai-google"


def provider_uses_size(provider_config: dict) -> bool:
    return str(provider_config.get("adapter") or "").strip() not in {"openai-google", "sysrv-google"}


def provider_uses_count(provider_config: dict) -> bool:
    return str(provider_config.get("adapter") or "").strip() != "sysrv-google"


def provider_uses_google_style_params(provider_config: dict) -> bool:
    return str(provider_config.get("adapter") or "").strip() in {"openai-google", "sysrv-google"}


def google_api_params(provider_config: dict) -> dict:
    return {
        "google_role": provider_config.get("google_role", "user"),
        "google_max_tokens": provider_config.get("google_max_tokens", 4096),
        "google_temperature": provider_config.get("google_temperature", ""),
        "google_top_p": provider_config.get("google_top_p", ""),
        "google_stream": bool(provider_config.get("google_stream", False)),
        "google_stop": provider_config.get("google_stop", ""),
        "google_presence_penalty": provider_config.get("google_presence_penalty", ""),
        "google_frequency_penalty": provider_config.get("google_frequency_penalty", ""),
        "google_logit_bias": provider_config.get("google_logit_bias", ""),
        "google_user": provider_config.get("google_user", ""),
        "google_response_format": provider_config.get("google_response_format", ""),
        "google_seen": provider_config.get("google_seen", ""),
        "google_tools": provider_config.get("google_tools", ""),
        "google_tool_choice": provider_config.get("google_tool_choice", ""),
    }


def script_runtime_params(provider_config: dict) -> dict:
    return {
        "request_timeout_seconds": provider_config.get("request_timeout_seconds", 300),
        "download_timeout_seconds": provider_config.get("download_timeout_seconds", 120),
        "max_retry_attempts": provider_config.get("max_retry_attempts", 5),
        "apimart_task_timeout_seconds": provider_config.get("apimart_task_timeout_seconds", 420),
        "apimart_task_poll_interval_seconds": provider_config.get("apimart_task_poll_interval_seconds", 5),
        "input_fidelity": provider_config.get("input_fidelity", ""),
        "mask_path": provider_config.get("mask_path", ""),
    }


def provider_display_sort_label(provider_key: str, provider_config: dict) -> str:
    display_name = str(provider_config.get("display_name") or provider_key or "").strip()
    return display_name.casefold()


def provider_sort_order(app_config: dict) -> list[str]:
    providers = app_config.get("providers", {})
    if not isinstance(providers, dict):
        return []
    return [
        key
        for key, _provider in sorted(
            providers.items(),
            key=lambda item: (provider_display_sort_label(item[0], item[1] if isinstance(item[1], dict) else {}), item[0].casefold()),
        )
    ]


def generation_params_from_options(
    app_config: dict,
    options: dict,
    generation_size: str,
    provider_key: str = "",
    provider_config: dict | None = None,
) -> dict:
    if provider_config is None:
        provider_key, provider_config = requested_provider_config(app_config, provider_key)
    call_method = provider_call_method(provider_config)
    proxy_context = provider_proxy_context(provider_config)
    effective_generation_size = generation_size if provider_uses_size(provider_config) else ""
    params = {
        "provider_key": provider_key,
        "adapter": provider_config.get("adapter", ""),
        "openai_call_method": call_method,
        "model": "response" if call_method == "response" else provider_config.get("model", "gpt-image-2"),
        "ratio": options.get("ratio", ""),
        "resolution_level": options.get("resolution_level", ""),
        "resolved_size": effective_generation_size,
        "quality": provider_config.get("quality", "high"),
        "output_format": provider_config.get("output_format", "png"),
        "output_compression": provider_config.get("output_compression", 80),
        "background": provider_config.get("background", "auto"),
        "moderation": provider_config.get("moderation", "low"),
        "user": provider_config.get("user", ""),
        "user_agent": provider_config.get("user_agent", ""),
        "proxy_mode": proxy_context["proxy_mode"],
        "allow_untrusted_proxy_certificate": proxy_context["allow_untrusted_proxy_certificate"],
        "n": options.get("n", options.get("count", 1)),
        "custom_script_used": False,
    }
    if provider_uses_google_style_params(provider_config):
        params.update(google_api_params(provider_config))
    params.update(script_runtime_params(provider_config))
    return params


def custom_script_for_generation(provider_config: dict, mode: str) -> str:
    call_method = provider_script_method(provider_config)
    scripts = provider_config.get("custom_scripts")
    if not isinstance(scripts, dict):
        return ""
    method_scripts = scripts.get(call_method)
    if not isinstance(method_scripts, dict):
        return ""
    return str(method_scripts.get(mode) or "").strip()


def default_openai_script_for_generation(provider_config: dict, mode: str) -> Path | None:
    adapter = str(provider_config.get("adapter") or "").strip()
    if adapter != "openai" or provider_call_method(provider_config) != "gpt-image-2":
        return None
    if mode == "text_to_image":
        return OPENAI_TEXT_SCRIPT
    if mode == "image_to_image":
        return OPENAI_IMAGE_SCRIPT
    return None


def default_shared_script_for_generation(provider_config: dict, mode: str) -> Path | None:
    adapter = str(provider_config.get("adapter") or "").strip()
    if adapter == "openai-google":
        if mode == "text_to_image":
            return GOOGLE_B2_TEXT_SCRIPT
        if mode == "image_to_image":
            return GOOGLE_B2_IMAGE_SCRIPT
        return None
    if adapter == "sysrv-google":
        if mode == "text_to_image":
            return SYSRV_GOOGLE_TEXT_SCRIPT
        if mode == "image_to_image":
            return SYSRV_GOOGLE_IMAGE_SCRIPT
        return None
    if adapter == "apimart-openai":
        if mode == "text_to_image":
            return APIMART_OPENAI_TEXT_SCRIPT
        if mode == "image_to_image":
            return APIMART_OPENAI_IMAGE_SCRIPT
        return None
    return default_openai_script_for_generation(provider_config, mode)


def api_key_for_provider(provider_config: dict) -> str:
    api_key = str(provider_config.get("api_key") or "").strip()
    if api_key:
        return api_key
    env_name = str(provider_config.get("api_key_env") or "").strip()
    return os.getenv(env_name, "") if env_name else ""


def provider_proxy_context(provider_config: dict) -> dict:
    proxy_mode = str(provider_config.get("proxy_mode") or "system").strip()
    if proxy_mode not in {"system", "custom", "none"}:
        proxy_mode = "system"
    proxy_url = str(provider_config.get("proxy_url") or "").strip()
    allow_untrusted = provider_config.get("allow_untrusted_proxy_certificate")
    if isinstance(allow_untrusted, bool):
        allow_untrusted_proxy_certificate = allow_untrusted
    elif allow_untrusted is None:
        allow_untrusted_proxy_certificate = True
    else:
        allow_untrusted_proxy_certificate = str(allow_untrusted).strip().lower() in {"1", "true", "yes", "on"}
    if proxy_mode == "custom":
        return {
            "proxy_mode": "custom",
            "use_system_proxy": True,
            "system_proxy": proxy_url,
            "allow_untrusted_proxy_certificate": allow_untrusted_proxy_certificate,
        }
    if proxy_mode == "none":
        return {
            "proxy_mode": "none",
            "use_system_proxy": False,
            "system_proxy": "",
            "allow_untrusted_proxy_certificate": allow_untrusted_proxy_certificate,
        }
    return {
        "proxy_mode": "system",
        "use_system_proxy": True,
        "system_proxy": "",
        "allow_untrusted_proxy_certificate": allow_untrusted_proxy_certificate,
    }


def custom_script_context(
    provider_config: dict,
    mode: str,
    prompt: str,
    input_image_paths: list[str],
    output_dir: str,
    options: dict,
) -> dict:
    call_method = provider_call_method(provider_config)
    effective_resolved_size = (
        options.get("resolved_size") or options.get("size") or ""
    ) if provider_uses_size(provider_config) else ""
    output_format = provider_config.get("output_format", "png")
    suffix = {
        "png": ".png",
        "jpeg": ".jpeg",
        "jpg": ".jpg",
        "webp": ".webp",
    }.get(str(output_format or "png").strip().lower(), ".png")
    output_path = Path(output_dir) / f"{uuid.uuid4().hex}{suffix}"
    result_json_path = output_path.with_suffix(f"{output_path.suffix}.result.json")
    context = {
        "base_url": provider_config.get("base_url") or "",
        "api_key": api_key_for_provider(provider_config),
        "model": "response" if call_method == "response" else provider_config.get("model", "gpt-image-2"),
        "operation_prompt": prompt,
        "resolved_size": effective_resolved_size,
        "n": options.get("n", options.get("count", 1)),
        "output_dir": output_dir,
        "output_path": str(output_path),
        "result_json_path": str(result_json_path),
        "input_images": list(input_image_paths),
        "mode": mode,
        "quality": provider_config.get("quality", "high"),
        "output_format": output_format,
        "output_compression": provider_config.get("output_compression", 80),
        "background": provider_config.get("background", "auto"),
        "moderation": provider_config.get("moderation", "low"),
        "user": provider_config.get("user", ""),
        "user_agent": provider_config.get("user_agent", ""),
    }
    if provider_uses_google_style_params(provider_config):
        context.update(google_api_params(provider_config))
    context.update(script_runtime_params(provider_config))
    context.update(provider_proxy_context(provider_config))
    return context


def history_params_snapshot(
    provider_key: str,
    provider_config: dict,
    options: dict | None = None,
    generation_size: str = "",
    custom_script_used: bool = False,
) -> dict:
    options = options if isinstance(options, dict) else {}
    call_method = provider_call_method(provider_config)
    proxy_context = provider_proxy_context(provider_config)
    effective_generation_size = (
        generation_size or options.get("resolved_size", "")
    ) if provider_uses_size(provider_config) else ""
    params = {
        "provider_key": provider_key,
        "adapter": provider_config.get("adapter", ""),
        "openai_call_method": call_method,
        "ratio": options.get("ratio", ""),
        "resolution_level": options.get("resolution_level", ""),
        "resolved_size": effective_generation_size,
        "n": options.get("n", options.get("count", "")),
        "quality": provider_config.get("quality", "high"),
        "output_format": provider_config.get("output_format", "png"),
        "output_compression": provider_config.get("output_compression", 80),
        "background": provider_config.get("background", "auto"),
        "moderation": provider_config.get("moderation", "low"),
        "user": provider_config.get("user", ""),
        "user_agent": provider_config.get("user_agent", ""),
        "proxy_mode": proxy_context["proxy_mode"],
        "allow_untrusted_proxy_certificate": proxy_context["allow_untrusted_proxy_certificate"],
        "model": "response" if call_method == "response" else provider_config.get("model", "gpt-image-2"),
        "custom_script_used": custom_script_used,
    }
    if provider_uses_google_style_params(provider_config):
        params.update(google_api_params(provider_config))
    params.update(script_runtime_params(provider_config))
    return params


def create_generate_history_record(
    conn,
    app_config: dict,
    data: dict,
    output_dir: str,
    options: dict | None = None,
    provider_key: str = "",
    provider_config: dict | None = None,
) -> int | None:
    try:
        if provider_config is None:
            provider_key, provider_config = requested_provider_config(app_config, provider_key)
        return create_generation_history(
            conn,
            {
                "prompt": str(data.get("prompt", "")).strip(),
                "mode": str(data.get("mode", "text_to_image")),
                "provider_key": provider_key,
                "adapter": provider_config.get("adapter", ""),
                "openai_call_method": provider_call_method(provider_config),
                "generation_path": output_dir,
                "resolved_size": "",
                "params": history_params_snapshot(provider_key, provider_config, options),
                "input_image_paths": data.get("input_image_paths", []),
                "tags": data.get("tags", []),
                "custom_script_used": False,
            },
        )
    except Exception:
        return None


def finish_generate_history_record(conn, history_id: int | None, payload: dict) -> None:
    try:
        finish_generation_history(conn, history_id, payload)
    except Exception:
        return


def create_retry_history_record(
    conn,
    *,
    app_config: dict,
    data: dict,
    output_dir: str,
    options: dict,
    generation_size: str,
    generation_params: dict,
    provider_key: str = "",
    provider_config: dict | None = None,
    attempt: int,
    delay_seconds: int,
    error: Exception,
    parent_history_id: int | None,
) -> None:
    try:
        if provider_config is None:
            provider_key, provider_config = requested_provider_config(app_config, provider_key)
        params = dict(generation_params or {})
        params.update(
            {
                "retry_attempt": attempt,
                "retryable": True,
                "retry_delay_seconds": delay_seconds,
                "parent_history_id": parent_history_id,
            }
        )
        create_generation_history(
            conn,
            {
                "status": "failed",
                "prompt": str(data.get("prompt", "")).strip(),
                "mode": str(data.get("mode", "text_to_image")),
                "provider_key": provider_key,
                "adapter": provider_config.get("adapter", ""),
                "openai_call_method": provider_call_method(provider_config),
                "generation_path": output_dir,
                "resolved_size": generation_size,
                "params": params,
                "input_image_paths": data.get("input_image_paths", []),
                "output_image_paths": [],
                "tags": data.get("tags", []),
                "error_message": (
                    f"第 {attempt} 次生成失败，将在 {delay_seconds} 秒后重试："
                    f"{retry_error_message(error)}"
                ),
                "custom_script_used": generation_params.get("custom_script_used", False),
                "finished_at": now_iso(),
            },
        )
    except Exception:
        return


def create_script_retry_history_records(
    conn,
    *,
    app_config: dict,
    data: dict,
    output_dir: str,
    generation_size: str,
    generation_params: dict,
    provider_key: str = "",
    provider_config: dict | None = None,
    retry_events: list[dict],
    parent_history_id: int | None,
) -> None:
    for index, event in enumerate(retry_events or [], start=1):
        if not isinstance(event, dict):
            continue
        attempt = int(event.get("attempt") or index)
        delay_seconds = int(event.get("delay_seconds") or event.get("delay") or 0)
        error_message = str(event.get("error") or event.get("reason") or "可重试错误")
        class RetryEventError(Exception):
            pass

        create_retry_history_record(
            conn,
            app_config=app_config,
            data=data,
            output_dir=output_dir,
            options=generation_params,
            generation_size=generation_size,
            generation_params=generation_params,
            provider_key=provider_key,
            provider_config=provider_config,
            attempt=attempt,
            delay_seconds=delay_seconds,
            error=RetryEventError(error_message),
            parent_history_id=parent_history_id,
        )


def run_generation_once(
    *,
    app_config: dict,
    provider_key: str,
    provider_config: dict,
    mode: str,
    prompt: str,
    input_image_paths: list[str],
    output_dir: str,
    options: dict,
    custom_script: str,
    shared_openai_script: Path | None,
):
    if custom_script or shared_openai_script:
        return run_custom_script(
            custom_script or shared_openai_script.read_text(encoding="utf-8"),
            custom_script_context(
                provider_config,
                mode,
                prompt,
                input_image_paths,
                output_dir,
                options,
            ),
            timeout_seconds=CUSTOM_SCRIPT_TIMEOUT_SECONDS,
        )
    provider = provider_from_config(app_config, provider_key, provider_config)
    return generate_image(
        provider=provider,
        mode=mode,
        prompt=prompt,
        input_images=input_image_paths,
        output_dir=output_dir,
        options=options,
    )


@api.get("/image")
def api_get_image():
    image_path = request.args.get("path")
    if not image_path:
        return jsonify({"error": "图片未找到"}), 404

    path = Path(image_path)
    if not path.is_file():
        return jsonify({"error": "图片未找到"}), 404

    return send_file(path)


@api.get("/thumbnail")
def api_get_thumbnail():
    image_path = request.args.get("path")
    if not image_path:
        return jsonify({"error": "图片未找到"}), 404

    try:
        thumb_path = get_or_create_thumbnail(image_path, thumbnail_dir())
    except FileNotFoundError:
        return jsonify({"error": "图片未找到"}), 404
    except Exception as exc:
        return jsonify({"error": f"缩略图生成失败：{exc}"}), 500

    return send_file(thumb_path, mimetype="image/webp")


@api.get("/instances")
def api_list_instances():
    filters = {
        "q": request.args.get("q", ""),
        "tags": requested_tags(),
        "provider": request.args.get("provider", "all"),
        "status": request.args.get("status", "all"),
        "statuses": request.args.getlist("statuses"),
        "size": request.args.get("size", "all"),
        "call_method": request.args.get("call_method", "all"),
        "model": request.args.get("model", "all"),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
        "mode_filter": request.args.get("mode_filter", "all"),
        "node_filter_type": request.args.get("node_filter_type", ""),
        "node_id": request.args.get("node_id", ""),
        "sort": request.args.get("sort", "created_desc"),
        "provider_sort_order": provider_sort_order(current_app.config["APP_CONFIG"]),
        "page": request.args.get("page", "1"),
        "per_page": request.args.get("per_page", "50"),
    }
    conn = db()
    try:
        return jsonify(list_instances(conn, filters))
    finally:
        conn.close()


@api.get("/instances/filter-options")
def api_list_instance_filter_options():
    conn = db()
    try:
        return jsonify(list_instance_filter_options(conn))
    finally:
        conn.close()


@api.post("/generate/cancel")
def api_cancel_generation():
    data = payload_json()
    task_id = str(data.get("generation_task_id") or data.get("task_id") or "").strip()
    if not task_id:
        return jsonify({"error": "缺少生成任务编号"}), 400
    cancel_generation_task(task_id)
    return jsonify({"cancelled": True, "generation_task_id": task_id, "updated": 0})


@api.get("/tags")
def api_list_tags():
    conn = db()
    try:
        return jsonify({"items": list_tags(conn)})
    finally:
        conn.close()


@api.get("/tag-management")
def api_list_tag_management():
    conn = db()
    try:
        items = list_used_tags_with_counts(conn, request.args.get("q", ""))
        return jsonify({"items": items, "total": len(items)})
    finally:
        conn.close()


@api.patch("/tag-management/<int:tag_id>/rename")
def api_rename_tag_management(tag_id: int):
    conn = db()
    try:
        data = payload_json()
        item = rename_used_tag(conn, tag_id, data.get("name"))
        return jsonify({"item": item, "tags": list_tags(conn)})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/tag-management/merge")
def api_merge_tag_management():
    conn = db()
    try:
        data = payload_json()
        result = merge_used_tags(conn, data.get("source_tag_ids"), data.get("target_tag_id"))
        return jsonify({**result, "tags": list_tags(conn)})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.get("/nodes")
def api_list_nodes():
    conn = db()
    try:
        return jsonify({"items": list_nodes(conn)})
    finally:
        conn.close()


@api.post("/nodes")
def api_create_node():
    conn = db()
    try:
        data = payload_json()
        node_id = create_node(conn, data.get("parent_id"), data.get("name"))
        return jsonify({"item": {"id": node_id}, "items": list_nodes(conn)}), 201
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.patch("/nodes/<int:node_id>")
def api_rename_node(node_id: int):
    conn = db()
    try:
        data = payload_json()
        item = rename_node(conn, node_id, data.get("name"))
        return jsonify({"item": item, "items": list_nodes(conn)})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/nodes/reorder")
def api_reorder_nodes():
    conn = db()
    try:
        data = payload_json()
        return jsonify({"items": reorder_nodes(conn, data.get("parent_id"), data.get("node_ids"))})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/session-snapshot")
def api_session_snapshot():
    try:
        payload = build_export_payload(
            Path(current_app.config["DB_FILE"]),
            Path(current_app.config["CONFIG_FILE"]),
            app_version(),
        )
        return jsonify({"snapshot": payload})
    except Exception as exc:
        return jsonify({"error": f"创建会话快照失败：{exc}"}), 500


@api.post("/session-restore")
def api_session_restore():
    try:
        data = payload_json()
        snapshot = data.get("snapshot")
        if not isinstance(snapshot, dict):
            return jsonify({"error": "会话快照无效"}), 400
        result = restore_export_payload(
            Path(current_app.config["DB_FILE"]),
            Path(current_app.config["CONFIG_FILE"]),
            backup_dir(),
            snapshot,
            app_version(),
            create_pre_restore=False,
            source_info={"type": "session_snapshot"},
        )
        current_app.config["APP_CONFIG"] = load_current_config()
        return jsonify(result)
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"恢复会话快照失败：{exc}"}), 500


@api.delete("/nodes/<int:node_id>")
def api_delete_node(node_id: int):
    conn = db()
    try:
        result = delete_node(conn, node_id)
        return jsonify({"result": result, "items": list_nodes(conn)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except KeyError:
        return jsonify({"error": "节点不存在"}), 404
    finally:
        conn.close()


@api.get("/generation-history")
def api_list_generation_history():
    filters = {
        "q": request.args.get("q", ""),
        "tags": requested_tags(),
        "status": request.args.get("status", "all"),
        "provider": request.args.get("provider", "all"),
        "size": request.args.get("size", "all"),
        "mode": request.args.get("mode", "all"),
        "call_method": request.args.get("call_method", "all"),
        "model": request.args.get("model", "all"),
        "number_type": request.args.get("number_type", "all"),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
        "save_sort": request.args.get("save_sort", "created_desc"),
        "provider_sort_order": provider_sort_order(current_app.config["APP_CONFIG"]),
        "page": request.args.get("page", "1"),
        "per_page": request.args.get("per_page", "50"),
    }
    conn = db()
    try:
        return jsonify(list_generation_history(conn, filters))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.get("/generation-history/filter-options")
def api_generation_history_filter_options():
    conn = db()
    try:
        return jsonify(list_generation_history_filter_options(conn))
    finally:
        conn.close()


@api.post("/generation-history/cleanup/preview")
def api_preview_generation_history_cleanup():
    conn = db()
    try:
        return jsonify(preview_generation_history_cleanup(conn, payload_json()))
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/generation-history/cleanup/failed")
def api_cleanup_failed_generation_history():
    conn = db()
    try:
        return jsonify(cleanup_generation_history(conn, {"type": "failed"}))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/generation-history/cleanup/before-date")
def api_cleanup_generation_history_before_date():
    conn = db()
    try:
        data = payload_json()
        return jsonify(cleanup_generation_history(
            conn,
            {"type": "before_date", "before_date": data.get("before_date")},
        ))
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/instances")
def api_create_instance():
    conn = db()
    try:
        instance_id = create_instance(conn, payload_json())
        return jsonify({"item": get_instance(conn, instance_id)}), 201
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/instances/bulk")
def api_create_instances_bulk():
    conn = db()
    try:
        data = payload_json()
        items = data.get("items")
        if not isinstance(items, list):
            raise ValueError("items 必须是列表")
        created = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("items 中的每一项必须是 JSON 对象")
            instance_id = create_instance(conn, item)
            created.append(get_instance(conn, instance_id))
        return jsonify({"items": created}), 201
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.put("/instances/<int:instance_id>")
def api_update_instance(instance_id: int):
    conn = db()
    try:
        update_instance(conn, instance_id, payload_json())
        item = get_instance(conn, instance_id)
        if item is None:
            return jsonify({"error": "实例不存在"}), 404
        return jsonify({"item": item})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except KeyError:
        return jsonify({"error": "实例不存在"}), 404
    finally:
        conn.close()


@api.post("/instances/<int:instance_id>/tags/add")
def api_add_instance_tags(instance_id: int):
    conn = db()
    try:
        data = payload_json()
        add_instance_tags(conn, instance_id, requested_body_tags(data))
        item = get_instance(conn, instance_id)
        if item is None:
            return jsonify({"error": "实例不存在"}), 404
        return jsonify({"item": item, "tags": list_tags(conn)})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except KeyError:
        return jsonify({"error": "实例不存在"}), 404
    finally:
        conn.close()


@api.post("/instances/<int:instance_id>/tags/remove")
def api_remove_instance_tags(instance_id: int):
    conn = db()
    try:
        data = payload_json()
        remove_instance_tags(conn, instance_id, requested_body_tags(data))
        item = get_instance(conn, instance_id)
        if item is None:
            return jsonify({"error": "实例不存在"}), 404
        return jsonify({"item": item, "tags": list_tags(conn)})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except KeyError:
        return jsonify({"error": "实例不存在"}), 404
    finally:
        conn.close()


@api.post("/instances/<int:instance_id>/tags/clear")
def api_clear_instance_tags(instance_id: int):
    conn = db()
    try:
        clear_instance_tags(conn, instance_id)
        item = get_instance(conn, instance_id)
        if item is None:
            return jsonify({"error": "实例不存在"}), 404
        return jsonify({"item": item, "tags": list_tags(conn)})
    except KeyError:
        return jsonify({"error": "实例不存在"}), 404
    finally:
        conn.close()


@api.delete("/instances/<int:instance_id>")
def api_delete_instance(instance_id: int):
    conn = db()
    try:
        if get_instance(conn, instance_id) is None:
            return jsonify({"error": "实例不存在"}), 404
        delete_instance(conn, instance_id)
        return "", 204
    finally:
        conn.close()


@api.post("/instances/<int:instance_id>/move")
def api_move_instance(instance_id: int):
    conn = db()
    try:
        data = payload_json()
        item = move_instance_to_node(conn, instance_id, data.get("node_id"))
        return jsonify({"item": item})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except KeyError:
        return jsonify({"error": "实例不存在"}), 404
    finally:
        conn.close()


@api.post("/instances/batch/tags/add")
def api_batch_add_tags():
    conn = db()
    try:
        data = payload_json()
        updated = batch_add_tags(conn, requested_ids(data), requested_body_tags(data))
        return jsonify({"updated": updated})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/instances/batch/tags/remove")
def api_batch_remove_tags():
    conn = db()
    try:
        data = payload_json()
        updated = batch_remove_tags(conn, requested_ids(data), requested_body_tags(data))
        return jsonify({"updated": updated})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/instances/batch/move")
def api_batch_move_instances():
    conn = db()
    try:
        data = payload_json()
        updated = batch_move_instances(conn, requested_ids(data), data.get("node_id"))
        return jsonify({"updated": updated})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/instances/batch/delete")
def api_batch_delete_instances():
    conn = db()
    try:
        data = payload_json()
        deleted = batch_delete_instances(conn, requested_ids(data))
        return jsonify({"deleted": deleted})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.get("/backups")
def api_list_backups():
    return jsonify({"items": list_backups(backup_dir())})


@api.get("/thumbnails/stats")
def api_thumbnail_stats():
    return jsonify(thumbnail_cache_stats(thumbnail_dir()))


@api.post("/thumbnails/clear")
def api_clear_thumbnails():
    try:
        return jsonify(clear_thumbnail_cache(thumbnail_dir()))
    except Exception as exc:
        return jsonify({"error": f"清理缩略图缓存失败：{exc}"}), 500


@api.post("/backups")
def api_create_backup():
    try:
        data = optional_payload_json()
        backup_type = str(data.get("backup_type") or "manual")
        item = create_backup(
            Path(current_app.config["DB_FILE"]),
            Path(current_app.config["CONFIG_FILE"]),
            backup_dir(),
            app_version(),
            backup_type,
        )
        return jsonify(item), 201
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"备份失败：{exc}"}), 500


@api.post("/backups/open-folder")
def api_open_backup_folder():
    try:
        open_backup_folder(backup_dir())
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"error": f"打开备份文件夹失败：{exc}"}), 500


@api.post("/backups/choose")
def api_choose_backup():
    try:
        path = choose_backup_file(str(backup_dir()))
        return jsonify({"path": path})
    except Exception as exc:
        return jsonify({"error": f"无法打开文件选择窗口：{exc}"}), 500


@api.post("/exports")
def api_start_export():
    if active_export_task() is not None:
        return jsonify({"error": "已有导出任务正在进行"}), 409
    task_id = f"export-{uuid.uuid4().hex}"
    task = {
        "task_id": task_id,
        "status": "running",
        "phase": "准备导出",
        "message": "正在准备导出数据",
        "processed_rows": 0,
        "total_rows": 0,
        "progress": 0,
    }
    with EXPORT_TASK_LOCK:
        EXPORT_TASKS[task_id] = task
    thread = threading.Thread(
        target=run_export_task,
        args=(
            task_id,
            Path(current_app.config["DB_FILE"]),
            Path(current_app.config["CONFIG_FILE"]),
            export_dir(),
            app_version(),
        ),
        daemon=True,
    )
    task["thread"] = thread
    thread.start()
    return jsonify({"task_id": task_id, "status": "running"}), 202


@api.get("/exports/tasks/<task_id>")
def api_get_export_task(task_id: str):
    with EXPORT_TASK_LOCK:
        task = EXPORT_TASKS.get(task_id)
        if task is None:
            return jsonify({"error": "导出任务不存在"}), 404
        return jsonify(serialize_export_task(task))


@api.post("/exports/json")
def api_export_json():
    try:
        result = export_json(
            Path(current_app.config["DB_FILE"]),
            Path(current_app.config["CONFIG_FILE"]),
            export_dir(),
            app_version(),
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": f"导出失败：{exc}"}), 500


@api.post("/restore/preview")
def api_restore_preview():
    try:
        data = payload_json()
        restore_path = Path(str(data.get("path") or ""))
        return jsonify(preview_restore_file(restore_path))
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"恢复文件预览失败：{exc}"}), 500


@api.post("/restore")
def api_restore():
    try:
        data = payload_json()
        if data.get("confirmed") is not True:
            return jsonify({"error": "恢复前必须二次确认"}), 400
        restore_path = Path(str(data.get("path") or ""))
        if active_export_task() is not None:
            return jsonify({"error": "当前有导出任务正在进行，不能恢复备份"}), 409
        begin_restore()
        try:
            restore_type = detect_restore_file_type(restore_path)
            if restore_type == "zip_export":
                result = restore_data_package(
                    Path(current_app.config["DB_FILE"]),
                    Path(current_app.config["CONFIG_FILE"]),
                    backup_dir(),
                    restore_path,
                    app_version(),
                )
            elif restore_type == "json_export":
                result = restore_export_json(
                    Path(current_app.config["DB_FILE"]),
                    Path(current_app.config["CONFIG_FILE"]),
                    backup_dir(),
                    restore_path,
                    app_version(),
                )
            else:
                result = restore_backup(
                    Path(current_app.config["DB_FILE"]),
                    Path(current_app.config["CONFIG_FILE"]),
                    backup_dir(),
                    restore_path,
                    app_version(),
                )
            current_app.config["APP_CONFIG"] = load_current_config()
            return jsonify(result)
        finally:
            end_restore()
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


def load_current_config() -> dict:
    return load_config(current_app.config["CONFIG_FILE"])


@api.get("/settings")
def api_get_settings():
    return jsonify({"settings": public_config(current_app.config["APP_CONFIG"])})


@api.get("/openai-script-examples")
def api_openai_script_examples():
    return jsonify(
        {
            "text_to_image": OPENAI_TEXT_SCRIPT.read_text(encoding="utf-8"),
            "image_to_image": OPENAI_IMAGE_SCRIPT.read_text(encoding="utf-8"),
        }
    )


@api.get("/openai-google-script-examples")
def api_openai_google_script_examples():
    return jsonify(
        {
            "text_to_image": GOOGLE_B2_TEXT_SCRIPT.read_text(encoding="utf-8"),
            "image_to_image": GOOGLE_B2_IMAGE_SCRIPT.read_text(encoding="utf-8"),
        }
    )


@api.get("/shared-script-examples")
def api_shared_script_examples():
    return jsonify(
        {
            "openai": {
                "text_to_image": OPENAI_TEXT_SCRIPT.read_text(encoding="utf-8"),
                "image_to_image": OPENAI_IMAGE_SCRIPT.read_text(encoding="utf-8"),
            },
            "openai-google": {
                "text_to_image": GOOGLE_B2_TEXT_SCRIPT.read_text(encoding="utf-8"),
                "image_to_image": GOOGLE_B2_IMAGE_SCRIPT.read_text(encoding="utf-8"),
            },
            "sysrv-google": {
                "text_to_image": SYSRV_GOOGLE_TEXT_SCRIPT.read_text(encoding="utf-8"),
                "image_to_image": SYSRV_GOOGLE_IMAGE_SCRIPT.read_text(encoding="utf-8"),
            },
            "apimart-openai": {
                "text_to_image": APIMART_OPENAI_TEXT_SCRIPT.read_text(encoding="utf-8"),
                "image_to_image": APIMART_OPENAI_IMAGE_SCRIPT.read_text(encoding="utf-8"),
            },
        }
    )


@api.get("/generation-path-history")
def api_get_generation_path_history():
    conn = db()
    try:
        return jsonify({"paths": shared_generation_path_history(conn)})
    finally:
        conn.close()


@api.post("/generation-path-history")
def api_save_generation_path_history():
    try:
        data = payload_json()
        submitted_paths: list[str] = []
        if isinstance(data.get("paths"), list):
            submitted_paths.extend(data.get("paths") or [])
        if "path" in data:
            submitted_paths.insert(0, data.get("path"))
        current = current_app.config["APP_CONFIG"].get("generation_path_history", [])
        paths = merge_path_history(submitted_paths, current)
        return jsonify({"paths": save_generation_path_history(paths)})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400


@api.get("/provider-field-history")
def api_get_provider_field_history():
    return jsonify({"history": shared_provider_field_history()})


@api.post("/provider-field-history")
def api_save_provider_field_history():
    try:
        data = payload_json()
        submitted = data.get("history")
        if not isinstance(submitted, dict):
            submitted = {}
            for field in PROVIDER_FIELD_HISTORY_FIELDS:
                if field in data:
                    submitted[field] = data.get(field)
        return jsonify({"history": save_provider_field_history(submitted)})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400


@api.put("/settings")
def api_update_settings():
    try:
        submitted = payload_json()
        existing_config = current_app.config["APP_CONFIG"]
        if "default_size" not in submitted:
            submitted["default_size"] = existing_config.get(
                "default_size",
                default_generation_size(existing_config),
            )
        if "default_resolution" not in submitted:
            submitted["default_resolution"] = existing_config.get(
                "default_resolution",
                default_generation_resolution(existing_config),
            )
        if "default_custom_resolution" not in submitted:
            submitted["default_custom_resolution"] = existing_config.get(
                "default_custom_resolution",
                "",
            )
        if (
            "default_resolution" in submitted
            and submitted.get("default_resolution") != existing_config.get("default_resolution")
            and submitted.get("default_clarity") == existing_config.get("default_clarity")
        ):
            submitted["default_clarity"] = submitted.get("default_resolution")
        if "default_aspect_ratio" not in submitted:
            submitted["default_aspect_ratio"] = existing_config.get(
                "default_aspect_ratio",
                "1:1",
            )
        if "default_clarity" not in submitted and "default_resolution" in submitted:
            submitted["default_clarity"] = submitted.get("default_resolution")
        elif "default_clarity" not in submitted:
            submitted["default_clarity"] = existing_config.get(
                "default_clarity",
                submitted.get("default_resolution", "1K"),
            )
        if "custom_generation_sizes" not in submitted:
            submitted["custom_generation_sizes"] = existing_config.get(
                "custom_generation_sizes",
                [],
            )
        if "default_count" not in submitted:
            submitted["default_count"] = existing_config.get(
                "default_count",
                default_generation_count(existing_config),
            )
        if "default_output_dir" not in submitted:
            submitted["default_output_dir"] = existing_config.get("default_output_dir", "")
        if "save_layout" not in submitted:
            submitted["save_layout"] = existing_config.get("save_layout", "double")
        if "generation_path_history" not in submitted:
            submitted["generation_path_history"] = existing_config.get("generation_path_history", [])
        if "provider_field_history" not in submitted:
            submitted["provider_field_history"] = existing_config.get("provider_field_history", {})
        config = normalize_config(submitted)
        config = strip_provider_default_sizes(config)
        save_config(current_app.config["CONFIG_FILE"], config)
        current_app.config["APP_CONFIG"] = config
        return jsonify({"settings": public_config(config)})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400


@api.post("/generate")
def api_generate():
    try:
        begin_generation()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409
    conn = db()
    history_id: int | None = None
    precreated_ids: list[int] = []
    generation_size = ""
    generation_params: dict = {}

    def mark_precreated_failed(message: str) -> None:
        for instance_id in precreated_ids:
            try:
                update_instance_generation_status(
                    conn,
                    instance_id,
                    "failed",
                    error=message,
                    finished_at=now_iso(),
                )
            except Exception:
                continue

    try:
        data = payload_json()
        app_config = current_app.config["APP_CONFIG"]
        requested_provider_key = str(data.get("provider_key") or "").strip()
        mode = data.get("mode", "text_to_image")
        prompt = str(data.get("prompt", "")).strip()
        generation_task_id = str(data.get("generation_task_id") or uuid.uuid4())
        clear_cancelled_generation_task(generation_task_id)
        retry_instance_id = optional_positive_int(data.get("retry_instance_id"))
        target_instance_id = optional_positive_int(data.get("target_instance_id"))
        if retry_instance_id and target_instance_id:
            raise ValueError("不能同时指定重新提交实例和目标实例")
        node_id = optional_node_id(data.get("node_id"))
        output_dir = str(
            data.get("generation_path")
            or data.get("output_dir")
            or app_config.get("default_output_dir")
            or ""
        ).strip()
        raw_options = data.get("options", {})
        provider_key, provider_config = requested_provider_config(app_config, requested_provider_key)
        history_id = create_generate_history_record(
            conn,
            app_config,
            data,
            output_dir,
            raw_options if isinstance(raw_options, dict) else {},
            provider_key=provider_key,
            provider_config=provider_config,
        )
        if not prompt:
            raise ValueError("提示词不能为空")
        input_image_paths = validate_input_image_paths(
            data.get("input_image_paths", []),
            mode,
        )

        if not output_dir:
            raise ValueError("输出目录不能为空，请先配置默认输出目录")
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"输出目录不可用：{exc}") from exc

        tags = data.get("tags", [])
        options = raw_options
        if not isinstance(options, dict):
            raise ValueError("生成选项必须是 JSON 对象")
        if provider_uses_size(provider_config):
            options, generation_size = normalize_generation_options(options, app_config)
        elif provider_uses_count(provider_config):
            options, generation_size = normalize_openai_google_generation_options(options, app_config)
        else:
            options, generation_size = normalize_no_size_single_output_generation_options(options, app_config)
        generation_params = generation_params_from_options(
            app_config,
            options,
            generation_size,
            provider_key=provider_key,
            provider_config=provider_config,
        )
        custom_script = custom_script_for_generation(provider_config, mode)
        shared_openai_script = None if custom_script else default_shared_script_for_generation(provider_config, mode)
        validate_adapter_supported(provider_config.get("adapter") or "")
        if custom_script:
            generation_params["custom_script_used"] = True
        elif shared_openai_script:
            generation_params["shared_script_used"] = True
        precreate_count = int(options.get("n", options.get("count", 1)) or 1)
        started_at = now_iso()
        base_instance_payload = {
            "prompt": prompt,
            "mode": mode,
            "source": "generated",
            "provider": provider_key,
            "generation_path": output_dir,
            "generation_size": generation_size,
            "generation_params": generation_params,
            "output_image_path": "",
            "input_image_paths": input_image_paths,
            "tags": tags,
            "node_id": node_id,
        }
        if retry_instance_id or target_instance_id:
            existing_id = retry_instance_id or target_instance_id
            existing = get_instance(conn, existing_id)
            if existing is None:
                raise ValueError("实例不存在")
            if retry_instance_id and existing.get("generation_status") != "failed":
                raise ValueError("只有生成失败实例可以重新提交")
            if target_instance_id:
                if existing.get("generation_status") == "running":
                    raise ValueError("生成中实例不能重复提交")
                if existing.get("output_image_path"):
                    raise ValueError("已有输出图，不能直接提交")
            prepare_instance_for_generation(
                conn,
                existing_id,
                base_instance_payload,
                task_id=generation_task_id,
                output_index=1,
                started_at=started_at,
            )
            precreated_ids.append(existing_id)
            precreate_count = 1
        else:
            for index in range(precreate_count):
                instance_id = create_instance(
                    conn,
                    {
                        **base_instance_payload,
                        "generation_status": "running",
                        "generation_task_id": generation_task_id,
                        "generation_output_index": index + 1,
                        "generation_started_at": started_at,
                    },
                )
                precreated_ids.append(instance_id)
        result = None
        attempt = 1
        with provider_generation_lock(provider_key):
            while True:
                try:
                    if is_generation_task_cancelled(generation_task_id):
                        mark_precreated_failed("生成已取消")
                        raise ValueError("生成已取消")
                    result = run_generation_once(
                        app_config=app_config,
                        provider_key=provider_key,
                        provider_config=provider_config,
                        mode=mode,
                        prompt=prompt,
                        input_image_paths=input_image_paths,
                        output_dir=output_dir,
                        options=options,
                        custom_script=custom_script,
                        shared_openai_script=shared_openai_script,
                    )
                    break
                except Exception as exc:
                    if is_generation_task_cancelled(generation_task_id):
                        mark_precreated_failed("生成已取消")
                        raise ValueError("生成已取消")
                    retry_allowed = (
                        (not custom_script)
                        and is_retryable_generation_error(exc)
                        and attempt < GENERATION_RETRY_MAX_ATTEMPTS
                    )
                    if not retry_allowed:
                        raise
                    delay_seconds = retry_delay_for_attempt(attempt, exc)
                    retry_message = (
                        f"第 {attempt} 次生成失败，正在等待 {delay_seconds} 秒后重试："
                        f"{retry_error_message(exc)}"
                    )
                    for instance_id in precreated_ids:
                        try:
                            update_instance_generation_status(
                                conn,
                                instance_id,
                                "running",
                                error=retry_message,
                            )
                        except Exception:
                            continue
                    create_retry_history_record(
                        conn,
                        app_config=app_config,
                        data=data,
                        output_dir=output_dir,
                        options=options,
                        generation_size=generation_size,
                        generation_params=generation_params,
                        provider_key=provider_key,
                        provider_config=provider_config,
                        attempt=attempt,
                        delay_seconds=delay_seconds,
                        error=exc,
                        parent_history_id=history_id,
                    )
                    sleep_for_retry(generation_task_id, delay_seconds)
                    attempt += 1
        output_paths = list(getattr(result, "output_paths", None) or [])
        if not output_paths and getattr(result, "output_path", ""):
            output_paths = [result.output_path]
        if not output_paths:
            raise ValueError("图片生成响应为空")
        if is_generation_task_cancelled(generation_task_id):
            mark_precreated_failed("生成已取消")
            raise ValueError("生成已取消")
        create_script_retry_history_records(
            conn,
            app_config=app_config,
            data=data,
            output_dir=output_dir,
            generation_size=generation_size,
            generation_params=generation_params,
            provider_key=provider_key,
            provider_config=provider_config,
            retry_events=list(getattr(result, "retry_events", None) or []),
            parent_history_id=history_id,
        )

        items = []
        effective_output_paths = output_paths
        if retry_instance_id or target_instance_id:
            update_instance_output_image(
                conn,
                precreated_ids[0],
                effective_output_paths[0],
                effective_output_paths,
            )
            items.append(get_instance(conn, precreated_ids[0]))
        else:
            for index, output_path in enumerate(effective_output_paths):
                if index < len(precreated_ids):
                    update_instance_output_image(conn, precreated_ids[index], output_path)
                    items.append(get_instance(conn, precreated_ids[index]))
                else:
                    instance_id = create_instance(
                        conn,
                        {
                            **base_instance_payload,
                            "provider": provider_key or result.provider,
                            "output_image_path": output_path,
                            "generation_status": "ready",
                            "generation_task_id": generation_task_id,
                            "generation_output_index": index + 1,
                            "generation_started_at": started_at,
                            "generation_finished_at": now_iso(),
                        },
                    )
                    items.append(get_instance(conn, instance_id))
            missing_output_ids = precreated_ids[len(effective_output_paths):]
            for instance_id in missing_output_ids:
                update_instance_generation_status(
                    conn,
                    instance_id,
                    "failed",
                    error="Provider 返回图片数量少于预期",
                    finished_at=now_iso(),
                )
                items.append(get_instance(conn, instance_id))
        response_item = next(
            (item for item in reversed(items) if item and item.get("output_image_path")),
            items[-1] if items else None,
        )
        successful_ids = [
            int(item["id"])
            for item in items
            if item and item.get("id")
        ]
        generation_params_with_instances = dict(generation_params)
        generation_params_with_instances["instance_ids"] = successful_ids
        if response_item and response_item.get("id"):
            generation_params_with_instances["primary_instance_id"] = int(response_item["id"])
        finish_generate_history_record(
            conn,
            history_id,
            {
                "status": "success",
                "resolved_size": generation_size,
                "params": generation_params_with_instances,
                "output_image_paths": effective_output_paths,
                "custom_script_used": generation_params.get("custom_script_used", False),
            },
        )
        record_successful_generation_path(output_dir)
        record_successful_provider_field_history(provider_config)
        return jsonify(
            {
                "item": response_item,
                "items": items,
                "output_image_paths": effective_output_paths,
                "history_id": history_id,
                "generation_task_id": generation_task_id,
            }
        ), 201
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        mark_precreated_failed(str(exc))
        failed_params = dict(generation_params or {})
        if precreated_ids:
            failed_params["instance_ids"] = precreated_ids
            failed_params["primary_instance_id"] = precreated_ids[0]
        finish_generate_history_record(
            conn,
            history_id,
            {"status": "failed", "error_message": str(exc), "params": failed_params},
        )
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        mark_precreated_failed(f"生成失败：{exc}")
        failed_params = dict(generation_params or {})
        if precreated_ids:
            failed_params["instance_ids"] = precreated_ids
            failed_params["primary_instance_id"] = precreated_ids[0]
        finish_generate_history_record(
            conn,
            history_id,
            {"status": "failed", "error_message": f"生成失败：{exc}", "params": failed_params},
        )
        return jsonify({"error": f"生成失败：{exc}"}), 500
    finally:
        conn.close()
        clear_cancelled_generation_task(generation_task_id if "generation_task_id" in locals() else "")
        end_generation()


@api.post("/paths/replace/preview")
def api_preview_path_replace():
    conn = db()
    try:
        data = payload_json()
        return jsonify(
            preview_path_replacement(
                conn,
                data.get("find", ""),
                data.get("replace", ""),
            )
        )
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@api.post("/paths/replace/apply")
def api_apply_path_replace():
    conn = db()
    try:
        data = payload_json()
        backup_dir = current_app.config["DB_FILE"].parent / "backups"
        return jsonify(
            apply_path_replacement(
                conn,
                current_app.config["DB_FILE"],
                backup_dir,
                data.get("find", ""),
                data.get("replace", ""),
            )
        )
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"路径替换失败：{exc}"}), 500
    finally:
        conn.close()


@api.post("/dialogs/directory")
def api_choose_directory():
    try:
        data = optional_payload_json()
        return jsonify({"path": choose_directory(data.get("initial_dir", ""))})
    except JsonObjectError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"无法打开文件选择窗口：{exc}"}), 500


@api.post("/dialogs/images")
def api_choose_images():
    try:
        return jsonify({"paths": choose_images()})
    except Exception as exc:
        return jsonify({"error": f"无法打开文件选择窗口：{exc}"}), 500


@api.get("/clipboard/image-paths")
def api_clipboard_image_paths():
    try:
        paths = clipboard_image_paths()
        if not paths:
            return (
                jsonify(
                    {
                        "error": "剪贴板中没有可用的本地图片路径，请从资源管理器复制图片文件，或点击选择图片。"
                    }
                ),
                400,
            )
        return jsonify({"paths": paths})
    except Exception as exc:
        return jsonify({"error": f"无法读取剪贴板图片路径：{exc}"}), 500












