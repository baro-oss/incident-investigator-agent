"""
Proactive monitoring scheduler (Ngày 32).

Hai nhiệm vụ mỗi tick (mặc định 60s):
  1. Fire scheduled triggers đến hạn → enqueue vào investigation queue.
  2. Check recurring incidents vượt ngưỡng → push Telegram/Slack alert (1 lần/pattern).

Không dùng cron library — asyncio.sleep loop là đủ cho interval-based trigger.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCAN_INTERVAL = 60  # giây giữa các lần scan

_task: Optional[asyncio.Task] = None
_running: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """Khởi động scheduler. Gọi trong server lifespan sau start_workers()."""
    global _task, _running
    _running = True
    _task = asyncio.create_task(_scheduler_loop(), name="scheduler")
    logger.info("Scheduler started (scan_interval=%ds)", SCAN_INTERVAL)


async def stop_scheduler() -> None:
    """Dừng scheduler khi shutdown."""
    global _running, _task
    _running = False
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    logger.info("Scheduler stopped")


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

async def _scheduler_loop() -> None:
    while _running:
        try:
            await _tick()
        except Exception as e:
            logger.error("Scheduler tick error: %s", e)
        try:
            await asyncio.sleep(SCAN_INTERVAL)
        except asyncio.CancelledError:
            return


async def _tick() -> None:
    _fire_due_triggers()
    await _check_recurring_alerts()


# ---------------------------------------------------------------------------
# A: Fire scheduled triggers
# ---------------------------------------------------------------------------

def _fire_due_triggers() -> None:
    from agent.storage.db import open_db
    from agent.intake.investigation_queue import enqueue, is_draining

    if is_draining():
        return

    now = _now()
    conn = open_db()
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_triggers WHERE enabled=1 AND next_run_at <= ? ORDER BY next_run_at",
            (now,),
        ).fetchall()
    except Exception as e:
        logger.warning("Scheduler: cannot read triggers: %s", e)
        return
    finally:
        conn.close()

    for row in rows:
        row = dict(row)
        try:
            req = _build_request(row)
            enqueue(req)
            _update_next_run(row["id"], row["interval_min"])
            logger.info(
                "Scheduler: fired trigger=%s project=%s service=%s interval=%dmin",
                row["id"][:8], row["project_id"], row["service"], row["interval_min"],
            )
        except Exception as e:
            logger.error("Scheduler: trigger %s error: %s", row["id"][:8], e)


def _build_request(row: Dict[str, Any]) -> Any:
    from agent.intake.normalizer import InvestigationRequest

    now_dt = datetime.now(timezone.utc)
    hour = now_dt.hour
    time_window = f"{hour:02d}:00-{(hour + 1) % 24:02d}:00"
    date_str = now_dt.strftime("%Y-%m-%d")
    key = f"{row['project_id']}|{row['service']}|{row['scenario']}|{time_window}"

    return InvestigationRequest(
        service=row["service"],
        scenario=row["scenario"],
        time_window=time_window,
        symptom=f"Scheduled investigation: {row['service']} ({row['scenario']})",
        date=date_str,
        raw_payload={},
        project_id=row["project_id"],
        dedup_key=key,
    )


def _update_next_run(trigger_id: str, interval_min: int) -> None:
    from agent.storage.db import open_db

    next_run = (datetime.now(timezone.utc) + timedelta(minutes=interval_min)).isoformat()
    conn = open_db()
    try:
        conn.execute(
            "UPDATE scheduled_triggers SET last_run_at=?, next_run_at=? WHERE id=?",
            (_now(), next_run, trigger_id),
        )
        conn.commit()
    except Exception as e:
        logger.warning("Scheduler: update next_run failed: %s", e)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B: Recurring incident alert push
# ---------------------------------------------------------------------------

async def _check_recurring_alerts() -> None:
    threshold = int(os.environ.get("RECURRING_ALERT_THRESHOLD", "5"))
    from agent.storage.db import open_db

    conn = open_db()
    try:
        rows = conn.execute(
            """
            SELECT project_id, service, root_cause_type, count, avg_steps, alerted_at
            FROM investigation_patterns
            WHERE count >= ? AND (alerted_at IS NULL OR alerted_at = '')
            ORDER BY count DESC
            """,
            (threshold,),
        ).fetchall()
    except Exception as e:
        logger.warning("Scheduler: cannot check recurring incidents: %s", e)
        return
    finally:
        conn.close()

    for row in rows:
        row = dict(row)
        try:
            await _push_recurring_alert(row, threshold)
            _mark_alerted(row["project_id"], row["service"], row["root_cause_type"])
        except Exception as e:
            logger.error("Scheduler: recurring alert error for %s/%s: %s",
                         row["project_id"], row["service"], e)


async def _push_recurring_alert(pattern: Dict[str, Any], threshold: int) -> None:
    msg = (
        f"⚠️ *Recurring Incident Alert*\n"
        f"Project: `{pattern['project_id']}` | Service: `{pattern['service']}`\n"
        f"Root cause: `{pattern['root_cause_type']}`\n"
        f"Xuất hiện: *{pattern['count']}* lần (ngưỡng: {threshold})\n"
        f"Avg steps: {pattern['avg_steps']:.1f}"
    )
    pushed = False

    # Telegram
    try:
        from agent.output.telegram import send_telegram
        ok = await send_telegram(msg)
        if ok:
            pushed = True
    except Exception as e:
        logger.debug("Recurring alert Telegram failed: %s", e)

    # Slack (nếu có SLACK_WEBHOOK_URL)
    slack_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if slack_url:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(slack_url, json={"text": msg.replace("*", "")})
            pushed = True
        except Exception as e:
            logger.debug("Recurring alert Slack failed: %s", e)

    if pushed:
        logger.info(
            "Recurring alert pushed: project=%s service=%s count=%d",
            pattern["project_id"], pattern["service"], pattern["count"],
        )


def _mark_alerted(project_id: str, service: str, root_cause_type: str) -> None:
    from agent.storage.db import open_db

    conn = open_db()
    try:
        conn.execute(
            """
            UPDATE investigation_patterns
            SET alerted_at = ?
            WHERE project_id = ? AND service = ? AND root_cause_type = ?
            """,
            (_now(), project_id, service, root_cause_type),
        )
        conn.commit()
    except Exception as e:
        logger.warning("Scheduler: mark_alerted failed: %s", e)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CRUD helpers (dùng bởi dashboard routes)
# ---------------------------------------------------------------------------

def list_triggers(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    from agent.storage.db import open_db

    conn = open_db()
    try:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM scheduled_triggers WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scheduled_triggers ORDER BY project_id, created_at DESC"
            ).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return [dict(r) for r in rows]


def create_trigger(project_id: str, service: str, scenario: str, interval_min: int) -> str:
    from agent.storage.db import open_db

    tid = str(uuid.uuid4())
    now = _now()
    next_run = (datetime.now(timezone.utc) + timedelta(minutes=interval_min)).isoformat()
    conn = open_db()
    try:
        conn.execute(
            """
            INSERT INTO scheduled_triggers
              (id, project_id, service, scenario, interval_min, enabled, next_run_at, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (tid, project_id, service, scenario, interval_min, next_run, now),
        )
        conn.commit()
    finally:
        conn.close()
    return tid


def toggle_trigger(trigger_id: str) -> None:
    from agent.storage.db import open_db

    conn = open_db()
    try:
        conn.execute(
            "UPDATE scheduled_triggers SET enabled = 1 - enabled WHERE id=?",
            (trigger_id,),
        )
        conn.commit()
    finally:
        conn.close()


def delete_trigger(trigger_id: str) -> None:
    from agent.storage.db import open_db

    conn = open_db()
    try:
        conn.execute("DELETE FROM scheduled_triggers WHERE id=?", (trigger_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Util
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
