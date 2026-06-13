"""
Telegram adapter — render verdict → tin nhắn Telegram, gửi qua Bot API.

Nguyên tắc: verdict structured là nguồn, Telegram chỉ là một renderer.
Tin nhắn: đọc được trong 3 giây trên điện thoại, cái quan trọng nhất lên đầu.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import aiohttp

from agent.engine.state import InvestigationState, Verdict

logger = logging.getLogger(__name__)

CONF_EMOJI = {
    "high": "🔴",
    "medium": "🟠",
    "low": "🟡",
    "insufficient": "⚪",
}

CONF_LABEL = {
    "high": "Độ tin CAO",
    "medium": "Độ tin TRUNG BÌNH",
    "low": "Độ tin THẤP",
    "insufficient": "Chưa đủ bằng chứng",
}


def render_telegram_message(state: InvestigationState) -> str:
    """
    Render verdict thành tin nhắn Telegram ngắn gọn.
    Đọc được trong 3 giây — quan trọng nhất lên đầu.
    """
    v = state.verdict
    inv_id = state.investigation_id

    if v is None:
        return (
            f"⚠️ *Điều tra #{inv_id}*\n"
            f"Không tạo được verdict (stop: {state.stop_reason}).\n"
            f"Đã đi {state.steps_taken} bước, thu {len(state.evidence)} observation."
        )

    conf_emoji = CONF_EMOJI.get(v.confidence, "⚪")
    conf_label = CONF_LABEL.get(v.confidence, v.confidence)

    lines = [
        f"{conf_emoji} *Incident Investigation #{inv_id}*",
        "",
        f"*Triệu chứng:* {state.symptom[:100]}",
        "",
        f"*Root cause:*",
        f"  {v.root_cause}",
        "",
        f"*{conf_label}*",
    ]

    # Bằng chứng — tối đa 3 dòng
    if v.evidence_summary:
        lines += ["", "*Bằng chứng chính:*", f"  {v.evidence_summary[:200]}"]

    # Lan truyền nếu có
    if v.propagation_note and v.propagation_note.strip():
        lines += ["", f"*Lan truyền:* {v.propagation_note[:150]}"]

    # Điều tra đã loại trừ gì — quan trọng cho độ tin cậy
    if v.competing_hypotheses and v.competing_hypotheses.strip():
        lines += ["", f"*Đã loại trừ:* {v.competing_hypotheses[:150]}"]

    lines += [
        "",
        f"_{state.steps_taken} bước · {len(state.evidence)} observation · {state.scenario}_",
    ]

    return "\n".join(lines)


def render_partial_verdict_message(state: InvestigationState) -> str:
    """Render khi hết budget hoặc timeout — không được im lặng."""
    lines = [
        f"⏱️ *Incident Investigation #{state.investigation_id} — Chưa kết luận*",
        "",
        f"*Triệu chứng:* {state.symptom[:100]}",
        f"*Stop:* {state.stop_reason} ({state.steps_taken}/{state.step_budget} bước)",
        "",
        "*Những gì đã thu được:*",
    ]
    for ev in state.evidence[-3:]:  # 3 bằng chứng gần nhất
        lines.append(f"  • [{ev.tool_name}] {ev.summary[:80]}")

    lines += ["", "⚠️ _Khuyến nghị: kiểm tra thủ công — agent chưa đủ thời gian kết luận._"]
    return "\n".join(lines)


async def send_telegram(message: str, chat_id_override: str = "") -> bool:
    """Gửi tin nhắn tới Telegram Bot. Trả True nếu thành công."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id_override or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID chưa cấu hình — bỏ qua gửi.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    logger.info("Telegram gửi OK (investigation=%s)", "?")
                    return True
                body = await resp.text()
                logger.error("Telegram lỗi %d: %s", resp.status, body[:200])
                return False
    except Exception as e:
        logger.error("Telegram exception: %s", e)
        return False


async def push_verdict_to_telegram(
    state: InvestigationState,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """Entry point: chọn renderer phù hợp rồi gửi. config["chat_id"] override env var."""
    if state.verdict and state.stop_reason == "verdict":
        message = render_telegram_message(state)
    else:
        message = render_partial_verdict_message(state)

    logger.info("Telegram message:\n%s", message)
    chat_id_override = (config or {}).get("chat_id", "")
    return await send_telegram(message, chat_id_override=chat_id_override)
