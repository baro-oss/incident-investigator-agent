# 17 — Roadmap Phase 12 (Ngày 61–63): LLM UI Catalog + Bug Fix Batch

> Tiếp nối sau **Phase 11 ✅ (60/60 ngày, 461/461 tests, CI xanh, deploy GreenNode AgentBase)**.
> Mục tiêu phase này: (A) nâng UI cấu hình LLM per-project từ free-text thô thành dropdown có catalog (gồm GreenNode MaaS self-hosted) + test connection + bảo mật key đúng; (B) fix batch bug UI/logic tìm được qua review toàn bộ dashboard.
> Plan trước: `docs/10`–`docs/16`. File này là Phase 12 — **3 ngày** (dồn từ bản 5 ngày, KHÔNG cắt scope).

---

## Định hướng phase này

**Chất lượng UI & bảo mật biên nhập.** Không thêm engine feature, không thêm tool, không mở rộng storage schema. Toàn bộ thay đổi nằm ở **biên dashboard/intake** (router, template, một endpoint mới) và **model catalog** (helper không-engine). 4 nguyên tắc kiến trúc + READ-ONLY giữ nguyên — không rò xuống engine.

**Phase nén 3 ngày:** mỗi ngày là một ngày nặng (cỡ L). Ngày 61 = catalog + dropdown; Ngày 62 = test connection + key security + toàn bộ bug fix batch; Ngày 63 = tests + CI + audit + đóng pha. Regression gate (461 tests + eval 4/4 + 2 KB E2E) chạy cuối mỗi ngày.

---

## Bugs tìm được qua code review (cơ sở Phase 12)

| # | Độ ưu tiên | Vị trí | Mô tả | Tác động |
|---|-----------|--------|-------|---------|
| **BUG-01** | HIGH | `dashboard/router.py:254,717` | `localhost:8000` hardcoded trong `dashboard_trigger_post` và `dashboard_investigation_replay` | Trigger UI + Replay đều fail sau Phase 11 đổi port sang 8080 |
| **BUG-02** | MEDIUM | `dashboard/templates/base.html:76` | `current_user.is_root or true` → Admin nav hiện với **mọi** user đã login, bất kể permission | Security: user thường thấy admin links |
| **BUG-03** | MEDIUM | `dashboard/queries.py:519-520` + `project_detail.html:65` | Decrypted API key render vào `value` attribute của `<input type="password">` | Key lộ trong HTML source; `view-source` hoặc DevTools đọc được |
| **BUG-04** | LOW | `dashboard/templates/base.html:21` | Version label "v0.9 · Phase 6" stale | Mismatch thực tế (Phase 11, 461 tests) |
| **BUG-05** | LOW | `dashboard/queries.py:14-16` | Pricing prefix `claude-opus`/`claude-sonnet` không match model ID thực `claude-sonnet-4-6`, `claude-opus-4-8` → cost estimate sai | Cost dashboard hiển thị số không đúng cho run gần đây |
| **BUG-06** | LOW | `dashboard/queries.py:487-489` + `project_detail.html:119-120` | Alert Channels grid hard-code `["telegram","teams","email"]`, bỏ qua `slack` đã có trong `SUPPORTED_CHANNELS` | Slack config không xuất hiện trong project detail UI |
| **BUG-07** | LOW | `dashboard/router.py:330-332` | `update_project` lỗi bị swallow bằng `except: pass` không log | Silent failure khi sửa project name/description |

---

## LLM UI Gaps (cơ sở Phase 12 — mục A)

| # | Gap | Hiện tại | Cần làm |
|---|-----|----------|--------|
| **LLM-01** | Không có model catalog | Free-text input, user gõ sai tên silently save | Dropdown provider + dropdown model `<select>` theo catalog (+ option "Khác" cho self-hosted) |
| **LLM-02** | `together` provider thiếu validation | Factory hỗ trợ, registry `SUPPORTED_PROVIDERS` không có → ValueError nếu user thử đặt | Thêm `together` vào `SUPPORTED_PROVIDERS` |
| **LLM-03** | API key lộ HTML | Key giải mã → render vào `value` attribute | Trả `llm_key_set: bool`, không trả key thật; UI hiện indicator |
| **LLM-04** | Không có "Test Connection" | Chỉ Save/Clear — không biết config đúng không cho đến khi investigation chạy fail | Endpoint `/dashboard/projects/{pid}/llm/test` + nút inline |
| **LLM-05** | Key preserve khi save config | Nếu user bấm Save với `api_key` trống → xóa key cũ (unintended) | Server-side: nếu `api_key` field rỗng → giữ key cũ trong DB |
| **LLM-06** | Model self-hosted (GreenNode MaaS) chưa support | Phải gõ tay base_url + model; không có provider preset | Thêm provider `greennode` (VNG Cloud AI Platform) vào catalog với base_url + 3 model preset; cho phép gõ model tùy chỉnh |

