from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.image_providers.base import ImageGenerationResult, ImageProvider
from backend.image_providers.aiapis_gpt_image_2 import AIAPISGptImage2Provider


PROVIDER_CAPABILITIES: dict[str, dict[str, Any]] = {
    "openai": {
        "implemented": True,
        "call_methods": {"gpt-image-2", "response"},
    },
    "aiapis_gpt_image_2": {
        "implemented": True,
        "call_methods": {"gpt-image-2", "response"},
    },
    "openai-google": {
        "implemented": True,
        "call_methods": {"gpt-image-2"},
    },
    "sysrv-google": {
        "implemented": True,
        "call_methods": {"gpt-image-2"},
    },
    "apimart-openai": {
        "implemented": True,
        "call_methods": {"gpt-image-2"},
    },
    "google": {
        "implemented": False,
        "message": "Google adapter 暂未实现。",
    },
    "other": {
        "implemented": False,
        "message": "Other adapter 暂未实现。",
    },
}


def adapter_capability(adapter: str) -> dict[str, Any] | None:
    return PROVIDER_CAPABILITIES.get(str(adapter or "").strip())


def validate_adapter_supported(adapter: str) -> None:
    clean_adapter = str(adapter or "").strip()
    capability = adapter_capability(clean_adapter)
    if capability is None:
        raise ValueError(f"未知图片生成适配器：{clean_adapter}")
    if not capability.get("implemented"):
        raise ValueError(str(capability.get("message") or f"{clean_adapter} adapter 暂未实现。"))


class NotImplementedImageProvider(ImageProvider):
    def __init__(self, config: dict[str, Any], adapter: str, message: str):
        super().__init__(config)
        self.name = adapter
        self.message = message

    def text_to_image(
        self, prompt: str, output_dir: str, options: dict[str, Any]
    ) -> ImageGenerationResult:
        raise ValueError(self.message)

    def image_to_image(
        self,
        prompt: str,
        input_images: list[str],
        output_dir: str,
        options: dict[str, Any],
    ) -> ImageGenerationResult:
        raise ValueError(self.message)


class GooglePlaceholderProvider(NotImplementedImageProvider):
    def __init__(self, config: dict[str, Any]):
        super().__init__(
            config,
            "google",
            str(PROVIDER_CAPABILITIES["google"]["message"]),
        )


class OpenAIGoogleScriptProvider(NotImplementedImageProvider):
    def __init__(self, config: dict[str, Any]):
        super().__init__(
            config,
            "openai-google",
            "openai-google adapter 需要通过共享脚本或自定义脚本生成。",
        )


class SysrvGoogleScriptProvider(NotImplementedImageProvider):
    def __init__(self, config: dict[str, Any]):
        super().__init__(
            config,
            "sysrv-google",
            "sysrv-google adapter 需要通过共享脚本或自定义脚本生成。",
        )


class ApimartOpenAIScriptProvider(NotImplementedImageProvider):
    def __init__(self, config: dict[str, Any]):
        super().__init__(
            config,
            "apimart-openai",
            "apimart-openai adapter 需要通过共享脚本或自定义脚本生成。",
        )


class OtherPlaceholderProvider(NotImplementedImageProvider):
    def __init__(self, config: dict[str, Any]):
        super().__init__(
            config,
            "other",
            str(PROVIDER_CAPABILITIES["other"]["message"]),
        )


PROVIDERS: dict[str, type[ImageProvider]] = {
    "openai": AIAPISGptImage2Provider,
    "aiapis_gpt_image_2": AIAPISGptImage2Provider,
    "openai-google": OpenAIGoogleScriptProvider,
    "sysrv-google": SysrvGoogleScriptProvider,
    "apimart-openai": ApimartOpenAIScriptProvider,
    "google": GooglePlaceholderProvider,
    "other": OtherPlaceholderProvider,
}


def provider_from_config(
    app_config: dict[str, Any],
    provider_name: str | None = None,
    provider_config: dict[str, Any] | None = None,
) -> ImageProvider:
    provider_name = provider_name or app_config.get("active_provider")
    if not provider_name:
        raise ValueError("未选择图片生成 Provider")

    provider_config = provider_config if provider_config is not None else app_config.get("providers", {}).get(provider_name)
    if provider_config is None:
        raise ValueError(f"未知图片生成提供方：{provider_name}")
    if not isinstance(provider_config, dict):
        provider_config = {}

    adapter = provider_config.get("adapter") or provider_name
    provider_class = PROVIDERS.get(adapter)
    if provider_class is None:
        raise ValueError(f"未知图片生成适配器：{adapter}")

    return provider_class(provider_config)


def generate_image(
    provider: ImageProvider,
    mode: str,
    prompt: str,
    input_images: list[str],
    output_dir: str,
    options: dict[str, Any],
) -> ImageGenerationResult:
    clean_prompt = prompt.strip()
    if not clean_prompt:
        raise ValueError("提示词不能为空")

    if mode not in {"text_to_image", "image_to_image"}:
        raise ValueError("未知生成模式")
    if mode == "image_to_image":
        if not input_images:
            raise ValueError("图生图需要至少 1 张输入图")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    copied_options = deepcopy(options)

    if mode == "text_to_image":
        return provider.text_to_image(clean_prompt, output_dir, copied_options)

    return provider.image_to_image(
        clean_prompt,
        list(input_images),
        output_dir,
        copied_options,
    )
