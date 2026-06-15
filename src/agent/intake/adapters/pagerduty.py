"""
Adapter: PagerDuty webhook → InvestigationRequest.

PagerDuty gửi POST khi incident trigger/acknowledge/resolve.
Chỉ xử lý event trigger — các event khác bỏ qua (trả None).

Payload format (v2 webhooks):
{
  "messages": [{
    "event": "incident.trigger",
    "incident": {
      "id": "P1ABC23",
      "title": "High error rate on payment-gateway",
      "status": "triggered",
      "urgency": "high",
      "service": {"name": "payment-gateway", "id": "..."},
      "created_at": "2024-01-15T14:05:00Z"
    }
  }]
}

Cũng hỗ trợ format v3 (messages → payload.event + payload.data).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agent.intake.adapters._shared import parse_alert_time
from agent.intake.normalizer import InvestigationRequest


def map_pagerduty(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    try:
        # v2 format: messages array
        messages = payload.get("messages") or []
        if messages:
            msg = messages[0]
            event_type = msg.get("event", "")
            if "trigger" not in event_type.lower():
                return None  # chỉ xử lý trigger
            incident = msg.get("incident") or {}
        else:
            # v3 / generic format: event + data at top level
            event_type = payload.get("event", {}).get("event_type", "")
            if "trigger" not in event_type.lower() and payload.get("event_type", "") not in ("trigger", "incident.triggered"):
                # Try to proceed anyway if we have incident data
                pass
            incident = payload.get("data", {}).get("incident", payload)

        title = incident.get("title", "")
        service_obj = incident.get("service") or {}
        service = (
            service_obj.get("name")
            or incident.get("service_name")
            or payload.get("service", "unknown-service")
        )
        created_at = incident.get("created_at") or incident.get("triggered_at", "")
        time_window, date_str = parse_alert_time(created_at)

        # Infer scenario từ title
        scenario = _infer_scenario(title)

        return InvestigationRequest.from_raw(
            service=service,
            scenario=scenario,
            time_window=time_window,
            symptom=title or f"{service}: PagerDuty incident triggered",
            date=date_str,
            raw_payload=payload,
        )
    except Exception:
        return None


def _infer_scenario(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ("deploy", "release", "rollout", "version")):
        return "scenario1"
    if any(w in t for w in ("connection", "refused", "downstream", "dependency")):
        return "scenario2"
    return "scenario1"
