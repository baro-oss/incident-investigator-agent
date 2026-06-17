"""
Tool: get_transaction_anomaly

Hỏi: "Merchant nào có tỷ lệ fail hoặc refund bất thường? Kênh nào có lỗi phổ biến nhất?"
Dùng khi: cần xác định merchant hoặc kênh giao dịch đang có hành vi bất thường
  (fail_rate cao, refund_rate cao, lỗi tập trung).
Không dùng để: xem tổng doanh thu (→ get_revenue_breakdown),
  xem chi tiết trạng thái merchant (→ get_merchant_status).
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
    channel: Optional[str] = params.get("channel")

    start_str, end_str = time_window.split("-")
    ts_start = f"{date}T{start_str}:00Z"
    ts_end = f"{date}T{end_str}:00Z"

    conn = open_db()

    # --- Baseline fail_rate và refund_rate toàn bộ (is_baseline=1) ---
    baseline_stats = conn.execute(
        """
        SELECT
            ROUND((100.0 * SUM(CASE WHEN status='failed'   THEN 1 ELSE 0 END) / COUNT(*))::numeric, 2) AS fail_rate,
            ROUND((100.0 * SUM(CASE WHEN status='refunded' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 2) AS refund_rate
        FROM ft_transactions
        WHERE scenario=? AND is_baseline=1
        """,
        (scenario,),
    ).fetchone()
    bl_fail = baseline_stats["fail_rate"] if baseline_stats and baseline_stats["fail_rate"] else 2.0
    bl_refund = baseline_stats["refund_rate"] if baseline_stats and baseline_stats["refund_rate"] else 1.5

    # --- Aggregate theo merchant ---
    merchant_filter = "AND merchant_id=?" if merchant_id else ""
    channel_filter = "AND channel=?" if channel else ""
    base_params_merchant = [scenario, ts_start, ts_end]
    if merchant_id:
        base_params_merchant.append(merchant_id)
    if channel:
        base_params_merchant.append(channel)

    merchant_rows = conn.execute(
        f"""
        SELECT
            merchant_id,
            COUNT(*)                                                          AS total,
            SUM(CASE WHEN status='failed'   THEN 1 ELSE 0 END)              AS failed,
            SUM(CASE WHEN status='refunded' THEN 1 ELSE 0 END)              AS refunded,
            ROUND((100.0 * SUM(CASE WHEN status='failed'   THEN 1 ELSE 0 END) / COUNT(*))::numeric, 2) AS fail_rate,
            ROUND((100.0 * SUM(CASE WHEN status='refunded' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 2) AS refund_rate
        FROM ft_transactions
        WHERE scenario=? AND is_baseline=0
          AND timestamp>=? AND timestamp<?
          {merchant_filter}
          {channel_filter}
        GROUP BY merchant_id
        ORDER BY refund_rate DESC, fail_rate DESC
        """,
        base_params_merchant,
    ).fetchall()

    # --- Aggregate lỗi phổ biến theo channel ---
    channel_rows = conn.execute(
        """
        SELECT
            channel,
            error_type,
            COUNT(*) AS cnt
        FROM ft_transactions
        WHERE scenario=? AND is_baseline=0
          AND timestamp>=? AND timestamp<?
          AND status='failed'
          AND error_type IS NOT NULL
        GROUP BY channel, error_type
        ORDER BY channel, cnt DESC
        """,
        (scenario, ts_start, ts_end),
    ).fetchall()

    conn.close()

    if not merchant_rows:
        return Observation(
            summary=(
                f"Không có dữ liệu giao dịch trong window {time_window} "
                f"cho scenario={scenario}"
                + (f", merchant={merchant_id}" if merchant_id else "")
                + (f", channel={channel}" if channel else "")
                + "."
            ),
            aggregates={},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={
                "tool_name": "get_transaction_anomaly",
                "time_window": time_window,
                "scenario": scenario,
            },
        )

    # --- Aggregates: per merchant ---
    aggregates: Dict[str, Any] = {}
    anomalous_merchants = []  # (merchant_id, refund_rate, refund_multiplier, fail_rate, fail_multiplier)

    for row in merchant_rows:
        mid = row["merchant_id"]
        refund_mult = round(row["refund_rate"] / max(bl_refund, 0.01), 1) if row["refund_rate"] else 0
        fail_mult = round(row["fail_rate"] / max(bl_fail, 0.01), 1) if row["fail_rate"] else 0

        aggregates[mid] = {
            "total": row["total"],
            "failed": row["failed"],
            "refunded": row["refunded"],
            "fail_rate": f"{row['fail_rate']}%",
            "refund_rate": f"{row['refund_rate']}%",
            "fail_rate_vs_baseline": f"{fail_mult}x",
            "refund_rate_vs_baseline": f"{refund_mult}x",
        }

        if refund_mult >= 3 or fail_mult >= 3:
            anomalous_merchants.append((mid, row["refund_rate"], refund_mult, row["fail_rate"], fail_mult))

    # Top error_type per channel
    channel_errors: Dict[str, str] = {}
    seen_channels: set = set()
    for row in channel_rows:
        if row["channel"] not in seen_channels:
            channel_errors[row["channel"]] = f"{row['error_type']} ({row['cnt']})"
            seen_channels.add(row["channel"])
    if channel_errors:
        aggregates["_top_error_by_channel"] = channel_errors

    # --- Samples: từ merchant bất thường nhất, hoặc merchant được chỉ định ---
    conn2 = open_db()
    if merchant_id:
        sample_merchant = merchant_id
    elif anomalous_merchants:
        sample_merchant = anomalous_merchants[0][0]
    else:
        sample_merchant = merchant_rows[0]["merchant_id"] if merchant_rows else None

    if sample_merchant:
        channel_param = [channel] if channel else []
        channel_q = "AND channel=?" if channel else ""
        sample_raw = conn2.execute(
            f"""
            SELECT timestamp, merchant_id, channel, amount, status, error_type, processor_id
            FROM ft_transactions
            WHERE scenario=? AND is_baseline=0
              AND timestamp>=? AND timestamp<?
              AND merchant_id=?
              {channel_q}
            ORDER BY timestamp
            LIMIT ?
            """,
            [scenario, ts_start, ts_end, sample_merchant] + channel_param + [SAMPLES_HARD_CAP],
        ).fetchall()
        samples = [dict(r) for r in sample_raw]
    else:
        samples = []
    conn2.close()

    total_tx = sum(r["total"] for r in merchant_rows)

    # --- Summary diễn giải ---
    if anomalous_merchants:
        # Merchant bất thường nhất
        worst = anomalous_merchants[0]
        wmid, w_refund, w_refund_mult, w_fail, w_fail_mult = worst
        details = []
        if w_refund_mult >= 3:
            details.append(f"refund_rate {w_refund}% ({w_refund_mult}x baseline {bl_refund}%)")
        if w_fail_mult >= 3:
            details.append(f"fail_rate {w_fail}% ({w_fail_mult}x baseline {bl_fail}%)")
        detail_str = ", ".join(details)

        other_anomalous = [a[0] for a in anomalous_merchants[1:]]
        other_note = f" Cũng bất thường: {', '.join(other_anomalous)}." if other_anomalous else ""
        normal_count = len(merchant_rows) - len(anomalous_merchants)
        normal_note = f" {normal_count} merchant khác bình thường." if normal_count > 0 else ""

        channel_note = ""
        if channel_errors:
            top_channel = next(iter(channel_errors))
            channel_note = f" Kênh {top_channel}: lỗi chủ đạo là {channel_errors[top_channel]}."

        summary = (
            f"{wmid}: {detail_str} trong {time_window}."
            f"{other_note}{normal_note}{channel_note}"
        )
    else:
        # Không có anomaly
        top_mid = merchant_rows[0]["merchant_id"]
        top_rr = merchant_rows[0]["refund_rate"]
        summary = (
            f"Không phát hiện merchant bất thường trong {time_window}. "
            f"fail_rate và refund_rate ở mức bình thường "
            f"(baseline fail={bl_fail}%, refund={bl_refund}%). "
            f"Merchant rate cao nhất: {top_mid} (refund={top_rr}%)."
        )

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=samples,
        total_count=total_tx,
        truncated=total_tx > SAMPLES_HARD_CAP,
        metadata={
            "tool_name": "get_transaction_anomaly",
            "time_window": time_window,
            "scenario": scenario,
            "date": date,
            "merchant_id": merchant_id,
            "channel": channel,
            "baseline_fail_rate": bl_fail,
            "baseline_refund_rate": bl_refund,
        },
    )


# ── Tool definition ────────────────────────────────────────────────────────────

get_transaction_anomaly = Tool(
    name="get_transaction_anomaly",
    description=(
        "Phân tích fail_rate và refund_rate giao dịch theo merchant và channel trong một khoảng thời gian, "
        "so sánh với baseline bình thường. "
        "Trả về: fail_rate%, refund_rate% per merchant (với bội số x baseline), "
        "và error_type phổ biến nhất per channel. "
        "Dùng khi: (1) nghi merchant cụ thể gây refund/fail bất thường, "
        "(2) xác định kênh nào đang có vấn đề, "
        "(3) phân biệt lỗi tập trung ở một merchant vs toàn hệ thống. "
        "Có thể filter theo merchant_id hoặc channel cụ thể. "
        "KHÔNG dùng để xem tổng doanh thu (→ get_revenue_breakdown) "
        "hay thông tin chi tiết merchant (→ get_merchant_status)."
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
                "description": "Filter theo merchant cụ thể (vd: 'merch-buzz'). Nếu bỏ trống → xem tất cả merchant.",
            },
            "channel": {
                "type": "string",
                "description": "Filter theo kênh thanh toán (vd: 'credit_card'). Nếu bỏ trống → xem tất cả kênh.",
            },
        },
        "required": ["time_window"],
    },
    run=_run,
)
