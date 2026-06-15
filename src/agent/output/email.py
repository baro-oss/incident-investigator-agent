"""
Email adapter — render verdict → HTML email, gửi qua SMTP.

Không cần dependency mới (dùng stdlib smtplib + email.mime).
SMTP chạy sync trong thread executor để compat với asyncio.

Global env (fallback khi config rỗng):
    SMTP_HOST        SMTP server hostname (bắt buộc để gửi)
    SMTP_PORT        port (mặc định 587 — STARTTLS)
    SMTP_USER        username auth (để trống nếu không cần auth)
    SMTP_PASSWORD    password auth
    SMTP_FROM        địa chỉ gửi
    SMTP_TO          recipient mặc định (override bằng config["to"])
    SMTP_USE_TLS     "true"/"false" — dùng STARTTLS (mặc định true)

Per-project config keys:
    to    recipient(s), comma-separated (override SMTP_TO)
    cc    CC list, comma-separated (optional)
"""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from agent.engine.state import InvestigationState

logger = logging.getLogger(__name__)

_CONF_LABEL = {
    "high": "CAO",
    "medium": "TRUNG BÌNH",
    "low": "THẤP",
    "insufficient": "Chưa đủ bằng chứng",
}
_HEADER_COLOR = {
    "high": "#DC143C",
    "medium": "#FF8C00",
    "low": "#DAA520",
    "insufficient": "#808080",
}
_CONF_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡", "insufficient": "⚪"}


# ── Render ────────────────────────────────────────────────────────────────────

def _row(label: str, value: str) -> str:
    return (
        f'<tr><td style="padding:6px 12px;font-weight:bold;white-space:nowrap;'
        f'color:#555;vertical-align:top">{label}</td>'
        f'<td style="padding:6px 12px;color:#222">{value}</td></tr>'
    )


def render_email_html(state: InvestigationState) -> str:
    v = state.verdict
    inv_id = state.investigation_id

    if v is None:
        header_color = "#808080"
        title = f"⏱️ Điều tra #{inv_id} — Chưa kết luận"
        rows = [
            _row("Stop reason", state.stop_reason or "-"),
            _row("Bước đã đi", f"{state.steps_taken}/{state.step_budget}"),
            _row("Bằng chứng", "; ".join(
                f"[{e.tool_name}] {e.summary[:60]}" for e in state.evidence[-3:]
            ) or "-"),
        ]
    else:
        conf = v.confidence
        header_color = _HEADER_COLOR.get(conf, "#808080")
        icon = _CONF_ICON.get(conf, "⚪")
        title = f"{icon} Incident Investigation #{inv_id}"
        rows = [
            _row("Root cause", v.root_cause),
            _row("Độ tin cậy", _CONF_LABEL.get(conf, conf)),
            _row("Triệu chứng", state.symptom[:150]),
        ]
        if v.evidence_summary:
            rows.append(_row("Bằng chứng", v.evidence_summary[:200]))
        if v.propagation_note and v.propagation_note.strip():
            rows.append(_row("Lan truyền", v.propagation_note[:150]))
        if v.competing_hypotheses and v.competing_hypotheses.strip():
            rows.append(_row("Đã loại trừ", v.competing_hypotheses[:150]))
        rows.append(_row("Kịch bản / Bước", f"{state.scenario} · {state.steps_taken} bước"))

    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f4f4f4">
<div style="max-width:600px;margin:24px auto;background:#fff;border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)">
  <div style="background:{header_color};padding:16px 20px">
    <h2 style="margin:0;color:#fff;font-size:18px">{title}</h2>
    <p style="margin:4px 0 0;color:rgba(255,255,255,.8);font-size:13px">Investigation ID: {inv_id}</p>
  </div>
  <table style="width:100%;border-collapse:collapse;margin:8px 0">
    {''.join(rows)}
  </table>
  <p style="margin:0;padding:12px 20px;font-size:11px;color:#999;border-top:1px solid #eee">
    Agent tự động · {state.project_id}
  </p>
</div>
</body></html>"""


def render_email_plain(state: InvestigationState) -> str:
    v = state.verdict
    if v is None:
        return (
            f"Điều tra #{state.investigation_id} — chưa kết luận\n"
            f"Stop: {state.stop_reason} ({state.steps_taken} bước)\n"
        )
    lines = [
        f"Root cause: {v.root_cause}",
        f"Độ tin: {_CONF_LABEL.get(v.confidence, v.confidence)}",
        f"Triệu chứng: {state.symptom[:150]}",
    ]
    if v.evidence_summary:
        lines.append(f"Bằng chứng: {v.evidence_summary[:200]}")
    if v.propagation_note:
        lines.append(f"Lan truyền: {v.propagation_note[:150]}")
    if v.competing_hypotheses:
        lines.append(f"Đã loại trừ: {v.competing_hypotheses[:150]}")
    return "\n".join(lines)


def _build_subject(state: InvestigationState) -> str:
    if state.verdict:
        icon = _CONF_ICON.get(state.verdict.confidence, "⚪")
        short = state.verdict.root_cause[:60]
        return f"[Alert {icon}] {short}"
    return f"[Alert ⏱️] Điều tra #{state.investigation_id} — chưa kết luận"


# ── Transport (sync — chạy trong executor) ───────────────────────────────────

def _send_sync(state: InvestigationState, config: Dict[str, Any]) -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        logger.warning("SMTP_HOST chưa cấu hình — bỏ qua gửi email.")
        return False

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", user).strip()
    default_to = os.getenv("SMTP_TO", "").strip()
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    to_raw = (config.get("to") or default_to).strip()
    if not to_raw:
        logger.warning("Không có địa chỉ email nhận (config['to'] và SMTP_TO đều rỗng).")
        return False

    to_list: List[str] = [a.strip() for a in to_raw.split(",") if a.strip()]
    cc_list: List[str] = [a.strip() for a in (config.get("cc") or "").split(",") if a.strip()]
    all_recipients = to_list + cc_list

    msg = MIMEMultipart("alternative")
    msg["Subject"] = _build_subject(state)
    msg["From"] = smtp_from
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    msg.attach(MIMEText(render_email_plain(state), "plain", "utf-8"))
    msg.attach(MIMEText(render_email_html(state), "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(smtp_from, all_recipients, msg.as_string())
        logger.info("Email gửi OK → %s (investigation=%s)", to_raw, state.investigation_id)
        return True
    except Exception as e:
        logger.error("Email exception: %s", e)
        return False


async def push_verdict_to_email(
    state: InvestigationState,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """Gửi verdict qua email. config["to"] override SMTP_TO env var."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _send_sync, state, config or {})
