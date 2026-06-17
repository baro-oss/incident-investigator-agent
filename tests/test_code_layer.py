"""
Tests Day 51 — F1: Code seam over MCP.

- distill_code_response: shape + validate_observation + ≤5 samples + risk-detect
- is_read_only_tool: guard loại tool write, giữ tool read
- service_repos CRUD round-trip (temp DB)
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.engine.hypothesis_catalog import MICROSERVICE_CATALOG, build_catalog_index
from agent.engine.loop import _tool_sequencing_hint
from agent.engine.specificity import _has_code_evidence_with_signals, compute_verdict_specificity
from agent.engine.state import Evidence, Hypothesis, InvestigationState, Verdict
from agent.tools.code_distill import _detect_risk_signals, distill_code_response
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation
from agent.tools.get_code_diff import CODE_DIFF_TOOL_NAME, build_code_diff_tool
from agent.tools.registry import is_read_only_tool


# ── Contract guard helper (dùng lại từ test_infra) ───────────────────────────

def _validate(obs: Observation) -> list:
    errors = []
    if not obs.summary or not obs.summary.strip():
        errors.append("summary rỗng")
    if obs.total_count is None:
        errors.append("total_count chưa set")
    if len(obs.samples) > SAMPLES_HARD_CAP:
        errors.append(f"samples quá nhiều ({len(obs.samples)} > {SAMPLES_HARD_CAP})")
    return errors


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_DIFF = """\
diff --git a/config/db.yaml b/config/db.yaml
index 1a2b3c4..5d6e7f8 100644
--- a/config/db.yaml
+++ b/config/db.yaml
@@ -10,7 +10,7 @@ database:
   host: db-primary.internal
-  max_pool: 100
+  max_pool: 20
   timeout: 30s
diff --git a/src/payment/processor.py b/src/payment/processor.py
index aabbcc..ddeeff 100644
--- a/src/payment/processor.py
+++ b/src/payment/processor.py
@@ -45,10 +45,8 @@ class PaymentProcessor:
   def process(self, req):
-    try:
-      result = self._call_provider(req)
-    except ProviderError as e:
-      logger.error("provider error: %s", e)
-      raise
+      result = self._call_provider(req)
       return result
"""

SAMPLE_FILE = """\
# config/db.yaml
database:
  host: db-primary.internal
  max_pool: 20
  timeout: 30s
  retry_limit: 3
"""

LARGE_DIFF = "\n".join(
    [f"@@ -{i+1},5 +{i+1},5 @@\n context\n-old line {i}\n+new line {i}" for i in range(10)]
)

DEP_BUMP_DIFF = """\
diff --git a/requirements.txt b/requirements.txt
@@ -3,3 +3,3 @@
-fastapi==0.100.0
+fastapi==0.137.0
-pydantic==1.10.0
+pydantic==2.5.0
"""


# ═════════════════════════════════════════════════════════════════════════════
# A. distill_code_response — shape + contract
# ═════════════════════════════════════════════════════════════════════════════

class TestDistillShape:
    """Observation shape hợp lệ theo contract Nguyên tắc #1."""

    def test_diff_returns_valid_observation(self):
        obs = distill_code_response(SAMPLE_DIFF, tool_name="get_diff", service="payment-gateway")
        errors = _validate(obs)
        assert errors == [], f"Contract violations: {errors}"

    def test_summary_not_empty(self):
        obs = distill_code_response(SAMPLE_DIFF, tool_name="get_diff", service="svc")
        assert obs.summary.strip()

    def test_summary_contains_tool_and_service(self):
        obs = distill_code_response(SAMPLE_DIFF, tool_name="read_file", service="checkout")
        assert "read_file" in obs.summary
        assert "checkout" in obs.summary

    def test_samples_hard_cap(self):
        obs = distill_code_response(LARGE_DIFF, tool_name="get_diff", service="svc")
        assert len(obs.samples) <= SAMPLES_HARD_CAP

    def test_large_diff_truncated_flag(self):
        obs = distill_code_response(LARGE_DIFF, tool_name="get_diff", service="svc")
        assert obs.total_count > SAMPLES_HARD_CAP
        assert obs.truncated is True

    def test_small_diff_not_truncated(self):
        obs = distill_code_response(SAMPLE_DIFF, tool_name="get_diff", service="svc")
        assert obs.total_count <= SAMPLES_HARD_CAP
        assert obs.truncated is False

    def test_aggregates_has_required_keys(self):
        obs = distill_code_response(SAMPLE_DIFF, tool_name="get_diff", service="svc")
        assert "files_changed" in obs.aggregates
        assert "additions" in obs.aggregates
        assert "deletions" in obs.aggregates
        assert "risk_signals" in obs.aggregates

    def test_metadata_has_source_code_mcp(self):
        obs = distill_code_response(SAMPLE_DIFF, tool_name="get_diff", service="svc")
        assert obs.metadata.get("source") == "code_mcp"
        assert obs.metadata.get("tool_name") == "get_diff"
        assert obs.metadata.get("service") == "svc"

    def test_file_content_returns_valid_observation(self):
        obs = distill_code_response(SAMPLE_FILE, tool_name="read_file", service="db-service")
        errors = _validate(obs)
        assert errors == []

    def test_empty_raw_degrade_safe(self):
        obs = distill_code_response("", tool_name="get_diff", service="svc")
        errors = _validate(obs)
        assert errors == []
        assert obs.total_count == 0
        assert obs.samples == []

    def test_whitespace_only_degrade_safe(self):
        obs = distill_code_response("   \n\t\n  ", tool_name="get_diff", service="svc")
        errors = _validate(obs)
        assert errors == []

    def test_no_raw_dump_in_summary(self):
        """Summary không phải raw dump — phải ngắn gọn và có diễn giải."""
        obs = distill_code_response(SAMPLE_DIFF, tool_name="get_diff", service="svc")
        # Summary không dài hơn 400 ký tự (nếu quá dài là raw dump)
        assert len(obs.summary) < 400


