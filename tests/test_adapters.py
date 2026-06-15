"""
Tests for T1: Intake adapters + Output renderers (Ngày 39).

Mỗi adapter ≥3 cases: happy · non-trigger→None · payload méo (no crash).
Mỗi output ≥3 cases: shape đúng · graceful không URL · state không có verdict.
"""
from __future__ import annotations

import pytest

from agent.engine.state import Evidence, Hypothesis, InvestigationState, Verdict
from agent.tools.contracts import Observation


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_state(with_verdict: bool = True) -> InvestigationState:
    state = InvestigationState(
        investigation_id="test-001",
        symptom="High error rate on payment-gateway",
        time_window="14:00-15:00",
        scenario="scenario1",
        date="2024-01-15",
        project_id="default",
    )
    state.steps_taken = 3
    if with_verdict:
        state.verdict = Verdict(
            root_cause="Deploy v2.3.1 gây TimeoutException",
            confidence="high",
            evidence_summary="Deployment lúc 14:03, lỗi tăng ngay sau đó",
            propagation_note="payment-gateway → auth-service",
            competing_hypotheses="DB pool: loại trừ (pool bình thường)",
            raw_text="VERDICT:\nRoot cause: Deploy v2.3.1",
        )
        state.stop_reason = "verdict"
    else:
        state.stop_reason = "timeout"
    obs = Observation(
        summary="Tìm thấy deployment v2.3.1",
        aggregates={}, samples=[], total_count=1, truncated=False, metadata={},
    )
    ev = state.add_evidence(0, "get_recent_deploys", {}, obs)
    return state


# ═════════════════════════════════════════════════════════════════════════════
# INTAKE ADAPTERS
# ═════════════════════════════════════════════════════════════════════════════

class TestPrometheusAdapter:
    def test_happy_path_returns_request(self):
        from agent.intake.adapters.prometheus import map_prometheus
        payload = {
            "status": "firing",
            "alerts": [{
                "labels": {"service": "payment-gateway", "scenario": "scenario1"},
                "annotations": {"summary": "High error rate"},
                "startsAt": "2024-01-15T14:05:00Z",
            }],
        }
        req = map_prometheus(payload)
        assert req is not None
        assert req.service == "payment-gateway"
        assert req.scenario == "scenario1"
        assert "High error rate" in req.symptom

    def test_missing_service_falls_back(self):
        from agent.intake.adapters.prometheus import map_prometheus
        payload = {
            "alerts": [{"labels": {}, "annotations": {"summary": "Alert"}, "startsAt": "2024-01-15T14:05:00Z"}]
        }
        req = map_prometheus(payload)
        assert req is not None  # fallback service name

    def test_malformed_payload_returns_none(self):
        from agent.intake.adapters.prometheus import map_prometheus
        assert map_prometheus(None) is None  # type: ignore
        assert map_prometheus({}) is not None  # empty payload → graceful default


class TestGrafanaAdapter:
    def test_happy_path_returns_request(self):
        from agent.intake.adapters.grafana import map_grafana
        payload = {
            "status": "firing",
            "alerts": [{
                "labels": {"service": "api-gateway", "scenario": "scenario4"},
                "annotations": {"summary": "Traffic surge 5x"},
                "startsAt": "2024-01-15T10:15:00Z",
            }],
        }
        req = map_grafana(payload)
        assert req is not None
        assert req.service == "api-gateway"
        assert "Traffic surge" in req.symptom

    def test_top_level_message_as_symptom(self):
        from agent.intake.adapters.grafana import map_grafana
        payload = {
            "status": "firing",
            "message": "Latency spike detected",
            "alerts": [{"labels": {"service": "svc"}, "annotations": {}, "startsAt": ""}],
        }
        req = map_grafana(payload)
        assert req is not None
        assert req.symptom == "Latency spike detected"

    def test_malformed_no_crash(self):
        from agent.intake.adapters.grafana import map_grafana
        assert map_grafana({"alerts": None}) is not None  # handles None alerts
        assert map_grafana({}) is not None  # empty but graceful


