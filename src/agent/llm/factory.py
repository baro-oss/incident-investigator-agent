"""Tạo LLMClient đúng loại dựa trên biến môi trường LLM_PROVIDER."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .anthropic import AnthropicClient
from .base import LLMClient
from .openai_compat import OpenAICompatibleClient


def create_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    extra_config: Optional[Dict[str, Any]] = None,
) -> LLMClient:
    """
    Trả LLMClient phù hợp.

    Provider hợp lệ:
      - "anthropic"  → AnthropicClient
      - "gemini"     → GeminiClient (google-genai)
      - "openai" / "groq" / "mistral" / "together" / "ollama" / bất kỳ
        → OpenAICompatibleClient (đổi base_url qua OPENAI_BASE_URL)
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "anthropic")
    model = model or os.environ.get("LLM_MODEL")

    cfg = extra_config or {}

    if provider == "anthropic":
        return AnthropicClient(
            model=model,
            api_key=cfg.get("api_key") or None,
            base_url=cfg.get("base_url") or None,
            default_headers=cfg.get("headers") or None,
        )

    if provider == "gemini":
        from .gemini import GeminiClient
        return GeminiClient(model=model, extra_config=extra_config)

    return OpenAICompatibleClient(
        model=model,
        api_key=cfg.get("api_key") or None,
        base_url=cfg.get("base_url") or None,
        default_headers=cfg.get("headers") or None,
    )