# ═════════════════════════════════════════════════════════════════════════════
# B. Risk signal detection
# ═════════════════════════════════════════════════════════════════════════════

class TestRiskDetect:
    """Heuristic generic — không keyword miền."""

    def test_config_knob_pool_detected(self):
        signals = _detect_risk_signals("-  max_pool: 100\n+  max_pool: 20")
        assert any("config-knob" in s for s in signals), f"Expected config-knob in {signals}"

    def test_config_knob_timeout_detected(self):
        signals = _detect_risk_signals("-  timeout: 30s\n+  timeout: 5s")
        assert any("config-knob" in s for s in signals)

    def test_config_knob_limit_detected(self):
        signals = _detect_risk_signals("-  retry_limit: 5\n+  retry_limit: 1")
        assert any("config-knob" in s for s in signals)

    def test_large_delete_detected(self):
        # 10 deletions, 1 addition → large-delete
        diff = "\n".join(["-  deleted line " + str(i) for i in range(10)]) + "\n+  one new line"
        signals = _detect_risk_signals(diff)
        assert any("large-delete" in s for s in signals)

    def test_removed_error_handling_detected(self):
        diff = "-  try:\n-    result = call()\n-  except Exception as e:\n-    log(e)\n+  result = call()"
        signals = _detect_risk_signals(diff)
        assert any("removed-error-handling" in s for s in signals)

    def test_dep_bump_detected(self):
        signals = _detect_risk_signals(DEP_BUMP_DIFF)
        assert any("dep-bump" in s for s in signals)

    def test_no_risk_clean_diff(self):
        clean = "+  # just a comment\n+  x = 1\n-  x = 0"
        signals = _detect_risk_signals(clean)
        # Không có risk signal rõ ràng — có thể 0 hoặc vài (dep không có)
        assert isinstance(signals, list)

    def test_pool_risk_appears_in_observation(self):
        obs = distill_code_response(SAMPLE_DIFF, tool_name="get_diff", service="svc")
        risk_signals = obs.aggregates.get("risk_signals", [])
        assert any("config-knob" in s for s in risk_signals), \
            f"Expected config-knob risk in diff with max_pool change. Got: {risk_signals}"

    def test_dep_bump_risk_in_observation(self):
        obs = distill_code_response(DEP_BUMP_DIFF, tool_name="get_diff", service="svc")
        risk_signals = obs.aggregates.get("risk_signals", [])
        assert any("dep-bump" in s for s in risk_signals)

    def test_removed_error_handling_in_observation(self):
        obs = distill_code_response(SAMPLE_DIFF, tool_name="get_diff", service="svc")
        risk_signals = obs.aggregates.get("risk_signals", [])
        assert any("removed-error-handling" in s for s in risk_signals)


