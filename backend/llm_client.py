import httpx

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL
        self.model = DEEPSEEK_MODEL

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.35,
        timeout_seconds: int = 240,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("未检测到 DEEPSEEK_API_KEY。请复制 .env.example 为 .env，并填入 DeepSeek API Key。")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "stream": False,
        }

        try:
            timeout = httpx.Timeout(timeout_seconds, connect=30)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:800] if exc.response is not None else str(exc)
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            raise RuntimeError(f"DeepSeek API HTTP 错误：{status_code}，{detail}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"DeepSeek API 请求超时：{timeout_seconds} 秒") from exc
        except httpx.TransportError as exc:
            raise RuntimeError(f"DeepSeek API 连接异常：{exc}") from exc

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("DeepSeek API 未返回有效 choices。")
        return choices[0]["message"]["content"].strip()
