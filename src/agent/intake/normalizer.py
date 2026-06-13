"""
Intake normalizer — chuẩn hóa payload alert đa dạng → InvestigationRequest thống nhất.

Engine chỉ thấy InvestigationRequest. Thêm nguồn alert = thêm mapper, không đụng engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class InvestigationRequest:
    """Alert đã chuẩn hóa — đây là thứ engine nhận vào."""
    symptom: str
    service: str
    time_window: str
    scenario: str          # "scenario1" | "scenario2"
    date: str
    raw_payload: Dict[str, Any]  # payload gốc — giữ để trace/debug
    dedup_key: str         # project + service + scenario + time_window → dedup
    project_id: str = "default"

    @classmethod
    def from_raw(
        cls,
        service: str,
        scenario: str,
        time_window: str,
        symptom: Optional[str] = None,
        date: str = "2024-01-15",
        raw_payload: Optional[Dict] = None,
        project_id: str = "default",
    ) -> "InvestigationRequest":
        auto_symptom = symptom or _auto_symptom(service, scenario)
        return cls(
            symptom=auto_symptom,
            service=service,
            time_window=time_window,
            scenario=scenario,
            date=date,
            raw_payload=raw_payload or {},
            dedup_key=f"{project_id}|{service}|{scenario}|{time_window}",
            project_id=project_id,
        )


def _auto_symptom(service: str, scenario: str) -> str:
    """Sinh symptom mô tả tự động nếu caller không cung cấp."""
    templates = {
        "scenario1": (
            f"{service}: tỷ lệ lỗi tăng đột biến, TimeoutException chiếm ưu thế, "
            "latency p99 vượt baseline nhiều lần"
        ),
        "scenario2": (
            f"{service}: ConnectionRefusedError tăng đột biến, "
            "nghi lỗi lan từ downstream service"
        ),
    }
    return templates.get(scenario, f"{service}: lỗi bất thường cần điều tra")


# ── Mapper ví dụ — Prometheus AlertManager format ─────────────────────────────

def map_alertmanager_payload(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    """
    Ví dụ mapper: nhận payload kiểu Prometheus AlertManager, chuẩn hóa.
    Thêm nguồn khác = thêm hàm map_X, không sửa phần còn lại.
    """
    try:
        alerts = payload.get("alerts", [payload])
        alert = alerts[0] if alerts else {}
        labels = alert.get("labels", {})

        service = labels.get("service") or labels.get("job", "unknown-service")
        scenario = labels.get("scenario", "scenario1")
        time_window = labels.get("time_window", "14:00-15:00")
        symptom = alert.get("annotations", {}).get("summary")

        return InvestigationRequest.from_raw(
            service=service,
            scenario=scenario,
            time_window=time_window,
            symptom=symptom,
            raw_payload=payload,
        )
    except Exception:
        return None


def map_simple_payload(payload: Dict[str, Any]) -> Optional[InvestigationRequest]:
    """
    Mapper đơn giản nhất — payload có service, scenario, time_window là đủ.
    Dùng cho trigger thủ công và script demo.
    """
    service = payload.get("service", "payment-gateway")
    scenario = payload.get("scenario", "scenario1")
    time_window = payload.get("time_window", "14:00-15:00")
    symptom = payload.get("symptom")
    date = payload.get("date", "2024-01-15")

    return InvestigationRequest.from_raw(
        service=service,
        scenario=scenario,
        time_window=time_window,
        symptom=symptom,
        date=date,
        raw_payload=payload,
    )
