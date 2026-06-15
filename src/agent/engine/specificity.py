"""
E12: Verdict specificity metric — đo độ cụ thể của verdict.

3 tín hiệu deterministic, không keyword miền:
  (a) root_cause có số/version/timestamp/service-name
  (b) evidence_summary có ≥2 số phân biệt
  (c) propagation_note không rỗng + có service/số

Score = sum(signals) / 3, range [0.0, 1.0].
Gate fires khi score < SPECIFICITY_THRESHOLD và conf in {high, medium}.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from agent.engine.state import InvestigationState, Verdict

SPECIFICITY_THRESHOLD = 0.40


def compute_verdict_specificity(
    verdict: "Verdict",
    state: "InvestigationState",
) -> Tuple[float, List[str]]:
    """Tính [0.0, 1.0] + list lý do mờ (rỗng khi đủ cụ thể)."""
    reasons: List[str] = []
    passed = 0

    root = verdict.root_cause or ""
    if _has_specific_token(root, state.available_services):
        passed += 1
    else:
        reasons.append("root_cause thiếu số/version/timestamp/service-name cụ thể")

    ev_summary = verdict.evidence_summary or ""
    if _count_distinct_numbers(ev_summary) >= 2:
        passed += 1
    else:
        reasons.append("evidence_summary thiếu ≥2 số đo cụ thể")

    prop = verdict.propagation_note or ""
    if prop.strip() and (
        _has_specific_token(prop, state.available_services)
        or bool(re.search(r"\d", prop))
    ):
        passed += 1
    else:
        reasons.append("propagation_note trống hoặc không nêu service/số liệu")

    return passed / 3, reasons


def _has_specific_token(text: str, services: list) -> bool:
    """True nếu text chứa số hoặc tên service."""
    if re.search(r"\d", text):
        return True
    if services:
        text_lower = text.lower()
        if any(s.lower() in text_lower for s in services):
            return True
    return False


def _count_distinct_numbers(text: str) -> int:
    """Đếm giá trị số phân biệt trong text (bao gồm dạng 87%, 5x, 8.4x, 200→1000)."""
    nums = re.findall(r"\d+(?:[.,]\d+)?", text)
    return len(set(nums))
