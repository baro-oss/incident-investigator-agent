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
Phase 1 (Ngày 6–10)  : Platform Extension   — webhook, adapter, MCP đầy đủ, 4 kịch bản  ✅ HOÀN TẤT
Phase 2 (Ngày 11–14) : Observability         — Langfuse, CI eval, memory xuyên phiên
Phase 3 (Ngày 15–17) : Architecture Upgrade  — LangGraph, multi-agent, resilience + CLI
Phase 4 (Ngày 18–20) : Product Polish        — Dashboard, domain mới, platform demo
```

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

**Mục tiêu:** Biết agent đúng *vì lý do đúng*, không phải may. Có vòng phản hồi tự động.

### Ngày 11 — Langfuse Integration

**Làm:**
- `pip install langfuse`
- `src/agent/observability/langfuse_tracer.py` — wrapper emit trace event → Langfuse span
- Span hierarchy: `investigation` → `step_{n}` → `tool_call` / `llm_call`
- Token usage tracking từ LLMResponse (thêm field `usage` vào LLMResponse)
- Wrap `_emit_trace()` trong `loop.py` để song song gửi Langfuse

**Không phá vỡ:** trace SQLite vẫn chạy — Langfuse là renderer thêm, không thay thế.

**Cổng:** Langfuse dashboard có trace đẹp từng bước điều tra, thấy latency từng tool call.

---

### Ngày 12 — Eval CI Framework

**Làm:**
- Mở rộng `eval_agent.py`: thêm metrics
  - `recall@1`: root cause đúng ở hypothesis #1 không
  - `steps_to_correct`: đi bao nhiêu bước trước khi có đủ bằng chứng
  - `hallucination_check`: verdict có claim nào không có bằng chứng đỡ không
- `.github/workflows/eval.yml` — chạy eval N=5 khi merge vào main
- Fail CI nếu `correct_rate < 0.7` ở bất kỳ kịch bản nào
- Lưu kết quả eval vào bảng `eval_results` (SQLite) để vẽ trend

**Cổng:** GitHub Actions green + eval trend chart từ SQLite data.

---

### Ngày 13 — Long-term Memory

**Làm:**
- Bảng `investigation_patterns` trong SQLite:
  ```sql
  (service, error_pattern, successful_tool_sequence, root_cause_type, count)
  ```
- Sau mỗi verdict `high` confidence: ghi pattern vào bảng
- Warm-start: nếu service+error_type đã điều tra thành công trước → đề xuất tool đầu tiên trong state (không bắt buộc LLM dùng)
- Baseline tự cập nhật: metric "bình thường" hôm nay → cập nhật `baseline_latency_p99` trong catalog sau 7 ngày không có incident

**Cổng:** 2nd investigation trên cùng service nhanh hơn (warm-start gợi đúng tool bước 1).

---

### Ngày 14 — OpenTelemetry + Cổng Phase 2

**Làm:**
- `pip install opentelemetry-sdk opentelemetry-exporter-otlp`
- Trace từ HTTP request vào webhook → investigation → từng tool call → output
- Export tới Jaeger local (`docker run jaegertracing/all-in-one`) hoặc Grafana Tempo
- Span attributes: `tool.name`, `step.number`, `verdict.confidence`, `llm.tokens`

**Cổng Phase 2:** Langfuse dashboard đẹp + CI eval tự động xanh + OTel trace xem được ở Jaeger.

---

## Phase 3 — Architecture Upgrade (Ngày 15–17)

**Mục tiêu:** Chứng minh kiến trúc scale được — không rewrite, chỉ nâng cấp.

### Ngày 15 — LangGraph Migration

**Tại sao dễ:** `decide_next_action`, `run_tool`, `update_state` đã là hàm pure → wrap thành node, không viết lại.

**Làm:**
- `pip install langgraph`
- `src/agent/engine/graph.py` — StateGraph thay InvestigationEngine class
  ```python
  graph = StateGraph(InvestigationState)
  graph.add_node("decide", decide_next_action)
  graph.add_node("run_tool", run_tool)
  graph.add_node("update", update_state)
  graph.add_conditional_edges("decide", route_fn)  # tool_call | verdict | budget
  ```
- `InvestigationEngine.run()` vẫn là interface — bên trong dùng graph compile
- Parallel tool execution: khi LLM suggest 2 tool độc lập → chạy song song (reduce steps)

**Cổng:** KB1 + KB2 pass qua LangGraph, cùng kết quả, bước có thể ít hơn (parallel).

---

### Ngày 16 — Multi-agent

**Kiến trúc:** Orchestrator phân công → Specialist agents chạy song song → Merge evidence.

```
OrchestratorAgent
├── LogAnalystAgent    (get_error_breakdown, trace_request)
└── MetricAnalystAgent (get_metrics, get_recent_deploys, get_dependencies)
         ↓ merge evidence
     VerdictAgent
