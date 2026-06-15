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


# ── Multi-agent conflict resolution (Ngày 33) ────────────────────────────────

class TestConflictResolution:
    def test_no_confirmed_returns_none(self, sample_state):
        sample_state.add_hypothesis("H1")
        sample_state.add_hypothesis("H2")
        assert sample_state.resolve_conflicting_hypotheses() is None

    def test_single_confirmed_returns_it(self, sample_state):
        h = sample_state.add_hypothesis("H1")
        h.status = "confirmed"
        h.confidence = "medium"
        result = sample_state.resolve_conflicting_hypotheses()
        assert result is h

    def test_high_beats_medium(self, sample_state):
        h_med = sample_state.add_hypothesis("H medium")
        h_med.status = "confirmed"
        h_med.confidence = "medium"

        h_high = sample_state.add_hypothesis("H high")
        h_high.status = "confirmed"
        h_high.confidence = "high"

        winner = sample_state.resolve_conflicting_hypotheses()
        assert winner is h_high

    def test_evidence_count_tiebreaker(self, sample_state, sample_observation):
        h1 = sample_state.add_hypothesis("H1 same conf")
        h1.status = "confirmed"
        h1.confidence = "medium"

        h2 = sample_state.add_hypothesis("H2 more evidence")
        h2.status = "confirmed"
        h2.confidence = "medium"

        # h2 có 2 evidence, h1 có 1
        ev1 = sample_state.add_evidence(1, "get_metrics", {}, sample_observation)
        ev2 = sample_state.add_evidence(2, "get_metrics", {}, sample_observation)
        ev3 = sample_state.add_evidence(3, "get_metrics", {}, sample_observation)
        h1.evidence_ids.append(ev1.id)
        h2.evidence_ids.extend([ev2.id, ev3.id])

        winner = sample_state.resolve_conflicting_hypotheses()
        assert winner is h2

    def test_ruled_out_not_eligible(self, sample_state):
        h_out = sample_state.add_hypothesis("ruled out")
        h_out.status = "ruled_out"
        h_out.confidence = "high"

        h_conf = sample_state.add_hypothesis("confirmed medium")
        h_conf.status = "confirmed"
        h_conf.confidence = "medium"

        winner = sample_state.resolve_conflicting_hypotheses()
        assert winner is h_conf


# ── E6: Hypothesis catalog domain-agnostic (Ngày 36) ─────────────────────────

class TestHypothesisCatalog:
    """Verify catalog-driven _update_hypotheses — engine không hardcode domain knowledge."""

    def _make_obs(self, tool: str, summary: str) -> Observation:
        return Observation(
            summary=summary, aggregates={}, samples=[], total_count=1,
            truncated=False, metadata={"tool_name": tool},
        )

    def test_microservice_deploy_confirmed(self, sample_state):
        from agent.engine.hypothesis_catalog import MICROSERVICE_CATALOG, build_catalog_index
        from agent.engine.loop import _update_hypotheses
        sample_state.hypothesis_catalog_index = build_catalog_index(MICROSERVICE_CATALOG)

        ev = sample_state.add_evidence(
            0, "get_recent_deploys", {},
            self._make_obs("get_recent_deploys",
                           "Tìm thấy 1 deployment: v2.3.1 tại 14:03 — TimeoutException tăng sau deploy"),
        )
        _update_hypotheses(sample_state, ev)

        tags = {h.id for h in sample_state.hypotheses}
        assert "deploy" in tags
        deploy_hyp = next(h for h in sample_state.hypotheses if h.id == "deploy")
        assert deploy_hyp.status in ("open", "confirmed")

    def test_microservice_deploy_ruled_out(self, sample_state):
        from agent.engine.hypothesis_catalog import MICROSERVICE_CATALOG, build_catalog_index
        from agent.engine.loop import _update_hypotheses
        sample_state.hypothesis_catalog_index = build_catalog_index(MICROSERVICE_CATALOG)

        ev = sample_state.add_evidence(
            0, "get_recent_deploys", {},
            self._make_obs("get_recent_deploys", "Không tìm thấy deployment nào trong 1 giờ qua."),
        )
        _update_hypotheses(sample_state, ev)

        deploy_hyp = next((h for h in sample_state.hypotheses if h.id == "deploy"), None)
        assert deploy_hyp is not None
        assert deploy_hyp.status == "ruled_out"

    def test_fintech_processor_timeout_confirmed(self, sample_state):
        from agent.engine.hypothesis_catalog import FINTECH_CATALOG, build_catalog_index
        from agent.engine.loop import _update_hypotheses
        sample_state.hypothesis_catalog_index = build_catalog_index(FINTECH_CATALOG)

        ev = sample_state.add_evidence(
            0, "get_transaction_anomaly", {},
            self._make_obs("get_transaction_anomaly",
                           "proc-alpha: fail_rate 65% (32.5x baseline 2%) trong 10:15-11:00. "
                           "Kênh credit_card: lỗi chủ đạo là ProcessorTimeout (5200)."),
        )
        _update_hypotheses(sample_state, ev)

        tags = {h.id for h in sample_state.hypotheses}
        assert "processor_timeout" in tags
        # Không tạo hypothesis microservice
        assert "deploy" not in tags
        assert "pool_exhaustion" not in tags

    def test_fintech_price_bug_confirmed(self, sample_state):
        from agent.engine.hypothesis_catalog import FINTECH_CATALOG, build_catalog_index
        from agent.engine.loop import _update_hypotheses
        sample_state.hypothesis_catalog_index = build_catalog_index(FINTECH_CATALOG)

        ev = sample_state.add_evidence(
            0, "get_merchant_status", {},
            self._make_obs("get_merchant_status",
                           "merch-buzz (Buzz Commerce, retail): status=chờ xử lý. "
                           "Notes: 'price_bug_reported'. Đang điều tra lỗi định giá."),
        )
        _update_hypotheses(sample_state, ev)

        tags = {h.id for h in sample_state.hypotheses}
        assert "price_configuration_error" in tags
        price_hyp = next(h for h in sample_state.hypotheses if h.id == "price_configuration_error")
        assert price_hyp.status in ("open", "confirmed")

    def test_fintech_no_anomaly_ruled_out(self, sample_state):
        from agent.engine.hypothesis_catalog import FINTECH_CATALOG, build_catalog_index
        from agent.engine.loop import _update_hypotheses
        sample_state.hypothesis_catalog_index = build_catalog_index(FINTECH_CATALOG)

        ev = sample_state.add_evidence(
            0, "get_transaction_anomaly", {},
            self._make_obs("get_transaction_anomaly",
                           "Không phát hiện merchant bất thường. fail_rate và refund_rate bình thường."),
        )
        _update_hypotheses(sample_state, ev)

        # hypothesis tạo ra nhưng phải ruled_out (không phát hiện → rule_out_kws match)
        for h in sample_state.hypotheses:
            if h.id in ("processor_timeout", "price_configuration_error"):
                assert h.status == "ruled_out", f"{h.id} should be ruled_out"

    def test_empty_catalog_no_crash(self, sample_state):
        from agent.engine.loop import _update_hypotheses
        sample_state.hypothesis_catalog_index = {}  # empty → fallback microservice, no crash

        ev = sample_state.add_evidence(
            0, "get_metrics", {},
            self._make_obs("get_metrics", "latency lệch 9x baseline"),
        )
        _update_hypotheses(sample_state, ev)  # must not crash


