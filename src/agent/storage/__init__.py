"""Storage seam — điểm vào duy nhất cho mọi truy cập DB (Postgres).

- `open_db()` / `get_db_path()`: API connection, giữ nguyên.
- `IntegrityError`: bắt lỗi ràng buộc trung lập.
- `get_database()`: facade `Database` cho code mới.
- `BACKEND_NAME`: luôn là "postgres".
"""
from .base import Database, StorageBackend
from .db import BACKEND_NAME, IntegrityError, get_db_path, open_db

_db_singleton = None  # type: ignore[var-annotated]


def get_database() -> Database:
    """Facade `Database` dùng chung (lazy singleton, bind vào backend đang chọn)."""
    global _db_singleton
    if _db_singleton is None:
        _db_singleton = Database(open_db)
    return _db_singleton


__all__ = [
    "open_db",
    "get_db_path",
    "IntegrityError",
    "BACKEND_NAME",
    "Database",
    "StorageBackend",
    "get_database",
]
