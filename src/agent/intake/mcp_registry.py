"""
MCP server registry — CRUD thao tác trên bảng mcp_servers (SQLite).

Mỗi MCP server thuộc về một project (project_id).
Backward compat: project_id='default' cho các server cũ.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.storage.db import IntegrityError, open_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_servers(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Liệt kê MCP servers.
    project_id=None → tất cả (admin view)
    project_id='xyz' → chỉ servers của project đó
    """
    conn = open_db()
    if project_id is not None:
        rows = conn.execute(
            "SELECT * FROM mcp_servers WHERE project_id=? ORDER BY created_at",
            (project_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM mcp_servers ORDER BY project_id, created_at"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_server(
    name: str,
    url: str,
    description: str = "",
    project_id: str = "default",
    auth_type: str = "none",
    auth_config: str = "{}",
) -> Dict[str, Any]:
    """
    Thêm MCP server vào registry của project.
    URL unique theo (url, project_id) → cùng 1 URL đăng ký được cho nhiều project,
    nhưng KHÔNG trùng trong cùng một project.
    Raise ValueError nếu URL đã tồn tại trong project này.

    auth_type: 'none' | 'bearer' | 'api_key'
    auth_config: JSON string — {"token":"..."} hoặc {"header":"X-API-Key","value":"..."}
    """
    from agent.security import encrypt_secret
    now = _now()
    url = url.rstrip("/")
    encrypted_auth = encrypt_secret(auth_config) if auth_type != "none" else auth_config
    conn = open_db()
    try:
        cursor = conn.execute(
            "INSERT INTO mcp_servers "
            "(name, url, description, enabled, project_id, auth_type, auth_config, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)",
            (name, url, description, project_id, auth_type, encrypted_auth, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM mcp_servers WHERE id=?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)
    except IntegrityError:
        raise ValueError(
            f"URL '{url}' đã tồn tại trong project '{project_id}'"
        )
    finally:
        conn.close()


def remove_server(server_id: int, project_id: Optional[str] = None) -> bool:
    """
    Xóa MCP server.
    project_id != None → chỉ xóa nếu server thuộc đúng project (tránh xóa nhầm).
    """
    conn = open_db()
    if project_id is not None:
        cursor = conn.execute(
            "DELETE FROM mcp_servers WHERE id=? AND project_id=?",
            (server_id, project_id),
        )
    else:
        cursor = conn.execute("DELETE FROM mcp_servers WHERE id=?", (server_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def update_server(
    server_id: int,
    project_id: Optional[str] = None,
    **fields,
) -> Optional[Dict[str, Any]]:
    """
    Cập nhật fields (name, url, description, enabled).
    project_id != None → chỉ update nếu server thuộc đúng project.
    """
    allowed = {"name", "url", "description", "enabled", "auth_type", "auth_config"}
    updates = {k: v for k, v in fields.items() if k in allowed}

    # Build WHERE
    where = "id=?"
    where_vals = [server_id]
    if project_id is not None:
        where += " AND project_id=?"
        where_vals.append(project_id)

    # Nếu không có gì update, chỉ fetch và trả về
    if not updates:
        conn = open_db()
        row = conn.execute(
            f"SELECT * FROM mcp_servers WHERE {where}", where_vals
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    if "url" in updates:
        updates["url"] = updates["url"].rstrip("/")

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + where_vals

    conn = open_db()
    try:
        conn.execute(f"UPDATE mcp_servers SET {set_clause} WHERE {where}", values)
        conn.commit()
        row = conn.execute(
            f"SELECT * FROM mcp_servers WHERE {where}", where_vals
        ).fetchone()
        return dict(row) if row else None
    except IntegrityError:
        raise ValueError(
            f"URL '{updates.get('url')}' đã tồn tại trong project này"
        )
    finally:
        conn.close()


def get_enabled_urls(project_id: str = "default") -> List[str]:
    """Trả URLs của servers enabled trong project — backward compat."""
    return [s["url"] for s in get_enabled_servers(project_id)]


def get_enabled_servers(project_id: str = "default") -> List[Dict[str, Any]]:
    """Trả full record (url + auth_type + auth_config) của servers enabled trong project.
    auth_config được giải mã at-rest (A2).
    """
    from agent.security import decrypt_secret
    conn = open_db()
    rows = conn.execute(
        "SELECT url, auth_type, auth_config FROM mcp_servers "
        "WHERE enabled=1 AND project_id=? ORDER BY created_at",
        (project_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("auth_type") != "none" and d.get("auth_config"):
            d["auth_config"] = decrypt_secret(d["auth_config"]) or d["auth_config"]
        result.append(d)
    return result


def get_server_by_id(
    server_id: int, project_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    conn = open_db()
    if project_id is not None:
        row = conn.execute(
            "SELECT * FROM mcp_servers WHERE id=? AND project_id=?",
            (server_id, project_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM mcp_servers WHERE id=?", (server_id,)
        ).fetchone()
    conn.close()
    return dict(row) if row else None
