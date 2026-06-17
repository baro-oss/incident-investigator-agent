# Phase 14 — Bug Fix & UX Batch (Ngày 70–73)

> **Chủ đề:** Bug tracking tập trung — mọi bug do người dùng report đều được log ở đây để trace.
> **Ràng buộc:** KHÔNG đụng engine lõi / schema chính; chỉ sửa bugs + UX dashboard/intake.
> **Baseline:** 594/594 tests · Phase 13 PASS (2026-06-16).

---

## Bug Registry (bảng theo dõi tất cả bugs đã report)

> Quy tắc: mọi bug người dùng báo cáo đều thêm vào đây với ngày report, nguồn, trạng thái.
> Format ID: `BUG-14-XX` (Phase 14), `UX-14-XX` (UX/DX), `ENG-14-XX` (engine context).

| ID | Ngày report | Severity | Mô tả | Nguồn | Trạng thái |
|----|-------------|----------|-------|-------|------------|
| BUG-14-01 | 2026-06-16 | HIGH | MCP URL UNIQUE toàn cục → cùng URL không đăng ký được cho nhiều project khác nhau | User (session trước) | ✅ Đã fix |
| BUG-14-02 | 2026-06-16 | MEDIUM | Service delete redirect URL double slash: `/services//delete` | User (2026-06-16) | ✅ Đã fix |
| BUG-14-03 | 2026-06-16 | MEDIUM | API key / secret key inputs không mask — người khác nhìn thấy trên UI | User (2026-06-16) | ✅ Đã fix |
| BUG-14-04 | 2026-06-16 | MEDIUM | `schema_postgres.sql` thiếu 3 column `llm_provider`, `llm_model`, `llm_config` so với SQLite migration | Session song song | ✅ Đã fix |
| BUG-14-05 | 2026-06-16 | LOW | SQLite pool warning "rolling back returned connection" — `open_db()` không commit trước `close()` | Session song song | ✅ Đã fix |
| UX-14-01 | 2026-06-16 | LOW | Service list thiếu description field — agent không có ngữ cảnh mô tả service | User (session trước) | ✅ Đã fix |
| UX-14-02 | 2026-06-16 | LOW | Trigger page: `<select>` cứng — không tự nhập service/scenario ngoài danh sách | User (session trước) | ✅ Đã fix |
| UX-14-03 | 2026-06-16 | LOW | Channels page: slack thiếu icon; card disabled màu tối đặc không phân biệt rõ | User (session trước) | ✅ Đã fix |
| UX-14-04 | 2026-06-16 | LOW | Login page default dark mode — nên là light mode để nhất quán với phần còn lại | User (2026-06-16) | ✅ Đã fix |
| ENG-14-01 | 2026-06-16 | LOW | Engine LLM context: `available_services` chỉ liệt kê tên, không có mô tả → LLM không biết service làm gì | Phát hiện khi fix UX-14-01 | ✅ Đã fix |
| OPS-14-01 | 2026-06-16 | — | Ansible setup `deployment/` — deploy PostgreSQL 16 lên server VPS (xem `.env`), port 5432 public, DB+user clawathon | Session song song | ✅ Đã setup |

---

## Chi tiết từng bug

### BUG-14-01 — MCP URL uniqueness: global → per-project ✅

**Mô tả:** Schema cũ: `mcp_servers.url TEXT UNIQUE` toàn cục → cùng 1 URL MCP chỉ đăng ký được vào 1 project. Multi-tenant scenario: 2 project dùng chung 1 MCP server sẽ fail khi thêm project thứ 2.

**Fix:**
- `data/schema.sql`: bỏ `UNIQUE` trên `url` riêng lẻ, comment rõ index mới qua migration.
- `data/schema_postgres.sql`: thêm `UNIQUE (url, project_id)` inline.
- `data/migrate_phase14.py`: rebuild `mcp_servers` (SQLite không drop column-level UNIQUE) → `CREATE UNIQUE INDEX idx_mcp_url_project ON mcp_servers (url, project_id)`.
- `src/agent/intake/mcp_registry.py`: cập nhật error message → "đã tồn tại trong project 'X'" thay vì "trong registry".

**Files:** `schema.sql` · `schema_postgres.sql` · `migrate_phase14.py` · `mcp_registry.py`

---

### BUG-14-02 — Service delete URL double slash 📋 TODO

**Mô tả:** URL `/dashboard/projects/default/services//delete` — double slash → 404/redirect sai. Xảy ra khi `svc.service` render thành empty string trong form action.

**Root cause candidates:**
1. Service tên rỗng `""` có trong DB (không bị chặn ở layer intake).
2. URL-special characters trong service name (vd `/`, `?`) làm hỏng path.

