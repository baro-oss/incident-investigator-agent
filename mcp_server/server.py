"""
MCP Tool Server — demo server expose investigation tools qua MCP protocol.

Giao thức: JSON-RPC 2.0 over HTTP (MCP Streamable HTTP transport subset).
Endpoint: POST /mcp

Đây là ví dụ cách bất kỳ team nào expose monitoring tools của họ:
- Team A: Prometheus metrics → map vào Tool/Observation
- Team B: Loki logs → map vào Tool/Observation
- Team C: Jaeger traces → map vào Tool/Observation
→ Agent tự discover, engine không thay đổi.

Upgrade Python 3.10+: thay server này bằng FastMCP (mcp SDK), wire y hệt.
"""
from __future__ import annotations

import asyncio
import dataclasses
import inspect
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure src/ in path khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agent.tools.registry import ALL_LOCAL_TOOLS

logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Tool Server", version="0.1.0", docs_url=None)

_MCP_PROTOCOL_VERSION = "2024-11-05"
_SERVER_INFO = {"name": "investigation-tools", "version": "0.1.0"}

# Tools exposed qua MCP — có thể bỏ 1 tool để demo hot-plug
# Mặc định: tất cả 5 tool nội bộ. Comment out bất kỳ dòng nào để thử hot-unplug.
_EXPOSED_TOOLS = {t.name: t for t in ALL_LOCAL_TOOLS}


@app.post("/mcp")
async def mcp_endpoint(request: Request) -> JSONResponse:
    """Endpoint JSON-RPC 2.0 duy nhất — xử lý tất cả MCP requests."""
    try:
        body = await request.json()
    except Exception:
        return _error_response(None, -32700, "Parse error")

    method = body.get("method", "")
    params = body.get("params") or {}
    req_id = body.get("id")

    if method == "initialize":
        return _result_response(req_id, {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": _SERVER_INFO,
        })

    elif method == "tools/list":
        tools_spec = []
        for t in _EXPOSED_TOOLS.values():
            tools_spec.append({
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            })
        return _result_response(req_id, {"tools": tools_spec})

    elif method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments") or {}

        tool = _EXPOSED_TOOLS.get(name)
        if tool is None:
            return _error_response(req_id, -32601, f"Tool not found: '{name}'")

        try:
            if inspect.iscoroutinefunction(tool.run):
                obs = await tool.run(arguments)
            else:
                obs = await asyncio.to_thread(tool.run, arguments)

            obs_json = json.dumps(dataclasses.asdict(obs), ensure_ascii=False)
            return _result_response(req_id, {
                "content": [{"type": "text", "text": obs_json}],
                "isError": False,
            })
        except Exception as e:
            logger.error("Tool '%s' lỗi: %s", name, e)
            return _result_response(req_id, {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            })

    elif method == "notifications/initialized":
        # Client thông báo đã init xong — không cần response theo MCP spec
        return JSONResponse(content={}, status_code=204)

    else:
        return _error_response(req_id, -32601, f"Method not found: '{method}'")


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "exposed_tools": list(_EXPOSED_TOOLS.keys()),
        "tool_count": len(_EXPOSED_TOOLS),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _result_response(req_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error_response(req_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})
