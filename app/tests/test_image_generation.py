from pathlib import Path
import base64
import sys
from types import SimpleNamespace
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.image_generation import generate_image, provider_from_config
from backend.image_providers.base import ImageGenerationResult, ImageProvider
from backend.image_providers.aiapis_gpt_image_2 import AIAPISGptImage2Provider


class FakeProvider(ImageProvider):
    name = "fake"

    def text_to_image(self, prompt, output_dir, options):
        path = Path(output_dir) / "text.png"
        path.write_bytes(b"image")
        return ImageGenerationResult(output_path=str(path), provider=self.name)

    def image_to_image(self, prompt, input_images, output_dir, options):
        path = Path(output_dir) / "edit.png"
        path.write_bytes(b"image")
        return ImageGenerationResult(output_path=str(path), provider=self.name)


class MutatingProvider(FakeProvider):
    def image_to_image(self, prompt, input_images, output_dir, options):
        input_images.append("provider-added.png")
        options["provider_added"] = True
        return super().image_to_image(prompt, input_images, output_dir, options)


class NestedMutatingProvider(FakeProvider):
    def text_to_image(self, prompt, output_dir, options):
        options["payload"]["size"] = "changed"
        return super().text_to_image(prompt, output_dir, options)


def test_text_to_image_generates_result(tmp_path):
    result = generate_image(
        provider=FakeProvider({}),
        mode="text_to_image",
        prompt="产品海报",
        input_images=[],
        output_dir=str(tmp_path),
        options={},
    )

    assert result.output_path.endswith("text.png")
    assert result.provider == "fake"


def test_image_to_image_requires_input_image(tmp_path):
    output_dir = tmp_path / "rejected-output"

    try:
        generate_image(
            provider=FakeProvider({}),
            mode="image_to_image",
            prompt="改成海报",
            input_images=[],
            output_dir=str(output_dir),
            options={},
        )
    except ValueError as exc:
        assert "图生图需要至少 1 张输入图" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

    assert not output_dir.exists()


def test_provider_mutation_does_not_change_caller_inputs(tmp_path):
    input_images = ["source.png"]
    options = {"size": "1024x1024"}

    generate_image(
        provider=MutatingProvider({}),
        mode="image_to_image",
        prompt="改成海报",
        input_images=input_images,
        output_dir=str(tmp_path),
        options=options,
    )

    assert input_images == ["source.png"]
    assert options == {"size": "1024x1024"}


def test_provider_nested_options_mutation_does_not_change_caller_options(tmp_path):
    options = {"payload": {"size": "1024x1024"}}

    generate_image(
        provider=NestedMutatingProvider({}),
        mode="text_to_image",
        prompt="产品海报",
        input_images=[],
        output_dir=str(tmp_path),
        options=options,
    )

    assert options == {"payload": {"size": "1024x1024"}}


def test_provider_from_config_returns_aiapis_provider():
    provider = provider_from_config(
        {
            "active_provider": "custom_aiapis",
            "providers": {
                "custom_aiapis": {
                    "adapter": "openai",
                    "base_url": "https://img.aiapis.help/v1",
                    "api_key": "test-key",
                    "model": "gpt-image-2",
                }
            },
        }
    )

    assert isinstance(provider, AIAPISGptImage2Provider)
    assert provider.name == "aiapis_gpt_image_2"
    assert provider.config["api_key"] == "test-key"


def test_aiapis_client_disables_sdk_retries():
    provider = AIAPISGptImage2Provider(
        {
            "base_url": "https://img.aiapis.help/v1",
            "api_key": "test-key",
        }
    )

    client = provider._client()

    assert client.max_retries == 0


def test_provider_capabilities_are_adapter_level_not_provider_level():
    from backend.image_generation import PROVIDER_CAPABILITIES

    assert set(PROVIDER_CAPABILITIES) == {
        "openai",
        "aiapis_gpt_image_2",
        "openai-google",
        "sysrv-google",
        "apimart-openai",
        "google",
        "other",
    }
    assert PROVIDER_CAPABILITIES["openai"]["implemented"] is True
    assert PROVIDER_CAPABILITIES["openai"]["call_methods"] == {"gpt-image-2", "response"}
    assert PROVIDER_CAPABILITIES["openai-google"]["implemented"] is True
    assert PROVIDER_CAPABILITIES["openai-google"]["call_methods"] == {"gpt-image-2"}
    assert PROVIDER_CAPABILITIES["sysrv-google"]["implemented"] is True
    assert PROVIDER_CAPABILITIES["sysrv-google"]["call_methods"] == {"gpt-image-2"}
    assert PROVIDER_CAPABILITIES["apimart-openai"]["implemented"] is True
    assert PROVIDER_CAPABILITIES["apimart-openai"]["call_methods"] == {"gpt-image-2"}
    assert PROVIDER_CAPABILITIES["google"]["implemented"] is False
    assert PROVIDER_CAPABILITIES["google"]["message"] == "Google adapter 暂未实现。"
    assert PROVIDER_CAPABILITIES["other"]["implemented"] is False
    assert PROVIDER_CAPABILITIES["other"]["message"] == "Other adapter 暂未实现。"


