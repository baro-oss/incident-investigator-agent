# 14 — Roadmap Phase 9 (Ngày 46–50): Engine lõi thông minh hơn — Prior · Tool-sequencing · Specificity

> Tiếp nối sau **45/45 ngày (Phase 1–8 ✅ hoàn tất, 173/173 tests, Python 3.14)**. File này là kế hoạch Phase 9.
> Mục tiêu: từ **"engine domain-agnostic + chất lượng được gác tự động"** → **"engine ĐIỀU TRA THÔNG MINH HƠN: ít bước hơn, hướng dẫn tốt hơn, verdict actionable hơn"**.
> Plan trước: `docs/10` (P1–4) · `docs/11` (P5) · `docs/12` (P6) · Phase 7 inline trong `BUILD_STATE.md` · `docs/13` (P8). File này tiếp nối.

---

## Định hướng phase này

**100% engine-core.** Không thêm cạnh mới (intake/output/UI), không infra mới. Cả 3 hướng đều siết vòng lặp điều tra ở giữa — đúng tinh thần "tập trung tối ưu engine lõi". Ba hướng:

| # | Tên | Một câu | Đòn bẩy hạ tầng sẵn có |
|---|-----|---------|------------------------|
| **E10** | Hypothesis-guided tool sequencing | Engine gợi ý "giả thuyết X còn open → tool nào kiểm tốt nhất tiếp theo" vào prompt mỗi bước | `HypothesisCatalogEntry.relevant_tools` (đã có) · `_build_user_message`/`summarize_for_llm` |
| **E11** | Cross-investigation service prior (service memory) | Sự cố lặp lại → pre-seed giả thuyết theo lịch sử service, bắt đầu đúng hướng thay vì từ 0 | `investigation_patterns` (đã có) · `get_warm_start_hint`/`save_pattern` · `calibration.py` |
| **E12** | Verdict specificity gate | Đo độ cụ thể của verdict; verdict mờ → nudge LLM làm rõ (loop) / hạ cấp + annotate (multi-agent) | `_apply_competing_gate` + `_check_evidence_grounding` (pattern để follow) |

---

## Ràng buộc cố định (không đổi)

- ❌ KHÔNG Kafka / message broker → queue vẫn **in-process asyncio**.
- ❌ KHÔNG Postgres/MySQL ở runtime → **giữ SQLite WAL**. Tier-2 vẫn Future.
- ❌ KHÔNG infra nặng → `pip install` + env là đủ.
- ✅ **READ-ONLY giữ nguyên** — output chỉ push.
- ✅ **Horizontal scale seam → vẫn Future** (Redis SSE giữ stub).
- ⚠️ **Lõi không được vỡ:** mọi ngày engine (46–49) phải qua **regression gate** = eval 4/4 mock + 2 KB end-to-end + push Telegram.

### Tuân thủ 4 nguyên tắc kiến trúc (kiểm trước, từng hướng)

| Nguyên tắc | E10 | E11 | E12 |
|-----------|-----|-----|-----|
| #1 LLM không thấy raw data | ✅ hint từ catalog + lịch sử tool (không raw row) | ✅ prior từ aggregate DB (count/type), không raw | ✅ metric đọc `evidence.summary` (đã chưng cất), không raw |
| #2 Một seam, engine domain-agnostic | ✅ đọc catalog (data), KHÔNG hardcode tool/keyword miền | ✅ map `root_cause_type→tag` đặt **trong catalog**, không nhét keyword vào engine | ✅ metric là heuristic số/chuỗi tổng quát, zero keyword miền |
| #3 Lõi deterministic, agent chỉ điều phối | ✅ hint **advisory** — LLM vẫn tự chọn tool | ✅ prior chỉ đổi **thứ tự khám phá**; confirm vẫn cần bằng chứng thật (`_update_hypotheses`) | ✅ metric + gate deterministic; nudge không ép verdict |
| #4 Async từ biên, một nguồn structured | ✅ không đụng | ✅ không đụng | ✅ `specificity_score` là field structured, render ở biên |

