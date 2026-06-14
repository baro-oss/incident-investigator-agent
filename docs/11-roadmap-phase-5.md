# 11 — Roadmap Phase 5 (Ngày 21–25): Hardening & Trust

> Tiếp nối sau **20/20 ngày (Phase 1–4 ✅ hoàn tất)**. File này là kế hoạch Phase 5.
> Mục tiêu: biến "demo chạy được" → **"tin được + an toàn + mở rộng được"**.
> Plan 20 ngày gốc: `docs/10-roadmap-20-ngay.md`. File này tiếp nối nó.

---

## Ràng buộc cố định (không đổi)

- ❌ KHÔNG Kafka / message broker → giữ asyncio background task
- ❌ KHÔNG chạy Postgres/MySQL ở runtime → **giữ SQLite WAL**
- ❌ KHÔNG infra nặng → `pip install` + env vars là đủ
- ⚠️ **Storage seam (Ngày 21):** thêm *abstraction* để đổi DB rẻ về sau — **runtime vẫn SQLite**. Đây là seam, KHÔNG phải migration. Migration thật (Tier-2) cần lệnh rõ.

---

## Bối cảnh & quyết định chốt (session lập kế hoạch)

- **5 theme × 5 ngày**, mỗi ngày anchor 1 theme; thứ tự ngày theo ưu tiên + phụ thuộc (không theo thứ tự liệt kê).
- **3 ưu tiên P0:** real-LLM eval (D21) · auth/RBAC (D22) · cost dashboard (D23).
- **Auth = RBAC động đầy đủ** (root · role động · project groups · scoped assignment). Người dùng chọn **giữ 5 ngày, Day 22 nặng** — ép trọn RBAC vào Day 22, chấp nhận spill sang Day 23 sáng; secret-mgmt + graceful-shutdown đẩy xuống cut-list.
- **Storage seam (D21):** chỉ làm Tier-1 (seam). Quét code xác nhận `open_db()` đã là chokepoint (17 file dùng), chỉ 3 file runtime còn `import sqlite3` trực tiếp → seam khả thi & rẻ.

---

## Tổng quan Phase 5

```
Day 21  Engine & Quality + Storage seam — real-LLM eval, calibration, Tier-1 DB seam
Day 22  Auth & RBAC (NGÀY NẶNG)         — root + role động + project groups + scoped assignment
Day 23  Observability                    — cost dashboard, verdict feedback loop, trace retention
Day 24  Integrations                     — webhook signature, Slack adapter, real MCP pack
Day 25  UI/UX + close                    — replay diff, tool test-run, search, Cổng Phase 5
```

| Ngày | Theme | Trọng lượng | Trạng thái |
|------|-------|:-----------:|-----------|
| 21 | Engine & Quality + Storage seam | M+ | ☐ |
| 22 | Auth & RBAC | **L** | ☐ |
| 23 | Observability | M | ☐ |
| 24 | Integrations | M | ☐ |
| 25 | UI/UX + close | S–M | ☐ |

**Phụ thuộc cứng:** D21 → D23 (cost cần token thật). D22 → D24 (auth concept dùng lại cho webhook signature). D23 chừa đệm sáng hứng spill RBAC.

---

## Ngày 21 — Engine & Quality + Storage Seam

**Mục tiêu:** lấp khoảng trống tin cậy #1 (eval mock → real) + dựng seam đổi DB không phá cấu trúc.

### A. Real-LLM eval *(must-land — ưu tiên cao nhất, unblock cost D23)*
- `eval_agent.py` / `eval_fintech.py`: thêm chế độ real-LLM (bỏ `--mock`), chạy N=10 × 6 KB với Anthropic (chạy 1 project bằng Gemini để chứng minh multi-provider).
- Lưu `eval_results`: `correct_rate`, `recall@1`, `avg_steps`, `token_total`, `latency`, `run_at`, `provider`.
- `recall@1` + **calibration** (HIGH có thật sự đúng nhiều hơn MEDIUM không) render trên `/dashboard/eval`.
- Negative-set KB: 1–2 kịch bản mà đáp án đúng là **"chưa đủ bằng chứng"** → đo chống false-positive *(if-time)*.

### B. Storage seam — Tier-1 *(paired)*
- `src/agent/storage/base.py` — `Database` Protocol: `execute / query / query_one / upsert / now / transaction`; row trả về **dict đồng nhất**.
- `src/agent/storage/sqlite_backend.py` — impl hiện tại, **gói SQLite-ism vào trong**: PRAGMA/WAL · placeholder `?` · UPSERT (`ON CONFLICT`/`INSERT OR …`) · bắt `sqlite3.IntegrityError` → exception trung lập.
- Sửa 3 file runtime còn `import sqlite3` trực tiếp (`storage/db.py`, `intake/mcp_registry.py`, `intake/project_registry.py`) → đi qua seam. 17 caller `open_db()` gần như giữ nguyên.
- `DB_BACKEND=sqlite` env scaffold (mặc định sqlite).
- *(if-time)* `storage/postgres_backend.py` **stub** implement Protocol (chưa wire) — chứng minh seam đóng đúng.

