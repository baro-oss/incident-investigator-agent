# Runbook — Deploy Investigation Agent lên GreenNode AgentBase

> Cập nhật lần cuối: Phase 11 (Ngày 60). Platform: GreenNode AgentBase Runtime.

---

## Ràng buộc cứng (đọc trước)

| Ràng buộc | Giá trị | Lý do |
|-----------|---------|-------|
| Port container | **8080** | AgentBase route mọi traffic vào port này — không đổi |
| Platform build | **linux/amd64** | Runtime chạy amd64, build arm64 sẽ crash |
| Health endpoint | `GET /health` → 200 | Platform dùng để đánh dấu ACTIVE |
| Database | **PostgreSQL** (managed external) | Disk container ephemeral — không có PVC/volume |
| Scale | `min=max=1` replica | In-memory queue/dedup/SSE — split-brain nếu >1 |
| Deploy method | `runtime.sh` hoặc `/agentbase-deploy` | KHÔNG dùng kubectl |
| Auto-inject vars | `GREENNODE_CLIENT_ID/SECRET/AGENT_IDENTITY/ENDPOINT_URL` | Platform bơm tự động — KHÔNG set tay |

---

## Chuẩn bị một lần

### 1. Credentials GreenNode

```bash
export GREENNODE_CLIENT_ID="<service-account-client-id>"
export GREENNODE_CLIENT_SECRET="<service-account-secret>"
```

Lấy từ IAM console → Service Accounts → tạo SA với quyền `AgentBase:*` + `CR:push`.

### 2. .env.prod (KHÔNG commit — gitignored)

```bash
cp .env.example .env.prod
# Điền các biến sau (tối thiểu):
#   ANTHROPIC_API_KEY hoặc LLM_PROVIDER+OPENAI_API_KEY+OPENAI_BASE_URL
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
#   DB_BACKEND=postgres
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname
#   APP_ENV=production
#   SESSION_SECRET_KEY=<random 32 bytes hex>
#   SECRET_KEY=<random 32 bytes base64>
#   PORT=8080
```

Tạo secret keys:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"    # SESSION_SECRET_KEY
python3 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"  # SECRET_KEY
```

### 3. PostgreSQL managed

Tạo PostgreSQL instance trên GreenNode (hoặc dùng external managed PG). Lấy connection string dạng:
```
postgresql://agent:<password>@<host>:5432/investigation
```

Init schema + seed một lần:
```bash
DB_BACKEND=postgres DATABASE_URL="postgresql://..." python data/init_db.py
DB_BACKEND=postgres DATABASE_URL="postgresql://..." python data/seed_scenario1.py
DB_BACKEND=postgres DATABASE_URL="postgresql://..." python data/seed_scenario2.py
# (thêm seed_scenario3.py / seed_scenario4.py tùy nhu cầu)
```

---

## Deploy lần đầu

### Bước 1 — Build image amd64

```bash
# Quan trọng: --platform linux/amd64 BẮT BUỘC (kể cả trên Apple Silicon)
docker build --platform linux/amd64 \
  -t vcr.vngcloud.vn/<namespace>/investigation-agent:v1.0.0 \
  .
```

### Bước 2 — Đăng nhập Container Registry

```bash
# Dùng agentbase-deploy skill:
/agentbase-deploy cr login

# Hoặc thủ công (lấy token từ IAM):
docker login vcr.vngcloud.vn -u <iam-token> -p <iam-token>
```

### Bước 3 — Push image

```bash
docker push vcr.vngcloud.vn/<namespace>/investigation-agent:v1.0.0
# Optionally tag latest:
docker tag vcr.vngcloud.vn/<namespace>/investigation-agent:v1.0.0 \
           vcr.vngcloud.vn/<namespace>/investigation-agent:latest
docker push vcr.vngcloud.vn/<namespace>/investigation-agent:latest
```

### Bước 4 — Tạo runtime

```bash
# Dùng agentbase-deploy skill (khuyến nghị):
/agentbase-deploy deploy \
  --name investigation-agent \
  --image vcr.vngcloud.vn/<namespace>/investigation-agent:latest \
  --env-file .env.prod \
  --min-replicas 1 --max-replicas 1 \
  --flavor <flavor-id>      # lấy: /agentbase-deploy flavors

# Hoặc runtime.sh:
runtime.sh create \
  --name investigation-agent \
  --from-cr vcr.vngcloud.vn/<namespace>/investigation-agent:latest \
  --env-file .env.prod \
  --min-replicas 1 --max-replicas 1
```

### Bước 5 — Poll ACTIVE + smoke test

```bash
# Đợi runtime ACTIVE (thường 30-90s)
/agentbase-monitor runtime-logs investigation-agent

