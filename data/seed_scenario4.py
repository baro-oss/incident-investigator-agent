"""
Sinh data Kịch bản 4: external traffic surge → rate limiting tại api-gateway.

Đường điều tra lý tưởng:
  get_error_breakdown(api-gateway) → RateLimitError 62% từ 10:15
  get_metrics(api-gateway, request_count) → spike 5x baseline (200→1000/phút)
  get_recent_deploys(10:00-11:00) → không có deploy
  get_dependencies(api-gateway) → downstream bình thường (optional confirm)
  → Verdict: external traffic surge gây rate limiting, không phải code bug

Tín hiệu âm tính QUAN TRỌNG:
  - Lỗi là RateLimitError (không phải TimeoutException/ConnectionError → không phải code bug)
  - Downstream services (payment-gateway, order-service) BÌNH THƯỜNG — rate limiter chặn
  - KHÔNG có deploy trong cửa sổ
  - Tỷ lệ lỗi tăng VÌ traffic tăng, không phải code mới
"""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

SCENARIO = "scenario4"
DATE = "2024-01-15"
WINDOW_START_HOUR = 9       # ghi log từ 09:00
WINDOW_END_HOUR = 12        # đến 12:00
SURGE_START = "10:15"       # traffic surge bắt đầu từ đây

TARGET_SERVICE = "api-gateway"

NOISE_ERROR_RATE = 0.03
RATE_LIMIT_ERROR_RATE = 0.62    # 62% request bị rate limit khi surge

NORMAL_RPM = 200            # request/phút bình thường
SURGE_RPM = 1000            # 5x traffic khi surge

# Metrics
GW_BASELINE_LATENCY = 95.0
GW_SURGE_LATENCY = 130.0    # tăng nhẹ (traffic overhead)

SERVICES = ["api-gateway", "payment-gateway", "auth-service", "order-service", "third-party-provider"]
NOISE_ERROR_TYPES = ["HTTP_400", "HTTP_404", "ValidationError"]
NORMAL_MESSAGES = [
    "Request routed successfully",
    "Cache hit",
    "Response forwarded",
    "Health check passed",
]

DB_PATH = Path(__file__).parent / "investigation.db"

random.seed(23)


def to_dt(time_str: str) -> datetime:
    return datetime.strptime(f"{DATE}T{time_str}:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def minutes_range(start_hour: int, end_hour: int):
    base = datetime(2024, 1, 15, start_hour, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 15, end_hour, 0, tzinfo=timezone.utc)
    cur = base
    while cur < end:
        yield cur
        cur += timedelta(minutes=1)


surge_dt = to_dt(SURGE_START)


def generate_logs() -> List[tuple]:
    rows = []

    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        surging = minute_dt >= surge_dt
        rps = SURGE_RPM if surging else NORMAL_RPM

        for _ in range(rps):
            sec = random.randint(0, 59)
            req_dt = minute_dt + timedelta(seconds=sec)
            req_ts = req_dt.isoformat().replace("+00:00", "Z")
            trace_id = f"tr-{random.randint(10**11, 10**12 - 1)}"

            # ── api-gateway: rate limiting khi surge ──────────────────
            if surging:
                roll = random.random()
                if roll < RATE_LIMIT_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, "api-gateway", "WARN",
                                 "Request rate limit exceeded — client throttled",
                                 "RateLimitError", trace_id))
                else:
                    rows.append((req_ts, SCENARIO, "api-gateway", "INFO",
                                 "Request routed successfully", None, trace_id))
            else:
                if random.random() < NOISE_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, "api-gateway", "WARN",
                                 "Minor error", random.choice(NOISE_ERROR_TYPES), trace_id))
                else:
                    rows.append((req_ts, SCENARIO, "api-gateway", "INFO",
                                 random.choice(NORMAL_MESSAGES), None, trace_id))

            # ── Downstream services: BÌNH THƯỜNG (rate limiter chặn) ──
            # Chỉ các request không bị rate limit (38%) mới đến downstream
            # Tổng request đến downstream ≈ bình thường → downstream không thấy surge
            if not surging or random.random() > RATE_LIMIT_ERROR_RATE:
                for svc in ["payment-gateway", "order-service"]:
                    if random.random() < NOISE_ERROR_RATE * 0.3:
                        rows.append((req_ts, SCENARIO, svc, "WARN",
                                     "Minor error", random.choice(NOISE_ERROR_TYPES),
                                     f"tr-{random.randint(10**11, 10**12 - 1)}"))

    return rows


