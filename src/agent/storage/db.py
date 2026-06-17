"""Storage dispatcher — luôn dùng Postgres backend.

Giữ API cũ `open_db()` / `get_db_path()` để tất cả caller không đổi gì.
Re-export `IntegrityError` trung lập → caller bắt lỗi bằng `except IntegrityError`.

  DB_BACKEND=postgres  DATABASE_URL=postgresql://...  (bắt buộc)
"""
from __future__ import annotations

from typing import Any, Optional

from agent.storage import postgres_backend as _backend

#: Tên backend đang dùng — health page đọc cái này.
BACKEND_NAME: str = _backend.name

#: Exception vi phạm ràng buộc, trung lập với driver. Dùng `except IntegrityError`.
IntegrityError = _backend.IntegrityError


def get_db_path() -> str:
    return _backend.db_path()


def open_db(path: Optional[str] = None) -> Any:
    """Mở connection Postgres từ pool. API giữ nguyên với code cũ."""
    return _backend.connect(path)
