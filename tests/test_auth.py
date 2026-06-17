"""
Auth + RBAC unit tests (Ngày 33).

Dùng pg_db fixture (schema-per-test Postgres isolation).
"""
from __future__ import annotations

import pytest


@pytest.fixture
def auth_db(pg_db):
    """pg_db đã tạo schema + tables + patched env."""
    return pg_db


# ---------------------------------------------------------------------------
# TestPasswordHash
# ---------------------------------------------------------------------------

class TestPasswordHash:
    def test_hash_and_verify(self):
        from agent.auth.rbac import hash_password, verify_password

        stored = hash_password("secret123")
        assert verify_password("secret123", stored)
        assert not verify_password("wrong", stored)

    def test_hash_unique_salt(self):
        from agent.auth.rbac import hash_password

        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # khác salt mỗi lần

    def test_bad_stored_format_returns_false(self):
        from agent.auth.rbac import verify_password

        assert not verify_password("anything", "not_valid_hash")


# ---------------------------------------------------------------------------
# TestUserCRUD
# ---------------------------------------------------------------------------

class TestUserCRUD:
    def test_create_and_get(self, auth_db):
        from agent.auth.rbac import create_user, get_user_by_username

        user = create_user("alice", "pw1")
        assert user["username"] == "alice"
        assert user["is_active"] == 1
        assert user["is_root"] == 0

        fetched = get_user_by_username("alice")
        assert fetched is not None
        assert fetched["id"] == user["id"]

    def test_duplicate_username_raises(self, auth_db):
        from agent.auth.rbac import create_user

        create_user("bob", "pw")
        with pytest.raises(ValueError, match="đã tồn tại"):
            create_user("bob", "pw2")

    def test_create_root_user(self, auth_db):
        from agent.auth.rbac import create_user

        user = create_user("admin", "pw", is_root=True)
        assert user["is_root"] == 1

    def test_list_users(self, auth_db):
        from agent.auth.rbac import create_user, list_users

        create_user("u1", "pw")
        create_user("u2", "pw")
        users = list_users()
        names = {u["username"] for u in users}
        assert {"u1", "u2"}.issubset(names)

    def test_delete_user(self, auth_db):
        from agent.auth.rbac import create_user, delete_user, get_user_by_id

        user = create_user("todelete", "pw")
        assert delete_user(user["id"])
        assert get_user_by_id(user["id"]) is None

    def test_cannot_delete_root_user(self, auth_db):
        from agent.auth.rbac import create_user, delete_user

        root = create_user("rootguy", "pw", is_root=True)
        with pytest.raises(ValueError, match="Không được xóa root"):
            delete_user(root["id"])


# ---------------------------------------------------------------------------
# TestAPIToken
# ---------------------------------------------------------------------------

class TestAPIToken:
    def test_create_and_verify(self, auth_db):
        from agent.auth.rbac import create_api_token, create_user, verify_token

        user = create_user("tokenuser", "pw")
        result = create_api_token(user["id"], name="ci-token")
        raw = result["token"]

        found = verify_token(raw)
        assert found is not None
        assert found["username"] == "tokenuser"
        assert found["is_active"] == 1

    def test_verify_invalid_token_returns_none(self, auth_db):
        from agent.auth.rbac import verify_token

        assert verify_token("totally_invalid_token_xyz") is None

    def test_revoke_token(self, auth_db):
        from agent.auth.rbac import create_api_token, create_user, revoke_token, verify_token

        user = create_user("revokeuser", "pw")
        result = create_api_token(user["id"])
        raw = result["token"]

        assert verify_token(raw) is not None
        assert revoke_token(result["id"])
        assert verify_token(raw) is None

    def test_inactive_user_token_rejected(self, auth_db):
        """verify_token trả is_active=0 — caller phải kiểm."""
        from agent.auth.rbac import create_api_token, create_user, update_user, verify_token

        user = create_user("inactiveuser", "pw")
        result = create_api_token(user["id"])
        raw = result["token"]

        update_user(user["id"], is_active=False)
        info = verify_token(raw)
        assert info is not None
        assert info["is_active"] == 0


