"""
Trigger kịch bản điều tra end-to-end và in kết quả.

Usage:
    python scripts/run_scenario.py
    python scripts/run_scenario.py --scenario scenario1 --budget 10
    python scripts/run_scenario.py --symptom "payment-gateway: 87% timeout" --window 14:00-15:00
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Thêm src vào path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from agent.engine.loop import InvestigationEngine
from agent.engine.state import InvestigationState
from agent.llm.factory import create_llm_client
from agent.tools.contracts import render_for_llm
from agent.tools.registry import get_tool_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def render_verdict(state: InvestigationState) -> str:
    lines = [
        "=" * 60,
        "VERDICT",
        "=" * 60,
    ]
    if state.verdict:
        v = state.verdict
        lines += [
            f"Root cause  : {v.root_cause}",
            f"Độ tin      : {v.confidence.upper()}",
            f"Bằng chứng  : {v.evidence_summary}",
            f"Lan truyền  : {v.propagation_note}",
            f"Cạnh tranh  : {v.competing_hypotheses}",
            "",
            "--- Raw ---",
            v.raw_text,
        ]
    else:
        lines.append("(Không có verdict)")

    lines += [
        "",
        f"Stop reason : {state.stop_reason}",
        f"Số bước     : {state.steps_taken}/{state.step_budget}",
        f"Bằng chứng  : {len(state.evidence)} Observation",
        f"Investigation ID: {state.investigation_id}",
    ]
    return "\n".join(lines)


def render_trace(state: InvestigationState) -> str:
    lines = ["\n--- Dấu vết điều tra ---"]
    for ev in state.evidence:
        lines.append(f"  Bước {ev.step + 1}: [{ev.tool_name}] {ev.summary}")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy điều tra sự cố end-to-end")
    parser.add_argument("--scenario", default="scenario1",
                        help="Kịch bản: scenario1 hoặc scenario2")
    parser.add_argument("--symptom", default=None,
                        help="Mô tả triệu chứng (tự động nếu không chỉ định)")
    parser.add_argument("--window", default=None,
                        help="Time window HH:MM-HH:MM (tự động theo kịch bản nếu bỏ qua)")
    parser.add_argument("--date", default="2024-01-15",
                        help="Ngày YYYY-MM-DD")
    parser.add_argument("--budget", type=int, default=10,
                        help="Số bước tối đa")
    args = parser.parse_args()

    # Symptom và window mặc định theo kịch bản
    symptom = args.symptom
    window = args.window
    if args.scenario == "scenario1":
        symptom = symptom or (
            "payment-gateway: tỷ lệ lỗi tăng đột biến từ 14:05, "
            "87% TimeoutException, latency p99 tăng gấp 9 lần baseline"
        )
        window = window or "14:00-15:00"
    else:
        symptom = symptom or (
            "payment-gateway: error rate tăng đột biến từ 15:11, "
            "92% ConnectionRefusedError — nghi lỗi từ downstream"
        )
        window = window or "15:00-16:00"

    print(f"\n{'='*60}")
    print(f"Kịch bản  : {args.scenario}")
    print(f"Triệu chứng: {symptom}")
    print(f"Time window: {window}")
    print(f"Budget     : {args.budget} bước")
    print(f"{'='*60}\n")

    llm = create_llm_client()
    tools = get_tool_registry()

    print(f"Tools ({len(tools)}): {', '.join(t.name for t in tools)}")
    print(f"LLM: {type(llm).__name__}\n")

    engine = InvestigationEngine(llm=llm, tools=tools, step_budget=args.budget)

    try:
        state = await engine.run(
            symptom=symptom,
            time_window=window,
            scenario=args.scenario,
            date=args.date,
        )
    except KeyboardInterrupt:
        print("\n[Interrupted]")
        return

    print(render_trace(state))
    print()
    print(render_verdict(state))


if __name__ == "__main__":
    asyncio.run(main())
