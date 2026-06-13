"""
Tool registry — build list[Tool] đưa vào engine.

Engine chỉ thấy list[Tool] đồng nhất.
Thêm tool mới: import + thêm vào ALL_TOOLS, hoặc cấu hình MCP_SERVER_URLS.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, List, Optional

from agent.tools.contracts import Tool
from agent.tools.get_dependencies import get_dependencies
from agent.tools.get_error_breakdown import get_error_breakdown
from agent.tools.get_metrics import get_metrics
from agent.tools.get_recent_deploys import get_recent_deploys
from agent.tools.trace_request import trace_request

if TYPE_CHECKING:
    from agent.tools.mcp_client import MCPClient

logger = logging.getLogger(__name__)

ALL_LOCAL_TOOLS: List[Tool] = [
    get_error_breakdown,
    get_metrics,
    get_recent_deploys,
    get_dependencies,
    trace_request,
]


def get_tool_registry() -> List[Tool]:
    """Trả về danh sách tool nội bộ (SQLite). Sync, không cần MCP."""
    return list(ALL_LOCAL_TOOLS)


async def build_tool_registry(mcp_clients: Optional[List["MCPClient"]] = None) -> List[Tool]:
    """
    Xây registry đầy đủ: local tools + MCP tools từ tất cả client đã connect.

    MCP tool override local tool cùng tên — MCP là nguồn ưu tiên khi đã cấu hình.
    Nếu MCP server không có tool X → dùng local fallback (nếu có).
    """
    # Bắt đầu với local tools
    tools_by_name: dict[str, Tool] = {t.name: t for t in ALL_LOCAL_TOOLS}

    if mcp_clients:
        for client in mcp_clients:
            try:
                mcp_tools = await client.get_tools()
                for t in mcp_tools:
                    if t.name in tools_by_name:
                        logger.info("MCP override local tool: %s", t.name)
                    tools_by_name[t.name] = t
            except Exception as e:
                logger.warning("Không lấy được tool từ MCP client %s: %s", client.url, e)

    merged = list(tools_by_name.values())
    sources = {"local": [], "mcp": []}
    for t in merged:
        if any(t.name == lt.name for lt in ALL_LOCAL_TOOLS):
            sources["local"].append(t.name)
        else:
            sources["mcp"].append(t.name)

    logger.info("Registry: %d tool(s) — local=%s mcp_only=%s",
                len(merged), sources["local"], sources["mcp"])
    return merged


def get_mcp_urls_from_env() -> List[str]:
    """Đọc MCP_SERVER_URLS từ env (comma-separated). Trả list URL."""
    raw = os.getenv("MCP_SERVER_URLS", "").strip()
    if not raw:
        return []
    return [u.strip() for u in raw.split(",") if u.strip()]