**Fix (Ngày 71):**
- `router.py`: validate `service.strip()` không rỗng + không chứa `/` khi `add_project_service`; trả redirect kèm flash error nếu invalid.
- `project_detail.html`: URL-encode service name trong form action (`{{ svc.service | urlencode }}`); thêm guard `{% if svc.service %}` bỏ qua row lỗi.
- `router.py:dashboard_project_del_service`: guard `if not service.strip(): redirect` phòng thủ.

**Files:** `router.py` · `project_detail.html`

---

### BUG-14-03 — API key / secret inputs không mask 📋 TODO

**Mô tả:** Các ô input chứa credential (API key, bearer token, API key value cho MCP) hiện là `type="password"` (đã ẩn khi load) nhưng **không có nút show/hide**. Người dùng không thể verify key đã nhập đúng chưa mà không reopen.

**Các field cần fix:**

| File | Field | Vị trí |
|------|-------|--------|
| `project_detail.html` | LLM API Key (`name="api_key"`) | Line ~90 |
| `mcp.html` | MCP Bearer Token (`id="bearer-token"`) | Line ~64 |
| `mcp.html` | MCP API Key Value (`id="apikey-value"`) | Line ~78 |

**Fix (Ngày 71):** Bọc mỗi `<input type="password">` trong `<div style="position:relative">`, thêm `<button type="button">` overlay ở góc phải toggle type `password`↔`text`. Dùng emoji 👁/🙈. JS function inline `toggleSecret(id, btn)`. Không cần library.

**Files:** `project_detail.html` · `mcp.html`

---

### BUG-14-04 — schema_postgres.sql thiếu llm columns ✅

**Mô tả:** `schema_postgres.sql` không có `llm_provider`, `llm_model`, `llm_config` — 3 column đã có trong SQLite migration (Phase 12). Hệ quả: fresh PG deploy bị lỗi khi save LLM config cho project.

**Fix:** Thêm 3 column vào block `CREATE TABLE projects` trong `schema_postgres.sql`.

**Files:** `data/schema_postgres.sql`

---

### BUG-14-05 — SQLite "rolling back returned connection" warning ✅

**Mô tả:** Pattern cũ `conn = open_db(); ...; conn.close()` trên SQLite backend trả connection về pool khi vẫn còn implicit transaction mở → pool phải rollback và log warning.

**Fix:**
- `sqlite_backend.py`: thêm `_SQLiteConn` wrapper — `__exit__` commit/rollback rồi close connection (đồng nhất với `_PGConnection` behavior).
- `auth/rbac.py`: migrate toàn bộ từ `conn = open_db(); ...; conn.close()` → `with open_db() as conn:`.

**Files:** `src/agent/storage/sqlite_backend.py` · `src/agent/auth/rbac.py`

---

### UX-14-04 — Login page default dark mode ✅

**Mô tả:** Login page (standalone, không extends base.html) không có theme detection → luôn render dark mode dù user đã chọn light mode ở dashboard.

**Fix:** Thêm script trước `</body>` đọc `localStorage('ia-theme')` (default `'light'`) và apply `body.theme-light` class. Cập nhật version string.

**Files:** `src/agent/dashboard/templates/login.html`

---

### OPS-14-01 — Ansible PostgreSQL deployment setup ✅

**Mô tả:** Setup tự động hoá deploy PostgreSQL 16 lên server VPS qua Ansible.

**Kết quả:** PG16 chạy trên server, port 5432 mở public, DB `clawathon` + user `clawathon` đã tạo. Tuning cho 1CPU/2GB RAM.

**Cấu trúc:**
```
deployment/
├── ansible.cfg                          # key, inventory, become
├── inventory/hosts.ini                  # server cloud
├── group_vars/all/vars.yml              # PG config + tuning
├── group_vars/all/vault.yml             # secrets (gitignored cùng thư mục)
├── playbooks/deploy_postgres.yml
└── roles/postgresql/
    ├── tasks/main.yml                   # cài PG16, tạo DB/user, UFW
    ├── handlers/main.yml
    ├── templates/postgresql.conf.j2     # tuned config
    └── templates/pg_hba.conf.j2        # allow 0.0.0.0/0
```

**Makefile targets:** `make ansible-ping` · `make ansible-check` · `make ansible-postgres`

**Ghi chú:** Thư mục `deployment/` gitignored (chứa PEM key — KHÔNG commit).

**Files:** `deployment/` (gitignored) · `Makefile` · `.gitignore`

---

### UX-14-01 — Service description field ✅

**Mô tả:** Service chỉ lưu tên, không có mô tả → agent không biết service làm gì (vd "payment-gateway" — cổng thanh toán hay internal gateway?).

