"""
Tests cho E11 — Cross-investigation service prior (Ngày 46).

Kiểm:
- HypothesisCatalogEntry.root_cause_type đầy đủ trên mọi entry
- build_rct_index lookup chính xác
- _classify_root_cause bao phủ cả fintech
- get_service_priors trả đúng dữ liệu từ DB
- _preseed_hypotheses xây Hypothesis từ priors
- InvestigationEngine.run() tích hợp: pre-seed hypotheses xuất hiện trong state
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from agent.engine.hypothesis_catalog import (
    FINTECH_CATALOG,
    MICROSERVICE_CATALOG,
    build_rct_index,
    get_default_catalog,
)
from agent.engine.loop import InvestigationEngine, _preseed_hypotheses
from agent.engine.state import Hypothesis


# ── Catalog: root_cause_type đầy đủ ─────────────────────────────────────────

class TestCatalogRootCauseType:
    def test_all_microservice_entries_have_rct(self):
        for entry in MICROSERVICE_CATALOG:
            assert entry.root_cause_type, f"tag={entry.tag} thiếu root_cause_type"

    def test_all_fintech_entries_have_rct(self):
        for entry in FINTECH_CATALOG:
            assert entry.root_cause_type, f"tag={entry.tag} thiếu root_cause_type"

    def test_rct_unique_within_each_catalog(self):
        ms_rcts = [e.root_cause_type for e in MICROSERVICE_CATALOG]
        assert len(ms_rcts) == len(set(ms_rcts)), "Duplicate root_cause_type trong MICROSERVICE_CATALOG"
        ft_rcts = [e.root_cause_type for e in FINTECH_CATALOG]
        assert len(ft_rcts) == len(set(ft_rcts)), "Duplicate root_cause_type trong FINTECH_CATALOG"

    def test_known_microservice_mappings(self):
        idx = build_rct_index(MICROSERVICE_CATALOG)
        assert idx["deploy_bug"].tag == "deploy"
        assert idx["pool_exhaustion"].tag == "pool_exhaustion"
        assert idx["provider_down"].tag == "provider_down"
        assert idx["timeout"].tag == "timeout"
        assert idx["latency_spike"].tag == "latency_spike"

    def test_known_fintech_mappings(self):
        idx = build_rct_index(FINTECH_CATALOG)
        assert idx["processor_timeout"].tag == "processor_timeout"
        assert idx["price_configuration_error"].tag == "price_configuration_error"
        assert idx["merchant_fraud"].tag == "merchant_fraud"
        assert idx["settlement_lag"].tag == "settlement_lag"


# ── _classify_root_cause fintech ─────────────────────────────────────────────

class TestClassifyRootCause:
    def setup_method(self):
        from agent.memory.patterns import _classify_root_cause
        self.classify = _classify_root_cause

    def test_deploy_bug(self):
        assert self.classify("Deploy v2.3.1 gây lỗi") == "deploy_bug"

    def test_pool_exhaustion(self):
        assert self.classify("Connection pool exhaustion") == "pool_exhaustion"

    def test_provider_down(self):
        assert self.classify("Provider MoMo bị sập") == "provider_down"

    def test_processor_timeout_fintech(self):
        assert self.classify("Processor timeout gây fail_rate tăng") == "processor_timeout"

    def test_price_configuration_error_fintech(self):
        assert self.classify("Price bug gây refund_rate tăng") == "price_configuration_error"

    def test_merchant_fraud_fintech(self):
        assert self.classify("Merchant fraud phát hiện") == "merchant_fraud"

    def test_settlement_lag_fintech(self):
        assert self.classify("Settlement lag chậm hơn baseline") == "settlement_lag"

    def test_latency_spike(self):
        assert self.classify("Latency spike bất thường") == "latency_spike"

    def test_timeout_generic(self):
        result = self.classify("Downstream timeout xảy ra")
        assert result == "timeout"

    def test_unknown_falls_through(self):
        assert self.classify("Không rõ nguyên nhân") == "unknown"


# ── get_service_priors ────────────────────────────────────────────────────────

def _make_temp_db_with_patterns(rows: list):
    """Tạo DB connection (Postgres) với investigation_patterns đã seed rows.
    Dùng open_db() — pg_db fixture phải được active trước.
    """
    from agent.storage.db import open_db
    conn = open_db()
    # Xóa dữ liệu cũ để đảm bảo isolation
    conn.execute("DELETE FROM investigation_patterns")
    for r in rows:
        conn.execute(
            "INSERT INTO investigation_patterns "
            "(project_id, service, error_pattern, root_cause_type, avg_steps, count) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (r["project_id"], r["service"], r["error_pattern"],
             r["root_cause_type"], r["avg_steps"], r["count"]),
        )
    conn.commit()
    return conn


class TestGetServicePriors:
    def test_returns_empty_when_no_data(self, pg_db):
        conn = _make_temp_db_with_patterns([])
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("default", "payment-gateway")
        assert result == []

    def test_returns_sorted_by_count_desc(self, pg_db):
        rows = [
            {"project_id": "p1", "service": "svc", "error_pattern": "err1",
             "root_cause_type": "deploy_bug", "avg_steps": 5.0, "count": 3},
            {"project_id": "p1", "service": "svc", "error_pattern": "err2",
             "root_cause_type": "pool_exhaustion", "avg_steps": 7.0, "count": 10},
        ]
        conn = _make_temp_db_with_patterns(rows)
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("p1", "svc")
        assert len(result) == 2
        assert result[0]["root_cause_type"] == "pool_exhaustion"  # count=10 first
        assert result[0]["count"] == 10
        assert result[1]["root_cause_type"] == "deploy_bug"

    def test_ignores_unknown_type(self, pg_db):
        rows = [
            {"project_id": "p1", "service": "svc", "error_pattern": "err1",
             "root_cause_type": "unknown", "avg_steps": 3.0, "count": 5},
            {"project_id": "p1", "service": "svc", "error_pattern": "err2",
             "root_cause_type": "deploy_bug", "avg_steps": 4.0, "count": 2},
        ]
        conn = _make_temp_db_with_patterns(rows)
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("p1", "svc")
        assert len(result) == 1
        assert result[0]["root_cause_type"] == "deploy_bug"

    def test_respects_limit(self, pg_db):
        rows = [
            {"project_id": "p", "service": "s", "error_pattern": f"e{i}",
             "root_cause_type": f"type_{i}", "avg_steps": 5.0, "count": i}
            for i in range(1, 6)
        ]
        conn = _make_temp_db_with_patterns(rows)
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("p", "s", limit=2)
        assert len(result) == 2

    def test_returns_empty_on_db_error(self):
        with patch("agent.memory.patterns.open_db", side_effect=Exception("DB down")):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("p", "svc")
        assert result == []


# ── _preseed_hypotheses ───────────────────────────────────────────────────────

class TestPreseedHypotheses:
    def _rct_index(self):
        return build_rct_index(MICROSERVICE_CATALOG)

    def test_returns_empty_when_service_empty(self, pg_db):
        rct_idx = self._rct_index()
        with patch("agent.memory.patterns.open_db", return_value=_make_temp_db_with_patterns([])):
            result = _preseed_hypotheses("p", "", rct_idx)
        assert result == []

    def test_returns_empty_when_no_priors(self, pg_db):
        rct_idx = self._rct_index()
        conn = _make_temp_db_with_patterns([])
        with patch("agent.memory.patterns.open_db", return_value=conn):
            result = _preseed_hypotheses("p", "svc", rct_idx)
        assert result == []

    def test_creates_hypothesis_with_prior_seen_count(self, pg_db):
        rows = [{"project_id": "p", "service": "svc", "error_pattern": "err",
                 "root_cause_type": "deploy_bug", "avg_steps": 5.0, "count": 7}]
        conn = _make_temp_db_with_patterns(rows)
        rct_idx = self._rct_index()
        with patch("agent.memory.patterns.open_db", return_value=conn):
            result = _preseed_hypotheses("p", "svc", rct_idx)
        assert len(result) == 1
        h = result[0]
        assert isinstance(h, Hypothesis)
        assert h.id == "deploy"           # catalog tag
        assert h.status == "open"
        assert h.prior_seen_count == 7
        assert "deploy" in h.keywords or "deployment" in h.keywords

    def test_skips_unknown_rct(self, pg_db):
        rows = [{"project_id": "p", "service": "svc", "error_pattern": "err",
                 "root_cause_type": "some_unknown_type", "avg_steps": 3.0, "count": 2}]
        conn = _make_temp_db_with_patterns(rows)
        rct_idx = self._rct_index()
        with patch("agent.memory.patterns.open_db", return_value=conn):
            result = _preseed_hypotheses("p", "svc", rct_idx)
        assert result == []

    def test_multiple_priors_order_preserved(self, pg_db):
        rows = [
            {"project_id": "p", "service": "s", "error_pattern": "e1",
             "root_cause_type": "pool_exhaustion", "avg_steps": 7.0, "count": 10},
            {"project_id": "p", "service": "s", "error_pattern": "e2",
             "root_cause_type": "deploy_bug", "avg_steps": 5.0, "count": 4},
        ]
        conn = _make_temp_db_with_patterns(rows)
        rct_idx = self._rct_index()
        with patch("agent.memory.patterns.open_db", return_value=conn):
            result = _preseed_hypotheses("p", "s", rct_idx)
        assert len(result) == 2
        assert result[0].id == "pool_exhaustion"
        assert result[1].id == "deploy"


# ── InvestigationEngine.run() integration ────────────────────────────────────

class TestEnginePreseedIntegration:
    """Kiểm engine pre-seed hypothesis vào state khi có prior."""

    async def test_preseed_appears_in_state(self, pg_db):
        """Engine.run() với service có prior → state bắt đầu với hypothesis đã có."""
        from unittest.mock import AsyncMock, MagicMock

        from agent.engine.loop import InvestigationEngine
        from agent.llm.base import LLMResponse, ToolCall
        from agent.tools.contracts import Tool, Observation

        # Mock LLM → trả submit_verdict ngay bước đầu
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            tool_calls=[ToolCall(
                id="call1",
                name="submit_verdict",
                arguments={
                    "root_cause": "Deploy bug",
                    "confidence": "medium",
                    "evidence_summary": "deploy tìm thấy",
                    "propagation_note": "root=svc",
                    "competing_hypotheses": "không",
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

        # DB với 1 prior cho service "payment-gateway"
        rows = [{"project_id": "default", "service": "payment-gateway",
                 "error_pattern": "err", "root_cause_type": "deploy_bug",
                 "avg_steps": 5.0, "count": 3}]
        conn = _make_temp_db_with_patterns(rows)

        engine = InvestigationEngine(
            llm=mock_llm, tools=[dummy_tool], step_budget=3,
        )

        with patch("agent.memory.patterns.open_db", return_value=conn):
            with patch("agent.storage.db.open_db", return_value=_make_temp_db_with_patterns([])):
                state = await engine.run(
                    symptom="payment-gateway: error rate high",
                    time_window="14:00-15:00",
                    scenario="test",
                    service="payment-gateway",
                )

        # Hypothesis "deploy" phải đã có từ đầu (id=deploy, prior_seen_count=3)
        prior_hyp = next((h for h in state.hypotheses if h.id == "deploy"), None)
        assert prior_hyp is not None, "Hypothesis 'deploy' không được pre-seed"
        assert prior_hyp.prior_seen_count == 3

    async def test_no_preseed_without_priors(self, pg_db):
        """Engine.run() khi DB trống → state không có hypothesis pre-seed."""
        from unittest.mock import AsyncMock, MagicMock

        from agent.engine.loop import InvestigationEngine
        from agent.llm.base import LLMResponse, ToolCall
        from agent.tools.contracts import Tool, Observation

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            tool_calls=[ToolCall(
                id="call1",
                name="submit_verdict",
                arguments={
                    "root_cause": "Không rõ",
                    "confidence": "low",
                    "evidence_summary": "ít bằng chứng",
                    "propagation_note": "N/A",
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
                summary="bình thường", aggregates={}, samples=[],
                total_count=0, truncated=False, metadata={},
            )),
        )

        conn = _make_temp_db_with_patterns([])
        engine = InvestigationEngine(llm=mock_llm, tools=[dummy_tool], step_budget=3)

        with patch("agent.memory.patterns.open_db", return_value=conn):
            with patch("agent.storage.db.open_db", return_value=_make_temp_db_with_patterns([])):
                state = await engine.run(
                    symptom="auth-service: latency spike",
                    time_window="10:00-11:00",
                    scenario="test",
                    service="auth-service",
                )

        prior_hyps = [h for h in state.hypotheses if h.prior_seen_count > 0]
        assert prior_hyps == [], f"Không có prior nhưng state có hypothesis pre-seed: {prior_hyps}"
