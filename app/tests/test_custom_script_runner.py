import base64
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.custom_script_runner import CUSTOM_SCRIPT_TIMEOUT_SECONDS, run_custom_script


def base_context(tmp_path: Path) -> dict:
    return {
        "base_url": "https://example.test/v1",
        "api_key": "key",
        "operation_prompt": "产品海报",
        "resolved_size": "1024x1024",
        "n": 2,
        "output_dir": str(tmp_path),
        "input_images": [],
        "mode": "text_to_image",
        "quality": "high",
        "output_format": "png",
        "output_compression": 80,
        "background": "auto",
        "moderation": "low",
        "user": "",
        "use_system_proxy": False,
    }


def test_v061_custom_script_default_timeout_is_3600_seconds():
    assert CUSTOM_SCRIPT_TIMEOUT_SECONDS == 3600


def test_custom_script_runner_accepts_software_output_path(tmp_path):
    result = run_custom_script(
        "Path(output_path).write_bytes(b'image')",
        base_context(tmp_path),
        timeout_seconds=5,
    )

    assert len(result.output_paths) == 1
    assert Path(result.output_path).parent == tmp_path
    assert Path(result.output_path).read_bytes() == b"image"


def test_custom_script_runner_prefers_injected_output_path_when_present(tmp_path):
    injected_output = tmp_path / "software-chosen.png"
    injected_result = tmp_path / "software-chosen.result.json"

    result = run_custom_script(
        "Path(output_path).write_bytes(b'injected')",
        {
            **base_context(tmp_path),
            "output_path": str(injected_output),
            "result_json_path": str(injected_result),
        },
        timeout_seconds=5,
    )

    assert result.output_paths == [str(injected_output)]
    assert injected_output.read_bytes() == b"injected"


def test_custom_script_runner_rejects_injected_output_path_outside_output_dir(tmp_path):
    outside = tmp_path.parent / "outside.png"

    try:
        run_custom_script(
            "Path(output_path).write_bytes(b'outside')",
            {
                **base_context(tmp_path),
                "output_path": str(outside),
            },
            timeout_seconds=5,
        )
    except ValueError as exc:
        assert "输出路径必须位于生成路径内" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_custom_script_runner_accepts_multiple_paths_from_result_json(tmp_path):
    script = """
from pathlib import Path
import json

first = Path(output_path)
second = first.with_name(first.stem + "_2" + first.suffix)
first.write_bytes(b"one")
second.write_bytes(b"two")
Path(result_json_path).write_text(
    json.dumps({"output_paths": [str(first), str(second)]}),
    encoding="utf-8",
)
"""

    result = run_custom_script(script, base_context(tmp_path), timeout_seconds=5)

    assert len(result.output_paths) == 2
    assert [Path(path).read_bytes() for path in result.output_paths] == [b"one", b"two"]
    assert all(Path(path).parent == tmp_path for path in result.output_paths)


