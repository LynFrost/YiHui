from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import getproxies
import base64
import json
import re
import time

try:
    httpx
except NameError:
    import httpx


def required_value(name):
    value = globals().get(name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required parameter: {name}")
    return value


def is_none_placeholder(value):
    return isinstance(value, str) and value.strip().lower() == "none"


def optional_text(name, default=""):
    value = globals().get(name)
    if value is None or is_none_placeholder(value):
        return default
    return str(value or default).strip()


def optional_bool(name, default=False):
    value = globals().get(name)
    if value is None or is_none_placeholder(value):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def optional_int(name, default=None):
    value = globals().get(name)
    if value in {None, ""} or is_none_placeholder(value):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def optional_float(name):
    value = globals().get(name)
    if value in {None, ""} or is_none_placeholder(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value).strip()


def optional_json_or_text(name):
    value = globals().get(name)
    if value in {None, ""} or is_none_placeholder(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
RETRY_DELAYS = [10, 30, 60, 120]
REQUEST_TIMEOUT_SECONDS = int(globals().get("request_timeout_seconds") or 300)
DOWNLOAD_TIMEOUT_SECONDS = int(globals().get("download_timeout_seconds") or 120)
MAX_RETRY_ATTEMPTS = int(globals().get("max_retry_attempts") or (len(RETRY_DELAYS) + 1))
retry_events = []


def normalize_base_url(value):
    clean_url = str(value).strip().rstrip("/")
    if clean_url.endswith("/v1"):
        return clean_url
    return f"{clean_url}/v1"


def chat_completions_url():
    return urljoin(f"{base_url}/", "chat/completions")


def system_https_proxy():
    if not optional_bool("use_system_proxy", True):
        return ""
    hostname = (urlparse(optional_text("base_url")).hostname or "").lower()
    if hostname == "localhost" or hostname == "::1" or hostname.startswith("127."):
        return ""
    injected_proxy = optional_text("system_proxy")
    if injected_proxy:
        return injected_proxy
    proxies = getproxies()
    return proxies.get("https") or proxies.get("http") or ""


def http_client_options(verify=True):
    options = {"trust_env": False, "verify": verify}
    proxy = system_https_proxy()
    if proxy:
        options["proxies"] = proxy
    return options


def is_certificate_error(error):
    current = error
    seen = set()
    while current and id(current) not in seen:
        seen.add(id(current))
        text = str(current).lower()
        if "certificate" in text or "cert" in text or "ssl" in text:
            return True
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return False


def should_allow_untrusted_proxy_certificate(proxy):
    if not proxy:
        return False
    return optional_bool("allow_untrusted_proxy_certificate", True)


def exception_text(error):
    parts = []
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(str(current))
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return "\n".join(part for part in parts if part)


def retryable_status_code(error):
    current = error
    seen = set()
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
    text = exception_text(error).lower()
    for status_code in RETRYABLE_STATUS_CODES:
        if str(status_code) in text:
            return status_code
    return None


def retry_after_seconds(error):
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
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
    return None


def retry_delay_for_attempt(attempt, error):
    explicit = retry_after_seconds(error)
    if explicit is not None:
        return explicit
    index = min(max(0, attempt - 1), len(RETRY_DELAYS) - 1)
    return RETRY_DELAYS[index]


def is_retryable_error(error):
    if is_certificate_error(error):
        return False
    if retryable_status_code(error) is not None:
        return True
    text = exception_text(error).lower()
    markers = [
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
        "connection error",
        "connection reset",
        "temporarily unavailable",
    ]
    return any(marker in text for marker in markers)


def http_timeout():
    return httpx.Timeout(
        REQUEST_TIMEOUT_SECONDS,
        connect=60,
        read=REQUEST_TIMEOUT_SECONDS,
        write=120,
        pool=60,
    )


def response_payload(response):
    try:
        return response.json()
    except Exception:
        text = getattr(response, "text", "")
        return json.loads(text) if text else {}


def post_chat_completions_once(payload, verify=True):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if user_agent:
        headers["User-Agent"] = user_agent
    with httpx.Client(**http_client_options(verify=verify), timeout=http_timeout()) as client:
        response = client.post(chat_completions_url(), headers=headers, json=payload)
        response.raise_for_status()
        return response_payload(response)


def post_chat_completions(payload):
    last_error = None
    for attempt in range(1, max(1, MAX_RETRY_ATTEMPTS) + 1):
        try:
            proxy = system_https_proxy()
            try:
                return post_chat_completions_once(payload, verify=True)
            except Exception as error:
                if not (should_allow_untrusted_proxy_certificate(proxy) and is_certificate_error(error)):
                    raise
                return post_chat_completions_once(payload, verify=False)
        except Exception as error:
            last_error = error
            if attempt >= max(1, MAX_RETRY_ATTEMPTS) or not is_retryable_error(error):
                raise
            delay = retry_delay_for_attempt(attempt, error)
            retry_events.append({
                "attempt": attempt,
                "delay_seconds": delay,
                "error": exception_text(error)[-4000:],
            })
            time.sleep(delay)
    raise last_error


def iter_strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
    elif isinstance(value, str):
        yield value


def is_image_bytes(value):
    return value.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF", b"GIF8"))


def download_image(url, output_file):
    headers = {"User-Agent": user_agent} if user_agent else {}
    proxy = system_https_proxy()
    try:
        with httpx.Client(**http_client_options(verify=True), timeout=DOWNLOAD_TIMEOUT_SECONDS) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            Path(output_file).write_bytes(response.content)
            return
    except Exception as error:
        if not (should_allow_untrusted_proxy_certificate(proxy) and is_certificate_error(error)):
            raise
    with httpx.Client(**http_client_options(verify=False), timeout=DOWNLOAD_TIMEOUT_SECONDS) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        Path(output_file).write_bytes(response.content)


def save_image_from_response(response, filename):
    for value in iter_strings(response):
        data_url = re.search(
            r"data:image/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=\s]+)",
            value,
        )
        if data_url:
            Path(filename).write_bytes(base64.b64decode(re.sub(r"\s+", "", data_url.group(1))))
            return filename

        image_url = re.search(r"https?://[^\s\"'<>)]*", value)
        if image_url:
            download_image(image_url.group(0), filename)
            return filename

        cleaned = re.sub(r"\s+", "", value)
        try:
            image_bytes = base64.b64decode(cleaned, validate=True)
        except Exception:
            continue
        if is_image_bytes(image_bytes):
            Path(filename).write_bytes(image_bytes)
            return filename

    summary = json.dumps(response, ensure_ascii=False)[:4000]
    raise RuntimeError(f"Image response did not include an image. Response summary: {summary}")


def add_optional_parameter(payload, key, value):
    if value is not None and value != "":
        payload[key] = value


base_url = normalize_base_url(required_value("base_url"))
api_key = str(required_value("api_key"))
model = str(required_value("model"))
operation_prompt = str(required_value("operation_prompt"))
output_path = Path(required_value("output_path"))
result_json_path = Path(required_value("result_json_path"))
user_agent = optional_text("user_agent")

payload = {
    "model": model,
    "messages": [
        {
            "role": optional_text("google_role", "user") or "user",
            "content": [
                {
                    "type": "text",
                    "text": operation_prompt,
                },
            ],
        },
    ],
    "stream": False,
}
add_optional_parameter(payload, "max_tokens", optional_int("google_max_tokens", 4096))
add_optional_parameter(payload, "temperature", optional_float("google_temperature"))
add_optional_parameter(payload, "top_p", optional_float("google_top_p"))
add_optional_parameter(payload, "stop", optional_json_or_text("google_stop"))
add_optional_parameter(payload, "presence_penalty", optional_float("google_presence_penalty"))
add_optional_parameter(payload, "frequency_penalty", optional_float("google_frequency_penalty"))
add_optional_parameter(payload, "logit_bias", optional_json_or_text("google_logit_bias"))
add_optional_parameter(payload, "user", optional_text("google_user"))
add_optional_parameter(payload, "response_format", optional_json_or_text("google_response_format"))
add_optional_parameter(payload, "seen", optional_json_or_text("google_seen"))
add_optional_parameter(payload, "tools", optional_json_or_text("google_tools"))
add_optional_parameter(payload, "tool_choice", optional_json_or_text("google_tool_choice"))

result = post_chat_completions(payload)
saved_path = save_image_from_response(result, output_path)
result_json_path.write_text(
    json.dumps({"output_paths": [str(saved_path)], "retry_events": retry_events}, ensure_ascii=False),
    encoding="utf-8",
)
