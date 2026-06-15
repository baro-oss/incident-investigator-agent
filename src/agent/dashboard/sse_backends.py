"""
SSE backend seam (Ngày 35) — cho phép swap pub/sub backend không sửa engine.

Hai backend:
  - InMemorySSEBroker (default): asyncio.Queue per-tab — đang dùng.
  - RedisSSEBrokerStub: stub để CHỨNG MINH seam; wire khi có Redis thật.

Chọn backend: `SSE_BACKEND=redis` (default = memory).
Engine và dashboard chỉ dùng `get_sse_broker()` — không biết backend là gì.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncGenerator, Dict, List

logger = logging.getLogger(__name__)


# ── Protocol ─────────────────────────────────────────────────────────────────

class SSEBroker:
    """Base interface cho SSE broker.

    Mỗi subclass phải hiện thực publish() + stream().
    """

    def publish(self, investigation_id: str, event_type: str, payload: dict) -> None:
        raise NotImplementedError

    async def stream(self, investigation_id: str) -> AsyncGenerator[str, None]:
        raise NotImplementedError
        # makes this a generator; type checker happy
        yield  # type: ignore[misc]


# ── In-memory (hiện tại — production cho single-node) ────────────────────────

class InMemorySSEBroker(SSEBroker):
    """asyncio.Queue per-subscriber. Hoạt động tốt cho single-process deployment."""

    def __init__(self) -> None:
        self._subs: Dict[str, List[asyncio.Queue]] = {}

    def publish(self, investigation_id: str, event_type: str, payload: dict) -> None:
        queues = self._subs.get(investigation_id, [])
        data = json.dumps(
            {"type": event_type, "payload": payload}, ensure_ascii=False, default=str
        )
        for q in queues:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    def publish_sync(self, investigation_id: str, event_type: str, payload: dict) -> None:
        """Gọi từ sync context — đẩy vào running event loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(self.publish, investigation_id, event_type, payload)
        except Exception as e:
            logger.debug("SSE publish_sync error: %s", e)

    async def stream(self, investigation_id: str) -> AsyncGenerator[str, None]:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subs.setdefault(investigation_id, []).append(q)
        logger.debug("SSE subscribe: inv=%s", investigation_id)
        try:
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"data: {data}\n\n"
                    try:
                        parsed = json.loads(data)
                        if parsed.get("type") in ("verdict", "done"):
                            yield 'data: {"type":"done"}\n\n'
                            break
                    except Exception:
                        pass
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            try:
                self._subs.get(investigation_id, []).remove(q)
            except ValueError:
                pass
            logger.debug("SSE unsubscribe: inv=%s", investigation_id)


# ── Redis stub (Tier-2 seam) ──────────────────────────────────────────────────

class RedisSSEBrokerStub(SSEBroker):
    """Redis pub/sub backend — STUB (chứng minh seam).

    Wire thật khi có Redis: REDIS_URL env + aioredis/redis-py.
    Mỗi investigation → channel key `sse:{investigation_id}`.
    Subscriber mở aioredis.subscribe(channel) và yield events về browser.
    """

    def __init__(self) -> None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        logger.info("RedisSSEBroker stub — REDIS_URL=%s (chưa wire)", redis_url)

    def publish(self, investigation_id: str, event_type: str, payload: dict) -> None:
        raise NotImplementedError(
            "SSE_BACKEND=redis chưa wire. "
            "Cần: pip install aioredis, hiện thực publish qua PUBLISH sse:{inv_id}, "
            "và stream() qua SUBSCRIBE. Xem src/agent/dashboard/sse_backends.py."
        )

    async def stream(self, investigation_id: str) -> AsyncGenerator[str, None]:
        raise NotImplementedError("RedisSSEBrokerStub.stream() chưa wire.")
        yield  # type: ignore[misc]


# ── Factory ───────────────────────────────────────────────────────────────────

_broker_instance: SSEBroker | None = None


def get_sse_broker() -> SSEBroker:
    """Singleton — chọn backend theo SSE_BACKEND env (default: memory)."""
    global _broker_instance
    if _broker_instance is None:
        backend = os.environ.get("SSE_BACKEND", "memory").lower()
        if backend == "redis":
            _broker_instance = RedisSSEBrokerStub()
        else:
            _broker_instance = InMemorySSEBroker()
        logger.info("SSE broker: %s", type(_broker_instance).__name__)
    return _broker_instance
