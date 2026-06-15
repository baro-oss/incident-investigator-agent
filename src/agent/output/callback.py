"""
C4 — Webhook callback outbound (Phase 6 Ngày 30).

Sau verdict, POST kết quả structured ra callback_url của caller.
Dùng để integrate CI/CD pipeline, monitoring system, ...

READ-ONLY với hệ thống ngoài: chỉ POST thông tin, không ghi/sửa/xóa.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agent.engine.state import InvestigationState

logger = logging.getLogger(__name__)


def _build_callback_payload(state: InvestigationState) -> Dict[str, Any]:
    v = state.verdict
    return {
        "investigation_id": state.investigation_id,
        "project_id": state.project_id,
        "scenario": state.scenario,
        "symptom": state.symptom,
        "stop_reason": state.stop_reason,
        "steps_taken": state.steps_taken,
        "verdict": {
            "root_cause": v.root_cause if v else None,
            "confidence": v.confidence if v else None,
            "evidence_summary": v.evidence_summary if v else None,
            "propagation_note": (v.propagation_note if v else None) or "",
            "competing_hypotheses": (v.competing_hypotheses if v else None) or "",
            "speculative": getattr(v, "speculative", False) if v else False,
        } if v else None,
    }


async def push_callback(
    state: InvestigationState,
    callback_url: str,
    headers: Optional[Dict[str, str]] = None,
) -> bool:
    """POST verdict structured ra callback_url. Trả True nếu thành công (2xx)."""
    import aiohttp

    payload = _build_callback_payload(state)
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                callback_url,
                json=payload,
                headers=req_headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if 200 <= resp.status < 300:
                    logger.info(
                        "Callback OK %d → %s (inv=%s)",
                        resp.status, callback_url, state.investigation_id,
                    )
                    return True
                body = await resp.text()
                logger.warning(
                    "Callback %d → %s: %s",
                    resp.status, callback_url, body[:200],
                )
                return False
    except Exception as e:
        logger.error("Callback error → %s: %s", callback_url, e)
        return False
