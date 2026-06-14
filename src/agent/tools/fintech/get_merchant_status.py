"""
Tool: get_merchant_status

Hỏi: "Trạng thái merchant này là gì? Có ghi chú vấn đề gì không?"
Dùng khi: cần xem trạng thái (active/blocked/degraded) và ghi chú vận hành của merchant,
  đặc biệt khi đã phát hiện bất thường từ get_transaction_anomaly và cần hiểu nguyên nhân.
Không dùng để: xem số liệu giao dịch (→ get_transaction_anomaly),
  xem doanh thu (→ get_revenue_breakdown), xem settlement (→ get_settlement_lag).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent.storage.db import open_db
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation, Tool


def _run(params: Dict[str, Any]) -> Observation:
    merchant_id: Optional[str] = params.get("merchant_id")
    scenario: str = params.get("scenario", "scenario_fintech1")

    conn = open_db()

    if merchant_id:
        rows = conn.execute(
            """
            SELECT id, name, category, status, notes
            FROM ft_merchants
            WHERE scenario=? AND id=?
            ORDER BY id
            """,
            (scenario, merchant_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, name, category, status, notes
            FROM ft_merchants
            WHERE scenario=?
            ORDER BY status, id
            """,
            (scenario,),
        ).fetchall()

    conn.close()

    if not rows:
        target = f"merchant_id={merchant_id}" if merchant_id else f"scenario={scenario}"
        return Observation(
            summary=f"Không tìm thấy merchant nào cho {target}.",
            aggregates={},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={
                "tool_name": "get_merchant_status",
                "merchant_id": merchant_id,
                "scenario": scenario,
            },
        )

    # Aggregates: per merchant
    aggregates: Dict[str, Any] = {}
    blocked_list: List[str] = []
    degraded_list: List[str] = []
    noted_list: List[str] = []  # có notes đáng chú ý

    for row in rows:
        mid = row["id"]
        status = row["status"]
        notes = row["notes"] or ""

        aggregates[mid] = {
            "name": row["name"],
            "category": row["category"],
            "status": status,
            "notes": notes if notes else "(không có ghi chú)",
        }

        if status == "blocked":
            blocked_list.append(mid)
        elif status == "degraded":
            degraded_list.append(mid)

        # Ghi chú có từ khóa quan trọng
        note_lower = notes.lower()
        if any(kw in note_lower for kw in ["bug", "error", "issue", "breach", "fraud", "price", "block"]):
            noted_list.append((mid, notes))

    total = len(rows)

    # --- Summary diễn giải ---
    if merchant_id:
        # Single merchant mode
        row = rows[0]
        mid = row["id"]
        status = row["status"]
        notes = row["notes"] or "không có ghi chú"
        name = row["name"]
        cat = row["category"]

        status_label = {
            "active": "hoạt động bình thường",
            "blocked": "BỊ KHÓA",
            "degraded": "ĐANG DEGRADED",
        }.get(status, status)

        summary = (
            f"{mid} ({name}, {cat}): status={status_label}. "
            f"Notes: '{notes}'."
        )
    else:
        # Multi-merchant mode
        n_active = total - len(blocked_list) - len(degraded_list)
        parts = []
        if blocked_list:
            parts.append(f"{len(blocked_list)} merchant bị khóa: {', '.join(blocked_list)}")
        if degraded_list:
            parts.append(f"{len(degraded_list)} merchant degraded: {', '.join(degraded_list)}")
        if parts:
            issue_str = "; ".join(parts)
            note_str = ""
            if noted_list:
                top_noted = noted_list[0]
                note_str = f" Chú ý: {top_noted[0]} — '{top_noted[1]}'."
            summary = (
                f"{issue_str}. {n_active}/{total} merchant hoạt động bình thường.{note_str}"
            )
        else:
            summary = (
                f"Tất cả {total} merchant đang active. "
                f"Không có merchant bị khóa hay degraded trong scenario={scenario}."
            )
            if noted_list:
                top = noted_list[0]
                summary += f" Tuy nhiên có ghi chú đáng chú ý: {top[0]} — '{top[1]}'."

    # Samples: tất cả (đã <= SAMPLES_HARD_CAP thường vì merchant ít)
    samples = [dict(r) for r in rows[:SAMPLES_HARD_CAP]]

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=samples,
        total_count=total,
        truncated=total > SAMPLES_HARD_CAP,
        metadata={
            "tool_name": "get_merchant_status",
            "merchant_id": merchant_id,
            "scenario": scenario,
            "blocked_count": len(blocked_list),
            "degraded_count": len(degraded_list),
        },
    )


# ── Tool definition ────────────────────────────────────────────────────────────

get_merchant_status = Tool(
    name="get_merchant_status",
    description=(
        "Tra cứu trạng thái và ghi chú vận hành của merchant. "
        "Trả về: status (active/blocked/degraded), category, notes — bao gồm các ghi chú sự cố "
        "(vd: 'price_bug_reported', 'fraud_suspected', 'processor_timeout'). "
        "Dùng khi: (1) cần giải thích tại sao một merchant có refund_rate/fail_rate cao, "
        "(2) xác nhận merchant có đang bị khóa hay degraded không, "
        "(3) đọc ghi chú vận hành để tìm root cause. "
        "Nếu không truyền merchant_id → trả tất cả merchant trong scenario. "
        "KHÔNG dùng để xem số liệu giao dịch thực (→ get_transaction_anomaly)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "scenario": {
                "type": "string",
                "description": "Kịch bản data fintech. Mặc định: 'scenario_fintech1'",
                "default": "scenario_fintech1",
            },
            "merchant_id": {
                "type": "string",
                "description": (
                    "ID merchant cần tra cứu (vd: 'merch-buzz'). "
                    "Bỏ trống để xem tất cả merchant trong scenario."
                ),
            },
        },
        "required": [],
    },
    run=_run,
)
