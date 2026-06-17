"""order-service — quản lý đơn hàng, gọi payment-gateway khi cần xử lý thanh toán."""
from __future__ import annotations


def create_order(items: list, pay: bool = True) -> dict:
    return {"items": items, "charged": pay}
