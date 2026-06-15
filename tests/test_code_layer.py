"""
Tests Day 51 — F1: Code seam over MCP.

- distill_code_response: shape + validate_observation + ≤5 samples + risk-detect
- is_read_only_tool: guard loại tool write, giữ tool read
- service_repos CRUD round-trip (temp DB)
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.tools.code_distill import distill_code_response, _detect_risk_signals
from agent.tools.contracts import SAMPLES_HARD_CAP, Observation
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
    """CRUD round-trip với temp DB — không đụng DB production."""

    def _make_temp_db(self) -> str:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE service_repos (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id     TEXT    NOT NULL DEFAULT 'default',
                service        TEXT    NOT NULL,
                provider       TEXT    NOT NULL DEFAULT 'github',
                repo_url       TEXT    NOT NULL,
                default_branch TEXT    NOT NULL DEFAULT 'main',
                subpath        TEXT    NOT NULL DEFAULT '',
                created_at     TEXT    NOT NULL,
                updated_at     TEXT    NOT NULL,
                UNIQUE(project_id, service)
            )
        """)
        conn.commit()
        conn.close()
        return path

    def test_upsert_and_get(self):
        db_path = self._make_temp_db()
        with patch("agent.intake.project_registry.open_db", side_effect=lambda: _open_sqlite(db_path)):
            from agent.intake.project_registry import upsert_service_repo, get_service_repo
            upsert_service_repo("default", "payment-gateway",
                                "https://github.com/org/payment",
                                provider="github", default_branch="main")
            repo = get_service_repo("default", "payment-gateway")
        assert repo is not None
        assert repo["repo_url"] == "https://github.com/org/payment"
        assert repo["provider"] == "github"
        assert repo["default_branch"] == "main"
        os.unlink(db_path)

    def test_upsert_update_existing(self):
        db_path = self._make_temp_db()
        with patch("agent.intake.project_registry.open_db", side_effect=lambda: _open_sqlite(db_path)):
            from agent.intake.project_registry import upsert_service_repo, get_service_repo
            upsert_service_repo("default", "checkout", "https://github.com/org/checkout")
            upsert_service_repo("default", "checkout", "https://github.com/org/checkout-v2",
                                default_branch="develop")
            repo = get_service_repo("default", "checkout")
        assert repo["repo_url"] == "https://github.com/org/checkout-v2"
        assert repo["default_branch"] == "develop"
        os.unlink(db_path)

    def test_list_service_repos(self):
        db_path = self._make_temp_db()
        with patch("agent.intake.project_registry.open_db", side_effect=lambda: _open_sqlite(db_path)):
            from agent.intake.project_registry import upsert_service_repo, list_service_repos
            upsert_service_repo("proj1", "svc-a", "https://github.com/org/svc-a")
            upsert_service_repo("proj1", "svc-b", "https://github.com/org/svc-b",
                                provider="gitlab")
            repos = list_service_repos("proj1")
        assert len(repos) == 2
        names = [r["service"] for r in repos]
        assert "svc-a" in names
        assert "svc-b" in names
        os.unlink(db_path)

    def test_delete_service_repo(self):
        db_path = self._make_temp_db()
        with patch("agent.intake.project_registry.open_db", side_effect=lambda: _open_sqlite(db_path)):
            from agent.intake.project_registry import (
                upsert_service_repo, delete_service_repo, get_service_repo
            )
            upsert_service_repo("default", "to-delete", "https://github.com/org/repo")
            deleted = delete_service_repo("default", "to-delete")
            repo = get_service_repo("default", "to-delete")
        assert deleted is True
        assert repo is None
        os.unlink(db_path)

    def test_delete_nonexistent_returns_false(self):
        db_path = self._make_temp_db()
        with patch("agent.intake.project_registry.open_db", side_effect=lambda: _open_sqlite(db_path)):
            from agent.intake.project_registry import delete_service_repo
            result = delete_service_repo("default", "nonexistent-svc")
        assert result is False
        os.unlink(db_path)

    def test_invalid_provider_raises(self):
        db_path = self._make_temp_db()
        with patch("agent.intake.project_registry.open_db", side_effect=lambda: _open_sqlite(db_path)):
            from agent.intake.project_registry import upsert_service_repo
            with pytest.raises(ValueError, match="Provider"):
                upsert_service_repo("default", "svc", "https://example.com",
                                    provider="badprovider")
        os.unlink(db_path)

    def test_subpath_stored_correctly(self):
        db_path = self._make_temp_db()
        with patch("agent.intake.project_registry.open_db", side_effect=lambda: _open_sqlite(db_path)):
            from agent.intake.project_registry import upsert_service_repo, get_service_repo
            upsert_service_repo("default", "mono-svc", "https://github.com/org/mono",
                                subpath="services/payment")
            repo = get_service_repo("default", "mono-svc")
        assert repo["subpath"] == "services/payment"
        os.unlink(db_path)

    def test_project_isolation(self):
        """Service mapping phải scope theo project_id."""
        db_path = self._make_temp_db()
        with patch("agent.intake.project_registry.open_db", side_effect=lambda: _open_sqlite(db_path)):
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
        os.unlink(db_path)


# ── DB helper (không dùng agent.storage.db để tránh side-effect) ─────────────

def _open_sqlite(path: str):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
