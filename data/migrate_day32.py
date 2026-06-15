"""
Migration Ngày 32: Proactive monitoring.

Thêm:
  - Bảng scheduled_triggers (cron-style per-project trigger)
  - Cột alerted_at vào investigation_patterns (dedup recurring alerts)

Chạy: python data/migrate_day32.py
Idempotent — an toàn khi chạy lại.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "investigation.db"


def _existing_columns(conn: sqlite3.Connection, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def migrate(db_path: str = str(DB_PATH)) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    now = datetime.now(timezone.utc).isoformat()

    # 1. Bảng scheduled_triggers
    if not _table_exists(conn, "scheduled_triggers"):
        conn.execute("""
            CREATE TABLE scheduled_triggers (
                id           TEXT PRIMARY KEY,
                project_id   TEXT NOT NULL DEFAULT 'default',
                service      TEXT NOT NULL,
                scenario     TEXT NOT NULL DEFAULT 'scenario1',
                interval_min INTEGER NOT NULL DEFAULT 60,
                enabled      INTEGER NOT NULL DEFAULT 1,
                last_run_at  TEXT,
                next_run_at  TEXT NOT NULL,
                created_at   TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sched_project ON scheduled_triggers (project_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sched_next ON scheduled_triggers (next_run_at)"
        )
        print("  CREATE TABLE scheduled_triggers OK")
    else:
        print("  scheduled_triggers: already exists")

    # 2. Cột alerted_at vào investigation_patterns (dedup recurring alert push)
    if "alerted_at" not in _existing_columns(conn, "investigation_patterns"):
        conn.execute(
            "ALTER TABLE investigation_patterns ADD COLUMN alerted_at TEXT"
        )
        print("  ALTER TABLE investigation_patterns ADD COLUMN alerted_at")
    else:
        print("  investigation_patterns.alerted_at: already exists")

    conn.commit()
    conn.close()
    print(f"Migration Ngày 32 OK — {db_path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else str(DB_PATH)
    migrate(path)
