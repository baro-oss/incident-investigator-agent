"""
Tests for E8: Engine calibration (calibration.py).

Unit tests — không cần API key, không cần real LLM.
Test downgrade logic với dữ liệu được seeded.
"""
import sqlite3
import tempfile
import os
import pytest

from agent.engine.state import Verdict


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_verdict(confidence: str) -> Verdict:
    return Verdict(
        root_cause="test root cause",
        confidence=confidence,
        evidence_summary="test evidence",
        propagation_note="test propagation",
        competing_hypotheses="none",
        raw_text="VERDICT:\nRoot cause: test",
    )


def _seed_db(path: str, rows: list) -> None:
    """Seed eval_results rows: [(scenario, correct, confidence), ...]"""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT, scenario TEXT, run_number INTEGER,
            correct INTEGER, confidence TEXT,
            recall_at_1 INTEGER, steps_taken INTEGER,
            hallucination INTEGER, token_total INTEGER, elapsed_s REAL,
            created_at TEXT, provider TEXT, model TEXT
        )
    """)
    for scenario, correct, confidence in rows:
        conn.execute(
            "INSERT INTO eval_results (run_id, scenario, run_number, correct, confidence, "
            "recall_at_1, steps_taken, hallucination, token_total, elapsed_s, created_at) "
            "VALUES (?, ?, ?, ?, ?, 0, 5, 0, 1000, 1.0, datetime('now'))",
            ("run1", scenario, 1, int(correct), confidence),
        )
    conn.commit()
    conn.close()


# ── Unit tests: get_calibration_adjustment (no DB) ───────────────────────────

class TestGetCalibrationAdjustment:
    """Pure logic tests — no DB required."""

    def test_no_data_no_change(self):
        from agent.engine.calibration import get_calibration_adjustment
        result = get_calibration_adjustment("high", {})
        assert result == "high"

    def test_unknown_tier_passthrough(self):
        from agent.engine.calibration import get_calibration_adjustment
        result = get_calibration_adjustment("insufficient", {"insufficient": {"count": 10, "accuracy": 0.5}})
        assert result == "insufficient"

    def test_below_min_data_no_change(self):
        from agent.engine.calibration import get_calibration_adjustment, MIN_DATA_POINTS
        stats = {"high": {"count": MIN_DATA_POINTS - 1, "correct": 0, "accuracy": 0.0}}
        result = get_calibration_adjustment("high", stats)
        assert result == "high"  # not enough data

    def test_high_accuracy_no_change(self):
        from agent.engine.calibration import get_calibration_adjustment
        stats = {"high": {"count": 10, "correct": 10, "accuracy": 1.0}}
        result = get_calibration_adjustment("high", stats)
        assert result == "high"

    def test_high_below_threshold_downgrades(self):
        from agent.engine.calibration import get_calibration_adjustment
        # high threshold = 0.80; 0.60 < 0.80 → downgrade to medium
        stats = {"high": {"count": 10, "correct": 6, "accuracy": 0.60}}
        result = get_calibration_adjustment("high", stats)
        assert result == "medium"

    def test_medium_below_threshold_downgrades(self):
        from agent.engine.calibration import get_calibration_adjustment
        # medium threshold = 0.60; 0.50 < 0.60 → downgrade to low
        stats = {"medium": {"count": 10, "correct": 5, "accuracy": 0.50}}
        result = get_calibration_adjustment("medium", stats)
        assert result == "low"

    def test_low_below_threshold_downgrades(self):
        from agent.engine.calibration import get_calibration_adjustment
        # low threshold = 0.40; 0.30 < 0.40 → downgrade to insufficient
        stats = {"low": {"count": 10, "correct": 3, "accuracy": 0.30}}
        result = get_calibration_adjustment("low", stats)
        assert result == "insufficient"

    def test_exactly_at_threshold_no_change(self):
        from agent.engine.calibration import get_calibration_adjustment
        # Exactly at threshold (0.80 >= 0.80) → no change
        stats = {"high": {"count": 10, "correct": 8, "accuracy": 0.80}}
        result = get_calibration_adjustment("high", stats)
        assert result == "high"


# ── Unit tests: apply_calibration ─────────────────────────────────────────────

class TestApplyCalibration:
    """Test apply_calibration on Verdict objects."""

    def test_no_change_sets_no_calibrated_confidence(self):
        from agent.engine.calibration import apply_calibration
        stats = {"high": {"count": 20, "correct": 20, "accuracy": 1.0}}
        verdict = _make_verdict("high")
        result = apply_calibration(verdict, stats)
        assert result.confidence == "high"
        assert result.calibrated_confidence is None

    def test_downgrade_sets_calibrated_confidence(self):
        from agent.engine.calibration import apply_calibration
        stats = {"high": {"count": 10, "correct": 5, "accuracy": 0.50}}
        verdict = _make_verdict("high")
        result = apply_calibration(verdict, stats)
        assert result.confidence == "medium"
        assert result.calibrated_confidence == "medium"

    def test_empty_stats_passthrough(self):
        from agent.engine.calibration import apply_calibration
        verdict = _make_verdict("high")
        result = apply_calibration(verdict, {})
        assert result.confidence == "high"
        assert result.calibrated_confidence is None

    def test_medium_downgraded_to_low(self):
        from agent.engine.calibration import apply_calibration
        stats = {"medium": {"count": 8, "correct": 4, "accuracy": 0.50}}
        verdict = _make_verdict("medium")
        result = apply_calibration(verdict, stats)
        assert result.confidence == "low"

    def test_insufficient_not_affected(self):
        from agent.engine.calibration import apply_calibration
        stats = {"insufficient": {"count": 10, "correct": 5, "accuracy": 0.50}}
        verdict = _make_verdict("insufficient")
        result = apply_calibration(verdict, stats)
        assert result.confidence == "insufficient"


# ── Integration: load_calibration_stats from temp DB ─────────────────────────

class TestLoadCalibrationStats:
    """Test loading calibration stats from a real SQLite DB."""

    def test_loads_high_accuracy(self, tmp_path):
        from agent.engine.calibration import load_calibration_stats, invalidate_cache
        invalidate_cache()
        db_path = str(tmp_path / "test.db")
        _seed_db(db_path, [
            ("s1", True, "high"), ("s1", True, "high"), ("s1", True, "high"),
            ("s1", True, "high"), ("s1", True, "high"),  # 5 high-accuracy runs
        ])
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        stats = load_calibration_stats(db=conn)
        conn.close()
        invalidate_cache()
        assert "high" in stats
        assert stats["high"]["count"] == 5
        assert stats["high"]["accuracy"] == 1.0

    def test_loads_low_accuracy(self, tmp_path):
        from agent.engine.calibration import load_calibration_stats, invalidate_cache
        invalidate_cache()
        db_path = str(tmp_path / "test.db")
        _seed_db(db_path, [
            ("s1", False, "high"), ("s1", False, "high"), ("s1", False, "high"),
            ("s1", False, "high"), ("s1", False, "high"), ("s1", False, "high"),
        ])
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        stats = load_calibration_stats(db=conn)
        conn.close()
        invalidate_cache()
        assert stats["high"]["accuracy"] == 0.0

    def test_empty_db_returns_empty_dict(self, tmp_path):
        from agent.engine.calibration import load_calibration_stats, invalidate_cache
        invalidate_cache()
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE eval_results (confidence TEXT, correct INTEGER)")
        conn.commit()
        conn.row_factory = sqlite3.Row
        stats = load_calibration_stats(db=conn)
        conn.close()
        invalidate_cache()
        assert stats == {}


# ── Integration: full pipeline (seeded bad accuracy → downgrade) ──────────────

class TestCalibrationPipeline:
    """End-to-end: bad historical accuracy → verdict gets downgraded."""

    def test_bad_history_downgrades_verdict(self, tmp_path):
        from agent.engine.calibration import (
            load_calibration_stats, apply_calibration, invalidate_cache,
        )
        invalidate_cache()
        db_path = str(tmp_path / "test.db")
        # Seed: 10 high-confidence runs, only 4 correct (40% < 80% threshold)
        _seed_db(db_path, [("s1", i < 4, "high") for i in range(10)])
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        stats = load_calibration_stats(db=conn)
        conn.close()
        invalidate_cache()

        verdict = _make_verdict("high")
        result = apply_calibration(verdict, stats)
        assert result.confidence == "medium"
        assert result.calibrated_confidence == "medium"

    def test_good_history_keeps_verdict(self, tmp_path):
        from agent.engine.calibration import (
            load_calibration_stats, apply_calibration, invalidate_cache,
        )
        invalidate_cache()
        db_path = str(tmp_path / "test.db")
        # Seed: 10 high-confidence runs, 9 correct (90% >= 80% threshold)
        _seed_db(db_path, [("s1", i < 9, "high") for i in range(10)])
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        stats = load_calibration_stats(db=conn)
        conn.close()
        invalidate_cache()

        verdict = _make_verdict("high")
        result = apply_calibration(verdict, stats)
        assert result.confidence == "high"
        assert result.calibrated_confidence is None
