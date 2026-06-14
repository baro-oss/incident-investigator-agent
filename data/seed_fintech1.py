"""
Sinh data KB-F1: Payment processor timeout.

Đường điều tra lý tưởng:
  ft_transactions → error_type="ProcessorTimeoutError" tập trung ở credit_card từ 10:15
  ft_revenue      → credit_card revenue giảm 60% từ 10:15 (debit/e_wallet bình thường)
  ft_merchants    → tất cả merchants healthy (tín hiệu âm: không phải merchant bug)
  ft_settlements  → processing_time bình thường (tín hiệu âm: không phải settlement lag)
  → Verdict: proc-alpha timeout → credit_card failed; debit_card/e_wallet KHÔNG bị ảnh hưởng

Tín hiệu âm tính QUAN TRỌNG:
  - debit_card và e_wallet transactions KHÔNG có ProcessorTimeoutError
  - Tất cả 4 merchants đều status='active' và không có notes bất thường
  - ft_settlements processing_time chỉ tăng nhẹ (12s → 14s), không phải nguyên nhân
  - 10:00-10:14: mọi thứ bình thường (warm-up trước incident)
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

# ── Thêm src vào path để import open_db ──────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agent.storage.db import open_db  # noqa: E402

# ── Tham số ───────────────────────────────────────────────────────────────────

SCENARIO = "fintech1"
DATE = "2024-01-16"

# Mốc thời gian
BASELINE_START_HOUR = 9       # 09:00 — baseline window
WINDOW_START_HOUR = 10        # 10:00 — investigation window bắt đầu
WINDOW_END_HOUR = 11          # 11:00 — investigation window kết thúc
INCIDENT_START = (10, 15)     # 10:15 — incident bắt đầu

# Khối lượng traffic
TX_PER_MIN_NORMAL = 200       # transactions/phút bình thường
TX_PER_MIN_INCIDENT = 185     # giảm nhẹ khi có lỗi (retry storms ít đi)

# Phân phối channel (credit/debit/ewallet)
CHANNEL_WEIGHTS = [0.50, 0.30, 0.20]   # credit_card, debit_card, e_wallet

# Tỷ lệ lỗi
NOISE_FAIL_RATE = 0.01        # 1% lỗi baseline (tất cả channels)
PROC_ALPHA_FAIL_RATE = 0.65   # 65% credit_card qua proc-alpha fail sau 10:15

# Processors
PROCESSORS = {
    "credit_card": ["proc-alpha", "proc-beta"],   # credit_card dùng cả 2; proc-alpha bị lỗi
    "debit_card": ["proc-gamma"],
    "e_wallet": ["proc-delta"],
}
PROC_ALPHA_SHARE = 0.75       # 75% credit_card đi qua proc-alpha

# Merchants
MERCHANTS = ["merch-a", "merch-b", "merch-c", "merch-d"]

# Amounts (rough range per channel)
AMOUNT_RANGE = {
    "credit_card": (50, 2000),
    "debit_card": (20, 500),
    "e_wallet": (10, 200),
}

# Revenue baseline per channel (VND k/min)
REVENUE_BASELINE = {
    "credit_card": 45000,
    "debit_card": 20000,
    "e_wallet": 15000,
}

CHANNELS = ["credit_card", "debit_card", "e_wallet"]

random.seed(42)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_dt(hour: int, minute: int, sec: int = 0) -> datetime:
    return datetime(2024, 1, 16, hour, minute, sec, tzinfo=timezone.utc)


def fmt(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def incident_dt() -> datetime:
    return make_dt(*INCIDENT_START)


def minutes_range(start_hour: int, end_hour: int):
    cur = make_dt(start_hour, 0)
    end = make_dt(end_hour, 0)
    while cur < end:
        yield cur
        cur += timedelta(minutes=1)


def is_incident(dt: datetime) -> bool:
    return dt >= incident_dt()


def pick_processor(channel: str, is_proc_alpha_tx: bool = False) -> str:
    procs = PROCESSORS[channel]
    if channel == "credit_card" and is_proc_alpha_tx:
        return "proc-alpha"
    return random.choice(procs)


# ── ft_transactions ───────────────────────────────────────────────────────────

def generate_transactions() -> List[tuple]:
    """
    Columns: timestamp, scenario, merchant_id, channel, amount, status,
             error_type, processor_id, is_baseline
    """
    rows = []

    # Baseline window: 09:00 - 10:00
    for minute_dt in minutes_range(BASELINE_START_HOUR, WINDOW_START_HOUR):
        for _ in range(TX_PER_MIN_NORMAL):
            sec = random.randint(0, 59)
            ts = fmt(minute_dt + timedelta(seconds=sec))
            channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
            merchant = random.choice(MERCHANTS)
            amount = round(random.uniform(*AMOUNT_RANGE[channel]), 2)
            proc = random.choice(PROCESSORS[channel])

            if random.random() < NOISE_FAIL_RATE:
                rows.append((ts, SCENARIO, merchant, channel, amount,
                             "failed", "PaymentDeclined", proc, 1))
            else:
                rows.append((ts, SCENARIO, merchant, channel, amount,
                             "success", None, proc, 1))

    # Investigation window: 10:00 - 11:00
    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        under_incident = is_incident(minute_dt)
        tx_count = TX_PER_MIN_INCIDENT if under_incident else TX_PER_MIN_NORMAL

        for _ in range(tx_count):
            sec = random.randint(0, 59)
            ts = fmt(minute_dt + timedelta(seconds=sec))
            channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
            merchant = random.choice(MERCHANTS)
            amount = round(random.uniform(*AMOUNT_RANGE[channel]), 2)

            if channel == "credit_card" and under_incident:
                # Phân chia proc-alpha vs proc-beta
                is_alpha = random.random() < PROC_ALPHA_SHARE
                proc = "proc-alpha" if is_alpha else "proc-beta"

                if is_alpha and random.random() < PROC_ALPHA_FAIL_RATE:
                    # proc-alpha timeout
                    rows.append((ts, SCENARIO, merchant, channel, amount,
                                 "failed", "ProcessorTimeoutError", proc, 0))
                else:
                    # proc-beta hoặc proc-alpha may mắn
                    rows.append((ts, SCENARIO, merchant, channel, amount,
                                 "success", None, proc, 0))
            else:
                # debit_card, e_wallet — KHÔNG bị ảnh hưởng
                proc = random.choice(PROCESSORS[channel])
                if random.random() < NOISE_FAIL_RATE:
                    rows.append((ts, SCENARIO, merchant, channel, amount,
                                 "failed", "PaymentDeclined", proc, 0))
                else:
                    rows.append((ts, SCENARIO, merchant, channel, amount,
                                 "success", None, proc, 0))

    return rows


# ── ft_revenue ────────────────────────────────────────────────────────────────

def generate_revenue() -> List[tuple]:
    """
    Columns: timestamp, scenario, channel, revenue, transaction_count,
             refund_amount, is_baseline
    """
    rows = []

    # Baseline: 09:00 - 10:00
    for minute_dt in minutes_range(BASELINE_START_HOUR, WINDOW_START_HOUR):
        ts = fmt(minute_dt)
        for channel in CHANNELS:
            base_rev = REVENUE_BASELINE[channel]
            rev = round(base_rev * random.uniform(0.95, 1.05), 2)
            tx_count = int(TX_PER_MIN_NORMAL * CHANNEL_WEIGHTS[CHANNELS.index(channel)])
            refund = round(rev * random.uniform(0.005, 0.015), 2)
            rows.append((ts, SCENARIO, channel, rev, tx_count, refund, 1))

    # Window: 10:00 - 11:00
    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        ts = fmt(minute_dt)
        under_incident = is_incident(minute_dt)
        for channel in CHANNELS:
            base_rev = REVENUE_BASELINE[channel]

            if channel == "credit_card" and under_incident:
                # Revenue giảm 60% do 65% tx fail, nhân thêm proc-alpha share (75%)
                # Effective fail: ~49% tổng credit_card tx → revenue giảm ~49%
                # Round to ~60% drop (đơn giản hóa có chủ ý cho rõ signal)
                rev = round(base_rev * random.uniform(0.37, 0.43), 2)
                tx_count = int(TX_PER_MIN_INCIDENT * CHANNEL_WEIGHTS[0])
            else:
                rev = round(base_rev * random.uniform(0.95, 1.05), 2)
                tx_count = int(TX_PER_MIN_NORMAL * CHANNEL_WEIGHTS[CHANNELS.index(channel)])

            refund = round(rev * random.uniform(0.005, 0.015), 2)
            is_base = 0 if under_incident else 1
            rows.append((ts, SCENARIO, channel, rev, tx_count, refund, is_base))

    return rows


# ── ft_merchants ──────────────────────────────────────────────────────────────

def generate_merchants() -> List[tuple]:
    """
    Columns: id, scenario, name, category, status, notes
    All merchants healthy — negative signal (không phải merchant bug).
    """
    return [
        ("merch-a", SCENARIO, "Alpha Retail",   "retail",      "active", ""),
        ("merch-b", SCENARIO, "Beta Electronics","electronics", "active", ""),
        ("merch-c", SCENARIO, "Gamma Fashion",  "fashion",     "active", ""),
        ("merch-d", SCENARIO, "Delta Food",     "food",        "active", ""),
    ]


# ── ft_settlements ────────────────────────────────────────────────────────────

def generate_settlements() -> List[tuple]:
    """
    Columns: timestamp, scenario, merchant_id, amount, processing_time_s, is_baseline

    processing_time_s tăng nhẹ từ ~12s → ~14s trong window nhưng KHÔNG phải root cause.
    """
    rows = []

    # Baseline: 09:00 - 10:00 (1 settlement/merchant/5min)
    for minute_dt in minutes_range(BASELINE_START_HOUR, WINDOW_START_HOUR):
        if minute_dt.minute % 5 != 0:
            continue
        ts = fmt(minute_dt)
        for merchant in MERCHANTS:
            amount = round(random.uniform(5000, 50000), 2)
            proc_time = round(random.gauss(12.0, 1.2), 2)
            rows.append((ts, SCENARIO, merchant, amount, proc_time, 1))

    # Window: 10:00 - 11:00
    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        if minute_dt.minute % 5 != 0:
            continue
        ts = fmt(minute_dt)
        under_incident = is_incident(minute_dt)
        for merchant in MERCHANTS:
            amount = round(random.uniform(5000, 50000), 2)
            # Tăng nhẹ processing_time — tín hiệu nhiễu, KHÔNG phải nguyên nhân
            if under_incident:
                proc_time = round(random.gauss(14.0, 1.5), 2)
            else:
                proc_time = round(random.gauss(12.0, 1.2), 2)
            proc_time = max(proc_time, 5.0)
            rows.append((ts, SCENARIO, merchant, amount, proc_time,
                         0 if under_incident else 1))

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def seed() -> None:
    db_path = str(ROOT / "data" / "investigation.db")
    conn = open_db(db_path)

    print(f"Seeding KB-F1 ({SCENARIO}) into {db_path} ...")

    # Idempotent: xóa data cũ của scenario này
    for table in ("ft_transactions", "ft_revenue", "ft_merchants", "ft_settlements"):
        conn.execute(f"DELETE FROM {table} WHERE scenario = ?", (SCENARIO,))
    conn.commit()

    # ft_transactions
    print("  Generating ft_transactions ...")
    tx_rows = generate_transactions()
    conn.executemany(
        "INSERT INTO ft_transactions "
        "(timestamp, scenario, merchant_id, channel, amount, status, "
        " error_type, processor_id, is_baseline) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tx_rows,
    )
    conn.commit()

    # ft_revenue
    print("  Generating ft_revenue ...")
    rev_rows = generate_revenue()
    conn.executemany(
        "INSERT INTO ft_revenue "
        "(timestamp, scenario, channel, revenue, transaction_count, "
        " refund_amount, is_baseline) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rev_rows,
    )
    conn.commit()

    # ft_merchants
    print("  Generating ft_merchants ...")
    merch_rows = generate_merchants()
    conn.executemany(
        "INSERT OR REPLACE INTO ft_merchants "
        "(id, scenario, name, category, status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        merch_rows,
    )
    conn.commit()

    # ft_settlements
    print("  Generating ft_settlements ...")
    settle_rows = generate_settlements()
    conn.executemany(
        "INSERT INTO ft_settlements "
        "(timestamp, scenario, merchant_id, amount, processing_time_s, is_baseline) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        settle_rows,
    )
    conn.commit()

    # Verify counts
    tx_total   = conn.execute("SELECT COUNT(*) FROM ft_transactions WHERE scenario=?",  (SCENARIO,)).fetchone()[0]
    rev_total  = conn.execute("SELECT COUNT(*) FROM ft_revenue WHERE scenario=?",       (SCENARIO,)).fetchone()[0]
    merch_total= conn.execute("SELECT COUNT(*) FROM ft_merchants WHERE scenario=?",     (SCENARIO,)).fetchone()[0]
    settle_total=conn.execute("SELECT COUNT(*) FROM ft_settlements WHERE scenario=?",   (SCENARIO,)).fetchone()[0]

    tx_fail = conn.execute(
        "SELECT COUNT(*) FROM ft_transactions WHERE scenario=? AND status='failed'",
        (SCENARIO,)
    ).fetchone()[0]
    tx_timeout = conn.execute(
        "SELECT COUNT(*) FROM ft_transactions WHERE scenario=? AND error_type='ProcessorTimeoutError'",
        (SCENARIO,)
    ).fetchone()[0]

    conn.close()

    print(f"\nKB-F1 seeded successfully:")
    print(f"  ft_transactions : {tx_total:,} rows  ({tx_fail:,} failed, {tx_timeout:,} ProcessorTimeoutError)")
    print(f"  ft_revenue      : {rev_total:,} rows  (1 row/channel/min × 3 channels)")
    print(f"  ft_merchants    : {merch_total} rows  (all status='active' — negative signal)")
    print(f"  ft_settlements  : {settle_total} rows  (processing_time ~12s→14s — noise, not cause)")
    print(f"\n  Incident window : 10:15 - 11:00 | Processor: proc-alpha | Channel: credit_card")
    print(f"  Root cause      : proc-alpha timeout → credit_card 65% fail rate")
    print(f"  Negative signals: debit_card/e_wallet unaffected; all merchants healthy")


if __name__ == "__main__":
    seed()