### GreenNode MaaS — phân tích từ curl mẫu (user cung cấp)

VNG Cloud AI Platform (MaaS) — tuyến LLM in-platform của AgentBase (Phase 11 docs §6 đã ghi chú).

| Thuộc tính | Giá trị |
|---|---|
| **Base URL** | `https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1` |
| **API style** | OpenAI-compat (`/v1/chat/completions`) **và** Anthropic-compat (`/v1/messages`) — MaaS expose cả hai |
| **Auth** | `Authorization: Bearer <AI_PLATFORM_API_KEY>` (Bearer token chuẩn — OpenAI SDK tự gửi) |
| **Models mẫu** | `minimax/minimax-m2.5` · `qwen/qwen3-5-27b` · `google/gemma-4-31b-it` |
| **Params** | `max_tokens`, `temperature`, `top_p`, `presence_penalty` (chuẩn OpenAI) |

**Tích hợp:** MaaS OpenAI-compatible qua `/chat/completions` → `OpenAICompatibleClient` cắm thẳng (`base_url` + `api_key`), **KHÔNG sửa client**. `openai.AsyncOpenAI` tự append `/chat/completions` vào base_url → lưu đúng `.../v1`. Provider `greennode` route qua nhánh else của factory → `OpenAICompatibleClient` tự động (không cần sửa factory). Model name có dấu `/` (vd `minimax/minimax-m2.5`) — OpenAI-compat field nhận bình thường.

---

## Ràng buộc cố định (không đổi)

- ❌ KHÔNG thêm engine feature / tool mới trong phase này
- ❌ KHÔNG sửa storage schema (không thêm cột, không tạo bảng mới)
- ❌ KHÔNG dùng external key vault / HSM — tiếp tục dùng Fernet qua `SECRET_KEY` (A2 đã có)
- ❌ KHÔNG sửa `OpenAICompatibleClient`/`AnthropicClient`/factory — GreenNode MaaS chạy qua client OpenAI-compat hiện có (chỉ thêm catalog metadata + base_url)
- ✅ **READ-ONLY giữ nguyên** — test connection chỉ gọi LLM với prompt giả lập, không đụng tool ghi
- ✅ **4 nguyên tắc giữ nguyên** — catalog LLM nằm ngoài engine; test connection không chạy investigation
- ✅ **Self-hosted / MaaS support** — GreenNode MaaS là provider OpenAI-compat thêm vào catalog (base_url preset); model self-hosted ngoài catalog vẫn nhập tay được qua option "Khác". KHÔNG hardcode key — key vẫn qua per-project config (Fernet) hoặc env.
- ✅ **Lõi không vỡ:** regression gate = 461 tests + eval 4/4 mock + 2 KB E2E

### Tuân thủ 4 nguyên tắc (kiểm trước)

| Nguyên tắc | Phase 12 |
|-----------|----------|
| #1 LLM không thấy raw data | ✅ Không đụng tool/Observation |
| #2 Một seam, engine domain-agnostic | ✅ Catalog LLM là helper ở biên dashboard, engine không biết |
| #3 Lõi deterministic | ✅ Không đụng engine logic |
| #4 Async từ biên, một nguồn structured | ✅ Test connection trả JSON structured |
| **READ-ONLY (fintech)** | ✅ Không thêm tool ghi; test connection = "chat" với LLM, không access tool |

---

## Tổng quan Phase 12 (3 ngày)

