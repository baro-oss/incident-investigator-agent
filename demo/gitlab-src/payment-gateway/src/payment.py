"""Payment handler — xử lý giao dịch, mượn connection từ pool để gọi provider."""
from __future__ import annotations

from db.pool import ConnectionPool

_pool = ConnectionPool()


def charge(amount: float, currency: str = "VND") -> dict:
    """Thực hiện một giao dịch thanh toán qua third-party-provider."""
    conn = _pool.acquire()
    try:
        # ... gọi auth-service để xác thực, rồi third-party-provider để charge ...
        return {"status": "ok", "amount": amount, "currency": currency}
    finally:
        conn.release()
