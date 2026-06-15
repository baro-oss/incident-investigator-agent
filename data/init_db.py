"""Khởi tạo DB từ schema file. Backend-aware (sqlite / postgres).

  # SQLite (default)
  python data/init_db.py [path/to/db]

  # PostgreSQL
  DB_BACKEND=postgres DATABASE_URL=postgresql://user:pass@host/db python data/init_db.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCHEMA_SQLITE = Path(__file__).parent / "schema.sql"
SCHEMA_POSTGRES = Path(__file__).parent / "schema_postgres.sql"


def init_db(db_path: str | None = None) -> None:
    backend = os.environ.get("DB_BACKEND", "sqlite").lower()
    if backend == "postgres":
        _init_postgres()
    else:
        _init_sqlite(db_path or "data/investigation.db")


def _init_sqlite(db_path: str) -> None:
    import sqlite3
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQLITE.read_text())
    conn.commit()
    conn.close()
    print(f"[sqlite] DB initialized: {path.resolve()}")


def _init_postgres() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from agent.storage.db import open_db  # type: ignore
    conn = open_db()
    conn.executescript(SCHEMA_POSTGRES.read_text())
    conn.close()
    url = os.environ.get("DATABASE_URL", "")
    # Redact password từ URL khi in
    import re
    display = re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", url)
    print(f"[postgres] DB initialized: {display}")


if __name__ == "__main__":
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    init_db(db_arg)