```
Day 61  LLM catalog + dropdown      PROVIDER_CATALOG (8 provider, +greennode MaaS) + GET /llm-catalog + provider/model <select> + base_url auto-fill + together/greennode providers
Day 62  Test conn + key + bug batch  POST /llm/test + UI + key security (BUG-03) + key preserve + port 8000 (BUG-01) + BUG-02/04/05/06/07
Day 63  Tests + CI + Audit + Cổng    Tests mới (~30) + CI matrix xanh + READ-ONLY/4 nguyên tắc audit + degrade safe + đóng pha
```

| Ngày | Theme | Trọng | Trạng thái |
|------|-------|:----:|-----------|
| 61 | LLM catalog + provider/model dropdown (+ GreenNode MaaS) | **L** | ☐ |
| 62 | Test connection + key security + BUG-01 + bug fix batch | **L** | ☐ |
| 63 | Tests + CI + Audit + Cổng Phase 12 | **L** | ☐ |

**Phụ thuộc:** D61 (catalog backend) → D62 (test connection dùng catalog; bug batch độc lập, dọn cùng D62) → D63 (tests phủ D61+D62, audit + đóng pha).
**Xương sống (KHÔNG cắt):** BUG-01 (port 8000 → app fail) · BUG-03 (key security) · BUG-02 (admin nav) · GreenNode MaaS support · D63 CI green.

---

## Ngày 61 — LLM catalog + provider/model dropdown *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** user chọn provider từ `<select>`, chọn model từ `<select>` (dropdown, không gõ tay) — base_url tự điền theo provider. Có option "Khác (tự nhập)" cho model self-hosted ngoài catalog.

### A. `src/agent/llm/catalog.py` *(must-land)*

Cấu trúc giàu metadata (không chỉ list model) — mỗi provider mang `label`, `base_url` mặc định, `models`, `allow_custom_model`:

```python
PROVIDER_CATALOG: dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic",
        "base_url": "",   # SDK default
        "models": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        "allow_custom_model": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "allow_custom_model": True,
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "allow_custom_model": True,
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "allow_custom_model": True,
    },
    "mistral": {
        "label": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "models": ["mistral-large-latest", "mistral-small-latest", "open-mixtral-8x7b"],
        "allow_custom_model": True,
    },
    "together": {
        "label": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "models": ["meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
        "allow_custom_model": True,
    },
    "ollama": {
        "label": "Ollama (self-hosted)",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3.2", "mistral", "qwen2.5", "phi3"],
        "allow_custom_model": True,
    },
    # GreenNode MaaS — VNG Cloud AI Platform (in-platform LLM của AgentBase)
    "greennode": {
        "label": "GreenNode MaaS (VNG Cloud)",
        "base_url": "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1",
        "models": ["minimax/minimax-m2.5", "qwen/qwen3-5-27b", "google/gemma-4-31b-it"],
        "allow_custom_model": True,   # self-hosted models thay đổi → cho gõ tay
    },
}

def get_provider_catalog() -> dict:
    return PROVIDER_CATALOG

def get_models_for_provider(provider: str) -> list[str]:
    return PROVIDER_CATALOG.get(provider, {}).get("models", [])

def get_default_base_url(provider: str) -> str:
    return PROVIDER_CATALOG.get(provider, {}).get("base_url", "")
```

> Catalog chỉ chứa **metadata công khai** (label / base URL / tên model) — KHÔNG chứa key. Endpoint trả nguyên dict an toàn.

### B. `GET /dashboard/llm-catalog` *(must-land)*

- Route mới trong `dashboard/router.py` (không cần login — data không nhạy cảm)
- Trả `{"catalog": get_provider_catalog()}` — JS dùng để populate dropdown model + auto-fill base_url

### C. Cập nhật `project_registry.py:SUPPORTED_PROVIDERS` *(must-land)*

- Thêm `"together"` **và** `"greennode"` → `{"anthropic", "openai", "gemini", "groq", "mistral", "ollama", "together", "greennode"}`
- `set_project_llm`: nếu `config` không có `base_url` **và** provider có `base_url` mặc định trong catalog → tự điền (`from agent.llm.catalog import get_default_base_url`). Defense-in-depth để greennode chạy kể cả khi UI không gửi base_url.

### D. Cập nhật `project_detail.html` LLM form *(must-land)*

