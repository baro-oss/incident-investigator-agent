"""
RBAC — DB operations cho users, roles, assignments, project groups, api_tokens.
Dùng storage seam (không import sqlite3 trực tiếp).
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.storage import IntegrityError, open_db

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return key.hex() == key_hex
    except Exception:
        return False


# ── Users ─────────────────────────────────────────────────────────────────────

def list_users() -> List[Dict[str, Any]]:
    with open_db() as conn:
        rows = conn.execute(
            "SELECT id, username, is_root, is_active, created_at FROM users ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with open_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with open_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def create_user(
    username: str,
    password: str,
    is_root: bool = False,
) -> Dict[str, Any]:
    uid = str(uuid.uuid4())
    phash = hash_password(password)
    now = _now()
    try:
        with open_db() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, is_root, is_active, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?)",
                (uid, username, phash, int(is_root), now),
            )
            row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            return dict(row)
    except IntegrityError:
        raise ValueError(f"Username '{username}' đã tồn tại")


def update_user(
    user_id: str,
    *,
    password: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    with open_db() as conn:
        if password is not None:
            conn.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (hash_password(password), user_id),
            )
        if is_active is not None:
            conn.execute(
                "UPDATE users SET is_active=? WHERE id=?",
                (int(is_active), user_id),
            )
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def delete_user(user_id: str) -> bool:
    with open_db() as conn:
        user = conn.execute("SELECT is_root FROM users WHERE id=?", (user_id,)).fetchone()
        if user and user["is_root"]:
            raise ValueError("Không được xóa root user")
        cursor = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    return cursor.rowcount > 0


# ── Roles ─────────────────────────────────────────────────────────────────────

def list_roles() -> List[Dict[str, Any]]:
    with open_db() as conn:
        rows = conn.execute("SELECT * FROM roles ORDER BY is_system DESC, name").fetchall()
    return [dict(r) for r in rows]


def get_role(role_id: str) -> Optional[Dict[str, Any]]:
    with open_db() as conn:
        row = conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
    return dict(row) if row else None


def create_role(
    role_id: str,
    name: str,
    description: str = "",
    permissions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    try:
        with open_db() as conn:
            conn.execute(
                "INSERT INTO roles (id, name, description, is_system) VALUES (?, ?, ?, 0)",
                (role_id, name, description),
            )
            for pkey in (permissions or []):
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_key) VALUES (?, ?)",
                    (role_id, pkey),
                )
            row = conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
            return dict(row)
    except IntegrityError:
        raise ValueError(f"Role id/name đã tồn tại: {role_id}")


def update_role(
    role_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    with open_db() as conn:
        if name:
            conn.execute("UPDATE roles SET name=? WHERE id=?", (name, role_id))
        if description is not None:
            conn.execute("UPDATE roles SET description=? WHERE id=?", (description, role_id))
        row = conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
    return dict(row) if row else None


def delete_role(role_id: str) -> bool:
    with open_db() as conn:
        role = conn.execute("SELECT is_system FROM roles WHERE id=?", (role_id,)).fetchone()
        if role and role["is_system"]:
            raise ValueError("Không được xóa system role")
        cursor = conn.execute("DELETE FROM roles WHERE id=?", (role_id,))
    return cursor.rowcount > 0


def get_role_permissions(role_id: str) -> List[str]:
    with open_db() as conn:
        rows = conn.execute(
            "SELECT permission_key FROM role_permissions WHERE role_id=?", (role_id,)
        ).fetchall()
    return [r["permission_key"] for r in rows]


def set_role_permissions(role_id: str, permission_keys: List[str]) -> None:
    with open_db() as conn:
        conn.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
        for pkey in permission_keys:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_key) VALUES (?, ?)",
                (role_id, pkey),
            )


# ── Role assignments ──────────────────────────────────────────────────────────

def list_user_assignments(user_id: str) -> List[Dict[str, Any]]:
    with open_db() as conn:
        rows = conn.execute(
            """SELECT ra.id, ra.role_id, r.name as role_name, ra.scope_type,
                      ra.scope_group_id, ra.scope_project_id
               FROM role_assignments ra JOIN roles r ON r.id=ra.role_id
               WHERE ra.user_id=?""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def assign_role(
    user_id: str,
    role_id: str,
    scope_type: str = "global",
    scope_group_id: Optional[str] = None,
    scope_project_id: Optional[str] = None,
) -> Dict[str, Any]:
    if scope_type not in ("global", "group", "project"):
        raise ValueError("scope_type phải là 'global', 'group', hoặc 'project'")
    aid = str(uuid.uuid4())
    with open_db() as conn:
        conn.execute(
            "INSERT INTO role_assignments (id, user_id, role_id, scope_type, scope_group_id, scope_project_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (aid, user_id, role_id, scope_type, scope_group_id, scope_project_id),
        )
        row = conn.execute("SELECT * FROM role_assignments WHERE id=?", (aid,)).fetchone()
    return dict(row)


def remove_assignment(assignment_id: str) -> bool:
    with open_db() as conn:
        cursor = conn.execute("DELETE FROM role_assignments WHERE id=?", (assignment_id,))
    return cursor.rowcount > 0


# ── user_can ──────────────────────────────────────────────────────────────────

