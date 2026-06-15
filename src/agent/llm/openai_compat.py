"""OpenAI-compatible adapter: OpenAI, Groq, Together AI, Mistral, Ollama, vLLM...

Chỉ cần đổi OPENAI_BASE_URL + OPENAI_API_KEY là xài được provider khác.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

import openai

from .base import LLMClient, LLMResponse, Message, ToolCall, ToolSpec


class OpenAICompatibleClient:
    """Implement LLMClient cho mọi provider dùng chuẩn OpenAI Chat Completions."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        default_headers: Optional[dict] = None,
    ) -> None:
        kwargs: dict = {
            "api_key": api_key or os.environ.get("OPENAI_API_KEY", ""),
            "base_url": base_url or os.environ.get("OPENAI_BASE_URL") or None,
        }
        if default_headers:
            kwargs["default_headers"] = default_headers
        self._client = openai.AsyncOpenAI(**kwargs)
        self._model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self._max_tokens = max_tokens

    async def complete(
        self,
        messages: List[Message],
        tools: List[ToolSpec],
        *,
        system: Optional[str] = None,
    ) -> LLMResponse:
        openai_messages = []

        if system:
            openai_messages.append({"role": "system", "content": system})

        # Thêm system message từ messages nếu có (OpenAI nhận system ở bất kỳ vị trí)
        for m in messages:
            openai_messages.append({"role": m.role, "content": m.content})

        kwargs = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": openai_messages,
        }
        if tools:
            kwargs["tools"] = [self._to_openai_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        return LLMResponse(
            text=message.content,
            tool_calls=tool_calls,
            usage=usage,
        )

    @staticmethod
    def _to_openai_tool(tool: ToolSpec) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
