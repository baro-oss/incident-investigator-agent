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
        base_url: Optional[str] = None,
        default_headers: Optional[dict] = None,
    ) -> None:
        kwargs: dict = {"api_key": api_key or os.environ["ANTHROPIC_API_KEY"]}
        if base_url:
            kwargs["base_url"] = base_url
        if default_headers:
            kwargs["default_headers"] = default_headers
        self._client = anthropic.AsyncAnthropic(**kwargs)
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

        # P1: Prompt caching — stable prefix (system + tools) cached per investigation step.
        # cache_control is silently ignored if the prefix is below the minimum cacheable size.
        if system:
            kwargs["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        if tools:
            tools_api = [self._to_anthropic_tool(t) for t in tools]
            tools_api[-1]["cache_control"] = {"type": "ephemeral"}
            kwargs["tools"] = tools_api

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

        usage: dict = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        # Cache hit/write counts (0 when caching doesn't apply or prefix too short)
        usage["cache_creation_input_tokens"] = getattr(
            response.usage, "cache_creation_input_tokens", 0
        ) or 0
        usage["cache_read_input_tokens"] = getattr(
            response.usage, "cache_read_input_tokens", 0
        ) or 0

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            usage=usage,
        )

    @staticmethod
    def _to_anthropic_tool(tool: ToolSpec) -> dict:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
