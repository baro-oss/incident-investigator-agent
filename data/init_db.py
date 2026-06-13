"""Khởi tạo SQLite DB từ schema.sql. Chạy một lần trước khi seed data."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCHEMA = Path(__file__).parent / "schema.sql"


def init_db(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA.read_text())
    conn.commit()
    conn.close()
    print(f"DB initialized: {path.resolve()}")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/investigation.db"
    init_db(db_path)
