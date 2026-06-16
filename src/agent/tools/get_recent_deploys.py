"""
Tool: get_recent_deploys

Hỏi: "Có deployment nào xảy ra xung quanh thời điểm sự cố không?"
Dùng khi: đã xác định có lỗi bất thường, muốn tìm thay đổi gần đây có thể là nguyên nhân.
Không dùng để: phân tích lỗi chi tiết (→ get_error_breakdown) hay latency (→ get_metrics).
"""
from __future__ import annotations

import re
from typing import Any, Dict

from agent.storage.db import open_db
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation, Tool


def _run(params: Dict[str, Any]) -> Observation:
    service: str | None = params.get("service")  # None = tất cả service
    time_window: str = params["time_window"]       # e.g. "13:00-15:00"
    scenario: str = params.get("scenario", "scenario1")
    date: str = params.get("date", "2024-01-15")
    lookback_minutes: int = int(params.get("lookback_minutes", 60))  # mở rộng window nhìn lùi

    # L4: validate time_window format
    if not re.match(r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$", time_window.strip()):
        return Observation(
            summary=f"time_window '{time_window}' không đúng định dạng HH:MM-HH:MM.",
            aggregates={}, samples=[], total_count=0, truncated=False,
            metadata={"tool_name": "get_recent_deploys", "error": "invalid_time_window"},
        )

    start_str, end_str = time_window.split("-")
    ts_start = f"{date}T{start_str}:00Z"
    ts_end = f"{date}T{end_str}:00Z"

    # Mở rộng window nhìn lùi để bắt deploy ngay trước sự cố
    h, m = map(int, start_str.split(":"))
    total_min = h * 60 + m - lookback_minutes
    lb_h, lb_m = divmod(max(total_min, 0), 60)
    ts_lookback = f"{date}T{lb_h:02d}:{lb_m:02d}:00Z"

    conn = open_db()

    query = """
        SELECT timestamp, service, version, status
        FROM deploys
        WHERE scenario=? AND timestamp>=? AND timestamp<?
        ORDER BY timestamp DESC
    """
    args = [scenario, ts_lookback, ts_end]
    if service:
        query = """
            SELECT timestamp, service, version, status
            FROM deploys
            WHERE scenario=? AND service=? AND timestamp>=? AND timestamp<?
            ORDER BY timestamp DESC
        """
        args = [scenario, service, ts_lookback, ts_end]

    rows = conn.execute(query, args).fetchall()
    conn.close()

    deploys = [dict(r) for r in rows]
    total = len(deploys)

    if total == 0:
        summary = (
            f"Không tìm thấy deployment nào trong {lookback_minutes} phút trước {time_window}"
            + (f" cho {service}" if service else "") + "."
        )
        return Observation(
            summary=summary,
            aggregates={"total_deploys": 0},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={"tool_name": "get_recent_deploys", "service": service or "all",
                      "time_window": time_window, "lookback_minutes": lookback_minutes},
        )

    # Aggregates: đếm theo service và status
    by_service: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for d in deploys:
        by_service[d["service"]] = by_service.get(d["service"], 0) + 1
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1

    # Deploy mới nhất — thường là thứ quan tâm nhất
    latest = deploys[0]
    latest_note = f"{latest['service']} {latest['version']} lúc {latest['timestamp'][11:16]} (status={latest['status']})"

    # Xây summary diễn giải — chú trọng tương quan thời gian với spike
    summary = (
        f"Tìm thấy {total} deployment trong {lookback_minutes} phút trước {end_str}. "
        f"Gần nhất: {latest_note}. "
    )
    if total > 1:
        summary += f"Còn {total - 1} deploy khác."

    aggregates: Dict[str, Any] = {"total_deploys": total}
    aggregates.update({f"svc:{k}": v for k, v in by_service.items()})
    aggregates.update({f"status:{k}": v for k, v in by_status.items()})

    samples = deploys[:SAMPLES_HARD_CAP]

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=samples,
        total_count=total,
        truncated=total > SAMPLES_HARD_CAP,
        metadata={"tool_name": "get_recent_deploys", "service": service or "all",
                  "time_window": time_window, "lookback_minutes": lookback_minutes,
                  "scenario": scenario},
    )


get_recent_deploys = Tool(
    name="get_recent_deploys",
    description=(
        "Tra cứu các deployment (release phần mềm) xảy ra trong và trước khoảng thời gian sự cố. "
        "Trả về: tên service, version, thời điểm deploy, trạng thái (success/failed/rolled_back). "
        "Dùng khi: đã thấy lỗi bất thường và muốn kiểm tra xem có deploy nào ngay trước spike không. "
        "Mặc định nhìn lùi 60 phút trước time_window để bắt deploy ngay trước sự cố. "
        "KHÔNG dùng để phân tích lỗi (→ get_error_breakdown) hay latency (→ get_metrics)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Tên service cần lọc. Bỏ qua để lấy tất cả service.",
            },
            "time_window": {
                "type": "string",
                "description": "Cửa sổ thời gian dạng 'HH:MM-HH:MM' (vd: '14:00-15:00')",
            },
            "lookback_minutes": {
                "type": "integer",
                "description": "Nhìn lùi thêm bao nhiêu phút trước thời điểm bắt đầu window. Mặc định: 60",
                "default": 60,
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
        "required": ["time_window"],
    },
    run=_run,
)
