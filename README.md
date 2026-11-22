# ASTRA

**BloodHound for JavaScript web apps.**

Drop a URL or a `.zip` of JS. ASTRA reconstructs the source, builds a callgraph with taint tags, records which functions are live in which user-facing features, and serves the result as an interactive graph you can query in cypher or natural language.

---

## Why

Real-world web apps ship as obfuscated, multi-chunk, sourcemap-stripped bundles. Off-the-shelf SAST tools (CodeQL, Semgrep, Snyk Code) are engineered for source repositories the analyst owns — that is rarely the bug-hunter's input. Dynamic-only tools (Burp DOM Invader, DOMLogger++) observe the running page but cannot prioritize *which* of the 8,000 functions in a webpack chunk to instrument. LLM-only "audit my repo" prototypes hallucinate without ground truth.

ASTRA is the missing middle: a callgraph-grounded, framework-aware static prior over JS bundles, fused with runtime coverage from a real Chrome session, queried through a BloodHound-style graph UI.

---

## What you get

- **Acquisition** — paste a URL or upload a zip. ASTRA fetches every `<script src>`, dynamic `import()`, inline blob, and `.map` file.
- **Sourcemap reconstruction** — restores the original source tree from public sourcemaps.
- **AST + callgraph** — framework-aware, with async edges (`Promise.then`, `addEventListener`, `postMessage`, `setTimeout`, RxJS, service workers).
- **Taint analysis** — source → sink chains with closure-expanded tags and hop-decayed confidence.
- **Feature-level coverage** — drive the site through scripted feature runs; ASTRA labels each function with which features actually execute it. Dead code falls out for free.
- **Interactive graph** — cytoscape.js explorer with code panel, taint chain viewer, and feature labels.
- **Query** — write cypher directly, pick a canned query template, or describe what you want in English.

---

## Tiers

| Tier  | LLM key source                | Quota                |
|-------|-------------------------------|----------------------|
| Free  | ASTRA's Gemini key            | 100 queries / user   |
| Pro   | Your Anthropic API key        | Unlimited (you pay)  |

**Free** uses Gemini Flash + `text-embedding-004` for NL → cypher, chain triage, and semantic search.

**Pro** unlocks the Sonnet → Opus advisor cascade for deeper chain audits. Opus fires only when Sonnet returns uncertain — your key is never burned for free-tier work.

---

## What ASTRA is not

- **Not a SCA tool.** No SBOM, no CVE-to-symbol reachability, no dependency-vuln scanning.
- **Not self-host.** ASTRA is delivered as a hosted SaaS. No desktop app, no local install.
- **Not multi-language.** JavaScript / TypeScript only at MVP. Python and Go are deferred.
- **Not an LLM-first analyzer.** The LLM never builds the graph; it triages and translates queries.

---

## Status

Local-development MVP. Sessions 0–9 of the roadmap in `CLAUDE.md` §12 are landed:

- **0–1** monorepo scaffold + vendored internal-upstream modules (sast, memory, mcp, prompts) @ `83cae23`.
- **2** embedded substrate — Kuzu graph + LanceDB vectors + per-run filesystem layout.
- **3** acquisition pipeline — Playwright headless Chromium harvests JS + sourcemaps; pure-stdlib sourcemap exploder reconstructs the original source tree.
- **4** auth + per-user quota + Anthropic-key vault — GitHub OAuth, Redis-backed daily counter (Lua-atomic), AES-256-GCM envelope encryption with `(user_id, provider)` AAD.
- **5** tier-routed LLM proxy — Gemini Flash for free tier (global daily kill-switch), user-supplied Anthropic key for Pro (Sonnet → Opus cascade with explicit `prefer_opus` or `"verdict":"uncertain"` escalation). Every call logged to `audit_llm_calls`.
- **6** `POST /runs` → acquisition + tree-sitter callgraph → Kuzu Function + CALLS edges. Background worker via FastAPI BackgroundTasks (RQ migration deferred).
- **7** feature coverage — Playwright CDP `Profiler.takePreciseCoverage`, action DSL, sourcemap-aware bundle→source resolution, `EXECUTED_IN` edges from Function → Feature.
- **8** Next.js 16 frontend MVP — sign-in with GitHub, runs CRUD, run detail with status polling, features CRUD with click-selector recording. No cytoscape graph canvas yet.
- **9** Cypher endpoints — raw, NL→Cypher (Gemini), 5 canned playbooks, and a Pro-tier `/advise` endpoint. Read-only keyword whitelist validator.

176 tests, `just test` finishes in ~30s.

A substantial portion of the analysis core is vendored from a private reference workspace (`internal-upstream`). See `VENDORED.md` for upstream provenance.

**Not yet shipped:** real RQ/Dramatiq worker, cytoscape graph canvas, sourcemap byte-range mapping for minified bundles, interprocedural taint port, deploy pipeline (Fly/Railway).

---

## Running locally

Prereqs: Python 3.12, Node 22+, npm, Redis 7+ on `localhost:6379`, Playwright Chromium (`playwright install chromium` after `uv sync`).

### 1. Backend

```
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
.venv/bin/playwright install chromium   # one-shot, ~100MB

cp .env.example .env                    # then populate:
#   ASTRA_GITHUB_CLIENT_ID=<from https://github.com/settings/developers>
#   ASTRA_GITHUB_CLIENT_SECRET=<from same>
#   ASTRA_GITHUB_REDIRECT_URI=http://127.0.0.1:8000/auth/github/callback
#   ASTRA_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
#   ASTRA_VAULT_KEK_HEX=$(python -c "import secrets; print(secrets.token_hex(32))")
#   ASTRA_GEMINI_API_KEY=<from https://aistudio.google.com/apikey>
#   ASTRA_BASE_URL=http://127.0.0.1:3000
#   ASTRA_FRONTEND_ORIGIN=http://127.0.0.1:3000

just dev-backend                        # http://127.0.0.1:8000
```

When registering the GitHub OAuth app, set the callback URL to `http://127.0.0.1:8000/auth/github/callback`.

### 2. Frontend

```
cd frontend && cp .env.example .env.local && cd ..
just dev-frontend                       # http://127.0.0.1:3000
```

### 3. Verify

```
just test                               # 176 backend tests, ~30s
curl http://127.0.0.1:8000/healthz      # {"ok": true}
```

Open http://127.0.0.1:3000 and click **Sign in with GitHub**. After login, paste a JS-heavy URL on `/runs/new`. Poll the detail page; when status reaches `done`, query the graph at `/runs/{id}/features` or via `POST /runs/{id}/nl` (curl works too — bring your cookie).

### Pro-tier (Anthropic) setup

After signing in, store your Anthropic key in the vault (no UI yet; use curl):

```
curl -X POST http://127.0.0.1:8000/auth/me           # confirm authed; copy cookie
# Use the same cookie:
# curl -X POST http://127.0.0.1:8000/vault/anthropic ...   # vault routes not yet exposed; coming in a follow-up session
```

For now Pro tier requires inserting the key directly via the `KeyVault` Python API in a dev shell. See `backend/vault/envelope.py`.

---

## License

TBD.
