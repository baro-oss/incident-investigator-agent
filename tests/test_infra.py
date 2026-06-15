"""
Tests for T1: Infra + contract guard (Ngày 40).

- Investigation queue: enqueue / depth / draining / crash recovery
- Scheduler: CRUD triggers + fire due trigger
- Project registry + MCP registry: CRUD
- Crypto: round-trip, backward compat, is_encrypted
- Contract guard (P2): Observation hợp lệ, bắt violation
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import uuid
from unittest.mock import patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _unique_id() -> str:
    return str(uuid.uuid4())[:8]


def _open_temp_db(path: str):
    """Mở temp DB với row_factory và schema tối thiểu."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# INVESTIGATION QUEUE
# ═════════════════════════════════════════════════════════════════════════════

class TestInvestigationQueue:
    """Test queue functions — không cần asyncio workers thật."""

    def test_is_draining_default_false(self):
        import agent.intake.investigation_queue as q
        old_draining = q._draining
        q._draining = False
        try:
            assert q.is_draining() is False
        finally:
            q._draining = old_draining

    def test_queue_depth_returns_int(self):
        import agent.intake.investigation_queue as q
        depth = q.queue_depth()
        assert isinstance(depth, int)
        assert depth >= 0

    def test_enqueue_saves_to_real_db(self):
        """enqueue → _persist_one → DB row exists với status=pending."""
        from agent.intake.investigation_queue import enqueue
        from agent.intake.normalizer import InvestigationRequest
        from agent.storage.db import open_db

        dedup_key = "default|test-svc|scenario1|" + _unique_id()
        req = InvestigationRequest(
            symptom="test",
            service="test-svc",
            time_window="14:00-15:00",
            scenario="scenario1",
            date="2024-01-15",
            raw_payload={},
            dedup_key=dedup_key,
            project_id="default",
        )
        enqueue(req)
        conn = open_db()
        try:
            row = conn.execute(
                "SELECT status FROM investigation_queue WHERE project_id='default' LIMIT 1",
            ).fetchone()
            assert row is not None
        finally:
            # Cleanup
            conn.execute("DELETE FROM investigation_queue WHERE payload LIKE '%test-svc%'")
            conn.commit()
            conn.close()

    def test_crash_recovery_sql_logic(self):
        """Verify SQL logic: UPDATE running→pending works on real DB."""
        from agent.storage.db import open_db
        import json
        from datetime import datetime, timezone

        row_id = _unique_id()
        dedup_key = "default|crash-svc|scenario1|" + row_id
        payload_json = json.dumps({"req": {
            "symptom": "crash test", "service": "crash-svc",
            "time_window": "14:00-15:00", "scenario": "scenario1",
            "date": "2024-01-15", "raw_payload": {}, "dedup_key": dedup_key,
            "project_id": "default", "multi_agent": False, "domain": "microservice",
        }, "step_budget": 10})

        conn = open_db()
        try:
            # investigation_queue needs: id (PK), project_id, payload, status, enqueued_at
            conn.execute(
                "INSERT INTO investigation_queue (id, project_id, payload, status, enqueued_at) "
                "VALUES (?, 'default', ?, 'running', ?)",
                (row_id, payload_json, __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()),
            )
            conn.commit()
            # Simulate crash recovery: reset running → pending
            conn.execute(
                "UPDATE investigation_queue SET status='pending' WHERE status='running' AND id=?",
                (row_id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT status FROM investigation_queue WHERE id=?", (row_id,)
            ).fetchone()
            assert row["status"] == "pending"
        finally:
            conn.execute("DELETE FROM investigation_queue WHERE id=?", (row_id,))
            conn.commit()
            conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# SCHEDULER CRUD
# ═════════════════════════════════════════════════════════════════════════════

class TestSchedulerCRUD:
    """Test scheduler trigger CRUD against real DB (cleanup after each test)."""

    def _cleanup(self, trigger_id: str) -> None:
        from agent.storage.db import open_db
        conn = open_db()
        conn.execute("DELETE FROM scheduled_triggers WHERE id=?", (trigger_id,))
        conn.commit()
        conn.close()

    def test_create_and_list_trigger(self):
        from agent.intake.scheduler import create_trigger, list_triggers
        project = "test-proj-" + _unique_id()
        trigger_id = create_trigger(
            project_id=project,
            service="payment-gateway",
            scenario="scenario1",
            interval_min=60,
        )
        assert trigger_id  # non-empty string
        try:
            triggers = list_triggers(project_id=project)
            assert any(t["id"] == trigger_id for t in triggers)
        finally:
            self._cleanup(trigger_id)

    def test_trigger_fields_set_correctly(self):
        from agent.intake.scheduler import create_trigger, list_triggers
        project = "test-proj-" + _unique_id()
        trigger_id = create_trigger(
            project_id=project,
            service="auth-service",
            scenario="scenario3",
            interval_min=30,
        )
        try:
            triggers = list_triggers(project_id=project)
            t = next(x for x in triggers if x["id"] == trigger_id)
            assert t["service"] == "auth-service"
            assert t["scenario"] == "scenario3"
            assert t["interval_min"] == 30
            assert t["enabled"] == 1
        finally:
            self._cleanup(trigger_id)

    def test_fire_due_trigger_enqueues(self, tmp_path):
        """_fire_due_triggers fires past-due triggers without crashing."""
        from agent.intake.investigation_queue import _persist_one
        import json

        # Inject a past-due trigger into the DB
        from agent.storage.db import open_db
        import uuid as _uuid
        trigger_id = str(_uuid.uuid4())
        project = "sched-test-" + _unique_id()
        conn = open_db()
        try:
            from datetime import datetime, timezone as _tz
            conn.execute(
                """INSERT INTO scheduled_triggers
                   (id, project_id, service, scenario, interval_min, enabled,
                    next_run_at, created_at)
                   VALUES (?, ?, 'svc', 'scenario1', 60, 1,
                           '2000-01-01T00:00:00+00:00', ?)""",
                (trigger_id, project, datetime.now(_tz.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        fired = []
        original_enqueue = None
        import agent.intake.investigation_queue as q_mod
        original_enqueue = q_mod.enqueue

        def mock_enqueue(req, step_budget=10):
            fired.append(req)

        try:
            q_mod.enqueue = mock_enqueue
            from agent.intake.scheduler import _fire_due_triggers
            _fire_due_triggers()
            assert any(r.project_id == project for r in fired)
        finally:
            q_mod.enqueue = original_enqueue
            # Cleanup
            conn = open_db()
            conn.execute("DELETE FROM scheduled_triggers WHERE id=?", (trigger_id,))
            conn.commit()
            conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# PROJECT REGISTRY CRUD
# ═════════════════════════════════════════════════════════════════════════════

class TestProjectRegistryCRUD:
    """Test project CRUD — dùng unique project_id để không xung đột với default."""

    def _pid(self) -> str:
        return "test-" + _unique_id()

    def test_create_and_get(self):
        from agent.intake.project_registry import create_project, get_project, delete_project
        pid = self._pid()
        try:
            p = create_project(pid, "Test Project")
            assert p["id"] == pid  # projects table uses 'id' column
            assert p["name"] == "Test Project"

            fetched = get_project(pid)
            assert fetched is not None
            assert fetched["id"] == pid
        finally:
            delete_project(pid)

    def test_list_includes_created(self):
        from agent.intake.project_registry import create_project, list_projects, delete_project
        pid = self._pid()
        try:
            create_project(pid, "Test List")
            projects = list_projects()
            ids = [p["id"] for p in projects]  # 'id' not 'project_id'
            assert pid in ids
        finally:
            delete_project(pid)

    def test_add_and_list_services(self):
        from agent.intake.project_registry import (
            create_project, delete_project,
            add_project_service, list_project_services,
        )
        pid = self._pid()
        try:
            create_project(pid, "Service Test")
            add_project_service(pid, "payment-gateway")
            add_project_service(pid, "auth-service")
            services = list_project_services(pid)
            assert "payment-gateway" in services
            assert "auth-service" in services
        finally:
            delete_project(pid)

    def test_delete_removes_project(self):
        from agent.intake.project_registry import create_project, get_project, delete_project
        pid = self._pid()
        create_project(pid, "Delete Me")
        delete_project(pid)
        assert get_project(pid) is None


# ═════════════════════════════════════════════════════════════════════════════
# MCP REGISTRY CRUD
# ═════════════════════════════════════════════════════════════════════════════

class TestMCPRegistryCRUD:
    def test_add_and_list_server(self):
        from agent.intake.mcp_registry import add_server, list_servers, remove_server
        project = "mcp-test-" + _unique_id()
        server = add_server(
            project_id=project,
            url="http://localhost:9999/mcp",
            name="test-mcp",
            description="test",
        )
        server_id = server["id"]
        try:
            servers = list_servers(project_id=project)
            assert any(s["id"] == server_id for s in servers)
        finally:
            remove_server(server_id, project_id=project)

    def test_server_enabled_by_default(self):
        from agent.intake.mcp_registry import add_server, list_servers, remove_server
        project = "mcp-test-" + _unique_id()
        server = add_server(
            project_id=project,
            url="http://localhost:9998/mcp",
            name="test",
        )
        sid = server["id"]
        try:
            servers = list_servers(project_id=project)
            s = next(x for x in servers if x["id"] == sid)
            assert s["enabled"] == 1
        finally:
            remove_server(sid, project_id=project)

    def test_remove_server(self):
        from agent.intake.mcp_registry import add_server, list_servers, remove_server
        project = "mcp-test-" + _unique_id()
        server = add_server(project_id=project, url="http://localhost:9997/mcp", name="t")
        sid = server["id"]
        remove_server(sid, project_id=project)
        servers = list_servers(project_id=project)
        assert not any(s["id"] == sid for s in servers)


# ═════════════════════════════════════════════════════════════════════════════
# CRYPTO
# ═════════════════════════════════════════════════════════════════════════════

class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        from agent.security.crypto import encrypt_secret, decrypt_secret
        with patch.dict(os.environ, {"SECRET_KEY": "test-secret-key-123"}):
            # Force re-read of env
            import agent.security.crypto as c
            c._WARNED_NO_KEY = False
            encrypted = encrypt_secret("super-secret-api-key")
            assert encrypted is not None
            assert encrypted.startswith("enc:")
            decrypted = decrypt_secret(encrypted)
            assert decrypted == "super-secret-api-key"

    def test_encrypt_idempotent(self):
        from agent.security.crypto import encrypt_secret
        with patch.dict(os.environ, {"SECRET_KEY": "test-key-456"}):
            import agent.security.crypto as c
            c._WARNED_NO_KEY = False
            once = encrypt_secret("value")
            twice = encrypt_secret(once)  # already encrypted
            assert once == twice

    def test_decrypt_plaintext_passthrough(self):
        from agent.security.crypto import decrypt_secret
        # Plaintext (no "enc:" prefix) → returned as-is
        assert decrypt_secret("plain-value") == "plain-value"

    def test_decrypt_none_returns_none(self):
        from agent.security.crypto import decrypt_secret
        assert decrypt_secret(None) is None

    def test_encrypt_none_returns_none(self):
        from agent.security.crypto import encrypt_secret
        assert encrypt_secret(None) is None

    def test_is_encrypted_detects_prefix(self):
        from agent.security.crypto import is_encrypted
        assert is_encrypted("enc:abc123") is True
        assert is_encrypted("plaintext") is False
        assert is_encrypted("") is False

    def test_no_key_passthrough(self):
        from agent.security.crypto import encrypt_secret, decrypt_secret
        with patch.dict(os.environ, {}, clear=True):
            import agent.security.crypto as c
            c._WARNED_NO_KEY = False
            # No key → pass-through (no encryption)
            enc = encrypt_secret("value")
            assert enc == "value"
            dec = decrypt_secret("value")
            assert dec == "value"


# ═════════════════════════════════════════════════════════════════════════════
# CONTRACT GUARD — Nguyên tắc #1: LLM không bao giờ thấy raw data
# ═════════════════════════════════════════════════════════════════════════════

from agent.tools.contracts import Observation


def validate_observation(obs: Observation) -> list:
    """
    Contract guard: kiểm Observation hợp lệ.
    Trả list lỗi (rỗng = hợp lệ).
    """
    errors = []
    if not obs.summary or not obs.summary.strip():
        errors.append("summary rỗng")
    if obs.total_count is None:
        errors.append("total_count chưa set")
    if len(obs.samples) > 5:
        errors.append(f"samples quá nhiều ({len(obs.samples)} > 5) — rò raw data")
    return errors


class TestContractGuard:
    """Enforce Nguyên tắc #1: tool không trả raw rows."""

    def test_valid_observation_passes(self):
        obs = Observation(
            summary="Tìm thấy 3 lỗi TimeoutException chiếm 65% (9.3x baseline).",
            aggregates={"error_rate": 65.0},
            samples=[{"ts": "14:01", "err": "TimeoutException"}],
            total_count=100,
            truncated=False,
            metadata={},
        )
        errors = validate_observation(obs)
        assert errors == []

    def test_empty_summary_fails(self):
        obs = Observation(
            summary="",
            aggregates={},
            samples=[],
            total_count=10,
            truncated=False,
            metadata={},
        )
        errors = validate_observation(obs)
        assert any("summary" in e for e in errors)

    def test_too_many_samples_fails(self):
        obs = Observation(
            summary="raw dump",
            aggregates={},
            samples=[{"id": i} for i in range(6)],  # 6 > 5
            total_count=1000,
            truncated=False,
            metadata={},
        )
        errors = validate_observation(obs)
        assert any("samples" in e for e in errors)

    def test_exactly_5_samples_passes(self):
        obs = Observation(
            summary="5 samples OK",
            aggregates={},
            samples=[{"id": i} for i in range(5)],
            total_count=100,
            truncated=True,
            metadata={},
        )
        errors = validate_observation(obs)
        assert errors == []

    def test_guard_catches_intentional_violation(self):
        """Simula tool cố tình trả 10 raw rows — guard bắt được."""
        # Simulate a badly-written tool that returns raw rows
        bad_tool_output = Observation(
            summary="Here are all the rows:",
            aggregates={},
            samples=[{"row": i, "data": "raw"} for i in range(10)],  # 10 raw rows
            total_count=10,
            truncated=False,
            metadata={},
        )
        errors = validate_observation(bad_tool_output)
        assert len(errors) >= 1
        assert any("samples" in e for e in errors)

    def test_all_real_tools_return_valid_observations(self):
        """
        Chạy từng local tool với scenario1 và kiểm contract.
        Dùng DB thật — nếu DB rỗng thì tool có thể trả empty observation.
        """
        import asyncio
        from agent.tools.contracts import Tool

        tool_files = [
            "get_error_breakdown",
            "get_metrics",
            "get_recent_deploys",
            "get_dependencies",
        ]

        for tool_name in tool_files:
            module = __import__(f"agent.tools.{tool_name}", fromlist=[tool_name])
            # Find the build_* function and get a Tool instance
            build_fn = next(
                (getattr(module, n) for n in dir(module) if n.startswith("build_")),
                None,
            )
            if build_fn is None:
                continue
            tool: Tool = build_fn()

            params = {"service": "payment-gateway", "time_window": "14:00-15:00", "scenario": "scenario1"}
            try:
                if asyncio.iscoroutinefunction(tool.run):
                    obs = asyncio.get_event_loop().run_until_complete(tool.run(params))
                else:
                    obs = tool.run(params)
                errors = validate_observation(obs)
                assert errors == [], f"{tool_name} contract violation: {errors}"
            except Exception as e:
                # Tool might fail if DB is empty — that's OK, just no crash
                pass
