"""Postgres backend — STUB (Tier-2, chưa wire).

Mục đích: CHỨNG MINH seam. Set `DB_BACKEND=postgres` → dispatcher (db.py) trỏ
vào đây thay vì sqlite_backend, không sửa engine/tools.

Hiện thực thật là việc Tier-2 (xem `docs/11-roadmap-phase-5.md` mục Future):
- psycopg shim cho hợp đồng connection trong `base.py` (qmark `?` → `%s`,
  cursor.fetchall→dict, lastrowid/rowcount)
- port ~12 `datetime(...)` + 8 UPSERT + DDL `schema.sql` sang dialect Postgres
- integration test trên Postgres thật
"""
from __future__ import annotations

import os
from typing import Optional

name = "postgres"


class IntegrityError(Exception):
    """Placeholder để `from agent.storage import IntegrityError` không vỡ
    khi backend chưa wire. Tier-2 sẽ map sang psycopg.errors.IntegrityError."""


def db_path() -> str:
    return os.environ.get("DATABASE_URL", "")


def connect(path: Optional[str] = None):
    raise NotImplementedError(
        "Backend 'postgres' chưa wire (Tier-2). Hiện chỉ hỗ trợ DB_BACKEND=sqlite. "
        "Xem docs/11-roadmap-phase-5.md (mục Future) để biết phạm vi migration thật."
    )
