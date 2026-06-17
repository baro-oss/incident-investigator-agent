# DEMO — Kịch bản trình diễn toàn hệ thống

Một mạch chạy xuyên suốt **mọi cạnh** của platform:

> webhook intake (nhiều nền tảng) → engine điều tra adaptive → **MCP telemetry** (logs · metrics · deploy history · service graph · service list) → **GitLab code MCP** (đọc source) → verdict neo bằng chứng code → **push Telegram**.

Backend: **Postgres** (theo `.env`). Source đọc từ group **gitlab.com/baopx-microservices**.

## Câu chuyện

Project **`demo-day`** (e-commerce/thanh toán). Lúc **09:02** ngày **2026-06-16** deploy
`payment-gateway v2.4.0` (code ở repo **mc-app-service**); từ **09:05** spike `TimeoutException`
+ "connection pool exhausted", p99 ~9x baseline. **Root cause neo trong source:** v2.4.0 hạ
`MAX_POOL_SIZE` **50→5** và **xoá retry/except guard** → pool cạn → upstream timeout.

Agent tự đi: `get_error_breakdown` → `get_metrics` → `get_recent_deploys` (v2.4.0 @ 09:02) →
`get_dependencies` → **`get_code_diff(payment-gateway, v2.4.0)` qua GitLab MCP → `code_distill`
phát hiện RISK** (config-knob pool→5 + removed-error-handling) → **Verdict CAO** → Telegram.

---

## 0. `.env` (đã điền sẵn trong session này)

```bash
# LLM mặc định: MiniMax qua GreenNode MaaS (OpenAI-compatible)
LLM_PROVIDER=greennode
LLM_MODEL=minimax/minimax-m2.5
OPENAI_API_KEY=vn-...                      # key GreenNode MaaS
OPENAI_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1

TELEGRAM_BOT_TOKEN=...                    # bot token dùng chung
DB_BACKEND=postgres                       # backend prod
DATABASE_URL=postgresql://...             # Postgres remote
GITLAB_TOKEN=glpat-...                    # đọc source (read_api) + push (write_repository)
GITLAB_NAMESPACE=baopx-microservices
ALLOW_ANON_TRIGGER=true                   # demo: trigger không cần API token
DEMO_CHAT_ID=-1004205633841              # chat Telegram của project demo
```

> Đổi LLM mặc định = đổi `LLM_PROVIDER`/`LLM_MODEL` + `OPENAI_API_KEY`/`OPENAI_BASE_URL`
> (provider không phải anthropic/gemini → đi qua client OpenAI-compatible). MiniMax hỗ trợ
> tool-calling nên engine loop chạy bình thường.

Mapping service → repo (trong [scripts/setup_demo.py](../scripts/setup_demo.py)):
`payment-gateway → mc-app-service` (culprit, có tag v2.3.0/v2.4.0) · `order-service → soundbox`.

---

## 1. Đường nhanh (Makefile)

```bash
make demo-prep      # seed scenario demo (PG) + push source GitLab (2 commit/tag) + provision project
make demo-up        # chạy CÙNG LÚC 3 server: telemetry:9000 · gitlab-code:9002 · main:8080 (Ctrl-C dừng hết)
# terminal khác:
make demo-webhook                 # bắn Prometheus alert
make demo-webhook src=sentry      # hoặc grafana | opsgenie | simple
make demo-down      # dừng cả 3 server
```

`make demo-prep` chạy 3 bước con (chạy lại an toàn — idempotent):
`make demo-seed` · `make demo-gitlab` · `make demo-setup`.

---

## 2. Bắn webhook bằng `curl` (giả lập từng nền tảng)

Tất cả POST tới `/projects/demo-day/trigger` + header `X-Alert-Source`. Server đang chạy port **8080**.

**Prometheus AlertManager:**
```bash
curl -sS -X POST localhost:8080/projects/demo-day/trigger \
  -H 'Content-Type: application/json' -H 'X-Alert-Source: prometheus' \
  -d '{"status":"firing","alerts":[{"labels":{"service":"payment-gateway","scenario":"demo","severity":"critical","alertname":"HighErrorRate"},"annotations":{"summary":"payment-gateway: error rate spiked, TimeoutException dominant, p99 ~9x baseline"},"startsAt":"2026-06-16T09:10:00Z"}]}'
```

**Sentry (issue webhook):**
```bash
curl -sS -X POST localhost:8080/projects/demo-day/trigger \
  -H 'Content-Type: application/json' -H 'X-Alert-Source: sentry' \
  -d '{"action":"created","data":{"issue":{"title":"TimeoutException: connection pool exhausted on payment-gateway","firstSeen":"2026-06-16T09:08:00Z","project":{"slug":"payment-gateway"},"metadata":{"type":"TimeoutException"},"tags":[{"key":"scenario","value":"demo"}]}}}'
```

