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
    keywords: List[str] = field(default_factory=list)  # E1: từ khóa để match evidence có liên quan


@dataclass
class Verdict:
    """Kết quả điều tra — trình bày lại trạng thái giả thuyết khi dừng."""
    root_cause: str
    confidence: Literal["high", "medium", "low", "insufficient"]
    evidence_summary: str
    propagation_note: str      # lỗi-gốc vs lỗi-lan
    competing_hypotheses: str  # có loại trừ giả thuyết cạnh tranh chưa
    raw_text: str              # toàn văn LLM trả về
    speculative: bool = False  # E2: True khi root cause không neo được vào bằng chứng thu thập
    calibrated_confidence: Optional[str] = None  # E8: set khi calibration hạ bậc confidence
    parse_degraded: bool = False  # E9: True khi verdict đến từ text-parse fallback (không qua structured tool call)


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

    # Token tracking (accumulate từ llm_resp.usage)
    total_tokens: int = 0
    # P1: Prompt caching stats — accumulate per investigation
    cache_creation_tokens: int = 0   # tokens written to cache (billed at 1.25×)
    cache_read_tokens: int = 0       # tokens read from cache (billed at 0.10×)

    # Long-term memory: gợi ý warm-start từ investigation_patterns trước
    warm_start_hint: Optional[str] = None

    # E4: Gate cạnh tranh — chỉ nudge 1 lần; tránh vòng lặp vô hạn
    _competing_gate_fired: bool = False

    # E6: Catalog giả thuyết theo domain — set bởi engine khi khởi tạo investigation.
    # Dict[tag, HypothesisCatalogEntry]; để Dict plain tránh circular import với hypothesis_catalog.py
    hypothesis_catalog_index: dict = field(default_factory=dict)

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

    def competing_open(self) -> List["Hypothesis"]:
        """E1: Giả thuyết cạnh tranh còn open khi đã có ít nhất 1 hypothesis được confirmed.

        Dùng cho cổng dừng Day 27: trước khi nhận verdict high/medium, kiểm còn hypothesis
        cạnh tranh mạnh chưa loại trừ không.
        """
        if not any(h.status == "confirmed" for h in self.hypotheses):
            return []
        return [h for h in self.hypotheses if h.status == "open"]

    def link_evidence_to_hypothesis(self, hyp_id: str, ev_id: str) -> None:
        for h in self.hypotheses:
            if h.id == hyp_id:
                if ev_id not in h.evidence_ids:
                    h.evidence_ids.append(ev_id)
                return

    def resolve_conflicting_hypotheses(self) -> "Optional[Hypothesis]":
        """Ngày 33: Khi nhiều hypothesis được confirmed, chọn winner theo confidence + evidence count.

        Rank: high=3 > medium=2 > low=1 > None=0. Tiebreaker: số evidence_ids nhiều hơn.
        Trả None nếu không có hypothesis nào confirmed.
        """
        confirmed = [h for h in self.hypotheses if h.status == "confirmed"]
        if not confirmed:
            return None
        if len(confirmed) == 1:
            return confirmed[0]
        _rank = {"high": 3, "medium": 2, "low": 1}
        return max(confirmed, key=lambda h: (_rank.get(h.confidence or "", 0), len(h.evidence_ids)))

    def is_looping(self) -> bool:
        """E4: Phát hiện lặp — bắt 2 liên tiếp giống hệt + dao động chu kỳ A→B→A→B.

        - Case 1: 2 call liên tiếp cùng name+params (unchanged)
        - Case 2: Dao động trong window N=6 với chu kỳ 2 hoặc 3
        Nudge call (_competing_gate) bị lọc ra để không làm nhiễu phát hiện lặp.
        """
        # Lọc nudge calls khỏi lịch sử kiểm tra
        hist = [c for c in self.tool_call_history if c.get("name") != "_competing_gate"]
        if len(hist) < 2:
            return False

        # Case 1: 2 liên tiếp giống hệt
        if hist[-1]["name"] == hist[-2]["name"] and hist[-1]["params"] == hist[-2]["params"]:
            return True

        # Case 2: Dao động — window N=6, kiểm chu kỳ 2 (A→B→A→B) và 3 (A→B→C→A→B→C)
        N = 6
        if len(hist) < N:
            return False
        window = hist[-N:]
        for period in (2, 3):
            needed = period * 2
            if len(window) < needed:
                continue
            tail = window[-needed:]
            first_half, second_half = tail[:period], tail[period:]
            if all(
                first_half[i]["name"] == second_half[i]["name"]
                and first_half[i]["params"] == second_half[i]["params"]
                for i in range(period)
            ):
                return True

        return False

    def summarize_for_llm(self) -> str:
        """Tổng hợp state gọn để đưa vào context LLM — KHÔNG đưa lịch sử thô."""
        lines = []

        # Danh sách service trong scope — LLM dùng để định hướng điều tra
        if self.available_services:
            lines.append(f"## Services trong project (chỉ điều tra các service này)")
            lines.append(f"  {', '.join(self.available_services)}")
            lines.append("")

        # Giả thuyết + bằng chứng liên kết — cap để gọn context (P1)
        if self.hypotheses:
            lines.append("## Giả thuyết đang theo dõi")
            # Ưu tiên open/confirmed; chỉ giữ tối đa 2 ruled_out gần nhất
            active = [h for h in self.hypotheses if h.status in ("open", "confirmed")]
            ruled_out = [h for h in self.hypotheses if h.status == "ruled_out"]
            # Tối đa 6 giả thuyết tổng (tránh context phình khi điều tra dài)
            show = (active + ruled_out[-2:])[:6]
            for h in show:
                ev_refs = []
                for ev_id in h.evidence_ids[-2:]:  # chỉ 2 evidence gần nhất / hypothesis
                    ev = next((e for e in self.evidence if e.id == ev_id), None)
                    if ev:
                        ev_refs.append(f"[{ev.tool_name}: {ev.summary[:80]}]")
                status_mark = {"open": "🔍", "confirmed": "✅", "ruled_out": "❌"}.get(h.status, "?")
                conf_note = f" (độ tin: {h.confidence})" if h.confidence else ""
                lines.append(f"  {status_mark} [{h.id}] {h.content}{conf_note}")
                for ref in ev_refs:
                    lines.append(f"      ↳ {ref}")
            if len(ruled_out) > 2:
                lines.append(f"  ❌ (+{len(ruled_out) - 2} giả thuyết đã loại trừ trước đó)")

        # Bằng chứng mới nhất (chỉ 3 gần nhất)
        if self.evidence:
            lines.append("## Bằng chứng mới thu thập")
            for ev in self.evidence[-3:]:
                lines.append(f"  Bước {ev.step} — {ev.tool_name}: {ev.summary}")

        # Tool đã gọi (tránh lặp)
        if self.tool_call_history:
            called = [f"{c['name']}({list(c['params'].keys())})" for c in self.tool_call_history[-5:]]
            lines.append(f"## Tool đã gọi (gần nhất): {' → '.join(called)}")

        # Warm-start hint từ long-term memory
        if self.warm_start_hint:
            lines.insert(0, f"## Gợi ý từ điều tra trước\n  {self.warm_start_hint}\n")

        return "\n".join(lines) if lines else "(chưa có bằng chứng)"
