from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "active_provider": "aiapis_gpt_image_2",
    "default_output_dir": "",
    "default_size": "1024x1024",
    "default_resolution": "1K",
    "default_custom_resolution": "",
    "default_aspect_ratio": "1:1",
    "default_clarity": "1K",
    "custom_generation_sizes": [],
    "generation_path_history": [],
    "provider_field_history": {
        "api_key_env": [],
        "model": [],
        "user_agent": [],
    },
    "default_count": 1,
    "save_layout": "double",
    "providers": {
        "aiapis_gpt_image_2": {
            "display_name": "AIAPIS GPT Image 2",
            "adapter": "openai",
            "base_url": "https://img.aiapis.help/v1",
            "api_key_env": "IMG_API_KEY",
            "api_key": "",
            "model": "gpt-image-2",
            "openai_call_method": "gpt-image-2",
            "quality": "high",
            "output_format": "png",
            "output_compression": 80,
            "background": "auto",
            "moderation": "low",
            "stream": False,
            "partial_images": 0,
            "user": "",
            "google_role": "user",
            "google_max_tokens": 4096,
            "google_temperature": "",
            "google_top_p": "",
            "google_stream": False,
            "google_stop": "",
            "google_presence_penalty": "",
            "google_frequency_penalty": "",
            "google_logit_bias": "",
            "google_user": "",
            "google_response_format": "",
            "google_seen": "",
            "google_tools": "",
            "google_tool_choice": "",
            "request_timeout_seconds": 300,
            "download_timeout_seconds": 120,
            "max_retry_attempts": 5,
            "apimart_task_timeout_seconds": 420,
            "apimart_task_poll_interval_seconds": 5,
            "input_fidelity": "",
            "mask_path": "",
            "user_agent": "",
            "proxy_mode": "system",
            "proxy_url": "",
            "allow_untrusted_proxy_certificate": True,
            "openai_example_mode": "text_to_image",
            "code_examples": {},
            "custom_scripts": {},
        }
    },
}