**Synergy:** eval run = **regression gate** cho refactor → chứng minh lõi (engine 2 KB + Telegram) không vỡ.

**Cổng Ngày 21:**
- eval real-LLM lưu DB cho 6 KB (correct_rate/token/latency thật) + calibration hiện trên dashboard ✅
- **không còn `import sqlite3` ngoài backend module** (trừ seed/init/migrate scripts) ✅
- eval pass = lõi không vỡ ✅

**KHÔNG làm ở Day 21:** Tier-2 (port query phân tích, DDL, PostgresBackend chạy thật) → xem *Future*.

---

## Ngày 22 — Auth & RBAC *(NGÀY NẶNG, cỡ L, có thể spill sang Day 23 sáng)*

**Mục tiêu:** root user tạo user · gán quyền theo nhóm project · role + quyền cấu hình động.

### Mô hình dữ liệu (6 bảng SQLite mới)
```sql
users(id, username, password_hash, is_root, is_active, created_at)
roles(id, name, description, is_system)              -- is_system=1: role seed, cấm xóa
permissions(key, description)                         -- CATALOG cố định (code enforce)
role_permissions(role_id, permission_key)             -- role có quyền nào (ĐỘNG)
project_groups(id, name, description)                 -- nhóm project có tên
project_group_members(group_id, project_id)           -- FK → projects.id (TEXT slug)
role_assignments(
  id, user_id, role_id,
  scope_type,            -- 'global' | 'group' | 'project'
  scope_group_id,        -- set khi scope_type='group'
  scope_project_id       -- set khi scope_type='project'
)
```

### Ranh giới "động"
- **`permissions` = từ vựng cố định** (mỗi quyền phải có chỗ code kiểm tra — không bịa được quyền engine không enforce).
- **`roles` + `role_permissions` + `role_assignments` = hoàn toàn động** (root tạo role, tick quyền, gán scope tùy ý). Đây là phần "cấu hình quyền động".

### Catalog quyền (~12, map vào route đang có)
`investigation.view · investigation.trigger · investigation.replay · observability.view (eval/cost/health) · project.view · project.manage · mcp.manage · channel.manage · llm.manage (nhạy cảm) · user.manage · role.manage · group.manage`

Role seed (cấm xóa, tạo thêm tùy ý): **admin** (đủ 12) · **operator** (view+trigger+replay+observability) · **viewer** (chỉ view).

### Logic kiểm tra
```python
def user_can(user, perm_key, project_id=None) -> bool:
    if user.is_root: return True
    for a in assignments_of(user):
        if perm_key in perms_of_role(a.role_id):
            if a.scope_type == 'global': return True
            if a.scope_type == 'project' and a.scope_project_id == project_id: return True
            if a.scope_type == 'group' and project_id in projects_of_group(a.scope_group_id):
                return True
    return False
```

### Chốt kỹ thuật (mặc định, 0 dependency nặng)
- Hash: stdlib `hashlib.pbkdf2_hmac` (bcrypt nếu thích).
- Session dashboard: starlette `SessionMiddleware` (cookie ký, ship sẵn FastAPI).
- Caller programmatic (curl `/trigger`, webhook): bảng `api_tokens` (token hash).
- Root bootstrap: `ROOT_USERNAME`/`ROOT_PASSWORD` env, tạo lần đầu nếu chưa có user.

### Thứ tự nội bộ (must-land trên → spill-được dưới)
1. Schema 6 bảng + migration idempotent — S
2. Catalog 12 quyền seed + 3 role seed + `user_can()` — M
3. Root bootstrap + pbkdf2 + SessionMiddleware + login/logout — M
4. Guard ~20 route bằng `require(perm, project_id=...)` — M
5. UI `/admin/users` + `/admin/roles` (lưới checkbox quyền) — M
   — ── *vạch spill: dưới đây được tràn sang Day 23 sáng* ──
6. Project groups + UI scoped-assignment (global/group/project) — M
7. `api_tokens` cho programmatic — S

**Cổng Ngày 22 (bắt buộc):** root login ✅ · guard chặn đúng quyền ✅ · tạo user + tạo **role động** + gán scope (tối thiểu project-lẻ) ✅. *Project groups + api_tokens = nên có, được phép spill.*

