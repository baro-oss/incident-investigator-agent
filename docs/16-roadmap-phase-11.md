# 16 — Roadmap Phase 11 (Ngày 56–60): Postgres Tier-2 + Deploy lên GreenNode AgentBase

> Tiếp nối sau **Phase 10 ✅ (55/55 ngày, 444/444 tests, CI xanh, Python 3.14)**. File này là kế hoạch Phase 11.
> Mục tiêu: đưa agent **lên cloud chạy dạng container trên GreenNode AgentBase Runtime**, với **Postgres làm runtime DB** (qua storage seam đã có từ Phase 5), single-instance, deploy fresh (init+seed trên PG).
> Plan trước: `docs/10` (P1–4) · `docs/11` (P5) · `docs/12` (P6) · Phase 7 inline `BUILD_STATE.md` · `docs/13` (P8) · `docs/14` (P9) · `docs/15` (P10). File này tiếp nối.
> **Nền tảng deploy = GreenNode AgentBase** (skills tham chiếu: `greennode-agentbase-skills/`). Các ràng buộc cứng của nền tảng được mô tả ở section "Ràng buộc nền tảng AgentBase" bên dưới — chúng định hình port, Dockerfile, deploy artifact và lý do **bắt buộc** Postgres.

---

## Định hướng phase này

**Ship lên production.** Hai mục tiêu gắn nhau: (1) đổi runtime DB **SQLite → Postgres** qua seam có sẵn; (2) đóng gói container chạy được trên **GreenNode AgentBase** (port 8080 + amd64 + deploy qua CR/`runtime.sh`), hardening config + lifecycle + observability cho prod. Phase này hấp thụ luôn 2 bug correctness multi-tenant phát hiện ở session review (B1/B2) + nợ trace retention.

**Đây KHÔNG phải "thêm tính năng"** — nó là chuyển hệ thống từ "chạy dev trên máy" sang "chạy prod trong container trên cloud", với DB managed bền vững thay file SQLite cục bộ.

---

## ⚠️ Thay đổi kiến trúc có chủ đích (người dùng đã ra lệnh — 2026-06-15)

CLAUDE.md ghi rule: *"KHÔNG chạy Postgres ở runtime → giữ SQLite WAL ... migration thật = Tier-2, **cần lệnh rõ**."* **Người dùng đã ra lệnh đó.** Phase 11 chính thức **kích hoạt Tier-2 Postgres**:

- ✅ Postgres trở thành **backend runtime prod** (qua `DB_BACKEND=postgres` + `DATABASE_URL`).
- ✅ SQLite **vẫn giữ** làm default dev/test (qua cùng seam) — KHÔNG bỏ. CI test cả 2 backend.
- ✅ **Single-instance** — đây là lý do KHÔNG đụng queue/dedup/SSE/rate-limiter (vẫn in-memory). Postgres thuần là lớp persistence.
- ✅ **Deploy fresh** — chỉ init schema + seed kịch bản trên PG; KHÔNG migrate dữ liệu SQLite cũ.
- ✅ `docker-compose` chạy Postgres **local** là artifact để dev/test trước khi đẩy cloud.

---

## Ràng buộc nền tảng AgentBase (đọc kỹ — định hình toàn bộ container)

Đọc từ `greennode-agentbase-skills/` (runtime contract + deploy ops). AgentBase Runtime là **serverless-style container** (K8s/Knative + autoscaling). Đây là sự thật nền tảng, KHÔNG phải lựa chọn của ta:

### 1. Hợp đồng container CỨNG (platform chỉ enforce 2 thứ)
- **Port `8080`** — platform route **mọi** traffic vào đây. Hệ thống hiện chạy `8000` (`scripts/start_server.py`) → **BẮT BUỘC đổi sang 8080**.
- **`GET /health` → HTTP 200** khi sẵn sàng → để đánh dấu runtime `ACTIVE`. (Đã có `/health`; Phase 11 tách thêm `/health/ready` cho readiness.)
- Ngoài 2 cái trên, route/payload tùy ta. Ta KHÔNG dùng AgentBase SDK (`POST /invocations` chỉ là convention của SDK) → giữ nguyên FastAPI hiện có, chỉ đổi port.

