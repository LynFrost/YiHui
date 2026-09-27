from __future__ import annotations

import base64
from contextlib import ExitStack
import os
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.parse import urljoin
from urllib.request import getproxies
from urllib.request import Request, urlopen

import httpx
from openai import OpenAI

from backend.image_providers.base import ImageGenerationResult, ImageProvider


DEFAULT_BASE_URL = "https://img.aiapis.help/v1"
IMAGE_BACKGROUNDS = {"auto", "opaque"}
RESPONSE_BACKGROUNDS = {"transparent", "opaque", "auto"}
OUTPUT_FORMATS = {"png", "jpeg", "webp"}


def resolve_output_url(base_url: str, output_url: str) -> str:
    if output_url.startswith("/"):
        return urljoin(base_url, output_url)
    return urljoin(f"{base_url.rstrip('/')}/", output_url)


def download_url(
    url: str,
    target: str | Path,
    timeout: int = 30,
    user_agent: str = "",
) -> None:
    request = Request(url, headers={"User-Agent": user_agent}) if user_agent else url
    with urlopen(request, timeout=timeout) as response:
        with Path(target).open("wb") as target_file:
            shutil.copyfileobj(response, target_file)


class AIAPISGptImage2Provider(ImageProvider):
    name = "aiapis_gpt_image_2"

    @property
    def base_url(self) -> str:
        return self.config.get("base_url") or DEFAULT_BASE_URL

    @property
    def call_method(self) -> str:
        method = str(self.config.get("openai_call_method") or "gpt-image-2").strip()
        return method if method in {"gpt-image-2", "response"} else "gpt-image-2"

    @property
    def user_agent(self) -> str:
        return str(self.config.get("user_agent") or "").strip()

    @property
    def proxy_mode(self) -> str:
        mode = str(self.config.get("proxy_mode") or "system").strip()
        return mode if mode in {"system", "custom", "none"} else "system"

    def _system_proxy(self) -> str:
        hostname = (urlparse(self.base_url).hostname or "").lower()
        if hostname == "localhost" or hostname == "::1" or hostname.startswith("127."):
            return ""
        proxies = getproxies()
        return proxies.get("https") or proxies.get("http") or ""

    def _proxy_url(self) -> str:
        if self.proxy_mode == "none":
            return ""
        if self.proxy_mode == "custom":
            return str(self.config.get("proxy_url") or "").strip()
        return self._system_proxy()

    def _allow_untrusted_proxy_certificate(self) -> bool:
        value = self.config.get("allow_untrusted_proxy_certificate")
        if value is None:
            return True
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _http_client(self) -> httpx.Client:
        proxy = self._proxy_url()
        verify = True
        if proxy and self._allow_untrusted_proxy_certificate():
            verify = False
        options: dict[str, Any] = {"trust_env": False, "verify": verify}
        if proxy:
            options["proxies"] = proxy
        return httpx.Client(**options, timeout=300)

    def _client(self) -> OpenAI:
        api_key = self.config.get("api_key") or os.getenv(
            str(self.config.get("api_key_env", ""))
        )
        if not api_key:
            raise ValueError("缺少 AIAPIS API Key")

        client_options: dict[str, Any] = {
            "base_url": self.base_url,
            "api_key": api_key,
            "max_retries": 0,
        }
        if self.user_agent:
            client_options["default_headers"] = {"User-Agent": self.user_agent}
        client_options["http_client"] = self._http_client()

        return OpenAI(**client_options)

    def _output_format(self) -> str:
        output_format = str(self.config.get("output_format") or "png").strip()
        return output_format if output_format in OUTPUT_FORMATS else "png"

    def _background(self, choices: set[str]) -> str:
        background = str(self.config.get("background") or "auto").strip()
        return background if background in choices else "auto"

    def _request_options(self, prompt: str, options: dict[str, Any]) -> dict[str, Any]:
        output_format = self._output_format()
        request_options = {
            "model": "gpt-image-2",
            "prompt": prompt,
            "n": options.get("n") or options.get("count") or 1,
            "size": options.get("resolved_size")
            or options.get("size")
            or "1024x1024",
            "quality": self.config.get("quality") or "high",
            "output_format": output_format,
            "background": self._background(IMAGE_BACKGROUNDS),
            "moderation": self.config.get("moderation") or "low",
        }
        if output_format in {"jpeg", "webp"}:
            request_options["output_compression"] = self.config.get(
                "output_compression",
                80,
            )
        user = str(self.config.get("user") or "").strip()
        if user:
            request_options["user"] = user
        return request_options

    def _edit_request_options(self, prompt: str, options: dict[str, Any]) -> dict[str, Any]:
        request_options = self._request_options(prompt, options)
        request_options.pop("moderation", None)
        return request_options

    def _responses_request_options(
        self, prompt: str, options: dict[str, Any]
    ) -> dict[str, Any]:
        output_format = self._output_format()
        tool_options: dict[str, Any] = {
            "type": "image_generation",
            "action": "generate",
            "model": "gpt-image-1.5",
            "size": options.get("resolved_size")
            or options.get("size")
            or "1024x1024",
            "quality": self.config.get("quality") or "high",
            "output_format": output_format,
            "background": self._background(RESPONSE_BACKGROUNDS),
            "moderation": self.config.get("moderation") or "low",
            "partial_images": 0,
        }
        if output_format in {"jpeg", "webp"}:
            tool_options["output_compression"] = self.config.get(
                "output_compression",
                80,
            )
        return {
            "model": "gpt-5.5",
            "input": prompt,
            "stream": False,
            "tool_choice": {"type": "image_generation"},
            "tools": [tool_options],
        }

    def _output_path(self, output_dir: str) -> Path:
        output_format = str(self.config.get("output_format") or "png").strip()
        suffix = {
            "png": ".png",
            "jpeg": ".jpeg",
            "webp": ".webp",
        }.get(output_format, ".png")
        return Path(output_dir) / f"{uuid.uuid4().hex}{suffix}"

    def _save_result(self, response: Any, output_dir: str) -> ImageGenerationResult:
        data = getattr(response, "data", None) or []
        if not data:
            raise ValueError("图片生成响应为空")

        output_paths: list[str] = []
        for item in data:
            output_path = self._output_path(output_dir)
            b64_json = getattr(item, "b64_json", None)
            if b64_json:
                output_path.write_bytes(base64.b64decode(b64_json))
                output_paths.append(str(output_path))
                continue

            output_url = getattr(item, "url", None)
            if output_url:
                url = resolve_output_url(self.base_url, output_url)
                temp_path = output_path.with_name(
                    f"{output_path.name}.{uuid.uuid4().hex}.tmp"
                )
                try:
                    if self.user_agent:
                        download_url(url, temp_path, user_agent=self.user_agent)
                    else:
                        download_url(url, temp_path)
                    temp_path.replace(output_path)
                except Exception:
                    temp_path.unlink(missing_ok=True)
                    raise
                output_paths.append(str(output_path))
                continue

            raise ValueError("图片生成响应缺少图片数据")

        return ImageGenerationResult(
            output_paths=output_paths,
            provider=self.name,
        )

    def _save_responses_result(
        self, response: Any, output_dir: str
    ) -> ImageGenerationResult:
        outputs = getattr(response, "output", None) or []
        output_paths: list[str] = []

        for item in outputs:
            if getattr(item, "type", None) != "image_generation_call":
                continue
            image_base64 = getattr(item, "result", None)
            if not image_base64:
                continue
            output_path = self._output_path(output_dir)
            output_path.write_bytes(base64.b64decode(image_base64))
            output_paths.append(str(output_path))

        if not output_paths:
            raise ValueError("图片生成响应为空")

        return ImageGenerationResult(
            output_paths=output_paths,
            provider=self.name,
        )

    def text_to_image(
        self, prompt: str, output_dir: str, options: dict[str, Any]
    ) -> ImageGenerationResult:
        if self.call_method == "response":
            response = self._client().responses.create(
                **self._responses_request_options(prompt, options)
            )
            return self._save_responses_result(response, output_dir)

        response = self._client().images.generate(
            **self._request_options(prompt, options)
        )
        return self._save_result(response, output_dir)

    def image_to_image(
        self,
        prompt: str,
        input_images: list[str],
        output_dir: str,
        options: dict[str, Any],
    ) -> ImageGenerationResult:
        if self.call_method == "response":
            raise ValueError("Responses API 图生图暂未实现。")

        with ExitStack() as stack:
            image_files = [
                stack.enter_context(Path(image_path).open("rb"))
                for image_path in input_images
            ]
            response = self._client().images.edit(
                image=image_files,
                **self._edit_request_options(prompt, options),
            )
        return self._save_result(response, output_dir)
