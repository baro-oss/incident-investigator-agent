"""
Migration idempotent: tạo bảng hypothesis_catalog cho OPS1 (Day 54).
Chạy an toàn nhiều lần — dùng IF NOT EXISTS / try-except.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.storage.db import open_db


def migrate():
    with open_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS hypothesis_catalog (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                domain          TEXT    NOT NULL DEFAULT 'microservice',
                project_id      TEXT    NOT NULL DEFAULT 'default',
                tag             TEXT    NOT NULL,
                content         TEXT    NOT NULL DEFAULT '',
                keywords        TEXT    NOT NULL DEFAULT '[]',
                relevant_tools  TEXT    NOT NULL DEFAULT '[]',
                confirm_kws     TEXT    NOT NULL DEFAULT '[]',
                rule_out_kws    TEXT    NOT NULL DEFAULT '[]',
                confirm_conf    TEXT    NOT NULL DEFAULT 'medium',
                root_cause_type TEXT    NOT NULL DEFAULT '',
                created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(domain, project_id, tag)
            )
        """)
        db.commit()
    print("migrate_day54: hypothesis_catalog OK")


if __name__ == "__main__":
    migrate()
