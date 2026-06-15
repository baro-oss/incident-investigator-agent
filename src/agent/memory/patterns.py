"""
Long-term memory — lưu pattern điều tra thành công, gợi ý warm-start.

Chỉ ghi khi verdict HIGH; đọc khi bắt đầu investigation mới.
Bảng: investigation_patterns (project_id, service, error_pattern, tool_sequence, ...)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from agent.storage.db import open_db

if TYPE_CHECKING:
    from agent.engine.state import InvestigationState

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_pattern(state: "InvestigationState") -> None:
    """Lưu pattern của investigation vừa kết thúc với verdict HIGH.

    Chỉ gọi sau khi state.verdict.confidence == 'high'.
    Idempotent: UNIQUE(project_id, service, error_pattern) → ON CONFLICT cập nhật.
    """
    if not state.verdict or state.verdict.confidence not in ("high", "medium"):
        return

    # Trích error_pattern từ root_cause (tối đa 80 ký tự)
    error_pattern = state.verdict.root_cause[:80]

    # Chuỗi tool được gọi theo thứ tự
    tool_sequence = json.dumps(
        [tc["name"] for tc in state.tool_call_history], ensure_ascii=False
    )

    # Root cause type: dựa vào từ khóa trong root_cause
    root_cause_type = _classify_root_cause(state.verdict.root_cause)

    # Service bị lỗi: đơn giản dùng symptom prefix hoặc hypothesis đầu tiên confirmed
    service = _extract_service(state)

    try:
        conn = open_db()
        conn.execute("""
            INSERT INTO investigation_patterns
                (project_id, service, error_pattern, tool_sequence, root_cause_type,
                 avg_steps, count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(project_id, service, error_pattern) DO UPDATE SET
                tool_sequence  = excluded.tool_sequence,
                root_cause_type = excluded.root_cause_type,
                avg_steps = round((investigation_patterns.avg_steps * investigation_patterns.count
                                   + excluded.avg_steps) / (investigation_patterns.count + 1), 2),
                count     = investigation_patterns.count + 1,
                updated_at = excluded.updated_at
        """, (
            state.project_id, service, error_pattern,
            tool_sequence, root_cause_type,
            float(state.steps_taken), _now(),
        ))
        conn.commit()
        conn.close()
        logger.info("[memory] Pattern lưu: project=%s service=%s type=%s",
                    state.project_id, service, root_cause_type)
    except Exception as exc:
        logger.warning("[memory] Không lưu được pattern: %s", exc)


def get_service_priors(
    project_id: str,
    service: str,
    *,
    limit: int = 3,
) -> List[dict]:
    """E11: Trả top-N root_cause_type đã gặp cho (project, service), sorted by count DESC.

    Mỗi phần tử: {"root_cause_type": str, "count": int, "avg_steps": float}
    Trả [] nếu không có dữ liệu.
    """
    try:
        conn = open_db()
        rows = conn.execute("""
            SELECT root_cause_type, count, avg_steps
            FROM investigation_patterns
            WHERE project_id=? AND service=? AND root_cause_type != 'unknown'
            ORDER BY count DESC LIMIT ?
        """, (project_id, service, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.debug("[memory] get_service_priors lỗi: %s", exc)
        return []


def get_warm_start_hint(
    project_id: str,
    service: str,
    error_keywords: Optional[List[str]] = None,
) -> Optional[str]:
    """Trả gợi ý warm-start nếu có pattern tương tự.

    Tìm bản ghi gần nhất cùng project_id + service; ưu tiên error_pattern khớp keyword.
    Trả None nếu không tìm thấy.
    """
    try:
        conn = open_db()

        if error_keywords:
            # Thử tìm match theo keyword
            for kw in error_keywords:
                row = conn.execute("""
                    SELECT tool_sequence, root_cause_type, avg_steps, count
                    FROM investigation_patterns
                    WHERE project_id=? AND service=? AND error_pattern LIKE ?
                    ORDER BY count DESC LIMIT 1
                """, (project_id, service, f"%{kw}%")).fetchone()
                if row:
                    conn.close()
                    return _format_hint(dict(row))

        # Fallback: lấy pattern phổ biến nhất theo service
        row = conn.execute("""
            SELECT tool_sequence, root_cause_type, avg_steps, count
            FROM investigation_patterns
            WHERE project_id=? AND service=?
            ORDER BY count DESC LIMIT 1
        """, (project_id, service)).fetchone()
        conn.close()

        return _format_hint(dict(row)) if row else None

    except Exception as exc:
        logger.debug("[memory] get_warm_start_hint lỗi: %s", exc)
        return None


def _format_hint(row: dict) -> str:
    tools = json.loads(row.get("tool_sequence", "[]"))
    tool_str = " → ".join(tools) if tools else "(không rõ)"
    return (
        f"Pattern trước: type={row['root_cause_type']}, "
        f"avg_steps={row['avg_steps']:.1f}, gặp {row['count']} lần. "
        f"Tool sequence hiệu quả: {tool_str}"
    )


def _classify_root_cause(root_cause: str) -> str:
    rc = root_cause.lower()
    # Microservice types
    if "deploy" in rc or "version" in rc:
        return "deploy_bug"
    if "pool" in rc or "exhaustion" in rc:
        return "pool_exhaustion"
    if "traffic" in rc or "surge" in rc or "ratelimit" in rc:
        return "traffic_surge"
    if "provider" in rc or "sập" in rc or "unavailable" in rc:
        return "provider_down"
    # Fintech types
    if "processor" in rc and "timeout" in rc:
        return "processor_timeout"
    if "price" in rc or "refund" in rc:
        return "price_configuration_error"
    if "fraud" in rc or "breach" in rc:
        return "merchant_fraud"
    if "settlement" in rc or "lag" in rc:
        return "settlement_lag"
    # Generic fallback — keep ordering: latency_spike before timeout to be specific
    if "spike" in rc:
        return "latency_spike"
    if "timeout" in rc or "latency" in rc or "connection" in rc:
        return "timeout"
    return "unknown"


def _extract_service(state: "InvestigationState") -> str:
    # Lấy service từ symptom (phần trước dấu ':')
    symptom = state.symptom or ""
    if ":" in symptom:
        return symptom.split(":")[0].strip()
    if state.available_services:
        return state.available_services[0]
    return "unknown"
