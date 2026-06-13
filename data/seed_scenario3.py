"""
Sinh data Kịch bản 3: auth-service DB connection pool exhaustion → cascade lên payment-gateway.

Đường điều tra lý tưởng:
  get_error_breakdown(payment-gateway) → AuthServiceTimeoutError 83% từ 08:11
  get_metrics(payment-gateway, latency_p99) → latency tăng (payment-gateway chờ auth)
  get_dependencies(payment-gateway)   → thấy phụ thuộc auth-service
  get_error_breakdown(auth-service)   → DatabaseConnectionPoolTimeout 82%
  get_metrics(auth-service, connection_wait_time) → spike 170x baseline (5ms→850ms)
  → Verdict: auth-service là root cause, độ tin CAO

Tín hiệu âm tính QUAN TRỌNG:
  - KHÔNG có deploy trong cửa sổ
  - third-party-provider BÌNH THƯỜNG
  - api-gateway, order-service BÌNH THƯỜNG
  - Nguồn lỗi: DB quá tải nội bộ của auth-service (không phải external dependency)
"""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

SCENARIO = "scenario3"
DATE = "2024-01-15"
WINDOW_START_HOUR = 7       # ghi log từ 07:00
WINDOW_END_HOUR = 10        # đến 10:00
AUTH_FAIL_START = "08:10"   # auth-service DB pool bắt đầu kiệt từ đây
CASCADE_START = "08:11"     # payment-gateway thấy lỗi 1 phút sau

ROOT_CAUSE_SERVICE = "auth-service"
CASCADED_SERVICE = "payment-gateway"

NOISE_ERROR_RATE = 0.03
AUTH_POOL_ERROR_RATE = 0.82     # 82% request auth-service fail
GATEWAY_CASCADE_RATE = 0.83     # 83% request payment-gateway fail

# Baseline metrics
AUTH_BASELINE_LATENCY = 45.0
AUTH_SPIKE_LATENCY = 365.0      # 8x baseline
AUTH_BASELINE_CONN_WAIT = 5.0
AUTH_SPIKE_CONN_WAIT = 855.0    # connection_wait_time spike 170x

GW_BASELINE_LATENCY = 120.0
GW_SPIKE_LATENCY = 455.0        # gateway chờ auth nên cũng chậm

REQUESTS_PER_MINUTE = 40

SERVICES = ["api-gateway", "payment-gateway", "auth-service", "order-service", "third-party-provider"]
NOISE_ERROR_TYPES = ["HTTP_400", "HTTP_404", "ValidationError"]
NORMAL_MESSAGES = [
    "Request processed successfully",
    "Cache hit",
    "DB query completed",
    "Token validated",
]

DB_PATH = Path(__file__).parent / "investigation.db"

random.seed(17)


def to_dt(time_str: str) -> datetime:
    return datetime.strptime(f"{DATE}T{time_str}:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def minutes_range(start_hour: int, end_hour: int):
    base = datetime(2024, 1, 15, start_hour, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 15, end_hour, 0, tzinfo=timezone.utc)
    cur = base
    while cur < end:
        yield cur
        cur += timedelta(minutes=1)


auth_fail_dt = to_dt(AUTH_FAIL_START)
cascade_dt = to_dt(CASCADE_START)


def generate_logs() -> List[tuple]:
    rows = []

    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        auth_failing = minute_dt >= auth_fail_dt
        gw_cascading = minute_dt >= cascade_dt

        for _ in range(REQUESTS_PER_MINUTE):
            sec = random.randint(0, 59)
            req_dt = minute_dt + timedelta(seconds=sec)
            req_ts = req_dt.isoformat().replace("+00:00", "Z")
            trace_id = f"tr-{random.randint(10**11, 10**12 - 1)}"

            # ── auth-service ──────────────────────────────────────────
            if auth_failing:
                if random.random() < AUTH_POOL_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, "auth-service", "ERROR",
                                 "DB connection pool exhausted — waited 850ms for free slot",
                                 "DatabaseConnectionPoolTimeout", trace_id))
                else:
                    rows.append((req_ts, SCENARIO, "auth-service", "INFO",
                                 "Token validated (slow — pool contention)", None, trace_id))
            else:
                if random.random() < NOISE_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, "auth-service", "WARN",
                                 "Minor error", random.choice(NOISE_ERROR_TYPES), trace_id))
                else:
                    rows.append((req_ts, SCENARIO, "auth-service", "INFO",
                                 "Token validated", None, trace_id))

            # ── payment-gateway ───────────────────────────────────────
            if gw_cascading:
                if random.random() < GATEWAY_CASCADE_RATE:
                    rows.append((req_ts, SCENARIO, "payment-gateway", "ERROR",
                                 "Auth service timed out after 30s — cannot verify token",
                                 "AuthServiceTimeoutError", trace_id))
                else:
                    rows.append((req_ts, SCENARIO, "payment-gateway", "INFO",
                                 "Payment processed (auth slow but OK)", None, trace_id))
            else:
                if random.random() < NOISE_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, "payment-gateway", "WARN",
                                 "Minor error", random.choice(NOISE_ERROR_TYPES), trace_id))
                else:
                    rows.append((req_ts, SCENARIO, "payment-gateway", "INFO",
                                 "Payment processed", None, trace_id))

            # ── Các service khác: BÌNH THƯỜNG ────────────────────────
            for svc in ["api-gateway", "order-service", "third-party-provider"]:
                if random.random() < NOISE_ERROR_RATE * 0.4:
                    rows.append((req_ts, SCENARIO, svc, "WARN",
                                 "Minor error", random.choice(NOISE_ERROR_TYPES),
                                 f"tr-{random.randint(10**11, 10**12 - 1)}"))

    return rows