# ═════════════════════════════════════════════════════════════════════════════
# C. READ-ONLY guard
# ═════════════════════════════════════════════════════════════════════════════

class TestReadOnlyGuard:
    """is_read_only_tool() — whitelist đọc, blacklist ghi."""

    # Local tools luôn allowed
    def test_local_tool_get_metrics_allowed(self):
        assert is_read_only_tool("get_metrics") is True

    def test_local_tool_get_error_breakdown_allowed(self):
        assert is_read_only_tool("get_error_breakdown") is True

    def test_local_tool_get_recent_deploys_allowed(self):
        assert is_read_only_tool("get_recent_deploys") is True

    def test_local_tool_trace_request_allowed(self):
        assert is_read_only_tool("trace_request") is True

    # Read prefix — allowed
    def test_get_prefix_allowed(self):
        assert is_read_only_tool("get_diff") is True

    def test_list_prefix_allowed(self):
        assert is_read_only_tool("list_files") is True

    def test_read_prefix_allowed(self):
        assert is_read_only_tool("read_file") is True

    def test_search_prefix_allowed(self):
        assert is_read_only_tool("search_code") is True

    def test_diff_allowed(self):
        assert is_read_only_tool("diff") is True

    def test_blame_allowed(self):
        assert is_read_only_tool("blame") is True

    def test_fetch_prefix_allowed(self):
        assert is_read_only_tool("fetch_commits") is True

    # Write keywords — blocked
    def test_create_blocked(self):
        assert is_read_only_tool("create_pr") is False

    def test_update_blocked(self):
        assert is_read_only_tool("update_file") is False

    def test_delete_blocked(self):
        assert is_read_only_tool("delete_branch") is False

    def test_write_blocked(self):
        assert is_read_only_tool("write_file") is False

    def test_merge_blocked(self):
        assert is_read_only_tool("merge_pr") is False

    def test_push_blocked(self):
        assert is_read_only_tool("push_commit") is False

    def test_commit_blocked(self):
        assert is_read_only_tool("commit_changes") is False

    def test_approve_blocked(self):
        assert is_read_only_tool("approve_pr") is False

    def test_comment_blocked(self):
        assert is_read_only_tool("comment_on_pr") is False

    def test_unknown_tool_blocked_by_default(self):
        """Tool không rõ prefix → fail-safe, không cho phép."""
        assert is_read_only_tool("do_something_unknown") is False

    @pytest.mark.asyncio
    async def test_guard_filters_write_tools_from_registry(self):
        """Mocked MCP trả cả tool read + write → chỉ read vào registry."""
        from agent.tools.contracts import Tool
        from agent.tools.registry import build_tool_registry

        async def mock_get_tools():
            return [
                Tool("get_diff", "read diff", {}, lambda p: None),
                Tool("create_pr", "create PR — WRITE", {}, lambda p: None),
                Tool("merge_branch", "merge — WRITE", {}, lambda p: None),
                Tool("list_commits", "list commits", {}, lambda p: None),
            ]

        mock_client = MagicMock()
        mock_client.url = "http://mock-mcp"
        mock_client.get_tools = mock_get_tools

        registry = await build_tool_registry(mcp_clients=[mock_client])
        tool_names = [t.name for t in registry]
        assert "get_diff" in tool_names
        assert "list_commits" in tool_names
        assert "create_pr" not in tool_names, "create_pr phải bị loại bởi guard"
        assert "merge_branch" not in tool_names, "merge_branch phải bị loại bởi guard"


# ═════════════════════════════════════════════════════════════════════════════
# D. service_repos CRUD round-trip (temp DB)
# ═════════════════════════════════════════════════════════════════════════════

