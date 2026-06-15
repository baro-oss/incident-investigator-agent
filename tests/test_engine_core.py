"""
Unit tests cho engine core: hypothesis lifecycle, loop detection, evidence grounding.
"""
from __future__ import annotations

import pytest

from agent.engine.loop import _check_evidence_grounding, _structured_args_to_verdict_text
from agent.engine.state import Evidence, Hypothesis, InvestigationState, Verdict
from agent.tools.contracts import Observation


# ── Hypothesis lifecycle (E1) ────────────────────────────────────────────────

class TestHypothesisLifecycle:
    def test_add_hypothesis_starts_open(self, sample_state):
        hyp = sample_state.add_hypothesis("Deploy v2.3.1 gây lỗi")
        assert hyp.status == "open"
        assert hyp.confidence is None
        assert hyp.id in [h.id for h in sample_state.hypotheses]

    def test_hypothesis_transitions_to_confirmed(self, sample_state):
        hyp = sample_state.add_hypothesis("Deploy v2.3.1 gây lỗi")
        hyp.status = "confirmed"
        hyp.confidence = "high"
        assert sample_state.hypotheses[0].status == "confirmed"
        assert sample_state.hypotheses[0].confidence == "high"

    def test_hypothesis_transitions_to_ruled_out(self, sample_state):
        hyp = sample_state.add_hypothesis("Provider down")
        hyp.status = "ruled_out"
        assert sample_state.hypotheses[0].status == "ruled_out"

    def test_multiple_hypotheses_independent_status(self, sample_state):
        h1 = sample_state.add_hypothesis("Deploy bug")
        h2 = sample_state.add_hypothesis("Provider down")
        h1.status = "confirmed"
        h2.status = "ruled_out"
        assert sample_state.hypotheses[0].status == "confirmed"
        assert sample_state.hypotheses[1].status == "ruled_out"


# ── competing_open() (E1) ────────────────────────────────────────────────────

class TestCompetingOpen:
    def test_empty_when_no_hypotheses(self, sample_state):
        assert sample_state.competing_open() == []

    def test_empty_when_none_confirmed(self, sample_state):
        sample_state.add_hypothesis("Deploy bug")
        sample_state.add_hypothesis("Provider down")
        # Không có confirmed → competing_open trả rỗng
        assert sample_state.competing_open() == []

    def test_returns_open_when_some_confirmed(self, sample_state):
        h1 = sample_state.add_hypothesis("Deploy bug")
        h2 = sample_state.add_hypothesis("Provider down")
        h1.status = "confirmed"
        # h2 còn open → là cạnh tranh
        result = sample_state.competing_open()
        assert len(result) == 1
        assert result[0].id == h2.id

    def test_empty_when_all_resolved(self, sample_state):
        h1 = sample_state.add_hypothesis("Deploy bug")
        h2 = sample_state.add_hypothesis("Provider down")
        h1.status = "confirmed"
        h2.status = "ruled_out"
        assert sample_state.competing_open() == []


# ── Loop oscillation detection (E4) ─────────────────────────────────────────

class TestLoopDetection:
    def _push(self, state: InvestigationState, name: str, params: dict = None):
        state.tool_call_history.append({"name": name, "params": params or {}})

    def test_no_loop_with_single_call(self, sample_state):
        self._push(sample_state, "get_metrics", {"service": "payment-gateway"})
        assert not sample_state.is_looping()

    def test_detects_two_consecutive_identical(self, sample_state):
        self._push(sample_state, "get_metrics", {"service": "payment-gateway"})
        self._push(sample_state, "get_metrics", {"service": "payment-gateway"})
        assert sample_state.is_looping()

    def test_no_loop_with_different_calls(self, sample_state):
        self._push(sample_state, "get_metrics", {"service": "payment-gateway"})
        self._push(sample_state, "get_error_breakdown", {"service": "payment-gateway"})
        assert not sample_state.is_looping()

    def test_detects_oscillation_period_2(self, sample_state):
        # A B A B A B → period 2
        for _ in range(3):
            self._push(sample_state, "get_metrics", {"service": "x"})
            self._push(sample_state, "get_error_breakdown", {"service": "x"})
        assert sample_state.is_looping()

    def test_detects_oscillation_period_3(self, sample_state):
        # A B C A B C → period 3
        for _ in range(2):
            self._push(sample_state, "get_metrics", {})
            self._push(sample_state, "get_error_breakdown", {})
            self._push(sample_state, "get_recent_deploys", {})
        assert sample_state.is_looping()

    def test_nudge_calls_filtered_out(self, sample_state):
        # _competing_gate calls không được tính vào lịch sử kiểm tra
        self._push(sample_state, "get_metrics", {"service": "x"})
        self._push(sample_state, "_competing_gate", {})
        self._push(sample_state, "get_error_breakdown", {"service": "x"})
        # Chỉ 2 call thật (get_metrics, get_error_breakdown) — không loop
        assert not sample_state.is_looping()


