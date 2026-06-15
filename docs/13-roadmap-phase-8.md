# 13 — Roadmap Phase 8 (Ngày 36–45): Engine domain-agnostic + Tự động hóa chất lượng + Cost/DX

> Tiếp nối sau **35/35 ngày (Phase 1–7 ✅ hoàn tất, 63/63 tests)**. File này là kế hoạch Phase 8.
> Mục tiêu: từ **"điều tra giỏi (microservice) + deploy được"** → **"engine domain-agnostic THẬT + chất lượng được gác tự động + rẻ hơn + dễ onboard"**.
> Plan trước: `docs/10` (Phase 1–4) · `docs/11` (Phase 5) · `docs/12` (Phase 6). Phase 7 (31–35) lên kế hoạch inline trong `BUILD_STATE.md`. File này tiếp nối.

---

## Ràng buộc cố định (không đổi)

- ❌ KHÔNG Kafka / message broker → queue vẫn **in-process asyncio** (Phase 6 D29).
- ❌ KHÔNG Postgres/MySQL ở runtime → **giữ SQLite WAL**. Tier-2 vẫn ở Future.
- ❌ KHÔNG infra nặng → `pip install` + env vars là đủ. CI (D41) là GitHub Actions chạy pytest + mock eval, không phải hạ tầng ngoài.
- ✅ **READ-ONLY giữ nguyên** — output chỉ push, không ghi ngược.
- ✅ **Horizontal scale seam → Future** (chốt session lập kế hoạch): chưa có nhu cầu multi-instance thật; Redis SSE giữ **stub** (Phase 7 D35), không hoàn thiện ở Phase 8.
- ⚠️ **Lõi không được vỡ:** mọi ngày engine (36–38, 43) phải qua **regression gate** = eval 4/4 mock + 2 KB end-to-end + push Telegram.

---

## Bối cảnh & quyết định chốt (session lập kế hoạch)

Session này **không code** — đọc toàn bộ trạng thái + **đọc kỹ code engine** (`loop.py`, `state.py`, `graph.py`, `multi_agent.py`) để đánh giá khách quan sau 7 phase → chốt Phase 8.

**Quyết định chốt qua trao đổi với người dùng:**
- **Day 38 real-LLM eval = SMOKE MỞ RỘNG (~$2)** — không chạy full N=10 (~$10). Đủ tín hiệu calibration thật theo mức confidence, khớp pattern tiết kiệm đã chọn ở Day 21.
- **Horizontal scale seam → Future** — giữ in-memory single-process; không kéo vào Phase 8 (tránh over-engineer khi chưa có nhu cầu multi-instance thật).
- **Tier-2 Postgres · bidirectional output → vẫn Future** (như Phase 6).

### Điểm yếu đã xác nhận trong code (cơ sở Nhóm E round 2 + production-readiness)

| # | Điểm yếu | Vị trí | Hệ quả |
|---|----------|--------|--------|
| **E6** | Vòng đời giả thuyết **hardcode theo miền microservice + keyword tiếng Việt** | `loop.py:_HYPOTHESIS_RELEVANCE` (5 tag) · `_update_hypotheses` (match chuỗi "tìm thấy"/"lệch"/"sập" + tool name microservice) | **Fintech investigation có 0 hypothesis** (tool `get_revenue_breakdown`… không khớp) → cổng cạnh tranh E4 không kích hoạt → E1/E4 chỉ chạy cho 4 KB microservice. **Engine nuốt domain knowledge — vi phạm ngầm nguyên tắc #2.** |
| **E7** | Hai đường engine (while-loop + LangGraph) **trùng logic**; multi-agent **không ngang hàng** single-agent | `loop.py:_run_loop` ↔ `graph.py:decide_node` (stop/gate viết 2 lần) · `multi_agent.py:_synthesize_verdict` thiếu competing gate + conflict resolution; merge dedup-content-string | Drift giữa 2 path; multi-agent bỏ qua liên kết evidence_id và 2 cơ chế engine mới |
| **E8** | Real-LLM eval chỉ **smoke 6/6 một lần**; calibration (E3) **chỉ hiển thị dashboard**, chưa feed ngược vào engine | `queries.py:get_calibration_*` (display-only) · insight "under-confident fintech" chưa đóng vòng | Engine không tự sửa over/under-confidence; calibration là báo cáo, không phải cơ chế |
| **E9** | Structured verdict đi **đường vòng** args→text→parse | `loop.py:_structured_args_to_verdict_text` → `_parse_verdict` | Vẫn phụ thuộc prefix tiếng Việt; parse hỏng âm thầm thành "insufficient" |
| **T1** | Test **mỏng & lệch**: 63 test chỉ phủ engine_core/auth/tools | `tests/` (3 file) | Không test: 8 intake adapter, 5 output renderer, queue, scheduler, multi-agent, graph, registry, crypto |
| **T2** | **Không có CI**; regression gate chạy tay mỗi ngày | — | Không gate tự động chặn commit làm vỡ lõi |
| **P1** | Không dùng **prompt caching** dù system prompt + tool specs là prefix ổn định | `loop.py:decide_next_action` | ~$0.17/run real-LLM, cao hơn cần thiết |
| **P2** | Nguyên tắc #1 (chống raw rows) **không enforce bằng máy** | — | Chỉ là quy ước; dễ rò raw data về sau mà không ai bắt |

