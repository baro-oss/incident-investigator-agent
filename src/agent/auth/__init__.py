"""Auth & RBAC layer — Phase 5 Ngày 22."""
from .permissions import PERMISSION_CATALOG, ROLE_SEEDS
from .rbac import (
    bootstrap_root,
    create_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    update_user,
    delete_user,
    list_roles,
    get_role,
    create_role,
    update_role,
    delete_role,
    get_role_permissions,
    set_role_permissions,
    list_user_assignments,
    assign_role,
    remove_assignment,
    user_can,
    # project groups
    list_groups,
    create_group,
    delete_group,
    add_group_member,
    remove_group_member,
    list_group_members,
    # api tokens
    create_api_token,
    list_user_tokens,
    revoke_token,
    verify_token,
)

__all__ = [
    "PERMISSION_CATALOG", "ROLE_SEEDS",
    "bootstrap_root",
    "create_user", "get_user_by_id", "get_user_by_username",
    "list_users", "update_user", "delete_user",
    "list_roles", "get_role", "create_role", "update_role", "delete_role",
    "get_role_permissions", "set_role_permissions",
    "list_user_assignments", "assign_role", "remove_assignment",
    "user_can",
    "list_groups", "create_group", "delete_group",
    "add_group_member", "remove_group_member", "list_group_members",
    "create_api_token", "list_user_tokens", "revoke_token", "verify_token",
]
