"""
Hypothesis catalog — danh sách giả thuyết mẫu theo domain.

Engine nhận catalog như tham số (như list[Tool]) — không hardcode domain knowledge bên trong.
Mỗi entry định nghĩa: tag, mô tả mặc định, keyword nhận diện bằng chứng,
tool liên quan, ngưỡng xác nhận/loại trừ.

Để thêm domain mới: tạo thêm List[HypothesisCatalogEntry] và truyền vào engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


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


# ── Domain: Microservice Ops ──────────────────────────────────────────────────

MICROSERVICE_CATALOG: List[HypothesisCatalogEntry] = [
    HypothesisCatalogEntry(
        tag="deploy",
        content="Deployment gần đây gây ra sự cố",
        keywords=["deployment", "deploy", "version"],
        relevant_tools={"get_recent_deploys"},
        confirm_kws={"deployment", "deploy", "version", "release", "tìm thấy"},
        rule_out_kws={"không tìm thấy", "0 deployment", "no deployment"},
        confirm_conf="medium",
    ),
    HypothesisCatalogEntry(
        tag="timeout",
        content="Downstream service phản hồi chậm gây timeout lan lên",
        keywords=["timeout", "latency", "chậm"],
        relevant_tools={"get_error_breakdown", "trace_request"},
        confirm_kws={"timeoutexception", "timeout", "latency", "deadline", "chậm"},
        rule_out_kws={"không có timeout", "latency bình thường"},
        confirm_conf="medium",
    ),
    HypothesisCatalogEntry(
        tag="latency_spike",
        content="Latency spike — có thể do code thay đổi hoặc dependency chậm",
        keywords=["latency", "spike", "lệch"],
        relevant_tools={"get_metrics"},
        confirm_kws={"lệch", "x baseline", "spike", "tăng", "cao hơn"},
        rule_out_kws={"bình thường", "không lệch", "normal"},
        confirm_conf="medium",
    ),
    HypothesisCatalogEntry(
        tag="pool_exhaustion",
        content="Connection pool exhaustion — quá nhiều kết nối đồng thời",
        keywords=["pool", "exhaustion", "connection", "wait_time"],
        relevant_tools={"get_metrics", "get_error_breakdown"},
        confirm_kws={"pool", "exhaustion", "connection", "wait_time", "queue"},
        rule_out_kws={"pool bình thường"},
        confirm_conf="high",
    ),
    HypothesisCatalogEntry(
        tag="provider_down",
        content="Provider/dependency ngoài bị sập",
        keywords=["provider", "unavailable", "sập"],
        relevant_tools={"get_dependencies", "get_error_breakdown"},
        confirm_kws={"provider", "unavailable", "serviceunavailable", "503", "sập"},
        rule_out_kws={"provider ok", "bình thường"},
        confirm_conf="high",
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
    ),
    HypothesisCatalogEntry(
        tag="price_configuration_error",
        content="Price configuration error gây refund_rate tăng bất thường",
        keywords=["price", "refund_rate", "bug"],
        relevant_tools={"get_merchant_status", "get_revenue_breakdown", "get_transaction_anomaly"},
        confirm_kws={"price_bug", "price", "refund_rate", "bug"},
        rule_out_kws={"bình thường", "không phát hiện", "đang active"},
        confirm_conf="high",
    ),
    HypothesisCatalogEntry(
        tag="merchant_fraud",
        content="Gian lận giao dịch hoặc merchant bị xâm phạm",
        keywords=["fraud", "breach", "blocked"],
        relevant_tools={"get_merchant_status", "get_transaction_anomaly"},
        confirm_kws={"fraud", "breach", "bị khóa", "blocked"},
        rule_out_kws={"bình thường", "đang active"},
        confirm_conf="medium",
    ),
    HypothesisCatalogEntry(
        tag="settlement_lag",
        content="Settlement lag — thời gian xử lý chậm hơn baseline",
        keywords=["settlement", "lag", "processing_time"],
        relevant_tools={"get_settlement_lag", "get_revenue_breakdown"},
        confirm_kws={"x baseline", "chậm", "processing_time", "lệch", "lag"},
        rule_out_kws={"bình thường", "không lệch"},
        confirm_conf="medium",
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
