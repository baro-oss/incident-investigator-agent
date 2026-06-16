# docs/18 — Roadmap Phase 13 (Ngày 64–69): Hardening & Sharpening

> **Trạng thái:** 📋 ĐÃ LÊN KẾ HOẠCH (duyệt 2026-06-16), CHƯA CODE.
> **Chủ đề:** Vá silent-death + parity rò prod · làm engine bớt dừng sớm & verdict cụ thể hơn · siết authz/READ-ONLY · lấp test reliability. **Không thêm cạnh mới.**

---

## Ràng buộc cứng (người dùng chốt 2026-06-16)

1. **KHÔNG đụng schema DB / engine state.** Giữ `Verdict` + `InvestigationState` dataclass nguyên vẹn; KHÔNG `ALTER TABLE`/`CREATE TABLE` mới. **Ngoại lệ duy nhất:** thêm giá trị status `'failed'` cho `investigation_queue` (cột `status` TEXT đã tồn tại — chỉ thêm giá trị, không đổi schema).
   - Hệ quả: H3 re-prompt đếm bằng **biến cục bộ trong loop**, KHÔNG thêm field vào `InvestigationState`. Specificity tuning chỉ sửa logic tính (field `specificity_score` đã có). Nếu một fix hóa ra cần field mới → **DỪNG và hỏi** trước khi thêm.
2. **4 nguyên tắc + READ-ONLY** giữ tuyệt đối. Siết guard nhưng không mở write path tới external source.
3. **Regression gate mỗi ngày:** 502 tests + eval 4/4 (mock) + 2 KB E2E + Telegram. Từ Ngày 65 chạy trên **cả sqlite & postgres**.
4. Mock eval (không tốn credit real-LLM trong Phase 13 trừ khi người dùng yêu cầu).

**Xương sống KHÔNG cắt:** H1 (PG cost crash) · H2 (silent-death) · H3 (dừng sớm) · M2 (queue status) · Ngày 69 (test + audit + cổng).
**Cắt nếu hụt giờ:** UX polish (Ngày 68 trang lỗi/logging) → specificity 2-lần-fire (Ngày 67) → graph parity test giữ mức smoke.

---

## Bối cảnh — phát hiện từ session audit (Session mở đầu Phase 13)

Đọc trực tiếp engine core + verify; 4 agent audit song song intake/dashboard/tools/tests. Bảng bug đầy đủ:

### HIGH
- **H1** `json_extract()` vỡ trên Postgres → `/dashboard/cost` + calibration card 500. `queries.py:73,76,83,85`; `postgres_backend._translate` (`:72`) không dịch `json_extract`. `payload` là TEXT → cần `(payload::jsonb->>'x')` + CAST hoặc extract sang Python.
- **H2** Investigation chết im lặng + leak dedup key khi cancel lúc drain. `runner.py:126` add key NGOÀI `async with limiter` (`:134`); discard (`:237`) TRONG; `push_verdict` (`:248`) NGOÀI. `CancelledError` không phải `Exception` → không bị bắt ở `investigation_queue.py:118`.
- **H3** Engine dừng sớm khi LLM trả text-không-verdict. `loop.py:429-431` tự bịa verdict insufficient → kết thúc ngay. Model tầm trung hay phát text giữa chừng.

