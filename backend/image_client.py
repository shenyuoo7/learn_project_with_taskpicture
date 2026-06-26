import base64
import asyncio
import re
from pathlib import Path
from typing import Any, Optional

import httpx

from .config import IMAGE_API_BASE_URL, IMAGE_API_KEY, IMAGE_API_TIMEOUT, IMAGE_MODEL, IMAGE_SIZE


MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)]+)\)")
DOWNLOAD_RETRY_DELAYS = [2, 4, 6]


class ImageGenerationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        raw_response: str = "",
        save_path: Optional[Path] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.raw_response = raw_response
        self.save_path = save_path


class ImageClient:
    def __init__(self) -> None:
        self.base_url = IMAGE_API_BASE_URL
        self.api_key = IMAGE_API_KEY
        self.model = IMAGE_MODEL
        self.timeout = IMAGE_API_TIMEOUT
        self.size = IMAGE_SIZE

    def _validate(self) -> None:
        if not self.base_url:
            raise RuntimeError("缺少 IMAGE_API_BASE_URL，请检查 .env。")
        if not self.api_key:
            raise RuntimeError("缺少 IMAGE_API_KEY，请检查 .env。")

    def _extract_image_data(self, data: dict[str, Any]) -> Optional[str]:
        if isinstance(data.get("data"), list) and data["data"]:
            item = data["data"][0]
            if isinstance(item, dict):
                image_data = (
                    item.get("b64_json")
                    or item.get("base64")
                    or item.get("image_base64")
                    or item.get("url")
                )
                if image_data:
                    return image_data

        if isinstance(data.get("choices"), list) and data["choices"]:
            choice = data["choices"][0]
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    image_data = (
                        part.get("b64_json")
                        or part.get("base64")
                        or part.get("image_base64")
                        or part.get("url")
                    )
                    if not image_data and isinstance(part.get("image_url"), dict):
                        image_data = part["image_url"].get("url")
                    if image_data:
                        return image_data
        return None

    async def _download_url(self, image_url: str, output_path: Path) -> None:
        last_exc: Optional[Exception] = None
        for attempt_index in range(1 + len(DOWNLOAD_RETRY_DELAYS)):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, trust_env=False) as client:
                    response = await client.get(image_url)
                if response.status_code >= 400:
                    raise ImageGenerationError(
                        f"图片 URL 下载失败：HTTP {response.status_code}",
                        status_code=response.status_code,
                        raw_response=response.text[:1000] or f"image_url={image_url}",
                        save_path=output_path,
                    )
                output_path.write_bytes(response.content)
                return
            except ImageGenerationError as exc:
                last_exc = exc
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, httpx.HTTPError) as exc:
                last_exc = ImageGenerationError(
                    f"图片 URL 下载异常：{exc}",
                    status_code=None,
                    raw_response=f"image_url={image_url}",
                    save_path=output_path,
                )
            if attempt_index < len(DOWNLOAD_RETRY_DELAYS):
                await asyncio.sleep(DOWNLOAD_RETRY_DELAYS[attempt_index])

        if isinstance(last_exc, ImageGenerationError):
            raise last_exc
        raise ImageGenerationError(
            "图片 URL 下载失败：未知错误",
            status_code=None,
            raw_response=f"image_url={image_url}",
            save_path=output_path,
        )

    async def save_image_from_response(self, data: dict[str, Any], output_path: Path) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image_data = self._extract_image_data(data)
        if not image_data:
            raise ValueError("Image response format not recognized.")

        if isinstance(image_data, str):
            markdown_match = MARKDOWN_IMAGE_RE.search(image_data.strip())
            if markdown_match:
                image_url = markdown_match.group(1).strip()
                await self._download_url(image_url, output_path)
                return image_url

            if image_data.startswith("http://") or image_data.startswith("https://"):
                await self._download_url(image_data, output_path)
                return image_data

            if image_data.startswith("data:image"):
                image_data = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(image_data)
        output_path.write_bytes(image_bytes)
        return "base64"

    async def generate_image(self, prompt: str, output_path: Path) -> str:
        self._validate()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self.base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        }
                    ],
                }
            ],
            "size": self.size,
            "local_batch_count": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(url, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, httpx.HTTPError) as exc:
            raise ImageGenerationError(
                f"图片 API 请求异常：{exc}",
                status_code=None,
                raw_response="",
                save_path=output_path,
            ) from exc
        else:
            raw_response = response.text
            if response.status_code >= 400:
                raise ImageGenerationError(
                    f"图片 API 请求失败：HTTP {response.status_code}",
                    status_code=response.status_code,
                    raw_response=raw_response[:1000],
                    save_path=output_path,
                )
            try:
                data = response.json()
            except Exception as exc:
                raise ImageGenerationError(
                    f"图片 API 响应不是合法 JSON：{exc}",
                    status_code=response.status_code,
                    raw_response=raw_response[:1000],
                    save_path=output_path,
                ) from exc

        try:
            return await self.save_image_from_response(data, output_path)
        except ImageGenerationError:
            raise
        except Exception as exc:
            raise ImageGenerationError(
                f"图片响应解析或保存失败：{exc}",
                status_code=response.status_code,
                raw_response=raw_response[:1000],
                save_path=output_path,
            ) from exc
