# API Reference

> Server mặc định: `http://localhost:8000`
> Xác thực: session cookie (đăng nhập qua `/auth/login`) hoặc Bearer token (`Authorization: Bearer <token>` — dùng cho webhook/automation).

---

## Auth

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/auth/login` | Trang đăng nhập |
| POST | `/auth/login` | Đăng nhập (form: `username`, `password`) |
| POST | `/auth/logout` | Đăng xuất |

---

## Core API

### Trigger & Health

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/trigger` | Trigger investigation (global, project=default) |
| GET | `/health` | Health check → `{"status":"ok","version":"..."}` |
| GET | `/adapters` | Liệt kê intake adapter đang đăng ký |

**POST `/trigger` body:**
```json
{
  "service": "payment-gateway",
  "scenario": "scenario1",
  "time_window": "14:00-15:00",
  "symptom": "Error rate tăng đột biến",   // tuỳ chọn
  "date": "2024-01-15"                      // tuỳ chọn
}
```

### MCP Servers (global)

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/mcp-servers` | Liệt kê MCP server toàn cục |
| POST | `/mcp-servers` | Đăng ký MCP server mới |
| PATCH | `/mcp-servers/{server_id}` | Cập nhật MCP server |
| DELETE | `/mcp-servers/{server_id}` | Xóa MCP server |
| POST | `/mcp-servers/{server_id}/ping` | Kiểm tra kết nối MCP server |

---

## Projects API (`/projects`)

### CRUD

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/projects` | Liệt kê tất cả project |
| POST | `/projects` | Tạo project mới |
| GET | `/projects/{project_id}` | Chi tiết một project |
| PATCH | `/projects/{project_id}` | Cập nhật project |
| DELETE | `/projects/{project_id}` | Xóa project |

### Investigation (project-scoped)

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/projects/{project_id}/trigger` | Trigger investigation cho project |

### Services

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/projects/{project_id}/services` | Liệt kê service trong project |
| POST | `/projects/{project_id}/services` | Thêm service vào project |
| DELETE | `/projects/{project_id}/services/{service}` | Xóa service khỏi project |

### Alert Channels

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/projects/{project_id}/channels` | Liệt kê kênh alert của project |
| POST | `/projects/{project_id}/channels` | Thêm kênh alert |
| PATCH | `/projects/{project_id}/channels/{channel}` | Cập nhật config kênh |
| DELETE | `/projects/{project_id}/channels/{channel}` | Xóa kênh alert |

### LLM Config (per-project)

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/projects/{project_id}/llm` | Lấy LLM config của project |
| PATCH | `/projects/{project_id}/llm` | Cập nhật LLM endpoint/model/key |

### MCP Servers (per-project)

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/projects/{project_id}/mcp-servers` | Liệt kê MCP server của project |
| POST | `/projects/{project_id}/mcp-servers` | Đăng ký MCP server cho project |
| PATCH | `/projects/{project_id}/mcp-servers/{server_id}` | Cập nhật |
| DELETE | `/projects/{project_id}/mcp-servers/{server_id}` | Xóa |
| POST | `/projects/{project_id}/mcp-servers/{server_id}/ping` | Kiểm tra kết nối |

---

## Dashboard (`/dashboard`)

Dashboard là giao diện HTML — dùng trình duyệt hoặc gọi API JSON với `Accept: application/json`.

### Investigations

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/dashboard/` | Trang chủ — danh sách investigation |
| GET | `/dashboard/investigations/{investigation_id}` | Chi tiết investigation + trace |
| GET | `/dashboard/investigations/{investigation_id}/diff` | Replay diff (so sánh run) |
| GET | `/dashboard/investigations/{investigation_id}/export` | Export trace JSON |
| POST | `/dashboard/investigations/{investigation_id}/replay` | Replay investigation |
| POST | `/dashboard/investigations/{investigation_id}/feedback` | Feedback 👍/👎 cho verdict |
| GET | `/dashboard/stream/{investigation_id}` | SSE stream trace realtime |