def generate_metrics() -> List[tuple]:
    rows = []

    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        ts = minute_dt.isoformat().replace("+00:00", "Z")
        auth_failing = minute_dt >= auth_fail_dt
        gw_cascading = minute_dt >= cascade_dt

        # auth-service — latency spike + connection_wait_time spike
        auth_latency = random.gauss(AUTH_SPIKE_LATENCY, 30) if auth_failing else random.gauss(AUTH_BASELINE_LATENCY, 4)
        auth_conn_wait = random.gauss(AUTH_SPIKE_CONN_WAIT, 60) if auth_failing else random.gauss(AUTH_BASELINE_CONN_WAIT, 1)
        auth_err = random.uniform(0.75, 0.88) if auth_failing else random.gauss(0.1, 0.02)
        is_auth_baseline = 0 if auth_failing else 1

        rows.append((ts, SCENARIO, "auth-service", "latency_p99", max(auth_latency, 10), is_auth_baseline))
        rows.append((ts, SCENARIO, "auth-service", "connection_wait_time", max(auth_conn_wait, 0), is_auth_baseline))
        rows.append((ts, SCENARIO, "auth-service", "error_rate", max(auth_err, 0), is_auth_baseline))

        # payment-gateway — latency cũng tăng (chờ auth), error_rate tăng
        gw_latency = random.gauss(GW_SPIKE_LATENCY, 40) if gw_cascading else random.gauss(GW_BASELINE_LATENCY, 10)
        gw_err = random.uniform(0.78, 0.88) if gw_cascading else random.gauss(0.3, 0.05)
        is_gw_baseline = 0 if gw_cascading else 1

        rows.append((ts, SCENARIO, "payment-gateway", "latency_p99", max(gw_latency, 30), is_gw_baseline))
        rows.append((ts, SCENARIO, "payment-gateway", "error_rate", max(gw_err, 0), is_gw_baseline))

        # Các service khác: BÌNH THƯỜNG
        for svc, (base_lat, base_err) in [
            ("api-gateway", (95, 0.8)),
            ("order-service", (80, 0.2)),
            ("third-party-provider", (200, 0.5)),
        ]:
            rows.append((ts, SCENARIO, svc, "latency_p99",
                         round(random.gauss(base_lat, base_lat * 0.05), 1), 1))
            rows.append((ts, SCENARIO, svc, "error_rate",
                         max(random.gauss(base_err * 0.01, 0.005), 0), 1))

    return rows


def generate_deploys() -> List[tuple]:
    # KB3: KHÔNG có deploy trong cửa sổ — tín hiệu âm tính
    return [
        ("2024-01-13T10:00:00Z", SCENARIO, "payment-gateway", "v2.3.1", "success"),
        ("2024-01-13T11:00:00Z", SCENARIO, "auth-service", "v1.4.2", "success"),
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

    print(f"KB3 seeded: {log_count} logs, {metric_count} metric rows, {len(deploys)} deploys")
    print(f"  Root cause:  auth-service — DB connection pool exhaustion từ {AUTH_FAIL_START}")
    print(f"  Cascade:     payment-gateway — AuthServiceTimeoutError từ {CASCADE_START}")
    print(f"  Key metric:  auth-service connection_wait_time spike {AUTH_BASELINE_CONN_WAIT}ms → {AUTH_SPIKE_CONN_WAIT}ms")
    print(f"  Tín hiệu âm: không có deploy, third-party-provider bình thường")


if __name__ == "__main__":
    main()
