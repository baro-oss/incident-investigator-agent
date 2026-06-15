-- Incident Investigation Agent — PostgreSQL schema
-- Dùng với DB_BACKEND=postgres + DATABASE_URL=postgresql://...
-- Tương đương schema.sql nhưng dùng dialect PostgreSQL:
--   INTEGER PRIMARY KEY AUTOINCREMENT → BIGSERIAL PRIMARY KEY
--   Bỏ PRAGMA (không dùng trong PG)
--   Giữ IF NOT EXISTS, UNIQUE, FK ON DELETE CASCADE, partial index

-- Logs từ các service
CREATE TABLE IF NOT EXISTS logs (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    scenario    TEXT NOT NULL,
    service     TEXT NOT NULL,
    level       TEXT NOT NULL,
    message     TEXT NOT NULL,
    error_type  TEXT,
    trace_id    TEXT
);

CREATE INDEX IF NOT EXISTS idx_logs_service_ts   ON logs (service, timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_trace_id     ON logs (trace_id) WHERE trace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_logs_scenario     ON logs (scenario, service, timestamp);

-- Metrics (time-series đã rời rạc hóa theo phút)
CREATE TABLE IF NOT EXISTS metrics (
    id           BIGSERIAL PRIMARY KEY,
    timestamp    TEXT NOT NULL,
    scenario     TEXT NOT NULL,
    service      TEXT NOT NULL,
    metric_name  TEXT NOT NULL,
    value        REAL NOT NULL,
    is_baseline  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_metrics_service_ts ON metrics (service, timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_scenario   ON metrics (scenario, service, metric_name, timestamp);

-- Deploy events
CREATE TABLE IF NOT EXISTS deploys (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    scenario    TEXT NOT NULL,
    service     TEXT NOT NULL,
    version     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'success'
);

CREATE INDEX IF NOT EXISTS idx_deploys_service_ts ON deploys (service, timestamp);

-- Service catalog (tĩnh — nạp một lần từ catalog.json)
CREATE TABLE IF NOT EXISTS service_catalog (
    service              TEXT PRIMARY KEY,
    description          TEXT NOT NULL,
    depends_on           TEXT NOT NULL DEFAULT '[]',
    baseline_error_rate  REAL NOT NULL,
    baseline_latency_p99 REAL NOT NULL
);

-- Trace events (ghi lại quá trình điều tra)
CREATE TABLE IF NOT EXISTS trace_events (
    id               BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    step             INTEGER NOT NULL,
    timestamp        TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    payload          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trace_inv ON trace_events (investigation_id, step);

-- Projects (multi-tenant isolation)
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Services thuộc về project
CREATE TABLE IF NOT EXISTS project_services (
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    service     TEXT NOT NULL,
    PRIMARY KEY (project_id, service)
);

CREATE INDEX IF NOT EXISTS idx_project_services ON project_services (project_id);

-- MCP server registry
CREATE TABLE IF NOT EXISTS mcp_servers (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT    NOT NULL,
    url         TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_enabled ON mcp_servers (enabled);

-- Alert channels per project
CREATE TABLE IF NOT EXISTS project_alert_channels (
    project_id  TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    config      TEXT    NOT NULL DEFAULT '{}',
    enabled     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (project_id, channel),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alert_channels ON project_alert_channels (project_id);

-- Eval results
CREATE TABLE IF NOT EXISTS eval_results (
    id           BIGSERIAL PRIMARY KEY,
    run_id       TEXT    NOT NULL,
    scenario     TEXT    NOT NULL,
    run_number   INTEGER NOT NULL,
    correct      INTEGER NOT NULL,
    confidence   TEXT,
    recall_at_1  INTEGER,
    steps_taken  INTEGER,
    hallucination INTEGER NOT NULL DEFAULT 0,
    token_total  INTEGER NOT NULL DEFAULT 0,
    elapsed_s    REAL,
    provider     TEXT,
    model        TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_results ON eval_results (run_id, scenario);

-- Long-term memory: pattern điều tra thành công
CREATE TABLE IF NOT EXISTS investigation_patterns (
    id              BIGSERIAL PRIMARY KEY,
    project_id      TEXT    NOT NULL DEFAULT 'default',
    service         TEXT    NOT NULL,
    error_pattern   TEXT    NOT NULL,
    tool_sequence   TEXT    NOT NULL,
    root_cause_type TEXT    NOT NULL,
    avg_steps       REAL    NOT NULL DEFAULT 0,
    count           INTEGER NOT NULL DEFAULT 1,
    updated_at      TEXT    NOT NULL,
    UNIQUE(project_id, service, error_pattern)
);

-- ── RBAC ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id            TEXT    PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    is_root       INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
    id          TEXT    PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    is_system   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS permissions (
    key         TEXT    PRIMARY KEY,
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
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id          TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    scope_type       TEXT NOT NULL DEFAULT 'global',
    scope_group_id   TEXT,
    scope_project_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_role_assignments_user ON role_assignments (user_id);

CREATE TABLE IF NOT EXISTS api_tokens (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    last_used   TEXT
);
