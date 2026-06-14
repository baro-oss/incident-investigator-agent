"""
Shared types và Protocol cho LLM interface.

Engine chỉ import từ đây — không phụ thuộc trực tiếp vào anthropic hay openai SDK.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Protocol, runtime_checkable


@dataclass
class Message:
    role: Literal["user", "assistant", "system"]
    content: str


@dataclass
class ToolSpec:
    """Hợp đồng tool phía LLM — map sang format của từng provider trong adapter."""
    name: str
    description: str
    input_schema: Dict[str, Any]  # JSON Schema object


@dataclass
class ToolCall:
    """Một lần LLM yêu cầu gọi tool."""
    id: str           # provider-specific call id (dùng khi cần multi-turn tool result)
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    """Kết quả normalize từ mọi provider.

    Chỉ một trong hai trường được điền:
    - text: LLM trả lời thẳng (điều tra xong / không cần tool)
    - tool_calls: LLM muốn gọi một hoặc nhiều tool
    """
    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Optional[Dict[str, int]] = None  # {"input_tokens": N, "output_tokens": M}

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@runtime_checkable
class LLMClient(Protocol):
    """Interface duy nhất mà engine giao tiếp với LLM."""

    async def complete(
        self,
        messages: List[Message],
        tools: List[ToolSpec],
        *,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """
        Gửi messages + tools cho LLM, trả LLMResponse đã normalize.

        Args:
            messages: Lịch sử hội thoại (không bao gồm system prompt).
            tools: Danh sách tool LLM có thể gọi. Rỗng = không có tool.
            system: System prompt (optional, tách riêng cho Anthropic convention).
        """
        ...
