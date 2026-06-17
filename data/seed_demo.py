"""
Sinh data Kịch bản DEMO: deploy payment-gateway v2.4.0 lúc 09:32 → connection
pool exhaustion → TimeoutException ở payment-gateway từ 09:35.

Root cause neo trong SOURCE (đọc qua GitLab code MCP):
  v2.4.0 hạ MAX_POOL_SIZE 50→5 + xoá retry/except guard → pool cạn → upstream timeout.

Đường điều tra lý tưởng:
  get_error_breakdown → ~84% TimeoutException sau 09:35
  get_metrics         → latency p99 lệch nhiều lần baseline trong 09:00-10:00
  get_recent_deploys  → v2.4.0 lúc 09:32 ngay trước spike
  get_dependencies    → payment-gateway → auth-service, third-party-provider
  get_code_diff(payment-gateway, v2.4.0) → RISK: config-knob pool→5 + removed-error-handling
  → Verdict: deploy v2.4.0 là root cause, độ tin CAO, neo bằng chứng code.

Khác scenario1: ngày/giờ riêng (09:00-10:00 khớp parse_alert_time floor-to-hour),
version v2.4.0/v2.3.0 (khớp tag GitLab demo), scenario="demo".

Chạy: python3 data/seed_demo.py
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

ROOT = Path(__file__).parent.parent


def _open_conn():
    """Mở connection Postgres qua storage seam."""
    sys.path.insert(0, str(ROOT / "src"))
    from agent.storage.db import open_db  # type: ignore
    return open_db()


# ── Cấu hình tham số hóa ─────────────────────────────────────────────────────

SCENARIO = "demo"
DATE = "2026-06-16"             # ngày demo (parse_alert_time floor-to-hour → 09:00-10:00)
WINDOW_START_HOUR = 8          # ghi log từ 08:00 (có baseline trước incident)
WINDOW_END_HOUR = 11           # kết thúc 11:00
DEPLOY_TIME = "09:02"          # mốc deploy v2.4.0 (đầu giờ → spike phủ gần hết window 09:00-10:00)
SPIKE_START = "09:05"          # lỗi bắt đầu tăng sau đây
VERSION_FAULTY = "v2.4.0"
VERSION_BEFORE = "v2.3.0"
TARGET_SERVICE = "payment-gateway"

NOISE_ERROR_RATE = 0.04        # 4% lỗi vặt trước sự cố
SPIKE_TIMEOUT_RATE = 0.84      # 84% request sau spike là TimeoutException
SPIKE_ERROR_RATE = 0.95        # tổng lỗi sau spike

REQUESTS_PER_MINUTE_NORMAL = 40
REQUESTS_PER_MINUTE_SPIKE = 36

SIMULATED_TOTAL_ERRORS = 18402
SIMULATED_TOTAL_REQUESTS = 51338

random.seed(2026)

SERVICES = ["api-gateway", "payment-gateway", "auth-service", "order-service", "third-party-provider"]
NOISE_ERROR_TYPES = ["HTTP_400", "HTTP_404", "ValidationError", "RateLimitError"]
NORMAL_MESSAGES = [
    "Request processed successfully",
    "Cache hit",
    "DB query completed",
    "Response sent",
]

_DATE_D = datetime.strptime(DATE, "%Y-%m-%d").date()
_SPIKE_DT = datetime.combine(
    _DATE_D,
    datetime.strptime(SPIKE_START, "%H:%M").time(),
    tzinfo=timezone.utc,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ts(time_str: str) -> str:
    """Tạo timestamp ISO-8601 UTC cho DATE + time_str (HH:MM)."""
    dt = datetime.strptime(f"{DATE}T{time_str}:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def minutes_range(start_hour: int, end_hour: int):
    base = datetime.combine(_DATE_D, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=start_hour)
    end = datetime.combine(_DATE_D, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=end_hour)
    current = base
    while current < end:
        yield current
        current += timedelta(minutes=1)


def is_after_spike(dt: datetime) -> bool:
    return dt >= _SPIKE_DT


# ── Sinh logs ─────────────────────────────────────────────────────────────────

def generate_logs() -> List[tuple]:
    rows = []
    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        spike = is_after_spike(minute_dt)
        rps = REQUESTS_PER_MINUTE_SPIKE if spike else REQUESTS_PER_MINUTE_NORMAL

        for _ in range(rps):
            req_dt = minute_dt + timedelta(seconds=random.randint(0, 59))
            req_ts = req_dt.isoformat().replace("+00:00", "Z")
            trace_id = f"tr-{random.randint(10**11, 10**12-1)}"

            if spike:
                roll = random.random()
                if roll < SPIKE_TIMEOUT_RATE:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "ERROR",
                                 "Connection pool exhausted — upstream timed out after 30000ms",
                                 "TimeoutException", trace_id))
                elif roll < SPIKE_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "ERROR",
                                 "Could not acquire connection from pool",
                                 "PoolExhaustedError", trace_id))
                else:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "INFO",
                                 "Request processed successfully", None, trace_id))
            else:
                if random.random() < NOISE_ERROR_RATE:
                    err_type = random.choice(NOISE_ERROR_TYPES)
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "WARN",
                                 f"Intermittent error: {err_type}", err_type, trace_id))
                else:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "INFO",
                                 random.choice(NORMAL_MESSAGES), None, trace_id))

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
    baseline_cutoff = datetime.combine(_DATE_D, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        spike = is_after_spike(minute_dt)
        minute_ts = minute_dt.isoformat().replace("+00:00", "Z")
        is_baseline = 1 if minute_dt < baseline_cutoff else 0

        if spike:
            latency = random.uniform(980, 1180)    # ~9x baseline 120
            err_rate = random.uniform(32, 40)
        else:
            latency = random.uniform(110, 135)
            err_rate = random.uniform(0.2, 0.5)
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "latency_p99", round(latency, 1), is_baseline))
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "error_rate", round(err_rate, 2), is_baseline))

        req_count = REQUESTS_PER_MINUTE_SPIKE if spike else REQUESTS_PER_MINUTE_NORMAL
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "request_count",
                     req_count + random.randint(-3, 3), is_baseline))

        for svc in [s for s in SERVICES if s != TARGET_SERVICE]:
            baselines = {
                "api-gateway":          (95, 0.8),
                "auth-service":         (45, 0.1),
                "order-service":        (80, 0.2),
                "third-party-provider": (200, 0.5),
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
        # Deploy lỗi — root cause
        (ts(DEPLOY_TIME), SCENARIO, TARGET_SERVICE, VERSION_FAULTY, "success"),
        # Deploy trước đó — baseline
        (ts("08:10"), SCENARIO, TARGET_SERVICE, VERSION_BEFORE, "success"),
        # Deploy service khác — không liên quan
        (ts("08:45"), SCENARIO, "auth-service", "v1.6.0", "success"),
        (ts("07:50"), SCENARIO, "order-service", "v3.4.1", "success"),
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
    target = os.environ.get("DATABASE_URL", "postgres")
    print(f"\nScenario DEMO seeded → {target}")
    print(f"  Date:   {DATE} | window khuyến nghị: 09:00-10:00")
    print(f"  Deploy: {TARGET_SERVICE} {VERSION_FAULTY} at {DEPLOY_TIME}")
    print(f"  Spike:  timeout rate {SPIKE_TIMEOUT_RATE*100:.0f}% from {SPIKE_START}")


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    db = str(root / "data" / "investigation.db")
    catalog = str(root / "data" / "catalog.json")
    seed(db, catalog)
