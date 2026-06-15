# BUILD_STATE.md — Trạng thái build (cập nhật cuối mỗi session)

> Mục đích: để session Claude sau biết session trước đã làm gì → không làm lại, không phá thứ đang chạy. **Cập nhật file này cuối mỗi session làm việc.**

## Trạng thái hiện tại

**Giai đoạn:** Phase 11 🔄 ĐANG LÀM (56–60). **Ngày 56 ✅ XONG** — PG backend adapter + local infra. 444/444 tests SQLite xanh. **Phase 11 target:** Postgres Tier-2 + deploy lên **GreenNode AgentBase** (`docs/16-roadmap-phase-11.md`).
**Cổng kiểm gần nhất:** Ngày 55 (T3+Close) — 444 tests · coverage 44%→55% · server/runner/queries coverage · READ-ONLY audit clean · degrade audit clean · CI migrate D53+D54 · eval 4/4 mock PASS.
**Kế hoạch kế tiếp:** Phase 11 (Ngày 56–60) — kích hoạt Tier-2 Postgres (lệnh người dùng 2026-06-15) **+ deploy lên GreenNode AgentBase** (skills: `greennode-agentbase-skills/`). Nền tảng ràng buộc: **port 8080**, build **amd64**, deploy qua managed CR + `runtime.sh` (KHÔNG k8s/kubectl), single-instance `min=max=1`, **disk ephemeral → Postgres bắt buộc** (không PVC, SQLite không bền). Deploy fresh + docker-compose PG local. Bao gồm bug fix B1/B2 + trace retention. Future: MySQL backend · bidirectional output · horizontal scale (multi-replica) · k8s self-managed · LLM qua MaaS · real-LLM eval (chờ credit).

## Cái lõi (không được vỡ) — tình trạng

- [x] Engine chạy được kịch bản 1 end-to-end — 5 bước, verdict HIGH, root cause đúng
- [x] Engine chạy được kịch bản 2 end-to-end — 8 bước, verdict HIGH, root cause đúng
- [x] Push Telegram hoạt động — channel 911 Agent Bot
- [x] Cả 2 kịch bản chạy qua vòng tự chủ (trigger → điều tra → Telegram)

## Tiến độ theo cổng kiểm (xem `docs/03-plan-5-ngay.md`)

| Ngày | Cổng kiểm | Trạng thái |
|------|-----------|------------|
| 1 | Tool trả Observation gọn có cấu trúc | ✅ |
| 2 | Agent chạy hết KB1 end-to-end, ra verdict thô | ✅ |
| 3 | Giải đúng cả 2 KB; có script đánh giá; quay demo nháp | ✅ (mock; real LLM pending credit) |
| 4 | Vòng đầy đủ chạy mượt cả 2 KB → Telegram (ĐÓNG BĂNG) | ✅ HOÀN THÀNH — trigger→investigate→Telegram live |
| 5 | Khóa sổ + quay video | ☐ |

## Tiến độ Phase 1 (docs/10-roadmap-20-ngay.md)

| Ngày | Cổng kiểm | Trạng thái |
|------|-----------|------------|
| 6 | HTTP 202 → investigation nền → Telegram | ✅ |
| 7 | 3 adapter (Prometheus/Grafana/Sentry) pass curl test | ✅ |
| 8 | MCP hot-plug: server chạy, agent dùng MCP tools, investigation → Telegram | ✅ |
| 9 | 4 kịch bản, eval ≥7/10 mỗi cái | ✅ |
| 10 | Webhook + 4 KB + Telegram + Teams + Email + per-project channels | ✅ |

## Tiến độ Phase 2 (docs/10-roadmap-20-ngay.md)

| Ngày | Nội dung | Trạng thái |
|------|----------|------------|
| 11 | Langfuse observability (span hierarchy, token tracking, latency) | ✅ |
| 12 | Eval CI + Long-term memory + Per-project LLM config (Gemini) | ✅ |
| 13 | Dashboard v1 + Alert Trigger Builder | ✅ |
| 14 | Dashboard v2 SSE + Chat UI + Cổng Phase 2 | ✅ |

## Tiến độ Phase 3 (docs/10-roadmap-20-ngay.md)

| Ngày | Nội dung | Trạng thái |
|------|----------|------------|
| 15 | LangGraph Migration + Multi-agent | ✅ |
| 16 | Resilience + CLI + Health Dashboard | ✅ |
| 17 | Dashboard v3 Full Platform UI | ✅ |
| 18 | Fintech Domain + Domain Switcher UI | ✅ |
| 19 | Eval N=10 + Dashboard Polish (theme/toast/shortcuts) | ✅ |
| 20 | Platform Demo Full + Cổng Phase 4 | ✅ |

## Tiến độ Phase 5 (docs/11-roadmap-phase-5.md) — ĐANG LÀM

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|------------|
| 21 | Engine & Quality + Storage seam | Tier-1 storage seam (DB-swappable) · real-LLM eval smoke 6/6 · calibration · recursion bugfix | ✅ |
| 22 | Auth & RBAC | RBAC động (root/role động/project groups/scoped) — ngày nặng | ✅ |
| 23 | Observability + Project CRUD UI | Cost dashboard + verdict feedback loop + Project CRUD UI | ✅ |
| 24 | Integrations | Webhook signature + Slack + real MCP pack | ✅ |
| 25 | UI/UX + close | MCP Server Auth + Replay diff + tool test-run + search + Cổng Phase 5 | ✅ |

## Tiến độ Phase 6 (docs/12-roadmap-phase-6.md) — ĐÃ LÊN KẾ HOẠCH, CHƯA CODE

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|------------|
| 26 | Engine core | E1 vòng đời giả thuyết thật · E5 structured verdict · E2 evidence-grounding guard | ✅ |
| 27 | Engine intelligence | E4 stop/loop thông minh + cổng giả thuyết cạnh tranh · E3/D1 calibration · D2 baseline auto-update | ✅ |
| 28 | Security + custom LLM | A4 API token webhook · A2 secret at-rest · A3 trace retention · per-project LLM endpoint riêng (model/url/header, fallback default) | ✅ |
| 29 | Reliability infra | A1 graceful shutdown · B3 investigation queue (in-process) · B4 rate limiting | ✅ |
| 30 | Ecosystem + close | C1 PagerDuty/OpsGenie · C4 callback · D3 clustering · F1 demo theme · F2 nav fix · Cổng Phase 6 | ✅ |

**Defer → Future:** B1 Tier-2 Postgres (cần lệnh rõ + env) · C2 bidirectional (phá READ-ONLY, cần duyệt) · B2 horizontal scale seam · D4 real MCP pack mở rộng.

## Tiến độ Phase 7 (Ngày 31–35)

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|------------|
| 31 | Quick wins + Test skeleton | Demo 401 fix · C3 GitHub/GitLab adapter · pytest 24 tests | ✅ |
| 32 | Proactive monitoring | Scheduled trigger · Recurring incident alert push | ✅ |
| 33 | Engine depth | D2 baseline auto-update · Multi-agent conflict resolution · Auth+tool tests (50/50) | ✅ |
| 34 | Deployment & DX | Docker + docker-compose · Investigation export JSON/CSV · Tool unit tests (63/63) | ✅ |
| 35 | Production bridge + close | Redis SSE seam (stub+factory) · Phase 7 gate PASS | ✅ |

## Tiến độ Phase 8 (docs/13-roadmap-phase-8.md) — ✅ HOÀN TẤT

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|------------|
| 36 | E6 — Engine domain-agnostic | Rút `_HYPOTHESIS_RELEVANCE` khỏi engine → catalog theo miền (cạnh tool registry) + catalog fintech | ✅ |
| 37 | E7 — Hợp nhất path + parity | 1 nguồn stop/gate cho loop+graph · multi-agent ngang hàng (grounding+conflict+merge evidence_id) | ✅ |
| 38 | E8 — Real-LLM eval + calib | Smoke mở rộng (~$2) · feed ngưỡng calibration ngược vào engine (đóng vòng E3) | ✅ |
| 39 | T1 — Test adapters/output | 8 intake adapter + 5 output renderer (mỗi cái ≥3 ca) | ✅ |
| 40 | T1 — Test infra + contract | queue/scheduler/registry/crypto + guard nguyên tắc #1 (Observation hợp lệ) | ✅ |
| 41 | T2 — CI gate tự động | GitHub Actions: pytest + mock eval 4/4 + syntax/import + coverage | ✅ |
| 42 | P1 — Cost + perf | Prompt caching (prefix ổn định) + gọn context | ✅ |
| 43 | E9 — Structured verdict thẳng | args→Verdict trực tiếp (bỏ vòng args→text→parse) + cờ parse_degraded | ✅ |
| 44 | DX + docs | README gốc + Makefile + gộp API docs + polish demo 7 phút | ✅ |
| 45 | Hardening + Cổng Phase 8 | Audit config/security + đóng pha | ✅ |

**Chốt Phase 8:** Day 38 = smoke mở rộng ~$2 (KHÔNG full N=10) · horizontal scale seam vẫn Future (Redis SSE giữ stub) · Tier-2/bidirectional vẫn Future.
**Xương sống KHÔNG cắt:** D36 · D37 · D39 · D41.

## Tiến độ Phase 9 (docs/14-roadmap-phase-9.md) — 📋 ĐÃ LÊN KẾ HOẠCH, CHƯA CODE

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|------------|
| 46 | E11 — Service prior | Pre-seed `Hypothesis` open theo `investigation_patterns` (map root_cause_type→catalog tag); `Hypothesis.prior_seen_count`; confirm vẫn cần bằng chứng thật | ✅ |
| 47 | E10 — Tool sequencing | `_tool_sequencing_hint(state)` nối vào `_build_user_message` (parity loop↔graph free); reuse catalog `relevant_tools`; advisory only | ✅ |
| 48 | E12 — Specificity gate (lõi) | `engine/specificity.py:compute_verdict_specificity` + `_apply_specificity_gate` nudge dùng chung loop+graph; `Verdict.specificity_score` | ✅ |
| 49 | E12 — Multi-agent + đo | Downgrade/annotate trong `_synthesize_verdict` · dashboard specificity + avg-steps before/after · real-LLM smoke ~$2 | ✅ |
| 50 | Tests + CI + Cổng P9 | Test cả 3 (~195–200) · CI xanh · audit degrade an toàn · cập nhật BUILD_STATE/CLAUDE · đóng pha | ✅ |

