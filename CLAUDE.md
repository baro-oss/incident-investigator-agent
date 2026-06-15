# CLAUDE.md — Chỉ thị vận hành cho dự án

> File này được nạp tự động đầu mỗi session. **Đọc kỹ trước khi làm bất cứ việc gì.**
> Tài liệu thiết kế chi tiết nằm trong `docs/`. File này là chỉ thị BẮT BUỘC, không phải gợi ý.

---

## Dự án là gì

**Agent điều tra sự cố microservice** — nhận triệu chứng (webhook alert hoặc trigger thủ công) → engine domain-agnostic tự điều tra qua loop adaptive + tool-calling → verdict neo bằng chứng → push Telegram.

Kiến trúc là **platform 4 cạnh pluggable** (intake · tool · output · model), engine bất biến ở giữa. Mỗi cạnh thêm adapter mà không sửa engine.

---

## Giai đoạn hiện tại

**Phase 1–4 ✅ HOÀN TẤT (20/20 ngày). Phase 5 ✅ HOÀN TẤT (25/25 ngày). Phase 6 ✅ HOÀN TẤT (26–30). Phase 7 ✅ HOÀN TẤT (31–35 — 63/63 tests). Phase 8 ✅ HOÀN TẤT (36–45 — 173/173 tests). Phase 9 ✅ HOÀN TẤT (46–50 — 262/262 tests) — engine lõi thông minh hơn: E10 tool-sequencing · E11 service prior · E12 specificity gate. Phase 10 ✅ HOÀN TẤT (51–55 — 444/444 tests) — agent đọc mã nguồn qua external MCP (GitHub/GitLab): F1 code seam + READ-ONLY guard · F2 deploy↔code synergy + E10/E11/E12 · V1 eval harness + E13 prior decay · P2 distill tổng quát · OPS1 catalog editor · T3 coverage 55%. Phase 11 📋 ĐÃ LÊN KẾ HOẠCH (56–60, CHƯA CODE) — Postgres Tier-2 + cloud container deploy: PG backend qua storage seam · dialect parity + đóng rò seam · Dockerfile prod + secrets fail-fast · SIGTERM drain + trace retention + bug B1/B2. Single-instance, deploy fresh.**

Plan 20 ngày gốc: `docs/10-roadmap-20-ngay.md`. Plan Phase 5: `docs/11-roadmap-phase-5.md`. Plan Phase 6: `docs/12-roadmap-phase-6.md`. Plan Phase 8 (ĐÃ XONG): `docs/13-roadmap-phase-8.md`. Plan Phase 9 (ĐÃ XONG): `docs/14-roadmap-phase-9.md`. Plan Phase 10 (ĐÃ XONG): `docs/15-roadmap-phase-10.md`. **Plan Phase 11 (KẾ HOẠCH TIẾP THEO): `docs/16-roadmap-phase-11.md`.**

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|-----------|
| 21 | Engine & Quality + Storage seam | Real-LLM eval smoke 6/6 · Tier-1 storage seam · recursion bugfix | ✅ |
| 22 | Auth & RBAC | RBAC động (root · role động · project groups · scoped assignment) | ✅ |
| 23 | Observability | Cost dashboard + verdict feedback loop + Project CRUD UI | ✅ |
| 24 | Integrations | Webhook signature (HMAC-SHA256) + Slack adapter + real MCP pack | ✅ |
| 25 | UI/UX + close | MCP server auth + Replay diff + tool test-run + search + Cổng Phase 5 | ✅ |

**Cổng Phase 5 PASS:** auth · cost · real-LLM eval · storage seam · Slack/MCP integration · replay diff · MCP auth · search · tool test-run.

