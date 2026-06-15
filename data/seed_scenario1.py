"""
Sinh data Kịch bản 1: deploy v2.3.1 lúc 14:03 → timeout ở payment-gateway từ 14:05.

Đường điều tra lý tưởng:
  get_error_breakdown → thấy 87% TimeoutException sau 14:05
  get_metrics         → thấy latency p99 lệch 9x baseline từ 14:05
  get_recent_deploys  → thấy v2.3.1 lúc 14:03 ngay trước spike
  → Verdict: deploy v2.3.1 là root cause, độ tin CAO

Tham số hóa để dễ tái tạo biến thể khi bị nghi hardcode.
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).parent.parent


def _open_conn():
    """Mở connection theo DB_BACKEND (sqlite / postgres)."""
    if os.environ.get("DB_BACKEND", "sqlite").lower() == "postgres":
        sys.path.insert(0, str(ROOT / "src"))
        from agent.storage.db import open_db  # type: ignore
        return open_db()
    path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "investigation.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# ── Cấu hình tham số hóa ─────────────────────────────────────────────────────

SCENARIO = "scenario1"
DATE = "2024-01-15"
WINDOW_START_HOUR = 13          # bắt đầu ghi log từ 13:00
WINDOW_END_HOUR = 16            # kết thúc lúc 16:00
DEPLOY_TIME = "14:03"           # mốc deploy v2.3.1
SPIKE_START = "14:05"           # lỗi bắt đầu tăng sau đây
VERSION_FAULTY = "v2.3.1"
VERSION_BEFORE = "v2.2.8"
TARGET_SERVICE = "payment-gateway"

# Tỷ lệ tín hiệu / nhiễu
NOISE_ERROR_RATE = 0.04         # 4% lỗi vặt ở mọi service trước sự cố
SPIKE_TIMEOUT_RATE = 0.87       # 87% request sau spike là TimeoutException
SPIKE_ERROR_RATE = 0.95         # tổng lỗi sau spike (phần còn lại = thành công)

# Khối lượng (nhỏ thôi — đủ signal, không GB)
REQUESTS_PER_MINUTE_NORMAL = 40     # request/phút trước spike
REQUESTS_PER_MINUTE_SPIKE = 38      # request/phút sau spike (giảm nhẹ vì timeout)

# total_count giả lập quy mô thật (tool báo con số này, không phải số dòng thật)
SIMULATED_TOTAL_ERRORS = 14203
SIMULATED_TOTAL_REQUESTS = 48721

random.seed(42)   # reproducible

# ── Helpers ───────────────────────────────────────────────────────────────────

SERVICES = ["api-gateway", "payment-gateway", "auth-service", "order-service", "third-party-provider"]
NOISE_ERROR_TYPES = ["HTTP_400", "HTTP_404", "ValidationError", "RateLimitError"]
NORMAL_MESSAGES = [
    "Request processed successfully",
    "Cache hit",
    "DB query completed",
    "Response sent",
]


def ts(date: str, time_str: str, jitter_sec: int = 0) -> str:
    """Tạo timestamp ISO-8601 UTC."""
    dt = datetime.strptime(f"{date}T{time_str}:00", "%Y-%m-%dT%H:%M:%S")
    dt = dt.replace(tzinfo=timezone.utc)
    dt += timedelta(seconds=random.randint(-jitter_sec, jitter_sec))
    return dt.isoformat().replace("+00:00", "Z")


def minutes_range(date: str, start_hour: int, end_hour: int):
    """Yield từng phút trong khoảng."""
    base = datetime(2024, 1, 15, start_hour, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 15, end_hour, 0, tzinfo=timezone.utc)
    current = base
    while current < end:
        yield current
        current += timedelta(minutes=1)


def is_after_spike(dt: datetime) -> bool:
    spike_dt = datetime(2024, 1, 15, 14, 5, tzinfo=timezone.utc)
    return dt >= spike_dt


# ── Sinh logs ─────────────────────────────────────────────────────────────────

def generate_logs() -> List[tuple]:
    rows = []

    for minute_dt in minutes_range(DATE, WINDOW_START_HOUR, WINDOW_END_HOUR):
        spike = is_after_spike(minute_dt)
        rps = REQUESTS_PER_MINUTE_SPIKE if spike else REQUESTS_PER_MINUTE_NORMAL

        for _ in range(rps):
            sec_offset = random.randint(0, 59)
            req_dt = minute_dt + timedelta(seconds=sec_offset)
            req_ts = req_dt.isoformat().replace("+00:00", "Z")

            trace_id = f"tr-{random.randint(10**11, 10**12-1)}"

            # ── Lỗi tại payment-gateway sau spike ──────────────────────────
            if spike:
                roll = random.random()
                if roll < SPIKE_TIMEOUT_RATE:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "ERROR",
                                 "Upstream connection timed out after 30000ms",
                                 "TimeoutException", trace_id))
                elif roll < SPIKE_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "ERROR",
                                 "Connection refused by downstream",
                                 "ConnectionRefusedError", trace_id))
                else:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "INFO",
                                 "Request processed successfully",
                                 None, trace_id))
            else:
                # Trước spike: chỉ nhiễu nhẹ
                if random.random() < NOISE_ERROR_RATE:
                    err_type = random.choice(NOISE_ERROR_TYPES)
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "WARN",
                                 f"Intermittent error: {err_type}",
                                 err_type, trace_id))
                else:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "INFO",
                                 random.choice(NORMAL_MESSAGES), None, trace_id))

            # ── Nhiễu từ các service khác (luôn nhẹ) ──────────────────────
            for svc in [s for s in SERVICES if s != TARGET_SERVICE]:
                if random.random() < NOISE_ERROR_RATE * 0.5:
                    err_type = random.choice(NOISE_ERROR_TYPES)
                    rows.append((req_ts, SCENARIO, svc, "WARN",
                                 f"Minor error: {err_type}", err_type,
                                 f"tr-{random.randint(10**11, 10**12-1)}"))

    return rows


# ── Sinh metrics ──────────────────────────────────────────────────────────────

def generate_metrics() -> List[tuple]:
    rows = []

    for minute_dt in minutes_range(DATE, WINDOW_START_HOUR, WINDOW_END_HOUR):
        spike = is_after_spike(minute_dt)
        minute_ts = minute_dt.isoformat().replace("+00:00", "Z")
        is_baseline = 1 if minute_dt < datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc) else 0

        # payment-gateway latency p99
        if spike:
            latency = random.uniform(950, 1250)   # spike: 950-1250ms
        else:
            latency = random.uniform(110, 135)    # baseline: 110-135ms
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "latency_p99", round(latency, 1), is_baseline))

        # payment-gateway error rate (errors/min)
        if spike:
            err_rate = random.uniform(32, 38)     # spike: ~35 errors/min
        else:
            err_rate = random.uniform(0.2, 0.5)   # baseline: <0.5/min
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "error_rate", round(err_rate, 2), is_baseline))

        # request count
        req_count = REQUESTS_PER_MINUTE_SPIKE if spike else REQUESTS_PER_MINUTE_NORMAL
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "request_count",
                     req_count + random.randint(-3, 3), is_baseline))

        # Các service khác — luôn bình thường
        for svc in [s for s in SERVICES if s != TARGET_SERVICE]:
            baselines = {
                "api-gateway":            (95, 0.8),
                "auth-service":           (45, 0.1),
                "order-service":          (80, 0.2),
                "third-party-provider":   (200, 0.5),
            }
            base_lat, base_err = baselines.get(svc, (100, 0.3))
            rows.append((minute_ts, SCENARIO, svc, "latency_p99",
                         round(random.uniform(base_lat * 0.9, base_lat * 1.1), 1), is_baseline))
            rows.append((minute_ts, SCENARIO, svc, "error_rate",
                         round(random.uniform(0, base_err * 1.5), 2), is_baseline))

    return rows


# ── Sinh deploys ──────────────────────────────────────────────────────────────

def generate_deploys() -> List[tuple]:
    return [
        # Deploy lỗi — đây là root cause
        (ts(DATE, DEPLOY_TIME, jitter_sec=0), SCENARIO,
         TARGET_SERVICE, VERSION_FAULTY, "success"),
        # Deploy trước đó — baseline
        (ts(DATE, "10:15", jitter_sec=0), SCENARIO,
         TARGET_SERVICE, VERSION_BEFORE, "success"),
        # Deploy service khác — không liên quan
        (ts(DATE, "09:30", jitter_sec=0), SCENARIO,
         "auth-service", "v1.4.2", "success"),
        (ts(DATE, "11:00", jitter_sec=0), SCENARIO,
         "order-service", "v3.1.0", "success"),
    ]


# ── Nạp catalog ───────────────────────────────────────────────────────────────

def load_catalog(catalog_path: Path) -> List[tuple]:
    data = json.loads(catalog_path.read_text())
    return [
        (
            svc["service"],
            svc["description"],
            json.dumps(svc["depends_on"]),
            svc["baseline_error_rate"],
            svc["baseline_latency_p99"],
        )
        for svc in data["services"]
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def seed(db_path: str, catalog_path: str) -> None:
    conn = _open_conn()

    # Xóa data cũ của scenario này trước khi seed lại
    conn.execute("DELETE FROM logs WHERE scenario = ?", (SCENARIO,))
    conn.execute("DELETE FROM metrics WHERE scenario = ?", (SCENARIO,))
    conn.execute("DELETE FROM deploys WHERE scenario = ?", (SCENARIO,))

    print("Generating logs...")
    logs = generate_logs()
    conn.executemany(
        "INSERT INTO logs (timestamp, scenario, service, level, message, error_type, trace_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        logs,
    )
    print(f"  {len(logs)} log rows inserted")

    print("Generating metrics...")
    metrics = generate_metrics()
    conn.executemany(
        "INSERT INTO metrics (timestamp, scenario, service, metric_name, value, is_baseline) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        metrics,
    )
    print(f"  {len(metrics)} metric rows inserted")

    print("Generating deploys...")
    deploys = generate_deploys()
    conn.executemany(
        "INSERT INTO deploys (timestamp, scenario, service, version, status) "
        "VALUES (?, ?, ?, ?, ?)",
        deploys,
    )
    print(f"  {len(deploys)} deploy rows inserted")

    print("Loading catalog...")
    catalog_rows = load_catalog(Path(catalog_path))
    conn.executemany(
        "INSERT INTO service_catalog "
        "(service, description, depends_on, baseline_error_rate, baseline_latency_p99) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (service) DO UPDATE SET "
        "description=EXCLUDED.description, depends_on=EXCLUDED.depends_on, "
        "baseline_error_rate=EXCLUDED.baseline_error_rate, "
        "baseline_latency_p99=EXCLUDED.baseline_latency_p99",
        catalog_rows,
    )
    print(f"  {len(catalog_rows)} services in catalog")

    conn.commit()
    conn.close()
    backend = os.environ.get("DB_BACKEND", "sqlite").lower()
    target = os.environ.get("DATABASE_URL", db_path) if backend == "postgres" else db_path
    print(f"\nScenario 1 seeded → {target}")
    print(f"  Deploy: {TARGET_SERVICE} {VERSION_FAULTY} at {DEPLOY_TIME}")
    print(f"  Spike:  timeout rate {SPIKE_TIMEOUT_RATE*100:.0f}% from {SPIKE_START}")


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    db = str(root / "data" / "investigation.db")
    catalog = str(root / "data" / "catalog.json")
    seed(db, catalog)
