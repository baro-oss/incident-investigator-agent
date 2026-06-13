"""Tạo LLMClient đúng loại dựa trên biến môi trường LLM_PROVIDER."""
from __future__ import annotations

import os
from typing import Optional

from .anthropic import AnthropicClient
from .base import LLMClient
from .openai_compat import OpenAICompatibleClient


def create_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMClient:
    """
    Trả LLMClient phù hợp.

    Provider hợp lệ:
      - "anthropic"  → AnthropicClient
      - "openai" / "groq" / "mistral" / "together" / "ollama" / bất kỳ
        → OpenAICompatibleClient (đổi base_url qua OPENAI_BASE_URL)
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "anthropic")
    model = model or os.environ.get("LLM_MODEL")

    if provider == "anthropic":
        return AnthropicClient(model=model)
    else:
        return OpenAICompatibleClient(model=model)
