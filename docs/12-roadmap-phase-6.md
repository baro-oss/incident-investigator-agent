# 12 — Roadmap Phase 6 (Ngày 26–30): Engine Quality + Production-readiness

> Tiếp nối sau **25/25 ngày (Phase 1–5 ✅ hoàn tất)**. File này là kế hoạch Phase 6.
> Mục tiêu: từ **"chạy được + tin được"** → **"điều tra GIỎI hơn + deploy được + mở rộng được"**.
> Plan trước: `docs/10-roadmap-20-ngay.md` (Phase 1–4) · `docs/11-roadmap-phase-5.md` (Phase 5). File này tiếp nối.

---

## Ràng buộc cố định (không đổi)

- ❌ KHÔNG Kafka / message broker → **investigation queue là in-process asyncio** (Day 29), không phải broker ngoài.
- ❌ KHÔNG chạy Postgres/MySQL ở runtime → **giữ SQLite WAL**. Tier-2 (Postgres chạy thật) **vẫn ở Future** — cần lệnh rõ.
- ❌ KHÔNG infra nặng → `pip install` + env vars là đủ.
- ✅ **READ-ONLY giữ nguyên** — output chỉ push (Telegram/Slack/email/callback), KHÔNG ghi ngược vào hệ thống ngoài. Bidirectional (C2) ở Future.
- ⚠️ **Lõi không được vỡ:** mọi ngày engine (26–27) phải qua **regression gate** = eval 4/4 mock + 2 KB end-to-end + push Telegram. Cải thiện engine KHÔNG được phá hồi quy.

---

## Bối cảnh & quyết định chốt (session lập kế hoạch)

- **Nhấn mạnh của người dùng:** cải thiện **engine core** bên cạnh tính năng production. Đọc code xác nhận danh sách đề xuất A–D gần như không chạm engine (chỉ D1/D2 engine-adjacent) → bổ sung **Nhóm E (Engine quality)** là spine của Phase 6.
- **Cấu trúc engine-first 2+2+1:** 2 ngày engine (26–27) · 2 ngày production hardening (28–29) · 1 ngày ecosystem + close (30).
- **3 P0:** engine quality (D26–27) · webhook auth + secret at-rest (D28) · graceful shutdown + queue (D29).
- **Chốt qua trao đổi:**
  - Tier-2 Postgres (B1) → **Future** (runtime vẫn SQLite; seam Tier-1 đã đủ chứng minh swappable; migration thật cần env + lệnh rõ).
  - Bidirectional output (C2) → **Future** (giữ ranh giới READ-ONLY; cần người dùng duyệt rõ mới làm).
  - Horizontal scale seam (B2) → **Future** (1 instance đang đủ; chưa có nhu cầu thật).

### 5 điểm yếu engine đã xác nhận trong code (cơ sở Nhóm E)

| # | Điểm yếu | Vị trí | Hệ quả |
|---|----------|--------|--------|
| E1 | Vòng đời giả thuyết không hoạt động — luôn `open`, `confidence` không bao giờ set, mọi evidence append vào mọi hypothesis | `loop.py:_update_hypotheses/_upsert_hypothesis` · `state.py:add_hypothesis` | "Loại trừ giả thuyết cạnh tranh" không được track trong state — chỉ là decorative |
| E2 | Verdict nhận ngay khi thấy chữ "VERDICT", không kiểm neo bằng chứng | `loop.py` (decide) · `graph.py:decide_node` | Nguyên tắc #1 (chống bịa) chỉ enforce bằng prompt; hallucination chỉ đo hậu kỳ |
| E3 | Confidence là LLM tự khai, parse text, default `medium` âm thầm | `loop.py:_parse_verdict` (`conf_map.get(..., "medium")`) | Không calibration; gốc của insight D21 "under-confident trên fintech" |
| E4 | Loop detection chỉ bắt 2 call liên tiếp giống hệt; step budget cứng = 10; không có cổng dừng | `state.py:is_looping` | Không bắt dao động A→B→A→B; không enforce "đã loại trừ cạnh tranh chưa" trước verdict |
| E5 | Parse verdict mong manh (prefix tiếng Việt từng dòng) | `loop.py:_parse_verdict` | LLM diễn đạt khác → fallback yếu, confidence sai âm thầm |

---

## Tổng quan Phase 6