**Grafana:**
```bash
curl -sS -X POST localhost:8080/projects/demo-day/trigger \
  -H 'Content-Type: application/json' -H 'X-Alert-Source: grafana' \
  -d '{"status":"firing","title":"[FIRING:1] payment-gateway HighLatency","alerts":[{"labels":{"service":"payment-gateway","scenario":"demo","alertname":"HighLatency"},"annotations":{"summary":"payment-gateway: latency p99 lệch nghiêm trọng so với baseline"},"startsAt":"2026-06-16T09:12:00Z"}]}'
```

**OpsGenie** (`createdAt` = epoch-ms của 09:14:00Z):
```bash
curl -sS -X POST localhost:8080/projects/demo-day/trigger \
  -H 'Content-Type: application/json' -H 'X-Alert-Source: opsgenie' \
  -d '{"action":"Create","alert":{"message":"High error rate on payment-gateway","source":"payment-gateway","details":{"service":"payment-gateway","scenario":"demo"},"createdAt":1781601240000}}'
```

**Trigger thủ công** (không có X-Alert-Source — `map_simple_payload`, tham số tường minh):
```bash
curl -sS -X POST localhost:8080/projects/demo-day/trigger \
  -H 'Content-Type: application/json' \
  -d '{"service":"payment-gateway","scenario":"demo","time_window":"09:00-10:00","date":"2026-06-16","symptom":"payment-gateway: TimeoutException tăng đột biến sau deploy"}'
```

> **PagerDuty** (`demo/webhooks/pagerduty.sh`): adapter *suy ra* scenario từ title (chỉ
> scenario1/scenario2) → không mang được `scenario=demo`; script nhắm scenario1 (data seed sẵn)
> để chứng minh routing đa nền tảng. Dùng 5 nền tảng trên cho kịch bản đọc code.

Mỗi curl trả `202 {"status":"accepted",...}`. Engine chạy nền → verdict đẩy Telegram.

---

## 3. Sanity check

```bash
curl -s localhost:8080/health | jq '{status, db_backend, llm_provider}'
curl -s localhost:9000/health | jq '{tools: .exposed_tools}'            # telemetry MCP
curl -s localhost:9002/health | jq '{server, token_set, tools}'        # gitlab code MCP
curl -s localhost:8080/projects/demo-day/services
curl -s localhost:8080/projects/demo-day/mcp-servers | jq '.servers[] | {id, name, url}'
```

## Bản đồ: yêu cầu → tool / nguồn

| Yêu cầu | Hiện thực |
|---|---|
| Webhook giả lập nhiều nền tảng | `curl … X-Alert-Source` → adapter (mục 2) |
| MCP collect **logs** | `get_error_breakdown` (MCP telemetry 9000) |
| **metrics** | `get_metrics` |
| **deployment history** | `get_recent_deploys` |
| **graph node service** | `get_dependencies` (`service_catalog.depends_on`) |
| **danh sách service** | `project_services` → `available_services` |
| MCP **GitLab đọc source** | MCP `gitlab-code` (9002) → `get_diff`/`read_file`/`search_code` → `get_code_diff` + `code_distill` |
| **Push Telegram** | output router → kênh per-project (`DEMO_CHAT_ID`) |

## Verdict kỳ vọng

`payment-gateway v2.4.0` (deploy 09:02) là **root cause**, độ tin **CAO**, neo bằng chứng:
spike TimeoutException ~9x + p99 lệch nghiêm trọng + **diff v2.4.0 hạ pool 50→5 và bỏ retry
guard** (RISK: config-knob + removed-error-handling). Tin Telegram về `DEMO_CHAT_ID`.

---

## Troubleshooting

- **`stop: llm_error`** → key LLM sai/hết hạn/hết credit. Kiểm `OPENAI_API_KEY` (GreenNode) còn
  hiệu lực; hoặc đổi `LLM_MODEL`/provider. Pipeline degrade an toàn — không chết im lặng.
- **`get_code_diff` trả metadata thay vì RISK** → MCP `gitlab-code` chưa chạy/đăng ký, hoặc log
  runner không có `code_mcp=True`. Kiểm `curl localhost:9002/health` (`token_set:true`) + tag
  `v2.4.0` tồn tại trên repo mc-app-service.
- **Tool báo "Không có log/metric"** → seed chưa chạy trên đúng backend. `make demo-seed` (nạp .env → Postgres).
- **Telegram im lặng** → thiếu `TELEGRAM_BOT_TOKEN` (env) hoặc `DEMO_CHAT_ID`; token luôn từ env, per-project chỉ override `chat_id`.
- **Trigger 401** → bật `ALLOW_ANON_TRIGGER=true` (đã set trong .env demo).
