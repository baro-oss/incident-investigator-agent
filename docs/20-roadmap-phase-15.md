# Phase 15 — UI Audit, i18n & UX Polish (Ngày 74–77)

## Bug Registry

### BUG-15-01 [HIGH] Version stale trong base.html
- **File:** `src/agent/dashboard/templates/base.html:21`
- **Vấn đề:** `v1.2 · Phase 12` — login.html hiển thị đúng `v1.4 · Phase 14`
- **Fix:** Cập nhật thành `v1.4 · Phase 14`

### BUG-15-02 [HIGH] Curl example dùng port 8000 trong trigger.html
- **File:** `src/agent/dashboard/templates/trigger.html:120`
- **Vấn đề:** `localhost:8000` — đã fix ở BUG-01 Phase 12 cho JS dynamic port nhưng hardcoded curl example chưa đổi
- **Fix:** Đổi thành `localhost:8080`

### BUG-15-03 [HIGH] Curl example dùng port 8000 trong admin_tokens.html
- **File:** `src/agent/dashboard/templates/admin_tokens.html:84`
- **Vấn đề:** `localhost:8000` trong hướng dẫn sử dụng
- **Fix:** Đổi thành `localhost:8080`

### BUG-15-04 [MEDIUM] Link chết trong health.html
- **File:** `src/agent/dashboard/templates/health.html:118`
- **Vấn đề:** `href="/projects/default/mcp-servers"` — route không tồn tại
- **Fix:** Đổi thành `/dashboard/mcp`

### BUG-15-05 [LOW] Empty state MCP page thiếu action guidance
- **File:** `src/agent/dashboard/templates/mcp.html:174`
- **Vấn đề:** Empty state chỉ có text, không có icon hoặc hướng dẫn rõ ràng
- **Fix:** Thêm icon + message hướng dẫn action đầu tiên

---

## UX Issues

### UX-15-01 [MEDIUM] Text "Xoá" vs "Xóa" không nhất quán
- **File:** `admin_users.html:78`, `metrics_live.html:21`
- **Chuẩn:** "Xóa" (dùng ở hầu hết template còn lại)
- **Fix:** Đổi tất cả "Xoá" → "Xóa"

### UX-15-02 [MEDIUM] CSS variable không nhất quán
- **Files:**
  - `catalog.html`: dùng `--bg-secondary`, `--text-muted` (không có trong style.css theme)
  - `cost.html`: dùng `--severity-high`, `--text-secondary` (không chuẩn)
- **Chuẩn:** `--surface`, `--surface2`, `--muted`, `--high`, `--text`
- **Fix:** Thay thế variables không chuẩn bằng variables chuẩn

### UX-15-03 [LOW] Admin pages thiếu breadcrumb/back navigation
- **Files:** `admin_roles.html`, `admin_tokens.html`, `admin_groups.html`
- **Vấn đề:** Không có "← Admin" hoặc back link đến trang cha rõ ràng
- **Fix:** Thêm back link vào page header

### UX-15-04 [LOW] channels.html thiếu confirm khi toggle OFF
- **File:** `src/agent/dashboard/templates/channels.html:41`
- **Vấn đề:** Tắt channel không có confirm dialog
- **Fix:** Thêm `onsubmit="return confirm(...)"` khi enabled=true

---

## i18n Plan

### I18N-15-01 — Cơ chế i18n client-side
- **Approach:** JS dict + `data-i18n` attribute
- **File mới:** `src/agent/dashboard/static/i18n.js`
- **Toggle:** Button trên navbar, lưu `ia-lang` vào localStorage
- **Ngôn ngữ:** `vi` (mặc định) + `en`

### Scope i18n (Phase 15):
- Navigation labels (sidebar + nav groups)
- Page titles + section headers chính
- Button labels phổ biến (Thêm, Xóa, Lưu, Huỷ, Bật, Tắt)
- Empty state text
- Không bắt buộc: flash messages, error từ server

---

## Bảng chuẩn hoá text

| Khái niệm | Chuẩn (VI) | Chuẩn (EN) |
|-----------|-----------|-----------|
| Thêm mới | Thêm | Add |
| Xóa | Xóa | Delete |
| Lưu | Lưu | Save |
| Huỷ | Huỷ | Cancel |
| Cập nhật | Cập nhật | Update |
| Bật | Bật | Enable |
| Tắt | Tắt | Disable |
| Đăng xuất | Đăng xuất | Logout |
| Quản lý | Quản lý | Manage |

---

## Tiến độ

| ID | Loại | Mô tả | Trạng thái |
|----|------|-------|-----------|
| BUG-15-01 | BUG | Version base.html | ✅ |
| BUG-15-02 | BUG | Port 8000 trigger.html | ✅ |
| BUG-15-03 | BUG | Port 8000 admin_tokens.html | ✅ |
| BUG-15-04 | BUG | Dead link health.html | ✅ |
| BUG-15-05 | UX | Empty state MCP | ✅ |
| UX-15-01 | UX | "Xoá" → "Xóa" | ✅ |
| UX-15-02 | UX | CSS var không chuẩn | ✅ |
| UX-15-03 | UX | Admin breadcrumb | ✅ |
| UX-15-04 | UX | Channel toggle confirm | ✅ |
| I18N-15-01 | I18N | i18n.js + toggle button | ✅ |

---

## Cổng kiểm Phase 15

- [x] i18n.js được serve 200, không có console error
- [x] `data-i18n` attributes trong nav base.html — JS thay text khi toggle
- [x] Reload trang → localStorage giữ ngôn ngữ (applyLang đọc `ia-lang` khi DOMContentLoaded)
- [x] Port 8000 không còn trong bất kỳ template nào (`trigger.html`, `admin_tokens.html`)
- [x] Dead link `/projects/default/mcp-servers` → `/dashboard/mcp`
- [x] "Xoá" không còn xuất hiện (tất cả là "Xóa")
- [x] CSS vars `--bg-secondary`, `--text-secondary`, `--severity-high` đã chuẩn hoá
- [x] 594/594 tests vẫn xanh
- [x] docs/20-roadmap-phase-15.md đầy đủ

**Cổng Phase 15 PASS ✅**
