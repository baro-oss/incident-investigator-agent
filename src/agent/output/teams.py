"""
Microsoft Teams adapter — render verdict → MessageCard, gửi qua Incoming Webhook.

Format: Office 365 Connector MessageCard (tương thích mọi Teams channel có Incoming Webhook).
Env: TEAMS_WEBHOOK_URL=https://xxx.webhook.office.com/webhookb2/...
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

from agent.engine.state import InvestigationState

logger = logging.getLogger(__name__)

# themeColor theo mức độ nghiêm trọng (hex, không có #)
_THEME_COLOR = {
    "high": "DC143C",       # đỏ
    "medium": "FF8C00",     # cam
    "low": "FFD700",        # vàng
    "insufficient": "808080",
}

_CONF_LABEL = {
    "high": "Độ tin CAO",
    "medium": "Độ tin TRUNG BÌNH",
    "low": "Độ tin THẤP",
    "insufficient": "Chưa đủ bằng chứng",
}


def _facts(items: List[tuple]) -> List[Dict[str, str]]:
    """Chuyển list (name, value) → facts array, bỏ qua giá trị rỗng."""
    return [{"name": n, "value": v} for n, v in items if v and v.strip()]


def render_teams_card(state: InvestigationState) -> Dict[str, Any]:
    """Render InvestigationState → MessageCard dict sẵn sàng POST."""
    v = state.verdict
    inv_id = state.investigation_id

    if v is None:
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "808080",
            "summary": f"Điều tra #{inv_id} — chưa kết luận",
            "sections": [{
                "activityTitle": f"⏱️ Điều tra #{inv_id} — Chưa kết luận",
                "activitySubtitle": f"Stop: {state.stop_reason} ({state.steps_taken}/{state.step_budget} bước)",
                "activityText": f"Triệu chứng: {state.symptom[:120]}",
                "facts": _facts([
                    ("Bằng chứng thu được", "; ".join(
                        f"[{e.tool_name}] {e.summary[:60]}" for e in state.evidence[-3:]
                    )),
                ]),
                "markdown": True,
            }],
        }

    color = _THEME_COLOR.get(v.confidence, "808080")
    conf_label = _CONF_LABEL.get(v.confidence, v.confidence)
    conf_icon = {"high": "🔴", "medium": "🟠", "low": "🟡", "insufficient": "⚪"}.get(v.confidence, "⚪")

    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": f"Incident Investigation #{inv_id}",
        "sections": [{
            "activityTitle": f"{conf_icon} Root cause: {v.root_cause[:120]}",
            "activitySubtitle": f"{conf_label} · {state.steps_taken} bước · {state.scenario}",
            "activityText": f"**Triệu chứng:** {state.symptom[:120]}",
            "facts": _facts([
                ("Bằng chứng chính", v.evidence_summary[:200] if v.evidence_summary else ""),
                ("Lan truyền", v.propagation_note[:150] if v.propagation_note else ""),
                ("Đã loại trừ", v.competing_hypotheses[:150] if v.competing_hypotheses else ""),
                ("Investigation ID", inv_id),
            ]),
            "markdown": True,
        }],
    }


async def push_verdict_to_teams(
    state: InvestigationState,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """Gửi verdict lên Microsoft Teams. config["webhook_url"] override env var."""
    url = (config or {}).get("webhook_url") or os.environ.get("TEAMS_WEBHOOK_URL", "").strip()
    if not url:
        logger.warning("TEAMS_WEBHOOK_URL chưa cấu hình — bỏ qua gửi Teams.")
        return False

    card = render_teams_card(state)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=card, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                body = await resp.text()
                if resp.status == 200 and body.strip() == "1":
                    logger.info("Teams gửi OK (investigation=%s)", state.investigation_id)
                    return True
                logger.error("Teams lỗi %d: %s", resp.status, body[:200])
                return False
    except Exception as e:
        logger.error("Teams exception: %s", e)
        return False
