"""
Script đánh giá agent: chạy N lần mỗi kịch bản, đếm tìm-đúng-root-cause.

Usage:
    python scripts/eval_agent.py                       # tất cả 4 kịch bản, 3 lần mỗi cái
    python scripts/eval_agent.py --scenario scenario1 --n 5
    python scripts/eval_agent.py --scenario scenario3 --n 5
    python scripts/eval_agent.py --mock                # dùng mock LLM (không cần API key)

Output: bảng kết quả mỗi run + tổng kết tỷ lệ đúng.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from agent.engine.loop import InvestigationEngine
from agent.engine.state import InvestigationState
from agent.llm.base import LLMClient, LLMResponse, Message, ToolCall, ToolSpec
from agent.tools.registry import get_tool_registry

logging.basicConfig(level=logging.WARNING)

# ── Ground truth cho từng kịch bản ───────────────────────────────────────────

SCENARIOS: Dict[str, Dict] = {
    "scenario1": {
        "symptom": (
            "payment-gateway: tỷ lệ lỗi tăng đột biến từ 14:05, "
            "87% TimeoutException, latency p99 tăng gấp 9 lần baseline"
        ),
        "time_window": "14:00-15:00",
        "date": "2024-01-15",
        "root_cause_keywords": ["v2.3.1", "deploy", "14:03", "payment-gateway"],
        "root_cause_service": "payment-gateway",
        "expected_confidence_min": "medium",
        "description": "Deploy v2.3.1 lúc 14:03 → timeout cascade",
    },
    "scenario2": {
        "symptom": (
            "payment-gateway: error rate tăng từ 15:10, ConnectionRefusedError 92%, "
            "nhưng latency gateway bình thường — nghi lỗi lan từ downstream"
        ),
        "time_window": "15:00-16:00",
        "date": "2024-01-15",
        "root_cause_keywords": ["third-party-provider", "provider", "sập", "unavailable"],
        "root_cause_service": "third-party-provider",
        "expected_confidence_min": "low",
        "description": "third-party-provider sập → lỗi lan ngược lên payment-gateway",
    },
    "scenario3": {
        "symptom": (
            "payment-gateway: lỗi tăng từ 08:11, AuthServiceTimeoutError 83%, "
            "latency tăng — nghi lỗi lan từ auth-service"
        ),
        "time_window": "08:00-09:00",
        "date": "2024-01-15",
        "root_cause_keywords": ["auth-service", "connection", "pool", "database"],
        "root_cause_service": "auth-service",
        "expected_confidence_min": "medium",
        "description": "auth-service DB connection pool exhaustion → cascade lên payment-gateway",
    },
    "scenario4": {
        "symptom": (
            "api-gateway: RateLimitError tăng đột biến từ 10:15, "
            "request_count tăng 5x baseline — nghi traffic surge"
        ),
        "time_window": "10:00-11:00",
        "date": "2024-01-15",
        "root_cause_keywords": ["traffic", "surge", "ratelimit", "rate_limit", "request_count"],
        "root_cause_service": "api-gateway",
        "expected_confidence_min": "medium",
        "description": "External traffic surge 5x → rate limiting tại api-gateway",
    },
}

CONF_RANK = {"high": 3, "medium": 2, "low": 1, "insufficient": 0}


# ── Mock LLMs cho eval không tốn API ─────────────────────────────────────────

class MockLLM_KB1:
    """Mock đi đúng KB1."""
    def __init__(self): self.call_count = 0
    async def complete(self, messages, tools, *, system=None):
        self.call_count += 1
        plan = [
            ToolCall("c1", "get_error_breakdown", {"service": "payment-gateway", "time_window": "14:00-15:00"}),
            ToolCall("c2", "get_metrics", {"service": "payment-gateway", "time_window": "14:00-15:00", "metric_name": "latency_p99"}),
            ToolCall("c3", "get_recent_deploys", {"time_window": "14:00-15:00"}),
        ]
        if self.call_count <= len(plan):
            return LLMResponse(tool_calls=[plan[self.call_count - 1]])
        return LLMResponse(text=(
            "VERDICT:\nRoot cause: Deploy v2.3.1 lúc 14:03 tại payment-gateway gây TimeoutException từ 14:05.\n"
            "Độ tin: CAO\nBằng chứng: 87% TimeoutException sau 14:05; latency 8.4x baseline; deploy v2.3.1 lúc 14:03.\n"
            "Lan truyền: Lỗi phát sinh tại payment-gateway.\nGiả thuyết cạnh tranh: Không có deploy nào ở service khác."
        ))


class MockLLM_KB2:
    """Mock đi đúng KB2 — xuyên service, loại trừ gateway là gốc."""
    def __init__(self): self.call_count = 0
    async def complete(self, messages, tools, *, system=None):
        self.call_count += 1
        plan = [
            ToolCall("c1", "get_error_breakdown", {"service": "payment-gateway", "time_window": "15:00-16:00", "scenario": "scenario2"}),
            ToolCall("c2", "get_metrics", {"service": "payment-gateway", "time_window": "15:00-16:00", "metric_name": "latency_p99", "scenario": "scenario2"}),
            ToolCall("c3", "get_dependencies", {"service": "payment-gateway"}),
            ToolCall("c4", "get_error_breakdown", {"service": "third-party-provider", "time_window": "15:00-16:00", "scenario": "scenario2"}),
            ToolCall("c5", "trace_request", {"service": "payment-gateway", "time_window": "15:10-16:00", "scenario": "scenario2"}),
        ]
        if self.call_count <= len(plan):
            return LLMResponse(tool_calls=[plan[self.call_count - 1]])
        return LLMResponse(text=(
            "VERDICT:\nRoot cause: third-party-provider sập từ 15:10, lỗi lan ngược lên payment-gateway.\n"
            "Độ tin: TRUNG BÌNH\nBằng chứng: Gateway latency bình thường (loại trừ gốc ở gateway); "
            "provider 82% ServiceUnavailableError; trace đứt tại gateway→provider.\n"
            "Lan truyền: Lỗi PHÁT SINH tại third-party-provider, LAN ĐẾN payment-gateway.\n"
            "Giả thuyết cạnh tranh: Gateway latency không lệch → loại trừ deploy/code gateway. Không có deploy trong window."
        ))


class MockLLM_KB3:
    """Mock đi đúng KB3 — xuyên service, tìm ra auth-service là gốc."""
    def __init__(self): self.call_count = 0
    async def complete(self, messages, tools, *, system=None):
        self.call_count += 1
        plan = [
            ToolCall("c1", "get_error_breakdown", {"service": "payment-gateway", "time_window": "08:00-09:00", "scenario": "scenario3"}),
            ToolCall("c2", "get_metrics", {"service": "payment-gateway", "time_window": "08:00-09:00", "metric_name": "latency_p99", "scenario": "scenario3"}),
            ToolCall("c3", "get_dependencies", {"service": "payment-gateway"}),
            ToolCall("c4", "get_error_breakdown", {"service": "auth-service", "time_window": "08:00-09:00", "scenario": "scenario3"}),
            ToolCall("c5", "get_metrics", {"service": "auth-service", "time_window": "08:00-09:00", "metric_name": "connection_wait_time", "scenario": "scenario3"}),
        ]
        if self.call_count <= len(plan):
            return LLMResponse(tool_calls=[plan[self.call_count - 1]])
        return LLMResponse(text=(
            "VERDICT:\nRoot cause: auth-service DB connection pool exhaustion từ 08:10, lỗi lan lên payment-gateway.\n"
            "Độ tin: CAO\nBằng chứng: payment-gateway 83% AuthServiceTimeoutError; "
            "auth-service connection_wait_time spike 5ms→855ms (171x baseline); auth-service latency 8x.\n"
            "Lan truyền: Lỗi PHÁT SINH tại auth-service (pool exhaustion), LAN ĐẾN payment-gateway.\n"
            "Giả thuyết cạnh tranh: Không có deploy trong window; third-party-provider bình thường; "
            "payment-gateway chỉ là nơi lỗi lan đến."
        ))


class MockLLM_KB4:
    """Mock đi đúng KB4 — nhận ra traffic surge, không phải code bug."""
    def __init__(self): self.call_count = 0
    async def complete(self, messages, tools, *, system=None):
        self.call_count += 1
        plan = [
            ToolCall("c1", "get_error_breakdown", {"service": "api-gateway", "time_window": "10:00-11:00", "scenario": "scenario4"}),
            ToolCall("c2", "get_metrics", {"service": "api-gateway", "time_window": "10:00-11:00", "metric_name": "request_count", "scenario": "scenario4"}),
            ToolCall("c3", "get_recent_deploys", {"time_window": "10:00-11:00", "scenario": "scenario4"}),
        ]
        if self.call_count <= len(plan):
            return LLMResponse(tool_calls=[plan[self.call_count - 1]])
        return LLMResponse(text=(
            "VERDICT:\nRoot cause: External traffic surge 5x từ 10:15 → rate_limit tại api-gateway.\n"
            "Độ tin: CAO\nBằng chứng: request_count spike 200→1000/phút (5x baseline); "
            "62% RateLimitError (không phải TimeoutException); không có deploy trong window.\n"
            "Lan truyền: Không lan — rate limiter chặn tại api-gateway, downstream bình thường.\n"
            "Giả thuyết cạnh tranh: Không có deploy (loại trừ code bug); "
            "downstream services bình thường (loại trừ cascade từ downstream)."
        ))


_MOCK_CLASSES = {
    "scenario1": MockLLM_KB1,
    "scenario2": MockLLM_KB2,
    "scenario3": MockLLM_KB3,
    "scenario4": MockLLM_KB4,
}


# ── Đánh giá một run ─────────────────────────────────────────────────────────

def evaluate_run(state: InvestigationState, scenario_config: Dict) -> Dict:
    verdict = state.verdict
    if verdict is None:
        return {
            "correct": False, "reason": "no_verdict", "confidence": "none",
            "steps": state.steps_taken, "recall_at_1": 0,
            "hallucination": 0, "token_total": state.total_tokens,
        }

    raw = (verdict.raw_text + " " + verdict.root_cause + " " + verdict.evidence_summary).lower()
    keywords = scenario_config["root_cause_keywords"]
    matched = [kw for kw in keywords if kw.lower() in raw]
    correct = len(matched) >= 2

    conf = verdict.confidence
    min_conf = scenario_config["expected_confidence_min"]
    conf_ok = CONF_RANK.get(conf, 0) >= CONF_RANK.get(min_conf, 0)

    # recall@1: service đúng có xuất hiện trong evidence của bước đầu tiên không
    target_service = scenario_config["root_cause_service"]
    recall_at_1 = 0
    if state.evidence:
        first_ev = state.evidence[0]
        first_raw = (first_ev.summary + str(first_ev.params)).lower()
        if target_service.lower() in first_raw:
            recall_at_1 = 1

    # hallucination check: verdict claim service nào không có evidence đỡ không
    hallucination = 0
    if verdict.root_cause:
        evidence_text = " ".join(e.summary for e in state.evidence).lower()
        rc_lower = verdict.root_cause.lower()
        if rc_lower and len(state.evidence) > 0:
            # Kiểm đơn giản: keyword chính trong root_cause có trong evidence không
            primary_kw = keywords[0].lower() if keywords else ""
            if primary_kw and primary_kw not in evidence_text and primary_kw in rc_lower:
                hallucination = 1  # claim về keyword nhưng không có evidence

    # token_efficiency: steps/token (đơn vị: steps per 1000 tokens)
    token_total = state.total_tokens

    return {
        "correct": correct,
        "confidence": conf,
        "conf_ok": conf_ok,
        "keywords_matched": matched,
        "steps": state.steps_taken,
        "stop_reason": state.stop_reason,
        "root_cause": verdict.root_cause[:80],
        "recall_at_1": recall_at_1,
        "hallucination": hallucination,
        "token_total": token_total,
    }


def _save_eval_results_to_db(
    run_id: str, scenario_id: str, results: List[Dict],
    provider: str = "mock", model: str = "",
) -> None:
    """Lưu kết quả eval vào bảng eval_results — qua storage seam (DB-agnostic)."""
    from agent.storage import get_database, get_db_path

    if not os.path.exists(get_db_path()):
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        db = get_database()
        with db.connection() as conn:
            for i, r in enumerate(results):
                conn.execute("""
                    INSERT INTO eval_results
                        (run_id, scenario, run_number, correct, confidence, recall_at_1,
                         steps_taken, hallucination, token_total, elapsed_s,
                         provider, model, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id, scenario_id, i + 1,
                    int(r.get("correct", False)),
                    r.get("confidence", "none"),
                    r.get("recall_at_1", 0),
                    r.get("steps", 0),
                    r.get("hallucination", 0),
                    r.get("token_total", 0),
                    r.get("elapsed_s"),
                    provider, model,
                    now,
                ))
    except Exception as e:
        print(f"[warn] Không lưu được eval_results: {e}")


