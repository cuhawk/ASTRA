-- ASTRA core auth + quota + vault schema. Idempotent.
-- Applied at app startup (backend.db.connection.init_db).

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    github_id       INTEGER NOT NULL UNIQUE,
    github_login    TEXT    NOT NULL,
    email           TEXT,
    created_at      INTEGER NOT NULL,  -- unix seconds
    last_login_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_github_id ON users(github_id);

CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,  -- base64url(32 random bytes)
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   INTEGER NOT NULL,
    expires_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS api_keys_encrypted (
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider         TEXT    NOT NULL,
    dek_ciphertext   BLOB    NOT NULL,
    dek_nonce        BLOB    NOT NULL,
    key_ciphertext   BLOB    NOT NULL,
    key_nonce        BLOB    NOT NULL,
    created_at       INTEGER NOT NULL,
    updated_at       INTEGER NOT NULL,
    PRIMARY KEY (user_id, provider)
);

-- Append-only audit log of quota deductions. Authoritative counter lives
-- in Redis (`quota:<user_id>:<YYYY-MM-DD>`); this table is for forensics
-- and billing reconciliation only.
CREATE TABLE IF NOT EXISTS audit_quota (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bucket       TEXT    NOT NULL,        -- YYYY-MM-DD
    delta        INTEGER NOT NULL,        -- positive = deduct
    reason       TEXT    NOT NULL,        -- e.g. "nl_to_cypher", "chain_triage"
    at           INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_quota_user_bucket ON audit_quota(user_id, bucket);

-- Append-only log of every LLM call (free + pro). Cost computed at call
-- time from token counts × per-model rate. Authoritative daily spend
-- counter lives in Redis (`llm_spend:<provider>:<YYYY-MM-DD>`); this
-- table is the forensic / billing surface.
CREATE TABLE IF NOT EXISTS audit_llm_calls (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER REFERENCES users(id) ON DELETE SET NULL,
    provider            TEXT    NOT NULL,
    model               TEXT    NOT NULL,
    reason              TEXT    NOT NULL,
    prompt_tokens       INTEGER NOT NULL DEFAULT 0,
    completion_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd            REAL    NOT NULL DEFAULT 0.0,
    outcome             TEXT    NOT NULL,
    duration_ms         INTEGER NOT NULL DEFAULT 0,
    at                  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_llm_calls_user_at ON audit_llm_calls(user_id, at);
CREATE INDEX IF NOT EXISTS idx_audit_llm_calls_at      ON audit_llm_calls(at);

-- Run lifecycle. `id` doubles as the slug under runs/<user_id>/<run_id>/
-- on disk (managed by backend.pillars.memory.runs.RunLayout).
CREATE TABLE IF NOT EXISTS runs (
    id           TEXT    PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url          TEXT,
    status       TEXT    NOT NULL,
    error        TEXT,
    created_at   INTEGER NOT NULL,
    started_at   INTEGER,
    finished_at  INTEGER,
    files        INTEGER NOT NULL DEFAULT 0,
    functions    INTEGER NOT NULL DEFAULT 0,
    edges        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_runs_user_status ON runs(user_id, status);

CREATE TABLE IF NOT EXISTS features (
    id                  TEXT    PRIMARY KEY,
    run_id              TEXT    NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    name                TEXT    NOT NULL,
    created_at          INTEGER NOT NULL,
    last_run_at         INTEGER,
    last_status         TEXT,
    error               TEXT,
    matched_functions   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (run_id, name)
);

CREATE INDEX IF NOT EXISTS idx_features_run ON features(run_id);

-- Persistent audit log of user-facing actions: runs created/deleted, features
-- recorded, auth logins, LLM calls (the row pointer here, transcripts live in
-- audit_llm_calls). Visible to the owning user; not cross-user.
-- Retention: 7 days, swept lazily on each insert (see backend.audit.events).
CREATE TABLE IF NOT EXISTS audit_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action       TEXT    NOT NULL,
    entity       TEXT    NOT NULL,
    entity_id    TEXT,
    payload      TEXT,
    at           INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_events_user_at ON audit_events(user_id, at);
CREATE INDEX IF NOT EXISTS idx_audit_events_at ON audit_events(at);

-- LLM transcript columns live on audit_llm_calls. SQLite has no
-- ADD COLUMN IF NOT EXISTS, so the migration runs in Python — see
-- backend.db.connection.init_db.

-- Per-run chat thread. One conversation per (user, run); ordering by id.
-- llm_call_id ties an assistant message to its audit row (transcript +
-- token usage live there). System-context messages are NOT persisted —
-- they're rebuilt per turn from the run's graph.
CREATE TABLE IF NOT EXISTS chat_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT    NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    role          TEXT    NOT NULL CHECK (role IN ('user', 'assistant')),
    content       TEXT    NOT NULL,
    llm_call_id   INTEGER REFERENCES audit_llm_calls(id) ON DELETE SET NULL,
    created_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_run ON chat_messages(run_id, id);
