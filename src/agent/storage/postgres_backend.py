"""Postgres backend — Tier-2 (Phase 11, Ngày 56).

Surface giống sqlite_backend để mọi caller không đổi gì:
    name, IntegrityError, db_path(), connect()

Shim đảm bảo:
  - Placeholder qmark ? → %s (psycopg3)
  - Literal % trong LIKE escaped → %%
  - INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
  - RETURNING id cho SERIAL tables → lastrowid
  - Row hỗ trợ key + index access + dict(row)
  - Connection pool (psycopg_pool) — không mở TCP mỗi query

Cài thêm: pip install '.[postgres]'  (psycopg[binary] + psycopg_pool)
"""
from __future__ import annotations

import os
import re
from typing import Any, List, Optional

import psycopg
import psycopg_pool
from psycopg.rows import dict_row

# ── Surface (phải khớp sqlite_backend) ───────────────────────────────────────

name = "postgres"
IntegrityError = psycopg.errors.IntegrityError

# ── Bảng có SERIAL id (auto-increment) — dùng RETURNING id để lấy lastrowid ──
# Chỉ những bảng này mới inject RETURNING id. Các bảng có TEXT PK (users, roles,
# projects...) không cần — lastrowid trả None và caller không dùng.
_SERIAL_ID_TABLES = frozenset({
    "logs",
    "metrics",
    "deploys",
    "trace_events",
    "mcp_servers",
    "eval_results",
    "investigation_patterns",
})

# ── Connection pool (module-level, lazy init) ─────────────────────────────────
_pool: Optional[psycopg_pool.ConnectionPool] = None


def _get_pool() -> psycopg_pool.ConnectionPool:
    global _pool
    if _pool is None:
        url = db_path()
        if not url:
            raise RuntimeError(
                "DATABASE_URL chưa set. "
                "Ví dụ: DATABASE_URL=postgresql://agent:pass@localhost/investigation"
            )
        _pool = psycopg_pool.ConnectionPool(
            url,
            min_size=1,
            max_size=10,
            open=True,
        )
    return _pool


def db_path() -> str:
    return os.environ.get("DATABASE_URL", "")


# ── SQL translation ───────────────────────────────────────────────────────────

def _translate(sql: str) -> str:
    """Dịch SQLite SQL dialect → PostgreSQL (psycopg3).

    Thứ tự quan trọng:
    1. Escape literal % (LIKE pattern) → %% TRƯỚC khi thay ? → %s
       (nếu đảo: % vừa mới thay trở thành %% → thành %%%s)
    2. ? → %s
    3. INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
    """
    sql = sql.replace("%", "%%").replace("?", "%s")
    if re.search(r"INSERT\s+OR\s+IGNORE\b", sql, re.IGNORECASE):
        sql = re.sub(r"INSERT\s+OR\s+IGNORE\b", "INSERT", sql, flags=re.IGNORECASE)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return sql


def _extract_table(sql: str) -> Optional[str]:
    """Tách tên bảng từ câu INSERT (đã qua _translate)."""
    m = re.search(r"INSERT\s+INTO\s+(\w+)", sql, re.IGNORECASE)
    return m.group(1).lower() if m else None


# ── Row wrapper ───────────────────────────────────────────────────────────────

class _PGRow:
    """Dict-row hỗ trợ key-access, index-access và dict(row) — tương tự sqlite3.Row."""

    __slots__ = ("_d", "_keys")

    def __init__(self, d: dict) -> None:
        self._d = d
        self._keys: List[str] = list(d.keys())

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._d[self._keys[key]]
        return self._d[key]

    def keys(self) -> List[str]:  # cho dict(row) hoạt động
        return self._keys

    def __iter__(self):
        return iter(self._d.values())

    def __repr__(self) -> str:
        return repr(self._d)


# ── Cursor wrapper ────────────────────────────────────────────────────────────

class _PGCursor:
    """Wraps psycopg cursor với API giống sqlite3 cursor."""

    __slots__ = ("_cur", "lastrowid")

    def __init__(self, cur: Any, lastrowid: Optional[int] = None) -> None:
        self._cur = cur
        self.lastrowid = lastrowid  # None khi không phải SERIAL table

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def fetchall(self) -> List[_PGRow]:
        rows = self._cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return [_PGRow(r) for r in rows]
        return []  # cursor đã consumed (vd sau RETURNING fetchone)

    def fetchone(self) -> Optional[_PGRow]:
        row = self._cur.fetchone()
        if row is None:
            return None
        return _PGRow(row) if isinstance(row, dict) else row


# ── Connection wrapper ────────────────────────────────────────────────────────

class _PGConnection:
    """Wraps psycopg connection với API giống sqlite3 connection.

    .close() trả connection về pool thay vì đóng thật.
    """

    __slots__ = ("_conn", "_pool")

    def __init__(self, pg_conn: Any, pool: Any) -> None:
        self._conn = pg_conn
        self._pool = pool

    def execute(self, sql: str, params: Any = ()) -> _PGCursor:
        """Thực thi 1 câu SQL. Với SERIAL tables + INSERT → inject RETURNING id."""
        sql = _translate(sql)
        table = _extract_table(sql)
        use_returning = bool(
            table
            and table in _SERIAL_ID_TABLES
            and sql.strip().upper().startswith("INSERT")
        )
        if use_returning:
            sql_r = sql.rstrip().rstrip(";") + " RETURNING id"
            cur = self._conn.cursor(row_factory=dict_row)
            cur.execute(sql_r, params or None)
            row = cur.fetchone()
            lastrowid = row["id"] if row else None
            return _PGCursor(cur, lastrowid=lastrowid)

        cur = self._conn.cursor(row_factory=dict_row)
        cur.execute(sql, params or None)
        return _PGCursor(cur)

    def executemany(self, sql: str, params_list: Any) -> None:
        """Bulk insert — placeholder và dialect đã dịch."""
        sql = _translate(sql)
        with self._conn.cursor() as cur:
            cur.executemany(sql, list(params_list))

    def executescript(self, script: str) -> None:
        """Thực thi DDL multi-statement (tương đương sqlite3.executescript).

        Split theo `;`, bỏ dòng comment `--`, bỏ block rỗng.
        Commit sau khi tất cả statements chạy xong.
        """
        with self._conn.cursor() as cur:
            for raw in script.split(";"):
                lines = [
                    ln for ln in raw.splitlines()
                    if not ln.strip().startswith("--")
                ]
                stmt = "\n".join(lines).strip()
                if stmt:
                    cur.execute(stmt)
        self._conn.commit()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        """Trả connection về pool (không đóng thật TCP connection)."""
        self._pool.putconn(self._conn)

    def __enter__(self) -> "_PGConnection":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def connect(path: Optional[str] = None) -> _PGConnection:  # noqa: ARG001
    """Lấy connection từ pool. Gọi .close() để trả về pool."""
    pool = _get_pool()
    pg_conn = pool.getconn()
    return _PGConnection(pg_conn, pool)