**Fix:**
- `schema.sql` + `schema_postgres.sql`: thêm `description TEXT NOT NULL DEFAULT ''` vào `project_services`.
- `data/migrate_phase14.py`: `ALTER TABLE project_services ADD COLUMN description`.
- `project_registry.py`: thêm `list_project_services_detailed()`, `get_service_descriptions()`, cập nhật `add_project_service(description="")` → upsert (có thể update mô tả service đã tồn tại).
- `queries.py:get_project_detail()`: trả services dạng `[{service, description}]` thay vì `[str]`.
- `router.py`: thêm `description: str = Form("")` vào `dashboard_project_add_service`.
- `project_detail.html`: hiện description dưới tên service; thêm input `description` trong form "Thêm / cập nhật".

**Files:** `schema.sql` · `schema_postgres.sql` · `migrate_phase14.py` · `project_registry.py` · `queries.py` · `router.py` · `project_detail.html`

---

### UX-14-02 — Trigger page: select → combobox ✅

**Mô tả:** Field Service/Scenario/Time Window là `<select>` cứng → không tự nhập tên service chưa có trong project, không thử scenario custom.

**Fix:** Đổi sang `<input type="text" list="...">` + `<datalist>` — vẫn gợi ý dropdown nhưng cho phép tự nhập giá trị khác. JS `switchDomain()` + `updateServices()` cập nhật `datalist` innerHTML thay vì `select` innerHTML.

**Files:** `trigger.html`

---

### UX-14-03 — Channels page: slack icon + disabled style ✅

**Mô tả:** Channels page thiếu icon cho `slack`; card khi disabled dùng `background:#0d0d0d` (màu cứng, không theo theme).

**Fix:** Thêm `'slack': '💬'` vào `channel_icons`; đổi disabled background sang `var(--surface2)` + `opacity:.7`.

**Files:** `channels.html`

---

### ENG-14-01 — Engine context: thêm service_descriptions ✅

**Mô tả:** `state.to_context()` chỉ list tên service (`payment-gateway, auth-service, ...`) không có mô tả → LLM không phân biệt được vai trò từng service, có thể điều tra nhầm hướng.

**Fix:**
- `state.py`: thêm `service_descriptions: Dict[str, str]` field; cập nhật `to_context()` render `- service: mô tả` thay vì plain list.
- `loop.py`: thêm `service_descriptions` param vào `investigate()`.
- `multi_agent.py`: propagate `service_descriptions` qua specialists + merge.
- `runner.py`: thêm `_get_service_descriptions()`, truyền vào engine call.

**Files:** `state.py` · `loop.py` · `multi_agent.py` · `runner.py`

---

## Lịch triển khai

| Ngày | Theme | Nội dung | Trạng thái |
|------|-------|----------|-----------|
| 70 | Commit batch (đã làm) | BUG-14-01 + UX-14-01/02/03 + ENG-14-01 + migrate_phase14.py | ✅ DONE |
| 71 | Bug fixes + UX | BUG-14-02 service delete URL · BUG-14-03 mask inputs · UX-14-04 login light mode | ✅ DONE |
| 71b | Session song song | BUG-14-04 PG schema parity · BUG-14-05 SQLite conn warning · OPS-14-01 Ansible setup | ✅ DONE |
| 72 | Tests + cổng P14 | Tests cho toàn bộ batch · 4 nguyên tắc · READ-ONLY audit · cổng | 📋 TODO |
| 73 | Reserve | Dự phòng cho bug phát sinh thêm | — |

---

## Cổng kiểm Phase 14

- [ ] `migrate_phase14.py` chạy idempotent trên SQLite
- [ ] BUG-14-01: Thêm cùng URL MCP vào 2 project → PASS; thêm trùng trong cùng project → lỗi rõ
- [ ] BUG-14-02: Form delete service tạo URL hợp lệ (không double slash); service tên rỗng bị reject
- [ ] BUG-14-03: Các input password có nút 👁 toggle; click 2 lần → ẩn lại
- [ ] BUG-14-04: `schema_postgres.sql` có đủ llm_provider/llm_model/llm_config trong CREATE TABLE projects
- [ ] BUG-14-05: Không còn "rolling back returned connection" warning trong SQLite log
- [ ] UX-14-01: Thêm service + description → hiển thị đúng; thêm lại → update description
- [ ] UX-14-02: Trigger page nhập tay service name ngoài danh sách → gửi đúng
- [ ] UX-14-03: Channels page slack có icon; disabled card nhìn rõ theo theme
- [ ] UX-14-04: Login page load với light mode theo mặc định; dark mode vẫn hoạt động
- [ ] ENG-14-01: `state.to_context()` chứa mô tả service khi có description
- [ ] ≥ 594 tests xanh (không giảm)
- [ ] READ-ONLY + 4 nguyên tắc giữ nguyên

---

## Ràng buộc

- **KHÔNG đụng** engine state field `Verdict`/`InvestigationState` ngoài `service_descriptions` (đã thêm)
- **KHÔNG thêm** column schema ngoài `project_services.description` (đã có trong migration)
- **KHÔNG sửa** test files hiện có — chỉ thêm tests mới
- Mock eval (không tốn credit)
