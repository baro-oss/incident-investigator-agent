"""
Sinh data Kịch bản 2: third-party-provider sập → lỗi dây chuyền lan ngược lên payment-gateway.

Đường điều tra lý tưởng:
  get_error_breakdown(payment-gateway) → thấy lỗi ConnectionError tăng từ 15:10
  get_metrics(payment-gateway)         → metric gateway KHÔNG lệch (tín hiệu âm tính)
  get_dependencies(payment-gateway)    → thấy phụ thuộc third-party-provider
  get_error_breakdown(third-party-provider) → lỗi timeout 100% từ 15:10
  trace_request(payment-gateway)       → trace đứt tại gateway→provider
  → Verdict: third-party-provider là root cause, độ tin TRUNG BÌNH
    (đoạn cuối dựa tương quan thời gian vì trace đứt)
    Gateway chỉ là nơi lỗi LAN ĐẾN, không phải PHÁT SINH.

Tín hiệu âm tính QUAN TRỌNG:
  - metric latency gateway KHÔNG lệch baseline (giao thức fail-fast, không tăng latency)
  - KHÔNG có deploy nào trong cửa sổ
  - Metric của auth-service BÌNH THƯỜNG
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

SCENARIO = "scenario2"
DATE = "2024-01-15"
WINDOW_START_HOUR = 14        # bắt đầu ghi log từ 14:00
WINDOW_END_HOUR = 17          # kết thúc lúc 17:00
PROVIDER_FAIL_START = "15:10" # provider sập từ đây
GATEWAY_FAIL_START = "15:11"  # gateway bắt đầu báo lỗi 1 phút sau (connection timeout)

NOISE_ERROR_RATE = 0.03
PROVIDER_ERROR_RATE = 1.0     # provider sập hoàn toàn
GATEWAY_CASCADE_ERROR_RATE = 0.92  # gateway: 92% request fail khi provider sập

REQUESTS_PER_MINUTE_NORMAL = 38
REQUESTS_PER_MINUTE_SPIKE = 35   # giảm nhẹ khi provider sập

random.seed(99)  # reproducible, khác KB1

SERVICES = ["api-gateway", "payment-gateway", "auth-service", "order-service", "third-party-provider"]
NOISE_ERROR_TYPES = ["HTTP_400", "HTTP_404", "ValidationError"]
NORMAL_MESSAGES = [
    "Request processed successfully",
    "Cache hit",
    "DB query completed",
    "Response sent",
]

DB_PATH = Path(__file__).parent / "investigation.db"


def ts_to_dt(date: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date}T{time_str}:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def minutes_range(start_hour: int, end_hour: int):
    base = datetime(2024, 1, 15, start_hour, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 15, end_hour, 0, tzinfo=timezone.utc)
    cur = base
    while cur < end:
        yield cur
        cur += timedelta(minutes=1)


provider_fail_dt = ts_to_dt(DATE, PROVIDER_FAIL_START)
gateway_fail_dt = ts_to_dt(DATE, GATEWAY_FAIL_START)


def is_provider_down(dt: datetime) -> bool:
    return dt >= provider_fail_dt


def is_gateway_cascading(dt: datetime) -> bool:
    return dt >= gateway_fail_dt


def generate_logs() -> List[tuple]:
    rows = []

    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        provider_down = is_provider_down(minute_dt)
        gateway_cascade = is_gateway_cascading(minute_dt)
        rps = REQUESTS_PER_MINUTE_SPIKE if provider_down else REQUESTS_PER_MINUTE_NORMAL

        for _ in range(rps):
            sec = random.randint(0, 59)
            req_dt = minute_dt + timedelta(seconds=sec)
            req_ts = req_dt.isoformat().replace("+00:00", "Z")

            # trace_id liền tới gateway, rồi NULL ở provider (cài đứt)
            shared_trace_id = f"tr-{random.randint(10**11, 10**12-1)}"

            # ── payment-gateway ─────────────────────────────────────
            if gateway_cascade:
                roll = random.random()
                if roll < GATEWAY_CASCADE_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, "payment-gateway", "ERROR",
                                 "Connection refused by third-party-provider",
                                 "ConnectionRefusedError", shared_trace_id))
                else:
                    rows.append((req_ts, SCENARIO, "payment-gateway", "INFO",
                                 "Request processed successfully", None, shared_trace_id))
            else:
                if random.random() < NOISE_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, "payment-gateway", "WARN",
                                 "Minor error", random.choice(NOISE_ERROR_TYPES), shared_trace_id))
                else:
                    rows.append((req_ts, SCENARIO, "payment-gateway", "INFO",
                                 random.choice(NORMAL_MESSAGES), None, shared_trace_id))

            # ── third-party-provider — trace_id = NULL khi down (cài đứt) ──
            if provider_down:
                rows.append((req_ts, SCENARIO, "third-party-provider", "ERROR",
                             "Service unavailable — upstream timeout",
                             "ServiceUnavailableError",
                             None))  # ← NULL trace_id = chỗ đứt
            else:
                if random.random() < NOISE_ERROR_RATE * 1.5:
                    rows.append((req_ts, SCENARIO, "third-party-provider", "WARN",
                                 "Slow response from upstream",
                                 "SlowResponseWarning",
                                 f"tr-{random.randint(10**11, 10**12-1)}"))
                else:
                    rows.append((req_ts, SCENARIO, "third-party-provider", "INFO",
                                 "Payment processed", None,
                                 f"tr-{random.randint(10**11, 10**12-1)}"))

            # ── Các service khác: nhiễu nhẹ, BÌNH THƯỜNG ──────────
            for svc in ["api-gateway", "auth-service", "order-service"]:
                if random.random() < NOISE_ERROR_RATE * 0.4:
                    rows.append((req_ts, SCENARIO, svc, "WARN",
                                 "Minor error", random.choice(NOISE_ERROR_TYPES),
                                 f"tr-{random.randint(10**11, 10**12-1)}"))

    return rows


def generate_metrics() -> List[tuple]:
    rows = []

    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        ts = minute_dt.isoformat().replace("+00:00", "Z")
        provider_down = is_provider_down(minute_dt)
        gateway_cascade = is_gateway_cascading(minute_dt)
        is_baseline = 0 if provider_down else 1

        # payment-gateway: latency KHÔNG lệch — fail-fast nên trả lỗi nhanh
        gw_latency = random.gauss(118, 8)          # baseline ~120ms
        gw_error_rate = 0.92 if gateway_cascade else random.gauss(0.3, 0.05)
        rows.append((ts, SCENARIO, "payment-gateway", "latency_p99",
                     max(gw_latency, 50), is_baseline))
        rows.append((ts, SCENARIO, "payment-gateway", "error_rate",
                     max(gw_error_rate, 0), is_baseline))

        # third-party-provider: lỗi tăng vọt
        prov_latency = 5000.0 if provider_down else random.gauss(195, 15)
        prov_error_rate = 1.0 if provider_down else random.gauss(0.5, 0.1)
        rows.append((ts, SCENARIO, "third-party-provider", "latency_p99",
                     max(prov_latency, 0), is_baseline))
        rows.append((ts, SCENARIO, "third-party-provider", "error_rate",
                     max(prov_error_rate, 0), is_baseline))

        # auth-service: bình thường hoàn toàn
        rows.append((ts, SCENARIO, "auth-service", "latency_p99",
                     random.gauss(45, 3), 1))
        rows.append((ts, SCENARIO, "auth-service", "error_rate",
                     max(random.gauss(0.1, 0.02), 0), 1))

    return rows


def generate_deploys() -> List[tuple]:
    # KB2: KHÔNG có deploy trong cửa sổ — tín hiệu âm tính
    # Deploy cuối ở cả hai service đều 3 ngày trước → không liên quan
    return [
        ("2024-01-12T09:00:00Z", SCENARIO, "payment-gateway", "v2.3.1", "success"),
        ("2024-01-12T09:30:00Z", SCENARIO, "third-party-provider", "v1.8.0", "success"),
    ]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Xóa data kịch bản 2 cũ nếu có
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

    print(f"KB2 seeded: {log_count} logs, {metric_count} metric rows, {len(deploys)} deploys")
    print(f"  Provider fail từ: {PROVIDER_FAIL_START}")
    print(f"  Gateway cascade từ: {GATEWAY_FAIL_START}")
    print(f"  Metric gateway: BÌNH THƯỜNG (tín hiệu âm tính)")
    print(f"  Deploy: {len(deploys)} records cũ 3 ngày trước (không liên quan)")

    conn.close()


if __name__ == "__main__":
    main()
