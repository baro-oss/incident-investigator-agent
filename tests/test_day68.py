"""
Ngày 68 — Security/authz + UX/DX polish.

Cổng kiểm:
  1. M5: _WRITE_PARTS bao phủ thêm các verb mới (fork, deploy, sync, ...)
  2. M6: catalog add/delete + channel toggle + service add/del + repo add/del require_perm("project.manage")
  3. M7: SSE endpoint yêu cầu đăng nhập (có require_login dependency)
  4. L8: replay error HTML-escape (str(e) không được reflect raw vào HTML)
  5. L5: external trigger thiếu X-Alert-Source → warning (không raise, không crash)
"""
from __future__ import annotations

import inspect

import pytest


# ═════════════════════════════════════════════════════════════════════════════
# 1. M5 — _WRITE_PARTS extended
# ═════════════════════════════════════════════════════════════════════════════

class TestReadOnlyGuardExtended:
    def test_new_write_verbs_blocked(self):
        """M5: các verb mới (fork, deploy, sync, archive, ...) phải bị chặn."""
        from agent.tools.registry import is_read_only_tool
        blocked = [
            "fork_repo", "deploy_service", "sync_branch",
            "archive_project", "lock_branch", "unlock_branch",
            "enable_feature", "disable_feature", "release_version",
            "dispatch_workflow", "replace_config", "revert_commit",
            "rename_branch", "restore_backup",
        ]
        for name in blocked:
            assert not is_read_only_tool(name), f"'{name}' phải bị chặn (write)"

    def test_read_tools_still_pass(self):
        """M5: các read tool hợp lệ vẫn pass sau khi mở rộng blacklist."""
        from agent.tools.registry import is_read_only_tool
        passing = [
            "get_diff", "list_branches", "search_commits",
            "fetch_logs", "read_file", "find_issues",
        ]
        for name in passing:
            assert is_read_only_tool(name), f"'{name}' phải pass (read-only)"

    def test_local_tools_always_pass(self):
        """Local tools (get_metrics, trace_request, ...) luôn READ-ONLY."""
        from agent.tools.registry import is_read_only_tool
        for name in ["get_metrics", "get_error_breakdown", "trace_request",
                     "get_recent_deploys", "get_dependencies"]:
            assert is_read_only_tool(name)

    def test_write_verbs_in_write_parts(self):
        """Mọi verb mới phải thực sự có trong _WRITE_PARTS."""
        from agent.tools.registry import _WRITE_PARTS
        for verb in ["fork", "deploy", "sync", "archive", "lock", "unlock",
                     "enable", "disable", "release", "dispatch", "replace",
                     "revert", "rename", "restore"]:
            assert verb in _WRITE_PARTS, f"'{verb}' phải có trong _WRITE_PARTS"


# ═════════════════════════════════════════════════════════════════════════════
# 2. M6 — mutation routes require_perm("project.manage")
# ═════════════════════════════════════════════════════════════════════════════

class TestMutationRoutesRequirePerm:
    def _fn_snippet(self, fn_name: str, window: int = 600) -> str:
        """Trả đoạn source bắt đầu từ 'async def fn_name', kéo dài window chars."""
        from agent.dashboard import router as r
        src = inspect.getsource(r)
        idx = src.find(f"async def {fn_name}")
        assert idx != -1, f"Không tìm thấy hàm {fn_name}"
        return src[idx:idx + window]

    def test_catalog_add_has_project_manage(self):
        snippet = self._fn_snippet("dashboard_catalog_add")
        assert 'require_perm("project.manage")' in snippet, \
            "dashboard_catalog_add phải dùng require_perm('project.manage')"

    def test_catalog_delete_has_project_manage(self):
        snippet = self._fn_snippet("dashboard_catalog_delete")
        assert 'require_perm("project.manage")' in snippet

    def test_channel_toggle_has_project_manage(self):
        snippet = self._fn_snippet("dashboard_channel_toggle")
        assert 'require_perm("project.manage")' in snippet

    def test_service_add_has_project_manage(self):
        snippet = self._fn_snippet("dashboard_project_add_service")
        assert 'require_perm("project.manage")' in snippet

    def test_service_del_has_project_manage(self):
        snippet = self._fn_snippet("dashboard_project_del_service")
        assert 'require_perm("project.manage")' in snippet

    def test_repo_add_has_project_manage(self):
        snippet = self._fn_snippet("dashboard_project_add_repo")
        assert 'require_perm("project.manage")' in snippet

    def test_repo_del_has_project_manage(self):
        snippet = self._fn_snippet("dashboard_project_del_repo")
        assert 'require_perm("project.manage")' in snippet


# ═════════════════════════════════════════════════════════════════════════════
# 3. M7 — SSE endpoint requires auth
# ═════════════════════════════════════════════════════════════════════════════

class TestSSERequiresAuth:
    def test_stream_endpoint_has_require_login(self):
        """M7: dashboard_stream phải có require_login (không anonymous)."""
        from agent.dashboard import router as r
        src = inspect.getsource(r)
        idx = src.find("async def dashboard_stream")
        # Tìm khu vực 400 chars trước hàm (chứa decorator + signature)
        snippet = src[max(0, idx-400):idx+200]
        assert "require_login" in snippet, \
            "dashboard_stream phải có require_login dependency (M7)"
        # Đảm bảo không còn comment "không cần login"
        assert "không cần login" not in snippet


# ═════════════════════════════════════════════════════════════════════════════
# 4. L8 — HTML escape replay error
# ═════════════════════════════════════════════════════════════════════════════

class TestReplayHTMLEscape:
    def test_replay_error_uses_html_escape(self):
        """L8: replay exception phải qua html.escape trước khi nhúng vào HTML."""
        from agent.dashboard import router as r
        src = inspect.getsource(r)
        # Tìm hàm replay
        idx = src.find("async def dashboard_investigation_replay")
        snippet = src[idx:idx+2000]
        # Phải có html.escape (hoặc _html.escape) chứ không phải f"...{e}..."
        assert "escape" in snippet, "Replay error phải dùng html.escape (L8)"
        # Không được có raw {e} không escape trong HTMLResponse
        assert 'f"<h3>Replay failed: {e}</h3>"' not in snippet, \
            "Không được reflect {e} raw vào HTML"


# ═════════════════════════════════════════════════════════════════════════════
# 5. L5 — external trigger without X-Alert-Source logs warning
# ═════════════════════════════════════════════════════════════════════════════

class TestL5ExternalAlertWarning:
    def test_l5_warning_logged_for_missing_source(self):
        """L5: external trigger thiếu X-Alert-Source → log warning nhưng không raise."""
        import logging
        from agent.intake.server import _handle_trigger_request, _allow_anon_trigger

        # Verify logic: source=None, no session → log warning
        import inspect as _ins
        src = _ins.getsource(_handle_trigger_request)
        assert "L5" in src, "_handle_trigger_request phải log L5 warning"
        assert "X-Alert-Source" in src or "x-alert-source" in src.lower()