> **Điểm canh gác #2 (quan trọng nhất):** thành quả lớn nhất của Phase 8 là engine **không còn hardcode keyword miền**. Phase 9 KHÔNG được tái phạm. Mọi tri thức miền (tool nào kiểm giả thuyết nào, root_cause_type ↔ tag) phải sống trong **catalog**, engine chỉ đọc.

---

## Điểm yếu / cơ hội đã xác nhận trong code (cơ sở Phase 9)

| # | Quan sát | Vị trí (đã đọc code) | Hệ quả |
|---|----------|----------------------|--------|
| **E10** | Việc chọn tool **hoàn toàn phó mặc LLM**. Catalog biết `relevant_tools` cho mỗi giả thuyết nhưng tri thức này **không bao giờ vào prompt**. | `loop.py:_build_user_message` (66) · `state.py:summarize_for_llm` (185) đọc hypotheses nhưng không nối với `relevant_tools` | LLM hay gọi lặp `get_metrics` thay vì chuyển sang tool xác nhận giả thuyết đang open; điều tra dài hơn cần thiết. Domain mới (fintech) thiếu prior knowledge càng lạc hướng. |
| **E11** | Mỗi investigation bắt đầu từ 0. `investigation_patterns` đã lưu `{service, root_cause_type, count, avg_steps, tool_sequence}` nhưng chỉ dùng làm **text hint** (`warm_start_hint`), KHÔNG seed giả thuyết. | `memory/patterns.py:get_warm_start_hint` (76) chỉ trả 1 chuỗi text · `state.warm_start_hint` render trong `summarize_for_llm` (229) | Sự cố lặp lại (phần lớn incident thực) vẫn tốn 2–3 bước đầu xác nhận điều đã biết. Hệ thống không "thông minh hơn theo thời gian" một cách có cấu trúc. |
| **E12** | Không có metric đo **độ actionable** của verdict. Grounding guard (E2) chỉ chặn verdict *bịa* (overlap < 25%), không phân biệt "payment-gateway lỗi" (mờ) vs "p99 9× baseline từ 14:03, deploy v2.3.1" (cụ thể) — cả hai đều pass. | `loop.py:_check_evidence_grounding` (183) chỉ check overlap; không có chiều "cụ thể" | Verdict mờ vẫn được push Slack → on-call vẫn phải tự mở dashboard → mất giá trị hệ thống. |

**Đòn bẩy chung:** cả 3 đều xây trên hạ tầng đã có. `relevant_tools` đã trong catalog (E10); `investigation_patterns` + lazy `_upsert_hypothesis`-theo-tag (E11); `_apply_competing_gate` idempotent + `_check_stop_conditions` dùng chung loop/graph (E12).

**Phát hiện kiến trúc làm Phase 9 rẻ:** `_run_loop` (loop.py:823) và `decide_node` (graph.py:68) **cùng gọi** `decide_next_action` → `_build_user_message`. Multi-agent specialist chạy `InvestigationEngine` bên dưới. ⇒ Hint E10 đặt trong `_build_user_message`/`summarize_for_llm` **tự động** tới cả 3 engine, parity miễn phí.

---

## Bối cảnh & quyết định chốt (session lập kế hoạch)

Session này **không code** — đọc kỹ toàn bộ engine (`loop.py`, `state.py`, `graph.py`, `multi_agent.py`, `hypothesis_catalog.py`, `calibration.py`, `memory/patterns.py`, `runner.py`, `schema.sql`) → chốt Phase 9.

**Quyết định mặc định (đề xuất — người dùng có thể veto bất kỳ):**