def test_custom_script_runner_rejects_outputs_outside_output_dir(tmp_path):
    outside = tmp_path.parent / "outside.png"
    script = f"""
from pathlib import Path
import json

Path(output_path).write_bytes(b"image")
Path({str(outside)!r}).write_bytes(b"outside")
Path(result_json_path).write_text(
    json.dumps({{"output_paths": [str(Path({str(outside)!r}))]}}),
    encoding="utf-8",
)
"""

    try:
        run_custom_script(script, base_context(tmp_path), timeout_seconds=5)
    except ValueError as exc:
        assert "输出路径必须位于生成路径内" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_custom_script_runner_rejects_missing_output(tmp_path):
    try:
        run_custom_script("print('no output')", base_context(tmp_path), timeout_seconds=5)
    except ValueError as exc:
        assert "自定义代码没有生成图片" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_v042_openai_text_script_normalizes_root_base_url_to_v1(tmp_path):
    script = (Path(__file__).resolve().parents[2] / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")
    captured = {}

    class FakeItem:
        b64_json = "b25l"
        url = None

    class FakeImages:
        def generate(self, **kwargs):
            return type("Resp", (), {"data": [FakeItem()]})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = FakeImages()

    context = base_context(tmp_path)
    context.update({
        "OpenAI": FakeClient,
        "base_url": "https://imgv2.aiapis.help/",
        "api_key": "injected-key",
        "operation_prompt": "生成图标",
        "output_path": str(tmp_path / "root-url.png"),
        "result_json_path": str(tmp_path / "result.json"),
    })

    exec(compile(script, "openai_text_to_image.py", "exec"), context, context)

    assert captured["client_kwargs"]["base_url"] == "https://imgv2.aiapis.help/v1"


def test_v042_openai_image_script_normalizes_root_base_url_to_v1(tmp_path):
    script = (Path(__file__).resolve().parents[2] / "files" / "openai_image_to_image.py").read_text(encoding="utf-8")
    input_path = tmp_path / "input.png"
    input_path.write_bytes(b"input")
    captured = {}

    class FakeItem:
        b64_json = "ZWRpdA=="
        url = None

    class FakeImages:
        def edit(self, **kwargs):
            return type("Resp", (), {"data": [FakeItem()]})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = FakeImages()

    context = base_context(tmp_path)
    context.update({
        "OpenAI": FakeClient,
        "base_url": "https://imgv2.aiapis.help/",
        "api_key": "injected-key",
        "operation_prompt": "编辑图片",
        "input_images": [str(input_path)],
        "output_path": str(tmp_path / "root-url-edit.png"),
        "result_json_path": str(tmp_path / "result.json"),
    })

    exec(compile(script, "openai_image_to_image.py", "exec"), context, context)

    assert captured["client_kwargs"]["base_url"] == "https://imgv2.aiapis.help/v1"


def test_v042_openai_text_script_uses_injected_params_and_handles_url_and_base64(tmp_path):
    script = (Path(__file__).resolve().parents[2] / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")
    captured = {}

    class FakeItem:
        def __init__(self, url=None, b64_json=None):
            self.url = url
            self.b64_json = b64_json

    class FakeImages:
        def generate(self, **kwargs):
            captured["generate_kwargs"] = kwargs
            return type("Resp", (), {
                "data": [
                    FakeItem(url="files/one.png"),
                    FakeItem(b64_json="dHdv"),
                ]
            })()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = FakeImages()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size=-1):
            if captured.get("download_read"):
                return b""
            captured["download_read"] = True
            return b"one"

    def fake_urlopen(request, timeout=60):
        captured["download_url"] = request.full_url
        captured["download_ua"] = request.headers.get("User-agent")
        captured["download_timeout"] = timeout
        return FakeResponse()

    context = base_context(tmp_path)
    context.update({
        "OpenAI": FakeClient,
        "urlopen": fake_urlopen,
        "api_key": "injected-key",
        "base_url": "https://example.test/v1",
        "user_agent": "Injected-UA",
        "operation_prompt": "生成海报",
        "resolved_size": "1536x864",
        "n": 2,
        "output_path": str(tmp_path / "first.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "output_format": "webp",
        "output_compression": 71,
        "quality": "medium",
        "background": "opaque",
        "moderation": "low",
        "user": "local-user",
        "model": "custom-image-model",
    })

    exec(compile(script, "openai_text_to_image.py", "exec"), context, context)

    client_kwargs = captured["client_kwargs"]
    assert client_kwargs.pop("http_client").trust_env is False
    assert client_kwargs == {
        "base_url": "https://example.test/v1",
        "api_key": "injected-key",
        "max_retries": 0,
        "default_headers": {"User-Agent": "Injected-UA"},
    }
    assert captured["generate_kwargs"] == {
        "model": "custom-image-model",
        "prompt": "生成海报",
        "size": "1536x864",
        "quality": "medium",
        "output_format": "webp",
        "background": "opaque",
        "moderation": "low",
        "n": 2,
        "user": "local-user",
        "output_compression": 71,
    }
    assert captured["download_url"] == "https://example.test/v1/files/one.png"
    assert captured["download_ua"] == "Injected-UA"
    assert captured["download_timeout"] == 120
    result_paths = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))["output_paths"]
    assert result_paths == [str(tmp_path / "first.png"), str(tmp_path / "first_2.png")]
    assert (tmp_path / "first.png").read_bytes() == b"one"
    assert (tmp_path / "first_2.png").read_bytes() == b"two"


