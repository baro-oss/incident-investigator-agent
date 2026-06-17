#!/usr/bin/env python3
"""
Provision project demo-day end-to-end (idempotent).

Tạo / cập nhật:
  - project 'demo-day' + 4 service (kèm mô tả)
  - 2 MCP server scoped vào project:
        telemetry-tools  (logs/metrics/deploys/graph/trace)  → port 9000
        gitlab-code      (đọc source qua GitLab API)         → port 9002
  - service_repos: mỗi service → repo gitlab.com (provider=gitlab)
  - kênh Telegram per-project (chat_id riêng)

Env:
  GITLAB_NAMESPACE   (bắt buộc cho repo mapping)  vd: baopx
  DEMO_CHAT_ID       (tùy chọn)  chat_id Telegram cho project (bỏ qua nếu trống)
  GITLAB_BASE        mặc định https://gitlab.com
  TELEMETRY_MCP_URL  mặc định http://localhost:9000/mcp
  GITLAB_MCP_URL     mặc định http://localhost:9002/mcp
  DEMO_PROJECT_ID    mặc định demo-day

Chạy: python3 scripts/setup_demo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from agent.intake import mcp_registry, project_registry
from agent.storage.db import BACKEND_NAME

PROJECT_ID = os.getenv("DEMO_PROJECT_ID", "demo-day")
GITLAB_BASE = os.getenv("GITLAB_BASE", "https://gitlab.com").rstrip("/")
NS = os.getenv("GITLAB_NAMESPACE", "")
DEMO_CHAT_ID = os.getenv("DEMO_CHAT_ID", "")
TELEMETRY_MCP_URL = os.getenv("TELEMETRY_MCP_URL", "http://localhost:9000/mcp")
GITLAB_MCP_URL = os.getenv("GITLAB_MCP_URL", "http://localhost:9002/mcp")

# service → mô tả ngắn (đưa vào prompt engine qua service_descriptions)
SERVICES = {
    "api-gateway": "Cửa vào duy nhất, route request tới payment-gateway và order-service.",
    "payment-gateway": "Xử lý giao dịch thanh toán; gọi auth-service để xác thực và third-party-provider để charge.",
    "auth-service": "Xác thực token và phân quyền người dùng (leaf node).",
    "order-service": "Quản lý đơn hàng; gọi payment-gateway khi cần xử lý thanh toán.",
}

# service (logic) → repo name trên GitLab (repo ≠ tên service). Chỉ service có trong
# map mới được gắn service_repos → get_code_diff chỉ kích hoạt cho các service này.
# Override bằng env SERVICE_REPOS_JSON nếu muốn (JSON {"service":"repo"}).
SERVICE_REPOS = {
    "payment-gateway": "payment-gateway",  # culprit — repo có lịch sử v2.3.0/v2.4.0
    "api-gateway": "api-gateway",          # stub
    "auth-service": "auth-service",        # stub
    "order-service": "order-service",      # stub
}


def _ensure_project() -> None:
    existing = project_registry.get_project(PROJECT_ID)
    if existing:
        print(f"• project '{PROJECT_ID}' đã tồn tại — giữ nguyên")
    else:
        project_registry.create_project(
            PROJECT_ID, "Demo Day — e-commerce platform",
            "Project demo trình diễn toàn hệ thống: intake → engine → MCP telemetry + GitLab code → Telegram.",
        )
        print(f"✅ tạo project '{PROJECT_ID}'")


def _ensure_services() -> None:
    for svc, desc in SERVICES.items():
        project_registry.add_project_service(PROJECT_ID, svc, desc)
    print(f"✅ {len(SERVICES)} service + mô tả: {', '.join(SERVICES)}")


def _ensure_mcp(name: str, url: str, description: str) -> None:
    # Reconcile theo NAME → đổi URL (vd localhost → endpoint AgentBase) không tạo trùng.
    by_name = {s["name"]: s for s in mcp_registry.list_servers(project_id=PROJECT_ID)}
    srv = by_name.get(name)
    if srv:
        if srv["url"].rstrip("/") != url.rstrip("/") or not srv.get("enabled"):
            mcp_registry.update_server(srv["id"], project_id=PROJECT_ID, url=url, enabled=1)
            print(f"✅ cập nhật MCP '{name}' → {url}")
        else:
            print(f"• MCP '{name}' giữ nguyên ({url})")
        return
    mcp_registry.add_server(name=name, url=url, description=description, project_id=PROJECT_ID)
    print(f"✅ đăng ký MCP '{name}' → {url}")


def _ensure_repos() -> None:
    if not NS:
        print("⚠️  GITLAB_NAMESPACE chưa set — BỎ QUA service_repos. "
              "get_code_diff sẽ không kích hoạt. Set GITLAB_NAMESPACE rồi chạy lại.")
        return
    import json as _json
    mapping = dict(SERVICE_REPOS)
    raw = os.getenv("SERVICE_REPOS_JSON", "").strip()
    if raw:
        try:
            mapping = _json.loads(raw)
        except Exception as e:
            print(f"⚠️  SERVICE_REPOS_JSON không parse được ({e}) — dùng mặc định.")
    for svc, repo in mapping.items():
        repo_url = f"{GITLAB_BASE}/{NS}/{repo}"
        project_registry.upsert_service_repo(
            PROJECT_ID, svc, repo_url, provider="gitlab", default_branch="main",
        )
        print(f"   {svc:16s} → {repo_url}")
    print(f"✅ map {len(mapping)} service → repo")


def _ensure_channel() -> None:
    if not DEMO_CHAT_ID:
        print("⚠️  DEMO_CHAT_ID chưa set — BỎ QUA kênh Telegram per-project. "
              "(Vẫn fallback env OUTPUT_CHANNELS nếu có.)")
        return
    project_registry.set_project_channel(
        PROJECT_ID, "telegram", {"chat_id": DEMO_CHAT_ID}, enabled=True,
    )
    print(f"✅ kênh Telegram per-project (chat_id={DEMO_CHAT_ID[:6]}…) "
          "— LƯU Ý: TELEGRAM_BOT_TOKEN vẫn lấy từ env.")


def main() -> None:
    print(f"=== Provision demo (DB backend={BACKEND_NAME}) ===")
    _ensure_project()
    _ensure_services()
    _ensure_mcp("telemetry-tools", TELEMETRY_MCP_URL,
                "Logs / metrics / deploys / service graph / trace (5 tool nội bộ qua MCP).")
    _ensure_mcp("gitlab-code", GITLAB_MCP_URL,
                "Đọc source code qua GitLab API (get_diff/read_file/search_code, READ-ONLY).")
    _ensure_repos()
    _ensure_channel()
    print("\nXong. Kiểm tra:")
    print(f"  curl -s localhost:8080/projects/{PROJECT_ID}/services")
    print(f"  curl -s localhost:8080/projects/{PROJECT_ID}/mcp-servers")
    print(f"  bash demo/webhooks/prometheus.sh   # bắn alert thử")


if __name__ == "__main__":
    main()
