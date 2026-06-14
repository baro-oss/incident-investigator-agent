"""
Resilience primitives — retry, concurrency control, circuit breaker.

Module-level singletons được import bởi runner.py và graph.py.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Retry with exponential backoff
# ---------------------------------------------------------------------------

async def with_retry(
    coro_fn: Callable[[], Coroutine[Any, Any, T]],
    max_attempts: int = 3,
    base_delay: float = 2.0,
) -> T:
    """Thử lại với exponential backoff khi LLM trả 429/5xx.

    coro_fn: callable không nhận arg, trả coroutine (lambda: llm.complete(...))
    """
    last_exc: Exception = RuntimeError("no attempts")
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_fn()
        except Exception as e:
            last_exc = e
            if not _is_retryable(e) or attempt == max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "LLM retry %d/%d sau %.1fs: %s", attempt, max_attempts, delay, e
            )
            await asyncio.sleep(delay)
    raise last_exc


def _is_retryable(e: Exception) -> bool:
    """Heuristic: rate limit / server overload → retry; logic error → không."""
    msg = str(e).lower()
    retryable_phrases = ("429", "rate limit", "overload", "503", "502", "timeout", "connection")
    return any(p in msg for p in retryable_phrases)


# ---------------------------------------------------------------------------
# Concurrency limiter
# ---------------------------------------------------------------------------

class ConcurrencyLimiter:
    """Giới hạn số investigation chạy song song. Queue khi đã đầy."""

    def __init__(self, max_concurrent: int = 3) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max = max_concurrent
        self._active = 0
        self._queued = 0

    async def __aenter__(self) -> "ConcurrencyLimiter":
        self._queued += 1
        await self._semaphore.acquire()
        self._queued -= 1
        self._active += 1
        return self

    async def __aexit__(self, *_: Any) -> None:
        self._active -= 1
        self._semaphore.release()

    @property
    def active(self) -> int:
        return self._active

    @property
    def queued(self) -> int:
        return self._queued

    @property
    def max_concurrent(self) -> int:
        return self._max

    def status_dict(self) -> dict:
        return {
            "active": self._active,
            "queued": self._queued,
            "max_concurrent": self._max,
            "available": max(0, self._max - self._active),
        }


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Circuit breaker cho LLM calls.

    State machine:
        closed (bình thường)
            → N failures liên tiếp → open (tạm dừng)
            → sau recovery_timeout → half-open (test)
            → success → closed; failure → open lại
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        name: str = "llm",
    ) -> None:
        self._threshold = failure_threshold
        self._timeout = recovery_timeout
        self._name = name
        self._failures = 0
        self._state = "closed"
        self._opened_at: float = 0.0

    @property
    def state(self) -> str:
        if self._state == "open":
            remaining = self._timeout - (time.monotonic() - self._opened_at)
            if remaining <= 0:
                return "half-open"  # caller vẫn thấy "open" cho đến khi test OK
        return self._state

    @property
    def failures(self) -> int:
        return self._failures

    @property
    def remaining_seconds(self) -> float:
        if self._state != "open":
            return 0.0
        return max(0.0, self._timeout - (time.monotonic() - self._opened_at))

    def status_dict(self) -> dict:
        return {
            "state": self.state,
            "failures": self._failures,
            "threshold": self._threshold,
            "remaining_s": round(self.remaining_seconds, 1),
        }

    async def call(self, coro_fn: Callable[[], Coroutine]) -> Any:
        """Chạy coro qua circuit breaker. Raise RuntimeError nếu circuit OPEN."""
        current = self.state
        if current == "open":
            raise RuntimeError(
                f"Circuit breaker [{self._name}] OPEN — LLM đã lỗi {self._failures}x. "
                f"Còn {self.remaining_seconds:.0f}s."
            )
        if current == "half-open":
            logger.info("Circuit breaker [%s]: half-open — testing...", self._name)
            # Cho phép 1 request thử; nếu OK → close, nếu fail → open lại
            self._state = "half-open"

        try:
            result = await coro_fn()
            # Success
            if self._state in ("half-open", "open"):
                logger.info("Circuit breaker [%s]: closed (LLM recovered)", self._name)
            self._failures = 0
            self._state = "closed"
            return result

        except Exception as e:
            self._failures += 1
            if self._failures >= self._threshold:
                if self._state != "open":
                    self._state = "open"
                    self._opened_at = time.monotonic()
                    logger.error(
                        "Circuit breaker [%s] OPEN: %d failures. Pause %.0fs.",
                        self._name, self._failures, self._timeout,
                    )
                    asyncio.create_task(_alert_circuit_open(self._name, self._failures))
            raise


async def _alert_circuit_open(name: str, failures: int) -> None:
    try:
        from agent.output.telegram import send_telegram
        await send_telegram(
            f"⚠️ Circuit Breaker [{name}] OPEN\n"
            f"LLM đã lỗi {failures} lần liên tiếp. Investigation tạm dừng 60s."
        )
    except Exception as ex:
        logger.warning("Không push được circuit alert: %s", ex)


# ---------------------------------------------------------------------------
# Module-level singletons — dùng bởi runner.py, router.py, graph.py
# ---------------------------------------------------------------------------

investigation_limiter = ConcurrencyLimiter(max_concurrent=3)
llm_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0, name="llm")
