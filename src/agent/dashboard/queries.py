"""Query layer cho Dashboard — đọc trace_events, eval_results, projects."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.storage.db import open_db


def parse_investigation_id(inv_id: str) -> Dict[str, str]:
    """dedup_key = '{project}|{service}|{scenario}|{time_window}' → các phần (best-effort).

    Trả {} nếu không đúng 4 phần (id lạ / format cũ) để caller fallback an toàn.
    """
    parts = (inv_id or "").split("|")
    if len(parts) == 4:
        return {
            "project": parts[0],
            "service": parts[1],
            "scenario": parts[2],
            "time_window": parts[3],
        }
    return {}


def short_investigation_code(inv_id: str) -> str:
    """Mã ngắn ổn định cho hiển thị (hash 6 hex của dedup_key đầy đủ)."""
    return hashlib.sha1((inv_id or "").encode()).hexdigest()[:6]

# ── Cost estimation ───────────────────────────────────────────────────────────

_PRICING: Dict[str, Dict[str, tuple]] = {
    "anthropic": {
        # Khớp theo substring trong model ID (vd: claude-haiku-4-5-20251001 → "haiku")
        "opus":    (15.00, 75.00),
        "sonnet":  (3.00,  15.00),
        "haiku":   (0.80,  4.00),
        "":        (3.00,  15.00),  # default sonnet
    },
    "openai": {
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4o":      (5.00, 15.00),
        "":            (3.00, 15.00),
    },
    "gemini": {"": (0.35, 1.05)},
    "groq":   {"": (0.05, 0.10)},
    "mock":   {"": (0.00, 0.00)},
}


def _get_pricing(provider: str, model: str):
    provider = (provider or "mock").lower()
    model = (model or "").lower()
    tiers = _PRICING.get(provider, {"": (0.0, 0.0)})
    # Dùng `in` thay vì startswith để khớp model ID thật như claude-haiku-4-5-20251001
    for keyword, prices in tiers.items():
        if keyword and keyword in model:
            return prices
    return tiers.get("", (0.0, 0.0))


def _cost_usd(tokens: int, provider: str, model: str) -> float:
    """Ước tính cost USD — giả định 60% input / 40% output."""
    if not tokens:
        return 0.0
    in_p, out_p = _get_pricing(provider, model)
    return (tokens * 0.60 * in_p + tokens * 0.40 * out_p) / 1_000_000


def get_cost_data() -> Dict[str, Any]:
    """Cost breakdown từ eval_results (token thật từ D21) + live investigations."""
    conn = open_db()

    # Per-scenario cost từ eval
    rows = conn.execute("""
        SELECT e.scenario,
               COUNT(*) as n,
               AVG(e.token_total) as avg_tokens,
               SUM(e.token_total) as total_tokens,
               MAX(e.provider) as provider,
               MAX(e.model) as model
        FROM eval_results e
        INNER JOIN (
            SELECT scenario, MAX(created_at) AS latest_at
            FROM eval_results GROUP BY scenario
        ) latest ON e.scenario=latest.scenario AND e.created_at=latest.latest_at
        WHERE e.token_total > 0
        GROUP BY e.scenario
        ORDER BY e.scenario
    """).fetchall()

    # Live investigations với total_tokens trong verdict payload
    live = conn.execute("""
        SELECT COUNT(DISTINCT investigation_id) AS n_inv,
               SUM(CAST(json_extract(payload,'$.total_tokens') AS INTEGER)) AS total_tokens
        FROM trace_events
        WHERE event_type='verdict'
          AND CAST(json_extract(payload,'$.total_tokens') AS INTEGER) > 0
    """).fetchone()

    # P1: Cache savings — sum cache_read/write tokens from verdict events
    cache_row = conn.execute("""
        SELECT
            COUNT(DISTINCT investigation_id) AS n_cached,
            SUM(COALESCE(CAST(json_extract(payload,'$.cache_read_tokens') AS INTEGER), 0))
                AS total_cache_reads,
            SUM(COALESCE(CAST(json_extract(payload,'$.cache_creation_tokens') AS INTEGER), 0))
                AS total_cache_writes
        FROM trace_events
        WHERE event_type='verdict'
    """).fetchone()

    conn.close()

    scenarios = []
    grand_tokens = 0
    grand_cost   = 0.0
    for r in rows:
        d = dict(r)
        avg_tok  = int(d["avg_tokens"] or 0)
        tot_tok  = int(d["total_tokens"] or 0)
        prov     = d["provider"] or "mock"
        mod      = d["model"] or ""
        cost_run = _cost_usd(avg_tok, prov, mod)
        cost_tot = _cost_usd(tot_tok, prov, mod)
        d.update({
            "avg_tokens": avg_tok,
            "total_tokens": tot_tok,
            "cost_per_run": round(cost_run, 5),
            "total_cost":   round(cost_tot, 4),
        })
        grand_tokens += tot_tok
        grand_cost   += cost_tot
        scenarios.append(d)

    live_d = dict(live) if live else {}
    live_tokens = int(live_d.get("total_tokens") or 0)

    cache_reads  = int((cache_row["total_cache_reads"]  or 0) if cache_row else 0)
    cache_writes = int((cache_row["total_cache_writes"] or 0) if cache_row else 0)
    n_cached     = int((cache_row["n_cached"]           or 0) if cache_row else 0)
    # Anthropic pricing: cache_read = 10% of standard input; cache_write = 125%
    in_price_per_tok = _get_pricing("anthropic", "sonnet")[0] / 1_000_000
    cache_savings_usd = round(cache_reads * in_price_per_tok * 0.90, 5)  # discount vs no-cache
    cache_extra_cost  = round(cache_writes * in_price_per_tok * 0.25, 5) # write overhead

    return {
        "scenarios": scenarios,
        "grand_total_tokens": grand_tokens,
        "grand_total_cost":   round(grand_cost, 4),
        "live_n_inv":         int(live_d.get("n_inv") or 0),
        "live_total_tokens":  live_tokens,
        "live_total_cost":    round(_cost_usd(live_tokens, "anthropic", "sonnet"), 4),
        # P1: Prompt caching stats
        "cache_n_inv":        n_cached,
        "cache_reads":        cache_reads,
        "cache_writes":       cache_writes,
        "cache_savings_usd":  cache_savings_usd,
        "cache_extra_cost":   cache_extra_cost,
        "cache_net_savings":  round(cache_savings_usd - cache_extra_cost, 5),
    }


# ── Investigation Feedback ────────────────────────────────────────────────────

def get_investigation_feedback(investigation_id: str) -> Optional[int]:
    """Returns 1 (👍), -1 (👎), hoặc None nếu chưa có."""
    conn = open_db()
    row = conn.execute(
        "SELECT score FROM investigation_feedback WHERE investigation_id=?",
        (investigation_id,)
    ).fetchone()
    conn.close()
    return int(row["score"]) if row else None


def set_investigation_feedback(investigation_id: str, score: int) -> None:
    """Upsert feedback (1 or -1). Optionally push Langfuse score nếu configured."""
    now = datetime.now(timezone.utc).isoformat()
    conn = open_db()
    conn.execute("""
        INSERT INTO investigation_feedback (investigation_id, score, created_at, updated_at)
        VALUES (?,?,?,?)
        ON CONFLICT(investigation_id) DO UPDATE SET score=excluded.score, updated_at=excluded.updated_at
    """, (investigation_id, score, now, now))
    conn.commit()
    conn.close()

    # Langfuse score (opt-in — chỉ khi LANGFUSE_PUBLIC_KEY set)
    try:
        import os
        if os.getenv("LANGFUSE_PUBLIC_KEY"):
            from langfuse import Langfuse
            lf = Langfuse()
            lf.score(
                trace_id=investigation_id,
                name="human_feedback",
                value=float(score),
                comment="thumbs_up" if score > 0 else "thumbs_down",
            )
    except Exception:
        pass


def delete_investigation(investigation_id: str) -> None:
    """Xóa toàn bộ trace_events + feedback của một investigation."""
    conn = open_db()
    conn.execute("DELETE FROM trace_events WHERE investigation_id = ?", (investigation_id,))
    conn.execute("DELETE FROM investigation_feedback WHERE investigation_id = ?", (investigation_id,))
    conn.commit()
    conn.close()


def list_investigations(
    project_id: Optional[str] = None,
    confidence: Optional[str] = None,
    search: Optional[str] = None,
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
        if search:
            term = search.lower()
            haystack = (
                (r["start_payload"] or "").lower()
                + " " + (r["verdict_payload"] or "").lower()
            )
            if term not in haystack:
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

        # Ưu tiên parse từ investigation_id (đáng tin) → fallback symptom/start payload.
        parsed = parse_investigation_id(r["investigation_id"])
        symptom = start.get("symptom", "")
        service = parsed.get("service") or (
            symptom.split(":")[0].strip() if ":" in symptom else ""
        )
        scenario = parsed.get("scenario") or start.get("scenario", "")

        result.append({
            "investigation_id": r["investigation_id"],
            "short_id": short_investigation_code(r["investigation_id"]),
            "project_id": r["project_id"],
            "started_at": (r["started_at"] or "")[:19].replace("T", " "),
            "elapsed_s": elapsed,
            "symptom": symptom,
            "service": service,
            "scenario": scenario,
            "time_window": parsed.get("time_window", ""),
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
    _parsed = parse_investigation_id(investigation_id)
    summary: Dict[str, Any] = {
        "investigation_id": investigation_id,
        "short_id": short_investigation_code(investigation_id),
        "service": _parsed.get("service", ""),
        "time_window": _parsed.get("time_window", ""),
    }

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


def get_metrics_live(service: Optional[str] = None) -> List[Dict[str, Any]]:
    """Baseline vs hiện tại mỗi metric_name × service."""
    conn = open_db()

    params: list = []
    service_clause = ""
    if service:
        service_clause = "WHERE m.service = ?"
        params.append(service)

    rows = conn.execute(f"""
        SELECT
            m.service,
            m.scenario,
            m.metric_name,
            ROUND(AVG(CASE WHEN m.is_baseline=0 THEN m.value END)::numeric, 2) AS current_avg,
            ROUND(AVG(CASE WHEN m.is_baseline=1 THEN m.value END)::numeric, 2) AS baseline_avg,
            COUNT(CASE WHEN m.is_baseline=0 THEN 1 END) AS current_samples,
            MAX(CASE WHEN m.is_baseline=0 THEN m.timestamp END) AS last_ts
        FROM metrics m
        {service_clause}
        GROUP BY m.service, m.scenario, m.metric_name
        ORDER BY m.service, m.metric_name
    """, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        cur = r["current_avg"] or 0
        base = r["baseline_avg"] or 0
        pct_change = round((cur - base) / base * 100, 1) if base else None
        result.append({
            "service": r["service"],
            "scenario": r["scenario"],
            "metric_name": r["metric_name"],
            "current_avg": cur,
            "baseline_avg": base,
            "pct_change": pct_change,
            "current_samples": r["current_samples"],
            "last_ts": (r["last_ts"] or "")[:19].replace("T", " "),
        })
    return result


def get_channel_config() -> List[Dict[str, Any]]:
    """Alert channel config: mỗi hàng là (project_id, channel, enabled, config)."""
    conn = open_db()
    # Lấy tất cả project × channel chuẩn; join bảng config
    projects = conn.execute("SELECT id FROM projects ORDER BY id").fetchall()
    channels = ["telegram", "teams", "email"]

    result = []
    for p in projects:
        pid = p["id"]
        for ch in channels:
            row = conn.execute(
                "SELECT enabled, config FROM project_alert_channels WHERE project_id=? AND channel=?",
                (pid, ch),
            ).fetchone()
            enabled = row["enabled"] if row else 0
            config_str = row["config"] if row else "{}"
            result.append({
                "project_id": pid,
                "channel": ch,
                "enabled": bool(enabled),
                "config": config_str,
            })
    conn.close()
    return result


def get_all_tools_for_dashboard() -> dict:
    """Trả {domain: [tool_dict]} cho Tool Registry Viewer."""
    from agent.tools.registry import ALL_LOCAL_TOOLS
    from agent.tools.registry_fintech import ALL_FINTECH_TOOLS

    def _fmt(tools):
        return [{"name": t.name, "description": t.description,
                 "params": list(t.input_schema.get("properties", {}).keys())}
                for t in tools]

    return {
        "microservice": _fmt(ALL_LOCAL_TOOLS),
        "fintech": _fmt(ALL_FINTECH_TOOLS),
    }


def get_mcp_servers_for_dashboard() -> List[Dict[str, Any]]:
    """Tất cả MCP servers kèm project name."""
    conn = open_db()
    rows = conn.execute("""
        SELECT m.id, m.name, m.url, m.description, m.enabled, m.project_id,
               m.auth_type, m.auth_config, p.name AS project_name
        FROM mcp_servers m
        LEFT JOIN projects p ON p.id = m.project_id
        ORDER BY m.project_id, m.created_at
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project_detail(project_id: str) -> Optional[Dict[str, Any]]:
    """Chi tiết một project: info + services + MCP + channels + recent investigations."""
    conn = open_db()
    p = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not p:
        conn.close()
        return None

    services = [
        {"service": r["service"], "description": (r["description"] or "")}
        for r in conn.execute(
            "SELECT service, description FROM project_services "
            "WHERE project_id=? ORDER BY service",
            (project_id,),
        ).fetchall()
    ]

    mcp_servers = [dict(r) for r in conn.execute(
        "SELECT id, name, url, enabled, auth_type FROM mcp_servers WHERE project_id=? ORDER BY created_at",
        (project_id,),
    ).fetchall()]

    channels_raw = conn.execute(
        "SELECT channel, enabled, config FROM project_alert_channels WHERE project_id=? ORDER BY channel",
        (project_id,),
    ).fetchall()
    channels = {r["channel"]: {"enabled": bool(r["enabled"]), "config": r["config"] or "{}"} for r in channels_raw}
    for ch in ["telegram", "teams", "email", "slack"]:
        if ch not in channels:
            channels[ch] = {"enabled": False, "config": "{}"}

    recent_invs = conn.execute("""
        SELECT te.investigation_id,
               MIN(te.timestamp) AS started_at,
               MAX(CASE WHEN te.event_type='verdict' THEN te.payload END) AS verdict_payload,
               MAX(CASE WHEN te.event_type='investigation_start' THEN te.payload END) AS start_payload
        FROM trace_events te
        WHERE te.project_id=?
        GROUP BY te.investigation_id
        ORDER BY MIN(te.timestamp) DESC
        LIMIT 10
    """, (project_id,)).fetchall()

    inv_list = []
    for r in recent_invs:
        start = json.loads(r["start_payload"] or "{}")
        verdict = json.loads(r["verdict_payload"] or "{}")
        inv_list.append({
            "investigation_id": r["investigation_id"],
            "started_at": (r["started_at"] or "")[:19].replace("T", " "),
            "scenario": start.get("scenario", ""),
            "root_cause": verdict.get("root_cause", ""),
            "confidence": verdict.get("confidence", ""),
        })

    # Decrypt llm_config — chỉ dùng base_url/headers; api_key KHÔNG rời server (BUG-03)
    from agent.security import decrypt_secret
    import json as _json
    try:
        raw_cfg_str = decrypt_secret(p["llm_config"]) if p["llm_config"] else None
        _full_cfg = _json.loads(raw_cfg_str) if raw_cfg_str else None
        llm_key_set = bool((_full_cfg or {}).get("api_key"))
        # Strip api_key trước khi trả về template
        llm_config_raw = {k: v for k, v in _full_cfg.items() if k != "api_key"} if _full_cfg else None
    except Exception:
        llm_config_raw = None
        llm_key_set = False

    # Service repos (Phase 10 — F1)
    try:
        service_repos = [dict(r) for r in conn.execute(
            "SELECT id, service, provider, repo_url, default_branch, subpath "
            "FROM service_repos WHERE project_id=? ORDER BY service",
            (project_id,),
        ).fetchall()]
    except Exception:
        service_repos = []

    conn.close()
    return {
        "id": p["id"],
        "name": p["name"],
        "description": p["description"] or "",
        "llm_provider": p["llm_provider"] or "anthropic (env)",
        "llm_model": p["llm_model"] or "",
        "llm_config_raw": llm_config_raw,
        "llm_key_set": llm_key_set,
        "services": services,
        "mcp_servers": mcp_servers,
        "channels": channels,
        "recent_investigations": inv_list,
        "service_repos": service_repos,
    }


