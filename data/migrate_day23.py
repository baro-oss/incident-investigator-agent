"""Migration Ngày 23 — investigation_feedback table (idempotent)."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.storage import open_db

def migrate():
    conn = open_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investigation_feedback (
            investigation_id TEXT PRIMARY KEY,
            score            INTEGER NOT NULL,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("OK: investigation_feedback table ready")

if __name__ == "__main__":
    migrate()
