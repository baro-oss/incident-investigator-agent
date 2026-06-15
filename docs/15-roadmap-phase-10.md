# 15 — Roadmap Phase 10 (Ngày 51–55): Agent đọc được mã nguồn (qua MCP) + đóng vòng đo

> Tiếp nối sau **Phase 9 ✅ (50/50 ngày, 262/262 tests, CI xanh, Python 3.14)**. File này là kế hoạch Phase 10.
> Mục tiêu: ngoài logs/metrics/deploys, agent **đọc được mã nguồn** (diff/file của deploy nghi vấn) **qua external MCP (GitHub/GitLab)** — biến root cause từ *"deploy trùng thời điểm"* (mờ) → *"deploy vX hạ pool 100→20"* (cụ thể, actionable). 100% qua seam MCP + distill, **không quản lý source trong hệ thống**.
> Plan trước: `docs/10` (P1–4) · `docs/11` (P5) · `docs/12` (P6) · Phase 7 inline `BUILD_STATE.md` · `docs/13` (P8) · `docs/14` (P9). File này tiếp nối.

---

## Định hướng phase này

**Một tính năng lõi mới + đóng các vòng còn hở.** Tính năng anchor: **agent đọc mã nguồn qua external MCP**. Đây KHÔNG phải "thêm 1 tool" — nó **hoàn thiện cung engine-intelligence của Phase 9**:

- `get_recent_deploys` tìm ra deploy nghi vấn → agent đọc **deploy đó đổi gì** trong code → bơm thẳng vào **E12 specificity** (verdict trích file+dòng+version).
- Gắn code tool vào `relevant_tools` của hypothesis `deploy_bug`/`dependency` → **E10** tự hint "đọc diff tiếp", **E11** prior deploy_bug → đọc diff sớm.

**Ràng buộc kiến trúc quyết định (chốt với người dùng):** *hệ thống này quản lý observability (logs/metrics/deploys), **KHÔNG** quản lý source code.* Vì vậy:

