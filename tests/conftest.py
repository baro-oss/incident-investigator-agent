"""
Shared fixtures cho toàn bộ test suite.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg
import pytest

from agent.engine.state import Evidence, Hypothesis, InvestigationState, Verdict
from agent.tools.contracts import Observation

_SCHEMA_SQL = (Path(__file__).parent.parent / "data" / "schema_postgres.sql").read_text()
_BASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://agent:agent@localhost:5432/investigation",
).split("?")[0]  # strip any existing options


@pytest.fixture
def pg_db(monkeypatch):
    """Schema-per-test Postgres isolation.

    Tạo schema riêng cho mỗi test, chạy full DDL, patch env,
    reset pool để app mở connection mới vào đúng schema.
    Sau test: đóng pool + drop schema.
    """
    import agent.storage.postgres_backend as pg_be

    schema = f"t{uuid.uuid4().hex[:8]}"
    test_url = f"{_BASE_URL}?options=-csearch_path%3D{schema}"

    with psycopg.connect(_BASE_URL, autocommit=True) as admin:
        admin.execute(f"CREATE SCHEMA {schema}")

    with psycopg.connect(test_url) as conn:
        conn.execute(_SCHEMA_SQL)
        conn.commit()

    old_pool = pg_be._pool
    pg_be._pool = None

    monkeypatch.setenv("DB_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", test_url)

    yield test_url, schema

    # Teardown: đóng pool test, khôi phục pool cũ, drop schema
    if pg_be._pool is not None and pg_be._pool is not old_pool:
        try:
            pg_be._pool.close()
        except Exception:
            pass
    pg_be._pool = old_pool

    with psycopg.connect(_BASE_URL, autocommit=True) as admin:
        admin.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


@pytest.fixture
def sample_state() -> InvestigationState:
    return InvestigationState(
        investigation_id="test-001",
        symptom="High error rate on payment-gateway",
        time_window="14:00-15:00",
        scenario="scenario1",
        date="2024-01-15",
        project_id="default",
    )


@pytest.fixture
def sample_observation() -> Observation:
    return Observation(
        summary="Deploy v2.3.1 at 14:03 — TimeoutException tăng 80% sau deploy",
        aggregates={"error_rate": 0.8, "deploy_count": 1},
        samples=[{"version": "v2.3.1", "deployed_at": "14:03"}],
        total_count=1,
        truncated=False,
        metadata={"tool_name": "get_recent_deploys", "service": "payment-gateway"},
    )


@pytest.fixture
def sample_verdict() -> Verdict:
    return Verdict(
        root_cause="Deploy v2.3.1 gây TimeoutException từ 14:05",
        confidence="high",
        evidence_summary="Deploy v2.3.1 lúc 14:03, TimeoutException tăng 80% từ 14:05",
        propagation_note="Lỗi gốc tại payment-gateway, lan lên api-gateway",
        competing_hypotheses="Provider down đã loại trừ — latency provider bình thường",
        raw_text="VERDICT:\nRoot cause: Deploy v2.3.1...",
    )
