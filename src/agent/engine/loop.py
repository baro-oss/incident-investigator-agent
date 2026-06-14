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

Trả verdict bằng định dạng PLAIN TEXT (không dùng Markdown):
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
    response = await llm.complete(
        messages=[Message(role="user", content=user_msg)],
        tools=_tools_to_specs(tools),
        system=SYSTEM_PROMPT,
    )

    if response.has_tool_calls:
        return response.tool_calls[0], None, response

    # Text response — kiểm tra có phải verdict không
    text = response.text or ""
    if "VERDICT" in text.upper():
        return None, text, response

    # LLM trả text nhưng không phải verdict → prompt lại (tránh vòng lặp vô hạn)
    logger.warning("LLM trả text không phải verdict, không phải tool_call: %s", text[:100])
    return None, f"VERDICT:\nChưa đủ bằng chứng.\nLLM response: {text}", response


async def run_tool(tool_call: ToolCall, tools: List[Tool]) -> Observation:
    """Pure: nhận tool_call → chạy tool → trả Observation."""
    tool = next((t for t in tools if t.name == tool_call.name), None)
    if tool is None:
        from agent.tools.contracts import Observation
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
    """Cập nhật/tạo giả thuyết dựa trên bằng chứng mới (heuristic đơn giản)."""
    summary_lower = ev.summary.lower()

    # Heuristic: deploy gần đây → tạo/cập nhật hypothesis deploy
    if ev.tool_name == "get_recent_deploys" and "deployment" in summary_lower:
        _upsert_hypothesis(state, "deploy", ev,
                           "Deployment gần đây gây ra sự cố")

    # Heuristic: lỗi timeout cao bất thường → giả thuyết downstream chậm
    if ev.tool_name == "get_error_breakdown" and "timeoutexception" in summary_lower:
        _upsert_hypothesis(state, "timeout", ev,
                           "Downstream service phản hồi chậm gây timeout lan lên")

    # Heuristic: latency spike → giả thuyết tài nguyên hoặc dependency chậm
    if ev.tool_name == "get_metrics" and ("lệch" in summary_lower or "x baseline" in summary_lower):
        _upsert_hypothesis(state, "latency_spike", ev,
                           "Latency spike — có thể do code thay đổi hoặc dependency chậm")

    # Gắn bằng chứng vào tất cả hypothesis đang open
    for h in state.hypotheses:
        if h.status == "open" and ev.id not in h.evidence_ids:
            h.evidence_ids.append(ev.id)


def _upsert_hypothesis(state: InvestigationState, tag: str, ev: Evidence, content: str) -> None:
    existing = next((h for h in state.hypotheses if tag in h.id or tag in h.content.lower()), None)
    if existing is None:
        h = state.add_hypothesis(content)
        h.id = tag  # dùng tag làm id để dễ upsert
    else:
        existing.evidence_ids.append(ev.id)


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
    # Chuẩn hóa confidence_raw: bỏ ký tự thừa, so sánh linh hoạt
    conf_key = confidence_raw.strip(" *:").upper()
    confidence = conf_map.get(conf_key, "medium")

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
    """Ghi một trace event vào SQLite. Fire-and-forget, không throw."""
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


class InvestigationEngine:
    """Orchestrator — chạy vòng lặp adaptive đến khi dừng."""

    def __init__(self, llm: LLMClient, tools: List[Tool], step_budget: int = 10) -> None:
        self.llm = llm
        self.tools = tools
        self.step_budget = step_budget

    async def run(
        self,
        symptom: str,
        time_window: str,
        scenario: str = "scenario1",
        date: str = "2024-01-15",
        project_id: str = "default",
        available_services: Optional[List[str]] = None,
        warm_start_hint: Optional[str] = None,
    ) -> InvestigationState:
        investigation_id = str(uuid.uuid4())[:12]
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

        logger.info("[%s] [%s] Bắt đầu điều tra: %s", investigation_id, project_id, symptom)
        _emit_trace(investigation_id, 0, "investigation_start", {
            "symptom": symptom, "time_window": time_window, "scenario": scenario,
            "project_id": project_id, "available_services": available_services or [],
        }, project_id=project_id)

        tracer = LangfuseTracer(
            investigation_id=investigation_id,
            symptom=symptom,
            scenario=scenario,
            project_id=project_id,
        )

        last_obs: Optional[Observation] = None
        verdict_text: Optional[str] = None

        while not state.finished:
            # --- Điều kiện dừng ---
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

            # --- Quyết định hành động ---
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

            # Accumulate tokens
            if llm_resp and llm_resp.usage:
                state.total_tokens += (
                    llm_resp.usage.get("input_tokens", 0)
                    + llm_resp.usage.get("output_tokens", 0)
                )

            # Ghi LLM call lên Langfuse
            output_desc = (f"tool:{tool_call.name}" if tool_call
                           else ("verdict" if vtext else "no_action"))
            tracer.record_llm_call(
                input_summary=state.symptom[:200],
                output_summary=output_desc,
                usage=llm_resp.usage if llm_resp else None,
                latency_ms=llm_ms,
            )

            if vtext:
                verdict_text = vtext
                state.stop_reason = "verdict"
                state.finished = True
                tracer.end_step()
                break

            if tool_call is None:
                logger.warning("[%s] Không có tool_call lẫn verdict", investigation_id)
                tracer.end_step()
                break

            # --- Ghi trace: chọn tool ---
            _emit_trace(investigation_id, current_step, "tool_call", {
                "tool": tool_call.name, "args": tool_call.arguments,
            })
            logger.info("[%s] Bước %d → %s(%s)",
                        investigation_id, current_step + 1,
                        tool_call.name, tool_call.arguments)

            # --- Chạy tool ---
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

            # --- Cập nhật state ---
            state = update_state(state, tool_call, obs)
            tracer.end_step()
            last_obs = obs

        # --- Xây verdict ---
        if verdict_text:
            state.verdict = _parse_verdict(verdict_text, state)

        _emit_trace(investigation_id, state.steps_taken, "verdict", {
            "stop_reason": state.stop_reason,
            "root_cause": state.verdict.root_cause if state.verdict else "N/A",
            "confidence": state.verdict.confidence if state.verdict else "N/A",
        })
        tracer.record_verdict(state.stop_reason, state.verdict)
        tracer.flush()

        logger.info("[%s] Kết thúc. Stop: %s | Root cause: %s",
                    investigation_id, state.stop_reason,
                    state.verdict.root_cause if state.verdict else "N/A")
        return state
