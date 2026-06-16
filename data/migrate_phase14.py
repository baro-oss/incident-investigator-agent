#!/usr/bin/env python3
"""
Migration Phase 14 — UX/DX batch:

  #4  project_services.description  — mô tả ngắn để agent có ngữ cảnh suy luận.
  #3  mcp_servers UNIQUE(url) → UNIQUE(url, project_id) — 1 URL đăng ký cho nhiều project.

Idempotent — chạy nhiều lần an toàn.

  python data/migrate_phase14.py

PG = deploy fresh (schema_postgres.sql đã đúng) → migration này skip trên Postgres.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _columns(conn, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _has_single_url_unique(conn) -> bool:
    """True nếu mcp_servers còn unique index trên đúng 1 cột [url] (legacy)."""
    for idx in conn.execute("PRAGMA index_list(mcp_servers)").fetchall():
        # index_list row: (seq, name, unique, origin, partial)
        name, is_unique = idx[1], idx[2]
        if not is_unique:
            continue
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info('{name}')").fetchall()]
        if cols == ["url"]:
            return True
    return False


def migrate():
    if os.environ.get("DB_BACKEND", "sqlite").lower() == "postgres":
        print("migrate_phase14: PG backend — deploy fresh, skipping SQLite-only migration.")
        return

    import sqlite3
    db_path = os.environ.get("DB_PATH", "data/investigation.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")  # tắt khi rebuild bảng

    # ── #4: project_services.description ──────────────────────────────────────
    if "description" not in _columns(conn, "project_services"):
        conn.execute(
            "ALTER TABLE project_services ADD COLUMN description TEXT NOT NULL DEFAULT ''"
        )
        print("  ALTER TABLE project_services ADD COLUMN description")
    else:
        print("  project_services.description đã tồn tại (no-op)")

    # ── #3: mcp_servers UNIQUE(url) → UNIQUE(url, project_id) ─────────────────
    # Đảm bảo project_id tồn tại (migrate_projects thường đã thêm)
    if "project_id" not in _columns(conn, "mcp_servers"):
        conn.execute(
            "ALTER TABLE mcp_servers ADD COLUMN project_id TEXT NOT NULL DEFAULT 'default'"
        )
        print("  ALTER TABLE mcp_servers ADD COLUMN project_id")

    if _has_single_url_unique(conn):
        # SQLite không drop được column-level UNIQUE → rebuild bảng.
        cols = _columns(conn, "mcp_servers")
        # Tập cột đầy đủ mà code mong đợi (giữ data hiện có)
        full = ["id", "name", "url", "description", "enabled",
                "created_at", "updated_at", "auth_type", "auth_config", "project_id"]
        keep = [c for c in full if c in cols]
        col_list = ", ".join(keep)

        conn.execute("ALTER TABLE mcp_servers RENAME TO mcp_servers_old")
        conn.execute("""
            CREATE TABLE mcp_servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                url         TEXT    NOT NULL,
                description TEXT    NOT NULL DEFAULT '',
                enabled     INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL,
                auth_type   TEXT    NOT NULL DEFAULT 'none',
                auth_config TEXT    NOT NULL DEFAULT '{}',
                project_id  TEXT    NOT NULL DEFAULT 'default'
            )
        """)
        conn.execute(
            f"INSERT INTO mcp_servers ({col_list}) SELECT {col_list} FROM mcp_servers_old"
        )
        conn.execute("DROP TABLE mcp_servers_old")
        print("  REBUILD mcp_servers (bỏ UNIQUE column-level trên url)")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_servers_enabled ON mcp_servers (enabled)")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mcp_url_project "
        "ON mcp_servers (url, project_id)"
    )
    print("  UNIQUE INDEX idx_mcp_url_project (url, project_id) đảm bảo tồn tại")

    conn.commit()
    conn.close()
    print("migrate_phase14 OK")


if __name__ == "__main__":
    migrate()