### 2. Disk EPHEMERAL → đây là lý do Postgres BẮT BUỘC (không phải tùy chọn)
- API `create`/`update` runtime (xem `runtime-ops.md`) liệt kê đầy đủ field: `name`, `imageUrl`, `command`, `args`, `environmentVariables`, `flavorId`, `autoscaling`, `networkConfig`. **KHÔNG có field volume / PVC / mount nào.**
- Mỗi `update` = **version mới = pod mới**; autoscaling spin pod; crash → pod mới. ⇒ **SQLite file trên disk container bị xóa sạch mỗi lần redeploy/restart/scale/crash.**
- ⇒ Trên AgentBase **không có cách giữ SQLite bền vững** (không PVC). State bền **chỉ có thể** nằm ở **external managed Postgres** (qua `DATABASE_URL`). Điều này **chốt** quyết định Tier-2: Postgres là điều kiện để có state, không phải nâng cấp "đẹp để có". (Platform Memory Service chỉ cho conversation/semantic memory — sai mục đích cho `logs/metrics/deploys/trace_events/projects`.)

### 3. Cơ chế deploy = build image → managed CR → `runtime.sh` (KHÔNG phải `kubectl`)
- **Build `linux/amd64`** — AgentBase Runtime chạy amd64. Máy dev (Apple Silicon arm64) **phải** `docker build --platform linux/amd64`.
- **Container Registry managed** `vcr.vngcloud.vn` (mỗi user 1 repo + 1 cặp credential, fetch qua IAM token). Không cần Docker Hub/GHCR.
- Deploy qua skill `agentbase-deploy` → `runtime.sh create/update` (tạo version + `DEFAULT` endpoint auto-track). ⇒ **`deploy/k8s/` skeleton phần lớn thành thừa** — D60 chuyển trọng tâm sang artifact + runbook cho luồng AgentBase.

### 4. Env injection + biến auto-inject (KHÔNG set tay)
- Config bơm vào container lúc runtime qua `--env-file` (chính là cơ chế cho `DATABASE_URL`, LLM keys, `OUTPUT_CHANNELS`...). Khớp với 12-factor + secrets fail-fast (D58).
- **4 biến platform tự bơm — `.env.example` TUYỆT ĐỐI không set tay** (gây xung đột / override giá trị platform):
  `GREENNODE_CLIENT_ID` · `GREENNODE_CLIENT_SECRET` · `GREENNODE_AGENT_IDENTITY` · `GREENNODE_ENDPOINT_URL`.

### 5. Single-instance ánh xạ thẳng vào autoscaling `min=max=1`
- Quyết định single-instance giờ có **lý do kỹ thuật cứng**: nếu `maxReplicas>1`, sẽ có ≥2 pod cùng giữ dedup/queue/SSE/rate-limiter **in-memory riêng rẽ** → split-brain. ⇒ Phase 11 deploy `--min-replicas 1 --max-replicas 1`. Bật autoscale chỉ khi externalize state (Future).

### 6. (Tùy chọn, synergy) LLM qua GreenNode MaaS
- AgentBase có **GreenNode AI Platform (MaaS)** — endpoint **OpenAI-compatible**. Factory `llm/openai_compat.py` của ta cắm thẳng qua `LLM_BASE_URL` + key. Không bắt buộc, nhưng là tuyến LLM "in-platform" khuyến nghị. Anthropic API vẫn dùng được như cũ.

---

## Ràng buộc cố định (không đổi)

- ❌ KHÔNG Kafka / message broker → queue vẫn **in-process asyncio**.
- ❌ KHÔNG multi-replica trong Phase 11 → **single-instance** (= AgentBase `min=max=1 replica`). Externalize queue/dedup/SSE (Redis) + horizontal scale **vẫn Future**.
- ❌ KHÔNG bỏ SQLite — seam giữ **cả hai** backend.
- ✅ **Port container = `8080`** (HARD, platform enforce) · build **`linux/amd64`** (HARD, runtime chạy amd64).
- ✅ **READ-ONLY giữ nguyên** · **4 nguyên tắc giữ nguyên** (DB swap nằm DƯỚI seam — engine/tools/dashboard/intake KHÔNG đổi).
- ⚠️ **Lõi không được vỡ:** mỗi ngày phải qua **regression gate** = 444 tests + eval 4/4 mock + 2 KB E2E + push Telegram. **Từ Ngày 57: tests phải xanh trên CẢ `sqlite` lẫn `postgres`.**

### Tuân thủ 4 nguyên tắc + READ-ONLY (kiểm trước)

