# Session 4: Auth + per-user quota

Branch: `feat/auth-and-quota`
Goal: Stand up the FastAPI app shell plus the user-facing surface required before any LLM endpoint can ship — auth (GitHub OAuth), DB-backed sessions, per-user daily quota counter, and an encrypted vault for user-supplied Anthropic keys.

## Decisions (locked 2026-05-22)

- **Auth:** GitHub OAuth (no magic-link).
- **Session storage:** DB-backed. Random `session_id` in an opaque, signed cookie (itsdangerous); session row in SQLite with `user_id`, `created_at`, `expires_at`. Revocable server-side.
- **Quota:** Real Redis dep. Atomic `INCR` on `quota:<user_id>:<YYYY-MM-DD>` + `EXPIRE` for daily reset. Tests use `fakeredis` in-process.
- **Vault:** Envelope encryption. KEK from env (`ASTRA_VAULT_KEK_HEX`, 32 bytes). Per-key random 256-bit DEK; ciphertext = AES-256-GCM(DEK, plaintext); stored DEK = AES-256-GCM(KEK, DEK). One row per `(user_id, provider)` in `api_keys_encrypted`.
- **DB:** SQLite via `aiosqlite`. Raw SQL DDL in `backend/db/schema.sql`. No Alembic in MVP. Apply at app startup (idempotent `CREATE TABLE IF NOT EXISTS`).
- **Config:** `pydantic-settings` reading from env. Required env keys documented in `.env.example`. No secrets committed.

## Layout

```
backend/
├── main.py              FastAPI app factory + lifespan (DB + Redis + vault)
├── config.py            pydantic-settings: env vars
├── auth/
│   ├── __init__.py
│   ├── routes.py        /auth/github/login, /github/callback, /logout, /me
│   ├── oauth.py         GitHub OAuth client (raw httpx)
│   ├── sessions.py      create / get / delete session rows; cookie signing
│   └── deps.py          FastAPI deps: get_current_user, require_user
├── quota/
│   ├── __init__.py
│   ├── counter.py       Redis-backed daily INCR + read
│   └── middleware.py    pre-LLM-call check + atomic deduct
├── vault/
│   ├── __init__.py
│   └── envelope.py      put_key / get_key / delete_key (AES-256-GCM envelope)
├── db/
│   ├── __init__.py
│   ├── connection.py    aiosqlite pool helpers; lifespan init
│   └── schema.sql       users, sessions, api_keys_encrypted, audit_quota
└── tests/
    ├── conftest.py      shared fixtures: app client, in-memory SQLite, fakeredis, vault KEK
    ├── test_auth_github_oauth.py
    ├── test_sessions.py
    ├── test_quota_counter.py
    ├── test_vault_envelope.py
    └── test_integration_auth_quota.py
```

## Tasks

1. **[SEQUENTIAL]** Add deps to `pyproject.toml`: `fastapi`, `uvicorn[standard]`, `httpx`, `pydantic-settings`, `itsdangerous`, `aiosqlite`, `cryptography`, `redis`, `fakeredis`. Dev deps: `pytest-httpx`. Reinstall.

2. **[SEQUENTIAL]** Scaffold app shell:
   - `backend/main.py` — `create_app()` factory + `lifespan` opening DB + Redis pool + reading vault KEK; mounts auth + quota routers; `/healthz`.
   - `backend/config.py` — `Settings` pydantic-settings model.
   - `backend/db/connection.py` — `get_db()` dependency yielding an `aiosqlite.Connection`. Single shared DB file path from settings (`:memory:` for tests).
   - `backend/db/schema.sql` — `users`, `sessions`, `api_keys_encrypted`, `audit_quota` tables. `CREATE TABLE IF NOT EXISTS` everywhere.
   - `backend/tests/conftest.py` — `app_client` fixture wrapping `httpx.AsyncClient + ASGITransport`, `fake_redis`, `tmp_db`, `vault_kek`.

