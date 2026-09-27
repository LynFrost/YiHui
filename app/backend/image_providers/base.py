from __future__ import annotations

from typing import Any


class ImageGenerationResult:
    def __init__(
        self,
        output_path: str | None = None,
        provider: str = "",
        output_paths: list[str] | None = None,
        retry_events: list[dict[str, Any]] | None = None,
    ):
        if output_paths is not None:
            self.output_paths = [str(path) for path in output_paths if path]
        elif output_path:
            self.output_paths = [str(output_path)]
        else:
            self.output_paths = []
        self.provider = provider
        self.retry_events = retry_events or []

    @property
    def output_path(self) -> str:
        return self.output_paths[-1] if self.output_paths else ""


class ImageProvider:
    name = "base"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def text_to_image(
        self, prompt: str, output_dir: str, options: dict[str, Any]
    ) -> ImageGenerationResult:
        raise NotImplementedError

    def image_to_image(
        self,
        prompt: str,
        input_images: list[str],
        output_dir: str,
        options: dict[str, Any],
    ) -> ImageGenerationResult:
        raise NotImplementedError
