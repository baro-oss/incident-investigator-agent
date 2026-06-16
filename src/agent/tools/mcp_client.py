"""
MCP Client — kết nối đến bất kỳ MCP server nào (Streamable HTTP transport).

Giao thức: JSON-RPC 2.0 over HTTP, endpoint duy nhất POST /mcp.
Tương thích với MCP spec (tools/list, tools/call, initialize).
Không cần `mcp` Python SDK — implement trực tiếp trên aiohttp.

Upgrade path Python 3.10+: swap class này → mcp.ClientSession + streamablehttp_client,
engine và registry không thay đổi.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from agent.tools.contracts import Observation, Tool

logger = logging.getLogger(__name__)

_MCP_PROTOCOL_VERSION = "2024-11-05"


class MCPClient:
    """
    Giữ một HTTP session đến MCP server suốt đời investigation.
    tool.run() đóng gói session này → engine gọi tool bình thường.

    Auth types:
      none     — không cần xác thực (default)
      bearer   — Authorization: Bearer <token>
      api_key  — <header>: <value>  (header name + value tuỳ chỉnh)
    """

    def __init__(
        self,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config or {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._req_id = 0
        self._initialized = False

    def _auth_headers(self) -> Dict[str, str]:
        """Build HTTP headers cho auth."""
        if self.auth_type == "bearer":
            token = self.auth_config.get("token", "")
            return {"Authorization": f"Bearer {token}"} if token else {}
        if self.auth_type == "api_key":
            header = self.auth_config.get("header", "X-API-Key")
            value = self.auth_config.get("value", "")
            return {header: value} if value else {}
        return {}

    async def connect(self) -> None:
        """Mở HTTP session (với auth header) và thực hiện MCP initialize handshake."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=self._auth_headers(),
        )
        result = await self._call("initialize", {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "investigation-agent", "version": "0.1.0"},
        })
        self._initialized = True
        server_info = result.get("serverInfo", {})
        logger.info("MCP kết nối OK: %s v%s", server_info.get("name", "?"), server_info.get("version", "?"))

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_tools(self) -> List[Tool]:
        """Discover tools từ MCP server, wrap thành list[Tool] theo hợp đồng nội bộ."""
        result = await self._call("tools/list", {})
        mcp_tools = result.get("tools", [])
        tools = [self._wrap_tool(t) for t in mcp_tools]
        logger.info("MCP %s: discover %d tool(s): %s",
                    self.url, len(tools), [t.name for t in tools])
        return tools

    # ── Private ──────────────────────────────────────────────────────────────────

    async def _call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Gửi JSON-RPC 2.0 request, trả `result`. Throw nếu lỗi giao thức."""
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params,
        }
        async with self._session.post(self.url, json=payload) as resp:
            resp.raise_for_status()
            body = await resp.json(content_type=None)

        if "error" in body:
            err = body["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")

        return body.get("result", {})

    async def call_tool_text(self, name: str, arguments: Dict[str, Any]) -> str:
        """Gọi tool trên MCP server, trả raw text KHÔNG qua _parse_observation.

        Dùng khi cần toàn bộ nội dung (vd: get_code_diff cần full diff text).
        """
        try:
            result = await self._call("tools/call", {"name": name, "arguments": arguments})
        except Exception as e:
            logger.warning("MCP tool '%s' lỗi: %s", name, e)
            return f"[MCP error: {e}]"
        return _extract_text(result.get("content", []))

    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Observation:
        """Gọi tool trên MCP server, parse kết quả → Observation."""
        try:
            result = await self._call("tools/call", {"name": name, "arguments": arguments})
        except Exception as e:
            logger.warning("MCP tool '%s' lỗi: %s", name, e)
            return Observation(
                summary=f"MCP tool {name} lỗi: {e}",
                aggregates={}, samples=[], total_count=0, truncated=False,
                metadata={"tool_name": name, "source": "mcp", "error": str(e)},
            )

        if result.get("isError"):
            content_text = _extract_text(result.get("content", []))
            return Observation(
                summary=f"Tool {name} báo lỗi: {content_text[:200]}",
                aggregates={}, samples=[], total_count=0, truncated=False,
                metadata={"tool_name": name, "source": "mcp", "is_error": True},
            )

        text = _extract_text(result.get("content", []))
        return _parse_observation(text, name, self.url)

    def _wrap_tool(self, mcp_tool: Dict[str, Any]) -> Tool:
        """Bọc một MCP tool thành Tool contract — engine chỉ thấy Tool."""
        name = mcp_tool["name"]

        # Closure: name được capture đúng vì hàm này chạy một lần cho mỗi tool
        async def run(params: Dict[str, Any], _name: str = name) -> Observation:
            return await self._call_tool(_name, params)

        return Tool(
            name=name,
            description=mcp_tool.get("description") or f"Tool từ MCP: {name}",
            input_schema=mcp_tool.get("inputSchema") or {},
            run=run,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_text(content: List[Dict[str, Any]]) -> str:
    """Lấy text từ MCP content list (TextContent items)."""
    parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "\n".join(parts)


_SUMMARY_CHARS = 200   # độ dài summary tối đa
_MAX_SAMPLES   = 5    # số dòng mẫu tối đa


def _distill_external_text(text: str, tool_name: str, server_url: str) -> Observation:
    """
    Distill text tự do từ external MCP → Observation có cấu trúc (Nguyên tắc #1).

    • summary: dòng đầu tiên (≤200 char) kèm prefix diễn giải
    • samples: ≤5 dòng đại diện (bỏ trống, ưu tiên dòng ngắn)
    • total_count: tổng số dòng không trống
    • truncated: True nếu text bị cắt khi lấy samples
    """
    if not text:
        return Observation(
            summary=f"Tool {tool_name} hoàn tất (không có output)",
            aggregates={},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={"tool_name": tool_name, "source": "mcp_external", "server_url": server_url},
        )

    lines = [ln.strip() for ln in text.splitlines()]
    nonempty = [ln for ln in lines if ln]

    # Summary = dòng đầu tiên có nội dung, cắt ở _SUMMARY_CHARS
    first_line = nonempty[0] if nonempty else text[:_SUMMARY_CHARS]
    summary = f"[{tool_name}] {first_line[:_SUMMARY_CHARS]}"
    if len(first_line) > _SUMMARY_CHARS:
        summary += "…"

    # Samples: ≤5 dòng đại diện từ phần còn lại (bỏ dòng đầu đã dùng làm summary)
    remaining = nonempty[1:] if len(nonempty) > 1 else []
    samples = remaining[:_MAX_SAMPLES]
    truncated = len(remaining) > _MAX_SAMPLES

    return Observation(
        summary=summary,
        aggregates={"total_lines": len(nonempty)},
        samples=samples,
        total_count=len(nonempty),
        truncated=truncated,
        metadata={"tool_name": tool_name, "source": "mcp_external", "server_url": server_url},
    )


def _parse_observation(text: str, tool_name: str, server_url: str) -> Observation:
    """
    Parse text từ MCP tool response → Observation.

    Nếu server trả JSON có cấu trúc Observation → reconstruct đầy đủ.
    Nếu server trả text tự do (external server không biết Observation) → wrap generic.
    """
    if text:
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "summary" in data and "aggregates" in data:
                return Observation(
                    summary=data["summary"],
                    aggregates=data.get("aggregates", {}),
                    samples=data.get("samples", []),
                    total_count=data.get("total_count", 0),
                    truncated=data.get("truncated", False),
                    metadata=data.get("metadata", {"tool_name": tool_name}),
                    trace_completeness=data.get("trace_completeness"),
                )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    # External server — distill text thay vì cắt 500-char (Nguyên tắc #1)
    return _distill_external_text(text, tool_name, server_url)
