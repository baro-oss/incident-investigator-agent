"""
Hợp đồng tool & Observation schema.

Đây là "đường ranh" — engine chỉ thấy Tool và Observation.
Không có gì từ SQLite, MCP, hay provider cụ thể lọt qua đây.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Observation:
    """
    Kết quả đã chưng cất từ một lần gọi tool.

    Thứ tự field = thứ tự ưu tiên khi LLM đọc:
    summary đặt ĐẦU vì model tầm trung định tuyến tốt hơn khi câu chốt nằm ngay đầu.
    """
    summary: str                            # Tool tự diễn giải — phải mang signal bước kế cần
    aggregates: Dict[str, Any]              # Số liệu đã gom nhóm (vd {"TimeoutException": 14203})
    samples: List[Dict[str, Any]]           # ≤5 mẫu đại diện — trần cứng, không bao giờ nhiều hơn
    total_count: int                        # Tổng thật trước khi cắt
    truncated: bool                         # Còn dữ liệu bị bỏ qua không
    metadata: Dict[str, Any]               # time_window, service, tool_name — để engine ghép bằng chứng
    # Chỉ dùng cho trace_request: báo cáo chỗ mất dấu
    trace_completeness: Optional[Dict[str, Any]] = None


@dataclass
class Tool:
    """
    Hợp đồng tool đồng nhất — engine chỉ thấy list[Tool].

    Tool nội bộ (SQLite) hay MCP đều phải bọc thành hình dạng này.
    description là chỗ đáng đổ công nhất: LLM đọc để quyết dùng tool nào.
    """
    name: str
    description: str           # Sắc, phân biệt rõ khi nào dùng tool này
    input_schema: Dict[str, Any]  # JSON Schema cho params
    run: Callable[..., Observation]  # (params: dict) -> Observation, có thể là coroutine


SAMPLES_HARD_CAP = 5  # trần cứng — không bao giờ trả nhiều hơn


def render_for_llm(obs: Observation) -> str:
    """
    Serialize Observation thành text gọn để đưa vào context LLM.

    Chỉ gọi ở biên — ngay trước khi gọi LLM. Không serialize ở chỗ khác.
    Không dump JSON thô: JSON lồng nhiều ngoặc làm model tầm trung khó đọc.
    """
    lines: List[str] = []

    # Summary luôn đầu tiên
    lines.append(f"[Observation] {obs.summary}")

    # Aggregates dạng liệt kê ngắn
    if obs.aggregates:
        lines.append("Aggregates:")
        for k, v in obs.aggregates.items():
            lines.append(f"  {k}: {v}")

    # Samples với chú thích tổng
    if obs.samples:
        count_note = f"total={obs.total_count}" + (" (truncated)" if obs.truncated else "")
        lines.append(f"Samples ({len(obs.samples)} shown, {count_note}):")
        for s in obs.samples:
            lines.append(f"  • {s}")

    # Trace completeness nếu có
    if obs.trace_completeness:
        tc = obs.trace_completeness
        lines.append(
            f"Trace: reached {tc.get('last_service', '?')} — "
            f"{'COMPLETE' if tc.get('complete') else 'BROKEN at ' + tc.get('break_point', '?')}"
        )

    # Metadata gọn
    meta_parts = []
    if "service" in obs.metadata:
        meta_parts.append(f"service={obs.metadata['service']}")
    if "time_window" in obs.metadata:
        meta_parts.append(f"window={obs.metadata['time_window']}")
    if meta_parts:
        lines.append(f"({', '.join(meta_parts)})")

    return "\n".join(lines)
