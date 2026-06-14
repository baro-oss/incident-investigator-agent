"""
Sinh data KB-F2: Merchant price bug causing refunds.

Đường điều tra lý tưởng:
  ft_transactions → merch-buzz có refund_rate 15% từ 14:00 (8x baseline 1.875%)
  ft_revenue      → refund_amount tăng mạnh từ 14:00, total revenue không giảm nhiều
  ft_merchants    → merch-buzz notes ghi nhận price_bug_reported kể từ 13:52
  ft_settlements  → bình thường (tín hiệu âm: không phải settlement/processor issue)
  → Verdict: merch-buzz product pricing bug (10x below actual) → customers refund at high rate

Tín hiệu âm tính QUAN TRỌNG:
  - merch-a, merch-b, merch-c có refund_rate bình thường (~0.5%)
  - Không có ProcessorError / ProcessorTimeoutError trong window
  - ft_settlements processing_time bình thường cho tất cả merchants
  - Bug bắt đầu 13:52 (trước window 14:00) — merch-buzz notes ghi nhận mốc này
  - Tổng transaction volume KHÔNG giảm (customers vẫn mua), chỉ refund tăng
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

SCENARIO = "fintech2"
DATE = "2024-01-17"

# Mốc thời gian
WARMUP_START = (13, 45)       # 13:45 — warm-up trước window
BUG_START = (13, 52)          # 13:52 — bug bắt đầu (trước window một chút)
WINDOW_START_HOUR = 14        # 14:00 — investigation window bắt đầu
WINDOW_END_HOUR = 15          # 15:00 — investigation window kết thúc

# Khối lượng traffic
TX_PER_MIN_NORMAL = 150       # transactions/phút baseline

# Phân phối channel
CHANNEL_WEIGHTS = [0.45, 0.35, 0.20]   # credit_card, debit_card, e_wallet
CHANNELS = ["credit_card", "debit_card", "e_wallet"]

# Merchants
MERCHANTS_NORMAL = ["merch-a", "merch-b", "merch-c"]
MERCHANT_BUG = "merch-buzz"
ALL_MERCHANTS = MERCHANTS_NORMAL + [MERCHANT_BUG]

# Phân phối merchant traffic (merch-buzz có ít traffic hơn vì mới/nhỏ hơn)
MERCHANT_WEIGHTS = [0.30, 0.30, 0.25, 0.15]  # a, b, c, buzz

# Tỷ lệ refund
BASELINE_REFUND_RATE = 0.005  # 0.5% — baseline tất cả merchants
BUG_REFUND_RATE = 0.15        # 15% — merch-buzz sau khi bug bắt đầu

# Tỷ lệ failed transactions (cả 2 scenario: rất thấp vì đây là refund bug, không processor bug)
NOISE_FAIL_RATE = 0.008       # 0.8% failed toàn hệ thống (không phải ProcessorError)

# Amounts
AMOUNT_RANGE = {
    "credit_card": (100, 3000),
    "debit_card": (50, 800),
    "e_wallet": (20, 300),
}

# Processors (bình thường — không ai bị lỗi)
PROCESSORS = {
    "credit_card": ["proc-alpha", "proc-beta"],
    "debit_card": ["proc-gamma"],
    "e_wallet": ["proc-delta"],
}

# Revenue baseline per channel (VND k/min)
REVENUE_BASELINE = {
    "credit_card": 40000,
    "debit_card": 22000,
    "e_wallet": 12000,
}

random.seed(77)  # reproducible, khác KB-F1


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_dt(hour: int, minute: int, sec: int = 0) -> datetime:
    return datetime(2024, 1, 17, hour, minute, sec, tzinfo=timezone.utc)


def fmt(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def bug_dt() -> datetime:
    return make_dt(*BUG_START)


def minutes_range_dt(start: datetime, end: datetime):
    cur = start
    while cur < end:
        yield cur
        cur += timedelta(minutes=1)


def is_bug_active(dt: datetime) -> bool:
    return dt >= bug_dt()


# ── ft_transactions ───────────────────────────────────────────────────────────

def generate_transactions() -> List[tuple]:
    """
    Columns: timestamp, scenario, merchant_id, channel, amount, status,
             error_type, processor_id, is_baseline
    """
    rows = []

    # Warm-up: 13:45 - 14:00 (không phải baseline chính, nhưng giúp confirm timing bug)
    warmup_start_dt = make_dt(*WARMUP_START)
    window_start_dt = make_dt(WINDOW_START_HOUR, 0)
    window_end_dt   = make_dt(WINDOW_END_HOUR, 0)

    for period_label, period_start, period_end, is_base_val in [
        ("warm-up",  warmup_start_dt, window_start_dt, 0),   # warm-up trước window
        ("window",   window_start_dt, window_end_dt,   0),   # investigation window
    ]:
        for minute_dt in minutes_range_dt(period_start, period_end):
            bug_active = is_bug_active(minute_dt)

            for _ in range(TX_PER_MIN_NORMAL):
                sec = random.randint(0, 59)
                ts = fmt(minute_dt + timedelta(seconds=sec))
                channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
                merchant = random.choices(ALL_MERCHANTS, weights=MERCHANT_WEIGHTS)[0]
                amount = round(random.uniform(*AMOUNT_RANGE[channel]), 2)
                proc = random.choice(PROCESSORS[channel])

                # Xác định status
                if merchant == MERCHANT_BUG and bug_active:
                    roll = random.random()
                    if roll < BUG_REFUND_RATE:
                        # Refund do giá sai — khách mua xong refund ngay
                        rows.append((ts, SCENARIO, merchant, channel, amount,
                                     "refunded", "PricingMismatch", proc, is_base_val))
                    elif roll < BUG_REFUND_RATE + NOISE_FAIL_RATE:
                        rows.append((ts, SCENARIO, merchant, channel, amount,
                                     "failed", "PaymentDeclined", proc, is_base_val))
                    else:
                        rows.append((ts, SCENARIO, merchant, channel, amount,
                                     "success", None, proc, is_base_val))
                else:
                    # Merchants bình thường
                    roll = random.random()
                    if roll < BASELINE_REFUND_RATE:
                        rows.append((ts, SCENARIO, merchant, channel, amount,
                                     "refunded", None, proc, is_base_val))
                    elif roll < BASELINE_REFUND_RATE + NOISE_FAIL_RATE:
                        rows.append((ts, SCENARIO, merchant, channel, amount,
                                     "failed", "PaymentDeclined", proc, is_base_val))
                    else:
                        rows.append((ts, SCENARIO, merchant, channel, amount,
                                     "success", None, proc, is_base_val))

    return rows


# ── ft_revenue ────────────────────────────────────────────────────────────────

def generate_revenue() -> List[tuple]:
    """
    Columns: timestamp, scenario, channel, revenue, transaction_count,
             refund_amount, is_baseline

    Tổng revenue không giảm nhiều (khách vẫn mua), nhưng refund_amount tăng ~3-4x
    vì merch-buzz chiếm ~15% traffic và 15% của số đó bị refund.
    """
    rows = []

    window_start_dt = make_dt(WINDOW_START_HOUR, 0)
    window_end_dt   = make_dt(WINDOW_END_HOUR, 0)

    for minute_dt in minutes_range_dt(window_start_dt, window_end_dt):
        ts = fmt(minute_dt)
        bug_active = is_bug_active(minute_dt)

        for channel in CHANNELS:
            base_rev = REVENUE_BASELINE[channel]
            # Revenue tổng không thay đổi nhiều (tx count bình thường)
            rev = round(base_rev * random.uniform(0.93, 1.07), 2)
            tx_count = int(TX_PER_MIN_NORMAL * CHANNEL_WEIGHTS[CHANNELS.index(channel)])

            if bug_active:
                # refund_amount tăng mạnh — merch-buzz ~15% traffic × 15% refund rate
                # Effective refund: ~2.25% tổng tx → ~8x baseline 0.5% × 15%weight ≈ 2.25%
                # Để rõ signal: tăng 4x so với baseline refund
                refund = round(rev * random.uniform(0.035, 0.055), 2)
                is_base = 0
            else:
                refund = round(rev * random.uniform(0.003, 0.008), 2)
                is_base = 1

            rows.append((ts, SCENARIO, channel, rev, tx_count, refund, is_base))

    return rows


# ── ft_merchants ──────────────────────────────────────────────────────────────

def generate_merchants() -> List[tuple]:
    """
    Columns: id, scenario, name, category, status, notes

    merch-buzz: status='active' nhưng notes ghi nhận price_bug_reported.
    Các merchant khác: hoàn toàn bình thường.
    """
    return [
        ("merch-a",    SCENARIO, "Alpha Retail",    "retail",      "active",
         ""),
        ("merch-b",    SCENARIO, "Beta Electronics", "electronics", "active",
         ""),
        ("merch-c",    SCENARIO, "Gamma Fashion",   "fashion",     "active",
         ""),
        ("merch-buzz", SCENARIO, "Buzz Marketplace", "marketplace", "active",
         "price_bug_reported: product prices showing 10x below actual since 13:52; investigation in progress"),
    ]


# ── ft_settlements ────────────────────────────────────────────────────────────

def generate_settlements() -> List[tuple]:
    """
    Columns: timestamp, scenario, merchant_id, amount, processing_time_s, is_baseline

    Hoàn toàn bình thường — tín hiệu âm tính:
    không phải settlement lag hay processor issue.
    """
    rows = []

    window_start_dt = make_dt(WINDOW_START_HOUR, 0)
    window_end_dt   = make_dt(WINDOW_END_HOUR, 0)

    for minute_dt in minutes_range_dt(window_start_dt, window_end_dt):
        if minute_dt.minute % 5 != 0:
            continue
        ts = fmt(minute_dt)
        for merchant in ALL_MERCHANTS:
            amount = round(random.uniform(3000, 40000), 2)
            # Bình thường cho tất cả merchants — 12s ± 1.2s
            proc_time = round(random.gauss(12.0, 1.2), 2)
            proc_time = max(proc_time, 5.0)
            rows.append((ts, SCENARIO, merchant, amount, proc_time, 1))

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def seed() -> None:
    db_path = str(ROOT / "data" / "investigation.db")
    conn = open_db(db_path)

    print(f"Seeding KB-F2 ({SCENARIO}) into {db_path} ...")

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
    tx_total    = conn.execute("SELECT COUNT(*) FROM ft_transactions WHERE scenario=?",  (SCENARIO,)).fetchone()[0]
    rev_total   = conn.execute("SELECT COUNT(*) FROM ft_revenue WHERE scenario=?",       (SCENARIO,)).fetchone()[0]
    merch_total = conn.execute("SELECT COUNT(*) FROM ft_merchants WHERE scenario=?",     (SCENARIO,)).fetchone()[0]
    settle_total= conn.execute("SELECT COUNT(*) FROM ft_settlements WHERE scenario=?",   (SCENARIO,)).fetchone()[0]

    # Stats breakdown
    tx_refund = conn.execute(
        "SELECT COUNT(*) FROM ft_transactions WHERE scenario=? AND status='refunded'",
        (SCENARIO,)
    ).fetchone()[0]
    buzz_refund = conn.execute(
        "SELECT COUNT(*) FROM ft_transactions "
        "WHERE scenario=? AND merchant_id=? AND status='refunded'",
        (SCENARIO, MERCHANT_BUG)
    ).fetchone()[0]
    buzz_total = conn.execute(
        "SELECT COUNT(*) FROM ft_transactions WHERE scenario=? AND merchant_id=?",
        (SCENARIO, MERCHANT_BUG)
    ).fetchone()[0]

    conn.close()

    buzz_refund_rate = (buzz_refund / buzz_total * 100) if buzz_total > 0 else 0

    print(f"\nKB-F2 seeded successfully:")
    print(f"  ft_transactions : {tx_total:,} rows  "
          f"({tx_refund:,} refunded total; merch-buzz: {buzz_refund}/{buzz_total} = {buzz_refund_rate:.1f}% refund rate)")
    print(f"  ft_revenue      : {rev_total:,} rows  (refund_amount 4x spike visible)")
    print(f"  ft_merchants    : {merch_total} rows  (merch-buzz notes: price_bug_reported @ 13:52)")
    print(f"  ft_settlements  : {settle_total} rows  (all ~12s — negative signal)")
    print(f"\n  Bug start       : 13:52 (before 14:00 window — warm-up context)")
    print(f"  Investigation   : 14:00 - 15:00")
    print(f"  Root cause      : merch-buzz product prices 10x below actual → refund surge")
    print(f"  Negative signals: merch-a/b/c normal; no ProcessorError; settlements normal")


if __name__ == "__main__":
    seed()