# ── E7: Stop conditions shared helper + multi-agent parity (Ngày 37) ─────────

class TestStopConditionsShared:
    """Verify _check_stop_conditions được dùng bởi cả 2 path (loop + graph)."""

    def test_budget_exhausted_returns_verdict_text(self, sample_state):
        from agent.engine.loop import _check_stop_conditions
        sample_state.steps_taken = sample_state.step_budget  # đúng ngưỡng
        result = _check_stop_conditions(sample_state)
        assert result is not None
        assert "VERDICT" in result
        assert sample_state.stop_reason == "budget"
        assert sample_state.finished is True

    def test_budget_not_exhausted_returns_none(self, sample_state):
        from agent.engine.loop import _check_stop_conditions
        sample_state.steps_taken = 0
        result = _check_stop_conditions(sample_state)
        assert result is None
        assert sample_state.finished is False

    def test_loop_detected_returns_verdict_text(self, sample_state):
        from agent.engine.loop import _check_stop_conditions
        # Tạo ABABAB oscillation
        for _ in range(3):
            sample_state.tool_call_history.append({"name": "get_metrics", "params": {"s": "x"}})
            sample_state.tool_call_history.append({"name": "get_error_breakdown", "params": {"s": "x"}})
        result = _check_stop_conditions(sample_state)
        assert result is not None
        assert "VERDICT" in result
        assert sample_state.stop_reason == "loop_detected"

    def test_both_conditions_false_returns_none(self, sample_state):
        from agent.engine.loop import _check_stop_conditions
        sample_state.steps_taken = 3
        sample_state.tool_call_history = [{"name": "get_metrics", "params": {}}]
        result = _check_stop_conditions(sample_state)
        assert result is None


class TestMultiAgentParity:
    """Multi-agent merge + synthesis ngang hàng single-agent."""

    def test_merge_states_prefers_confirmed_hypothesis(self):
        from agent.engine.multi_agent import MultiAgentEngine
        from agent.tools.contracts import Observation as Obs

        def _make_state(inv_id):
            return InvestigationState(
                investigation_id=inv_id,
                symptom="test",
                time_window="14:00-15:00",
                scenario="scenario1",
                date="2024-01-15",
            )

        # log_state: hypothesis open
        log_state = _make_state("log_001")
        h_open = log_state.add_hypothesis("Deploy bug — open")
        h_open.status = "open"
        h_open.confidence = None

        # metric_state: same content, confirmed
        metric_state = _make_state("metric_001")
        h_conf = metric_state.add_hypothesis("Deploy bug — open")  # same content
        h_conf.status = "confirmed"
        h_conf.confidence = "high"
        obs = Obs(summary="x", aggregates={}, samples=[], total_count=1, truncated=False, metadata={})
        ev = metric_state.add_evidence(0, "get_recent_deploys", {}, obs)
        h_conf.evidence_ids.append(ev.id)

        engine = MultiAgentEngine.__new__(MultiAgentEngine)
        engine._hypothesis_catalog = None
        merged = engine._merge_states(
            log_state, metric_state,
            "test-001", "test", "14:00-15:00", "scenario1", "2024-01-15",
            "default", [], None,
        )

        assert len(merged.hypotheses) == 1
        assert merged.hypotheses[0].status == "confirmed"
        assert merged.hypotheses[0].confidence == "high"

    def test_conflict_resolution_annotation_in_synthesis(self, sample_state):
        # Verify resolve_conflicting_hypotheses trả winner khi >1 confirmed
        h1 = sample_state.add_hypothesis("Hypothesis A")
        h1.status = "confirmed"
        h1.confidence = "high"
        h1.evidence_ids = ["ev1", "ev2"]

        h2 = sample_state.add_hypothesis("Hypothesis B")
        h2.status = "confirmed"
        h2.confidence = "medium"
        h2.evidence_ids = ["ev3"]

        winner = sample_state.resolve_conflicting_hypotheses()
        assert winner is h1  # high beats medium
