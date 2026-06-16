"""
Tool: get_dependencies

Hỏi: "Service X phụ thuộc trực tiếp vào những service nào?"
Dùng khi: muốn biết upstream/downstream để truy tìm nguồn gốc lỗi lan.
Chỉ trả MỘT tầng (gọi trực tiếp), không phải toàn bộ cây dependency.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from agent.storage.db import open_db
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation, Tool


def _run(params: Dict[str, Any]) -> Observation:
    service: str = params["service"]

    conn = open_db()

    # Lấy thông tin service
    row = conn.execute(
        "SELECT service, description, depends_on FROM service_catalog WHERE service=?",
        (service,),
    ).fetchone()

    if not row:
        conn.close()
        return Observation(
            summary=f"Không tìm thấy service '{service}' trong catalog.",
            aggregates={},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={"tool_name": "get_dependencies", "service": service},
        )

    depends_on = json.loads(row["depends_on"])  # List[str]

    # Lấy thông tin chi tiết của từng dependency
    dep_details = []
    for dep_svc in depends_on:
        dep_row = conn.execute(
            "SELECT service, description, baseline_error_rate, baseline_latency_p99 FROM service_catalog WHERE service=?",
            (dep_svc,),
        ).fetchone()
        if dep_row:
            dep_details.append({
                "service": dep_row["service"],
                "description": dep_row["description"],
                "baseline_error_rate": dep_row["baseline_error_rate"],
                "baseline_latency_p99_ms": dep_row["baseline_latency_p99"],
            })
        else:
            dep_details.append({"service": dep_svc, "description": "unknown"})

    # Tìm service nào phụ thuộc vào service này (downstream callers)
    caller_rows = conn.execute(
        "SELECT service FROM service_catalog WHERE depends_on LIKE ?",
        (f'%"{service}"%',),
    ).fetchall()
    callers = [r["service"] for r in caller_rows]

    conn.close()

    # Xây summary
    if not depends_on:
        summary = (
            f"{service} không phụ thuộc service nào khác (leaf node). "
            f"Được gọi bởi: {', '.join(callers) if callers else 'không ai'}."
        )
    else:
        dep_names = ", ".join(depends_on)
        summary = (
            f"{service} phụ thuộc trực tiếp vào: {dep_names}. "
            f"Được gọi bởi: {', '.join(callers) if callers else 'không ai'}. "
            f"→ Nếu {service} lỗi, hãy điều tra cả {dep_names}."
        )

    aggregates: Dict[str, Any] = {
        "direct_dependencies": len(depends_on),
        "called_by": len(callers),
        "dep_names": ", ".join(depends_on) if depends_on else "none",
        "caller_names": ", ".join(callers) if callers else "none",
    }

    return Observation(
        summary=summary,
        aggregates=aggregates,
        samples=dep_details[:SAMPLES_HARD_CAP],
        total_count=len(dep_details),
        truncated=len(dep_details) > SAMPLES_HARD_CAP,
        metadata={"tool_name": "get_dependencies", "service": service},
    )


get_dependencies = Tool(
    name="get_dependencies",
    description=(
        "Tra cứu dependency trực tiếp (một tầng) của một service trong kiến trúc microservice. "
        "Trả về: danh sách service mà service đó gọi trực tiếp, và danh sách service gọi ngược lại nó. "
        "Dùng khi: đã xác định service có vấn đề và muốn biết lỗi có thể lan từ/đến đâu. "
        "Chỉ trả một tầng — gọi nhiều lần để đi ngược dòng từng bước. "
        "KHÔNG dùng để phân tích lỗi hay metric — đây chỉ là bản đồ topology."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Tên service cần xem dependency (vd: 'payment-gateway')",
            },
        },
        "required": ["service"],
    },
    run=_run,
)
