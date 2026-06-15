"""
SSE Broker — in-memory pub/sub cho real-time dashboard.

Mỗi investigation_id có một danh sách asyncio.Queue (1 queue = 1 browser tab).
`publish()` được gọi từ engine loop sau mỗi trace event.
`stream()` là async generator dùng bởi FastAPI StreamingResponse.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List

logger = logging.getLogger(__name__)

# investigation_id → list of subscriber queues
_subs: Dict[str, List[asyncio.Queue]] = {}


def publish_sync(investigation_id: str, event_type: str, payload: dict) -> None:
    """Gọi từ sync context (loop trong asyncio event loop).
    Dùng call_soon_threadsafe để đẩy vào event loop đang chạy.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(_do_publish, investigation_id, event_type, payload)
    except Exception as e:
        logger.debug("SSE publish_sync lỗi: %s", e)


def _do_publish(investigation_id: str, event_type: str, payload: dict) -> None:
    """Chạy trong event loop — đưa event vào tất cả queue subscriber."""
    queues = _subs.get(investigation_id, [])
    data = json.dumps({"type": event_type, "payload": payload}, ensure_ascii=False, default=str)
    for q in queues:
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass  # browser chậm — bỏ qua event này


async def stream(investigation_id: str) -> AsyncGenerator[str, None]:
    """Async generator: yield SSE-formatted string cho mỗi event."""
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _subs.setdefault(investigation_id, []).append(q)
    logger.debug("SSE subscribe: inv=%s subs=%d", investigation_id, len(_subs[investigation_id]))

    try:
        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=20.0)
                yield f"data: {data}\n\n"

                # Nếu là event kết thúc → đóng stream
                try:
                    parsed = json.loads(data)
                    if parsed.get("type") in ("verdict", "done"):
                        yield "data: {\"type\":\"done\"}\n\n"
                        break
                except Exception:
                    pass

            except asyncio.TimeoutError:
                # Heartbeat giữ connection
                yield ": heartbeat\n\n"

    finally:
        subs = _subs.get(investigation_id, [])
        try:
            subs.remove(q)
        except ValueError:
            pass
        logger.debug("SSE unsubscribe: inv=%s", investigation_id)
