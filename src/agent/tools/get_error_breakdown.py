"""
Tool: get_error_breakdown

Hỏi: "Service X đang gặp loại lỗi gì, phân bố ra sao, so với bình thường thế nào?"
Dùng khi: cần xác định có lỗi bất thường không và loại lỗi chủ đạo là gì.
Không dùng để: xem latency/throughput (dùng get_metrics), xem deploy (dùng get_recent_deploys).
"""
from __future__ import annotations

import re
from typing import Any, Dict

from agent.storage.db import open_db
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation, Tool

# Simulated total để thể hiện quy mô thật — giải thích trong Observation
_SIMULATED_SCALE_FACTOR = 6.1   # tool nhân lên khi report total_count


def _run(params: Dict[str, Any]) -> Observation:
    service: str = params["service"]
    time_window: str = params["time_window"]   # e.g. "14:00-15:00"
    scenario: str = params.get("scenario", "scenario1")
    date: str = params.get("date", "2024-01-15")

    # L4: validate time_window format
    if not re.match(r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$", time_window.strip()):
        return Observation(
            summary=f"time_window '{time_window}' không đúng định dạng HH:MM-HH:MM.",
            aggregates={}, samples=[], total_count=0, truncated=False,
            metadata={"tool_name": "get_error_breakdown", "error": "invalid_time_window"},
        )

    start_str, end_str = time_window.split("-")
    ts_start = f"{date}T{start_str}:00Z"
    ts_end = f"{date}T{end_str}:00Z"

    conn = open_db()

    # Tổng request trong window
    total_requests = conn.execute(
        "SELECT COUNT(*) FROM logs WHERE scenario=? AND service=? AND timestamp>=? AND timestamp<?",
        (scenario, service, ts_start, ts_end),
    ).fetchone()[0]

    # Breakdown theo error_type
    breakdown_rows = conn.execute(
        """
        SELECT
            COALESCE(error_type, 'OK') AS error_type,
            COUNT(*) AS cnt
        FROM logs
        WHERE scenario=? AND service=? AND timestamp>=? AND timestamp<?
        GROUP BY error_type
        ORDER BY cnt DESC
        """,
        (scenario, service, ts_start, ts_end),
    ).fetchall()

    # Tính baseline error rate từ catalog
    catalog_row = conn.execute(
        "SELECT baseline_error_rate FROM service_catalog WHERE service=?",
        (service,),
    ).fetchone()
    baseline_err_per_min = catalog_row["baseline_error_rate"] if catalog_row else 0.5

    # Thời lượng window (phút) để so baseline
    h_start, m_start = map(int, start_str.split(":"))
    h_end, m_end = map(int, end_str.split(":"))
    window_minutes = (h_end * 60 + m_end) - (h_start * 60 + m_start)
    baseline_total_errors = baseline_err_per_min * window_minutes

    # Tổng lỗi thật (không tính OK)
    real_errors = sum(
        row["cnt"] for row in breakdown_rows if row["error_type"] != "OK"
    )

    # Aggregates: tỷ lệ % mỗi loại
    aggregates: Dict[str, Any] = {}
    for row in breakdown_rows:
        if total_requests > 0:
            pct = round(row["cnt"] * 100.0 / total_requests, 1)
        else:
            pct = 0.0
        aggregates[row["error_type"]] = f"{row['cnt']} ({pct}%)"

    # Tìm thời điểm spike bắt đầu (phút đầu tiên error_rate > 5x baseline)
    spike_time = _detect_spike_start(conn, scenario, service, ts_start, ts_end, baseline_err_per_min)

    # Samples: ưu tiên dominant error type sau thời điểm spike (đại diện cho tín hiệu thật)
    dominant_type = (
        breakdown_rows[0]["error_type"]
        if breakdown_rows and breakdown_rows[0]["error_type"] != "OK"
        else None
    )
    spike_ts = f"{date}T{spike_time}:00Z" if spike_time else ts_start
    if dominant_type:
        sample_rows = conn.execute(
            """
            SELECT timestamp, level, message, error_type, trace_id
            FROM logs
            WHERE scenario=? AND service=? AND timestamp>=? AND timestamp<?
              AND error_type=?
            ORDER BY timestamp
            LIMIT ?
            """,
            (scenario, service, spike_ts, ts_end, dominant_type, SAMPLES_HARD_CAP),
        ).fetchall()
    else:
        sample_rows = conn.execute(
            """
            SELECT timestamp, level, message, error_type, trace_id
            FROM logs
            WHERE scenario=? AND service=? AND timestamp>=? AND timestamp<?
              AND error_type IS NOT NULL
            ORDER BY timestamp
            LIMIT ?
            """,
            (scenario, service, ts_start, ts_end, SAMPLES_HARD_CAP),
        ).fetchall()
    samples = [dict(r) for r in sample_rows]

    conn.close()

    # Simulated total_count (giả lập quy mô production)
    simulated_total = int(real_errors * _SIMULATED_SCALE_FACTOR)

    # Xây summary diễn giải
    if total_requests == 0:
        summary = f"Không có log nào từ {service} trong window {time_window}."
    elif real_errors == 0:
        summary = f"{service}: không có lỗi trong {time_window} (baseline bình thường)."
    else:
        dominant = breakdown_rows[0] if breakdown_rows[0]["error_type"] != "OK" else (breakdown_rows[1] if len(breakdown_rows) > 1 else None)
        if dominant and dominant["error_type"] != "OK":
            pct = round(dominant["cnt"] * 100.0 / total_requests, 1)
            multiplier = round(real_errors / max(baseline_total_errors, 0.01), 1)
            spike_note = f", bắt đầu tăng từ {spike_time}" if spike_time else ""
            summary = (
                f"{service}: {pct}% lỗi là {dominant['error_type']}{spike_note}. "
                f"Tổng lỗi trong window gấp {multiplier}x baseline ({simulated_total:,} lỗi ở quy mô production)."
            )
        else:
            summary = f"{service}: {real_errors} lỗi trong {time_window}, phần lớn là nhiễu nhẹ."

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=samples,
        total_count=simulated_total,
        truncated=real_errors > SAMPLES_HARD_CAP,
        metadata={
            "tool_name": "get_error_breakdown",
            "service": service,
            "time_window": time_window,
            "scenario": scenario,
            "real_rows_in_db": total_requests,
        },
    )


