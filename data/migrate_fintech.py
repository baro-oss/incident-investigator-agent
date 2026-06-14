"""Migration idempotent: tạo fintech tables (ft_*)."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.storage.db import open_db

STEPS = [
    ("ft_transactions", """
        CREATE TABLE IF NOT EXISTS ft_transactions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            scenario     TEXT NOT NULL,
            merchant_id  TEXT NOT NULL,
            channel      TEXT NOT NULL,
            amount       REAL NOT NULL,
            status       TEXT NOT NULL DEFAULT 'success',
            error_type   TEXT,
            processor_id TEXT,
            is_baseline  INTEGER NOT NULL DEFAULT 0
        )
    """),
    ("idx_ft_tx_scenario", "CREATE INDEX IF NOT EXISTS idx_ft_tx_scenario ON ft_transactions (scenario, merchant_id, timestamp)"),
    ("idx_ft_tx_channel",  "CREATE INDEX IF NOT EXISTS idx_ft_tx_channel  ON ft_transactions (scenario, channel, timestamp)"),

    ("ft_revenue", """
        CREATE TABLE IF NOT EXISTS ft_revenue (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT NOT NULL,
            scenario         TEXT NOT NULL,
            channel          TEXT NOT NULL,
            revenue          REAL NOT NULL,
            transaction_count INTEGER NOT NULL,
            refund_amount    REAL NOT NULL DEFAULT 0,
            is_baseline      INTEGER NOT NULL DEFAULT 0
        )
    """),
    ("idx_ft_rev_scenario", "CREATE INDEX IF NOT EXISTS idx_ft_rev_scenario ON ft_revenue (scenario, channel, timestamp)"),

    ("ft_merchants", """
        CREATE TABLE IF NOT EXISTS ft_merchants (
            id       TEXT NOT NULL,
            scenario TEXT NOT NULL,
            name     TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'retail',
            status   TEXT NOT NULL DEFAULT 'active',
            notes    TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (id, scenario)
        )
    """),

    ("ft_settlements", """
        CREATE TABLE IF NOT EXISTS ft_settlements (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT NOT NULL,
            scenario         TEXT NOT NULL,
            merchant_id      TEXT NOT NULL,
            amount           REAL NOT NULL,
            processing_time_s REAL NOT NULL,
            is_baseline      INTEGER NOT NULL DEFAULT 0
        )
    """),
    ("idx_ft_settle_scenario", "CREATE INDEX IF NOT EXISTS idx_ft_settle_scenario ON ft_settlements (scenario, merchant_id, timestamp)"),
]

def run():
    conn = open_db()
    for name, sql in STEPS:
        try:
            conn.execute(sql)
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  skip {name}: {e}")
    conn.commit()
    conn.close()
    print("migrate_fintech: done")

if __name__ == "__main__":
    run()