```
Day 26  Engine core          — E1 vòng đời giả thuyết thật + E5 structured verdict + E2 evidence-grounding guard
Day 27  Engine intelligence  — E4 stop/loop thông minh + cổng giả thuyết cạnh tranh + E3/D1 calibration + D2 baseline auto-update
Day 28  Security + custom LLM — A4 API token webhook + A2 secret at-rest + A3 trace retention + D per-project LLM endpoint (model/url/header)
Day 29  Reliability infra     — A1 graceful shutdown + B3 investigation queue + B4 rate limiting (in-process, no Kafka)
Day 30  Ecosystem + close     — C1 PagerDuty/OpsGenie + C3 deploy hook + C4 callback + D3 clustering + Cổng Phase 6
```

| Ngày | Theme | Trọng lượng | Trạng thái |
|------|-------|:-----------:|-----------|
| 26 | Engine core | **L** | ☐ |
| 27 | Engine intelligence | M+ | ☐ |
| 28 | Security + custom LLM | M+ | ☐ |
| 29 | Reliability infra | M+ | ☐ |
| 30 | Ecosystem + close | M | ☐ |

**Phụ thuộc cứng:** D26 → D27 (intelligence xây trên vòng đời giả thuyết thật). D27 calibration cần **dữ liệu eval thật** (D21 real-LLM eval) + **feedback** (D23 👍/👎). D28 A4 dùng lại bảng `api_tokens` + verify code đã có từ D22. D29 A1 drain queue của B3 (cùng ngày, thứ tự nội bộ).

---

## Ngày 26 — Engine Core *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** biến hợp đồng giả thuyết/bằng chứng/verdict từ "decorative" → **thật sự enforce trong state**. Đây là lõi của "điều tra giỏi hơn".

### A. E1 — Vòng đời giả thuyết thật *(must-land)*
- `state.py` — `Hypothesis` có chuyển trạng thái thật: `open → confirmed | ruled_out`; `confidence` được set theo LOẠI bằng chứng (tương quan thời gian + cơ chế nhân quả = high; chỉ tương quan = medium; suy đoán = low).
- `loop.py:_update_hypotheses` — bỏ heuristic match chuỗi cứng; thay bằng: (1) gắn evidence vào hypothesis **theo liên quan** (service/tool/keyword khớp), không append mù vào mọi hypothesis open; (2) đánh `ruled_out` khi bằng chứng mâu thuẫn.
- Thêm helper `state.competing_open()` → danh sách giả thuyết cạnh tranh còn `open` (dùng cho cổng dừng D27).
- `summarize_for_llm()` — render trạng thái hypothesis (✅/❌/🔍) + confidence để LLM thấy đã loại trừ gì.

### B. E5 — Structured verdict *(must-land)*
- Verdict không còn parse prefix tiếng Việt mong manh. Hai hướng (chọn 1 khi code):
  - **Tool-call verdict:** thêm tool ảo `submit_verdict(root_cause, confidence, evidence_ids, propagation, competing)` → LLM gọi tool này để kết luận → engine nhận args structured.
  - **JSON block:** prompt yêu cầu khối JSON cuối; parse JSON, fallback về parser cũ nếu lỗi.
- Bỏ default `medium` âm thầm: parse fail → `insufficient` + flag `parse_degraded=True` (không giả vờ tự tin).
- Giữ `raw_text` để backward-compat dashboard.

### C. E2 — Evidence-grounding guard *(must-land)*
- Trước khi finalize verdict: kiểm `root_cause` + `evidence_summary` có **trỏ tới evidence đã thu** không (qua `evidence_ids` structured từ E5, hoặc keyword-overlap fallback).
- Nếu **không neo được** → hạ confidence xuống `low`/`insufficient` + gắn cờ `speculative=True` (đúng tinh thần "tool im lặng về chỗ đứt = agent bịa").
- Đây là **chặn trong loop**, không phải đo hậu kỳ như eval hiện tại.

**Cổng Ngày 26 (bắt buộc):**
- Hypothesis có ≥1 lần chuyển `confirmed`/`ruled_out` thật trong 1 investigation (không còn toàn `open`) ✅
- Verdict đi qua structured path (tool-call/JSON), parse fail → `insufficient` không phải `medium` ✅
- Verdict không neo được bằng chứng → confidence bị hạ + cờ speculative ✅
- **Regression: eval 4/4 mock + 2 KB end-to-end + Telegram không vỡ** ✅

