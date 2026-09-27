from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlparse
from urllib.request import getproxies
import base64
import json
import shutil
import time

try:
    httpx
except NameError:
    import httpx

try:
    OpenAI
except NameError:
    from openai import OpenAI

try:
    Request
except NameError:
    from urllib.request import Request

try:
    urlopen
except NameError:
    from urllib.request import urlopen


def required_value(name):
    value = globals().get(name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required parameter: {name}")
    return value


def optional_text(name, default=""):
    return str(globals().get(name) or default).strip()


def optional_bool(name, default=False):
    value = globals().get(name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
RETRY_DELAYS = [10, 30, 60, 120]
REQUEST_TIMEOUT_SECONDS = int(globals().get("request_timeout_seconds") or 300)
DOWNLOAD_TIMEOUT_SECONDS = int(globals().get("download_timeout_seconds") or 120)
MAX_RETRY_ATTEMPTS = int(globals().get("max_retry_attempts") or (len(RETRY_DELAYS) + 1))
APIMART_TASK_TIMEOUT_SECONDS = int(globals().get("apimart_task_timeout_seconds") or 420)
APIMART_TASK_POLL_INTERVAL_SECONDS = int(globals().get("apimart_task_poll_interval_seconds") or 5)
retry_events = []


def normalize_base_url(value):
    clean_url = str(value).strip().rstrip("/")
    if clean_url.endswith("/v1"):
        return clean_url
    return f"{clean_url}/v1"


def response_items(response):
    items = list(getattr(response, "data", None) or [])
    expanded_items = []
    for item in items:
        task_id = apimart_task_id(item)
        if task_id and not item_value(item, "url") and not item_value(item, "b64_json"):
            expanded_items.extend(wait_for_apimart_task_items(task_id))
        else:
            expanded_items.append(item)
    return expanded_items


def item_value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def apimart_task_id(item):
    for name in ("task_id", "id"):
        value = item_value(item, name)
        if value:
            return str(value)
    return ""


def apimart_task_status(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        return str(data.get("status") or "").lower()
    return ""


def apimart_task_image_items(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError(f"APIMart task response did not include a data object: {payload}")

    status = str(data.get("status") or "").lower()
    if status in {"failed", "cancelled", "canceled", "error"}:
        raise RuntimeError(f"APIMart task failed: {payload}")
    if status != "completed":
        raise RuntimeError(f"APIMart task is not completed yet: {payload}")

    result = data.get("result") or {}
    images = result.get("images") or []
    output_items = []
    for image in images:
        if not isinstance(image, dict):
            continue
        b64_json = image.get("b64_json")
        if b64_json:
            output_items.append(SimpleNamespace(b64_json=b64_json, url=None))
            continue
        image_url = image.get("url")
        if isinstance(image_url, list) and image_url:
            output_items.append(SimpleNamespace(url=str(image_url[0]), b64_json=None))
        elif isinstance(image_url, str) and image_url:
            output_items.append(SimpleNamespace(url=image_url, b64_json=None))

    if not output_items:
        raise RuntimeError(f"Completed APIMart task did not include image data: {payload}")
    return output_items


def resolve_image_url(url):
    base_url = str(required_value("base_url")).rstrip("/")
    return urljoin(f"{base_url}/", str(url))


def apimart_task_url(task_id):
    base_url = str(required_value("base_url")).rstrip("/")
    return urljoin(f"{base_url}/", f"tasks/{task_id}")


def is_apimart_endpoint():
    return (urlparse(optional_text("base_url")).hostname or "").lower() == "api.apimart.ai"


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
    for attr in ("retry_after", "retry_after_seconds"):
        value = getattr(error, attr, None)
        if value is None:
            continue
        try:
            seconds = int(float(value))
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return min(seconds, 600)
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
        "apitimeouterror",
        "connection error",
        "connection reset",
        "temporarily unavailable",
    ]
    return any(marker in text for marker in markers)


def openai_client(verify=True):
    timeout = httpx.Timeout(
        REQUEST_TIMEOUT_SECONDS,
        connect=60,
        read=REQUEST_TIMEOUT_SECONDS,
        write=120,
        pool=60,
    )
    client_options = {
        "base_url": base_url,
        "api_key": api_key,
        "http_client": httpx.Client(**http_client_options(verify=verify), timeout=timeout),
        "max_retries": 0,
    }
    if user_agent:
        client_options["default_headers"] = {"User-Agent": user_agent}
    return OpenAI(**client_options)


def apimart_generation_payload_from_edit_options(request_options):
    payload = {
        "model": request_options["model"],
        "prompt": request_options["prompt"],
        "n": request_options.get("n", 1),
        "size": "1:1",
        "resolution": "1k",
        "quality": request_options.get("quality", "high"),
        "image_urls": [],
    }
    for image_file in request_options.get("image") or []:
        image_file.seek(0)
        encoded = base64.b64encode(image_file.read()).decode("ascii")
        image_file.seek(0)
        payload["image_urls"].append(f"data:image/png;base64,{encoded}")
    return payload


def run_apimart_generation_request(request_options, verify=True):
    timeout = httpx.Timeout(
        REQUEST_TIMEOUT_SECONDS,
        connect=60,
        read=REQUEST_TIMEOUT_SECONDS,
        write=120,
        pool=60,
    )
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if user_agent:
        headers["User-Agent"] = user_agent
    with httpx.Client(**http_client_options(verify=verify), timeout=timeout) as client:
        response = client.post(
            f"{base_url.rstrip('/')}/images/generations",
            headers=headers,
            json=apimart_generation_payload_from_edit_options(request_options),
        )
        response.raise_for_status()
        return SimpleNamespace(data=response.json().get("data") or [])


def run_openai_request(request_options):
    last_error = None
    for attempt in range(1, max(1, MAX_RETRY_ATTEMPTS) + 1):
        try:
            proxy = system_https_proxy()
            try:
                if is_apimart_endpoint() and request_options.get("model") == "gpt-image-2":
                    return run_apimart_generation_request(request_options, verify=True)
                return openai_client(verify=True).images.edit(**request_options)
            except Exception as error:
                if not (should_allow_untrusted_proxy_certificate(proxy) and is_certificate_error(error)):
                    raise
                if is_apimart_endpoint() and request_options.get("model") == "gpt-image-2":
                    return run_apimart_generation_request(request_options, verify=False)
                return openai_client(verify=False).images.edit(**request_options)
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


def download_image_once(url, output_file):
    user_agent = optional_text("user_agent")
    headers = {"User-Agent": user_agent} if user_agent else {}
    proxy = system_https_proxy()
    if not proxy:
        request = Request(url, headers=headers) if headers else url
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            with Path(output_file).open("wb") as file:
                shutil.copyfileobj(response, file)
        return

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
    return


def download_image(url, output_file):
    last_error = None
    for attempt in range(1, max(1, MAX_RETRY_ATTEMPTS) + 1):
        try:
            return download_image_once(url, output_file)
        except Exception as error:
            last_error = error
            if attempt >= max(1, MAX_RETRY_ATTEMPTS) or not is_retryable_error(error):
                raise
            delay = retry_delay_for_attempt(attempt, error)
            retry_events.append({
                "attempt": attempt,
                "delay_seconds": delay,
                "error": f"download failed: {exception_text(error)[-3800:]}",
            })
            time.sleep(delay)
    raise last_error


def fetch_apimart_task(task_id):
    user_agent = optional_text("user_agent")
    headers = {"Authorization": f"Bearer {api_key}"}
    if user_agent:
        headers["User-Agent"] = user_agent
    url = apimart_task_url(task_id)
    proxy = system_https_proxy()

    if not proxy:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        with httpx.Client(**http_client_options(verify=True), timeout=DOWNLOAD_TIMEOUT_SECONDS) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as error:
        if not (should_allow_untrusted_proxy_certificate(proxy) and is_certificate_error(error)):
            raise

    with httpx.Client(**http_client_options(verify=False), timeout=DOWNLOAD_TIMEOUT_SECONDS) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def wait_for_apimart_task_items(task_id):
    deadline = time.monotonic() + APIMART_TASK_TIMEOUT_SECONDS
    last_payload = {}
    while time.monotonic() < deadline:
        payload = fetch_apimart_task(task_id)
        last_payload = payload
        status = apimart_task_status(payload)
        if status == "completed":
            return apimart_task_image_items(payload)
        if status in {"failed", "cancelled", "canceled", "error"}:
            raise RuntimeError(f"APIMart task {task_id} failed: {payload}")
        time.sleep(max(1, APIMART_TASK_POLL_INTERVAL_SECONDS))
    raise TimeoutError(f"Timed out waiting for APIMart task {task_id}: {last_payload}")


def save_response_item(item, output_file):
    b64_json = getattr(item, "b64_json", None)
    if b64_json:
        Path(output_file).write_bytes(base64.b64decode(b64_json))
        return

    image_url = getattr(item, "url", None)
    if image_url:
        download_image(resolve_image_url(image_url), output_file)
        return

    raise RuntimeError("Image response did not include url or b64_json.")


def indexed_output_path(first_path, index):
    first_path = Path(first_path)
    if index == 1:
        return first_path
    return first_path.with_name(f"{first_path.stem}_{index}{first_path.suffix}")


base_url = normalize_base_url(required_value("base_url"))
api_key = str(required_value("api_key"))
operation_prompt = str(required_value("operation_prompt"))
resolved_size = str(required_value("resolved_size"))
output_dir = Path(required_value("output_dir"))
output_path = Path(required_value("output_path"))
result_json_path = Path(required_value("result_json_path"))
input_images = list(globals().get("input_images") or [])
n = int(globals().get("n") or 1)
quality = optional_text("quality", "high")
output_format = optional_text("output_format", "png")
output_compression = int(globals().get("output_compression") or 80)
background = optional_text("background", "auto")
user = optional_text("user")
user_agent = optional_text("user_agent")
model = optional_text("model", "gpt-image-2")
input_fidelity = optional_text("input_fidelity")
mask_path = optional_text("mask_path")

if not input_images:
    raise ValueError("Missing required parameter: input_images")

output_dir.mkdir(parents=True, exist_ok=True)

image_files = []
mask_file = None
try:
    image_files = [open(path, "rb") for path in input_images]
    if mask_path:
        mask_file = open(mask_path, "rb")

    request_options = {
        "model": model,
        "image": image_files,
        "prompt": operation_prompt,
        "n": n,
        "size": resolved_size,
        "quality": quality,
        "output_format": output_format,
        "background": background,
    }
    if user:
        request_options["user"] = user
    if output_format in {"jpeg", "webp"}:
        request_options["output_compression"] = output_compression
    if input_fidelity and request_options["model"] != "gpt-image-2":
        request_options["input_fidelity"] = input_fidelity
    if mask_file:
        request_options["mask"] = mask_file

    resp = run_openai_request(request_options)
finally:
    for file in image_files:
        file.close()
    if mask_file:
        mask_file.close()

output_paths = []
for index, item in enumerate(response_items(resp), start=1):
    item_output_path = indexed_output_path(output_path, index)
    save_response_item(item, item_output_path)
    output_paths.append(str(item_output_path))

if not output_paths:
    raise RuntimeError("Image response was empty.")

result_json_path.write_text(
    json.dumps({"output_paths": output_paths, "retry_events": retry_events}, ensure_ascii=False),
    encoding="utf-8",
)
