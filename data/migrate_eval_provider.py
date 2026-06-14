"""Migration idempotent — thêm cột provider, model vào eval_results.

Phase 5 Ngày 21: real-LLM eval cần ghi lại LLM nào chạy (anthropic/gemini/...)
để đọc số liệu thật + calibration phân theo provider.

Chạy: python data/migrate_eval_provider.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.storage import open_db


def _columns(conn, table: str):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate() -> None:
    conn = open_db()
    cols = _columns(conn, "eval_results")
    added = []
    if "provider" not in cols:
        conn.execute("ALTER TABLE eval_results ADD COLUMN provider TEXT")
        added.append("provider")
    if "model" not in cols:
        conn.execute("ALTER TABLE eval_results ADD COLUMN model TEXT")
        added.append("model")
    conn.commit()
    conn.close()
    print(f"[migrate_eval_provider] cột thêm: {added or '(đã có sẵn — no-op)'}")


if __name__ == "__main__":
    migrate()
