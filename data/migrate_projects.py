"""
Migration: thêm project isolation layer.

Chạy một lần trên DB hiện có:
  python data/migrate_projects.py

Idempotent — an toàn khi chạy lại.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _existing_columns(conn: sqlite3.Connection, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate(db_path: str) -> None:
    if os.environ.get("DB_BACKEND", "sqlite").lower() == "postgres":
        print("migrate_projects: PG backend — deploy fresh, skipping SQLite-only migration.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    now = datetime.now(timezone.utc).isoformat()

    # 1. Bảng projects (CREATE IF NOT EXISTS đã có trong schema.sql)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)

    # 2. Bảng project_services
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_services (
            project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            service     TEXT NOT NULL,
            PRIMARY KEY (project_id, service)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_services ON project_services (project_id)"
    )

    # 3. Thêm project_id vào mcp_servers (nếu chưa có)
    if "project_id" not in _existing_columns(conn, "mcp_servers"):
        conn.execute(
            "ALTER TABLE mcp_servers ADD COLUMN project_id TEXT NOT NULL DEFAULT 'default'"
        )
        print("  ALTER TABLE mcp_servers ADD COLUMN project_id")

    # 4. Thêm project_id vào trace_events (nếu chưa có)
    if "project_id" not in _existing_columns(conn, "trace_events"):
        conn.execute(
            "ALTER TABLE trace_events ADD COLUMN project_id TEXT NOT NULL DEFAULT 'default'"
        )
        print("  ALTER TABLE trace_events ADD COLUMN project_id")

    # 5. Bảng project_alert_channels
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_alert_channels (
            project_id  TEXT    NOT NULL,
            channel     TEXT    NOT NULL,
            config      TEXT    NOT NULL DEFAULT '{}',
            enabled     INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (project_id, channel),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_alert_channels ON project_alert_channels (project_id)"
    )

    # 6. Seed default project (INSERT OR IGNORE — safe to run nhiều lần)
    conn.execute("""
        INSERT OR IGNORE INTO projects (id, name, description, created_at, updated_at)
        VALUES ('default', 'Default Project', 'Dự án mặc định — backward compat', ?, ?)
    """, (now, now))

    # 7. Per-project LLM config (thêm cột vào projects)
    existing_proj_cols = _existing_columns(conn, "projects")
    for col, typedef in [
        ("llm_provider", "TEXT"),
        ("llm_model",    "TEXT"),
        ("llm_config",   "TEXT NOT NULL DEFAULT '{}'"),
    ]:
        if col not in existing_proj_cols:
            conn.execute(f"ALTER TABLE projects ADD COLUMN {col} {typedef}")
            print(f"  ALTER TABLE projects ADD COLUMN {col}")

    # 8. Bảng eval_results
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       TEXT    NOT NULL,
            scenario     TEXT    NOT NULL,
            run_number   INTEGER NOT NULL,
            correct      INTEGER NOT NULL,
            confidence   TEXT,
            recall_at_1  INTEGER,
            steps_taken  INTEGER,
            hallucination INTEGER NOT NULL DEFAULT 0,
            token_total  INTEGER NOT NULL DEFAULT 0,
            elapsed_s    REAL,
            created_at   TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_eval_results ON eval_results (run_id, scenario)"
    )

    # 9. Bảng investigation_patterns (long-term memory)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investigation_patterns (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL DEFAULT 'default',
            service         TEXT    NOT NULL,
            error_pattern   TEXT    NOT NULL,
            tool_sequence   TEXT    NOT NULL,
            root_cause_type TEXT    NOT NULL,
            avg_steps       REAL    NOT NULL DEFAULT 0,
            count           INTEGER NOT NULL DEFAULT 1,
            updated_at      TEXT    NOT NULL,
            UNIQUE(project_id, service, error_pattern)
        )
    """)

    # 10. Bảng investigation_queue (B3 — Phase 6 Ngày 29, in-process queue persist)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investigation_queue (
            id          TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL DEFAULT 'default',
            payload     TEXT NOT NULL,
            priority    INTEGER NOT NULL DEFAULT 0,
            status      TEXT NOT NULL DEFAULT 'pending',
            enqueued_at TEXT NOT NULL,
            started_at  TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_inv_queue_status ON investigation_queue (status, enqueued_at)"
    )

    conn.commit()
    conn.close()
    print(f"Migration OK: {db_path}")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/investigation.db"
    migrate(db_path)
