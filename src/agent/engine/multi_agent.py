"""
MultiAgentEngine — OrchestratorAgent → 2 specialist agents (parallel) → VerdictAgent.

Architecture:
    OrchestratorAgent
    ├── LogAnalystAgent    (get_error_breakdown, trace_request)
    └── MetricAnalystAgent (get_metrics, get_recent_deploys, get_dependencies)
             ↓ asyncio.gather (parallel)
         EvidenceMerger
             ↓
         VerdictAgent (1 LLM call, all evidence → verdict)

Public interface: MultiAgentEngine.run() → InvestigationState
Ký hiệu "multi_agent": True trong trace_events để phân biệt với single-agent.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from agent.engine.loop import (
    InvestigationEngine,
    _emit_trace,
    _parse_verdict,
    SYSTEM_PROMPT,
)
from agent.engine.state import Evidence, InvestigationState, Verdict
from agent.llm.base import LLMClient, Message
from agent.observability.langfuse_tracer import LangfuseTracer
from agent.tools.contracts import Tool

logger = logging.getLogger(__name__)

# Tool sets per specialist (by name)
_LOG_TOOLS = {"get_error_breakdown", "trace_request"}
_METRIC_TOOLS = {"get_metrics", "get_recent_deploys", "get_dependencies"}

VERDICT_SYSTEM_PROMPT = """Bạn là agent tổng hợp kết quả điều tra sự cố.
Bạn nhận bằng chứng đã thu thập từ 2 specialist agents (Log Analyst + Metric Analyst).
Nhiệm vụ: tổng hợp thành verdict duy nhất, NEO vào bằng chứng thực tế.

