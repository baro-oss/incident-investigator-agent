"""
Tests Day 53 — E13: Prior decay + V1 eval harness.

- _decay_weight: exponential decay theo thời gian
- get_service_priors: sort theo weighted_count (không phải raw count)
- InvestigationEngine no_prior=True: không pre-seed hypothesis
- evaluate_run: ghi specificity_score
- get_eval_comparison_data: group by prior_flag
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from agent.memory.patterns import _HALF_LIFE_DAYS, _decay_weight


# ═════════════════════════════════════════════════════════════════════════════
# A. _decay_weight — hàm mũ theo thời gian
# ═════════════════════════════════════════════════════════════════════════════

def _iso(days_ago: float) -> str:
    """Tạo ISO timestamp cách đây N ngày."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


class TestDecayWeight:

    def test_today_returns_one(self):
        w = _decay_weight(_iso(0))
        assert abs(w - 1.0) < 0.02, f"Today weight phải gần 1.0, got {w}"

    def test_half_life_returns_half(self):
        w = _decay_weight(_iso(_HALF_LIFE_DAYS))
        assert abs(w - 0.5) < 0.05, f"Weight sau {_HALF_LIFE_DAYS} ngày phải gần 0.5, got {w}"

    def test_two_half_lives_returns_quarter(self):
        w = _decay_weight(_iso(_HALF_LIFE_DAYS * 2))
        assert abs(w - 0.25) < 0.05, f"Weight sau {_HALF_LIFE_DAYS*2} ngày phải gần 0.25, got {w}"

    def test_older_is_less_than_newer(self):
        w_new = _decay_weight(_iso(1))
        w_old = _decay_weight(_iso(60))
        assert w_new > w_old

    def test_empty_string_degrade_safe(self):
        """Không có updated_at → không crash, trả 1.0 (không penalty)."""
        assert _decay_weight("") == 1.0

    def test_bad_iso_degrade_safe(self):
        assert _decay_weight("not-a-date") == 1.0

    def test_weight_is_between_zero_and_one(self):
        for days in [0, 7, 30, 90, 365]:
            w = _decay_weight(_iso(days))
            assert 0.0 < w <= 1.0, f"Weight phải trong (0,1], got {w} for {days} days"

    def test_monotonically_decreasing(self):
        weights = [_decay_weight(_iso(d)) for d in [0, 10, 30, 60, 120]]
        for i in range(len(weights) - 1):
            assert weights[i] > weights[i + 1], \
                f"Weight phải giảm dần, got {weights}"


# ═════════════════════════════════════════════════════════════════════════════
# B. get_service_priors — sort theo weighted_count
# ═════════════════════════════════════════════════════════════════════════════

def _make_patterns_db(rows: list):
    """
    rows: list of (root_cause_type, count, avg_steps, updated_at_days_ago)
    Seeds investigation_patterns in pg_db and returns an open connection.
    pg_db fixture must be active.
    """
    from agent.storage.db import open_db
    conn = open_db()
    conn.execute("DELETE FROM investigation_patterns")
    for rct, count, avg_steps, days_ago in rows:
        conn.execute(
            "INSERT INTO investigation_patterns "
            "(project_id, service, error_pattern, root_cause_type, avg_steps, count, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            ("proj", "svc", f"pattern-{rct}", rct, avg_steps, count, _iso(days_ago))
        )
    conn.commit()
    return conn


