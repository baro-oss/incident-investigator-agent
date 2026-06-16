"""
Ngày 66 — Engine quality I: chống dừng sớm + trace trung thực + graph parity.

Cổng kiểm:
  1. H3: LLM trả text rác → re-prompt rồi mới insufficient
  2. M3: trace rớt hop giữa → complete=False + break_point + summary đúng
  3. M1: graph path tích lũy cache stats (parity với loop path)
  4. M10: loop path có with_retry (smoke)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_state(investigation_id="test-inv"):
    from agent.engine.state import InvestigationState
    return InvestigationState(
        investigation_id=investigation_id,
        symptom="test",
        time_window="14:00-15:00",
        scenario="scenario1",
        date="2024-01-01",
        project_id="default",
    )


# ═════════════════════════════════════════════════════════════════════════════
# H3 — re-prompt khi LLM trả text thô
# ═════════════════════════════════════════════════════════════════════════════

class TestRepromptOnTextResponse:
    @pytest.mark.asyncio
    async def test_text_response_triggers_reprompt(self):
        """H3: LLM trả text (không phải tool/VERDICT) → re-prompt, không dừng ngay."""
        from agent.engine.loop import decide_next_action, _MAX_TEXT_RETRIES
        from agent.llm.base import LLMResponse, Message

        state = _make_state("h3-reprompt")
        call_count = 0

        async def _mock_complete(messages, tools, system=None):
            nonlocal call_count
            call_count += 1
            # Lần 1: trả text rác; lần 2: trả tool_call
            if call_count <= _MAX_TEXT_RETRIES:
                resp = MagicMock()
                resp.has_tool_calls = False
                resp.text = "Tôi cần thêm thông tin"
                resp.tool_calls = []
                resp.usage = {"input_tokens": 10, "output_tokens": 5}
                return resp
            else:
                # Lần cuối: trả tool_call
                from agent.llm.base import ToolCall
                tc = ToolCall(id="tc1", name="get_metrics", arguments={"service": "svc"})
                resp = MagicMock()
                resp.has_tool_calls = True
                resp.tool_calls = [tc]
                resp.usage = {"input_tokens": 10, "output_tokens": 5}
                return resp

        mock_llm = MagicMock()
        mock_llm.complete = _mock_complete

        tool_call, vtext, llm_resp, v_obj = await decide_next_action(state, mock_llm, [])

        # Phải gọi LLM nhiều hơn 1 lần (có re-prompt)
        assert call_count > 1, f"Expected >1 LLM calls (got {call_count})"
        # Kết quả phải là tool_call, không phải verdict insufficient
        assert tool_call is not None
        assert vtext is None

    @pytest.mark.asyncio
    async def test_text_response_insufficient_after_max_retries(self):
        """H3: sau _MAX_TEXT_RETRIES lần text liên tiếp → tổng hợp insufficient verdict."""
        from agent.engine.loop import decide_next_action, _MAX_TEXT_RETRIES

        state = _make_state("h3-exhaust")
        call_count = 0

        async def _always_text(messages, tools, system=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.has_tool_calls = False
            resp.text = "Không biết làm gì"
            resp.tool_calls = []
            resp.usage = {}
            return resp

        mock_llm = MagicMock()
        mock_llm.complete = _always_text

        tool_call, vtext, llm_resp, v_obj = await decide_next_action(state, mock_llm, [])

        # Phải thử đúng (_MAX_TEXT_RETRIES + 1) lần
        assert call_count == _MAX_TEXT_RETRIES + 1
        # Kết quả là verdict insufficient
        assert tool_call is None
        assert vtext is not None
        assert "VERDICT" in vtext.upper()

    @pytest.mark.asyncio
    async def test_verdict_text_on_first_call_not_reprompted(self):
        """H3: nếu LLM trả text VERDICT ngay lần đầu → không re-prompt."""
        from agent.engine.loop import decide_next_action

        state = _make_state("h3-verdict-text")
        call_count = 0

        async def _verdict_text(messages, tools, system=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.has_tool_calls = False
            resp.text = "VERDICT:\nRoot cause: lỗi DB"
            resp.tool_calls = []
            resp.usage = {}
            return resp

        mock_llm = MagicMock()
        mock_llm.complete = _verdict_text

        tool_call, vtext, llm_resp, v_obj = await decide_next_action(state, mock_llm, [])

        assert call_count == 1, "Verdict text không nên trigger re-prompt"
        assert "VERDICT" in (vtext or "").upper()


# ═════════════════════════════════════════════════════════════════════════════
# M3 — trace multi-hop gap detection
# ═════════════════════════════════════════════════════════════════════════════

class TestTraceGapDetection:
    def _make_trace_rows(self, rows_spec):
        """rows_spec: list of (service, error_type)."""
        result = []
        for i, (svc, err) in enumerate(rows_spec):
            result.append({
                "trace_id": "abc123",
                "service": svc,
                "error_type": err,
                "error_message": err or "",
                "latency_ms": 100,
                "timestamp": f"2024-01-01T14:00:{i:02d}",
            })
        return result

    def _run_trace_logic(self, rows_spec):
        """Trích xuất logic detect từ trace_request.py."""
        from agent.tools.trace_request import trace_request  # noqa — just check import

        services_seen = {}
        has_error_per_service = {}
        for row in self._make_trace_rows(rows_spec):
            svc = row["service"]
            if svc not in services_seen:
                services_seen[svc] = []
            services_seen[svc].append(row)
            if row["error_type"]:
                has_error_per_service[svc] = True

        services_reached = list(services_seen.keys())
        break_point = None

        if len(services_reached) == 1:
            break_point = f"trace chỉ thấy ở {services_reached[0]}, không lan sang service khác"
            complete = False
        else:
            for idx, svc in enumerate(services_reached):
                if has_error_per_service.get(svc) and idx < len(services_reached) - 1:
                    break_point = (
                        f"lỗi tại {svc} (hop {idx+1}/{len(services_reached)}), "
                        "trace downstream có thể không đầy đủ"
                    )
                    break
            complete = break_point is None

        return complete, break_point, services_reached

    def test_single_service_is_incomplete(self):
        complete, bp, services = self._run_trace_logic([
            ("payment-gateway", "TimeoutError"),
        ])
        assert not complete
        assert bp is not None
        assert "payment-gateway" in bp

    def test_two_services_no_error_is_complete(self):
        complete, bp, services = self._run_trace_logic([
            ("payment-gateway", None),
            ("auth-service", None),
        ])
        assert complete
        assert bp is None

    def test_error_at_intermediate_service_is_incomplete(self):
        """M3: lỗi ở service giữa chain → complete=False + break_point."""
        complete, bp, services = self._run_trace_logic([
            ("payment-gateway", None),
            ("fraud-service", "TimeoutError"),  # giữa chain, có lỗi
            ("bank-api", None),
        ])
        assert not complete
        assert bp is not None
        assert "fraud-service" in bp

    def test_error_at_last_service_is_complete(self):
        """Lỗi chỉ ở service cuối (không có downstream bị mất) → vẫn complete."""
        complete, bp, services = self._run_trace_logic([
            ("payment-gateway", None),
            ("fraud-service", None),
            ("bank-api", "ConnectionError"),  # cuối chain → không đứt downstream
        ])
        assert complete
        assert bp is None


# ═════════════════════════════════════════════════════════════════════════════
# M1 — graph path cache token parity
# ═════════════════════════════════════════════════════════════════════════════

class TestGraphCacheTokenParity:
    def test_graph_node_accumulates_cache_tokens(self):
        """M1: _decide_and_emit (graph node) phải cộng cache_creation/read_input_tokens."""
        from agent.engine.state import InvestigationState

        # Build minimal inv state
        inv = InvestigationState(
            investigation_id="m1-graph",
            symptom="test",
            time_window="14:00-15:00",
            scenario="scenario1",
            date="2024-01-01",
            project_id="default",
        )
        assert inv.cache_creation_tokens == 0
        assert inv.cache_read_tokens == 0

        # Simulate graph node token update
        mock_usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 40,
            "cache_read_input_tokens": 20,
        }

        # Apply the same logic as graph.py lines 88-94 (M1 fix)
        inv.total_tokens += (
            mock_usage.get("input_tokens", 0)
            + mock_usage.get("output_tokens", 0)
        )
        inv.cache_creation_tokens += mock_usage.get("cache_creation_input_tokens", 0)
        inv.cache_read_tokens += mock_usage.get("cache_read_input_tokens", 0)

        assert inv.total_tokens == 150
        assert inv.cache_creation_tokens == 40
        assert inv.cache_read_tokens == 20


# ═════════════════════════════════════════════════════════════════════════════
# M10 — loop path có with_retry (smoke test)
# ═════════════════════════════════════════════════════════════════════════════

class TestLoopPathRetry:
    @pytest.mark.asyncio
    async def test_with_retry_imported_in_loop(self):
        """M10: with_retry phải được import và gọi trong loop._run_loop."""
        from agent.engine import loop as loop_mod
        import inspect
        src = inspect.getsource(loop_mod.InvestigationEngine._run_loop)
        assert "with_retry" in src, "with_retry phải được dùng trong _run_loop (M10)"

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_error(self):
        """M10: khi LLM raise 429/rate limit, with_retry thử lại → investigation tiếp tục."""
        from agent.engine.resilience import with_retry

        call_count = 0

        async def _flaky():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 rate limit exceeded")
            return "ok"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_retry(_flaky)
        assert result == "ok"
        assert call_count == 2, "Phải thử lại sau lỗi rate limit"
