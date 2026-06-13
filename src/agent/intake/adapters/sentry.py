"""
Adapter: Sentry Issue webhook payload → InvestigationRequest.

Sentry POST body:
{
  "action": "created",
  "data": {
    "issue": {
      "title":     "TimeoutException: ...",
      "firstSeen": "2024-01-15T14:05:00Z",
      "lastSeen":  "2024-01-15T14:55:00Z",
      "project":   {"slug": "payment-gateway", "name": "payment-gateway"},
      "metadata":  {"type": "TimeoutException", "value": "..."},
      "tags":      [{"key": "scenario", "value": "scenario1"}]
    }
  }
}

Khác Prometheus/Grafana: service = project slug; scenario từ tags list; time từ firstSeen.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agent.intake.adapters._shared import parse_alert_time
from agent.intake.normalizer import InvestigationRequest


def map_sentry(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    try:
        issue = payload.get("data", {}).get("issue", {})

        project = issue.get("project", {})
        service = project.get("slug") or project.get("name", "unknown-service")

        # Tìm scenario trong tags list
        scenario = "scenario1"
        for tag in issue.get("tags", []):
            if tag.get("key") == "scenario":
                scenario = tag["value"]
                break

        symptom = issue.get("title")
        # Nếu title thiếu context thì thêm error type từ metadata
        metadata = issue.get("metadata", {})
        if not symptom and metadata:
            symptom = f"{metadata.get('type', 'Error')}: {metadata.get('value', '')}"

        first_seen = issue.get("firstSeen", "")
        time_window, date_str = parse_alert_time(first_seen)

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
