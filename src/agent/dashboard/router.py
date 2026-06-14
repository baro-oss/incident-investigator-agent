"""Dashboard APIRouter — mount vào server.py tại /dashboard."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent.dashboard.queries import (
    get_eval_summary,
    get_investigation_detail,
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


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    project_id: Optional[str] = None,
    confidence: Optional[str] = None,
):
    invs = list_investigations(
        project_id=project_id or None,
        confidence=confidence or None,
        limit=100,
    )
    return templates.TemplateResponse("index.html", {
        "request": request,
        "active": "home",
        "investigations": invs,
        "total": len(invs),
        "projects": _get_all_project_ids(),
        "filter_project": project_id or "",
        "filter_confidence": confidence or "",
    })


@router.get("/investigations/{investigation_id}", response_class=HTMLResponse)
async def dashboard_detail(request: Request, investigation_id: str):
    inv = get_investigation_detail(investigation_id)
    if not inv:
        return HTMLResponse("<h3>Investigation not found</h3>", status_code=404)

    langfuse_url = None
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
        langfuse_url = f"{host}/traces"

    return templates.TemplateResponse("detail.html", {
        "request": request,
        "active": "home",
        "inv": inv,
        "langfuse_url": langfuse_url,
    })


@router.get("/stream/{investigation_id}")
async def dashboard_stream(investigation_id: str):
    """SSE endpoint — stream trace events của investigation đang chạy."""
    from agent.dashboard.sse import stream as sse_stream

    async def event_generator():
        async for chunk in sse_stream(investigation_id):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tắt nginx buffer nếu có
            "Connection": "keep-alive",
        },
    )


@router.get("/chat", response_class=HTMLResponse)
async def dashboard_chat(request: Request):
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

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "active": "chat",
        "projects": projects,
        "quick_scenarios": quick_scenarios,
    })


@router.get("/trigger", response_class=HTMLResponse)
async def dashboard_trigger_get(
    request: Request,
    scenario: Optional[str] = None,
    project_id: Optional[str] = None,
):
    projects = get_projects_overview()
    svc_map = _get_project_services_map()

    first_pid = (project_id or (projects[0]["id"] if projects else "default"))
    services = svc_map.get(first_pid, [])
    recent = list_investigations(limit=5)

    return templates.TemplateResponse("trigger.html", {
        "request": request,
        "active": "trigger",
        "projects": projects,
        "services": services,
        "selected_project": first_pid,
        "selected_service": services[0] if services else "",
        "selected_scenario": scenario or "scenario1",
        "project_services_json": json.dumps(svc_map),
        "recent": recent[:5],
        "result": None,
    })


@router.post("/trigger", response_class=HTMLResponse)
async def dashboard_trigger_post(
    request: Request,
    project_id: str = Form(...),
    service: str = Form(...),
    scenario: str = Form(...),
    time_window: str = Form(...),
    symptom: str = Form(""),
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

    return templates.TemplateResponse("trigger.html", {
        "request": request,
        "active": "trigger",
        "projects": projects,
        "services": services,
        "selected_project": project_id,
        "selected_service": service,
        "selected_scenario": scenario,
        "project_services_json": json.dumps(svc_map),
        "recent": recent[:5],
        "result": result,
    })


@router.get("/projects", response_class=HTMLResponse)
async def dashboard_projects(request: Request):
    projects = get_projects_overview()
    return templates.TemplateResponse("projects.html", {
        "request": request,
        "active": "projects",
        "projects": projects,
    })


@router.get("/health", response_class=HTMLResponse)
async def dashboard_health(request: Request):
    """Trang sức khoẻ hệ thống: LLM, limiter, circuit breaker, MCP."""
    import os
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

    return templates.TemplateResponse("health.html", {
        "request": request,
        "active": "health",
        "limiter": limiter,
        "breaker": breaker,
        "provider": provider,
        "model": model,
        "llm_key_set": llm_key_set,
        "mcp_servers": mcp_servers_raw,
    })


@router.get("/metrics-live", response_class=HTMLResponse)
async def dashboard_metrics_live(request: Request, service: Optional[str] = None):
    """Live metrics panel — baseline vs current per service."""
    metrics = get_metrics_live(service=service)
    projects = get_projects_overview()
    all_services = sorted({m["service"] for m in metrics})

    return templates.TemplateResponse("metrics_live.html", {
        "request": request,
        "active": "metrics",
        "metrics": metrics,
        "selected_service": service or "",
        "all_services": all_services,
        "projects": projects,
    })


@router.get("/channels", response_class=HTMLResponse)
async def dashboard_channels(request: Request):
    """Alert channel config per project."""
    channels = get_channel_config()
    projects = get_projects_overview()

    return templates.TemplateResponse("channels.html", {
        "request": request,
        "active": "channels",
        "channel_rows": channels,
        "projects": projects,
    })


@router.post("/channels/{project_id}/{channel}/toggle", response_class=HTMLResponse)
async def dashboard_channel_toggle(request: Request, project_id: str, channel: str):
    """Toggle enable/disable một kênh alert."""
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
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/dashboard/channels", status_code=303)


# ── MCP Registry UI ───────────────────────────────────────────────────────────

@router.get("/mcp", response_class=HTMLResponse)
async def dashboard_mcp(request: Request):
    servers = get_mcp_servers_for_dashboard()
    projects = _get_all_project_ids()
    return templates.TemplateResponse("mcp.html", {
        "request": request,
        "active": "mcp",
        "servers": servers,
        "projects": projects,
    })


@router.post("/mcp/register", response_class=HTMLResponse)
async def dashboard_mcp_register(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    project_id: str = Form("default"),
    description: str = Form(""),
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
        return templates.TemplateResponse("mcp.html", {
            "request": request,
            "active": "mcp",
            "servers": servers,
            "projects": projects,
            "register_error": error,
        })
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/dashboard/mcp", status_code=303)


@router.post("/mcp/{server_id}/delete", response_class=HTMLResponse)
async def dashboard_mcp_delete(request: Request, server_id: int):
    from agent.intake.mcp_registry import remove_server
    remove_server(server_id)
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/dashboard/mcp", status_code=303)


@router.post("/mcp/{server_id}/ping")
async def dashboard_mcp_ping(server_id: int):
    """Ping một MCP server — trả JSON kết quả để JS hiển thị."""
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
                data = await resp.json()
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
async def dashboard_project_detail(request: Request, project_id: str):
    proj = get_project_detail(project_id)
    if not proj:
        return HTMLResponse("<h3>Project not found</h3>", status_code=404)
    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "active": "projects",
        "proj": proj,
    })


@router.post("/projects/{project_id}/services/add", response_class=HTMLResponse)
async def dashboard_project_add_service(request: Request, project_id: str, service: str = Form(...)):
    from agent.intake.project_registry import add_project_service
    try:
        add_project_service(project_id, service.strip())
    except Exception:
        pass
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/dashboard/projects/{project_id}", status_code=303)


@router.post("/projects/{project_id}/services/{service}/delete", response_class=HTMLResponse)
async def dashboard_project_del_service(request: Request, project_id: str, service: str):
    from agent.intake.project_registry import remove_project_service
    try:
        remove_project_service(project_id, service)
    except Exception:
        pass
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/dashboard/projects/{project_id}", status_code=303)


@router.post("/projects/{project_id}/channels/{channel}/config", response_class=HTMLResponse)
async def dashboard_project_channel_config(
    request: Request, project_id: str, channel: str,
    config_json: str = Form("{}"),
    enabled: str = Form("0"),
):
    from agent.intake.project_registry import set_project_channel
    try:
        set_project_channel(project_id, channel, json.loads(config_json), enabled == "1")
    except Exception:
        pass
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/dashboard/projects/{project_id}", status_code=303)


# ── Investigation Replay ───────────────────────────────────────────────────────

@router.post("/investigations/{investigation_id}/replay")
async def dashboard_investigation_replay(request: Request, investigation_id: str):
    """Chạy lại investigation gốc — trigger mới, redirect sang detail."""
    import aiohttp
    from fastapi.responses import RedirectResponse

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


# ── Demo Mode ─────────────────────────────────────────────────────────────────

@router.get("/demo", response_class=HTMLResponse)
async def dashboard_demo(request: Request):
    """Full-screen demo view — ẩn nav, chỉ hiện trigger + SSE stream + verdict."""
    projects = get_projects_overview()
    quick_scenarios = [
        {"label": "payment-gateway timeout (14:00)", "service": "payment-gateway",
         "scenario": "scenario1", "time_window": "14:00-15:00",
         "symptom": "payment-gateway: tỷ lệ lỗi tăng đột biến từ 14:05, 87% TimeoutException"},
        {"label": "provider sập (15:00)", "service": "payment-gateway",
         "scenario": "scenario2", "time_window": "15:00-16:00",
         "symptom": "payment-gateway: ConnectionRefusedError 92%, latency bình thường"},
        {"label": "DB pool exhaustion (08:00)", "service": "payment-gateway",
         "scenario": "scenario3", "time_window": "08:00-09:00",
         "symptom": "payment-gateway: AuthServiceTimeoutError 83% từ 08:11"},
        {"label": "traffic surge (10:00)", "service": "api-gateway",
         "scenario": "scenario4", "time_window": "10:00-11:00",
         "symptom": "api-gateway: RateLimitError tăng đột biến, request_count tăng 5x"},
    ]
    return templates.TemplateResponse("demo.html", {
        "request": request,
        "projects": projects,
        "quick_scenarios": quick_scenarios,
    })


@router.get("/tools", response_class=HTMLResponse)
async def dashboard_tools(request: Request, domain: Optional[str] = None):
    """Tool Registry Viewer — danh sách tools theo domain."""
    all_tools = get_all_tools_for_dashboard()
    selected = domain or "microservice"
    return templates.TemplateResponse("tools.html", {
        "request": request,
        "active": "tools",
        "all_tools": all_tools,
        "selected_domain": selected,
    })


@router.get("/eval", response_class=HTMLResponse)
async def dashboard_eval(request: Request):
    eval_rows = get_eval_summary()

    total_runs    = sum(r["n"]  for r in eval_rows)
    total_correct = sum(r["ok"] for r in eval_rows)
    overall_rate  = (total_correct * 100 // total_runs) if total_runs else 0

    # Dữ liệu cho Chart.js
    eval_labels = [r["scenario"] for r in eval_rows]
    eval_rates  = [(r["ok"] * 100 // r["n"]) if r["n"] else 0 for r in eval_rows]
    eval_steps  = [round(r["avg_steps"], 1) for r in eval_rows]
    eval_recall = [round((r["recall"] or 0) * 100, 0) for r in eval_rows]

    return templates.TemplateResponse("eval.html", {
        "request": request,
        "active": "eval",
        "eval_rows": eval_rows,
        "total_runs": total_runs,
        "total_correct": total_correct,
        "overall_rate": overall_rate,
        "eval_labels": eval_labels,
        "eval_rates": eval_rates,
        "eval_steps": eval_steps,
        "eval_recall": eval_recall,
    })