def test_provider_from_config_rejects_empty_active_provider():
    try:
        provider_from_config({"active_provider": "", "providers": {}})
    except ValueError as exc:
        assert "未选择图片生成 Provider" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_provider_from_config_rejects_unknown_adapter():
    try:
        provider_from_config(
            {
                "active_provider": "custom",
                "providers": {
                    "custom": {
                        "adapter": "missing_adapter",
                    }
                },
            }
        )
    except ValueError as exc:
        assert "未知图片生成适配器：missing_adapter" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_provider_from_config_returns_google_placeholder_provider():
    provider = provider_from_config(
        {
            "active_provider": "google_proxy",
            "providers": {
                "google_proxy": {
                    "adapter": "google",
                    "display_name": "Google Proxy",
                }
            },
        }
    )

    try:
        provider.text_to_image("产品海报", "D:\\out", {})
    except ValueError as exc:
        assert "Google adapter 暂未实现。" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_v058_provider_from_config_openai_google_does_not_fall_back_to_images_provider():
    provider = provider_from_config(
        {
            "active_provider": "xiaoyun",
            "providers": {
                "xiaoyun": {
                    "adapter": "openai-google",
                    "display_name": "Xiaoyun",
                }
            },
        }
    )

    try:
        provider.text_to_image("产品海报", "D:\\out", {})
    except ValueError as exc:
        assert "openai-google adapter 需要通过共享脚本或自定义脚本生成。" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_provider_from_config_returns_other_placeholder_provider():
    provider = provider_from_config(
        {
            "active_provider": "custom_proxy",
            "providers": {
                "custom_proxy": {
                    "adapter": "other",
                    "display_name": "Custom Proxy",
                }
            },
        }
    )

    try:
        provider.text_to_image("产品海报", "D:\\out", {})
    except ValueError as exc:
        assert "Other adapter 暂未实现。" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_provider_from_config_rejects_unknown_provider():
    try:
        provider_from_config({"active_provider": "missing", "providers": {}})
    except ValueError as exc:
        assert "未知图片生成提供方" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_aiapis_request_options_uses_official_size_without_resolution():
    provider = AIAPISGptImage2Provider(
        {
            "model": "gpt-image-2",
            "quality": "high",
            "output_format": "png",
            "background": "auto",
            "moderation": "low",
        }
    )

    request_options = provider._request_options(
        "产品海报",
        {"resolved_size": "3840x2160", "n": 2},
    )

    assert request_options["model"] == "gpt-image-2"
    assert request_options["prompt"] == "产品海报"
    assert request_options["size"] == "3840x2160"
    assert request_options["n"] == 2
    assert request_options["quality"] == "high"
    assert request_options["output_format"] == "png"
    assert request_options["background"] == "auto"
    assert request_options["moderation"] == "low"
    assert "stream" not in request_options
    assert "partial_images" not in request_options
    assert "resolution" not in request_options
    assert "output_compression" not in request_options


def test_aiapis_response_request_options_use_responses_api_tool_shape():
    provider = AIAPISGptImage2Provider(
        {
            "openai_call_method": "response",
            "quality": "medium",
            "output_format": "webp",
            "output_compression": 66,
            "background": "transparent",
            "moderation": "low",
        }
    )

    request_options = provider._responses_request_options(
        "产品海报",
        {"resolved_size": "1536x864", "n": 4},
    )
    tool = request_options["tools"][0]

    assert request_options["model"] == "gpt-5.5"
    assert request_options["input"] == "产品海报"
    assert request_options["stream"] is False
    assert request_options["tool_choice"] == {"type": "image_generation"}
    assert tool["type"] == "image_generation"
    assert tool["action"] == "generate"
    assert tool["model"] == "gpt-image-1.5"
    assert tool["size"] == "1536x864"
    assert tool["quality"] == "medium"
    assert tool["output_format"] == "webp"
    assert tool["output_compression"] == 66
    assert tool["background"] == "transparent"
    assert tool["moderation"] == "low"
    assert tool["partial_images"] == 0
    assert "n" not in request_options


