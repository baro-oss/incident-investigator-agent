"""SQLite connection helper — một điểm duy nhất mở DB."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def get_db_path() -> str:
    return os.environ.get("DB_PATH", "data/investigation.db")


def open_db(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
