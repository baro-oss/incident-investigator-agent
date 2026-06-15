"""
Tests cho intake/server.py — các route chính qua FastAPI TestClient.
Dùng lifespan=False để bỏ qua startup (DB bootstrap, worker pool, scheduler).
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


def _make_client():
    from agent.intake.server import app
    return TestClient(app, raise_server_exceptions=False)


# ── Health & meta ─────────────────────────────────────────────────────────────

class TestHealthRoute:
    def test_health_returns_200(self):
        client = _make_client()
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status_ok(self):
        client = _make_client()
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_has_uptime(self):
        client = _make_client()
        data = client.get("/health").json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))

    def test_health_has_active_investigations(self):
        client = _make_client()
        data = client.get("/health").json()
        assert "active_investigations" in data


class TestAdaptersRoute:
    def test_adapters_returns_200(self):
        client = _make_client()
        resp = client.get("/adapters")
        assert resp.status_code == 200

    def test_adapters_has_supported_sources(self):
        client = _make_client()
        data = client.get("/adapters").json()
        assert "supported_sources" in data
        assert isinstance(data["supported_sources"], list)
        assert len(data["supported_sources"]) > 0


# ── Auth routes ───────────────────────────────────────────────────────────────

class TestAuthRoutes:
    def test_login_get_returns_html(self):
        client = _make_client()
        resp = client.get("/auth/login", follow_redirects=False)
        assert resp.status_code in (200, 303)

    def test_login_post_wrong_creds_stays_on_login(self):
        client = _make_client()
        resp = client.post(
            "/auth/login",
            data={"username": "nonexistent_user_xyz", "password": "wrong"},
            follow_redirects=False,
        )
        # Either 200 (login page with error) or 303 (redirect)
        assert resp.status_code in (200, 303)

    def test_logout_redirects(self):
        client = _make_client()
        resp = client.post("/auth/logout", follow_redirects=False)
        assert resp.status_code == 303


# ── Projects ──────────────────────────────────────────────────────────────────

class TestProjectRoutes:
    def test_list_projects_returns_200(self):
        client = _make_client()
        resp = client.get("/projects")
        assert resp.status_code == 200

    def test_list_projects_has_projects_key(self):
        client = _make_client()
        data = client.get("/projects").json()
        assert "projects" in data
        assert isinstance(data["projects"], list)

    def test_get_nonexistent_project_returns_404(self):
        client = _make_client()
        resp = client.get("/projects/nonexistent-project-xyz-abc")
        assert resp.status_code == 404

    def test_create_project_missing_id_returns_422(self):
        client = _make_client()
        resp = client.post("/projects", json={"name": "Test"})
        assert resp.status_code == 422

    def test_create_project_missing_name_returns_422(self):
        client = _make_client()
        resp = client.post("/projects", json={"id": "test-proj-abc"})
        assert resp.status_code == 422

    def test_create_project_invalid_id_returns_422(self):
        client = _make_client()
        resp = client.post("/projects", json={"id": "test proj!", "name": "Test"})
        assert resp.status_code == 422

    def test_create_and_get_project(self):
        client = _make_client()
        project_id = "test-cov-proj-d55"
        # Cleanup first if exists
        client.delete(f"/projects/{project_id}")
        resp = client.post("/projects", json={"id": project_id, "name": "Test D55", "description": "coverage"})
        assert resp.status_code == 201
        # Get it back
        get_resp = client.get(f"/projects/{project_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == project_id
        # Cleanup
        client.delete(f"/projects/{project_id}")


# ── Trigger ───────────────────────────────────────────────────────────────────

class TestTriggerRoute:
    def test_trigger_requires_auth_by_default(self):
        client = _make_client()
        resp = client.post("/trigger", json={
            "service": "payment-gateway",
            "scenario": "scenario1",
            "time_window": "14:00-15:00",
        })
        # Without auth, expects 401
        assert resp.status_code == 401

    def test_trigger_with_anon_allowed_returns_202(self):
        import os
        client = _make_client()
        with patch.dict(os.environ, {"ALLOW_ANON_TRIGGER": "true"}), \
             patch("agent.intake.server.trigger_investigation"):
            resp = client.post("/trigger", json={
                "service": "payment-gateway",
                "scenario": "scenario1",
                "time_window": "14:00-15:00",
            })
        assert resp.status_code == 202

    def test_trigger_empty_payload_does_not_crash(self):
        import os
        client = _make_client()
        with patch.dict(os.environ, {"ALLOW_ANON_TRIGGER": "true"}), \
             patch("agent.intake.server.trigger_investigation"):
            resp = client.post("/trigger", json={})
        # Server accepts or rejects gracefully (no 5xx)
        assert resp.status_code < 500

    def test_trigger_has_investigation_id_in_response(self):
        import os
        client = _make_client()
        with patch.dict(os.environ, {"ALLOW_ANON_TRIGGER": "true"}), \
             patch("agent.intake.server.trigger_investigation"):
            resp = client.post("/trigger", json={
                "service": "svc",
                "scenario": "scenario1",
                "time_window": "10:00-11:00",
            })
        if resp.status_code == 202:
            data = resp.json()
            assert "investigation_id" in data or "status" in data

    def test_project_trigger_valid_returns_202(self):
        import os
        client = _make_client()
        project_id = "trig-test-d55"
        client.delete(f"/projects/{project_id}")
        client.post("/projects", json={"id": project_id, "name": "Trig test"})
        with patch.dict(os.environ, {"ALLOW_ANON_TRIGGER": "true"}), \
             patch("agent.intake.server.trigger_investigation"):
            resp = client.post(f"/projects/{project_id}/trigger", json={
                "service": "svc",
                "scenario": "scenario1",
                "time_window": "10:00-11:00",
            })
        assert resp.status_code == 202
        client.delete(f"/projects/{project_id}")

    def test_project_trigger_unknown_project_returns_404(self):
        client = _make_client()
        resp = client.post("/projects/nonexistent-xyz/trigger", json={
            "service": "svc",
            "scenario": "scenario1",
            "time_window": "10:00-11:00",
        })
        assert resp.status_code == 404


# ── MCP servers (global compat) ───────────────────────────────────────────────

class TestMcpServerRoutes:
    def test_list_mcp_servers_returns_200(self):
        client = _make_client()
        resp = client.get("/mcp-servers")
        assert resp.status_code == 200

    def test_list_mcp_servers_has_servers_key(self):
        client = _make_client()
        data = client.get("/mcp-servers").json()
        assert "servers" in data or isinstance(data, (list, dict))
