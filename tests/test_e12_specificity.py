"""
Tests cho E12 — Verdict specificity gate (Ngày 48).

Kiểm:
- compute_verdict_specificity tính đúng 3 tín hiệu
- _has_specific_token / _count_distinct_numbers helper chính xác
- _apply_specificity_gate fire khi mờ, pass khi cụ thể
- Gate idempotent (1 lần), budget-guard, chỉ high/medium conf
- run_tool xử lý _SPECIFICITY_GATE_NAME đúng cách
- Parity: cùng state → cùng score (deterministic)
- Wiring trong _run_loop: vague verdict → gate fires → tiếp tục điều tra
"""
from __future__ import annotations

import pytest

from agent.engine.specificity import (
    SPECIFICITY_THRESHOLD,
    _count_distinct_numbers,
    _has_specific_token,
    compute_verdict_specificity,
)
from agent.engine.state import InvestigationState, Verdict


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_state(services=None) -> InvestigationState:
    state = InvestigationState(
        investigation_id="test-e12",
        symptom="payment-gateway: error",
        time_window="14:00-15:00",
        scenario="test",
        date="2024-01-15",
    )
    state.available_services = services or []
    return state


def _make_verdict(root_cause="", evidence_summary="", propagation_note="",
                  confidence="high") -> Verdict:
    return Verdict(
        root_cause=root_cause,
        confidence=confidence,
        evidence_summary=evidence_summary,
        propagation_note=propagation_note,
        competing_hypotheses="",
        raw_text="",
    )


def _specific_verdict() -> Verdict:
    return _make_verdict(
        root_cause="Deploy v2.3.1 lúc 14:03 gây TimeoutException",
        evidence_summary="87% timeout sau deploy; latency 8.4x baseline",
        propagation_note="Lỗi phát sinh tại payment-gateway từ 14:05",
    )


def _vague_verdict() -> Verdict:
    return _make_verdict(
        root_cause="Hệ thống gặp sự cố",
        evidence_summary="Có lỗi xảy ra",
        propagation_note="",
    )


# ── _has_specific_token ───────────────────────────────────────────────────────

class TestHasSpecificToken:
    def test_digit_in_text_passes(self):
        assert _has_specific_token("Deploy v2.3.1 gây lỗi", [])

    def test_timestamp_passes(self):
        assert _has_specific_token("Lỗi từ 14:03", [])

    def test_percent_value_passes(self):
        assert _has_specific_token("87% timeout", [])

    def test_no_digit_no_service_fails(self):
        assert not _has_specific_token("Hệ thống gặp sự cố", [])

    def test_service_name_match_no_digit(self):
        assert _has_specific_token("Lỗi tại payment-gateway", ["payment-gateway"])

    def test_service_name_case_insensitive(self):
        assert _has_specific_token("PAYMENT-GATEWAY lỗi", ["payment-gateway"])

    def test_no_service_match_fails(self):
        assert not _has_specific_token("Lỗi tại unknown-svc", ["payment-gateway"])

    def test_empty_text_fails(self):
        assert not _has_specific_token("", [])


# ── _count_distinct_numbers ───────────────────────────────────────────────────

class TestCountDistinctNumbers:
    def test_no_numbers(self):
        assert _count_distinct_numbers("không có số nào") == 0

    def test_single_number(self):
        assert _count_distinct_numbers("82% lỗi") == 1

    def test_two_distinct_numbers(self):
        assert _count_distinct_numbers("87% timeout; 8 lần retry") == 2

    def test_duplicate_numbers_counted_once(self):
        assert _count_distinct_numbers("5x; 5x baseline") == 1

    def test_many_distinct_numbers(self):
        assert _count_distinct_numbers("200→1000/phút (5x); 62% lỗi; 171x baseline") >= 4

    def test_decimal_number(self):
        assert _count_distinct_numbers("8.4x baseline") == 1

    def test_threshold_returns_correct_value(self):
        assert SPECIFICITY_THRESHOLD == 0.40


# ── compute_verdict_specificity ───────────────────────────────────────────────

