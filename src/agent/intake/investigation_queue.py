"""
B3 — In-process investigation queue (Phase 6 Ngày 29).

asyncio.Queue + worker pool (WORKER_COUNT=3).
Persist pending vào SQLite investigation_queue → sống sót qua restart.
Crash recovery: rows status='running' bị reset về 'pending' khi khởi động.

Không dùng Kafka hay broker ngoài — asyncio.Queue in-process là đủ.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

WORKER_COUNT = 3

# Module-level state (khởi tạo trong start_workers())
_queue: Optional[asyncio.Queue] = None
_workers: List[asyncio.Task] = []
_draining: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_workers() -> None:
    """Khởi động worker pool. Gọi trong server lifespan (sau event loop bắt đầu)."""
    global _queue, _workers, _draining
    _queue = asyncio.Queue()
    _draining = False
    _workers = [
        asyncio.create_task(_worker(i), name=f"inv-worker-{i}")
        for i in range(WORKER_COUNT)
    ]
    _reload_pending()
    logger.info("Investigation queue started: %d workers", WORKER_COUNT)


async def drain_and_stop(timeout: float = 60.0) -> None:
    """
    A1 Graceful shutdown:
    1. Stop accepting new work (_draining=True)
    2. Đợi workers xong (timeout)
    3. Cancel còn lại
    """
    global _draining
    _draining = True
    logger.info("Queue draining (timeout=%.0fs) …", timeout)

    if not _workers:
        return

    # Đợi queue trống (items đang chạy xong)
    try:
        await asyncio.wait_for(_queue.join(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Queue drain timeout — cancelling remaining workers")

    for w in _workers:
        if not w.done():
            w.cancel()
    await asyncio.gather(*_workers, return_exceptions=True)
    _workers.clear()
    logger.info("Queue drained and workers stopped")


def enqueue(req: Any, step_budget: int = 10) -> None:
    """Thêm investigation vào queue. Persist ngay vào SQLite."""
    _persist_one(req)
    if _queue is not None and not _draining:
        _queue.put_nowait((req, step_budget))
    else:
        logger.warning("Queue not started or draining — investigation persisted but not in-memory: %s", req.dedup_key)


def is_draining() -> bool:
    return _draining


def queue_depth() -> int:
    return _queue.qsize() if _queue is not None else 0


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

async def _worker(worker_id: int) -> None:
    from agent.intake.runner import run_investigation_background

    while True:
        # Poll với timeout ngắn để có thể check _draining
        try:
            item = await asyncio.wait_for(_queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            if _draining and (_queue is None or _queue.empty()):
                logger.debug("Worker %d: draining complete", worker_id)
                return
            continue
        except asyncio.CancelledError:
            return

        req, step_budget = item
        _set_db_status(req.dedup_key, "running")
        status = "done"
        try:
            await run_investigation_background(req, step_budget=step_budget)
        except asyncio.CancelledError:
            logger.warning("Worker %d: investigation %s cancelled", worker_id, req.dedup_key)
            status = "failed"
            raise
        except Exception as e:
            logger.error("Worker %d: investigation %s crashed: %s", worker_id, req.dedup_key, e)
            status = "failed"
        finally:
            _set_db_status(req.dedup_key, status)
            _queue.task_done()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _open():
    from agent.storage.db import open_db
    return open_db()


def _persist_one(req: Any) -> None:
    payload = json.dumps(dataclasses.asdict(req))
    conn = _open()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO investigation_queue "
            "(id, project_id, payload, status, enqueued_at) VALUES (?, ?, ?, 'pending', ?)",
            (req.dedup_key, req.project_id, payload, _now()),
        )
        conn.commit()
    except Exception as e:
        logger.warning("Cannot persist queue item %s: %s", req.dedup_key, e)
    finally:
        conn.close()


def _set_db_status(key: str, status: str) -> None:
    conn = _open()
    try:
        conn.execute(
            "UPDATE investigation_queue SET status=? WHERE id=?",
            (status, key),
        )
        conn.commit()
    except Exception as e:
        logger.warning("Cannot update queue status %s→%s: %s", key, status, e)
    finally:
        conn.close()


def _reload_pending() -> None:
    """Crash recovery: reset stale 'running' → 'pending', load all pending."""
    from agent.intake.normalizer import InvestigationRequest

    conn = _open()
    try:
        # Rows còn 'running' = crashed mid-run → reset
        conn.execute(
            "UPDATE investigation_queue SET status='pending' WHERE status='running'"
        )
        conn.commit()
        rows = conn.execute(
            "SELECT payload FROM investigation_queue WHERE status='pending' ORDER BY enqueued_at"
        ).fetchall()
    except Exception as e:
        logger.warning("Cannot reload pending queue: %s", e)
        rows = []
    finally:
        conn.close()

    reloaded = 0
    for row in rows:
        try:
            data = json.loads(row["payload"])
            req = InvestigationRequest(**data)
            _queue.put_nowait((req, 10))
            reloaded += 1
        except Exception as e:
            logger.warning("Skip bad queue row: %s", e)

    if reloaded:
        logger.info("Reloaded %d pending investigation(s) from DB", reloaded)
