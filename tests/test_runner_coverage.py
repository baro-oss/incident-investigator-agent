"""
Coverage tests cho intake/runner.py — helper functions + trigger_investigation.
Không chạy full async engine để giữ tests nhanh.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── _get_mcp_servers_for_project ─────────────────────────────────────────────

class TestGetMcpServersForProject:
    def test_returns_list_when_db_available(self):
        from agent.intake.runner import _get_mcp_servers_for_project
        # DB has been migrated, default project exists — should not crash
        result = _get_mcp_servers_for_project("default")
        assert isinstance(result, list)

    def test_fallback_when_db_fails(self):
        from agent.intake.runner import _get_mcp_servers_for_project
        with patch("agent.intake.mcp_registry.get_enabled_servers", side_effect=Exception("DB error")):
            result = _get_mcp_servers_for_project("default")
        assert isinstance(result, list)

    def test_returns_list_for_unknown_project(self):
        from agent.intake.runner import _get_mcp_servers_for_project
        result = _get_mcp_servers_for_project("nonexistent-project-xyz")
        assert isinstance(result, list)


# ── _get_project_services ─────────────────────────────────────────────────────

class TestGetProjectServices:
    def test_returns_list(self):
        from agent.intake.runner import _get_project_services
        result = _get_project_services("default")
        assert isinstance(result, list)

    def test_fallback_when_db_fails(self):
        from agent.intake.runner import _get_project_services
        with patch("agent.intake.project_registry.list_project_services", side_effect=Exception("err")):
            result = _get_project_services("default")
        assert result == []


# ── _make_error_state ─────────────────────────────────────────────────────────

def _make_req(service="svc", scenario="scenario1", time_window="10:00-11:00",
              project_id="default", key_suffix=""):
    from agent.intake.normalizer import InvestigationRequest
    dedup = f"{project_id}|{service}|{scenario}|{time_window}{key_suffix}"
    return InvestigationRequest(
        service=service,
        scenario=scenario,
        time_window=time_window,
        symptom="test symptom",
        date="2024-01-01",
        raw_payload={},
        project_id=project_id,
        dedup_key=dedup,
    )


class TestMakeErrorState:
    def test_returns_finished_state(self):
        from agent.intake.runner import _make_error_state
        req = _make_req()
        state = _make_error_state(req, "timeout")
        assert state.finished is True
        assert state.stop_reason == "timeout"

    def test_state_has_correct_investigation_id(self):
        from agent.intake.runner import _make_error_state
        req = _make_req(service="payment-gateway", scenario="scenario2", time_window="15:00-16:00")
        state = _make_error_state(req, "error: boom")
        assert state.investigation_id == req.dedup_key
        assert "error" in state.stop_reason


# ── trigger_investigation ─────────────────────────────────────────────────────

class TestTriggerInvestigation:
    def test_trigger_uses_queue_when_available(self):
        from agent.intake.runner import trigger_investigation
        req = _make_req(key_suffix="-a")
        mock_queue = MagicMock()
        with patch("agent.intake.investigation_queue._queue", mock_queue), \
             patch("agent.intake.investigation_queue.enqueue") as mock_enqueue:
            trigger_investigation(req, step_budget=5)
        mock_enqueue.assert_called_once_with(req, step_budget=5)

    def test_trigger_fallback_when_no_queue(self):
        from agent.intake.runner import trigger_investigation
        req = _make_req(key_suffix="-b")
        with patch("agent.intake.investigation_queue._queue", None), \
             patch("asyncio.create_task") as mock_task:
            trigger_investigation(req, step_budget=3)
        mock_task.assert_called_once()


# ── run_investigation_background — dedup ──────────────────────────────────────

class TestRunInvestigationDedup:
    @pytest.mark.asyncio
    async def test_dedup_skips_duplicate_key(self):
        from agent.intake.runner import run_investigation_background, _active_investigations
        req = _make_req(key_suffix="-dedup-999")
        _active_investigations.add(req.dedup_key)
        try:
            # Should return immediately (dedup skip) without calling engine
            with patch("agent.intake.runner._connect_mcp_clients") as mock_connect:
                await run_investigation_background(req)
                mock_connect.assert_not_called()
        finally:
            _active_investigations.discard(req.dedup_key)


# ── _connect / _close MCP clients ────────────────────────────────────────────

class TestMcpClientConnect:
    @pytest.mark.asyncio
    async def test_connect_skips_unreachable_server(self):
        from agent.intake.runner import _connect_mcp_clients
        servers = [{"url": "http://127.0.0.1:59999", "auth_type": "none", "auth_config": "{}"}]
        clients = await _connect_mcp_clients(servers)
        # Non-reachable server should be skipped gracefully
        assert isinstance(clients, list)

    @pytest.mark.asyncio
    async def test_close_mcp_clients_handles_empty(self):
        from agent.intake.runner import _close_mcp_clients
        # No exception on empty list
        await _close_mcp_clients([])
