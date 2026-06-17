"""
Tests Day 54: P2 (distill external MCP text) + OPS1 (hypothesis_catalog DB CRUD & merge).
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


# ── P2: _distill_external_text ─────────────────────────────────────────────────

class TestDistillExternalText:
    """P2: external MCP text phải được distill đúng cách (Nguyên tắc #1)."""

    def setup_method(self):
        from agent.tools.mcp_client import _distill_external_text
        self._distill = _distill_external_text

    def test_empty_text_returns_valid_observation(self):
        obs = self._distill("", "my_tool", "http://srv")
        assert obs.summary != ""
        assert obs.truncated is False
        assert obs.total_count == 0

    def test_short_text_fits_in_summary(self):
        obs = self._distill("One line result", "my_tool", "http://srv")
        assert "One line result" in obs.summary
        assert obs.truncated is False

    def test_summary_contains_tool_name_prefix(self):
        obs = self._distill("hello world", "get_diff", "http://srv")
        assert "get_diff" in obs.summary

    def test_summary_capped_at_200_chars(self):
        long_line = "X" * 300
        obs = self._distill(long_line, "tool", "http://srv")
        assert len(obs.summary) <= 210  # 200 + prefix "[tool] " + ellipsis

    def test_multiline_produces_samples(self):
        text = "\n".join([f"line {i}" for i in range(10)])
        obs = self._distill(text, "tool", "http://srv")
        assert len(obs.samples) <= 5
        assert obs.total_count == 10

    def test_truncated_flag_set_when_many_lines(self):
        text = "\n".join([f"line {i}" for i in range(20)])
        obs = self._distill(text, "tool", "http://srv")
        assert obs.truncated is True

    def test_not_truncated_when_few_lines(self):
        text = "line1\nline2\nline3"
        obs = self._distill(text, "tool", "http://srv")
        assert obs.truncated is False

    def test_source_metadata_set_correctly(self):
        obs = self._distill("text", "my_tool", "http://remote:9000")
        assert obs.metadata["source"] == "mcp_external"
        assert obs.metadata["server_url"] == "http://remote:9000"
        assert obs.metadata["tool_name"] == "my_tool"

    def test_aggregates_has_total_lines(self):
        text = "a\nb\nc\nd\ne\nf"
        obs = self._distill(text, "tool", "http://srv")
        assert "total_lines" in obs.aggregates
        assert obs.aggregates["total_lines"] == 6

    def test_blank_lines_ignored_in_total_count(self):
        text = "a\n\n\nb\n\nc"
        obs = self._distill(text, "tool", "http://srv")
        assert obs.total_count == 3  # only non-blank lines


# ── P2: _parse_observation now uses distill ────────────────────────────────────

class TestParseObservationDistills:
    """Đảm bảo _parse_observation dùng distill thay vì cắt 500-char."""

    def test_long_text_not_truncated_to_500(self):
        from agent.tools.mcp_client import _parse_observation
        long_text = "line\n" * 200  # 1000+ chars
        obs = _parse_observation(long_text, "tool", "http://srv")
        # summary không phải toàn bộ text
        assert len(obs.summary) < 300
        assert obs.total_count > 0

    def test_structured_json_still_reconstructed(self):
        from agent.tools.mcp_client import _parse_observation
        data = json.dumps({
            "summary": "test summary",
            "aggregates": {"count": 5},
            "samples": ["a"],
            "total_count": 10,
            "truncated": False,
        })
        obs = _parse_observation(data, "tool", "http://srv")
        assert obs.summary == "test summary"
        assert obs.aggregates["count"] == 5


# ── OPS1: load_db_catalog_entries ─────────────────────────────────────────────

class TestLoadDbCatalogEntries:

    def test_empty_db_returns_empty_list(self, pg_db):
        from agent.engine.hypothesis_catalog import load_db_catalog_entries
        entries = load_db_catalog_entries("microservice", "test-project-load-empty")
        assert entries == []

    def test_returns_entries_from_db(self, pg_db):
        from agent.storage.db import open_db
        conn = open_db()
        conn.execute(
            "INSERT INTO hypothesis_catalog (domain, project_id, tag, content, keywords, relevant_tools, confirm_kws, rule_out_kws, confirm_conf, root_cause_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("microservice", "default", "cache_miss", "Cache miss", '["cache"]', '["get_metrics"]', '["cache"]', '[]', "medium", "cache_miss"),
        )
        conn.commit()
        conn.close()

        from agent.engine.hypothesis_catalog import load_db_catalog_entries
        entries = load_db_catalog_entries("microservice", "default")
        assert any(e.tag == "cache_miss" for e in entries)
        entry = next(e for e in entries if e.tag == "cache_miss")
        assert "cache" in entry.keywords
        assert "get_metrics" in entry.relevant_tools

    def test_filters_by_domain(self, pg_db):
        from agent.storage.db import open_db
        conn = open_db()
        conn.execute(
            "INSERT INTO hypothesis_catalog (domain, project_id, tag, content, keywords, relevant_tools, confirm_kws, rule_out_kws, confirm_conf, root_cause_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("fintech", "proj-filter-test", "fraud", "Fraud detection", '[]', '[]', '[]', '[]', "high", "fraud"),
        )
        conn.commit()
        conn.close()

        from agent.engine.hypothesis_catalog import load_db_catalog_entries
        ms_entries = load_db_catalog_entries("microservice", "proj-filter-test")
        ft_entries = load_db_catalog_entries("fintech", "proj-filter-test")
        assert ms_entries == []
        assert len(ft_entries) == 1


# ── OPS1: merge_catalog_with_db ────────────────────────────────────────────────

class TestMergeCatalogWithDb:

    def test_empty_db_returns_base_unchanged(self, pg_db):
        from agent.engine.hypothesis_catalog import merge_catalog_with_db, MICROSERVICE_CATALOG
        result = merge_catalog_with_db(MICROSERVICE_CATALOG, "microservice", "proj-merge-empty")
        assert len(result) == len(MICROSERVICE_CATALOG)

    def test_db_entry_overrides_same_tag(self, pg_db):
        from agent.storage.db import open_db
        conn = open_db()
        conn.execute(
            "INSERT INTO hypothesis_catalog (domain, project_id, tag, content, keywords, relevant_tools, confirm_kws, rule_out_kws, confirm_conf, root_cause_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (domain, project_id, tag) DO UPDATE SET content=EXCLUDED.content, confirm_conf=EXCLUDED.confirm_conf",
            ("microservice", "default", "deploy", "Overridden deploy content", '["deploy"]', '[]', '[]', '[]', "high", "deploy_bug"),
        )
        conn.commit()
        conn.close()

        from agent.engine.hypothesis_catalog import merge_catalog_with_db, MICROSERVICE_CATALOG
        result = merge_catalog_with_db(MICROSERVICE_CATALOG, "microservice", "default")

        deploy_entry = next(e for e in result if e.tag == "deploy")
        assert deploy_entry.content == "Overridden deploy content"
        assert deploy_entry.confirm_conf == "high"

    def test_new_db_tag_appended(self, pg_db):
        from agent.storage.db import open_db
        conn = open_db()
        conn.execute(
            "INSERT INTO hypothesis_catalog (domain, project_id, tag, content, keywords, relevant_tools, confirm_kws, rule_out_kws, confirm_conf, root_cause_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ("microservice", "default", "cache_miss_new", "Cache miss hypothesis", '["cache"]', '["get_metrics"]', '["cache"]', '[]', "medium", "cache_miss"),
        )
        conn.commit()
        conn.close()

        from agent.engine.hypothesis_catalog import merge_catalog_with_db, MICROSERVICE_CATALOG
        result = merge_catalog_with_db(MICROSERVICE_CATALOG, "microservice", "default")

        tags = [e.tag for e in result]
        assert "cache_miss_new" in tags
        assert len(result) == len(MICROSERVICE_CATALOG) + 1

    def test_base_order_preserved(self, pg_db):
        from agent.engine.hypothesis_catalog import merge_catalog_with_db, MICROSERVICE_CATALOG
        result = merge_catalog_with_db(MICROSERVICE_CATALOG, "microservice", "proj-order-test")
        # First N tags should match base order
        base_tags = [e.tag for e in MICROSERVICE_CATALOG]
        result_tags = [e.tag for e in result]
        assert result_tags[:len(base_tags)] == base_tags