def test_aiapis_save_responses_result_decodes_image_generation_call(tmp_path, monkeypatch):
    provider = AIAPISGptImage2Provider(
        {
            "openai_call_method": "response",
            "output_format": "png",
        }
    )
    output_path = tmp_path / "response.png"
    encoded = base64.b64encode(b"response-image").decode("ascii")

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: output_path)

    result = provider._save_responses_result(
        SimpleNamespace(
            output=[
                SimpleNamespace(type="message", result="ignored"),
                SimpleNamespace(type="image_generation_call", result=encoded),
            ],
        ),
        str(tmp_path),
    )

    assert result.output_path == str(output_path)
    assert output_path.read_bytes() == b"response-image"


def test_aiapis_request_options_adds_output_compression_for_jpeg_and_webp():
    jpeg_provider = AIAPISGptImage2Provider(
        {
            "model": "gpt-image-2",
            "output_format": "jpeg",
            "output_compression": 72,
        }
    )
    webp_provider = AIAPISGptImage2Provider(
        {
            "model": "gpt-image-2",
            "output_format": "webp",
            "output_compression": 64,
        }
    )

    jpeg_options = jpeg_provider._request_options("产品海报", {"resolved_size": "1024x1024"})
    webp_options = webp_provider._request_options("产品海报", {"resolved_size": "1024x1024"})

    assert jpeg_options["output_compression"] == 72
    assert webp_options["output_compression"] == 64


def test_aiapis_output_path_uses_output_format_extension(tmp_path):
    png_provider = AIAPISGptImage2Provider({"output_format": "png"})
    jpeg_provider = AIAPISGptImage2Provider({"output_format": "jpeg"})
    webp_provider = AIAPISGptImage2Provider({"output_format": "webp"})

    assert png_provider._output_path(str(tmp_path)).suffix == ".png"
    assert jpeg_provider._output_path(str(tmp_path)).suffix == ".jpeg"
    assert webp_provider._output_path(str(tmp_path)).suffix == ".webp"


def test_aiapis_relative_url_preserves_base_path(tmp_path, monkeypatch):
    provider = AIAPISGptImage2Provider(
        {
            "base_url": "https://img.aiapis.help/v1",
            "api_key": "test-key",
        }
    )
    output_path = tmp_path / "result.png"
    downloaded = {}

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: output_path)

    def fake_download(url, target):
        downloaded["url"] = url
        Path(target).write_bytes(b"image")

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.download_url",
        fake_download,
    )

    result = provider._save_result(
        SimpleNamespace(data=[SimpleNamespace(url="files/x.png")]),
        str(tmp_path),
    )

    assert downloaded["url"] == "https://img.aiapis.help/v1/files/x.png"
    assert result.output_path == str(output_path)


def test_aiapis_save_result_preserves_all_returned_images(tmp_path, monkeypatch):
    provider = AIAPISGptImage2Provider(
        {
            "base_url": "https://img.aiapis.help/v1",
            "api_key": "test-key",
        }
    )
    output_paths = [tmp_path / "one.png", tmp_path / "two.png"]
    output_iter = iter(output_paths)
    downloaded_urls = []

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: next(output_iter))

    def fake_download(url, target):
        downloaded_urls.append(url)
        Path(target).write_bytes(f"image:{url}".encode("utf-8"))

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.download_url",
        fake_download,
    )

    result = provider._save_result(
        SimpleNamespace(
            data=[
                SimpleNamespace(url="files/one.png"),
                SimpleNamespace(url="files/two.png"),
            ]
        ),
        str(tmp_path),
    )

    assert result.output_paths == [str(path) for path in output_paths]
    assert result.output_path == str(output_paths[-1])
    assert downloaded_urls == [
        "https://img.aiapis.help/v1/files/one.png",
        "https://img.aiapis.help/v1/files/two.png",
    ]


