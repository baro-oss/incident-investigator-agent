"""
LangGraph StateGraph — wrap 3 hàm pure thành nodes.

Engine interface vẫn là InvestigationEngine.run(); bên trong dùng graph này.
Nodes: decide → run_tool → update → (loop) → decide → ... → END

Lazy import các pure functions từ loop.py để tránh circular import.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore


# ---------------------------------------------------------------------------
# Graph state schema
# ---------------------------------------------------------------------------

class LoopState(TypedDict, total=False):
    """Trạng thái chuyển giữa các nodes trong investigation loop."""
    inv: Any                     # InvestigationState
    last_obs: Optional[Any]      # Observation
    tool_call: Optional[Any]     # ToolCall | None
    verdict_text: Optional[str]
    verdict_obj: Optional[Any]   # E9: Verdict trực tiếp từ structured path
    llm: Any                     # LLMClient
    tools: List[Any]             # List[Tool]
    tracer: Any                  # LangfuseTracer


# ---------------------------------------------------------------------------
# Nodes — mỗi node wrap đúng 1 hàm pure (hoặc routing logic)
# ---------------------------------------------------------------------------

async def decide_node(state: LoopState) -> Dict[str, Any]:
    """Decide node: check stop conditions → call decide_next_action."""
    from agent.engine.loop import decide_next_action, _emit_trace, _check_stop_conditions

    inv = state["inv"]
    llm = state["llm"]
    tools = state["tools"]
    tracer = state["tracer"]
    last_obs = state.get("last_obs")

    investigation_id = inv.investigation_id
    current_step = inv.steps_taken

    # --- E7: Stop conditions — dùng chung với while-loop path ---
    stop_vtext = _check_stop_conditions(inv)
    if stop_vtext:
        return {"inv": inv, "verdict_text": stop_vtext, "tool_call": None, "verdict_obj": None}

    tracer.start_step(current_step)

    # --- Call pure function: retry + circuit breaker ---
    from agent.engine.resilience import with_retry, llm_circuit_breaker

    try:
        t_llm = time.monotonic()
        tool_call, vtext, llm_resp, v_obj = await llm_circuit_breaker.call(
            lambda: with_retry(lambda: decide_next_action(inv, llm, tools, last_obs))
        )
        llm_ms = (time.monotonic() - t_llm) * 1000
    except Exception as e:
        logger.error("[%s] LLM error tại bước %d: %s", investigation_id, current_step, e)
        tracer.end_step()
        inv.stop_reason = "llm_error"
        inv.finished = True
        return {
            "inv": inv,
            "verdict_text": (
                f"VERDICT:\nRoot cause: LLM lỗi — {e}\n"
                "Độ tin: CHƯA ĐỦ BẰNG CHỨNG\n"
                "Bằng chứng: N/A\nLan truyền: N/A\nGiả thuyết cạnh tranh: N/A"
            ),
            "tool_call": None,
            "verdict_obj": None,
        }

    if llm_resp and llm_resp.usage:
        inv.total_tokens += (
            llm_resp.usage.get("input_tokens", 0)
            + llm_resp.usage.get("output_tokens", 0)
        )

    output_desc = (
        f"tool:{tool_call.name}" if tool_call
        else ("verdict_structured" if v_obj is not None else ("verdict" if vtext else "no_action"))
    )
    tracer.record_llm_call(
        input_summary=inv.symptom[:200],
        output_summary=output_desc,
        usage=llm_resp.usage if llm_resp else None,
        latency_ms=llm_ms,
    )

    from agent.engine.loop import (
        _apply_competing_gate, _apply_specificity_gate, _emit_trace,
    )

    if v_obj is not None:
        # E9: structured path — cổng cạnh tranh rồi cổng specificity
        nudge_tc, _ = _apply_competing_gate(inv, conf_override=v_obj.confidence)
        if nudge_tc:
            _emit_trace(investigation_id, current_step, "tool_call", {
                "tool": nudge_tc.name, "args": nudge_tc.arguments,
            }, project_id=inv.project_id)
            return {"inv": inv, "tool_call": nudge_tc, "verdict_text": None, "verdict_obj": None}
        # E12: specificity gate
        spec_tc = _apply_specificity_gate(inv, verdict_obj=v_obj)
        if spec_tc:
            _emit_trace(investigation_id, current_step, "tool_call", {
                "tool": spec_tc.name, "args": spec_tc.arguments,
            }, project_id=inv.project_id)
            return {"inv": inv, "tool_call": spec_tc, "verdict_text": None, "verdict_obj": None}
        inv.stop_reason = "verdict"
        inv.finished = True
        tracer.end_step()
        return {"inv": inv, "verdict_text": None, "tool_call": None, "verdict_obj": v_obj}

    if vtext:
        # E4: cổng cạnh tranh — chặn verdict high/medium nếu còn hypothesis open
        nudge_tc, accepted_vtext = _apply_competing_gate(inv, vtext)
        if nudge_tc:
            _emit_trace(investigation_id, current_step, "tool_call", {
                "tool": nudge_tc.name, "args": nudge_tc.arguments,
            }, project_id=inv.project_id)
            return {"inv": inv, "tool_call": nudge_tc, "verdict_text": None, "verdict_obj": None}
        # E12: specificity gate
        spec_tc = _apply_specificity_gate(inv, accepted_vtext)
        if spec_tc:
            _emit_trace(investigation_id, current_step, "tool_call", {
                "tool": spec_tc.name, "args": spec_tc.arguments,
            }, project_id=inv.project_id)
            return {"inv": inv, "tool_call": spec_tc, "verdict_text": None, "verdict_obj": None}
        inv.stop_reason = "verdict"
        inv.finished = True
        tracer.end_step()
        return {"inv": inv, "verdict_text": accepted_vtext, "tool_call": None, "verdict_obj": None}

    if tool_call:
        _emit_trace(investigation_id, current_step, "tool_call", {
            "tool": tool_call.name, "args": tool_call.arguments,
        }, project_id=inv.project_id)
        logger.info("[%s] Bước %d → %s(%s)",
                    investigation_id, current_step + 1,
                    tool_call.name, tool_call.arguments)
        return {"inv": inv, "tool_call": tool_call, "verdict_text": None, "verdict_obj": None}

    # Không có tool_call lẫn verdict — dừng an toàn
    logger.warning("[%s] Không có tool_call lẫn verdict", investigation_id)
    tracer.end_step()
    inv.finished = True
    return {"inv": inv, "tool_call": None, "verdict_text": None, "verdict_obj": None}


async def run_tool_node(state: LoopState) -> Dict[str, Any]:
    """Run tool node: thực thi tool_call → Observation."""
    from agent.engine.loop import run_tool as run_tool_fn, _emit_trace

    tool_call = state["tool_call"]
    tools = state["tools"]
    inv = state["inv"]
    tracer = state["tracer"]

    t_tool = time.monotonic()
    try:
        obs = await run_tool_fn(tool_call, tools)
    except Exception as e:
        from agent.tools.contracts import Observation as Obs
        obs = Obs(
            summary=f"Tool {tool_call.name} lỗi: {e}",
            aggregates={}, samples=[], total_count=0, truncated=False,
            metadata={"tool_name": tool_call.name, "error": str(e)},
        )
    tool_ms = (time.monotonic() - t_tool) * 1000

    _emit_trace(inv.investigation_id, inv.steps_taken, "tool_result", {
        "tool": tool_call.name, "summary": obs.summary,
    }, project_id=inv.project_id)
    tracer.record_tool_call(tool_call.name, tool_call.arguments, obs.summary, tool_ms)

    return {"last_obs": obs}


def update_node(state: LoopState) -> Dict[str, Any]:
    """Update node: cập nhật InvestigationState với Observation vừa nhận."""
    from agent.engine.loop import update_state

    inv = state["inv"]
    tool_call = state["tool_call"]
    last_obs = state["last_obs"]
    tracer = state["tracer"]

    updated = update_state(inv, tool_call, last_obs)
    tracer.end_step()

    return {"inv": updated}


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def _route_after_decide(state: LoopState) -> str:
    from langgraph.graph import END
    inv = state["inv"]
    if inv.finished or state.get("verdict_text") is not None or state.get("verdict_obj") is not None:
        return END
    if state.get("tool_call") is not None:
        return "run_tool"
    return END


def _route_after_update(state: LoopState) -> str:
    from langgraph.graph import END
    if state["inv"].finished:
        return END
    return "decide"


# ---------------------------------------------------------------------------
# Graph builder + module-level cache
# ---------------------------------------------------------------------------

_COMPILED_GRAPH = None


def get_compiled_graph():
    """Trả về compiled graph (lazy-init, singleton)."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = _build_graph()
        logger.info("LangGraph investigation graph compiled")
    return _COMPILED_GRAPH


def _build_graph():
    from langgraph.graph import StateGraph, START, END

    g = StateGraph(LoopState)

    g.add_node("decide", decide_node)
    g.add_node("run_tool", run_tool_node)
    g.add_node("update", update_node)

    g.add_edge(START, "decide")

    g.add_conditional_edges("decide", _route_after_decide, {
        "run_tool": "run_tool",
        END: END,
    })
    g.add_edge("run_tool", "update")
    g.add_conditional_edges("update", _route_after_update, {
        "decide": "decide",
        END: END,
    })

    return g.compile()