- **Provider:** `<select name="provider">` với 8 `<option>` (anthropic/openai/gemini/groq/mistral/together/ollama/greennode), label đọc từ catalog `label`. Option trống đầu = "dùng default env".
- **Model:** `<select name="model">` (dropdown đúng nghĩa) — JS populate options từ catalog khi chọn provider. Cuối list thêm option `── Khác (tự nhập) ──` → khi chọn, hiện `<input type="text" name="model_custom">` để gõ model self-hosted ngoài catalog.
- **Base URL:** `<input name="base_url">` — JS tự điền `get_default_base_url(provider)` khi đổi provider (nếu field trống), user vẫn sửa được. Với greennode → tự điền `https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1`.
- JS `onchange` trên provider `<select>`: fetch `/dashboard/llm-catalog` (cache sau lần đầu) → render `<option>` model + auto-fill base_url + pre-select model hiện tại nếu có.
- Pre-select provider + model đúng nếu đã có config (`proj.llm_provider` / `proj.llm_model`); nếu model hiện tại không trong catalog → chọn "Khác" + điền vào `model_custom`.
- Server (`dashboard_project_save_llm`): `model = model_custom.strip() or model.strip()` — ưu tiên custom nếu có.

**Cổng Ngày 61:**
- `GET /dashboard/llm-catalog` trả JSON đủ 8 provider (có `greennode` với base_url + 3 model) ✅
- Provider dropdown hiển thị đúng label; model dropdown populate theo provider; base_url tự điền ✅
- Chọn `greennode` → model dropdown có `minimax/minimax-m2.5`, `qwen/qwen3-5-27b`, `google/gemma-4-31b-it`; base_url auto-fill MaaS endpoint ✅
- Option "Khác (tự nhập)" → gõ model tùy chỉnh lưu được ✅
- `set_project_llm(project_id, "together", ...)` và `set_project_llm(project_id, "greennode", ...)` không raise ValueError; greennode tự điền base_url nếu thiếu ✅
- 461 tests vẫn xanh ✅

**KHÔNG làm ở D61:** test connection (D62); bug fixes (D62).

---

## Ngày 62 — Test connection + key security + BUG-01 + bug fix batch *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** user kiểm được endpoint LLM trước khi save; key không lộ trong HTML; trigger/replay hoạt động đúng port; dọn sạch toàn bộ bug batch (BUG-01 → BUG-07).

> Ngày này gộp 2 cụm: **(I)** LLM config quality (test connection + key security + BUG-01) và **(II)** bug fix batch (BUG-02 → BUG-07). Cả hai đều ở biên dashboard, không phụ thuộc nhau → làm tuần tự trong cùng ngày.

### Phần I — LLM config quality

#### A. `POST /dashboard/projects/{pid}/llm/test` *(must-land)*

- Tạo LLM client từ config hiện tại của project (gọi `get_project_llm(pid)` + factory)
- Gọi LLM với prompt tối giản: `"Say OK"` với `max_tokens=5`
- Trả `{"ok": bool, "latency_ms": int, "error": str | null, "model": str}`
- Degrade an toàn: nếu không có per-project config → dùng global env → test global config
- Timeout 10s → trả `{"ok": false, "error": "timeout"}`
- **GreenNode MaaS:** provider `greennode` route qua `OpenAICompatibleClient` (nhánh else factory) với base_url MaaS + key → test connection gọi `/chat/completions` đúng path SDK. Không cần nhánh riêng.

#### B. UI "Test Connection" *(must-land)*

- Nút `🔌 Test Connection` (JS fetch, không reload page)
- Hiện inline badge: `✓ OK (123ms)` hoặc `✗ Error: <message>`
- Badge tự mất sau 8s

#### C. Fix BUG-03 — Key security *(must-land)*

**Backend (`dashboard/queries.py:get_project_detail`):**
- Thay vì `llm_config_raw = {provider, model, base_url, api_key, headers}` với key thật → trả:
  ```python
  "llm_config_display": {
      "provider": ...,
      "model": ...,
      "base_url": ...,
      "key_set": bool(api_key),  # chỉ bool
      "headers": ...,
  }
  ```
- `api_key` KHÔNG bao giờ rời server side về template

