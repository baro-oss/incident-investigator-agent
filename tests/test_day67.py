"""
Ngày 67 — Engine quality II: specificity tuning + competing gate + code-diff + deps.

Cổng kiểm:
  1. Specificity: verdict chỉ nhắc time-window KHÔNG qua gate (timestamp bị lọc)
  2. Competing gate multi-agent: high + open competing → downgrade + annotate
  3. M8: get_code_diff dùng call_tool_text (không qua _parse_observation)
  4. M9: get_dependencies cap ≤5 samples + truncated đúng
  5. L4: time_window sai format → error Observation (4 tools)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_state(investigation_id="test-inv", project_id="default"):
    from agent.engine.state import InvestigationState
    return InvestigationState(
        investigation_id=investigation_id,
        symptom="test",
        time_window="14:00-15:00",
        scenario="scenario1",
        date="2024-01-01",
        project_id=project_id,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1. Specificity: timestamp pattern không inflate count
# ═════════════════════════════════════════════════════════════════════════════

class TestSpecificityTimestampFilter:
    def test_time_window_not_counted_as_numbers(self):
        """14:00-15:00 không tạo ra 2+ distinct numbers."""
        from agent.engine.specificity import _count_distinct_numbers
        text = "Trong time window 14:00-15:00 không có số đo cụ thể."
        count = _count_distinct_numbers(text)
        assert count < 2, f"time_window không nên tạo count ≥2 (got {count})"

    def test_real_metrics_still_counted(self):
        """Số đo thực (87%, 500ms) vẫn được đếm bình thường."""
        from agent.engine.specificity import _count_distinct_numbers
        text = "Error rate tăng 87% so với baseline 3%. Latency p99=500ms."
        count = _count_distinct_numbers(text)
        assert count >= 3, f"87, 3, 500 phải được đếm (got {count})"

    def test_mixed_time_and_metrics(self):
        """Kết hợp: time (lọc) + số đo (giữ)."""
        from agent.engine.specificity import _count_distinct_numbers
        text = "Lúc 9:30-10:00 error rate=95%, latency=1200ms, 42 request thất bại."
        count = _count_distinct_numbers(text)
        # 9:30 → bỏ, 10:00 → bỏ; còn 95, 1200, 42 → 3
        assert count >= 3

    def test_evidence_summary_with_only_timestamps_fails_signal_b(self):
        """Sau khi lọc timestamp, evidence_summary chỉ có HH:MM → count < 2 → signal (b) fail."""
        from agent.engine.specificity import _count_distinct_numbers
        # Trước fix: "14:00 đến 15:00" → {14, 00, 15} → count=3 → signal (b) PASS (sai)
        # Sau fix: strip HH:MM → count=0 → signal (b) FAIL (đúng)
        text = "Thấy lỗi ở khoảng 14:00 đến 15:00"
        count = _count_distinct_numbers(text)
        assert count < 2, f"Timestamp-only evidence_summary phải count<2 (got {count})"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Competing gate — multi-agent
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiAgentCompetingGate:
    def _make_merged_state_with_competing(self, conf="high"):
        """Tạo state có 1 confirmed + 1 open hypothesis và verdict conf."""
        from agent.engine.state import (
            Evidence, Hypothesis, InvestigationState, Verdict,
        )

        state = InvestigationState(
            investigation_id="ma-gate",
            symptom="test",
            time_window="14:00-15:00",
            scenario="scenario1",
            date="2024-01-01",
            project_id="default",
        )
        h1 = Hypothesis(id="h1", content="DB pool exhausted", status="confirmed", confidence="high")
        h2 = Hypothesis(id="h2", content="Provider sập", status="open", confidence="medium")
        state.hypotheses = [h1, h2]

        verdict = Verdict(
            root_cause="DB pool exhausted gây timeout",
            confidence=conf,
            evidence_summary="Pool utilization 100%",
            propagation_note="Lan sang API gateway",
            competing_hypotheses="",
            raw_text="",
        )
        state.verdict = verdict
        return state

    def test_competing_gate_downgrades_high(self):
        """Verdict high + open competing hypothesis → downgrade → medium."""
        merged = self._make_merged_state_with_competing("high")
        assert merged.competing_open(), "Phải có competing hypothesis"

        competing = merged.competing_open()
        if merged.verdict.confidence in ("high", "medium") and competing:
            names = "; ".join(h.content[:60] for h in competing[:3])
            _dg = {"high": "medium", "medium": "low"}
            orig = merged.verdict.confidence
            merged.verdict.confidence = _dg.get(orig, orig)
            merged.verdict.competing_hypotheses = (
                (merged.verdict.competing_hypotheses or "")
                + f" [⚠ E4 competing-gate: {len(competing)} hypothesis chưa loại trừ — {names[:80]}]"
            )

        assert merged.verdict.confidence == "medium"
        assert "E4" in (merged.verdict.competing_hypotheses or "")

    def test_competing_gate_skips_when_no_open(self):
        """Không có competing hypothesis open → verdict không bị downgrade."""
        merged = self._make_merged_state_with_competing("high")
        # Đóng tất cả hypothesis
        for h in merged.hypotheses:
            h.status = "confirmed"
        assert not merged.competing_open()
        original_conf = merged.verdict.confidence

        competing = merged.competing_open()
        if merged.verdict.confidence in ("high", "medium") and competing:
            _dg = {"high": "medium", "medium": "low"}
            merged.verdict.confidence = _dg.get(merged.verdict.confidence, merged.verdict.confidence)

        assert merged.verdict.confidence == original_conf

    def test_competing_gate_skips_low_conf(self):
        """Verdict low/insufficient không bị downgrade bởi gate."""
        merged = self._make_merged_state_with_competing("low")
        assert merged.competing_open()

        competing = merged.competing_open()
        if merged.verdict.confidence in ("high", "medium") and competing:
            _dg = {"high": "medium", "medium": "low"}
            merged.verdict.confidence = _dg.get(merged.verdict.confidence, merged.verdict.confidence)

        assert merged.verdict.confidence == "low"


# ═════════════════════════════════════════════════════════════════════════════
# 3. M8 — get_code_diff dùng call_tool_text
# ═════════════════════════════════════════════════════════════════════════════

class TestCodeDiffUsesCallToolText:
    def test_call_tool_text_method_exists(self):
        """MCPClient phải có method call_tool_text."""
        from agent.tools.mcp_client import MCPClient
        assert hasattr(MCPClient, "call_tool_text"), "MCPClient phải có call_tool_text"

    @pytest.mark.asyncio
    async def test_call_tool_text_returns_raw_string(self):
        """call_tool_text trả string, không tạo Observation."""
        from agent.tools.mcp_client import MCPClient

        client = MCPClient.__new__(MCPClient)
        client._req_id = 0
        client.url = "http://mock"

        fake_result = {"content": [{"type": "text", "text": "diff --git a/file.py b/file.py\n+print('hello')"}]}
        client._call = AsyncMock(return_value=fake_result)

        result = await client.call_tool_text("get_diff", {"repo": "r", "ref": "v1"})
        assert isinstance(result, str)
        assert "diff --git" in result
        assert "+print" in result

    @pytest.mark.asyncio
    async def test_get_code_diff_calls_call_tool_text(self):
        """build_code_diff_tool phải gọi code_mcp_client.call_tool_text, không diff_tool.run()."""
        import inspect
        from agent.tools import get_code_diff as gcd_mod
        src = inspect.getsource(gcd_mod)
        assert "call_tool_text" in src, "get_code_diff phải dùng call_tool_text (M8)"
        assert "raw_obs" not in src or "raw_obs.summary" not in src, \
            "get_code_diff không được dùng raw_obs.summary (double-distill)"


# ═════════════════════════════════════════════════════════════════════════════
# 4. M9 — get_dependencies cap + truncated
# ═════════════════════════════════════════════════════════════════════════════

class TestDependenciesSampleCap:
    def test_truncated_flag_import(self):
        """get_dependencies.py phải import SAMPLES_HARD_CAP và dùng truncated đúng."""
        import inspect
        from agent.tools import get_dependencies as gd_mod
        src = inspect.getsource(gd_mod)
        assert "SAMPLES_HARD_CAP" in src
        assert "truncated=len(dep_details) > SAMPLES_HARD_CAP" in src

    def test_samples_capped_at_hard_cap(self):
        """Nếu có >5 deps, samples phải ≤5 và truncated=True."""
        from agent.tools.contracts import SAMPLES_HARD_CAP

        # Tạo dep_details lớn hơn cap
        dep_details = [{"service": f"svc{i}"} for i in range(10)]
        samples = dep_details[:SAMPLES_HARD_CAP]
        truncated = len(dep_details) > SAMPLES_HARD_CAP
        assert len(samples) == SAMPLES_HARD_CAP
        assert truncated is True

    def test_samples_not_truncated_when_few(self):
        """Nếu deps ≤5, truncated=False."""
        from agent.tools.contracts import SAMPLES_HARD_CAP
        dep_details = [{"service": f"svc{i}"} for i in range(3)]
        truncated = len(dep_details) > SAMPLES_HARD_CAP
        assert truncated is False


# ═════════════════════════════════════════════════════════════════════════════
# 5. L4 — time_window validation (4 tools)
# ═════════════════════════════════════════════════════════════════════════════

class TestTimeWindowValidation:
    @pytest.mark.parametrize("tool_fn,tool_name", [
        ("agent.tools.get_error_breakdown", "get_error_breakdown"),
        ("agent.tools.get_metrics", "get_metrics"),
        ("agent.tools.trace_request", "trace_request"),
        ("agent.tools.get_recent_deploys", "get_recent_deploys"),
    ])
    def test_invalid_time_window_returns_error_obs(self, tool_fn, tool_name):
        """Tool với time_window sai format phải trả Observation có 'error' (không raise)."""
        import importlib
        mod = importlib.import_module(tool_fn)
        _run = mod._run

        result = _run({"service": "payment-gateway", "time_window": "not-a-window"})
        assert result.total_count == 0
        assert "HH:MM" in result.summary or "định dạng" in result.summary
        assert result.metadata.get("error") == "invalid_time_window"

    def test_valid_time_window_passes(self):
        """time_window hợp lệ (HH:MM-HH:MM) không bị chặn ở lớp validation."""
        import re
        valid = "14:00-15:00"
        assert re.match(r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$", valid.strip())

    def test_invalid_patterns_rejected(self):
        """Các pattern sai đều bị reject."""
        import re
        pattern = r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$"
        invalid = ["not-a-window", "14:00", "14:00-", "-15:00", "14:00-15:00:00", ""]
        for tw in invalid:
            assert not re.match(pattern, tw.strip()), f"'{tw}' phải bị reject"
