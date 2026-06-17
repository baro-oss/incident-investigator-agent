# DEMO — Trình diễn toàn hệ thống

> **Mạch câu chuyện:** webhook alert từ nhiều nền tảng → agent tự điều tra qua MCP tools
> (logs · metrics · deploy history · service graph) → đọc source GitLab → verdict neo bằng
> chứng code → push Telegram.
>
> Trong lúc demo, ta cấu hình trực tiếp trên UI: LLM model · service mới · MCP server ·
> repo source map · Telegram channel — để người xem thấy platform là **pluggable hoàn toàn**.
>
> Backend: **Postgres** · LLM: **MiniMax (GreenNode MaaS)** · MCP: **AgentBase endpoints** ·
> Project: `demo-day`.

---

## Phần 0 — Chuẩn bị (off-camera, 1 lần)

### 0.1 Seed dữ liệu + GitLab repos

```bash
make demo-prep
# seed scenario "demo" vào Postgres + push source v2.3.0/v2.4.0 lên GitLab +
# provision project demo-day (4 service, 2 MCP AgentBase, service repos, Telegram)
```

### 0.2 Khởi động server chính

```bash
make server            # cổng 8080 — MCP đã trên AgentBase, không cần demo-up
```

Kiểm tra nhanh:

```bash
curl -s localhost:8080/health | jq '{status, db_backend, llm_provider}'
# → { "status": "ok", "db_backend": "postgres", "llm_provider": "greennode" }
```

> **MCP telemetry** và **GitLab code MCP** đã chạy thường trực trên **AgentBase** (không cần local):
> - Telemetry: `https://<your-mcp-telemetry-endpoint>.agentbase-runtime.aiplatform.vngcloud.vn/mcp`
> - GitLab Code: `https://<your-mcp-gitlab-endpoint>.agentbase-runtime.aiplatform.vngcloud.vn/mcp`

---

## Phần 1 — Cấu hình trực tiếp trên Dashboard UI

> **Mở trình duyệt:** `http://localhost:8080/dashboard/`

### Bước 1a — Xem danh sách project

