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

# ── E1: Hypothesis lifecycle — relevance config per tag ──────────────────────

_HYPOTHESIS_RELEVANCE: Dict[str, Dict] = {
    "deploy": {
        "tools": {"get_recent_deploys"},
        "confirm_kws": {"deployment", "deploy", "version", "release", "tìm thấy"},
        "rule_out_kws": {"không tìm thấy", "0 deployment", "no deployment"},
        "confirm_conf": "medium",
    },
    "timeout": {
        "tools": {"get_error_breakdown", "trace_request"},
        "confirm_kws": {"timeoutexception", "timeout", "latency", "deadline", "chậm"},
        "rule_out_kws": {"không có timeout", "latency bình thường"},
        "confirm_conf": "medium",
    },
    "latency_spike": {
        "tools": {"get_metrics"},
        "confirm_kws": {"lệch", "x baseline", "spike", "tăng", "cao hơn"},
        "rule_out_kws": {"bình thường", "không lệch", "normal"},
        "confirm_conf": "medium",
    },
    "pool_exhaustion": {
        "tools": {"get_metrics", "get_error_breakdown"},
        "confirm_kws": {"pool", "exhaustion", "connection", "wait_time", "queue"},
        "rule_out_kws": {"pool bình thường"},
        "confirm_conf": "high",
    },
    "provider_down": {
        "tools": {"get_dependencies", "get_error_breakdown"},
        "confirm_kws": {"provider", "unavailable", "serviceunavailable", "503", "sập"},
        "rule_out_kws": {"provider ok", "bình thường"},
        "confirm_conf": "high",
    },
}

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
    vtext: str,
) -> "Tuple[Optional[ToolCall], Optional[str]]":
    """E4: Chặn verdict high/medium nếu còn hypothesis cạnh tranh chưa loại trừ.

    Chỉ gate 1 lần (tránh vòng lặp vô hạn). Gate pass khi:
    - confidence thấp hơn medium
    - không còn competing hypothesis
    - không còn budget
    - gate đã fired rồi

    Returns (nudge_tool_call, None) khi gate fire,
            (None, vtext) khi gate pass.
    """
    if state._competing_gate_fired:
        return None, vtext

    conf = _quick_parse_confidence(vtext)
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