**Phase 6 ✅ HOÀN TẤT (26–30):**

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|-----------|
| 26 | Engine core | Vòng đời giả thuyết thật (E1) · structured verdict (E5) · evidence-grounding guard (E2) | ✅ |
| 27 | Engine intelligence | Stop/loop thông minh + cổng giả thuyết cạnh tranh (E4) · confidence calibration (E3/D1) | ✅ |
| 28 | Security + custom LLM | API token webhook (A4) · secret at-rest (A2) · trace retention (A3) · per-project LLM endpoint riêng | ✅ |
| 29 | Reliability infra | Graceful shutdown (A1) · investigation queue in-process (B3) · rate limiting (B4) · sidebar grouping · light mode | ✅ |
| 30 | Ecosystem + close | PagerDuty/OpsGenie (C1) · callback outbound (C4) · root cause clustering (D3) · Cổng Phase 6 | ✅ |

**Defer → Future:** Tier-2 Postgres (B1, cần lệnh rõ) · bidirectional output (C2, phá READ-ONLY) · horizontal scale seam (B2). Chi tiết: `docs/12-roadmap-phase-6.md`.

**Phase 8 ✅ HOÀN TẤT (36–45 — 173/173 tests):**

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|-----------|
| 36 | E6 — Engine domain-agnostic | Rút hypothesis lifecycle khỏi engine → catalog theo miền (cạnh tool registry) + catalog fintech | ✅ |
| 37 | E7 — Hợp nhất path + parity | 1 nguồn stop/gate cho loop+graph · multi-agent ngang hàng (grounding+conflict+merge evidence_id) | ✅ |
| 38 | E8 — Real-LLM eval + calib | Smoke mở rộng (~$2) · feed ngưỡng calibration ngược vào engine (đóng vòng E3) | ✅ |
| 39 | T1 — Test adapters/output | 8 intake adapter + 5 output renderer | ✅ |
| 40 | T1 — Test infra + contract | queue/scheduler/registry/crypto + guard nguyên tắc #1 (Observation hợp lệ) | ✅ |
| 41 | T2 — CI gate tự động | GitHub Actions: pytest + mock eval + syntax/import + coverage | ✅ |
| 42 | P1 — Cost + perf | Prompt caching (prefix ổn định) + gọn context | ✅ |
| 43 | E9 — Structured verdict thẳng | args→Verdict trực tiếp (bỏ vòng args→text→parse) + cờ parse_degraded | ✅ |
| 44 | DX + docs | README gốc + Makefile + gộp API docs + polish demo | ✅ |
| 45 | Hardening + Cổng Phase 8 | Audit config/security + đóng pha | ✅ |

**Cổng Phase 8 PASS:** engine domain-agnostic · parity loop↔graph · calibration đóng vòng · CI xanh · 173 tests · prompt caching · E9 structured verdict · README+Makefile+API docs · security audit + startup warnings. Chi tiết: `docs/13-roadmap-phase-8.md`.

**Phase 9 ✅ HOÀN TẤT (46–50 — 262/262 tests) — engine-core round 3 (`docs/14-roadmap-phase-9.md`):**

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|-----------|
| 46 | E11 — Service prior | Pre-seed giả thuyết theo lịch sử service (`investigation_patterns` → catalog tag); confirm vẫn cần bằng chứng thật | ✅ |
| 47 | E10 — Tool sequencing | Hint `relevant_tools` cho giả thuyết open vào prompt (advisory) · parity loop↔graph miễn phí qua `_build_user_message` | ✅ |
| 48 | E12 — Specificity gate (lõi) | `compute_verdict_specificity` + `_apply_specificity_gate` nudge dùng chung loop+graph (idempotent, budget-guard) | ✅ |
| 49 | E12 — Multi-agent + đo | Downgrade/annotate multi-agent · dashboard specificity + avg-steps before/after · real-LLM smoke ~$2 | ✅ |
| 50 | Tests + CI + Cổng P9 | 262 tests · CI xanh · audit degrade an toàn · đóng pha | ✅ |

**Cổng Phase 9 PASS:** E11 pre-seed + 27 tests · E10 hint+parity + 21 tests · E12 gate+downgrade+dashboard + 41 tests · nguyên tắc #2 giữ vững · mock eval 4/4 · 262/262 tests · CI xanh. Chi tiết: `docs/14-roadmap-phase-9.md`.