Mở [`/dashboard/projects`](http://localhost:8080/dashboard/projects):

- Thấy project **`demo-day`** đã tồn tại.
- Click vào **demo-day** để vào trang chi tiết.

---

### Bước 1b — Cấu hình LLM model (MiniMax / GreenNode MaaS)

Trong trang project [`/dashboard/projects/demo-day`](http://localhost:8080/dashboard/projects/demo-day):

1. Cuộn xuống mục **"LLM Configuration"**.
2. **Provider** → chọn `greennode`.
3. **Model** → chọn `minimax/minimax-m2.5`.
4. **Base URL** → tự điền `https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1`.
5. Nhập **API Key** (GreenNode MaaS key) → click **"Test Connection"** → badge `✓ Hoạt động`.
6. Click **"Lưu cấu hình LLM"**.

> **Điểm nhấn:** mỗi project có thể dùng LLM riêng — một project Anthropic, project khác Groq, project khác MiniMax tự host.

---

### Bước 1c — Thêm service mới (live)

Vẫn trong trang **demo-day**, mục **"Services"**:

Hiện có 4 service: `api-gateway`, `payment-gateway`, `auth-service`, `order-service`.

**Thêm service thứ 5:**

| Trường | Giá trị |
|---|---|
| Service name | `notification-service` |
| Mô tả | `Gửi thông báo đến user qua email/SMS khi giao dịch hoàn tất.` |

→ Click **"Thêm service"** → service xuất hiện ngay trong danh sách (không reload trang).

> **Điểm nhấn:** danh sách service này được đưa vào prompt engine dưới dạng `available_services` — agent biết topology của hệ thống mà không cần tool riêng.

---

### Bước 1d — Thêm MCP server

Mở [`/dashboard/mcp`](http://localhost:8080/dashboard/mcp):

Hiện có 2 MCP đã đăng ký cho **demo-day** (AgentBase endpoints). Để demo tính năng hot-plug, ta **thêm thủ công** MCP telemetry cục bộ:

| Trường | Giá trị |
|---|---|
| Tên | `telemetry-local-demo` |
| URL | `http://localhost:9000/mcp` |
| Project | `demo-day` |
| Mô tả | `MCP telemetry cục bộ (demo hot-plug)` |

→ Click **"Đăng ký"** → Click **"Ping"** trên dòng vừa thêm → badge `✓ ok`.

> **Điểm nhấn:** engine merge tool từ mọi MCP — MCP nào expose tool cùng tên → override local. Thêm MCP mới không cần restart server.

---

### Bước 1e — Thêm repo source map

Vẫn trong trang **demo-day**, mục **"Source Repositories"**:

4 service hiện đã có repo map. Thêm repo cho `notification-service`:

| Trường | Giá trị |
|---|---|
| Service | `notification-service` |
| Repo URL | `https://gitlab.com/baopx-microservices/notification-service` |
| Provider | `gitlab` |
| Branch | `main` |

→ Click **"Thêm repo"**.

> **Điểm nhấn:** khi service này xuất hiện trong incident, engine tự kích hoạt `get_code_diff` đọc source — không cần config thêm bất cứ đâu.

---

### Bước 1f — Cấu hình kênh Telegram

Mở [`/dashboard/channels`](http://localhost:8080/dashboard/channels):

1. Chọn project **demo-day**.
2. Bật **Telegram** → nhập `Chat ID` (vd: `-1004205633841`).
3. Toggle **"Bật"** → click **"Lưu"**.

> **Điểm nhấn:** mỗi project nhận alert vào channel riêng. `TELEGRAM_BOT_TOKEN` chung từ env — chỉ `chat_id` khác nhau giữa các project (multi-tenant).

---

### Bước 1g — Xem sức khỏe hệ thống

Mở [`/dashboard/health`](http://localhost:8080/dashboard/health):

- DB backend: **postgres** ✓
- LLM provider: **greennode** ✓
- 2 MCP AgentBase: **reachable** ✓
- Queue: 0 in-flight

---

## Phần 2 — Kích hoạt điều tra (intake đa nền tảng)

### Bước 2a — Trigger qua UI

Mở [`/dashboard/trigger`](http://localhost:8080/dashboard/trigger):

| Trường | Giá trị |
|---|---|
| Project | `demo-day` |
| Service | `payment-gateway` |
| Scenario | `demo` |
| Time window | `09:00-10:00` |
| Date | `2026-06-16` |

→ Click **"Trigger"** → `202 Accepted`.

### Bước 2b — Hoặc webhook curl (nhiều nền tảng)

```bash
# Prometheus
make demo-webhook

# Grafana
make demo-webhook src=grafana

# Sentry
make demo-webhook src=sentry

# OpsGenie
make demo-webhook src=opsgenie
```

> Mỗi webhook format khác nhau (JSON schema, header `X-Alert-Source`) → engine nhận cùng 1 `InvestigationRequest` — đây là **platform 4 cạnh pluggable** trong thực tế.

---

## Phần 3 — Xem agent điều tra (terminal log)

```
[demo-day] Kết nối 2 MCP server(s) → Registry 8 tool
Thêm get_code_diff (code_mcp=True, 4 repo mapping)
available_services: api-gateway, payment-gateway, auth-service, order-service, notification-service

Bước 1  get_error_breakdown    → 84% TimeoutException từ 09:05
Bước 2  get_metrics            → p99 = 993ms, baseline 120ms, spike 8.3x từ 09:05
Bước 3  get_recent_deploys     → payment-gateway v2.4.0 @ 09:02 (trước spike 3 phút)
Bước 4  get_dependencies       → payment-gateway → auth-service / third-party-provider
Bước 5  get_code_diff(payment-gateway, v2.4.0)
         ← GitLab API → diff thật: MAX_POOL_SIZE 50→5 + xóa retry guard
         code_distill → RISK: config-knob · removed-error-handling

Stop: verdict | confidence=high
Root cause: v2.4.0 giảm MAX_POOL_SIZE 50→5 + xóa error-handling → pool exhaustion → timeout
Telegram gửi OK → chat -1004205633841
```

---

## Phần 4 — Kết quả

### Bước 4a — Tin Telegram

Mở chat Telegram → tin nhắn root cause:
- Service: `payment-gateway`, deploy `v2.4.0`
- Bằng chứng code: pool 50→5 + removed error-handling
- Độ tin: **HIGH**

### Bước 4b — Dashboard investigation

Mở [`/dashboard/`](http://localhost:8080/dashboard/):

- Click investigation vừa chạy → xem trace từng bước.
- Tab **Replay diff** → so sánh 2 phiên cùng incident.
- [`/dashboard/cost`](http://localhost:8080/dashboard/cost) → chi phí LLM theo project.

---

## Kịch bản 2 — auth-service / JWT leeway (scenario `demo2`)

> Culprit khác hẳn: **auth-service** deploy `v1.2.0` @ 14:05 ngày 2026-06-17 bỏ
> `leeway=30` trong `jwt.decode` + xoá try/except → token hợp lệ bị reject khi đồng
> hồ lệch → **HTTP_401 ~78%** từ 14:08, lan ngược lên payment-gateway → api-gateway / order-service.

```bash
make demo2-prep          # seed scenario demo2 + push auth-service v1.1.0/v1.2.0 lên GitLab
make server              # (nếu chưa chạy) cổng 8080
make demo2-webhook       # bắn Prometheus alert (auth-service, demo2, 14:00-15:00)
# hoặc: make demo2-webhook src=demo2-simple   (trigger thủ công, mọi tham số tường minh)
```

Đường điều tra: `get_error_breakdown` (78% HTTP_401) → `get_metrics` (error_rate vọt) →
`get_recent_deploys` (auth-service v1.2.0 @ 14:05) → `get_dependencies` (được gọi bởi
payment-gateway → blast radius) → `get_code_diff(auth-service, v1.2.0)` → RISK:
removed-error-handling (leeway + try/except bị xoá) → **Verdict HIGH**.

---

## Tổng kết tính năng được phủ

| Tính năng | Chứng minh tại |
|---|---|
| **LLM pluggable** (Anthropic · GreenNode/MiniMax · Groq …) | Bước 1b — dropdown provider/model |
| **Service registry** (mô tả đưa vào engine) | Bước 1c — thêm `notification-service` live |
| **MCP hot-plug** (merge tool, override cùng tên) | Bước 1d — thêm MCP, ping |
| **Service → repo mapping** (kích hoạt code diff tự động) | Bước 1e — map repo mới |
| **Multi-tenant Telegram** (per-project chat_id) | Bước 1f — cấu hình channel |
| **Intake đa nền tảng** (Prometheus/Grafana/Sentry/OpsGenie) | Phần 2 — nhiều webhook format |
| **Engine adaptive** + tool-calling | Phần 3 — chuỗi 5+ bước |
| **MCP telemetry** (logs/metrics/deploys/graph) | `get_error_breakdown`, `get_metrics`, … |
| **GitLab code MCP** + `code_distill` RISK signals | `get_code_diff` → pool 50→5 |
| **Output neo bằng chứng** → Telegram | Phần 4a |
| **Observability** (trace · replay · cost · specificity) | Phần 4b |
| **Postgres backend** + project isolation | Toàn mạch |

---

## Chú thích nhanh

| | |
|---|---|
| Main app | `http://localhost:8080` |
| Dashboard | `http://localhost:8080/dashboard/` |
| MCP telemetry (AgentBase) | `https://<your-mcp-telemetry-endpoint>.agentbase-runtime.aiplatform.vngcloud.vn` |
| MCP GitLab code (AgentBase) | `https://<your-mcp-gitlab-endpoint>.agentbase-runtime.aiplatform.vngcloud.vn` |
| AgentBase console | `https://aiplatform.console.vngcloud.vn/agent-runtime?tab=runtime` |
| Runbook kỹ thuật đầy đủ | [`docs/DEMO.md`](docs/DEMO.md) |