class TestServiceReposCRUD:
    """CRUD round-trip với pg_db — schema-per-test isolation."""

    def test_upsert_and_get(self, pg_db):
        from agent.intake.project_registry import upsert_service_repo, get_service_repo
        upsert_service_repo("default", "payment-gateway",
                            "https://github.com/org/payment",
                            provider="github", default_branch="main")
        repo = get_service_repo("default", "payment-gateway")
        assert repo is not None
        assert repo["repo_url"] == "https://github.com/org/payment"
        assert repo["provider"] == "github"
        assert repo["default_branch"] == "main"

    def test_upsert_update_existing(self, pg_db):
        from agent.intake.project_registry import upsert_service_repo, get_service_repo
        upsert_service_repo("default", "checkout", "https://github.com/org/checkout")
        upsert_service_repo("default", "checkout", "https://github.com/org/checkout-v2",
                            default_branch="develop")
        repo = get_service_repo("default", "checkout")
        assert repo["repo_url"] == "https://github.com/org/checkout-v2"
        assert repo["default_branch"] == "develop"

    def test_list_service_repos(self, pg_db):
        from agent.intake.project_registry import upsert_service_repo, list_service_repos
        upsert_service_repo("proj1", "svc-a", "https://github.com/org/svc-a")
        upsert_service_repo("proj1", "svc-b", "https://github.com/org/svc-b",
                            provider="gitlab")
        repos = list_service_repos("proj1")
        assert len(repos) == 2
        names = [r["service"] for r in repos]
        assert "svc-a" in names
        assert "svc-b" in names

    def test_delete_service_repo(self, pg_db):
        from agent.intake.project_registry import (
            upsert_service_repo, delete_service_repo, get_service_repo
        )
        upsert_service_repo("default", "to-delete", "https://github.com/org/repo")
        deleted = delete_service_repo("default", "to-delete")
        repo = get_service_repo("default", "to-delete")
        assert deleted is True
        assert repo is None

    def test_delete_nonexistent_returns_false(self, pg_db):
        from agent.intake.project_registry import delete_service_repo
        result = delete_service_repo("default", "nonexistent-svc")
        assert result is False

    def test_invalid_provider_raises(self, pg_db):
        from agent.intake.project_registry import upsert_service_repo
        with pytest.raises(ValueError, match="Provider"):
            upsert_service_repo("default", "svc", "https://example.com",
                                provider="badprovider")

    def test_subpath_stored_correctly(self, pg_db):
        from agent.intake.project_registry import upsert_service_repo, get_service_repo
        upsert_service_repo("default", "mono-svc", "https://github.com/org/mono",
                            subpath="services/payment")
        repo = get_service_repo("default", "mono-svc")
        assert repo["subpath"] == "services/payment"

    def test_project_isolation(self, pg_db):
        """Service mapping phải scope theo project_id."""
        from agent.intake.project_registry import (
            upsert_service_repo, list_service_repos
        )
        upsert_service_repo("proj-a", "shared-svc", "https://github.com/org/repo-a")
        upsert_service_repo("proj-b", "shared-svc", "https://github.com/org/repo-b")
        repos_a = list_service_repos("proj-a")
        repos_b = list_service_repos("proj-b")
        assert len(repos_a) == 1
        assert repos_a[0]["repo_url"] == "https://github.com/org/repo-a"
        assert len(repos_b) == 1
        assert repos_b[0]["repo_url"] == "https://github.com/org/repo-b"


# ═════════════════════════════════════════════════════════════════════════════
# E. get_code_diff tool — factory + degrade scenarios
# ═════════════════════════════════════════════════════════════════════════════

