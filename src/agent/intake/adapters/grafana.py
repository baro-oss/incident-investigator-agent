"""
Adapter: Grafana Unified Alerting webhook payload → InvestigationRequest.

Grafana POST body (unified alerting):
{
  "status": "firing",
  "orgId": 1,
  "alerts": [{
    "labels":      {"service": "...", "scenario": "...", "alertname": "..."},
    "annotations": {"summary": "..."},
    "startsAt":    "2024-01-15T14:05:00Z",
    "values":      {"B0": 1234.5}
  }],
  "title":   "[FIRING:1] HighLatency",
  "message": "..."
}

Khác Prometheus: có `title`/`message` top-level; `values` chứa metric tại thời điểm alert.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agent.intake.adapters._shared import parse_alert_time
from agent.intake.normalizer import InvestigationRequest


def map_grafana(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    try:
        alerts = payload.get("alerts") or [payload]
        alert = alerts[0]
        labels = alert.get("labels") or {}
        annotations = alert.get("annotations") or {}

        service = (
            labels.get("service")
            or labels.get("job")
            or payload.get("commonLabels", {}).get("service", "unknown-service")
        )
        scenario = labels.get("scenario", "scenario1")

        # Grafana đặt summary tốt hơn ở top-level message nếu annotations rỗng
        symptom = (
            annotations.get("summary")
            or annotations.get("description")
            or payload.get("message")
            or payload.get("title")
        )

        starts_at = alert.get("startsAt", "")
        time_window, date_str = parse_alert_time(starts_at)

        return InvestigationRequest.from_raw(
            service=service,
            scenario=scenario,
            time_window=time_window,
            symptom=symptom,
            date=date_str,
            raw_payload=payload,
        )
    except Exception:
        return None