| Nguyên tắc | Phase 11 |
|-----------|----------|
| #1 LLM không thấy raw data | ✅ Không đụng tool/Observation — chỉ đổi backend lưu trữ phía dưới |
| #2 Một seam, engine domain-agnostic | ✅ DB swap nằm dưới `storage/db.py` seam; engine/tools không biết "Postgres" là gì. **Đóng rò seam:** `auth/rbac.py` đang `import sqlite3` trực tiếp → sửa về `open_db()` |
| #3 Lõi deterministic | ✅ Không đụng engine logic |
| #4 Async từ biên, một nguồn structured | ✅ Không đổi |
| **READ-ONLY (fintech)** | ✅ Không thêm tool ghi; DB write chỉ là persistence nội bộ (logs/trace/metadata) như trước |

> **Điểm canh gác:** DB migration tuyệt đối **không được rò lên engine/tools**. Sau migration, `grep -rn "import sqlite3" src/agent` chỉ còn đúng `sqlite_backend.py`. Mọi caller dùng `open_db()` + `IntegrityError` trung lập từ seam.

---

## Điểm yếu / cơ hội đã xác nhận trong code (cơ sở Phase 11)

| # | Quan sát | Vị trí | Hệ quả |
|---|----------|--------|--------|
| **DB1** | `postgres_backend.connect()` mới là **stub** (`raise NotImplementedError`). Seam chọn được backend nhưng PG chưa hiện thực. | `storage/postgres_backend.py` | Phải viết connection shim thật (psycopg) đúng surface `base.py`. |
| **DB2** | Seam chỉ bọc **connection**, không bọc **SQL dialect**: `?` placeholder (29 dòng), `INSERT OR IGNORE/REPLACE`, `datetime()/julianday()`, `AUTOINCREMENT`. | rải rác `src/`, `data/schema.sql` | PG cần dịch dialect; đây là phần dễ sót. |
| **DB3** | **Rò seam:** `auth/rbac.py` `import sqlite3` trực tiếp, bypass dispatcher. | `auth/rbac.py` | Vi phạm Nguyên tắc #2; PG sẽ vỡ ở RBAC. |
| **DB4** | `open_db()` gọi **rất nhiều** (25 call site; mỗi `_emit_trace` mở+đóng 1 connection/bước). Với SQLite (file cục bộ) là rẻ; với PG = **TCP+auth handshake mỗi query** → churn nặng. | `storage/db.py` + caller | PG **cần connection pool** ở backend, nếu không perf rất tệ. |
| **OPS2** | `trace_events` **phình vô hạn** — A3 (Phase 6) có retention config nhưng chưa có cleanup job enforce. | `trace_events` | DB lớn dần; prod cần cleanup theo TTL. |
| **B1** | `_make_error_state` **mất `project_id`** → timeout/error route sai kênh project. | `intake/runner.py:98` | Bug multi-tenant ở nhánh lỗi. |
| **B2** | 2 `_emit_trace` (`tool_call`/`tool_result`) trong `_run_loop` **thiếu `project_id`** (graph.py đã đúng). | `engine/loop.py:1069,1090` | Trace bước tool ghi sai project → parity loop↔graph lệch. |
| **CFG1** | Secrets ở prod mới chỉ **startup warning** (SESSION_SECRET_KEY/SECRET_KEY); Dockerfile chưa non-root/healthcheck. | `intake/server.py` · `Dockerfile` | Cần fail-fast + container hardening cho prod. |
| **PLAT1** | Server bind port **`8000`**; AgentBase route mọi traffic vào **`8080`**. | `scripts/start_server.py` · `Dockerfile` · health tests | Container không nhận traffic / không lên `ACTIVE` nếu sai port. **HARD fix ở D58.** |
| **PLAT2** | Disk container **ephemeral** (AgentBase không có volume/PVC) → SQLite cục bộ mất mỗi deploy/restart/scale. | nền tảng | Củng cố: Postgres là **bắt buộc**, không phải tùy chọn. (Đã xử lý qua D56–D57.) |

**Đòn bẩy:** seam đã có (`db.py` dispatcher + `base.py` hợp đồng + `sqlite_backend` mẫu + `postgres_backend` stub ghi sẵn scope). Phần lớn việc = hiện thực 1 backend + dịch dialect + container/config.

---

## Tổng quan Phase 11

