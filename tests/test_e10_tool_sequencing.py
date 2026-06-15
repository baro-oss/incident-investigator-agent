"""
Tests cho E10 — Hypothesis-guided tool sequencing (Ngày 47).

Kiểm:
- _tool_sequencing_hint trả hint cho open hypothesis có relevant_tool chưa gọi
- Hint biến mất khi tất cả relevant_tools đã gọi
- Không hint khi không có giả thuyết open
- Prior hypotheses (prior_seen_count > 0) xếp trước (E11 synergy)
- Cap ≤3 giả thuyết
- _build_user_message chứa hint khi có giả thuyết open
- Parity: cùng state → cùng hint (loop và graph cùng gọi _build_user_message)
"""
from __future__ import annotations

import pytest

from agent.engine.hypothesis_catalog import MICROSERVICE_CATALOG, build_catalog_index
from agent.engine.loop import _build_user_message, _tool_sequencing_hint
from agent.engine.state import Hypothesis, InvestigationState


def _make_state(hypotheses=None, tool_history=None) -> InvestigationState:
    state = InvestigationState(
        investigation_id="test-e10",
        symptom="payment-gateway: high error rate",
        time_window="14:00-15:00",
        scenario="test",
        date="2024-01-15",
    )
    state.hypothesis_catalog_index = build_catalog_index(MICROSERVICE_CATALOG)
    if hypotheses:
        state.hypotheses = hypotheses
    if tool_history:
        state.tool_call_history = tool_history
    return state


def _open_hyp(tag: str, prior: int = 0) -> Hypothesis:
    return Hypothesis(
        id=tag, content=f"Hypothesis {tag}", status="open",
        keywords=[], prior_seen_count=prior,
    )


# ── _tool_sequencing_hint ────────────────────────────────────────────────────

class TestToolSequencingHint:
    def test_returns_empty_when_no_hypotheses(self):
        state = _make_state()
        assert _tool_sequencing_hint(state) == ""

    def test_returns_empty_when_no_catalog(self):
        state = _make_state(hypotheses=[_open_hyp("deploy")])
        state.hypothesis_catalog_index = {}
        assert _tool_sequencing_hint(state) == ""

    def test_hint_for_open_with_uncalled_tool(self):
        state = _make_state(hypotheses=[_open_hyp("deploy")])
        hint = _tool_sequencing_hint(state)
        assert "deploy" in hint
        assert "get_recent_deploys" in hint

    def test_hint_contains_header(self):
        state = _make_state(hypotheses=[_open_hyp("deploy")])
        hint = _tool_sequencing_hint(state)
        assert "Tool gợi ý" in hint

    def test_no_hint_when_all_tools_called(self):
        state = _make_state(
            hypotheses=[_open_hyp("deploy")],
            tool_history=[
                {"name": "get_recent_deploys", "params": {}},
                {"name": "get_code_diff", "params": {}},
            ],
        )
        hint = _tool_sequencing_hint(state)
        assert hint == ""

    def test_partial_tools_called_shows_uncalled(self):
        """pool_exhaustion cần get_metrics và get_error_breakdown — gọi 1 thì còn 1."""
        state = _make_state(
            hypotheses=[_open_hyp("pool_exhaustion")],
            tool_history=[{"name": "get_metrics", "params": {}}],
        )
        hint = _tool_sequencing_hint(state)
        assert "pool_exhaustion" in hint
        assert "get_error_breakdown" in hint
        assert "get_metrics" not in hint

    def test_no_hint_for_confirmed_hypothesis(self):
        confirmed = Hypothesis(
            id="deploy", content="deploy bug", status="confirmed", keywords=[],
        )
        state = _make_state(hypotheses=[confirmed])
        assert _tool_sequencing_hint(state) == ""

    def test_no_hint_for_ruled_out_hypothesis(self):
        ruled_out = Hypothesis(
            id="deploy", content="deploy bug", status="ruled_out", keywords=[],
        )
        state = _make_state(hypotheses=[ruled_out])
        assert _tool_sequencing_hint(state) == ""

    def test_prior_hypothesis_listed_first(self):
        """Giả thuyết prior (prior_seen_count > 0) phải xuất hiện trước regular."""
        regular = _open_hyp("timeout", prior=0)
        prior_hyp = _open_hyp("deploy", prior=5)
        state = _make_state(hypotheses=[regular, prior_hyp])
        hint = _tool_sequencing_hint(state)
        # deploy (prior 5×) phải xuất hiện trước timeout
        assert hint.index("deploy") < hint.index("timeout")

    def test_prior_note_in_hint(self):
        state = _make_state(hypotheses=[_open_hyp("deploy", prior=3)])
        hint = _tool_sequencing_hint(state)
        assert "prior 3×" in hint

    def test_no_prior_note_when_zero(self):
        state = _make_state(hypotheses=[_open_hyp("deploy", prior=0)])
        hint = _tool_sequencing_hint(state)
        assert "prior" not in hint

    def test_cap_at_three_hypotheses(self):
        """Với >3 giả thuyết open, chỉ hiện ≤3."""
        hyps = [_open_hyp(t) for t in ["deploy", "timeout", "pool_exhaustion", "provider_down"]]
        state = _make_state(hypotheses=hyps)
        hint = _tool_sequencing_hint(state)
        # Đếm số dòng hint (mỗi hypothesis 1 dòng)
        hint_lines = [ln for ln in hint.split("\n") if ln.strip().startswith(("deploy", "timeout", "pool", "provider"))]
        assert len(hint_lines) <= 3

    def test_hypothesis_without_catalog_entry_skipped(self):
        """Hypothesis với id không có trong catalog → bỏ qua, không crash."""
        unknown_hyp = Hypothesis(id="unknown_tag", content="unknown", status="open", keywords=[])
        state = _make_state(hypotheses=[unknown_hyp])
        hint = _tool_sequencing_hint(state)
        assert hint == "" or "unknown_tag" not in hint

    def test_multiple_tools_in_hint(self):
        """provider_down có 2 relevant_tools — cả 2 xuất hiện khi chưa gọi gì."""
        state = _make_state(hypotheses=[_open_hyp("provider_down")])
        hint = _tool_sequencing_hint(state)
        assert "get_dependencies" in hint
        assert "get_error_breakdown" in hint


