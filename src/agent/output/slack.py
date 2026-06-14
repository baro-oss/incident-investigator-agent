"""
Slack output adapter — Incoming Webhook (không OAuth).

Env: SLACK_WEBHOOK_URL
Per-project override: config["webhook_url"]

Format: Block Kit với màu attachment theo severity.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import aiohttp

from agent.engine.state import InvestigationState

logger = logging.getLogger(__name__)

_CONFIDENCE_COLOR = {
    "high": "#DC143C",
    "medium": "#FF8C00",
    "low": "#FFD700",
    "insufficient": "#808080",
}
_CONFIDENCE_EMOJI = {
    "high": ":red_circle:",
    "medium": ":large_orange_circle:",
    "low": ":large_yellow_circle:",
    "insufficient": ":white_circle:",
}


def _render_slack_payload(state: InvestigationState) -> Dict[str, Any]:
    """Build Slack Incoming Webhook payload với Block Kit."""
    verdict = state.verdict
    stop = state.stop_reason or ("verdict" if verdict else "timeout")
    if verdict:
        conf = (verdict.confidence or "insufficient").lower()
        root = verdict.root_cause or "(không xác định)"
        evidence_summary = verdict.evidence_summary or ""
    else:
        conf = "insufficient"
        root = "(điều tra chưa hoàn thành)"
        evidence_summary = ""

    color = _CONFIDENCE_COLOR.get(conf, "#808080")
    emoji = _CONFIDENCE_EMOJI.get(conf, ":white_circle:")

    header = f"{emoji} *[{state.project_id}] {state.scenario}* — Confidence {conf.upper()}"

    fields = [
        {"type": "mrkdwn", "text": f"*Root cause:*\n{root}"},
        {
            "type": "mrkdwn",
            "text": f"*Steps:* {state.steps_taken} / {state.step_budget} | *Tokens:* {state.total_tokens}",
        },
    ]

    if evidence_summary:
        fields.append({
            "type": "mrkdwn",
            "text": f"*Evidence:*\n{evidence_summary[:200]}",
        })

    # Hiện tối đa 3 evidence items riêng lẻ nếu summary trống
    elif state.evidence:
        ev_lines = []
        for ev in state.evidence[:3]:
            ev_lines.append(f"• [{ev.tool_name}] {ev.summary[:120]}")
        if len(state.evidence) > 3:
            ev_lines.append(f"… và {len(state.evidence) - 3} evidence khác")
        fields.append({
            "type": "mrkdwn",
            "text": "*Evidence:*\n" + "\n".join(ev_lines),
        })

    if stop != "verdict":
        fields.append({
            "type": "mrkdwn",
            "text": f":warning: *Stop reason:* `{stop}`",
        })

    attachment = {
        "color": color,
        "blocks": [
            {"type": "section", "fields": fields[:10]},
        ],
    }

    symptom_short = (state.symptom or "")[:120]
    if symptom_short:
        attachment["blocks"].insert(0, {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Triệu chứng:* {symptom_short}"},
        })

    return {
        "text": header,
        "attachments": [attachment],
    }


async def push_verdict_to_slack(
    state: InvestigationState,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    config = config or {}
    webhook_url = config.get("webhook_url") or os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL chưa cấu hình — bỏ qua Slack push")
        return

    payload = _render_slack_payload(state)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                body = await resp.text()
                if resp.status == 200 and body.strip() == "ok":
                    logger.info(
                        "Slack push OK — conf=%s scenario=%s",
                        state.verdict and state.verdict.confidence,
                        state.scenario,
                    )
                else:
                    logger.warning("Slack push status=%d body=%r", resp.status, body[:200])
    except Exception as e:
        logger.error("Slack push lỗi: %s", e)