### MEDIUM
- **M1** Graph path (DEFAULT) không cộng cache-token. `graph.py:88-92` thiếu `cache_creation/read_input_tokens` mà `loop.py:1012-1014` có → cache stats luôn 0 ở prod.
- **M2** Queue đánh dấu crash là `done`. `investigation_queue.py:120-121` `finally` luôn set `done`; không có `failed`, không retry.
- **M3** `trace_request` báo trace-đứt là dead code. `trace_request.py:120-125` chỉ `pass`; chỉ case 1-service xử lý; multi-hop đứt báo `complete=True` (`:127`) — vi phạm nguyên tắc #4.
- **M4** Cost dashboard tính giá sai. `queries.py:121,131` hardcode Sonnet; `_get_pricing` (`:34-35`) prefix `"claude-haiku-4"` lệch model thật `claude-3-5-haiku-*`.
- **M5** READ-ONLY guard blacklist + lỗ hẹp. `registry.py:42-78`: tool read-prefix + verb ghi vị trí sau ngoài `_WRITE_PARTS` lọt (`search_and_replace`, `fetch_and_apply`, `read_and_archive`). Write tool GitHub/GitLab thật đều bị bắt → rủi ro thực thấp, fix defense-in-depth.
- **M6** IDOR: channel toggle (`router.py:427`), services add/delete, **catalog add/delete** (`:1360,:1397`) chỉ `require_login`. Catalog lái engine → đáng lo nhất. 🔶 verify.
- **M7** SSE `/stream/{id}` (`router.py:141`) không auth + cross-project enumerable; `sse_backends.get_sse_broker()` dead code (`SSE_BACKEND=redis` no-op). 🔶 verify.
- **M8** `get_code_diff` distill 2 lần. `get_code_diff.py:132-138` risk heuristic chạy trên summary đã cắt 200-char → code-risk Phase 10 vô hiệu. 🔶 verify.
- **M9** `get_dependencies` không cap samples. `get_dependencies.py:91-93` thiếu `[:SAMPLES_HARD_CAP]`, `truncated=False` cứng. 🔶 verify.
- **M10** `resilience.py` chỉ chạy graph path & 0 test (205 dòng). loop path gọi `decide_next_action` thẳng không retry.
- **M11** `with open_db()` rò connection trên SQLite. `hypothesis_catalog.py:183,237,264,274` (sqlite3 `__exit__` chỉ commit, không close). 🔶 verify.
- **M12** Dedup race TOCTOU. Key chỉ add khi background task chạy, không phải lúc enqueue → 2 trigger trùng cùng lọt.

### LOW (chọn lọc)
- **L1** `push_verdict(None)` thiếu guard (`output/router.py:57`). **L2** multi_agent không set `parse_degraded` (`multi_agent.py:353`). **L3** `_emit_trace` mở conn mới mỗi event + sync DB trong async loop (`loop.py:745`). **L4** `time_window.split("-")` không validate (mọi tool; loop bọc try → error-obs). **L5** HMAC bỏ qua khi thiếu `X-Alert-Source` (`server.py:689`). **L6** `list_investigations` filter sau `LIMIT`. **L7** open-redirect `next` GET login (`server.py:284`). **L8** HTML reflect chưa escape (`exc.perm`, replay error fragment).

### Điểm yếu engine
- Dừng sớm (H3). Specificity signal (b) đếm cả số từ timestamp (`specificity.py:42,91`); gate fire 1 lần. Tool sequencing chỉ advisory cap 3 (`loop.py:70-105`). Multi-agent không có competing gate (`multi_agent.py:360-373`). Grounding 25% overlap thô (`loop.py:230-277`). Summary chỉ giữ 3 evidence gần nhất (`state.py:227`).

### UX/DX gaps
- Cost dashboard số sai (M1+M4). Seam giả Redis SSE (M7). Replay/error HTML fragment thô. Không phân biệt timeout/error/crash (M2). trace_request nói "complete" khi đứt (M3). Logging thiếu correlation field nhất quán.

---

## Kế hoạch theo ngày