# ── _build_user_message chứa hint ───────────────────────────────────────────

class TestBuildUserMessageWithHint:
    def test_message_includes_hint_when_applicable(self):
        state = _make_state(hypotheses=[_open_hyp("deploy")])
        msg = _build_user_message(state, last_obs=None)
        assert "Tool gợi ý" in msg
        assert "get_recent_deploys" in msg

    def test_message_no_hint_when_no_open(self):
        confirmed = Hypothesis(id="deploy", content="deploy", status="confirmed", keywords=[])
        state = _make_state(hypotheses=[confirmed])
        msg = _build_user_message(state, last_obs=None)
        assert "Tool gợi ý" not in msg

    def test_hint_appears_before_buoc_tiep_theo(self):
        state = _make_state(hypotheses=[_open_hyp("deploy")])
        msg = _build_user_message(state, last_obs=None)
        hint_pos = msg.find("Tool gợi ý")
        question_pos = msg.find("Bước tiếp theo")
        assert hint_pos < question_pos, "Hint phải xuất hiện trước câu hỏi"

    def test_hint_updates_after_tool_call(self):
        """Sau khi gọi hết relevant_tools của deploy, hint không còn nhắc deploy nữa."""
        state = _make_state(hypotheses=[_open_hyp("deploy")])
        msg_before = _build_user_message(state, last_obs=None)
        assert "deploy" in msg_before

        # Giả lập đã gọi hết relevant_tools của deploy (F2: bao gồm get_code_diff)
        state.tool_call_history.append({"name": "get_recent_deploys", "params": {}})
        state.tool_call_history.append({"name": "get_code_diff", "params": {}})
        msg_after = _build_user_message(state, last_obs=None)
        # deploy không còn trong hint (nhưng có thể còn trong summarize_for_llm)
        after_hint_section = msg_after.split("## Tool gợi ý")[1] if "## Tool gợi ý" in msg_after else ""
        assert "deploy" not in after_hint_section


# ── Parity: loop ↔ graph dùng cùng _build_user_message ──────────────────────

class TestParity:
    def test_same_state_same_hint(self):
        """Cùng state → _tool_sequencing_hint trả cùng kết quả (deterministic)."""
        state = _make_state(hypotheses=[_open_hyp("deploy", prior=2), _open_hyp("timeout")])
        hint1 = _tool_sequencing_hint(state)
        hint2 = _tool_sequencing_hint(state)
        assert hint1 == hint2

    def test_same_state_same_build_message(self):
        """_build_user_message là hàm pure — cùng input → cùng output."""
        state = _make_state(hypotheses=[_open_hyp("pool_exhaustion")])
        msg1 = _build_user_message(state, last_obs=None)
        msg2 = _build_user_message(state, last_obs=None)
        assert msg1 == msg2

    def test_hint_empty_string_when_all_called(self):
        """Idempotent khi đã gọi hết tool: trả '' không có whitespace thừa."""
        state = _make_state(
            hypotheses=[_open_hyp("deploy")],
            tool_history=[
                {"name": "get_recent_deploys", "params": {}},
                {"name": "get_code_diff", "params": {}},
            ],
        )
        assert _tool_sequencing_hint(state) == ""
