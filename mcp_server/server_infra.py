"""
MCP Infra Tool Server — real infrastructure tools qua MCP protocol.

Đây là MCP server "thật" (không phụ thuộc synthetic data của project):
- fetch_url: HTTP GET bất kỳ URL → trả text content
- list_files: liệt kê file trong thư mục
- get_system_info: CPU / memory / disk / process
- check_port: kiểm tra TCP port có mở không

Chứng minh hot-plug: agent của project này có thể discover + dùng tool từ
server này mà không cần chỉnh engine hay local tool registry.

Port: 9001 (khác 9000 dùng bởi server.py demo)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import socket
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Infra Tool Server", version="1.0.0", docs_url=None)

_MCP_PROTOCOL_VERSION = "2024-11-05"
_SERVER_INFO = {"name": "infra-tools", "version": "1.0.0"}


# ── Tool definitions ──────────────────────────────────────────────────────────

_TOOL_SPECS = [
    {
        "name": "fetch_url",
        "description": (
            "HTTP GET một URL và trả nội dung text. Hữu ích để kiểm tra endpoint, "
            "đọc config remote, hoặc lấy status trang web. Tự động cắt nội dung > 4000 ký tự."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL cần fetch (http/https)"},
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout (mặc định 10 giây)",
                    "default": 10,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "Liệt kê file và thư mục trong một đường dẫn. Trả tên, loại (file/dir), "
            "và kích thước. Hữu ích để kiểm tra log dir, config dir."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Đường dẫn thư mục cần liệt kê"},
                "max_entries": {
                    "type": "integer",
                    "description": "Số entry tối đa trả về (mặc định 50)",
                    "default": 50,
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "get_system_info",
        "description": (
            "Lấy thông tin hệ thống hiện tại: CPU cores, memory, disk usage, "
            "OS info, uptime. Hữu ích để kiểm tra resource pressure khi điều tra sự cố."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "check_port",
        "description": (
            "Kiểm tra TCP port trên host có đang mở không. Trả is_open, latency_ms. "
            "Hữu ích để xác nhận service endpoint còn alive khi điều tra."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Hostname hoặc IP"},
                "port": {"type": "integer", "description": "Port number (1-65535)"},
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout (mặc định 5 giây)",
                    "default": 5,
                },
            },
            "required": ["host", "port"],
        },
    },
]


# ── Tool implementations ───────────────────────────────────────────────────────

def _tool_fetch_url(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url", "")
    timeout = int(args.get("timeout_seconds", 10))

    if not url.startswith(("http://", "https://")):
        return {
            "summary": f"URL không hợp lệ: '{url}' (phải bắt đầu bằng http:// hoặc https://)",
            "status_code": None,
            "content": "",
            "error": "invalid_url",
        }

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MCP-Infra/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="replace")
            truncated = len(raw) > 4000
            content = raw[:4000]
            return {
                "summary": f"HTTP {status} — {len(raw)} bytes, Content-Type: {content_type}",
                "status_code": status,
                "content": content,
                "truncated": truncated,
                "total_bytes": len(raw),
                "error": None,
            }
    except Exception as e:
        return {
            "summary": f"Fetch lỗi: {type(e).__name__}: {e}",
            "status_code": None,
            "content": "",
            "error": str(e),
        }


def _tool_list_files(args: Dict[str, Any]) -> Dict[str, Any]:
    path_str = args.get("path", ".")
    max_entries = int(args.get("max_entries", 50))

    try:
        p = Path(path_str).expanduser().resolve()
        if not p.exists():
            return {
                "summary": f"Đường dẫn không tồn tại: '{path_str}'",
                "entries": [],
                "total": 0,
                "error": "not_found",
            }
        if not p.is_dir():
            return {
                "summary": f"'{path_str}' là file, không phải thư mục",
                "entries": [],
                "total": 0,
                "error": "not_a_dir",
            }

        entries = []
        all_items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        for item in all_items[:max_entries]:
            try:
                size = item.stat().st_size if item.is_file() else None
                entries.append({
                    "name": item.name,
                    "type": "file" if item.is_file() else "dir",
                    "size_bytes": size,
                })
            except OSError:
                entries.append({"name": item.name, "type": "unknown", "size_bytes": None})

        total = sum(1 for _ in p.iterdir())
        return {
            "summary": f"{total} entries trong '{p}'" + (f" (hiển thị {max_entries})" if total > max_entries else ""),
            "path": str(p),
            "entries": entries,
            "total": total,
            "truncated": total > max_entries,
        }
    except Exception as e:
        return {
            "summary": f"list_files lỗi: {e}",
            "entries": [],
            "error": str(e),
        }


def _tool_get_system_info(_args: Dict[str, Any]) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "os": platform.system(),
        "os_version": platform.version()[:120],
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        "cpu_cores": os.cpu_count() or 1,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # Memory (best-effort — không import psutil)
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {}
        for line in lines[:5]:
            k, v = line.split(":")
            mem[k.strip()] = v.strip()
        info["memory"] = mem
    except Exception:
        info["memory"] = "unavailable (non-Linux hoặc thiếu /proc/meminfo)"

    # Disk usage cho thư mục hiện tại
    try:
        stat = os.statvfs(".")
        total_gb = stat.f_frsize * stat.f_blocks / 1e9
        free_gb = stat.f_frsize * stat.f_bavail / 1e9
        info["disk_cwd"] = {
            "total_gb": round(total_gb, 2),
            "free_gb": round(free_gb, 2),
            "used_pct": round((1 - free_gb / total_gb) * 100, 1) if total_gb else 0,
        }
    except Exception:
        info["disk_cwd"] = "unavailable"

    summary_parts = [f"OS: {info['os']}", f"CPU: {info['cpu_cores']} cores", f"Host: {info['hostname']}"]
    if isinstance(info.get("disk_cwd"), dict):
        d = info["disk_cwd"]
        summary_parts.append(f"Disk: {d['used_pct']}% used ({d['free_gb']:.1f}GB free)")

    return {"summary": " | ".join(summary_parts), **info}


def _tool_check_port(args: Dict[str, Any]) -> Dict[str, Any]:
    host = args.get("host", "localhost")
    port = int(args.get("port", 80))
    timeout = float(args.get("timeout_seconds", 5))

    import time
    start = time.monotonic()
    is_open = False
    error = None

    try:
        with socket.create_connection((host, port), timeout=timeout):
            is_open = True
    except socket.timeout:
        error = "timeout"
    except ConnectionRefusedError:
        error = "connection_refused"
    except Exception as e:
        error = str(e)

    latency_ms = round((time.monotonic() - start) * 1000, 1)
    status = "OPEN" if is_open else f"CLOSED ({error})"
    return {
        "summary": f"{host}:{port} → {status} ({latency_ms}ms)",
        "host": host,
        "port": port,
        "is_open": is_open,
        "latency_ms": latency_ms,
        "error": error,
    }


_TOOL_RUNNERS = {
    "fetch_url": _tool_fetch_url,
    "list_files": _tool_list_files,
    "get_system_info": _tool_get_system_info,
    "check_port": _tool_check_port,
}


# ── MCP endpoint ─────────────────────────────────────────────────────────────

@app.post("/mcp")
async def mcp_endpoint(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _error_resp(None, -32700, "Parse error")

    method = body.get("method", "")
    params = body.get("params") or {}
    req_id = body.get("id")

    if method == "initialize":
        return _ok_resp(req_id, {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": _SERVER_INFO,
        })

    elif method == "tools/list":
        return _ok_resp(req_id, {"tools": _TOOL_SPECS})

    elif method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        runner = _TOOL_RUNNERS.get(name)
        if runner is None:
            return _error_resp(req_id, -32601, f"Tool not found: '{name}'")
        try:
            result = await asyncio.to_thread(runner, arguments)
            return _ok_resp(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "isError": False,
            })
        except Exception as e:
            logger.error("Tool '%s' error: %s", name, e)
            return _ok_resp(req_id, {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            })

    elif method == "notifications/initialized":
        return JSONResponse(content={}, status_code=204)

    else:
        return _error_resp(req_id, -32601, f"Method not found: '{method}'")


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "server": "infra-tools",
        "tools": [t["name"] for t in _TOOL_SPECS],
        "tool_count": len(_TOOL_SPECS),
    }


def _ok_resp(req_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error_resp(req_id: Any, code: int, msg: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}})