```
Day 56  PG backend     Connection shim (psycopg + pool) + schema_postgres + init/seed + docker-compose local
Day 57  Dialect parity Dịch dialect (placeholder/upsert/datetime) + đóng rò seam rbac.py + CI matrix sqlite|postgres
Day 58  Container      Port 8080 + Dockerfile prod (non-root/healthcheck/amd64) + secrets fail-fast + /health/ready + B1
Day 59  Lifecycle/Obs  SIGTERM drain + JSON log + /health sâu + trace retention + B2 fix
Day 60  Deploy+Close   AgentBase deploy (CR + runtime.sh) + docker-compose.prod + runbook/docs + E2E smoke + Cổng P11
```

| Ngày | Theme | Trọng | Trạng thái |
|------|-------|:----:|-----------|
| 56 | PG backend adapter + local dev infra | **L** | ✅ |
| 57 | Dialect parity + đóng rò seam + CI matrix | **L** | ✅ |
| 58 | Container & config hardening + port 8080 + B1 | M | ✅ |
| 59 | Lifecycle + observability + retention + B2 | M | ✅ |
| 60 | Deploy lên AgentBase + smoke + Cổng Phase 11 | M | ✅ |

**Phụ thuộc cứng:** D56 (backend) → D57 (dialect cần backend chạy) → D58 (container chạy PG cần parity) → D59 → D60.
**Xương sống (KHÔNG cắt):** D56 + D57 (PG parity + 444 tests xanh trên PG) · D58 (**port 8080** + container + secrets + B1) · B2 (D59).

---

## Ngày 56 — PG backend adapter + local dev infra *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** `DB_BACKEND=postgres` chạy thật — `open_db()` trả connection PG đúng hợp đồng `base.py`, có pool; schema + seed dựng được trên PG; dev có docker-compose để bật PG local.

### A. Connection shim + pool *(must-land)*
- Thay stub `postgres_backend.py` bằng adapter thật, đúng surface (`name`, `IntegrityError`, `db_path()`, `connect()`):
  - `connect()` trả **wrapper** quanh psycopg connection cung cấp đúng API mà 25 caller đang dùng (xem `base.py`): `.execute(sql, params=())` (tự mở cursor + dịch `?`→`%s`), row truy cập **cả key lẫn index** + `dict(row)` (psycopg `dict_row`/row factory), `.commit()`, `.close()`, `cursor.fetchone/fetchall`, `lastrowid` (PG không có → shim qua `RETURNING id`), `rowcount`.
  - `IntegrityError = psycopg.errors.IntegrityError`; `db_path()` đọc `DATABASE_URL`.
- **Connection pool** (DB4): `psycopg_pool.ConnectionPool` module-level; `connect()` lấy từ pool, `close()` trả về pool. Giữ `open_db()` không đổi → caller không vỡ.
- Driver qua extra `[postgres]` trong `pyproject.toml`: `psycopg[binary]`, `psycopg_pool`.

### B. Schema + init + seed trên PG *(must-land)*
- `data/schema_postgres.sql`: dịch DDL — `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY` (hoặc `GENERATED ALWAYS AS IDENTITY`); bỏ PRAGMA WAL/foreign_keys; map type (TEXT/REAL/INTEGER/BOOLEAN); giữ UNIQUE/FK/index.
- `data/init_db.py` **backend-aware**: chọn `schema.sql` (sqlite) hoặc `schema_postgres.sql` (postgres) theo `DB_BACKEND`.
- `seed_scenario1/2.py` + `migrate_*.py` chạy được trên PG (deploy fresh = init + seed).

### C. Local dev infra *(must-land)*
- `docker-compose.yml`: service `postgres` (image `postgres:16-alpine`, named volume, env `POSTGRES_DB/USER/PASSWORD`, healthcheck `pg_isready`). Dev: `docker compose up -d postgres` + `DB_BACKEND=postgres DATABASE_URL=...`.
- `.env.example`: thêm `DB_BACKEND`, `DATABASE_URL` (comment hướng dẫn local vs cloud).

**Cổng Ngày 56:**
- `docker compose up -d postgres` OK; `DB_BACKEND=postgres python data/init_db.py` + seed → schema + dữ liệu kịch bản trong PG ✅
- `open_db()` round-trip insert/select ≥1 bảng trên PG; pool hoạt động (không churn connection mỗi query) ✅
- SQLite path KHÔNG đổi (`DB_BACKEND` unset → sqlite; 444 tests xanh như cũ) ✅

