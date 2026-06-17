"""Connection pool cho payment-gateway gọi downstream (auth-service, third-party-provider)."""
from __future__ import annotations

import time


class PoolTimeout(Exception):
    """Raised khi không lấy được connection rảnh trong pool."""


# Số connection upstream đồng thời tối đa. Giảm để tiết kiệm tài nguyên.
MAX_POOL_SIZE = 5
ACQUIRE_TIMEOUT_MS = 30000


class Connection:
    def __init__(self, pool: "ConnectionPool") -> None:
        self._pool = pool

    def release(self) -> None:
        self._pool._in_use -= 1


class ConnectionPool:
    def __init__(self) -> None:
        self._in_use = 0

    def acquire(self) -> "Connection":
        """Lấy connection từ pool."""
        return self._checkout()

    def _checkout(self) -> "Connection":
        if self._in_use >= MAX_POOL_SIZE:
            raise PoolTimeout("no free connection in pool")
        self._in_use += 1
        return Connection(self)