# ── Chạy một kịch bản N lần ──────────────────────────────────────────────────

async def run_scenario_n_times(
    scenario_id: str,
    n: int,
    use_mock: bool,
    budget: int,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> List[Dict]:
    cfg = SCENARIOS[scenario_id]
    tools = get_tool_registry()
    results = []

    for i in range(n):
        if use_mock:
            llm = _MOCK_CLASSES[scenario_id]()
        else:
            from agent.llm.factory import create_llm_client
            llm = create_llm_client(provider=provider, model=model)

        engine = InvestigationEngine(llm=llm, tools=tools, step_budget=budget)
        t0 = time.time()
        state = await engine.run(
            symptom=cfg["symptom"],
            time_window=cfg["time_window"],
            scenario=scenario_id,
            date=cfg["date"],
        )
        elapsed = time.time() - t0
        result = evaluate_run(state, cfg)
        result["run"] = i + 1
        result["elapsed_s"] = round(elapsed, 1)
        results.append(result)

        mark = "✅" if result["correct"] else "❌"
        hall = "⚠️ hall" if result.get("hallucination") else ""
        print(f"  Run {i+1}: {mark} correct={result['correct']} conf={result['confidence']} "
              f"steps={result['steps']} recall@1={result.get('recall_at_1',0)} "
              f"tokens={result.get('token_total',0)} {hall} ({elapsed:.1f}s)")
        print(f"         root_cause: {result['root_cause']}")

    return results


def print_summary(scenario_id: str, results: List[Dict]) -> None:
    n = len(results)
    correct = sum(1 for r in results if r["correct"])
    conf_ok = sum(1 for r in results if r.get("conf_ok"))
    avg_steps = sum(r["steps"] for r in results) / n if n else 0
    recall_rate = sum(r.get("recall_at_1", 0) for r in results) / n if n else 0
    hall_count = sum(r.get("hallucination", 0) for r in results)
    avg_tokens = sum(r.get("token_total", 0) for r in results) / n if n else 0

    rate = correct * 100 // n if n else 0
    gate = "✅ PASS" if rate >= 70 else "❌ FAIL"
    print(f"\n{'='*58}")
    print(f"  {scenario_id}: {correct}/{n} đúng root cause ({rate}%)  {gate}")
    print(f"  Confidence OK: {conf_ok}/{n}  |  Avg steps: {avg_steps:.1f}")
    print(f"  Recall@1: {recall_rate:.0%}  |  Hallucination: {hall_count}/{n}  |  Avg tokens: {avg_tokens:.0f}")
    print(f"  Stop reasons: {set(r['stop_reason'] for r in results)}")
    print(f"{'='*58}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=["scenario1", "scenario2", "scenario3", "scenario4", "all"],
        default="all",
    )
    parser.add_argument("--n", type=int, default=3, help="Số lần chạy mỗi kịch bản")
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--mock", action="store_true", help="Dùng mock LLM (không cần API key)")
    parser.add_argument("--provider", default=None, help="Override LLM provider (mặc định: env LLM_PROVIDER)")
    parser.add_argument("--model", default=None, help="Override LLM model (mặc định: env LLM_MODEL)")
    args = parser.parse_args()

    scenarios_to_run = (
        list(SCENARIOS.keys()) if args.scenario == "all"
        else [args.scenario]
    )

    if args.mock:
        provider_label, model_label = "mock", "mock"
    else:
        provider_label = args.provider or os.environ.get("LLM_PROVIDER", "anthropic")
        model_label = args.model or os.environ.get("LLM_MODEL", "") or "(default)"
    mode = "MOCK LLM" if args.mock else f"REAL LLM [{provider_label}/{model_label}]"
    print(f"\n{'='*58}")
    print(f"  Eval agent — {mode} — {args.n} runs/scenario — budget={args.budget}")
    print(f"  Kịch bản: {scenarios_to_run}")
    print(f"{'='*58}")

    run_id = str(uuid.uuid4())[:12]
    all_results = {}
    for sc in scenarios_to_run:
        print(f"\n--- {sc}: {SCENARIOS[sc]['description']} ---")
        results = await run_scenario_n_times(
            sc, args.n, args.mock, args.budget,
            provider=args.provider, model=args.model,
        )
        all_results[sc] = results
        print_summary(sc, results)
        _save_eval_results_to_db(run_id, sc, results, provider=provider_label, model=model_label)

    if len(scenarios_to_run) > 1:
        total_runs = sum(len(r) for r in all_results.values())
        total_correct = sum(sum(1 for x in r if x["correct"]) for r in all_results.values())
        rate = total_correct * 100 // total_runs if total_runs else 0
        print(f"\nTOTAL: {total_correct}/{total_runs} runs đúng root cause ({rate}%)")
        # Kiểm cổng: tất cả scenario >= 70%
        all_pass = all(
            sum(1 for x in r if x["correct"]) * 100 // len(r) >= 70
            for r in all_results.values()
        )
        print(f"CỔNG NGÀY 12: {'✅ PASS — tất cả kịch bản ≥70%' if all_pass else '❌ FAIL — có kịch bản <70%'}")
    print(f"\n[run_id={run_id}] Kết quả đã lưu vào data/investigation.db (bảng eval_results)")


if __name__ == "__main__":
    asyncio.run(main())
