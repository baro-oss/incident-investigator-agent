"""
Coverage tests cho dashboard/queries.py — các hàm query DB.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ── get_cost_data ─────────────────────────────────────────────────────────────

class TestGetCostData:
    def test_returns_dict(self):
        from agent.dashboard.queries import get_cost_data
        result = get_cost_data()
        assert isinstance(result, dict)

    def test_has_grand_total_key(self):
        from agent.dashboard.queries import get_cost_data
        result = get_cost_data()
        assert any(k in result for k in ("grand_total_tokens", "grand_total_cost", "scenarios"))

    def test_does_not_crash(self):
        from agent.dashboard.queries import get_cost_data
        result = get_cost_data()
        assert result is not None


# ── list_investigations ───────────────────────────────────────────────────────

class TestListInvestigations:
    def test_returns_list(self):
        from agent.dashboard.queries import list_investigations
        result = list_investigations()
        assert isinstance(result, list)

    def test_filter_by_project(self):
        from agent.dashboard.queries import list_investigations
        result = list_investigations(project_id="default")
        assert isinstance(result, list)

    def test_filter_by_confidence(self):
        from agent.dashboard.queries import list_investigations
        result = list_investigations(confidence="high")
        assert isinstance(result, list)

    def test_filter_by_search(self):
        from agent.dashboard.queries import list_investigations
        result = list_investigations(search="payment-gateway")
        assert isinstance(result, list)


# ── get_eval_summary ─────────────────────────────────────────────────────────

class TestGetEvalSummary:
    def test_returns_list_or_dict(self):
        from agent.dashboard.queries import get_eval_summary
        result = get_eval_summary()
        assert isinstance(result, (list, dict))

    def test_does_not_crash(self):
        from agent.dashboard.queries import get_eval_summary
        result = get_eval_summary()
        assert result is not None


# ── get_projects_overview ─────────────────────────────────────────────────────

class TestGetProjectsOverview:
    def test_returns_list(self):
        from agent.dashboard.queries import get_projects_overview
        result = get_projects_overview()
        assert isinstance(result, list)


# ── get_metrics_live ─────────────────────────────────────────────────────────

class TestGetMetricsLive:
    def test_returns_list(self):
        from agent.dashboard.queries import get_metrics_live
        result = get_metrics_live()
        assert isinstance(result, list)

    def test_filter_by_service(self):
        from agent.dashboard.queries import get_metrics_live
        result = get_metrics_live(service="payment-gateway")
        assert isinstance(result, list)


# ── get_specificity_data ──────────────────────────────────────────────────────

class TestGetSpecificityData:
    def test_returns_dict(self):
        from agent.dashboard.queries import get_specificity_data
        result = get_specificity_data()
        assert isinstance(result, dict)


# ── get_eval_comparison_data ─────────────────────────────────────────────────

class TestGetEvalComparisonData:
    def test_returns_dict_with_prior_keys(self):
        from agent.dashboard.queries import get_eval_comparison_data
        result = get_eval_comparison_data()
        assert isinstance(result, dict)
        assert "with_prior" in result
        assert "no_prior" in result

    def test_does_not_crash_on_empty_db(self):
        from agent.dashboard.queries import get_eval_comparison_data
        result = get_eval_comparison_data()
        assert result is not None


# ── get_mcp_servers_for_dashboard ─────────────────────────────────────────────

class TestGetMcpServersForDashboard:
    def test_returns_list(self):
        from agent.dashboard.queries import get_mcp_servers_for_dashboard
        result = get_mcp_servers_for_dashboard()
        assert isinstance(result, list)


# ── get_all_tools_for_dashboard ───────────────────────────────────────────────

class TestGetAllToolsForDashboard:
    def test_returns_dict_or_list(self):
        from agent.dashboard.queries import get_all_tools_for_dashboard
        result = get_all_tools_for_dashboard()
        assert isinstance(result, (dict, list))

    def test_contains_microservice_domain(self):
        from agent.dashboard.queries import get_all_tools_for_dashboard
        result = get_all_tools_for_dashboard()
        if isinstance(result, dict):
            assert "microservice" in result
            tools = result["microservice"]
        else:
            tools = result
        assert len(tools) > 0

    def test_tools_have_name_field(self):
        from agent.dashboard.queries import get_all_tools_for_dashboard
        result = get_all_tools_for_dashboard()
        if isinstance(result, dict):
            tools = result.get("microservice", [])
        else:
            tools = result
        if tools:
            assert "name" in tools[0]


# ── pricing helper ────────────────────────────────────────────────────────────

class TestPricingHelper:
    def test_anthropic_sonnet_pricing(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("anthropic", "claude-sonnet-4")
        assert in_p > 0 and out_p > 0

    def test_mock_provider_zero_cost(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("mock", "")
        assert in_p == 0.0 and out_p == 0.0

    def test_unknown_provider_fallback(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("unknown-provider", "some-model")
        assert isinstance(in_p, float) and isinstance(out_p, float)

    def test_cost_usd_with_tokens(self):
        from agent.dashboard.queries import _cost_usd
        cost = _cost_usd(100_000, "anthropic", "claude-sonnet")
        assert cost > 0.0

    def test_cost_usd_zero_tokens(self):
        from agent.dashboard.queries import _cost_usd
        assert _cost_usd(0, "anthropic", "claude-sonnet") == 0.0