```

**Làm:**
- `src/agent/engine/multi_agent.py` — orchestrator + specialist agents
- Mỗi specialist là InvestigationEngine với tool set giới hạn
- Evidence merger: combine Observation từ nhiều agent trước khi gọi VerdictAgent
- Dedup evidence: tránh 2 agent gọi cùng tool

**Demo:** KB2 — 2 agent chạy song song, kết quả trong ít thời gian hơn.

**Cổng:** Multi-agent KB1+KB2 đúng, thời gian ≤ single-agent.

---

### Ngày 17 — Resilience + Interactive CLI

**A. Resilience (nửa ngày):**
- Retry với exponential backoff khi LLM lỗi tạm thời (429, 503)
- Concurrent investigation cap: max N phiên cùng lúc, queue phần còn lại
- Circuit breaker: nếu LLM fail liên tiếp 3 lần → pause 60s → alert Telegram
- Graceful shutdown: SIGTERM → finish phiên đang chạy → push verdict partial

```python
# src/agent/engine/resilience.py
async def with_retry(coro, max_attempts=3, base_delay=2.0): ...
class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int = 3): ...
```

**B. Interactive CLI Mode (nửa ngày) — pull mode:**
- `scripts/chat.py` — REPL nhận câu hỏi tự nhiên → engine điều tra → in kết quả
- Không cần Telegram, không cần webhook — dùng trực tiếp trong terminal

```bash
python scripts/chat.py
> Điều tra payment-gateway từ 14:00 đến 15:00 hôm nay
[agent chạy] → Root cause: Deploy v2.3.1... (HIGH confidence)
> Còn auth-service thì sao?
[agent chạy] → auth-service bình thường trong window đó
```

**Câu chuyện pitch:** "Hai cửa vào, một engine — push khi có alert, pull khi muốn hỏi."

**Cổng Phase 3:** 3 phiên concurrent không conflict + CLI hỏi-đáp hoạt động + retry tự phục hồi.

---

## Phase 4 — Product Polish (Ngày 18–20)

**Mục tiêu:** Nhìn thấy được, pitch được, 2 domain live.

### Ngày 18 — Dashboard UI

**Stack:** FastAPI + Jinja2 (lightweight, không cần Node.js build step).

**Làm:**
- `src/agent/dashboard/` — FastAPI router mount vào server.py
- Trang chủ: danh sách investigations (từ `trace_events` SQLite, group by `investigation_id`)
- Detail page: trace viewer — từng bước với tool, observation rút gọn, hypothesis
- SSE endpoint: stream trace events real-time khi investigation đang chạy (demo wow moment)
- Service registry: list service + baseline + dependency (đọc từ `service_catalog`)

**Cổng:** Mở browser, thấy investigation history, click vào xem trace từng bước.

---

### Ngày 19 — Domain Mới: Fintech Anomaly

**Chứng minh domain-agnostic:** Engine không đổi một dòng. Chỉ thêm tool pack mới.

**Tool pack fintech:**
- `get_revenue_breakdown(time_window)` — doanh thu theo channel, so baseline
- `get_transaction_anomaly(service, time_window)` — tỷ lệ hoàn tiền, thất bại
- `get_merchant_status(merchant_id)` — merchant có bị block/lỗi không
- `get_settlement_lag(time_window)` — độ trễ đối soát so thông thường

**Kịch bản fintech:**
- KB-F1: Doanh thu sụt 40% từ 10:00 → nguyên nhân: payment processor X timeout
- KB-F2: Tỷ lệ hoàn tiền tăng 8x → nguyên nhân: merchant Y có bug giá sản phẩm

**Làm:**
- `data/seed_fintech.py` — synthetic fintech data
- `src/agent/tools/fintech/` — 4 tool mới theo hợp đồng Tool/Observation
- `src/agent/tools/registry_fintech.py` — tool registry cho fintech domain
- Trigger fintech: `python scripts/trigger.py --domain fintech --scenario kb-f1`

**Cổng:** Agent giải đúng 2 kịch bản fintech, engine code không thay đổi.

---

### Ngày 20 — Platform Demo + Cổng Phase 4

**Chuẩn bị:**
- Chạy eval N=10 tất cả kịch bản (4 incident + 2 fintech) — lấy số liệu thật
- Test MCP: add tool mới vào MCP server không restart engine
- Dashboard mở sẵn, Telegram + Slack mở sẵn trên điện thoại

**Mạch demo 5 phút:**
1. `trigger.py --scenario scenario1` → stream trace terminal → Telegram ping → Dashboard trace
2. `trigger.py --scenario scenario2` → đường điều tra khác → Slack ping
3. Cắm tool mới qua MCP live không restart
4. `trigger.py --domain fintech --scenario kb-f1` → same engine, different domain → verdict
5. Mở Langfuse: "đây là trace chi tiết + cost từng run"
6. Đọc số liệu: "6 kịch bản, N=10, correct rate X%, avg M bước"

**Cổng Phase 4:** 2 domain live + MCP hot-plug demo + eval numbers thật + dashboard.

---

## Thứ tự cắt nếu hụt giờ (cắt từ trên xuống)

1. **OTel (Ngày 14)** — Langfuse đã đủ cho observability demo
2. **Multi-agent (Ngày 16)** — thay bằng kể-bằng-lời + kiến trúc đã sẵn sàng
3. **Email adapter (Ngày 10)** — Slack đủ rồi
4. **KB4 traffic surge (Ngày 9)** — 3 kịch bản đã đủ chống hardcode
5. **Dashboard SSE real-time (Ngày 18)** — static page vẫn demo được

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` (trạng thái) + file này (plan)
2. Làm theo ngày hiện tại, kết thúc bằng verify cổng kiểm
3. Cuối session: cập nhật `BUILD_STATE.md` (đã xong gì, cổng nào đã qua)
4. Nguyên tắc không đổi: 4 nguyên tắc kiến trúc trong `CLAUDE.md`, stack nhẹ (không Kafka/Postgres)