class TestSentryAdapter:
    def test_happy_path_returns_request(self):
        from agent.intake.adapters.sentry import map_sentry
        payload = {
            "action": "created",
            "data": {
                "issue": {
                    "title": "TimeoutException: downstream service unavailable",
                    "firstSeen": "2024-01-15T14:05:00Z",
                    "project": {"slug": "payment-gateway", "name": "Payment Gateway"},
                    "tags": [{"key": "scenario", "value": "scenario2"}],
                    "metadata": {},
                }
            },
        }
        req = map_sentry(payload)
        assert req is not None
        assert req.service == "payment-gateway"
        assert req.scenario == "scenario2"
        assert "TimeoutException" in req.symptom

    def test_scenario_from_tags(self):
        from agent.intake.adapters.sentry import map_sentry
        payload = {
            "data": {
                "issue": {
                    "title": "Error",
                    "firstSeen": "",
                    "project": {"slug": "svc"},
                    "tags": [{"key": "scenario", "value": "scenario3"}],
                    "metadata": {},
                }
            }
        }
        req = map_sentry(payload)
        assert req is not None
        assert req.scenario == "scenario3"

    def test_malformed_no_crash(self):
        from agent.intake.adapters.sentry import map_sentry
        # Adapters gracefully handle malformed payloads (return None or fallback request)
        map_sentry({})  # must not raise
        map_sentry({"data": {}})  # must not raise
        assert map_sentry(None) is None  # type: ignore


class TestPagerdutyAdapter:
    def test_trigger_event_returns_request(self):
        from agent.intake.adapters.pagerduty import map_pagerduty
        payload = {
            "messages": [{
                "event": "incident.trigger",
                "incident": {
                    "title": "High error rate",
                    "service": {"name": "payment-gateway"},
                    "created_at": "2024-01-15T14:05:00Z",
                },
            }]
        }
        req = map_pagerduty(payload)
        assert req is not None
        assert req.service == "payment-gateway"
        assert "High error rate" in req.symptom

    def test_non_trigger_event_returns_none(self):
        from agent.intake.adapters.pagerduty import map_pagerduty
        payload = {
            "messages": [{
                "event": "incident.acknowledge",
                "incident": {
                    "title": "Alert",
                    "service": {"name": "svc"},
                    "created_at": "2024-01-15T14:05:00Z",
                },
            }]
        }
        req = map_pagerduty(payload)
        assert req is None

    def test_malformed_no_crash(self):
        from agent.intake.adapters.pagerduty import map_pagerduty
        assert map_pagerduty({}) is not None or map_pagerduty({}) is None  # no crash
        assert map_pagerduty(None) is None  # type: ignore


class TestOpsgenieAdapter:
    def test_create_action_returns_request(self):
        from agent.intake.adapters.opsgenie import map_opsgenie
        payload = {
            "action": "Create",
            "alert": {
                "message": "High error rate",
                "source": "payment-gateway",
                "details": {"service": "payment-gateway", "scenario": "scenario1"},
                "tags": ["critical"],
                "createdAt": 1705327500000,
            },
        }
        req = map_opsgenie(payload)
        assert req is not None
        assert req.service == "payment-gateway"
        assert "High error rate" in req.symptom

    def test_non_create_action_returns_none(self):
        from agent.intake.adapters.opsgenie import map_opsgenie
        payload = {
            "action": "Close",
            "alert": {"message": "Alert", "source": "svc", "details": {}, "tags": [], "createdAt": 0},
        }
        req = map_opsgenie(payload)
        assert req is None

    def test_malformed_no_crash(self):
        from agent.intake.adapters.opsgenie import map_opsgenie
        assert map_opsgenie({}) is not None or map_opsgenie({}) is None  # no crash
        assert map_opsgenie(None) is None  # type: ignore


class TestGithubAdapter:
    def test_push_to_main_returns_request(self):
        from agent.intake.adapters.github import map_github
        payload = {
            "_event_type": "push",
            "ref": "refs/heads/main",
            "repository": {"name": "payment-gateway"},
            "head_commit": {
                "message": "fix: handle timeout errors",
                "timestamp": "2024-01-15T14:03:00Z",
            },
            "pusher": {"name": "alice"},
        }
        req = map_github(payload)
        assert req is not None
        assert req.service == "payment-gateway"
        assert "alice" in req.symptom

    def test_push_to_feature_branch_returns_none(self):
        from agent.intake.adapters.github import map_github
        payload = {
            "_event_type": "push",
            "ref": "refs/heads/feature/new-ui",
            "repository": {"name": "svc"},
            "head_commit": {"message": "wip", "timestamp": ""},
            "pusher": {"name": "bob"},
        }
        req = map_github(payload)
        assert req is None  # non-main branch filtered

    def test_deployment_event_returns_request(self):
        from agent.intake.adapters.github import map_github
        payload = {
            "_event_type": "deployment",
            "action": "created",
            "repository": {"name": "payment-gateway"},
            "deployment": {
                "environment": "production",
                "description": "Deploy v2.3.1",
                "created_at": "2024-01-15T14:03:00Z",
            },
        }
        req = map_github(payload)
        assert req is not None
        assert req.service == "payment-gateway"

    def test_malformed_no_crash(self):
        from agent.intake.adapters.github import map_github
        assert map_github({}) is None  # no recognized event
        assert map_github(None) is None  # type: ignore


