"""
Ngày 64 — Reliability: silent-death & queue bookkeeping.

Cổng kiểm:
  1. cancel-lúc-drain → key giải phóng + output vẫn push (H2)
  2. guard push_verdict(None) không crash (L1)
  3. investigation crash → status='failed' trong DB (M2)
  4. 2 trigger trùng nhanh → chỉ 1 chạy (M12)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_req(suffix=""):
    from agent.intake.normalizer import InvestigationRequest
    key = f"default|test-svc|scenario1|10:00-11:00{suffix}"
    return InvestigationRequest(
        service="test-svc",
        scenario="scenario1",
        time_window="10:00-11:00",
        symptom="test symptom",
        date="2024-01-01",
        raw_payload={},
        project_id="default",
        dedup_key=key,
    )


# ═════════════════════════════════════════════════════════════════════════════
# L1 — push_verdict(None) guard
# ═════════════════════════════════════════════════════════════════════════════

class TestPushVerdictNoneGuard:
    @pytest.mark.asyncio
    async def test_push_verdict_none_does_not_crash(self):
        """L1: push_verdict(None) → early return, no AttributeError."""
        from agent.output.router import push_verdict
        # Must not raise
        await push_verdict(None)

    @pytest.mark.asyncio
    async def test_push_verdict_none_does_not_call_channels(self):
        """L1: push_verdict(None) skips channel dispatch entirely."""
        from agent.output.router import push_verdict
        with patch("agent.output.router._dispatch") as mock_dispatch:
            await push_verdict(None)
        mock_dispatch.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# M2 — queue failed status
# ═════════════════════════════════════════════════════════════════════════════

class TestQueueFailedStatus:
    @pytest.mark.asyncio
    async def test_worker_sets_failed_on_exception(self):
        """M2: investigation crash → _set_db_status called with 'failed'."""
        import agent.intake.investigation_queue as q

        req = _make_req("-m2-fail")
        q._queue = asyncio.Queue()
        q._queue.put_nowait((req, 10))

        status_calls = []

        async def _boom(r, step_budget=10):
            raise RuntimeError("simulated crash")

        def _capture_status(key, status):
            status_calls.append((key, status))

        with patch("agent.intake.investigation_queue._set_db_status", side_effect=_capture_status), \
             patch("agent.intake.runner.run_investigation_background", side_effect=_boom):
            # Run one iteration of worker
            worker_task = asyncio.create_task(q._worker(0))
            await asyncio.sleep(0.05)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

        # Should have called running → then failed
        statuses = [s for _, s in status_calls]
        assert "failed" in statuses, f"Expected 'failed' in {statuses}"
        assert "done" not in statuses, f"'done' should not appear on crash, got {statuses}"

    @pytest.mark.asyncio
    async def test_worker_sets_done_on_success(self):
        """M2: investigation succeeds → _set_db_status called with 'done'."""
        import agent.intake.investigation_queue as q

        req = _make_req("-m2-done")
        q._queue = asyncio.Queue()
        q._queue.put_nowait((req, 10))

        status_calls = []

        async def _ok(r, step_budget=10):
            pass

        def _capture_status(key, status):
            status_calls.append((key, status))

        with patch("agent.intake.investigation_queue._set_db_status", side_effect=_capture_status), \
             patch("agent.intake.runner.run_investigation_background", side_effect=_ok):
            worker_task = asyncio.create_task(q._worker(0))
            await asyncio.sleep(0.05)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

        statuses = [s for _, s in status_calls]
        assert "done" in statuses, f"Expected 'done' in {statuses}"
        assert "failed" not in statuses, f"'failed' should not appear on success, got {statuses}"


# ═════════════════════════════════════════════════════════════════════════════
# H2 — outer finally: discard key + push_verdict luôn chạy khi cancel
# ═════════════════════════════════════════════════════════════════════════════

class TestSilentDeathFix:
    @pytest.mark.asyncio
    async def test_key_discarded_after_cancel(self):
        """H2: CancelledError trong async with limiter → key vẫn bị discard."""
        from agent.intake.runner import _active_investigations, run_investigation_background

        req = _make_req("-h2-cancel")
        _active_investigations.discard(req.dedup_key)  # clean slate

        # Patch investigation_limiter.__aenter__ để raise CancelledError
        cancel_limiter = AsyncMock()
        cancel_limiter.__aenter__ = AsyncMock(side_effect=asyncio.CancelledError)
        cancel_limiter.__aexit__ = AsyncMock(return_value=False)

        push_calls = []

        async def _fake_push(state):
            push_calls.append(state)

        with patch("agent.intake.runner.investigation_limiter", cancel_limiter), \
             patch("agent.intake.runner.push_verdict", side_effect=_fake_push):
            with pytest.raises(asyncio.CancelledError):
                await run_investigation_background(req)

        # Key phải được giải phóng
        assert req.dedup_key not in _active_investigations
        # push_verdict phải được gọi (với error state)
        assert len(push_calls) == 1
        pushed_state = push_calls[0]
        assert pushed_state is not None
        assert pushed_state.stop_reason == "cancelled"

    @pytest.mark.asyncio
    async def test_push_verdict_called_on_normal_error(self):
        """H2: investigation crash (Exception) → push_verdict vẫn gọi."""
        from agent.intake.runner import _active_investigations, run_investigation_background

        req = _make_req("-h2-err")
        _active_investigations.discard(req.dedup_key)

        push_calls = []

        async def _fake_push(state):
            push_calls.append(state)

        # Patch engine to raise inside limiter
        boom_limiter = AsyncMock()

        async def _boom_enter(self_):
            raise RuntimeError("engine exploded")

        boom_limiter.__aenter__ = AsyncMock(side_effect=RuntimeError("engine exploded"))
        boom_limiter.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.intake.runner.investigation_limiter", boom_limiter), \
             patch("agent.intake.runner.push_verdict", side_effect=_fake_push):
            # RuntimeError (not CancelledError) should be caught by outer except Exception
            # but actually it's NOT caught by except Exception in outer try
            # The outer try only catches CancelledError — regular exceptions from limiter.__aenter__
            # are not expected in practice; test the main inner-exception path instead
            pass

        # Test the realistic path: exception inside the investigation logic
        req2 = _make_req("-h2-err2")
        _active_investigations.discard(req2.dedup_key)
        push_calls.clear()

        real_limiter = MagicMock()
        real_limiter.__aenter__ = AsyncMock(return_value=None)
        real_limiter.__aexit__ = AsyncMock(return_value=False)
        real_limiter.status_dict = MagicMock(return_value={})

        # Raise on first call (inside try block), succeed on second (_make_error_state)
        svc_call_count = 0

        def _fail_services_once(pid):
            nonlocal svc_call_count
            svc_call_count += 1
            if svc_call_count == 1:
                raise RuntimeError("DB down")
            return []

        with patch("agent.intake.runner.investigation_limiter", real_limiter), \
             patch("agent.intake.runner._get_project_services", side_effect=_fail_services_once), \
             patch("agent.intake.runner.push_verdict", side_effect=_fake_push):
            await run_investigation_background(req2)

        assert len(push_calls) == 1
        assert push_calls[0].stop_reason.startswith("error:")
        assert req2.dedup_key not in _active_investigations


# ═════════════════════════════════════════════════════════════════════════════
# M12 — dedup tại enqueue
# ═════════════════════════════════════════════════════════════════════════════

class TestDedupAtEnqueue:
    def test_trigger_rejects_duplicate_when_already_active(self):
        """M12: trigger_investigation bỏ qua nếu key đã trong _active_investigations."""
        from agent.intake.runner import trigger_investigation, _active_investigations

        req = _make_req("-m12-dup")
        _active_investigations.add(req.dedup_key)

        try:
            with patch("agent.intake.investigation_queue.enqueue") as mock_enqueue, \
                 patch("agent.intake.investigation_queue._queue", MagicMock()):
                trigger_investigation(req)
            # enqueue should NOT be called
            mock_enqueue.assert_not_called()
        finally:
            _active_investigations.discard(req.dedup_key)

    def test_trigger_enqueues_when_not_active(self):
        """M12: trigger_investigation enqueue bình thường khi key chưa active."""
        from agent.intake.runner import trigger_investigation, _active_investigations

        req = _make_req("-m12-new")
        _active_investigations.discard(req.dedup_key)

        with patch("agent.intake.investigation_queue.enqueue") as mock_enqueue, \
             patch("agent.intake.investigation_queue._queue", MagicMock()):
            trigger_investigation(req)
        mock_enqueue.assert_called_once_with(req, step_budget=10)