**KHÔNG làm ở Day 26:** đổi kiến trúc multi-agent merge (để Future/spill); thêm tool mới.

---

## Ngày 27 — Engine Intelligence

**Mục tiêu:** dừng đúng lúc + tự tin đúng mức. Dùng dữ liệu eval/feedback đã có (D21/D23) để calibrate thật.

### A. E4 — Stop/loop thông minh + cổng giả thuyết cạnh tranh
- `is_looping()` nâng cấp: phát hiện **dao động** (cửa sổ N call, không chỉ 2 liên tiếp) + params lệch nhẹ (normalize trước khi so).
- **Cổng dừng:** trước khi nhận verdict `high`/`medium`, kiểm `state.competing_open()` — nếu còn giả thuyết cạnh tranh mạnh chưa loại trừ VÀ còn budget → nudge LLM "loại trừ X trước khi kết luận" (1 lần, tránh vòng lặp).
- **Adaptive step budget:** budget gợi ý theo độ phức tạp (số service trong scope / scenario), trần cứng vẫn giữ an toàn cho LangGraph (`step_budget*3+6`).

### B. E3 / D1 — Confidence calibration
- **Grounding:** confidence được suy ra từ LOẠI bằng chứng (E1) thay vì chỉ LLM tự khai — engine có quyền hạ cấp nếu evidence không đủ.
- **Auto-recalibrate:** đọc `eval_results` + `investigation_feedback` (👍/👎 từ D23) → đo accuracy thực tế theo từng mức confidence → đề xuất ngưỡng low/medium/high. Render trên `/dashboard/eval` (mở rộng card calibration D21).
- Negative-set: dùng kịch bản "chưa đủ bằng chứng" (nếu có từ D21) để đo chống over-confidence.

### C. D2 — Baseline auto-update *(if-time)*
- `get_metrics` (+ tool fintech tương ứng): baseline rolling 7 ngày từ dữ liệu thay vì hardcode → giảm false-positive khi pattern traffic đổi.
- Giữ deterministic: tính trong tool bằng SQL, không để LLM thấy raw.

**Cổng Ngày 27:**
- Loop detection bắt được dao động A→B→A→B (test giả lập) ✅
- Cổng cạnh tranh chặn verdict sớm khi còn giả thuyết mạnh chưa loại trừ ✅
- Calibration thật render trên dashboard (accuracy theo mức confidence từ eval+feedback) ✅
- Regression eval không vỡ ✅

---

## Ngày 28 — Security Hardening + Per-project Custom LLM

**Mục tiêu:** đóng lỗ anonymous trigger + không lưu credential plaintext + chống DB phình + **mỗi project tự cấu hình LLM endpoint riêng (model/url/header key), fallback default nếu không cấu hình**.

### A. A4 — API token auth cho webhook *(P0, rẻ — phần lớn đã có)*
- Bảng `api_tokens` + verify code **đã có sẵn trong `rbac.py` từ D22** → chỉ cần wire.
- `/trigger` + `/projects/*/trigger`: validate header `X-API-Token` qua `api_tokens` (token hash). Không token / sai → 401.
- Backward-compat: env cờ `ALLOW_ANON_TRIGGER` (mặc định off ở prod) để dev cũ không gãy.
- UI `/dashboard/admin/tokens`: tạo/list/revoke token (route + UI còn thiếu từ spill D22).

### B. A2 — Secret management at-rest *(P0)*
- Mã hóa `projects.llm_config` + `mcp_servers.auth_config` (chứa bearer/api_key) trong SQLite.
- Key từ env `SECRET_KEY`; dùng `cryptography.Fernet` (nếu cho thêm dep) hoặc AES stdlib-based.
- Migration idempotent: detect plaintext cũ → mã hóa tại chỗ; đọc → giải mã trong suốt ở seam.
- Không log plaintext credential ở bất kỳ đâu.

### C. A3 — Trace retention / purge *(rẻ)*
- Startup purge + (tùy chọn) background task: xóa `trace_events` cũ hơn `TRACE_RETENTION_DAYS` (mặc định config được).
- Idempotent, an toàn: chỉ xóa trace_events, không đụng investigations/verdict.

### D. Per-project Custom LLM endpoint — *(last mile của D12; pair chặt với A2)*

> **Đã có từ D12 (KHÔNG làm lại):** cột `llm_provider/llm_model/llm_config` (JSON) · `get/set_project_llm()` · **fallback project chưa cấu hình → default agent LLM (anthropic sonnet 4.6) đã chạy** ở `runner.py` (project config → global env). Day 28 hoàn thiện "last mile" còn thiếu.

