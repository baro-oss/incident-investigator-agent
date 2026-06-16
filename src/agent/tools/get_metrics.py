"""
Tool: get_metrics

Hỏi: "Metric nào của service X bất thường trong khoảng thời gian này? So với baseline ra sao?"
Dùng khi: cần xác nhận service có thực sự bị ảnh hưởng về hiệu năng (latency, error rate, throughput)
  hay metric bình thường (→ loại trừ service đó là root cause).
Không dùng để: phân tích loại lỗi cụ thể (→ get_error_breakdown).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from agent.storage.db import open_db
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation, Tool

_METRIC_LABELS = {
    "latency_p99": "latency p99 (ms)",
    "error_rate": "error rate (errors/min)",
    "request_count": "request count (/min)",
}


def _run(params: Dict[str, Any]) -> Observation:
    service: str = params["service"]
    time_window: str = params["time_window"]
    metric_name: str = params.get("metric_name", "latency_p99")
    scenario: str = params.get("scenario", "scenario1")
    date: str = params.get("date", "2024-01-15")

    # L4: validate time_window format
    if not re.match(r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$", time_window.strip()):
        return Observation(
            summary=f"time_window '{time_window}' không đúng định dạng HH:MM-HH:MM.",
            aggregates={}, samples=[], total_count=0, truncated=False,
            metadata={"tool_name": "get_metrics", "error": "invalid_time_window"},
        )

    start_str, end_str = time_window.split("-")
    ts_start = f"{date}T{start_str}:00Z"
    ts_end = f"{date}T{end_str}:00Z"

    conn = open_db()

    # Baseline từ catalog
    catalog_row = conn.execute(
        "SELECT baseline_latency_p99, baseline_error_rate FROM service_catalog WHERE service=?",
        (service,),
    ).fetchone()

    baseline_map = {
        "latency_p99": catalog_row["baseline_latency_p99"] if catalog_row else 100.0,
        "error_rate": catalog_row["baseline_error_rate"] if catalog_row else 0.5,
        "request_count": None,  # không có baseline cố định
    }
    baseline_val = baseline_map.get(metric_name)

    # Thống kê trong window
    stats = conn.execute(
        """
        SELECT
            COUNT(*) as data_points,
            ROUND(AVG(value), 2) as avg_val,
            ROUND(MIN(value), 2) as min_val,
            ROUND(MAX(value), 2) as max_val
        FROM metrics
        WHERE scenario=? AND service=? AND metric_name=?
          AND timestamp>=? AND timestamp<?
        """,
        (scenario, service, metric_name, ts_start, ts_end),
    ).fetchone()

    # Tìm peak và thời điểm peak
    peak_row = conn.execute(
        """
        SELECT timestamp, value
        FROM metrics
        WHERE scenario=? AND service=? AND metric_name=?
          AND timestamp>=? AND timestamp<?
        ORDER BY value DESC LIMIT 1
        """,
        (scenario, service, metric_name, ts_start, ts_end),
    ).fetchone()

    # Samples: ≤5 data point để LLM "nhìn tận mắt"
    sample_rows = conn.execute(
        """
        SELECT timestamp, value
        FROM metrics
        WHERE scenario=? AND service=? AND metric_name=?
          AND timestamp>=? AND timestamp<?
        ORDER BY timestamp
        LIMIT ?
        """,
        (scenario, service, metric_name, ts_start, ts_end, SAMPLES_HARD_CAP),
    ).fetchall()
    samples = [{"timestamp": r["timestamp"], metric_name: r["value"]} for r in sample_rows]

    total_points = stats["data_points"] if stats else 0
    conn.close()

    if total_points == 0:
        return Observation(
            summary=f"Không có dữ liệu metric '{metric_name}' cho {service} trong {time_window}.",
            aggregates={},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={"tool_name": "get_metrics", "service": service,
                      "time_window": time_window, "metric_name": metric_name},
        )

    label = _METRIC_LABELS.get(metric_name, metric_name)
    avg_val = stats["avg_val"]
    max_val = stats["max_val"]
    peak_time = peak_row["timestamp"][11:16] if peak_row else "?"

    # So baseline và xây summary
    aggregates: Dict[str, Any] = {
        "avg": f"{avg_val} {label.split('(')[-1].strip(')')}",
        "max": f"{max_val} @ {peak_time}",
        "min": str(stats["min_val"]),
        "data_points": total_points,
    }

    if baseline_val is not None and baseline_val > 0:
        multiplier = round(avg_val / baseline_val, 1)
        aggregates["baseline"] = str(baseline_val)
        aggregates["vs_baseline"] = f"{multiplier}x"

        if multiplier >= 3:
            severity = "LỆCH NGHIÊM TRỌNG"
            direction = "cao hơn"
        elif multiplier >= 1.5:
            severity = "lệch đáng kể"
            direction = "cao hơn"
        elif multiplier <= 0.5:
            severity = "thấp bất thường"
            direction = "thấp hơn"
        else:
            severity = "bình thường"
            direction = "bằng"

        if severity in ("LỆCH NGHIÊM TRỌNG", "lệch đáng kể"):
            summary = (
                f"{service}: {label} trung bình {avg_val} trong {time_window} — "
                f"{severity} ({multiplier}x baseline={baseline_val}). "
                f"Peak {max_val} lúc {peak_time}."
            )
        elif severity == "bình thường":
            summary = (
                f"{service}: {label} bình thường trong {time_window} "
                f"(avg={avg_val}, baseline={baseline_val}, ratio={multiplier}x). "
                f"Metric này KHÔNG lệch — có thể loại trừ {service} là nguồn lỗi hiệu năng."
            )
        else:
            summary = (
                f"{service}: {label} avg={avg_val}, baseline={baseline_val} ({multiplier}x). "
                f"Mức độ {severity}."
            )
    else:
        summary = (
            f"{service}: {label} avg={avg_val}, max={max_val} lúc {peak_time} "
            f"trong {time_window}. (Không có baseline để so sánh.)"
        )

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=samples,
        total_count=total_points,
        truncated=total_points > SAMPLES_HARD_CAP,
        metadata={
            "tool_name": "get_metrics",
            "service": service,
            "time_window": time_window,
            "metric_name": metric_name,
            "scenario": scenario,
        },
    )


# ── Tool definition ────────────────────────────────────────────────────────────

get_metrics = Tool(
    name="get_metrics",
    description=(
        "Lấy thống kê metric hiệu năng (latency p99, error rate, request count) của một service "
        "trong khoảng thời gian, so sánh với baseline bình thường. "
        "Dùng để: (1) xác nhận service có thực sự bị ảnh hưởng hiệu năng không, "
        "(2) tìm thời điểm metric bắt đầu lệch, "
        "(3) loại trừ service là root cause khi metric BÌNH THƯỜNG. "
        "Metric hợp lệ: 'latency_p99', 'error_rate', 'request_count'. "
        "KHÔNG dùng để phân tích loại lỗi cụ thể (→ get_error_breakdown)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Tên service (vd: 'payment-gateway')",
            },
            "time_window": {
                "type": "string",
                "description": "Cửa sổ thời gian 'HH:MM-HH:MM' (vd: '14:00-15:00')",
            },
            "metric_name": {
                "type": "string",
                "enum": ["latency_p99", "error_rate", "request_count"],
                "description": "Metric cần xem. Mặc định: 'latency_p99'",
                "default": "latency_p99",
            },
            "scenario": {
                "type": "string",
                "description": "Kịch bản: 'scenario1' hoặc 'scenario2'. Mặc định: 'scenario1'",
                "default": "scenario1",
            },
            "date": {
                "type": "string",
                "description": "Ngày 'YYYY-MM-DD'. Mặc định: '2024-01-15'",
                "default": "2024-01-15",
            },
        },
        "required": ["service", "time_window"],
    },
    run=_run,
)