---

## Tổng quan Phase 8

```
Day 36  E6  Engine domain-agnostic   — hypothesis catalog theo miền (rút khỏi engine) + catalog fintech
Day 37  E7  Hợp nhất path + parity   — 1 nguồn stop/gate cho loop+graph; multi-agent ngang hàng
Day 38  E8  Real-LLM eval + vòng calib— smoke mở rộng ($2) + feed ngưỡng ngược vào engine
Day 39  T1  Test: adapters + output  — 8 intake adapter + 5 output renderer
Day 40  T1  Test: infra + contract   — queue/scheduler/registry/crypto + guard nguyên tắc #1
Day 41  T2  CI gate tự động          — GitHub Actions: pytest + mock eval + syntax/import + coverage
Day 42  P1  Cost + perf              — prompt caching + gọn context
Day 43  E9  Structured verdict thẳng — args→Verdict trực tiếp + cờ parse_degraded
Day 44      DX + docs               — README + Makefile + gộp API docs + polish demo
Day 45      Hardening + Cổng Phase 8 — audit config/security + đóng pha
```

| Ngày | Theme | Trọng | Trạng thái |
|------|-------|:----:|-----------|
| 36 | E6 — Engine domain-agnostic | **L** | ☐ |
| 37 | E7 — Hợp nhất path + multi-agent parity | M+ | ☐ |
| 38 | E8 — Real-LLM eval + đóng vòng calibration | M+ | ☐ |
| 39 | T1 — Test adapters + output | M | ☐ |
| 40 | T1 — Test infra + contract guard | M | ☐ |
| 41 | T2 — CI gate hồi quy tự động | M | ☐ |
| 42 | P1 — Cost + perf (prompt caching) | M | ☐ |
| 43 | E9 — Structured verdict đường thẳng | M | ☐ |
| 44 | DX + docs | M | ☐ |
| 45 | Hardening + Cổng Phase 8 | M | ☐ |

**Phụ thuộc cứng:** D36 → D37 (parity xây trên hypothesis catalog). D37 → D38 (calibration đo trên engine đã hợp nhất). D39+D40 → D41 (CI chạy chính các test mới). D43 độc lập, có thể đổi chỗ nếu cần.

**Xương sống (KHÔNG cắt):** D36 · D37 · D39 · D41.

---

## Ngày 36 — E6: Engine domain-agnostic *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** rút domain knowledge ra khỏi engine. Vòng đời giả thuyết phải chạy cho MỌI miền (microservice + fintech) qua catalog cắm vào, không phải keyword hardcode.

### A. Rút `_HYPOTHESIS_RELEVANCE` ra khỏi engine *(must-land)*
- Tạo khái niệm **hypothesis catalog theo miền** đặt CẠNH tool registry (vd `registry.py` cho microservice, `registry_fintech.py` cho fintech) — không nằm trong `loop.py`.
- Mỗi entry catalog: `tag`, `content`, `keywords`, `relevant_tools`, `confirm_kws`, `rule_out_kws`, `confirm_conf`. Đây chính là cấu trúc `_HYPOTHESIS_RELEVANCE` hiện có — chỉ **di chuyển vị trí** + đa miền hóa.
- Engine nhận catalog qua tham số (như nhận `list[Tool]`) — `loop.py` đọc catalog, KHÔNG hardcode tag/keyword. Giữ nguyên cơ chế lifecycle `open→confirmed/ruled_out` đã có.

### B. Catalog fintech *(must-land)*
- Thêm hypothesis catalog cho fintech: provider timeout (`get_settlement_lag`/`get_transaction_anomaly`) · price bug (`get_merchant_status`/`get_revenue_breakdown`) · fraud · settlement lag.
- Verify: investigation fintech (KB-F1/F2) có hypothesis chuyển trạng thái thật.

### C. Giữ seam sạch
- `summarize_for_llm()` render hypothesis không đổi (đã có ✅/❌/🔍).
- Nếu project không cung cấp catalog → engine chạy không hypothesis-tracking (degrade an toàn, không crash).

