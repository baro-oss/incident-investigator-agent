"""
Gọi tool thủ công — cổng kiểm cuối Ngày 1.

Cách dùng:
  python scripts/run_tool.py get_error_breakdown --service payment-gateway --time_window 14:00-15:00
  python scripts/run_tool.py get_metrics --service payment-gateway --time_window 14:00-15:00 --metric_name latency_p99
  python scripts/run_tool.py get_metrics --service payment-gateway --time_window 14:00-15:00 --metric_name error_rate
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Đảm bảo import được khi chạy từ root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from agent.tools.contracts import render_for_llm
from agent.tools.get_error_breakdown import get_error_breakdown
from agent.tools.get_metrics import get_metrics

TOOLS = {
    "get_error_breakdown": get_error_breakdown,
    "get_metrics": get_metrics,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Gọi tool thủ công và in Observation")
    parser.add_argument("tool", choices=list(TOOLS.keys()), help="Tên tool")
    parser.add_argument("--service", required=True)
    parser.add_argument("--time_window", required=True, help="VD: 14:00-15:00")
    parser.add_argument("--metric_name", default="latency_p99",
                        choices=["latency_p99", "error_rate", "request_count"])
    parser.add_argument("--scenario", default="scenario1")
    parser.add_argument("--date", default="2024-01-15")
    parser.add_argument("--raw", action="store_true",
                        help="In toàn bộ Observation thay vì chỉ render_for_llm")
    args = parser.parse_args()

    params = {
        "service": args.service,
        "time_window": args.time_window,
        "scenario": args.scenario,
        "date": args.date,
    }
    if args.tool == "get_metrics":
        params["metric_name"] = args.metric_name

    tool = TOOLS[args.tool]
    print(f"\n{'='*60}")
    print(f"Tool: {tool.name}")
    print(f"Params: {params}")
    print(f"{'='*60}\n")

    obs = tool.run(params)

    if args.raw:
        print("=== Raw Observation ===")
        print(f"summary     : {obs.summary}")
        print(f"aggregates  : {obs.aggregates}")
        print(f"samples     : {obs.samples}")
        print(f"total_count : {obs.total_count}")
        print(f"truncated   : {obs.truncated}")
        print(f"metadata    : {obs.metadata}")
    else:
        print("=== render_for_llm output ===")
        print(render_for_llm(obs))

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
