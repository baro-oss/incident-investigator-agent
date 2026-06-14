"""
Langfuse tracer (v3 API) — emit spans song song với SQLite trace, không thay thế.

Opt-in: chỉ hoạt động khi LANGFUSE_PUBLIC_KEY được set.
Mọi method đều catch exception — không bao giờ làm vỡ investigation.

Span hierarchy (Langfuse v3):
  root_span (investigation)          ← lf.start_span()
    └── step_span (step_N)           ← root_span.start_span()
          ├── generation (llm)       ← step_span.start_generation()
          └── span (tool_call)       ← step_span.start_span()
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LangfuseTracer:
    """Stateful tracer cho một investigation. Thread-safe đủ dùng với asyncio."""

    def __init__(
        self,
        investigation_id: str,
        symptom: str,
        scenario: str,
        project_id: str,
        model: str = "",
    ) -> None:
        self._enabled = False
        self._lf = None
        self._root_span = None
        self._step_span = None
        self._model = model or os.getenv("LLM_MODEL", "unknown")

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        if not public_key:
            return  # silent no-op

        try:
            from langfuse import Langfuse
            self._lf = Langfuse(
                public_key=public_key,
                secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
            self._root_span = self._lf.start_span(
                name="investigation",
                input={"symptom": symptom, "scenario": scenario},
                metadata={"project_id": project_id, "investigation_id": investigation_id},
            )
            self._enabled = True
            logger.info(
                "Langfuse trace started: inv=%s trace_id=%s",
                investigation_id, self._root_span.trace_id,
            )
        except Exception as exc:
            logger.warning("Langfuse init thất bại (bỏ qua): %s", exc)

    # ── Step lifecycle ────────────────────────────────────────────────────────

    def start_step(self, step: int) -> None:
        if not self._enabled or self._root_span is None:
            return
        try:
            self._step_span = self._root_span.start_span(
                name=f"step_{step}",
                input={"step": step},
            )
        except Exception as exc:
            logger.debug("Langfuse start_step: %s", exc)

    def end_step(self) -> None:
        if not self._enabled or self._step_span is None:
            return
        try:
            self._step_span.end()
            self._step_span = None
        except Exception as exc:
            logger.debug("Langfuse end_step: %s", exc)

    # ── LLM call ─────────────────────────────────────────────────────────────

    def record_llm_call(
        self,
        input_summary: str,
        output_summary: str,
        usage: Optional[Dict[str, int]] = None,
        latency_ms: float = 0.0,
    ) -> None:
        if not self._enabled or self._step_span is None:
            return
        try:
            usage_details = (
                {"input": usage.get("input_tokens", 0),
                 "output": usage.get("output_tokens", 0)}
                if usage else {}
            )
            gen = self._step_span.start_generation(
                name="llm_decision",
                model=self._model,
                input=[{"role": "user", "content": input_summary[:500]}],
                output=output_summary[:300],
                usage_details=usage_details,
                metadata={"latency_ms": round(latency_ms)},
            )
            gen.end()
        except Exception as exc:
            logger.debug("Langfuse record_llm_call: %s", exc)

    # ── Tool call ─────────────────────────────────────────────────────────────

    def record_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result_summary: str,
        latency_ms: float = 0.0,
    ) -> None:
        if not self._enabled or self._step_span is None:
            return
        try:
            span = self._step_span.start_span(
                name="tool_call",
                input={"tool": tool_name, "args": args},
                output={"summary": result_summary[:300]},
                metadata={"latency_ms": round(latency_ms)},
            )
            span.end()
        except Exception as exc:
            logger.debug("Langfuse record_tool_call: %s", exc)

    # ── Verdict ───────────────────────────────────────────────────────────────

    def record_verdict(self, stop_reason: str, verdict: Any) -> None:
        if not self._enabled or self._root_span is None:
            return
        try:
            output: Dict[str, Any] = {"stop_reason": stop_reason}
            if verdict:
                output["root_cause"] = verdict.root_cause
                output["confidence"] = verdict.confidence

            self._root_span.update(output=output)

            if verdict:
                _CONF_SCORE = {"high": 1.0, "medium": 0.6, "low": 0.3, "insufficient": 0.0}
                self._root_span.score_trace(
                    name="confidence",
                    value=_CONF_SCORE.get(verdict.confidence, 0.0),
                    comment=verdict.root_cause[:100],
                )

            self._root_span.end()
        except Exception as exc:
            logger.debug("Langfuse record_verdict: %s", exc)

    # ── Flush ─────────────────────────────────────────────────────────────────

    def flush(self) -> None:
        if not self._enabled or self._lf is None:
            return
        try:
            self._lf.flush()
        except Exception as exc:
            logger.debug("Langfuse flush: %s", exc)
