"""
Đánh giá agent cho 2 kịch bản Fintech.

Usage:
    python scripts/eval_fintech.py              # mock LLM, 2 kịch bản × 1 lần
    python scripts/eval_fintech.py --n 3        # 3 lần mỗi kịch bản
    python scripts/eval_fintech.py --api        # dùng API thật (cần ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from agent.engine.loop import InvestigationEngine
from agent.engine.state import InvestigationState
from agent.llm.base import LLMClient, LLMResponse, ToolCall
from agent.tools.registry_fintech import get_fintech_tool_registry

# ── Ground truth ──────────────────────────────────────────────────────────────

SCENARIOS: Dict[str, Dict] = {
    "fintech1": {
        "symptom": (
            "credit_card channel: tỷ lệ fail tăng từ 10:15, "
            "65% ProcessorTimeoutError — nghi lỗi payment processor"
        ),
        "time_window": "10:00-11:00",
        "date": "2024-01-15",
        "root_cause_keywords": ["proc-alpha", "processor", "timeout", "credit_card"],
        "root_cause_service": "proc-alpha",
        "expected_confidence_min": "medium",
        "description": "proc-alpha timeout từ 10:15 → 65% fail trên credit_card",
    },
    "fintech2": {
        "symptom": (
            "merch-buzz: refund_rate tăng đột biến từ 14:00, "
            "14.8% (~8x baseline 1.9%) — nghi price bug"
        ),
        "time_window": "14:00-15:00",
        "date": "2024-01-15",
        "root_cause_keywords": ["merch-buzz", "price", "refund", "bug"],
        "root_cause_service": "merch-buzz",
        "expected_confidence_min": "medium",
        "description": "merch-buzz price bug → refund_rate 8x baseline",
    },
}

CONF_RANK = {"high": 3, "medium": 2, "low": 1, "insufficient": 0}


# ── Mock LLMs ─────────────────────────────────────────────────────────────────

class MockLLM_FT1:
    """Mock đi đúng KB-F1: proc-alpha timeout → credit_card fail."""
    def __init__(self): self.call_count = 0

    async def complete(self, messages, tools, *, system=None):
        self.call_count += 1
        plan = [
            ToolCall("f1c1", "get_revenue_breakdown",
                     {"time_window": "10:00-11:00", "scenario": "fintech1"}),
            ToolCall("f1c2", "get_transaction_anomaly",
                     {"time_window": "10:00-11:00", "scenario": "fintech1"}),
            ToolCall("f1c3", "get_merchant_status",
                     {"scenario": "fintech1", "merchant_id": "proc-alpha"}),
        ]
        if self.call_count <= len(plan):
            return LLMResponse(tool_calls=[plan[self.call_count - 1]])
        return LLMResponse(text=(
            "VERDICT:\n"
            "Root cause: proc-alpha payment processor timeout từ 10:15 gây 65% fail trên kênh credit_card.\n"
            "Độ tin: CAO\n"
            "Bằng chứng: credit_card revenue giảm ~99% so baseline; "
            "ProcessorTimeoutError chiếm 65% fail; proc-alpha processor báo timeout từ 10:15.\n"
            "Lan truyền: Lỗi phát sinh tại proc-alpha, lan đến credit_card channel.\n"
            "Giả thuyết cạnh tranh: debit_card và e_wallet bình thường — xác nhận vấn đề tập trung ở proc-alpha."
        ))


class MockLLM_FT2:
    """Mock đi đúng KB-F2: merch-buzz price bug → refund_rate 8x baseline."""
    def __init__(self): self.call_count = 0

    async def complete(self, messages, tools, *, system=None):
        self.call_count += 1
        plan = [
            ToolCall("f2c1", "get_transaction_anomaly",
                     {"time_window": "14:00-15:00", "scenario": "fintech2"}),
            ToolCall("f2c2", "get_merchant_status",
                     {"scenario": "fintech2", "merchant_id": "merch-buzz"}),
            ToolCall("f2c3", "get_settlement_lag",
                     {"time_window": "14:00-15:00", "scenario": "fintech2"}),
        ]
        if self.call_count <= len(plan):
            return LLMResponse(tool_calls=[plan[self.call_count - 1]])
        return LLMResponse(text=(
            "VERDICT:\n"
            "Root cause: merch-buzz price bug từ 14:00 gây refund_rate 14.8% (~8x baseline 1.9%).\n"
            "Độ tin: CAO\n"
            "Bằng chứng: merch-buzz refund_rate 14.8% (8x baseline); "
            "merchant notes price_bug_reported; settlement_lag tăng tại merch-buzz.\n"
            "Lan truyền: Lỗi phát sinh tại merch-buzz (price bug), không lan đến merchant khác.\n"
            "Giả thuyết cạnh tranh: merch-a, merch-b, merch-c refund_rate bình thường — "
            "xác nhận vấn đề tập trung ở merch-buzz."
        ))


_MOCK_CLASSES = {
    "fintech1": MockLLM_FT1,
    "fintech2": MockLLM_FT2,
}


# ── Đánh giá một run ─────────────────────────────────────────────────────────

def evaluate_run(state: InvestigationState, cfg: Dict) -> Dict:
    verdict = state.verdict
    if verdict is None:
        return {
            "correct": False, "reason": "no_verdict", "confidence": "none",
            "steps": state.steps_taken, "recall_at_1": 0,
            "hallucination": 0, "token_total": state.total_tokens,
        }

    raw = (verdict.raw_text + " " + verdict.root_cause + " " + verdict.evidence_summary).lower()
    keywords = cfg["root_cause_keywords"]
    matched = [kw for kw in keywords if kw.lower() in raw]
    correct = len(matched) >= 2

    conf = verdict.confidence
    min_conf = cfg["expected_confidence_min"]
    conf_ok = CONF_RANK.get(conf, 0) >= CONF_RANK.get(min_conf, 0)

    target_service = cfg["root_cause_service"]
    recall_at_1 = 0
    if state.evidence:
        first_ev = state.evidence[0]
        first_raw = (first_ev.summary + str(first_ev.params)).lower()
        if target_service.lower() in first_raw:
            recall_at_1 = 1

    hallucination = 0
    if verdict.root_cause:
        evidence_text = " ".join(e.summary for e in state.evidence).lower()
        primary_kw = keywords[0].lower() if keywords else ""
        if primary_kw and primary_kw not in evidence_text and primary_kw in verdict.root_cause.lower():
            hallucination = 1

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
        "token_total": state.total_tokens,
    }


def _save_eval_to_db(run_id: str, scenario_id: str, results: List[Dict]) -> None:
    db_path = Path(__file__).parent.parent / "data" / "investigation.db"
    if not db_path.exists():
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = sqlite3.connect(str(db_path))
        for i, r in enumerate(results):
            conn.execute("""
                INSERT INTO eval_results
                    (run_id, scenario, run_number, correct, confidence, recall_at_1,
                     steps_taken, hallucination, token_total, elapsed_s, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, scenario_id, i + 1,
                int(r.get("correct", False)),
                r.get("confidence", "none"),
                r.get("recall_at_1", 0),
                r.get("steps", 0),
                r.get("hallucination", 0),
                r.get("token_total", 0),
                r.get("elapsed_s"),
                now,
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[warn] Không lưu eval_results: {e}")


# ── Chạy N lần ──────────────────────────────────────────────────────────────

async def run_scenario_n_times(scenario_id: str, n: int, use_mock: bool) -> List[Dict]:
    cfg = SCENARIOS[scenario_id]
    tools = get_fintech_tool_registry()
    results = []

    for i in range(n):
        if use_mock:
            llm = _MOCK_CLASSES[scenario_id]()
        else:
            from agent.llm.factory import create_llm_client
            llm = create_llm_client()

        engine = InvestigationEngine(llm=llm, tools=tools, step_budget=8)
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
        hall = " ⚠️ hall" if result.get("hallucination") else ""
        print(f"  Run {i+1}: {mark} correct={result['correct']} conf={result['confidence']} "
              f"steps={result['steps']} recall@1={result.get('recall_at_1',0)}{hall} ({elapsed:.1f}s)")
        print(f"         root_cause: {result['root_cause']}")

    return results


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), default=None)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--api", action="store_true", help="Dùng API thật thay vì mock")
    args = parser.parse_args()

    use_mock = not args.api
    run_id = str(uuid.uuid4())[:8]
    scenarios_to_run = [args.scenario] if args.scenario else list(SCENARIOS.keys())

    print(f"\n{'='*60}")
    print(f"Fintech Eval · run_id={run_id} · {'API' if not use_mock else 'Mock'} · N={args.n}")
    print(f"{'='*60}")

    all_pass = True
    for sc_id in scenarios_to_run:
        cfg = SCENARIOS[sc_id]
        print(f"\n[{sc_id}] {cfg['description']}")
        results = await run_scenario_n_times(sc_id, args.n, use_mock)
        _save_eval_to_db(run_id, sc_id, results)

        correct = sum(1 for r in results if r["correct"])
        avg_steps = sum(r["steps"] for r in results) / len(results)
        print(f"  → {correct}/{args.n} PASS · avg_steps={avg_steps:.1f}")
        if correct < args.n:
            all_pass = False

    print(f"\n{'='*60}")
    print(f"{'✅ TẤT CẢ PASS' if all_pass else '❌ CÓ SCENARIO FAIL'}")
    print(f"{'='*60}\n")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