**Cổng Ngày 36 (bắt buộc):**
- Fintech investigation có ≥1 hypothesis `confirmed`/`ruled_out` thật ✅
- Microservice 4 KB không đổi hành vi (regression eval 4/4 mock) ✅
- `grep` trong `src/agent/engine/` không còn keyword miền nào (deploy/timeout/fintech…) hardcode ✅
- 2 KB end-to-end + Telegram không vỡ ✅

**KHÔNG làm ở Day 36:** đổi schema Hypothesis; thêm tool mới; sửa multi-agent (để D37).

---

## Ngày 37 — E7: Hợp nhất path + multi-agent parity

**Mục tiêu:** một nguồn sự thật cho stop/gate; multi-agent chạy đủ cơ chế engine như single-agent.

### A. Hợp nhất stop/gate *(must-land)*
- Tách điều kiện dừng (budget/loop/no-action) + competing gate thành helper dùng chung → `loop.py:_run_loop` và `graph.py:decide_node` GỌI CHUNG, không viết 2 lần.
- Verify parity: cùng mock scenario → loop path và graph path ra verdict **giống hệt**.

### B. Multi-agent ngang hàng *(must-land)*
- `multi_agent.py:_synthesize_verdict` chạy: evidence-grounding guard (đã import) + `resolve_conflicting_hypotheses` + competing-awareness.
- `_merge_states`: merge theo **evidence_id** thay vì dedup content-string; hypothesis từ specialist được gộp đúng (không mất liên kết).

**Cổng Ngày 37:**
- Parity test: loop ↔ graph cùng verdict trên mock ✅
- Multi-agent verdict chạy grounding + conflict resolution (có annotate winner khi >1 confirmed) ✅
- Regression eval 4/4 ✅

---

## Ngày 38 — E8: Real-LLM eval + đóng vòng calibration

**Mục tiêu:** calibration không còn là báo cáo — trở thành cơ chế engine tự hạ verdict over-confident.

### A. Smoke real-LLM mở rộng *(~$2 — chốt)*
- Chạy ~2–3 lần × 6 KB (microservice + fintech) real-LLM → lưu accuracy theo mức confidence vào `eval_results`.
- Negative-set: dùng/ thêm kịch bản "chưa đủ bằng chứng" để đo over-confidence.

### B. Đóng vòng calibration *(must-land)*
- Engine đọc ngưỡng calibration đo được (eval + feedback 👍/👎 D23) → **tự hạ confidence** khi mức đó có accuracy dưới ngưỡng (mở rộng E2 grounding guard).
- Dashboard `/dashboard/eval` hiện **before/after** (confidence LLM khai vs. confidence sau calibrate).

**Cổng Ngày 38:**
- Calibration đo trên real-LLM (≥2 run/KB) lưu DB ✅
- Engine hạ cấp verdict khi accuracy-cho-mức-confidence < ngưỡng (test giả lập) ✅
- Dashboard hiện before/after ✅
- Regression 4/4 ✅

---

## Ngày 39 — T1: Test adapters + output

**Mục tiêu:** phủ test code parsing dễ vỡ nhất (đã thêm mà chưa có test).

- pytest cho **8 intake adapter** (github/gitlab/pagerduty/opsgenie/prometheus/grafana/sentry): mỗi adapter ≥3 ca — happy · non-trigger → None · payload méo (không crash).
- pytest cho **5 output renderer** (slack/teams/email/telegram/callback): shape payload đúng (Block Kit color theo severity, callback dict structured), graceful khi thiếu URL.

**Cổng Ngày 39:** mỗi adapter/output có ≥3 ca; tất cả PASS; test count tăng đáng kể.

---

## Ngày 40 — T1: Test infra + contract guard

**Mục tiêu:** phủ subsystem chưa test + enforce nguyên tắc #1 bằng máy.

- Test `investigation_queue` (enqueue/drain/crash-recovery reset running→pending), `scheduler` tick (fire due trigger, recurring alert threshold), `project_registry`/`mcp_registry` CRUD, `crypto` round-trip + backward-compat plaintext.
- **Contract guard (P2):** test assert mọi tool trả `Observation` hợp lệ — có `summary`, `total_count`, `len(samples) ≤ 5`, không rò raw rows. Enforce nguyên tắc #1.

**Cổng Ngày 40:** subsystem được phủ; contract test bắt được 1 tool cố tình làm hỏng (≥6 samples / thiếu total_count) ✅.

---

## Ngày 41 — T2: CI gate hồi quy tự động

**Mục tiêu:** biến regression gate chạy tay thành tự động.

- GitHub Actions workflow: `pytest` + `eval_agent.py --mock` (gate 4/4) + syntax check 76 file + import check. Coverage report (không bắt buộc ngưỡng, chỉ hiển thị).
- Cache pip; chạy trên push + PR.

**Cổng Ngày 41:** CI xanh khi push sạch; commit cố tình làm vỡ lõi (mock eval < 4/4) → CI đỏ ✅.

