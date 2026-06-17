"""
Sinh data Kịch bản DEMO2: deploy auth-service v1.2.0 lúc 14:05 → JWT decode bỏ
clock-skew leeway → token hợp lệ bị từ chối oan → HTTP_401 / AuthenticationError ở
auth-service từ 14:08, lan ngược lên payment-gateway → api-gateway / order-service.

Root cause neo trong SOURCE (đọc qua GitLab code MCP):
  v1.2.0 bỏ `leeway=30` trong jwt.decode + xoá try/except AuthenticationError + bump
  PyJWT 2.7→2.8 → token vừa phát hành (đồng hồ lệch) bị reject → 401 hàng loạt.

Đường điều tra lý tưởng:
  get_error_breakdown(auth-service) → ~78% HTTP_401 sau 14:08
  get_metrics(auth-service)         → error_rate vọt, latency lệch baseline 45ms
  get_recent_deploys(auth-service)  → v1.2.0 lúc 14:05 ngay trước spike
  get_dependencies(auth-service)    → leaf node, được gọi bởi payment-gateway
                                       (→ blast radius lan lên api-gateway / order-service)
  get_code_diff(auth-service, v1.2.0) → RISK: removed-error-handling (leeway + try/except bị xoá)
  → Verdict: deploy v1.2.0 là root cause, độ tin CAO, neo bằng chứng code.

Khác scenario "demo": ngày/giờ riêng (14:00-15:00 khớp parse_alert_time floor-to-hour),
service auth-service, version v1.2.0/v1.1.0 (khớp tag GitLab demo), scenario="demo2".

Chạy: python3 data/seed_demo2.py
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

SCENARIO = "demo2"
DATE = "2026-06-17"            # ngày demo (parse_alert_time floor-to-hour → 14:00-15:00)
INCIDENT_HOUR = 14            # giờ xảy ra sự cố (baseline = mọi phút trước giờ này)
WINDOW_START_HOUR = 13        # ghi log từ 13:00 (có baseline trước incident)
WINDOW_END_HOUR = 16          # kết thúc 16:00
DEPLOY_TIME = "14:05"         # mốc deploy v1.2.0
SPIKE_START = "14:08"         # lỗi 401 bắt đầu tăng sau đây (3 phút sau deploy)
VERSION_FAULTY = "v1.2.0"
VERSION_BEFORE = "v1.1.0"
TARGET_SERVICE = "auth-service"

NOISE_ERROR_RATE = 0.03       # 3% lỗi vặt trước sự cố
SPIKE_401_RATE = 0.78         # 78% request sau spike là HTTP_401 (token bị reject oan)
SPIKE_ERROR_RATE = 0.92       # tổng lỗi sau spike (78% 401 + ~14% InvalidTokenError)

REQUESTS_PER_MINUTE_NORMAL = 60   # auth-service traffic cao (mọi request đều xác thực)
REQUESTS_PER_MINUTE_SPIKE = 58

SIMULATED_TOTAL_ERRORS = 22418
SIMULATED_TOTAL_REQUESTS = 64902

random.seed(2027)

SERVICES = ["api-gateway", "payment-gateway", "auth-service", "order-service", "third-party-provider"]
NOISE_ERROR_TYPES = ["HTTP_400", "HTTP_404", "ValidationError", "RateLimitError"]
NORMAL_MESSAGES = [
    "Token verified, claims extracted",
    "Authorization granted",
    "JWT signature valid",
    "Session refreshed",
]

# Service nào bị ảnh hưởng lan (caller của auth-service, trực tiếp + transitive) và
# hệ số nhân latency/error trong lúc spike. third-party-provider không liên quan.
DOWNSTREAM_SPIKE = {
    "payment-gateway": 3.2,   # caller trực tiếp của auth-service → ảnh hưởng nặng nhất
    "api-gateway":     2.1,   # transitive qua payment-gateway / order-service
    "order-service":   1.9,   # transitive qua payment-gateway
}

# baseline (latency_p99 ms, error_rate %/phút) — khớp catalog.json
BASELINES = {
    "api-gateway":          (95, 0.8),
    "auth-service":         (45, 0.1),
    "order-service":        (80, 0.2),
    "third-party-provider": (200, 0.5),
    "payment-gateway":      (120, 0.3),
}

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
                if roll < SPIKE_401_RATE:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "ERROR",
                                 "Authentication rejected — JWT validation failed: "
                                 "token rejected after clock-skew tolerance removed (HTTP 401)",
                                 "HTTP_401", trace_id))
                elif roll < SPIKE_ERROR_RATE:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "ERROR",
                                 "jwt.InvalidTokenError: signature/exp check failed without leeway",
                                 "InvalidTokenError", trace_id))
                else:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "INFO",
                                 "Token verified, claims extracted", None, trace_id))
            else:
                if random.random() < NOISE_ERROR_RATE:
                    err_type = random.choice(NOISE_ERROR_TYPES)
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "WARN",
                                 f"Intermittent error: {err_type}", err_type, trace_id))
                else:
                    rows.append((req_ts, SCENARIO, TARGET_SERVICE, "INFO",
                                 random.choice(NORMAL_MESSAGES), None, trace_id))

            # Lỗi lan: caller của auth-service thấy 401 dội ngược (downstream auth failures).
            for svc in [s for s in SERVICES if s != TARGET_SERVICE]:
                if spike and svc in DOWNSTREAM_SPIKE:
                    # tỷ lệ lan tỉ lệ với mức ảnh hưởng (api-gw nhẹ hơn payment-gw)
                    lan_rate = 0.10 * DOWNSTREAM_SPIKE[svc]
                    if random.random() < lan_rate:
                        rows.append((req_ts, SCENARIO, svc, "ERROR",
                                     "Upstream auth failure — downstream request rejected (HTTP 401)",
                                     "HTTP_401",
                                     f"tr-{random.randint(10**11, 10**12-1)}"))
                        continue
                if random.random() < NOISE_ERROR_RATE * 0.5:
                    err_type = random.choice(NOISE_ERROR_TYPES)
                    rows.append((req_ts, SCENARIO, svc, "WARN",
                                 f"Minor error: {err_type}", err_type,
                                 f"tr-{random.randint(10**11, 10**12-1)}"))
    return rows


# ── Sinh metrics ──────────────────────────────────────────────────────────────

def generate_metrics() -> List[tuple]:
    rows = []
    baseline_cutoff = datetime.combine(_DATE_D, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=INCIDENT_HOUR)
    for minute_dt in minutes_range(WINDOW_START_HOUR, WINDOW_END_HOUR):
        spike = is_after_spike(minute_dt)
        minute_ts = minute_dt.isoformat().replace("+00:00", "Z")
        is_baseline = 1 if minute_dt < baseline_cutoff else 0

        # Target: auth-service — error_rate vọt cao, latency tăng vừa (decode nhanh, lỗi là logic 401)
        base_lat, base_err = BASELINES[TARGET_SERVICE]
        if spike:
            latency = random.uniform(base_lat * 2.2, base_lat * 2.9)   # 45 → ~110ms
            err_rate = random.uniform(34, 42)
        else:
            latency = random.uniform(base_lat * 0.9, base_lat * 1.1)
            err_rate = random.uniform(0.05, 0.3)
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "latency_p99", round(latency, 1), is_baseline))
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "error_rate", round(err_rate, 2), is_baseline))

        req_count = REQUESTS_PER_MINUTE_SPIKE if spike else REQUESTS_PER_MINUTE_NORMAL
        rows.append((minute_ts, SCENARIO, TARGET_SERVICE, "request_count",
                     req_count + random.randint(-3, 3), is_baseline))

        for svc in [s for s in SERVICES if s != TARGET_SERVICE]:
            base_lat, base_err = BASELINES.get(svc, (100, 0.3))
            mult = DOWNSTREAM_SPIKE.get(svc, 1.0)
            if spike and svc in DOWNSTREAM_SPIKE:
                lat = random.uniform(base_lat * mult * 0.9, base_lat * mult * 1.1)
                err = random.uniform(base_err * 8, base_err * 14)   # lỗi lan lên caller
            else:
                lat = random.uniform(base_lat * 0.9, base_lat * 1.1)
                err = random.uniform(0, base_err * 1.5)
            rows.append((minute_ts, SCENARIO, svc, "latency_p99", round(lat, 1), is_baseline))
            rows.append((minute_ts, SCENARIO, svc, "error_rate", round(err, 2), is_baseline))
    return rows


# ── Sinh deploys ──────────────────────────────────────────────────────────────

def generate_deploys() -> List[tuple]:
    return [
        # Deploy lỗi — root cause
        (ts(DEPLOY_TIME), SCENARIO, TARGET_SERVICE, VERSION_FAULTY, "success"),
        # Deploy trước đó — baseline
        (ts("13:10"), SCENARIO, TARGET_SERVICE, VERSION_BEFORE, "success"),
        # Deploy nhiễu — đặt trên service NGOÀI blast radius (third-party-provider không
        # có metrics tăng) để agent dễ loại trừ; tránh red-herring trên caller (payment-gateway
        # / order-service có latency cao do lan → dễ thành giả thuyết cạnh tranh giả).
        (ts("13:25"), SCENARIO, "third-party-provider", "v5.1.0", "success"),
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
    print(f"\nScenario DEMO2 seeded → {target}")
    print(f"  Date:   {DATE} | window khuyến nghị: 14:00-15:00")
    print(f"  Deploy: {TARGET_SERVICE} {VERSION_FAULTY} at {DEPLOY_TIME}")
    print(f"  Spike:  HTTP_401 rate {SPIKE_401_RATE*100:.0f}% from {SPIKE_START}")


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    db = str(root / "data" / "investigation.db")
    catalog = str(root / "data" / "catalog.json")
    seed(db, catalog)