**KHÔNG làm ở D56:** dịch hết dialect call-site (D57); container (D58).

---

## Ngày 57 — Dialect parity + đóng rò seam + CI matrix *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** toàn bộ truy vấn chạy đúng trên PG; engine/tools không rò backend; CI bảo vệ cả 2 backend.

### A. Dialect parity *(must-land)*
- `INSERT OR IGNORE` → `ON CONFLICT (...) DO NOTHING`; `INSERT OR REPLACE` → `ON CONFLICT (...) DO UPDATE` (seam-neutral — cả 2 backend hiểu).
- `datetime()/julianday()/strftime()` (3 chỗ): tính trong Python (truyền ISO string vào query) hoặc nhánh theo backend.
- Quét 29 dòng execute dùng `?` — adapter PG đã dịch `?`→`%s`; kiểm không có `?` literal trong SQL gây dịch sai.

### B. Đóng rò seam (Nguyên tắc #2) *(must-land)*
- `auth/rbac.py`: bỏ `import sqlite3`; dùng `open_db()` + `IntegrityError` từ `agent.storage.db`.
- `data/migrate_*.py`: bắt exception **trung lập** (vd `OperationalError/ProgrammingError` re-export từ seam) thay vì `sqlite3.OperationalError` trực tiếp → idempotent trên cả 2 backend.

### C. CI matrix *(must-land)*
- `.github/workflows/ci.yml`: matrix `DB_BACKEND: [sqlite, postgres]`. Job postgres dùng `services: postgres:16` (GitHub Actions service container) → init + seed + pytest + eval gate trên PG.

**Cổng Ngày 57:**
- **444/444 tests xanh trên CẢ `sqlite` lẫn `postgres`** ✅
- 2 KB E2E + push Telegram + eval 4/4 trên PG ✅
- `grep -rn "import sqlite3" src/agent` → **chỉ còn `sqlite_backend.py`** ✅
- Nguyên tắc #2 giữ: engine/tools/dashboard không tham chiếu backend ✅

---

## Ngày 58 — Container & config hardening + port 8080 + B1 *(cỡ M)*

**Mục tiêu:** container prod khớp hợp đồng AgentBase — port 8080, non-root, healthcheck, config 12-factor, secrets fail-fast.

### A. Port 8080 (HARD — hợp đồng AgentBase) *(must-land)*
- `scripts/start_server.py`: bind **`8080`** (đọc từ `PORT` env, default `8080`). AgentBase route mọi traffic vào 8080.
- Cập nhật mọi nơi giả định `8000`: Dockerfile `EXPOSE 8080` + `HEALTHCHECK`, docker-compose, health smoke tests, docs Khởi động nhanh. (MCP demo server port 9000 giữ nguyên — không deploy lên AgentBase.)

### B. Dockerfile prod *(must-land)*
- Multi-stage (build deps → slim runtime), **non-root user**, build/target **`linux/amd64`**, `EXPOSE 8080`, `HEALTHCHECK` gọi `/health/ready`, cài `.[postgres]`; entrypoint chạy `init_db`/`migrate` idempotent rồi `uvicorn` bind `0.0.0.0:8080`.
- `.dockerignore` loại `.env`, `.greennode.json`, registry creds, `data/*.db`, `.venv`, `.git` (AgentBase deploy skill cũng cảnh báo điểm này).

### C. 12-factor + secrets fail-fast *(must-land)*
- Config qua env (AgentBase bơm qua `--env-file` lúc runtime): `DB_BACKEND`, `DATABASE_URL`, `OUTPUT_CHANNELS`, LLM keys (`LLM_BASE_URL`/`LLM_API_KEY` nếu dùng MaaS)...
- **Fail-fast:** nếu `APP_ENV=production` mà thiếu `SESSION_SECRET_KEY`/`SECRET_KEY` → **refuse start** (hiện chỉ warning). Dev giữ fallback.
- `.env.example` đủ biến **và** ghi chú rõ **4 biến AgentBase auto-inject KHÔNG set tay** (`GREENNODE_CLIENT_ID/CLIENT_SECRET/AGENT_IDENTITY/ENDPOINT_URL`).

### D. Health probes *(must-land)*
- `/health/ready` (readiness: ping DB + trả `backend_name`) **tách khỏi** `/health` (liveness: không chạm DB, chỉ xác nhận process sống). AgentBase đánh dấu `ACTIVE` qua `/health`; cloud/k8s dùng `/health/ready` cho readiness.

