"""
FastAPI dependencies cho auth: get_current_user, require_login, require_perm.
Custom exceptions cho exception_handler trong server.py.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Request


class NotAuthenticated(Exception):
    """User chưa đăng nhập — handler redirect về /auth/login."""
    pass


class NotAuthorized(Exception):
    """User đã đăng nhập nhưng thiếu quyền cần thiết."""
    def __init__(self, perm: str = ""):
        self.perm = perm
        super().__init__(perm)


# ── Dependency: lấy user hiện tại từ session ─────────────────────────────────

def get_current_user(request: Request) -> Optional[dict]:
    """Trả user dict hoặc None nếu chưa login. Không raise."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    try:
        from agent.auth.rbac import get_user_by_id
        user = get_user_by_id(user_id)
        if user and user["is_active"]:
            return user
    except Exception:
        pass
    return None


def require_login(request: Request) -> dict:
    """Dependency: raise NotAuthenticated nếu chưa login."""
    # Cũng hỗ trợ API token qua header X-API-Token
    token_header = request.headers.get("X-API-Token", "")
    if token_header:
        try:
            from agent.auth.rbac import verify_token
            token_info = verify_token(token_header)
            if token_info and token_info["is_active"]:
                return {
                    "id": token_info["user_id"],
                    "username": token_info["username"],
                    "is_root": token_info["is_root"],
                    "is_active": token_info["is_active"],
                }
        except Exception:
            pass

    user = get_current_user(request)
    if user is None:
        raise NotAuthenticated()
    return user


def require_perm(perm: str, get_project_id=None):
    """
    Factory trả dependency function (không wrap Depends — caller tự wrap).
    Dùng: user: dict = Depends(require_perm("investigation.view"))
    """
    def dep(request: Request, user: dict = Depends(require_login)) -> dict:
        pid: Optional[str] = None
        if get_project_id:
            try:
                pid = get_project_id(request)
            except Exception:
                pass
        else:
            pid = request.path_params.get("project_id") or request.query_params.get("project_id")

        if user.get("is_root"):
            return user

        try:
            from agent.auth.rbac import user_can
            if not user_can(user["id"], perm, pid):
                raise NotAuthorized(perm)
        except NotAuthorized:
            raise
        except Exception:
            raise NotAuthorized(perm)
        return user
    return dep
