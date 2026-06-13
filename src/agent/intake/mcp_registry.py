"""
MCP server registry — CRUD thao tác trên bảng mcp_servers (SQLite).

Mỗi MCP server thuộc về một project (project_id).
Backward compat: project_id='default' cho các server cũ.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.storage.db import open_db


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
) -> Dict[str, Any]:
    """
    Thêm MCP server vào registry của project.
    Raise ValueError nếu URL đã tồn tại (URL unique toàn cục).
    """
    now = _now()
    url = url.rstrip("/")
    conn = open_db()
    try:
        cursor = conn.execute(
            "INSERT INTO mcp_servers (name, url, description, enabled, project_id, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?, ?)",
            (name, url, description, project_id, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM mcp_servers WHERE id=?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        raise ValueError(f"URL '{url}' đã tồn tại trong registry")
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
    allowed = {"name", "url", "description", "enabled"}
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
    except sqlite3.IntegrityError:
        raise ValueError(f"URL '{updates.get('url')}' đã tồn tại trong registry")
    finally:
        conn.close()


def get_enabled_urls(project_id: str = "default") -> List[str]:
    """Trả URLs của servers enabled trong project — nguồn chính cho runner."""
    conn = open_db()
    rows = conn.execute(
        "SELECT url FROM mcp_servers WHERE enabled=1 AND project_id=? ORDER BY created_at",
        (project_id,),
    ).fetchall()
    conn.close()
    return [r["url"] for r in rows]


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
