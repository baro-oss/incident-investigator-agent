# 10 — Roadmap 20 ngày (Phase 2 trở đi)

> MVP 5 ngày đã hoàn thành trong **Ngày 1** thực tế.  
> File này là kế hoạch mở rộng 20 ngày, chia 4 phase rõ ràng.  
> **Nguyên tắc giữ nguyên:** không thêm Kafka, không thêm PostgreSQL — giữ stack nhẹ (SQLite WAL + asyncio).

---

## Trạng thái xuất phát Phase 1 (đã xong — không làm lại)

### MVP gốc (Ngày 1–5)
- Engine adaptive loop + 5 tool nội bộ + 2 kịch bản synthetic
- Verdict neo bằng chứng, trace events ghi SQLite
- Telegram adapter + intake normalizer/runner + trigger script
- Eval script (`eval_agent.py`) chạy N lần tự đếm đúng/sai
- Real LLM verified: KB1 (5 bước, HIGH) + KB2 (8 bước, HIGH) đúng root cause
- Full pipeline: `trigger.py --scenario X` → investigate → Telegram push

### Phase 1 đã xong (Ngày 6–8 + extras)

**Ngày 6 — FastAPI Webhook ✅**
- `src/agent/intake/server.py` v0.1: POST /trigger → 202 Accepted ngay, GET /health
- `scripts/start_server.py`

**Ngày 7 — Multi-adapter Intake ✅**
- `src/agent/intake/adapters/` — prometheus, grafana, sentry
- Router `X-Alert-Source` header → adapter đúng; GET /adapters list nguồn hỗ trợ
- `parse_alert_time()` chuẩn hóa ISO timestamp → (time_window, date)

**Ngày 8 — MCP Hot-plug ✅**
- `src/agent/tools/mcp_client.py` — MCPClient (JSON-RPC 2.0 over HTTP, không dùng mcp SDK vì Python 3.9)
- `src/agent/tools/registry.py` — `build_tool_registry(mcp_clients)` merge local + MCP
- `mcp_server/server.py` — demo MCP server, expose 5 tool nội bộ qua JSON-RPC
- `scripts/start_mcp_server.py`

**Ngày 8+ — MCP Registry DB ✅** (ngoài plan gốc, theo yêu cầu)
- `data/schema.sql` — thêm bảng `mcp_servers`
- `src/agent/intake/mcp_registry.py` — CRUD: list/add/remove/update/ping, lưu SQLite
- `src/agent/intake/server.py` v0.3: GET/POST/PATCH/DELETE /mcp-servers, /ping

