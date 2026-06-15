"""
Ngày 53 — eval_results: thêm specificity_score + prior_flag.

Idempotent: ALTER TABLE bọc trong try/except (SQLite không hỗ trợ IF NOT EXISTS
cho ADD COLUMN). Chạy an toàn nhiều lần.
"""
from __future__ import annotations
import pathlib, sqlite3, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from agent.storage.db import get_db_path


def run() -> None:
    path = get_db_path()
    conn = sqlite3.connect(path)
    added = []
    for stmt, name in [
        ("ALTER TABLE eval_results ADD COLUMN specificity_score REAL", "specificity_score"),
        ("ALTER TABLE eval_results ADD COLUMN prior_flag INTEGER NOT NULL DEFAULT 0", "prior_flag"),
    ]:
        try:
            conn.execute(stmt)
            added.append(name)
        except sqlite3.OperationalError:
            pass  # already exists
    conn.commit()
    conn.close()
    if added:
        print(f"migrate_day53: added columns {added}")
    else:
        print("migrate_day53: columns already exist — OK")


if __name__ == "__main__":
    run()
