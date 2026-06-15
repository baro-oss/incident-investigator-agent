"""
FastAPI webhook server — cửa vào HTTP cho investigation engine.

── Backward compat (route về project 'default') ──────────────
POST /trigger                    → investigation
GET/POST/PATCH/DELETE /mcp-servers[/{id}[/ping]]

── Projects ──────────────────────────────────────────────────
GET    /projects
POST   /projects
GET    /projects/{pid}
PATCH  /projects/{pid}
DELETE /projects/{pid}

── Per-project trigger ───────────────────────────────────────
POST   /projects/{pid}/trigger

── Per-project services ─────────────────────────────────────
GET    /projects/{pid}/services
POST   /projects/{pid}/services
DELETE /projects/{pid}/services/{svc}

── Per-project MCP servers ──────────────────────────────────
GET    /projects/{pid}/mcp-servers
POST   /projects/{pid}/mcp-servers
PATCH  /projects/{pid}/mcp-servers/{mid}
DELETE /projects/{pid}/mcp-servers/{mid}
POST   /projects/{pid}/mcp-servers/{mid}/ping

── Auth (Phase 5 Ngày 22) ───────────────────────────────────
GET    /auth/login
POST   /auth/login
POST   /auth/logout
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path as _Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from agent.auth.deps import NotAuthenticated, NotAuthorized
from agent.intake.adapters import list_sources, route_adapter
from agent.intake.mcp_registry import (
    add_server,
    get_server_by_id,
    list_servers,
    remove_server,
    update_server,
)
from agent.intake.normalizer import map_simple_payload
from agent.intake.project_registry import (
    SUPPORTED_CHANNELS,
    add_project_service,
    create_project,
    delete_project,
    get_project,
    get_project_llm,
    list_project_channels,
    list_project_services,
    list_projects,
    remove_project_channel,
    remove_project_service,
    set_project_channel,
    set_project_llm,
    update_project,
)
from agent.intake.runner import _active_investigations, trigger_investigation

logger = logging.getLogger(__name__)
_start_time = time.time()

_TEMPLATES_DIR = _Path(__file__).parent.parent / "dashboard" / "templates"
_auth_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _project_or_404(project_id: str):
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' không tồn tại")
    return p


def _resolve_request(source: Optional[str], payload: Dict[str, Any], project_id: str = "default"):
    if source:
        req = route_adapter(source, payload)
        if req is None:
            raise HTTPException(
                status_code=422,
                detail=f"Adapter '{source}' không parse được payload. Nguồn hỗ trợ: {list_sources()}",
            )
    else:
        req = map_simple_payload(payload)
        if req is None:
            raise HTTPException(status_code=422, detail="Không thể parse payload")

    req.project_id = project_id
    req.dedup_key = f"{project_id}|{req.service}|{req.scenario}|{req.time_window}"
    return req


# ── Startup ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap root user từ env ROOT_USERNAME/ROOT_PASSWORD
    try:
        from agent.auth.rbac import bootstrap_root
        bootstrap_root()
    except Exception as e:
        logger.warning("bootstrap_root failed (migration not run yet?): %s", e)

    # A3: Trace retention purge on startup
    try:
        retention_days = int(os.environ.get("TRACE_RETENTION_DAYS", "30"))
        from agent.storage.db import open_db
        _conn = open_db()
        cutoff_ts = (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            - __import__("datetime").timedelta(days=retention_days)
        ).isoformat()
        result = _conn.execute(
            "DELETE FROM trace_events WHERE created_at < ?", (cutoff_ts,)
        )
        _conn.commit()
        _conn.close()
        if result.rowcount:
            logger.info("A3 trace retention: purged %d events older than %d days", result.rowcount, retention_days)
    except Exception as e:
        logger.warning("A3 trace retention purge failed: %s", e)

    projects = list_projects()
    for p in projects:
        servers = list_servers(project_id=p["id"])
        enabled = sum(1 for s in servers if s["enabled"])
        services = list_project_services(p["id"])
        logger.info(
            "Project '%s': %d MCP server(s) enabled, services: %s",
            p["id"], enabled, services or "(none)",
        )
    yield


app = FastAPI(title="Investigation Agent", version="0.8.0", docs_url="/docs", lifespan=lifespan)

# ── SessionMiddleware (RBAC — Phase 5 Ngày 22) ───────────────────────────────
_SESSION_SECRET = os.getenv("SESSION_SECRET_KEY", "dev-secret-rbac-change-in-prod")
app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    session_cookie="ia_session",
    max_age=3600 * 24 * 7,  # 1 tuần
    https_only=False,
    same_site="lax",
)


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    # Nếu request là AJAX/API → JSON 401; ngược lại redirect HTML
    accept = request.headers.get("Accept", "")
    if "application/json" in accept or request.url.path.startswith("/api"):
        return JSONResponse(status_code=401, content={"detail": "Chưa đăng nhập"})
    return RedirectResponse(f"/auth/login?next={request.url.path}", status_code=303)


@app.exception_handler(NotAuthorized)
async def not_authorized_handler(request: Request, exc: NotAuthorized):
    accept = request.headers.get("Accept", "")
    if "application/json" in accept:
        return JSONResponse(status_code=403, content={"detail": f"Thiếu quyền: {exc.perm}"})
    return HTMLResponse(
        f"<h3 style='font-family:sans-serif;padding:2rem'>403 Forbidden — thiếu quyền: <code>{exc.perm}</code>"
        f"<br><a href='/dashboard'>← Về dashboard</a></h3>",
        status_code=403,
    )


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/auth/login", response_class=HTMLResponse)
async def auth_login_get(request: Request, next: str = "/dashboard"):
    # Nếu đã đăng nhập → redirect
    if request.session.get("user_id"):
        return RedirectResponse(next or "/dashboard", status_code=303)
    return _auth_templates.TemplateResponse("login.html", {
        "request": request,
        "next": next,
        "error": None,
    })


@app.post("/auth/login", response_class=HTMLResponse)
async def auth_login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/dashboard"),
):
    from agent.auth.rbac import get_user_by_username, verify_password
    user = get_user_by_username(username)
    error = None
    if not user:
        error = "Tên đăng nhập hoặc mật khẩu không đúng"
    elif not user["is_active"]:
        error = "Tài khoản bị vô hiệu hóa"
    elif not verify_password(password, user["password_hash"]):
        error = "Tên đăng nhập hoặc mật khẩu không đúng"

    if error:
        return _auth_templates.TemplateResponse("login.html", {
            "request": request,
            "next": next,
            "error": error,
        })

    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["is_root"] = bool(user["is_root"])
    redirect_to = next if next.startswith("/") else "/dashboard"
    return RedirectResponse(redirect_to, status_code=303)


@app.post("/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/auth/login", status_code=303)


# ── Dashboard UI ──────────────────────────────────────────────────────────────

from agent.dashboard.router import router as _dash_router

_STATIC = _Path(__file__).parent.parent / "dashboard" / "static"
app.mount("/dashboard/static", StaticFiles(directory=str(_STATIC)), name="dashboard-static")
app.include_router(_dash_router, prefix="/dashboard")


# ── Backward compat: global trigger → default project ─────────────────────────

@app.post("/trigger", status_code=202)
async def trigger_global(request: Request) -> JSONResponse:
    return await _handle_trigger_request(request, "default")


# ── Backward compat: global MCP server management ─────────────────────────────

@app.get("/mcp-servers")
def get_mcp_servers_global() -> Dict[str, Any]:
    return _list_mcp_servers("default")


@app.post("/mcp-servers", status_code=201)
def create_mcp_server_global(body: Dict[str, Any]) -> Dict[str, Any]:
    return _create_mcp_server("default", body)


@app.patch("/mcp-servers/{server_id}")
def patch_mcp_server_global(server_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return _patch_mcp_server("default", server_id, body)


@app.delete("/mcp-servers/{server_id}")
def delete_mcp_server_global(server_id: int) -> Dict[str, Any]:
    return _delete_mcp_server("default", server_id)


@app.post("/mcp-servers/{server_id}/ping")
async def ping_mcp_server_global(server_id: int) -> Dict[str, Any]:
    return await _ping_mcp_server("default", server_id)


# ── Health / meta ─────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "active_investigations": len(_active_investigations),
        "active_ids": list(_active_investigations),
    }


@app.get("/adapters")
def adapters() -> Dict[str, Any]:
    return {"supported_sources": list_sources()}


# ── Project CRUD ──────────────────────────────────────────────────────────────

project_router = APIRouter(prefix="/projects", tags=["projects"])


@project_router.get("")
def get_projects() -> Dict[str, Any]:
    projects = list_projects()
    result = []
    for p in projects:
        services = list_project_services(p["id"])
        servers = list_servers(project_id=p["id"])
        result.append({
            **p,
            "services": services,
            "mcp_server_count": len(servers),
            "mcp_enabled": sum(1 for s in servers if s["enabled"]),
        })
    return {"projects": result, "total": len(result)}


@project_router.post("", status_code=201)
def post_project(body: Dict[str, Any]) -> Dict[str, Any]:
    project_id = (body.get("id") or "").strip().lower().replace(" ", "-")
    name = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip()

    if not project_id:
        raise HTTPException(422, "'id' là bắt buộc (slug, vd: 'payment-platform')")
    if not name:
        raise HTTPException(422, "'name' là bắt buộc")
    if not project_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(422, "'id' chỉ được dùng chữ cái, số, dấu gạch ngang/dưới")

    try:
        return create_project(project_id, name, description)
    except ValueError as e:
        raise HTTPException(409, str(e))


@project_router.get("/{project_id}")
def get_one_project(project_id: str) -> Dict[str, Any]:
    p = _project_or_404(project_id)
    services = list_project_services(project_id)
    servers = list_servers(project_id=project_id)
    return {**p, "services": services, "mcp_servers": servers}


@project_router.patch("/{project_id}")
def patch_project(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _project_or_404(project_id)
    updated = update_project(project_id, **body)
    return updated


@project_router.delete("/{project_id}")
def del_project(project_id: str) -> Dict[str, Any]:
    try:
        if not delete_project(project_id):
            raise HTTPException(404, f"Project '{project_id}' không tồn tại")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "deleted", "id": project_id}


@project_router.post("/{project_id}/trigger", status_code=202)
async def trigger_project(project_id: str, request: Request) -> JSONResponse:
    _project_or_404(project_id)
    return await _handle_trigger_request(request, project_id)


@project_router.get("/{project_id}/services")
def get_services(project_id: str) -> Dict[str, Any]:
    _project_or_404(project_id)
    services = list_project_services(project_id)
    return {"project_id": project_id, "services": services, "total": len(services)}


@project_router.post("/{project_id}/services", status_code=201)
def post_service(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _project_or_404(project_id)
    service = (body.get("service") or "").strip()
    if not service:
        raise HTTPException(422, "'service' là bắt buộc")
    add_project_service(project_id, service)
    return {"project_id": project_id, "service": service, "status": "added"}


@project_router.delete("/{project_id}/services/{service}")
def del_service(project_id: str, service: str) -> Dict[str, Any]:
    _project_or_404(project_id)
    if not remove_project_service(project_id, service):
        raise HTTPException(404, f"Service '{service}' không có trong project '{project_id}'")
    return {"project_id": project_id, "service": service, "status": "removed"}


@project_router.get("/{project_id}/channels")
def get_channels(project_id: str) -> Dict[str, Any]:
    _project_or_404(project_id)
    channels = list_project_channels(project_id)
    return {
        "project_id": project_id,
        "channels": channels,
        "total": len(channels),
        "supported": sorted(SUPPORTED_CHANNELS),
    }


@project_router.post("/{project_id}/channels", status_code=201)
def post_channel(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _project_or_404(project_id)
    channel = (body.get("channel") or "").strip().lower()
    if not channel:
        raise HTTPException(422, "'channel' là bắt buộc")
    config = body.get("config") or {}
    if not isinstance(config, dict):
        raise HTTPException(422, "'config' phải là object JSON")
    enabled = bool(body.get("enabled", True))
    if channel == "email" and not config.get("to") and not __import__("os").getenv("SMTP_TO"):
        raise HTTPException(422, "Email channel cần config['to'] hoặc env SMTP_TO")
    try:
        return set_project_channel(project_id, channel, config=config, enabled=enabled)
    except ValueError as e:
        raise HTTPException(422, str(e))


@project_router.patch("/{project_id}/channels/{channel}")
def patch_channel(project_id: str, channel: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _project_or_404(project_id)
    existing = list_project_channels(project_id)
    entry = next((c for c in existing if c["channel"] == channel), None)
    if entry is None:
        raise HTTPException(404, f"Channel '{channel}' chưa cấu hình cho project '{project_id}'")
    new_config = body.get("config", entry["config"])
    new_enabled = bool(body.get("enabled", entry["enabled"]))
    try:
        return set_project_channel(project_id, channel, config=new_config, enabled=new_enabled)
    except ValueError as e:
        raise HTTPException(422, str(e))


@project_router.delete("/{project_id}/channels/{channel}")
def del_channel(project_id: str, channel: str) -> Dict[str, Any]:
    _project_or_404(project_id)
    if not remove_project_channel(project_id, channel):
        raise HTTPException(404, f"Channel '{channel}' chưa cấu hình cho project '{project_id}'")
    return {"project_id": project_id, "channel": channel, "status": "removed"}


@project_router.get("/{project_id}/llm")
def get_llm_config(project_id: str) -> Dict[str, Any]:
    _project_or_404(project_id)
    cfg = get_project_llm(project_id)
    return {"project_id": project_id, "llm": cfg, "using_global_env": cfg is None}


@project_router.patch("/{project_id}/llm")
def patch_llm_config(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _project_or_404(project_id)
    provider = (body.get("provider") or "").strip().lower()
    model = body.get("model") or None
    config = body.get("config") or {}
    if not provider:
        raise HTTPException(422, "'provider' là bắt buộc (anthropic|gemini|openai|groq|...)")
    if not isinstance(config, dict):
        raise HTTPException(422, "'config' phải là object JSON")
    try:
        result = set_project_llm(project_id, provider, model=model, config=config)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"project_id": project_id, "llm": result}


@project_router.get("/{project_id}/mcp-servers")
def get_mcp_servers(project_id: str) -> Dict[str, Any]:
    _project_or_404(project_id)
    return _list_mcp_servers(project_id)


@project_router.post("/{project_id}/mcp-servers", status_code=201)
def post_mcp_server(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    _project_or_404(project_id)
    return _create_mcp_server(project_id, body)


@project_router.patch("/{project_id}/mcp-servers/{server_id}")
def patch_mcp_server(project_id: str, server_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    _project_or_404(project_id)
    return _patch_mcp_server(project_id, server_id, body)


@project_router.delete("/{project_id}/mcp-servers/{server_id}")
def del_mcp_server(project_id: str, server_id: int) -> Dict[str, Any]:
    _project_or_404(project_id)
    return _delete_mcp_server(project_id, server_id)


@project_router.post("/{project_id}/mcp-servers/{server_id}/ping")
async def ping_mcp_server(project_id: str, server_id: int) -> Dict[str, Any]:
    _project_or_404(project_id)
    return await _ping_mcp_server(project_id, server_id)


app.include_router(project_router)


# ── Shared implementation ─────────────────────────────────────────────────────

def _allow_anon_trigger() -> bool:
    """A4: Cho phép trigger không cần token khi ALLOW_ANON_TRIGGER=true (dev-only)."""
    return os.environ.get("ALLOW_ANON_TRIGGER", "false").lower() in ("1", "true", "yes")


async def _handle_trigger_request(request: Request, project_id: str) -> JSONResponse:
    """Đọc raw body → A4 token auth → verify webhook signature → parse JSON → dispatch."""
    import json as _json
    from agent.intake.adapters._shared import verify_webhook_signature

    # A4: API token auth — validate X-API-Token trước khi xử lý
    if not _allow_anon_trigger():
        raw_token = (
            request.headers.get("x-api-token")
            or request.headers.get("x-api-key")
        )
        if not raw_token:
            raise HTTPException(
                status_code=401,
                detail="Yêu cầu header X-API-Token. Set ALLOW_ANON_TRIGGER=true để bỏ qua (dev).",
            )
        from agent.auth.rbac import verify_token
        token_user = verify_token(raw_token)
        if not token_user:
            raise HTTPException(status_code=401, detail="API token không hợp lệ hoặc đã thu hồi.")
        if not token_user.get("is_active"):
            raise HTTPException(status_code=403, detail="Tài khoản bị vô hiệu hóa.")

    raw_body = await request.body()
    source = request.headers.get("x-alert-source")

    # Verify chữ ký nếu source header được cung cấp
    if source:
        headers_lower = {k.lower(): v for k, v in request.headers.items()}
        if not verify_webhook_signature(source, raw_body, headers_lower):
            raise HTTPException(
                status_code=401,
                detail=(
                    f"Webhook signature không hợp lệ cho source '{source}'. "
                    "Kiểm tra HMAC-SHA256 header và env secret."
                ),
            )

    try:
        payload = _json.loads(raw_body) if raw_body else {}
    except _json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Payload không phải JSON hợp lệ")

    return await _do_trigger(project_id, payload, source)


async def _do_trigger(
    project_id: str,
    payload: Dict[str, Any],
    source: Optional[str],
) -> JSONResponse:
    req = _resolve_request(source, payload, project_id)

    if req.dedup_key in _active_investigations:
        return JSONResponse(status_code=202, content={
            "status": "duplicate",
            "investigation_id": req.dedup_key,
            "project_id": project_id,
        })

    trigger_investigation(req)
    return JSONResponse(status_code=202, content={
        "status": "accepted",
        "investigation_id": req.dedup_key,
        "project_id": project_id,
        "service": req.service,
        "scenario": req.scenario,
        "time_window": req.time_window,
        "adapter": source or "simple",
        "engine": "multi_agent" if req.multi_agent else "langgraph",
        "message": "Điều tra đã bắt đầu nền. Kết quả sẽ gửi qua Telegram.",
    })


def _list_mcp_servers(project_id: str) -> Dict[str, Any]:
    servers = list_servers(project_id=project_id)
    return {
        "project_id": project_id,
        "servers": servers,
        "total": len(servers),
        "enabled": sum(1 for s in servers if s["enabled"]),
    }


def _create_mcp_server(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    import json as _json
    name = (body.get("name") or "").strip()
    url = (body.get("url") or "").strip()
    description = (body.get("description") or "").strip()
    auth_type = (body.get("auth_type") or "none").strip()
    auth_config = (body.get("auth_config") or "{}").strip()

    if not name:
        raise HTTPException(422, "'name' là bắt buộc")
    if not url:
        raise HTTPException(422, "'url' là bắt buộc")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "'url' phải bắt đầu bằng http:// hoặc https://")
    if auth_type not in ("none", "bearer", "api_key"):
        raise HTTPException(422, "'auth_type' phải là: none | bearer | api_key")
    try:
        _json.loads(auth_config)
    except Exception:
        raise HTTPException(422, "'auth_config' phải là JSON hợp lệ")

    try:
        return add_server(name, url, description, project_id=project_id,
                          auth_type=auth_type, auth_config=auth_config)
    except ValueError as e:
        raise HTTPException(409, str(e))


def _patch_mcp_server(project_id: str, server_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        updated = update_server(server_id, project_id=project_id, **body)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if updated is None:
        raise HTTPException(404, f"MCP server id={server_id} không thuộc project '{project_id}'")
    return updated


def _delete_mcp_server(project_id: str, server_id: int) -> Dict[str, Any]:
    if not remove_server(server_id, project_id=project_id):
        raise HTTPException(404, f"MCP server id={server_id} không thuộc project '{project_id}'")
    return {"status": "deleted", "id": server_id, "project_id": project_id}


async def _ping_mcp_server(project_id: str, server_id: int) -> Dict[str, Any]:
    server = get_server_by_id(server_id, project_id=project_id)
    if not server:
        raise HTTPException(404, f"MCP server id={server_id} không thuộc project '{project_id}'")

    import json as _json
    from agent.tools.mcp_client import MCPClient
    auth_config: Dict[str, Any] = {}
    try:
        auth_config = _json.loads(server.get("auth_config") or "{}")
    except Exception:
        pass
    client = MCPClient(
        server["url"],
        auth_type=server.get("auth_type", "none"),
        auth_config=auth_config,
    )
    try:
        await client.connect()
        tools = await client.get_tools()
        return {
            "status": "ok",
            "id": server_id,
            "project_id": project_id,
            "url": server["url"],
            "tool_count": len(tools),
            "tools": [{"name": t.name, "description": t.description[:80]} for t in tools],
        }
    except Exception as e:
        return {"status": "error", "id": server_id, "url": server["url"], "error": str(e)}
    finally:
        await client.close()
