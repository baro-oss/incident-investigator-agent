"""
Adapter: Prometheus AlertManager webhook payload → InvestigationRequest.

AlertManager POST body:
{
  "receiver": "...",
  "status": "firing",
  "alerts": [{
    "labels":      {"service": "...", "scenario": "...", "severity": "critical"},
    "annotations": {"summary": "..."},
    "startsAt":    "2024-01-15T14:05:00Z"
  }]
}
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agent.intake.adapters._shared import parse_alert_time
from agent.intake.normalizer import InvestigationRequest


def map_prometheus(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    try:
        alerts = payload.get("alerts") or [payload]
        alert = alerts[0]
        labels = alert.get("labels") or payload.get("commonLabels") or {}
        annotations = alert.get("annotations") or payload.get("commonAnnotations") or {}

        service = (
            labels.get("service")
            or labels.get("job")
            or payload.get("commonLabels", {}).get("service", "unknown-service")
        )
        scenario = labels.get("scenario", "scenario1")
        symptom = annotations.get("summary") or annotations.get("description")

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