Trả verdict bằng định dạng PLAIN TEXT:
VERDICT:
Root cause: <mô tả ngắn gọn>
Độ tin: <CAO/TRUNG BÌNH/THẤP/CHƯA ĐỦ BẰNG CHỨNG>
Bằng chứng: <tóm tắt 1-2 câu>
Lan truyền: <lỗi gốc ở đâu, lan thế nào>
Giả thuyết cạnh tranh: <đã loại trừ gì, tại sao>"""


class MultiAgentEngine:
    """
    OrchestratorAgent: chạy 2 specialist song song → merge → VerdictAgent.

    - specialist_budget: số bước tối đa mỗi specialist (mặc định = step_budget // 2)
    - Parallel: 2 specialist chạy asyncio.gather → giảm wall-clock time
    """

    def __init__(
        self,
        llm: LLMClient,
        all_tools: List[Tool],
        step_budget: int = 10,
        hypothesis_catalog=None,
    ) -> None:
        self.llm = llm
        self.all_tools = all_tools
        self.specialist_budget = max(3, step_budget // 2)
        # E6: catalog cho domain — truyền xuống từng specialist engine
        self._hypothesis_catalog = hypothesis_catalog

        self.log_tools = [t for t in all_tools if t.name in _LOG_TOOLS]
        self.metric_tools = [t for t in all_tools if t.name in _METRIC_TOOLS]

        # Fallback: nếu tool split rỗng → dùng all tools
        if not self.log_tools:
            self.log_tools = all_tools
        if not self.metric_tools:
            self.metric_tools = all_tools

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
        service: Optional[str] = None,   # E11
    ) -> InvestigationState:
        investigation_id = investigation_id or str(uuid.uuid4())[:12]

        logger.info("[%s] [multi-agent] Bắt đầu: %s", investigation_id, symptom)
        _emit_trace(investigation_id, 0, "investigation_start", {
            "symptom": symptom, "time_window": time_window, "scenario": scenario,
            "project_id": project_id, "available_services": available_services or [],
            "engine": "multi_agent",
        }, project_id=project_id)

        tracer = LangfuseTracer(
            investigation_id=investigation_id,
            symptom=symptom,
            scenario=scenario,
            project_id=project_id,
        )

        # --- Step 1: Run specialists in parallel ---
        log_id = f"{investigation_id}_log"
        metric_id = f"{investigation_id}_metric"

        _emit_trace(investigation_id, 0, "multi_agent_start", {
            "log_agent_id": log_id, "metric_agent_id": metric_id,
            "log_tools": [t.name for t in self.log_tools],
            "metric_tools": [t.name for t in self.metric_tools],
        }, project_id=project_id)

        log_state_fut = self._run_specialist(
            "LogAnalystAgent", self.log_tools, log_id,
            symptom, time_window, scenario, date, project_id,
            available_services, warm_start_hint, service,
        )
        metric_state_fut = self._run_specialist(
            "MetricAnalystAgent", self.metric_tools, metric_id,
            symptom, time_window, scenario, date, project_id,
            available_services, warm_start_hint, service,
        )

        log_state, metric_state = await asyncio.gather(log_state_fut, metric_state_fut)

        logger.info("[%s] Specialists xong — log: %d bước, metric: %d bước",
                    investigation_id, log_state.steps_taken, metric_state.steps_taken)

        # --- Step 2: Merge evidence ---
        merged = self._merge_states(
            log_state, metric_state,
            investigation_id, symptom, time_window, scenario, date,
            project_id, available_services, warm_start_hint,
        )

        _emit_trace(investigation_id, merged.steps_taken, "multi_agent_merge", {
            "total_evidence": len(merged.evidence),
            "log_steps": log_state.steps_taken,
            "metric_steps": metric_state.steps_taken,
        }, project_id=project_id)

        # --- Step 3: VerdictAgent (1 LLM call) ---
        merged = await self._synthesize_verdict(merged, investigation_id, project_id, tracer)

        # Emit final verdict trace
        _emit_trace(investigation_id, merged.steps_taken, "verdict", {
            "stop_reason": merged.stop_reason,
            "root_cause": merged.verdict.root_cause if merged.verdict else "N/A",
            "confidence": merged.verdict.confidence if merged.verdict else "N/A",
            "multi_agent": True,
            "total_tokens": merged.total_tokens,
            "cache_creation_tokens": merged.cache_creation_tokens,
            "cache_read_tokens": merged.cache_read_tokens,
        }, project_id=project_id)
        tracer.record_verdict(merged.stop_reason, merged.verdict)
        tracer.flush()

        logger.info("[%s] [multi-agent] Kết thúc. Root cause: %s | Confidence: %s",
                    investigation_id,
                    merged.verdict.root_cause if merged.verdict else "N/A",
                    merged.verdict.confidence if merged.verdict else "N/A")
        return merged

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _run_specialist(
        self,
        role: str,
        tools: List[Tool],
        sub_id: str,
        symptom: str,
        time_window: str,
        scenario: str,
        date: str,
        project_id: str,
        available_services: Optional[List[str]],
        warm_start_hint: Optional[str],
        service: Optional[str] = None,  # E11
    ) -> InvestigationState:
        """Chạy một specialist engine với tool set giới hạn."""
        logger.info("[%s] %s bắt đầu (%d tools)",
                    sub_id, role, len(tools))
        engine = InvestigationEngine(
            self.llm, tools, self.specialist_budget,
            hypothesis_catalog=self._hypothesis_catalog,
        )
        state = await engine.run(
            symptom=symptom,
            time_window=time_window,
            scenario=scenario,
            date=date,
            project_id=project_id,
            available_services=available_services,
            warm_start_hint=warm_start_hint,
            investigation_id=sub_id,
            service=service,  # E11
        )
        logger.info("[%s] %s xong: %d bằng chứng, stop=%s",
                    sub_id, role, len(state.evidence), state.stop_reason)
        return state

    def _merge_states(
        self,
        log_state: InvestigationState,
        metric_state: InvestigationState,
        investigation_id: str,
        symptom: str,
        time_window: str,
        scenario: str,
        date: str,
        project_id: str,
        available_services: Optional[List[str]],
        warm_start_hint: Optional[str],
    ) -> InvestigationState:
        """Gộp evidence từ 2 specialist vào 1 InvestigationState."""
        merged = InvestigationState(
            investigation_id=investigation_id,
            symptom=symptom,
            time_window=time_window,
            scenario=scenario,
            date=date,
            step_budget=log_state.step_budget + metric_state.step_budget,
            project_id=project_id,
            available_services=available_services or [],
            warm_start_hint=warm_start_hint,
        )

        # Gộp evidence, re-assign step numbers tuần tự
        combined: List[Evidence] = []
        seen_ids: set = set()
        for ev in log_state.evidence + metric_state.evidence:
            if ev.id not in seen_ids:
                seen_ids.add(ev.id)
                combined.append(ev)

        merged.evidence = combined
        merged.steps_taken = len(combined)

        # E7: Gộp hypotheses — dedup theo content, prefer confirmed/higher-confidence/more-evidence
        _rank = {"high": 3, "medium": 2, "low": 1}
        content_to_hyp: dict = {}
        for h in log_state.hypotheses + metric_state.hypotheses:
            existing = content_to_hyp.get(h.content)
            if existing is None:
                content_to_hyp[h.content] = h
            else:
                # Prefer confirmed over open; tiebreak: higher confidence then more evidence
                def _score(x):
                    status_rank = 2 if x.status == "confirmed" else (1 if x.status == "open" else 0)
                    return (status_rank, _rank.get(x.confidence or "", 0), len(x.evidence_ids))
                if _score(h) > _score(existing):
                    # Merge evidence_ids from both into winner
                    h.evidence_ids = list(set(existing.evidence_ids + h.evidence_ids))
                    content_to_hyp[h.content] = h
                else:
                    existing.evidence_ids = list(set(existing.evidence_ids + h.evidence_ids))
        merged.hypotheses = list(content_to_hyp.values())

        # Gộp tool call history
        merged.tool_call_history = (
            log_state.tool_call_history + metric_state.tool_call_history
        )

        # Tổng tokens + cache stats
        merged.total_tokens = log_state.total_tokens + metric_state.total_tokens
        merged.cache_creation_tokens = log_state.cache_creation_tokens + metric_state.cache_creation_tokens
        merged.cache_read_tokens = log_state.cache_read_tokens + metric_state.cache_read_tokens

        return merged

    async def _synthesize_verdict(
        self,
        merged: InvestigationState,
        investigation_id: str,
        project_id: str,
        tracer: LangfuseTracer,
    ) -> InvestigationState:
        """VerdictAgent: 1 LLM call tổng hợp tất cả evidence → verdict."""
        import time

        # Build evidence summary
        evidence_lines = []
        for ev in merged.evidence:
            evidence_lines.append(f"[{ev.tool_name}] {ev.summary}")

        evidence_block = "\n".join(evidence_lines) if evidence_lines else "(Không có bằng chứng)"

        user_msg = (
            f"# Tổng hợp điều tra sự cố: {merged.symptom}\n"
            f"Cửa sổ thời gian: {merged.time_window} | Kịch bản: {merged.scenario}\n\n"
            f"## Bằng chứng từ LogAnalystAgent + MetricAnalystAgent (chạy song song):\n"
            f"{evidence_block}\n\n"
            "Dựa trên toàn bộ bằng chứng, hãy đưa ra VERDICT cuối cùng."
        )

        tracer.start_step(merged.steps_taken)

        try:
            import time as _time
            t0 = _time.monotonic()
            response = await self.llm.complete(
                messages=[Message(role="user", content=user_msg)],
                tools=[],   # VerdictAgent không được gọi tool — chỉ verdict
                system=VERDICT_SYSTEM_PROMPT,
            )
            llm_ms = (_time.monotonic() - t0) * 1000

            verdict_text = response.text or ""
            if response.has_tool_calls or "VERDICT" not in verdict_text.upper():
                verdict_text = (
                    "VERDICT:\nRoot cause: Không tổng hợp được.\n"
                    "Độ tin: CHƯA ĐỦ BẰNG CHỨNG\n"
                    f"Bằng chứng: {evidence_block[:200]}\n"
                    "Lan truyền: Không rõ\nGiả thuyết cạnh tranh: N/A"
                )

            if response.usage:
                merged.total_tokens += (
                    response.usage.get("input_tokens", 0)
                    + response.usage.get("output_tokens", 0)
                )
                merged.cache_creation_tokens += response.usage.get("cache_creation_input_tokens", 0)
                merged.cache_read_tokens += response.usage.get("cache_read_input_tokens", 0)

            tracer.record_llm_call(
                input_summary=merged.symptom[:200],
                output_summary="verdict_synthesis",
                usage=response.usage,
                latency_ms=llm_ms,
            )

        except Exception as e:
            logger.error("[%s] VerdictAgent LLM error: %s", investigation_id, e)
            verdict_text = (
                f"VERDICT:\nRoot cause: VerdictAgent lỗi — {e}\n"
                "Độ tin: CHƯA ĐỦ BẰNG CHỨNG\n"
                "Bằng chứng: N/A\nLan truyền: N/A\nGiả thuyết cạnh tranh: N/A"
            )

        tracer.end_step()

        merged.verdict = _parse_verdict(verdict_text, merged)
        # E2: kiểm evidence grounding cho multi-agent verdict
        from agent.engine.loop import _check_evidence_grounding
        merged.verdict = _check_evidence_grounding(merged.verdict, merged.evidence)
        # E8: Calibration
        from agent.engine.calibration import apply_calibration
        merged.verdict = apply_calibration(merged.verdict)
        # E12: specificity — multi-agent không loop được → downgrade trực tiếp nếu mờ
        from agent.engine.specificity import SPECIFICITY_THRESHOLD, compute_verdict_specificity
        spec_score, spec_reasons = compute_verdict_specificity(merged.verdict, merged)
        merged.verdict.specificity_score = spec_score
        if spec_score < SPECIFICITY_THRESHOLD and merged.verdict.confidence in ("high", "medium"):
            _dg = {"high": "medium", "medium": "low"}
            orig_conf = merged.verdict.confidence
            merged.verdict.confidence = _dg.get(orig_conf, orig_conf)
            warn = f" [⚠ E12 specificity={spec_score:.2f} — {'; '.join(spec_reasons[:2])}]"
            merged.verdict.evidence_summary = (merged.verdict.evidence_summary or "") + warn
            logger.info(
                "[%s] E12 multi-agent specificity downgrade: score=%.2f → %s→%s",
                investigation_id, spec_score, orig_conf, merged.verdict.confidence,
            )

        # E7: conflict resolution — ngang hàng single-agent path
        winner = merged.resolve_conflicting_hypotheses()
        n_confirmed = sum(1 for h in merged.hypotheses if h.status == "confirmed")
        if winner and n_confirmed > 1:
            conflict_note = (
                f" [Conflict resolved: {n_confirmed} confirmed; winner={winner.id}"
                f" conf={winner.confidence} ev={len(winner.evidence_ids)}]"
            )
            merged.verdict.competing_hypotheses = (
                (merged.verdict.competing_hypotheses or "") + conflict_note
            )
            logger.info(
                "[%s] Multi-agent conflict resolution: %d confirmed → winner=%s (%s)",
                investigation_id, n_confirmed, winner.id, winner.confidence,
            )

        merged.stop_reason = "verdict"
        merged.finished = True

        return merged
