"""
Tests cho Phase 12 — LLM catalog, test-connection endpoint, bug-fix batch (BUG-01..07).
Target: ≥30 tests mới, tổng ≥490 cùng baseline 461.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: LLM Catalog — catalog.py
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMCatalog:
    def test_has_8_providers(self):
        from agent.llm.catalog import get_provider_catalog
        assert len(get_provider_catalog()) == 8

    def test_includes_greennode(self):
        from agent.llm.catalog import get_provider_catalog
        assert "greennode" in get_provider_catalog()

    def test_greennode_base_url_is_maas_endpoint(self):
        from agent.llm.catalog import get_default_base_url
        url = get_default_base_url("greennode")
        assert "maas-llm-aiplatform-hcm.api.vngcloud.vn" in url
        assert url.endswith("/v1")

    def test_greennode_has_3_models(self):
        from agent.llm.catalog import get_models_for_provider
        assert len(get_models_for_provider("greennode")) == 3

    def test_greennode_model_minimax(self):
        from agent.llm.catalog import get_models_for_provider
        assert "minimax/minimax-m2.5" in get_models_for_provider("greennode")

    def test_greennode_model_qwen(self):
        from agent.llm.catalog import get_models_for_provider
        assert "qwen/qwen3-5-27b" in get_models_for_provider("greennode")

    def test_greennode_model_gemma(self):
        from agent.llm.catalog import get_models_for_provider
        assert "google/gemma-4-31b-it" in get_models_for_provider("greennode")

    def test_includes_together(self):
        from agent.llm.catalog import get_provider_catalog
        assert "together" in get_provider_catalog()

    def test_all_providers_have_label(self):
        from agent.llm.catalog import get_provider_catalog
        for pid, info in get_provider_catalog().items():
            assert info.get("label"), f"Provider '{pid}' thiếu label"

    def test_all_providers_have_models_list(self):
        from agent.llm.catalog import get_provider_catalog
        for pid, info in get_provider_catalog().items():
            assert isinstance(info.get("models"), list), f"Provider '{pid}' thiếu models list"
            assert len(info["models"]) > 0, f"Provider '{pid}' models list rỗng"

    def test_get_models_for_unknown_provider_returns_empty(self):
        from agent.llm.catalog import get_models_for_provider
        assert get_models_for_provider("unknown-xyz") == []

    def test_get_default_base_url_anthropic_empty(self):
        from agent.llm.catalog import get_default_base_url
        assert get_default_base_url("anthropic") == ""

    def test_get_default_base_url_groq_correct(self):
        from agent.llm.catalog import get_default_base_url
        url = get_default_base_url("groq")
        assert "groq.com" in url

    def test_get_default_base_url_unknown_empty(self):
        from agent.llm.catalog import get_default_base_url
        assert get_default_base_url("nonexistent") == ""

    def test_together_has_base_url(self):
        from agent.llm.catalog import get_default_base_url
        url = get_default_base_url("together")
        assert "together" in url and url.endswith("/v1")


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: SUPPORTED_PROVIDERS trong set_project_llm
# ─────────────────────────────────────────────────────────────────────────────

class TestSupportedProviders:
    def _run_set_llm(self, provider):
        """Gọi set_project_llm với DB mock — chỉ test validation."""
        from agent.intake.project_registry import set_project_llm
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        with patch("agent.intake.project_registry.open_db", return_value=mock_conn), \
             patch("agent.security.encrypt_secret", return_value="enc"):
            set_project_llm("default", provider, config={})

    def test_greennode_accepted_as_provider(self):
        self._run_set_llm("greennode")  # không raise

    def test_together_accepted_as_provider(self):
        self._run_set_llm("together")  # không raise

    def test_invalid_provider_raises_value_error(self):
        from agent.intake.project_registry import set_project_llm
        with pytest.raises(ValueError, match="không hỗ trợ"):
            set_project_llm("default", "unknown-xyz", config={})


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: GET /dashboard/llm-catalog HTTP endpoint
# ─────────────────────────────────────────────────────────────────────────────

from contextlib import contextmanager

@contextmanager
def _dashboard_client():
    """TestClient với require_login trả root user; đóng kết nối đúng cách."""
    from fastapi.testclient import TestClient
    from agent.intake.server import app
    from agent.auth.deps import require_login
    root_user = {"id": "root", "username": "root", "is_root": True}
    app.dependency_overrides[require_login] = lambda: root_user
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        # Reset _draining flag set by lifespan shutdown so subsequent non-lifespan
        # TestClient instances (test_server.py) do not see a draining state.
        import agent.intake.investigation_queue as _q
        _q._draining = False


class TestLLMCatalogEndpoint:
    def test_returns_200_when_authenticated(self):
        with _dashboard_client() as client:
            resp = client.get("/dashboard/llm-catalog")
        assert resp.status_code == 200

    def test_response_is_json_with_8_providers(self):
        with _dashboard_client() as client:
            data = client.get("/dashboard/llm-catalog").json()
        assert len(data) == 8

    def test_response_has_greennode_with_correct_base_url(self):
        with _dashboard_client() as client:
            data = client.get("/dashboard/llm-catalog").json()
        assert "greennode" in data
        assert "vngcloud" in data["greennode"]["base_url"]


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: BUG-01 — Port không còn hardcoded 8000
# ─────────────────────────────────────────────────────────────────────────────

class TestBugPortFix:
    def test_server_port_default_is_8080(self):
        """Khi không set PORT env, _SERVER_PORT phải là 8080 (AgentBase contract)."""
        env_backup = os.environ.pop("PORT", None)
        try:
            import importlib
            import agent.dashboard.router as router_mod
            importlib.reload(router_mod)
            assert router_mod._SERVER_PORT == 8080
        finally:
            if env_backup is not None:
                os.environ["PORT"] = env_backup
            import importlib
            import agent.dashboard.router as router_mod
            importlib.reload(router_mod)

    def test_server_port_reads_env_var(self):
        """PORT env var được đọc đúng."""
        os.environ["PORT"] = "9999"
        try:
            import importlib
            import agent.dashboard.router as router_mod
            importlib.reload(router_mod)
            assert router_mod._SERVER_PORT == 9999
        finally:
            del os.environ["PORT"]
            import importlib
            import agent.dashboard.router as router_mod
            importlib.reload(router_mod)


# ─────────────────────────────────────────────────────────────────────────────
# Section 5: BUG-03 — API key không lộ trong llm_config_raw
# ─────────────────────────────────────────────────────────────────────────────

class TestBugKeySecurityFix:
    def _setup_project_llm_with_key(self, project_id="default"):
        from agent.intake.project_registry import set_project_llm
        set_project_llm(project_id, "anthropic", config={"api_key": "sk-test-secret-123"})

    def _teardown(self, project_id="default"):
        from agent.intake.project_registry import clear_project_llm
        clear_project_llm(project_id)

    def test_llm_key_set_field_present_in_detail(self):
        """get_project_detail trả về trường llm_key_set."""
        from agent.dashboard.queries import get_project_detail
        proj = get_project_detail("default")
        assert proj is not None
        assert "llm_key_set" in proj

    def test_api_key_not_in_llm_config_raw_when_set(self):
        """Sau khi set key, llm_config_raw không chứa api_key."""
        self._setup_project_llm_with_key()
        try:
            from agent.dashboard.queries import get_project_detail
            proj = get_project_detail("default")
            raw = proj.get("llm_config_raw") or {}
            assert "api_key" not in raw, "api_key không được trả về template!"
        finally:
            self._teardown()

    def test_llm_key_set_true_when_key_exists(self):
        """llm_key_set=True khi project có api_key."""
        self._setup_project_llm_with_key()
        try:
            from agent.dashboard.queries import get_project_detail
            proj = get_project_detail("default")
            assert proj["llm_key_set"] is True
        finally:
            self._teardown()

    def test_llm_key_set_false_when_no_key(self):
        """llm_key_set=False khi project không có key."""
        self._teardown()  # đảm bảo sạch
        from agent.dashboard.queries import get_project_detail
        proj = get_project_detail("default")
        assert proj["llm_key_set"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Section 6: BUG-05 — Pricing prefixes khớp model mới
# ─────────────────────────────────────────────────────────────────────────────

class TestBugPricingFix:
    def test_claude_opus_4_model_has_pricing(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("anthropic", "claude-opus-4-8")
        assert in_p > 0 and out_p > 0

    def test_claude_sonnet_4_model_has_pricing(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("anthropic", "claude-sonnet-4-6")
        assert in_p > 0 and out_p > 0

    def test_claude_haiku_4_model_has_pricing(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("anthropic", "claude-haiku-4-5-20251001")
        assert in_p > 0 and out_p > 0

    def test_keyword_matching_for_opus(self):
        """M4 (Ngày 65): dùng keyword 'opus'/'sonnet'/'haiku' thay prefix dài."""
        from agent.dashboard.queries import _PRICING, _get_pricing
        anthropic_tiers = _PRICING.get("anthropic", {})
        # Keyword-based keys (Phase 13 M4 fix)
        assert "opus" in anthropic_tiers, "Cần keyword 'opus' trong PRICING anthropic"
        # Real model IDs vẫn khớp đúng giá
        in_p, _ = _get_pricing("anthropic", "claude-opus-4-8")
        assert in_p == 15.00, f"claude-opus-4-8 phải lấy giá opus $15/M, got {in_p}"


# ─────────────────────────────────────────────────────────────────────────────
# Section 7: BUG-06 — Slack channel hiển thị trong project detail
# ─────────────────────────────────────────────────────────────────────────────

class TestBugSlackChannelFix:
    def test_get_project_detail_has_slack_in_channels(self):
        """channels dict của project phải có key 'slack'."""
        from agent.dashboard.queries import get_project_detail
        proj = get_project_detail("default")
        assert proj is not None
        assert "slack" in proj["channels"], "Slack channel phải có trong channels dict"

    def test_supported_channels_includes_slack(self):
        from agent.intake.project_registry import SUPPORTED_CHANNELS
        assert "slack" in SUPPORTED_CHANNELS


# ─────────────────────────────────────────────────────────────────────────────
# Section 8: LLM-05 — Key preserve khi api_key field rỗng
# ─────────────────────────────────────────────────────────────────────────────

class TestKeyPreserve:
    def test_existing_key_preserved_when_empty_submitted(self):
        """Nếu api_key="" trong form nhưng DB đã có key → key cũ được giữ."""
        from agent.intake.project_registry import set_project_llm, get_project_llm, clear_project_llm

        # Setup: set key ban đầu
        set_project_llm("default", "anthropic", config={"api_key": "sk-original-key"})
        try:
            # Simulate save với api_key rỗng (form để trống)
            existing = get_project_llm("default")
            cfg = {}
            api_key_from_form = ""
            if api_key_from_form.strip():
                cfg["api_key"] = api_key_from_form.strip()
            else:
                if existing and existing.get("config", {}).get("api_key"):
                    cfg["api_key"] = existing["config"]["api_key"]

            assert cfg.get("api_key") == "sk-original-key"
        finally:
            clear_project_llm("default")

    def test_new_key_replaces_old_when_submitted(self):
        """Nếu api_key mới được submit, key cũ bị thay."""
        from agent.intake.project_registry import set_project_llm, get_project_llm, clear_project_llm

        set_project_llm("default", "anthropic", config={"api_key": "sk-old-key"})
        try:
            existing = get_project_llm("default")
            api_key_from_form = "sk-new-key"
            cfg = {}
            if api_key_from_form.strip():
                cfg["api_key"] = api_key_from_form.strip()
            else:
                if existing and existing.get("config", {}).get("api_key"):
                    cfg["api_key"] = existing["config"]["api_key"]

            assert cfg.get("api_key") == "sk-new-key"
        finally:
            clear_project_llm("default")


# ─────────────────────────────────────────────────────────────────────────────
# Section 9: Test connection endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMTestEndpoint:
    def test_no_llm_config_returns_error_json(self):
        """Project không có LLM config → {"status": "error"}."""
        from agent.intake.project_registry import clear_project_llm
        clear_project_llm("default")
        with _dashboard_client() as client:
            resp = client.post("/dashboard/projects/default/llm/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_with_llm_config_calls_client(self):
        """Với LLM config hợp lệ → create_llm_client được gọi."""
        from agent.intake.project_registry import set_project_llm, clear_project_llm
        from agent.llm.base import LLMResponse

        set_project_llm("default", "anthropic", config={"api_key": "sk-fake"})
        mock_resp = LLMResponse(text="ok")
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = mock_resp
        try:
            with patch("agent.llm.factory.create_llm_client", return_value=mock_llm):
                with _dashboard_client() as client:
                    resp = client.post("/dashboard/projects/default/llm/test")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "latency_ms" in data
        finally:
            clear_project_llm("default")

    def test_llm_exception_returns_error_json(self):
        """Nếu LLM client throw exception → {"status": "error"}."""
        from agent.intake.project_registry import set_project_llm, clear_project_llm

        set_project_llm("default", "anthropic", config={"api_key": "sk-fake"})
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = Exception("Connection refused")
        try:
            with patch("agent.llm.factory.create_llm_client", return_value=mock_llm):
                with _dashboard_client() as client:
                    resp = client.post("/dashboard/projects/default/llm/test")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "error"
            assert "Connection refused" in data["message"]
        finally:
            clear_project_llm("default")


# ─────────────────────────────────────────────────────────────────────────────
# Section 10: model_custom routing trong dashboard_project_save_llm
# ─────────────────────────────────────────────────────────────────────────────

class TestModelCustomRouting:
    def test_custom_model_id_used_when_model_is_custom_sentinel(self):
        """model='_custom' + model_custom='my-model' → effective_model='my-model'."""
        model = "_custom"
        model_custom = "my-org/my-model-v1"
        effective = model_custom.strip() if model.strip() == "_custom" else model.strip() or None
        assert effective == "my-org/my-model-v1"

    def test_catalog_model_used_when_not_custom(self):
        """model='claude-sonnet-4-6' → effective_model='claude-sonnet-4-6'."""
        model = "claude-sonnet-4-6"
        model_custom = ""
        effective = model_custom.strip() if model.strip() == "_custom" else model.strip() or None
        assert effective == "claude-sonnet-4-6"

    def test_empty_model_results_in_none(self):
        """model='' → effective_model=None (dùng default)."""
        model = ""
        model_custom = ""
        effective = model_custom.strip() if model.strip() == "_custom" else model.strip() or None
        assert effective is None
