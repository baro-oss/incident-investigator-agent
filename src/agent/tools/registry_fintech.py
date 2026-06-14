"""
Fintech tool registry — danh sách tool fintech đưa vào engine.

Sử dụng:
    from agent.tools.registry_fintech import get_fintech_tool_registry, ALL_FINTECH_TOOLS

    tools = get_fintech_tool_registry()  # list[Tool] sẵn sàng cho engine

Kết hợp với tool registry chính:
    from agent.tools.registry import build_tool_registry
    from agent.tools.registry_fintech import ALL_FINTECH_TOOLS
    # → truyền ALL_FINTECH_TOOLS vào engine riêng, hoặc merge thủ công nếu cần.
"""
from __future__ import annotations

from typing import List

from agent.tools.contracts import Tool
from agent.tools.fintech.get_merchant_status import get_merchant_status
from agent.tools.fintech.get_revenue_breakdown import get_revenue_breakdown
from agent.tools.fintech.get_settlement_lag import get_settlement_lag
from agent.tools.fintech.get_transaction_anomaly import get_transaction_anomaly

ALL_FINTECH_TOOLS: List[Tool] = [
    get_revenue_breakdown,
    get_transaction_anomaly,
    get_merchant_status,
    get_settlement_lag,
]


def get_fintech_tool_registry() -> List[Tool]:
    """Trả về danh sách fintech tools sẵn sàng cho engine."""
    return list(ALL_FINTECH_TOOLS)