**Template (`project_detail.html`):**
- Nếu `proj.llm_config_display.key_set`: hiện badge `🔑 (đã set)` + field `api_key` để trống
- Placeholder thay đổi: `"Để trống = giữ key cũ"` khi key_set = True, `"sk-..."` khi chưa có

#### D. Fix key preserve khi save — LLM-05 *(must-land)*

**Backend (`dashboard/router.py:dashboard_project_save_llm`):**
- Nếu `api_key.strip() == ""` và project đang có key trong DB → KHÔNG xóa key cũ, giữ nguyên
- Chỉ cập nhật `api_key` khi user gõ key mới

**Logic:**
```python
if api_key.strip():
    cfg["api_key"] = api_key.strip()
elif llm_key_set:  # key đã có trong DB → giữ nguyên
    existing_cfg = get_project_llm(project_id)
    if existing_cfg and existing_cfg.get("config", {}).get("api_key"):
        cfg["api_key"] = existing_cfg["config"]["api_key"]
```

#### E. Fix BUG-01 — Port hardcoded *(must-land — xương sống)*

**`dashboard/router.py:254` và `:717`:**
```python
# Thay:
f"http://localhost:8000/projects/{project_id}/trigger"
# Bằng:
_SERVER_PORT = int(os.environ.get("PORT", "8080"))
f"http://localhost:{_SERVER_PORT}/projects/{project_id}/trigger"
```
- Định nghĩa `_SERVER_PORT` module-level một lần (trên cùng file).

### Phần II — Bug fix batch (BUG-02 → BUG-07)

#### F. Fix BUG-02 — Admin nav `or true` *(must-land — xương sống)*

**`base.html:76`:**
```jinja
{# Thay: #}
{% if current_user and (current_user.is_root or true) %}
{# Bằng: #}
{% if current_user and (current_user.is_root or current_user.get('has_admin_perm')) %}
```
- Route `dashboard_home` và các route đã inject `current_user` → thêm `has_admin_perm` vào `_ctx()`:
  ```python
  def _ctx(request, user, **kwargs):
      from agent.auth.rbac import user_can
      has_admin = user.get("is_root") or user_can(user["id"], "user.manage")
      return {"request": request, "current_user": user, "has_admin_perm": has_admin, **kwargs}
  ```

#### G. Fix BUG-04 — Version label stale *(must-land)*

**`base.html:21`:**
```html
<!-- Thay: v0.9 · Phase 6 -->
<!-- Bằng: v1.2 · Phase 12 -->
```

#### H. Fix BUG-05 — Pricing model prefix stale *(must-land)*

**`dashboard/queries.py:14-16`:**
```python
# Thay prefixes cũ:
"anthropic": {
    "claude-opus":   (15.00, 75.00),
    "claude-sonnet": (3.00,  15.00),
    "claude-haiku":  (0.25,  1.25),
    "":              (3.00,  15.00),
}
# Bằng:
"anthropic": {
    "claude-opus-4":    (15.00, 75.00),
    "claude-sonnet-4":  (3.00,  15.00),
    "claude-haiku-4":   (0.25,  1.25),
    "":                 (3.00,  15.00),
}
```
- Prefix `claude-sonnet-4` match `claude-sonnet-4-6`, prefix `claude-opus-4` match `claude-opus-4-8`, v.v.
- **GreenNode MaaS / self-hosted:** `_PRICING` không có entry `greennode` → `_get_pricing` default `(0.0, 0.0)`. Chấp nhận được — self-hosted bill theo infra, không per-token. (Tùy chọn: thêm `"greennode": {"": (0.0, 0.0)}` cho rõ ràng trong dashboard.)

#### I. Fix BUG-06 — Slack thiếu trong channels grid *(must-land)*

**`dashboard/queries.py:487-489`:**
```python
# Thay:
for ch in ["telegram", "teams", "email"]:
# Bằng:
for ch in ["telegram", "teams", "email", "slack"]:
```

**`project_detail.html:119`:**
```jinja
{# Thêm slack icon: #}
{% set ch_icons = {'telegram': '✈', 'teams': '⊞', 'email': '✉', 'slack': '⊞'} %}
{# Thay grid 3 cột thành 4 cột: #}
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
```

#### J. Fix BUG-07 — Silent failure trong router *(must-land)*

