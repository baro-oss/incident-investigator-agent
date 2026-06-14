"""
Tool: get_revenue_breakdown

Hỏi: "Doanh thu theo kênh thanh toán thay đổi thế nào trong khoảng thời gian này?"
Dùng khi: cần đánh giá mức độ ảnh hưởng tài chính, xem kênh nào bị sụt doanh thu, so sánh với baseline.
Không dùng để: xem fail_rate/refund_rate theo merchant (→ get_transaction_anomaly),
  xem trạng thái merchant (→ get_merchant_status), xem độ trễ settlement (→ get_settlement_lag).
"""
from __future__ import annotations

from typing import Any, Dict

from agent.storage.db import open_db
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation, Tool


def _run(params: Dict[str, Any]) -> Observation:
    time_window: str = params["time_window"]   # "HH:MM-HH:MM"
    scenario: str = params.get("scenario", "scenario_fintech1")
    date: str = params.get("date", "2024-01-15")

    start_str, end_str = time_window.split("-")
    ts_start = f"{date}T{start_str}:00Z"
    ts_end = f"{date}T{end_str}:00Z"

    conn = open_db()

    # Doanh thu hiện tại theo channel
    current_rows = conn.execute(
        """
        SELECT
            channel,
            ROUND(SUM(revenue), 2)          AS total_revenue,
            SUM(transaction_count)          AS total_tx,
            ROUND(SUM(refund_amount), 2)    AS total_refund
        FROM ft_revenue
        WHERE scenario=? AND is_baseline=0
          AND timestamp>=? AND timestamp<?
        GROUP BY channel
        ORDER BY total_revenue DESC
        """,
        (scenario, ts_start, ts_end),
    ).fetchall()

    # Baseline theo channel (is_baseline=1, cùng khoảng giờ nếu có, hoặc toàn bộ)
    baseline_rows = conn.execute(
        """
        SELECT
            channel,
            ROUND(AVG(revenue), 4)  AS avg_revenue_per_row,
            COUNT(*)                AS row_count
        FROM ft_revenue
        WHERE scenario=? AND is_baseline=1
          AND timestamp>=? AND timestamp<?
        GROUP BY channel
        """,
        (scenario, ts_start, ts_end),
    ).fetchall()

    # Nếu không có baseline trong window → lấy toàn bộ baseline
    if not baseline_rows:
        baseline_rows = conn.execute(
            """
            SELECT
                channel,
                ROUND(AVG(revenue), 4)  AS avg_revenue_per_row,
                COUNT(*)                AS row_count
            FROM ft_revenue
            WHERE scenario=? AND is_baseline=1
            GROUP BY channel
            """,
            (scenario,),
        ).fetchall()

    conn.close()

    # Build baseline lookup: channel → avg revenue per record
    baseline_map: Dict[str, float] = {
        r["channel"]: r["avg_revenue_per_row"] for r in baseline_rows
    }

    if not current_rows:
        return Observation(
            summary=f"Không có dữ liệu doanh thu trong window {time_window} cho scenario={scenario}.",
            aggregates={},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={
                "tool_name": "get_revenue_breakdown",
                "time_window": time_window,
                "scenario": scenario,
            },
        )

    # Build aggregates và tính delta
    aggregates: Dict[str, Any] = {}
    anomalies = []

    for row in current_rows:
        ch = row["channel"]
        cur_rev = row["total_revenue"]
        cur_tx = row["total_tx"]
        cur_refund = row["total_refund"]

        # Baseline: avg_revenue_per_row * số rows hiện tại (proxy quy mô tương đương)
        # Nếu không có baseline → delta N/A
        base_avg = baseline_map.get(ch)
        if base_avg and base_avg > 0:
            # So sánh trên cùng đơn vị revenue/row
            current_avg = cur_rev / max(cur_tx, 1) if cur_tx else 0
            delta_pct = round((current_avg - base_avg) / base_avg * 100, 1)
        else:
            delta_pct = None

        aggregates[ch] = {
            "current_revenue": cur_rev,
            "baseline_revenue_per_row": base_avg,
            "delta_pct": delta_pct,
            "transaction_count": cur_tx,
            "refund_amount": cur_refund,
        }

        if delta_pct is not None and delta_pct <= -20:
            anomalies.append((ch, delta_pct, cur_rev, base_avg))

    # Xây summary với diễn giải rõ ràng
    total_current = sum(r["total_revenue"] for r in current_rows)
    total_tx = sum(r["total_tx"] for r in current_rows)

    if anomalies:
        # Sắp xếp theo mức giảm nặng nhất
        anomalies.sort(key=lambda x: x[1])
        worst_ch, worst_delta, worst_rev, worst_base = anomalies[0]
        drop_desc = f"{worst_ch} revenue giảm {abs(worst_delta)}% so với baseline"
        if len(anomalies) > 1:
            other = ", ".join(a[0] for a in anomalies[1:])
            drop_desc += f"; {other} cũng giảm"
        normal_channels = [
            r["channel"] for r in current_rows
            if r["channel"] not in {a[0] for a in anomalies}
        ]
        normal_note = (
            f" {', '.join(normal_channels)} bình thường."
            if normal_channels
            else ""
        )
        summary = (
            f"{drop_desc} trong window {time_window}."
            f"{normal_note}"
            f" Tổng doanh thu: {total_current:,.0f} ({total_tx:,} giao dịch)."
        )
    else:
        # Không anomaly — tóm tắt theo kênh lớn nhất
        top_ch = current_rows[0]["channel"] if current_rows else "?"
        top_rev = current_rows[0]["total_revenue"] if current_rows else 0
        summary = (
            f"Doanh thu theo channel trong {time_window} ổn định. "
            f"Kênh lớn nhất: {top_ch} ({top_rev:,.0f}). "
            f"Tổng: {total_current:,.0f} từ {total_tx:,} giao dịch. Không có dấu hiệu sụt bất thường."
        )

    # Samples: các record revenue cao nhất (đại diện cho tín hiệu)
    conn2 = open_db()
    sample_raw = conn2.execute(
        """
        SELECT timestamp, channel, revenue, transaction_count, refund_amount
        FROM ft_revenue
        WHERE scenario=? AND is_baseline=0
          AND timestamp>=? AND timestamp<?
        ORDER BY revenue DESC
        LIMIT ?
        """,
        (scenario, ts_start, ts_end, SAMPLES_HARD_CAP),
    ).fetchall()
    conn2.close()

    samples = [dict(r) for r in sample_raw]
    total_rows = sum(r["total_tx"] for r in current_rows)

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=samples,
        total_count=total_rows,
        truncated=total_rows > SAMPLES_HARD_CAP,
        metadata={
            "tool_name": "get_revenue_breakdown",
            "time_window": time_window,
            "scenario": scenario,
            "date": date,
        },
    )


# ── Tool definition ────────────────────────────────────────────────────────────

get_revenue_breakdown = Tool(
    name="get_revenue_breakdown",
    description=(
        "Phân tích doanh thu theo kênh thanh toán (credit_card, debit_card, e_wallet, v.v.) "
        "trong một khoảng thời gian, so sánh với baseline bình thường. "
        "Trả về: Δ% revenue per channel, transaction_count, refund_amount, và kênh nào bị sụt bất thường. "
        "Dùng khi: (1) cần định lượng tác động tài chính của sự cố, "
        "(2) xác định kênh nào bị ảnh hưởng nhất, "
        "(3) phân biệt sụt doanh thu vs sụt giao dịch. "
        "KHÔNG dùng để xem fail_rate/refund per merchant (→ get_transaction_anomaly) "
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
                "description": "Kịch bản data fintech (vd: 'scenario_fintech1'). Mặc định: 'scenario_fintech1'",
                "default": "scenario_fintech1",
            },
            "date": {
                "type": "string",
                "description": "Ngày dạng 'YYYY-MM-DD'. Mặc định: '2024-01-15'",
                "default": "2024-01-15",
            },
        },
        "required": ["time_window"],
    },
    run=_run,
)
