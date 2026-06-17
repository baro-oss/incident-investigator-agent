"""auth-service — xác thực token và phân quyền người dùng."""
from __future__ import annotations

from auth.validator import AuthenticationError, verify


def authenticate(token: str, key: str) -> dict:
    """Xác thực một request; trả claims nếu token hợp lệ."""
    return verify(token, key)
