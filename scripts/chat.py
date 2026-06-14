"""
CLI REPL — nhập thông tin sự cố → chạy investigation engine trực tiếp → in verdict.

Usage:
    python scripts/chat.py
    python scripts/chat.py --project default --multi-agent
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Thêm src vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


QUICK_SCENARIOS = {
    "1": {
        "service": "payment-gateway",
        "scenario": "scenario1",
        "time_window": "14:00-15:00",
        "symptom": "payment-gateway: tỷ lệ lỗi tăng đột biến từ 14:05, 87% TimeoutException",
    },
    "2": {
        "service": "payment-gateway",
        "scenario": "scenario2",
        "time_window": "15:00-16:00",
        "symptom": "payment-gateway: ConnectionRefusedError 92%, latency bình thường",
    },
    "3": {
        "service": "payment-gateway",
        "scenario": "scenario3",
        "time_window": "08:00-09:00",
        "symptom": "payment-gateway: AuthServiceTimeoutError 83% từ 08:11",
    },
    "4": {
        "service": "api-gateway",
        "scenario": "scenario4",
        "time_window": "10:00-11:00",
        "symptom": "api-gateway: RateLimitError tăng đột biến, request_count tăng 5x",
    },
}

BANNER = """
╔══════════════════════════════════════════════════════╗
║        Investigation Agent — CLI Chat v0.6           ║
║  Engine chạy trực tiếp (không qua HTTP server)       ║
╚══════════════════════════════════════════════════════╝

Quick scenarios (nhập số để chọn, hoặc Enter để nhập thủ công):
  [1] scenario1 — payment-gateway timeout (14:00-15:00)
  [2] scenario2 — provider sập (15:00-16:00)
  [3] scenario3 — DB pool exhaustion (08:00-09:00)
  [4] scenario4 — traffic surge (10:00-11:00)
  [q] Thoát
"""


def _input(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nThoát.")
        sys.exit(0)


def _print_verdict(state) -> None:
    v = state.verdict
    sep = "─" * 54
    print(f"\n{sep}")
    print(f"  VERDICT  [{getattr(v, 'confidence', '?').upper()}]")
    print(sep)
    if v:
        print(f"  Root cause : {v.root_cause}")
        print(f"  Spread     : {getattr(v, 'cascade', '') or getattr(v, 'affected_services', '')}")
        if getattr(v, 'recommended_action', None):
            print(f"  Action     : {v.recommended_action}")
        if getattr(v, 'evidence_ids', None):
            print(f"  Evidence   : {', '.join(v.evidence_ids)}")
    else:
        print("  (Không có verdict)")
    print(f"  Stop reason: {state.stop_reason}")
    print(f"  Steps      : {state.steps_taken} / {state.step_budget}")
    print(f"  Tokens     : {state.total_tokens}")
    print(sep)


async def _run(project_id: str, multi_agent: bool, step_budget: int) -> None:
    from agent.llm.factory import create_llm_client
    from agent.tools.registry import build_tool_registry
    from agent.engine.loop import InvestigationEngine
    from agent.engine.multi_agent import MultiAgentEngine

    while True:
        print(BANNER)
        choice = _input("Lựa chọn: ")

        if choice.lower() == "q":
            print("Thoát.")
            break

        if choice in QUICK_SCENARIOS:
            info = QUICK_SCENARIOS[choice]
            service = info["service"]
            scenario = info["scenario"]
            time_window = info["time_window"]
            symptom = info["symptom"]
        else:
            print("\n── Nhập thông tin sự cố ──")
            service = _input("Service (vd payment-gateway): ") or "payment-gateway"
            scenario = _input("Scenario (vd scenario1): ") or "scenario1"
            time_window = _input("Time window (vd 14:00-15:00): ") or "14:00-15:00"
            symptom = _input(f"Symptom (Enter để dùng mặc định): ")
            if not symptom:
                symptom = f"{service}: sự cố trong {time_window}"

        print(f"\n[→] Đang điều tra {service} · {scenario} · {time_window}")
        print(f"    Engine: {'multi_agent' if multi_agent else 'langgraph'}")
        print(f"    Project: {project_id}\n")

        try:
            llm = create_llm_client()
            tools = await build_tool_registry()

            if multi_agent:
                engine = MultiAgentEngine(llm=llm, all_tools=tools, step_budget=step_budget)
            else:
                engine = InvestigationEngine(llm=llm, tools=tools, step_budget=step_budget)

            state = await engine.run(
                symptom=symptom,
                time_window=time_window,
                scenario=scenario,
                project_id=project_id,
            )

            _print_verdict(state)

        except KeyboardInterrupt:
            print("\nHủy investigation.")
        except Exception as e:
            print(f"\n[!] Lỗi: {e}")

        again = _input("\nInvestigation khác? [Y/n]: ")
        if again.lower() == "n":
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Investigation Agent REPL")
    parser.add_argument("--project", default="default", help="Project ID (mặc định: default)")
    parser.add_argument("--multi-agent", action="store_true", help="Dùng MultiAgentEngine")
    parser.add_argument("--steps", type=int, default=10, help="Step budget (mặc định: 10)")
    args = parser.parse_args()

    # Nạp .env nếu có
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    asyncio.run(_run(
        project_id=args.project,
        multi_agent=args.multi_agent,
        step_budget=args.steps,
    ))


if __name__ == "__main__":
    main()
