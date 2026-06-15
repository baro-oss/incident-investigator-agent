"""
Migration: RBAC layer — Phase 5 Ngày 22.

Idempotent — an toàn khi chạy lại nhiều lần.
  python data/migrate_rbac.py [path/to/investigation.db]
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _existing_tables(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def migrate(db_path: str) -> None:
    if os.environ.get("DB_BACKEND", "sqlite").lower() == "postgres":
        print("migrate_rbac: PG backend — deploy fresh, skipping SQLite-only migration.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    existing = _existing_tables(conn)
    now = _now()

    # 1. users
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_root       INTEGER NOT NULL DEFAULT 0,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL
        )
    """)

    # 2. roles
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            is_system   INTEGER NOT NULL DEFAULT 0
        )
    """)

    # 3. permissions catalog
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            key         TEXT PRIMARY KEY,
            description TEXT NOT NULL DEFAULT ''
        )
    """)

    # 4. role_permissions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id        TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_key TEXT NOT NULL REFERENCES permissions(key) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_key)
        )
    """)

    # 5. project_groups
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_groups (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL
        )
    """)

    # 6. project_group_members
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_group_members (
            group_id    TEXT NOT NULL REFERENCES project_groups(id) ON DELETE CASCADE,
            project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            PRIMARY KEY (group_id, project_id)
        )
    """)

    # 7. role_assignments
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_assignments (
            id               TEXT PRIMARY KEY,
            user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id          TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            scope_type       TEXT NOT NULL DEFAULT 'global',
            scope_group_id   TEXT,
            scope_project_id TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_role_assignments_user ON role_assignments (user_id)"
    )

    # 8. api_tokens
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash  TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            last_used   TEXT
        )
    """)

    conn.commit()
    print("  Tạo 6 bảng RBAC + api_tokens OK")

    # ── Seed permissions catalog ──────────────────────────────────────────────
    PERMISSION_CATALOG = {
        "investigation.view":    "Xem danh sách và chi tiết điều tra",
        "investigation.trigger": "Kích hoạt điều tra mới",
        "investigation.replay":  "Phát lại điều tra cũ",
        "observability.view":    "Xem eval, cost, health dashboard",
        "project.view":          "Xem danh sách project",
        "project.manage":        "Tạo/sửa/xóa project và services",
        "mcp.manage":            "Quản lý MCP server registry",
        "channel.manage":        "Quản lý alert channels",
        "llm.manage":            "Cấu hình LLM per project (nhạy cảm)",
        "user.manage":           "Tạo/sửa/xóa user",
        "role.manage":           "Tạo/sửa role và gán quyền",
        "group.manage":          "Quản lý project groups",
    }
    for key, desc in PERMISSION_CATALOG.items():
        conn.execute(
            "INSERT OR IGNORE INTO permissions (key, description) VALUES (?, ?)",
            (key, desc),
        )

    # ── Seed 3 system roles ───────────────────────────────────────────────────
    ROLE_SEEDS = {
        "admin": {
            "name": "Admin",
            "description": "Toàn quyền hệ thống",
            "permissions": list(PERMISSION_CATALOG.keys()),
        },
        "operator": {
            "name": "Operator",
            "description": "Điều tra và quan sát",
            "permissions": [
                "investigation.view", "investigation.trigger", "investigation.replay",
                "observability.view", "project.view",
            ],
        },
        "viewer": {
            "name": "Viewer",
            "description": "Chỉ xem",
            "permissions": ["investigation.view", "project.view"],
        },
    }
    for rid, rd in ROLE_SEEDS.items():
        conn.execute(
            "INSERT OR IGNORE INTO roles (id, name, description, is_system) VALUES (?, ?, ?, 1)",
            (rid, rd["name"], rd["description"]),
        )
        for pkey in rd["permissions"]:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_key) VALUES (?, ?)",
                (rid, pkey),
            )

    conn.commit()
    print("  Seed 12 permissions + 3 system roles OK")

    # ── Bootstrap root user từ env ────────────────────────────────────────────
    root_username = os.getenv("ROOT_USERNAME", "root")
    root_password = os.getenv("ROOT_PASSWORD", "")

    if root_password:
        existing_root = conn.execute(
            "SELECT id FROM users WHERE username=?", (root_username,)
        ).fetchone()
        if not existing_root:
            uid = str(uuid.uuid4())
            salt = os.urandom(16)
            key = hashlib.pbkdf2_hmac("sha256", root_password.encode(), salt, 100_000)
            phash = salt.hex() + ":" + key.hex()
            conn.execute(
                "INSERT INTO users (id, username, password_hash, is_root, is_active, created_at) "
                "VALUES (?, ?, ?, 1, 1, ?)",
                (uid, root_username, phash, now),
            )
            conn.commit()
            print(f"  Root user '{root_username}' tạo mới OK")
        else:
            print(f"  Root user '{root_username}' đã tồn tại — giữ nguyên")
    else:
        print("  ROOT_PASSWORD không set — bỏ qua bootstrap root user")
        print("  (Set ROOT_PASSWORD env trước khi chạy để tạo root user)")

    conn.close()
    print(f"Migration RBAC OK: {db_path}")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/investigation.db"
    migrate(db_path)
