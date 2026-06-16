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


class _SQLiteConn:
    """Wrap sqlite3.Connection để __exit__ đóng connection (giống _PGConnection).

    sqlite3 context manager gốc commit/rollback nhưng không close — gây rò
    connection khi dùng `with open_db() as conn:`. Wrapper này đóng sau khi thoát.
    """

    __slots__ = ("_conn",)

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def __enter__(self) -> "_SQLiteConn":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False


def connect(path: Optional[str] = None) -> _SQLiteConn:
    """Mở connection SQLite (WAL + foreign_keys + row→dict được).

    Giữ nguyên hành vi `open_db()` cũ → 17+ caller không vỡ.
    """
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return _SQLiteConn(conn)