# ---------------------------------------------------------------------------
# TestRoleAndPermission
# ---------------------------------------------------------------------------

class TestRoleAndPermission:
    def _seed_perm(self, key: str) -> None:
        from agent.storage.db import open_db
        conn = open_db()
        conn.execute(
            "INSERT INTO permissions (key, description) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (key, ""),
        )
        conn.commit()
        conn.close()

    def test_create_role_with_permissions(self, auth_db):
        from agent.auth.rbac import create_role, get_role_permissions

        self._seed_perm("investigation.view")
        self._seed_perm("investigation.trigger")

        create_role("operator", "Operator", permissions=["investigation.view", "investigation.trigger"])
        perms = get_role_permissions("operator")
        assert "investigation.view" in perms
        assert "investigation.trigger" in perms

    def test_duplicate_role_raises(self, auth_db):
        from agent.auth.rbac import create_role

        create_role("testrole", "Test Role")
        with pytest.raises(ValueError):
            create_role("testrole", "Another Name")

    def test_delete_system_role_raises(self, auth_db):
        from agent.auth.rbac import delete_role
        from agent.storage.db import open_db

        conn = open_db()
        conn.execute(
            "INSERT INTO roles (id, name, is_system) VALUES (%s, %s, %s)",
            ("admin", "Admin", 1),
        )
        conn.commit()
        conn.close()

        with pytest.raises(ValueError, match="system role"):
            delete_role("admin")


# ---------------------------------------------------------------------------
# TestUserCan (permission check)
# ---------------------------------------------------------------------------

class TestUserCan:
    def _seed(self):
        """Helper: tạo user, role, permission và gán global."""
        from agent.auth.rbac import assign_role, create_role, create_user
        from agent.storage.db import open_db

        conn = open_db()
        conn.execute(
            "INSERT INTO permissions (key) VALUES ('investigation.view') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO permissions (key) VALUES ('investigation.trigger') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO projects (id, name) VALUES ('proj_a', 'Project A') ON CONFLICT DO NOTHING"
        )
        conn.commit()
        conn.close()

        user = create_user("op_user", "pw")
        create_role("op_role", "Operator", permissions=["investigation.view"])
        assign_role(user["id"], "op_role", scope_type="global")
        return user

    def test_global_permission_allowed(self, auth_db):
        from agent.auth.rbac import user_can

        user = self._seed()
        assert user_can(user["id"], "investigation.view")

    def test_unassigned_permission_denied(self, auth_db):
        from agent.auth.rbac import user_can

        user = self._seed()
        assert not user_can(user["id"], "investigation.trigger")

    def test_root_user_bypasses_all_checks(self, auth_db):
        from agent.auth.rbac import create_user, user_can

        root = create_user("rootcheck", "pw", is_root=True)
        assert user_can(root["id"], "any.permission.whatsoever")

    def test_inactive_user_denied(self, auth_db):
        from agent.auth.rbac import update_user, user_can

        user = self._seed()
        update_user(user["id"], is_active=False)
        assert not user_can(user["id"], "investigation.view")

    def test_project_scoped_permission(self, auth_db):
        from agent.auth.rbac import assign_role, create_role, create_user, user_can
        from agent.storage.db import open_db

        conn = open_db()
        conn.execute(
            "INSERT INTO permissions (key) VALUES ('investigation.view') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO projects (id, name) VALUES ('proj_x', 'ProjX') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO projects (id, name) VALUES ('proj_y', 'ProjY') ON CONFLICT DO NOTHING"
        )
        conn.commit()
        conn.close()

        user = create_user("scoped_user", "pw")
        create_role("view_role", "View", permissions=["investigation.view"])
        assign_role(user["id"], "view_role", scope_type="project", scope_project_id="proj_x")

        assert user_can(user["id"], "investigation.view", project_id="proj_x")
        assert not user_can(user["id"], "investigation.view", project_id="proj_y")
