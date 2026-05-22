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
