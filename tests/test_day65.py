"""
Ngày 65 — Dialect parity prod + cost accuracy.

Cổng kiểm:
  1. H1: _translate() dịch json_extract → (col::jsonb->>'field') đúng
  2. H1: queries.py tương thích với cả SQLite (không crash)
  3. M4: _get_pricing khớp model ID thật (haiku-4-5, sonnet-4-6, opus-4-8)
  4. M11: hypothesis_catalog không rò connection (close() luôn gọi)
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


# ═════════════════════════════════════════════════════════════════════════════
# H1 — _translate: json_extract → jsonb
# ═════════════════════════════════════════════════════════════════════════════

class TestJsonExtractTranslate:
    def test_simple_field(self):
        from agent.storage.postgres_backend import _translate
        sql = "SELECT json_extract(payload,'$.total_tokens') FROM t"
        result = _translate(sql)
        assert "json_extract" not in result
        assert "(payload::jsonb->>'total_tokens')" in result

    def test_table_alias(self):
        from agent.storage.postgres_backend import _translate
        sql = "SELECT json_extract(te.payload,'$.confidence') FROM trace_events te"
        result = _translate(sql)
        assert "(te.payload::jsonb->>'confidence')" in result

    def test_cast_wrapper_preserved(self):
        """CAST(json_extract(payload,'$.total_tokens') AS INTEGER) → CAST((payload::jsonb->>'total_tokens') AS INTEGER)"""
        from agent.storage.postgres_backend import _translate
        sql = "SELECT CAST(json_extract(payload,'$.cache_read_tokens') AS INTEGER) FROM t"
        result = _translate(sql)
        assert "CAST((payload::jsonb->>'cache_read_tokens') AS INTEGER)" in result

    def test_multiple_occurrences(self):
        """Nhiều json_extract trong cùng câu SQL đều được dịch."""
        from agent.storage.postgres_backend import _translate
        sql = (
            "SELECT json_extract(p,'$.a') AS a, json_extract(p,'$.b') AS b "
            "FROM t WHERE json_extract(p,'$.c') IS NOT NULL"
        )
        result = _translate(sql)
        assert result.count("json_extract") == 0
        assert result.count("::jsonb") == 3

    def test_existing_translations_still_work(self):
        """Các translation cũ (?, INSERT OR IGNORE) vẫn chạy sau khi thêm json_extract."""
        from agent.storage.postgres_backend import _translate
        sql = "INSERT OR IGNORE INTO t (id, payload) VALUES (?, ?)"
        result = _translate(sql)
        assert "ON CONFLICT DO NOTHING" in result
        assert "%s" in result
        assert "?" not in result

    def test_no_false_positive(self):
        """Câu SQL không có json_extract không bị ảnh hưởng."""
        from agent.storage.postgres_backend import _translate
        sql = "SELECT id, payload FROM trace_events WHERE event_type='verdict'"
        result = _translate(sql)
        assert "::jsonb" not in result


# ═════════════════════════════════════════════════════════════════════════════
# H1 — queries.py không crash trên SQLite (integration sanity)
# ═════════════════════════════════════════════════════════════════════════════

class TestQueriesSqliteCompat:
    def test_get_cost_data_no_crash(self):
        """get_cost_data() chạy được với DB SQLite hiện tại."""
        from agent.dashboard.queries import get_cost_data
        result = get_cost_data()
        assert isinstance(result, dict)
        assert "scenarios" in result
        assert "grand_total_tokens" in result
        assert "cache_reads" in result

    def test_get_calibration_with_feedback_no_crash(self):
        from agent.dashboard.queries import get_calibration_with_feedback
        result = get_calibration_with_feedback()
        assert isinstance(result, dict)
        assert "eval" in result
        assert "feedback" in result


# ═════════════════════════════════════════════════════════════════════════════
# M4 — pricing accuracy with real model IDs
# ═════════════════════════════════════════════════════════════════════════════

class TestPricingAccuracy:
    def test_haiku_4_5_gets_haiku_price(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("anthropic", "claude-haiku-4-5-20251001")
        assert in_p == 0.80 and out_p == 4.00, f"Expected haiku pricing, got ({in_p}, {out_p})"

    def test_sonnet_4_6_gets_sonnet_price(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("anthropic", "claude-sonnet-4-6")
        assert in_p == 3.00 and out_p == 15.00

    def test_opus_4_8_gets_opus_price(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("anthropic", "claude-opus-4-8")
        assert in_p == 15.00 and out_p == 75.00

    def test_unknown_model_falls_back_to_default(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("anthropic", "claude-new-unknown-model")
        assert in_p == 3.00 and out_p == 15.00  # default sonnet

    def test_mock_provider_returns_zero(self):
        from agent.dashboard.queries import _get_pricing
        in_p, out_p = _get_pricing("mock", "any-model")
        assert in_p == 0.0 and out_p == 0.0

    def test_groq_provider(self):
        from agent.dashboard.queries import _get_pricing
        in_p, _ = _get_pricing("groq", "llama3-70b")
        assert in_p == 0.05

    def test_cost_usd_uses_correct_pricing(self):
        """_cost_usd cho haiku phải rẻ hơn opus."""
        from agent.dashboard.queries import _cost_usd
        haiku_cost = _cost_usd(1_000_000, "anthropic", "claude-haiku-4-5-20251001")
        opus_cost  = _cost_usd(1_000_000, "anthropic", "claude-opus-4-8")
        assert haiku_cost < opus_cost, "Haiku phải rẻ hơn Opus"


# ═════════════════════════════════════════════════════════════════════════════
# M11 — hypothesis_catalog đóng connection
# ═════════════════════════════════════════════════════════════════════════════

class TestHypothesisCatalogConnectionClose:
    def test_load_db_catalog_closes_connection(self):
        """load_db_catalog_entries phải gọi conn.close() dù query thành công."""
        from agent.engine import hypothesis_catalog as hc
        close_calls = []

        original_open = None

        class _FakeConn:
            def execute(self, sql, params=()):
                m = MagicMock()
                m.fetchall.return_value = []
                return m
            def close(self):
                close_calls.append(1)
            def commit(self): pass

        with patch("agent.storage.db.open_db", return_value=_FakeConn()):
            hc.load_db_catalog_entries("microservice", "default")

        assert len(close_calls) == 1, "close() phải được gọi đúng 1 lần"

    def test_list_catalog_entries_closes_on_exception(self):
        """list_catalog_entries_db phải gọi close() kể cả khi execute raises."""
        from agent.engine import hypothesis_catalog as hc
        close_calls = []

        class _BrokenConn:
            def execute(self, sql, params=()):
                raise RuntimeError("DB broken")
            def close(self):
                close_calls.append(1)
            def commit(self): pass

        with patch("agent.storage.db.open_db", return_value=_BrokenConn()):
            result = hc.list_catalog_entries_db()

        # Exception bị bắt trong try/except → trả []
        assert result == []
        # close() phải được gọi trong finally
        assert len(close_calls) == 1, "close() phải được gọi kể cả khi có exception"