**Rủi ro đã chấp nhận:** L nhét 1 slot → khả năng spill cao; bù lại không cắt tính năng RBAC nào.

---

## Ngày 23 — Observability + Project CRUD UI *(+ hứng spill Day 22)*

**Mục tiêu:** giờ đã có token thật từ Day 21 → ra "$/investigation"; đồng thời hoàn thiện quản lý project từ browser.

- **Cost dashboard `/dashboard/cost` (P0):** token + $/investigation per scenario/project (roadmap Day14C chưa ship); giá theo bảng provider.
- **Verdict feedback loop:** nút 👍/👎 trên trang detail → ghi `investigation_patterns` + Langfuse score → vòng phản hồi thật.
- **Project CRUD UI (thêm D23):** tạo/sửa/xóa project trực tiếp từ `/dashboard/projects` thay vì phải dùng API. Gồm:
  - Form tạo project (id slug, name, description) ngay trên trang list
  - Nút Edit inline trên project card (sửa name + description)
  - Nút Delete với confirm (guard: không xóa project `default`)
  - Guard route bằng `require_perm("project.manage")`
- **Trace retention:** policy purge/archive `trace_events` cũ (chống SQLite phình).

**Cổng Ngày 23:** cost page hiện $/inv thật · 👎 ghi DB + Langfuse score · tạo/xóa project từ UI không cần curl.

---

## Ngày 24 — Integrations

- **Webhook signature verify:** HMAC/chữ ký cho Prometheus/Sentry/Grafana → chặn trigger giả (pair với auth Day 22).
- **Slack output adapter:** thêm renderer vào output router (kênh bị thay bằng Teams ở Day10; nhiều team vẫn cần).
- **Real MCP tool pack:** cắm 1 MCP server cộng đồng thật thay demo server → chứng minh hot-plug ngoài đời.

**Cổng Ngày 24:** webhook không chữ ký → 401, có chữ ký → 202 · Slack nhận verdict · agent discover + dùng tool từ MCP server thật.

---

## Ngày 25 — UI/UX + Đóng Phase 5

- **Replay side-by-side diff:** so verdict cũ/mới cạnh nhau (consistency + demo).
- **Tool Registry test-run:** "nhập args → chạy → xem Observation" (roadmap Day18C chưa làm).
- **Investigation search** (full-text verdict/root_cause) + hoàn thiện mobile responsive.
- **Graceful shutdown** (SIGTERM → finish phiên → push partial verdict) — nếu còn giờ (đẩy từ Day 22).
- Cập nhật `BUILD_STATE.md` + bảng Phase trong `CLAUDE.md`.

**Cổng Phase 5:** auth bật + secret (nếu kịp) + cost thật + real-LLM eval + storage seam + ≥1 integration thật (Slack/MCP) + replay diff. Demo 7 phút chạy lại smooth.

---

## Thứ tự cắt nếu hụt giờ (từ dưới lên)

1. Investigation search (D25)
2. Trace retention (D23)
3. **Secret-mgmt** (đã đẩy khỏi D22) — LLM config để env/plaintext tạm
4. **Graceful shutdown** (D25) — làm nếu còn giờ
5. Day 22 spill: `api_tokens` → project-groups (cắt theo thứ tự này)
6. Real MCP pack (D24) — demo MCP server đã đủ chứng minh hot-plug

---

## Future / sau Phase 5 (chưa lên lịch)

- **Tier-2 — DB migration thật:** port ~12 `datetime()` + 8 UPSERT sang dialect-aware, DDL `schema.sql` → Postgres/MySQL, `PostgresBackend` chạy thật + integration test. Đây mới là "đổi DB thật" — cần lệnh rõ.
- **Secret management:** mã hóa `projects.llm_config` + api key at-rest (nếu bị cắt khỏi Phase 5).
- **Bidirectional integrations:** agent ack PagerDuty / comment incident / tạo ticket — ⚠️ phá ranh giới READ-ONLY, cần người dùng duyệt.
- **Horizontal scale:** dedup set + SSE broker in-memory → external store (trần của kiến trúc hiện tại khi lên multi-instance).
- **Confidence calibration nâng cao**, baseline auto-update (roadmap Day12B chưa làm).

---

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` + file này.
2. Bám ngày hiện tại, kết thúc bằng verify Cổng kiểm.
3. Cuối session: cập nhật `BUILD_STATE.md`.
4. Lõi không được vỡ: engine chạy 2 KB end-to-end + push Telegram — ưu tiên trên mọi thứ "đẹp để có".
5. Lệch 4 nguyên tắc / stack → hỏi người dùng trước. (Đặc biệt: Tier-2 DB migration cần lệnh rõ.)