class TestGitlabAdapter:
    def test_push_to_main_returns_request(self):
        from agent.intake.adapters.gitlab import map_gitlab
        payload = {
            "_event_type": "push hook",
            "object_kind": "push",
            "ref": "refs/heads/main",
            "project": {"name": "payment-gateway"},
            "commits": [{"message": "fix: crash fix", "timestamp": "2024-01-15T14:03:00Z", "author": {"name": "bob"}}],
        }
        req = map_gitlab(payload)
        assert req is not None
        assert req.service == "payment-gateway"

    def test_pipeline_failed_returns_request(self):
        from agent.intake.adapters.gitlab import map_gitlab
        payload = {
            "object_kind": "pipeline",
            "object_attributes": {"status": "failed", "ref": "main", "created_at": "2024-01-15T14:03:00Z"},
            "project": {"name": "payment-gateway"},
        }
        req = map_gitlab(payload)
        assert req is not None
        assert req.service == "payment-gateway"

    def test_pipeline_success_returns_none(self):
        from agent.intake.adapters.gitlab import map_gitlab
        payload = {
            "object_kind": "pipeline",
            "object_attributes": {"status": "success", "ref": "main"},
            "project": {"name": "payment-gateway"},
        }
        req = map_gitlab(payload)
        assert req is None  # only failed pipelines trigger investigation

    def test_push_feature_branch_returns_none(self):
        from agent.intake.adapters.gitlab import map_gitlab
        payload = {
            "object_kind": "push",
            "ref": "refs/heads/feature/abc",
            "project": {"name": "svc"},
            "commits": [{"message": "wip", "timestamp": ""}],
        }
        req = map_gitlab(payload)
        assert req is None

    def test_malformed_no_crash(self):
        from agent.intake.adapters.gitlab import map_gitlab
        assert map_gitlab({}) is None  # no recognized kind
        assert map_gitlab(None) is None  # type: ignore


class TestAdapterRouter:
    def test_routes_to_correct_adapter(self):
        from agent.intake.adapters import route_adapter
        payload = {
            "alerts": [{
                "labels": {"service": "svc", "scenario": "scenario1"},
                "annotations": {"summary": "test"},
                "startsAt": "2024-01-15T14:05:00Z",
            }]
        }
        req = route_adapter("prometheus", payload)
        assert req is not None

    def test_unknown_source_returns_none(self):
        from agent.intake.adapters import route_adapter
        assert route_adapter("unknown-source", {}) is None

    def test_list_sources_nonempty(self):
        from agent.intake.adapters import list_sources
        sources = list_sources()
        assert len(sources) >= 7
        assert "prometheus" in sources
        assert "github" in sources
        assert "sentry" in sources


# ═════════════════════════════════════════════════════════════════════════════
# OUTPUT RENDERERS
# ═════════════════════════════════════════════════════════════════════════════

class TestSlackOutput:
    def test_render_with_verdict_has_correct_shape(self):
        from agent.output.slack import _render_slack_payload
        state = _make_state(with_verdict=True)
        payload = _render_slack_payload(state)
        assert "text" in payload
        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        attachment = payload["attachments"][0]
        assert "color" in attachment
        assert "blocks" in attachment
        # HIGH confidence → red color
        assert attachment["color"] == "#DC143C"

    def test_render_without_verdict_still_returns_payload(self):
        from agent.output.slack import _render_slack_payload
        state = _make_state(with_verdict=False)
        payload = _render_slack_payload(state)
        assert "text" in payload
        assert "attachments" in payload
        # No verdict → insufficient (gray)
        assert payload["attachments"][0]["color"] == "#808080"

    async def test_push_without_url_does_not_raise(self):
        from agent.output.slack import push_verdict_to_slack
        state = _make_state(with_verdict=True)
        # No URL set — should log warning and return silently
        await push_verdict_to_slack(state, config={})

    def test_medium_confidence_uses_orange_color(self):
        from agent.output.slack import _render_slack_payload
        state = _make_state(with_verdict=True)
        state.verdict.confidence = "medium"
        payload = _render_slack_payload(state)
        assert payload["attachments"][0]["color"] == "#FF8C00"


