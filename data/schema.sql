-- Incident Investigation Agent — SQLite schema
-- WAL mode được bật khi init DB (xem data/init_db.py)

-- Logs từ các service
CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,          -- ISO-8601, e.g. "2024-01-15T14:05:03Z"
    scenario    TEXT NOT NULL,          -- "scenario1" | "scenario2" — để lọc kịch bản
    service     TEXT NOT NULL,
    level       TEXT NOT NULL,          -- ERROR | WARN | INFO
    message     TEXT NOT NULL,
    error_type  TEXT,                   -- TimeoutException | ConnectionError | NULL nếu không lỗi
    trace_id    TEXT                    -- NULL ở chỗ trace đứt (KB2)
);

CREATE INDEX IF NOT EXISTS idx_logs_service_ts   ON logs (service, timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_trace_id     ON logs (trace_id) WHERE trace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_logs_scenario     ON logs (scenario, service, timestamp);

-- Metrics (time-series đã rời rạc hóa theo phút)
CREATE TABLE IF NOT EXISTS metrics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    scenario     TEXT NOT NULL,
    service      TEXT NOT NULL,
    metric_name  TEXT NOT NULL,         -- latency_p99 | error_rate | request_count | ...
    value        REAL NOT NULL,
    is_baseline  INTEGER NOT NULL DEFAULT 0  -- 1 = khoảng "bình thường" trước sự cố
);

CREATE INDEX IF NOT EXISTS idx_metrics_service_ts ON metrics (service, timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_scenario   ON metrics (scenario, service, metric_name, timestamp);

-- Deploy events
CREATE TABLE IF NOT EXISTS deploys (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    scenario    TEXT NOT NULL,
    service     TEXT NOT NULL,
    version     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'success'  -- success | failed | rolled_back
);

CREATE INDEX IF NOT EXISTS idx_deploys_service_ts ON deploys (service, timestamp);

-- Service catalog (tĩnh — nạp một lần từ catalog.json)
CREATE TABLE IF NOT EXISTS service_catalog (
    service              TEXT PRIMARY KEY,
    description          TEXT NOT NULL,
    depends_on           TEXT NOT NULL DEFAULT '[]',  -- JSON array of service names
    baseline_error_rate  REAL NOT NULL,               -- errors/min bình thường
    baseline_latency_p99 REAL NOT NULL                -- ms
);

-- Trace events (ghi lại quá trình điều tra — dùng từ Ngày 2)
CREATE TABLE IF NOT EXISTS trace_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL,
    step            INTEGER NOT NULL,
    timestamp       TEXT NOT NULL,
    event_type      TEXT NOT NULL,   -- tool_call | tool_result | decision | verdict
    payload         TEXT NOT NULL    -- JSON
);

CREATE INDEX IF NOT EXISTS idx_trace_inv ON trace_events (investigation_id, step);

-- Projects (multi-tenant isolation)
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,               -- slug, vd "payment-platform"
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Services thuộc về project (many-to-many: 1 service có thể ở nhiều project)
CREATE TABLE IF NOT EXISTS project_services (
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    service     TEXT NOT NULL,
    PRIMARY KEY (project_id, service)
);

CREATE INDEX IF NOT EXISTS idx_project_services ON project_services (project_id);

-- MCP server registry (quản lý qua API, load lúc start server)
CREATE TABLE IF NOT EXISTS mcp_servers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,                -- tên hiển thị, vd "Prometheus Metrics"
    url         TEXT    NOT NULL UNIQUE,         -- endpoint MCP, vd "http://host:9000/mcp"
    description TEXT    NOT NULL DEFAULT '',     -- mô tả ngắn gọn
    enabled     INTEGER NOT NULL DEFAULT 1,      -- 0 = tắt, không kết nối
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_enabled ON mcp_servers (enabled);

-- Alert channels per project
CREATE TABLE IF NOT EXISTS project_alert_channels (
    project_id  TEXT    NOT NULL,
    channel     TEXT    NOT NULL,   -- 'telegram' | 'teams' | 'email'
    config      TEXT    NOT NULL DEFAULT '{}',  -- JSON: channel-specific overrides
    enabled     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (project_id, channel),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alert_channels ON project_alert_channels (project_id);

-- Eval results (lưu kết quả mỗi lần chạy eval_agent.py)
CREATE TABLE IF NOT EXISTS eval_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT    NOT NULL,   -- UUID per eval run (cùng run_id cho tất cả scenario trong 1 lần chạy)
    scenario     TEXT    NOT NULL,
    run_number   INTEGER NOT NULL,
    correct      INTEGER NOT NULL,   -- 0/1
    confidence   TEXT,
    recall_at_1  INTEGER,            -- 0/1: service đúng có trong evidence sau bước 1 không
    steps_taken  INTEGER,
    hallucination INTEGER NOT NULL DEFAULT 0,  -- 1 = verdict claim gì không có evidence đỡ
    token_total  INTEGER NOT NULL DEFAULT 0,
    elapsed_s    REAL,
    provider     TEXT,               -- LLM provider chạy eval (anthropic/gemini/mock) — Phase 5 D21
    model        TEXT,               -- LLM model (vd claude-sonnet-4-6)
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_results ON eval_results (run_id, scenario);

-- Long-term memory: pattern điều tra thành công
CREATE TABLE IF NOT EXISTS investigation_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      TEXT    NOT NULL DEFAULT 'default',
    service         TEXT    NOT NULL,   -- service bị lỗi (root cause)
    error_pattern   TEXT    NOT NULL,   -- error_type keyword chính (vd "TimeoutException")
    tool_sequence   TEXT    NOT NULL,   -- JSON array: chuỗi tool dẫn đến verdict HIGH
    root_cause_type TEXT    NOT NULL,   -- vd "deploy_bug" | "provider_down" | "pool_exhaustion"
    avg_steps       REAL    NOT NULL DEFAULT 0,
    count           INTEGER NOT NULL DEFAULT 1,
    updated_at      TEXT    NOT NULL,
    UNIQUE(project_id, service, error_pattern)
);

-- ── RBAC (Auth & RBAC — Phase 5 Ngày 22) ────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id            TEXT    PRIMARY KEY,  -- UUID slug
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    is_root       INTEGER NOT NULL DEFAULT 0,  -- 1 = super-admin, bypass all checks
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
    id          TEXT    PRIMARY KEY,  -- slug vd "admin", "operator"
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    is_system   INTEGER NOT NULL DEFAULT 0   -- 1 = seed role, cấm xóa
);

CREATE TABLE IF NOT EXISTS permissions (
    key         TEXT    PRIMARY KEY,  -- vd "investigation.view"
    description TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id        TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_key TEXT NOT NULL REFERENCES permissions(key) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_key)
);

CREATE TABLE IF NOT EXISTS project_groups (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_group_members (
    group_id    TEXT NOT NULL REFERENCES project_groups(id) ON DELETE CASCADE,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, project_id)
);

CREATE TABLE IF NOT EXISTS role_assignments (
    id               TEXT PRIMARY KEY,  -- UUID
    user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id          TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    scope_type       TEXT NOT NULL DEFAULT 'global',  -- 'global' | 'group' | 'project'
    scope_group_id   TEXT,  -- set khi scope_type='group'
    scope_project_id TEXT   -- set khi scope_type='project'
);

CREATE INDEX IF NOT EXISTS idx_role_assignments_user ON role_assignments (user_id);

CREATE TABLE IF NOT EXISTS api_tokens (
    id          TEXT PRIMARY KEY,       -- UUID
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,   -- sha256 hex của token thực
    name        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    last_used   TEXT
);