def test_v042_openai_text_script_retries_untrusted_proxy_certificate_with_system_proxy(tmp_path, monkeypatch):
    script = (Path(__file__).resolve().parents[2] / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")
    captured = {"client_kwargs": []}

    class FakeItem:
        b64_json = "b2s="
        url = None

    class FakeImages:
        def __init__(self, owner):
            self.owner = owner

        def generate(self, **kwargs):
            http_client = self.owner["http_client"]
            if http_client.verify is not False:
                raise RuntimeError("Connection error.") from httpx.ConnectError(
                    "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
                )
            return type("Resp", (), {"data": [FakeItem()]})()

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            captured["client_kwargs"].append(kwargs)
            self.images = FakeImages(kwargs)

    class FakeHttpClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.trust_env = kwargs.get("trust_env")
            self.proxies = kwargs.get("proxies")
            self.verify = kwargs.get("verify", True)

    monkeypatch.setattr(httpx, "Client", FakeHttpClient)

    context = base_context(tmp_path)
    context.update({
        "OpenAI": FakeClient,
        "httpx": httpx,
        "api_key": "injected-key",
        "base_url": "https://example.test/",
        "operation_prompt": "生成图片",
        "resolved_size": "1024x1024",
        "output_path": str(tmp_path / "proxy.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "use_system_proxy": True,
        "system_proxy": "http://127.0.0.1:7892",
        "allow_untrusted_proxy_certificate": True,
    })

    exec(compile(script, "openai_text_to_image.py", "exec"), context, context)

    http_clients = [item["http_client"] for item in captured["client_kwargs"]]
    assert http_clients[0].proxies == "http://127.0.0.1:7892"
    assert http_clients[0].verify is True
    assert http_clients[1].proxies == "http://127.0.0.1:7892"
    assert http_clients[1].verify is False
    assert (tmp_path / "proxy.png").read_bytes() == b"ok"


def test_v044_openai_text_script_bypasses_system_proxy_for_loopback_base_url(tmp_path, monkeypatch):
    script = (Path(__file__).resolve().parents[2] / "files" / "openai_text_to_image.py").read_text(encoding="utf-8")
    captured = {}

    class FakeItem:
        b64_json = "bG9jYWw="
        url = None

    class FakeImages:
        def generate(self, **kwargs):
            return type("Resp", (), {"data": [FakeItem()]})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = FakeImages()

    class FakeHttpClient:
        def __init__(self, **kwargs):
            self.proxies = kwargs.get("proxies")

    monkeypatch.setattr(httpx, "Client", FakeHttpClient)

    context = base_context(tmp_path)
    context.update({
        "OpenAI": FakeClient,
        "httpx": httpx,
        "api_key": "injected-key",
        "base_url": "http://127.0.0.1:8806/",
        "operation_prompt": "本地 mock",
        "resolved_size": "1024x1024",
        "output_path": str(tmp_path / "loopback.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "use_system_proxy": True,
        "system_proxy": "http://127.0.0.1:7892",
    })

    exec(compile(script, "openai_text_to_image.py", "exec"), context, context)

    assert captured["client_kwargs"]["http_client"].proxies is None
    assert (tmp_path / "loopback.png").read_bytes() == b"local"


def test_v042_openai_image_script_uses_all_input_images_in_order(tmp_path):
    script = (Path(__file__).resolve().parents[2] / "files" / "openai_image_to_image.py").read_text(encoding="utf-8")
    first_input = tmp_path / "input-1.png"
    second_input = tmp_path / "input-2.png"
    mask_path = tmp_path / "mask.png"
    first_input.write_bytes(b"one")
    second_input.write_bytes(b"two")
    mask_path.write_bytes(b"mask")
    captured = {}

    class FakeItem:
        b64_json = "ZWRpdA=="
        url = None

    class FakeImages:
        def edit(self, **kwargs):
            captured["edit_kwargs"] = kwargs
            captured["image_names"] = [item.name for item in kwargs["image"]]
            captured["image_closed_during_call"] = [item.closed for item in kwargs["image"]]
            captured["mask_name"] = kwargs["mask"].name
            captured["mask_closed_during_call"] = kwargs["mask"].closed
            return type("Resp", (), {"data": [FakeItem()]})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = FakeImages()

    context = base_context(tmp_path)
    context.update({
        "OpenAI": FakeClient,
        "api_key": "injected-key",
        "base_url": "https://example.test/v1",
        "user_agent": "",
        "operation_prompt": "图1和图2融合",
        "resolved_size": "1024x1024",
        "n": 1,
        "output_path": str(tmp_path / "edited.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "input_images": [str(first_input), str(second_input)],
        "input_fidelity": "high",
        "mask_path": str(mask_path),
        "output_format": "png",
        "output_compression": 80,
        "quality": "high",
        "background": "auto",
        "user": "",
        "model": "custom-edit-model",
    })

    exec(compile(script, "openai_image_to_image.py", "exec"), context, context)

    client_kwargs = captured["client_kwargs"]
    assert client_kwargs.pop("http_client").trust_env is False
    assert client_kwargs == {
        "base_url": "https://example.test/v1",
        "api_key": "injected-key",
        "max_retries": 0,
    }
    assert captured["image_names"] == [str(first_input), str(second_input)]
    assert captured["image_closed_during_call"] == [False, False]
    assert captured["mask_name"] == str(mask_path)
    assert captured["mask_closed_during_call"] is False
    edit_kwargs = captured["edit_kwargs"]
    assert edit_kwargs["model"] == "custom-edit-model"
    assert edit_kwargs["prompt"] == "图1和图2融合"
    assert edit_kwargs["n"] == 1
    assert edit_kwargs["size"] == "1024x1024"
    assert edit_kwargs["quality"] == "high"
    assert edit_kwargs["output_format"] == "png"
    assert edit_kwargs["background"] == "auto"
    assert edit_kwargs["input_fidelity"] == "high"
    assert "output_compression" not in edit_kwargs
    assert (tmp_path / "edited.png").read_bytes() == b"edit"
    result_paths = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))["output_paths"]
    assert result_paths == [str(tmp_path / "edited.png")]


def test_v042_openai_image_script_retries_untrusted_proxy_certificate_with_system_proxy(tmp_path, monkeypatch):
    script = (Path(__file__).resolve().parents[2] / "files" / "openai_image_to_image.py").read_text(encoding="utf-8")
    input_path = tmp_path / "input.png"
    input_path.write_bytes(b"input")
    captured = {"client_kwargs": []}

    class FakeItem:
        b64_json = "ZWRpdA=="
        url = None

    class FakeImages:
        def __init__(self, owner):
            self.owner = owner

        def edit(self, **kwargs):
            http_client = self.owner["http_client"]
            if http_client.verify is not False:
                raise RuntimeError("Connection error.") from httpx.ConnectError(
                    "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
                )
            return type("Resp", (), {"data": [FakeItem()]})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"].append(kwargs)
            self.images = FakeImages(kwargs)

    class FakeHttpClient:
        def __init__(self, **kwargs):
            self.trust_env = kwargs.get("trust_env")
            self.proxies = kwargs.get("proxies")
            self.verify = kwargs.get("verify", True)

    monkeypatch.setattr(httpx, "Client", FakeHttpClient)

    context = base_context(tmp_path)
    context.update({
        "OpenAI": FakeClient,
        "httpx": httpx,
        "api_key": "injected-key",
        "base_url": "https://example.test/",
        "operation_prompt": "编辑图片",
        "resolved_size": "1024x1024",
        "input_images": [str(input_path)],
        "output_path": str(tmp_path / "proxy-edit.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "use_system_proxy": True,
        "system_proxy": "http://127.0.0.1:7892",
        "allow_untrusted_proxy_certificate": True,
    })

    exec(compile(script, "openai_image_to_image.py", "exec"), context, context)

    http_clients = [item["http_client"] for item in captured["client_kwargs"]]
    assert http_clients[0].proxies == "http://127.0.0.1:7892"
    assert http_clients[0].verify is True
    assert http_clients[1].proxies == "http://127.0.0.1:7892"
    assert http_clients[1].verify is False
    assert (tmp_path / "proxy-edit.png").read_bytes() == b"edit"


def test_v044_openai_image_script_bypasses_system_proxy_for_localhost_base_url(tmp_path, monkeypatch):
    script = (Path(__file__).resolve().parents[2] / "files" / "openai_image_to_image.py").read_text(encoding="utf-8")
    input_path = tmp_path / "input.png"
    input_path.write_bytes(b"input")
    captured = {}

    class FakeItem:
        b64_json = "ZWRpdC1sb2NhbA=="
        url = None

    class FakeImages:
        def edit(self, **kwargs):
            return type("Resp", (), {"data": [FakeItem()]})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = FakeImages()

    class FakeHttpClient:
        def __init__(self, **kwargs):
            self.proxies = kwargs.get("proxies")

    monkeypatch.setattr(httpx, "Client", FakeHttpClient)

    context = base_context(tmp_path)
    context.update({
        "OpenAI": FakeClient,
        "httpx": httpx,
        "api_key": "injected-key",
        "base_url": "http://localhost:8806/",
        "operation_prompt": "本地 mock 图生图",
        "resolved_size": "1024x1024",
        "input_images": [str(input_path)],
        "output_path": str(tmp_path / "loopback-edit.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "use_system_proxy": True,
        "system_proxy": "http://127.0.0.1:7892",
    })

    exec(compile(script, "openai_image_to_image.py", "exec"), context, context)

    assert captured["client_kwargs"]["http_client"].proxies is None
    assert (tmp_path / "loopback-edit.png").read_bytes() == b"edit-local"


def test_v058_openai_google_text_script_uses_chat_completions_and_injected_params(tmp_path, monkeypatch):
    script = (Path(__file__).resolve().parents[2] / "files" / "google_b2_text_to_image_xiaoyun.py").read_text(encoding="utf-8")
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "data:image/png;base64,b2s="
                        }
                    }
                ]
            }

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["post_url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    context = base_context(tmp_path)
    context.update({
        "httpx": httpx,
        "base_url": "https://www.xiaoyunapi.com/",
        "api_key": "injected-key",
        "model": "gemini-3.1-flash-image-preview",
        "operation_prompt": "画10只鱼",
        "output_path": str(tmp_path / "google-text.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "user_agent": "Injected-UA",
        "google_role": "user",
        "google_max_tokens": 4096,
        "google_temperature": "0.7",
        "google_top_p": "0.9",
        "google_stream": False,
        "google_stop": "END",
        "google_presence_penalty": "0.1",
        "google_frequency_penalty": "0.2",
        "google_logit_bias": "{\"42\": 1}",
        "google_user": "operator",
        "google_response_format": "{\"type\":\"json_object\"}",
        "google_seen": "scene-a",
        "google_tools": "[{\"type\":\"function\"}]",
        "google_tool_choice": "auto",
        "use_system_proxy": False,
    })

    exec(compile(script, "google_b2_text_to_image_xiaoyun.py", "exec"), context, context)

    assert captured["post_url"] == "https://www.xiaoyunapi.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer injected-key"
    assert captured["headers"]["User-Agent"] == "Injected-UA"
    assert captured["client_kwargs"]["trust_env"] is False
    payload = captured["payload"]
    assert payload["model"] == "gemini-3.1-flash-image-preview"
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == [{"type": "text", "text": "画10只鱼"}]
    assert payload["max_tokens"] == 4096
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.9
    assert payload["stream"] is False
    assert payload["stop"] == "END"
    assert payload["presence_penalty"] == 0.1
    assert payload["frequency_penalty"] == 0.2
    assert payload["logit_bias"] == {"42": 1}
    assert payload["user"] == "operator"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["seen"] == "scene-a"
    assert payload["tools"] == [{"type": "function"}]
    assert payload["tool_choice"] == "auto"
    assert (tmp_path / "google-text.png").read_bytes() == b"ok"
    result_paths = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))["output_paths"]
    assert result_paths == [str(tmp_path / "google-text.png")]