1. **E11 = pre-seed giả thuyết (không chỉ text hint).** Tạo `Hypothesis` trạng thái `open` theo lịch sử service NGAY khi khởi tạo state. Vì `_upsert_hypothesis` lookup theo `tag`, bằng chứng về sau cập nhật lifecycle các giả thuyết pre-seed này **sạch sẽ, không cần code đặc biệt**. Mạnh hơn và demo được rõ hơn so với chỉ chèn text. *(Đánh đổi: thêm 1 field vào `Hypothesis` + seed có kiểm soát; vẫn cần bằng chứng thật để confirm → không vi phạm #3.)*
2. **E12 = nudge trong loop + downgrade trong multi-agent.** Loop/graph còn budget → nudge LLM làm rõ (giống competing gate, idempotent). Multi-agent VerdictAgent chỉ 1 LLM call không lặp được → áp dưới dạng **annotate + hạ cấp** (giống grounding guard). Một metric `compute_verdict_specificity` dùng chung cả hai.
3. **Day 49 real-LLM eval = SMOKE MỞ RỘNG (~$2)** — KHÔNG full N=10. Khớp pattern tiết kiệm đã chọn ở Day 21/Day 38. Đây là ngày "chứng minh" E10/E11 giảm số bước + E12 nâng specificity trên LLM thật (mock không đo được vì kịch bản mock dài cố định).
4. **Helper gate dùng chung loop+graph (bài học E7).** E12 KHÔNG được viết logic gate 2 lần. Tách `_apply_specificity_gate` + `compute_verdict_specificity`, gọi từ cả `loop.py` lẫn `graph.py`.

**Thứ tự ưu tiên (rủi ro tăng dần):** E11 (đòn bẩy cao, rủi ro thấp) → E10 (tác động rộng, parity free) → E12 (rủi ro cao nhất: metric dễ false-positive, multi-agent bất đối xứng).

---

## Tổng quan Phase 9

```
Day 46  E11  Cross-investigation service prior — pre-seed giả thuyết theo lịch sử service
Day 47  E10  Hypothesis-guided tool sequencing — hint relevant_tools cho giả thuyết open (parity free)
Day 48  E12  Verdict specificity gate (lõi)    — metric + gate nudge cho loop/graph (helper dùng chung)
Day 49  E12  Multi-agent parity + đo trên LLM  — downgrade/annotate multi-agent + dashboard + real-LLM smoke ~$2
Day 50       Tests + CI + Hardening + Cổng P9  — test cả 3 + CI xanh + audit degrade an toàn + đóng pha
```

| Ngày | Theme | Trọng | Trạng thái |
|------|-------|:----:|-----------|
| 46 | E11 — Service prior (pre-seed hypothesis) | **L** | ☐ |
| 47 | E10 — Hypothesis-guided tool sequencing | M+ | ☐ |
| 48 | E12 — Specificity metric + gate (loop/graph) | M+ | ☐ |
| 49 | E12 — Multi-agent parity + real-LLM measurement | M+ | ☐ |
| 50 | Tests + CI + Hardening + Cổng Phase 9 | M | ☐ |

**Phụ thuộc cứng:** E11 (D46) → E10 (D47): hint sequencing **xếp ưu tiên theo prior count** của E11 (synergy). E12 lõi (D48) → E12 multi-agent + đo (D49). D46–49 → D50 (test/CI chạy chính các tính năng mới).

**Xương sống (KHÔNG cắt):** D46 (E11) · D47 (E10) · D48 (E12 lõi) · D50 (test + gate). D49 đo trên real-LLM có thể thu nhỏ (xem mục cắt giờ).

---

## Ngày 46 — E11: Cross-investigation service prior *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** sự cố lặp lại trên một service → engine **pre-seed giả thuyết** đúng hướng từ `investigation_patterns`, bắt đầu thông minh thay vì từ 0. Confirm vẫn cần bằng chứng thật.

### A. Mở rộng dữ liệu giả thuyết *(must-land)*
- `state.py:Hypothesis` — thêm `prior_seen_count: int = 0` (đánh dấu giả thuyết đến từ lịch sử + số lần đã gặp). Mặc định 0 = không phải prior.
- `state.py:summarize_for_llm` — giả thuyết có `prior_seen_count > 0` render kèm chú thích `(đã gặp N lần trên service này — ưu tiên kiểm)` và **xếp lên đầu** danh sách giả thuyết open.

### B. Tra cứu prior từ lịch sử *(must-land)*
- `memory/patterns.py` (hoặc module mới `memory/priors.py`) — `get_service_priors(project_id, service, domain) -> List[Tuple[tag, count]]`:
  - Query `investigation_patterns WHERE project_id=? AND service=? ORDER BY count DESC`.
  - Map `root_cause_type` (vd `deploy_bug`, `pool_exhaustion`) → catalog `tag` (vd `deploy`, `pool_exhaustion`).
  - **Mapping sống trong catalog, không trong engine (nguyên tắc #2):** thêm field `root_cause_type: str` vào `HypothesisCatalogEntry`, build index ngược `{root_cause_type → tag}`. Engine chỉ đọc.
- Mở rộng `_classify_root_cause` (patterns.py:128) phủ fintech + `traffic_surge`→`latency_spike` để prior fintech hoạt động (hiện trả `unknown` cho mọi root cause fintech).

### C. Pre-seed vào state *(must-land)*
- `InvestigationEngine.run()` + `MultiAgentEngine.run()` — nhận `service: Optional[str]`; gọi `get_service_priors`; với mỗi tag prior, tạo `Hypothesis` trạng thái `open` (content + keywords từ catalog, `prior_seen_count=count`) **trước** vòng lặp. Tái dùng cơ chế tag của `_upsert_hypothesis` → bằng chứng sau cập nhật lifecycle bình thường.
- `intake/runner.py` — truyền `service=req.service` vào `engine.run()` (hiện chỉ truyền `warm_start_hint`).

**Cổng Ngày 46 (bắt buộc):**
- Service có lịch sử (count≥1) → state khởi tạo có giả thuyết prior open, đúng tag, xếp đầu ✅
- **Không confirm-không-bằng-chứng:** giả thuyết prior vẫn `open` cho tới khi có evidence khớp `confirm_kws` (test giả lập) ✅
- Prior fintech hoạt động (root_cause_type fintech map đúng tag) ✅
- Service chưa có lịch sử → 0 prior, hành vi y hệt trước (degrade an toàn) ✅
- Regression eval 4/4 mock + microservice 4 KB không đổi + 2 KB E2E + Telegram ✅

**KHÔNG làm ở D46:** đụng tool sequencing (D47); đụng specificity (D48). Chỉ pre-seed + render.

---

## Ngày 47 — E10: Hypothesis-guided tool sequencing

**Mục tiêu:** mỗi bước, engine nói cho LLM biết "giả thuyết nào còn open và tool nào kiểm nó" — LLM vẫn tự quyết (advisory).

### A. Sinh hint từ catalog + lịch sử *(must-land)*
- Hàm thuần `_tool_sequencing_hint(state) -> str` (trong `loop.py`, hoặc method trên state):
  - Với mỗi giả thuyết `open` có entry catalog (`state.hypothesis_catalog_index`): liệt kê `relevant_tools` **chưa** xuất hiện trong `tool_call_history`.
  - Output: `Để kiểm "deploy" (open): chưa gọi get_recent_deploys.` Bỏ qua giả thuyết không còn tool chưa gọi.
  - **Xếp ưu tiên theo `prior_seen_count` (E11 synergy)** rồi tới open thường.
- Nối hint vào `_build_user_message` (loop.py:66) — đặt sau `summarize_for_llm`, trước câu hỏi "Bước tiếp theo".

### B. Parity + tiết kiệm context *(must-land)*
- Parity **miễn phí**: `_build_user_message` được gọi bởi cả `_run_loop` lẫn `decide_node` + specialist multi-agent. Thêm test khẳng định cùng state → cùng hint ở cả 2 path.
- Cap độ dài hint (≤3 giả thuyết, ≤vài dòng) để không phình context (bài học P1).
- Advisory-only: engine **không** ép gọi tool — chỉ in gợi ý (nguyên tắc #3).

### C. (Stretch, nếu dư giờ) tách confirm/rule_out
- Tùy chọn: thêm `confirm_tools`/`rule_out_tools` vào catalog entry cho hint sắc hơn. MVP **tái dùng `relevant_tools`** là đủ — chỉ làm nếu còn thời gian, không nằm trong cổng.

**Cổng Ngày 47:**
- Hint xuất hiện cho giả thuyết open có relevant_tool chưa gọi; biến mất khi đã gọi hết ✅
- Hint xếp giả thuyết prior (E11) lên trước ✅
- loop ↔ graph sinh hint **giống hệt** (parity test) ✅
- Không có giả thuyết open / đã gọi hết tool → không hint (không rác) ✅
- Regression 4/4 + context không phình bất thường ✅

---

## Ngày 48 — E12: Verdict specificity gate — metric + gate (loop/graph)

**Mục tiêu:** đo độ cụ thể của verdict; verdict mờ + còn budget → nudge LLM làm rõ trước khi nhận. Helper dùng chung loop+graph (không drift — bài học E7).

### A. Metric độ cụ thể *(must-land)*
- Module mới `engine/specificity.py` (theo style `calibration.py`): `compute_verdict_specificity(verdict, state) -> Tuple[float, List[str]]`.
- Tín hiệu (deterministic, tổng quát — KHÔNG keyword miền):
  - (a) `root_cause` chứa **số / version-token / timestamp / tên service** (khớp `state.available_services`);
  - (b) `evidence_summary` tham chiếu ≥2 quan sát **có số**;
  - (c) `propagation_note` không rỗng và nêu được service.
- Ngưỡng **bảo thủ** — hiệu chỉnh sao cho 4 KB mock hiện tại vẫn pass (tránh false-positive làm vỡ regression).
- `state.py:Verdict` — thêm `specificity_score: Optional[float] = None`.

### B. Gate nudge dùng chung *(must-land)*
- `loop.py:_apply_specificity_gate(state, *, vtext=None, conf_override=None)` — **mirror** `_apply_competing_gate`: idempotent qua `state._specificity_gate_fired`; budget-guard (`budget_remaining<=1` → pass); chỉ gate khi conf ∈ {high, medium} và score < ngưỡng. Fire → trả nudge `ToolCall(_specificity_gate)`.
- `run_tool` (loop.py:340) — xử lý `_specificity_gate` như synthetic tool: Observation "verdict còn mờ — bổ sung số liệu/timestamp/tên service cụ thể trước khi kết luận".
- Wire **sau** competing gate ở cả 2 nhánh (v_obj + vtext) trong `loop.py:_run_loop` (859–883) **và** `graph.py:decide_node` (107–133). Hai gate idempotent độc lập → tệ nhất +2 bước.

**Cổng Ngày 48:**
- Metric chấm đúng: verdict cụ thể (KB1/KB2 thật) điểm cao; verdict mờ điểm thấp (test) ✅
- Gate nudge đúng 1 lần trên verdict mờ; pass khi verdict cụ thể / hết budget / đã fire ✅
- loop ↔ graph parity (cùng nudge trên cùng state) ✅
- Regression 4/4 (ngưỡng không làm 4 KB mock bị gate sai) ✅

---

## Ngày 49 — E12: Multi-agent parity + đo trên real-LLM

**Mục tiêu:** đưa specificity ngang hàng multi-agent (downgrade vì không loop được) + **chứng minh** E10/E11/E12 có tác dụng trên LLM thật.

### A. Multi-agent parity *(must-land)*
- `multi_agent.py:_synthesize_verdict` (350–356) — sau grounding + calibration, gọi `compute_verdict_specificity`; nếu score < ngưỡng → **annotate** `evidence_summary` + hạ 1 bậc confidence (giống grounding guard). VerdictAgent 1-call không nudge được → đây là cơ chế đúng cho nó.
- `loop.py:run()` finalize (698–712) — luôn tính + set `verdict.specificity_score` (kể cả khi gate không fire) để mọi verdict đều có điểm; emit trong verdict trace event (730).

### B. Dashboard *(must-land, nhẹ)*
- `/dashboard/eval` (hoặc `cost`) — cột/biểu đồ `specificity_score` + **avg steps before/after** (đọc `trace_events`) để thấy E10+E11 giảm bước. Tái dùng pattern `eval.html` đã có.

### C. Real-LLM smoke ~$2 *(chốt — đo, không full N=10)*
- Chạy 2–3 lần × 6 KB (microservice + fintech) real-LLM. **Đo:**
  1. avg steps khi bật prior+sequencing vs tắt (đòn bẩy E10/E11);
  2. phân bố `specificity_score` + số lần gate fire (đòn bẩy E12).
- Lưu vào `eval_results`. Ghi nhận **trung thực** kể cả khi cải thiện nhỏ.

**Cổng Ngày 49:**
- Multi-agent ghi `specificity_score` + hạ cấp verdict mờ ✅
- Dashboard hiện specificity + avg-steps before/after ✅
- Real-LLM smoke cho thấy **giảm số bước đo được** HOẶC **specificity nâng đo được** (ghi số thật) ✅
- Regression 4/4 ✅

---

## Ngày 50 — Tests + CI + Hardening + Cổng Phase 9

**Mục tiêu:** phủ test cả 3 tính năng, CI giữ xanh, audit degrade an toàn, đóng pha.

### A. Tests (mở rộng `tests/test_engine_core.py` + file mới nếu cần)
- **E11:** pre-seed từ lịch sử đúng tag · không confirm-không-bằng-chứng · map fintech root_cause_type→tag · service mới → 0 prior.
- **E10:** nội dung hint đúng · parity loop↔graph · rỗng khi không có open/đã gọi hết · ưu tiên prior.
- **E12:** metric chấm good/vague · gate idempotent + budget-guard · multi-agent downgrade · `specificity_score` luôn được set.
- Mục tiêu: +~20–30 tests (173 → ~195–200), tất cả PASS.

### B. CI + Hardening
- `.github/workflows/ci.yml` chạy sẵn pytest + mock eval 4/4 → xác nhận **xanh** với test mới (kiểm syntax/import phủ file mới `specificity.py`/`priors.py`).
- Audit **degrade an toàn:** không patterns → không prior; không catalog → không hint; không evidence → specificity `insufficient`. Không secret/dep mới.
- Cập nhật `BUILD_STATE.md` + bảng Phase trong `CLAUDE.md` → Phase 9 ✅.

**Cổng Phase 9 (bắt buộc):**
- **E11:** prior giảm bước đo được; pre-seed đúng; confirm vẫn cần bằng chứng ✅
- **E10:** hint sequencing live; loop↔graph parity; advisory (không ép tool) ✅
- **E12:** gate nudge (loop/graph) + downgrade (multi-agent) live; metric không làm vỡ 4 KB mock; dashboard có specificity ✅
- **Nguyên tắc #2 giữ vững:** `grep` `src/agent/engine/` không có keyword miền mới hardcode; mapping root_cause_type↔tag nằm trong catalog ✅
- **Regression: eval 4/4 + 2 KB E2E + Telegram không vỡ** ✅
- Tests xanh (~195–200) + CI xanh ✅

---

## Thứ tự cắt nếu hụt giờ (từ dưới lên)

1. D47 mục C (tách confirm/rule_out) — stretch, bỏ trước tiên.
2. D49 mục C (real-LLM smoke) → giữ tối thiểu 1 run/KB, hoặc tạm mock + ghi "đo real-LLM sau".
3. D49 mục B (dashboard specificity) → để verdict trace ghi điểm là đủ, UI sau.
4. D48 mục A nâng cao (tín hiệu c) → giữ (a)+(b) là đủ cho metric tối thiểu.

> **KHÔNG cắt:** D46 (E11 pre-seed) · D47 mục A+B (E10 hint + parity) · D48 mục B (E12 gate loop/graph) · D50 (test + Cổng). Đây là xương sống engine-quality của Phase 9.

---

## Future / sau Phase 9 (chưa lên lịch)

- **Catalog editor UI** — cho phép vận hành thêm giả thuyết/keyword/tool-mapping mà không sửa Python (gỡ nốt "hypothesis catalog hardcode trong code").
- **Prior decay theo thời gian** — pattern cũ giảm trọng số (hiện chỉ đếm count thuần).
- **B1 Tier-2 Postgres · C2 bidirectional · B2 horizontal scale seam · D4 real MCP pack** — như Phase 8, vẫn Future.

---

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` + file này.
2. Bám ngày hiện tại, kết thúc bằng verify Cổng kiểm.
3. Cuối session: cập nhật `BUILD_STATE.md`.
4. **Lõi không được vỡ:** engine chạy 2 KB end-to-end + push Telegram — ưu tiên trên mọi thứ. Ngày engine (46–49) chạy regression gate trước khi đóng.
5. Lệch 4 nguyên tắc / stack → hỏi người dùng trước.
