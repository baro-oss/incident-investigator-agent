"""SQLite backend — hiện thực mặc định của storage seam.

⚠️ Đây là MODULE DUY NHẤT trong `src/agent/` được phép `import sqlite3`.
Đổi sang Postgres/MySQL = thêm file backend tương tự (cùng surface) + set
`DB_BACKEND`. Engine / tools / dashboard / intake KHÔNG đổi.

Surface mọi backend phải cung cấp (xem `base.py` để biết hợp đồng connection):
    name: str
    IntegrityError: type
    db_path() -> str
    connect(path=None) -> connection
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional

#: Tên backend (dùng cho dispatcher + health page).
name = "sqlite"

#: Lỗi vi phạm ràng buộc (UNIQUE/FK) — native của backend này.
#: Dispatcher (db.py) re-export thành `agent.storage.IntegrityError` trung lập.
IntegrityError = sqlite3.IntegrityError


def db_path() -> str:
    return os.environ.get("DB_PATH", "data/investigation.db")


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    """Mở connection SQLite (WAL + foreign_keys + row→dict được).

    Giữ nguyên hành vi `open_db()` cũ → 17+ caller không vỡ.
    """
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
