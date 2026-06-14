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
