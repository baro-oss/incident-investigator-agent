"""Storage dispatcher — chọn backend theo env `DB_BACKEND` (mặc định sqlite).

Giữ API cũ `open_db()` / `get_db_path()` để 17+ caller không phải đổi gì.
Re-export `IntegrityError` trung lập (bind vào backend đang chọn) → caller bắt
lỗi ràng buộc bằng `except IntegrityError`, không phụ thuộc driver native.

  DB_BACKEND=sqlite    → SQLite WAL (default, dev/test)
  DB_BACKEND=postgres  → PostgreSQL qua psycopg3 + pool (Tier-2, prod)
                         Yêu cầu: DATABASE_URL set + pip install '.[postgres]'
"""
from __future__ import annotations

import os
from typing import Any, Optional

from agent.storage import sqlite_backend

_BACKENDS = {"sqlite": sqlite_backend}


def _load_backend():
    backend_name = os.environ.get("DB_BACKEND", "sqlite").lower()
    if backend_name in _BACKENDS:
        return _BACKENDS[backend_name]
    if backend_name == "postgres":
        from agent.storage import postgres_backend
        return postgres_backend
    raise ValueError(
        f"DB_BACKEND='{backend_name}' không hỗ trợ. "
        "Hỗ trợ: sqlite | postgres (cần DATABASE_URL + pip install '.[postgres]')."
    )


_backend = _load_backend()

#: Tên backend đang dùng (vd 'sqlite') — health page đọc cái này.
BACKEND_NAME: str = _backend.name

#: Exception vi phạm ràng buộc, trung lập với driver. Dùng `except IntegrityError`.
IntegrityError = _backend.IntegrityError


def get_db_path() -> str:
    return _backend.db_path()


def open_db(path: Optional[str] = None) -> Any:
    """Mở connection theo backend đang chọn. API giữ nguyên với code cũ."""
    return _backend.connect(path)
