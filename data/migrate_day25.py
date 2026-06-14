#!/usr/bin/env python3
"""
Migration Ngày 25: thêm auth_type + auth_config vào mcp_servers.

Idempotent — chạy nhiều lần an toàn.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.storage.db import open_db


def migrate():
    conn = open_db()

    # Kiểm tra cột đã tồn tại chưa
    cols = {row[1] for row in conn.execute("PRAGMA table_info(mcp_servers)").fetchall()}

    added = []
    if "auth_type" not in cols:
        conn.execute("ALTER TABLE mcp_servers ADD COLUMN auth_type TEXT NOT NULL DEFAULT 'none'")
        added.append("auth_type")
    if "auth_config" not in cols:
        conn.execute("ALTER TABLE mcp_servers ADD COLUMN auth_config TEXT NOT NULL DEFAULT '{}'")
        added.append("auth_config")

    conn.commit()
    conn.close()

    if added:
        print(f"Migration OK: thêm cột {added} vào mcp_servers")
    else:
        print("Migration OK: các cột đã tồn tại (no-op)")


if __name__ == "__main__":
    migrate()
