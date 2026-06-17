"""Khởi tạo DB Postgres từ schema file.

  DB_BACKEND=postgres DATABASE_URL=postgresql://user:pass@host/db python data/init_db.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCHEMA_POSTGRES = Path(__file__).parent / "schema_postgres.sql"


def init_db() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from agent.storage.db import open_db  # type: ignore
    from datetime import datetime, timezone

    conn = open_db()
    conn.executescript(SCHEMA_POSTGRES.read_text())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO projects (id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (id) DO NOTHING",
        ("default", "Default Project", "Dự án mặc định — backward compat", now, now),
    )
    conn.commit()
    conn.close()
    url = os.environ.get("DATABASE_URL", "")
    display = re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", url)
    print(f"[postgres] DB initialized: {display}")


if __name__ == "__main__":
    init_db()
