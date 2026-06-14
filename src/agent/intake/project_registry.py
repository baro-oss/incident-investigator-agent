"""
Project registry — CRUD cho projects và project_services.

Mỗi project có:
- id (slug, vd "payment-platform") — dùng trong URL
- Danh sách services (project_services)
- Danh sách MCP servers (mcp_servers.project_id)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.storage.db import IntegrityError, open_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Projects ──────────────────────────────────────────────────────────────────

def list_projects() -> List[Dict[str, Any]]:
    conn = open_db()
    rows = conn.execute(
        "SELECT id, name, description, created_at, updated_at "
        "FROM projects ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    conn = open_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_project(project_id: str, name: str, description: str = "") -> Dict[str, Any]:
    """
    Tạo project mới. project_id là slug (vd 'payment-platform').
    Raise ValueError nếu id đã tồn tại.
    """
    now = _now()
    conn = open_db()
    try:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, name, description, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return dict(row)
    except IntegrityError:
        raise ValueError(f"Project id '{project_id}' đã tồn tại")
    finally:
        conn.close()


def update_project(project_id: str, **fields) -> Optional[Dict[str, Any]]:
    """Cập nhật name / description. Trả None nếu không tìm thấy."""
    allowed = {"name", "description"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_project(project_id)

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [project_id]

    conn = open_db()
    conn.execute(f"UPDATE projects SET {set_clause} WHERE id=?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_project(project_id: str) -> bool:
    """Xóa project (cascade xóa project_services; mcp_servers cần xử lý riêng)."""
    if project_id == "default":
        raise ValueError("Không được xóa project 'default'")
    conn = open_db()
    # Orphan mcp_servers của project này → gán về 'default'
    conn.execute(
        "UPDATE mcp_servers SET project_id='default' WHERE project_id=?", (project_id,)
    )
    cursor = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


# ── Project services ──────────────────────────────────────────────────────────

def list_project_services(project_id: str) -> List[str]:
    conn = open_db()
    rows = conn.execute(
        "SELECT service FROM project_services WHERE project_id=? ORDER BY service",
        (project_id,),
    ).fetchall()
    conn.close()
    return [r["service"] for r in rows]


def add_project_service(project_id: str, service: str) -> bool:
    """Thêm service vào project. Trả False nếu đã tồn tại."""
    conn = open_db()
    try:
        conn.execute(
            "INSERT INTO project_services (project_id, service) VALUES (?, ?)",
            (project_id, service),
        )
        conn.commit()
        return True
    except IntegrityError:
        return False  # đã tồn tại — OK, không phải lỗi
    finally:
        conn.close()


def remove_project_service(project_id: str, service: str) -> bool:
    conn = open_db()
    cursor = conn.execute(
        "DELETE FROM project_services WHERE project_id=? AND service=?",
        (project_id, service),
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


# ── Project alert channels ────────────────────────────────────────────────────

SUPPORTED_CHANNELS = {"telegram", "teams", "email", "slack"}


def list_project_channels(project_id: str) -> List[Dict[str, Any]]:
    """Trả list channel đang cấu hình cho project (kể cả disabled)."""
    conn = open_db()
    rows = conn.execute(
        "SELECT channel, config, enabled FROM project_alert_channels "
        "WHERE project_id=? ORDER BY channel",
        (project_id,),
    ).fetchall()
    conn.close()
    return [
        {"channel": r["channel"], "config": json.loads(r["config"]), "enabled": bool(r["enabled"])}
        for r in rows
    ]


def get_enabled_project_channels(project_id: str) -> List[Dict[str, Any]]:
    """Trả list channel đang enabled — dùng bởi router khi push verdict."""
    conn = open_db()
    rows = conn.execute(
        "SELECT channel, config FROM project_alert_channels "
        "WHERE project_id=? AND enabled=1 ORDER BY channel",
        (project_id,),
    ).fetchall()
    conn.close()
    return [{"channel": r["channel"], "config": json.loads(r["config"])} for r in rows]


def set_project_channel(
    project_id: str,
    channel: str,
    config: Optional[Dict[str, Any]] = None,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Upsert channel config cho project. Raise ValueError nếu channel không hỗ trợ."""
    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(f"Channel '{channel}' không hỗ trợ. Hỗ trợ: {sorted(SUPPORTED_CHANNELS)}")
    config_str = json.dumps(config or {})
    conn = open_db()
    conn.execute(
        """
        INSERT INTO project_alert_channels (project_id, channel, config, enabled)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(project_id, channel) DO UPDATE SET config=excluded.config, enabled=excluded.enabled
        """,
        (project_id, channel, config_str, int(enabled)),
    )
    conn.commit()
    conn.close()
    return {"project_id": project_id, "channel": channel, "config": config or {}, "enabled": enabled}


def remove_project_channel(project_id: str, channel: str) -> bool:
    conn = open_db()
    cursor = conn.execute(
        "DELETE FROM project_alert_channels WHERE project_id=? AND channel=?",
        (project_id, channel),
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


# ── Per-project LLM config ────────────────────────────────────────────────────

def get_project_llm(project_id: str) -> Optional[Dict[str, Any]]:
    """Trả cấu hình LLM của project, hoặc None nếu chưa set."""
    conn = open_db()
    row = conn.execute(
        "SELECT llm_provider, llm_model, llm_config FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    conn.close()
    if not row or not row["llm_provider"]:
        return None
    return {
        "provider": row["llm_provider"],
        "model": row["llm_model"],
        "config": json.loads(row["llm_config"] or "{}"),
    }


def set_project_llm(
    project_id: str,
    provider: str,
    model: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Cập nhật cấu hình LLM cho project. Raise ValueError nếu project không tồn tại."""
    SUPPORTED_PROVIDERS = {"anthropic", "openai", "gemini", "groq", "mistral", "ollama"}
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Provider '{provider}' không hỗ trợ. Hỗ trợ: {sorted(SUPPORTED_PROVIDERS)}"
        )
    config_str = json.dumps(config or {})
    conn = open_db()
    cursor = conn.execute(
        "UPDATE projects SET llm_provider=?, llm_model=?, llm_config=?, updated_at=? WHERE id=?",
        (provider, model, config_str, _now(), project_id),
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        raise ValueError(f"Project '{project_id}' không tồn tại")
    return {"provider": provider, "model": model, "config": config or {}}
