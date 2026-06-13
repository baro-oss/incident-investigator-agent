"""Anthropic Claude adapter."""
from __future__ import annotations

import json
import os
from typing import List, Optional

import anthropic

from .base import LLMClient, LLMResponse, Message, ToolCall, ToolSpec


class AnthropicClient:
    """Implement LLMClient cho Anthropic API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        self._model = model or os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
        self._max_tokens = max_tokens

    async def complete(
        self,
        messages: List[Message],
        tools: List[ToolSpec],
        *,
        system: Optional[str] = None,
    ) -> LLMResponse:
        anthropic_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"  # system đi qua param riêng
        ]

        kwargs = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": anthropic_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [self._to_anthropic_tool(t) for t in tools]

        response = await self._client.messages.create(**kwargs)

        tool_calls = []
        text_parts = []

        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )
            elif block.type == "text":
                text_parts.append(block.text)

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _to_anthropic_tool(tool: ToolSpec) -> dict:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