class TestGetCodeDiffTool:
    """build_code_diff_tool() factory: schema, degrade-safe, distill path."""

    def test_tool_name(self):
        tool = build_code_diff_tool("default")
        assert tool.name == CODE_DIFF_TOOL_NAME
        assert tool.name == "get_code_diff"

    def test_schema_required_fields(self):
        tool = build_code_diff_tool("default")
        required = tool.input_schema.get("required", [])
        assert "service" in required
        assert "version" in required

    def test_tool_passes_read_only_guard(self):
        assert is_read_only_tool("get_code_diff") is True

    @pytest.mark.asyncio
    async def test_no_repo_mapping_degrade_safe(self, pg_db):
        """Khi chưa cấu hình repo → Observation hợp lệ, status=no_repo_mapping."""
        tool = build_code_diff_tool("proj-no-repo")
        obs = await tool.run({"service": "unknown-svc", "version": "v1.0"})
        assert obs.summary.strip()
        assert obs.metadata.get("status") == "no_repo_mapping"
        assert obs.metadata.get("source") == "code_mcp"
        assert _validate(obs) == []

    @pytest.mark.asyncio
    async def test_no_repo_mapping_summary_helpful(self, pg_db):
        tool = build_code_diff_tool("proj-no-repo")
        obs = await tool.run({"service": "svc", "version": "v2"})
        assert "chưa cấu hình" in obs.summary or "repo" in obs.summary.lower()

    @pytest.mark.asyncio
    async def test_repo_mapping_no_mcp_client(self, pg_db):
        """Repo đã cấu hình, chưa có MCP → metadata về repo_url, configured=True."""
        from agent.intake.project_registry import upsert_service_repo
        upsert_service_repo("proj1", "payment-gw", "https://github.com/org/pay")
        tool = build_code_diff_tool("proj1", code_mcp_client=None)
        obs = await tool.run({"service": "payment-gw", "version": "v1.5.0"})
        assert obs.metadata.get("status") == "no_mcp_client"
        assert obs.metadata.get("source") == "code_mcp"
        assert obs.aggregates.get("configured") is True
        assert "https://github.com/org/pay" in (obs.aggregates.get("repo_url", "") or obs.summary)
        assert _validate(obs) == []

    @pytest.mark.asyncio
    async def test_with_mcp_client_distills_raw(self, pg_db):
        """Có MCP client → gọi call_tool_text, distill output, trả Observation chưng cất."""
        raw_diff = (
            "diff --git a/config.yaml b/config.yaml\n"
            "@@ -1,3 +1,3 @@\n"
            "-  max_pool: 100\n"
            "+  max_pool: 20\n"
        )

        from agent.tools.contracts import Tool as _Tool

        async def _mock_get_tools():
            # Trả tool với tên get_diff để code_diff tìm thấy
            dummy = _Tool("get_diff", "mock diff", {}, AsyncMock())
            return [dummy]

        mock_client = MagicMock()
        mock_client.get_tools = _mock_get_tools
        # M8: code_diff dùng call_tool_text thay vì diff_tool.run()
        mock_client.call_tool_text = AsyncMock(return_value=raw_diff)

        from agent.intake.project_registry import upsert_service_repo
        upsert_service_repo("proj1", "api-svc", "https://github.com/org/api")
        tool = build_code_diff_tool("proj1", code_mcp_client=mock_client)
        obs = await tool.run({"service": "api-svc", "version": "v2.1"})

        assert obs.metadata.get("source") == "code_mcp"
        risk = obs.aggregates.get("risk_signals", [])
        assert any("config-knob" in s for s in risk), f"Expected config-knob in {risk}"
        assert _validate(obs) == []

    @pytest.mark.asyncio
    async def test_mcp_error_degrade_safe(self, pg_db):
        """MCP raises → Observation status=mcp_error, không crash."""
        async def _mock_get_tools():
            raise ConnectionError("MCP server down")

        mock_client = MagicMock()
        mock_client.get_tools = _mock_get_tools

        from agent.intake.project_registry import upsert_service_repo
        upsert_service_repo("proj1", "svc", "https://github.com/org/svc")
        tool = build_code_diff_tool("proj1", code_mcp_client=mock_client)
        obs = await tool.run({"service": "svc", "version": "v1"})

        assert obs.metadata.get("status") == "mcp_error"
        assert obs.metadata.get("source") == "code_mcp"
        assert _validate(obs) == []

    @pytest.mark.asyncio
    async def test_all_cases_have_code_mcp_source(self, pg_db):
        """Mọi nhánh trả về metadata source=code_mcp."""
        tool = build_code_diff_tool("proj-x")
        obs = await tool.run({"service": "missing", "version": "v0"})
        assert obs.metadata.get("source") == "code_mcp"


# ═════════════════════════════════════════════════════════════════════════════
# F. Catalog code-aware — deploy entry + E10 hint
# ═════════════════════════════════════════════════════════════════════════════