**`dashboard/router.py:330-332`:**
```python
# Thay:
try:
    update_project(project_id, name=name.strip(), description=description.strip())
except Exception:
    pass
# Bằng:
try:
    update_project(project_id, name=name.strip(), description=description.strip())
except Exception as e:
    logger.warning("update_project %s failed: %s", project_id, e)
```
- Tương tự cho `add_project_service` và `remove_project_service` swallow errors.

**Cổng Ngày 62:**
- `POST /dashboard/projects/default/llm/test` với config hợp lệ → `{"ok": true, "latency_ms": ...}`; provider sai → `{"ok": false, "error": "..."}` ✅
- HTML `project_detail` không chứa chuỗi `api_key` trong source khi key đã set ✅
- Save config với api_key rỗng → key cũ giữ nguyên ✅
- Trigger UI + Replay hoạt động (đúng port 8080) ✅
- Admin nav ẩn khi user thường (không is_root, không user.manage perm) ✅
- Version label "v1.2 · Phase 12"; pricing đúng cho `claude-sonnet-4-6`; Slack card hiện trong channels grid; `update_project` lỗi được log ✅
- 461 tests vẫn xanh ✅

---

## Ngày 63 — Tests + CI + Audit + Cổng Phase 12 *(NGÀY NẶNG, cỡ L)*

**Mục tiêu:** mọi thứ D61-D62 đều có test; CI xanh trên cả 2 backend; audit + đóng pha.

> Ngày này gộp 2 cụm: **(I)** tests + CI (~30 test mới, target ≥490) và **(II)** audit + tài liệu + cổng kiểm.

### Phần I — Tests + CI

#### A. Tests LLM catalog *(must-land)*

- `test_llm_catalog.py`: `get_models_for_provider("anthropic")` trả list đúng; provider lạ trả `[]`; `get_default_base_url("greennode")` trả MaaS endpoint; `get_default_base_url("anthropic")` trả `""`
- `test_project_llm.py` mở rộng: `set_project_llm("together", ...)` và `set_project_llm("greennode", ...)` không ValueError; greennode không truyền base_url → DB lưu base_url mặc định catalog
- Test `GET /dashboard/llm-catalog` → 200 + JSON có 8 key (gồm `greennode` với base_url + models)

#### B. Tests test-connection *(must-land)*

- Mock `create_llm_client` → `POST /dashboard/projects/default/llm/test` trả `{"ok": true}`
- Mock LLM raise exception → trả `{"ok": false, "error": ...}`
- Không có per-project config → fallback global → ok degrade

#### C. Tests BUG-01 / BUG-03 / key preserve *(must-land)*

- `test_dashboard_router.py`: `POST /dashboard/trigger` (mock investigation) với PORT env=8080 → đúng URL
- `GET /dashboard/projects/default` (mock `get_project_detail`) → response HTML không chứa chuỗi `api_key` trong value attribute
- `POST /dashboard/projects/default/llm` với `api_key=""` khi đang có key → key không bị xóa

#### D. Tests bug fixes batch *(must-land)*

- `test_pricing`: `_get_pricing("anthropic", "claude-sonnet-4-6")` → `(3.00, 15.00)`
- `test_channels`: `get_project_detail` → channels dict có key `"slack"`
- (BUG-02 admin nav: assert `has_admin_perm` False cho user thường → template không render admin link — test qua TestClient nếu khả thi, hoặc unit test `_ctx`)
- Mock eval 4/4 PASS

### Phần II — Audit + đóng pha

#### E. Audit READ-ONLY *(must-land)*

```bash
grep -rn "github\|gitlab\|repo_url\|get_code_diff\|write\|push\|merge\|PR" src/agent/engine/
```
→ chỉ còn comment/docstring, không có lời gọi thật từ engine.

Test connection: `POST /llm/test` không gọi tool nào, không trigger investigation.

#### F. Audit 4 nguyên tắc *(must-land)*

- #1: LLM catalog + test connection không trả raw data
- #2: `from agent.llm.catalog import ...` chỉ trong dashboard/router (+ project_registry cho `get_default_base_url`), KHÔNG trong engine/
- #3: engine/loop.py không thay đổi
- #4: test connection trả JSON structured

#### G. Degrade safe *(must-land)*

