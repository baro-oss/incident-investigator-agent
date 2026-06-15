"""
Tool unit tests (Ngày 34): get_metrics, get_error_breakdown.

Dùng temp SQLite DB với dữ liệu seed nhỏ — không phụ thuộc DB thật.
"""
from __future__ import annotations

import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Fixture: temp DB với schema metrics/logs/service_catalog
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS service_catalog (
    service               TEXT PRIMARY KEY,
    baseline_latency_p99  REAL NOT NULL DEFAULT 100.0,
    baseline_error_rate   REAL NOT NULL DEFAULT 0.5
);

CREATE TABLE IF NOT EXISTS metrics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    scenario     TEXT NOT NULL,
    service      TEXT NOT NULL,
    metric_name  TEXT NOT NULL,
    value        REAL NOT NULL,
    is_baseline  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT NOT NULL,
    scenario   TEXT NOT NULL,
    service    TEXT NOT NULL,
    level      TEXT NOT NULL,
    message    TEXT NOT NULL,
    error_type TEXT,
    trace_id   TEXT
);
"""

# Seed: service 'payment-gateway', scenario1, 14:00-15:00
_METRIC_ROWS = [
    ("2024-01-15T14:05:00Z", "scenario1", "payment-gateway", "latency_p99", 900.0, 0),
    ("2024-01-15T14:10:00Z", "scenario1", "payment-gateway", "latency_p99", 950.0, 0),
    ("2024-01-15T14:15:00Z", "scenario1", "payment-gateway", "latency_p99", 880.0, 0),
    # Baseline rows (is_baseline=1, trước window)
    ("2024-01-15T13:00:00Z", "scenario1", "payment-gateway", "latency_p99", 100.0, 1),
    ("2024-01-15T13:10:00Z", "scenario1", "payment-gateway", "latency_p99", 95.0, 1),
    # error_rate metric
    ("2024-01-15T14:05:00Z", "scenario1", "payment-gateway", "error_rate", 45.0, 0),
    ("2024-01-15T14:10:00Z", "scenario1", "payment-gateway", "error_rate", 50.0, 0),
]

_LOG_ROWS = [
    ("2024-01-15T14:05:00Z", "scenario1", "payment-gateway", "ERROR", "Timeout", "TimeoutException"),
    ("2024-01-15T14:06:00Z", "scenario1", "payment-gateway", "ERROR", "Timeout", "TimeoutException"),
    ("2024-01-15T14:07:00Z", "scenario1", "payment-gateway", "ERROR", "Conn fail", "ConnectionError"),
    ("2024-01-15T14:08:00Z", "scenario1", "payment-gateway", "INFO", "OK", None),
    ("2024-01-15T14:09:00Z", "scenario1", "payment-gateway", "INFO", "OK", None),
]


@pytest.fixture
def tools_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_tools.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(TOOLS_SCHEMA)

    # Seed service_catalog
    conn.execute(
        "INSERT INTO service_catalog VALUES (?, ?, ?)",
        ("payment-gateway", 100.0, 0.5),
    )

    # Seed metrics
    for row in _METRIC_ROWS:
        conn.execute(
            "INSERT INTO metrics (timestamp, scenario, service, metric_name, value, is_baseline)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            row,
        )

    # Seed logs
    for row in _LOG_ROWS:
        conn.execute(
            "INSERT INTO logs (timestamp, scenario, service, level, message, error_type)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            row,
        )

    conn.commit()
    conn.close()

    monkeypatch.setenv("DB_PATH", str(db_file))
    yield str(db_file)


# ---------------------------------------------------------------------------
# TestGetMetrics
# ---------------------------------------------------------------------------

class TestGetMetrics:
    def test_returns_observation(self, tools_db):
        from agent.tools.get_metrics import _run
        from agent.tools.contracts import Observation

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "metric_name": "latency_p99",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert isinstance(obs, Observation)

    def test_summary_not_empty(self, tools_db):
        from agent.tools.get_metrics import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "metric_name": "latency_p99",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert len(obs.summary) > 0

    def test_summary_mentions_service(self, tools_db):
        from agent.tools.get_metrics import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "metric_name": "latency_p99",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert "payment-gateway" in obs.summary.lower() or "payment" in obs.summary.lower()

    def test_aggregates_present(self, tools_db):
        from agent.tools.get_metrics import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "metric_name": "latency_p99",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert isinstance(obs.aggregates, dict)
        assert len(obs.aggregates) > 0

    def test_empty_window_returns_observation(self, tools_db):
        """Không có data trong window → trả Observation hợp lệ, không crash."""
        from agent.tools.get_metrics import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "02:00-03:00",  # ngoài range seed
            "metric_name": "latency_p99",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert obs.summary is not None

    def test_error_rate_metric(self, tools_db):
        from agent.tools.get_metrics import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "metric_name": "error_rate",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert obs.total_count >= 0  # Observation hợp lệ

    def test_spike_detected_in_summary(self, tools_db):
        """Latency ~9x baseline → summary nên đề cập bất thường."""
        from agent.tools.get_metrics import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "metric_name": "latency_p99",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        # avg ~910ms vs baseline 100ms — summary phải đề cập x hoặc lệch
        summary_low = obs.summary.lower()
        assert any(kw in summary_low for kw in ["x baseline", "lệch", "spike", "bất thường", "cao"]), \
            f"Expected anomaly mention, got: {obs.summary}"


# ---------------------------------------------------------------------------
# TestGetErrorBreakdown
# ---------------------------------------------------------------------------

class TestGetErrorBreakdown:
    def test_returns_observation(self, tools_db):
        from agent.tools.get_error_breakdown import _run
        from agent.tools.contracts import Observation

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert isinstance(obs, Observation)

    def test_summary_mentions_error_type(self, tools_db):
        from agent.tools.get_error_breakdown import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert "TimeoutException" in obs.summary or "timeout" in obs.summary.lower()

    def test_total_count_positive(self, tools_db):
        from agent.tools.get_error_breakdown import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert obs.total_count > 0

    def test_aggregates_has_breakdown(self, tools_db):
        from agent.tools.get_error_breakdown import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert isinstance(obs.aggregates, dict)

    def test_empty_window_no_crash(self, tools_db):
        from agent.tools.get_error_breakdown import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "01:00-02:00",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert obs.total_count == 0

    def test_samples_capped(self, tools_db):
        """samples không vượt SAMPLES_HARD_CAP (5)."""
        from agent.tools.contracts import SAMPLES_HARD_CAP
        from agent.tools.get_error_breakdown import _run

        obs = _run({
            "service": "payment-gateway",
            "time_window": "14:00-15:00",
            "scenario": "scenario1",
            "date": "2024-01-15",
        })
        assert len(obs.samples) <= SAMPLES_HARD_CAP
