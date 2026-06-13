"""
Demo trigger — mô phỏng alert đến, chạy điều tra nền, push Telegram.

Usage:
    python scripts/trigger.py --scenario scenario1
    python scripts/trigger.py --scenario scenario2
    python scripts/trigger.py --scenario scenario1 --budget 8 --watch

--watch: in live trace ra console trong khi điều tra chạy (giống demo streaming).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from agent.intake.normalizer import map_simple_payload
from agent.intake.runner import run_investigation_background
from agent.output.telegram import render_telegram_message, render_partial_verdict_message

# Log format rõ cho demo
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)

SCENARIO_PAYLOADS = {
    "scenario1": {
        "service": "payment-gateway",
        "scenario": "scenario1",
        "time_window": "14:00-15:00",
        "date": "2024-01-15",
        "symptom": (
            "payment-gateway: tỷ lệ lỗi tăng đột biến từ 14:05, "
            "87% TimeoutException, latency p99 tăng gấp 9 lần baseline"
        ),
    },
    "scenario2": {
        "service": "payment-gateway",
        "scenario": "scenario2",
        "time_window": "15:00-16:00",
        "date": "2024-01-15",
        "symptom": (
            "payment-gateway: error rate tăng đột biến từ 15:11, "
            "92% ConnectionRefusedError — nghi lỗi từ downstream"
        ),
    },
}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger điều tra sự cố")
    parser.add_argument("--scenario", choices=["scenario1", "scenario2"], default="scenario1")
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--watch", action="store_true",
                        help="In trace live ra console")
    args = parser.parse_args()

    payload = SCENARIO_PAYLOADS[args.scenario]
    req = map_simple_payload(payload)

    print(f"\n{'='*60}")
    print(f"  TRIGGER: {args.scenario}")
    print(f"  Service : {req.service}")
    print(f"  Window  : {req.time_window}")
    print(f"  Budget  : {args.budget} bước")
    print(f"{'='*60}")
    print(f"\n[{time.strftime('%H:%M:%S')}] Alert nhận — bắt đầu điều tra nền...\n")

    # Chạy investigation (await trực tiếp cho demo đơn giản)
    await run_investigation_background(req, step_budget=args.budget)

    print(f"\n[{time.strftime('%H:%M:%S')}] Điều tra hoàn tất. Kiểm tra Telegram.")


if __name__ == "__main__":
    asyncio.run(main())