async def decide_next_action(
    state: InvestigationState,
    llm: LLMClient,
    tools: List[Tool],
    last_obs: Optional[Observation] = None,
) -> Tuple[Optional[ToolCall], Optional[str], Optional[LLMResponse]]:
    """Pure: nhận state → hỏi LLM → trả (tool_call, verdict_text, llm_response).

    Đúng một trong tool_call/verdict_text sẽ có giá trị; llm_response luôn có (trừ exception).
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
        # E5: LLM gọi submit_verdict → chuyển args có cấu trúc → verdict text reliable
        if tc.name == VERDICT_TOOL_NAME:
            logger.info("[%s] Bước %d → submit_verdict (structured)",
                        state.investigation_id, state.steps_taken + 1)
            return None, _structured_args_to_verdict_text(tc.arguments), response
        return tc, None, response

    # Text response fallback — kiểm tra có phải verdict không (backward compat MockLLM)
    text = response.text or ""
    if "VERDICT" in text.upper():
        return None, text, response

    # LLM trả text nhưng không phải verdict → prompt lại (tránh vòng lặp vô hạn)
    logger.warning("LLM trả text không phải verdict, không phải tool_call: %s", text[:100])
    return None, f"VERDICT:\nChưa đủ bằng chứng.\nLLM response: {text}", response


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

    tool = next((t for t in tools if t.name == tool_call.name), None)
    if tool is None:
        return Observation(
            summary=f"Tool '{tool_call.name}' không tồn tại trong registry.",
            aggregates={}, samples=[], total_count=0, truncated=False,
            metadata={"tool_name": tool_call.name, "error": "not_found"},
        )

    if inspect.iscoroutinefunction(tool.run):
        return await tool.run(tool_call.arguments)
    return await asyncio.get_event_loop().run_in_executor(None, tool.run, tool_call.arguments)


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
    """E1: Cập nhật vòng đời giả thuyết dựa trên bằng chứng mới.

    Thay heuristic cũ (append mù vào mọi open hypothesis):
    - Tạo hypothesis khi evidence signal rõ
    - Chỉ gắn evidence vào hypothesis CÓ LIÊN QUAN (tool/keyword match)
    - Chuyển open→confirmed khi bằng chứng xác nhận
    - Chuyển open→ruled_out khi bằng chứng mâu thuẫn
    - Set confidence trên hypothesis theo loại bằng chứng
    """
    import re
    summary_lower = ev.summary.lower()
    tool = ev.tool_name

    # --- Tạo hypothesis mới từ signal trong evidence ---
    if tool == "get_recent_deploys":
        if "tìm thấy" in summary_lower and ("deployment" in summary_lower or "deploy" in summary_lower):
            _upsert_hypothesis(state, "deploy", ev,
                               "Deployment gần đây gây ra sự cố",
                               keywords=["deployment", "deploy", "version"])
        elif "không tìm thấy" in summary_lower:
            # Không có deploy → tạo hypothesis với status ruled_out ngay
            _upsert_hypothesis(state, "deploy", ev,
                               "Deployment gần đây gây ra sự cố",
                               keywords=["deployment", "deploy"],
                               initial_status="ruled_out")

    if tool == "get_error_breakdown" and "timeoutexception" in summary_lower:
        _upsert_hypothesis(state, "timeout", ev,
                           "Downstream service phản hồi chậm gây timeout lan lên",
                           keywords=["timeout", "latency", "chậm"])

    if tool == "get_metrics" and ("lệch" in summary_lower or "x baseline" in summary_lower):
        _upsert_hypothesis(state, "latency_spike", ev,
                           "Latency spike — có thể do code thay đổi hoặc dependency chậm",
                           keywords=["latency", "spike", "lệch"])

    if tool in ("get_metrics", "get_error_breakdown") and (
        "pool" in summary_lower or "exhaustion" in summary_lower or "wait_time" in summary_lower
    ):
        _upsert_hypothesis(state, "pool_exhaustion", ev,
                           "Connection pool exhaustion — quá nhiều kết nối đồng thời",
                           keywords=["pool", "exhaustion", "connection", "wait_time"])

    if tool in ("get_dependencies", "get_error_breakdown") and (
        "unavailable" in summary_lower or "serviceunavailable" in summary_lower
        or "503" in summary_lower or "sập" in summary_lower
    ):
        _upsert_hypothesis(state, "provider_down", ev,
                           "Provider/dependency ngoài bị sập",
                           keywords=["provider", "unavailable", "sập"])

    # --- Cập nhật lifecycle cho hypothesis đã có ---
    ev_words = set(re.findall(r'\w+', summary_lower))
    for hyp in state.hypotheses:
        if hyp.status == "ruled_out":
            continue  # không tái xử lý hypothesis đã loại trừ

        rel_cfg = _HYPOTHESIS_RELEVANCE.get(hyp.id, {})
        rel_tools: set = rel_cfg.get("tools", set())
        confirm_kws: set = rel_cfg.get("confirm_kws", set())
        rule_out_kws: set = rel_cfg.get("rule_out_kws", set())
        confirm_conf: str = rel_cfg.get("confirm_conf", "medium")

        # Kiểm liên quan: tool match HOẶC keyword overlap với hyp.keywords
        hyp_kw_set = set(hyp.keywords)
        is_relevant = (
            tool in rel_tools
            or bool(hyp_kw_set & ev_words)
            or bool(confirm_kws & ev_words)
        )
        if not is_relevant:
            continue  # bằng chứng không liên quan → bỏ qua

        # Gắn evidence vào hypothesis
        if ev.id not in hyp.evidence_ids:
            hyp.evidence_ids.append(ev.id)

        # Rule-out: bằng chứng mâu thuẫn
        if rule_out_kws and any(kw in summary_lower for kw in rule_out_kws):
            hyp.status = "ruled_out"
            logger.debug("Hypothesis '%s' ruled_out bởi evidence: %s", hyp.id, ev.summary[:60])
            continue

        # Confirm: bằng chứng xác nhận mạnh
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

    def __init__(self, llm: LLMClient, tools: List[Tool], step_budget: int = 10) -> None:
        self.llm = llm
        self.tools = tools
        self.step_budget = step_budget
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
        )

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
            state, verdict_text = await self._run_with_graph(state, tracer)
        else:
            state, verdict_text = await self._run_loop(state, tracer, investigation_id)

        # --- Finalize ---
        if verdict_text:
            state.verdict = _parse_verdict(verdict_text, state)
            # E2: Kiểm tra root_cause có neo vào bằng chứng không; hạ confidence nếu không
            state.verdict = _check_evidence_grounding(state.verdict, state.evidence)

        _emit_trace(investigation_id, state.steps_taken, "verdict", {
            "stop_reason": state.stop_reason,
            "root_cause": state.verdict.root_cause if state.verdict else "N/A",
            "confidence": state.verdict.confidence if state.verdict else "N/A",
            "speculative": state.verdict.speculative if state.verdict else False,
            "total_tokens": state.total_tokens,
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
    ) -> Tuple[InvestigationState, Optional[str]]:
        """Chạy investigation loop qua LangGraph StateGraph."""
        initial: Dict[str, Any] = {
            "inv": state,
            "last_obs": None,
            "tool_call": None,
            "verdict_text": None,
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
            return result["inv"], result.get("verdict_text")
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
            return state, verdict_text

    # -----------------------------------------------------------------------
    # Private: fallback while-loop path (original logic)
    # -----------------------------------------------------------------------

    async def _run_loop(
        self,
        state: InvestigationState,
        tracer: Any,
        investigation_id: str,
    ) -> Tuple[InvestigationState, Optional[str]]:
        """Fallback: original adaptive while loop."""
        last_obs: Optional[Observation] = None
        verdict_text: Optional[str] = None

        while not state.finished:
            if state.steps_taken >= state.step_budget:
                state.stop_reason = "budget"
                state.finished = True
                verdict_text = (
                    "VERDICT:\nRoot cause: Chưa xác định được trong ngân sách bước.\n"
                    "Độ tin: CHƯA ĐỦ BẰNG CHỨNG\n"
                    f"Bằng chứng: Đã đi {state.steps_taken} bước, chưa kết luận.\n"
                    "Lan truyền: Không rõ\nGiả thuyết cạnh tranh: Chưa loại trừ đủ"
                )
                break

            if state.is_looping():
                state.stop_reason = "loop_detected"
                state.finished = True
                verdict_text = (
                    "VERDICT:\nRoot cause: Phát hiện vòng lặp tool — dừng sớm.\n"
                    "Độ tin: THẤP\n"
                    f"Bằng chứng: {state.evidence[-1].summary if state.evidence else 'N/A'}\n"
                    "Lan truyền: Không rõ\nGiả thuyết cạnh tranh: Chưa loại trừ đủ"
                )
                break

            current_step = state.steps_taken
            tracer.start_step(current_step)

            try:
                t_llm = time.monotonic()
                tool_call, vtext, llm_resp = await decide_next_action(
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

            output_desc = (f"tool:{tool_call.name}" if tool_call
                           else ("verdict" if vtext else "no_action"))
            tracer.record_llm_call(
                input_summary=state.symptom[:200],
                output_summary=output_desc,
                usage=llm_resp.usage if llm_resp else None,
                latency_ms=llm_ms,
            )

            if vtext:
                # E4: cổng cạnh tranh — chặn verdict high/medium nếu còn hypothesis open
                nudge_tc, accepted_vtext = _apply_competing_gate(state, vtext)
                if nudge_tc:
                    # Gate fires: inject nudge như một tool call, tiếp tục vòng
                    tool_call = nudge_tc
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

        return state, verdict_text
