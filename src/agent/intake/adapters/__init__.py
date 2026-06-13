"""
Intake adapter router.

route_adapter(source, payload) → Optional[InvestigationRequest]

source khớp với header X-Alert-Source (case-insensitive).
Không có header → caller dùng map_simple_payload trực tiếp.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from agent.intake.adapters.grafana import map_grafana
from agent.intake.adapters.prometheus import map_prometheus
from agent.intake.adapters.sentry import map_sentry
from agent.intake.normalizer import InvestigationRequest

_ADAPTERS: Dict[str, Callable[[Dict[str, Any]], Optional[InvestigationRequest]]] = {
    "prometheus": map_prometheus,
    "alertmanager": map_prometheus,   # alias phổ biến
    "grafana": map_grafana,
    "sentry": map_sentry,
}


def route_adapter(source: str, payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    """Chọn adapter theo source string, gọi, trả InvestigationRequest hoặc None."""
    adapter = _ADAPTERS.get(source.lower().strip())
    if adapter is None:
        return None
    return adapter(payload)


def list_sources() -> list:
    return sorted(_ADAPTERS.keys())
