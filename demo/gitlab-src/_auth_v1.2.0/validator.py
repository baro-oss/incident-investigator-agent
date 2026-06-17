"""Xác thực JWT cho auth-service — giải mã token và trích claims."""
from __future__ import annotations

import jwt

JWT_ALGORITHM = "HS256"


class AuthenticationError(Exception):
    """Raised khi token không hợp lệ hoặc đã hết hạn."""


def verify(token: str, key: str) -> dict:
    """Giải mã & xác thực JWT; trả claims nếu hợp lệ."""
    return jwt.decode(
        token,
        key,
        algorithms=[JWT_ALGORITHM],
    )