- **Mở rộng `llm_config` schema** chứa endpoint đầy đủ: `base_url` (URL endpoint), `api_key` (credential riêng project), `headers` (custom header dict, vd `{"X-Api-Key": "..."}` — vài gateway dùng header khác `Authorization: Bearer`), `max_tokens` (optional).
- **Wire factory (bug hiện tại):** `create_llm_client` đang **bỏ rơi `extra_config`** cho anthropic + openai-compat (chỉ gemini nhận). Sửa: truyền `extra_config` xuống CẢ `AnthropicClient` và `OpenAICompatibleClient`.
- **`AnthropicClient`:** nhận `base_url` + `default_headers` từ `extra_config` (anthropic SDK hỗ trợ `base_url=`/`default_headers=`); hiện chỉ có `api_key`+`model`.
- **`OpenAICompatibleClient`:** thêm `default_headers` từ `extra_config` (đã có `base_url`+`api_key`, thiếu custom headers).
- **Fallback giữ nguyên:** `get_project_llm()` trả `None` → `create_llm_client()` mặc định → default agent LLM. (Logic đã có ở `runner.py`, chỉ verify không vỡ.)
- **UI `/dashboard/projects/{pid}`:** form LLM config thêm field `base_url` + `api_key` + `headers` (JSON textarea). Guard bằng `require_perm("llm.manage")` (quyền nhạy cảm có sẵn từ D22).
- **Bảo mật (pair A2):** `api_key`/`headers` trong `llm_config` **được A2 cùng ngày mã hóa at-rest** — không lưu plaintext credential project. *(if-time)* nút "Test LLM" gọi 1 lượt thử validate config trước khi lưu.

**Cổng Ngày 28:**
- `/trigger` không token → 401, có token hợp lệ → 202 ✅
- `llm_config`/`auth_config` trong DB ở dạng mã hóa, đọc qua seam giải mã đúng ✅
- Purge trace_events cũ chạy, DB không phình ✅
- **Project A cấu hình LLM riêng (model + base_url + header key) → investigation dùng đúng endpoint đó; Project B không cấu hình → fallback default sonnet 4.6** ✅

---

## Ngày 29 — Reliability Infra + UI Polish *(in-process, KHÔNG Kafka)*

**Mục tiêu:** không mất investigation khi restart + chịu được alert storm + cải thiện UX dashboard.

### A. B3 — Investigation queue *(thay fire-and-forget)*
- `runner.py`: thay `asyncio.Task` fire-and-forget → **internal priority queue** (asyncio.Queue / heap) + worker pool (dùng lại `ConcurrencyLimiter` max=3 từ D16).
- Visibility timeout + **retry on crash** (dùng lại `with_retry` từ D16).
- Persist hàng đợi pending vào SQLite (bảng `investigation_queue`) → sống sót qua restart.

### B. A1 — Graceful shutdown
- SIGTERM handler trong lifespan: ngừng nhận trigger mới → **finish phiên đang chạy** → push **partial verdict** cho phiên dở (không chết im lặng) → **drain queue** (persist pending) → exit.
- Pair với B3: drain = flush queue ra SQLite, restart sau đọc lại.

### C. B4 — Rate limiting
- Per-project throttle `/trigger`: max N investigations/giờ (config qua project hoặc env).
- Vượt ngưỡng → 429 + thông báo, không tạo investigation → chống tự-DDoS khi alert storm.

### D. UI — Gom nhóm sidebar navigation theo chức năng
- Sidebar hiện có 11 link phẳng → chia thành nhóm ngữ nghĩa (ví dụ: **Điều tra** · **Cấu hình** · **Quan sát** · **Admin**).
- Mỗi nhóm có label section nhỏ; collapsible tùy chọn (JS toggle, lưu state `localStorage`).
- Không thay đổi routes hay logic — chỉ thay đổi `base.html` nav template + CSS.

### E. UI — Đổi default theme sang Light mode
- `base.html`: bỏ `body.theme-dark` là mặc định; default không có class → Light mode.
- JS `_applyTheme()`: đọc `localStorage` key `ia-theme`; nếu chưa set → mặc định `light`.
- Toggle button label và logic cập nhật tương ứng.