def test_aiapis_relative_url_uses_default_base_path_when_config_omits_base_url(
    tmp_path, monkeypatch
):
    provider = AIAPISGptImage2Provider({"api_key": "test-key"})
    output_path = tmp_path / "result.png"
    downloaded = {}

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: output_path)

    def fake_download(url, target):
        downloaded["url"] = url
        Path(target).write_bytes(b"image")

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.download_url",
        fake_download,
    )

    provider._save_result(
        SimpleNamespace(data=[SimpleNamespace(url="files/x.png")]),
        str(tmp_path),
    )

    assert downloaded["url"] == "https://img.aiapis.help/v1/files/x.png"


def test_aiapis_root_relative_url_resolves_from_origin(tmp_path, monkeypatch):
    provider = AIAPISGptImage2Provider(
        {
            "base_url": "https://img.aiapis.help/v1",
            "api_key": "test-key",
        }
    )
    output_path = tmp_path / "result.png"
    downloaded = {}

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: output_path)

    def fake_download(url, target):
        downloaded["url"] = url
        Path(target).write_bytes(b"image")

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.download_url",
        fake_download,
    )

    provider._save_result(
        SimpleNamespace(data=[SimpleNamespace(url="/p/img.png")]),
        str(tmp_path),
    )

    assert downloaded["url"] == "https://img.aiapis.help/p/img.png"


def test_aiapis_url_download_uses_temp_file_then_atomic_replace(tmp_path, monkeypatch):
    provider = AIAPISGptImage2Provider(
        {
            "base_url": "https://img.aiapis.help/v1",
            "api_key": "test-key",
        }
    )
    output_path = tmp_path / "result.png"
    writes = {}

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: output_path)

    def fake_download(url, target):
        writes["target"] = Path(target)
        assert Path(target) != output_path
        assert str(target).endswith(".tmp")
        Path(target).write_bytes(b"downloaded")

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.download_url",
        fake_download,
    )

    provider._save_result(
        SimpleNamespace(data=[SimpleNamespace(url="files/x.png")]),
        str(tmp_path),
    )

    assert writes["target"].exists() is False
    assert output_path.read_bytes() == b"downloaded"


def test_aiapis_url_download_failure_does_not_leave_final_file(tmp_path, monkeypatch):
    provider = AIAPISGptImage2Provider(
        {
            "base_url": "https://img.aiapis.help/v1",
            "api_key": "test-key",
        }
    )
    output_path = tmp_path / "result.png"

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: output_path)

    def failing_download(url, target):
        Path(target).write_bytes(b"partial")
        raise TimeoutError("download timed out")

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.download_url",
        failing_download,
    )

    try:
        provider._save_result(
            SimpleNamespace(data=[SimpleNamespace(url="files/x.png")]),
            str(tmp_path),
        )
    except TimeoutError:
        pass
    else:
        raise AssertionError("Expected TimeoutError")

    assert output_path.exists() is False


def test_aiapis_client_uses_configured_user_agent(monkeypatch):
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.OpenAI",
        fake_openai,
    )

    provider = AIAPISGptImage2Provider(
        {
            "base_url": "https://img.aiapis.help/v1",
            "api_key": "test-key",
            "user_agent": "Mozilla/5.0 PowerShell/7.4",
        }
    )

    provider._client()

    assert captured["base_url"] == "https://img.aiapis.help/v1"
    assert captured["api_key"] == "test-key"
    assert captured["default_headers"] == {
        "User-Agent": "Mozilla/5.0 PowerShell/7.4"
    }
    assert captured["http_client"].trust_env is False


def test_aiapis_client_omits_default_headers_when_user_agent_empty(monkeypatch):
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.OpenAI",
        fake_openai,
    )

    AIAPISGptImage2Provider({"api_key": "test-key", "user_agent": ""})._client()

    assert "default_headers" not in captured


def test_v057_aiapis_client_honors_provider_proxy_mode(monkeypatch):
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.OpenAI",
        fake_openai,
    )
    provider = AIAPISGptImage2Provider(
        {
            "api_key": "test-key",
            "base_url": "https://img.aiapis.help/v1",
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:7890",
            "allow_untrusted_proxy_certificate": False,
        }
    )

    provider._client()

    assert captured["http_client"].trust_env is False


def test_v057_aiapis_none_proxy_mode_does_not_read_system_proxy(monkeypatch):
    def fail_getproxies():
        raise AssertionError("system proxy should not be read")

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.getproxies",
        fail_getproxies,
    )

    provider = AIAPISGptImage2Provider(
        {
            "api_key": "test-key",
            "base_url": "https://img.aiapis.help/v1",
            "proxy_mode": "none",
        }
    )

    assert provider._proxy_url() == ""