def generate_metrics() -> List[tuple]:
    rows = []

    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        ts = minute_dt.isoformat().replace("+00:00", "Z")
        surging = minute_dt >= surge_dt
        is_baseline = 0 if surging else 1

        # api-gateway: request_count spike 5x, error_rate spike, latency nhẹ tăng
        req_count = random.gauss(SURGE_RPM, 50) if surging else random.gauss(NORMAL_RPM, 15)
        gw_latency = random.gauss(GW_SURGE_LATENCY, 10) if surging else random.gauss(GW_BASELINE_LATENCY, 6)
        gw_err = random.uniform(0.58, 0.66) if surging else random.gauss(0.8 / 100, 0.002)

        rows.append((ts, SCENARIO, "api-gateway", "request_count", max(req_count, 0), is_baseline))
        rows.append((ts, SCENARIO, "api-gateway", "latency_p99", max(gw_latency, 20), is_baseline))
        rows.append((ts, SCENARIO, "api-gateway", "error_rate", max(gw_err, 0), is_baseline))

        # Downstream services: BÌNH THƯỜNG — request_count không tăng
        for svc, (base_lat, base_err, base_rps) in [
            ("payment-gateway", (120, 0.3, 80)),
            ("order-service", (80, 0.2, 60)),
            ("auth-service", (45, 0.1, 120)),
            ("third-party-provider", (200, 0.5, 40)),
        ]:
            rows.append((ts, SCENARIO, svc, "latency_p99",
                         max(random.gauss(base_lat, base_lat * 0.05), 10), 1))
            rows.append((ts, SCENARIO, svc, "error_rate",
                         max(random.gauss(base_err / 100, 0.001), 0), 1))
            rows.append((ts, SCENARIO, svc, "request_count",
                         max(random.gauss(base_rps, base_rps * 0.05), 0), 1))

    return rows


def generate_deploys() -> List[tuple]:
    # KB4: KHÔNG có deploy trong cửa sổ — tín hiệu âm tính cốt lõi
    return [
        ("2024-01-14T08:00:00Z", SCENARIO, "api-gateway", "v3.2.0", "success"),
        ("2024-01-14T09:00:00Z", SCENARIO, "payment-gateway", "v2.3.1", "success"),
    ]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    for table in ["logs", "metrics", "deploys"]:
        conn.execute(f"DELETE FROM {table} WHERE scenario=?", (SCENARIO,))
    conn.commit()

    logs = generate_logs()
    conn.executemany(
        "INSERT INTO logs (timestamp,scenario,service,level,message,error_type,trace_id) VALUES (?,?,?,?,?,?,?)",
        logs,
    )

    metrics = generate_metrics()
    conn.executemany(
        "INSERT INTO metrics (timestamp,scenario,service,metric_name,value,is_baseline) VALUES (?,?,?,?,?,?)",
        metrics,
    )

    deploys = generate_deploys()
    conn.executemany(
        "INSERT INTO deploys (timestamp,scenario,service,version,status) VALUES (?,?,?,?,?)",
        deploys,
    )

    conn.commit()

    log_count = conn.execute("SELECT COUNT(*) FROM logs WHERE scenario=?", (SCENARIO,)).fetchone()[0]
    metric_count = conn.execute("SELECT COUNT(*) FROM metrics WHERE scenario=?", (SCENARIO,)).fetchone()[0]
    conn.close()

    surge_logs = sum(1 for _ in range(0))  # placeholder
    print(f"KB4 seeded: {log_count} logs, {metric_count} metric rows, {len(deploys)} deploys")
    print(f"  Root cause: external traffic surge từ {SURGE_START} ({NORMAL_RPM}→{SURGE_RPM} req/min)")
    print(f"  Lỗi chủ đạo: RateLimitError ({RATE_LIMIT_ERROR_RATE*100:.0f}% khi surge)")
    print(f"  Tín hiệu âm: không deploy, downstream bình thường, lỗi là RateLimit không phải TimeoutException")


if __name__ == "__main__":
    main()
