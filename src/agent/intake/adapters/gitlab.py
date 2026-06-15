"""
Adapter: GitLab webhook → InvestigationRequest.

GitLab gửi POST với header X-Gitlab-Event.
Chỉ xử lý Push Hook và Pipeline Hook — các event khác trả None.

Header phân biệt event: X-Gitlab-Event

Payload Push Hook:
{
  "object_kind": "push",
  "ref": "refs/heads/main",
  "project": {"name": "payment-gateway", "path_with_namespace": "org/payment-gateway"},
  "commits": [{"message": "fix: ...", "timestamp": "2024-01-15T14:03:00+00:00"}]
}

Payload Pipeline Hook (object_kind: pipeline):
{
  "object_kind": "pipeline",
  "object_attributes": {
    "status": "failed",
    "ref": "main",
    "created_at": "2024-01-15 14:03:00 UTC"
  },
  "project": {"name": "payment-gateway"}
}
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agent.intake.adapters._shared import parse_alert_time
from agent.intake.normalizer import InvestigationRequest


def map_gitlab(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    """Parse GitLab webhook payload.

    _event_type được inject vào payload từ header X-Gitlab-Event bởi server.
    Nếu thiếu, dùng object_kind trong payload.
    """
    try:
        event_type = payload.pop("_event_type", "")
        kind = (
            event_type.lower().replace(" hook", "").strip()
            or payload.get("object_kind", "").lower()
        )

        if kind == "push":
            return _map_push(payload)
        elif kind == "pipeline":
            return _map_pipeline(payload)
        else:
            return None
    except Exception:
        return None


def _map_push(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    project = payload.get("project") or {}
    service = project.get("name") or (project.get("path_with_namespace", "") or "").split("/")[-1]
    if not service:
        return None

    # Chỉ quan tâm push lên nhánh chính
    ref = payload.get("ref", "")
    if ref and not any(b in ref for b in ("main", "master", "production", "prod", "release")):
        return None

    commits = payload.get("commits") or []
    last_commit = commits[0] if commits else {}
    timestamp = last_commit.get("timestamp") or payload.get("checkout_sha", "")
    time_window, date_str = parse_alert_time(timestamp)

    commit_msg = last_commit.get("message", "")
    author = (last_commit.get("author") or {}).get("name", "")
    symptom = (
        f"GitLab push to {ref} by {author}: {commit_msg[:120]}"
        if author
        else f"GitLab push to {ref}: {commit_msg[:120]}"
    )

    scenario = _infer_scenario_from_commit(commit_msg)

    return InvestigationRequest.from_raw(
        service=service,
        scenario=scenario,
        time_window=time_window,
        symptom=symptom,
        date=date_str,
        raw_payload=payload,
    )


def _map_pipeline(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    attrs = payload.get("object_attributes") or {}

    # Chỉ xử lý pipeline thất bại
    status = attrs.get("status", "")
    if status and status not in ("failed", ""):
        return None

    project = payload.get("project") or {}
    service = project.get("name") or ""
    if not service:
        return None

    timestamp = attrs.get("created_at") or attrs.get("finished_at", "")
    # GitLab dùng format "2024-01-15 14:03:00 UTC" — chuẩn hóa trước khi parse
    timestamp = timestamp.replace(" UTC", "Z").replace(" ", "T") if timestamp else ""
    time_window, date_str = parse_alert_time(timestamp)

    ref = attrs.get("ref", "")
    symptom = f"GitLab pipeline failed on {ref} for {service}" if ref else f"GitLab pipeline failed for {service}"

    return InvestigationRequest.from_raw(
        service=service,
        scenario="scenario1",  # pipeline failure thường do deploy bug
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
    return "scenario1"
