-- Incident Investigation Agent — PostgreSQL schema (Phase 11)
-- Dùng với DB_BACKEND=postgres + DATABASE_URL=postgresql://...
-- Tương đương schema.sql + tất cả migration (deploy fresh, không migrate data cũ).
-- Dialect PG: BIGSERIAL, không PRAGMA, IF NOT EXISTS, ON CONFLICT.

-- ── Core tables ───────────────────────────────────────────────────────────────

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

CREATE TABLE IF NOT EXISTS deploys (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    scenario    TEXT NOT NULL,
    service     TEXT NOT NULL,
    version     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'success'
);

CREATE INDEX IF NOT EXISTS idx_deploys_service_ts ON deploys (service, timestamp);

CREATE TABLE IF NOT EXISTS service_catalog (
    service              TEXT PRIMARY KEY,
    description          TEXT NOT NULL,
    depends_on           TEXT NOT NULL DEFAULT '[]',
    baseline_error_rate  REAL NOT NULL,
    baseline_latency_p99 REAL NOT NULL
);

-- trace_events includes project_id (added via migrate_projects.py in SQLite)
CREATE TABLE IF NOT EXISTS trace_events (
    id               BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    step             INTEGER NOT NULL,
    timestamp        TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    payload          TEXT NOT NULL,
    project_id       TEXT NOT NULL DEFAULT 'default'
);

CREATE INDEX IF NOT EXISTS idx_trace_inv ON trace_events (investigation_id, step);

-- ── Multi-tenant ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_services (
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    service     TEXT NOT NULL,
    PRIMARY KEY (project_id, service)
);

CREATE INDEX IF NOT EXISTS idx_project_services ON project_services (project_id);