# Endpoint được tạo tự động (DEFAULT endpoint)
ENDPOINT="https://<runtime-endpoint>"

# Liveness
curl "$ENDPOINT/health"
# → {"status":"ok","db_backend":"postgres","llm_key_set":true,...}

# Readiness (ping DB)
curl "$ENDPOINT/health/ready"
# → {"status":"ready","backend":"postgres","db":"ok"}

# Trigger smoke (cần X-API-Token — tạo qua dashboard)
curl -X POST "$ENDPOINT/trigger" \
  -H "X-API-Token: <token>" \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-gateway","scenario":"scenario1","time_window":"14:00-15:00"}'
# → 202 Accepted + investigation_id

# Kiểm tra trace/verdict trên dashboard:
open "$ENDPOINT/dashboard"
```

---

## Update (deploy version mới)

```bash
# 1. Build + push image mới
docker build --platform linux/amd64 \
  -t vcr.vngcloud.vn/<namespace>/investigation-agent:v1.1.0 .
docker push vcr.vngcloud.vn/<namespace>/investigation-agent:v1.1.0

# 2. Update runtime (tạo version mới, DEFAULT auto-track)
runtime.sh update investigation-agent \
  --image vcr.vngcloud.vn/<namespace>/investigation-agent:v1.1.0

# 3. Verify
curl "$ENDPOINT/health"
```

> **Lưu ý:** Mỗi `update` tạo **version mới = pod mới** → disk container reset. PostgreSQL giữ data bền vững qua update.

---

## Rollback

```bash
# Liệt kê versions
runtime.sh versions investigation-agent

# Rollback về version cũ
runtime.sh rollback investigation-agent --version <version-id>
```

---

## Monitor

```bash
# Logs live
/agentbase-monitor runtime-logs investigation-agent

# Metrics CPU/RAM
/agentbase-monitor metrics investigation-agent

# Dashboard
open "$ENDPOINT/dashboard"
```

---

## Môi trường local với đầy đủ stack (pre-deploy test)

```bash
# Build image local
docker build --platform linux/amd64 -t investigation-agent:local .

# Start full stack (app + postgres)
AGENT_IMAGE=investigation-agent:local \
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Init DB
docker compose -f docker-compose.prod.yml exec agent \
  sh -c 'DB_BACKEND=postgres python data/init_db.py && \
         DB_BACKEND=postgres python data/seed_scenario1.py'

# Test
curl http://localhost:8080/health
curl http://localhost:8080/health/ready

# Dừng
docker compose -f docker-compose.prod.yml down
```

---

## Biến môi trường quan trọng

| Biến | Mô tả | Bắt buộc prod |
|------|-------|:---:|
| `PORT` | Port server (phải là 8080) | ✅ |
| `APP_ENV` | `production` → fail-fast nếu thiếu secrets | ✅ |
| `DB_BACKEND` | `postgres` | ✅ |
| `DATABASE_URL` | PG connection string | ✅ |
| `ANTHROPIC_API_KEY` | Hoặc OpenAI-compat key | ✅ |
| `TELEGRAM_BOT_TOKEN` | Output Telegram | nếu dùng Telegram |
| `SESSION_SECRET_KEY` | Ký session cookie | ✅ |
| `SECRET_KEY` | Mã hóa at-rest (LLM config) | ✅ |
| `LOG_FORMAT` | `json` cho log aggregator | Khuyến nghị |
| `TRACE_RETENTION_DAYS` | Giữ trace bao nhiêu ngày (default 30) | - |
| `GREENNODE_*` | **Auto-inject bởi platform** — KHÔNG set | ❌ |

---

## Troubleshoot

| Triệu chứng | Nguyên nhân thường gặp | Fix |
|-------------|------------------------|-----|
| Runtime không ACTIVE | `/health` chưa trả 200 | Xem logs; kiểm tra DB connection |
| `503 Not ready` từ `/health/ready` | DB không kết nối được | Kiểm tra `DATABASE_URL`, PG whitelist IP |
| `RuntimeError: [PROD] Từ chối khởi động` | `SESSION_SECRET_KEY` hoặc `SECRET_KEY` chưa set | Điền trong `.env.prod` |
| Traffic không vào | Port != 8080 | Kiểm tra `PORT=8080` trong `.env.prod` + image |
| OOMKilled | Flavor quá nhỏ | Tăng flavor: `/agentbase-deploy flavors` → resize |
| Data mất sau deploy | SQLite trên disk container | Chuyển sang `DB_BACKEND=postgres` + managed PG |
