"""OpenAI-compatible chat client with graceful offline degradation."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator

from app.config import Settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise LLMError("模型返回内容不是合法 JSON")


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.llm_enabled
        self._client = None
        self.last_error: str | None = None
        self.last_usage: dict[str, int] = {}
        if self.enabled:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url or None,
                timeout=settings.llm_timeout,
                max_retries=1,
            )

    # ------------------------------------------------------------- helpers
    def _ensure(self) -> None:
        if not self.enabled or self._client is None:
            raise LLMError("LLM 未启用（缺少 API Key 或 LLM_PROVIDER=offline）")

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "model": self.settings.llm_model if self.enabled else "offline-rules",
            "base_url": self.settings.llm_base_url if self.enabled else "",
            "provider": self.settings.llm_provider,
            "last_error": self.last_error,
        }

    async def _create(self, **kwargs: Any):
        self._ensure()
        try:
            response = await self._client.chat.completions.create(**kwargs)
            usage = getattr(response, "usage", None)
            if usage:
                self.last_usage = {
                    "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                    "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                    "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
                }
            self.last_error = None
            return response
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("LLM request failed: %s", exc)
            raise LLMError(self.last_error) from exc

    # ---------------------------------------------------------- structured
    async def json_chat(self, system: str, user: str) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        base = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
        }
        try:
            response = await self._create(
                response_format={"type": "json_object"}, **base
            )
        except LLMError:
            # Some OpenAI-compatible providers don't implement json_object.
            response = await self._create(**base)
        content = response.choices[0].message.content or ""
        return extract_json(content)

    # --------------------------------------------------------- tool calling
    async def tool_plan(
        self, system: str, user: str, tools: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], str]:
        response = await self._create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0.0,
            max_tokens=self.settings.llm_max_tokens,
        )
        message = response.choices[0].message
        calls: list[dict[str, Any]] = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            calls.append({
                "id": call.id,
                "name": call.function.name,
                "args": arguments,
                "source": "llm",
            })
        return calls, (message.content or "")

    # ------------------------------------------------------------ free text
    async def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        response = await self._create(
            model=self.settings.llm_model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=0.5,
            max_tokens=self.settings.llm_max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    async def stream_text(
        self, system: str, messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        self._ensure()
        try:
            stream = await self._client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[{"role": "system", "content": system}, *messages],
                temperature=0.55,
                max_tokens=self.settings.llm_max_tokens,
                stream=True,
            )
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("LLM streaming request failed: %s", exc)
            raise LLMError(self.last_error) from exc
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise LLMError(self.last_error) from exc

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