class TestGetServicePriorsDecay:

    def test_newer_pattern_ranked_higher_same_count(self, pg_db):
        """Cùng count=5 nhưng pattern A mới hơn B → A đứng trước."""
        conn = _make_patterns_db([
            ("deploy_bug", 5, 3.0, 60),    # B: cũ 60 ngày
            ("pool_exhaustion", 5, 3.0, 1), # A: mới 1 ngày
        ])
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("proj", "svc")
        assert result[0]["root_cause_type"] == "pool_exhaustion", \
            f"Pattern mới phải đứng trước, got {result[0]['root_cause_type']}"

    def test_weighted_count_present_in_result(self, pg_db):
        conn = _make_patterns_db([("deploy_bug", 3, 3.0, 0)])
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("proj", "svc")
        assert "weighted_count" in result[0]

    def test_today_weighted_count_equals_count(self, pg_db):
        """Pattern updated hôm nay → weighted_count ≈ count (decay ≈ 1.0)."""
        conn = _make_patterns_db([("deploy_bug", 4, 3.0, 0)])
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("proj", "svc")
        wc = result[0]["weighted_count"]
        assert abs(wc - 4.0) < 0.1, f"weighted_count phải ≈ count=4, got {wc}"

    def test_old_pattern_lower_weighted_count(self, pg_db):
        """Pattern 60 ngày tuổi (2× half-life) → weighted_count ≈ count × 0.25."""
        conn = _make_patterns_db([("deploy_bug", 8, 3.0, _HALF_LIFE_DAYS * 2)])
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("proj", "svc")
        wc = result[0]["weighted_count"]
        assert wc < 8.0 * 0.4, f"weighted_count của pattern cũ phải < 40% count, got {wc}"

    def test_empty_returns_empty(self, pg_db):
        conn = _make_patterns_db([])
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("proj", "svc")
        assert result == []

    def test_limit_respected(self, pg_db):
        conn = _make_patterns_db([
            (f"type_{i}", 1, 3.0, i) for i in range(10)
        ])
        with patch("agent.memory.patterns.open_db", return_value=conn):
            from agent.memory.patterns import get_service_priors
            result = get_service_priors("proj", "svc", limit=3)
        assert len(result) <= 3


# ═════════════════════════════════════════════════════════════════════════════
# C. InvestigationEngine no_prior=True — không pre-seed hypothesis
# ═════════════════════════════════════════════════════════════════════════════

class TestNoPriorFlag:

    @pytest.mark.asyncio
    async def test_no_prior_skips_preseed(self):
        """no_prior=True → _preseed_hypotheses không được gọi."""
        from agent.engine.loop import InvestigationEngine
        from agent.tools.registry import get_tool_registry

        mock_llm = MagicMock()
        mock_llm.complete = MagicMock(return_value=None)

        engine = InvestigationEngine(
            llm=mock_llm,
            tools=get_tool_registry(),
            no_prior=True,
        )
        assert engine._no_prior is True

        with patch("agent.engine.loop._preseed_hypotheses") as mock_preseed:
            mock_preseed.return_value = []
            # Không cần chạy đến completion — chỉ cần preseed không được gọi
            # Ta có thể kiểm bằng cách patch và chắc chắn không có call
            # Nhưng _preseed_hypotheses vẫn được gọi (có check bên trong engine)
            # Thực ra: với no_prior=True, engine KHÔNG gọi _preseed_hypotheses
            pass

        # Verify bằng cách chạy một investigation ngắn và kiểm state không có prior hyps
        # Dùng mock LLM trả verdict ngay bước đầu
        from agent.llm.base import LLMResponse, ToolCall

        call_count = 0

        class QuickMock:
            async def complete(self, messages, tools, *, system=None):
                nonlocal call_count
                call_count += 1
                return LLMResponse(text="VERDICT:\nRoot cause: test\nĐộ tin: THẤP\nBằng chứng: test\nLan truyền: test\nGiả thuyết cạnh tranh: none")

        engine2 = InvestigationEngine(
            llm=QuickMock(),
            tools=get_tool_registry(),
            no_prior=True,
        )

        # Seed a fake prior first
        db_path = _make_patterns_db([("deploy_bug", 10, 3.0, 0)])
        with patch("agent.engine.loop.open_db", side_effect=lambda: _open_sqlite(db_path)):
            with patch("agent.memory.patterns.open_db", side_effect=lambda: _open_sqlite(db_path)):
                state = await engine2.run(
                    symptom="svc: test error",
                    time_window="00:00-01:00",
                    service="svc",
                    project_id="proj",
                )

        # Với no_prior=True, không có hypothesis nào được pre-seed từ DB
        # (hypothesis có thể được tạo trong quá trình investigation, nhưng prior_seen_count = 0)
        prior_seeded = [h for h in state.hypotheses if h.prior_seen_count > 0]
        assert prior_seeded == [], \
            f"no_prior=True không được pre-seed hypothesis với prior_seen_count>0, got {prior_seeded}"
        os.unlink(db_path)

    def test_no_prior_false_by_default(self):
        """no_prior mặc định là False (backward compat)."""
        from agent.engine.loop import InvestigationEngine
        mock_llm = MagicMock()
        engine = InvestigationEngine(llm=mock_llm, tools=[])
        assert engine._no_prior is False