| Ngày | Theme | Deliverable | Cổng kiểm |
|------|-------|-------------|-----------|
| 64 | Reliability: silent-death & queue bookkeeping | H2 outer-`finally` (discard + push luôn chạy) · L1 guard `push_verdict(None)` · M2 status `failed` (chỉ `done` khi success) · M12 add dedup key tại enqueue · bắt `CancelledError` riêng ở worker | cancel-lúc-drain → key giải phóng + output push; crash → status=`failed` + reload được; 2 trigger trùng nhanh → 1 chạy |
| 65 | Dialect parity prod + cost accuracy | H1 dịch `json_extract`→`(col::jsonb->>'x')`+CAST (hoặc extract Python) · M4 `_get_pricing` substring + giá theo provider/model thật · M11 đóng conn trong `finally` | `/dashboard/cost` + calibration card 200 trên **PG**; Haiku tính đúng giá Haiku; không rò conn (SQLite) qua catalog editor |
| 66 | Engine quality I: chống dừng sớm + trace trung thực + graph parity | H3 re-prompt 1–2 lần (biến cục bộ, KHÔNG thêm state field) trước khi insufficient · M3 dependency↔trace cross-check + hạ độ tin + cờ khi đứt · M1 cộng cache-token graph path + dồn token accounting vào helper chung · M10(1) bật `with_retry` cho loop path | mock text rác → re-prompt rồi mới insufficient; trace rớt hop giữa → `complete=False`+break_point; graph → cache stats >0; loop có retry khi LLM lỗi tạm |
| 67 | Engine quality II: specificity tuning + tool sequencing + code-diff | Loại số timestamp/time-window khỏi `_count_distinct_numbers` · threshold theo confidence · (cân nhắc) specificity gate fire 2 lần · competing gate cho multi-agent · M8 fix code-diff distill 2 lần · M9 cap `get_dependencies` samples · L4 validate `time_window`→error-obs | verdict chỉ-nhắc-time-window KHÔNG qua gate; multi-agent high+competing-open bị downgrade; code-diff ra additions/deletions/risk thật; deps ≤5 samples + `truncated` đúng |
| 68 | Security/authz + UX/DX polish | M5 siết READ-ONLY guard (allowlist tên / mở verb + yêu cầu cả prefix-đọc lẫn không-verb-ghi) · M6 `require_perm` scoped cho channel/service/repo/**catalog** · M7 auth+scope cho SSE + xóa/nối thật `sse_backends` · trang lỗi nhất quán + escape (L8) · L5 HMAC bắt buộc path external · logging thêm investigation_id/project_id nhất quán | tool ghi giả định bị loại khỏi registry; user A không sửa project B; SSE yêu cầu auth + đúng project; không còn HTML-fragment reflect exception |
| 69 | Tests reliability + Cổng Phase 13 | Unit test `postgres_backend._translate` · test invariant **error→push_verdict luôn chạy** · test `resilience` (retry/CB/limiter) · test graph-execution + parity loop↔graph · test READ-ONLY guard với tên ghi · test queue drain + `failed` · thay test mong manh (AST/source-grep day59, logic-dup phase12) bằng test hành vi · audit READ-ONLY+4 nguyên tắc+degrade · cập nhật BUILD_STATE/CLAUDE/docs · đóng pha | tests mới xanh cả 2 backend; `_translate` có test; invariant push-on-every-branch có test; audit clean; Cổng P13 PASS |

---

## Map deliverable → 3 mảng người dùng yêu cầu

- **Bug fixes & reliability:** Ngày 64 (H2/L1/M2/M12) · Ngày 65 (H1/M11) · Ngày 68 (M5/M6/M7/L5/L8).
- **Engine optimization:** Ngày 66 (H3/M3/M1/M10) · Ngày 67 (specificity/tool-seq/M8/M9/competing-gate).
- **UX / developer experience:** Ngày 65 (cost đúng) · Ngày 68 (trang lỗi/SSE seam/logging) · Ngày 69 (test reliability).

## Defer → Future (không trong Phase 13)
- Real-LLM eval đầy đủ (chờ credit). Horizontal scale / Redis SSE thật (M7 chỉ dọn dead-code hoặc nối tối thiểu). Bidirectional / code action (phá READ-ONLY). MySQL backend. Thêm field state/schema cho engine (cần lệnh rõ).
