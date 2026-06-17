"""Xác thực JWT cho auth-service — giải mã token và trích claims."""
from __future__ import annotations

import jwt

JWT_ALGORITHM = "HS256"
# Cho phép lệch đồng hồ ±30s giữa các node để token vừa phát hành không bị từ chối oan.
CLOCK_SKEW_LEEWAY = 30


class AuthenticationError(Exception):
    """Raised khi token không hợp lệ hoặc đã hết hạn."""


def verify(token: str, key: str) -> dict:
    """Giải mã & xác thực JWT; trả claims nếu hợp lệ, raise AuthenticationError nếu không."""
    try:
        return jwt.decode(
            token,
            key,
            algorithms=[JWT_ALGORITHM],
            leeway=CLOCK_SKEW_LEEWAY,  # dung sai lệch đồng hồ giữa các node
        )
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(str(exc)) from exc