### Operations

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/dashboard/trigger` | Form trigger investigation |
| POST | `/dashboard/trigger` | Submit trigger (form) |
| GET | `/dashboard/health` | Dashboard health (metrics realtime) |
| GET | `/dashboard/metrics-live` | Live metrics widget |
| GET | `/dashboard/chat` | CLI chat REPL UI |
| GET | `/dashboard/demo` | Demo kịch bản có hướng dẫn |

### Config

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/dashboard/projects` | Quản lý project |
| POST | `/dashboard/projects` | Tạo project mới (form) |
| POST | `/dashboard/projects/{project_id}/edit` | Sửa project (form) |
| POST | `/dashboard/projects/{project_id}/delete` | Xóa project (form) |
| GET | `/dashboard/projects/{project_id}` | Chi tiết project + services + LLM |
| POST | `/dashboard/projects/{project_id}/services/add` | Thêm service (form) |
| POST | `/dashboard/projects/{project_id}/services/{service}/delete` | Xóa service |
| POST | `/dashboard/projects/{project_id}/llm` | Cập nhật LLM config (form) |
| POST | `/dashboard/projects/{project_id}/channels/{channel}/config` | Cập nhật channel config |
| GET | `/dashboard/channels` | Quản lý alert channels |
| POST | `/dashboard/channels/{project_id}/{channel}/toggle` | Bật/tắt channel |
| GET | `/dashboard/mcp` | Quản lý MCP server |
| POST | `/dashboard/mcp/register` | Đăng ký MCP server (form) |
| POST | `/dashboard/mcp/{server_id}/delete` | Xóa MCP server |
| POST | `/dashboard/mcp/{server_id}/ping` | Ping MCP server |

### Analytics

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/dashboard/cost` | Cost dashboard (token + prompt caching stats) |
| GET | `/dashboard/eval` | Eval dashboard (accuracy, calibration before/after) |
| GET | `/dashboard/tools` | Danh sách tool + test-run |
| POST | `/dashboard/tools/{tool_name}/run` | Chạy thử tool |

### Admin (RBAC)

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/dashboard/admin/users` | Tạo user |
| POST | `/dashboard/admin/users/{user_id}/toggle` | Bật/tắt user |
| POST | `/dashboard/admin/users/{user_id}/assign` | Gán role cho user |
| POST | `/dashboard/admin/assignments/{assignment_id}/remove` | Xóa assignment |
| GET | `/dashboard/admin/roles` | Liệt kê role |
| POST | `/dashboard/admin/roles` | Tạo role |
| POST | `/dashboard/admin/roles/{role_id}/permissions` | Cập nhật permission |
| POST | `/dashboard/admin/roles/{role_id}/delete` | Xóa role |
| GET | `/dashboard/admin/groups` | Liệt kê project group |
| POST | `/dashboard/admin/groups` | Tạo group |
| POST | `/dashboard/admin/groups/{group_id}/add-member` | Thêm member |
| POST | `/dashboard/admin/groups/{group_id}/remove-member` | Xóa member |
| GET | `/dashboard/admin/tokens` | Liệt kê API token |
| POST | `/dashboard/admin/tokens` | Tạo API token |
| POST | `/dashboard/admin/tokens/{token_id}/revoke` | Thu hồi token |

### Scheduler

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/dashboard/scheduled` | Danh sách scheduled trigger |
| POST | `/dashboard/scheduled` | Tạo scheduled trigger |
| POST | `/dashboard/scheduled/{trigger_id}/toggle` | Bật/tắt trigger |
| POST | `/dashboard/scheduled/{trigger_id}/delete` | Xóa trigger |

---

## Intake Adapters (Webhook)

Tất cả alert webhook gửi qua `POST /trigger` (hoặc `POST /projects/{id}/trigger`) với header `X-Alert-Source` để router chọn adapter đúng.

| `X-Alert-Source` | Adapter | Payload format |
|-----------------|---------|----------------|
| `prometheus` | PrometheusAdapter | AlertManager webhook |
| `grafana` | GrafanaAdapter | Grafana alert JSON |
| `sentry` | SentryAdapter | Sentry issue webhook |
| `pagerduty` | PagerDutyAdapter | PagerDuty incident webhook |
| `opsgenie` | OpsGenieAdapter | OpsGenie alert webhook |
| `github` | GitHubAdapter | GitHub Actions deploy event |
| `gitlab` | GitLabAdapter | GitLab pipeline event |
| *(không có)* | Fallback | Raw JSON → InvestigationRequest trực tiếp |

Ví dụ webhook Prometheus:
```bash
curl -X POST localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -H "X-Alert-Source: prometheus" \
  -d '{
    "alerts": [{
      "labels": {"alertname": "HighErrorRate", "service": "payment-gateway"},
      "annotations": {"summary": "Error rate > 5%"},
      "startsAt": "2024-01-15T14:00:00Z"
    }]
  }'
```

---

## Webhook Signature (HMAC-SHA256)

Để bảo mật webhook từ nguồn ngoài, set `WEBHOOK_SECRET` trong `.env`. Server xác thực header `X-Webhook-Signature: sha256=<hmac>`.

```bash
# Tạo signature:
echo -n '<body>' | openssl dgst -sha256 -hmac '<WEBHOOK_SECRET>'
```
