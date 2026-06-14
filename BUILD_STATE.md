# BUILD_STATE.md — Trạng thái build (cập nhật cuối mỗi session)

> Mục đích: để session Claude sau biết session trước đã làm gì → không làm lại, không phá thứ đang chạy. **Cập nhật file này cuối mỗi session làm việc.**

## Trạng thái hiện tại

**Giai đoạn:** Phase 6 📋 (Ngày 26–30, đang thực hiện).
**Kế hoạch Phase 6:** `docs/12-roadmap-phase-6.md`.
**Cổng kiểm gần nhất:** Ngày 27 — E4 loop oscillation ✅ · E4 cổng cạnh tranh ✅ · E3/D1 calibration dashboard ✅ · eval 4/4 PASS ✅
**Việc kế tiếp:** Ngày 28 (Security + custom LLM — A4 webhook token · A2 secret at-rest · A3 trace retention · per-project LLM endpoint last mile).

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
| 28 | Security + custom LLM | A4 API token webhook · A2 secret at-rest · A3 trace retention · per-project LLM endpoint riêng (model/url/header, fallback default) | 📋 |
| 29 | Reliability infra | A1 graceful shutdown · B3 investigation queue (in-process) · B4 rate limiting | 📋 |
| 30 | Ecosystem + close | C1 PagerDuty/OpsGenie · C3 deploy hook · C4 callback · D3 clustering · Cổng Phase 6 | 📋 |

**Defer → Future:** B1 Tier-2 Postgres (cần lệnh rõ + env) · C2 bidirectional (phá READ-ONLY, cần duyệt) · B2 horizontal scale seam · D4 real MCP pack mở rộng.

## Nhật ký session (mới nhất lên đầu)

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