**Ngày 8+ — Project Isolation ✅** (ngoài plan gốc, theo yêu cầu)
- `data/schema.sql` — thêm `projects` (TEXT PK slug), `project_services` (junction)
- `data/migrate_projects.py` — migration idempotent, seed project 'default'
- `src/agent/intake/project_registry.py` — CRUD projects + services
- `src/agent/intake/mcp_registry.py` — tất cả function nhận `project_id`
- `src/agent/intake/normalizer.py` — `InvestigationRequest` có `project_id`; dedup_key: `{project_id}|{service}|{scenario}|{time_window}`
- `src/agent/engine/state.py` — `InvestigationState` có `project_id`, `available_services`
- `src/agent/engine/loop.py` — `run()` nhận project context, `_emit_trace()` ghi project_id
- `src/agent/intake/runner.py` — `_get_mcp_urls_for_project()`, `_get_project_services()`
- `src/agent/intake/server.py` v0.4: 22 routes (backward compat + full /projects/* CRUD)

---

## Ràng buộc cố định (không thay đổi dù ai đề xuất)

- ❌ KHÔNG Kafka / message broker → giữ asyncio background task
- ❌ KHÔNG PostgreSQL → giữ SQLite WAL
- ❌ KHÔNG thêm infra nặng → mọi thứ chạy được bằng `pip install` + env vars
- ✅ MCP: mở rộng thêm tool pack MCP, không chỉ 1 tool demo
- ✅ LangGraph: nâng cấp loop (không rewrite vì hàm pure sẵn rồi)
- ✅ Multi-agent: dùng LangGraph orchestration

---

## Tổng quan 4 phase

```
Phase 1 (Ngày 6–10)  : Platform Extension   — webhook, adapter, MCP, 4 kịch bản, output đa kênh  ✅ HOÀN TẤT
Phase 2 (Ngày 11–14) : Observability + UI v1 — Langfuse, eval CI, long-term memory, Dashboard + Chat UI
Phase 3 (Ngày 15–17) : Architecture Upgrade  — LangGraph, multi-agent, resilience, full platform UI
Phase 4 (Ngày 18–20) : Product Polish        — Fintech domain, eval N=10, demo hoàn chỉnh
```

### Tiến độ Phase 2

| Ngày | Nội dung | Trạng thái |
|------|----------|-----------|
| 11 | Langfuse integration, token usage, span hierarchy | ✅ |
| 12 | Eval CI (recall@1, hallucination, token_efficiency) + Long-term memory | ☐ |
| 13 | Dashboard v1: investigation list, trace viewer, alert trigger builder | ☐ |
| 14 | Dashboard v2: SSE real-time, Chat UI, eval chart + Cổng Phase 2 | ☐ |

### Tiến độ Phase 1

| Ngày | Nội dung | Trạng thái |
|------|----------|-----------|
| 6 | FastAPI webhook POST /trigger → 202 → Telegram | ✅ |
| 7 | 3 adapter: Prometheus / Grafana / Sentry | ✅ |
| 8 | MCP hot-plug (agent là consumer) | ✅ |
| 8+ | MCP Registry DB (lưu SQLite, CRUD API, /ping) | ✅ (extra) |
| 8+ | Project Isolation (multi-tenant, /projects/* routes) | ✅ (extra) |
| 9 | Kịch bản 3 & 4 (DB pool, traffic surge) | ✅ |
| 10 | Output đa kênh (Teams) + cổng Phase 1 | ✅ |

---

## Phase 1 — Platform Extension (Ngày 6–10)

**Mục tiêu:** Engine nhận alert thật qua webhook, nhiều kênh output, MCP hot-plug thật sự, 4 kịch bản chống hardcode.

### Ngày 6 — FastAPI Webhook

**Làm:**
- `src/agent/intake/server.py` — FastAPI app
  - `POST /trigger` → `map_simple_payload()` → `trigger_investigation()` → trả `202 Accepted` ngay
  - `GET /health` → số phiên đang chạy, uptime
- `scripts/start_server.py` — uvicorn wrapper
- Giữ nguyên `runner.py` — server chỉ là cửa vào HTTP mới

**Test:**
```bash
uvicorn agent.intake.server:app --reload
curl -X POST localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-gateway","scenario":"scenario1","time_window":"14:00-15:00"}'
# → 202 {"status":"accepted","investigation_id":"..."}
# Telegram nhận verdict sau ~1 phút
```

**Cổng:** HTTP 202 → investigation chạy nền → Telegram ping.

---

### Ngày 7 — Multi-adapter Intake

**Làm:**
- `src/agent/intake/adapters/prometheus.py` — map Prometheus AlertManager payload
- `src/agent/intake/adapters/grafana.py` — map Grafana unified alerting
- `src/agent/intake/adapters/sentry.py` — map Sentry issue webhook
- Router trong `server.py`: đọc header `X-Alert-Source` → chọn adapter đúng

**Cấu trúc adapter:**
```python
# Mỗi adapter là hàm đơn giản
def map_prometheus(payload: dict) -> Optional[InvestigationRequest]: ...
def map_grafana(payload: dict) -> Optional[InvestigationRequest]: ...
```

**Test:** curl với payload mẫu của từng nguồn, verify InvestigationRequest được tạo đúng.

**Cổng:** 3 adapter hoạt động, test bằng curl payload thật.

---

### Ngày 8 — MCP Hot-plug (Agent là MCP Consumer)

**Mục tiêu thực (cập nhật):** Agent là **MCP consumer** — nhận tool từ bất kỳ MCP server bên ngoài nào. Dữ liệu không phải chỉ từ SQLite nội bộ; bất kỳ team nào có hệ thống monitoring riêng đều có thể expose qua MCP để agent dùng.

**Vì sao không dùng `mcp` Python SDK:** Python 3.9 không tương thích (SDK yêu cầu ≥3.10). Thay vào đó implement **MCP Streamable HTTP transport trực tiếp** (JSON-RPC 2.0 over HTTP) — đây chính là chuẩn giao thức mà mọi MCP server đều theo. Khi upgrade lên Python 3.10+: swap client → `mcp.ClientSession`, server → `FastMCP`, không đổi engine.

**Kiến trúc:**
```
Investigation Engine
       ↓ list[Tool] (đường ranh giữ nguyên)
   Tool Registry
       ├── Local Tools  (SQLite — luôn có, fallback)
       └── MCP Tools    (từ bất kỳ MCP server nào — dynamic)
                ↑
    MCP_SERVER_URLS=url1,url2,...  (env var)
```

**Làm:**
- `src/agent/tools/mcp_client.py` — `MCPClient`: kết nối → `initialize` → `tools/list` → `tools/call`
  - Wrap từng MCP tool thành `Tool` (đường ranh không vỡ: engine chỉ thấy `list[Tool]`)
  - Parse kết quả → `Observation` (JSON nếu server "biết" format; generic wrapper nếu external)
- `src/agent/tools/registry.py` — thêm `build_tool_registry(mcp_clients)` async
  - MCP tool override local tool cùng tên (MCP là nguồn ưu tiên khi đã cấu hình)
- `src/agent/intake/runner.py` — đọc `MCP_SERVER_URLS`, connect trước investigation, close sau
- `mcp_server/server.py` — demo MCP server (FastAPI + JSON-RPC 2.0)
  - Expose 5 tool nội bộ qua MCP protocol để test round-trip
  - Đây là **ví dụ** — bất kỳ server nào implement cùng giao thức đều cắm vào được
- `scripts/start_mcp_server.py`

**Demo hot-plug:**
```bash
# Terminal 1: start MCP tool server (port 9000)
python scripts/start_mcp_server.py

# Terminal 2: start investigation server
MCP_SERVER_URLS=http://localhost:9000/mcp python scripts/start_server.py

# Terminal 3: trigger
curl -X POST localhost:8000/trigger -H "Content-Type: application/json" \
  -d '{"service":"payment-gateway","scenario":"scenario1","time_window":"14:00-15:00"}'
# Telegram nhận verdict — agent đã dùng tools từ MCP server

# Thêm tool mới vào mcp_server/server.py → restart MCP server → agent tự discover
# KHÔNG cần restart investigation server hay sửa engine
```

**Câu chuyện pitch:** "Bất kỳ team nào tự viết MCP server cho monitoring system của họ (Prometheus, Loki, Jaeger...) là agent cắm vào được ngay — không sửa một dòng engine."

**Cổng:** Bật MCP server → investigation dùng MCP tools → Telegram verdict đúng. Bỏ 1 tool khỏi MCP server → investigation tự điều chỉnh (dùng local fallback hoặc kết luận với ít tool hơn).

> **✅ DONE.** Ngoài plan gốc, đã build thêm theo yêu cầu:
> - **MCP Registry DB**: `mcp_servers` bảng SQLite, CRUD API (`GET/POST/PATCH/DELETE /mcp-servers`, `/ping`). Investigation tự đọc DB thay vì cần env var.
> - **Project Isolation**: `projects` + `project_services` bảng, MCP servers scoped per project. Webhook route `POST /projects/{id}/trigger`. `dedup_key` bao gồm `project_id`. `InvestigationState` có `available_services` gợi ý scope.

---

### Ngày 9 — Kịch bản 3 & 4

**Kịch bản 3 (KB3): DB connection pool exhaustion**
- auth-service chiếm hết connection pool → timeout lan lên payment-gateway
- Tín hiệu: auth-service latency tăng, connection_wait_time metric spike
- Root cause: auth-service (không phải payment-gateway)
- `data/seed_scenario3.py`

**Kịch bản 4 (KB4): Traffic surge → rate limiting**  
- api-gateway nhận traffic gấp 5x → rate limit kick in → HTTP_429 hàng loạt
- Tín hiệu: request_count spike tại api-gateway, lỗi là RateLimitError không phải lỗi code
- Root cause: external traffic surge, không phải code bug
- `data/seed_scenario4.py`

**Eval:**
```bash
python scripts/eval_agent.py --n 5  # chạy cả 4 kịch bản
# Target: ≥7/10 đúng root cause mỗi kịch bản
```

**Cổng:** 4 kịch bản, eval ≥7/10 mỗi cái.

---

### Ngày 10 — Output Đa kênh + Cổng Phase 1

**Đã làm (thực tế):**
- `src/agent/output/teams.py` — Microsoft Teams Incoming Webhook adapter (MessageCard / Office 365 Connector)
- `src/agent/output/email.py` — SMTP adapter (stdlib smtplib, HTML + plain text, async via executor)
- `src/agent/output/router.py` — fan-out verdict: DB per-project channels → fallback env `OUTPUT_CHANNELS`
- `src/agent/intake/project_registry.py` — channel CRUD: `list/get_enabled/set/remove_project_channel`
- `data/schema.sql` + `migrate_projects.py` — bảng `project_alert_channels` (project_id, channel, config JSON, enabled)
- `src/agent/intake/server.py` — 4 routes: GET/POST/PATCH/DELETE `/projects/{pid}/channels`
- `src/agent/intake/runner.py` — đổi sang `push_verdict` (output router)
- `src/agent/output/telegram.py` — thêm `config["chat_id"]` override

**Config toàn cục (env):**
```bash
OUTPUT_CHANNELS=telegram,teams   # fallback khi project không có DB channels
TEAMS_WEBHOOK_URL=https://xxx.webhook.office.com/...
SMTP_HOST=smtp.example.com
SMTP_USER=alert@example.com
SMTP_PASSWORD=xxx
SMTP_FROM=alert@example.com
SMTP_TO=oncall@example.com
```

**Per-project override (API):**
```bash
POST /projects/{pid}/channels
Body: {"channel": "teams", "config": {"webhook_url": "https://..."}, "enabled": true}
```

**Router priority:** DB per-project channels (nếu có) → env `OUTPUT_CHANNELS` (fallback).

**Cổng Phase 1 ✅ PASS:** Webhook live + 4 kịch bản + Telegram + Teams + Email + per-project channel config.

**Quyết định lệch plan gốc:** Dùng Microsoft Teams thay Slack (yêu cầu từ người dùng). Email adapter thêm vào cùng session (yêu cầu bổ sung). Per-project channel config thêm cùng lúc để hoàn chỉnh kiến trúc output.

---

## Phase 2 — Observability & Quality (Ngày 11–14)

**Mục tiêu:** Biết agent đúng *vì lý do đúng*, không phải may. Có vòng phản hồi tự động. Dashboard bắt đầu xuất hiện.

### Ngày 11 — Langfuse Integration ✅

**Đã làm:**
- `src/agent/observability/langfuse_tracer.py` — tracer stateful, opt-in qua `LANGFUSE_PUBLIC_KEY`
- Span hierarchy: `investigation` → `step_{n}` → `llm_decision` / `tool_call`
- `LLMResponse.usage` — token tracking từ Anthropic + OpenAI-compat
- Timing: `time.monotonic()` đo latency LLM + tool riêng biệt
- `decide_next_action` trả 3-tuple; SQLite trace không đổi — Langfuse additive
- Langfuse SDK v3 (API khác v2 — đã fix: `start_span`, `usage_details`, nested spans)

**Cổng ✅ PASS:** Langfuse dashboard có trace đẹp từng bước + latency + token usage.

---

### Ngày 12 — Eval Framework + Long-term Memory

**A. Eval CI Framework:**
- Mở rộng `eval_agent.py` thêm metrics chi tiết:
  - `recall@1` — root cause đúng ở hypothesis #1 không
  - `steps_to_correct` — bao nhiêu bước trước khi có đủ bằng chứng
  - `hallucination_check` — verdict có claim nào không có evidence đỡ không
  - `token_efficiency` — tổng token / số bước (từ `LLMResponse.usage`)
- `.github/workflows/eval.yml` — chạy eval N=5 khi push/merge vào main
- Fail CI nếu `correct_rate < 0.7` ở bất kỳ kịch bản nào
- Bảng `eval_results` (SQLite): `(run_id, scenario, correct_rate, recall_at_1, steps_to_correct, token_total, run_at)`

**B. Long-term Memory:**
- Bảng `investigation_patterns` trong SQLite:
  ```sql
  (service, error_pattern, successful_tool_sequence, root_cause_type, avg_steps, count)
  ```
- Sau mỗi verdict `high` confidence → ghi pattern
- Warm-start: service+error_type đã thấy → inject `hint_tool` vào `InvestigationState` (LLM thấy nhưng không bắt buộc dùng)
- Baseline tự cập nhật: metric bình thường → cập nhật `baseline_latency_p99` trong catalog sau 7 ngày không có incident

**Cổng:** CI eval xanh + lần điều tra thứ 2 cùng service có warm-start hint.

---

### Ngày 13 — Dashboard UI v1 + Alert Trigger Builder

**Stack:** FastAPI + Jinja2 (mount vào `server.py` hiện tại, không cần Node.js build step).

**A. Core Dashboard:**
- `src/agent/dashboard/` — APIRouter mount vào server.py: `app.mount("/dashboard", ...)`
- `GET /dashboard` — trang chủ: danh sách investigations (từ `trace_events` group by `investigation_id`)
  - Cột: investigation_id, project, service, scenario, verdict confidence, steps, thời gian
  - Filter: project_id, confidence, date range
- `GET /dashboard/investigations/{inv_id}` — trace viewer:
  - Timeline từng bước: tool → observation summary → hypothesis update
  - Verdict card: root cause, confidence, evidence summary
  - Langfuse link (nếu có `LANGFUSE_PUBLIC_KEY`)
- Static files: `src/agent/dashboard/static/` (CSS + minimal JS, không framework)

**B. Alert Trigger Builder:**
- `GET /dashboard/trigger` — form UI thay thế curl:
  - Dropdown: project, service (từ `project_services`), scenario, time window
  - Submit → POST `/projects/{pid}/trigger` → hiển thị investigation_id + link trace
- `GET /dashboard/projects` — danh sách projects + services overview

**Cổng:** Mở browser thấy investigation history, click detail trace, trigger investigation từ form.

---

### Ngày 14 — Dashboard v2: Real-time + Chat UI + Cổng Phase 2

**A. Real-time SSE:**
- `GET /dashboard/stream/{inv_id}` — SSE endpoint stream trace events khi investigation đang chạy
- Dashboard detail page tự động subscribe SSE khi `stop_reason` chưa có
- Mỗi `_emit_trace` event → push SSE → browser append step vào timeline live

**B. Chat UI (wow moment):**
- `GET /dashboard/chat` — trang chat interface:
  - Input: gõ tự nhiên "Điều tra payment-gateway từ 14:00" hoặc chọn từ dropdown
  - Submit → POST `/projects/{pid}/trigger` → investigation chạy background
  - SSE auto-connect → stream từng bước điều tra trực tiếp vào browser
  - Verdict hiện cuối cùng với confidence badge
- Câu chuyện pitch: "Không cần curl, không cần terminal — chat thẳng với agent."

**C. Eval Trend + Token Cost:**
- `GET /dashboard/eval` — chart eval trend từ `eval_results` table (Chart.js CDN)
  - correct_rate theo ngày/run, token_efficiency, steps_to_correct per scenario
- `GET /dashboard/cost` — token usage summary từ trace + Langfuse (nếu available)

**Cổng Phase 2:** Langfuse live + CI eval xanh + Dashboard SSE + Chat UI hoạt động.

---

## Phase 3 — Architecture Upgrade (Ngày 15–17)

**Mục tiêu:** Chứng minh kiến trúc scale được — không rewrite, chỉ nâng cấp. Dashboard mở rộng theo.

### Ngày 15 — LangGraph Migration + Multi-agent

**A. LangGraph Migration:**

Tại sao dễ: `decide_next_action`, `run_tool`, `update_state` đã là hàm pure → wrap thành node, không viết lại logic.

- `pip install langgraph`
- `src/agent/engine/graph.py` — StateGraph thay InvestigationEngine class:
  ```python
  graph = StateGraph(InvestigationState)
  graph.add_node("decide", decide_next_action_node)
  graph.add_node("run_tool", run_tool_node)
  graph.add_node("update", update_state_node)
  graph.add_conditional_edges("decide", route_fn)  # tool_call | verdict | budget | loop
  ```
- `InvestigationEngine.run()` vẫn là public interface — bên trong compile graph
- Parallel tool execution: khi LLM suggest 2 tool độc lập → `asyncio.gather` → giảm bước

**B. Multi-agent:**

Kiến trúc:
```
OrchestratorAgent
├── LogAnalystAgent    (get_error_breakdown, trace_request)
└── MetricAnalystAgent (get_metrics, get_recent_deploys, get_dependencies)
         ↓ merge evidence
     VerdictAgent
```

- `src/agent/engine/multi_agent.py` — orchestrator + 2 specialist + verdict agent
- Mỗi specialist: InvestigationEngine với tool set giới hạn + step budget riêng
- Evidence merger: combine + dedup Observation trước khi VerdictAgent kết luận

**C. Dashboard: Agent Graph Visualization:**
- `GET /dashboard/investigations/{inv_id}/graph` — visualize agent graph
  - Node: step, tool, LLM decision
  - Edge: thứ tự thực thi
  - Parallel nodes hiện song song

**Demo:** KB2 — 2 specialist agent chạy song song → VerdictAgent merge → kết quả nhanh hơn.

**Cổng:** KB1+KB2 pass qua LangGraph, multi-agent đúng + nhanh hơn, graph hiện trên dashboard.

---

### Ngày 16 — Resilience + CLI + System Health Dashboard

**A. Resilience:**
- `src/agent/engine/resilience.py`:
  - `with_retry(coro, max_attempts=3, base_delay=2.0)` — exponential backoff khi LLM 429/503
  - `ConcurrencyLimiter(max_concurrent=3)` — queue investigation khi vượt giới hạn
  - Circuit breaker: LLM fail 3 lần liên tiếp → pause 60s → alert Telegram
  - Graceful shutdown: SIGTERM → finish phiên đang chạy → push verdict partial

**B. Interactive CLI:**
- `scripts/chat.py` — REPL nhận câu hỏi tự nhiên:
  ```bash
  python scripts/chat.py
  > Điều tra payment-gateway từ 14:00 đến 15:00 hôm nay
  [agent chạy] → Root cause: Deploy v2.3.1... (HIGH confidence)
  > Còn auth-service thì sao?
  [agent chạy] → auth-service bình thường trong window đó
  ```
- Parse câu tự nhiên → `InvestigationRequest` → chạy engine trực tiếp (không qua HTTP)

**C. Dashboard: System Health + Queue:**
- `GET /dashboard/health` — system health page:
  - LLM provider status (ping test)
  - Investigation queue: đang chạy / đang chờ / giới hạn concurrent
  - Circuit breaker state: closed / open / half-open
  - MCP servers status (ping từng server)
- `GET /dashboard/metrics-live` — **Live Metrics Widget**:
  - Panel hiện baseline vs current cho mỗi service từ SQLite metrics table
  - Auto-refresh mỗi 30s (simple polling)
  - Màu: xanh = trong baseline, cam = ±50%, đỏ = >2x
- `GET /dashboard/channels` — **Alert Channel Config UI**:
  - Per-project: enable/disable Telegram/Teams/Email
  - Form test-send (gửi message thử ngay trên UI)

**Câu chuyện pitch:** "Hai cửa vào, một engine — push khi có alert, pull khi muốn hỏi."

**Cổng Phase 3:** 3 phiên concurrent không conflict + CLI hỏi-đáp + health page live + circuit breaker.

---

### Ngày 17 — Dashboard v3: Full Platform Management UI

Mục tiêu: Mọi thứ đã build được quản lý từ browser — không cần curl, không cần CLI.

**A. MCP Registry UI:**
- `GET /dashboard/mcp` — danh sách MCP servers:
  - Columns: name, URL, project, status (ping), tools count
  - Ping button → gọi `/mcp-servers/{id}/ping` → hiển thị latency + tools list
  - Register form: name, URL, project dropdown
  - Delete với confirm

**B. Project Management UI:**
- `GET /dashboard/projects/{pid}` — project detail:
  - Services list + thêm/xóa service
  - MCP servers gắn với project
  - Alert channels: toggle enable/disable, edit config (webhook URL, chat_id, email)
  - Recent investigations của project

**C. Investigation Replay (tính năng mới):**
- `POST /dashboard/investigations/{inv_id}/replay` — chạy lại investigation:
  - Dùng cùng `symptom`, `scenario`, `time_window` từ investigation gốc
  - Kết quả mới hiện song song với kết quả cũ để so sánh
  - Useful cho eval ("agent có ra cùng kết luận không?") + demo

**D. Demo Mode:**
- `GET /dashboard/demo` — full-screen demo view:
  - Ẩn cài đặt, chỉ hiện trigger + chat + live stream + verdict
  - Dark mode, font lớn, animations nhẹ

**Cổng:** Toàn bộ platform (projects, MCP, channels, trigger, replay) quản lý từ browser.

---

## Phase 4 — Product Polish (Ngày 18–20)

**Mục tiêu:** Nhìn thấy được, pitch được, 2 domain live, demo hoàn chỉnh.

### Ngày 18 — Domain Mới: Fintech + Domain Switcher UI

**Chứng minh domain-agnostic:** Engine không đổi một dòng. Chỉ thêm tool pack mới.

**A. Tool pack fintech:**
- `src/agent/tools/fintech/get_revenue_breakdown.py` — doanh thu theo channel, so baseline
- `src/agent/tools/fintech/get_transaction_anomaly.py` — tỷ lệ hoàn tiền, thất bại theo merchant
- `src/agent/tools/fintech/get_merchant_status.py` — merchant có bị block/lỗi không
- `src/agent/tools/fintech/get_settlement_lag.py` — độ trễ đối soát so thông thường
- `src/agent/tools/registry_fintech.py` — tool registry fintech domain

**B. Kịch bản fintech:**
- KB-F1: Doanh thu sụt 40% từ 10:00 → nguyên nhân: payment processor X timeout
- KB-F2: Tỷ lệ hoàn tiền tăng 8x → nguyên nhân: merchant Y bug giá sản phẩm
- `data/seed_fintech.py` — synthetic fintech data (transactions, revenue, settlements)

**C. Dashboard: Domain Switcher + Tool Registry Viewer:**
- Domain selector trong navbar: `Microservice Ops` | `Fintech Anomaly`
- Khi switch domain: tool list thay, scenario list thay, trigger form thay
- `GET /dashboard/tools` — **Tool Registry Viewer**:
  - Danh sách tất cả tools (local + MCP) với description, input schema
  - Test tool trực tiếp: nhập args → chạy → xem Observation output
- Trigger fintech từ UI: dropdown domain → scenario KB-F1/KB-F2

**Cổng:** 2 kịch bản fintech đúng, engine code không đổi, domain switch hoạt động trên dashboard.

---

### Ngày 19 — Eval N=10 + Dashboard Polish + Demo Prep

**A. Eval toàn diện:**
- Chạy eval N=10 cho tất cả 6 kịch bản (scenario1-4 + KB-F1 + KB-F2)
- Lưu kết quả vào `eval_results` table
- Dashboard `/dashboard/eval` hiện số liệu thật:
  - Correct rate per scenario + average
  - Steps to correct distribution
  - Token cost per scenario
  - Trend chart so sánh runs

**B. Dashboard Polish:**
- Responsive layout (mobile-friendly cho demo trên điện thoại)
- Loading states, error states cho mọi API call
- Toast notifications khi investigation complete
- Keyboard shortcuts: `Ctrl+K` mở chat, `R` refresh, `T` trigger

**C. Demo Prep:**
- Kiểm tra toàn bộ flow demo 5 phút (script bên dưới)
- Seed data sạch cho demo
- Chạy thử demo 2 lần — ghi lại điểm kẹt
- Sửa điểm kẹt

**Cổng:** 6 kịch bản eval xong + số liệu thật + dashboard hoàn chỉnh + demo chạy smooth.

---

### Ngày 20 — Platform Demo Full + Cổng Phase 4

**Mạch demo 7 phút:**
1. Mở `/dashboard/demo` → giới thiệu platform
2. Chat UI: gõ "Điều tra payment-gateway 14:00-15:00" → stream live → verdict HIGH
3. Mở investigation detail: trace timeline từng bước, hypothesis evolution
4. Langfuse: "đây là trace chi tiết + token cost"
5. Trigger KB2 (provider sập) → multi-agent chạy song song → nhanh hơn
6. MCP hot-plug: thêm tool mới vào MCP server, không restart engine → tool xuất hiện ngay
7. Switch domain fintech → trigger KB-F1 → engine code không đổi
8. Đọc số liệu: "6 kịch bản, N=10, correct rate X%, avg M bước, avg $Y/investigation"

**Chuẩn bị kỹ thuật:**
- Chạy `python data/init_db.py && python data/migrate_projects.py` fresh
- Seed tất cả 6 kịch bản
- Server + MCP server + dashboard đang chạy
- Telegram + Teams mở sẵn trên điện thoại

**Cổng Phase 4 / Kết thúc 20 ngày:**
2 domain live + MCP hot-plug demo + eval numbers thật + full dashboard + Chat UI + multi-agent.

---

## Thứ tự cắt nếu hụt giờ (cắt từ dưới lên)

1. **Investigation Replay (Ngày 17C)** — demo vẫn ổn không có
2. **Multi-agent (Ngày 15B)** — kể bằng lời + kiến trúc đã sẵn sàng; single-agent đã đủ
3. **Live Metrics Widget (Ngày 16C)** — health page không có widget vẫn pass
4. **Fintech domain (Ngày 18)** — 4 kịch bản microservice đã chứng minh đủ
5. **Circuit breaker (Ngày 16A)** — retry + concurrent cap đủ cho demo

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` (trạng thái) + file này (plan)
2. Làm theo ngày hiện tại, kết thúc bằng verify cổng kiểm
3. Cuối session: cập nhật `BUILD_STATE.md` (đã xong gì, cổng nào đã qua)
4. Nguyên tắc không đổi: 4 nguyên tắc kiến trúc trong `CLAUDE.md`, stack nhẹ (không Kafka/Postgres)
