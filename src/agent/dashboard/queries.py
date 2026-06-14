"""Query layer cho Dashboard — đọc trace_events, eval_results, projects."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agent.storage.db import open_db


def list_investigations(
    project_id: Optional[str] = None,
    confidence: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Danh sách investigations từ trace_events, mỗi inv_id là 1 hàng."""
    conn = open_db()

    # Lấy investigation_start event để biết symptom, scenario
    # Lấy verdict event để biết root_cause, confidence
    rows = conn.execute("""
        SELECT
            te.investigation_id,
            te.project_id,
            MIN(te.timestamp) AS started_at,
            MAX(CASE WHEN te.event_type='verdict' THEN te.timestamp END) AS finished_at,
            MAX(CASE WHEN te.event_type='investigation_start' THEN te.payload END) AS start_payload,
            MAX(CASE WHEN te.event_type='verdict' THEN te.payload END) AS verdict_payload,
            MAX(te.step) AS max_step
        FROM trace_events te
        GROUP BY te.investigation_id, te.project_id
        ORDER BY MIN(te.timestamp) DESC
        LIMIT ?
    """, (limit,)).fetchall()

    conn.close()

    result = []
    for r in rows:
        start = json.loads(r["start_payload"] or "{}")
        verdict = json.loads(r["verdict_payload"] or "{}")

        conf = verdict.get("confidence", "")
        if confidence and conf != confidence:
            continue
        if project_id and r["project_id"] != project_id:
            continue

        # Tính elapsed giây
        elapsed = None
        if r["started_at"] and r["finished_at"]:
            try:
                from datetime import datetime
                fmt = "%Y-%m-%dT%H:%M:%S.%f+00:00"
                def _parse(s):
                    for f in ("%Y-%m-%dT%H:%M:%S.%f+00:00",
                              "%Y-%m-%dT%H:%M:%S+00:00",
                              "%Y-%m-%dT%H:%M:%S.%fZ",
                              "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            return datetime.strptime(s, f)
                        except ValueError:
                            pass
                    return None
                t0 = _parse(r["started_at"])
                t1 = _parse(r["finished_at"])
                if t0 and t1:
                    elapsed = round((t1 - t0).total_seconds(), 1)
            except Exception:
                pass

        result.append({
            "investigation_id": r["investigation_id"],
            "project_id": r["project_id"],
            "started_at": (r["started_at"] or "")[:19].replace("T", " "),
            "elapsed_s": elapsed,
            "symptom": start.get("symptom", ""),
            "service": start.get("symptom", "").split(":")[0].strip() if ":" in start.get("symptom","") else "",
            "scenario": start.get("scenario", ""),
            "steps": r["max_step"] or 0,
            "root_cause": verdict.get("root_cause", ""),
            "confidence": conf,
            "stop_reason": verdict.get("stop_reason", ""),
        })

    return result


def get_investigation_detail(investigation_id: str) -> Optional[Dict[str, Any]]:
    """Chi tiết một investigation: summary + danh sách steps."""
    conn = open_db()
    rows = conn.execute("""
        SELECT step, timestamp, event_type, payload
        FROM trace_events
        WHERE investigation_id = ?
        ORDER BY step ASC, timestamp ASC
    """, (investigation_id,)).fetchall()
    conn.close()

    if not rows:
        return None

    events = []
    summary: Dict[str, Any] = {"investigation_id": investigation_id}

    for r in rows:
        payload = json.loads(r["payload"] or "{}")
        ts = (r["timestamp"] or "")[:19].replace("T", " ")

        if r["event_type"] == "investigation_start":
            summary["symptom"] = payload.get("symptom", "")
            summary["scenario"] = payload.get("scenario", "")
            summary["project_id"] = payload.get("project_id", "default")
            summary["started_at"] = ts
            summary["engine"] = payload.get("engine", "loop")

        elif r["event_type"] == "verdict":
            summary["root_cause"] = payload.get("root_cause", "")
            summary["confidence"] = payload.get("confidence", "")
            summary["stop_reason"] = payload.get("stop_reason", "")
            summary["finished_at"] = ts

        events.append({
            "step": r["step"],
            "timestamp": ts,
            "event_type": r["event_type"],
            "payload": payload,
        })

    # Nhóm sự kiện theo bước để hiển thị dễ hơn
    steps: Dict[int, Dict] = {}
    for ev in events:
        s = ev["step"]
        if s not in steps:
            steps[s] = {"step": s, "tool_call": None, "tool_result": None, "decision": None}
        if ev["event_type"] == "tool_call":
            steps[s]["tool_call"] = ev["payload"]
            steps[s]["timestamp"] = ev["timestamp"]
        elif ev["event_type"] == "tool_result":
            steps[s]["tool_result"] = ev["payload"]
        elif ev["event_type"] == "decision":
            steps[s]["decision"] = ev["payload"]

    summary["steps"] = [v for k, v in sorted(steps.items()) if k > 0]
    summary["raw_events"] = events
    return summary


def get_projects_overview() -> List[Dict[str, Any]]:
    """Projects + services + investigation count."""
    conn = open_db()
    projects = conn.execute(
        "SELECT id, name, description, llm_provider, llm_model FROM projects ORDER BY id"
    ).fetchall()

    result = []
    for p in projects:
        services = conn.execute(
            "SELECT service FROM project_services WHERE project_id=? ORDER BY service",
            (p["id"],),
        ).fetchall()

        inv_count = conn.execute(
            "SELECT COUNT(DISTINCT investigation_id) FROM trace_events WHERE project_id=?",
            (p["id"],),
        ).fetchone()[0]

        result.append({
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "services": [s["service"] for s in services],
            "investigation_count": inv_count,
            "llm_provider": p["llm_provider"] or "anthropic (env)",
            "llm_model": p["llm_model"] or "",
        })

    conn.close()
    return result


def get_eval_summary() -> List[Dict[str, Any]]:
    """Kết quả eval gần nhất per scenario."""
    conn = open_db()
    # Lấy run_id mới nhất
    latest = conn.execute(
        "SELECT run_id FROM eval_results ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not latest:
        conn.close()
        return []

    rows = conn.execute("""
        SELECT scenario,
               COUNT(*) as n,
               SUM(correct) as ok,
               AVG(steps_taken) as avg_steps,
               AVG(recall_at_1) as recall,
               SUM(hallucination) as hall,
               AVG(token_total) as avg_tokens
        FROM eval_results WHERE run_id=?
        GROUP BY scenario ORDER BY scenario
    """, (latest["run_id"],)).fetchall()
    conn.close()

    return [dict(r) for r in rows]
