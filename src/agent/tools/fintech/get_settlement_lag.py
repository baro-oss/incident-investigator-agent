"""
Tool: get_settlement_lag

Hỏi: "Quá trình đối soát/settlement có bị chậm bất thường không?"
Dùng khi: cần xác định xem settlement đang bị trễ hay hoạt động bình thường,
  phân tích theo merchant để tìm merchant nào bị ảnh hưởng nặng nhất.
Không dùng để: xem fail_rate/refund_rate (→ get_transaction_anomaly),
  xem doanh thu (→ get_revenue_breakdown), xem trạng thái merchant (→ get_merchant_status).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agent.storage.db import open_db
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation, Tool


def _run(params: Dict[str, Any]) -> Observation:
    time_window: str = params["time_window"]
    scenario: str = params.get("scenario", "scenario_fintech1")
    date: str = params.get("date", "2024-01-15")
    merchant_id: Optional[str] = params.get("merchant_id")

    start_str, end_str = time_window.split("-")
    ts_start = f"{date}T{start_str}:00Z"
    ts_end = f"{date}T{end_str}:00Z"

    conn = open_db()

    # --- Baseline processing_time_s (is_baseline=1) ---
    baseline_filter = "AND merchant_id=?" if merchant_id else ""
    baseline_args = [scenario] + ([merchant_id] if merchant_id else [])

    baseline_row = conn.execute(
        f"""
        SELECT
            ROUND(AVG(processing_time_s)::numeric, 2)  AS avg_s,
            COUNT(*)                           AS row_count
        FROM ft_settlements
        WHERE scenario=? AND is_baseline=1
          {baseline_filter}
        """,
        baseline_args,
    ).fetchone()
    bl_avg = baseline_row["avg_s"] if baseline_row and baseline_row["avg_s"] else 12.0
    bl_count = baseline_row["row_count"] if baseline_row else 0

    # --- Current per merchant ---
    merchant_filter = "AND merchant_id=?" if merchant_id else ""
    current_args = [scenario, ts_start, ts_end] + ([merchant_id] if merchant_id else [])

    merchant_rows = conn.execute(
        f"""
        SELECT
            merchant_id,
            ROUND(AVG(processing_time_s)::numeric, 2)  AS avg_s,
            ROUND(MAX(processing_time_s)::numeric, 2)  AS max_s,
            ROUND(MIN(processing_time_s)::numeric, 2)  AS min_s,
            COUNT(*)                           AS cnt
        FROM ft_settlements
        WHERE scenario=? AND is_baseline=0
          AND timestamp>=? AND timestamp<?
          {merchant_filter}
        GROUP BY merchant_id
        ORDER BY avg_s DESC
        """,
        current_args,
    ).fetchall()

    # --- Overall aggregate (toàn bộ trong window) ---
    overall_row = conn.execute(
        f"""
        SELECT
            ROUND(AVG(processing_time_s)::numeric, 2) AS avg_s,
            ROUND(MAX(processing_time_s)::numeric, 2) AS max_s,
            COUNT(*)                          AS cnt
        FROM ft_settlements
        WHERE scenario=? AND is_baseline=0
          AND timestamp>=? AND timestamp<?
          {merchant_filter}
        """,
        current_args,
    ).fetchone()

    conn.close()

    if not merchant_rows or (overall_row and overall_row["cnt"] == 0):
        return Observation(
            summary=(
                f"Không có dữ liệu settlement trong window {time_window} "
                f"cho scenario={scenario}"
                + (f", merchant={merchant_id}" if merchant_id else "")
                + "."
            ),
            aggregates={},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={
                "tool_name": "get_settlement_lag",
                "time_window": time_window,
                "scenario": scenario,
            },
        )

    overall_avg = overall_row["avg_s"] if overall_row else None
    overall_max = overall_row["max_s"] if overall_row else None
    total_records = overall_row["cnt"] if overall_row else 0

    # --- Aggregates per merchant ---
    aggregates: Dict[str, Any] = {}
    lagging_merchants = []  # ratio >= 2

    for row in merchant_rows:
        mid = row["merchant_id"]
        ratio = round(row["avg_s"] / max(bl_avg, 0.01), 2) if row["avg_s"] else 0

        aggregates[mid] = {
            "current_avg_s": row["avg_s"],
            "baseline_avg_s": bl_avg,
            "ratio": f"{ratio}x",
            "max_s": row["max_s"],
            "count": row["cnt"],
        }

        if ratio >= 2.0:
            lagging_merchants.append((mid, row["avg_s"], ratio))

    # Overall ratio
    if overall_avg and bl_avg:
        overall_ratio = round(overall_avg / max(bl_avg, 0.01), 2)
    else:
        overall_ratio = None

    # --- Samples ---
    conn2 = open_db()
    sample_merchant_filter = "AND merchant_id=?" if merchant_id else ""
    sample_args = [scenario, ts_start, ts_end] + ([merchant_id] if merchant_id else []) + [SAMPLES_HARD_CAP]

    if lagging_merchants and not merchant_id:
        # Focus samples on worst lagging merchant
        worst_mid = lagging_merchants[0][0]
        sample_raw = conn2.execute(
            """
            SELECT timestamp, merchant_id, amount, processing_time_s
            FROM ft_settlements
            WHERE scenario=? AND is_baseline=0
              AND timestamp>=? AND timestamp<?
              AND merchant_id=?
            ORDER BY processing_time_s DESC
            LIMIT ?
            """,
            [scenario, ts_start, ts_end, worst_mid, SAMPLES_HARD_CAP],
        ).fetchall()
    else:
        sample_raw = conn2.execute(
            f"""
            SELECT timestamp, merchant_id, amount, processing_time_s
            FROM ft_settlements
            WHERE scenario=? AND is_baseline=0
              AND timestamp>=? AND timestamp<?
              {sample_merchant_filter}
            ORDER BY processing_time_s DESC
            LIMIT ?
            """,
            sample_args,
        ).fetchall()
    conn2.close()

    samples = [dict(r) for r in sample_raw]

    # --- Summary diễn giải ---
    if lagging_merchants:
        worst = lagging_merchants[0]
        wmid, wavg, wratio = worst
        others = [m[0] for m in lagging_merchants[1:]]
        other_note = f" Cũng lag: {', '.join(others)}." if others else ""
        normal_count = len(merchant_rows) - len(lagging_merchants)
        normal_note = f" {normal_count} merchant khác trong giới hạn bình thường." if normal_count > 0 else ""

        summary = (
            f"Settlement lag bất thường: {wmid} avg {wavg}s "
            f"({wratio}x baseline {bl_avg}s) trong {time_window}."
            f"{other_note}{normal_note}"
            f" Overall avg: {overall_avg}s."
        )
    else:
        ratio_note = f" ({overall_ratio}x baseline)" if overall_ratio else ""
        summary = (
            f"Settlement lag bình thường trong {time_window}: "
            f"avg {overall_avg}s{ratio_note}, baseline {bl_avg}s. "
            f"Không có merchant nào bị trễ đáng kể (threshold: 2x baseline). "
            f"Max: {overall_max}s."
        )

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=samples,
        total_count=total_records,
        truncated=total_records > SAMPLES_HARD_CAP,
        metadata={
            "tool_name": "get_settlement_lag",
            "time_window": time_window,
            "scenario": scenario,
            "date": date,
            "merchant_id": merchant_id,
            "baseline_avg_s": bl_avg,
            "baseline_sample_count": bl_count,
        },
    )


# ── Tool definition ────────────────────────────────────────────────────────────

get_settlement_lag = Tool(
    name="get_settlement_lag",
    description=(
        "Phân tích độ trễ xử lý settlement (processing_time_s) theo merchant trong một khoảng thời gian, "
        "so sánh với baseline bình thường. "
        "Trả về: avg/max processing_time per merchant, ratio vs baseline, và merchant nào bị lag nhất. "
        "Dùng khi: (1) nghi settlement đang bị nghẽn hoặc chậm, "
        "(2) cần xác nhận vấn đề có liên quan đến xử lý thanh toán backend không, "
        "(3) phân biệt lag toàn hệ thống vs lag tập trung ở một merchant. "
        "Có thể filter theo merchant_id cụ thể. "
        "KHÔNG dùng để xem fail/refund rate (→ get_transaction_anomaly) "
        "hay trạng thái merchant (→ get_merchant_status)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "time_window": {
                "type": "string",
                "description": "Cửa sổ thời gian dạng 'HH:MM-HH:MM' (vd: '13:00-14:00')",
            },
            "scenario": {
                "type": "string",
                "description": "Kịch bản data fintech. Mặc định: 'scenario_fintech1'",
                "default": "scenario_fintech1",
            },
            "date": {
                "type": "string",
                "description": "Ngày dạng 'YYYY-MM-DD'. Mặc định: '2024-01-15'",
                "default": "2024-01-15",
            },
            "merchant_id": {
                "type": "string",
                "description": "Filter theo merchant cụ thể (vd: 'merch-buzz'). Bỏ trống → xem tất cả merchant.",
            },
        },
        "required": ["time_window"],
    },
    run=_run,
)