# ═════════════════════════════════════════════════════════════════════════════
# D. evaluate_run — specificity_score trong result
# ═════════════════════════════════════════════════════════════════════════════

class TestEvalHarness:

    def _make_state_with_verdict(self, specificity: float = None):
        from agent.engine.state import InvestigationState, Verdict
        state = InvestigationState(
            investigation_id="eval-test",
            symptom="svc: error",
            time_window="00:00-01:00",
            scenario="scenario1",
            date="2026-06-15",
        )
        state.steps_taken = 3
        state.stop_reason = "verdict"
        state.verdict = Verdict(
            root_cause="Deploy v2.3.1 lúc 14:03 payment-gateway",
            confidence="high",
            evidence_summary="87% timeout sau 14:05; latency 8x",
            propagation_note="lỗi tại payment-gateway",
            competing_hypotheses="provider ok",
            raw_text="",
            specificity_score=specificity,
        )
        return state

    def test_evaluate_run_has_specificity_key(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from eval_agent import evaluate_run, SCENARIOS

        state = self._make_state_with_verdict(specificity=0.75)
        result = evaluate_run(state, SCENARIOS["scenario1"])
        assert "specificity_score" in result

    def test_specificity_score_captured(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from eval_agent import evaluate_run, SCENARIOS

        state = self._make_state_with_verdict(specificity=0.67)
        result = evaluate_run(state, SCENARIOS["scenario1"])
        assert result["specificity_score"] == pytest.approx(0.67)

    def test_specificity_none_when_no_verdict(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from eval_agent import evaluate_run, SCENARIOS
        from agent.engine.state import InvestigationState

        state = InvestigationState(
            investigation_id="x", symptom="s", time_window="t", scenario="s1", date="d",
        )
        state.stop_reason = "budget"
        result = evaluate_run(state, SCENARIOS["scenario1"])
        assert result["specificity_score"] is None


# ═════════════════════════════════════════════════════════════════════════════
# E. get_eval_comparison_data — group by prior_flag
# ═════════════════════════════════════════════════════════════════════════════

def _seed_eval_rows(rows: list) -> None:
    """Insert eval_results rows vào Postgres test schema hiện tại."""
    from agent.storage.db import open_db
    conn = open_db()
    for prior_flag, steps, spec, correct in rows:
        conn.execute(
            "INSERT INTO eval_results (prior_flag, steps_taken, specificity_score, correct) "
            "VALUES (?, ?, ?, ?)",
            (prior_flag, steps, spec, correct),
        )
    conn.commit()
    conn.close()


class TestEvalComparisonData:

    def test_empty_db_returns_none_for_both(self, pg_db):
        from agent.dashboard.queries import get_eval_comparison_data
        result = get_eval_comparison_data()
        assert result["with_prior"] is None
        assert result["no_prior"] is None

    def test_with_prior_grouped_correctly(self, pg_db):
        _seed_eval_rows([(0, 3, 0.75, 1), (0, 5, 0.50, 1)])
        from agent.dashboard.queries import get_eval_comparison_data
        result = get_eval_comparison_data()
        assert result["with_prior"] is not None
        assert result["with_prior"]["n"] == 2
        assert result["no_prior"] is None

    def test_no_prior_grouped_correctly(self, pg_db):
        _seed_eval_rows([(1, 4, 0.25, 1), (1, 6, 0.00, 0)])
        from agent.dashboard.queries import get_eval_comparison_data
        result = get_eval_comparison_data()
        assert result["no_prior"] is not None
        assert result["no_prior"]["n"] == 2
        assert result["with_prior"] is None

    def test_both_groups_present(self, pg_db):
        _seed_eval_rows([(0, 3, 0.75, 1), (1, 5, 0.25, 1)])
        from agent.dashboard.queries import get_eval_comparison_data
        result = get_eval_comparison_data()
        assert result["with_prior"] is not None
        assert result["no_prior"] is not None

    def test_avg_steps_computed(self, pg_db):
        _seed_eval_rows([(0, 3, 0.5, 1), (0, 5, 0.5, 1)])
        from agent.dashboard.queries import get_eval_comparison_data
        result = get_eval_comparison_data()
        assert result["with_prior"]["avg_steps"] == pytest.approx(4.0)