- ❌ KHÔNG local diff / không seed source vào SQLite. `service_repos` chỉ lưu **mapping metadata** (service→repo), không lưu source.
- ✅ Agent đọc code **chỉ qua seam MCP external** (GitHub/GitLab MCP) — như một **extension**, không phải main flow.
- ✅ `get_recent_deploys` **giữ nguyên** (đọc bảng `deploys` — metadata vận hành, hợp lệ).
- ✅ Trọng tâm kỹ thuật = **distillation wrapper**: raw diff/file mà MCP trả → code Observation đã chưng cất (Nguyên tắc #1).
- ✅ **READ-ONLY guard** ở seam: chỉ tool đọc (list/get/diff/blame/search), chặn write/PR/merge/push.

---

## Ràng buộc cố định (không đổi)

- ❌ KHÔNG Kafka / message broker → queue vẫn **in-process asyncio**.
- ❌ KHÔNG Postgres/MySQL ở runtime → **giữ SQLite WAL**. Tier-2 vẫn Future.
- ❌ KHÔNG local diff / không quản lý source — code chỉ đọc qua **external MCP**.
- ✅ **READ-ONLY giữ nguyên** — code tool chỉ đọc; output chỉ push.
- ✅ **Horizontal scale · Tier-2 Postgres · bidirectional → vẫn Future** (không kéo vào Phase 10).
- ⚠️ **Lõi không được vỡ:** mọi ngày engine/tool (51–54) phải qua **regression gate** = eval 4/4 mock + 2 KB end-to-end + push Telegram.

### Tuân thủ 4 nguyên tắc + READ-ONLY (kiểm trước — lớp code)

| Nguyên tắc | Lớp code (F1/F2) |
|-----------|------------------|
| #1 LLM không thấy raw data | ✅ distill wrapper: diff/file → summary tự diễn giải + ≤5 hunk đại diện + aggregates; **không raw dump** |
| #2 Một seam, engine domain-agnostic | ✅ code = thêm `Tool` qua seam MCP; risk heuristic **generic** (pool/timeout/config/dep-bump), không keyword miền; mapping tool↔hypothesis sống **trong catalog** |
| #3 Lõi deterministic, agent chỉ điều phối | ✅ distill + risk-detect deterministic; LLM chỉ chọn gọi tool; **confirm vẫn cần bằng chứng thật** |
| #4 Async từ biên, một nguồn structured | ✅ code Observation là structured; render ở biên |
| **READ-ONLY (fintech)** | ✅ whitelist tool đọc; **chặn write/create/update/delete/merge/push/PR** ở seam, tool vi phạm bị loại khỏi registry |

> **Điểm canh gác #2 + READ-ONLY (quan trọng nhất):** Phase 8 đã gỡ keyword miền khỏi engine — Phase 10 KHÔNG tái phạm (risk heuristic phải generic, mapping ở catalog). Và lớp code **tuyệt đối không có thao tác ghi** lên repo.

---

## Điểm yếu / cơ hội đã xác nhận trong code (cơ sở Phase 10)

| # | Quan sát | Vị trí (đã đọc code) | Hệ quả |
|---|----------|----------------------|--------|
| **F (mới)** | Agent **không đọc được mã nguồn**. `get_recent_deploys` biết "deploy vX lúc 14:03" nhưng không biết **vX đổi gì** → root cause dừng ở tương quan thời gian, không chỉ ra thay đổi cụ thể. GitHub/GitLab hiện chỉ là *intake adapter* (webhook→trigger), không phải đọc-code. | `tools/get_recent_deploys.py` · `intake/adapters/github.py`,`gitlab.py` (chỉ intake) | Verdict deploy_bug mờ; on-call vẫn phải tự mở repo. Bỏ lỡ đòn bẩy lớn nhất để nâng specificity (E12). |
| **P2** | Distill external MCP **yếu**: text external bị **cắt cứng 500 ký tự** rồi nhét `summary` → vi phạm ngầm Nguyên tắc #1 với mọi MCP trả dữ liệu giàu (diff, trace dài). | `tools/mcp_client.py:185` `_parse_observation` | Rào chắn của lớp code; và nợ kỹ thuật chung cho mọi external MCP. |
| **V1** | Real-LLM eval **chưa từng chạy** (D38 + D49 đều SKIP vì hết credit) → E10/E11/E12 **chưa kiểm chứng trên LLM thật**. | `scripts/eval_agent.py` | Tuyên bố "giảm bước / nâng specificity" còn là giả định. Cần harness đo + chạy khi có credit. |
| **E13** | Prior **không decay**: `investigation_patterns.count` tăng vô hạn, pattern cũ không giảm trọng. | `memory/patterns.py:get_service_priors` | Prior lệch về sự cố cũ; "thông minh theo thời gian" chưa phản ánh gần đây. |
| **OPS1** | Catalog **hardcode Python**: vận hành không thêm được hypothesis/keyword/tool-mapping mà không sửa code. | `engine/hypothesis_catalog.py` | Mở rộng miền/tool phải đụng code + deploy lại. |
| **T3** | Coverage **~29%**, display-only. Dashboard/server/runner/scheduler test mỏng. | `.github/workflows/ci.yml` | Regression rủi ro ở các cạnh ít test. |

**Đòn bẩy chung:** lớp code dựng trên seam MCP **đã có** (`MCPClient`, registry, `build_tool_registry`, project-scoped `mcp_servers`); chỉ thêm **distill wrapper + guard + mapping**. Synergy E10/E11/E12 **miễn phí** vì catalog + `_build_user_message` + `specificity.py` đã sẵn.

---

## Bối cảnh & quyết định chốt (session lập kế hoạch)

Session này **không code** — đọc kỹ engine + tool + MCP (`loop.py`, `state.py`, `registry.py`, `contracts.py`, `mcp_client.py`, `get_recent_deploys.py`, `hypothesis_catalog.py`, `memory/patterns.py`, `schema.sql`) → chốt Phase 10.

**Quyết định chốt (đã xác nhận với người dùng):**

1. **Code đọc CHỈ qua external MCP — không local diff.** Hệ thống không quản lý source; `service_repos` chỉ là mapping metadata. GitHub/GitLab MCP là **extension**, không phải main flow.
2. **`get_recent_deploys` giữ nguyên** — không thay/không bỏ. Code tool **bổ sung** chiều "đọc thay đổi của deploy".
3. **Real-LLM eval = mock + defer.** Chưa có credit → D53 chạy mock, dựng harness đo, real-LLM ~$2 chờ top-up (1 lệnh khi có).
4. **Defer→Future giữ nguyên Future:** Tier-2 Postgres · bidirectional · horizontal scale — không kéo vào Phase 10.
5. **5 ngày** (dồn khối lượng, không cắt scope) — gộp từ bản 10 ngày.

**Thứ tự ưu tiên (rủi ro tăng dần):** F1 code seam (nền) → F2 synergy+specificity (tác động) → V1/E13 đo+decay → P2/OPS1 hardening+editor → T3/Close.

---

## Tổng quan Phase 10

```
Day 51  F1        Code seam over MCP        — distill wrapper + service_repos + READ-ONLY guard + UI
Day 52  F2        Deploy↔code + specificity — get_recent_deploys→đọc diff version; catalog code-aware (E10/E11); code→E12
Day 53  V1+E13    Eval harness + prior decay— đo avg-steps/specificity before-after (mock; real chờ credit) + time-weight prior
Day 54  P2+OPS1   Distill tổng quát + editor— distill mọi external MCP (sửa 500-char) + budget + catalog editor UI
Day 55  T3+Close  Coverage + Cổng P10       — coverage/CI + docs/README + audit READ-ONLY/degrade + đóng pha
```

| Ngày | Theme | Trọng | Trạng thái |
|------|-------|:----:|-----------|
| 51 | F1 — Code seam over MCP (distill + repo map + guard) | **L** | ✅ |
| 52 | F2 — Deploy↔code synergy + code→specificity | **L** | ✅ |
| 53 | V1 + E13 — Eval harness (mock) + prior decay | M | ✅ |
| 54 | P2 + OPS1 — Distill tổng quát + catalog editor | M+ | ✅ |
| 55 | T3 + Close — Coverage + CI + Cổng Phase 10 | M | ✅ |

**Phụ thuộc cứng:** F1 (D51) → F2 (D52): F2 cần distill+guard+mapping của F1. F2 → D53 (đo cần code layer chạy). D51–54 → D55 (test/gate/đóng).

**Xương sống (KHÔNG cắt):** D51 (F1) · D52 (F2) · D55 (test + Cổng). D53/D54 có thể thu nhỏ (xem mục cắt giờ).

---

## Ngày 51 — F1: Code seam over MCP *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** agent đọc được mã nguồn qua external MCP, distill đúng Nguyên tắc #1, READ-ONLY, và biết repo nào cho service nào.

### A. Hợp đồng + distillation wrapper *(must-land)*
- Module mới `src/agent/tools/code_distill.py`: `distill_code_response(raw, *, tool_name, service) -> Observation`.
  - Input: raw text/JSON từ external MCP (diff / file content / blame / search result).
  - Output: Observation — `summary` tự diễn giải risk ("deploy vX đổi 3 file, +45/−12; hạ `max_pool` 100→20 trong db.yaml"); `aggregates` = {files_changed, additions, deletions, risk_signals:[...]}; `samples` ≤5 hunk/path đại diện; `total_count`. **Không raw dump.**
- `risk_signals` — heuristic **generic** (KHÔNG keyword miền): config-knob đổi (pool/timeout/retry/limit/max/min + số), dependency bump (version token đổi trong manifest), xóa lớn (deletions ≫ additions), bỏ error-handling (try/except/catch biến mất). Regex/đếm thuần.

### B. service→repo mapping + READ-ONLY guard *(must-land)*
- Migration idempotent `data/migrate_*.py`: bảng `service_repos` (project_id, service, provider, repo_url, default_branch, subpath). Chỉ **metadata**, không source.
- CRUD trong `project_registry.py` (hoặc module nhỏ mới); decrypt/encrypt nếu chứa token (tái dùng `security/crypto.py`).
- **READ-ONLY guard** ở seam: hàm `is_read_only_tool(name) -> bool` — whitelist tiền tố đọc (`get_`,`list_`,`read_`,`search_`,`diff`,`blame`,`show`,`fetch`) + blacklist cứng (`create/update/delete/write/merge/push/commit/comment/approve/...`). `build_tool_registry` (hoặc bước riêng cho code-MCP) **lọc** tool: tool ghi → loại khỏi registry + `logger.warning`.
- UI: card "Repo / Source" trong `project_detail.html` (giống card MCP/LLM) — thêm/sửa/xóa mapping.

### C. Tests (mocked MCP)
- `tests/test_code_layer.py` (mới): distill diff→Observation đúng shape + `validate_observation` pass + ≤5 samples; risk-detect đúng trên fixture (pool/dep-bump); raw file→summary; empty→degrade an toàn.
- guard: tool write bị loại, tool read giữ; service_repos CRUD round-trip.
- *(tùy chọn nhẹ)* demo-MCP stand-in trong `mcp_server/server.py`: thêm tool code trả raw payload đại diện — để demo live không cần token GitHub. **Không bắt buộc, không nằm trong cổng.**

**Cổng Ngày 51 (bắt buộc):**
- `distill_code_response` trả Observation hợp lệ từ raw diff; ≤5 samples; không raw dump; risk signal đúng trên fixture ✅
- READ-ONLY guard loại tool write, giữ tool read ✅
- `service_repos` CRUD + UI render ✅
- Regression eval 4/4 + 2 KB E2E + Telegram **không đụng** (code tool chưa vào catalog mặc định) ✅

**KHÔNG làm ở D51:** đụng catalog/synergy (D52); đụng eval/decay (D53). Chỉ seam + distill + guard + mapping.

---

## Ngày 52 — F2: Deploy↔code synergy + code→specificity *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** nối deploy nghi vấn → đọc code đúng version; catalog đẩy E10/E11; code evidence nâng E12.

### A. Deploy↔code synergy *(must-land)*
- Code tool `input_schema` nhận `service` + `version`/`ref` (+ optional `path`); map `version→repo` qua `service_repos`. Agent: `get_recent_deploys` (giữ nguyên) trả version → gọi code tool với đúng version đó.
- Wrapper code-MCP đọc `service_repos` để chọn repo theo service đang điều tra (project-scoped).

### B. Catalog code-aware → E10/E11 miễn phí *(must-land)*
- `hypothesis_catalog.py`: thêm code tool vào `relevant_tools` của entry `deploy_bug` (+ `dependency`/`dependency_failure`). Giữ `root_cause_type`.
- ⇒ **E10** `_tool_sequencing_hint`: hypothesis `deploy` open → hint "chưa gọi code tool" tự xuất hiện. **E11** prior deploy_bug pre-seed → đọc diff sớm. **Không sửa engine** — chỉ thêm data vào catalog (giữ Nguyên tắc #2).

### C. Code → E12 specificity + grounding *(must-land)*
- `engine/specificity.py`: code evidence (có file path + version + số dòng) là **tín hiệu "cụ thể" mạnh** → cộng điểm; verdict trích file+dòng+version.
- `_check_evidence_grounding`: code Observation `summary` vào pool overlap như evidence thường (đảm bảo `evidence_id` link — không phải đổi logic).
- `tests/test_code_layer.py` (+~25): synergy (deploy version→code tool, mocked) · catalog hint xuất hiện khi deploy open · code-grounded verdict điểm specificity > vague · parity loop↔graph.

**Cổng Ngày 52 (bắt buộc):**
- Deploy version → code tool đọc đúng repo/version (mocked) ✅
- Catalog: `deploy_bug.relevant_tools` chứa code tool; E10 hint xuất hiện khi deploy open; E11 prior đẩy sớm ✅
- Code-grounded verdict điểm specificity cao hơn vague (test) ✅
- Nguyên tắc #2: `grep src/agent/engine/` **không** có repo/git/keyword miền hardcode ✅
- ~25 tests pass; regression 4/4 + 2 KB E2E + Telegram ✅

---

## Ngày 53 — V1 + E13: Eval harness (mock) + prior decay

**Mục tiêu:** dựng harness đo đòn bẩy E10/E11/E12 + code layer (chạy mock, real chờ credit); cho prior decay theo thời gian.

### A. Eval harness *(must-land — mock)*
- `scripts/eval_agent.py`: đo **avg-steps** + **specificity_score**; flag A/B `--no-prior` (tắt E11) để so; lưu vào `eval_results`.
- `dashboard/eval.html`: panel before/after avg-steps + specificity (tái dùng pattern Phase 9).
- Chạy **mock** (4/4 gate giữ). Real-LLM ~$2: ghi nhận **chờ credit** — lệnh sẵn, không chặn cổng.

### B. Prior decay *(must-land)*
- `memory/patterns.py:get_service_priors`: **time-weight** count theo `updated_at` (vd half-life N ngày) → pattern cũ trọng số thấp hơn pattern mới cùng count. Confirm vẫn cần bằng chứng thật (chỉ đổi thứ tự khám phá — Nguyên tắc #3).
- Refresh calibration sau khi đổi trọng số prior.

**Cổng Ngày 53:**
- Harness ghi avg-steps + specificity vào `eval_results` + dashboard before/after ✅
- Prior decay: pattern cũ trọng số < pattern mới cùng count (test) ✅
- Mock eval 4/4; degrade an toàn (không pattern → không prior) ✅
- Real-LLM: lệnh chạy sẵn, ghi "đo sau khi top-up" ✅

---

## Ngày 54 — P2 + OPS1: Distill tổng quát + catalog editor

**Mục tiêu:** trả nợ distill external MCP (mọi loại, không chỉ code); cho vận hành sửa catalog không cần đụng Python.

### A. Distill tổng quát *(must-land)*
- `tools/mcp_client.py:_parse_observation`: external trả JSON-Observation → giữ nguyên; text dài → **distill** (summary đầu + ≤5 dòng/đoạn đại diện + `total_count`) thay vì cắt cứng 500-char. Tái dùng heuristic của `code_distill` nơi hợp lý.
- Tinh chỉnh observation budget/context (cost) — đo lại token sau distill.

### B. Catalog editor UI *(must-land)*
- Persist catalog: bảng `hypothesis_catalog` (domain/project-scoped: tag, keywords, confirm_kws, relevant_tools, root_cause_type). Load **override** lên default hardcode (default vẫn là fallback an toàn).
- `dashboard/router.py` + template: CRUD hypothesis (thêm/sửa tag·keywords·relevant_tools·root_cause_type·repo-tool mapping). Engine đọc index như cũ (`build_catalog_index`) — chỉ đổi **nguồn** (DB override + default).

**Cổng Ngày 54:**
- External MCP text dài → distill (không truncate cứng 500-char); token đo lại ✅
- Catalog editor: thêm hypothesis qua UI → xuất hiện trong investigation (load DB override) ✅
- Default catalog vẫn là fallback khi DB rỗng (degrade an toàn) ✅
- Regression 4/4 ✅

> **Cắt nếu hụt giờ:** OPS1 (catalog editor) là phần nặng nhất D54 — nếu thiếu giờ, giữ A (distill tổng quát) là must, đẩy B sang Future. Persist-catalog có thể chỉ làm read-path (load DB nếu có) trước, UI sau.

---

## Ngày 55 — T3 + Close: Coverage + CI + Cổng Phase 10

**Mục tiêu:** phủ test các cạnh mỏng + lớp code, CI xanh, audit READ-ONLY/degrade, đóng pha.

### A. Coverage + CI
- Thêm tests dashboard/server/runner (happy + 1–2 ca lỗi mỗi cái). CI `import/syntax` phủ file mới (`code_distill.py`, `service_repos`, catalog persist). Cân nhắc **ngưỡng coverage gate** nhẹ (display→enforce, vd ≥35%).
- `tests/test_code_layer.py` đầy đủ chạy trong CI.

### B. Close
- `docs/15` (file này) cập nhật trạng thái ☐→✅. `README.md` + `docs/api.md`: thêm code tools + repo config + READ-ONLY note.
- **Audit READ-ONLY:** `grep` xác nhận không có tool ghi lọt registry; guard chặn đúng.
- **Audit degrade an toàn:** không repo mapping → không code tool; external MCP lỗi → Observation lỗi (không crash); không catalog DB → default.
- Cập nhật `BUILD_STATE.md` + bảng Phase trong `CLAUDE.md` → Phase 10 ✅.

**Cổng Phase 10 (bắt buộc):**
- **F:** code reading qua MCP seam; distill đúng P#1 (không raw); **READ-ONLY guard** chặn write ✅
- **F synergy:** deploy↔code; catalog code-aware (E10/E11); code→E12 specificity đo được ✅
- **V1:** eval harness đo before/after (mock; real chờ credit) ✅
- **E13:** prior decay live ✅
- **P2:** distill tổng quát (hết truncate 500-char) ✅
- **OPS1:** catalog editor live (hoặc read-path + ghi nhận UI sau nếu cắt) ✅
- **T3:** coverage tăng + CI xanh + tests pass ✅
- **Nguyên tắc #2 + READ-ONLY giữ vững:** `grep` engine không keyword miền; không tool ghi ✅
- **Regression: eval 4/4 + 2 KB E2E + Telegram không vỡ** ✅

---

## Thứ tự cắt nếu hụt giờ (từ dưới lên)

1. D51 mục C demo-MCP stand-in — tùy chọn, bỏ trước tiên (tests vẫn dùng mocked MCP).
2. D54 mục B catalog editor UI → giữ read-path (load DB nếu có), UI/write sang Future.
3. D53 mục A real-LLM → đã defer (mock + ghi chờ credit); giữ harness là đủ.
4. D55 ngưỡng coverage gate → để display-only nếu chưa kịp enforce.

> **KHÔNG cắt:** D51 (F1 distill+guard+mapping) · D52 (F2 synergy+catalog+specificity) · D55 (test + Cổng + audit READ-ONLY). Đây là xương sống Phase 10.

---

## Future / sau Phase 10 (chưa lên lịch)

- **Bidirectional code action** (vd mở PR rollback) — phá READ-ONLY, cần duyệt riêng rõ ràng.
- **Catalog editor đầy đủ** (nếu D54 chỉ kịp read-path).
- **B1 Tier-2 Postgres · C2 bidirectional output · B2 horizontal scale seam** — như Phase 8/9, vẫn Future.
- **Real-LLM eval đầy đủ** (chạy khi có credit; harness đã sẵn từ D53).

---

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` + file này.
2. Bám ngày hiện tại, kết thúc bằng verify Cổng kiểm.
3. Cuối session: cập nhật `BUILD_STATE.md`.
4. **Lõi không được vỡ:** engine chạy 2 KB end-to-end + push Telegram — ưu tiên trên mọi thứ. Ngày engine/tool (51–54) chạy regression gate trước khi đóng.
5. **READ-ONLY tuyệt đối với code:** code tool chỉ đọc; bất kỳ tool ghi nào từ MCP đều bị guard loại. Lệch → hỏi người dùng trước.
6. Lệch 4 nguyên tắc / stack → hỏi người dùng trước.