# ── Evidence grounding guard (E2) ────────────────────────────────────────────

class TestEvidenceGrounding:
    def _make_evidence(self, tool: str, summary: str) -> Evidence:
        obs = Observation(summary=summary, aggregates={}, samples=[], total_count=1, truncated=False, metadata={})
        return Evidence(id="ev1", step=1, tool_name=tool, params={}, summary=summary, observation=obs)

    def test_good_verdict_not_flagged(self, sample_verdict):
        ev = self._make_evidence("get_recent_deploys", "Deploy v2.3.1 lúc 14:03 — TimeoutException tăng")
        result = _check_evidence_grounding(sample_verdict, [ev])
        assert not result.speculative
        assert result.confidence == "high"

    def test_no_evidence_flags_speculative(self, sample_verdict):
        result = _check_evidence_grounding(sample_verdict, [])
        assert result.speculative
        assert result.confidence == "insufficient"

    def test_unrelated_verdict_downgraded(self):
        verdict = Verdict(
            root_cause="unicorn magic caused the outage",
            confidence="high",
            evidence_summary="Deployment happened",
            propagation_note="...",
            competing_hypotheses="none",
            raw_text="",
        )
        ev = self._make_evidence("get_metrics", "error_rate tăng 80% từ 14:05 deploy payment-gateway")
        result = _check_evidence_grounding(verdict, [ev])
        assert result.speculative
        assert result.confidence != "high"

    def test_insufficient_confidence_passthrough(self):
        verdict = Verdict(
            root_cause="chưa đủ bằng chứng",
            confidence="insufficient",
            evidence_summary="",
            propagation_note="",
            competing_hypotheses="",
            raw_text="",
        )
        result = _check_evidence_grounding(verdict, [])
        # insufficient không bị xử lý thêm
        assert result.confidence == "insufficient"
        assert not result.speculative


# ── Structured verdict args → text (E5) ─────────────────────────────────────

class TestStructuredVerdictText:
    def test_converts_high_confidence(self):
        args = {
            "root_cause": "Deploy v2.3.1 gây lỗi",
            "confidence": "high",
            "evidence_summary": "Deploy tại 14:03",
            "propagation": "payment-gateway → api-gateway",
            "competing_hypotheses": "Provider down đã loại trừ",
        }
        text = _structured_args_to_verdict_text(args)
        assert "VERDICT:" in text
        assert "CAO" in text
        assert "Deploy v2.3.1" in text

    def test_converts_insufficient_confidence(self):
        args = {
            "root_cause": "unknown",
            "confidence": "insufficient",
            "evidence_summary": "",
            "propagation": "",
            "competing_hypotheses": "",
        }
        text = _structured_args_to_verdict_text(args)
        assert "CHƯA ĐỦ BẰNG CHỨNG" in text

    def test_missing_confidence_defaults_to_insufficient(self):
        args = {"root_cause": "x", "evidence_summary": "", "propagation": "", "competing_hypotheses": ""}
        text = _structured_args_to_verdict_text(args)
        assert "CHƯA ĐỦ BẰNG CHỨNG" in text


# ── link_evidence_to_hypothesis ──────────────────────────────────────────────

class TestEvidenceLinking:
    def test_link_adds_evidence_id_to_hypothesis(self, sample_state, sample_observation):
        hyp = sample_state.add_hypothesis("Deploy bug")
        ev = sample_state.add_evidence(1, "get_recent_deploys", {}, sample_observation)
        sample_state.link_evidence_to_hypothesis(hyp.id, ev.id)
        assert ev.id in sample_state.hypotheses[0].evidence_ids

    def test_link_idempotent(self, sample_state, sample_observation):
        hyp = sample_state.add_hypothesis("Deploy bug")
        ev = sample_state.add_evidence(1, "get_recent_deploys", {}, sample_observation)
        sample_state.link_evidence_to_hypothesis(hyp.id, ev.id)
        sample_state.link_evidence_to_hypothesis(hyp.id, ev.id)
        # Không duplicate
        assert sample_state.hypotheses[0].evidence_ids.count(ev.id) == 1

    def test_link_nonexistent_hypothesis_is_noop(self, sample_state, sample_observation):
        ev = sample_state.add_evidence(1, "get_recent_deploys", {}, sample_observation)
        sample_state.link_evidence_to_hypothesis("nonexistent-id", ev.id)
        # Không crash