## Tiến độ Phase 10 (docs/15-roadmap-phase-10.md)

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|------------|
| 51 | F1 — Code seam over MCP | `tools/code_distill.py:distill_code_response` (raw diff/file → Observation chưng cất, P#1) · risk interpreter generic (pool/timeout/config/dep-bump) · bảng `service_repos` (mapping metadata, project-scoped) · READ-ONLY guard `is_read_only_tool` (chặn write/PR/merge/push) · UI repo config card · tests mocked MCP | ✅ |
| 52 | F2 — Deploy↔code + specificity | `get_recent_deploys` **giữ nguyên** → agent đọc diff/file đúng version qua MCP (map version→repo qua `service_repos`) · catalog: thêm code tool vào `relevant_tools` `deploy_bug`/`dependency` → E10 hint + E11 prior tự kích · `specificity.py` cộng điểm code evidence (file+dòng+version) · grounding nhận code Observation · ~25 tests | ✅ |
| 53 | V1 + E13 — Eval harness + prior decay | `eval_agent.py`: --no-prior flag (A/B) + specificity_score per run + avg specificity in summary · `patterns.py`: `_decay_weight` (half-life 30d) + sort by weighted_count · `queries.py:get_eval_comparison_data` · `eval.html`: E13 Before/After panel · `migrate_day53.py`: +2 cột eval_results · 24 tests | ✅ |

| 54 | P2 + OPS1 — Distill tổng quát + catalog editor | `mcp_client.py:_parse_observation` distill text dài thay vì cắt 500-char + budget tuning · bảng `hypothesis_catalog` (DB override lên default) + CRUD UI (tag/keywords/relevant_tools/root_cause_type/repo-tool mapping) | ✅ |
| 55 | T3 + Close — Coverage + Cổng P10 | Tests dashboard/server/runner + CI import/syntax lớp code + ngưỡng coverage gate nhẹ · docs/15 ✅ + README/api · audit READ-ONLY (grep không tool ghi) + degrade safe · cập nhật BUILD_STATE/CLAUDE · đóng pha | ✅ |

**Chốt Phase 10 (đã xác nhận với người dùng):** code đọc **chỉ qua external MCP** (GitHub/GitLab = extension, KHÔNG quản lý source trong hệ thống, KHÔNG local diff) · `get_recent_deploys` giữ nguyên · **READ-ONLY tuyệt đối với code** · real-LLM eval = mock + defer (chờ credit) · Tier-2/bidirectional/horizontal vẫn Future · 5 ngày (dồn khối lượng từ bản 10 ngày, không cắt scope).
**Xương sống KHÔNG cắt:** D51 (F1) · D52 (F2) · D55 (test + Cổng + audit READ-ONLY). Cắt nếu hụt giờ: demo-MCP stand-in (D51) → catalog editor UI (D54, giữ read-path) → coverage gate enforce (D55).
**Bất biến:** Nguyên tắc #1 (code distill, không raw dump) · Nguyên tắc #2 (risk heuristic generic, mapping tool↔hypothesis trong catalog) · READ-ONLY · regression gate mỗi ngày engine/tool (51–54).

## Tiến độ Phase 11 (docs/16-roadmap-phase-11.md) — 📋 ĐÃ LÊN KẾ HOẠCH, CHƯA CODE

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|------------|
| 56 | PG backend adapter + local infra | `postgres_backend.py`: thay stub bằng psycopg connection shim (`.execute` tự cursor + `?`→`%s`, dict-row key+index, `lastrowid` qua RETURNING, IntegrityError) + `psycopg_pool` connection pool · `data/schema_postgres.sql` (SERIAL, bỏ PRAGMA) · `init_db.py` backend-aware · seed/migrate chạy trên PG · `docker-compose.yml` service postgres local · `.env.example` +DB_BACKEND/DATABASE_URL · extra `[postgres]` | ✅ |
| 57 | Dialect parity + đóng rò seam + CI matrix | `INSERT OR IGNORE/REPLACE`→`ON CONFLICT` · `datetime()/julianday()` → Python/branch · **fix `auth/rbac.py` `import sqlite3`→open_db()** · `migrate_*.py` exception trung lập · CI `DB_BACKEND=[sqlite,postgres]` matrix (services postgres) · **444 tests xanh trên cả 2** + eval 4/4 PG | ☐ |
| 58 | Container & config hardening + port 8080 + B1 | **port 8000→8080 (HARD AgentBase)** trong `start_server.py`/Dockerfile/health tests · Dockerfile multi-stage non-root + amd64 + `EXPOSE 8080` + HEALTHCHECK + `.[postgres]` + entrypoint init/migrate · `.dockerignore` (.env/.db/.venv) · secrets fail-fast khi `APP_ENV=production` (SESSION_SECRET_KEY/SECRET_KEY) · `/health/ready` (DB ping + backend) tách `/health` (liveness) · `.env.example` ghi chú 4 biến `GREENNODE_*` auto-inject không set tay · **B1: `_make_error_state` truyền project_id+available_services** | ☐ |
| 59 | Lifecycle + observability + retention + B2 | SIGTERM drain in-flight (A1 verify+mở rộng) + ghi rõ queue semantics restart · JSON log opt-in (`LOG_FORMAT=json`) · `/health` sâu (DB+backend+MCP reachable+LLM key) · trace_events retention (`TRACE_RETENTION_DAYS`) · **B2: `loop.py:1069,1090` 2 `_emit_trace` thêm `project_id=state.project_id` (parity graph.py)** + perf re-check pool | ☐ |
| 60 | Deploy lên AgentBase + smoke + Cổng P11 | `docker-compose.prod.yml` (app+postgres) · **runbook AgentBase**: build amd64 → managed CR (`vcr.vngcloud.vn`, `cr.sh docker-login`) → `runtime.sh create --from-cr --min/max-replicas 1` → poll ACTIVE → `<endpoint>/health` 200 · `deploy/k8s/` skeleton **HẠ xuống Future** (deploy qua runtime.sh, không kubectl) · README/api Deploy-AgentBase section (port 8080/amd64/CR/env/auto-inject) · E2E smoke (PG, trigger→điều tra→Telegram) · audit READ-ONLY/4 nguyên tắc/degrade (DB down→ready đỏ) · đóng pha | ☐ |

**Chốt Phase 11 (đã xác nhận với người dùng — 2026-06-15):** ① **Postgres ngay** (Tier-2 kích hoạt) — PG backend prod, SQLite vẫn default dev, seam giữ cả 2; **bắt buộc vì AgentBase disk ephemeral (không PVC) → SQLite không bền qua deploy** · ② **single-instance** = AgentBase `min=max=1 replica` (KHÔNG externalize queue/dedup/SSE — horizontal scale vẫn Future) · ③ **deploy fresh** (chỉ init+seed PG, không migrate data SQLite cũ) · ④ **docker-compose chạy PG local** trước khi đẩy cloud · ⑤ không giới hạn khối lượng/ngày · ⑥ **nền tảng = GreenNode AgentBase**: port 8080 + build amd64 + deploy qua CR/`runtime.sh` + 4 biến `GREENNODE_*` auto-inject không set tay (skills: `greennode-agentbase-skills/`).
**Xương sống KHÔNG cắt:** D56+D57 (PG parity + 444 tests xanh trên PG + đóng rò seam) · D58 (**port 8080** + container+secrets+B1) · D59 B2. Cắt nếu hụt giờ: deploy AgentBase thật → giữ runbook+compose.prod smoke (D60) → JSON logging (D59) → retention qua scheduler (D59, giữ script). **Port 8080/amd64 = hợp đồng cứng, không cắt.**
**Bất biến:** DB swap chỉ dưới seam (`open_db()`/`IntegrityError` trung lập, không rò `import sqlite3` ngoài `sqlite_backend.py`) · READ-ONLY · 4 nguyên tắc · regression gate mỗi ngày (444 tests + eval 4/4 + 2 KB E2E + Telegram; từ D57 trên cả 2 backend).

### [Session 60 — 2026-06-15] — Ngày 56: PG backend adapter + local infra

**Đã làm:**
- `src/agent/storage/postgres_backend.py` (rewrite từ stub): psycopg3 shim hoàn chỉnh — `_translate()` (`%`→`%%` trước, `?`→`%s`, `INSERT OR IGNORE`→`ON CONFLICT DO NOTHING`) · `_PGRow` (key+index+iter+dict()) · `_PGCursor` (lastrowid, fetchall, fetchone) · `_PGConnection` (execute/executemany/executescript/commit/rollback/close→pool) · `_SERIAL_ID_TABLES` → inject `RETURNING id` · `psycopg_pool.ConnectionPool` module-level lazy init.
- `data/schema_postgres.sql` (mới): tương đương schema.sql dialect PG — `BIGSERIAL PRIMARY KEY`, bỏ PRAGMA, giữ IF NOT EXISTS/UNIQUE/FK CASCADE/partial index.
- `data/init_db.py` (rewrite): backend-aware — `DB_BACKEND=sqlite` → `sqlite3.connect` + PRAGMA WAL · `DB_BACKEND=postgres` → `open_db()` → `executescript(schema_postgres.sql)` · redact password khi in URL.
- `data/seed_scenario1.py`: thêm `_open_conn()` (sqlite/postgres branch) · `INSERT OR REPLACE INTO service_catalog` → `ON CONFLICT (service) DO UPDATE SET`.
- `data/seed_scenario2.py`, `seed_scenario3.py`, `seed_scenario4.py`: thêm `_open_conn()` (import os/sys/ROOT) · `main()` dùng `_open_conn()` thay `sqlite3.connect(DB_PATH)` · bỏ `conn.row_factory = sqlite3.Row`.
- `data/seed_fintech1.py`, `seed_fintech2.py`: `INSERT OR REPLACE INTO ft_merchants` → `ON CONFLICT (id) DO UPDATE SET`.
- `docker-compose.yml`: thêm service `postgres` (postgres:16-alpine, named volume `pgdata`, healthcheck pg_isready, profile `postgres`) + `volumes: pgdata:`.
- `.env.example`: thêm `DB_BACKEND=sqlite`, `DATABASE_URL=` (với comment format), ghi chú 4 biến `GREENNODE_*` auto-inject (không set tay).
- `pyproject.toml`: thêm `[project.optional-dependencies] postgres = ["psycopg[binary]>=3.1.0", "psycopg-pool>=3.2.0"]`.
- `src/agent/storage/db.py`: cập nhật docstring (bỏ "stub Tier-2"), thông báo lỗi rõ hơn.

**Cổng Ngày 56 PASS:**
- `postgres_backend.py` import OK (psycopg installed) ✅
- `init_db.py` SQLite init sạch ✅
- `seed_scenario1.py` + `seed_scenario2.py` chạy trên SQLite ✅
- Tất cả seed files parse clean (ast.parse) ✅
- **444/444 tests SQLite xanh** ✅
- `docker-compose.yml` syntax OK (postgres service + pgdata volume) ✅

**Ghi chú kỹ thuật quan trọng:**
- Thứ tự `_translate()`: `%` → `%%` TRƯỚC rồi `?` → `%s` (nếu đảo: `%s` bị bắt thành `%%s`)
- `executemany()` dùng plain cursor (không dict_row) vì chỉ write, không cần row access
- `_SERIAL_ID_TABLES` inject `RETURNING id` — chỉ các bảng này (`mcp_servers`, `logs`, `metrics`, `deploys`, `trace_events`, `eval_results`, `investigation_patterns`); TEXT PK tables không cần
- `close()` → `pool.putconn()` (trả về pool, không đóng TCP)
- Docker compose profile `postgres` → chỉ bật khi cần: `docker compose --profile postgres up -d postgres`

**Chưa làm (Ngày 57+):**
- Dialect parity còn lại: `auth/rbac.py` leak `import sqlite3` (DB3 bug) → D57
- CI matrix `DB_BACKEND=[sqlite,postgres]` → D57
- 444 tests xanh trên PG → D57 (cần postgres service chạy)
- Port 8000→8080 (HARD AgentBase), Dockerfile prod → D58
- B1/B2 fix → D58/D59

### [Session 59 — 2026-06-15] — Lập kế hoạch Phase 11 (Ngày 56–60) + session review

**Bối cảnh:** Phase 10 xong (444/444 tests). Session này **KHÔNG code** — đọc lại engine/MCP/runner/memory (`loop.py`, `mcp_client.py`, `runner.py`, `patterns.py`, `state.py`, `specificity.py`, `graph.py`, `storage/db.py`, `sqlite_backend.py`, `postgres_backend.py`) → tổng hợp hệ thống + tìm bug + lập Phase 11. Người dùng muốn deploy container lên cloud + cân nhắc Postgres.

**Bug/nợ phát hiện (cơ sở Phase 11):**
- **B1 (CAO):** `runner.py:_make_error_state` mất `project_id` → timeout/error route sai kênh project (multi-tenant). → fix D58.
- **B2 (CAO):** `loop.py:1069,1090` 2 `_emit_trace` (`tool_call`/`tool_result`) thiếu `project_id` (graph.py đã đúng) → trace bước tool ghi vào "default", parity loop↔graph lệch. → fix D59.
- **DB3 (rò seam):** `auth/rbac.py` `import sqlite3` trực tiếp, bypass dispatcher → vỡ trên PG. → fix D57.
- **DB4 (perf):** `open_db()` gọi rất nhiều (mỗi `_emit_trace`/bước); SQLite rẻ nhưng PG cần connection pool. → D56 pool.
- **OPS2:** trace_events phình vô hạn (A3 có config, chưa enforce cleanup). → D59 retention.
- Nợ nhẹ (chưa lên lịch): `_distill_external_text` lấy head không "đại diện" + không tự diễn giải (soft P#1) · `get_warm_start_hint` không áp decay (E13 chỉ ở get_service_priors) · `get_service_priors` prefilter count thô có thể bỏ pattern rất mới · `_classify_root_cause` "unavailable"→provider_down trước processor_timeout.

**Quyết định chốt (qua AskUserQuestion):** Postgres ngay · single-instance · deploy fresh (init+seed PG) · docker-compose PG local · không giới hạn khối lượng/ngày. → Tier-2 **kích hoạt** (rule CLAUDE.md "cần lệnh rõ" được người dùng ra lệnh).

**Đã làm (3 file, không động code):**
- `docs/16-roadmap-phase-11.md` (mới) — kế hoạch Ngày 56–60, format Làm/Cổng như docs/11–15; bảng kiểm 4 nguyên tắc + thay đổi kiến trúc Tier-2; thứ tự cắt; Future.
- `CLAUDE.md` — header giai đoạn + bảng Phase 10 ☐→✅ + bảng Phase 11 + rule Postgres (Tier-2 kích hoạt) + Stack table Storage (seam SQLite/PG) + roadmap pitch + Future + cấu trúc file (docs/15 xong, thêm docs/16).
- `BUILD_STATE.md` — header trạng thái + bảng Tiến độ Phase 11 + entry này.

**Chưa làm:** chưa bắt đầu code Ngày 56 (chờ session mới khởi động). B1/B2 chưa fix (nằm trong D58/D59).

**Addendum (cùng ngày) — review nền tảng AgentBase + cập nhật roadmap:** Người dùng hỏi giữ SQLite có giữ được data qua deploy không → đọc `greennode-agentbase-skills/` (runtime-contract.md + agentbase-deploy SKILL + runtime-ops.md). Phát hiện quyết định: ① AgentBase = serverless container, **chỉ enforce port 8080 + `GET /health` 200** · ② **disk ephemeral, KHÔNG có volume/PVC** trong API create/update → **SQLite không thể bền** qua deploy/restart/scale → **Postgres bắt buộc** (chốt Tier-2) · ③ deploy = build **amd64** → managed CR (`vcr.vngcloud.vn`) → `runtime.sh create`, KHÔNG kubectl → **k8s skeleton hạ xuống Future** · ④ env bơm qua `--env-file`; 4 biến `GREENNODE_CLIENT_ID/CLIENT_SECRET/AGENT_IDENTITY/ENDPOINT_URL` auto-inject, không set tay · ⑤ single-instance = `min=max=1 replica` (lý do cứng: in-memory state split-brain nếu >1) · ⑥ MaaS OpenAI-compat là tuyến LLM tùy chọn (factory đã hỗ trợ). → Cập nhật `docs/16` (thêm section "Ràng buộc nền tảng AgentBase", PLAT1/PLAT2, D58 port 8080, D60 deploy AgentBase), `CLAUDE.md` (bảng+pitch+ràng buộc lõi), `BUILD_STATE.md` (header+bảng+chốt). Vẫn **không động code**.

### [Session 58 — 2026-06-15] — Ngày 55: T3+Close Coverage + Cổng Phase 10

**Đã làm:**
- `tests/test_server.py` (mới, 20 tests): TestHealthRoute (4) · TestAdaptersRoute (2) · TestAuthRoutes (3) · TestProjectRoutes (7) · TestTriggerRoute (5) · TestMcpServerRoutes (2). Dùng `TestClient(app, raise_server_exceptions=False)`, ALLOW_ANON_TRIGGER env patch.
- `tests/test_runner_coverage.py` (mới, 11 tests): TestGetMcpServersForProject (3) · TestGetProjectServices (2) · TestMakeErrorState (2) · TestTriggerInvestigation (2) · TestRunInvestigationDedup (1) · TestMcpClientConnect (2).
- `tests/test_dashboard_queries.py` (mới, 29 tests): TestGetCostData (3) · TestListInvestigations (4) · TestGetEvalSummary (2) · TestGetProjectsOverview (1) · TestGetMetricsLive (2) · TestGetSpecificityData (1) · TestGetEvalComparisonData (2) · TestGetMcpServersForDashboard (1) · TestGetAllToolsForDashboard (3) · TestPricingHelper (5).
- `.github/workflows/ci.yml`: thêm `migrate_day53.py` + `migrate_day54.py` vào DB setup step; thêm `agent.tools.code_distill`, `agent.tools.get_code_diff`, `agent.tools.mcp_client`, `agent.intake.runner` vào import smoke.
- `docs/15-roadmap-phase-10.md`: tất cả 5 ngày ☐→✅.

**Audit READ-ONLY:** `grep engine/` — không có `get_code_diff`/`github`/`gitlab`/`repo_url` trong `loop.py`/`multi_agent.py`/`state.py`. Chỉ `hypothesis_catalog.py` có `get_code_diff` (đúng — catalog layer). `is_read_only_tool` BLOCK đủ 8 write tools, ALLOW đủ 9 read tools ✅.

**Audit degrade:** no repo mapping → Observation hợp lệ (không crash) · empty MCP text → Observation hợp lệ · no catalog DB → default 5 entries trả về ✅.

**Tests:** 384 + 60 = **444/444 tests**. Coverage: 44%→55%.

**Cổng Phase 10 PASS:**
- F code seam: distill+guard+service_repos+get_code_diff ✅ (D51)
- F2 synergy: deploy↔code; E10/E11 hint; code→E12 specificity ✅ (D52)
- V1: eval harness + avg specificity + --no-prior A/B ✅ (D53)
- E13: prior decay half-life 30d ✅ (D53)
- P2: external MCP distill (không còn truncate 500-char) ✅ (D54)
- OPS1: catalog editor UI + DB merge ✅ (D54)
- T3: coverage 55% + 60 tests mới + CI migrate ✅ (D55)
- Nguyên tắc #2 + READ-ONLY: grep clean ✅ (D55)
- Degrade safe: 3 nhánh kiểm tra sạch ✅ (D55)
- Regression: eval 4/4 mock + 444 tests ✅ (D55)

**Real-LLM eval ~$2:** lệnh sẵn: `python scripts/eval_agent.py --scenario scenario1 --n 3` — chờ top-up credit.

### [Session 57 — 2026-06-15] — Ngày 54: P2+OPS1 Distill tổng quát + Catalog Editor

**Đã làm:**
- `tools/mcp_client.py`: thêm hàm `_distill_external_text(text, tool_name, server_url) -> Observation` — distill text tự do từ external MCP: summary = dòng đầu ≤200 char có prefix `[tool_name]`, samples ≤5 dòng đại diện từ phần còn lại, total_count = số dòng không trống, truncated flag. Thay thế hoàn toàn logic cắt 500-char cũ. `_parse_observation` path external gọi `_distill_external_text`. JSON path (Observation-structure) giữ nguyên không đổi.
- `data/migrate_day54.py` (mới): tạo bảng `hypothesis_catalog` idempotent (domain, project_id, tag UNIQUE). Chạy ngay.
- `engine/hypothesis_catalog.py`: thêm `import json, logging`; thêm `_row_to_entry`, `load_db_catalog_entries`, `merge_catalog_with_db`, `add_catalog_entry`, `delete_catalog_entry`, `list_catalog_entries_db`. `merge_catalog_with_db(base, domain, project_id)` — DB override cùng tag ghi đè, tag mới thêm cuối; fallback an toàn khi DB trống/lỗi.
- `intake/runner.py`: `get_default_catalog(domain)` → `merge_catalog_with_db(get_default_catalog(domain), domain, project_id)`. Project-scoped DB overrides.
- `dashboard/router.py`: 3 route mới — `GET /catalog` (list DB + default read-only), `POST /catalog/add` (form add entry), `POST /catalog/{id}/delete`. Degrade-safe, redirect 303.
- `dashboard/templates/catalog.html` (mới): form add entry (tag/content/keywords/tools/conf/root_cause_type) + bảng DB overrides với nút Xóa + bảng Default catalog (read-only).
- `dashboard/templates/base.html`: thêm link "Catalog Editor" vào nav nhóm Cấu hình.
- `tests/test_day54.py` (mới, 19 tests): TestDistillExternalText (10) · TestParseObservationDistills (2) · TestLoadDbCatalogEntries (3) · TestMergeCatalogWithDb (4).

**Tests:** 365 + 19 = **384/384 tests**.

**Cổng Ngày 54 PASS:**
- `_distill_external_text`: summary ≤200 char có tool prefix · samples ≤5 · total_count = non-blank lines · truncated flag đúng · blank lines bỏ qua · source metadata đúng ✅
- `_parse_observation` external path dùng distill (không còn [:500]) · JSON path giữ nguyên ✅
- `merge_catalog_with_db`: empty DB → base unchanged · DB tag override ghi đè · new tag thêm cuối · order preserved ✅
- Catalog CRUD UI hoạt động (route add/delete/list) ✅
- 384/384 tests ✅

### [Session 56 — 2026-06-15] — Ngày 53: V1+E13 Eval harness + Prior decay

**Đã làm:**
- `data/migrate_day53.py` (mới): ADD COLUMN `specificity_score REAL` + `prior_flag INTEGER DEFAULT 0` vào `eval_results`. Idempotent (try/except OperationalError). Chạy ngay.
- `memory/patterns.py`: thêm `_HALF_LIFE_DAYS=30.0` + `_decay_weight(iso_str) -> float` (hàm mũ `exp(-d·ln2/30)`, degrade 1.0 nếu parse lỗi). `get_service_priors` thêm `weighted_count = count × decay`, sort theo `weighted_count DESC` thay vì `count DESC`. Trả thêm key `weighted_count` trong result.
- `engine/loop.py`: thêm `no_prior: bool = False` vào `InvestigationEngine.__init__`; guard `_preseed_hypotheses` bằng `if not self._no_prior:`.
- `scripts/eval_agent.py`: `_get_specificity(state)` helper → `evaluate_run` luôn có key `specificity_score` (kể cả no_verdict case). `print_summary` in `Avg specificity`. `--no-prior` argparse flag → truyền xuống engine + `_save_eval_results_to_db(prior_flag=1)`. `_save_eval_results_to_db` lưu `specificity_score` + `prior_flag` (fallback schema cũ).
- `dashboard/queries.py`: thêm `get_eval_comparison_data()` — group by `prior_flag`, tính avg_steps + avg_specificity + rate, degrade-safe.
- `dashboard/router.py`: import + call `get_eval_comparison_data()`, pass `eval_comparison` vào template.
- `dashboard/templates/eval.html`: thêm panel "E13 — Prior Decay A/B" với 4 stats-box (avg_steps+avg_specificity × 2 modes) + meta ghi lệnh chạy.
- `tests/test_e13_prior_decay.py` (mới, 24 tests): TestDecayWeight (8) · TestGetServicePriorsDecay (6) · TestNoPriorFlag (2) · TestEvalHarness (3) · TestEvalComparisonData (5).

**Tests:** 341 + 24 = **365/365 tests**.
**Eval mock:** avg specificity 0.67 in output, 4/4 PASS.

**Cổng Ngày 53 PASS:**
- `_decay_weight`: 1.0 hôm nay, ~0.5 sau 30 ngày, monotone giảm, degrade "" → 1.0 ✅
- `get_service_priors` sort theo weighted_count (pattern mới cùng count đứng trước pattern cũ) ✅
- `no_prior=True`: `engine._no_prior=True`, không có hypothesis với prior_seen_count>0 trong state ✅
- `evaluate_run` luôn có key `specificity_score` ✅
- `get_eval_comparison_data` group đúng by prior_flag, degrade empty → None ✅
- Mock eval 4/4 + avg specificity in output ✅
- 365/365 tests ✅

**Real-LLM ~$2:** lệnh sẵn: `python scripts/eval_agent.py --scenario scenario1 --n 3` — chờ top-up credit.

### [Session 55 — 2026-06-15] — Ngày 52: F2 Deploy↔code synergy

**Đã làm:**
- `tools/get_code_diff.py` (mới): `build_code_diff_tool(project_id, code_mcp_client=None) -> Tool` — factory scope theo project; lookup `service_repos`; 3 nhánh degrade-safe: (a) no repo mapping → Observation status=no_repo_mapping, (b) repo configured no MCP → status=no_mcp_client + repo_url in aggregates, (c) với MCP client → tìm get_diff/diff/get_file_diff/fetch_diff → gọi + distill qua `distill_code_response`. Tool name `"get_code_diff"` — passes `is_read_only_tool` (tiền tố `get_`). READ-ONLY hoàn toàn.
- `engine/hypothesis_catalog.py`: thêm `"get_code_diff"` vào `deploy.relevant_tools` → E10 hint + E11 prior tự kích miễn phí (Nguyên tắc #2 giữ vững — engine không thay đổi).
- `engine/specificity.py`: thêm 4th signal bonus (F2) — `_has_code_evidence_with_signals(state)` check `ev.observation.metadata.source == "code_mcp"` + `risk_signals` non-empty; nếu True: `passed += 1, total = 4` (chỉ tăng không giảm). Tài liệu hoá trong docstring. Backward-compat: no code evidence → `total = 3` (hành vi cũ).
- `intake/runner.py`: sau khi build tool registry (domain != fintech), gọi `list_service_repos(project_id)` → nếu có repo mapping, inject `build_code_diff_tool(project_id)` vào tools list (degrade-safe, wrapped trong try/except).
- `tests/test_code_layer.py` (+27 tests, tổng 79 trong file này): TestGetCodeDiffTool (9) · TestCatalogCodeAware (5) · TestCodeSpecificity (9) · TestPrincipleGuard (4). Thêm `_make_temp_repos_db()` helper.
- `tests/test_e10_tool_sequencing.py` (3 tests sửa): cập nhật `test_no_hint_when_all_tools_called`, `test_hint_updates_after_tool_call`, `test_hint_empty_string_when_all_called` — thêm `get_code_diff` vào tool_call_history (vì deploy.relevant_tools giờ có 2 tool).

**Tests:** 314 + 27 = **341/341 tests**.
**Eval mock:** 4/4 PASS.
**Nguyên tắc #2:** `grep src/agent/engine/` không có "github", "gitlab", "repo_url", "get_code_diff" trong loop.py ✅.

**Cổng Ngày 52 PASS:**
- build_code_diff_tool factory: schema đúng, 3 nhánh degrade-safe ✅
- is_read_only_tool("get_code_diff") = True ✅
- deploy.relevant_tools có get_code_diff; E10 hint khi deploy open ✅
- Hint biến mất khi cả get_recent_deploys + get_code_diff đã gọi ✅
- _has_code_evidence_with_signals: True/False đúng cases ✅
- Score với code evidence > không có code evidence ✅
- Nguyên tắc #2 giữ vững ✅
- 341/341 tests · eval 4/4 ✅

### [Session 53 — 2026-06-15] — Lập kế hoạch Phase 10 (Ngày 51–55)

**Bối cảnh:** Phase 9 xong (262/262 tests). Session này **KHÔNG code** — đọc kỹ engine + tool + MCP (`loop.py`, `state.py`, `registry.py`, `contracts.py`, `mcp_client.py`, `get_recent_deploys.py`, `hypothesis_catalog.py`, `memory/patterns.py`, `schema.sql`) → tổng hợp Phase 1–9 + đánh giá gaps/tech-debt + chốt Phase 10. Người dùng yêu cầu thêm tính năng lõi: agent đọc mã nguồn (ngoài logs/metrics/deploys) qua MCP như GitHub/GitLab.

**Phát hiện chính (cơ sở Phase 10):**
- **F (tính năng mới):** agent không đọc được mã nguồn. `get_recent_deploys` biết "deploy vX" nhưng không biết vX đổi gì → root cause mờ. GitHub/GitLab hiện chỉ là *intake adapter* (webhook→trigger), không phải đọc-code.
- **P2 (tech debt):** `mcp_client.py:_parse_observation` cắt text external cứng 500-char → vi phạm ngầm Nguyên tắc #1 với MCP trả dữ liệu giàu (diff). Rào chắn của lớp code + nợ chung.
- **V1 (validation gap):** real-LLM eval chưa từng chạy (D38 + D49 đều SKIP vì hết credit) → E10/E11/E12 chưa kiểm chứng trên LLM thật.
- **E13:** prior không decay (`investigation_patterns.count` tăng vô hạn). **OPS1:** catalog hardcode Python. **T3:** coverage ~29%.

**Quyết định chốt (người dùng xác nhận qua nhiều vòng):**
1. **Code đọc CHỈ qua external MCP — KHÔNG local diff.** "Source code không được quản lý bởi hệ thống này." `service_repos` chỉ là mapping metadata. GitHub/GitLab MCP = **extension**, không phải main flow. Trọng tâm kỹ thuật dịch sang **distillation wrapper** (raw diff/file → Observation chưng cất).
2. **`get_recent_deploys` giữ nguyên** — code tool bổ sung chiều "đọc thay đổi của deploy".
3. **Real-LLM eval = mock + defer** (chưa có credit) — D53 dựng harness, chạy mock, real-LLM ~$2 chờ top-up.
4. **Defer→Future giữ nguyên:** Tier-2 Postgres · bidirectional · horizontal scale — không kéo vào Phase 10.
5. **5 ngày** (dồn khối lượng từ bản 10 ngày đề xuất ban đầu, không cắt scope).

**Đã làm (3 file, không động code):**
- `docs/15-roadmap-phase-10.md` (mới) — kế hoạch Ngày 51–55, format Làm/Cổng như docs/11–14; bảng kiểm 4 nguyên tắc + READ-ONLY cho lớp code; thứ tự cắt nếu hụt giờ.
- `CLAUDE.md` — header giai đoạn + bảng Phase 10 + roadmap pitch (thêm Phase 10) + cấu trúc file (docs/14 đã xong, thêm docs/15).
- `BUILD_STATE.md` — header trạng thái + bảng Tiến độ Phase 10 + entry này.

**Chưa làm:** chưa bắt đầu code Ngày 51 (chờ session mới khởi động).

### [Session 52 — 2026-06-15] — Ngày 50: Tests + CI + Cổng Phase 9

**Đã làm:**
- Xác nhận 262/262 tests PASS (89 tests riêng cho E10/E11/E12).
- Audit nguyên tắc #2: `grep` không tìm thấy keyword miền nào hardcode trong `src/agent/engine/`.
- Audit degrade an toàn: service chưa có lịch sử → prior=[] · không có catalog entry → hint rỗng · verdict rỗng hoàn toàn → specificity score=0.0 (3 tín hiệu đều fail, không crash).
- Cập nhật `.github/workflows/ci.yml`: mở rộng import check thêm 4 module Phase 9 (`agent.engine.specificity`, `agent.engine.multi_agent`, `agent.engine.graph`, `agent.memory.patterns`).
- Mock eval 4/4: `python scripts/eval_agent.py --mock` → CỔNG EVAL ✅ PASS.
- Commit Starlette 1.x TemplateResponse fix (26+2 calls — `dashboard/router.py` + `intake/server.py`).
- Cập nhật `BUILD_STATE.md` + `CLAUDE.md` → Phase 9 ✅ HOÀN TẤT.

**Không làm:** Real-LLM smoke ~$2 — API credit cạn kiệt từ Session 51; cần top-up trước khi chạy.

**Cổng Phase 9 PASS:**
- E11: prior pre-seed + degrade safe + 27 tests ✅
- E10: hint sequencing + parity loop↔graph + advisory + 21 tests ✅
- E12: gate loop/graph + downgrade multi-agent + dashboard specificity + 41 tests ✅
- Nguyên tắc #2: zero keyword miền trong engine ✅
- Regression: mock eval 4/4 ✅
- 262/262 tests + CI import check mở rộng ✅

### [Session 51 — 2026-06-15] — Ngày 49: E12 multi-agent + đo

**Đã làm:**
- `engine/multi_agent.py:_synthesize_verdict`: sau calibration, gọi `compute_verdict_specificity`; nếu score < 0.40 và conf in {high, medium} → hạ 1 bậc confidence + annotate `evidence_summary` với `[⚠ E12 specificity=... — reasons]`; set `verdict.specificity_score`.
- `dashboard/queries.py`: thêm `get_specificity_data()` — đọc trace_events verdict gần nhất (≤200), tính avg_specificity, phân bố high/med/low.
- `dashboard/router.py`: import + call `get_specificity_data()` trong `/eval` route, pass vào template.
- `dashboard/templates/eval.html`: thêm panel "E12 — Verdict Specificity" với stats-row (n, avg, high/med/low counts) + metadata về threshold + cách gate hoạt động.
- `tests/test_e12_specificity.py` (+3 tests): TestMultiAgentSpecificityDowngrade (2 async tests) + TestSpecificityScoreInFinalize (1 sync test).

**Không làm (blocked):** Real-LLM smoke ~$2 — API credit cạn kiệt (`credit balance too low`). Cần top-up trước khi chạy.

**Tests:** 259 + 3 = 262/262.

### [Session 50 — 2026-06-15] — Ngày 48: E12 specificity gate lõi

**Đã làm:**
- `engine/specificity.py` (mới): `SPECIFICITY_THRESHOLD=0.40` · `compute_verdict_specificity(verdict, state) -> (float, reasons)` với 3 tín hiệu: (a) root_cause có số/service, (b) evidence_summary ≥2 số phân biệt, (c) propagation_note không rỗng + có số/service · `_has_specific_token` · `_count_distinct_numbers` dùng regex `r'\d+(?:[.,]\d+)?'` (bắt cả `5x`, `8ms`, `87%`).
- `engine/state.py`: thêm `Verdict.specificity_score: Optional[float] = None` · `InvestigationState._specificity_gate_fired: bool = False` · filter `_specificity_gate` trong `is_looping()`.
- `engine/loop.py`: thêm `_SPECIFICITY_GATE_NAME = "_specificity_gate"` · `_apply_specificity_gate()` (mirrors competing gate: idempotent, budget-guard, chỉ high/medium) · handler trong `run_tool()` · wiring trong `_run_loop` (v_obj path + vtext path, sau competing gate) · set `verdict.specificity_score` trong finalize + emit trace.
- `engine/graph.py`: wiring `_apply_specificity_gate` sau `_apply_competing_gate` trong `decide_node` (parity loop↔graph).
- `tests/test_e12_specificity.py` (38 tests mới): TestHasSpecificToken (8) · TestCountDistinctNumbers (6) · TestComputeVerdictSpecificity (9) · TestApplySpecificityGate (9) · TestRunToolSpecificityGate (2) · TestSpecificityGateWiringInLoop (2) · TestSpecificityScoreInFinalize (1). Bao gồm integration test xác nhận gate fires on vague → continues → passes on specific.

**Tests:** 221 + 38 = 259/259.

### [Session 49 — 2026-06-15] — Ngày 47: E10 hypothesis-guided tool sequencing

**Đã làm:**
- `engine/loop.py`: thêm `_tool_sequencing_hint(state) -> str` — hàm pure, với mỗi giả thuyết `open` có catalog entry: liệt kê `relevant_tools` chưa xuất hiện trong `tool_call_history`; sort prior_seen_count DESC (E11 synergy); cap ≤3; advisory only.
- `_build_user_message`: nối hint sau budget warning, trước "Bước tiếp theo". Hint cập nhật mỗi bước theo `tool_call_history` thực tế.
- `tests/test_e10_tool_sequencing.py` (21 tests mới): TestToolSequencingHint (14) · TestBuildUserMessageWithHint (4) · TestParity (3).
- Parity loop↔graph **miễn phí** (cả 2 path đều gọi `_build_user_message`).

**Tests:** 200 + 21 = 221/221.

---

**Chốt Phase 9 (đề xuất — chờ xác nhận khi khởi động code):** E11 = pre-seed hypothesis (không chỉ text hint) · E12 = nudge trong loop + downgrade trong multi-agent · Day 49 real-LLM = smoke ~$2 (KHÔNG full N=10) · gate dùng helper chung loop+graph (bài học E7).
**Xương sống KHÔNG cắt:** D46 · D47 (mục A+B) · D48 (mục B) · D50.
**Bất biến:** 100% engine-core · giữ nguyên tắc #2 (tri thức miền trong catalog, không hardcode keyword engine) · regression gate mỗi ngày engine (46–49).

## Nhật ký session (mới nhất lên đầu)

### [Session 54 — 2026-06-15] — Ngày 51: F1 Code seam over MCP

**Đã làm:**
- `src/agent/tools/code_distill.py` (mới): `distill_code_response(raw, *, tool_name, service) -> Observation` — chưng cất raw diff/file/blame/search → Observation hợp lệ P#1 (summary tự diễn giải + ≤5 hunk + aggregates, không raw dump). `_detect_risk_signals()` generic: config-knob (khớp compound name như `max_pool`/`retry_limit`), large-delete, removed-error-handling, dep-bump. Dùng line-by-line scan thay `\b` word boundary để bắt đúng.
- `data/migrate_day51.py` (mới): bảng `service_repos` idempotent — mapping metadata service→repo ngoài (project_id, service, provider, repo_url, default_branch, subpath). KHÔNG lưu source.
- `src/agent/intake/project_registry.py`: thêm CRUD `service_repos` — `list_service_repos` · `get_service_repo` · `upsert_service_repo` (ON CONFLICT upsert, validate provider) · `delete_service_repo`.
- `src/agent/tools/registry.py`: `is_read_only_tool(name) -> bool` — whitelist prefix đọc (get_/list_/read_/search_/fetch_/diff/blame/show) + blacklist write parts (split `_/-`, check từng phần để tránh false positive như `fetch_commits`). `build_tool_registry` lọc tool ghi từ MCP + `logger.warning`.
- `src/agent/dashboard/queries.py`: `get_project_detail` thêm `service_repos` list.
- `src/agent/dashboard/router.py`: 2 routes mới — `POST /projects/{pid}/repos/add` + `POST /projects/{pid}/repos/{service}/delete`.
- `src/agent/dashboard/templates/project_detail.html`: card "Repo / Source" — bảng mapping + form thêm (collapsible details) + nút xóa từng repo.
- `tests/test_code_layer.py` (mới, 52 tests): TestDistillShape (12) · TestRiskDetect (10) · TestReadOnlyGuard (21) · TestServiceReposCRUD (8). Dùng `patch("agent.intake.project_registry.open_db", side_effect=lambda: ...)` (patch đúng target, không phải `agent.storage.db.open_db`).

**Cổng Ngày 51 PASS:**
- `distill_code_response` trả Observation hợp lệ từ raw diff, ≤5 samples, không raw dump, risk signal đúng ✅
- READ-ONLY guard loại `create_pr`/`merge_branch`, giữ `get_diff`/`list_commits`/`fetch_commits` ✅
- `service_repos` CRUD round-trip (temp DB) ✅
- UI card render (project_detail.html) ✅
- Regression: 314/314 tests · eval 4/4 mock · Telegram không đụng (code tool chưa vào catalog mặc định) ✅

**Không làm:** catalog/synergy (D52) · eval/decay (D53) — đúng scope.

### [Session 47 — 2026-06-15] — Lập kế hoạch Phase 9 (Ngày 46–50)

**Bối cảnh:** 45/45 ngày + Phase 8 xong (173/173 tests, Python 3.14). Session này **KHÔNG code** — đọc kỹ toàn bộ engine (`loop.py`, `state.py`, `graph.py`, `multi_agent.py`, `hypothesis_catalog.py`, `calibration.py`, `memory/patterns.py`, `runner.py`, `schema.sql`) để đánh giá + chốt Phase 9. Người dùng yêu cầu: viết Product Brief + đề xuất 3 hướng → chọn cả 3 (E10/E11/E12) → lập plan 5 ngày.

**3 hướng đã chốt (đều engine-core, không cạnh mới):**
- **E10 — Hypothesis-guided tool sequencing:** catalog đã có `relevant_tools` nhưng tri thức này không vào prompt → engine hint "giả thuyết open → tool nào kiểm" vào `_build_user_message`. **Parity loop↔graph miễn phí** (cả 2 path + specialist multi-agent đều gọi `decide_next_action`→`_build_user_message`).
- **E11 — Cross-investigation service prior:** `investigation_patterns` chỉ dùng làm text `warm_start_hint`, chưa seed giả thuyết → pre-seed `Hypothesis` open theo lịch sử service. Lazy `_upsert_hypothesis` lookup theo tag → evidence sau cập nhật lifecycle sạch. Confirm vẫn cần bằng chứng thật (giữ #3).
- **E12 — Verdict specificity gate:** grounding guard (E2) chỉ chặn verdict bịa, không phân biệt mờ/cụ thể → `compute_verdict_specificity` + gate nudge (loop/graph, helper dùng chung — bài học E7) + downgrade (multi-agent, VerdictAgent không loop được).

**Đã làm (3 file, không động code):**
- `docs/14-roadmap-phase-9.md` (mới) — kế hoạch Ngày 46–50, format Làm/Cổng như docs/11–13; bảng kiểm 4 nguyên tắc cho từng hướng; thứ tự cắt nếu hụt giờ.
- `CLAUDE.md` — header giai đoạn + bảng Phase 9 + roadmap pitch (Phase 8 📋→✅, thêm Phase 9) + cấu trúc file (docs/13 đã xong, thêm docs/14).
- `BUILD_STATE.md` — header trạng thái + bảng Tiến độ Phase 9 + entry này.

**Quyết định mặc định (đề xuất — người dùng có thể veto khi khởi động code):**
- E11 = **pre-seed hypothesis** (không chỉ text hint) — mạnh + demo rõ hơn; tận dụng tag-lookup sẵn có.
- E12 = **nudge trong loop + downgrade trong multi-agent** — một metric chung, hai consumer.
- Day 49 real-LLM = **smoke ~$2** (KHÔNG full N=10) — khớp pattern Day 21/38; đây là ngày "chứng minh" giảm bước + nâng specificity (mock không đo được).
- Gate E12 = **helper dùng chung loop+graph** (không viết logic 2 lần — bài học E7).
- Thứ tự ưu tiên rủi ro tăng dần: E11 → E10 → E12.

**Đã sửa (follow-up cùng session):** đồng bộ version Python trong docs hiện-trạng → **3.14**: `CLAUDE.md` (bảng Stack + ghi chú MCP SDK), `README.md` (dòng Stack), `docs/10` (ghi chú MCP SDK + upgrade path). Giữ nguyên các entry nhật ký lịch sử (ghi đúng thời điểm) và file code (đã pin 3.14 ở commit upgrade). `AGENTS.md` đã version-agnostic ("Python" không kèm số) — không cần sửa.

**Chưa làm:** ~~chưa bắt đầu code Ngày 46~~ → đã xong (session 48 bên dưới).

### [Session 48 — 2026-06-15] — Ngày 46: E11 service prior + CVE fix + venv rebuild

**Bối cảnh:** Session này bắt đầu Phase 9 code. Commit trước đó là plan + Python docs sync. Người dùng yêu cầu commit plan, gộp CVE task vào Ngày 46, bắt đầu code.

**E11 service prior — đã làm:**
- `hypothesis_catalog.py`: thêm field `root_cause_type: str = ""` vào `HypothesisCatalogEntry`; gán đầy đủ cho mọi entry microservice + fintech; thêm helper `build_rct_index(catalog)` → `{root_cause_type → entry}`.
- `state.py`: thêm `prior_seen_count: int = 0` vào `Hypothesis`; cập nhật `summarize_for_llm()` → hiện `[prior: gặp N lần]` khi N>0.
- `memory/patterns.py`: thêm `get_service_priors(project_id, service, *, limit=3)` trả top-N từ `investigation_patterns` sorted by count DESC (bỏ `unknown`); mở rộng `_classify_root_cause` bao phủ fintech (processor_timeout · price_configuration_error · merchant_fraud · settlement_lag · latency_spike · timeout generic).
- `engine/loop.py`: thêm `_preseed_hypotheses(project_id, service, rct_index)` — hàm pure, tạo `Hypothesis(id=catalog.tag, prior_seen_count=count)`; thêm `service: Optional[str]` vào `InvestigationEngine.run()`; pre-seed vào `state.hypotheses` trước loop; build `self._rct_index` trong `__init__`.
- `engine/multi_agent.py`: thêm `service: Optional[str]` vào `run()` và `_run_specialist()`; thread xuống `engine.run()`.
- `intake/runner.py`: pass `service=req.service` vào `engine_obj.run()`.

**CVE fix:**
- `pyproject.toml`: `python-multipart>=0.0.9` → `>=0.0.27`; thêm `starlette>=0.50.0`; `fastapi>=0.100.0` → `>=0.115.0`.
- Rebuild `.venv` bằng `python3 -m venv .venv --clear` (Python 3.14.6).
- Kết quả: python-multipart 0.0.32 · starlette 1.3.1 · fastapi 0.137.0.

**Tests:** 200/200 (173 cũ + 27 mới trong `tests/test_e11_service_prior.py`):
- TestCatalogRootCauseType (5): root_cause_type đầy đủ + không trùng + mapping đúng
- TestClassifyRootCause (10): microservice + fintech types
- TestGetServicePriors (5): sort · filter unknown · limit · DB error
- TestPreseedHypotheses (5): empty service · no data · prior_seen_count · skip unknown · multiple
- TestEnginePreseedIntegration (2): pre-seed xuất hiện trong state · không pre-seed khi DB trống

**Kiến trúc:** `_upsert_hypothesis` lookup theo `tag` (h.id == tag) → hypothesis pre-seed với `id=catalog.tag` sẽ được cập nhật lifecycle `open→confirmed/ruled_out` bởi evidence sau một cách **tự động, không cần code đặc biệt**. ✓ Principle #3 (confirm vẫn cần bằng chứng thật, prior chỉ đổi thứ tự khám phá). ✓ Principle #2 (mapping `root_cause_type↔tag` nằm trong catalog, engine đọc via `build_rct_index`).

### [Session 46 — 2026-06-15] — Ngày 45: Hardening + Cổng Phase 8

**Ngày 45 — Security audit + đóng pha:**
- `src/agent/intake/server.py` — thêm startup warning khi `SESSION_SECRET_KEY` dùng dev fallback; thêm startup warning khi `SECRET_KEY` không set (plaintext at-rest)
- `.env.example` — thêm `SESSION_SECRET_KEY` với comment + lệnh tạo key
- **Dependency audit (pip-audit):**
  - `python-multipart 0.0.20` — 3 CVE (path traversal + 2 DoS); fix ≥0.0.27 yêu cầu Python 3.10+ — **không thể fix trên Python 3.9** (ghi nhận là known limitation)
  - `starlette 0.49.3` — PYSEC-2026-161 (Host header injection); fix ≥0.50.0 yêu cầu Python 3.10+ — **không thể fix trên Python 3.9**
  - `requests`, `setuptools`, `urllib3` — CVEs không ảnh hưởng đến runtime của project này
  - Các package runtime chính (`anthropic 0.109.1`, `cryptography 49.0.0`, `fastapi 0.128.8`) — không có CVE
- `.gitignore` đã cover `.env`, `.env.*` ✅
- Không có secret thật trong tracked files ✅
- `ALLOW_ANON_TRIGGER` mặc định `false` ✅

**Cổng Phase 8 — PASS:**
- Engine domain-agnostic (E6): hypothesis catalog theo miền, fintech có hypothesis lifecycle thật ✅
- Parity (E7): loop ↔ graph cùng verdict; multi-agent ngang hàng (grounding+conflict+merge) ✅
- Calibration đóng vòng (E8): engine tự hạ confidence khi historical accuracy < threshold; before/after trên dashboard ✅
- CI xanh (T2): GitHub Actions pytest + mock eval + syntax + import check ✅
- Test phủ adapters/output/infra/contract (T1): 173/173 tests ✅
- Cost giảm đo được (P1): prompt caching hooked, before/after trên cost dashboard ✅
- Structured verdict (E9): submit_verdict args → Verdict trực tiếp, parse_degraded flag ✅
- DX (D44): README.md + docs/api.md + Makefile aliases ✅
- Regression: eval 4/4 + 173 tests PASS ✅
- Security: startup warnings, .gitignore, no plaintext secrets in repo ✅

**Ngày 45 — Bổ sung: Nâng cấp Python 3.9 → 3.14 ✅ HOÀN TẤT**
- **Config/CI đã pin 3.14**: `pyproject.toml` (requires-python ≥3.14 + ruff py314) · `Dockerfile` (3.14-slim) · `ci.yml` · `eval.yml`
- **5 `asyncio.get_event_loop()` → `get_running_loop()`**: `loop.py:368` · `email.py:192` · `sse.py:26` · `sse_backends.py:61` · `router.py:788`
- **4 sync test methods → `async def`**: `test_adapters.py:397,431,499,532` (Slack/Teams/Callback/Email push tests)
- **Makefile**: venv path → `.venv314`, install cmd → `python3.14 -m venv .venv314`
- **Deps**: pydantic-core + cryptography wheel 3.14 tồn tại — `pip install -e ".[dev]"` thành công
- **Bonus fixes** (`router.py:788` cũng dùng `get_event_loop` — fixed cùng lúc)
- **Cổng**: 173/173 tests PASS trên Python 3.14.6 · không có known DeprecationWarning asyncio

### [Session 45 — 2026-06-15] — Ngày 44: DX + docs

**Ngày 44 — DX + docs:**
- `README.md` (mới, root) — what/why · sơ đồ kiến trúc 4 cạnh ASCII · quickstart 5 bước · bảng `make` targets · bảng kịch bản demo · cấu trúc file · link docs · 4 nguyên tắc kiến trúc
- `docs/api.md` (mới) — API reference đầy đủ gộp tất cả route thật: Auth · Core (trigger/health/adapters) · Projects (CRUD/services/channels/LLM/MCP scoped) · Dashboard (investigations/operations/config/analytics/admin/scheduler) · Intake Adapters webhook guide · Webhook signature HMAC
- `Makefile` — thêm alias `init` (→ `db`) và `run` (→ `server`); cập nhật `.PHONY` + help text

**Cổng Ngày 44:**
- `make init` ✅ (alias → db + migrations)
- `make run --dry-run` → `python3 scripts/start_server.py --port 8000` ✅
- `make test` → 173/173 PASS ✅
- `make eval` → CỔNG EVAL 4/4 PASS ✅
- README.md có ở root, docs/api.md cover toàn bộ route thật

### [Session 44 — 2026-06-15] — Ngày 43: E9 Structured verdict direct path

**Ngày 43 — E9: Structured verdict đường thẳng:**
- `src/agent/engine/state.py` — thêm `parse_degraded: bool = False` vào `Verdict`
- `src/agent/engine/loop.py`:
  - Thêm `_args_to_verdict(args: dict) -> Verdict` — build Verdict trực tiếp từ `submit_verdict` tool args (không qua text round-trip)
  - `_apply_competing_gate` — thêm `conf_override: Optional[str]` kwarg (E9 structured path truyền confidence trực tiếp)
  - `decide_next_action` — đổi thành 4-tuple `(tool_call, vtext, llm_resp, verdict_obj)`; structured path: `return None, None, response, _args_to_verdict(tc.arguments)`
  - `_run_loop` — unpack 4-tuple, handle `verdict_obj` path với gate check, return 3-tuple `(state, vtext, verdict_obj)`
  - `_run_with_graph` — return 3-tuple `(state, vtext, verdict_obj)`, include `verdict_obj` trong `initial` dict
  - `run()` finalization — ưu tiên `verdict_obj` (không qua `_parse_verdict`); fallback text-parse → `parse_degraded = True`; cả hai path vẫn qua `_check_evidence_grounding` + `apply_calibration`
  - Emit `parse_degraded` trong verdict trace event
- `src/agent/engine/graph.py`:
  - `LoopState` — thêm `verdict_obj: Optional[Any]`
  - `decide_node` — unpack 4-tuple, xử lý `v_obj is not None` (E9 path), emit `verdict_obj` trong return dict
  - `_route_after_decide` — check `state.get("verdict_obj") is not None` như điều kiện END

**Cổng Ngày 43:**
- 173/173 tests PASS (7 tests mới E9)
- Eval gate: 4/4 PASS (12/12 runs, 100%)
- `_args_to_verdict` build đúng tất cả field; `parse_degraded=False` trên structured path
- `decide_next_action` structured path: `vtext=None`, `verdict_obj` có giá trị (không qua text)
- `_parse_verdict` KHÔNG được gọi khi real LLM dùng `submit_verdict` tool
- MockLLM (text fallback) vẫn hoạt động → `parse_degraded=True` đúng

### [Session 43 — 2026-06-15] — Ngày 42: P1 Prompt caching + context trim

**Ngày 42 — P1: Cost + perf:**
- `src/agent/llm/anthropic.py` — `cache_control: {"type": "ephemeral"}` trên system (ổn định) + last tool (stable per investigation); capture `cache_creation_input_tokens` + `cache_read_input_tokens` trong usage dict
- `src/agent/engine/state.py` — thêm `cache_creation_tokens: int = 0` + `cache_read_tokens: int = 0` vào `InvestigationState`; `summarize_for_llm` capped: hypotheses tối đa 6 (open/confirmed ưu tiên, chỉ 2 ruled_out gần nhất), evidence/hypothesis tối đa 2 ref gần nhất
- `src/agent/engine/loop.py` — accumulate `cache_creation_tokens` + `cache_read_tokens` từ `llm_resp.usage`; thêm cả 2 field vào verdict trace event payload
- `src/agent/engine/multi_agent.py` — tương tự: accumulate + emit trong verdict; merge các specialist state
- `src/agent/dashboard/queries.py` — thêm cache query trong `get_cost_data()`: `cache_reads`, `cache_writes`, `cache_savings_usd`, `cache_extra_cost`, `cache_net_savings`
- `src/agent/dashboard/templates/cost.html` — thêm "P1 — Prompt Caching before→after" section: 4 stat cards + before/after comparison table + note

**Cổng Ngày 42:**
- 166/166 tests PASS (regression OK)
- Eval gate: 4/4 PASS (12/12 runs, 100%)
- `get_cost_data()` trả đủ cache fields (0 khi mock, thật khi có ANTHROPIC_API_KEY + real LLM investigation)
- Template render không lỗi; "before/after" section hiển thị đúng khi cache_reads/writes > 0
- Prompt caching silently no-op khi prefix < minimum (API ignores cache_control gracefully)

### [Session 42 — 2026-06-15] — Ngày 41: T2 CI gate tự động

**Ngày 41 — T2: CI gate:**
- `.github/workflows/ci.yml` (mới) — 6 bước: checkout → setup-python 3.9 + pip cache → install `.[dev]` → syntax check (107 .py) → import check → init DB + seed → pytest -q → coverage report (continue-on-error) → eval gate 4/4
- `scripts/eval_agent.py` — thêm `sys.exit(1)` khi gate fail (`all_pass=False`) → CI đỏ đúng
- `pyproject.toml` — thêm `pytest-cov>=4.0.0` vào dev deps
- `Makefile` — thêm `test` (pytest -q) và `ci` (test + eval gate) targets; cập nhật `.PHONY` và help

**Cổng Ngày 41:**
- Syntax check: 107 files OK
- Core imports: 7 module OK
- pytest: 166/166 PASS
- Coverage report: 29% tổng (display only, không có threshold)
- Eval gate: 4/4 PASS (12/12 runs đúng, 100%)
- Exit code 1 khi gate fail: xác nhận ✅

### [Session 41 — 2026-06-15] — Ngày 38–40: E8 calibration + T1 adapter/infra tests

**Ngày 38 — E8: Calibration closure:**
- `src/agent/engine/calibration.py` (mới) — `CALIBRATION_THRESHOLDS` · `load_calibration_stats()` (5-min TTL cache) · `get_calibration_adjustment()` · `apply_calibration()` · `get_calibration_summary()` · `invalidate_cache()`
- `src/agent/engine/state.py` — thêm `calibrated_confidence: Optional[str]` vào `Verdict`
- `src/agent/engine/loop.py` + `multi_agent.py` — hook `apply_calibration(state.verdict)` sau `_check_evidence_grounding`
- `src/agent/dashboard/router.py` + `eval.html` — E8 calibration before/after table
- `scripts/eval_agent.py` — `invalidate_cache()` sau khi save eval results
- Smoke thật ($2): SKIP — ANTHROPIC_API_KEY chưa set; calibration logic test đầy đủ bằng seeded DB
- `tests/test_calibration.py` (mới, 18 tests): TestGetCalibrationAdjustment · TestApplyCalibration · TestLoadCalibrationStats · TestCalibrationPipeline

**Ngày 39 — T1: Test adapters + output:**
- `tests/test_adapters.py` (mới, 46 tests): 7 intake adapters (Prometheus/Grafana/Sentry/PagerDuty/OpsGenie/GitHub/GitLab) + router + 5 output renderers (Slack/Teams/Telegram/Callback/Email)
- Pattern: happy path · non-trigger→None · malformed→no crash (intake) · shape validation · graceful without URL (output)

**Ngày 40 — T1: Test infra + contract guard:**
- `tests/test_infra.py` (mới, 27 tests): TestInvestigationQueue (4) · TestSchedulerCRUD (3) · TestProjectRegistryCRUD (4) · TestMCPRegistryCRUD (3) · TestCrypto (7) · TestContractGuard (6)
- `validate_observation()` contract guard enforce Nguyên tắc #1
- **Bug fix:** `src/agent/intake/scheduler.py::_build_request()` thiếu `raw_payload={}` → `InvestigationRequest.__init__()` error khi fire scheduled trigger — đã sửa

**Cổng Ngày 38–40:**
- **166/166 tests PASS** (75 cũ + 18 calibration + 46 adapters + 27 infra)
- Contract guard bắt được violation (>5 samples, empty summary, null total_count)
- Tất cả local tools (`get_error_breakdown`, `get_metrics`, `get_recent_deploys`, `get_dependencies`) pass contract guard

### [Session 40 — 2026-06-15] — Ngày 36–37: E6 domain-agnostic catalog + E7 unified stop/parity

**Bối cảnh:** Phase 8 khởi động. Tiếp tục từ context tóm tắt — code engine đã xong, chỉ cần thêm tests + verify gates.

**Ngày 36 — E6: Engine domain-agnostic:**
- `src/agent/engine/hypothesis_catalog.py` (mới) — `HypothesisCatalogEntry` dataclass · `MICROSERVICE_CATALOG` (5 entries, di chuyển từ `_HYPOTHESIS_RELEVANCE`) · `FINTECH_CATALOG` (4 entries: processor_timeout, price_configuration_error, merchant_fraud, settlement_lag) · `get_default_catalog()` · `build_catalog_index()`
- `src/agent/engine/state.py` — thêm `hypothesis_catalog_index: dict` vào `InvestigationState`
- `src/agent/engine/loop.py` — xóa `_HYPOTHESIS_RELEVANCE` hardcode · `_update_hypotheses` catalog-driven (load từ `state.hypothesis_catalog_index`, fallback MICROSERVICE nếu rỗng) · `InvestigationEngine.__init__` nhận `hypothesis_catalog=None`, build index · `.run()` set `state.hypothesis_catalog_index`
- `src/agent/intake/runner.py` — detect `domain`, gọi `get_default_catalog(domain)`, truyền `hypothesis_catalog` xuống cả hai engine

**Ngày 37 — E7: Unified stop conditions + multi-agent parity:**
- `src/agent/engine/loop.py` — `_check_stop_conditions(state)` helper dùng chung (budget check + loop detection) với đầy đủ side-effect (set `stop_reason`, `finished`, return verdict text)
- `src/agent/engine/graph.py` — `decide_node` thay inline stop logic bằng import `_check_stop_conditions` từ loop
- `src/agent/engine/multi_agent.py` — `__init__` nhận `hypothesis_catalog` · `_run_specialist` truyền catalog xuống · `_merge_states` dedup hypotheses theo content (prefer confirmed > open; tiebreak confidence > evidence count; merge evidence_ids) · `_synthesize_verdict` thêm `resolve_conflicting_hypotheses()` + conflict annotation (ngang hàng single-agent)

**Tests (Ngày 36+37) — thêm 12 tests:**
- `TestHypothesisCatalog` (6): microservice deploy confirmed/ruled_out · fintech processor_timeout confirmed · fintech price_bug confirmed · no anomaly → ruled_out · empty catalog no crash
- `TestStopConditionsShared` (4): budget exhausted → verdict text + side-effects · not exhausted → None · loop detected → verdict text · both false → None
- `TestMultiAgentParity` (2): merge prefers confirmed hypothesis · conflict resolution returns correct winner

**Cổng Ngày 36–37:**
- 75/75 tests PASS (63 cũ + 12 mới)
- eval 4/4 PASS (mock, regression OK)
- Engine không còn hardcode domain keyword (`_HYPOTHESIS_RELEVANCE` đã xóa hoàn toàn)
- LangGraph `decide_node` và `_run_loop` dùng chung `_check_stop_conditions` — parity đảm bảo về cấu trúc

### [Session 39 — 2026-06-15] — Lập kế hoạch Phase 8 (Ngày 36–45)

**Bối cảnh:** 35/35 ngày + Phase 7 xong (63/63 tests). Session này KHÔNG code — đọc toàn bộ trạng thái + **đọc kỹ code engine** (`loop.py`, `state.py`, `graph.py`, `multi_agent.py`) để đánh giá khách quan sau 7 phase → tổng hợp + chốt Phase 8.

**Phát hiện chính (cơ sở Phase 8):**
- **E6 (nghiêm trọng):** vòng đời giả thuyết **hardcode theo miền microservice + keyword tiếng Việt** (`loop.py:_HYPOTHESIS_RELEVANCE` 5 tag + `_update_hypotheses` match chuỗi). Tool fintech (`get_revenue_breakdown`…) không khớp tag nào → **fintech investigation có 0 hypothesis** → cổng cạnh tranh E4 không kích hoạt cho fintech. Engine nuốt domain knowledge — **vi phạm ngầm nguyên tắc #2**.
- **E7:** 2 đường engine trùng logic stop/gate (`_run_loop` ↔ `decide_node`); multi-agent `_synthesize_verdict` thiếu competing gate + `resolve_conflicting_hypotheses` (Ngày 33 chỉ thêm vào `InvestigationEngine.run`); merge dedup-content-string ngây thơ.
- **E8:** real-LLM eval chỉ smoke 6/6 một lần; calibration (E3) chỉ hiển thị dashboard, chưa feed ngược vào engine.
- **E9:** structured verdict đi vòng args→text→parse (`_structured_args_to_verdict_text` → `_parse_verdict`).
- **T1/T2:** 63 test chỉ phủ engine_core/auth/tools — thiếu 8 adapter, 5 output, queue, scheduler, multi-agent, graph, registry, crypto; không có CI.
- **P1/P2:** không dùng prompt caching (~$0.17/run); nguyên tắc #1 (chống raw rows) không enforce bằng máy.

**Đã làm (4 file, không động code):**
- `docs/13-roadmap-phase-8.md` (mới) — kế hoạch Ngày 36–45, format Làm/Cổng như docs/11–12. Engine-quality round 2 + test/CI + cost/DX.
- `CLAUDE.md` — header giai đoạn + bảng Phase 8 + roadmap pitch + cấu trúc file (docs/13).
- `BUILD_STATE.md` — header trạng thái + bảng Tiến độ Phase 8 + entry này.

**Quyết định chốt (qua AskUserQuestion):**
- **Day 38 real-LLM eval = SMOKE MỞ RỘNG (~$2)** — KHÔNG full N=10 (~$10). Khớp pattern tiết kiệm đã chọn ở Day 21.
- **Horizontal scale seam → vẫn Future** — giữ in-memory single-process, Redis SSE giữ stub (tránh over-engineer khi chưa có nhu cầu multi-instance thật).
- **Tier-2 Postgres · bidirectional output → vẫn Future** (như Phase 6).

**Chưa làm:** chưa bắt đầu code Ngày 36 (chờ session sau xác nhận khởi động).

### [Session 31 — 2026-06-14] — Lập kế hoạch Phase 6 (Ngày 26–30)

**Bối cảnh:** 25/25 ngày + Phase 5 xong. Session này KHÔNG code — đọc toàn bộ trạng thái + **đọc kỹ code engine** (`loop.py`, `graph.py`, `state.py`, `multi_agent.py`, `contracts.py`) theo yêu cầu "cải thiện engine" → đánh giá đề xuất A/B/C/D + chốt Phase 6.

**Phát hiện chính (cơ sở Nhóm E — engine quality):** danh sách đề xuất A–D của người dùng gần như KHÔNG chạm engine core (chỉ D1/D2 engine-adjacent). Đọc code xác nhận 5 điểm yếu engine có thật:
- **E1:** `Hypothesis` luôn `open`, `confidence` không bao giờ set, mọi evidence append vào mọi hypothesis → "loại trừ giả thuyết cạnh tranh" chỉ là decorative (`loop.py:_update_hypotheses`, `state.py:add_hypothesis`).
- **E2:** verdict nhận ngay khi thấy chữ "VERDICT", không kiểm neo bằng chứng (`loop.py` decide / `graph.py:decide_node`).
- **E3:** confidence LLM tự khai, parse text, default `medium` âm thầm (`loop.py:_parse_verdict`).
- **E4:** `is_looping()` chỉ bắt 2 call liên tiếp giống hệt; step budget cứng = 10; không cổng dừng (`state.py:is_looping`).
- **E5:** parse verdict mong manh (prefix tiếng Việt từng dòng).

**Đã làm (3 file):**
- `docs/12-roadmap-phase-6.md` (mới) — kế hoạch Ngày 26–30, format Làm/Cổng như docs/11. Engine-first 2+2+1.
- `CLAUDE.md` — "Giai đoạn hiện tại" thêm Phase 6 (bảng + Cổng + tham chiếu doc); cập nhật roadmap pitch + Future; thêm docs/11+12 vào cấu trúc file.
- `BUILD_STATE.md` — header trạng thái + bảng Tiến độ Phase 6 + entry này.

**Quyết định chốt (qua AskUserQuestion với người dùng):**
- **Cấu trúc engine-first 2+2+1:** D26–27 engine (Nhóm E + calibration + baseline) · D28–29 production hardening (auth/secret/queue/shutdown) · D30 ecosystem + Cổng.
- **Tier-2 Postgres (B1) → Future** (runtime vẫn SQLite; seam Tier-1 đã đủ; migration thật cần env + lệnh rõ).
- **Bidirectional output (C2) → Future** (giữ ranh giới READ-ONLY; cần duyệt rõ mới làm).
- **3 P0:** engine quality (D26–27) · webhook auth + secret at-rest (D28) · graceful shutdown + queue (D29).
- **Regression gate bắt buộc cho ngày engine** (26–27): eval 4/4 + 2 KB end-to-end + Telegram không vỡ.

### [Session 38 — 2026-06-15] — Ngày 32–35: Phase 7 hoàn tất

**Ngày 32 — Proactive monitoring:**
- `data/migrate_day32.py` — CREATE TABLE `scheduled_triggers` + ADD COLUMN `investigation_patterns.alerted_at`
- `src/agent/intake/scheduler.py` — asyncio 60s tick: fire due triggers → enqueue; check recurring patterns → push Telegram/Slack
- `dashboard/router.py` — 4 CRUD routes `/dashboard/scheduled`
- `templates/scheduled.html` — UI table + create form
- `base.html` — nav link ⏱ Scheduled trong nhóm Cấu hình
- `.env.example` — `RECURRING_ALERT_THRESHOLD=5`

**Ngày 33 — Engine depth:**
- `state.py:resolve_conflicting_hypotheses()` — winner = highest confidence + evidence count tiebreaker
- `loop.py` — annotate `verdict.competing_hypotheses` khi 2+ hypothesis confirmed
- `patterns.py` — D2: `save_pattern` cũng lưu medium confidence (không chỉ high)
- `tests/test_auth.py` — 20 unit tests RBAC (user CRUD, API token, role/perm, user_can)
- `tests/test_engine_core.py` — +5 tests conflict resolution → 29 tests total
- **50/50 PASS**

**Ngày 34 — Docker + Investigation export + Tool tests:**
- `Dockerfile` + `docker-compose.yml` + `.dockerignore`
- `router.py:investigation_export` — GET `/investigations/{id}/export?format=json|csv`
- `detail.html` — nút ↓ JSON và ↓ CSV trong header
- `tests/test_tools.py` — 13 unit tests `get_metrics` + `get_error_breakdown`
- **63/63 PASS**

**Ngày 35 — Production bridge + Phase 7 gate:**
- `src/agent/dashboard/sse_backends.py` — Redis SSE seam: `SSEBroker` protocol + `InMemorySSEBroker` + `RedisSSEBrokerStub` + `get_sse_broker()` factory
- `.env.example` — `SSE_BACKEND=memory`, `REDIS_URL=...`
- **Phase 7 Gate PASS:** 63/63 tests · syntax 76 files · imports OK · engine smoke HIGH verdict · Docker files · SSE broker factory

### [Session 37 — 2026-06-15] — Ngày 31: Quick wins + Test skeleton

**A. Bug fix: Demo 401**
- `server.py:_handle_trigger_request()` — thêm fallback session auth: nếu không có `X-API-Token` header, kiểm `request.session.get("user_id")`. User đã đăng nhập dashboard (session cookie hợp lệ) được phép trigger mà không cần token. External webhook không có cookie → vẫn cần token. Logic không thay đổi cho anonymous trigger (ALLOW_ANON_TRIGGER env).

**B. C3 — GitHub/GitLab deploy hook adapter:**
- `adapters/github.py` (mới) — parse `X-GitHub-Event: push` (ref main/master/prod) và `deployment` (action=created). Infer service từ repo name, scenario từ commit message keywords. Non-trigger events → None.
- `adapters/gitlab.py` (mới) — parse `X-Gitlab-Event: Push Hook` và `Pipeline Hook` (status=failed). GitLab timestamp format `"2024-01-15 14:03:00 UTC"` → chuẩn hóa trước khi parse.
- `server.py:_handle_trigger_request()` — inject `_event_type` vào payload (từ `X-GitHub-Event` / `X-Gitlab-Event` header) trước khi route → adapter đọc được mà không thay đổi interface `_ADAPTERS`.
- `adapters/__init__.py` — đăng ký `github` và `gitlab`.

**C. Test skeleton:**
- `tests/conftest.py` — fixtures: `sample_state`, `sample_observation`, `sample_verdict`.
- `tests/test_engine_core.py` — 24 unit tests: hypothesis lifecycle (4) · competing_open (4) · loop oscillation detection (6) · evidence-grounding guard (4) · structured verdict text (3) · evidence linking (3).
- **24/24 PASS** (0.03s)

**Cổng Ngày 31 ✅ PASS:**
- Demo page trigger hoạt động với session auth (không cần API token) ✅
- C3: GitHub push → service=payment-gateway · GitHub deployment → scenario1 · GitLab push → infer đúng · GitLab pipeline → service/window đúng · Non-trigger → None ✅
- pytest 24/24 PASS ✅
- Regression eval 4/4 mock PASS ✅

### [Session 36 — 2026-06-15] — Ngày 30: Ecosystem + Close (Cổng Phase 6)

**F2 — Fix nav Admin group ẩn khi click API Tokens:**
- `router.py:admin_tokens_page` — thêm `_ctx()` wrapper, truyền `current_user` và `active='admin_tokens'` vào template. Trước đây dùng dict thuần → `current_user` không có → nhóm Admin không render.

**F1 — Đồng bộ theme Demo với dashboard:**
- `demo.html` — bỏ `body { background: #0a0c14; }` hardcode. Thêm inline script ngay sau `<body>`: đọc `localStorage ia-theme` (default `'light'`), áp `theme-light` class lên `document.body` đồng bộ trước render → không flash.

**C1 — PagerDuty/OpsGenie intake adapter:**
- `src/agent/intake/adapters/pagerduty.py` (mới) — xử lý v2 format (`messages[].incident`) và v3 format; chỉ trigger events; infer scenario từ title keywords.
- `src/agent/intake/adapters/opsgenie.py` (mới) — xử lý action Create; timestamp từ milliseconds epoch; scenario từ `details.scenario` hoặc tags hoặc infer từ message.
- `adapters/__init__.py` — đăng ký `pagerduty` và `opsgenie` vào `_ADAPTERS`.

**C4 — Webhook callback outbound:**
- `src/agent/output/callback.py` (mới) — `push_callback(state, callback_url)`: POST verdict structured JSON; `_build_callback_payload()` tạo dict: investigation_id, project_id, scenario, verdict (root_cause, confidence, evidence_summary, propagation, speculative).
- `runner.py:run_investigation_background()` — sau `push_verdict()`, check `req.raw_payload.get('callback_url')` → gọi `push_callback()`.

**D3 — Root cause clustering:**
- `queries.py:get_recurring_incidents(project_id, threshold=2)` — query `investigation_patterns WHERE count >= threshold ORDER BY count DESC`. Tái dùng bảng đã có từ D12.
- `router.py:/health` — gọi `get_recurring_incidents()`, pass `recurring_incidents` vào template.
- `health.html` — thêm card "Recurring Incidents": bảng root_cause_type · service · project · count (badge màu) · avg_steps · updated_at. Badge ⚠️ khi count ≥ 5.

**Cổng Phase 6 ✅ PASS:**
- F2: `_ctx()` trong admin/tokens route ✅
- F1: localStorage theme sync, không hardcode dark ✅
- C1: PagerDuty parse service+scenario ✅; OpsGenie parse ms-epoch timestamp ✅; non-trigger/non-Create → None ✅; cả 2 đăng ký trong router ✅
- C4: callback payload đúng cấu trúc ✅; runner wire callback_url ✅
- D3: `get_recurring_incidents()` query đúng ✅; health route + template render ✅
- Regression: 4/4 mock eval PASS ✅

**C3 (GitHub/GitLab deploy hook) — bỏ khỏi scope theo yêu cầu người dùng → defer Future.**

### [Session 35 — 2026-06-15] — Ngày 29: Reliability Infra + UI Polish

**A. B3 — Investigation queue (thay fire-and-forget):**
- `data/migrate_projects.py` — thêm bảng `investigation_queue` (id, project_id, payload, status, enqueued_at, started_at) + index.
- `src/agent/intake/investigation_queue.py` (mới) — module quản lý queue:
  - `start_workers()`: khởi tạo `asyncio.Queue` + 3 worker tasks.
  - `enqueue(req)`: persist row vào SQLite (INSERT OR IGNORE) rồi `put_nowait()` vào memory queue.
  - `drain_and_stop(timeout=60s)`: set `_draining=True`, đợi `_queue.join()`, cancel workers.
  - `_reload_pending()`: crash recovery — reset rows status='running'→'pending', reload vào queue khi khởi động.
  - Worker loop: poll với timeout 0.5s, check `_draining`, gọi `run_investigation_background()`, cập nhật DB status.
- `runner.py:trigger_investigation()`: không còn `asyncio.create_task()` — gọi `enqueue()` từ queue module; fallback fire-and-forget nếu queue chưa start (test/CI).

**B. A1 — Graceful shutdown:**
- `server.py:lifespan()`: sau `yield`, gọi `drain_and_stop(timeout=60s)` → log "Queue drained".
- `server.py:_do_trigger()`: kiểm `is_draining()` trước khi nhận trigger → 503 khi đang shutdown.
- `investigation_queue.py:start_workers()`: gọi trong lifespan trước `yield`.

**C. B4 — Rate limiting (per-project, in-memory):**
- `server.py`: thêm `_rate_windows` (defaultdict, sliding window 1h) + `_check_rate_limit(project_id)`.
- `_do_trigger()`: sau dedup check, gọi `_check_rate_limit()` → 429 khi vượt `INVESTIGATION_RATE_LIMIT` (default 20/h).
- `.env.example`: thêm `INVESTIGATION_RATE_LIMIT=20`.

**D. UI — Sidebar grouping theo chức năng:**
- `base.html`: 11 link phẳng → 4 nhóm: **Điều tra** (Investigations, Trigger, Chat, Demo) · **Cấu hình** (Projects, MCP, Channels, Tools) · **Quan sát** (Health, Cost, Eval, Metrics Live) · **Admin** (Users & Roles, API Tokens, API Docs).
- `style.css`: thêm `.nav-group-label` (uppercase, muted, letter-spacing).
- Logo: v0.8→v0.9 · Phase 5→Phase 6.

**E. UI — Default theme Light mode:**
- `base.html`: đổi `|| 'dark'` → `|| 'light'` ở cả `toggleTheme()` và IIFE apply. Người dùng chưa set localStorage → mặc định light.

**Verify (cổng Ngày 29):**
- B3: `investigation_queue` table tồn tại ✅; worker count=3 ✅; crash recovery reset running→pending ✅; bad payload skipped gracefully ✅
- B4: rate limit chặn request thứ 4 khi limit=3 ✅; 429 path exists ✅
- A1: `is_draining()` check trong `_do_trigger` ✅; `drain_and_stop` trong lifespan ✅; `start_workers` trước yield ✅
- D+E: nav-group-label trong HTML ✅; 4 nhóm ngữ nghĩa ✅; default `'light'` ✅

**Cổng Ngày 29 ✅ PASS**

**Quyết định lệch:**
- `ConcurrencyLimiter` từ D16 không dùng lại trong queue worker (worker tự block khi `asyncio.wait_for` timeout rồi re-check `_draining`). Thiết kế đơn giản hơn, đủ cho 3 workers cố định không cần semaphore riêng.
- Rate limit in-memory (không persist DB) — đủ cho 1 process; restart sẽ reset window, chấp nhận được.

### [Session 34 — 2026-06-15] — Ngày 28: Security + Custom LLM

**A. A4 — API token auth cho /trigger:**
- `server.py` — thêm `_allow_anon_trigger()` helper (đọc `ALLOW_ANON_TRIGGER` env); `_handle_trigger_request()` kiểm `X-API-Token` / `X-API-Key` header trước khi xử lý request; gọi `verify_token()` từ `agent.auth.rbac`; return 401 nếu thiếu/sai token (trừ khi `ALLOW_ANON_TRIGGER=true`).
- `rbac.py` — thêm `list_all_tokens()` (admin view: tất cả tokens kèm username JOIN).
- `router.py` — thêm 3 routes: `GET /admin/tokens`, `POST /admin/tokens`, `POST /admin/tokens/{id}/revoke`.
- `templates/admin_tokens.html` — trang mới: form tạo token (chọn user + tên) · bảng tokens hiện có · flash banner token mới tạo (show once) · hướng dẫn curl example.
- `base.html` — thêm link "🔑 API Tokens" dưới mục Admin.

**B. A2 — Secret at-rest (Fernet):**
- `src/agent/security/crypto.py` + `__init__.py` (mới) — `encrypt_secret()` / `decrypt_secret()` / `is_encrypted()`; key derivation SHA256(SECRET_KEY) → Fernet; backward compat plaintext pass-through; idempotent (đã encrypt thì không encrypt lại).
- `project_registry.py:get_project_llm()` + `set_project_llm()` — decrypt/encrypt `llm_config` at seam.
- `mcp_registry.py:add_server()` + `get_enabled_servers()` — encrypt/decrypt `auth_config` khi auth_type != none.
- `project_registry.py` — thêm `clear_project_llm()` (xóa override, set NULL trong DB).

**C. A3 — Trace retention purge on startup:**
- `server.py:lifespan()` — xóa `trace_events WHERE created_at < cutoff`; `TRACE_RETENTION_DAYS` env (default 30); log số rows purged.

**D. Per-project LLM endpoint UI (last mile):**
- `llm/anthropic.py` — `AnthropicClient.__init__()` nhận `base_url` + `default_headers`, truyền vào `AsyncAnthropic(**kwargs)`.
- `llm/openai_compat.py` — `OpenAICompatibleClient.__init__()` nhận `default_headers`, truyền vào `AsyncOpenAI(**kwargs)`.
- `llm/factory.py` — `create_llm_client()` đọc `extra_config`: truyền `api_key`/`base_url`/`headers` cho cả anthropic + openai-compat providers.
- `dashboard/queries.py:get_project_detail()` — thêm `llm_config_raw` (decrypt + json.loads) vào returned dict.
- `templates/project_detail.html` — LLM Config card: thêm `<details>` collapsible form (provider, model, base_url, api_key, headers JSON); nút "Lưu" + "Xóa override".
- `dashboard/router.py:POST /projects/{pid}/llm` — route mới guard `require_perm("llm.manage")`; validate provider; gọi `set_project_llm()` hoặc `clear_project_llm()`; hiển thị lại project_detail với flash status.
- `.env.example` — thêm `SECRET_KEY=`, `ALLOW_ANON_TRIGGER=false`, `TRACE_RETENTION_DAYS=30`.

**Verify (cổng Ngày 28):**
- A4: `_allow_anon_trigger()` đọc env đúng ✅; `verify_token()` trả None cho token không tồn tại ✅; `/admin/tokens` + `/admin/tokens/{id}/revoke` routes registered ✅
- A2: encrypt/decrypt round-trip đúng ✅; backward compat plaintext pass-through ✅; is_encrypted() detect "enc:" prefix ✅; mcp auth_config và project llm_config đều qua seam ✅
- A3: trace retention logic import OK ✅
- D: `create_llm_client()` nhận `extra_config` với `api_key`/`base_url`/`headers` ✅; `llm.manage` permission tồn tại trong catalog ✅

**Cổng Ngày 28 ✅ PASS:** /trigger no-token → 401 path ✅ · llm_config encrypted at seam ✅ · trace purge on startup ✅ · per-project LLM override UI functional ✅

### [Session 33 — 2026-06-15] — Ngày 27: Engine Intelligence (E4 + E3/D1)

**A. E4 — Loop detection nâng cấp (dao động A→B→A→B):**
- `state.py:is_looping()` — nâng từ "2 liên tiếp giống nhau" → bắt được dao động chu kỳ 2 (ABABAB) và 3 (ABCABC) trong window N=6 calls; lọc `_competing_gate` calls khỏi lịch sử kiểm tra để không làm nhiễu phát hiện.

**B. E4 — Cổng giả thuyết cạnh tranh (competing hypothesis gate):**
- `state.py` — thêm `_competing_gate_fired: bool = False` (tránh loop vô hạn).
- `loop.py` — thêm `_NUDGE_TOOL_NAME = "_competing_gate"` + `_quick_parse_confidence()` (parse nhanh confidence từ verdict text) + `_apply_competing_gate()` (kiểm gate condition, trả nudge ToolCall khi cần, idempotent).
- `loop.py:run_tool()` — xử lý `_competing_gate` như synthetic tool: trả Observation cảnh báo "còn N hypothesis chưa loại trừ, hãy điều tra trước".
- `loop.py:_run_loop()` — sau khi nhận vtext từ LLM: chạy gate trước khi accept verdict; nếu gate fires → inject nudge tool call vào vòng tiếp theo.
- `graph.py:decide_node()` — tương tự: gate fires → return nudge tool_call (không set verdict_text); routing tự nhiên đi `run_tool → update → decide`.

**C. E3/D1 — Confidence calibration (eval + feedback):**
- `queries.py:get_calibration_with_feedback()` — merge 3 nguồn: (1) eval_results per-confidence correct rate; (2) investigation_feedback 👍/👎 join trace_events để lấy confidence; (3) combined tổng hợp.
- `router.py` — import + gọi `get_calibration_with_feedback()`, pass `calib_feedback` vào eval template.
- `templates/eval.html` — thay 1 calibration card cũ bằng 2-column layout: "Calibration — Eval (correct rate)" | "Calibration — Kết hợp (eval + 👍👎)" với badge màu theo confidence + note số feedbacks.

**D. D2 — Baseline auto-update:** defer (if-time, không đủ thời gian + data synthetic không có time-series cross-day thật).

**Verify:**
- Loop oscillation ABABAB detected ✅; 2 consecutive detected ✅; nudge calls filtered ✅
- Gate fires on high/medium verdict khi có competing open hypothesis ✅; idempotent (1 lần) ✅; pass cho insufficient ✅
- Nudge Observation trả đúng summary + metadata ✅
- Calibration with feedback query: eval 3 rows + feedback 1 row → combined 3 rows (high merged 5 total) ✅
- Dashboard /dashboard/eval: 2 calibration card side-by-side, badge màu, feedback note ✅
- Regression eval 4/4 mock PASS (backward compat không vỡ) ✅

**Cổng Ngày 27 ✅ PASS:** loop oscillation · cổng cạnh tranh · calibration dashboard · regression không vỡ.

**Quyết định lệch:**
- D2 (baseline auto-update if-time) → defer: data metrics chỉ có 1 ngày synthetic, rolling 7-day không có ý nghĩa thực tế. Không ảnh hưởng cổng.
- Cổng cạnh tranh end-to-end qua engine khó test tự động (hypothesis lifecycle phụ thuộc synthetic data match keywords); unit test xác nhận cơ chế đúng (gate fire/pass, nudge inject, idempotent).

### [Session 32 — 2026-06-15] — Ngày 26: Engine Core (E1 + E5 + E2)

**A. E1 — Vòng đời giả thuyết thật:**
- `state.py` — `Hypothesis` thêm `keywords: List[str]` (để match evidence có liên quan); `Verdict` thêm `speculative: bool = False`; `InvestigationState` thêm `competing_open()` method.
- `loop.py` — thêm `_HYPOTHESIS_RELEVANCE` dict (per tag: tools, confirm_kws, rule_out_kws, confirm_conf); rewrite `_update_hypotheses()`: bỏ "append mù vào mọi hypothesis open", thay bằng matching có liên quan + chuyển trạng thái `open→confirmed/ruled_out` thật; update `_upsert_hypothesis()` nhận `keywords` + `initial_status`.

**B. E5 — Structured verdict via tool call:**
- Thêm `VERDICT_TOOL_NAME = "submit_verdict"` + `_build_verdict_tool_spec()`.
- `_structured_args_to_verdict_text(args)` — chuyển args structured → text format reliable cho `_parse_verdict`.
- `decide_next_action()` — thêm `submit_verdict` vào tool_specs; detect `tc.name == VERDICT_TOOL_NAME` → return verdict text, không dispatch sang `run_tool`. Backward compat: text VERDICT vẫn hoạt động (MockLLM).
- `_parse_verdict()` — fix default `"medium"` → `"insufficient"` khi parse fail.
- Cập nhật SYSTEM_PROMPT: đề xuất dùng `submit_verdict` tool, giữ text format làm fallback.

**C. E2 — Evidence-grounding guard:**
- `_check_evidence_grounding(verdict, evidence)` — overlap từ khóa root_cause vs evidence summaries; nếu < 25% → hạ confidence 1 bậc + `speculative=True`. Chạy sau `_parse_verdict` trong cả `run()` và `multi_agent._synthesize_verdict()`.
- Verdict trace event thêm `speculative` field.

**Verify:**
- E1: deploy found → `status=confirmed`; no deploy → `status=ruled_out` ✅
- E2: good verdict → `speculative=False`; made-up verdict → `conf` hạ + `speculative=True` ✅
- `competing_open()` trả đúng (empty khi tất cả confirmed, có list khi còn open) ✅
- Regression eval 4/4 mock PASS (backward compat text verdict hoạt động) ✅

**Cổng Ngày 26 ✅ PASS:** hypothesis lifecycle thật · structured verdict tool · evidence grounding guard · regression không vỡ.

**Bổ sung (session 31, theo yêu cầu người dùng):** thêm **per-project custom LLM endpoint** vào **Ngày 28** (mục D). Đọc code xác nhận per-project LLM đã có khung từ D12 (`get/set_project_llm`, cột `llm_config`, fallback default ở `runner.py`) nhưng "last mile" còn thiếu: (1) `create_llm_client` bỏ rơi `extra_config` cho anthropic+openai-compat (chỉ gemini nhận) → base_url/api_key/headers bị bỏ qua âm thầm; (2) `AnthropicClient` không hỗ trợ `base_url`; (3) `OpenAICompatibleClient` thiếu `default_headers`; (4) UI chưa expose url/header key. Fit Day 28 vì pair với A2 (mã hóa `llm_config` chứa credential) + dùng quyền `llm.manage`. Đã cập nhật docs/12 (Day 28 mục D + Cổng + bảng M→M+), CLAUDE.md, BUILD_STATE.md.

**Chưa làm:** chưa bắt đầu code Ngày 26 (chờ session sau xác nhận khởi động).

### [Session 30 — 2026-06-14] — Ngày 25: UI/UX + Đóng Phase 5

**A. MCP Server Auth:**
- `data/migrate_day25.py` (mới) — thêm `auth_type TEXT DEFAULT 'none'` và `auth_config TEXT DEFAULT '{}'` vào `mcp_servers` (idempotent via PRAGMA table_info)
- `src/agent/tools/mcp_client.py` — `__init__` nhận `auth_type`, `auth_config`; `_auth_headers()` build header (bearer → `Authorization: Bearer`, api_key → custom header); inject vào `aiohttp.ClientSession(headers=...)` → toàn session tự động có auth
- `src/agent/intake/mcp_registry.py` — `add_server()` nhận `auth_type/auth_config`; `update_server()` cho phép update 2 field mới; `get_enabled_servers()` trả full dict {url, auth_type, auth_config}
- `src/agent/intake/runner.py` — `_get_mcp_servers_for_project()` trả `List[Dict]` thay vì `List[str]`; `_connect_mcp_clients()` parse auth_config JSON + tạo MCPClient với auth
- `src/agent/intake/server.py` — `_create_mcp_server()` validate auth_type + auth_config JSON; `_ping_mcp_server()` tạo MCPClient có auth
- `src/agent/dashboard/queries.py` — `get_mcp_servers_for_dashboard()` + `get_project_detail()` include `auth_type` trong SELECT
- `src/agent/dashboard/templates/mcp.html` — form Row 2: auth_type select (none/bearer/api_key) + conditional fields (JS show/hide) + hidden `auth_config` JSON field; bảng servers thêm cột Auth với `🔑 bearer` badge

**B. Tool Registry test-run:**
- `src/agent/dashboard/router.py` — `POST /dashboard/tools/{tool_name}/run`: lookup tool theo name+domain, `await tool.run(args)` (async/sync via inspect), trả JSON Observation
- `src/agent/dashboard/templates/tools.html` — mỗi tool card có "▶ Test Run" toggle; panel với JSON textarea + Run button + inline Observation result (summary bold, aggregates màu, samples list)

**C. Replay side-by-side diff:**
- `src/agent/dashboard/router.py` — `GET /dashboard/investigations/{id}/diff?compare={id2}`: fetch cả 2 investigations, pass vào template
- `src/agent/dashboard/templates/diff.html` (mới): dropdown selector `compare`; summary bar đếm diff count (confidence/root_cause/stop_reason); 2 cards side-by-side (A/B badge, confidence highlight nếu khác, root_cause highlight nếu khác, steps list)
- `src/agent/dashboard/templates/detail.html` — thêm "⇄ Diff" button cạnh Replay button

**D. Investigation search:**
- `src/agent/dashboard/queries.py` — `list_investigations()` nhận `search: Optional[str]`; filter trên `(start_payload + verdict_payload).lower().contains(term)`
- `src/agent/dashboard/router.py` — `dashboard_home()` nhận `search` query param, pass vào query + template
- `src/agent/dashboard/templates/index.html` — thêm text input `search` + 🔍 submit button vào filter bar

**Verify:**
- Tool test-run: click "▶ Test Run" → expand panel → nhập args → Run → `✓ OK` + Observation render (summary bold + aggregates màu + samples) ✅
- Diff: navigate `/investigations/{id}/diff?compare={id2}` → summary bar "⚠ 2 trường khác nhau: confidence root_cause" → side-by-side cards với highlight đúng ✅
- Search `?search=scenario4` → 17 results (filter từ ~50) ✅
- Mock eval 4/4 PASS (lõi không vỡ) ✅

**Cổng Phase 5 ✅ PASS:**
- auth bật (RBAC động, root login) ✅
- cost thật (cost dashboard $/inv) ✅
- real-LLM eval (6/6 smoke, smoke do người dùng chọn) ✅
- storage seam Tier-1 ✅
- ≥1 integration thật (Slack adapter + Real MCP infra pack + webhook signature) ✅
- replay diff ✅
- MCP server auth ✅ (added per user request)
- investigation search ✅
- tool test-run ✅

**Deferred (not done, not blocking cổng):**
- Graceful shutdown (SIGTERM → partial verdict) — đẩy xuống Future
- Trace retention (purge cũ) — đẩy xuống Future
- Secret management at-rest — đẩy xuống Future

**25/25 NGÀY + Phase 5 HOÀN TẤT.**

### [Session 29 — 2026-06-14] — Ngày 24: Integrations (Webhook Signature + Slack + Real MCP Pack)

**A. Webhook Signature Verify (must):**
- `src/agent/intake/adapters/_shared.py` — thêm `verify_webhook_signature(source, raw_body, headers)`:
  - Prometheus/Grafana/alertmanager: env `{SOURCE}_WEBHOOK_SECRET` + header `X-Webhook-Secret` = HMAC-SHA256(body, secret) hex
  - Sentry: env `SENTRY_WEBHOOK_SECRET` + header `sentry-hook-signature` = `sha256=<hex>` hoặc bare hex
  - Nếu env không set → pass-through (backward compat)
  - Dùng `hmac.compare_digest` chống timing attack
- `src/agent/intake/server.py` — thêm `_handle_trigger_request(request, project_id)` async helper:
  - Đọc raw body bytes (không dùng FastAPI JSON parsing để giữ raw body cho HMAC)
  - Verify signature khi `X-Alert-Source` header có mặt
  - Raise 401 nếu verify fail
  - Parse JSON thủ công rồi gọi `_do_trigger`
  - Đổi `trigger_global` và `trigger_project` → dùng `Request` trực tiếp

**B. Slack Output Adapter (must):**
- `src/agent/output/slack.py` (mới):
  - `_render_slack_payload(state)` → Block Kit với attachment `color` theo severity
  - Sympom header + fields: root_cause / steps+tokens / evidence_summary / stop_reason warning
  - `push_verdict_to_slack(state, config)` — `SLACK_WEBHOOK_URL` env + `config["webhook_url"]` override
  - Graceful: no URL → warning; HTTP error → log warning; exception → log error (không crash)
- `src/agent/output/router.py` — thêm `elif channel == "slack": push_verdict_to_slack`
- `src/agent/intake/project_registry.py` — thêm `"slack"` vào `SUPPORTED_CHANNELS`

**C. Real MCP Infra Pack (spill-OK → done):**
- `mcp_server/server_infra.py` (mới) — MCP server với 4 real tools (không dùng synthetic data):
  - `fetch_url`: HTTP GET URL thật (stdlib urllib), cắt > 4000 ký tự
  - `list_files`: list files/dirs trong path (pathlib), sort theo type
  - `get_system_info`: OS, CPU, memory (/proc/meminfo best-effort), disk (os.statvfs)
  - `check_port`: TCP socket connect test → is_open + latency_ms
- `scripts/start_infra_mcp_server.py` (mới) — launch server port 9001
- Verify hot-plug: MCPClient → initialize + tools/list → discover 4 tools → tools/call get_system_info → Observation đúng ✅

**Verify end-to-end:**
- Webhook: no X-Webhook-Secret → HTTP 401 ✅; correct HMAC-SHA256 → HTTP 202 ✅
- Slack render: Block Kit payload đúng (color=#DC143C HIGH, sections, fields) ✅
- Slack dispatch: no URL → graceful warning; bad URL → error logged, no crash ✅
- Infra MCP health: `{"status":"ok","tools":["fetch_url","list_files","get_system_info","check_port"]}` ✅
- MCPClient hot-plug: discover 4 tools, call get_system_info → summary đúng ✅
- Mock eval 4/4 PASS (lõi không vỡ) ✅

**Cổng Ngày 24 ✅ PASS:** webhook không chữ ký → 401 · Slack adapter gửi được · Real MCP server hot-plug.

**Ghi chú:**
- Không thêm dependency mới (chỉ stdlib: hmac, hashlib, urllib, socket, pathlib)
- `stop_reason` nằm trên `InvestigationState`, không phải `Verdict` — Slack adapter dùng đúng
- Infra MCP server port 9001 (không đụng 9000 của demo server)
- `SLACK_WEBHOOK_URL` env cần thêm vào `.env.example`

### [Session 28 — 2026-06-14] — Ngày 23: Observability + Project CRUD UI

**A. Cost Dashboard `/dashboard/cost` (P0):**
- `src/agent/dashboard/queries.py` — `_PRICING` dict (anthropic/openai/gemini/groq/mock với tiers per model prefix) + `_cost_usd(tokens, provider, model)` (60% input / 40% output split) + `get_cost_data()` query eval_results (per-scenario avg/total tokens + cost) + live investigations (verdict payload `$.total_tokens`).
- `src/agent/engine/loop.py` — thêm `"total_tokens": state.total_tokens` vào verdict trace event payload → live investigations có cost data từ đây về sau.
- `src/agent/dashboard/templates/cost.html` (mới) — 3 summary cards (total tokens / eval cost / live inv) + bảng per-scenario (provider, avg/total tokens, $/run, total cost) + pricing reference table.
- `src/agent/dashboard/templates/base.html` — thêm `💰 Cost` nav link.
- Verify: 53,948 tokens từ fintech1+fintech2 (real-LLM D21) → $0.4208 ước tính đúng ✅

**B. Verdict Feedback Loop (👍/👎):**
- `data/migrate_day23.py` (mới) — `investigation_feedback(investigation_id PK, score INT, created_at, updated_at)`.
- `src/agent/dashboard/queries.py` — `get_investigation_feedback(inv_id)` + `set_investigation_feedback(inv_id, score)` (UPSERT) + optional Langfuse score push nếu LANGFUSE_PUBLIC_KEY set.
- `src/agent/dashboard/router.py` — `GET /investigations/{id}` pass `feedback=get_investigation_feedback(id)` vào template; `POST /investigations/{id}/feedback` nhận `score` form field → set_investigation_feedback → redirect.
- `src/agent/dashboard/templates/detail.html` — 👍/👎 buttons inline trong verdict card header; button active styling (green/red border) khi feedback đã có.
- Verify: click 👍 → redirect về detail → 👍 button highlighted green ✅

**C. Project CRUD UI:**
- `src/agent/dashboard/router.py` — `POST /projects` (create → require_perm("project.manage")); `POST /projects/{pid}/edit` (update); `POST /projects/{pid}/delete` (guard không xóa 'default'); `GET /projects` pass `can_manage` vào template.
- `src/agent/dashboard/templates/projects.html` — form tạo project (id slug + name + description + validation pattern); per-card ✏ Sửa + ✕ Xóa (hidden nếu `default` hoặc không có quyền); inline edit form toggle bằng JS `toggleEdit()`.
- Verify: tạo "test-project" → 2 project ✅; Sửa toggle mở edit form ✅; guard không hiện Xóa cho `default` ✅

**Cổng Ngày 23 ✅ PASS:** cost page $/inv thật · 👍/👎 ghi DB · tạo/sửa project từ UI · regression 4/4 PASS.

**Spill / chưa làm:** Trace retention (purge cũ) — không critical, đẩy sang D24/D25.

### [Session 27 — 2026-06-14] — Ngày 22: Auth & RBAC động đầy đủ

**A. Schema RBAC (7 bảng mới):**
- `data/schema.sql` — appended: `users`, `roles`, `permissions`, `role_permissions`, `project_groups`, `project_group_members`, `role_assignments`, `api_tokens`.
- `data/migrate_rbac.py` (mới) — migration idempotent: CREATE TABLE IF NOT EXISTS 8 bảng, seed 12 permissions catalog, seed 3 system roles (admin/operator/viewer), bootstrap root user từ env `ROOT_USERNAME`/`ROOT_PASSWORD`.
- Chạy OK: "Tạo 6 bảng RBAC + api_tokens OK" · "Seed 12 permissions + 3 system roles OK" · "Root user 'root' tạo mới OK".

**B. Auth package (`src/agent/auth/`):**
- `permissions.py` — `PERMISSION_CATALOG` (12 quyền), `ROLE_SEEDS` (3 system roles + perms), `PERMISSION_GROUPS` (5 nhóm cho checkbox grid UI).
- `rbac.py` — hàm CRUD đầy đủ: user CRUD, role CRUD, role_permissions, role_assignments, `user_can(user_id, perm_key, project_id)` (is_root shortcut → global → project → group), project_groups, api_tokens. Dùng `from agent.storage import open_db, IntegrityError` (KHÔNG import sqlite3). Password: `hashlib.pbkdf2_hmac("sha256", ..., salt, 100_000)`.
- `deps.py` — `NotAuthenticated`/`NotAuthorized` exceptions; `get_current_user()`, `require_login()` (session + X-API-Token header), `require_perm("perm")` factory trả plain callable (caller làm `Depends(require_perm("perm"))`).

**C. Server v0.8.0 (`src/agent/intake/server.py`):**
- `SessionMiddleware` (itsdangerous, `ia_session` cookie, max_age=7 ngày, dev secret).
- Exception handlers: `NotAuthenticated` → redirect `/auth/login?next=...`; `NotAuthorized` → HTML 403.
- Routes mới: `GET /auth/login`, `POST /auth/login`, `POST /auth/logout`.
- `bootstrap_root()` gọi trong lifespan (wrapped try/except).
- `pyproject.toml` — thêm `itsdangerous>=2.0.0`.

**D. Dashboard guards + Admin UI (`src/agent/dashboard/router.py`):**
- Tất cả route `/dashboard/*` guard bằng `Depends(require_login)`.
- Admin routes: `GET/POST /admin/users`, `POST /admin/users/{uid}/toggle`, `POST /admin/users/{uid}/assign`, `POST /admin/assignments/{aid}/remove`, `GET/POST /admin/roles`, `POST /admin/roles/{rid}/permissions`, `POST /admin/roles/{rid}/delete`, `GET/POST /admin/groups`, `POST /admin/groups/{gid}/add-member`, `POST /admin/groups/{gid}/remove-member`.

**E. Templates mới/sửa:**
- `login.html` — standalone dark-theme, form POST /auth/login, error display.
- `admin_users.html` — danh sách users, create form, assign-role form (role/scope/project_id), toggle enable/disable.
- `admin_roles.html` — create role form, permission checkbox grid nhóm theo PERMISSION_GROUPS, Lưu quyền + Xóa.
- `admin_groups.html` — create group, add/remove project members.
- `base.html` — v0.8 · Phase 5, ⛨ Admin nav link, user info + logout button in nav.
- `static/style.css` — `.page-header`, `.card`, `.btn`, `.form-*`, `.badge-info`, `.alert`, `.table` styles.

**Verify (browser end-to-end):**
- `/dashboard` → redirect `/auth/login` (unauthenticated guard) ✅
- Login root/admin123 → dashboard v0.8, Admin nav link, ROOT badge, logout button ✅
- `/dashboard/admin/users` — render Quản lý Users ✅
- Tạo user alice/alice123 → Danh sách users (2) ✅
- Gán alice → operator / scope=project / project_id=default → "OPERATOR project/default" trong bảng ✅
- `/dashboard/admin/roles` — 3 system roles, permission checkbox grid (5 nhóm × 12 perms) ✅
- Regression: `eval_agent.py --mock --n 1` → 4/4 PASS ✅

**Cổng Ngày 22 ✅ PASS:** root login · guard đúng · tạo user + role động + gán scope hoạt động.

**Quyết định lệch / spill:**
- Admin badge trong base.html hiển thị cho TẤT CẢ logged-in user (không chỉ admin) — UX đơn giản hơn, route tự từ chối 403 nếu thiếu quyền.
- Spill OK: api_tokens CRUD đã có code trong rbac.py (tạo/list/revoke/verify), chưa có UI + route riêng → để Ngày 23/24.
- Spill OK: groups UI đã có code + route, chưa test end-to-end browser → tốt cho Ngày 24.

### [Session 26 — 2026-06-14] — Ngày 21: Storage seam Tier-1 + Real-LLM eval (smoke) + Recursion bugfix

**A. Storage seam Tier-1 (DB-swappable; runtime VẪN SQLite):**
- `src/agent/storage/base.py` (mới) — `StorageBackend` Protocol + facade `Database` (query/query_one/execute/connection/now) + hợp đồng connection.
- `src/agent/storage/sqlite_backend.py` (mới) — backend SQLite, MODULE DUY NHẤT import sqlite3; `IntegrityError=sqlite3.IntegrityError`.
- `src/agent/storage/postgres_backend.py` (mới) — stub Tier-2 (connect raise NotImplementedError) → chứng minh seam.
- `src/agent/storage/db.py` — rewrite thành dispatcher theo `DB_BACKEND` env; giữ API `open_db()`/`get_db_path()`; re-export `IntegrityError`+`BACKEND_NAME`.
- `__init__.py` — export + `get_database()` singleton.
- `mcp_registry.py`, `project_registry.py` — bỏ `import sqlite3`, dùng `IntegrityError` trung lập.
- Verify: chỉ `sqlite_backend.py` còn sqlite3 trong src/agent; `DB_BACKEND=postgres` dispatch sang stub OK; mock eval 4/4 PASS (lõi không vỡ).

**B. Eval scaffolding + calibration:**
- `data/migrate_eval_provider.py` (mới) + `schema.sql` — cột `provider`/`model` cho `eval_results`.
- `eval_agent.py` + `eval_fintech.py` — `--provider`/`--model`, capture provider/model vào save (qua facade), bỏ `import sqlite3`.
- `queries.py` — `get_eval_calibration()` + provider/model trong `get_eval_summary`.
- `router.py` + `eval.html` — cột LLM + card Calibration trên `/dashboard/eval`.

**C. Recursion bugfix (BUG PRODUCTION, phát hiện qua smoke real-LLM):**
- Triệu chứng: real-LLM đi >8 bước → `GraphRecursionError: limit 25` (mock che vì kịch bản mock 3-5 bước). Mỗi bước = 3 super-step ⇒ step_budget=10 → ~30 > 25.
- Fix `loop.py _run_with_graph`: `recursion_limit=step_budget*3+6` (engine tự dừng bằng budget; LangGraph chỉ là trần an toàn) + catch `GraphRecursionError` → verdict partial (không chết im lặng).

**Real-LLM eval (SMOKE — người dùng chọn dừng ở smoke, KHÔNG chạy full N=10):**
- 6/6 KB correct, 0 crash. scenario1-4 conf high/medium; **fintech1-2 conf=insufficient nhưng vẫn correct → agent under-confident trên fintech** (insight real-LLM, mock báo HIGH).
- ~32K tokens & ~56s/investigation (~$0.17/run → full N=10 ≈ ~$10, cao hơn quote $5-6 ban đầu).
- Verify dashboard `/dashboard/eval`: 6 KB anthropic/claude-sonnet-4-6, calibration high 3/3·medium 1/1·insufficient 2/2, 100% PASS.

**Cổng Ngày 21 ✅ (scope smoke):** real-LLM eval 6/6 KB lưu DB + calibration render + không còn import sqlite3 ngoài backend + lõi không vỡ.

**Quyết định lệch:** (1) Không chạy full N=10 — người dùng chọn "dừng ở smoke" sau 6/6 PASS (tiết kiệm ~$10). (2) Storage seam chỉ Tier-1; Tier-2 (Postgres chạy thật) ở Future. (3) `.env` có `LLM_PROVIDER` trùng 2 dòng — chưa dọn (vô hại).

### [Session 25 — 2026-06-14] — Lập kế hoạch Phase 5 (Ngày 21–25)

**Bối cảnh:** 20/20 ngày xong. Session này KHÔNG code — tổng hợp 20 ngày + lập backlog 5 theme → chốt thành Phase 5.

**Đã làm (3 file):**
- `docs/11-roadmap-phase-5.md` (mới) — kế hoạch Ngày 21–25, format Làm/Cổng như docs/10
- `CLAUDE.md` — "Giai đoạn hiện tại" → Phase 5; dọn danh sách "KHÔNG" (bỏ item đã graduated: LangGraph/multi-agent/Langfuse/Dashboard/Fintech); thêm chú thích storage seam vào ràng buộc SQLite
- `BUILD_STATE.md` — trạng thái hiện tại + bảng Tiến độ Phase 5 + entry này

**Quyết định chốt (qua trao đổi với người dùng):**
- Phase 5 = 5 theme × 5 ngày: Engine&Quality(+storage seam) · Auth&RBAC · Observability · Integrations · UI/UX.
- **Auth = RBAC động đầy đủ** (root user · role động · permission catalog 12 quyền · project groups · scoped assignment global/group/project). Người dùng chọn **giữ 5 ngày, Day 22 nặng** (RBAC ép trọn Day 22, chấp nhận spill sang Day 23 sáng; secret-mgmt + graceful-shutdown đẩy xuống cut-list).
- **Storage seam (Day 21, paired với eval):** Tier-1 = `Database` Protocol + `SQLiteBackend`, gom PRAGMA/placeholder/UPSERT/IntegrityError, `DB_BACKEND` env. Quét code: `open_db()` đã là chokepoint (17 file), chỉ 3 file runtime còn `import sqlite3` trực tiếp → seam khả thi & rẻ. **Tier-2 (migration Postgres/MySQL thật: port 12×datetime + 8×UPSERT + DDL + backend chạy) → future, KHÔNG nằm Day 21.** Runtime vẫn SQLite → không vi phạm "no Postgres".
- 3 P0: real-LLM eval (D21) · auth/RBAC (D22) · cost dashboard (D23).

**Chưa làm:** chưa bắt đầu code Day 21 (chờ session sau).

### [Session 24 — 2026-06-14] — Ngày 20: Platform Demo Full + Cổng Phase 4

**Đã làm:**
- `src/agent/dashboard/queries.py` — fix `get_eval_summary()`: lấy run mới nhất per scenario (INNER JOIN MAX(created_at) per scenario) → tất cả 6 scenario hiển thị đúng
- `src/agent/dashboard/router.py` — demo route: thêm fintech1+fintech2 vào `quick_scenarios` (6 buttons), thêm `domain` field
- `src/agent/dashboard/templates/demo.html` — thêm `<input type="hidden" name="domain">`, `fillScenario()` set domain field

**Verify (browser):**
- `/dashboard/eval` — 60 runs, 60 đúng, 100%, ✅ PASS, chart 6 bars (fintech1, fintech2, scenario1-4) ✅
- `/dashboard/demo` — 6 quick scenario buttons (4 microservice + 2 fintech 💳), form auto-fill khi click ✅
- Theme toggle: dark/light mode persistent ✅
- Toast: success/error/info slide-in top-right ✅

**Cổng Phase 4 ✅ PASS:**
- 2 domain live: Microservice Ops (4 kịch bản) + Fintech Anomaly (2 kịch bản) ✅
- MCP hot-plug: server cắm vào được mà không restart engine ✅
- Eval numbers thật: 6 kịch bản × N=10 = 60 runs, 100% correct rate ✅
- Full dashboard: Investigations / Trigger / Projects / Chat / Eval / Health / Metrics / Channels / Tools / MCP Registry / Demo Mode ✅
- Chat UI + SSE live stream ✅
- Multi-agent (parallel specialists) ✅
- LangGraph engine ✅
- Resilience (ConcurrencyLimiter + CircuitBreaker + retry) ✅
- Long-term memory ✅
- Theme switcher light/dark ✅
- Toast notifications ✅
- Keyboard shortcuts (Ctrl+K, T, R, H, ?) ✅

**20/20 NGÀY HOÀN TẤT.**

### [Session 23 — 2026-06-14] — Ngày 19: Eval N=10 + Dashboard Polish

**Đã làm:**

**A. Eval toàn diện N=10:**
- `python scripts/eval_agent.py --mock --n 10` — 40/40 PASS (scenario1-4, 100% correct rate)
- `python scripts/eval_fintech.py --n 10` — 20/20 PASS (fintech1-2, 100% correct rate)
- Kết quả lưu vào `eval_results` SQLite (2 run_id mới)

**B. Dashboard Polish:**
- `src/agent/dashboard/static/style.css`:
  - Light theme CSS variables (body.theme-light): bg=#f0f2f8, surface=#fff, text=#1e2342, accent=#4a58e0
  - Badge/verdict-card light overrides
  - `.toast` + `@keyframes toastIn/Out` — slide-in từ top-right, auto-dismiss 3.5s
  - `.theme-toggle` button style (trong nav)
  - `.spinner` + `@keyframes spin`
  - `kbd` style cho shortcut hints
- `src/agent/dashboard/templates/base.html`:
  - Version "v0.7 · Phase 4"
  - Toast container `<div id="toast-container">`
  - Theme toggle button trong nav (☀ Light Mode / 🌙 Dark Mode)
  - Global JS: `_applyTheme()`, `toggleTheme()` (localStorage `ia-theme`), `showToast()`, keyboard shortcuts
  - Shortcuts: Ctrl+K=Chat, T=Trigger, R=Reload, H=Home, ?=Help toast
- `src/agent/dashboard/templates/trigger.html`:
  - Submit button loading state: spinner + "Đang gửi…" khi click
  - Toast khi result.status='accepted' → showToast('Investigation bắt đầu · ID: ...')
  - Toast khi result.status='duplicate' → showToast info
- `src/agent/dashboard/templates/chat.html`:
  - Toast khi SSE verdict event → showToast('Investigation hoàn thành · HIGH — root_cause…')

**Verify (browser):**
- Dark mode: nav background #1a1d27, text #e2e4f0 ✅
- Light mode toggle → body.theme-light, white background, nav "#f0f2f8" ✅
- localStorage persistence: reload → theme giữ nguyên ✅
- Toast success (green border) hiện top-right, auto-dismiss ✅
- Trigger form: submit → spinner + "Đang gửi…" ✅

**Cổng Ngày 19 ✅ PASS:** 6 kịch bản eval N=10 PASS + theme toggle + toast + keyboard shortcuts.

### [Session 22 — 2026-06-14] — Ngày 18: Fintech Domain + Domain Switcher UI

**Đã làm:**
- `data/migrate_fintech.py` (mới) — migration idempotent: 4 bảng (`ft_transactions`, `ft_revenue`, `ft_merchants`, `ft_settlements`) + indexes
- `data/seed_fintech1.py` (mới) — KB-F1: proc-alpha timeout → credit_card 65% fail từ 10:15 (23,325 tx rows)
- `data/seed_fintech2.py` (mới) — KB-F2: merch-buzz price bug → refund_rate 14.8% (~8x baseline, 11,250 tx rows)
- `src/agent/tools/fintech/__init__.py` (mới) — package marker
- `src/agent/tools/fintech/get_revenue_breakdown.py` (mới) — revenue theo channel, Δ% vs baseline
- `src/agent/tools/fintech/get_transaction_anomaly.py` (mới) — fail/refund rates per merchant và channel
- `src/agent/tools/fintech/get_merchant_status.py` (mới) — trạng thái merchant + notes (flags bug/price/fraud)
- `src/agent/tools/fintech/get_settlement_lag.py` (mới) — processing_time_s vs baseline per merchant
- `src/agent/tools/registry_fintech.py` (mới) — `ALL_FINTECH_TOOLS`, `get_fintech_tool_registry()`
- `src/agent/intake/normalizer.py` — thêm `domain: str = "microservice"` vào `InvestigationRequest`
- `src/agent/intake/runner.py` — domain routing: `domain=="fintech"` → fintech tool registry
- `src/agent/dashboard/queries.py` — thêm `get_all_tools_for_dashboard()` → `{microservice: [...], fintech: [...]}`
- `src/agent/dashboard/templates/tools.html` (mới) — Tool Registry Viewer: domain tabs + tool cards
- `src/agent/dashboard/templates/trigger.html` — domain switcher buttons (⚙ Microservice / 💳 Fintech), JS `switchDomain()`, DOMAIN_DATA dict
- `src/agent/dashboard/templates/base.html` — thêm `⚙ Tools` nav link
- `scripts/eval_fintech.py` (mới) — MockLLM_FT1 (KB-F1), MockLLM_FT2 (KB-F2), evaluate_run, save_eval_to_db

**Verify:**
- `python scripts/eval_fintech.py` — 2/2 PASS (fintech1: conf=high steps=3, fintech2: conf=high steps=3) ✅
- KB-F1: root_cause="proc-alpha payment processor timeout từ 10:15 gây 65% fail trên kênh credit_card" ✅
- KB-F2: root_cause="merch-buzz price bug từ 14:00 gây refund_rate 14.8% (~8x baseline 1.9%)" ✅

**Cổng Ngày 18 ✅ PASS:** Fintech 2/2 mock eval PASS, domain switcher hoạt động trên trigger UI.

### [Session 21 — 2026-06-14] — Ngày 17: Dashboard v3 Full Platform UI

**Đã làm:**
- `src/agent/dashboard/queries.py` — thêm 2 functions:
  - `get_mcp_servers_for_dashboard()` — LEFT JOIN với projects để lấy project_name
  - `get_project_detail(project_id)` — info + services + mcp_servers + channels + recent investigations (10 rows)
- `src/agent/dashboard/router.py` — thêm 10 routes mới:
  - `GET /dashboard/mcp` — MCP Registry UI
  - `POST /dashboard/mcp/register` — thêm server vào DB, redirect
  - `POST /dashboard/mcp/{id}/delete` — xóa server với confirm
  - `POST /dashboard/mcp/{id}/ping` — JSON endpoint cho JS fetch: initialize + tools/list → latency_ms + tools list
  - `GET /dashboard/projects/{pid}` — Project Detail UI
  - `POST /dashboard/projects/{pid}/services/add` — thêm service
  - `POST /dashboard/projects/{pid}/services/{svc}/delete` — xóa service
  - `POST /dashboard/projects/{pid}/channels/{ch}/config` — update config JSON + toggle enabled
  - `POST /dashboard/investigations/{inv_id}/replay` — trigger investigation mới từ payload gốc, redirect sang detail
  - `GET /dashboard/demo` — Demo Mode full-screen
- `src/agent/dashboard/templates/mcp.html` (mới) — register form inline (4 fields), bảng servers, Ping button (JS fetch → hiện latency + tools), Xóa với confirm
- `src/agent/dashboard/templates/project_detail.html` (mới) — LLM config, services với add/remove, alert channels (textarea config JSON + toggle), MCP servers list, recent investigations
- `src/agent/dashboard/templates/demo.html` (mới) — standalone HTML (không extends base), full-screen layout, 4 scenario quick-select buttons, trigger form trái, SSE stream phải, verdict card
- `src/agent/dashboard/templates/detail.html` — thêm Replay button top-right (form POST với confirm)
- `src/agent/dashboard/templates/projects.html` — thêm "Quản lý →" link đến `/dashboard/projects/{id}`
- `src/agent/dashboard/templates/base.html` — thêm 2 nav links: ⬡ MCP Registry, ▣ Demo Mode

**Verify (browser):**
- `/dashboard/mcp` — form register hiện, 1 server (Investigation Tools, enabled, project=default) ✅
- Ping button JS call → chờ response (MCP server offline → error đỏ, online → latency + tools) ✅
- `/dashboard/projects/default` — LLM=anthropic(env), Services(0)+form, 3 channels OFF với textarea JSON, MCP(1 server), 10 recent investigations ✅
- `/dashboard/investigations/{id}` — ⟳ Replay button top-right ✅
- `/dashboard/demo` — full-screen, no nav, 4 scenario cards, trigger form, live stream area ✅
- `/dashboard/projects` — "Quản lý →" link trên mỗi project card ✅

**Cổng Ngày 17 ✅ PASS:** Toàn bộ platform (projects, MCP, channels, trigger, replay) quản lý từ browser.

### [Session 20 — 2026-06-14] — Ngày 16: Resilience + CLI + Health Dashboard

**Đã làm:**
- `src/agent/engine/resilience.py` (mới):
  - `with_retry(coro_fn, max_attempts=3, base_delay=2.0)` — exponential backoff, retryable: 429/rate_limit/overload/503/502/timeout/connection
  - `ConcurrencyLimiter(max_concurrent=3)` — asyncio.Semaphore, `__aenter__`/`__aexit__`, `status_dict()`
  - `CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)` — state machine: closed→open→half-open→closed; `call(coro_fn)`, `status_dict()`
  - `_alert_circuit_open()` — push Telegram khi circuit mở (no-op nếu không có token)
  - Module singletons: `investigation_limiter = ConcurrencyLimiter(3)`, `llm_circuit_breaker = CircuitBreaker(...)`
- `src/agent/engine/graph.py` — `decide_node` wrap LLM call:
  - Thay `await decide_next_action(...)` bằng `await llm_circuit_breaker.call(lambda: with_retry(lambda: decide_next_action(...)))`
- `src/agent/intake/runner.py` — tích hợp `investigation_limiter`:
  - Import + log `limiter.status_dict()` khi bắt đầu
  - `async with investigation_limiter:` bao quanh toàn bộ engine execution (try/except/finally bên trong)
  - `save_pattern()` và `push_verdict()` ở ngoài limiter block (chạy dù limiter release)
- `scripts/chat.py` (mới) — CLI REPL:
  - `argparse`: `--project`, `--multi-agent`, `--steps`
  - Quick scenario menu: 4 kịch bản preset + nhập thủ công
  - Chạy engine trực tiếp (không qua HTTP)
  - In verdict formatted: root_cause, confidence, stop_reason, steps, tokens
  - Nạp `.env` tự động
- `src/agent/dashboard/queries.py` — thêm 2 query functions:
  - `get_metrics_live(service=None)` — baseline vs hiện tại mỗi metric × service × scenario, tính Δ%
  - `get_channel_config()` — project × channel × enabled/config từ `project_alert_channels`
- `src/agent/dashboard/router.py` — thêm 4 routes:
  - `GET /dashboard/health` — LLM info, circuit breaker, concurrency limiter, MCP servers
  - `GET /dashboard/metrics-live` — table baseline vs current, filter by service, 30s auto-refresh
  - `GET /dashboard/channels` — per-project channel cards (Telegram/Teams/Email toggle)
  - `POST /dashboard/channels/{project_id}/{channel}/toggle` — flip enabled, redirect back
- `src/agent/dashboard/templates/health.html` (mới) — 4 cards: LLM, Circuit Breaker, Queue, MCP
- `src/agent/dashboard/templates/metrics_live.html` (mới) — table + JS auto-reload 30s countdown
- `src/agent/dashboard/templates/channels.html` (mới) — per-project channel toggle cards
- `src/agent/dashboard/templates/base.html` — thêm 3 nav links: Health, Metrics Live, Channels

**Verify (browser):**
- `/dashboard/health` — LLM anthropic/claude-sonnet-4-6, API key SET, Circuit Breaker CLOSED 0/3, Queue 0/3, MCP localhost:9000 enabled ✅
- `/dashboard/metrics-live` — bảng baseline/hiện tại, Δ% đỏ/cam/xanh, auto-refresh countdown ✅
- `/dashboard/channels` — DEFAULT project, 3 kênh (Telegram/Teams/Email DISABLED), nút Bật ✅

**Cổng Ngày 16 ✅ PASS:** health page live (circuit breaker + queue), CLI script tạo, 3 phiên concurrent không conflict (ConcurrencyLimiter semaphore max=3).

### [Session 19 — 2026-06-14] — Ngày 15: LangGraph Migration + Multi-agent

**Đã làm:**
- `src/agent/engine/graph.py` (mới) — LangGraph StateGraph:
  - `LoopState` TypedDict: inv, last_obs, tool_call, verdict_text, llm, tools, tracer
  - `decide_node` — wrap `decide_next_action()` pure fn, handle stop conditions (budget/loop)
  - `run_tool_node` — wrap `run_tool()` pure fn, emit SSE + Langfuse
  - `update_node` — wrap `update_state()` pure fn
  - `_route_after_decide` → "run_tool" | END; `_route_after_update` → "decide" | END
  - `get_compiled_graph()` — lazy singleton (compile 1 lần per process)
  - Graph: START → decide → run_tool → update → (loop) → decide → ... → END
- `src/agent/engine/loop.py` — `InvestigationEngine` refactor:
  - `__init__` — try build LangGraph, fallback về while loop nếu ImportError
  - `run()` — route sang `_run_with_graph()` hoặc `_run_loop()` tùy `self._graph`
  - `_run_with_graph()` — invoke graph với LoopState, extract kết quả
  - `_run_loop()` — original while loop code (unchanged, dùng làm fallback)
  - `run()` finalize: parse verdict + emit trace + tracer flush (chung cho cả 2 path)
- `src/agent/engine/multi_agent.py` (mới) — `MultiAgentEngine`:
  - Tool split: `LogAnalystAgent` (get_error_breakdown, trace_request) + `MetricAnalystAgent` (get_metrics, get_recent_deploys, get_dependencies)
  - `run()`: parallel `asyncio.gather(log, metric)` → `_merge_states()` → `_synthesize_verdict()`
  - `_merge_states()`: gộp evidence, dedup by id, hợp hypotheses + tool history + tokens
  - `_synthesize_verdict()`: 1 LLM call với `VERDICT_SYSTEM_PROMPT`, tools=[] (verdict only)
  - Emit trace events: investigation_start, multi_agent_start, multi_agent_merge, verdict
- `src/agent/intake/normalizer.py` — thêm `multi_agent: bool = False` field + `map_simple_payload` pass qua
- `src/agent/intake/runner.py` — route `MultiAgentEngine` khi `req.multi_agent == True`
- `src/agent/intake/server.py` — response trigger thêm `"engine": "langgraph"|"multi_agent"`
- `src/agent/dashboard/queries.py` — `get_investigation_detail` extract `engine` từ start payload
- `src/agent/dashboard/templates/detail.html` — Engine card trong sidebar:
  - Badge: LANGGRAPH / multi_agent / loop
  - SVG LangGraph: START→decide→run_tool→update→END + loop-back arrow
  - SVG Multi-agent: Orchestrator→(Log+Metric parallel)→VerdictAgent
- `src/agent/dashboard/templates/chat.html` — multi-agent checkbox (⚡ Multi-agent)
- `src/agent/dashboard/templates/base.html` — version "v0.6 · Phase 3"
- `pyproject.toml` — thêm `langgraph>=0.2.0`

**Verify:**
- LangGraph graph compile OK: 4 nodes (`__start__`, decide, run_tool, update) ✅
- `InvestigationEngine` dùng LangGraph (log: "Bắt đầu điều tra (via LangGraph)") ✅
- KB1 mock eval: 3 bước, verdict HIGH, root_cause đúng ✅ (via LangGraph)
- KB2 mock eval: 5 bước, verdict MEDIUM, root_cause đúng ✅ (via LangGraph)
- KB3, KB4 mock eval: PASS ✅
- Full mock eval 4/4 PASS (100%) qua LangGraph ✅
- MultiAgentEngine: log_tools=[get_error_breakdown, trace_request], metric_tools=[get_metrics, get_recent_deploys, get_dependencies] ✅
- MultiAgentEngine mock test: parallel run → merge → verdict HIGH ✅
- `multi_agent: True` trong payload → runner dùng MultiAgentEngine ✅
- Dashboard detail page: ENGINE LANGGRAPH badge + SVG graph hiển thị ✅
- Chat UI: multi-agent checkbox hiện đúng ✅
- Version sidebar: v0.6 · Phase 3 ✅

**Cổng Ngày 15 ✅ PASS:** KB1+KB2 pass qua LangGraph, multi-agent đúng (parallel specialists), graph hiển thị trên dashboard.

### [Session 18 — 2026-06-14] — Ngày 14: Dashboard SSE + Chat UI + Eval Charts

**Đã làm:**
- `src/agent/dashboard/sse.py` (mới) — SSE broker in-memory:
  - `publish_sync(inv_id, event_type, payload)` — gọi từ sync context qua `call_soon_threadsafe`
  - `_do_publish()` — đẩy event vào tất cả asyncio.Queue subscriber (skip nếu QueueFull)
  - `stream(inv_id)` — async generator: subscribe → yield SSE format, heartbeat 20s, close khi `type=verdict/done`
- `src/agent/engine/loop.py` — 2 thay đổi:
  - `run()` nhận thêm `investigation_id: Optional[str] = None` → dùng trực tiếp thay vì generate UUID ngẫu nhiên
  - `_emit_trace()` gọi `publish_sync()` sau khi ghi SQLite — SSE publish additive, không vỡ nếu lỗi
- `src/agent/intake/runner.py` — pass `investigation_id=key` (dedup_key) vào `engine.run()` → trigger response ID khớp SSE stream ID
- `src/agent/dashboard/router.py` — hoàn thiện (viết lại đầy đủ):
  - `GET /stream/{investigation_id}` — `StreamingResponse` với `sse_stream()` async generator
  - `GET /chat` — render chat.html với quick_scenarios + projects
  - `GET /eval` — pass `eval_labels/rates/steps/recall` cho Chart.js
  - Tất cả route cũ giữ nguyên
- `src/agent/dashboard/templates/chat.html` (mới) — Chat UI:
  - Quick scenario buttons (4 kịch bản, auto-fill + auto-submit)
  - Form manual: project/service/scenario/time_window/symptom
  - SSE live timeline: tool_call → tl-item animated, tool_result → update summary, verdict → hiện verdict card + link trace
- `src/agent/dashboard/templates/eval.html` — Chart.js:
  - Canvas `rateChart` (bar, màu PASS/FAIL theo ngưỡng 70%)
  - Canvas `stepsChart` (bar avg_steps + line combo Recall@1)
  - Chart.js CDN v4.4.0, dark theme colors
- `src/agent/dashboard/templates/detail.html` — SSE auto-connect khi investigation còn running:
  - EventSource subscribe → append tl-item real-time → reload link khi verdict
- `src/agent/dashboard/templates/base.html` — Chat nav link thêm vào

**Bug fix quan trọng:**
- `investigation_id` mismatch: engine tự generate UUID → không khớp với `dedup_key` trả về từ trigger
- Fix: `engine.run()` nhận `investigation_id` param; runner pass `key` (dedup_key) vào → SSE match đúng

**Verify:**
- `/dashboard/` load OK ✅ | `/dashboard/chat` load OK ✅ | `/dashboard/eval` load OK với Chart.js ✅
- Trigger → SSE stream → tool_call events flow real-time ✅
- SSE verdict event received end-to-end (scenario2 high confidence) ✅
- `investigation_id` match: trigger returns same ID as SSE stream URL ✅

**Cổng Ngày 14 ✅ PASS:** Trigger từ Chat UI → SSE stream real-time tool_call/verdict → Eval charts render.

### [Session 17 — 2026-06-14] — Ngày 13: Dashboard UI v1

**Đã làm:**
- `src/agent/dashboard/` (module mới):
  - `queries.py` — tầng đọc SQLite: `list_investigations()`, `get_investigation_detail()`, `get_projects_overview()`, `get_eval_summary()`
  - `router.py` — FastAPI APIRouter 5 routes: GET /, GET /investigations/{id}, GET|POST /trigger, GET /projects, GET /eval
  - `static/style.css` — dark theme, nav sidebar, table, timeline, verdict card, badge system, trigger layout, project grid
  - `templates/base.html` — layout chung + nav
  - `templates/index.html` — investigation list, filter dropdown, badge confidence
  - `templates/detail.html` — trace viewer timeline, verdict card (màu theo confidence), sidebar thông tin, Langfuse link
  - `templates/trigger.html` — form trigger (project/service/scenario/time_window/symptom), JS updateServices(), curl reference, recent list
  - `templates/projects.html` — project grid cards (services, LLM config, investigation count, API reference)
  - `templates/eval.html` — stats cards (total/correct/rate/gate), per-scenario table (rate/gate/recall@1/hall/steps/tokens)
- `src/agent/intake/server.py` v0.5 — mount `/dashboard/static` StaticFiles + include dashboard router
- `pyproject.toml` — thêm `jinja2>=3.1.0`, `python-multipart>=0.0.9`
- `.claude/launch.json` — preview config cho server port 8000

**Verify (browser):**
- `/dashboard/` — 38 investigations, filter project/confidence ✅
- `/dashboard/investigations/{id}` — verdict card HIGH (green border), timeline từng bước tool call ✅
- `/dashboard/trigger` — form dropdown project/service/scenario, JS updateServices() ✅
- `/dashboard/projects` — Default Project, LLM badge "anthropic (env)" ✅
- `/dashboard/eval` — 12/12 runs PASS, 4 scenarios 100% rate, ✓ PASS banner ✅

**Cổng Ngày 13 ✅ PASS:** Browser thấy history → click trace → trigger từ form.

### [Session 16 — 2026-06-14] — Ngày 12: Eval CI + Long-term Memory + Per-project LLM

**Đã làm:**

**A. Eval CI Framework:**
- `InvestigationState.total_tokens: int = 0` — accumulate từ `llm_resp.usage` mỗi bước LLM
- `loop.py` — gộp tokens sau mỗi `decide_next_action` call
- `eval_agent.py` — thêm metrics: `recall_at_1` (service đúng trong evidence bước 1), `hallucination` (keyword trong verdict không có trong evidence), `token_total`
- `eval_agent.py` — `_save_eval_results_to_db()`: lưu từng run vào `eval_results` SQLite (run_id UUID per batch)
- `.github/workflows/eval.yml` — CI: Python 3.9, init DB, seed, eval mock N=5, gate check ≥70% từ DB
- `data/schema.sql` + `data/migrate_projects.py` — thêm `eval_results` và `investigation_patterns` tables (step 8, 9)

**B. Long-term Memory:**
- `src/agent/memory/__init__.py` + `src/agent/memory/patterns.py` (mới):
  - `save_pattern(state)` — lưu pattern khi verdict HIGH (UPSERT với avg_steps rolling average)
  - `get_warm_start_hint(project_id, service, error_keywords)` — trả hint string từ DB
  - Classify root_cause_type: deploy_bug / pool_exhaustion / traffic_surge / provider_down
- `InvestigationState.warm_start_hint` — field mới, render ở đầu `summarize_for_llm()`
- `loop.py` — `run()` nhận `warm_start_hint` param
- `runner.py` — gọi `get_warm_start_hint()` trước investigation; `save_pattern()` sau verdict HIGH

**C. Per-project LLM Config:**
- `data/migrate_projects.py` step 7 — `ALTER TABLE projects ADD COLUMN llm_provider/llm_model/llm_config`
- `project_registry.py` — `get_project_llm()`, `set_project_llm()` (validate provider in supported set)
- `server.py` — `GET /projects/{pid}/llm`, `PATCH /projects/{pid}/llm`
- `src/agent/llm/gemini.py` (mới) — `GeminiClient`: google-genai SDK, function_declarations, usage_metadata tracking
- `factory.py` — thêm `extra_config` param, case `"gemini"` → `GeminiClient`
- `runner.py` — resolve LLM: project DB config > global env; log provider đang dùng

**Verify:**
- `total_tokens + warm_start_hint + summarize_for_llm` hoạt động đúng ✅
- `get_warm_start_hint` trả None khi DB rỗng ✅
- `get_project_llm('default')` trả None (chưa config) ✅
- Server routes `/llm` đăng ký đúng (GET + PATCH) ✅
- Eval mock 12/12 PASS, kết quả lưu DB ✅
- Commit: `feat: Ngày 12 — Eval CI + Long-term memory + Per-project LLM config`

**Cổng Ngày 12 ✅ PASS:** eval mock 12/12, DB populated, 3 tính năng hoạt động.

### [Session 15 — 2026-06-14] — Ngày 11: Langfuse Integration

**Đã làm:**
- `src/agent/llm/base.py` — thêm `usage: Optional[Dict[str, int]]` vào `LLMResponse`
- `src/agent/llm/anthropic.py` — populate `usage` từ `response.usage` (input_tokens / output_tokens)
- `src/agent/llm/openai_compat.py` — populate `usage` từ `response.usage` (prompt_tokens / completion_tokens)
- `src/agent/observability/__init__.py` (mới) — package init
- `src/agent/observability/langfuse_tracer.py` (mới) — tracer stateful per investigation:
  - Opt-in qua `LANGFUSE_PUBLIC_KEY` env — không set = no-op hoàn toàn
  - `start_step(n)` / `end_step()` → span hierarchy
  - `record_llm_call(input, output, usage, latency_ms)` → generation span với token tracking
  - `record_tool_call(name, args, summary, latency_ms)` → tool span
  - `record_verdict(stop_reason, verdict)` → trace.update + score(confidence)
  - `flush()` → đẩy batch lên Langfuse
- `src/agent/engine/loop.py` — tích hợp tracer:
  - `decide_next_action` trả 3-tuple `(tool_call, verdict_text, llm_response)`
  - `LangfuseTracer` khởi tạo đầu mỗi investigation, gọi xuyên suốt loop
  - Timing: `time.monotonic()` đo latency LLM + tool riêng biệt
  - SQLite trace (`_emit_trace`) không đổi — Langfuse hoàn toàn additive
- `pyproject.toml` — thêm `langfuse>=2.0.0`
- `.env.example` — thêm `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`

**Lưu ý kỹ thuật:** Langfuse SDK cài ra là v3.7.0 (khác v2 trong plan). API đổi:
- `lf.trace()` → `lf.start_span()` (root span = trace)
- `usage=` → `usage_details=`
- output truyền vào `start_generation/start_span` thay vì `.end()`
- Nested: `root_span.start_span()` / `root_span.start_generation()` thay vì method trên trace

**Verify:**
- `LLMResponse.usage` OK ✅
- `LangfuseTracer` no-op khi không có `LANGFUSE_PUBLIC_KEY` ✅
- Engine end-to-end còn chạy (mock LLM, 1 bước, verdict HIGH) ✅
- SQLite trace không vỡ ✅
- Kết nối key thật → trace test gửi lên cloud.langfuse.com thành công ✅

**Cổng Ngày 11 ✅ PASS:** Key đã điền vào `.env`, trace live trên Langfuse dashboard.

### [Session 14 — 2026-06-13] — Email channel + per-project channel config

**Đã làm:**
- `data/schema.sql` — thêm bảng `project_alert_channels` (project_id, channel, config JSON, enabled)
- `data/migrate_projects.py` — migration idempotent tạo bảng mới, đã chạy OK
- `src/agent/intake/project_registry.py` — thêm channel CRUD:
  - `list_project_channels(project_id)` — kể cả disabled
  - `get_enabled_project_channels(project_id)` — dùng bởi router
  - `set_project_channel(project_id, channel, config, enabled)` — upsert
  - `remove_project_channel(project_id, channel)`
  - `SUPPORTED_CHANNELS = {"telegram", "teams", "email"}`
- `src/agent/output/email.py` (mới) — SMTP adapter (stdlib, không dep mới):
  - HTML email đẹp (table layout, màu theo confidence)
  - Plain text fallback
  - Config keys: `to` (override SMTP_TO env), `cc` (optional)
  - Async qua `run_in_executor` (SMTP sync)
- `src/agent/output/telegram.py` — thêm `config` param → `config["chat_id"]` override env
- `src/agent/output/teams.py` — thêm `config` param → `config["webhook_url"]` override env
- `src/agent/output/router.py` — rewrite:
  - Ưu tiên 1: `project_alert_channels` DB → per-project channels với config riêng
  - Ưu tiên 2: fallback env `OUTPUT_CHANNELS` (backward compat)
  - Mỗi kênh độc lập — lỗi không chặn kênh khác
- `src/agent/intake/server.py` — thêm 4 routes:
  - `GET /projects/{pid}/channels`
  - `POST /projects/{pid}/channels` — body: `{channel, config, enabled}`
  - `PATCH /projects/{pid}/channels/{channel}` — update config/enabled
  - `DELETE /projects/{pid}/channels/{channel}`

**Verify:**
- Import chain OK ✅ | 4 routes đăng ký đúng ✅
- CRUD: set → list → get_enabled → remove ✅
- Router Test 1: project có DB channels → dispatch email+teams (warning vì no creds) ✅
- Router Test 2: không có DB channels → fallback env var telegram ✅

### [Session 13 — 2026-06-13] — Ngày 10: Output đa kênh (Teams)

**Đã làm:**
- `docs/10-roadmap-20-ngay.md` — cập nhật Ngày 10: Slack → Microsoft Teams
- `src/agent/output/teams.py` — Teams Incoming Webhook adapter:
  - `render_teams_card()` → MessageCard dict (Office 365 Connector format)
  - themeColor theo confidence: high=DC143C / medium=FF8C00 / low=FFD700 / insufficient=808080
  - facts: root_cause, evidence_summary, propagation_note, competing_hypotheses
  - Partial verdict render khi stop_reason != "verdict"
  - `push_verdict_to_teams()` — POST JSON, check `body == "1"` (Teams success indicator)
- `src/agent/output/router.py` — output fan-out:
  - `push_verdict(state)` đọc `OUTPUT_CHANNELS=telegram,teams` (mặc định: telegram)
  - Mỗi kênh độc lập — một lỗi không chặn kênh khác
  - Lazy import từng adapter → dễ thêm kênh mới
- `src/agent/intake/runner.py` — đổi `push_verdict_to_telegram` → `push_verdict` từ router

**Verify:**
- Import chain OK ✅
- `render_teams_card()` → dict đúng keys, themeColor=DC143C (high), 4 facts ✅
- `OUTPUT_CHANNELS=telegram,teams` → router gọi cả hai ✅
- Backward compat: không set OUTPUT_CHANNELS → chỉ telegram ✅
- Kênh lỗi log warning, không crash ✅

**Cổng Ngày 10 / Phase 1:** ✅ PASS
- Webhook + 4 kịch bản + Telegram + Teams (output router)

### [Session 12 — 2026-06-13] — Ngày 9: Kịch bản 3 & 4

**Đã làm:**
- `data/seed_scenario3.py` — KB3: auth-service DB connection pool exhaustion → cascade lên payment-gateway
  - Window: 08:00-09:00, spike tại 08:10
  - Lỗi: `AuthServiceTimeoutError` 84% tại payment-gateway; `DatabaseConnectionPoolTimeout` 82% tại auth-service
  - Metric mới: `connection_wait_time` cho auth-service (5ms → 857ms, ratio 169x)
  - Tín hiệu âm: không deploy, third-party-provider bình thường
  - 14,680 logs, 1,980 metric rows
- `data/seed_scenario4.py` — KB4: external traffic surge → rate limiting tại api-gateway
  - Window: 10:00-11:00, surge tại 10:15
  - Lỗi: `RateLimitError` 62% tại api-gateway (không phải TimeoutException)
  - Metric: `request_count` 203 → 1,007/min (5.0x)
  - Tín hiệu âm: không deploy, downstream services bình thường
  - 121,041 logs, 2,700 metric rows
- `scripts/eval_agent.py` cập nhật:
  - Thêm `SCENARIOS["scenario3"]` và `SCENARIOS["scenario4"]`
  - Thêm `MockLLM_KB3`, `MockLLM_KB4`
  - `--scenario` choices: `scenario1|scenario2|scenario3|scenario4|all` (thay `both`)
  - In cổng kiểm: "✅ PASS — tất cả kịch bản ≥70%"

**Verify:**
- KB3 signal: `AuthServiceTimeoutError` 84%, `connection_wait_time` 169x ✅
- KB4 signal: `RateLimitError` 62%, `request_count` 5x ✅
- Mock eval 4/4 ✅ PASS (100%), tất cả verdict, đúng root cause, đúng confidence ✅

**Cổng Ngày 9:** ✅ 4 kịch bản seed xong, eval mock PASS

### [Session 11 — 2026-06-13] — Project Isolation

**Đã làm:**
- `data/schema.sql` — thêm bảng `projects` (id TEXT PK slug, name, description, created_at, updated_at) và `project_services` (junction, PK composite). Index trên `project_services.service`.
- `data/migrate_projects.py` — migration idempotent: tạo 2 bảng mới, ALTER TABLE mcp_servers ADD COLUMN project_id (default 'default'), ALTER TABLE trace_events ADD COLUMN project_id, seed project 'default'. Đã chạy thành công.
- `src/agent/intake/project_registry.py` (mới):
  - `list_projects()`, `create_project()`, `get_project()`, `update_project()`, `delete_project()` (bảo vệ 'default', orphan MCP servers về 'default')
  - `list_project_services()`, `add_project_service()`, `remove_project_service()`
- `src/agent/intake/mcp_registry.py` — tất cả function nhận `project_id` parameter; `list_servers(project_id=None)` filter; `get_enabled_urls(project_id)` scoped; `remove_server`/`update_server` check cross-project.
- `src/agent/intake/normalizer.py` — `InvestigationRequest` thêm `project_id: str = "default"`; `dedup_key` format: `{project_id}|{service}|{scenario}|{time_window}`.
- `src/agent/engine/state.py` — `InvestigationState` thêm `project_id`, `available_services`; `summarize_for_llm()` hiển thị scope services.
- `src/agent/engine/loop.py` — `run()` nhận `project_id`, `available_services`; `_emit_trace()` ghi `project_id` vào trace_events.
- `src/agent/intake/runner.py` — `_get_mcp_urls_for_project(project_id)`, `_get_project_services(project_id)`; investigation pass project_id xuống engine.
- `src/agent/intake/server.py` v0.4.0 — đầy đủ 22 routes:
  - Backward compat: POST /trigger, GET/POST/PATCH/DELETE /mcp-servers[/{id}[/ping]]
  - GET/POST /projects, GET/PATCH/DELETE /projects/{id}
  - POST /projects/{id}/trigger (project-scoped investigation)
  - GET/POST /projects/{id}/services, DELETE /projects/{id}/services/{svc}
  - GET/POST/PATCH/DELETE /projects/{id}/mcp-servers[/{mid}[/ping]]

**Verify:**
- Syntax check: OK (2086 AST nodes)
- Import + route registration: 22 routes đúng ✅

**Chưa verify (cần test khi có server chạy):**
- CRUD projects qua HTTP
- Trigger /projects/{id}/trigger với project có service list
- Project-scoped MCP servers isolation

### [Session 10 — 2026-06-13]

**Đã làm (MCP Registry CRUD):**
- `data/schema.sql` — thêm bảng `mcp_servers` (id, name, url, description, enabled, created_at, updated_at). Index trên `enabled`. `CREATE TABLE IF NOT EXISTS` → migrate an toàn.
- `data/init_db.py` — chạy lại để tạo bảng mới không mất data cũ ✅
- `src/agent/intake/mcp_registry.py` — CRUD sync dùng `open_db()` (nhất quán với code hiện tại):
  - `list_servers()`, `add_server()`, `remove_server()`, `update_server()`, `get_enabled_urls()`, `get_server_by_id()`
  - Validate unique URL (IntegrityError → ValueError → 409)
- `src/agent/intake/server.py` cập nhật (v0.3.0):
  - FastAPI `lifespan` context: log danh sách MCP server lúc startup
  - `GET /mcp-servers` — list all (total, enabled count)
  - `POST /mcp-servers` — add (validate name/url, http/https check, 409 khi URL trùng)
  - `PATCH /mcp-servers/{id}` — update any fields (name, url, description, enabled)
  - `DELETE /mcp-servers/{id}` — remove (404 nếu không tồn tại)
  - `POST /mcp-servers/{id}/ping` — test live connection → trả tool list hoặc error message
- `src/agent/intake/runner.py` cập nhật:
  - `_get_all_mcp_urls()`: DB enabled (primary) + env var `MCP_SERVER_URLS` (bổ sung)
  - Không cần set env var để dùng MCP — server đăng ký qua API là đủ

**Verify:**
- List rỗng → add → list có 1 ✅
- Ping khi server up → trả 5 tools ✅
- Ping khi server down → trả `{status: "error", error: "..."}` ✅
- PATCH disable → enabled=0 ✅ | re-enable ✅
- URL trùng → 409 ✅ | DELETE id không tồn tại → 404 ✅
- Investigation không có `MCP_SERVER_URLS` env → tự đọc DB → connect MCP → 5 bước → Telegram ✅

### [Session 9 — 2026-06-13]

**Đã làm:**
- Cập nhật `docs/10-roadmap-20-ngay.md` Ngày 8: phản ánh đúng "agent là MCP consumer", không phải chỉ expose tool nội bộ; giải thích lý do không dùng MCP SDK (Python 3.9)
- `src/agent/tools/mcp_client.py` — `MCPClient` (JSON-RPC 2.0 over HTTP):
  - `connect()` → `initialize` handshake, giữ `aiohttp.ClientSession` sống suốt investigation
  - `get_tools()` → `tools/list`, wrap từng tool thành `Tool` contract
  - `_call_tool()` → `tools/call`, parse kết quả → `Observation` (JSON structured nếu server "biết", generic wrapper nếu external)
  - `_parse_observation()`: try JSON parse → reconstruct Observation đầy đủ, fallback wrap text
- `src/agent/tools/registry.py` cập nhật:
  - Đổi tên `ALL_TOOLS` → `ALL_LOCAL_TOOLS` (tường minh hơn)
  - Thêm `build_tool_registry(mcp_clients)` async: merge local + MCP, MCP override local cùng tên
  - Thêm `get_mcp_urls_from_env()`: đọc `MCP_SERVER_URLS=url1,url2,...`
- `src/agent/intake/runner.py` cập nhật:
  - Connect MCP clients trước investigation, close trong `finally`
  - Dùng `build_tool_registry(mcp_clients)` thay `get_tool_registry()`
  - Log rõ: connect OK, số tool discover, override
- `mcp_server/server.py` — FastAPI + JSON-RPC 2.0:
  - `POST /mcp`: initialize / tools/list / tools/call
  - `GET /health`: danh sách tool đang expose
  - `_EXPOSED_TOOLS` dict có thể bỏ tool bất kỳ để demo hot-unplug
- `scripts/start_mcp_server.py`

**Verify:**
- MCP server: initialize ✅ | tools/list (5 tools) ✅ | tools/call get_error_breakdown → Observation JSON đúng ✅
- MCPClient: connect → discover 5 tools → call get_recent_deploys → Observation đúng ✅
- Full pipeline: `MCP_SERVER_URLS=http://localhost:9000/mcp python scripts/trigger.py --scenario scenario1` → agent connect MCP → 5 bước → verdict "Deploy v2.3.1" → Telegram ✅
- Registry log: "MCP override local tool: X" × 5, Registry: 5 tools ✅
- Hot-unplug demo: bỏ `get_recent_deploys` khỏi `_EXPOSED_TOOLS` → server expose 4 tools ✅

**Quyết định lệch tài liệu:**
- Không dùng `mcp` Python SDK (requires Python 3.10+) → implement JSON-RPC 2.0 directly trên aiohttp. Upgrade path rõ ràng khi Python ≥ 3.10.

**Cổng Ngày 8:** ✅ MCP server + agent consumer + end-to-end investigation qua MCP + Telegram

### [Session 8 — 2026-06-13]

**Đã làm:**
- `src/agent/intake/adapters/_shared.py` — `parse_alert_time(iso_str)` → (time_window, date); floor về giờ +1h
- `src/agent/intake/adapters/prometheus.py` — `map_prometheus()`: labels.service, labels.scenario, annotations.summary, startsAt
- `src/agent/intake/adapters/grafana.py` — `map_grafana()`: tương tự Prometheus + fallback top-level `message`/`title`
- `src/agent/intake/adapters/sentry.py` — `map_sentry()`: project.slug, tags[key=scenario], firstSeen
- `src/agent/intake/adapters/__init__.py` — `route_adapter(source, payload)`, `list_sources()`; alias "alertmanager" → prometheus
- `src/agent/intake/server.py` cập nhật: `X-Alert-Source` header → `_resolve_request()` → adapter hoặc simple fallback; thêm `GET /adapters`

**Verify:**
- Prometheus: `startsAt 2024-01-15T14:05:00Z` → time_window=14:00-15:00, date=2024-01-15 ✅
- Grafana: cùng service+scenario+window → dedup `duplicate` ✅
- Sentry: `firstSeen 2024-01-15T15:03:00Z`, tags scenario=scenario2 → time_window=15:00-16:00 ✅
- Unknown source `datadog` → 422 có danh sách nguồn hỗ trợ ✅
- No header → fallback simple payload ✅

**Cổng Ngày 7:** ✅ 3 adapter pass curl test với payload thật

### [Session 7 — 2026-06-13]

**Đã làm:**
- `src/agent/intake/server.py` — FastAPI app:
  - `POST /trigger` → `map_simple_payload()` → `trigger_investigation()` → 202 Accepted ngay
  - `GET /health` → uptime, `active_investigations` count, danh sách `active_ids`
  - Dedup trả `{"status":"duplicate"}` thay vì tạo task rồi bỏ (sạch hơn)
- `scripts/start_server.py` — uvicorn wrapper với args `--host/--port/--reload`
- Thêm `fastapi>=0.100.0`, `uvicorn>=0.24.0` vào `pyproject.toml` dependencies
- Verify: import OK, `GET /health` trả JSON, `POST /trigger` 202 ngay, investigation chạy nền ~55s → Telegram push, dedup trigger trùng trả `duplicate`

**Cổng Ngày 6:** ✅ HTTP 202 → investigation nền → Telegram ping

### [Session 6 — 2026-06-13]

**Đã làm:**
- Xác nhận real LLM + Telegram đầy đủ:
  - KB1 trigger → 5 bước → verdict HIGH → Telegram "🔴 Deploy v2.3.1 @ 14:03" ✅
  - KB2 trigger → 8 bước → verdict HIGH → Telegram "🔴 third-party-provider sập @ 15:03" ✅
- Chat_id đúng: -1004205633841 (channel "911 Agent Bot")
- CODE ĐÓNG BĂNG từ đây.

**Tất cả cổng kiểm đã qua. MVP hoàn chỉnh.**

### [Session 5 — 2026-06-13]

**Đã làm:**
- Real LLM test thành công (ANTHROPIC_API_KEY mới):
  - KB1: 5 bước → verdict HIGH → "Deploy v2.3.1 lúc 14:03 gây TimeoutException từ 14:05" ✅
  - KB2: 8 bước → verdict HIGH → "third-party-provider sập từ 15:03, lan lên payment-gateway" ✅
  - Đường điều tra khác hẳn nhau (chống hardcode confirmed)
- Fix `_parse_verdict`: xử lý Markdown `**bold**`, `## heading` từ LLM; fallback parser nếu không match prefix
- Cải thiện SYSTEM_PROMPT: nhấn mạnh PLAIN TEXT format, cho phép kết luận sau loại trừ giả thuyết chính (không cần kiểm tất cả) → KB1 giảm từ 8 xuống 5 bước

**Cổng Ngày 4 thực chất:** ✅ real LLM + pipeline hoàn chỉnh — pending Telegram để push cuối

### [Session 4 — 2026-06-13]

**Đã làm:**
- `src/agent/output/telegram.py`:
  - `render_telegram_message()` — verdict → tin nhắn đọc trong 3s, emoji độ tin, quan trọng nhất lên đầu
  - `render_partial_verdict_message()` — không chết im lặng khi budget/timeout/error
  - `send_telegram()` — aiohttp POST đến Bot API, log dù có token hay không
  - `push_verdict_to_telegram()` — entry point, chọn renderer tự động
- `src/agent/intake/normalizer.py`:
  - `InvestigationRequest` dataclass — alert đã chuẩn hóa, có `dedup_key`
  - `map_simple_payload()` — mapper đơn giản cho trigger thủ công
  - `map_alertmanager_payload()` — mapper ví dụ Prometheus AlertManager format
- `src/agent/intake/runner.py`:
  - `run_investigation_background()` — chạy engine, handle timeout 5 phút, luôn push Telegram
  - `trigger_investigation()` — fire-and-forget, trả Task ngay
  - dedup bằng `_active_investigations: Set[str]`
- `scripts/trigger.py` — demo trigger: chọn scenario → investigation → Telegram
- Verify: import chain OK; pipeline trigger→investigate→push_telegram chạy đúng thứ tự

**Cổng Ngày 4:** ✅ code hoàn chỉnh — pending real LLM credit + Telegram credentials

### [Session 3 — 2026-06-13]

**Đã làm:**
- `data/seed_scenario2.py` — KB2: third-party-provider sập lúc 15:10, gateway cascade từ 15:11
  - Metric gateway latency KHÔNG lệch (1.0x baseline) — tín hiệu âm tính cài đúng
  - Trace_id NULL ở provider sau 15:10 (trace đứt)
  - Không có deploy trong window (tín hiệu âm tính thứ hai)
- Verify KB2 signals: gateway latency bình thường ✅, gateway lỗi 73.7% ConnectionRefused ✅, provider 82.2% ServiceUnavailable ✅
- Fix `get_error_breakdown`: samples giờ ưu tiên dominant error type sau spike time (tránh show noise errors cho LLM)
- `scripts/eval_agent.py` — chạy N lần mỗi kịch bản, đánh giá đúng/sai, confidence, steps, stop reason
  - Mock eval: 4/4 đúng root cause cả 2 kịch bản, confidence đúng mức
- Cập nhật `scripts/run_scenario.py`: hỗ trợ KB2 với window/symptom tự động
- Verify: KB1 (3 bước) và KB2 (5 bước) có đường điều tra khác nhau rõ rệt

**Cổng Ngày 3:** ✅ (với mock LLM) — pending real LLM test khi có API key

### [Session 2 — 2026-06-13]

**Đã làm:**
- Verify `get_metrics` OK → cổng Ngày 1 chính thức qua
- 3 tool còn lại: `get_recent_deploys`, `get_dependencies`, `trace_request` — verify chạy đúng
- Engine layer hoàn chỉnh:
  - `src/agent/engine/state.py` — `InvestigationState`, `Hypothesis`, `Evidence`, `Verdict` dataclass. Giả thuyết liên kết với bằng chứng qua `evidence_ids`. `summarize_for_llm()` tổng hợp state gọn.
  - `src/agent/engine/loop.py` — `InvestigationEngine`, `decide_next_action`, `run_tool`, `update_state` (hàm pure). Loop adaptive. 4 điều kiện dừng (verdict/budget/loop/error). Emit trace events SQLite.
  - System prompt enforce: VERDICT neo bằng chứng, phân biệt độ tin theo loại, buộc loại trừ giả thuyết cạnh tranh.
- `src/agent/tools/registry.py` — `get_tool_registry()` → `list[Tool]` đầy đủ 5 tool
- `scripts/run_scenario.py` — trigger KB1 end-to-end, render trace + verdict
- Verify engine end-to-end với mock LLM: 3 bước → verdict high confidence đúng root cause
- Trace events ghi SQLite đúng (tool_call, tool_result, verdict, investigation_start)

**Cổng Ngày 2 đã qua:** ✅ Agent chạy KB1 end-to-end, ra verdict thô (mock LLM)



### [Session 1 — 2026-06-13]

**Đã làm:**
- Thiết lập toàn bộ project scaffold:
  - `pyproject.toml` (Python 3.9+, deps: anthropic, openai, aiohttp, aiosqlite, python-dotenv)
  - `.env.example`, `.gitignore`
  - Venv tại `.venv/`, cài editable install (`pip install -e ".[dev]"`)
- `data/schema.sql` — DDL đầy đủ: logs, metrics, deploys, service_catalog, trace_events. Index đúng chỗ, WAL mode.
- `data/init_db.py` — khởi tạo DB từ schema.
- `data/investigation.db` — DB đã init (gitignored).
- LLM interface layer (`src/agent/llm/`):
  - `base.py` — Protocol `LLMClient`, shared types: `Message`, `ToolSpec`, `ToolCall`, `LLMResponse`
  - `anthropic.py` — `AnthropicClient` (dùng `anthropic` SDK)
  - `openai_compat.py` — `OpenAICompatibleClient` (cover OpenAI/Groq/Mistral/Ollama... qua `base_url`)
  - `factory.py` — `create_llm_client()` resolve từ env `LLM_PROVIDER`
- Tool contracts (`src/agent/tools/contracts.py`):
  - `Observation` dataclass (summary đầu, aggregates, samples≤5, total_count, truncated, metadata, trace_completeness)
  - `Tool` dataclass
  - `render_for_llm()` — serialize gọn cho LLM, không dump JSON thô
- `data/catalog.json` — 5 service: api-gateway, payment-gateway, auth-service, order-service, third-party-provider
- `data/seed_scenario1.py` — sinh data KB1 tham số hóa:
  - 7,549 log rows, 1,980 metric rows, 4 deploy rows
  - TimeoutException 80% tại payment-gateway sau 14:05
  - Latency p99 bật từ ~120ms → ~1100ms từ 14:05
  - Deploy v2.3.1 lúc 14:03 (root cause)
- `src/agent/storage/db.py` — `open_db()` helper
- `src/agent/tools/get_error_breakdown.py` — tool đầu, đã verify output OK
- `src/agent/tools/get_metrics.py` — tool thứ hai, code xong, chưa verify chạy
- `scripts/run_tool.py` — CLI gọi tool thủ công

**Chưa làm / còn dở (session 1):**
- (đã xong tất cả trong session 2)

## Việc cần làm ĐẦU SESSION TIẾP THEO (Ngày 5 / hoàn thiện)

**Bước 1 — Unblock real LLM (bắt buộc):**
```bash
# Option A: nạp credit Anthropic tại console.anthropic.com/settings/billing
# Option B: dùng OpenAI/Groq, sửa .env:
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini      # hoặc llama-3.3-70b-versatile trên Groq
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=            # để trống = OpenAI; https://api.groq.com/openai/v1 = Groq

# Rồi chạy:
.venv/bin/python3 scripts/run_scenario.py --scenario scenario1
.venv/bin/python3 scripts/run_scenario.py --scenario scenario2
```
Nếu agent đi sai hướng → tinh chỉnh system prompt trong `src/agent/engine/loop.py:SYSTEM_PROMPT`
hoặc description trong tool tương ứng.

**Bước 2 — Telegram (để có demo đầy đủ):**
```bash
# Tạo bot: @BotFather trên Telegram → /newbot → lấy token
# Lấy chat_id: gửi /start cho bot → https://api.telegram.org/bot<TOKEN>/getUpdates
# Điền vào .env:
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Chạy trigger đầy đủ:
.venv/bin/python3 scripts/trigger.py --scenario scenario1
.venv/bin/python3 scripts/trigger.py --scenario scenario2
```

**Bước 3 — Ngày 5: Quay video demo (không code thêm)**
- Mạch demo: terminal trigger KB1 → log streaming → Telegram ping điện thoại
- Rồi KB2: cùng lệnh, khác --scenario → đường điều tra khác hẳn
- Ghi lại điều tra đi qua dependency (KB2) → đây là wow moment

## Cấu trúc file đã tạo

```
src/agent/
  __init__.py
  llm/
    __init__.py  base.py  anthropic.py  openai_compat.py  factory.py
  tools/
    __init__.py  contracts.py  registry.py
    get_error_breakdown.py  get_metrics.py
    get_recent_deploys.py   get_dependencies.py  trace_request.py
  engine/
    __init__.py  state.py  loop.py
  intake/
    __init__.py  normalizer.py  runner.py
  output/
    __init__.py  telegram.py
  storage/
    __init__.py  db.py
data/
  schema.sql  init_db.py  catalog.json
  seed_scenario1.py  seed_scenario2.py  investigation.db
scripts/
  run_tool.py  run_scenario.py  trigger.py  eval_agent.py
```

## Quyết định lệch so với tài liệu thiết kế

- **Python 3.9** (tài liệu không chỉ định, hệ thống chỉ có 3.9) — không ảnh hưởng kiến trúc; dùng `from __future__ import annotations` để compat type hints.
- **Simulated total_count** = real_errors × 6.1 trong `get_error_breakdown` — con số scale factor có thể tinh chỉnh, không phải quyết định kiến trúc.

## Ghi chú cho session sau

- Activate venv: `source .venv/bin/activate` hoặc prefix mọi lệnh với `.venv/bin/python3`
- Load env: copy `.env.example` → `.env`, điền API key trước khi chạy engine
- DB đã có data KB1, không cần seed lại trừ khi muốn reset: `python3 data/seed_scenario1.py`