def test_v059_openai_google_text_script_treats_none_placeholder_as_empty(tmp_path, monkeypatch):
    script = (Path(__file__).resolve().parents[2] / "files" / "google_b2_text_to_image_xiaoyun.py").read_text(encoding="utf-8")
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"image": base64.b64encode(b"\x89PNG\r\n\x1a\nout").decode("ascii")}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    context = base_context(tmp_path)
    context.update({
        "httpx": httpx,
        "base_url": "https://www.xiaoyunapi.com/",
        "api_key": "injected-key",
        "model": "gemini-3.1-flash-image-preview",
        "operation_prompt": "画10只鱼",
        "output_path": str(tmp_path / "google-none.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "user_agent": "None",
        "google_role": "user",
        "google_max_tokens": 4096,
        "google_temperature": "None",
        "google_top_p": "",
        "google_stream": False,
        "google_stop": None,
        "google_presence_penalty": "None",
        "google_frequency_penalty": "",
        "google_logit_bias": "None",
        "google_user": "None",
        "google_response_format": "",
        "google_seen": None,
        "google_tools": "None",
        "google_tool_choice": "",
        "use_system_proxy": False,
    })

    exec(compile(script, "google_b2_text_to_image_xiaoyun.py", "exec"), context, context)

    payload = captured["payload"]
    assert "User-Agent" not in captured["headers"]
    assert payload["max_tokens"] == 4096
    assert payload["stream"] is False
    for key in [
        "temperature",
        "top_p",
        "stop",
        "presence_penalty",
        "frequency_penalty",
        "logit_bias",
        "user",
        "response_format",
        "seen",
        "tools",
        "tool_choice",
    ]:
        assert key not in payload
    assert (tmp_path / "google-none.png").read_bytes() == b"\x89PNG\r\n\x1a\nout"


def test_v058_openai_google_image_script_sends_all_input_images_in_order(tmp_path, monkeypatch):
    script = (Path(__file__).resolve().parents[2] / "files" / "google_b2_image_to_image_xiaoyun.py").read_text(encoding="utf-8")
    first_input = tmp_path / "input-1.png"
    second_input = tmp_path / "input-2.jpg"
    first_input.write_bytes(b"\x89PNG\r\n\x1a\none")
    second_input.write_bytes(b"\xff\xd8\xfftwo")
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"image": base64.b64encode(b"\x89PNG\r\n\x1a\nout").decode("ascii")}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["post_url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    context = base_context(tmp_path)
    context.update({
        "httpx": httpx,
        "base_url": "https://www.xiaoyunapi.com/v1/",
        "api_key": "injected-key",
        "model": "gemini-3.1-flash-image-preview",
        "operation_prompt": "在图1和图2上添加10只鱼",
        "input_images": [str(first_input), str(second_input)],
        "output_path": str(tmp_path / "google-image.png"),
        "result_json_path": str(tmp_path / "result.json"),
        "google_role": "user",
        "google_max_tokens": 4096,
        "google_stream": False,
        "use_system_proxy": False,
    })

    exec(compile(script, "google_b2_image_to_image_xiaoyun.py", "exec"), context, context)

    assert captured["post_url"] == "https://www.xiaoyunapi.com/v1/chat/completions"
    content = captured["payload"]["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "在图1和图2上添加10只鱼"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[2]["type"] == "image_url"
    assert content[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert (tmp_path / "google-image.png").read_bytes() == b"\x89PNG\r\n\x1a\nout"


