"""
Hypothesis catalog — danh sách giả thuyết mẫu theo domain.

Engine nhận catalog như tham số (như list[Tool]) — không hardcode domain knowledge bên trong.
Mỗi entry định nghĩa: tag, mô tả mặc định, keyword nhận diện bằng chứng,
tool liên quan, ngưỡng xác nhận/loại trừ.

Để thêm domain mới: tạo thêm List[HypothesisCatalogEntry] và truyền vào engine.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class HypothesisCatalogEntry:
    """Cấu hình một loại giả thuyết — engine dùng để tạo và cập nhật lifecycle."""
    tag: str                  # ID duy nhất, dùng làm Hypothesis.id
    content: str              # Mô tả mặc định khi tạo mới Hypothesis
    keywords: List[str]       # Từ khóa để match evidence có liên quan đến hypothesis này
    relevant_tools: Set[str]  # Tool nào khi gọi có thể sinh signal cho hypothesis này
    confirm_kws: Set[str]     # Từ khóa trong observation summary → xác nhận hypothesis
    rule_out_kws: Set[str]    # Từ khóa trong observation summary → loại trừ hypothesis
    confirm_conf: str         # Confidence khi confirm: "high" | "medium" | "low"
    # E11: khóa liên kết với investigation_patterns.root_cause_type
    root_cause_type: str = ""


# ── Domain: Microservice Ops ──────────────────────────────────────────────────

MICROSERVICE_CATALOG: List[HypothesisCatalogEntry] = [
    HypothesisCatalogEntry(
        tag="deploy",
        content="Deployment gần đây gây ra sự cố",
        keywords=["deployment", "deploy", "version"],
        relevant_tools={"get_recent_deploys", "get_code_diff"},
        confirm_kws={"deployment", "deploy", "version", "release", "tìm thấy"},
        rule_out_kws={"không tìm thấy", "0 deployment", "no deployment"},
        confirm_conf="medium",
        root_cause_type="deploy_bug",
    ),
    HypothesisCatalogEntry(
        tag="timeout",
        content="Downstream service phản hồi chậm gây timeout lan lên",
        keywords=["timeout", "latency", "chậm"],
        relevant_tools={"get_error_breakdown", "trace_request"},
        confirm_kws={"timeoutexception", "timeout", "latency", "deadline", "chậm"},
        rule_out_kws={"không có timeout", "latency bình thường"},
        confirm_conf="medium",
        root_cause_type="timeout",
    ),
    HypothesisCatalogEntry(
        tag="latency_spike",
        content="Latency spike — có thể do code thay đổi hoặc dependency chậm",
        keywords=["latency", "spike", "lệch"],
        relevant_tools={"get_metrics"},
        confirm_kws={"lệch", "x baseline", "spike", "tăng", "cao hơn"},
        rule_out_kws={"bình thường", "không lệch", "normal"},
        confirm_conf="medium",
        root_cause_type="latency_spike",
    ),
    HypothesisCatalogEntry(
        tag="pool_exhaustion",
        content="Connection pool exhaustion — quá nhiều kết nối đồng thời",
        keywords=["pool", "exhaustion", "connection", "wait_time"],
        relevant_tools={"get_metrics", "get_error_breakdown"},
        confirm_kws={"pool", "exhaustion", "connection", "wait_time", "queue"},
        rule_out_kws={"pool bình thường"},
        confirm_conf="high",
        root_cause_type="pool_exhaustion",
    ),
    HypothesisCatalogEntry(
        tag="provider_down",
        content="Provider/dependency ngoài bị sập",
        keywords=["provider", "unavailable", "sập"],
        relevant_tools={"get_dependencies", "get_error_breakdown"},
        confirm_kws={"provider", "unavailable", "serviceunavailable", "503", "sập"},
        rule_out_kws={"provider ok", "bình thường"},
        confirm_conf="high",
        root_cause_type="provider_down",
    ),
]


# ── Domain: Fintech ───────────────────────────────────────────────────────────

FINTECH_CATALOG: List[HypothesisCatalogEntry] = [
    HypothesisCatalogEntry(
        tag="processor_timeout",
        content="Payment processor timeout gây fail_rate tăng đột biến",
        keywords=["processor", "timeout", "fail_rate"],
        relevant_tools={"get_transaction_anomaly", "get_settlement_lag", "get_merchant_status"},
        # "processortimeout" = ProcessorTimeout lowercased; "degraded" = processor status
        confirm_kws={"processortimeout", "processor_timeout", "fail_rate", "timeout", "degraded"},
        rule_out_kws={"bình thường", "không phát hiện", "đang active"},
        confirm_conf="medium",
        root_cause_type="processor_timeout",
    ),
    HypothesisCatalogEntry(
        tag="price_configuration_error",
        content="Price configuration error gây refund_rate tăng bất thường",
        keywords=["price", "refund_rate", "bug"],
        relevant_tools={"get_merchant_status", "get_revenue_breakdown", "get_transaction_anomaly"},
        confirm_kws={"price_bug", "price", "refund_rate", "bug"},
        rule_out_kws={"bình thường", "không phát hiện", "đang active"},
        confirm_conf="high",
        root_cause_type="price_configuration_error",
    ),
    HypothesisCatalogEntry(
        tag="merchant_fraud",
        content="Gian lận giao dịch hoặc merchant bị xâm phạm",
        keywords=["fraud", "breach", "blocked"],
        relevant_tools={"get_merchant_status", "get_transaction_anomaly"},
        confirm_kws={"fraud", "breach", "bị khóa", "blocked"},
        rule_out_kws={"bình thường", "đang active"},
        confirm_conf="medium",
        root_cause_type="merchant_fraud",
    ),
    HypothesisCatalogEntry(
        tag="settlement_lag",
        content="Settlement lag — thời gian xử lý chậm hơn baseline",
        keywords=["settlement", "lag", "processing_time"],
        relevant_tools={"get_settlement_lag", "get_revenue_breakdown"},
        confirm_kws={"x baseline", "chậm", "processing_time", "lệch", "lag"},
        rule_out_kws={"bình thường", "không lệch"},
        confirm_conf="medium",
        root_cause_type="settlement_lag",
    ),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_default_catalog(domain: str = "microservice") -> List[HypothesisCatalogEntry]:
    """Trả catalog mặc định theo domain. Fallback về microservice nếu domain không nhận ra."""
    if domain == "fintech":
        return FINTECH_CATALOG
    return MICROSERVICE_CATALOG


def build_catalog_index(
    catalog: List[HypothesisCatalogEntry],
) -> Dict[str, HypothesisCatalogEntry]:
    """Build dict{tag → entry} cho lookup O(1). Dùng trong _update_hypotheses."""
    return {entry.tag: entry for entry in catalog}


def build_rct_index(
    catalog: List[HypothesisCatalogEntry],
) -> Dict[str, HypothesisCatalogEntry]:
    """Build dict{root_cause_type → entry} cho E11 pre-seed. Bỏ qua entry không có root_cause_type."""
    return {entry.root_cause_type: entry for entry in catalog if entry.root_cause_type}


# ── OPS1: Catalog DB persistence ─────────────────────────────────────────────

def _row_to_entry(row: dict) -> Optional[HypothesisCatalogEntry]:
    try:
        return HypothesisCatalogEntry(
            tag=row["tag"],
            content=row.get("content", ""),
            keywords=json.loads(row.get("keywords") or "[]"),
            relevant_tools=set(json.loads(row.get("relevant_tools") or "[]")),
            confirm_kws=set(json.loads(row.get("confirm_kws") or "[]")),
            rule_out_kws=set(json.loads(row.get("rule_out_kws") or "[]")),
            confirm_conf=row.get("confirm_conf", "medium"),
            root_cause_type=row.get("root_cause_type", ""),
        )
    except Exception as e:
        logger.warning("hypothesis_catalog: bỏ qua row lỗi tag=%s: %s", row.get("tag"), e)
        return None


def load_db_catalog_entries(domain: str = "microservice", project_id: str = "default") -> List[HypothesisCatalogEntry]:
    """Đọc tất cả entry trong DB cho (domain, project_id). Trả [] nếu bảng chưa có."""
    try:
        from agent.storage.db import open_db
        db = open_db()
        try:
            rows = db.execute(
                "SELECT * FROM hypothesis_catalog WHERE domain=? AND project_id=?",
                (domain, project_id),
            ).fetchall()
        finally:
            db.close()
        entries = [_row_to_entry(dict(r)) for r in rows]
        return [e for e in entries if e is not None]
    except Exception as e:
        logger.warning("load_db_catalog_entries: %s", e)
        return []


def merge_catalog_with_db(
    base: List[HypothesisCatalogEntry],
    domain: str = "microservice",
    project_id: str = "default",
) -> List[HypothesisCatalogEntry]:
    """
    Merge DB entries lên trên default catalog.

    • DB entry cùng tag → ghi đè default
    • DB entry tag mới → thêm vào cuối
    DB override không xóa default entries không có trong DB.
    """
    db_entries = load_db_catalog_entries(domain, project_id)
    if not db_entries:
        return list(base)

    by_tag: Dict[str, HypothesisCatalogEntry] = {e.tag: e for e in base}
    for entry in db_entries:
        by_tag[entry.tag] = entry  # overwrite hoặc thêm mới

    # Giữ thứ tự: base trước (theo tag order), rồi new tags từ DB
    base_tags = [e.tag for e in base]
    new_tags = [e.tag for e in db_entries if e.tag not in {e2.tag for e2 in base}]
    ordered_tags = base_tags + new_tags
    return [by_tag[t] for t in ordered_tags if t in by_tag]


# ── OPS1: CRUD helpers (dùng cho dashboard routes) ───────────────────────────

def add_catalog_entry(
    domain: str,
    project_id: str,
    tag: str,
    content: str,
    keywords: List[str],
    relevant_tools: List[str],
    confirm_kws: List[str],
    rule_out_kws: List[str],
    confirm_conf: str,
    root_cause_type: str,
) -> None:
    from agent.storage.db import open_db
    db = open_db()
    try:
        db.execute(
            """INSERT INTO hypothesis_catalog
               (domain, project_id, tag, content, keywords, relevant_tools,
                confirm_kws, rule_out_kws, confirm_conf, root_cause_type)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (domain, project_id, tag) DO UPDATE SET
               content=EXCLUDED.content, keywords=EXCLUDED.keywords,
               relevant_tools=EXCLUDED.relevant_tools,
               confirm_kws=EXCLUDED.confirm_kws,
               rule_out_kws=EXCLUDED.rule_out_kws,
               confirm_conf=EXCLUDED.confirm_conf,
               root_cause_type=EXCLUDED.root_cause_type""",
            (
                domain, project_id, tag, content,
                json.dumps(keywords, ensure_ascii=False),
                json.dumps(relevant_tools, ensure_ascii=False),
                json.dumps(confirm_kws, ensure_ascii=False),
                json.dumps(rule_out_kws, ensure_ascii=False),
                confirm_conf, root_cause_type,
            ),
        )
        db.commit()
    finally:
        db.close()


def delete_catalog_entry(entry_id: int) -> bool:
    from agent.storage.db import open_db
    db = open_db()
    try:
        cur = db.execute("DELETE FROM hypothesis_catalog WHERE id=?", (entry_id,))
        db.commit()
        return cur.rowcount > 0
    finally:
        db.close()


def list_catalog_entries_db(domain: Optional[str] = None, project_id: Optional[str] = None) -> List[dict]:
    """Trả list raw dict từ DB để hiển thị trong UI."""
    try:
        from agent.storage.db import open_db
        db = open_db()
        try:
            clauses, params = [], []
            if domain:
                clauses.append("domain=?")
                params.append(domain)
            if project_id:
                clauses.append("project_id=?")
                params.append(project_id)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = db.execute(
                f"SELECT * FROM hypothesis_catalog {where} ORDER BY domain, project_id, tag",
                params,
            ).fetchall()
        finally:
            db.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
