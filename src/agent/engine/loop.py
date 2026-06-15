"""
InvestigationEngine — lõi điều tra adaptive.

Mỗi bước là hàm pure: decide_next_action → run_tool → update_state.
Loop đọc state, không đọc lịch sử hội thoại thô.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from agent.engine.state import Evidence, Hypothesis, InvestigationState, Verdict
from agent.llm.base import LLMClient, LLMResponse, Message, ToolCall, ToolSpec
from agent.observability.langfuse_tracer import LangfuseTracer
from agent.storage.db import open_db
from agent.tools.contracts import Observation, Tool, render_for_llm

logger = logging.getLogger(__name__)

# ── E5: Structured verdict tool ──────────────────────────────────────────────

VERDICT_TOOL_NAME = "submit_verdict"

# ── E4: Competing hypothesis gate — nudge tool name ─────────────────────────

_NUDGE_TOOL_NAME = "_competing_gate"

# ── E12: Specificity gate — nudge tool name ─────────────────────────────────

_SPECIFICITY_GATE_NAME = "_specificity_gate"

# ── E6: Hypothesis catalog — loaded from hypothesis_catalog.py, NOT hardcoded here ──────

# E2: Từ ngữ chức năng loại khỏi kiểm tra overlap bằng chứng
_STOP_WORDS = {
    "là", "và", "có", "của", "trong", "cho", "với", "từ", "đến",
    "tại", "gây", "bởi", "do", "qua", "theo", "vì", "khi", "sau",
    "a", "an", "the", "of", "in", "at", "from",
}

SYSTEM_PROMPT = """Bạn là agent điều tra sự cố microservice. Nhiệm vụ: tìm root cause bằng cách gọi tool thu thập bằng chứng, rồi đưa ra verdict NGAY KHI đủ bằng chứng.

Quy tắc bắt buộc:
1. Mỗi lượt chỉ gọi MỘT tool, hoặc đưa ra verdict.
2. Trước khi kết luận: "Đã loại trừ giả thuyết cạnh tranh CHÍNH chưa?" — không cần loại trừ mọi thứ, chỉ cần loại trừ giả thuyết đối lập mạnh nhất.
3. Verdict PHẢI neo bằng chứng cụ thể.
4. Độ tin:
   - CAO: tương quan thời gian rõ + cơ chế nhân quả (vd: deploy ngay trước spike)
   - TRUNG BÌNH: chỉ tương quan thời gian
   - THẤP: suy đoán
5. Phân biệt service lỗi PHÁT SINH (root) vs. lỗi LAN ĐẾN (propagation).
6. HIỆU QUẢ: Nếu đã thấy deploy ngay trước spike VÀ đã kiểm ít nhất 1 giả thuyết cạnh tranh → ĐỦ để kết luận. Không cần kiểm tất cả service.