**Cổng Ngày 29:**
- Kill -TERM giữa lúc điều tra → partial verdict được push, pending persist, restart đọc lại không mất ✅
- Burst 20 trigger → queue xử lý tuần tự (limiter max=3), không sập ✅
- Vượt rate limit → 429 ✅
- Sidebar có nhóm chức năng rõ ràng ✅
- Default theme Light mode khi vào lần đầu (chưa set localStorage) ✅

---

## Ngày 30 — Ecosystem + Đóng Phase 6

**Mục tiêu:** mở rộng biên nhận/đẩy (giữ READ-ONLY) + recurring-incident view + đóng pha.

- **C1 — PagerDuty/OpsGenie intake adapter:** thêm adapter (route qua `X-Alert-Source`) → normalize → investigation. READ-ONLY: chỉ nhận alert, KHÔNG ack/resolve. Pattern giống 3 adapter có sẵn.
- **C3 — GitHub/GitLab deploy hook (proactive):** webhook khi có release → auto-trigger "deploy mới có gây lỗi không?". Khớp kịch bản deploy-bug sẵn có. Đây là proactive mode (pull-style).
- **C4 — Webhook callback outbound:** sau verdict, POST kết quả structured ra `callback_url` của caller → integrate CI/CD. Thực chất là 1 output adapter (HTTP POST), giữ READ-ONLY với hệ thống ngoài.
- **D3 — Root cause clustering:** group investigations có verdict tương tự (trên `investigation_patterns`) → view "top recurring incidents" + cảnh báo nếu cùng root cause lặp > N lần/ngày.
- Cập nhật `BUILD_STATE.md` + bảng Phase trong `CLAUDE.md`.

**Cổng Phase 6 (bắt buộc):**
- **Engine giỏi hơn, đo được:** hypothesis lifecycle thật + verdict neo bằng chứng + calibration hiện trên dashboard ✅
- Webhook auth bật (anonymous → 401) + secret at-rest ✅
- Graceful shutdown + queue (kill giữa chừng không mất investigation) ✅
- ≥1 intake mới hoạt động (PagerDuty/OpsGenie hoặc deploy hook) ✅
- **Regression: eval 4/4 + 2 KB end-to-end + Telegram không vỡ** ✅
- Demo 7 phút chạy lại smooth.

---

## Thứ tự cắt nếu hụt giờ (từ dưới lên)

1. D3 root cause clustering (D30)
2. C4 webhook callback (D30)
3. D2 baseline auto-update (D27, đã đánh dấu if-time)
4. B4 rate limiting (D29)
5. A3 trace retention (D28) — rẻ nên ưu tiên giữ
6. C1 hoặc C3 (giữ ít nhất 1 intake mới cho Cổng)

> **KHÔNG cắt:** E1/E2/E5 (D26), E3/E4 (D27), A4/A2 (D28), A1/B3 (D29). Đây là xương sống engine + P0 production.

---

## Future / sau Phase 6 (chưa lên lịch)

- **B1 — Tier-2 DB migration thật:** `PostgresBackend` chạy thật (port ~12 `datetime()` + 8 UPSERT dialect-aware, DDL `schema.sql`) + integration test. **Cần Postgres env + lệnh rõ.**
- **C2 — Bidirectional integrations:** agent comment/ack incident (Jira/Linear/PagerDuty). ⚠️ **Phá READ-ONLY — cần người dùng duyệt rõ** + guard write-capable riêng.
- **B2 — Horizontal scale seam:** dedup set + SSE broker in-memory → external store (Redis) khi lên multi-instance. Trần cứng của kiến trúc hiện tại.
- **D4 — Real MCP pack mở rộng:** tool query Prometheus/Loki/Elasticsearch thật qua MCP (mở rộng pack infra D24). Spill-OK nếu D30 hụt.
- **Multi-agent merge nâng cao:** conflict resolution khi 2 specialist bất đồng (hiện merge naive — dedup theo content string).

---

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` + file này.
2. Bám ngày hiện tại, kết thúc bằng verify Cổng kiểm.
3. Cuối session: cập nhật `BUILD_STATE.md`.
4. **Lõi không được vỡ:** engine chạy 2 KB end-to-end + push Telegram — ưu tiên trên mọi thứ. Ngày engine (26–27) chạy regression gate trước khi đóng.
5. Lệch 4 nguyên tắc / stack → hỏi người dùng trước. (Đặc biệt: Tier-2 DB migration + bidirectional output cần lệnh rõ.)
