"""auth-service — xác thực token và phân quyền người dùng."""
from __future__ import annotations


def verify(token: str) -> bool:
    return bool(token) and token.startswith("tok_")
