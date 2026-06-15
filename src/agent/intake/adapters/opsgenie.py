"""
Adapter: OpsGenie webhook → InvestigationRequest.

OpsGenie gửi POST khi alert được tạo/đóng/acknowledge.
Chỉ xử lý action Create (alert mới) — các action khác trả None.

Payload format:
{
  "action": "Create",
  "alert": {
    "alertId":   "abc123",
    "message":   "High error rate on payment-gateway",
    "alias":     "payment-gateway-high-error",
    "source":    "payment-gateway",
    "tags":      ["critical", "scenario1"],
    "details":   {"service": "payment-gateway", "scenario": "scenario1"},
    "createdAt": 1705327500000  (milliseconds epoch)
  },
  "source": {"name": "payment-gateway"}
}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agent.intake.adapters._shared import parse_alert_time
from agent.intake.normalizer import InvestigationRequest


def map_opsgenie(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    try:
        action = payload.get("action", "")
        if action.lower() not in ("create", ""):
            return None  # chỉ xử lý alert mới

        alert = payload.get("alert") or {}
        details = alert.get("details") or {}

        message = alert.get("message", "")
        service = (
            details.get("service")
            or alert.get("source")
            or (payload.get("source") or {}).get("name")
            or "unknown-service"
        )

        # Scenario từ details hoặc tags
        tags = alert.get("tags") or []
        scenario = (
            details.get("scenario")
            or next((t for t in tags if t.startswith("scenario")), None)
            or _infer_scenario(message)
        )

        # Timestamp: createdAt là milliseconds epoch
        created_ms = alert.get("createdAt")
        if created_ms:
            dt = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            created_at = dt.isoformat()
        else:
            created_at = ""
        time_window, date_str = parse_alert_time(created_at)

        return InvestigationRequest.from_raw(
            service=service,
            scenario=scenario,
            time_window=time_window,
            symptom=message or f"{service}: OpsGenie alert created",
            date=date_str,
            raw_payload=payload,
        )
    except Exception:
        return None


def _infer_scenario(message: str) -> str:
    m = message.lower()
    if any(w in m for w in ("deploy", "release", "rollout")):
        return "scenario1"
    if any(w in m for w in ("connection", "refused", "downstream")):
        return "scenario2"
    return "scenario1"