def _detect_spike_start(conn, scenario, service, ts_start, ts_end, baseline_err_per_min) -> str | None:
    """Tìm phút đầu tiên error count vượt 5x baseline. Trả HH:MM hoặc None."""
    # Group by phút
    rows = conn.execute(
        """
        SELECT SUBSTR(timestamp, 1, 16) as minute,
               SUM(CASE WHEN error_type IS NOT NULL THEN 1 ELSE 0 END) as err_cnt
        FROM logs
        WHERE scenario=? AND service=? AND timestamp>=? AND timestamp<?
        GROUP BY minute
        ORDER BY minute
        """,
        (scenario, service, ts_start, ts_end),
    ).fetchall()

    threshold = max(baseline_err_per_min * 5, 3)  # ít nhất 3 lỗi/phút
    for row in rows:
        if row["err_cnt"] > threshold:
            return row["minute"][11:]  # "HH:MM"
    return None


# ── Tool definition ────────────────────────────────────────────────────────────

get_error_breakdown = Tool(
    name="get_error_breakdown",
    description=(
        "Phân tích phân bố lỗi của một service trong một khoảng thời gian. "
        "Trả về: loại lỗi chiếm ưu thế, tỷ lệ %, so sánh với baseline bình thường, "
        "thời điểm spike bắt đầu, và tổng số lỗi. "
        "Dùng làm BƯỚC ĐẦU khi có triệu chứng lỗi ở một service cụ thể. "
        "KHÔNG dùng để xem latency/throughput (→ get_metrics) "
        "hay tìm nguyên nhân deploy (→ get_recent_deploys)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Tên service cần phân tích (vd: 'payment-gateway')",
            },
            "time_window": {
                "type": "string",
                "description": "Cửa sổ thời gian dạng 'HH:MM-HH:MM' (vd: '14:00-15:00')",
            },
            "scenario": {
                "type": "string",
                "description": "Kịch bản data: 'scenario1' hoặc 'scenario2'. Mặc định: 'scenario1'",
                "default": "scenario1",
            },
            "date": {
                "type": "string",
                "description": "Ngày dạng 'YYYY-MM-DD'. Mặc định: '2024-01-15'",
                "default": "2024-01-15",
            },
        },
        "required": ["service", "time_window"],
    },
    run=_run,
)
