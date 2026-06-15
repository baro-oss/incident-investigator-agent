"""
Migration Day 51 — bảng service_repos.

Lưu mapping metadata service → repo ngoài (GitHub/GitLab).
Chỉ metadata; source code KHÔNG lưu trong hệ thống này.
Idempotent — chạy nhiều lần không bị lỗi.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.storage.db import open_db


def migrate() -> None:
    conn = open_db()

    # Bảng mapping service → repo ngoài (chỉ metadata)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS service_repos (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id     TEXT    NOT NULL DEFAULT 'default',
            service        TEXT    NOT NULL,
            provider       TEXT    NOT NULL DEFAULT 'github',  -- github | gitlab | bitbucket
            repo_url       TEXT    NOT NULL,
            default_branch TEXT    NOT NULL DEFAULT 'main',
            subpath        TEXT    NOT NULL DEFAULT '',        -- subdir trong mono-repo
            created_at     TEXT    NOT NULL,
            updated_at     TEXT    NOT NULL,
            UNIQUE(project_id, service)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_service_repos_project
        ON service_repos (project_id)
    """)

    conn.commit()
    conn.close()
    print("migrate_day51: service_repos OK")


if __name__ == "__main__":
    migrate()
