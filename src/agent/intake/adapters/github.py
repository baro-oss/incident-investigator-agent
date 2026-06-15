"""
Adapter: GitHub webhook → InvestigationRequest.

GitHub gửi POST khi có push / deployment / deployment_status event.
Chỉ xử lý push và deployment — các event khác trả None.

Header phân biệt event: X-GitHub-Event

Payload push:
{
  "ref": "refs/heads/main",
  "repository": {"name": "payment-gateway", "full_name": "org/payment-gateway"},
  "head_commit": {"message": "fix: ...", "timestamp": "2024-01-15T14:03:00Z"},
  "pusher": {"name": "alice"}
}

Payload deployment:
{
  "action": "created",
  "deployment": {"environment": "production", "created_at": "2024-01-15T14:03:00Z"},
  "repository": {"name": "payment-gateway"}
}
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agent.intake.adapters._shared import parse_alert_time
from agent.intake.normalizer import InvestigationRequest


def map_github(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    """Parse GitHub webhook payload.

    _event_type được inject vào payload từ header X-GitHub-Event bởi server.
    Nếu thiếu, tự infer từ cấu trúc payload.
    """
    try:
        event_type = payload.pop("_event_type", "")

        # Infer event nếu không có header
        if not event_type:
            if "deployment" in payload and "action" in payload:
                event_type = "deployment"
            elif "ref" in payload and "head_commit" in payload:
                event_type = "push"
            else:
                return None

        event_type = event_type.lower()

        if event_type == "push":
            return _map_push(payload)
        elif event_type in ("deployment", "deployment_status"):
            return _map_deployment(payload)
        else:
            return None
    except Exception:
        return None


def _map_push(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    repo = payload.get("repository") or {}
    service = repo.get("name") or payload.get("repository", {}).get("full_name", "").split("/")[-1]
    if not service:
        return None

    # Chỉ quan tâm push lên nhánh chính
    ref = payload.get("ref", "")
    if ref and not any(b in ref for b in ("main", "master", "production", "prod", "release")):
        return None

    head_commit = payload.get("head_commit") or {}
    timestamp = head_commit.get("timestamp") or payload.get("created_at", "")
    time_window, date_str = parse_alert_time(timestamp)

    commit_msg = head_commit.get("message", "")
    pusher = (payload.get("pusher") or {}).get("name", "")
    symptom = f"GitHub push to {ref} by {pusher}: {commit_msg[:120]}" if pusher else f"GitHub push to {ref}: {commit_msg[:120]}"

    scenario = _infer_scenario_from_commit(commit_msg)

    return InvestigationRequest.from_raw(
        service=service,
        scenario=scenario,
        time_window=time_window,
        symptom=symptom,
        date=date_str,
        raw_payload=payload,
    )


def _map_deployment(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    action = payload.get("action", "")
    # Chỉ xử lý khi deployment mới được tạo
    if action and action not in ("created", ""):
        return None

    repo = payload.get("repository") or {}
    service = repo.get("name") or ""
    if not service:
        return None

    deployment = payload.get("deployment") or {}
    timestamp = deployment.get("created_at") or deployment.get("updated_at", "")
    time_window, date_str = parse_alert_time(timestamp)

    environment = deployment.get("environment", "production")
    description = deployment.get("description", "") or deployment.get("ref", "")
    symptom = f"GitHub deployment to {environment}: {description[:120]}" if description else f"GitHub deployment to {environment}"

    return InvestigationRequest.from_raw(
        service=service,
        scenario="scenario1",  # deploy_bug là kịch bản mặc định cho deployment event
        time_window=time_window,
        symptom=symptom,
        date=date_str,
        raw_payload=payload,
    )


def _infer_scenario_from_commit(msg: str) -> str:
    m = msg.lower()
    if any(w in m for w in ("fix", "hotfix", "patch", "bug", "revert")):
        return "scenario1"
    if any(w in m for w in ("connection", "timeout", "pool", "db", "database")):
        return "scenario3"
    if any(w in m for w in ("traffic", "scale", "rate", "limit")):
        return "scenario4"
    return "scenario1"