SUPPORTED_RESOLUTION_MODES = {"1K", "2K", "4K", "custom"}
SUPPORTED_RESOLUTIONS = SUPPORTED_RESOLUTION_MODES
SIZE_PATTERN = re.compile(r"^[1-9][0-9]*x[1-9][0-9]*$")
SIZE_MAP: dict[str, dict[str, str]] = {
    "1:1": {"1K": "1024x1024", "2K": "2048x2048", "4K": "2880x2880"},
    "5:4": {"1K": "1280x1024", "2K": "2560x2048", "4K": "3200x2560"},
    "9:16": {"1K": "864x1536", "2K": "1152x2048", "4K": "2160x3840"},
    "21:9": {"1K": "2016x864", "2K": "2688x1152", "4K": "3808x1632"},
    "16:9": {"1K": "1536x864", "2K": "2048x1152", "4K": "3840x2160"},
    "4:3": {"1K": "1024x768", "2K": "2048x1536", "4K": "3264x2448"},
    "3:2": {"1K": "1536x1024", "2K": "2016x1344", "4K": "3504x2336"},
    "4:5": {"1K": "1024x1280", "2K": "2048x2560", "4K": "2560x3200"},
    "3:4": {"1K": "768x1024", "2K": "1536x2048", "4K": "2448x3264"},
    "2:3": {"1K": "1024x1536", "2K": "1344x2016", "4K": "2336x3504"},
}
DEFAULT_PROVIDER_ADAPTER = "openai"
OPENAI_DEFAULT_BASE_URL = "https://img.aiapis.help/v1"
OPENAI_GOOGLE_DEFAULT_BASE_URL = "https://www.xiaoyunapi.com/v1"
OPENAI_GOOGLE_DEFAULT_API_KEY_ENV = "XIAOYUN_API_KEY"
OPENAI_GOOGLE_DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
SUPPORTED_PROVIDER_ADAPTERS = {
    "openai",
    "openai-google",
    "sysrv-google",
    "apimart-openai",
    "google",
    "other",
}
LEGACY_PROVIDER_ADAPTERS = {"aiapis_gpt_image_2": "openai"}
SUPPORTED_OPENAI_CALL_METHODS = {"gpt-image-2", "response"}
SUPPORTED_CODE_METHODS = SUPPORTED_OPENAI_CALL_METHODS | {"openai-google", "sysrv-google", "apimart-openai"}
SUPPORTED_OPENAI_EXAMPLE_MODES = {"text_to_image", "image_to_image"}
SUPPORTED_QUALITIES = {"low", "medium", "high", "auto"}
SUPPORTED_OUTPUT_FORMATS = {"png", "jpeg", "webp"}
SUPPORTED_BACKGROUNDS = {"auto", "opaque", "transparent"}
SUPPORTED_MODERATIONS = {"auto", "low"}
SUPPORTED_PROXY_MODES = {"system", "custom", "none"}
PROVIDER_DEFAULTS: dict[str, Any] = {
    "display_name": "",
    "adapter": DEFAULT_PROVIDER_ADAPTER,
    "base_url": "https://img.aiapis.help/v1",
    "api_key_env": "IMG_API_KEY",
    "api_key": "",
    "model": "gpt-image-2",
    "openai_call_method": "gpt-image-2",
    "quality": "high",
    "output_format": "png",
    "output_compression": 80,
    "background": "auto",
    "moderation": "low",
    "stream": False,
    "partial_images": 0,
    "user": "",
    "google_role": "user",
    "google_max_tokens": 4096,
    "google_temperature": "",
    "google_top_p": "",
    "google_stream": False,
    "google_stop": "",
    "google_presence_penalty": "",
    "google_frequency_penalty": "",
    "google_logit_bias": "",
    "google_user": "",
    "google_response_format": "",
    "google_seen": "",
    "google_tools": "",
    "google_tool_choice": "",
    "request_timeout_seconds": 300,
    "download_timeout_seconds": 120,
    "max_retry_attempts": 5,
    "apimart_task_timeout_seconds": 420,
    "apimart_task_poll_interval_seconds": 5,
    "input_fidelity": "",
    "mask_path": "",
    "user_agent": "",
    "proxy_mode": "system",
    "proxy_url": "",
    "allow_untrusted_proxy_certificate": True,
    "openai_example_mode": "text_to_image",
    "code_examples": {},
    "custom_scripts": {},
}
PROVIDER_CAPABILITY_FIELD_PREFIXES = ("supports_",)
PROVIDER_CAPABILITY_FIELDS = {
    "capabilities",
    "implemented",
    "settingsKind",
    "settings_kind",
    "callMethods",
    "call_methods",
    "message",
}
PROVIDER_FIELD_HISTORY_FIELDS = ("api_key_env", "model", "user_agent")