def get_eval_summary() -> List[Dict[str, Any]]:
    """Kết quả eval gần nhất per scenario — lấy run mới nhất của từng scenario."""
    conn = open_db()
    # Lấy run_id mới nhất cho mỗi scenario
    rows = conn.execute("""
        SELECT e.scenario,
               COUNT(*) as n,
               SUM(e.correct) as ok,
               AVG(e.steps_taken) as avg_steps,
               AVG(e.recall_at_1) as recall,
               SUM(e.hallucination) as hall,
               AVG(e.token_total) as avg_tokens,
               MAX(e.provider) as provider,
               MAX(e.model) as model
        FROM eval_results e
        INNER JOIN (
            SELECT scenario, MAX(created_at) AS latest_at
            FROM eval_results
            GROUP BY scenario
        ) latest ON e.scenario = latest.scenario AND e.created_at = latest.latest_at
        GROUP BY e.scenario
        ORDER BY e.scenario
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_eval_calibration() -> List[Dict[str, Any]]:
    """Calibration — theo từng mức confidence, agent đúng bao nhiêu %.

    Dùng run mới nhất per scenario (đồng bộ get_eval_summary). Agent calibrated
    tốt: HIGH → rate cao, LOW → rate thấp. Mock thường 100% high → ít ý nghĩa;
    có giá trị khi chạy real-LLM.
    """
    conn = open_db()
    rows = conn.execute("""
        SELECT e.confidence AS confidence,
               COUNT(*) AS n,
               SUM(e.correct) AS ok
        FROM eval_results e
        INNER JOIN (
            SELECT scenario, MAX(created_at) AS latest_at
            FROM eval_results
            GROUP BY scenario
        ) latest ON e.scenario = latest.scenario AND e.created_at = latest.latest_at
        GROUP BY e.confidence
    """).fetchall()
    conn.close()
    order = {"high": 0, "medium": 1, "low": 2, "insufficient": 3, "none": 4}
    out = []
    for r in rows:
        d = dict(r)
        d["rate"] = round((d["ok"] / d["n"]) * 100) if d["n"] else 0
        out.append(d)
    out.sort(key=lambda x: order.get(x["confidence"], 9))
    return out


def get_calibration_with_feedback() -> Dict[str, Any]:
    """E3/D1: Calibration thật — kết hợp eval_results + investigation_feedback (👍/👎).

    Returns dict với 3 list:
    - "eval": per-confidence từ eval_results (correct rate)
    - "feedback": per-confidence từ investigation_feedback (positive rate)
    - "combined": merge cả hai (tổng hợp)
    """
    conn = open_db()

    # 1. Từ eval_results — run mới nhất per scenario
    eval_rows = conn.execute("""
        SELECT e.confidence, COUNT(*) AS n, SUM(e.correct) AS ok
        FROM eval_results e
        INNER JOIN (
            SELECT scenario, MAX(created_at) AS latest_at
            FROM eval_results GROUP BY scenario
        ) latest ON e.scenario = latest.scenario AND e.created_at = latest.latest_at
        GROUP BY e.confidence
    """).fetchall()

    # 2. Từ investigation_feedback — join trace_events để lấy confidence
    feedback_rows = conn.execute("""
        SELECT
            json_extract(te.payload, '$.confidence') AS confidence,
            COUNT(*) AS n,
            SUM(CASE WHEN f.score > 0 THEN 1 ELSE 0 END) AS positive
        FROM investigation_feedback f
        JOIN trace_events te
            ON te.investigation_id = f.investigation_id
            AND te.event_type = 'verdict'
        WHERE json_extract(te.payload, '$.confidence') IS NOT NULL
          AND json_extract(te.payload, '$.confidence') != 'N/A'
        GROUP BY json_extract(te.payload, '$.confidence')
    """).fetchall()

    conn.close()

    order = {"high": 0, "medium": 1, "low": 2, "insufficient": 3}

    eval_out = []
    for r in eval_rows:
        d = dict(r)
        d["rate"] = round((d["ok"] / d["n"]) * 100) if d["n"] else 0
        eval_out.append(d)
    eval_out.sort(key=lambda x: order.get(x.get("confidence", ""), 9))

    feedback_out = []
    for r in feedback_rows:
        d = dict(r)
        d["rate"] = round((d["positive"] / d["n"]) * 100) if d["n"] else 0
        feedback_out.append(d)
    feedback_out.sort(key=lambda x: order.get(x.get("confidence", ""), 9))

    # Combined: merge cả hai nguồn
    combined: Dict[str, Dict] = {}
    for row in eval_out:
        conf = row.get("confidence") or "unknown"
        combined[conf] = {"confidence": conf, "n": row["n"], "accurate": int(row["ok"] or 0)}
    for row in feedback_out:
        conf = row.get("confidence") or "unknown"
        if conf in combined:
            combined[conf]["n"] += row["n"]
            combined[conf]["accurate"] += int(row.get("positive") or 0)
        else:
            combined[conf] = {"confidence": conf, "n": row["n"],
                              "accurate": int(row.get("positive") or 0)}
    combined_out = []
    for d in combined.values():
        d["rate"] = round((d["accurate"] / d["n"]) * 100) if d["n"] else 0
        combined_out.append(d)
    combined_out.sort(key=lambda x: order.get(x.get("confidence", ""), 9))

    return {"eval": eval_out, "feedback": feedback_out, "combined": combined_out}


# ── D3: Root cause clustering ─────────────────────────────────────────────────

def get_recurring_incidents(
    project_id: Optional[str] = None,
    threshold: int = 2,
) -> List[Dict[str, Any]]:
    """
    D3: Group investigations theo root_cause_type từ investigation_patterns.
    Trả các pattern xuất hiện >= threshold lần, sắp xếp theo count DESC.

    project_id=None → tất cả projects (admin view).
    """
    conn = open_db()
    if project_id:
        rows = conn.execute(
            """
            SELECT project_id, service, root_cause_type, count, avg_steps, updated_at
            FROM investigation_patterns
            WHERE project_id = ? AND count >= ?
            ORDER BY count DESC, updated_at DESC
            """,
            (project_id, threshold),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT project_id, service, root_cause_type, count, avg_steps, updated_at
            FROM investigation_patterns
            WHERE count >= ?
            ORDER BY count DESC, updated_at DESC
            """,
            (threshold,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_specificity_data() -> Dict[str, Any]:
    """E12: Thống kê specificity từ trace_events verdict gần nhất (≤200 rows)."""
    conn = open_db()
    try:
        rows = conn.execute("""
            SELECT payload
            FROM trace_events
            WHERE event_type = 'verdict'
            ORDER BY id DESC
            LIMIT 200
        """).fetchall()
    except Exception:
        rows = []
    conn.close()

    scores: list = []
    steps_list: list = []
    for row in rows:
        try:
            payload = json.loads(row["payload"] if hasattr(row, "__getitem__") else row[0])
            score = payload.get("specificity_score")
            if score is not None:
                scores.append(float(score))
        except Exception:
            continue

    avg = round(sum(scores) / len(scores), 2) if scores else 0.0
    return {
        "n": len(scores),
        "avg_specificity": avg,
        "high_n": sum(1 for s in scores if s >= 0.67),
        "med_n":  sum(1 for s in scores if 0.40 <= s < 0.67),
        "low_n":  sum(1 for s in scores if s < 0.40),
        "threshold": 0.40,
    }


def get_eval_comparison_data() -> Dict[str, Any]:
    """E13: So sánh avg_steps + avg_specificity với/không có prior (prior_flag).

    Trả dict với 2 key: "with_prior" và "no_prior", mỗi key là dict hoặc None.
    Degrade an toàn: trả {with_prior: None, no_prior: None} nếu bảng chưa có cột.
    """
    conn = open_db()
    out: Dict[str, Any] = {"with_prior": None, "no_prior": None}
    try:
        rows = conn.execute("""
            SELECT prior_flag,
                   COUNT(*) AS n,
                   AVG(steps_taken) AS avg_steps,
                   AVG(specificity_score) AS avg_specificity,
                   SUM(correct) AS ok
            FROM eval_results
            GROUP BY prior_flag
        """).fetchall()
        for r in rows:
            d = dict(r)
            d["avg_steps"] = round(d.get("avg_steps") or 0, 1)
            d["avg_specificity"] = round(d.get("avg_specificity") or 0, 2) if d.get("avg_specificity") is not None else None
            d["rate"] = round((d["ok"] / d["n"]) * 100) if d.get("n") else 0
            key = "no_prior" if d.get("prior_flag") else "with_prior"
            out[key] = d
    except Exception:
        pass
    finally:
        conn.close()
    return out
