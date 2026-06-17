"""api-gateway — cửa vào duy nhất, route request tới payment-gateway / order-service."""
from __future__ import annotations

ROUTES = {
    "/pay": "payment-gateway",
    "/order": "order-service",
}


def route(path: str) -> str:
    return ROUTES.get(path, "not-found")
