"""
MCP GitLab Code Server — đọc source code qua GitLab REST API v4.

Đây là "code seam" của Phase 10: agent đọc mã nguồn qua external MCP, hệ thống
KHÔNG quản lý source. Tất cả tool READ-ONLY (chỉ GET tới GitLab API).

Tools expose (JSON-RPC 2.0 over HTTP, endpoint POST /mcp):
- get_diff(repo, ref, path)    → unified diff của commit/tag `ref` so với parent.
                                  Tên `get_diff` khớp candidate của get_code_diff
                                  → kích hoạt code_distill (Nguyên tắc #1).
- read_file(repo, ref, path)   → nội dung 1 file tại ref (cắt 4000 ký tự).
- search_code(repo, query)     → tìm chuỗi trong blobs của repo.

Config qua env (không hardcode secret):
- GITLAB_TOKEN     : Personal Access Token (scope read_api / read_repository).
- GITLAB_API_BASE  : mặc định https://gitlab.com/api/v4

Port: 9002 (khác 9000 demo tools, 9001 infra tools).

Upgrade path Python 3.10+: thay bằng FastMCP, wire y hệt — engine/registry không đổi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="MCP GitLab Code Server", version="1.0.0", docs_url=None)

_MCP_PROTOCOL_VERSION = "2024-11-05"
_SERVER_INFO = {"name": "gitlab-code", "version": "1.0.0"}

_API_BASE = os.getenv("GITLAB_API_BASE", "https://gitlab.com/api/v4").rstrip("/")
_TOKEN = os.getenv("GITLAB_TOKEN", "")
_HTTP_TIMEOUT = int(os.getenv("GITLAB_HTTP_TIMEOUT", "15"))
_MAX_FILE_CHARS = 4000


# ── Tool definitions ──────────────────────────────────────────────────────────

_TOOL_SPECS = [
    {
        "name": "get_diff",
        "description": (
            "Lấy diff (unified) của một commit/tag/ref so với parent trong repo GitLab. "
            "Dùng để đọc thay đổi của version deploy nghi vấn. Trả raw diff text. READ-ONLY."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "URL hoặc path_with_namespace của repo (vd 'org/payment-gateway')"},
                "ref": {"type": "string", "description": "Tag / branch / commit SHA cần xem diff (vd 'v2.4.0')"},
                "path": {"type": "string", "description": "Lọc theo path file/dir (tùy chọn — để trống = toàn bộ)"},
            },
            "required": ["repo", "ref"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Đọc nội dung một file tại một ref (tag/branch/commit) trong repo GitLab. "
            "Cắt nội dung > 4000 ký tự. READ-ONLY."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "URL hoặc path_with_namespace của repo"},
                "ref": {"type": "string", "description": "Ref (mặc định nhánh mặc định của repo)"},
                "path": {"type": "string", "description": "Đường dẫn file trong repo (vd 'src/db/pool.py')"},
            },
            "required": ["repo", "path"],
        },
    },
    {
        "name": "search_code",
        "description": (
            "Tìm một chuỗi trong source code (blobs) của repo GitLab. Trả danh sách file + dòng khớp. READ-ONLY."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "URL hoặc path_with_namespace của repo"},
                "query": {"type": "string", "description": "Chuỗi cần tìm"},
            },
            "required": ["repo", "query"],
        },
    },
]


# ── GitLab API helpers ─────────────────────────────────────────────────────────

def _project_id(repo: str) -> str:
    """
    Chuẩn hóa `repo` (URL đầy đủ hoặc path) → project id URL-encoded cho GitLab API.

    'https://gitlab.com/org/payment-gateway.git' → 'org%2Fpayment-gateway'
    'org/payment-gateway'                          → 'org%2Fpayment-gateway'
    """
    r = repo.strip()
    if r.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(r)
        path = parsed.path
    else:
        path = r
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return urllib.parse.quote(path, safe="")


def _api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """GET tới GitLab API, trả JSON đã parse. Raise RuntimeError nếu lỗi HTTP."""
    url = f"{_API_BASE}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "MCP-GitLabCode/1.0"}
    if _TOKEN:
        headers["PRIVATE-TOKEN"] = _TOKEN
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw else None


def _api_get_raw(path: str, params: Optional[Dict[str, Any]] = None) -> str:
    """GET tới GitLab API, trả text thô (cho file raw)."""
    url = f"{_API_BASE}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "MCP-GitLabCode/1.0"}
    if _TOKEN:
        headers["PRIVATE-TOKEN"] = _TOKEN
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _assemble_unified_diff(file_diffs: List[Dict[str, Any]], path_filter: str = "") -> str:
    """
    Ghép list per-file diff (từ GitLab commit diff API) thành unified diff text.

    Thêm header `diff --git` + `---/+++` để code_distill đếm đúng file/additions/deletions
    và dò risk signal (config-knob, removed-error-handling, dep-bump).
    """
    parts: List[str] = []
    for fd in file_diffs:
        old_path = fd.get("old_path") or fd.get("new_path") or "?"
        new_path = fd.get("new_path") or fd.get("old_path") or "?"
        if path_filter and path_filter not in old_path and path_filter not in new_path:
            continue
        parts.append(f"diff --git a/{old_path} b/{new_path}")
        if fd.get("new_file"):
            parts.append(f"--- /dev/null")
        else:
            parts.append(f"--- a/{old_path}")
        if fd.get("deleted_file"):
            parts.append(f"+++ /dev/null")
        else:
            parts.append(f"+++ b/{new_path}")
        body = fd.get("diff") or ""
        parts.append(body.rstrip("\n"))
    return "\n".join(parts)


# ── Tool implementations ───────────────────────────────────────────────────────

def _tool_get_diff(args: Dict[str, Any]) -> str:
    repo = args.get("repo", "")
    ref = args.get("ref", "")
    path_filter = (args.get("path") or "").strip()
    if not repo or not ref:
        return f"[get_diff] thiếu repo hoặc ref (repo='{repo}', ref='{ref}')"
    if not _TOKEN:
        return "[get_diff] GITLAB_TOKEN chưa cấu hình — không gọi được GitLab API."

    pid = _project_id(repo)
    try:
        # Resolve ref (tag/branch/sha) → commit SHA
        commit = _api_get(f"projects/{pid}/repository/commits/{urllib.parse.quote(ref, safe='')}")
        sha = commit.get("id") if isinstance(commit, dict) else None
        if not sha:
            return f"[get_diff] không resolve được ref '{ref}' trong {repo}"
        # Lấy diff của commit so với parent
        file_diffs = _api_get(f"projects/{pid}/repository/commits/{sha}/diff")
        if not isinstance(file_diffs, list) or not file_diffs:
            return f"[get_diff] commit {sha[:8]} ({ref}) không có thay đổi file."
        title = (commit.get("title") or "").strip()
        header = f"# commit {sha[:10]} ({ref}) — {title}\n"
        return header + _assemble_unified_diff(file_diffs, path_filter)
    except urllib.error.HTTPError as e:
        return f"[get_diff] GitLab API HTTP {e.code} cho {repo}@{ref}: {e.reason}"
    except Exception as e:  # noqa: BLE001
        return f"[get_diff] lỗi {type(e).__name__}: {e}"


def _tool_read_file(args: Dict[str, Any]) -> str:
    repo = args.get("repo", "")
    ref = (args.get("ref") or "").strip()
    path = (args.get("path") or "").strip()
    if not repo or not path:
        return f"[read_file] thiếu repo hoặc path (repo='{repo}', path='{path}')"
    if not _TOKEN:
        return "[read_file] GITLAB_TOKEN chưa cấu hình — không gọi được GitLab API."

    pid = _project_id(repo)
    enc_path = urllib.parse.quote(path, safe="")
    try:
        if not ref:
            project = _api_get(f"projects/{pid}")
            ref = (project or {}).get("default_branch", "main")
        content = _api_get_raw(f"projects/{pid}/repository/files/{enc_path}/raw", {"ref": ref})
        truncated = len(content) > _MAX_FILE_CHARS
        body = content[:_MAX_FILE_CHARS]
        head = f"# {repo}:{path}@{ref} ({len(content)} bytes{', truncated' if truncated else ''})\n"
        return head + body
    except urllib.error.HTTPError as e:
        return f"[read_file] GitLab API HTTP {e.code} cho {repo}:{path}@{ref}: {e.reason}"
    except Exception as e:  # noqa: BLE001
        return f"[read_file] lỗi {type(e).__name__}: {e}"


def _tool_search_code(args: Dict[str, Any]) -> str:
    repo = args.get("repo", "")
    query = (args.get("query") or "").strip()
    if not repo or not query:
        return f"[search_code] thiếu repo hoặc query (repo='{repo}', query='{query}')"
    if not _TOKEN:
        return "[search_code] GITLAB_TOKEN chưa cấu hình — không gọi được GitLab API."

    pid = _project_id(repo)
    try:
        results = _api_get(f"projects/{pid}/search", {"scope": "blobs", "search": query})
        if not isinstance(results, list) or not results:
            return f"[search_code] không tìm thấy '{query}' trong {repo}."
        lines = [f"# {len(results)} kết quả cho '{query}' trong {repo}"]
        for r in results[:10]:
            fname = r.get("path", "?")
            ln = r.get("startline", "?")
            data = (r.get("data") or "").strip().splitlines()
            snippet = data[0][:120] if data else ""
            lines.append(f"{fname}:{ln}  {snippet}")
        return "\n".join(lines)
    except urllib.error.HTTPError as e:
        return f"[search_code] GitLab API HTTP {e.code} cho {repo}: {e.reason}"
    except Exception as e:  # noqa: BLE001
        return f"[search_code] lỗi {type(e).__name__}: {e}"


_TOOL_RUNNERS = {
    "get_diff": _tool_get_diff,
    "read_file": _tool_read_file,
    "search_code": _tool_search_code,
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
            text = await asyncio.to_thread(runner, arguments)
            return _ok_resp(req_id, {
                "content": [{"type": "text", "text": text}],
                "isError": text.startswith("["),  # "[tool] ..." là thông điệp lỗi/empty
            })
        except Exception as e:  # noqa: BLE001
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
        "server": "gitlab-code",
        "api_base": _API_BASE,
        "token_set": bool(_TOKEN),
        "tools": [t["name"] for t in _TOOL_SPECS],
        "tool_count": len(_TOOL_SPECS),
    }


def _ok_resp(req_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error_resp(req_id: Any, code: int, msg: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}})
