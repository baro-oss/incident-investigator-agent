"""Storage seam — hợp đồng backend + facade `Database`.

Tier-1 (file này + sqlite_backend + db dispatcher): trừu tượng hóa backend để
đổi DB rẻ về sau — runtime VẪN SQLite. Tier-2 (port query phân tích + backend
Postgres chạy thật) là việc Future. Xem `docs/11-roadmap-phase-5.md` (Ngày 21).

Quy ước dùng:
- Code CŨ: `open_db()` (db.py) → connection; dùng `conn.execute(...).fetchall()`.
- Code MỚI (vd RBAC Day 22): nên dùng facade `Database`
  (`query` / `query_one` / `execute` / `connection` / `now`).
- Bắt lỗi ràng buộc: `except IntegrityError` (trung lập, không phụ thuộc driver).

Hợp đồng connection mà MỌI backend phải thoả (để caller cũ không vỡ):
    .execute(sql, params=()) -> cursor     # placeholder qmark `?`
    cursor: .fetchall() .fetchone() .lastrowid .rowcount
    row: dict(row) -> {cột: giá_trị}
    .commit()  .close()
    UPSERT: hỗ trợ cú pháp `INSERT ... ON CONFLICT(...) DO UPDATE`
Backend mới (vd Postgres) chịu trách nhiệm shim cho thoả hợp đồng này (Tier-2).
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Protocol, Sequence


class StorageBackend(Protocol):
    """Hợp đồng tối thiểu của một backend storage."""

    name: str
    IntegrityError: type  # exception backend raise khi vi phạm ràng buộc

    def connect(self, path: Optional[str] = None) -> Any: ...
    def db_path(self) -> str: ...


class Database:
    """Facade gọn cho code mới — mở/commit/close mỗi lời gọi (giống style hiện tại).

    Dùng cho CRUD đơn giản. Với giao dịch nhiều câu lệnh atomic, dùng
    `with db.connection() as conn:` rồi gọi `conn.execute(...)` trực tiếp
    (commit tự động khi thoát context, rollback nếu raise).
    """

    def __init__(self, open_conn) -> None:
        self._open = open_conn  # callable: () -> connection

    @contextmanager
    def connection(self) -> Iterator[Any]:
        conn = self._open()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        conn = self._open()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        conn = self._open()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Chạy 1 câu ghi + commit. Trả `lastrowid` (INSERT) hoặc `rowcount`."""
        conn = self._open()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid if cur.lastrowid is not None else cur.rowcount
        finally:
            conn.close()

    @staticmethod
    def now() -> str:
        """Timestamp ISO-8601 UTC — chuẩn chung cho mọi bảng."""
        return datetime.now(timezone.utc).isoformat()