def test_download_url_uses_request_with_user_agent(tmp_path, monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size=-1):
            if captured.get("read"):
                return b""
            captured["read"] = True
            return b"image"

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.urlopen",
        fake_urlopen,
    )

    target = tmp_path / "download.png"
    from backend.image_providers.aiapis_gpt_image_2 import download_url

    download_url(
        "https://img.aiapis.help/v1/files/one.png",
        target,
        timeout=60,
        user_agent="Mozilla/5.0 PowerShell/7.4",
    )

    assert isinstance(captured["request"], Request)
    assert captured["request"].headers["User-agent"] == "Mozilla/5.0 PowerShell/7.4"
    assert captured["timeout"] == 60
    assert target.read_bytes() == b"image"


def test_aiapis_save_result_passes_user_agent_to_download(tmp_path, monkeypatch):
    provider = AIAPISGptImage2Provider(
        {
            "base_url": "https://img.aiapis.help/v1",
            "api_key": "test-key",
            "user_agent": "Mozilla/5.0 PowerShell/7.4",
        }
    )
    output_path = tmp_path / "result.png"
    downloaded = {}

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: output_path)

    def fake_download(url, target, user_agent=""):
        downloaded["url"] = url
        downloaded["user_agent"] = user_agent
        Path(target).write_bytes(b"image")

    monkeypatch.setattr(
        "backend.image_providers.aiapis_gpt_image_2.download_url",
        fake_download,
    )

    provider._save_result(
        SimpleNamespace(data=[SimpleNamespace(url="files/x.png")]),
        str(tmp_path),
    )

    assert downloaded["url"] == "https://img.aiapis.help/v1/files/x.png"
    assert downloaded["user_agent"] == "Mozilla/5.0 PowerShell/7.4"


def test_v042_aiapis_save_result_decodes_base64_outputs(tmp_path, monkeypatch):
    provider = AIAPISGptImage2Provider({"output_format": "png"})
    output_paths = [tmp_path / "one.png", tmp_path / "two.png"]
    output_iter = iter(output_paths)

    monkeypatch.setattr(provider, "_output_path", lambda output_dir: next(output_iter))

    result = provider._save_result(
        SimpleNamespace(
            data=[
                SimpleNamespace(b64_json=base64.b64encode(b"one").decode("ascii"), url=None),
                SimpleNamespace(b64_json=base64.b64encode(b"two").decode("ascii"), url=None),
            ]
        ),
        str(tmp_path),
    )

    assert result.output_paths == [str(path) for path in output_paths]
    assert [path.read_bytes() for path in output_paths] == [b"one", b"two"]


def test_v042_aiapis_request_options_omits_blank_user_and_png_compression():
    provider = AIAPISGptImage2Provider(
        {
            "output_format": "png",
            "output_compression": 88,
            "user": "  ",
        }
    )

    request_options = provider._request_options("产品海报", {"resolved_size": "1024x1024", "n": 1})

    assert "output_compression" not in request_options
    assert "user" not in request_options


def test_v042_aiapis_image_to_image_passes_all_images_in_order(tmp_path, monkeypatch):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    captured = {}

    class FakeImages:
        def edit(self, **kwargs):
            captured["kwargs"] = kwargs
            captured["image_names"] = [item.name for item in kwargs["image"]]
            captured["image_closed_during_call"] = [item.closed for item in kwargs["image"]]
            return SimpleNamespace(
                data=[SimpleNamespace(b64_json=base64.b64encode(b"edited").decode("ascii"), url=None)]
            )

    class FakeClient:
        images = FakeImages()

    provider = AIAPISGptImage2Provider(
        {
            "output_format": "png",
            "quality": "high",
            "background": "auto",
        }
    )
    monkeypatch.setattr(provider, "_client", lambda: FakeClient())
    monkeypatch.setattr(provider, "_output_path", lambda output_dir: tmp_path / "edited.png")

    result = provider.image_to_image(
        "按图1和图2生成",
        [str(first), str(second)],
        str(tmp_path),
        {"resolved_size": "1024x1024", "n": 1},
    )

    assert captured["image_names"] == [str(first), str(second)]
    assert captured["image_closed_during_call"] == [False, False]
    assert captured["kwargs"]["prompt"] == "按图1和图2生成"
    assert captured["kwargs"]["size"] == "1024x1024"
    assert "moderation" not in captured["kwargs"]
    assert result.output_path == str(tmp_path / "edited.png")
    assert (tmp_path / "edited.png").read_bytes() == b"edited"




