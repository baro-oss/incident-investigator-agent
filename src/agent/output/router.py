"""
Output router — fan-out verdict đến tất cả kênh của project.

Thứ tự ưu tiên:
  1. project_alert_channels (DB) — per-project config, mỗi kênh có thể override URL/chat_id/to
  2. OUTPUT_CHANNELS env var — fallback global (backward compat)

Thêm kênh mới:
  1. Viết adapter src/agent/output/<channel>.py với push_verdict_to_<channel>(state, config)
  2. Đăng ký trong _dispatch() bên dưới
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from agent.engine.state import InvestigationState

logger = logging.getLogger(__name__)


async def _dispatch(channel: str, state: InvestigationState, config: Dict[str, Any]) -> None:
    """Gọi adapter tương ứng. Lỗi log nhưng không raise."""
    try:
        if channel == "telegram":
            from agent.output.telegram import push_verdict_to_telegram
            await push_verdict_to_telegram(state, config=config)
        elif channel == "teams":
            from agent.output.teams import push_verdict_to_teams
            await push_verdict_to_teams(state, config=config)
        elif channel == "email":
            from agent.output.email import push_verdict_to_email
            await push_verdict_to_email(state, config=config)
        elif channel == "slack":
            from agent.output.slack import push_verdict_to_slack
            await push_verdict_to_slack(state, config=config)
        else:
            logger.warning("Output channel không hỗ trợ: '%s' (bỏ qua)", channel)
    except Exception as e:
        logger.error("Kênh '%s' lỗi: %s", channel, e)


async def push_verdict(state: Optional[InvestigationState]) -> None:
    """
    Gửi verdict đến tất cả kênh của project.

    Nếu project có cấu hình channel trong DB → dùng đó (kể cả config override).
    Nếu không có → fallback env var OUTPUT_CHANNELS=telegram,teams,...
    Mỗi kênh chạy độc lập — một kênh lỗi không chặn kênh khác.
    """
    if state is None:
        logger.error("push_verdict called with state=None — skipping output")
        return
    channels: List[Dict[str, Any]] = []

    # Thử load per-project channels từ DB
    try:
        from agent.intake.project_registry import get_enabled_project_channels
        channels = get_enabled_project_channels(state.project_id)
    except Exception as e:
        logger.warning("Không đọc được project channels từ DB: %s", e)

    if channels:
        logger.info("Project '%s': push verdict → %s", state.project_id, [c["channel"] for c in channels])
        for entry in channels:
            await _dispatch(entry["channel"], state, entry["config"])
    else:
        # Fallback: global OUTPUT_CHANNELS env var
        raw = os.getenv("OUTPUT_CHANNELS", "telegram")
        global_channels = [c.strip() for c in raw.split(",") if c.strip()]
        logger.info("Fallback global channels: %s", global_channels)
        for channel in global_channels:
            await _dispatch(channel, state, {})