### E. B1 fix *(must-land)*
- `intake/runner.py:_make_error_state` truyền `project_id` (+ `available_services`) → error/timeout route đúng kênh project.

**Cổng Ngày 58:**
- App bind **8080**; `docker build --platform linux/amd64` OK; `docker compose up` (app + postgres) → trigger investigation E2E local trên port 8080 OK ✅
- `/health/ready` trả DB ok + `backend=postgres`; `/health` sống kể cả DB chậm ✅
- `APP_ENV=production` thiếu secret → fail-fast (test) ✅
- B1: error state giữ `project_id` (test) ✅

---

## Ngày 59 — Lifecycle + observability + retention + B2 *(cỡ M)*

**Mục tiêu:** an toàn dưới vòng đời container (SIGTERM), quan sát được, DB không phình.

### A. Graceful lifecycle *(must-land)*
- SIGTERM: drain investigation **in-flight** (A1 đã có → verify + đảm bảo background task hoàn tất hoặc push verdict "timeout/shutdown" trước khi exit, không chết im lặng).
- Ghi rõ **semantics queue in-process khi restart**: single-instance → job đang chờ trong queue mất khi pod bị thay (at-most-once). Tài liệu hoá + (tùy chọn nhẹ) log queue depth lúc shutdown.

### B. Observability *(must-land)*
- JSON logging opt-in (`LOG_FORMAT=json`) cho log aggregator cloud.
- `/health` (hoặc `/health/deep`) mở rộng: DB ping + backend + số MCP server reachable + LLM key presence.

### C. Trace retention (OPS2) *(must-land)*
- `trace_events` cleanup theo `TRACE_RETENTION_DAYS` (env): chạy lúc startup + (tùy chọn) qua scheduler có sẵn. Degrade an toàn nếu env không set (mặc định giữ lâu).

### D. B2 fix *(must-land)*
- `engine/loop.py:1069,1090`: 2 `_emit_trace` (`tool_call`/`tool_result`) thêm `project_id=state.project_id` → **parity với `graph.py`** (đã đúng).
- Đo lại `open_db()` call count / investigation → xác nhận pool D56 không churn (perf re-check sau khi đổi PG).

**Cổng Ngày 59:**
- SIGTERM drain: investigation in-flight không mất verdict (test/sim) ✅
- `/health` sâu + JSON log hoạt động ✅
- Retention xóa trace cũ đúng TTL; không set env → degrade an toàn ✅
- B2: trace `tool_call`/`tool_result` mang đúng `project_id` (test); parity loop↔graph ✅

---

## Ngày 60 — Deploy lên AgentBase + smoke + Cổng Phase 11 *(cỡ M)*

**Mục tiêu:** image deploy được lên AgentBase (hoặc full stack local qua compose), smoke E2E, đóng pha.

### A. Deploy artifacts *(must-land = compose + runbook AgentBase; k8s skeleton là Future)*
- `docker-compose.prod.yml`: app + postgres + volume + healthcheck + `depends_on` — chạy full stack local/staging để chứng minh trước khi đẩy cloud.
- **Runbook AgentBase** (luồng deploy thật, dùng skill `agentbase-deploy`):
  1. `docker build --platform linux/amd64 -t <runtime>:<tag> .`
  2. Login + push lên managed CR (`vcr.vngcloud.vn`) qua `cr.sh credentials docker-login` → `docker push`.
  3. `runtime.sh create --name <runtime> --image <cr>/<runtime>:<tag> --flavor 1x1-general --env-file .env.production --from-cr --min-replicas 1 --max-replicas 1` (single-instance).
  4. Poll `ACTIVE` → lấy `DEFAULT` endpoint URL → `curl <url>/health` = 200.
  - Managed Postgres tham chiếu qua `DATABASE_URL` trong env-file (PG nằm ngoài AgentBase: managed PG / VPC).
- `deploy/k8s/` skeleton: **HẠ xuống Future** (deploy thật qua `runtime.sh`, không `kubectl`). Chỉ ghi 1 đoạn note trong runbook nếu cần k8s tự quản về sau.

### B. Docs *(must-land)*
- `docs/16` (file này) ☐→✅. `README.md` + `docs/api.md`: section **Deploy lên AgentBase** — port 8080, build amd64, CR + `runtime.sh`, env PG/secrets, `--min/max-replicas 1`, 4 biến auto-inject không set tay, health probes, ghi chú READ-ONLY + single-instance.