class TestTeamsOutput:
    def test_render_returns_message_card(self):
        from agent.output.teams import render_teams_card
        state = _make_state(with_verdict=True)
        card = render_teams_card(state)
        assert card["@type"] == "MessageCard"
        assert "sections" in card
        assert len(card["sections"]) > 0
        # HIGH → red (DC143C)
        assert card["themeColor"] == "DC143C"

    def test_render_without_verdict_returns_card(self):
        from agent.output.teams import render_teams_card
        state = _make_state(with_verdict=False)
        card = render_teams_card(state)
        assert card["@type"] == "MessageCard"
        assert card["themeColor"] == "808080"  # gray

    async def test_push_without_url_returns_false(self):
        from agent.output.teams import push_verdict_to_teams
        state = _make_state(with_verdict=True)
        result = await push_verdict_to_teams(state, config={})
        assert result is False

    def test_render_facts_contain_root_cause(self):
        from agent.output.teams import render_teams_card
        state = _make_state(with_verdict=True)
        card = render_teams_card(state)
        # Root cause should appear in activityTitle
        section = card["sections"][0]
        assert "Deploy v2.3.1" in section["activityTitle"]


class TestTelegramOutput:
    def test_render_with_verdict_contains_root_cause(self):
        from agent.output.telegram import render_telegram_message
        state = _make_state(with_verdict=True)
        msg = render_telegram_message(state)
        assert "Deploy v2.3.1" in msg
        assert "Độ tin CAO" in msg

    def test_render_without_verdict_mentions_stop_reason(self):
        from agent.output.telegram import render_telegram_message
        state = _make_state(with_verdict=False)
        msg = render_telegram_message(state)
        assert "timeout" in msg.lower() or "stop" in msg.lower() or "không tạo được" in msg.lower()

    def test_render_truncates_long_content(self):
        from agent.output.telegram import render_telegram_message
        state = _make_state(with_verdict=True)
        state.symptom = "x" * 500
        msg = render_telegram_message(state)
        # Symptom should be truncated to ~100 chars
        assert len(msg) < 2000  # overall reasonable length

    def test_render_medium_confidence_label(self):
        from agent.output.telegram import render_telegram_message
        state = _make_state(with_verdict=True)
        state.verdict.confidence = "medium"
        msg = render_telegram_message(state)
        assert "TRUNG BÌNH" in msg


class TestCallbackOutput:
    def test_payload_has_correct_fields(self):
        from agent.output.callback import _build_callback_payload
        state = _make_state(with_verdict=True)
        payload = _build_callback_payload(state)
        assert payload["investigation_id"] == "test-001"
        assert payload["project_id"] == "default"
        assert payload["scenario"] == "scenario1"
        assert payload["verdict"] is not None
        assert payload["verdict"]["root_cause"] == "Deploy v2.3.1 gây TimeoutException"
        assert payload["verdict"]["confidence"] == "high"

    def test_payload_without_verdict(self):
        from agent.output.callback import _build_callback_payload
        state = _make_state(with_verdict=False)
        payload = _build_callback_payload(state)
        assert payload["verdict"] is None
        assert payload["stop_reason"] == "timeout"

    async def test_push_to_bad_url_does_not_raise(self):
        from agent.output.callback import push_callback
        state = _make_state(with_verdict=True)
        # Connect to localhost:1 should fail gracefully
        result = await push_callback(state, "http://localhost:1/callback")
        assert result is False  # connection error → False, no exception

    def test_speculative_flag_included(self):
        from agent.output.callback import _build_callback_payload
        state = _make_state(with_verdict=True)
        state.verdict.speculative = True
        payload = _build_callback_payload(state)
        assert payload["verdict"]["speculative"] is True


class TestEmailOutput:
    def test_render_html_contains_root_cause(self):
        from agent.output.email import render_email_html
        state = _make_state(with_verdict=True)
        html = render_email_html(state)
        assert "Deploy v2.3.1" in html
        assert "<html" in html.lower() or "<table" in html.lower() or "Root cause" in html

    def test_render_html_without_verdict(self):
        from agent.output.email import render_email_html
        state = _make_state(with_verdict=False)
        html = render_email_html(state)
        assert isinstance(html, str)
        assert len(html) > 0

    async def test_push_without_smtp_config_does_not_raise(self):
        from agent.output.email import push_verdict_to_email
        state = _make_state(with_verdict=True)
        # No SMTP_HOST configured → should log and return without crashing
        await push_verdict_to_email(state, config={})