def _get_group_projects(group_id: str) -> List[str]:
    with open_db() as conn:
        rows = conn.execute(
            "SELECT project_id FROM project_group_members WHERE group_id=?", (group_id,)
        ).fetchall()
    return [r["project_id"] for r in rows]


def _get_role_perm_set(role_id: str) -> set:
    with open_db() as conn:
        rows = conn.execute(
            "SELECT permission_key FROM role_permissions WHERE role_id=?", (role_id,)
        ).fetchall()
    return {r["permission_key"] for r in rows}


def user_can(user_id: str, perm_key: str, project_id: Optional[str] = None) -> bool:
    user = get_user_by_id(user_id)
    if not user or not user["is_active"]:
        return False
    if user["is_root"]:
        return True

    with open_db() as conn:
        assignments = conn.execute(
            "SELECT role_id, scope_type, scope_group_id, scope_project_id "
            "FROM role_assignments WHERE user_id=?",
            (user_id,),
        ).fetchall()

    for a in assignments:
        perm_set = _get_role_perm_set(a["role_id"])
        if perm_key not in perm_set:
            continue
        if a["scope_type"] == "global":
            return True
        if a["scope_type"] == "project" and a["scope_project_id"] == project_id:
            return True
        if a["scope_type"] == "group" and project_id:
            if project_id in _get_group_projects(a["scope_group_id"]):
                return True
    return False


# ── Bootstrap root ────────────────────────────────────────────────────────────

def bootstrap_root() -> None:
    root_username = os.getenv("ROOT_USERNAME", "root")
    root_password = os.getenv("ROOT_PASSWORD", "")
    if not root_password:
        log.warning("ROOT_PASSWORD không set — root user không được tạo tự động")
        return
    existing = get_user_by_username(root_username)
    if existing:
        return
    try:
        create_user(root_username, root_password, is_root=True)
        log.info("Root user '%s' đã tạo", root_username)
    except Exception as e:
        log.error("Lỗi khi tạo root user: %s", e)


# ── Project groups ────────────────────────────────────────────────────────────

def list_groups() -> List[Dict[str, Any]]:
    with open_db() as conn:
        rows = conn.execute("SELECT * FROM project_groups ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def create_group(name: str, description: str = "") -> Dict[str, Any]:
    gid = str(uuid.uuid4())
    now = _now()
    try:
        with open_db() as conn:
            conn.execute(
                "INSERT INTO project_groups (id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (gid, name, description, now),
            )
            row = conn.execute("SELECT * FROM project_groups WHERE id=?", (gid,)).fetchone()
            return dict(row)
    except IntegrityError:
        raise ValueError(f"Group name '{name}' đã tồn tại")


def delete_group(group_id: str) -> bool:
    with open_db() as conn:
        cursor = conn.execute("DELETE FROM project_groups WHERE id=?", (group_id,))
    return cursor.rowcount > 0


def list_group_members(group_id: str) -> List[str]:
    with open_db() as conn:
        rows = conn.execute(
            "SELECT project_id FROM project_group_members WHERE group_id=?", (group_id,)
        ).fetchall()
    return [r["project_id"] for r in rows]


def add_group_member(group_id: str, project_id: str) -> bool:
    try:
        with open_db() as conn:
            conn.execute(
                "INSERT INTO project_group_members (group_id, project_id) VALUES (?, ?)",
                (group_id, project_id),
            )
        return True
    except IntegrityError:
        return False


def remove_group_member(group_id: str, project_id: str) -> bool:
    with open_db() as conn:
        cursor = conn.execute(
            "DELETE FROM project_group_members WHERE group_id=? AND project_id=?",
            (group_id, project_id),
        )
    return cursor.rowcount > 0


# ── API tokens ────────────────────────────────────────────────────────────────

def create_api_token(user_id: str, name: str = "") -> Dict[str, Any]:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    tid = str(uuid.uuid4())
    now = _now()
    with open_db() as conn:
        conn.execute(
            "INSERT INTO api_tokens (id, user_id, token_hash, name, created_at) VALUES (?, ?, ?, ?, ?)",
            (tid, user_id, token_hash, name, now),
        )
    return {"id": tid, "token": raw, "name": name, "created_at": now}


def list_user_tokens(user_id: str) -> List[Dict[str, Any]]:
    with open_db() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, last_used FROM api_tokens WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def revoke_token(token_id: str) -> bool:
    with open_db() as conn:
        cursor = conn.execute("DELETE FROM api_tokens WHERE id=?", (token_id,))
    return cursor.rowcount > 0


def list_all_tokens() -> List[Dict[str, Any]]:
    """Admin view: tất cả tokens kèm username."""
    with open_db() as conn:
        rows = conn.execute(
            "SELECT at.id, at.name, at.user_id, u.username, at.created_at, at.last_used "
            "FROM api_tokens at JOIN users u ON u.id=at.user_id "
            "ORDER BY at.created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def verify_token(raw_token: str) -> Optional[Dict[str, Any]]:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with open_db() as conn:
        row = conn.execute(
            "SELECT at.id, at.user_id, u.username, u.is_root, u.is_active "
            "FROM api_tokens at JOIN users u ON u.id=at.user_id "
            "WHERE at.token_hash=?",
            (token_hash,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE api_tokens SET last_used=? WHERE token_hash=?",
                (_now(), token_hash),
            )
    return dict(row) if row else None
