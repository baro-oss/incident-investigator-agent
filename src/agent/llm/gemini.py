"""Google Gemini adapter — implement LLMClient Protocol."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .base import LLMClient, LLMResponse, Message, ToolCall, ToolSpec


class GeminiClient:
    """Implement LLMClient cho Google Gemini API (google-genai SDK).

    Yêu cầu: pip install google-genai
    Env: GEMINI_API_KEY
    Model mặc định: gemini-2.0-flash
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise ImportError(
                "Cần cài google-genai: pip install google-genai"
            ) from exc

        self._genai = genai
        self._types = genai_types
        self._client = genai.Client(
            api_key=api_key or os.environ.get("GEMINI_API_KEY", "")
        )
        self._model = model or os.environ.get("LLM_MODEL", "gemini-2.0-flash")
        self._extra = extra_config or {}

    async def complete(
        self,
        messages: List[Message],
        tools: List[ToolSpec],
        *,
        system: Optional[str] = None,
    ) -> LLMResponse:
        types = self._types

        # Chuyển messages sang Gemini Content format
        contents = []
        for m in messages:
            role = "user" if m.role == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=m.content)],
                )
            )

        # Chuyển tool specs sang Gemini function declarations
        gemini_tools = None
        if tools:
            fn_decls = [
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters=t.input_schema,
                )
                for t in tools
            ]
            gemini_tools = [types.Tool(function_declarations=fn_decls)]

        config_kwargs: Dict[str, Any] = {}
        if system:
            config_kwargs["system_instruction"] = system
        if self._extra.get("temperature") is not None:
            config_kwargs["temperature"] = self._extra["temperature"]
        if self._extra.get("max_output_tokens") is not None:
            config_kwargs["max_output_tokens"] = self._extra["max_output_tokens"]

        gen_config = types.GenerateContentConfig(
            tools=gemini_tools,
            **config_kwargs,
        ) if (gemini_tools or config_kwargs) else None

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=gen_config,
        )

        tool_calls: List[ToolCall] = []
        text_parts: List[str] = []

        candidate = response.candidates[0] if response.candidates else None
        if candidate:
            for part in (candidate.content.parts or []):
                if part.function_call:
                    fc = part.function_call
                    tool_calls.append(
                        ToolCall(
                            id=fc.name,
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                        )
                    )
                elif part.text:
                    text_parts.append(part.text)

        # Usage tracking (Gemini trả usage_metadata)
        usage: Optional[Dict[str, int]] = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "input_tokens": getattr(um, "prompt_token_count", 0) or 0,
                "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
            }

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            usage=usage,
        )