def deep_merge(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(defaults)

    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        elif isinstance(merged.get(key), dict) and not isinstance(value, dict):
            continue
        else:
            merged[key] = copy.deepcopy(value)

    return merged


def clean_generation_size(value: Any) -> str:
    size = str(value or "").strip()
    return size if SIZE_PATTERN.fullmatch(size) else DEFAULT_CONFIG["default_size"]


def aspect_ratio_for_size(size: str, clarity: str | None = None) -> str:
    if clarity in {"1K", "2K", "4K"}:
        for ratio, values in SIZE_MAP.items():
            if values.get(clarity) == size:
                return ratio
    for ratio, values in SIZE_MAP.items():
        if size in values.values():
            return ratio
    return ""


def size_for_aspect_ratio(aspect_ratio: str, clarity: str) -> str:
    return SIZE_MAP.get(aspect_ratio, {}).get(clarity, "")


def normalize_custom_generation_sizes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        size = str(item or "").strip()
        if not SIZE_PATTERN.fullmatch(size) or size in seen:
            continue
        normalized.append(size)
        seen.add(size)
    return normalized


def normalize_generation_path_history(value: Any, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        path = str(item or "").strip()
        if not path or path in seen:
            continue
        normalized.append(path)
        seen.add(path)
        if len(normalized) >= limit:
            break
    return normalized


def normalize_provider_adapter(value: Any) -> str:
    adapter = str(value or "").strip()
    adapter = LEGACY_PROVIDER_ADAPTERS.get(adapter, adapter)
    return adapter or DEFAULT_PROVIDER_ADAPTER


def normalize_provider_base_url(value: Any, adapter: str) -> str:
    base_url = str(value or "").strip()
    if adapter not in {"openai", "openai-google", "apimart-openai"}:
        return base_url
    clean_url = base_url.rstrip("/")
    if not clean_url:
        return OPENAI_GOOGLE_DEFAULT_BASE_URL if adapter == "openai-google" else ""
    if clean_url.endswith("/v1"):
        return clean_url
    if adapter in {"openai", "apimart-openai"}:
        return f"{clean_url}/v1"
    return clean_url


def default_base_url_for_adapter(adapter: str) -> str:
    if adapter == "openai-google":
        return OPENAI_GOOGLE_DEFAULT_BASE_URL
    if adapter == "apimart-openai":
        return "https://api.apimart.ai/v1"
    return OPENAI_DEFAULT_BASE_URL


def default_api_key_env_for_adapter(adapter: str) -> str:
    if adapter == "openai-google":
        return OPENAI_GOOGLE_DEFAULT_API_KEY_ENV
    if adapter == "sysrv-google":
        return "SYSRV_GOOGLE_API_KEY"
    if adapter == "apimart-openai":
        return "APIMART_API_KEY"
    return "IMG_API_KEY"


def default_model_for_adapter(adapter: str) -> str:
    if adapter in {"openai-google", "sysrv-google"}:
        return OPENAI_GOOGLE_DEFAULT_MODEL
    return "gpt-image-2"


def normalize_choice(value: Any, choices: set[str], default: str) -> str:
    text = str(value or "").strip()
    return text if text in choices else default


def normalize_int_range(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def normalize_bool_false(value: Any) -> bool:
    return False


def normalize_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_code_map(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, dict[str, str]] = {}
    for method, mode_map in value.items():
        method_key = str(method or "").strip()
        if method_key not in SUPPORTED_CODE_METHODS:
            continue
        if not isinstance(mode_map, dict):
            continue
        cleaned_modes: dict[str, str] = {}
        for mode, code in mode_map.items():
            mode_key = str(mode or "").strip()
            if mode_key not in SUPPORTED_OPENAI_EXAMPLE_MODES:
                continue
            if isinstance(code, str):
                cleaned_modes[mode_key] = code
        if cleaned_modes:
            normalized[method_key] = cleaned_modes
    return normalized


def normalize_provider_field_history(value: Any, limit: int = 20) -> dict[str, list[str]]:
    source = value if isinstance(value, dict) else {}
    normalized: dict[str, list[str]] = {}
    for field in PROVIDER_FIELD_HISTORY_FIELDS:
        normalized[field] = []
        seen: set[str] = set()
        values = source.get(field)
        if not isinstance(values, list):
            continue
        for item in values:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            normalized[field].append(text)
            seen.add(text)
            if len(normalized[field]) >= limit:
                break
    return normalized


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    loaded = config if isinstance(config, dict) else {}
    top_level = {
        key: value for key, value in loaded.items() if key != "providers"
    }
    normalized = deep_merge(DEFAULT_CONFIG, top_level)

    loaded_providers = loaded.get("providers")
    if isinstance(loaded_providers, dict):
        normalized["providers"] = normalize_providers(loaded_providers)
    else:
        normalized["providers"] = normalize_providers(DEFAULT_CONFIG["providers"])

    loaded_default_resolution = str(top_level.get("default_resolution") or "").strip()
    loaded_default_clarity = str(top_level.get("default_clarity") or "").strip()
    if loaded_default_clarity in SUPPORTED_RESOLUTION_MODES:
        default_clarity = loaded_default_clarity
    elif loaded_default_resolution in SUPPORTED_RESOLUTION_MODES:
        default_clarity = loaded_default_resolution
    else:
        default_clarity = DEFAULT_CONFIG["default_clarity"]

    default_size = clean_generation_size(normalized.get("default_size"))
    default_aspect_ratio = str(top_level.get("default_aspect_ratio") or "").strip()
    if default_aspect_ratio not in SIZE_MAP:
        default_aspect_ratio = aspect_ratio_for_size(default_size, default_clarity)
    if default_aspect_ratio not in SIZE_MAP:
        default_aspect_ratio = DEFAULT_CONFIG["default_aspect_ratio"]

    normalized["default_custom_resolution"] = str(
        normalized.get("default_custom_resolution") or ""
    ).strip()
    normalized["default_aspect_ratio"] = default_aspect_ratio
    normalized["default_clarity"] = default_clarity
    normalized["default_resolution"] = default_clarity
    normalized["default_size"] = default_size

    custom_sizes = normalize_custom_generation_sizes(
        normalized.get("custom_generation_sizes")
    )
    if default_clarity == "custom" and default_size not in custom_sizes:
        custom_sizes.append(default_size)
    normalized["custom_generation_sizes"] = custom_sizes
    normalized["generation_path_history"] = normalize_generation_path_history(
        normalized.get("generation_path_history")
    )
    normalized["provider_field_history"] = normalize_provider_field_history(
        normalized.get("provider_field_history")
    )

    try:
        default_count = int(normalized.get("default_count"))
    except (TypeError, ValueError):
        default_count = DEFAULT_CONFIG["default_count"]
    if default_count < 1:
        default_count = DEFAULT_CONFIG["default_count"]
    normalized["default_count"] = default_count

    if normalized.get("save_layout") not in {"single", "double"}:
        normalized["save_layout"] = DEFAULT_CONFIG["save_layout"]

    provider_keys = list(normalized["providers"])
    if normalized.get("active_provider") not in normalized["providers"]:
        normalized["active_provider"] = provider_keys[0] if provider_keys else ""
    return normalized


def normalize_providers(providers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in providers.items():
        provider_key = str(key).strip()
        if not provider_key:
            continue
        provider_config = value if isinstance(value, dict) else {}
        provider = deep_merge(PROVIDER_DEFAULTS, provider_config)
        raw_adapter = provider_config.get("adapter")
        if not raw_adapter:
            raw_adapter = provider_key if provider_key in SUPPORTED_PROVIDER_ADAPTERS else DEFAULT_PROVIDER_ADAPTER
        provider["adapter"] = normalize_provider_adapter(raw_adapter)
        has_base_url = "base_url" in provider_config
        raw_base_url = provider_config.get("base_url") if has_base_url else None
        if not has_base_url or (
            provider["adapter"] == "openai-google"
            and str(raw_base_url).strip().rstrip("/") == OPENAI_DEFAULT_BASE_URL
        ):
            raw_base_url = default_base_url_for_adapter(provider["adapter"])
        provider["base_url"] = normalize_provider_base_url(
            raw_base_url,
            provider["adapter"],
        )
        has_api_key_env = "api_key_env" in provider_config
        raw_api_key_env = provider_config.get("api_key_env") if has_api_key_env else None
        if not has_api_key_env or (
            provider["adapter"] == "openai-google"
            and str(raw_api_key_env).strip() == "IMG_API_KEY"
        ):
            raw_api_key_env = default_api_key_env_for_adapter(provider["adapter"])
        provider["api_key_env"] = str(raw_api_key_env or "").strip()
        has_model = "model" in provider_config
        raw_model = provider_config.get("model") if has_model else None
        if not has_model or (
            provider["adapter"] == "openai-google"
            and str(raw_model).strip() == "gpt-image-2"
        ):
            raw_model = default_model_for_adapter(provider["adapter"])
        provider["model"] = str(raw_model or "").strip()
        provider["openai_call_method"] = normalize_choice(
            provider.get("openai_call_method"),
            SUPPORTED_OPENAI_CALL_METHODS,
            "gpt-image-2",
        )
        provider["openai_example_mode"] = normalize_choice(
            provider.get("openai_example_mode"),
            SUPPORTED_OPENAI_EXAMPLE_MODES,
            "text_to_image",
        )
        provider["quality"] = normalize_choice(provider.get("quality"), SUPPORTED_QUALITIES, "high")
        provider["output_format"] = normalize_choice(
            provider.get("output_format"),
            SUPPORTED_OUTPUT_FORMATS,
            "png",
        )
        provider["output_compression"] = normalize_int_range(
            provider.get("output_compression"),
            80,
            0,
            100,
        )
        provider["background"] = normalize_choice(
            provider.get("background"),
            SUPPORTED_BACKGROUNDS,
            "auto",
        )
        provider["moderation"] = normalize_choice(
            provider.get("moderation"),
            SUPPORTED_MODERATIONS,
            "low",
        )
        provider["stream"] = normalize_bool_false(provider.get("stream"))
        provider["partial_images"] = 0
        provider["user"] = str(provider.get("user") or "").strip()
        provider["google_role"] = str(provider.get("google_role") or "user").strip() or "user"
        provider["google_max_tokens"] = normalize_int_range(
            provider.get("google_max_tokens"),
            4096,
            1,
            200000,
        )
        provider["google_temperature"] = str(provider.get("google_temperature") or "").strip()
        provider["google_top_p"] = str(provider.get("google_top_p") or "").strip()
        provider["google_stream"] = False
        provider["google_stop"] = str(provider.get("google_stop") or "").strip()
        provider["google_presence_penalty"] = str(provider.get("google_presence_penalty") or "").strip()
        provider["google_frequency_penalty"] = str(provider.get("google_frequency_penalty") or "").strip()
        provider["google_logit_bias"] = str(provider.get("google_logit_bias") or "").strip()
        provider["google_user"] = str(provider.get("google_user") or "").strip()
        provider["google_response_format"] = str(provider.get("google_response_format") or "").strip()
        provider["google_seen"] = str(provider.get("google_seen") or "").strip()
        provider["google_tools"] = str(provider.get("google_tools") or "").strip()
        provider["google_tool_choice"] = str(provider.get("google_tool_choice") or "").strip()
        provider["request_timeout_seconds"] = normalize_int_range(
            provider.get("request_timeout_seconds"),
            300,
            1,
            86400,
        )
        provider["download_timeout_seconds"] = normalize_int_range(
            provider.get("download_timeout_seconds"),
            120,
            1,
            86400,
        )
        provider["max_retry_attempts"] = normalize_int_range(
            provider.get("max_retry_attempts"),
            5,
            1,
            100,
        )
        provider["apimart_task_timeout_seconds"] = normalize_int_range(
            provider.get("apimart_task_timeout_seconds"),
            420,
            1,
            86400,
        )
        provider["apimart_task_poll_interval_seconds"] = normalize_int_range(
            provider.get("apimart_task_poll_interval_seconds"),
            5,
            1,
            3600,
        )
        provider["input_fidelity"] = str(provider.get("input_fidelity") or "").strip()
        provider["mask_path"] = str(provider.get("mask_path") or "").strip()
        provider["user_agent"] = str(provider.get("user_agent") or "").strip()
        provider["proxy_mode"] = normalize_choice(
            provider.get("proxy_mode"),
            SUPPORTED_PROXY_MODES,
            "system",
        )
        provider["proxy_url"] = str(provider.get("proxy_url") or "").strip()
        provider["allow_untrusted_proxy_certificate"] = normalize_bool(
            provider.get("allow_untrusted_proxy_certificate"),
            True,
        )
        provider["code_examples"] = normalize_code_map(provider.get("code_examples"))
        provider["custom_scripts"] = normalize_code_map(provider.get("custom_scripts"))
        for field in list(provider):
            if field in PROVIDER_CAPABILITY_FIELDS or field.startswith(
                PROVIDER_CAPABILITY_FIELD_PREFIXES
            ):
                provider.pop(field, None)
        normalized[provider_key] = provider
    return normalized


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)

    if not config_path.exists():
        config = copy.deepcopy(DEFAULT_CONFIG)
        save_config(config_path, config)
        return config

    with config_path.open("r", encoding="utf-8") as config_file:
        loaded = json.load(config_file)

    if not isinstance(loaded, dict):
        loaded = {}

    config = normalize_config(loaded)
    save_config(config_path, config)
    return config


def save_config(path: str | Path, config: dict[str, Any]) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("w", encoding="utf-8") as config_file:
        json.dump(config, config_file, ensure_ascii=False, indent=2)
        config_file.write("\n")