### C. Smoke + audit *(must-land)*
- **E2E smoke:** `DB_BACKEND=postgres` trên container (compose local hoặc endpoint AgentBase nếu đẩy được), trigger → điều tra → push Telegram; `<endpoint>/health` = 200.
- Audit: READ-ONLY giữ · 4 nguyên tắc giữ (DB swap dưới seam) · degrade an toàn (DB down → `/health/ready` đỏ, app KHÔNG crash-loop; intake trả 503 thay vì 500) · port 8080 + amd64 đúng hợp đồng AgentBase.
- Cập nhật `BUILD_STATE.md` + bảng Phase trong `CLAUDE.md` → Phase 11 ✅.

**Cổng Phase 11 (bắt buộc):**
- **DB:** Postgres backend live; 444 tests xanh trên **cả** sqlite + postgres (CI matrix) ✅
- **Seam:** rò `import sqlite3` đóng (chỉ còn `sqlite_backend.py`); dialect parity (placeholder/upsert/datetime) ✅
- **Container:** bind port **8080** + build **amd64**; non-root + healthcheck; secrets fail-fast ở prod; readiness=DB ping tách liveness ✅
- **AgentBase:** image push CR + `runtime.sh create` lên `ACTIVE` (hoặc runbook đầy đủ + compose smoke nếu chưa có credential cloud); single-instance `min=max=1` ✅
- **Lifecycle:** SIGTERM drain; trace retention enforce ✅
- **Bug fix:** B1 (project_id ở error state) + B2 (project_id ở trace tool) ✅
- **Smoke:** 2 KB E2E + Telegram + eval 4/4 trên PG **trong container** ✅
- **Bất biến:** READ-ONLY + 4 nguyên tắc giữ; single-instance (không externalize state) ✅

---

## Thứ tự cắt nếu hụt giờ (từ dưới lên)

1. **D60 deploy AgentBase thật** — nếu chưa có IAM credential cloud, giữ **runbook đầy đủ + compose.prod smoke** là đủ chứng minh; push lên AgentBase sau.
2. **D59 JSON logging** — log text vẫn dùng được; format JSON sau.
3. **D59 retention qua scheduler** — giữ script + chạy lúc startup; scheduler sau.

> **KHÔNG cắt:** D56 + D57 (PG parity + 444 tests xanh trên PG + đóng rò seam) · D58 (**port 8080** + container + secrets fail-fast + B1) · D59 B2 fix. Đây là xương sống Phase 11. Port 8080/amd64 là hợp đồng cứng — không cắt.

---

## Future / sau Phase 11 (chưa lên lịch)

- **Multi-replica / horizontal scale** — externalize queue/dedup/SSE/rate-limiter (Redis); hoàn thiện Redis SSE seam (stub). Cần khi muốn AgentBase `maxReplicas>1`.
- **`deploy/k8s/` self-managed** — chỉ cần nếu deploy ngoài AgentBase (cluster tự quản). Trên AgentBase deploy qua `runtime.sh`, không cần manifest.
- **LLM qua GreenNode MaaS** — tuyến OpenAI-compat in-platform (factory đã hỗ trợ); bật bằng env khi cần, không phải việc bắt buộc Phase 11.
- **MySQL backend** — seam đã sẵn; thêm `mysql_backend.py` nếu cần.
- **Bidirectional / code action** (mở PR rollback) — phá READ-ONLY, cần duyệt riêng.
- **Real-LLM eval đầy đủ** — chạy khi có credit (harness sẵn từ P10).

---

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` + file này.
2. Bám ngày hiện tại, kết thúc bằng verify Cổng kiểm.
3. Cuối session: cập nhật `BUILD_STATE.md`.
4. **Lõi không được vỡ:** engine chạy 2 KB end-to-end + push Telegram — ưu tiên trên mọi thứ. Từ D57: regression gate chạy trên **cả 2 backend**.
5. **DB migration tuyệt đối không rò lên engine/tools:** mọi caller qua `open_db()` + seam. Lệch → hỏi người dùng trước.
6. **Single-instance:** KHÔNG externalize queue/dedup/SSE trong Phase 11. Lệch (đụng multi-replica) → hỏi trước.
7. Lệch 4 nguyên tắc / READ-ONLY → hỏi người dùng trước.