class TestComputeVerdictSpecificity:
    def test_all_signals_pass(self):
        v = _specific_verdict()
        state = _make_state()
        score, reasons = compute_verdict_specificity(v, state)
        assert score == pytest.approx(1.0)
        assert reasons == []

    def test_all_signals_fail_vague(self):
        v = _vague_verdict()
        state = _make_state()
        score, reasons = compute_verdict_specificity(v, state)
        assert score == pytest.approx(0.0)
        assert len(reasons) == 3

    def test_signal_a_only_root_cause_number(self):
        v = _make_verdict(
            root_cause="Lỗi từ 14:03",
            evidence_summary="không có số",
            propagation_note="",
        )
        score, reasons = compute_verdict_specificity(v, _make_state())
        assert score == pytest.approx(1 / 3)
        assert len(reasons) == 2

    def test_signal_b_two_numbers_in_evidence(self):
        v = _make_verdict(
            root_cause="Lỗi hệ thống",
            evidence_summary="87% lỗi; 5x baseline",
            propagation_note="",
        )
        score, reasons = compute_verdict_specificity(v, _make_state())
        assert score == pytest.approx(1 / 3)

    def test_signal_c_propagation_with_number(self):
        v = _make_verdict(
            root_cause="Lỗi hệ thống",
            evidence_summary="không có số",
            propagation_note="Lỗi từ svc-a lúc 14:05",
        )
        score, reasons = compute_verdict_specificity(v, _make_state())
        assert score == pytest.approx(1 / 3)

    def test_two_signals_pass(self):
        v = _make_verdict(
            root_cause="Deploy v2.3.1 gây lỗi",
            evidence_summary="87% timeout; 8x baseline",
            propagation_note="",
        )
        score, reasons = compute_verdict_specificity(v, _make_state())
        assert score == pytest.approx(2 / 3)
        assert len(reasons) == 1

    def test_service_name_in_propagation_with_services(self):
        v = _make_verdict(
            root_cause="Lỗi hệ thống",
            evidence_summary="không có số",
            propagation_note="Lỗi phát sinh tại payment-gateway",
        )
        state = _make_state(services=["payment-gateway"])
        score, reasons = compute_verdict_specificity(v, state)
        # signal (c) passes via service name match
        assert score == pytest.approx(1 / 3)
        assert "propagation_note" not in " ".join(reasons)

    def test_deterministic_same_input(self):
        v = _specific_verdict()
        state = _make_state()
        score1, _ = compute_verdict_specificity(v, state)
        score2, _ = compute_verdict_specificity(v, state)
        assert score1 == score2

    def test_threshold_boundary(self):
        """2/3 tín hiệu = 0.67 > 0.40 → pass."""
        v = _make_verdict(
            root_cause="Deploy v2.3.1",
            evidence_summary="87% lỗi; 5x baseline",
            propagation_note="",
        )
        score, _ = compute_verdict_specificity(v, _make_state())
        assert score >= SPECIFICITY_THRESHOLD


# ── _apply_specificity_gate ───────────────────────────────────────────────────

