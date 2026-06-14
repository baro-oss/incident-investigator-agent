"""Dashboard APIRouter — mount vào server.py tại /dashboard.
Phase 5 Ngày 22: tất cả route đều require_login; admin routes guard thêm permission.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent.auth.deps import NotAuthorized, require_login, require_perm, get_current_user
from agent.dashboard.queries import (
    get_cost_data,
    get_eval_calibration,
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
    user: dict = Depends(require_login),
):
    invs = list_investigations(
        project_id=project_id or None,
        confidence=confidence or None,
        limit=100,
    )
    return templates.TemplateResponse("index.html", _ctx(request, user,
        active="home",
        investigations=invs,
        total=len(invs),
        projects=_get_all_project_ids(),
        filter_project=project_id or "",
        filter_confidence=confidence or "",
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
    return templates.TemplateResponse("detail.html", _ctx(request, user,
        active="home",
        inv=inv,
        langfuse_url=langfuse_url,
        feedback=feedback,
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

    return templates.TemplateResponse("chat.html", _ctx(request, user,
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

    return templates.TemplateResponse("trigger.html", _ctx(request, user,
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

    return templates.TemplateResponse("trigger.html", _ctx(request, user,
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
    return templates.TemplateResponse("projects.html", _ctx(request, user,
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
        return templates.TemplateResponse("projects.html", _ctx(request, user,
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

    return templates.TemplateResponse("health.html", _ctx(request, user,
        active="health",
        limiter=limiter,
        breaker=breaker,
        provider=provider,
        model=model,
        llm_key_set=llm_key_set,
        mcp_servers=mcp_servers_raw,
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

    return templates.TemplateResponse("metrics_live.html", _ctx(request, user,
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

    return templates.TemplateResponse("channels.html", _ctx(request, user,
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
    return templates.TemplateResponse("mcp.html", _ctx(request, user,
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
        return templates.TemplateResponse("mcp.html", _ctx(request, user,
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


# ── Project Detail UI ─────────────────────────────────────────────────────────

@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def dashboard_project_detail(
    request: Request, project_id: str,
    user: dict = Depends(require_login),
):
    proj = get_project_detail(project_id)
    if not proj:
        return HTMLResponse("<h3>Project not found</h3>", status_code=404)
    return templates.TemplateResponse("project_detail.html", _ctx(request, user,
        active="projects",
        proj=proj,
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
    return templates.TemplateResponse("cost.html", _ctx(request, user,
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
    return templates.TemplateResponse("demo.html", _ctx(request, user,
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
    return templates.TemplateResponse("tools.html", _ctx(request, user,
        active="tools",
        all_tools=all_tools,
        selected_domain=selected,
    ))


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

    return templates.TemplateResponse("eval.html", _ctx(request, user,
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
    return templates.TemplateResponse("admin_users.html", _ctx(request, user,
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
        return templates.TemplateResponse("admin_users.html", _ctx(request, user,
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
    return templates.TemplateResponse("admin_roles.html", _ctx(request, user,
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
        return templates.TemplateResponse("admin_roles.html", _ctx(request, user,
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
    return templates.TemplateResponse("admin_groups.html", _ctx(request, user,
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