---

## Ngày 42 — P1: Cost + perf (prompt caching)

**Mục tiêu:** giảm $/run, đo được.

- Anthropic **prompt caching** trên prefix ổn định (SYSTEM_PROMPT + tool specs) → cắt input token. (Anthropic SDK: `cache_control` trên system/tools block.)
- Gọn `summarize_for_llm`: cap số evidence trong context, bỏ phần dư.
- Đo $/run before/after trên cost dashboard (`/dashboard/cost`).

**Cổng Ngày 42:** $/run giảm đo được trên cost dashboard; eval correctness không đổi (4/4) ✅.

---

## Ngày 43 — E9: Structured verdict đường thẳng

**Mục tiêu:** bỏ vòng args→text→parse.

- `submit_verdict` args → dựng **trực tiếp** `Verdict` (bỏ `_structured_args_to_verdict_text` ở đường structured). Text chỉ còn fallback cho MockLLM / khi LLM không gọi tool.
- Thêm cờ `parse_degraded=True` khi phải fallback text-parse → không âm thầm "insufficient", hiện cờ trên verdict/trace.

**Cổng Ngày 43:** structured path không qua `_parse_verdict`; parse hỏng được gắn cờ `parse_degraded`; regression 4/4 ✅.

---

## Ngày 44 — DX + docs

**Mục tiêu:** người mới clone chạy được trong vài phút.

- **README.md gốc** (chưa có ở root): what/why · quickstart (link CLAUDE.md mục Khởi động nhanh) · sơ đồ kiến trúc 4 cạnh · trỏ docs/.
- **Makefile**: `init` (init_db + migrate), `seed`, `run`, `mcp`, `test` (pytest), `eval` (mock gate) — mỗi target một dòng.
- Gộp/đối chiếu API docs (route hiện có) cho khớp thực tế.
- Polish kịch bản demo 7 phút (trigger → điều tra → Telegram → dashboard).

**Cổng Ngày 44:** clone mới bootstrap được từ README + `make`; `make test` + `make eval` xanh; demo chạy end-to-end ✅.

---

## Ngày 45 — Hardening + Đóng Phase 8

**Mục tiêu:** audit cuối + đóng pha.

- **Security/config audit:** không plaintext secret trong repo/log; `SECRET_KEY` + session secret BẮT BUỘC từ env ở prod (cảnh báo nếu dùng dev fallback); rà dependency.
- Cập nhật `BUILD_STATE.md` + bảng Phase trong `CLAUDE.md`.

**Cổng Phase 8 (bắt buộc):**
- **Engine domain-agnostic:** fintech có hypothesis lifecycle thật; engine không hardcode keyword miền ✅
- **Parity:** loop ↔ graph cùng verdict; multi-agent ngang hàng ✅
- **Calibration đóng vòng:** engine tự hạ over-confidence; before/after trên dashboard ✅
- **CI xanh** + test phủ adapters/output/infra + contract guard ✅
- **Cost giảm** đo được (prompt caching) ✅
- **DX:** README + Makefile, clone mới chạy được ✅
- **Regression: eval 4/4 + 2 KB end-to-end + Telegram không vỡ** ✅

---

## Thứ tự cắt nếu hụt giờ (từ dưới lên)

1. D44 docs polish (giữ README tối thiểu)
2. D42 prompt caching
3. D38 → giữ smoke tối thiểu (1 run/KB), hoãn đóng-vòng-calibration nếu kẹt
4. D43 structured verdict thẳng
5. D40 contract guard (giữ test infra cơ bản)

> **KHÔNG cắt:** D36 (engine domain-agnostic) · D37 (parity) · D39 (test adapters/output) · D41 (CI gate). Đây là xương sống engine-quality + production-readiness của Phase 8.

---

## Future / sau Phase 8 (chưa lên lịch)

- **B1 — Tier-2 DB migration thật** (Postgres chạy thật) — cần env + lệnh rõ.
- **C2 — Bidirectional integrations** — phá READ-ONLY, cần duyệt rõ.
- **B2 — Horizontal scale seam** — hoàn thiện Redis SSE stub + dedup/rate-limit ra external store khi lên multi-instance. **Chốt: vẫn Future ở Phase 8.**
- **D4 — Real MCP pack mở rộng** (Prometheus/Loki/Elasticsearch thật qua MCP).

---

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` + file này.
2. Bám ngày hiện tại, kết thúc bằng verify Cổng kiểm.
3. Cuối session: cập nhật `BUILD_STATE.md`.
4. **Lõi không được vỡ:** engine chạy 2 KB end-to-end + push Telegram — ưu tiên trên mọi thứ. Ngày engine (36–38, 43) chạy regression gate trước khi đóng.
5. Lệch 4 nguyên tắc / stack → hỏi người dùng trước.
