"""LLM Client — unified interface to DeepSeek API.

Supports both chat (V3.1) and reasoning (R1) models.
All models go through a single interface with model name selection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class LLMResponse:
    """Standard response from the LLM."""

    content: str
    model: str
    tokens_in: int
    tokens_out: int
    finish_reason: str = "stop"
    reasoning_content: str = ""  # R1 reasoning trace


class LLMClient:
    """Async LLM client for DeepSeek API.

    Usage:
        client = LLMClient(api_key="sk-...")
        resp = await client.chat("Hello", system="You are a helpful assistant")
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com/v1",
        default_model: str = "deepseek-chat",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def chat(
        self,
        prompt: str,
        system: str = "",
        model: str = "",
        temperature: float = 0.1,
        max_tokens: int = 8192,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            prompt: The user message
            system: System prompt
            model: Model name (defaults to self.default_model)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Max tokens to generate
            response_format: e.g. {"type": "json_object"}

        Returns:
            LLMResponse with content and usage stats
        """
        client = await self._get_client()
        model = model or self.default_model

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format:
            body["response_format"] = response_format

        try:
            response = await client.post("/chat/completions", json=body)
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            message = choice["message"]
            usage = data.get("usage", {})

            return LLMResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                finish_reason=choice.get("finish_reason", "stop"),
                reasoning_content=message.get("reasoning_content", ""),
            )
        except httpx.HTTPStatusError as e:
            error_body = ""
            try:
                error_body = await e.response.aread()
                error_body = error_body.decode()
            except Exception:
                pass
            raise RuntimeError(
                f"LLM API error {e.response.status_code}: {error_body}"
            ) from e

    async def chat_json(
        self,
        prompt: str,
        system: str = "",
        model: str = "",
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Send a chat request and parse JSON response."""
        resp = await self.chat(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(resp.content)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"LLM returned invalid JSON: {resp.content[:200]}"
            ) from e

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