**Phase 10 ✅ HOÀN TẤT (51–55 — 444/444 tests) — agent đọc mã nguồn qua external MCP (`docs/15-roadmap-phase-10.md`):**

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|-----------|
| 51 | F1 — Code seam over MCP | `code_distill` wrapper (raw diff/file → Observation chưng cất, P#1) · risk interpreter generic · `service_repos` mapping · READ-ONLY guard (chặn write/PR/merge) · UI repo config | ✅ |
| 52 | F2 — Deploy↔code + specificity | `get_recent_deploys` (giữ nguyên) → đọc diff version nghi vấn qua MCP · catalog code-aware (gắn code tool vào `relevant_tools` deploy_bug → E10/E11 tự kích) · code→E12 specificity + grounding | ✅ |
| 53 | V1 + E13 — Eval harness + prior decay | Đo avg-steps/specificity before-after (mock; real-LLM ~$2 chờ credit) · time-weight `investigation_patterns` (prior decay) + refresh calibration | ✅ |
| 54 | P2 + OPS1 — Distill tổng quát + catalog editor | Distill mọi external MCP (sửa truncate 500-char) + budget · catalog editor UI (thêm hypothesis/keyword/tool+repo mapping không sửa Python) | ✅ |
| 55 | T3 + Close — Coverage + Cổng P10 | Coverage dashboard/server/runner + CI lớp code · docs/README · audit READ-ONLY + degrade safe · đóng pha | ✅ |

**Ràng buộc lõi Phase 10:** hệ thống KHÔNG quản lý source — code chỉ đọc qua external MCP (GitHub/GitLab là extension) · `get_recent_deploys` giữ nguyên · READ-ONLY tuyệt đối với code · real-LLM eval defer (mock + chờ credit) · bidirectional/horizontal vẫn Future.

**Phase 11 🔄 ĐANG LÀM (56–60) — Postgres Tier-2 + deploy lên GreenNode AgentBase (`docs/16-roadmap-phase-11.md`):**

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|-----------|
| 56 | PG backend adapter + local infra | psycopg connection shim (`?`→`%s`, dict-row, lastrowid) + connection pool qua storage seam · `schema_postgres.sql` + init/seed PG · `docker-compose` postgres local | ✅ |
| 57 | Dialect parity + đóng rò seam + CI matrix | `INSERT OR`→`ON CONFLICT` · `datetime/julianday` · **fix `auth/rbac.py` `import sqlite3`** · CI matrix `DB_BACKEND=[sqlite,postgres]` · 444 tests xanh trên cả 2 | ✅ |
| 58 | Container & config hardening + port 8080 + B1 | **port 8000→8080 (HARD AgentBase)** · Dockerfile non-root + multi-stage + amd64 + HEALTHCHECK · secrets fail-fast (prod) · `/health/ready` (DB ping) vs `/health` · **B1: `_make_error_state` truyền project_id** | ☐ |
| 59 | Lifecycle + observability + retention + B2 | SIGTERM drain in-flight · JSON log opt-in · `/health` sâu · trace_events retention (TTL) · **B2: 2 `_emit_trace` thêm project_id (parity graph.py)** | ☐ |
| 60 | Deploy lên AgentBase + smoke + Cổng P11 | build amd64 → managed CR (`vcr.vngcloud.vn`) → `runtime.sh create` (`min=max=1`) · `docker-compose.prod` + runbook/README/api docs · E2E smoke (PG) · audit READ-ONLY/degrade · đóng pha | ☐ |

**Ràng buộc lõi Phase 11:** Postgres = backend runtime prod (Tier-2 kích hoạt theo lệnh người dùng — **bắt buộc vì AgentBase disk ephemeral, không PVC → SQLite không bền**) · SQLite vẫn default dev, seam giữ cả 2 · **nền tảng = GreenNode AgentBase**: port **8080** + build **amd64** + deploy qua CR/`runtime.sh` (KHÔNG `kubectl`) + 4 biến `GREENNODE_*` auto-inject không set tay · **single-instance** = `min=max=1 replica` (KHÔNG externalize queue/dedup/SSE — horizontal scale vẫn Future) · deploy fresh (init+seed PG, không migrate data SQLite cũ) · DB swap tuyệt đối không rò lên engine/tools · READ-ONLY + 4 nguyên tắc giữ. Skills tham chiếu: `greennode-agentbase-skills/`.

**Trạng thái chi tiết hơn:** xem `BUILD_STATE.md`.

---

## Quy tắc không over-engineer

Bạn (Claude) sẽ có xu hướng tự thêm thứ "chuyên nghiệp hơn". **KHÔNG.** Khi thấy mình định làm bất kỳ cái nào dưới đây mà người dùng chưa yêu cầu rõ, DỪNG và hỏi trước.

### Vẫn còn trong danh sách KHÔNG (chưa làm / chưa được phép):
- ⚠️ **Postgres Tier-2 ĐÃ ĐƯỢC KÍCH HOẠT cho Phase 11** (người dùng ra lệnh 2026-06-15, deploy cloud). PG = backend runtime **prod** qua `DB_BACKEND=postgres` + `DATABASE_URL`; **SQLite WAL vẫn là default dev/test** qua cùng storage seam (Phase 5 Ngày 21). ❌ KHÔNG MySQL/vector DB ở runtime · ❌ KHÔNG bỏ SQLite. DB swap **chỉ dưới seam** — engine/tools/dashboard/intake KHÔNG đổi.
- ❌ KHÔNG Kafka / message broker → **asyncio background task**
- ❌ KHÔNG sinh GB data thật → **vài nghìn dòng/kịch bản**; dùng `total_count` lớn để giả lập quy mô
- ❌ KHÔNG OpenTelemetry → **trace ghi SQLite + Langfuse opt-in** là đủ

> **Đã graduated (trước đây cấm, nay đã build Phase 2–4 — KHÔNG làm lại):** LangGraph (D15) · multi-agent (D15) · Langfuse (D11) · Dashboard UI (D13–17) · Fintech domain (D18). Chi tiết: `BUILD_STATE.md`.

### Đã làm (do người dùng yêu cầu rõ — KHÔNG làm lại từ đầu, không thay thế):
- ✅ FastAPI webhook server (POST /trigger, GET /health, v0.4.0)
- ✅ 3 adapter intake: Prometheus, Grafana, Sentry (routing qua X-Alert-Source)
- ✅ MCP hot-plug: agent là MCP consumer (JSON-RPC 2.0 over HTTP trực tiếp, không dùng mcp SDK — nay đã lên Python 3.14, SDK khả dụng nhưng giữ JSON-RPC vì đã chạy ổn)
- ✅ MCP Registry lưu DB (SQLite), CRUD API, /ping test live
- ✅ Project Isolation: multi-tenant qua projects + project_services, MCP scoped per project
- ✅ 4 kịch bản: deploy bug · provider sập · DB pool exhaustion · traffic surge
- ✅ Output router: `OUTPUT_CHANNELS=telegram,teams,email` fan-out; Teams + Email adapter
- ✅ Per-project alert channels: `project_alert_channels` DB, mỗi project config kênh riêng (telegram/teams/email với config override)

### Roadmap — câu chuyện pitch (chưa phải code):
**Phase 5** ✅ (xem `docs/11-roadmap-phase-5.md`): RBAC/auth · cost dashboard · Slack output · webhook signature · real MCP pack · storage seam.
**Phase 6** ✅ (xem `docs/12-roadmap-phase-6.md`): engine quality (hypothesis lifecycle · evidence-grounding verdict · calibration) · webhook auth + secret at-rest · graceful shutdown + in-process queue · PagerDuty/deploy-hook intake.
**Phase 7** ✅ (Ngày 31–35): proactive monitoring scheduler · multi-agent conflict resolution · Docker + export · Redis SSE seam · 63/63 tests.
**Phase 8** ✅ (Ngày 36–45, `docs/13`): engine domain-agnostic (hypothesis catalog theo miền) · hợp nhất loop/graph path + multi-agent parity · real-LLM calibration đóng vòng · test adapters/output/infra + CI gate · prompt caching · DX/docs.
**Phase 9** ✅ (Ngày 46–50, `docs/14`): engine lõi thông minh hơn — E10 hypothesis-guided tool sequencing · E11 cross-investigation service prior · E12 verdict specificity gate. 100% engine-core, không cạnh mới.
**Phase 10** ✅ (Ngày 51–55, `docs/15`): agent đọc mã nguồn qua external MCP (GitHub/GitLab) — code-distill seam (P#1) + READ-ONLY guard + `service_repos` mapping · synergy deploy↔code (E10/E11) + code→E12 specificity · eval harness (mock) + prior decay · distill tổng quát + catalog editor · coverage 55%/CI. 444/444 tests.
**Phase 11** 📋 (Ngày 56–60, `docs/16`, CHƯA CODE): Postgres Tier-2 + deploy lên **GreenNode AgentBase** — PG backend qua storage seam (psycopg shim + pool, **bắt buộc vì AgentBase disk ephemeral**) · dialect parity + đóng rò seam `rbac.py` + CI matrix sqlite|postgres · **port 8080 + build amd64** + Dockerfile prod (non-root/healthcheck/secrets fail-fast) · deploy qua managed CR + `runtime.sh` (single-instance `min=max=1`) · SIGTERM drain + trace retention · bug fix B1 (project_id ở error state) + B2 (project_id ở trace tool). Deploy fresh.
**Future:** MySQL backend (seam sẵn) · bidirectional integration / code action (phá READ-ONLY, cần duyệt) · horizontal scale seam (externalize queue/dedup/SSE + Redis, cho multi-replica) · real-LLM eval đầy đủ (chờ credit, harness từ P10).

---

## Stack hiện tại (không đổi nếu không có lệnh rõ)

| Thành phần | Hiện thực |
|------------|-----------|
| Ngôn ngữ | Python 3.14 (nâng từ 3.9 ở Ngày 45) |
| Agent loop | Tự viết (loop adaptive, hàm pure) |
| LLM | Anthropic API (factory hỗ trợ OpenAI-compat: Groq, Mistral, ...) |
| Storage | Storage seam (`DB_BACKEND`) — **SQLite WAL** (default dev) · **Postgres** (prod, Tier-2 từ Phase 11). Bảng: logs, metrics, deploys, trace_events, mcp_servers, projects, project_services |
| HTTP server | FastAPI + uvicorn |
| HTTP client | aiohttp (MCP client, Telegram push) |
| MCP protocol | JSON-RPC 2.0 over HTTP (không dùng mcp SDK) |
| Output | Telegram · Teams · Email — router fan-out, per-project channel config |
| Multi-tenant | Projects (TEXT PK slug) + project_services (junction table) |
| Async | asyncio background task (fire-and-forget) |

---

## Bốn nguyên tắc kiến trúc (mọi quyết định code phải tuân)

1. **LLM không bao giờ thấy dữ liệu thô.** Tool aggregate bằng SQL, trả Observation đã chưng cất (summary + aggregates + ≤5 samples + total_count). Trả raw rows → SAI.

2. **Một đường ranh (seam).** Engine chỉ thấy `list[Tool]` đồng nhất (name, description, input_schema, run→Observation). Engine KHÔNG được biết "log"/"SQLite"/"MCP"/"project" là gì.

3. **Lõi deterministic, agent chỉ điều phối.** Tính toán nằm trong tool; LLM chỉ chọn tool + quyết điểm dừng.

4. **Async từ biên nhận; một nguồn structured, nhiều renderer.** Observation/verdict/trace đều structured, render ra text chỉ ở biên tiêu thụ.

---

## Yêu cầu thiết kế code (không phải build thêm — để dễ mở rộng sau)

- `InvestigationState` là **dataclass thuần dữ liệu**, tách khỏi logic.
- Mỗi bước loop là **hàm pure**: `decide_next_action(state)`, `run_tool(action)`, `update_state(state, obs)`. Lên LangGraph sau = bọc mỗi hàm thành node.
- Giả thuyết và bằng chứng **liên kết nhau** qua `evidence_ids` — không phải hai list rời.
- Tool registry: `build_tool_registry(mcp_clients)` merge local + MCP, MCP override local cùng tên.

---

## Những điểm dễ làm sai

- **Observation:** summary đặt ĐẦU, mang signal bước kế cần. Tool TỰ diễn giải ("gấp 9 lần baseline"), không trả số thô. → `docs/04`, `docs/06`.
- **Loop:** adaptive, KHÔNG plan-ahead. Đưa state đã tổng hợp, KHÔNG lịch sử thô. → `docs/05`.
- **Dừng:** model tầm trung hay dừng sớm → buộc kiểm "đã loại trừ giả thuyết cạnh tranh chưa". Có step budget + phát hiện lặp. → `docs/05`.
- **Verdict:** neo bằng chứng (không claim trần), độ tin theo LOẠI bằng chứng, "chưa đủ bằng chứng" là hợp lệ, phân biệt lỗi-gốc/lỗi-lan. → `docs/05`.
- **Trace đứt:** `trace_request` PHẢI báo cáo chỗ mất dấu; bắc cầu bằng tương quan thời gian + HẠ độ tin + gắn cờ suy đoán. Tool im lặng về chỗ đứt = agent bịa. → `docs/06`, `docs/07`.
- **Output:** mọi nhánh kết thúc (thành công / timeout / lỗi) đều push Telegram, không chết im lặng. → `docs/08`.
- **Project isolation:** mọi investigation mang `project_id`; `dedup_key` format: `{project_id}|{service}|{scenario}|{time_window}`. MCP tools chỉ từ server thuộc project đó.

---

## Ranh giới fintech (an toàn — bắt buộc)

Chỉ synthetic data, tool **READ-ONLY**, không PII, không kết nối hệ thống thật. Tool không được có thao tác ghi/xóa/sửa lên bất kỳ nguồn nào ngoại trừ trace_events (ghi trace nội bộ).

---

## Quy trình làm việc qua nhiều session

1. **Đầu session:** đọc file này + `BUILD_STATE.md` (trạng thái) + `docs/10-roadmap-20-ngay.md` (plan Phase 1–4).
2. **Bám ngày hiện tại** trong Phase — xem bảng "Giai đoạn hiện tại" ở trên. Kết thúc bằng verify cổng kiểm của ngày đó.
3. **Cuối session:** cập nhật `BUILD_STATE.md` (đã xong gì, cổng nào đã qua, quyết định lệch so với tài liệu).
4. **Cái lõi không được vỡ:** engine chạy 2 kịch bản end-to-end + push Telegram. Ưu tiên nó trên mọi thứ "đẹp để có".
5. **Lệch khung:** điều chỉnh chi tiết (schema thêm field, tách tool) thì tự làm; lệch 4 nguyên tắc hoặc stack → hỏi người dùng trước.
6. **Git commit cuối ngày:** sau khi cổng kiểm pass và `BUILD_STATE.md` đã cập nhật, tạo 1 commit:
   ```bash
   git add -A
   git commit -m "feat: Ngày N — <tóm tắt ngắn>"
   ```
   Quy tắc commit bắt buộc:
   - **KHÔNG BAO GIỜ** commit `.env` hoặc bất kỳ file chứa secret/API key thật.
   - Chỉ `.env.example` (template rỗng) mới được commit.
   - `.gitignore` đã cover: `.env`, `.env.*` — KHÔNG override hay bypass.

---

## Cấu trúc file (hiện tại)

```
.
├── CLAUDE.md                   ← file này (chỉ thị, tự nạp)
├── AGENTS.md                   ← bản sao cho Cowork
├── BUILD_STATE.md              ← trạng thái build (cập nhật mỗi session)
├── docs/
│   ├── README.md               ← mục lục tổng quan
│   ├── 01-roadmap.md
│   ├── 02-architecture.md
│   ├── 03-plan-5-ngay.md       ← lịch sử MVP ban đầu (không còn là plan chính)
│   ├── 04-hop-dong-tool-va-observation.md
│   ├── 05-engine.md
│   ├── 06-tool-layer.md
│   ├── 07-synthetic-data-va-kich-ban.md
│   ├── 08-vong-tu-chu-va-output.md
│   ├── 09-trace-va-storage.md
│   ├── 10-roadmap-20-ngay.md  ← Phase 1–4 (đã xong)
│   ├── 11-roadmap-phase-5.md  ← Phase 5 (đã xong)
│   ├── 12-roadmap-phase-6.md  ← Phase 6 (đã xong)
│   ├── 13-roadmap-phase-8.md  ← Phase 8 (đã xong)
│   ├── 14-roadmap-phase-9.md  ← Phase 9 (đã xong)
│   ├── 15-roadmap-phase-10.md ← Phase 10 (đã xong)
│   └── 16-roadmap-phase-11.md ← KẾ HOẠCH TIẾP THEO (Phase 11, Ngày 56–60, chưa code)
├── data/
│   ├── schema.sql              ← DDL đầy đủ (có projects, project_services, mcp_servers)
│   ├── init_db.py
│   ├── migrate_projects.py     ← migration idempotent (chạy khi clone mới)
│   ├── seed_scenario1.py
│   ├── seed_scenario2.py
│   └── investigation.db        ← gitignored
├── mcp_server/
│   └── server.py               ← demo MCP server (FastAPI + JSON-RPC 2.0)
├── scripts/
│   ├── start_server.py         ← uvicorn FastAPI server (port 8000)
│   ├── start_mcp_server.py     ← uvicorn MCP demo server (port 9000)
│   ├── trigger.py              ← trigger investigation thủ công
│   ├── run_scenario.py
│   ├── run_tool.py
│   └── eval_agent.py
└── src/agent/
    ├── llm/                    ← base.py, anthropic.py, openai_compat.py, factory.py
    ├── tools/
    │   ├── contracts.py        ← Tool, Observation dataclass (đường ranh)
    │   ├── registry.py         ← build_tool_registry(mcp_clients)
    │   ├── mcp_client.py       ← MCPClient (JSON-RPC 2.0 over HTTP)
    │   ├── get_error_breakdown.py
    │   ├── get_metrics.py
    │   ├── get_recent_deploys.py
    │   ├── get_dependencies.py
    │   └── trace_request.py
    ├── engine/
    │   ├── state.py            ← InvestigationState, Hypothesis, Evidence, Verdict
    │   └── loop.py             ← InvestigationEngine, decide/run_tool/update_state (pure)
    ├── intake/
    │   ├── server.py           ← FastAPI v0.4.0 (22 routes, project-scoped)
    │   ├── runner.py           ← fire-and-forget background task
    │   ├── normalizer.py       ← InvestigationRequest (có project_id)
    │   ├── mcp_registry.py     ← CRUD mcp_servers DB (project-scoped)
    │   ├── project_registry.py ← CRUD projects + project_services
    │   └── adapters/
    │       ├── __init__.py     ← route_adapter(), list_sources()
    │       ├── _shared.py      ← parse_alert_time()
    │       ├── prometheus.py
    │       ├── grafana.py
    │       └── sentry.py
    ├── output/
    │   └── telegram.py         ← push_verdict_to_telegram()
    └── storage/
        └── db.py               ← open_db()
```

---

## Khởi động nhanh (khi clone hoặc session mới)

```bash
# 1. Activate venv
source .venv/bin/activate   # hoặc prefix mọi lệnh với .venv/bin/python3

# 2. Env vars (copy .env.example → .env, điền API key)
cp .env.example .env

# 3. Init / migrate DB (idempotent — chạy khi có file mới trong data/)
python3 data/init_db.py
python3 data/migrate_projects.py

# 4. Seed data (nếu DB trống)
python3 data/seed_scenario1.py
python3 data/seed_scenario2.py

# 5. Chạy server
python3 scripts/start_server.py              # port 8000
python3 scripts/start_mcp_server.py          # port 9000 (optional — MCP demo)

# 6. Trigger investigation
curl -X POST localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-gateway","scenario":"scenario1","time_window":"14:00-15:00"}'
# hoặc project-scoped:
curl -X POST localhost:8000/projects/default/trigger \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-gateway","scenario":"scenario1","time_window":"14:00-15:00"}'
```