class TestApplySpecificityGate:
    def test_gate_fires_on_vague_high_conf(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        v = _vague_verdict()
        tc = _apply_specificity_gate(state, verdict_obj=v)
        assert tc is not None
        assert tc.name == "_specificity_gate"
        assert state._specificity_gate_fired is True

    def test_gate_passes_on_specific_verdict(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        v = _specific_verdict()
        tc = _apply_specificity_gate(state, verdict_obj=v)
        assert tc is None
        assert state._specificity_gate_fired is False

    def test_gate_idempotent_second_call_returns_none(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        v = _vague_verdict()
        tc1 = _apply_specificity_gate(state, verdict_obj=v)
        assert tc1 is not None
        tc2 = _apply_specificity_gate(state, verdict_obj=v)
        assert tc2 is None

    def test_gate_no_fire_for_low_confidence(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        v = _vague_verdict()
        v.confidence = "low"
        tc = _apply_specificity_gate(state, verdict_obj=v)
        assert tc is None

    def test_gate_no_fire_for_insufficient_confidence(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        v = _vague_verdict()
        v.confidence = "insufficient"
        tc = _apply_specificity_gate(state, verdict_obj=v)
        assert tc is None

    def test_gate_budget_guard_no_fire_when_budget_le_1(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        state.step_budget = 3
        state.steps_taken = 2  # remaining = 1 → budget_guard
        v = _vague_verdict()
        tc = _apply_specificity_gate(state, verdict_obj=v)
        assert tc is None

    def test_gate_fires_from_vtext_path(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        vtext = (
            "VERDICT:\nRoot cause: Hệ thống lỗi\n"
            "Độ tin: CAO\nBằng chứng: không rõ\n"
            "Lan truyền: \nGiả thuyết cạnh tranh: N/A"
        )
        tc = _apply_specificity_gate(state, vtext)
        assert tc is not None
        assert tc.name == "_specificity_gate"

    def test_gate_passes_for_medium_conf_specific(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        v = _specific_verdict()
        v.confidence = "medium"
        tc = _apply_specificity_gate(state, verdict_obj=v)
        assert tc is None

    def test_gate_arguments_contain_score_and_reasons(self):
        from agent.engine.loop import _apply_specificity_gate

        state = _make_state()
        v = _vague_verdict()
        tc = _apply_specificity_gate(state, verdict_obj=v)
        assert tc is not None
        assert "score" in tc.arguments
        assert "reasons" in tc.arguments
        assert tc.arguments["score"] == pytest.approx(0.0, abs=0.01)


# ── run_tool handles _SPECIFICITY_GATE_NAME ───────────────────────────────────

class TestRunToolSpecificityGate:
    async def test_run_tool_returns_observation_for_specificity_gate(self):
        from agent.engine.loop import run_tool
        from agent.llm.base import ToolCall

        tc = ToolCall(
            id="spec_nudge",
            name="_specificity_gate",
            arguments={"score": 0.0, "reasons": ["root_cause thiếu số", "evidence_summary thiếu số"]},
        )
        obs = await run_tool(tc, [])
        assert obs is not None
        assert "specificity" in obs.summary.lower() or "mờ" in obs.summary
        assert obs.aggregates.get("gate") == "specificity"

    async def test_specificity_gate_observation_has_score(self):
        from agent.engine.loop import run_tool
        from agent.llm.base import ToolCall

        tc = ToolCall(
            id="spec_nudge",
            name="_specificity_gate",
            arguments={"score": 0.33, "reasons": ["thiếu số"]},
        )
        obs = await run_tool(tc, [])
        assert obs.aggregates.get("score") == pytest.approx(0.33, abs=0.01)


# ── Wiring trong _run_loop ────────────────────────────────────────────────────

class TestSpecificityGateWiringInLoop:
    """Kiểm gate được kích hoạt trong _run_loop khi verdict mờ."""

    async def test_vague_verdict_triggers_gate_then_continues(self):
        """MockLLM: lượt 1 trả verdict mờ (high conf) → gate fires → lượt 2 trả verdict cụ thể → pass."""
        from unittest.mock import AsyncMock, MagicMock

        from agent.engine.loop import InvestigationEngine
        from agent.llm.base import LLMResponse, ToolCall
        from agent.tools.contracts import Observation, Tool

        call_count = [0]

        async def mock_complete(messages, tools, *, system=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # Lượt 1: verdict mờ — score sẽ = 0/3 → gate fires
                return LLMResponse(
                    tool_calls=[ToolCall(
                        id="v1",
                        name="submit_verdict",
                        arguments={
                            "root_cause": "Hệ thống lỗi",
                            "confidence": "high",
                            "evidence_summary": "không rõ",
                            "propagation": "",
                            "competing_hypotheses": "N/A",
                        },
                    )],
                    usage={"input_tokens": 10, "output_tokens": 10},
                )
            # Lượt 2+: verdict cụ thể — score ≥ 2/3 → gate passes
            return LLMResponse(
                tool_calls=[ToolCall(
                    id="v2",
                    name="submit_verdict",
                    arguments={
                        "root_cause": "Deploy v2.3.1 lúc 14:03 gây lỗi",
                        "confidence": "high",
                        "evidence_summary": "87% lỗi; latency 8x baseline",
                        "propagation": "Lỗi phát sinh tại payment-gateway từ 14:05",
                        "competing_hypotheses": "N/A",
                    },
                )],
                usage={"input_tokens": 10, "output_tokens": 10},
            )

        mock_llm = MagicMock()
        mock_llm.complete = mock_complete
        mock_llm.model_id = "mock"

        dummy_tool = Tool(
            name="get_metrics",
            description="metrics",
            input_schema={"type": "object", "properties": {}},
            run=AsyncMock(return_value=Observation(
                summary="metrics bình thường", aggregates={}, samples=[],
                total_count=0, truncated=False, metadata={},
            )),
        )

        from unittest.mock import patch
        with patch("agent.storage.db.open_db") as mock_db:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
            mock_db.return_value = mock_conn

            engine = InvestigationEngine(llm=mock_llm, tools=[dummy_tool], step_budget=5)
            state = await engine.run(
                symptom="payment-gateway: high error rate",
                time_window="14:00-15:00",
                scenario="test",
            )

        assert state.verdict is not None
        # Gate phải đã fired trong quá trình (tránh loop vô hạn)
        assert state._specificity_gate_fired is True
        # Verdict cuối phải là verdict cụ thể (lần 2)
        assert "v2.3.1" in state.verdict.root_cause or "Deploy" in state.verdict.root_cause
        # specificity_score phải được set khi finalize
        assert state.verdict.specificity_score is not None
        assert state.verdict.specificity_score > SPECIFICITY_THRESHOLD

    async def test_specific_verdict_no_gate_fires(self):
        """MockLLM trả verdict cụ thể ngay lần đầu → gate không fire."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from agent.engine.loop import InvestigationEngine
        from agent.llm.base import LLMResponse, ToolCall
        from agent.tools.contracts import Observation, Tool

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            tool_calls=[ToolCall(
                id="v1",
                name="submit_verdict",
                arguments={
                    "root_cause": "Deploy v2.3.1 lúc 14:03 gây lỗi",
                    "confidence": "high",
                    "evidence_summary": "87% lỗi; latency 8x baseline",
                    "propagation": "Lỗi phát sinh tại svc từ 14:05",
                    "competing_hypotheses": "N/A",
                },
            )],
            usage={"input_tokens": 10, "output_tokens": 10},
        ))
        mock_llm.model_id = "mock"

        dummy_tool = Tool(
            name="get_metrics",
            description="metrics",
            input_schema={"type": "object", "properties": {}},
            run=AsyncMock(return_value=Observation(
                summary="metrics bình thường", aggregates={}, samples=[],
                total_count=0, truncated=False, metadata={},
            )),
        )

        with patch("agent.storage.db.open_db") as mock_db:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
            mock_db.return_value = mock_conn

            engine = InvestigationEngine(llm=mock_llm, tools=[dummy_tool], step_budget=5)
            state = await engine.run(
                symptom="payment-gateway: high error rate",
                time_window="14:00-15:00",
                scenario="test",
            )

        assert state.verdict is not None
        assert state._specificity_gate_fired is False  # không fire vì verdict đã cụ thể
        assert state.verdict.specificity_score is not None
        assert state.verdict.specificity_score > SPECIFICITY_THRESHOLD


# ── specificity_score được set khi finalize ───────────────────────────────────

# ── Multi-agent downgrade ─────────────────────────────────────────────────────

class TestMultiAgentSpecificityDowngrade:
    """E12 Ngày 49: _synthesize_verdict downgrade khi verdict mờ."""

    async def test_vague_verdict_downgraded_in_synthesize(self):
        """MockLLM trả verdict mờ (0 specific signals) → confidence bị hạ."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from agent.engine.multi_agent import MultiAgentEngine
        from agent.llm.base import LLMResponse
        from agent.tools.contracts import Observation, Tool

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            text=(
                "VERDICT:\nRoot cause: Hệ thống gặp sự cố\n"
                "Độ tin: CAO\nBằng chứng: không rõ\n"
                "Lan truyền: \nGiả thuyết cạnh tranh: N/A"
            ),
            usage={"input_tokens": 5, "output_tokens": 5},
        ))
        mock_llm.model_id = "mock"

        dummy_tool = Tool(
            name="get_metrics", description="m",
            input_schema={"type": "object", "properties": {}},
            run=AsyncMock(return_value=Observation(
                summary="metrics bình thường", aggregates={}, samples=[],
                total_count=0, truncated=False, metadata={},
            )),
        )

        with patch("agent.storage.db.open_db") as mock_db:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
            mock_db.return_value = mock_conn

            engine = MultiAgentEngine(llm=mock_llm, all_tools=[dummy_tool], step_budget=3)
            state = await engine.run(
                symptom="payment-gateway: error",
                time_window="14:00-15:00",
                scenario="test",
            )

        assert state.verdict is not None
        assert state.verdict.specificity_score is not None
        assert state.verdict.specificity_score < SPECIFICITY_THRESHOLD
        # confidence phải bị hạ từ high → medium (hoặc thấp hơn)
        assert state.verdict.confidence in ("medium", "low", "insufficient")
        # evidence_summary phải có annotation E12
        assert "E12 specificity" in (state.verdict.evidence_summary or "")

    async def test_specific_verdict_not_downgraded(self):
        """MockLLM trả verdict cụ thể → confidence giữ nguyên, không annotate E12."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from agent.engine.multi_agent import MultiAgentEngine
        from agent.llm.base import LLMResponse
        from agent.tools.contracts import Observation, Tool

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            text=(
                "VERDICT:\nRoot cause: Deploy v2.3.1 lúc 14:03 gây lỗi\n"
                "Độ tin: CAO\nBằng chứng: 87% lỗi; latency 8x baseline\n"
                "Lan truyền: Lỗi từ svc-a lúc 14:05\nGiả thuyết cạnh tranh: N/A"
            ),
            usage={"input_tokens": 5, "output_tokens": 5},
        ))
        mock_llm.model_id = "mock"

        dummy_tool = Tool(
            name="get_metrics", description="m",
            input_schema={"type": "object", "properties": {}},
            run=AsyncMock(return_value=Observation(
                summary="ok", aggregates={}, samples=[],
                total_count=0, truncated=False, metadata={},
            )),
        )

        with patch("agent.storage.db.open_db") as mock_db:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
            mock_db.return_value = mock_conn

            engine = MultiAgentEngine(llm=mock_llm, all_tools=[dummy_tool], step_budget=3)
            state = await engine.run(
                symptom="payment-gateway: error",
                time_window="14:00-15:00",
                scenario="test",
            )

        assert state.verdict is not None
        assert state.verdict.specificity_score is not None
        assert state.verdict.specificity_score >= SPECIFICITY_THRESHOLD
        assert "E12 specificity" not in (state.verdict.evidence_summary or "")

    def test_specificity_score_set_on_all_verdicts(self):
        """compute_verdict_specificity có thể nhận mọi loại Verdict mà không throw."""
        from agent.engine.state import InvestigationState
        verdicts = [
            _vague_verdict(),
            _specific_verdict(),
            _make_verdict(root_cause="", evidence_summary="", propagation_note=""),
        ]
        state = _make_state()
        for v in verdicts:
            score, reasons = compute_verdict_specificity(v, state)
            assert 0.0 <= score <= 1.0


# ── specificity_score được set khi finalize ───────────────────────────────────

class TestSpecificityScoreInFinalize:
    async def test_verdict_has_specificity_score_after_run(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from agent.engine.loop import InvestigationEngine
        from agent.llm.base import LLMResponse, ToolCall
        from agent.tools.contracts import Observation, Tool

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            tool_calls=[ToolCall(
                id="c1",
                name="submit_verdict",
                arguments={
                    "root_cause": "Deploy v2.3.1 lúc 14:03",
                    "confidence": "medium",
                    "evidence_summary": "87% lỗi; latency 8x baseline",
                    "propagation": "Lỗi từ svc-a lúc 14:05",
                    "competing_hypotheses": "N/A",
                },
            )],
            usage={"input_tokens": 10, "output_tokens": 10},
        ))
        mock_llm.model_id = "mock"

        dummy_tool = Tool(
            name="get_metrics", description="m",
            input_schema={"type": "object", "properties": {}},
            run=AsyncMock(return_value=Observation(
                summary="ok", aggregates={}, samples=[],
                total_count=0, truncated=False, metadata={},
            )),
        )

        with patch("agent.storage.db.open_db") as mock_db:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
            mock_db.return_value = mock_conn

            engine = InvestigationEngine(llm=mock_llm, tools=[dummy_tool], step_budget=3)
            state = await engine.run(
                symptom="payment-gateway: error",
                time_window="14:00-15:00",
                scenario="test",
            )

        assert state.verdict is not None
        assert state.verdict.specificity_score is not None
        assert 0.0 <= state.verdict.specificity_score <= 1.0
