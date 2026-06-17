"""Connection pool cho payment-gateway gọi downstream (auth-service, third-party-provider)."""
from __future__ import annotations

import time


class PoolTimeout(Exception):
    """Raised khi không lấy được connection rảnh trong pool."""


# Số connection upstream đồng thời tối đa. Sized cho throughput giờ cao điểm.
MAX_POOL_SIZE = 50
ACQUIRE_TIMEOUT_MS = 30000
MAX_RETRIES = 3


class Connection:
    def __init__(self, pool: "ConnectionPool") -> None:
        self._pool = pool

    def release(self) -> None:
        self._pool._in_use -= 1


class ConnectionPool:
    def __init__(self) -> None:
        self._in_use = 0

    def acquire(self) -> "Connection":
        """Lấy connection; retry kèm backoff khi gặp pool timeout tạm thời."""
        attempt = 0
        while True:
            try:
                return self._checkout()
            except PoolTimeout:
                attempt += 1
                if attempt >= MAX_RETRIES:
                    raise
                time.sleep(0.2 * attempt)  # backoff trước khi thử lại

    def _checkout(self) -> "Connection":
        if self._in_use >= MAX_POOL_SIZE:
            raise PoolTimeout("no free connection in pool")
        self._in_use += 1
        return Connection(self)