-- mcp_servers includes auth_type, auth_config, project_id (added via migrate files in SQLite)
CREATE TABLE IF NOT EXISTS mcp_servers (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT    NOT NULL,
    url         TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    auth_type   TEXT    NOT NULL DEFAULT 'none',
    auth_config TEXT    NOT NULL DEFAULT '{}',
    project_id  TEXT    NOT NULL DEFAULT 'default'
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_enabled ON mcp_servers (enabled);

CREATE TABLE IF NOT EXISTS project_alert_channels (
    project_id  TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    config      TEXT    NOT NULL DEFAULT '{}',
    enabled     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (project_id, channel),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alert_channels ON project_alert_channels (project_id);

-- ── Eval & patterns ───────────────────────────────────────────────────────────

-- eval_results includes specificity_score, prior_flag (added via migrate_day53.py in SQLite)
CREATE TABLE IF NOT EXISTS eval_results (
    id               BIGSERIAL PRIMARY KEY,
    run_id           TEXT    NOT NULL,
    scenario         TEXT    NOT NULL,
    run_number       INTEGER NOT NULL,
    correct          INTEGER NOT NULL,
    confidence       TEXT,
    recall_at_1      INTEGER,
    steps_taken      INTEGER,
    hallucination    INTEGER NOT NULL DEFAULT 0,
    token_total      INTEGER NOT NULL DEFAULT 0,
    elapsed_s        REAL,
    provider         TEXT,
    model            TEXT,
    created_at       TEXT    NOT NULL,
    specificity_score REAL,
    prior_flag       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_eval_results ON eval_results (run_id, scenario);

-- investigation_patterns includes alerted_at (added via migrate_day32.py in SQLite)
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
    alerted_at      TEXT,
    UNIQUE(project_id, service, error_pattern)
);

-- ── RBAC ──────────────────────────────────────────────────────────────────────

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

-- ── Extended tables (added via migrations in SQLite) ─────────────────────────

CREATE TABLE IF NOT EXISTS investigation_feedback (
    investigation_id TEXT PRIMARY KEY,
    score            INTEGER NOT NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_triggers (
    id           TEXT PRIMARY KEY,
    project_id   TEXT    NOT NULL DEFAULT 'default',
    service      TEXT    NOT NULL,
    scenario     TEXT    NOT NULL DEFAULT 'scenario1',
    interval_min INTEGER NOT NULL DEFAULT 60,
    enabled      INTEGER NOT NULL DEFAULT 1,
    last_run_at  TEXT,
    next_run_at  TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sched_project ON scheduled_triggers (project_id);
CREATE INDEX IF NOT EXISTS idx_sched_next    ON scheduled_triggers (next_run_at);

CREATE TABLE IF NOT EXISTS investigation_queue (
    id          TEXT PRIMARY KEY,
    project_id  TEXT    NOT NULL DEFAULT 'default',
    payload     TEXT    NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'pending',
    enqueued_at TEXT    NOT NULL,
    started_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_inv_queue_status ON investigation_queue (status, enqueued_at);

-- service_repos: mapping service → code repository (Phase 10 D51)
CREATE TABLE IF NOT EXISTS service_repos (
    id             BIGSERIAL PRIMARY KEY,
    project_id     TEXT    NOT NULL DEFAULT 'default',
    service        TEXT    NOT NULL,
    provider       TEXT    NOT NULL DEFAULT 'github',
    repo_url       TEXT    NOT NULL,
    default_branch TEXT    NOT NULL DEFAULT 'main',
    subpath        TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    UNIQUE(project_id, service)
);

CREATE INDEX IF NOT EXISTS idx_service_repos_project ON service_repos (project_id, service);

-- hypothesis_catalog: per-project hypothesis overrides (Phase 10 D54)
CREATE TABLE IF NOT EXISTS hypothesis_catalog (
    id              BIGSERIAL PRIMARY KEY,
    domain          TEXT    NOT NULL DEFAULT 'microservice',
    project_id      TEXT    NOT NULL DEFAULT 'default',
    tag             TEXT    NOT NULL,
    content         TEXT    NOT NULL DEFAULT '',
    keywords        TEXT    NOT NULL DEFAULT '[]',
    relevant_tools  TEXT    NOT NULL DEFAULT '[]',
    confirm_kws     TEXT    NOT NULL DEFAULT '[]',
    rule_out_kws    TEXT    NOT NULL DEFAULT '[]',
    confirm_conf    TEXT    NOT NULL DEFAULT 'medium',
    root_cause_type TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT '',
    UNIQUE(domain, project_id, tag)
);

-- ── Fintech domain tables (Phase 3 D18, migrate_fintech.py) ──────────────────

CREATE TABLE IF NOT EXISTS ft_transactions (
    id           BIGSERIAL PRIMARY KEY,
    timestamp    TEXT    NOT NULL,
    scenario     TEXT    NOT NULL,
    merchant_id  TEXT    NOT NULL,
    channel      TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'success',
    error_type   TEXT,
    processor_id TEXT,
    is_baseline  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ft_tx_scenario ON ft_transactions (scenario, merchant_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ft_tx_channel  ON ft_transactions (scenario, channel, timestamp);

CREATE TABLE IF NOT EXISTS ft_revenue (
    id                BIGSERIAL PRIMARY KEY,
    timestamp         TEXT    NOT NULL,
    scenario          TEXT    NOT NULL,
    channel           TEXT    NOT NULL,
    revenue           REAL    NOT NULL,
    transaction_count INTEGER NOT NULL,
    refund_amount     REAL    NOT NULL DEFAULT 0,
    is_baseline       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ft_rev_scenario ON ft_revenue (scenario, channel, timestamp);

-- ft_merchants: composite PK (id, scenario)
CREATE TABLE IF NOT EXISTS ft_merchants (
    id       TEXT    NOT NULL,
    scenario TEXT    NOT NULL,
    name     TEXT    NOT NULL,
    category TEXT    NOT NULL DEFAULT 'retail',
    status   TEXT    NOT NULL DEFAULT 'active',
    notes    TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (id, scenario)
);

CREATE TABLE IF NOT EXISTS ft_settlements (
    id                BIGSERIAL PRIMARY KEY,
    timestamp         TEXT    NOT NULL,
    scenario          TEXT    NOT NULL,
    merchant_id       TEXT    NOT NULL,
    amount            REAL    NOT NULL,
    processing_time_s REAL    NOT NULL,
    is_baseline       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ft_settle_scenario ON ft_settlements (scenario, merchant_id, timestamp);
