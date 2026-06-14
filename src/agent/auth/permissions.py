"""Permission catalog + role seeds — constants, không truy cập DB."""
from __future__ import annotations

PERMISSION_CATALOG: dict = {
    "investigation.view":    "Xem danh sách và chi tiết điều tra",
    "investigation.trigger": "Kích hoạt điều tra mới",
    "investigation.replay":  "Phát lại điều tra cũ",
    "observability.view":    "Xem eval, cost, health dashboard",
    "project.view":          "Xem danh sách project",
    "project.manage":        "Tạo/sửa/xóa project và services",
    "mcp.manage":            "Quản lý MCP server registry",
    "channel.manage":        "Quản lý alert channels",
    "llm.manage":            "Cấu hình LLM per project (nhạy cảm)",
    "user.manage":           "Tạo/sửa/xóa user",
    "role.manage":           "Tạo/sửa role và gán quyền",
    "group.manage":          "Quản lý project groups",
}

ROLE_SEEDS: dict = {
    "admin": {
        "name": "Admin",
        "description": "Toàn quyền hệ thống",
        "permissions": list(PERMISSION_CATALOG.keys()),
    },
    "operator": {
        "name": "Operator",
        "description": "Điều tra và quan sát",
        "permissions": [
            "investigation.view", "investigation.trigger", "investigation.replay",
            "observability.view", "project.view",
        ],
    },
    "viewer": {
        "name": "Viewer",
        "description": "Chỉ xem",
        "permissions": ["investigation.view", "project.view"],
    },
}

# Tên hiển thị theo nhóm (để render UI checkbox grid)
PERMISSION_GROUPS: dict = {
    "Investigation": ["investigation.view", "investigation.trigger", "investigation.replay"],
    "Observability": ["observability.view"],
    "Project":       ["project.view", "project.manage"],
    "Infrastructure":["mcp.manage", "channel.manage", "llm.manage"],
    "Admin":         ["user.manage", "role.manage", "group.manage"],
}