3. **[PARALLEL after 2]** Auth module. Subagent: `general-purpose`.
   - `oauth.py`: `GitHubOAuth(client_id, client_secret).authorize_url(state)`, `exchange_code(code) → AccessToken`, `fetch_user(token) → GitHubUser{id, login, email}`. Pure httpx. No global state.
   - `sessions.py`: `create_session(db, user_id) → SessionRecord` (random 32-byte id, base64 in cookie); `get_session(db, sid)`; `delete_session(db, sid)`. Cookie helpers: `sign(sid)`, `verify(signed)` via `itsdangerous.Signer(secret)`.
   - `routes.py`:
     - `GET /auth/github/login` → 302 to GitHub auth URL with random `state` (CSRF cookie).
     - `GET /auth/github/callback?code=&state=` → verify state cookie, exchange code, upsert user row, create session, set cookie, 302 to `/`.
     - `POST /auth/logout` → delete session, clear cookie.
     - `GET /auth/me` → current user JSON (401 if not authed).
   - `deps.py`: `get_current_user(...)` dependency that reads cookie → verifies → loads session → loads user.

4. **[PARALLEL after 2]** Quota module. Subagent: `general-purpose`.
   - `counter.py`:
     - `class QuotaCounter(redis_client, daily_limit: int)`
     - `async def remaining(user_id) -> int`
     - `async def deduct(user_id) -> int` — atomic `INCR` then `EXPIRE` if first hit; raises `QuotaExceeded` if past limit. Returns new remaining.
     - Key: `quota:{user_id}:{YYYY-MM-DD}` (UTC). TTL: 26h (slack for clock skew across day boundary).
   - `middleware.py`: a FastAPI dependency `enforce_quota(user)` for LLM endpoints (no endpoints yet — Session 5 — but ship the dep so it's wired and tested).

5. **[PARALLEL after 2]** Vault module. Subagent: `general-purpose`.
   - `envelope.py`:
     - `class KeyVault(kek_hex: str, db_conn)`.
     - `async def put(user_id, provider, plaintext: str) -> None` — generates random 256-bit DEK, encrypts plaintext with AES-256-GCM (random 12-byte nonce), encrypts DEK with KEK + separate nonce, writes row `(user_id, provider, dek_ciphertext, dek_nonce, key_ciphertext, key_nonce)`. Upsert.
     - `async def get(user_id, provider) -> str | None` — round-trip decrypts. Returns `None` if no row.
     - `async def delete(user_id, provider) -> bool`.
     - Never logs plaintext.

6. **[SEQUENTIAL after 3+4+5]** Integration: wire routers into `main.py`. Add an integration test that walks a full GitHub OAuth flow using `pytest-httpx` to mock GitHub endpoints, lands a session, hits `/auth/me`, then hits a probe endpoint (`/probe/quota`) guarded by `enforce_quota` and confirms quota counts down. Anthropic-key roundtrip too.

7. **[SEQUENTIAL]** Wire `just dev-backend` to start uvicorn. Commit. Squash-merge to `main`.

## Verification

- [ ] `just dev-backend` boots and serves `/healthz` returning `{"ok": true}`.
- [ ] `just test` passes — at minimum: 4 oauth + 4 session + 5 quota + 5 vault + 1 e2e integration = ~19 new tests, total ~52.
- [ ] `.env.example` enumerates every required env var (none committed populated).
- [ ] No secrets in git. (Pre-flight grep for keywords.)
- [ ] Anthropic key plaintext is never logged. Spot-check tests assert this.
- [ ] OAuth `state` parameter actually validated (CSRF defense).

## Out of scope

- Magic-link / SSO providers other than GitHub.
- Per-IP rate limiting (Session 10 ops detail).
- Audit log shipped to memory engine (Session 5 owns logging of LLM calls).
- Frontend UI for login (Session 8).
- Email verification.
- 2FA / MFA.
- Account deletion / GDPR endpoints — post-MVP.
