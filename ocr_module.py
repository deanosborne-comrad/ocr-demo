import base64
import contextlib
import io
import logging
import os
import threading
import time
from typing import List, Sequence, Tuple

import httpx
import numpy as np
from PIL import Image, ImageOps
from olmocr.prompts import PageResponse, build_no_anchoring_v4_yaml_prompt
from olmocr.train.dataloader import FrontMatterParser

logger = logging.getLogger(__name__)
ocr_lock = threading.Lock()


class TemporaryOcrError(Exception):
    """Raised when the upstream olmOCR endpoint indicates a transient failure."""


class OCRProcessor:
    """Thin client around the olmOCR OpenAI-compatible API."""

    def __init__(
        self,
        server_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        max_tokens: int = 8000,
        max_retries: int = 4,
        request_timeout: float = 90.0,
        temperature_schedule: Sequence[float] | None = None,
        target_longest_image_dim: int = 1400,
    ) -> None:
        self.server_url = (server_url or os.getenv("OLMOCR_SERVER_URL", "http://localhost:30024/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("OLMOCR_API_KEY")
        self.model_name = model_name or os.getenv("OLMOCR_MODEL", "allenai/olmOCR-2-7B-1025-FP8")
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.temperature_schedule = tuple(temperature_schedule or (0.1, 0.2, 0.3, 0.5, 0.8))
        self.target_longest_image_dim = max(256, int(target_longest_image_dim))
        self._prompt = build_no_anchoring_v4_yaml_prompt()
        self._parser = FrontMatterParser(front_matter_class=PageResponse)
        timeout = httpx.Timeout(timeout=request_timeout)
        self._client = httpx.Client(timeout=timeout)
        logger.info(
            "Initialized olmOCR client -> server=%s model=%s retries=%s",
            self.server_url,
            self.model_name,
            self.max_retries,
        )

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        client = getattr(self, "_client", None)
        if client:
            with contextlib.suppress(Exception):
                client.close()

    def process_image(self, image_np: np.ndarray) -> List[Tuple[str, float]]:
        """Process an RGB/greyscale numpy array and return text fragments with dummy confidence."""
        if image_np is None or image_np.size == 0:
            return []

        pil_image = self._prepare_pil_image(image_np)
        natural_text = self._run_with_retries(pil_image)
        if not natural_text:
            return []

        lines = [line.strip() for line in natural_text.splitlines() if line.strip()]
        return [(line, 1.0) for line in lines] or [(natural_text.strip(), 1.0)]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _prepare_pil_image(self, image_np: np.ndarray) -> Image.Image:
        clipped = np.clip(image_np, 0, 255).astype(np.uint8)

        if clipped.ndim == 2:
            clipped = np.stack([clipped] * 3, axis=-1)
        elif clipped.shape[2] == 4:
            clipped = clipped[:, :, :3]

        image = Image.fromarray(clipped, mode="RGB")
        image = ImageOps.exif_transpose(image)
        longest_dim = max(image.width, image.height)
        if longest_dim > self.target_longest_image_dim:
            scale = self.target_longest_image_dim / float(longest_dim)
            new_size = (max(1, int(round(image.width * scale))), max(1, int(round(image.height * scale))))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        return image

    def _run_with_retries(self, base_image: Image.Image) -> str:
        rotation = 0
        attempt = 0

        while attempt < self.max_retries:
            rotated = self._apply_rotation(base_image, rotation)
            payload = self._build_payload(rotated, attempt)
            try:
                response = self._dispatch(payload)
                page_response = self._parse_page_response(response)
            except TemporaryOcrError as exc:
                backoff = min(30, 2 ** attempt)
                logger.warning("Temporary olmOCR error (%s). Retrying in %ss.", exc, backoff)
                time.sleep(backoff)
                attempt += 1
                continue
            except Exception as exc:
                logger.error("olmOCR request failed permanently: %s", exc)
                break

            if not page_response.is_rotation_valid and attempt < self.max_retries - 1:
                rotation = (rotation + page_response.rotation_correction) % 360
                logger.info("olmOCR suggested rotation correction -> %s degrees", page_response.rotation_correction)
                attempt += 1
                continue

            return page_response.natural_text or ""

        logger.error("olmOCR failed after %s attempts", self.max_retries)
        return ""

    def _apply_rotation(self, image: Image.Image, rotation: int) -> Image.Image:
        if rotation not in {0, 90, 180, 270}:
            return image
        if rotation == 0:
            return image

        transpose_map = {
            90: Image.Transpose.ROTATE_90,
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_270,
        }
        return image.transpose(transpose_map[rotation])

    def _build_payload(self, image: Image.Image, attempt: int) -> dict:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        temperature = self.temperature_schedule[min(attempt, len(self.temperature_schedule) - 1)]
        return {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}},
                    ],
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "priority": self.max_retries - attempt,
        }

    def _dispatch(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.server_url}/chat/completions"
        with ocr_lock:
            response = self._client.post(url, headers=headers, json=payload)

        if response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
            raise TemporaryOcrError(f"{response.status_code} {response.text}")

        response.raise_for_status()
        return response.json()

    def _parse_page_response(self, response_json: dict) -> PageResponse:
        if "choices" not in response_json or not response_json["choices"]:
            raise ValueError("olmOCR response missing choices")

        choice = response_json["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise TemporaryOcrError(f"finish_reason={choice.get('finish_reason')}")

        content = choice["message"]["content"]
        if isinstance(content, list):  # OpenAI vision models may return a list
            content = "".join(item.get("text", "") for item in content)

        front_matter, text = self._parser._extract_front_matter_and_text(content)

        return self._parser._parse_front_matter(front_matter, text)
