"""
InvestigationState — dataclass thuần dữ liệu, tách khỏi logic.

Giả thuyết và bằng chứng LIÊN KẾT với nhau qua evidence_ids.
Verdict và đánh giá đều dựa vào liên kết này.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from agent.tools.contracts import Observation


@dataclass
class Evidence:
    """Một Observation đã thu — gắn id để giả thuyết trỏ tới."""
    id: str
    step: int
    tool_name: str
    params: Dict[str, Any]
    summary: str          # observation.summary — để render nhanh không cần unwrap
    observation: Observation


@dataclass
class Hypothesis:
    """Một giả thuyết về nguyên nhân sự cố."""
    id: str
    content: str
    status: Literal["open", "confirmed", "ruled_out"]
    evidence_ids: List[str] = field(default_factory=list)
    confidence: Optional[Literal["high", "medium", "low"]] = None
    # high = tương quan thời gian + cơ chế nhân quả rõ
    # medium = chỉ tương quan thời gian
    # low = suy đoán


@dataclass
class Verdict:
    """Kết quả điều tra — trình bày lại trạng thái giả thuyết khi dừng."""
    root_cause: str
    confidence: Literal["high", "medium", "low", "insufficient"]
    evidence_summary: str
    propagation_note: str      # lỗi-gốc vs lỗi-lan
    competing_hypotheses: str  # có loại trừ giả thuyết cạnh tranh chưa
    raw_text: str              # toàn văn LLM trả về


@dataclass
class InvestigationState:
    """Trạng thái toàn phiên điều tra."""
    investigation_id: str
    symptom: str
    time_window: str
    scenario: str
    date: str

    project_id: str = "default"
    available_services: List[str] = field(default_factory=list)  # services trong project

    hypotheses: List[Hypothesis] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)

    steps_taken: int = 0
    step_budget: int = 10

    finished: bool = False
    stop_reason: Optional[str] = None  # "verdict" | "budget" | "loop_detected" | "timeout"
    verdict: Optional[Verdict] = None

    # Lịch sử tool calls để phát hiện lặp
    tool_call_history: List[Dict[str, Any]] = field(default_factory=list)

    def add_evidence(self, step: int, tool_name: str, params: Dict[str, Any],
                     obs: Observation) -> Evidence:
        ev = Evidence(
            id=str(uuid.uuid4())[:8],
            step=step,
            tool_name=tool_name,
            params=params,
            summary=obs.summary,
            observation=obs,
        )
        self.evidence.append(ev)
        return ev

    def add_hypothesis(self, content: str) -> Hypothesis:
        hyp = Hypothesis(
            id=str(uuid.uuid4())[:8],
            content=content,
            status="open",
        )
        self.hypotheses.append(hyp)
        return hyp

    def link_evidence_to_hypothesis(self, hyp_id: str, ev_id: str) -> None:
        for h in self.hypotheses:
            if h.id == hyp_id:
                if ev_id not in h.evidence_ids:
                    h.evidence_ids.append(ev_id)
                return

    def is_looping(self) -> bool:
        """Phát hiện lặp: 2 tool call liên tiếp cùng name + params giống nhau."""
        if len(self.tool_call_history) < 2:
            return False
        last = self.tool_call_history[-1]
        prev = self.tool_call_history[-2]
        return last["name"] == prev["name"] and last["params"] == prev["params"]

    def summarize_for_llm(self) -> str:
        """Tổng hợp state gọn để đưa vào context LLM — KHÔNG đưa lịch sử thô."""
        lines = []

        # Danh sách service trong scope — LLM dùng để định hướng điều tra
        if self.available_services:
            lines.append(f"## Services trong project (chỉ điều tra các service này)")
            lines.append(f"  {', '.join(self.available_services)}")
            lines.append("")

        # Giả thuyết + bằng chứng liên kết
        if self.hypotheses:
            lines.append("## Giả thuyết đang theo dõi")
            for h in self.hypotheses:
                ev_refs = []
                for ev_id in h.evidence_ids:
                    ev = next((e for e in self.evidence if e.id == ev_id), None)
                    if ev:
                        ev_refs.append(f"[{ev.tool_name}: {ev.summary[:80]}]")
                status_mark = {"open": "🔍", "confirmed": "✅", "ruled_out": "❌"}.get(h.status, "?")
                conf_note = f" (độ tin: {h.confidence})" if h.confidence else ""
                lines.append(f"  {status_mark} [{h.id}] {h.content}{conf_note}")
                for ref in ev_refs:
                    lines.append(f"      ↳ {ref}")

        # Bằng chứng mới nhất (chỉ 3 gần nhất)
        if self.evidence:
            lines.append("## Bằng chứng mới thu thập")
            for ev in self.evidence[-3:]:
                lines.append(f"  Bước {ev.step} — {ev.tool_name}: {ev.summary}")

        # Tool đã gọi (tránh lặp)
        if self.tool_call_history:
            called = [f"{c['name']}({list(c['params'].keys())})" for c in self.tool_call_history[-5:]]
            lines.append(f"## Tool đã gọi (gần nhất): {' → '.join(called)}")

        return "\n".join(lines) if lines else "(chưa có bằng chứng)"
