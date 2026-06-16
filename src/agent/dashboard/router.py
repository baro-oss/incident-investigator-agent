"""Dashboard APIRouter — mount vào server.py tại /dashboard.
Phase 5 Ngày 22: tất cả route đều require_login; admin routes guard thêm permission.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent.auth.deps import NotAuthorized, require_login, require_perm, get_current_user
from agent.dashboard.queries import (
    get_cost_data,
    get_eval_calibration,
    get_calibration_with_feedback,
    get_eval_summary,
    get_investigation_detail,
    get_investigation_feedback,
    set_investigation_feedback,
    get_projects_overview,
    list_investigations,
    get_metrics_live,
    get_channel_config,
    get_mcp_servers_for_dashboard,
    get_project_detail,
    get_all_tools_for_dashboard,
    get_specificity_data,
    get_eval_comparison_data,
)

_HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_all_project_ids() -> list:
    try:
        from agent.intake.project_registry import list_projects
        return [p["id"] for p in list_projects()]
    except Exception:
        return ["default"]


def _get_project_services_map() -> Dict[str, list]:
    try:
        from agent.intake.project_registry import list_project_services, list_projects
        return {p["id"]: list_project_services(p["id"]) for p in list_projects()}
    except Exception:
        return {}


def _ctx(request: Request, user: dict, **kwargs) -> dict:
    """Context dict chuẩn cho template — mang theo user info."""
    return {"request": request, "current_user": user, **kwargs}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    project_id: Optional[str] = None,
    confidence: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(require_login),
):
    invs = list_investigations(
        project_id=project_id or None,
        confidence=confidence or None,
        search=search or None,
        limit=100,
    )
    return templates.TemplateResponse(request, "index.html", _ctx(request, user,
        active="home",
        investigations=invs,
        total=len(invs),
        projects=_get_all_project_ids(),
        filter_project=project_id or "",
        filter_confidence=confidence or "",
        filter_search=search or "",
    ))


@router.get("/investigations/{investigation_id}", response_class=HTMLResponse)
async def dashboard_detail(
    request: Request, investigation_id: str,
    user: dict = Depends(require_login),
):
    inv = get_investigation_detail(investigation_id)
    if not inv:
        return HTMLResponse("<h3>Investigation not found</h3>", status_code=404)

    langfuse_url = None
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
        langfuse_url = f"{host}/traces"

    feedback = get_investigation_feedback(investigation_id)
    return templates.TemplateResponse(request, "detail.html", _ctx(request, user,
        active="home",
        inv=inv,
        langfuse_url=langfuse_url,
        feedback=feedback,
    ))


@router.get("/investigations/{investigation_id}/diff", response_class=HTMLResponse)
async def dashboard_diff(
    request: Request,
    investigation_id: str,
    compare: Optional[str] = None,
    user: dict = Depends(require_login),
):
    inv_a = get_investigation_detail(investigation_id)
    if not inv_a:
        return HTMLResponse("<h3>Investigation not found</h3>", status_code=404)

    inv_b = get_investigation_detail(compare) if compare else None
    all_invs = list_investigations(limit=50)

    return templates.TemplateResponse(request, "diff.html", _ctx(request, user,
        active="home",
        inv_a=inv_a,
        inv_b=inv_b,
        compare_id=compare or "",
        all_invs=all_invs,
    ))


@router.get("/stream/{investigation_id}")
async def dashboard_stream(investigation_id: str):
    """SSE endpoint — không cần login (JS fetch không dễ kiểm session)."""
    from agent.dashboard.sse import stream as sse_stream

    async def event_generator():
        async for chunk in sse_stream(investigation_id):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/chat", response_class=HTMLResponse)
async def dashboard_chat(
    request: Request,
    user: dict = Depends(require_login),
):
    projects = get_projects_overview()

    quick_scenarios = [
        {
            "label": "scenario1 — payment-gateway timeout (14:00)",
            "service": "payment-gateway",
            "scenario": "scenario1",
            "time_window": "14:00-15:00",
            "symptom": "payment-gateway: tỷ lệ lỗi tăng đột biến từ 14:05, 87% TimeoutException",
        },
        {
            "label": "scenario2 — provider sập (15:00)",
            "service": "payment-gateway",
            "scenario": "scenario2",
            "time_window": "15:00-16:00",
            "symptom": "payment-gateway: ConnectionRefusedError 92%, latency bình thường",
        },
        {
            "label": "scenario3 — auth-service DB pool (08:00)",
            "service": "payment-gateway",
            "scenario": "scenario3",
            "time_window": "08:00-09:00",
            "symptom": "payment-gateway: AuthServiceTimeoutError 83% từ 08:11",
        },
        {
            "label": "scenario4 — api-gateway traffic surge (10:00)",
            "service": "api-gateway",
            "scenario": "scenario4",
            "time_window": "10:00-11:00",
            "symptom": "api-gateway: RateLimitError tăng đột biến, request_count tăng 5x",
        },
    ]

    return templates.TemplateResponse(request, "chat.html", _ctx(request, user,
        active="chat",
        projects=projects,
        quick_scenarios=quick_scenarios,
    ))


@router.get("/trigger", response_class=HTMLResponse)
async def dashboard_trigger_get(
    request: Request,
    scenario: Optional[str] = None,
    project_id: Optional[str] = None,
    user: dict = Depends(require_login),
):
    projects = get_projects_overview()
    svc_map = _get_project_services_map()

    first_pid = (project_id or (projects[0]["id"] if projects else "default"))
    services = svc_map.get(first_pid, [])
    recent = list_investigations(limit=5)

    return templates.TemplateResponse(request, "trigger.html", _ctx(request, user,
        active="trigger",
        projects=projects,
        services=services,
        selected_project=first_pid,
        selected_service=services[0] if services else "",
        selected_scenario=scenario or "scenario1",
        project_services_json=json.dumps(svc_map),
        recent=recent[:5],
        result=None,
    ))


@router.post("/trigger", response_class=HTMLResponse)
async def dashboard_trigger_post(
    request: Request,
    project_id: str = Form(...),
    service: str = Form(...),
    scenario: str = Form(...),
    time_window: str = Form(...),
    symptom: str = Form(""),
    user: dict = Depends(require_login),
):
    import aiohttp

    payload: Dict[str, Any] = {
        "service": service,
        "scenario": scenario,
        "time_window": time_window,
    }
    if symptom.strip():
        payload["symptom"] = symptom.strip()

    result = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://localhost:8000/projects/{project_id}/trigger",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                result = await resp.json()
    except Exception as e:
        result = {"status": "error", "error": str(e)}

    projects = get_projects_overview()
    svc_map = _get_project_services_map()
    services = svc_map.get(project_id, [])
    recent = list_investigations(limit=5)

    return templates.TemplateResponse(request, "trigger.html", _ctx(request, user,
        active="trigger",
        projects=projects,
        services=services,
        selected_project=project_id,
        selected_service=service,
        selected_scenario=scenario,
        project_services_json=json.dumps(svc_map),
        recent=recent[:5],
        result=result,
    ))


@router.get("/projects", response_class=HTMLResponse)
async def dashboard_projects(
    request: Request,
    user: dict = Depends(require_login),
):
    projects = get_projects_overview()
    can_manage = user.get("is_root") or __import__("agent.auth.rbac", fromlist=["user_can"]).user_can(user["id"], "project.manage")
    return templates.TemplateResponse(request, "projects.html", _ctx(request, user,
        active="projects",
        projects=projects,
        can_manage=can_manage,
    ))


@router.post("/projects", response_class=HTMLResponse)
async def dashboard_project_create(
    request: Request,
    project_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    user: dict = Depends(require_perm("project.manage")),
):
    from agent.intake.project_registry import create_project
    error = None
    try:
        create_project(project_id.strip().lower(), name.strip(), description.strip())
    except ValueError as e:
        error = str(e)

    if error:
        projects = get_projects_overview()
        can_manage = True
        return templates.TemplateResponse(request, "projects.html", _ctx(request, user,
            active="projects",
            projects=projects,
            can_manage=can_manage,
            create_error=error,
        ))
    return RedirectResponse("/dashboard/projects", status_code=303)


@router.post("/projects/{project_id}/edit", response_class=HTMLResponse)
async def dashboard_project_edit(
    request: Request, project_id: str,
    name: str = Form(...),
    description: str = Form(""),
    user: dict = Depends(require_perm("project.manage")),
):
    from agent.intake.project_registry import update_project
    try:
        update_project(project_id, name=name.strip(), description=description.strip())
    except Exception:
        pass
    return RedirectResponse("/dashboard/projects", status_code=303)


@router.post("/projects/{project_id}/delete", response_class=HTMLResponse)
async def dashboard_project_delete(
    request: Request, project_id: str,
    user: dict = Depends(require_perm("project.manage")),
):
    from agent.intake.project_registry import delete_project
    try:
        delete_project(project_id)
    except ValueError:
        pass
    return RedirectResponse("/dashboard/projects", status_code=303)


@router.get("/health", response_class=HTMLResponse)
async def dashboard_health(
    request: Request,
    user: dict = Depends(require_login),
):
    from agent.engine.resilience import investigation_limiter, llm_circuit_breaker
    from agent.intake.mcp_registry import list_servers

    limiter = investigation_limiter.status_dict()
    breaker = llm_circuit_breaker.status_dict()

    provider = os.getenv("LLM_PROVIDER", "anthropic")
    model = os.getenv("LLM_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022"))
    llm_key_set = bool(
        os.getenv("ANTHROPIC_API_KEY") or
        os.getenv("OPENAI_API_KEY") or
        os.getenv("GROQ_API_KEY")
    )

    mcp_servers_raw = []
    try:
        mcp_servers_raw = list_servers(project_id=None)
    except Exception:
        pass

    from agent.dashboard.queries import get_recurring_incidents
    recurring = get_recurring_incidents(project_id=None, threshold=2)

    return templates.TemplateResponse(request, "health.html", _ctx(request, user,
        active="health",
        limiter=limiter,
        breaker=breaker,
        provider=provider,
        model=model,
        llm_key_set=llm_key_set,
        mcp_servers=mcp_servers_raw,
        recurring_incidents=recurring,
    ))


@router.get("/metrics-live", response_class=HTMLResponse)
async def dashboard_metrics_live(
    request: Request,
    service: Optional[str] = None,
    user: dict = Depends(require_login),
):
    metrics = get_metrics_live(service=service)
    projects = get_projects_overview()
    all_services = sorted({m["service"] for m in metrics})

    return templates.TemplateResponse(request, "metrics_live.html", _ctx(request, user,
        active="metrics",
        metrics=metrics,
        selected_service=service or "",
        all_services=all_services,
        projects=projects,
    ))


@router.get("/channels", response_class=HTMLResponse)
async def dashboard_channels(
    request: Request,
    user: dict = Depends(require_login),
):
    channels = get_channel_config()
    projects = get_projects_overview()

    return templates.TemplateResponse(request, "channels.html", _ctx(request, user,
        active="channels",
        channel_rows=channels,
        projects=projects,
    ))


@router.post("/channels/{project_id}/{channel}/toggle", response_class=HTMLResponse)
async def dashboard_channel_toggle(
    request: Request, project_id: str, channel: str,
    user: dict = Depends(require_login),
):
    from agent.storage.db import open_db
    conn = open_db()
    existing = conn.execute(
        "SELECT enabled FROM project_alert_channels WHERE project_id=? AND channel=?",
        (project_id, channel),
    ).fetchone()
    if existing:
        new_val = 0 if existing["enabled"] else 1
        conn.execute(
            "UPDATE project_alert_channels SET enabled=? WHERE project_id=? AND channel=?",
            (new_val, project_id, channel),
        )
    else:
        conn.execute(
            "INSERT INTO project_alert_channels (project_id, channel, config, enabled) VALUES (?,?,?,1)",
            (project_id, channel, "{}"),
        )
    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard/channels", status_code=303)


# ── MCP Registry UI ───────────────────────────────────────────────────────────

@router.get("/mcp", response_class=HTMLResponse)
async def dashboard_mcp(
    request: Request,
    user: dict = Depends(require_login),
):
    servers = get_mcp_servers_for_dashboard()
    projects = _get_all_project_ids()
    return templates.TemplateResponse(request, "mcp.html", _ctx(request, user,
        active="mcp",
        servers=servers,
        projects=projects,
    ))


@router.post("/mcp/register", response_class=HTMLResponse)
async def dashboard_mcp_register(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    project_id: str = Form("default"),
    description: str = Form(""),
    user: dict = Depends(require_login),
):
    from agent.intake.mcp_registry import add_server
    error = None
    try:
        add_server(name=name, url=url, description=description, project_id=project_id)
    except ValueError as e:
        error = str(e)

    if error:
        servers = get_mcp_servers_for_dashboard()
        projects = _get_all_project_ids()
        return templates.TemplateResponse(request, "mcp.html", _ctx(request, user,
            active="mcp",
            servers=servers,
            projects=projects,
            register_error=error,
        ))
    return RedirectResponse("/dashboard/mcp", status_code=303)


@router.post("/mcp/{server_id}/delete", response_class=HTMLResponse)
async def dashboard_mcp_delete(
    request: Request, server_id: int,
    user: dict = Depends(require_login),
):
    from agent.intake.mcp_registry import remove_server
    remove_server(server_id)
    return RedirectResponse("/dashboard/mcp", status_code=303)


@router.post("/mcp/{server_id}/ping")
async def dashboard_mcp_ping(server_id: int):
    import aiohttp, time
    from agent.intake.mcp_registry import get_server_by_id

    srv = get_server_by_id(server_id)
    if not srv:
        return {"status": "error", "error": "Server not found"}

    url = srv["url"]
    t0 = time.monotonic()
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": "2024-11-05",
                                  "capabilities": {}, "clientInfo": {"name": "dashboard", "version": "1"}}}
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                await resp.json()
                latency_ms = round((time.monotonic() - t0) * 1000)

            tools_payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
            async with session.post(url, json=tools_payload, timeout=aiohttp.ClientTimeout(total=5)) as resp2:
                tools_data = await resp2.json()
                tools = [t.get("name") for t in (tools_data.get("result", {}).get("tools") or [])]

        return {"status": "ok", "latency_ms": latency_ms, "tools": tools, "tools_count": len(tools)}
    except Exception as e:
        latency_ms = round((time.monotonic() - t0) * 1000)
        return {"status": "error", "error": str(e), "latency_ms": latency_ms}


# ── LLM catalog (JSON) ────────────────────────────────────────────────────────

@router.get("/llm-catalog")
async def dashboard_llm_catalog(user: dict = Depends(require_login)):
    from agent.llm.catalog import get_provider_catalog
    return JSONResponse(get_provider_catalog())


# ── Project Detail UI ─────────────────────────────────────────────────────────

@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def dashboard_project_detail(
    request: Request, project_id: str,
    user: dict = Depends(require_login),
):
    from agent.llm.catalog import get_provider_catalog
    proj = get_project_detail(project_id)
    if not proj:
        return HTMLResponse("<h3>Project not found</h3>", status_code=404)
    return templates.TemplateResponse(request, "project_detail.html", _ctx(request, user,
        active="projects",
        proj=proj,
        llm_save_ok=False,
        llm_save_err="",
        llm_catalog=get_provider_catalog(),
    ))


@router.post("/projects/{project_id}/services/add", response_class=HTMLResponse)
async def dashboard_project_add_service(
    request: Request, project_id: str,
    service: str = Form(...),
    user: dict = Depends(require_login),
):
    from agent.intake.project_registry import add_project_service
    try:
        add_project_service(project_id, service.strip())
    except Exception:
        pass
    return RedirectResponse(f"/dashboard/projects/{project_id}", status_code=303)


@router.post("/projects/{project_id}/services/{service}/delete", response_class=HTMLResponse)
async def dashboard_project_del_service(
    request: Request, project_id: str, service: str,
    user: dict = Depends(require_login),
):
    from agent.intake.project_registry import remove_project_service
    try:
        remove_project_service(project_id, service)
    except Exception:
        pass
    return RedirectResponse(f"/dashboard/projects/{project_id}", status_code=303)


@router.post("/projects/{project_id}/llm", response_class=HTMLResponse)
async def dashboard_project_save_llm(
    request: Request, project_id: str,
    provider: str = Form(""),
    model: str = Form(""),
    model_custom: str = Form(""),
    base_url: str = Form(""),
    api_key: str = Form(""),
    headers_json: str = Form("{}"),
    clear: str = Form(""),
    user: dict = Depends(require_perm("llm.manage")),
):
    from agent.intake.project_registry import set_project_llm, clear_project_llm
    from agent.llm.catalog import get_provider_catalog
    llm_save_ok = False
    llm_save_err = ""
    if clear == "1":
        clear_project_llm(project_id)
        llm_save_ok = True
    else:
        try:
            extra = json.loads(headers_json) if headers_json.strip() else {}
        except json.JSONDecodeError:
            llm_save_err = "Extra Headers không phải JSON hợp lệ."
            extra = {}
        if not llm_save_err:
            cfg: dict = {}
            if base_url.strip():
                cfg["base_url"] = base_url.strip()
            if api_key.strip():
                cfg["api_key"] = api_key.strip()
            if extra:
                cfg["headers"] = extra
            # Resolve model: "_custom" → dùng model_custom free-text
            effective_model = (
                model_custom.strip() if model.strip() == "_custom" else model.strip()
            ) or None
            if not provider.strip():
                llm_save_err = "Provider không được để trống (vd: anthropic, groq, openai)."
            else:
                try:
                    set_project_llm(
                        project_id,
                        provider.strip(),
                        effective_model,
                        cfg,
                    )
                    llm_save_ok = True
                except ValueError as e:
                    llm_save_err = str(e)
    from agent.dashboard.queries import get_project_detail
    proj = get_project_detail(project_id)
    if not proj:
        return HTMLResponse("<h3>Project not found</h3>", status_code=404)
    return templates.TemplateResponse(request, "project_detail.html", _ctx(request, user,
        active="projects",
        proj=proj,
        llm_save_ok=llm_save_ok,
        llm_save_err=llm_save_err,
        llm_catalog=get_provider_catalog(),
    ))


@router.post("/projects/{project_id}/channels/{channel}/config", response_class=HTMLResponse)
async def dashboard_project_channel_config(
    request: Request, project_id: str, channel: str,
    config_json: str = Form("{}"),
    enabled: str = Form("0"),
    user: dict = Depends(require_login),
):
    from agent.intake.project_registry import set_project_channel
    try:
        set_project_channel(project_id, channel, json.loads(config_json), enabled == "1")
    except Exception:
        pass
    return RedirectResponse(f"/dashboard/projects/{project_id}", status_code=303)


@router.post("/projects/{project_id}/repos/add", response_class=HTMLResponse)
async def dashboard_project_add_repo(
    request: Request, project_id: str,
    service: str = Form(...),
    repo_url: str = Form(...),
    provider: str = Form("github"),
    default_branch: str = Form("main"),
    subpath: str = Form(""),
    user: dict = Depends(require_login),
):
    from agent.intake.project_registry import upsert_service_repo
    try:
        upsert_service_repo(
            project_id,
            service.strip(),
            repo_url.strip(),
            provider=provider.strip() or "github",
            default_branch=default_branch.strip() or "main",
            subpath=subpath.strip(),
        )
    except Exception:
        pass
    return RedirectResponse(f"/dashboard/projects/{project_id}", status_code=303)


@router.post("/projects/{project_id}/repos/{service}/delete", response_class=HTMLResponse)
async def dashboard_project_del_repo(
    request: Request, project_id: str, service: str,
    user: dict = Depends(require_login),
):
    from agent.intake.project_registry import delete_service_repo
    try:
        delete_service_repo(project_id, service)
    except Exception:
        pass
    return RedirectResponse(f"/dashboard/projects/{project_id}", status_code=303)


@router.post("/investigations/{investigation_id}/replay")
async def dashboard_investigation_replay(
    request: Request, investigation_id: str,
    user: dict = Depends(require_login),
):
    import aiohttp

    inv = get_investigation_detail(investigation_id)
    if not inv:
        return HTMLResponse("<h3>Investigation not found</h3>", status_code=404)

    project_id = inv.get("project_id", "default")
    raw = next((e for e in inv.get("raw_events", []) if e["event_type"] == "investigation_start"), None)
    if not raw:
        return HTMLResponse("<h3>Cannot replay: no start event</h3>", status_code=400)

    start_payload = raw["payload"]
    payload = {
        "service": start_payload.get("service", ""),
        "scenario": start_payload.get("scenario", ""),
        "time_window": start_payload.get("time_window", ""),
    }
    if start_payload.get("symptom"):
        payload["symptom"] = start_payload["symptom"]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://localhost:8000/projects/{project_id}/trigger",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                result = await resp.json()
        new_id = result.get("investigation_id", "")
        if new_id:
            return RedirectResponse(f"/dashboard/investigations/{new_id}", status_code=303)
    except Exception as e:
        return HTMLResponse(f"<h3>Replay failed: {e}</h3>", status_code=500)

    return RedirectResponse("/dashboard", status_code=303)


@router.get("/cost", response_class=HTMLResponse)
async def dashboard_cost(
    request: Request,
    user: dict = Depends(require_perm("observability.view")),
):
    data = get_cost_data()
    return templates.TemplateResponse(request, "cost.html", _ctx(request, user,
        active="cost",
        **data,
    ))


@router.post("/investigations/{investigation_id}/feedback", response_class=HTMLResponse)
async def investigation_feedback(
    request: Request,
    investigation_id: str,
    score: int = Form(...),
    user: dict = Depends(require_login),
):
    set_investigation_feedback(investigation_id, score)
    return RedirectResponse(f"/dashboard/investigations/{investigation_id}", status_code=303)


@router.get("/demo", response_class=HTMLResponse)
async def dashboard_demo(
    request: Request,
    user: dict = Depends(require_login),
):
    projects = get_projects_overview()
    quick_scenarios = [
        {"label": "payment-gateway timeout (14:00)", "service": "payment-gateway",
         "scenario": "scenario1", "time_window": "14:00-15:00", "domain": "microservice",
         "symptom": "payment-gateway: tỷ lệ lỗi tăng đột biến từ 14:05, 87% TimeoutException"},
        {"label": "provider sập (15:00)", "service": "payment-gateway",
         "scenario": "scenario2", "time_window": "15:00-16:00", "domain": "microservice",
         "symptom": "payment-gateway: ConnectionRefusedError 92%, latency bình thường"},
        {"label": "DB pool exhaustion (08:00)", "service": "payment-gateway",
         "scenario": "scenario3", "time_window": "08:00-09:00", "domain": "microservice",
         "symptom": "payment-gateway: AuthServiceTimeoutError 83% từ 08:11"},
        {"label": "traffic surge (10:00)", "service": "api-gateway",
         "scenario": "scenario4", "time_window": "10:00-11:00", "domain": "microservice",
         "symptom": "api-gateway: RateLimitError tăng đột biến, request_count tăng 5x"},
        {"label": "💳 processor timeout credit_card", "service": "proc-alpha",
         "scenario": "fintech1", "time_window": "10:00-11:00", "domain": "fintech",
         "symptom": "credit_card: 65% fail từ 10:15, ProcessorTimeoutError"},
        {"label": "💳 merchant price bug refund 8x", "service": "merch-buzz",
         "scenario": "fintech2", "time_window": "14:00-15:00", "domain": "fintech",
         "symptom": "merch-buzz: refund_rate 14.8% từ 14:00 (~8x baseline)"},
    ]
    return templates.TemplateResponse(request, "demo.html", _ctx(request, user,
        projects=projects,
        quick_scenarios=quick_scenarios,
    ))


@router.get("/tools", response_class=HTMLResponse)
async def dashboard_tools(
    request: Request,
    domain: Optional[str] = None,
    user: dict = Depends(require_login),
):
    all_tools = get_all_tools_for_dashboard()
    selected = domain or "microservice"
    return templates.TemplateResponse(request, "tools.html", _ctx(request, user,
        active="tools",
        all_tools=all_tools,
        selected_domain=selected,
    ))


@router.post("/tools/{tool_name}/run")
async def run_tool_testrun(
    tool_name: str,
    request: Request,
    user: dict = Depends(require_login),
):
    """Gọi thẳng tool.run(args) — không cần agent, không cần LLM."""
    import asyncio
    import inspect
    from dataclasses import asdict

    body = await request.json()
    args: Dict[str, Any] = body.get("args", {})
    domain: str = body.get("domain", "microservice")

    from agent.tools.registry import ALL_LOCAL_TOOLS
    from agent.tools.registry_fintech import ALL_FINTECH_TOOLS
    pool = ALL_LOCAL_TOOLS if domain != "fintech" else ALL_FINTECH_TOOLS

    tool = next((t for t in pool if t.name == tool_name), None)
    if not tool:
        return JSONResponse({"error": f"Tool '{tool_name}' không tìm thấy"}, status_code=404)

    try:
        if inspect.iscoroutinefunction(tool.run):
            obs = await tool.run(args)
        else:
            obs = await asyncio.get_running_loop().run_in_executor(None, tool.run, args)

        return JSONResponse({
            "summary": obs.summary,
            "aggregates": obs.aggregates,
            "samples": obs.samples,
            "total_count": obs.total_count,
            "truncated": obs.truncated,
            "metadata": obs.metadata,
            "trace_completeness": obs.trace_completeness,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/eval", response_class=HTMLResponse)
async def dashboard_eval(
    request: Request,
    user: dict = Depends(require_login),
):
    eval_rows = get_eval_summary()

    total_runs    = sum(r["n"]  for r in eval_rows)
    total_correct = sum(r["ok"] for r in eval_rows)
    overall_rate  = (total_correct * 100 // total_runs) if total_runs else 0

    eval_labels = [r["scenario"] for r in eval_rows]
    eval_rates  = [(r["ok"] * 100 // r["n"]) if r["n"] else 0 for r in eval_rows]
    eval_steps  = [round(r["avg_steps"], 1) for r in eval_rows]
    eval_recall = [round((r["recall"] or 0) * 100, 0) for r in eval_rows]

    eval_calibration = get_eval_calibration()
    calib_feedback = get_calibration_with_feedback()

    # E8: calibration adjustments — what engine would auto-adjust
    from agent.engine.calibration import load_calibration_stats, get_calibration_summary
    calib_stats = load_calibration_stats()
    calib_adjustments = get_calibration_summary(calib_stats)

    # E12: specificity stats từ trace_events
    specificity_data = get_specificity_data()

    # E13: A/B comparison with/without prior
    eval_comparison = get_eval_comparison_data()

    return templates.TemplateResponse(request, "eval.html", _ctx(request, user,
        active="eval",
        eval_rows=eval_rows,
        total_runs=total_runs,
        total_correct=total_correct,
        overall_rate=overall_rate,
        eval_labels=eval_labels,
        eval_rates=eval_rates,
        eval_steps=eval_steps,
        eval_recall=eval_recall,
        eval_calibration=eval_calibration,
        calib_feedback=calib_feedback,
        calib_adjustments=calib_adjustments,
        specificity_data=specificity_data,
        eval_comparison=eval_comparison,
    ))


# ── Admin: Users ──────────────────────────────────────────────────────────────

@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_get(
    request: Request,
    user: dict = Depends(require_perm("user.manage")),
):
    from agent.auth.rbac import list_users, list_roles, list_user_assignments
    users = list_users()
    roles = list_roles()
    # Enrich với assignments
    for u in users:
        u["assignments"] = list_user_assignments(u["id"])
    return templates.TemplateResponse(request, "admin_users.html", _ctx(request, user,
        active="admin",
        users=users,
        roles=roles,
    ))


@router.post("/admin/users", response_class=HTMLResponse)
async def admin_users_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    user: dict = Depends(require_perm("user.manage")),
):
    from agent.auth.rbac import create_user, list_users, list_roles, list_user_assignments
    error = None
    try:
        create_user(username.strip(), password)
    except ValueError as e:
        error = str(e)

    if error:
        users = list_users()
        roles = list_roles()
        for u in users:
            u["assignments"] = list_user_assignments(u["id"])
        return templates.TemplateResponse(request, "admin_users.html", _ctx(request, user,
            active="admin",
            users=users,
            roles=roles,
            create_error=error,
        ))
    return RedirectResponse("/dashboard/admin/users", status_code=303)


@router.post("/admin/users/{target_user_id}/toggle", response_class=HTMLResponse)
async def admin_user_toggle(
    request: Request, target_user_id: str,
    user: dict = Depends(require_perm("user.manage")),
):
    from agent.auth.rbac import get_user_by_id, update_user
    target = get_user_by_id(target_user_id)
    if target and not target["is_root"]:
        update_user(target_user_id, is_active=not bool(target["is_active"]))
    return RedirectResponse("/dashboard/admin/users", status_code=303)


@router.post("/admin/users/{target_user_id}/assign", response_class=HTMLResponse)
async def admin_user_assign(
    request: Request, target_user_id: str,
    role_id: str = Form(...),
    scope_type: str = Form("global"),
    scope_project_id: str = Form(""),
    user: dict = Depends(require_perm("role.manage")),
):
    from agent.auth.rbac import assign_role
    try:
        assign_role(
            target_user_id, role_id,
            scope_type=scope_type,
            scope_project_id=scope_project_id or None,
        )
    except Exception:
        pass
    return RedirectResponse("/dashboard/admin/users", status_code=303)


@router.post("/admin/assignments/{assignment_id}/remove", response_class=HTMLResponse)
async def admin_assignment_remove(
    request: Request, assignment_id: str,
    user: dict = Depends(require_perm("role.manage")),
):
    from agent.auth.rbac import remove_assignment
    remove_assignment(assignment_id)
    return RedirectResponse("/dashboard/admin/users", status_code=303)


# ── Admin: Roles ──────────────────────────────────────────────────────────────

@router.get("/admin/roles", response_class=HTMLResponse)
async def admin_roles_get(
    request: Request,
    user: dict = Depends(require_perm("role.manage")),
):
    from agent.auth.rbac import list_roles, get_role_permissions
    from agent.auth.permissions import PERMISSION_CATALOG, PERMISSION_GROUPS
    roles = list_roles()
    for r in roles:
        r["perms"] = set(get_role_permissions(r["id"]))
    return templates.TemplateResponse(request, "admin_roles.html", _ctx(request, user,
        active="admin",
        roles=roles,
        permission_catalog=PERMISSION_CATALOG,
        permission_groups=PERMISSION_GROUPS,
    ))


@router.post("/admin/roles", response_class=HTMLResponse)
async def admin_roles_post(
    request: Request,
    role_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    user: dict = Depends(require_perm("role.manage")),
):
    from agent.auth.rbac import create_role, list_roles, get_role_permissions
    from agent.auth.permissions import PERMISSION_CATALOG, PERMISSION_GROUPS
    error = None
    try:
        create_role(role_id.strip().lower(), name.strip(), description.strip())
    except ValueError as e:
        error = str(e)

    if error:
        roles = list_roles()
        for r in roles:
            r["perms"] = set(get_role_permissions(r["id"]))
        return templates.TemplateResponse(request, "admin_roles.html", _ctx(request, user,
            active="admin",
            roles=roles,
            permission_catalog=PERMISSION_CATALOG,
            permission_groups=PERMISSION_GROUPS,
            create_error=error,
        ))
    return RedirectResponse("/dashboard/admin/roles", status_code=303)


@router.post("/admin/roles/{role_id}/permissions", response_class=HTMLResponse)
async def admin_role_set_permissions(
    request: Request, role_id: str,
    user: dict = Depends(require_perm("role.manage")),
):
    from agent.auth.rbac import set_role_permissions
    from agent.auth.permissions import PERMISSION_CATALOG
    form = await request.form()
    # Checkboxes: key = permission key, value = "on"
    selected = [k for k in PERMISSION_CATALOG.keys() if form.get(k) == "on"]
    set_role_permissions(role_id, selected)
    return RedirectResponse("/dashboard/admin/roles", status_code=303)


@router.post("/admin/roles/{role_id}/delete", response_class=HTMLResponse)
async def admin_role_delete(
    request: Request, role_id: str,
    user: dict = Depends(require_perm("role.manage")),
):
    from agent.auth.rbac import delete_role
    try:
        delete_role(role_id)
    except ValueError:
        pass
    return RedirectResponse("/dashboard/admin/roles", status_code=303)


# ── Admin: Project Groups ─────────────────────────────────────────────────────

@router.get("/admin/groups", response_class=HTMLResponse)
async def admin_groups_get(
    request: Request,
    user: dict = Depends(require_perm("group.manage")),
):
    from agent.auth.rbac import list_groups, list_group_members
    from agent.intake.project_registry import list_projects
    groups = list_groups()
    for g in groups:
        g["members"] = list_group_members(g["id"])
    projects = list_projects()
    return templates.TemplateResponse(request, "admin_groups.html", _ctx(request, user,
        active="admin",
        groups=groups,
        projects=projects,
    ))


@router.post("/admin/groups", response_class=HTMLResponse)
async def admin_groups_post(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    user: dict = Depends(require_perm("group.manage")),
):
    from agent.auth.rbac import create_group
    try:
        create_group(name.strip(), description.strip())
    except ValueError:
        pass
    return RedirectResponse("/dashboard/admin/groups", status_code=303)


@router.post("/admin/groups/{group_id}/add-member", response_class=HTMLResponse)
async def admin_group_add_member(
    request: Request, group_id: str,
    project_id: str = Form(...),
    user: dict = Depends(require_perm("group.manage")),
):
    from agent.auth.rbac import add_group_member
    add_group_member(group_id, project_id)
    return RedirectResponse("/dashboard/admin/groups", status_code=303)


@router.post("/admin/groups/{group_id}/remove-member", response_class=HTMLResponse)
async def admin_group_remove_member(
    request: Request, group_id: str,
    project_id: str = Form(...),
    user: dict = Depends(require_perm("group.manage")),
):
    from agent.auth.rbac import remove_group_member
    remove_group_member(group_id, project_id)
    return RedirectResponse("/dashboard/admin/groups", status_code=303)


# ── A4: Admin API tokens ──────────────────────────────────────────────────────

@router.get("/admin/tokens")
async def admin_tokens_page(
    request: Request,
    user: dict = Depends(require_perm("user.manage")),
    new_token: str = "",
    new_token_name: str = "",
):
    from agent.auth.rbac import list_all_tokens, list_users
    tokens = list_all_tokens()
    users = list_users()
    return templates.TemplateResponse(request, "admin_tokens.html",
        _ctx(request, user,
             active="admin_tokens",
             tokens=tokens,
             users=users,
             new_token=new_token,
             new_token_name=new_token_name,
        ),
    )


@router.post("/admin/tokens")
async def admin_create_token(
    request: Request,
    user_id: str = Form(...),
    name: str = Form(""),
    user: dict = Depends(require_perm("user.manage")),
):
    from agent.auth.rbac import create_api_token
    result = create_api_token(user_id, name=name)
    return RedirectResponse(
        f"/dashboard/admin/tokens?new_token={result['token']}&new_token_name={result['name']}",
        status_code=303,
    )


@router.post("/admin/tokens/{token_id}/revoke")
async def admin_revoke_token(
    request: Request,
    token_id: str,
    user: dict = Depends(require_perm("user.manage")),
):
    from agent.auth.rbac import revoke_token
    revoke_token(token_id)
    return RedirectResponse("/dashboard/admin/tokens", status_code=303)


# ── Scheduled triggers (Ngày 32) ─────────────────────────────────────────────

@router.get("/scheduled", response_class=HTMLResponse)
async def scheduled_list(
    request: Request,
    project_id: Optional[str] = None,
    user: dict = Depends(require_login),
):
    from agent.intake.scheduler import list_triggers
    from agent.intake.project_registry import list_projects, list_project_services
    triggers = list_triggers(project_id=project_id or None)
    projects = [p["id"] for p in list_projects()]
    services_map = {p: list_project_services(p) for p in projects}
    return templates.TemplateResponse(request, "scheduled.html", _ctx(request, user,
        active="scheduled",
        triggers=triggers,
        projects=projects,
        services_map=services_map,
        filter_project=project_id or "",
    ))


@router.post("/scheduled", response_class=HTMLResponse)
async def scheduled_create(
    request: Request,
    project_id: str = Form("default"),
    service: str = Form(...),
    scenario: str = Form("scenario1"),
    interval_min: int = Form(60),
    user: dict = Depends(require_login),
):
    from agent.intake.scheduler import create_trigger
    try:
        create_trigger(project_id, service, scenario, max(5, interval_min))
    except Exception as e:
        pass  # DB error — bỏ qua, reload page
    return RedirectResponse("/dashboard/scheduled", status_code=303)


@router.post("/scheduled/{trigger_id}/toggle", response_class=HTMLResponse)
async def scheduled_toggle(
    request: Request,
    trigger_id: str,
    user: dict = Depends(require_login),
):
    from agent.intake.scheduler import toggle_trigger
    toggle_trigger(trigger_id)
    return RedirectResponse("/dashboard/scheduled", status_code=303)


@router.post("/scheduled/{trigger_id}/delete", response_class=HTMLResponse)
async def scheduled_delete(
    request: Request,
    trigger_id: str,
    user: dict = Depends(require_login),
):
    from agent.intake.scheduler import delete_trigger
    delete_trigger(trigger_id)
    return RedirectResponse("/dashboard/scheduled", status_code=303)


# ── Investigation export (Ngày 34) ──────────────────────────────────────────

@router.get("/investigations/{investigation_id}/export")
async def investigation_export(
    request: Request,
    investigation_id: str,
    format: str = "json",
    user: dict = Depends(require_login),
):
    """Export một investigation ra JSON hoặc CSV."""
    import csv
    import io

    from agent.dashboard.queries import get_investigation_detail

    detail = get_investigation_detail(investigation_id)
    if not detail:
        return JSONResponse({"error": "Not found"}, status_code=404)

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["investigation_id", "step", "timestamp", "event_type", "tool", "summary"])
        for ev in detail.get("raw_events", []):
            payload = ev.get("payload", {})
            tool = payload.get("tool", "")
            summary = payload.get("summary", payload.get("root_cause", ""))
            writer.writerow([
                investigation_id,
                ev.get("step", ""),
                ev.get("timestamp", ""),
                ev.get("event_type", ""),
                tool,
                summary,
            ])
        csv_bytes = output.getvalue().encode("utf-8")
        fname = f"investigation_{investigation_id}.csv"
        return StreamingResponse(
            iter([csv_bytes]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    # default: JSON
    fname = f"investigation_{investigation_id}.json"
    payload_bytes = json.dumps(detail, ensure_ascii=False, indent=2).encode("utf-8")
    return StreamingResponse(
        iter([payload_bytes]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ── OPS1: Catalog Editor ──────────────────────────────────────────────────────

@router.get("/catalog", response_class=HTMLResponse)
async def dashboard_catalog(
    request: Request,
    domain: Optional[str] = None,
    project_id: Optional[str] = None,
    user: dict = Depends(require_login),
):
    from agent.engine.hypothesis_catalog import list_catalog_entries_db, get_default_catalog
    db_entries = list_catalog_entries_db(domain=domain or None, project_id=project_id or None)
    # Show defaults in a separate read-only list
    default_catalog = get_default_catalog(domain or "microservice")
    return templates.TemplateResponse(request, "catalog.html", _ctx(request, user,
        active="catalog",
        db_entries=db_entries,
        default_catalog=default_catalog,
        filter_domain=domain or "microservice",
        filter_project=project_id or "default",
        projects=_get_all_project_ids(),
    ))


@router.post("/catalog/add", response_class=HTMLResponse)
async def dashboard_catalog_add(
    request: Request,
    domain: str = Form("microservice"),
    project_id: str = Form("default"),
    tag: str = Form(...),
    content: str = Form(""),
    keywords: str = Form(""),
    relevant_tools: str = Form(""),
    confirm_kws: str = Form(""),
    rule_out_kws: str = Form(""),
    confirm_conf: str = Form("medium"),
    root_cause_type: str = Form(""),
    user: dict = Depends(require_login),
):
    def _split(s: str):
        return [x.strip() for x in s.split(",") if x.strip()]

    from agent.engine.hypothesis_catalog import add_catalog_entry
    add_catalog_entry(
        domain=domain,
        project_id=project_id,
        tag=tag.strip(),
        content=content.strip(),
        keywords=_split(keywords),
        relevant_tools=_split(relevant_tools),
        confirm_kws=_split(confirm_kws),
        rule_out_kws=_split(rule_out_kws),
        confirm_conf=confirm_conf,
        root_cause_type=root_cause_type.strip(),
    )
    return RedirectResponse(
        f"/dashboard/catalog?domain={domain}&project_id={project_id}",
        status_code=303,
    )


@router.post("/catalog/{entry_id}/delete", response_class=HTMLResponse)
async def dashboard_catalog_delete(
    request: Request, entry_id: int,
    domain: str = Form("microservice"),
    project_id: str = Form("default"),
    user: dict = Depends(require_login),
):
    from agent.engine.hypothesis_catalog import delete_catalog_entry
    delete_catalog_entry(entry_id)
    return RedirectResponse(
        f"/dashboard/catalog?domain={domain}&project_id={project_id}",
        status_code=303,
    )