- LLM test connection với `SECRET_KEY` unset → degrade (plaintext config, warn, không crash)
- Model dropdown khi JS fail load → user vẫn gõ tay được (fallback: option "Khác" / `<input>`)
- Slack channel form khi chưa config → empty state đúng

#### H. Tài liệu *(must-land)*

- Cập nhật `BUILD_STATE.md` + bảng Phase 12 trong `CLAUDE.md` → Phase 12 ✅
- Cập nhật `docs/17` (file này) → tất cả ngày ☐→✅

**Cổng Phase 12 (bắt buộc):**
- **LLM catalog:** provider dropdown 8 option + model `<select>` + base_url auto-fill + `together`/`greennode` không ValueError ✅
- **GreenNode MaaS:** chọn `greennode` → 3 model preset + base_url MaaS auto-fill; test connection route qua OpenAICompatibleClient OK; option "Khác" cho self-hosted model ngoài catalog ✅
- **Test connection:** endpoint hoạt động + UI badge + degrade ok ✅
- **Key security:** API key không xuất hiện trong HTML source (check `view-source`) ✅
- **Key preserve:** Save config với api_key rỗng không xóa key cũ ✅
- **BUG-01:** Trigger UI + Replay hoạt động đúng trên port 8080 ✅
- **BUG-02:** Admin nav ẩn với user thường ✅
- **BUG-04..07:** version / pricing / slack / silent-error đã fix ✅
- **Tests:** ≥490/490 xanh · CI matrix (sqlite + postgres) xanh ✅
- **Bất biến:** READ-ONLY + 4 nguyên tắc giữ · engine không thay đổi ✅

---

## Thứ tự cắt nếu hụt giờ (từ dưới lên)

1. **D62 test connection UI** — giữ endpoint, bỏ badge UI (dùng curl test thủ công).
2. **D62 BUG-06 slack** — slack channel card defer (chỉ là hiển thị, không ảnh hưởng function).
3. **D61 model dropdown JS** — giữ provider `<select>`, model về free-text (user gõ tay). Catalog backend + base_url auto-fill + `together`/`greennode` provider vẫn làm (GreenNode MaaS support KHÔNG cắt — là yêu cầu deploy).
4. **D63 coverage gate** — giữ số lượng tests, bỏ enforce coverage %.

> **KHÔNG cắt:** BUG-01 (port 8000) · BUG-02 (admin nav) · BUG-03 (key security) · key preserve · GreenNode MaaS support · CI green.

---

## Future / sau Phase 12 (chưa lên lịch)

- **Multi-replica / horizontal scale** — externalize queue/dedup/SSE (Redis); hoàn thiện Redis SSE seam (stub).
- **Real-LLM eval đầy đủ** — chạy khi có credit (harness sẵn từ P10).
- **LLM catalog tự cập nhật** — fetch từ provider API (Anthropic `/models`, GreenNode MaaS `/models` nếu có) thay vì hardcode.
- **GreenNode MaaS qua Anthropic-compat (`/v1/messages`)** — hiện route qua OpenAI-compat (`/chat/completions`); MaaS cũng expose `/v1/messages`. Nếu cần native Anthropic features (prompt caching, tool-use format) → thêm tuyến AnthropicClient + base_url override. Chưa cần Phase 12.
- **Per-project LLM key rotation UI** — xóa/reset key độc lập với provider config.
- **Bidirectional / code action** (mở PR rollback) — phá READ-ONLY, cần duyệt riêng.
- **MySQL backend** — seam đã sẵn; thêm `mysql_backend.py`.

---

## Quy trình làm việc qua session

1. Đầu session: đọc `CLAUDE.md` + `BUILD_STATE.md` + file này.
2. Bám ngày hiện tại, kết thúc bằng verify Cổng kiểm.
3. Cuối session: cập nhật `BUILD_STATE.md`.
4. **Lõi không được vỡ:** 461 tests + eval 4/4 mock + 2 KB E2E. Ưu tiên trên mọi thứ.
5. **DB swap không rò lên engine:** không phải vấn đề của phase này (seam đã đóng ở P11), nhưng vẫn giữ quy tắc.
6. **READ-ONLY + 4 nguyên tắc:** lệch → hỏi người dùng trước.
