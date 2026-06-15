"""
Shared fixtures cho toàn bộ test suite.
"""
from __future__ import annotations

import pytest

from agent.engine.state import Evidence, Hypothesis, InvestigationState, Verdict
from agent.tools.contracts import Observation


@pytest.fixture
def sample_state() -> InvestigationState:
    return InvestigationState(
        investigation_id="test-001",
        symptom="High error rate on payment-gateway",
        time_window="14:00-15:00",
        scenario="scenario1",
        date="2024-01-15",
        project_id="default",
    )


@pytest.fixture
def sample_observation() -> Observation:
    return Observation(
        summary="Deploy v2.3.1 at 14:03 — TimeoutException tăng 80% sau deploy",
        aggregates={"error_rate": 0.8, "deploy_count": 1},
        samples=[{"version": "v2.3.1", "deployed_at": "14:03"}],
        total_count=1,
        truncated=False,
        metadata={"tool_name": "get_recent_deploys", "service": "payment-gateway"},
    )


@pytest.fixture
def sample_verdict() -> Verdict:
    return Verdict(
        root_cause="Deploy v2.3.1 gây TimeoutException từ 14:05",
        confidence="high",
        evidence_summary="Deploy v2.3.1 lúc 14:03, TimeoutException tăng 80% từ 14:05",
        propagation_note="Lỗi gốc tại payment-gateway, lan lên api-gateway",
        competing_hypotheses="Provider down đã loại trừ — latency provider bình thường",
        raw_text="VERDICT:\nRoot cause: Deploy v2.3.1...",
    )