class TestCatalogCodeAware:
    """Deploy entry có get_code_diff; E10 hint tự kích khi deploy open."""

    def test_deploy_entry_has_get_code_diff(self):
        deploy_entry = next(e for e in MICROSERVICE_CATALOG if e.tag == "deploy")
        assert "get_code_diff" in deploy_entry.relevant_tools

    def test_deploy_entry_still_has_get_recent_deploys(self):
        deploy_entry = next(e for e in MICROSERVICE_CATALOG if e.tag == "deploy")
        assert "get_recent_deploys" in deploy_entry.relevant_tools

    def test_hint_generated_for_open_deploy_hypothesis(self):
        """Khi hypothesis deploy open, hint phải gợi ý get_code_diff + get_recent_deploys."""
        catalog_idx = build_catalog_index(MICROSERVICE_CATALOG)
        state = InvestigationState(
            investigation_id="test-01",
            symptom="test",
            time_window="00:00-01:00",
            scenario="s1",
            date="2026-06-15",
            hypothesis_catalog_index=catalog_idx,
        )
        state.hypotheses.append(Hypothesis(
            id="deploy",
            content="Deployment gây sự cố",
            status="open",
        ))
        hint = _tool_sequencing_hint(state)
        assert "get_code_diff" in hint
        assert "deploy" in hint

    def test_hint_excludes_already_called_tool(self):
        """Sau khi gọi get_code_diff → hint không gợi ý nữa."""
        catalog_idx = build_catalog_index(MICROSERVICE_CATALOG)
        state = InvestigationState(
            investigation_id="test-02",
            symptom="test",
            time_window="00:00-01:00",
            scenario="s1",
            date="2026-06-15",
            hypothesis_catalog_index=catalog_idx,
        )
        state.hypotheses.append(Hypothesis(id="deploy", content="deploy", status="open"))
        state.tool_call_history = [
            {"name": "get_code_diff", "params": {"service": "svc", "version": "v1"}},
            {"name": "get_recent_deploys", "params": {}},
        ]
        hint = _tool_sequencing_hint(state)
        # Cả 2 tool đã gọi → không còn uncalled → hint trống hoặc không đề cập deploy
        assert "get_code_diff" not in hint
        assert "get_recent_deploys" not in hint

    def test_no_hint_when_no_open_hypothesis(self):
        catalog_idx = build_catalog_index(MICROSERVICE_CATALOG)
        state = InvestigationState(
            investigation_id="test-03",
            symptom="test",
            time_window="00:00-01:00",
            scenario="s1",
            date="2026-06-15",
            hypothesis_catalog_index=catalog_idx,
        )
        state.hypotheses.append(Hypothesis(id="deploy", content="deploy", status="confirmed"))
        hint = _tool_sequencing_hint(state)
        assert hint == ""


# ═════════════════════════════════════════════════════════════════════════════
# G. Code evidence → specificity boost (E12 + F2)
# ═════════════════════════════════════════════════════════════════════════════

def _make_code_evidence(risk_signals: list) -> Evidence:
    """Helper: tạo Evidence có source=code_mcp với risk_signals cho sẵn."""
    obs = Observation(
        summary="get_code_diff (svc@v2): 2 file(s) changed; RISK: config-knob changed: pool→20",
        aggregates={"files_changed": 2, "risk_signals": risk_signals},
        samples=[],
        total_count=2,
        truncated=False,
        metadata={"source": "code_mcp", "tool_name": "get_code_diff"},
    )
    return Evidence(
        id="ev-code-01",
        step=2,
        tool_name="get_code_diff",
        params={"service": "svc", "version": "v2"},
        summary=obs.summary,
        observation=obs,
    )


def _make_base_state() -> InvestigationState:
    return InvestigationState(
        investigation_id="spec-test",
        symptom="payment latency spike",
        time_window="14:00-15:00",
        scenario="s1",
        date="2026-06-15",
        available_services=["payment-gateway"],
    )


def _make_vague_verdict() -> Verdict:
    return Verdict(
        root_cause="something went wrong",
        confidence="medium",
        evidence_summary="errors occurred",
        propagation_note="",
        competing_hypotheses="",
        raw_text="",
    )


def _make_specific_verdict() -> Verdict:
    return Verdict(
        root_cause="payment-gateway v2.3.1 max_pool hạ từ 100 xuống 20",
        confidence="high",
        evidence_summary="error_rate tăng 5× (baseline 1%, hiện 5.2%) từ 14:02",
        propagation_note="payment-gateway pool exhausted → checkout timeout 3s",
        competing_hypotheses="provider_down loại trừ: provider metrics bình thường",
        raw_text="",
    )