Khi đã đủ bằng chứng: ưu tiên gọi tool `submit_verdict` với đầy đủ thông tin có cấu trúc.
Fallback (nếu không dùng được tool): trả text theo format PLAIN TEXT:
VERDICT:
Root cause: <mô tả ngắn gọn>
Độ tin: <CAO/TRUNG BÌNH/THẤP/CHƯA ĐỦ BẰNG CHỨNG>
Bằng chứng: <tóm tắt 1-2 câu>
Lan truyền: <lỗi gốc ở đâu, lan thế nào>
Giả thuyết cạnh tranh: <đã loại trừ gì, tại sao>"""


def _tool_sequencing_hint(state: InvestigationState) -> str:
    """E10: Gợi ý tool tiếp theo cho mỗi giả thuyết open có relevant_tool chưa gọi.

    Advisory only — LLM vẫn tự quyết tool. Cap ≤3 giả thuyết để không phình context.
    Ưu tiên giả thuyết có prior_seen_count cao (E11 synergy).
    """
    catalog_index = state.hypothesis_catalog_index
    if not catalog_index:
        return ""

    called_tools = {c["name"] for c in state.tool_call_history}

    # Giả thuyết open, xếp prior lên trước
    open_hyps = sorted(
        [h for h in state.hypotheses if h.status == "open"],
        key=lambda h: h.prior_seen_count,
        reverse=True,
    )
    if not open_hyps:
        return ""

    lines: List[str] = []
    for hyp in open_hyps[:3]:
        entry = catalog_index.get(hyp.id)
        if not entry:
            continue
        uncalled = entry.relevant_tools - called_tools
        if not uncalled:
            continue
        prior_note = f" (prior {hyp.prior_seen_count}×)" if hyp.prior_seen_count > 0 else ""
        tool_list = ", ".join(sorted(uncalled))
        lines.append(f"  {hyp.id}{prior_note} → {tool_list}")

    if not lines:
        return ""
    return "## Tool gợi ý (advisory)\n" + "\n".join(lines)


def _build_user_message(state: InvestigationState, last_obs: Optional[Observation]) -> str:
    parts = [
        f"# Điều tra sự cố: {state.symptom}",
        f"Cửa sổ thời gian: {state.time_window} | Kịch bản: {state.scenario}",
        f"Bước: {state.steps_taken + 1}/{state.step_budget}",
        "",
        state.summarize_for_llm(),
    ]

    if last_obs:
        parts += [
            "",
            "## Kết quả tool vừa chạy:",
            render_for_llm(last_obs),
        ]

    if state.steps_taken + 1 >= state.step_budget - 1:
        parts.append(
            f"\n⚠️ Còn {state.step_budget - state.steps_taken - 1} bước. "
            "Nếu đã đủ bằng chứng, hãy đưa ra VERDICT ngay."
        )

    # E10: gợi ý tool theo giả thuyết open (advisory, cập nhật mỗi bước)
    hint = _tool_sequencing_hint(state)
    if hint:
        parts += ["", hint]

    parts += [
        "",
        "Bước tiếp theo: gọi tool nào, hoặc đưa ra VERDICT?",
    ]

    return "\n".join(parts)


def _tools_to_specs(tools: List[Tool]) -> List[ToolSpec]:
    return [ToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
            for t in tools]


def _build_verdict_tool_spec() -> ToolSpec:
    """E5: Tool spec cho submit_verdict — LLM gọi để kết luận có cấu trúc."""
    return ToolSpec(
        name=VERDICT_TOOL_NAME,
        description=(
            "Đưa ra verdict cuối cùng của cuộc điều tra. "
            "Gọi tool này khi đã đủ bằng chứng để kết luận. "
            "Tất cả field phải neo vào bằng chứng thực tế đã thu thập."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "root_cause": {
                    "type": "string",
                    "description": "Nguyên nhân gốc rễ — mô tả cụ thể, trỏ vào bằng chứng thực tế",
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low", "insufficient"],
                    "description": (
                        "high: tương quan thời gian rõ + cơ chế nhân quả; "
                        "medium: chỉ tương quan thời gian; "
                        "low: suy đoán; insufficient: chưa đủ bằng chứng"
                    ),
                },
                "evidence_summary": {
                    "type": "string",
                    "description": "Tóm tắt bằng chứng chính đã thu thập",
                },
                "propagation": {
                    "type": "string",
                    "description": "Lỗi gốc ở đâu, lan đến dịch vụ nào",
                },
                "competing_hypotheses": {
                    "type": "string",
                    "description": "Giả thuyết cạnh tranh đã loại trừ và lý do",
                },
            },
            "required": ["root_cause", "confidence", "evidence_summary", "propagation", "competing_hypotheses"],
        },
    )


def _structured_args_to_verdict_text(args: dict) -> str:
    """E5: Chuyển args từ submit_verdict tool → text format mà _parse_verdict đọc được.

    Tạo text từ structured data nên reliable hơn LLM tự viết free text.
    """
    conf_map_inv = {
        "high": "CAO", "medium": "TRUNG BÌNH",
        "low": "THẤP", "insufficient": "CHƯA ĐỦ BẰNG CHỨNG",
    }
    conf_vi = conf_map_inv.get(
        str(args.get("confidence", "insufficient")).lower(),
        "CHƯA ĐỦ BẰNG CHỨNG",
    )
    return "\n".join([
        "VERDICT:",
        f"Root cause: {args.get('root_cause', '')}",
        f"Độ tin: {conf_vi}",
        f"Bằng chứng: {args.get('evidence_summary', '')}",
        f"Lan truyền: {args.get('propagation', '')}",
        f"Giả thuyết cạnh tranh: {args.get('competing_hypotheses', '')}",
    ])


def _args_to_verdict(args: dict) -> "Verdict":
    """E9: Dựng Verdict trực tiếp từ submit_verdict args — bỏ text round-trip."""
    conf_valid = {"high", "medium", "low", "insufficient"}
    raw_conf = str(args.get("confidence", "insufficient")).lower().strip()
    confidence = raw_conf if raw_conf in conf_valid else "insufficient"
    return Verdict(
        root_cause=str(args.get("root_cause", "Không xác định")),
        confidence=confidence,
        evidence_summary=str(args.get("evidence_summary", "")),
        propagation_note=str(args.get("propagation", "")),
        competing_hypotheses=str(args.get("competing_hypotheses", "")),
        raw_text="",
        parse_degraded=False,
    )


def _check_evidence_grounding(verdict: "Verdict", evidence: "List[Evidence]") -> "Verdict":
    """E2: Kiểm root_cause có neo vào bằng chứng đã thu không.

    Nếu overlap từ khóa giữa root_cause và evidence summaries < 25% → hạ confidence
    1 bậc + đánh dấu speculative=True. Không chặn verdict — chỉ calibrate tin cậy.
    """
    from agent.engine.state import Verdict as _Verdict

    if verdict.confidence == "insufficient":
        return verdict
    if not evidence:
        return _Verdict(
            root_cause=verdict.root_cause, confidence="insufficient",
            evidence_summary=verdict.evidence_summary,
            propagation_note=verdict.propagation_note,
            competing_hypotheses=verdict.competing_hypotheses,
            raw_text=verdict.raw_text, speculative=True,
        )

    import re
    root_words = set(re.findall(r'\w+', verdict.root_cause.lower())) - _STOP_WORDS
    if not root_words:
        return verdict

    all_ev_words: set = set()
    for ev in evidence:
        all_ev_words.update(re.findall(r'\w+', (ev.summary or "").lower()))

    overlap = root_words & all_ev_words
    overlap_ratio = len(overlap) / len(root_words)

    if overlap_ratio >= 0.25:
        return verdict  # đủ neo bằng chứng

    _downgrade = {"high": "medium", "medium": "low", "low": "insufficient"}
    new_conf = _downgrade.get(verdict.confidence, verdict.confidence)
    warning = f" [⚠ speculative — root cause ít neo bằng chứng: {overlap_ratio:.0%} overlap]"
    logger.warning(
        "Verdict speculative: overlap=%.0f%% root_words=%s overlap_words=%s",
        overlap_ratio * 100, list(root_words)[:5], list(overlap)[:5],
    )
    return _Verdict(
        root_cause=verdict.root_cause, confidence=new_conf,
        evidence_summary=verdict.evidence_summary + warning,
        propagation_note=verdict.propagation_note,
        competing_hypotheses=verdict.competing_hypotheses,
        raw_text=verdict.raw_text, speculative=True,
    )


def _quick_parse_confidence(text: str) -> str:
    """E4: Parse nhanh confidence từ verdict text — không cần full parse."""
    conf_map = {
        "CAO": "high", "TRUNG BÌNH": "medium", "THẤP": "low",
        "CHƯA ĐỦ BẰNG CHỨNG": "insufficient",
        "HIGH": "high", "MEDIUM": "medium", "LOW": "low",
        "INSUFFICIENT": "insufficient",
    }
    for line in text.split("\n"):
        low = line.strip().lower()
        if "độ tin:" in low:
            raw = low.split("độ tin:", 1)[1].strip(" *:").upper()
            for k, v in conf_map.items():
                if k in raw:
                    return v
    return "insufficient"


def _apply_competing_gate(
    state: "InvestigationState",
    vtext: Optional[str] = None,
    *,
    conf_override: Optional[str] = None,
) -> "Tuple[Optional[ToolCall], Optional[str]]":
    """E4: Chặn verdict high/medium nếu còn hypothesis cạnh tranh chưa loại trừ.

    Chỉ gate 1 lần (tránh vòng lặp vô hạn). Gate pass khi:
    - confidence thấp hơn medium
    - không còn competing hypothesis
    - không còn budget
    - gate đã fired rồi

    E9: conf_override cho phép truyền confidence trực tiếp (structured path) thay vì parse từ text.

    Returns (nudge_tool_call, None) khi gate fire,
            (None, vtext) khi gate pass.
    """
    if state._competing_gate_fired:
        return None, vtext

    conf = conf_override if conf_override else (_quick_parse_confidence(vtext) if vtext else "insufficient")
    if conf not in ("high", "medium"):
        return None, vtext

    competing = state.competing_open()
    if not competing:
        return None, vtext

    budget_remaining = state.step_budget - state.steps_taken
    if budget_remaining <= 1:
        return None, vtext

    # Gate fires — nudge LLM loại trừ hypothesis cạnh tranh trước khi kết luận
    state._competing_gate_fired = True
    names = "; ".join(h.content[:60] for h in competing[:3])
    logger.info(
        "[%s] E4 gate cạnh tranh: chặn verdict %s — %d hypothesis open: [%s]",
        state.investigation_id, conf, len(competing), names[:100],
    )
    nudge = ToolCall(
        id="gate_nudge",
        name=_NUDGE_TOOL_NAME,
        arguments={"competing_hypotheses": names, "count": len(competing)},
    )
    return nudge, None


def _apply_specificity_gate(
    state: "InvestigationState",
    vtext: Optional[str] = None,
    *,
    verdict_obj: Optional["Verdict"] = None,
) -> Optional[ToolCall]:
    """E12: Nudge khi verdict mờ (specificity thấp) + còn budget + chưa fired.

    Mirrors _apply_competing_gate: idempotent (1 lần), budget-guard, chỉ high/medium.
    Trả ToolCall(name=_SPECIFICITY_GATE_NAME) nếu gate fires, None nếu pass.
    """
    if state._specificity_gate_fired:
        return None

    if verdict_obj is not None:
        conf = verdict_obj.confidence
        v = verdict_obj
    elif vtext:
        conf = _quick_parse_confidence(vtext)
        v = _parse_verdict(vtext, state)
    else:
        return None

    if conf not in ("high", "medium"):
        return None

    budget_remaining = state.step_budget - state.steps_taken
    if budget_remaining <= 1:
        return None

    from agent.engine.specificity import SPECIFICITY_THRESHOLD, compute_verdict_specificity
    score, reasons = compute_verdict_specificity(v, state)
    if score >= SPECIFICITY_THRESHOLD:
        return None

    state._specificity_gate_fired = True
    logger.info(
        "[%s] E12 specificity gate: score=%.2f < %.2f — %s",
        state.investigation_id, score, SPECIFICITY_THRESHOLD, reasons,
    )
    return ToolCall(
        id="specificity_nudge",
        name=_SPECIFICITY_GATE_NAME,
        arguments={"score": round(score, 2), "reasons": reasons},
    )


async def decide_next_action(
    state: InvestigationState,
    llm: LLMClient,
    tools: List[Tool],
    last_obs: Optional[Observation] = None,
) -> Tuple[Optional[ToolCall], Optional[str], Optional[LLMResponse], Optional[Verdict]]:
    """Pure: nhận state → hỏi LLM → trả (tool_call, verdict_text, llm_response, verdict_obj).

    E9: Structured path trả verdict_obj trực tiếp (bỏ text round-trip).
    Text path (MockLLM / fallback) trả verdict_text, verdict_obj=None.
    Đúng một trong tool_call/verdict_text/verdict_obj sẽ có giá trị.
    """
    user_msg = _build_user_message(state, last_obs)
    # E5: thêm submit_verdict vào tool list để LLM có thể kết luận có cấu trúc
    tool_specs = _tools_to_specs(tools) + [_build_verdict_tool_spec()]
    response = await llm.complete(
        messages=[Message(role="user", content=user_msg)],
        tools=tool_specs,
        system=SYSTEM_PROMPT,
    )

    if response.has_tool_calls:
        tc = response.tool_calls[0]
        # E9: LLM gọi submit_verdict → dựng Verdict trực tiếp (không qua text round-trip)
        if tc.name == VERDICT_TOOL_NAME:
            logger.info("[%s] Bước %d → submit_verdict (E9 structured direct)",
                        state.investigation_id, state.steps_taken + 1)
            return None, None, response, _args_to_verdict(tc.arguments)
        return tc, None, response, None

    # Text response fallback — kiểm tra có phải verdict không (backward compat MockLLM)
    text = response.text or ""
    if "VERDICT" in text.upper():
        return None, text, response, None

    # LLM trả text nhưng không phải verdict → prompt lại (tránh vòng lặp vô hạn)
    logger.warning("LLM trả text không phải verdict, không phải tool_call: %s", text[:100])
    return None, f"VERDICT:\nChưa đủ bằng chứng.\nLLM response: {text}", response, None


async def run_tool(tool_call: ToolCall, tools: List[Tool]) -> Observation:
    """Pure: nhận tool_call → chạy tool → trả Observation."""
    # E4: Nudge từ competing gate — không phải tool thật, trả cảnh báo có cấu trúc
    if tool_call.name == _NUDGE_TOOL_NAME:
        competing = tool_call.arguments.get("competing_hypotheses", "")
        count = tool_call.arguments.get("count", "?")
        return Observation(
            summary=(
                f"⚠️ Cổng cạnh tranh: còn {count} giả thuyết chưa loại trừ: [{competing}]. "
                "Hãy điều tra để loại trừ (hoặc xác nhận) trước khi đưa ra kết luận cuối."
            ),
            aggregates={"gate": "competing_hypothesis", "open_count": count},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={"tool_name": _NUDGE_TOOL_NAME, "gate": "competing"},
        )

    if tool_call.name == _SPECIFICITY_GATE_NAME:
        reasons = tool_call.arguments.get("reasons", [])
        score = tool_call.arguments.get("score", 0.0)
        return Observation(
            summary=(
                f"⚠️ Verdict còn mờ (specificity={score:.2f}): "
                + ("; ".join(reasons) if reasons else "thiếu chi tiết cụ thể") + ". "
                "Hãy bổ sung số liệu cụ thể (version/timestamp/%, so baseline) vào verdict."
            ),
            aggregates={"gate": "specificity", "score": score},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={"tool_name": _SPECIFICITY_GATE_NAME, "gate": "specificity"},
        )

    tool = next((t for t in tools if t.name == tool_call.name), None)
    if tool is None:
        return Observation(
            summary=f"Tool '{tool_call.name}' không tồn tại trong registry.",
            aggregates={}, samples=[], total_count=0, truncated=False,
            metadata={"tool_name": tool_call.name, "error": "not_found"},
        )

    if inspect.iscoroutinefunction(tool.run):
        return await tool.run(tool_call.arguments)
    return await asyncio.get_running_loop().run_in_executor(None, tool.run, tool_call.arguments)


def update_state(
    state: InvestigationState,
    tool_call: ToolCall,
    obs: Observation,
) -> InvestigationState:
    """Pure: nhận state + kết quả → trả state mới (mutate in-place vì dataclass không immutable)."""
    # Ghi bằng chứng
    ev = state.add_evidence(
        step=state.steps_taken,
        tool_name=tool_call.name,
        params=tool_call.arguments,
        obs=obs,
    )

    # Cập nhật/tạo giả thuyết đơn giản dựa trên summary
    _update_hypotheses(state, ev)

    # Ghi lịch sử để phát hiện lặp
    state.tool_call_history.append({"name": tool_call.name, "params": tool_call.arguments})
    state.steps_taken += 1

    return state


def _update_hypotheses(state: InvestigationState, ev: Evidence) -> None:
    """E6: Cập nhật vòng đời giả thuyết dựa trên bằng chứng mới — catalog-driven.

    Đọc catalog từ state.hypothesis_catalog_index (set bởi engine khi khởi tạo).
    Fallback về MICROSERVICE_CATALOG nếu chưa set (backward compat với test/script cũ).

    Phase 1: Tạo hypothesis mới khi evidence có signal từ tool liên quan.
    Phase 2: Cập nhật lifecycle hypothesis đã có (open→confirmed/ruled_out).
    """
    import re
    from agent.engine.hypothesis_catalog import MICROSERVICE_CATALOG, build_catalog_index

    catalog_index = state.hypothesis_catalog_index
    if not catalog_index:
        catalog_index = build_catalog_index(MICROSERVICE_CATALOG)

    summary_lower = ev.summary.lower()
    tool = ev.tool_name

    # --- Phase 1: Tạo hypothesis mới từ signal trong evidence ---
    for entry in catalog_index.values():
        if tool not in entry.relevant_tools:
            continue
        # Rule-out kiểm trước (rule_out_kws thường specific hơn confirm_kws)
        if entry.rule_out_kws and any(kw in summary_lower for kw in entry.rule_out_kws):
            _upsert_hypothesis(state, entry.tag, ev, entry.content,
                               keywords=list(entry.keywords), initial_status="ruled_out")
        elif any(kw in summary_lower for kw in entry.confirm_kws):
            _upsert_hypothesis(state, entry.tag, ev, entry.content,
                               keywords=list(entry.keywords))

    # --- Phase 2: Cập nhật lifecycle cho hypothesis đã có ---
    ev_words = set(re.findall(r'\w+', summary_lower))
    for hyp in state.hypotheses:
        if hyp.status == "ruled_out":
            continue

        entry = catalog_index.get(hyp.id)
        if not entry:
            continue  # hypothesis không có trong catalog → bỏ qua lifecycle update

        rel_tools = entry.relevant_tools
        confirm_kws = entry.confirm_kws
        rule_out_kws = entry.rule_out_kws
        confirm_conf = entry.confirm_conf

        hyp_kw_set = set(hyp.keywords)
        is_relevant = (
            tool in rel_tools
            or bool(hyp_kw_set & ev_words)
            or bool(confirm_kws & ev_words)
        )
        if not is_relevant:
            continue

        if ev.id not in hyp.evidence_ids:
            hyp.evidence_ids.append(ev.id)

        if rule_out_kws and any(kw in summary_lower for kw in rule_out_kws):
            hyp.status = "ruled_out"
            logger.debug("Hypothesis '%s' ruled_out bởi evidence: %s", hyp.id, ev.summary[:60])
            continue

        if hyp.status == "open" and confirm_kws and any(kw in summary_lower for kw in confirm_kws):
            hyp.status = "confirmed"
            hyp.confidence = confirm_conf
            logger.debug("Hypothesis '%s' confirmed (conf=%s): %s", hyp.id, confirm_conf, ev.summary[:60])


def _upsert_hypothesis(
    state: InvestigationState,
    tag: str,
    ev: Evidence,
    content: str,
    keywords: Optional[List[str]] = None,
    initial_status: str = "open",
) -> None:
    """Tạo mới hoặc cập nhật hypothesis theo tag. E1: nhận keywords để match evidence sau."""
    existing = next(
        (h for h in state.hypotheses if h.id == tag or tag in h.id),
        None,
    )
    if existing is None:
        h = state.add_hypothesis(content)
        h.id = tag
        h.keywords = list(keywords or [])
        if initial_status != "open":
            h.status = initial_status  # type: ignore[assignment]
        if ev.id not in h.evidence_ids:
            h.evidence_ids.append(ev.id)
    else:
        # Merge keywords và gắn evidence
        existing.keywords = list(set(existing.keywords) | set(keywords or []))
        if ev.id not in existing.evidence_ids:
            existing.evidence_ids.append(ev.id)
        # Nếu hypothesis đang open và initial_status là ruled_out → chuyển trạng thái
        if initial_status == "ruled_out" and existing.status == "open":
            existing.status = "ruled_out"


def _strip_md(s: str) -> str:
    """Bỏ Markdown bold/italic/header khỏi chuỗi để parse dễ hơn."""
    import re
    s = re.sub(r"\*+", "", s)      # **bold** / *italic*
    s = re.sub(r"^#+\s*", "", s)   # ## heading
    s = re.sub(r"`+", "", s)       # `code`
    return s.strip()


def _parse_verdict(text: str, state: InvestigationState) -> Verdict:
    """Trích xuất thông tin từ text verdict của LLM.

    Xử lý cả plain text lẫn Markdown (LLM hay dùng **bold**).
    """
    lines = text.split("\n")

    root_cause = ""
    confidence_raw = ""
    evidence_summary = ""
    propagation = ""
    competing = ""

    for line in lines:
        clean = _strip_md(line)
        low = clean.lower()

        if low.startswith("root cause:"):
            root_cause = clean.split(":", 1)[1].strip()
        elif low.startswith("độ tin:"):
            confidence_raw = clean.split(":", 1)[1].strip().upper()
        elif low.startswith("bằng chứng:") and not evidence_summary:
            evidence_summary = clean.split(":", 1)[1].strip()
        elif low.startswith("lan truyền:"):
            propagation = clean.split(":", 1)[1].strip()
        elif low.startswith("giả thuyết cạnh tranh:"):
            competing = clean.split(":", 1)[1].strip()

    # Fallback: nếu không parse được root_cause, lấy dòng đầu sau "VERDICT"
    if not root_cause:
        in_verdict = False
        for line in lines:
            clean = _strip_md(line)
            if "VERDICT" in clean.upper():
                in_verdict = True
                continue
            if in_verdict and clean and not clean.startswith("#"):
                root_cause = clean
                break

    conf_map = {
        "CAO": "high", "TRUNG BÌNH": "medium", "THẤP": "low",
        "CHƯA ĐỦ BẰNG CHỨNG": "insufficient", "INSUFFICIENT": "insufficient",
        "HIGH": "high", "MEDIUM": "medium", "LOW": "low",
    }
    # E5: Chuẩn hóa confidence_raw; parse fail → "insufficient" (không giả vờ tự tin)
    conf_key = confidence_raw.strip(" *:").upper()
    confidence = conf_map.get(conf_key, "insufficient")

    return Verdict(
        root_cause=root_cause or "(không parse được)",
        confidence=confidence,
        evidence_summary=evidence_summary,
        propagation_note=propagation,
        competing_hypotheses=competing,
        raw_text=text,
    )


def _check_stop_conditions(state: "InvestigationState") -> Optional[str]:
    """E7: Kiểm điều kiện dừng — dùng chung cho cả while-loop path lẫn LangGraph path.

    Trả verdict_text (str) nếu nên dừng, trả None nếu tiếp tục.
    Mutate state.stop_reason và state.finished khi dừng.
    """
    if state.steps_taken >= state.step_budget:
        state.stop_reason = "budget"
        state.finished = True
        return (
            "VERDICT:\nRoot cause: Chưa xác định được trong ngân sách bước.\n"
            "Độ tin: CHƯA ĐỦ BẰNG CHỨNG\n"
            f"Bằng chứng: Đã đi {state.steps_taken} bước, chưa kết luận.\n"
            "Lan truyền: Không rõ\nGiả thuyết cạnh tranh: Chưa loại trừ đủ"
        )
    if state.is_looping():
        state.stop_reason = "loop_detected"
        state.finished = True
        last_summary = state.evidence[-1].summary if state.evidence else "N/A"
        return (
            "VERDICT:\nRoot cause: Phát hiện vòng lặp tool — dừng sớm.\n"
            "Độ tin: THẤP\n"
            f"Bằng chứng: {last_summary}\n"
            "Lan truyền: Không rõ\nGiả thuyết cạnh tranh: Chưa loại trừ đủ"
        )
    return None


def _preseed_hypotheses(
    project_id: str,
    service: str,
    rct_index: Dict[str, Any],
) -> List[Hypothesis]:
    """E11: Tạo Hypothesis open từ investigation_patterns của service này.

    Trả [] nếu service rỗng, DB chưa có dữ liệu, hoặc lỗi.
    Hypothesis được tạo với id = catalog.tag để _upsert_hypothesis merge đúng sau này.
    """
    if not service or not rct_index:
        return []
    try:
        from agent.memory.patterns import get_service_priors
        priors = get_service_priors(project_id, service)
    except Exception:
        return []

    result: List[Hypothesis] = []
    for prior in priors:
        rct = prior.get("root_cause_type", "")
        entry = rct_index.get(rct)
        if not entry:
            continue
        h = Hypothesis(
            id=entry.tag,
            content=entry.content,
            status="open",
            keywords=list(entry.keywords),
            prior_seen_count=prior.get("count", 0),
        )
        result.append(h)
    return result


def _emit_trace(
    investigation_id: str,
    step: int,
    event_type: str,
    payload: Dict[str, Any],
    project_id: str = "default",
) -> None:
    """Ghi một trace event vào SQLite + push SSE. Fire-and-forget, không throw."""
    try:
        conn = open_db()
        conn.execute(
            "INSERT INTO trace_events "
            "(investigation_id, step, timestamp, event_type, payload, project_id) "
            "VALUES (?,?,?,?,?,?)",
            (investigation_id, step, datetime.now(timezone.utc).isoformat(),
             event_type, json.dumps(payload, ensure_ascii=False, default=str),
             project_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Không ghi được trace event: %s", e)

    # Push SSE (no-op nếu không có subscriber)
    try:
        from agent.dashboard.sse import publish_sync
        publish_sync(investigation_id, event_type, payload)
    except Exception:
        pass


class InvestigationEngine:
    """Orchestrator — chạy vòng lặp adaptive đến khi dừng.

    Bên trong dùng LangGraph StateGraph (nếu available), fallback về while loop.
    Public interface không đổi: run() → InvestigationState.
    """

    def __init__(
        self,
        llm: LLMClient,
        tools: List[Tool],
        step_budget: int = 10,
        hypothesis_catalog=None,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.step_budget = step_budget
        # E6: build catalog index cho domain (default microservice)
        from agent.engine.hypothesis_catalog import (
            MICROSERVICE_CATALOG, build_catalog_index, build_rct_index,
        )
        _catalog = hypothesis_catalog if hypothesis_catalog is not None else MICROSERVICE_CATALOG
        self._catalog_index = build_catalog_index(_catalog)
        self._rct_index = build_rct_index(_catalog)  # E11: root_cause_type → entry
        # Try compile LangGraph (lazy — lỗi import thì fallback)
        self._graph = None
        try:
            from agent.engine.graph import get_compiled_graph
            self._graph = get_compiled_graph()
        except Exception as e:
            logger.info("LangGraph không khả dụng, dùng while loop: %s", e)

    async def run(
        self,
        symptom: str,
        time_window: str,
        scenario: str = "scenario1",
        date: str = "2024-01-15",
        project_id: str = "default",
        available_services: Optional[List[str]] = None,
        warm_start_hint: Optional[str] = None,
        investigation_id: Optional[str] = None,
        service: Optional[str] = None,   # E11: service name cho prior lookup
    ) -> InvestigationState:
        investigation_id = investigation_id or str(uuid.uuid4())[:12]
        state = InvestigationState(
            investigation_id=investigation_id,
            symptom=symptom,
            time_window=time_window,
            scenario=scenario,
            date=date,
            step_budget=self.step_budget,
            project_id=project_id,
            available_services=available_services or [],
            warm_start_hint=warm_start_hint,
            hypothesis_catalog_index=self._catalog_index,  # E6: domain catalog
        )

        # E11: Pre-seed hypothesis open từ investigation_patterns của service này
        _svc = service or (symptom.split(":")[0].strip() if ":" in symptom else "")
        prior_hyps = _preseed_hypotheses(project_id, _svc, self._rct_index)
        state.hypotheses.extend(prior_hyps)
        if prior_hyps:
            logger.info("[%s] E11 pre-seed %d hypothesis(es) cho service='%s': %s",
                        investigation_id, len(prior_hyps), _svc,
                        [h.id for h in prior_hyps])

        logger.info("[%s] [%s] Bắt đầu điều tra (via %s): %s",
                    investigation_id, project_id,
                    "LangGraph" if self._graph else "loop", symptom)
        _emit_trace(investigation_id, 0, "investigation_start", {
            "symptom": symptom, "time_window": time_window, "scenario": scenario,
            "project_id": project_id, "available_services": available_services or [],
            "engine": "langgraph" if self._graph else "loop",
        }, project_id=project_id)

        tracer = LangfuseTracer(
            investigation_id=investigation_id,
            symptom=symptom,
            scenario=scenario,
            project_id=project_id,
        )

        if self._graph is not None:
            state, verdict_text, verdict_obj = await self._run_with_graph(state, tracer)
        else:
            state, verdict_text, verdict_obj = await self._run_loop(state, tracer, investigation_id)

        # --- Finalize ---
        from agent.engine.calibration import apply_calibration
        if verdict_obj is not None:
            # E9: structured direct path — dùng Verdict đã dựng, không parse text
            state.verdict = verdict_obj
            state.verdict = _check_evidence_grounding(state.verdict, state.evidence)
            state.verdict = apply_calibration(state.verdict)
        elif verdict_text:
            # Fallback text-parse path (MockLLM / stop conditions / error)
            state.verdict = _parse_verdict(verdict_text, state)
            state.verdict.parse_degraded = True  # E9: đánh dấu đường fallback
            # E2: Kiểm tra root_cause có neo vào bằng chứng không; hạ confidence nếu không
            state.verdict = _check_evidence_grounding(state.verdict, state.evidence)
            # E8: Calibration — hạ confidence nếu historical accuracy < threshold
            state.verdict = apply_calibration(state.verdict)

        # E12: compute + store specificity score trên verdict cuối
        if state.verdict:
            from agent.engine.specificity import compute_verdict_specificity
            spec_score, _ = compute_verdict_specificity(state.verdict, state)
            state.verdict.specificity_score = spec_score

        # Ngày 33: Multi-agent conflict resolution — annotate khi nhiều hypothesis confirmed
        winner = state.resolve_conflicting_hypotheses()
        n_confirmed = sum(1 for h in state.hypotheses if h.status == "confirmed")
        if winner and state.verdict and n_confirmed > 1:
            conflict_note = (
                f" [Conflict resolved: {n_confirmed} confirmed; winner={winner.id}"
                f" conf={winner.confidence} ev={len(winner.evidence_ids)}]"
            )
            state.verdict.competing_hypotheses = (
                (state.verdict.competing_hypotheses or "") + conflict_note
            )
            logger.info(
                "[%s] Conflict resolution: %d confirmed → winner=%s (%s)",
                investigation_id, n_confirmed, winner.id, winner.confidence,
            )

        _emit_trace(investigation_id, state.steps_taken, "verdict", {
            "stop_reason": state.stop_reason,
            "root_cause": state.verdict.root_cause if state.verdict else "N/A",
            "confidence": state.verdict.confidence if state.verdict else "N/A",
            "speculative": state.verdict.speculative if state.verdict else False,
            "parse_degraded": state.verdict.parse_degraded if state.verdict else False,
            "specificity_score": state.verdict.specificity_score if state.verdict else None,
            "total_tokens": state.total_tokens,
            # P1: prompt caching stats
            "cache_creation_tokens": state.cache_creation_tokens,
            "cache_read_tokens": state.cache_read_tokens,
        }, project_id=project_id)
        tracer.record_verdict(state.stop_reason, state.verdict)
        tracer.flush()

        logger.info("[%s] Kết thúc. Stop: %s | Root cause: %s",
                    investigation_id, state.stop_reason,
                    state.verdict.root_cause if state.verdict else "N/A")
        return state

    # -----------------------------------------------------------------------
    # Private: LangGraph path
    # -----------------------------------------------------------------------

    async def _run_with_graph(
        self,
        state: InvestigationState,
        tracer: Any,
    ) -> Tuple[InvestigationState, Optional[str], Optional[Verdict]]:
        """Chạy investigation loop qua LangGraph StateGraph."""
        initial: Dict[str, Any] = {
            "inv": state,
            "last_obs": None,
            "tool_call": None,
            "verdict_text": None,
            "verdict_obj": None,
            "llm": self.llm,
            "tools": self.tools,
            "tracer": tracer,
        }
        # recursion_limit phải ≥ step_budget × 3 (mỗi bước = decide+run_tool+update)
        # + đệm cho node decide kết thúc. Engine tự dừng bằng step_budget; đây chỉ là
        # trần an toàn của LangGraph, KHÔNG được thấp hơn budget engine. Mặc định LG=25
        # gây GraphRecursionError với real-LLM đi sâu (>8 bước) — bug bị mock che.
        from langgraph.errors import GraphRecursionError

        recursion_limit = self.step_budget * 3 + 6
        try:
            result = await self._graph.ainvoke(
                initial, config={"recursion_limit": recursion_limit}
            )
            return result["inv"], result.get("verdict_text"), result.get("verdict_obj")
        except GraphRecursionError:
            logger.warning(
                "[%s] Chạm recursion_limit=%d của LangGraph — kết luận partial (không chết im lặng).",
                state.investigation_id, recursion_limit,
            )
            state.stop_reason = "recursion_limit"
            state.finished = True
            verdict_text = (
                "VERDICT:\nRoot cause: Chưa xác định — chạm trần đệ quy graph.\n"
                "Độ tin: CHƯA ĐỦ BẰNG CHỨNG\n"
                f"Bằng chứng: Đã đi {state.steps_taken} bước, chưa kết luận.\n"
                "Lan truyền: Không rõ\nGiả thuyết cạnh tranh: Chưa loại trừ đủ"
            )
            return state, verdict_text, None

    # -----------------------------------------------------------------------
    # Private: fallback while-loop path (original logic)
    # -----------------------------------------------------------------------

    async def _run_loop(
        self,
        state: InvestigationState,
        tracer: Any,
        investigation_id: str,
    ) -> Tuple[InvestigationState, Optional[str], Optional[Verdict]]:
        """Fallback: original adaptive while loop."""
        last_obs: Optional[Observation] = None
        verdict_text: Optional[str] = None
        verdict_obj: Optional[Verdict] = None

        while not state.finished:
            # E7: điều kiện dừng dùng chung với LangGraph path
            stop_vtext = _check_stop_conditions(state)
            if stop_vtext:
                verdict_text = stop_vtext
                break

            current_step = state.steps_taken
            tracer.start_step(current_step)

            try:
                t_llm = time.monotonic()
                tool_call, vtext, llm_resp, v_obj = await decide_next_action(
                    state, self.llm, self.tools, last_obs
                )
                llm_ms = (time.monotonic() - t_llm) * 1000
            except Exception as e:
                logger.error("[%s] LLM error tại bước %d: %s", investigation_id, current_step, e)
                tracer.end_step()
                state.stop_reason = "llm_error"
                state.finished = True
                verdict_text = (
                    f"VERDICT:\nRoot cause: LLM lỗi — {e}\n"
                    "Độ tin: CHƯA ĐỦ BẰNG CHỨNG\n"
                    "Bằng chứng: N/A\nLan truyền: N/A\nGiả thuyết cạnh tranh: N/A"
                )
                break

            if llm_resp and llm_resp.usage:
                state.total_tokens += (
                    llm_resp.usage.get("input_tokens", 0)
                    + llm_resp.usage.get("output_tokens", 0)
                )
                # P1: accumulate cache stats for cost dashboard
                state.cache_creation_tokens += llm_resp.usage.get("cache_creation_input_tokens", 0)
                state.cache_read_tokens += llm_resp.usage.get("cache_read_input_tokens", 0)

            output_desc = (
                f"tool:{tool_call.name}" if tool_call
                else ("verdict_structured" if v_obj is not None else ("verdict" if vtext else "no_action"))
            )
            tracer.record_llm_call(
                input_summary=state.symptom[:200],
                output_summary=output_desc,
                usage=llm_resp.usage if llm_resp else None,
                latency_ms=llm_ms,
            )

            if v_obj is not None:
                # E9: structured path — cổng cạnh tranh rồi cổng specificity
                nudge_tc, _ = _apply_competing_gate(state, conf_override=v_obj.confidence)
                if nudge_tc:
                    tool_call = nudge_tc
                    v_obj = None
                else:
                    # E12: specificity gate
                    spec_tc = _apply_specificity_gate(state, verdict_obj=v_obj)
                    if spec_tc:
                        tool_call = spec_tc
                        v_obj = None
                    else:
                        verdict_obj = v_obj
                        state.stop_reason = "verdict"
                        state.finished = True
                        tracer.end_step()
                        break

            if vtext:
                # E4: cổng cạnh tranh — chặn verdict high/medium nếu còn hypothesis open
                nudge_tc, accepted_vtext = _apply_competing_gate(state, vtext)
                if nudge_tc:
                    # Gate fires: inject nudge như một tool call, tiếp tục vòng
                    tool_call = nudge_tc
                else:
                    # E12: specificity gate
                    spec_tc = _apply_specificity_gate(state, accepted_vtext)
                    if spec_tc:
                        tool_call = spec_tc
                    else:
                        verdict_text = accepted_vtext
                        state.stop_reason = "verdict"
                        state.finished = True
                        tracer.end_step()
                        break

            if tool_call is None:
                logger.warning("[%s] Không có tool_call lẫn verdict", investigation_id)
                tracer.end_step()
                break

            _emit_trace(investigation_id, current_step, "tool_call", {
                "tool": tool_call.name, "args": tool_call.arguments,
            })
            logger.info("[%s] Bước %d → %s(%s)",
                        investigation_id, current_step + 1,
                        tool_call.name, tool_call.arguments)

            try:
                t_tool = time.monotonic()
                obs = await run_tool(tool_call, self.tools)
                tool_ms = (time.monotonic() - t_tool) * 1000
            except Exception as e:
                logger.error("[%s] Tool error: %s", investigation_id, e)
                from agent.tools.contracts import Observation as Obs
                obs = Obs(
                    summary=f"Tool {tool_call.name} lỗi: {e}",
                    aggregates={}, samples=[], total_count=0, truncated=False,
                    metadata={"tool_name": tool_call.name, "error": str(e)},
                )
                tool_ms = (time.monotonic() - t_tool) * 1000

            _emit_trace(investigation_id, current_step, "tool_result", {
                "tool": tool_call.name, "summary": obs.summary,
            })
            tracer.record_tool_call(
                tool_name=tool_call.name,
                args=tool_call.arguments,
                result_summary=obs.summary,
                latency_ms=tool_ms,
            )

            state = update_state(state, tool_call, obs)
            tracer.end_step()
            last_obs = obs

        return state, verdict_text, verdict_obj
