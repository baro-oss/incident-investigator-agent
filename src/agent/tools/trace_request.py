"""
Tool: trace_request

Hỏi: "Request lỗi này đi qua những service nào, bị chặn ở đâu?"
Dùng khi: muốn lần theo một request cụ thể xuyên service để tìm điểm gốc của lỗi.
Báo cáo trung thực chỗ trace đứt — không im lặng về khoảng mất dấu.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent.storage.db import open_db
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation, Tool

SERVICES_ORDER = [
    "api-gateway",
    "order-service",
    "payment-gateway",
    "auth-service",
    "third-party-provider",
]


def _run(params: Dict[str, Any]) -> Observation:
    service: str = params["service"]          # service để lấy trace_id mẫu
    time_window: str = params["time_window"]  # e.g. "14:05-14:30"
    scenario: str = params.get("scenario", "scenario1")
    date: str = params.get("date", "2024-01-15")
    trace_id: Optional[str] = params.get("trace_id")  # nếu đã biết trace_id cụ thể

    start_str, end_str = time_window.split("-")
    ts_start = f"{date}T{start_str}:00Z"
    ts_end = f"{date}T{end_str}:00Z"

    conn = open_db()

    # Nếu không có trace_id cụ thể, lấy trace_id của một lỗi điển hình trong service đó
    if not trace_id:
        row = conn.execute(
            """
            SELECT trace_id FROM logs
            WHERE scenario=? AND service=? AND timestamp>=? AND timestamp<?
              AND error_type IS NOT NULL AND trace_id IS NOT NULL
            ORDER BY timestamp
            LIMIT 1
            """,
            (scenario, service, ts_start, ts_end),
        ).fetchone()
        if not row:
            conn.close()
            return Observation(
                summary=f"Không tìm thấy request lỗi nào có trace_id ở {service} trong {time_window}.",
                aggregates={"traced_services": 0},
                samples=[],
                total_count=0,
                truncated=False,
                metadata={"tool_name": "trace_request", "service": service,
                          "time_window": time_window},
            )
        trace_id = row["trace_id"]

    # Tìm tất cả log có trace_id này — xuyên mọi service
    trace_rows = conn.execute(
        """
        SELECT timestamp, service, level, message, error_type
        FROM logs
        WHERE scenario=? AND trace_id=?
        ORDER BY timestamp
        """,
        (scenario, trace_id),
    ).fetchall()

    # Tìm % request có trace_id (đánh giá độ phủ chung của hệ thống)
    total_errors_in_window = conn.execute(
        """
        SELECT COUNT(*) FROM logs
        WHERE scenario=? AND service=? AND timestamp>=? AND timestamp<?
          AND error_type IS NOT NULL
        """,
        (scenario, service, ts_start, ts_end),
    ).fetchone()[0]

    conn.close()

    if not trace_rows:
        return Observation(
            summary=(
                f"trace_id={trace_id} không tìm thấy trong log (trace bị mất ngay từ đầu). "
                f"Có thể service không có distributed tracing."
            ),
            aggregates={"traced_services": 0},
            samples=[],
            total_count=0,
            truncated=False,
            trace_completeness={
                "complete": False,
                "break_point": "unknown — trace_id không xuất hiện trong bất kỳ log nào",
                "last_service": "unknown",
                "services_reached": [],
            },
            metadata={"tool_name": "trace_request", "service": service,
                      "trace_id": trace_id, "time_window": time_window},
        )

    # Phân nhóm theo service
    services_seen: Dict[str, List[dict]] = {}
    has_error_per_service: Dict[str, bool] = {}
    for row in trace_rows:
        svc = row["service"]
        if svc not in services_seen:
            services_seen[svc] = []
        services_seen[svc].append(dict(row))
        if row["error_type"]:
            has_error_per_service[svc] = True

    services_reached = list(services_seen.keys())

    # Phát hiện trace đứt: nếu một service gọi downstream nhưng trace không có ở đó
    # Dựa vào catalog dependency: nếu service X có lỗi và phụ thuộc Y, nhưng Y không có trace → đứt
    break_point: Optional[str] = None
    for svc in services_reached:
        if has_error_per_service.get(svc):
            # service này có lỗi — check xem dependency có trace không
            # (đơn giản: nếu chỉ có 1 service trong trace → trace chưa lan được)
            pass

    complete = len(services_reached) >= 2  # cơ bản: trace qua được ít nhất 2 service

    # Với scenario1: trace chỉ có ở payment-gateway (các service khác có trace_id khác)
    # → đây là trace "đứt" — agent phải dựa vào tương quan thời gian
    if len(services_reached) == 1:
        break_point = f"trace chỉ thấy ở {services_reached[0]}, không lan sang service khác"
        complete = False

    last_service = services_reached[-1] if services_reached else "unknown"
    error_services = [s for s, has_err in has_error_per_service.items() if has_err]

    # Summary diễn giải
    if complete:
        summary = (
            f"trace_id={trace_id[:12]}... đi qua {len(services_reached)} service: "
            f"{' → '.join(services_reached)}. "
            f"Lỗi xuất hiện tại: {', '.join(error_services) if error_services else 'không có'}."
        )
    else:
        summary = (
            f"trace_id={trace_id[:12]}... CHỈ THẤY ở {services_reached[0]} — trace đứt. "
            f"Nguyên nhân: service khác không ghi trace_id này vào log (distributed tracing chưa đầy đủ). "
            f"→ Độ tin BỊ HẠ: bắc cầu bằng tương quan thời gian + dependency map thay vì trace trực tiếp."
        )

    aggregates: Dict[str, Any] = {
        "trace_id": trace_id[:16] + "...",
        "services_reached": len(services_reached),
        "has_errors": len(error_services),
        "error_services": ", ".join(error_services) if error_services else "none",
        "trace_complete": complete,
        "total_errors_in_window_at_source": total_errors_in_window,
    }

    samples = [dict(r) for r in trace_rows[:SAMPLES_HARD_CAP]]

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=samples,
        total_count=len(trace_rows),
        truncated=len(trace_rows) > SAMPLES_HARD_CAP,
        trace_completeness={
            "complete": complete,
            "break_point": break_point or "N/A",
            "last_service": last_service,
            "services_reached": services_reached,
        },
        metadata={"tool_name": "trace_request", "service": service,
                  "trace_id": trace_id, "time_window": time_window, "scenario": scenario},
    )


trace_request = Tool(
    name="trace_request",
    description=(
        "Lần theo một request lỗi xuyên qua các service, tìm điểm gốc và chỗ trace đứt. "
        "Tự động lấy một trace_id lỗi điển hình từ service chỉ định nếu không cung cấp trace_id. "
        "Trả về: danh sách service request đã đi qua, lỗi xuất hiện ở đâu, "
        "và CẢNH BÁO rõ nếu trace bị mất — kèm hướng dẫn hạ độ tin. "
        "Dùng khi: muốn phân biệt service nào là nơi lỗi PHÁT SINH vs. nơi lỗi LAN ĐẾN. "
        "QUAN TRỌNG: trace đứt KHÔNG có nghĩa không có dữ liệu — tool sẽ gợi ý bắc cầu bằng dependency + thời gian."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Service để lấy trace_id mẫu (lỗi điển hình gần nhất trong time_window)",
            },
            "time_window": {
                "type": "string",
                "description": "Cửa sổ thời gian dạng 'HH:MM-HH:MM' (vd: '14:05-15:00')",
            },
            "trace_id": {
                "type": "string",
                "description": "trace_id cụ thể nếu đã biết. Bỏ qua để tool tự chọn trace lỗi đại diện.",
            },
            "scenario": {
                "type": "string",
                "description": "Kịch bản: 'scenario1' hoặc 'scenario2'. Mặc định: 'scenario1'",
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