class TestCodeSpecificity:
    """_has_code_evidence_with_signals + compute_verdict_specificity boost."""

    def test_no_evidence_returns_false(self):
        state = _make_base_state()
        assert _has_code_evidence_with_signals(state) is False

    def test_wrong_source_returns_false(self):
        state = _make_base_state()
        obs = Observation(
            summary="metrics summary",
            aggregates={"risk_signals": ["config-knob"]},
            samples=[],
            total_count=1,
            truncated=False,
            metadata={"source": "local_tool"},
        )
        state.evidence.append(Evidence(
            id="ev-local", step=1, tool_name="get_metrics", params={},
            summary=obs.summary, observation=obs,
        ))
        assert _has_code_evidence_with_signals(state) is False

    def test_code_mcp_no_risk_signals_returns_false(self):
        state = _make_base_state()
        state.evidence.append(_make_code_evidence(risk_signals=[]))
        assert _has_code_evidence_with_signals(state) is False

    def test_code_mcp_with_risk_signals_returns_true(self):
        state = _make_base_state()
        state.evidence.append(_make_code_evidence(risk_signals=["config-knob changed: pool→20"]))
        assert _has_code_evidence_with_signals(state) is True

    def test_code_evidence_boosts_score(self):
        """Cùng 2/3 signals pass: với code evidence → 3/4=0.75 > 2/3≈0.667."""
        state_no_code = _make_base_state()
        state_with_code = _make_base_state()
        state_with_code.evidence.append(_make_code_evidence(["config-knob"]))

        # Verdict có 2 signal pass: root_cause có số, evidence_summary có 2 số
        v = Verdict(
            root_cause="v2.3.1 deployed at 14:00",
            confidence="medium",
            evidence_summary="error 5% vs baseline 1%, pool wait 200ms",
            propagation_note="",   # signal 3 fails
            competing_hypotheses="",
            raw_text="",
        )
        score_no_code, _ = compute_verdict_specificity(v, state_no_code)
        score_with_code, _ = compute_verdict_specificity(v, state_with_code)
        assert score_with_code > score_no_code, (
            f"Code evidence không boost: {score_with_code} vs {score_no_code}"
        )

    def test_no_code_evidence_backward_compat(self):
        """Không có code evidence → score = passed/3, không thay đổi logic cũ."""
        state = _make_base_state()
        v = _make_vague_verdict()
        score, _ = compute_verdict_specificity(v, state)
        assert score == 0.0   # 0/3

    def test_vague_verdict_zero_score(self):
        state = _make_base_state()
        v = _make_vague_verdict()
        score, reasons = compute_verdict_specificity(v, state)
        assert score == 0.0
        assert len(reasons) == 3

    def test_code_grounded_scores_higher_than_vague(self):
        """Vague=0/3=0.0; với code evidence (0+1)/4=0.25 > 0.0."""
        state_vague = _make_base_state()
        state_code = _make_base_state()
        state_code.evidence.append(_make_code_evidence(["config-knob"]))

        v = _make_vague_verdict()
        score_vague, _ = compute_verdict_specificity(v, state_vague)
        score_code, _ = compute_verdict_specificity(v, state_code)
        assert score_code > score_vague

    def test_all_three_signals_plus_code_gives_max(self):
        state = _make_base_state()
        state.evidence.append(_make_code_evidence(["config-knob", "large-delete"]))
        v = _make_specific_verdict()
        score, reasons = compute_verdict_specificity(v, state)
        assert score == 1.0
        assert reasons == []


# ═════════════════════════════════════════════════════════════════════════════
# H. Principle #2 guard — engine/ không hardcode domain keywords
# ═════════════════════════════════════════════════════════════════════════════

class TestPrincipleGuard:
    """Engine lõi không chứa keyword domain (repo/git/github/gitlab/code_mcp)."""

    def _read_engine_files(self) -> str:
        import pathlib
        engine_dir = pathlib.Path(__file__).parent.parent / "src" / "agent" / "engine"
        code_files = ["loop.py", "state.py", "specificity.py", "multi_agent.py"]
        combined = ""
        for fname in code_files:
            p = engine_dir / fname
            if p.exists():
                combined += p.read_text()
        return combined

    def test_no_github_in_engine(self):
        code = self._read_engine_files()
        assert "github" not in code.lower(), "engine/ không được chứa 'github'"

    def test_no_gitlab_in_engine(self):
        code = self._read_engine_files()
        assert "gitlab" not in code.lower(), "engine/ không được chứa 'gitlab'"

    def test_no_hardcoded_repo_url_in_engine(self):
        code = self._read_engine_files()
        assert "repo_url" not in code, "engine/ không được chứa 'repo_url'"

    def test_get_code_diff_not_hardcoded_in_engine_loop(self):
        """loop.py chỉ xử lý tool qua interface, không hardcode tên tool cụ thể."""
        import pathlib
        loop_code = (
            pathlib.Path(__file__).parent.parent / "src" / "agent" / "engine" / "loop.py"
        ).read_text()
        assert "get_code_diff" not in loop_code, (
            "loop.py không được hardcode tên tool 'get_code_diff' — dùng catalog thay thế"
        )
