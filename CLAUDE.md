# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Status:** repository is empty. This file is the design contract. Future sessions treat it as the source of truth until code exists. When unsure about an unbuilt component, ask before writing speculative code.

---

## 1. What ASTRA is

**ASTRA = BloodHound for JS web apps, delivered as a hosted SaaS.**

The product in one paragraph: a user pastes a URL or uploads a `.zip` of JavaScript. ASTRA crawls / unpacks it on the server, reconstructs original sources from sourcemaps, builds a framework-aware callgraph with taint tags (source → sink), captures runtime coverage from a real Chrome session to label every function with which user-facing features actually execute it, and serves the result as an interactive graph the user can query in cypher or natural language. One screen, drop-and-see.

What it is **not**:
- Not a SCA tool (no SBOM, no CVE-to-symbol reachability).
- Not a self-host product (no desktop app, no local install, no offline mode).
- Not a multi-language SAST (JS/TS only at MVP; Python/Go are P2).
- Not an LLM-first analyzer (LLM is bounded advisor, never builds the graph).

---

## 2. Reference workspace

Substantial portions of the analysis core already exist (private) at:

**internal-upstream**

Do **not** re-implement what is already there. Before scoping new work, read:

- `tlx/modules/js_analyzer/` — callgraph + taint + framework detect (vendor as-is)
- `tlx/modules/rag/` — ChromaDB ingest + Gemini `text-embedding-004` (vendor, swap ChromaDB → LanceDB)
- `tlx/mcp_server/` — MCP server scaffold (vendor)
- `tlx/modules/mock_backend/` — replay harness (reuse for tests)
- `bin/caido-mcp.py` — Caido GraphQL wrapper (vendor for post-MVP `astra-mcp` bridge)
- `tlx/prompts/` — advisor cascade prompts (port + generalize)

Vendor by `git subtree` or copy + upstream-SHA header. Record provenance on first commit.

---

## 3. The four pillars

The product is one app. Internally it is organized around four pillars that share a substrate.

### Pillar 1 — Codebase memory engine
Per-run long-term memory layer that an agent can read/write across sessions.

- Stores normalized facts: call edges, taint tags, framework detections, file-level summaries, advisor verdicts, user-marked findings.
- Backed by **Kuzu** (embedded graph DB, Cypher dialect) + **LanceDB** (embedded vector store) + SQLite for metadata. Per-run files, namespaced by user.
- Every write records provenance: skill name, model id, source line range, timestamp.
- Read path = MCP server. Agents never glob files for memory.

### Pillar 2 — LLM-augmented SAST
Static analyzer where the callgraph is ground truth and the LLM is a bounded advisor on a tiny "hot" subset of taint chains.

- Acquisition: Playwright + chrome-devtools fetches every `<script src>`, dynamic `import()`, inline blob, fetch'd JS, and `.map` file.
- Sourcemap reconstruction restores the original source tree.
- AST via **swc** (Rust, with Python bindings) for speed and native TS support.
- Callgraph with framework detection (React, Vue, Angular, Svelte, Next, Nuxt, etc.).
- Async edge resolver: `Promise.then`, `await`, `setTimeout`, `addEventListener`, `postMessage`, RxJS, service workers.
- Closure-expanded taint tags with hop-decayed confidence; jsluice merge.
- Best-first chain extraction; ranks by `(source × sink severity, path length, framework match)`.
- Output is structured JSON per chain (nodes, edges, taint trail, evidence). SARIF export deferred.

### Pillar 3 — Hosted SaaS runtime
The runtime that drives crawl/upload → analyze → query.

Two tiers, same backend, different LLM key:

| Tier  | LLM key source                | Quota                | Notes                                |
|-------|-------------------------------|----------------------|--------------------------------------|
| Free  | ASTRA-owned Gemini key        | 100 queries / user   | Embeddings + Flash for NL→cypher + chain triage |
| Pro   | User-supplied Anthropic key   | Unlimited (user pays)| Sonnet → Opus cascade on hard chains |

Design rules:
- Core analysis (acquisition → AST → callgraph → taint → coverage → graph DB → cypher) **runs with zero LLM calls**. LLM only translates queries and triages chains.
- All compute on ASTRA infra. Web UI is the only entry point.
- Free-tier metering: per-authenticated-user counter, server-side. Global daily Gemini-spend kill-switch.
- Pro tier: user pastes Anthropic key in web settings. Stored encrypted at rest, decrypted per-request, never logged.
- Uploads retained ≤24h then purged. Users can pin a run.
- Per-IP rate limit; 50 MB upload cap.
- Opus fires only when Sonnet returns `uncertain`. Explicit `advise(chain_id, prompt)` call, never implicit fallback.
- Every LLM call logged with cost/tokens/outcome to memory engine.

### Pillar 4 — Feature-level reachability + dead-code analysis
Join the static callgraph against runtime coverage from a real Chrome session.

- Drive site through scripted/manual feature runs (login, checkout, search, settings, admin, etc.) via chrome-devtools `Profiler.startPreciseCoverage` / `takePreciseCoverage`.
- Each run emits a labeled coverage snapshot.
- Join: `Function.live_in[]`, `Function.hit_count`, `(:Function)-[:EXECUTED_IN]->(:Feature)`.

Outputs:
- Per-function liveness label (`dead` | `live_in:[feature_ids]`).
- Pruned taint chains: source → sink chains not exercised by any live feature are downranked.
- Feature-scoped attack surface: e.g. "sinks reachable from URL hash **and** executed in checkout".
- Coverage gaps: callgraph nodes hit by no feature run = dead code OR under-explored flow.

**Explicitly out of scope:** SBOM generation, CVE-to-symbol reachability, dep-vuln SCA.

---

## 4. Product UX

A hosted **drop-it-and-see** web app. Two input modes:

1. **Paste URL** → server-side headless crawler fetches JS → analyze.
2. **Upload `.zip`** of JS files → server unzips → analyze.

Output is one screen: interactive graph (cytoscape.js) on left, code/chain side panel on right, query bar at the bottom, quota counter visible (free tier). No multi-page wizard, no project management UI.

BloodHound is the **feel** to target — drop input, graph pops up, query reachability — not the architecture. There is no client-side database and no on-prem ingestor. The user only sees a webpage.

---

## 5. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser (Next.js + cytoscape.js + shadcn)                           │
│   - graph canvas | code panel | query bar | quota | auth UI          │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ HTTPS / JSON
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                                   │
│   - auth (magic-link or OAuth) + user metadata (SQLite)              │
│   - run orchestrator                                                 │
│   - LLM proxy (Gemini free tier, Anthropic Pro key vault)            │
│   - cypher endpoint (Kuzu) + NL→cypher translator                    │
│   - MCP server surface (read/write graph, advisor)                   │
└────┬──────────────────┬──────────────────┬───────────────────────────┘
     │                  │                  │
     ▼                  ▼                  ▼
┌─────────────┐  ┌────────────────┐  ┌────────────────────────────────┐
│ Worker pool │  │ Per-run stores │  │ Object storage                 │
│ (RQ/Dramatiq│  │  - Kuzu (.kuzu)│  │  - raw JS + sourcemaps         │
│  on Redis)  │  │  - LanceDB     │  │  - coverage snapshots          │
│             │  │  - SQLite      │  │  - advisor transcripts (Pro)   │
│ acquire,    │  │  (per run, per │  │                                │
│ AST,        │  │   user)        │  │  runs/<user_id>/<run_id>/      │
│ callgraph,  │  └────────────────┘  └────────────────────────────────┘
│ taint,      │
│ coverage    │
└─────────────┘
```

Per-run isolation: dedicated Kuzu + LanceDB files per run, namespaced by user. Shared global SQLite for auth/metadata only. No cross-run leakage.

---

## 6. What to vendor vs rebuild

| ASTRA component                | internal-upstream source                                  | Action  |
|--------------------------------|-------------------------------------------------|---------|
| JS callgraph + taint           | `tlx/modules/js_analyzer/`                      | vendor  |
| RAG ingest + per-repo store    | `tlx/modules/rag/`                              | vendor; swap ChromaDB → LanceDB |
| MCP server scaffold            | `tlx/mcp_server/`                               | vendor  |
| Mock backend (replay harness)  | `tlx/modules/mock_backend/`                     | reuse for tests |
| Sourcemap reconstruction       | `js-harvest` + `sourcemap-explode` skills       | port    |
| Advisor cascade prompts        | `tlx/prompts/`                                  | port; generalize whitelist |
| Caido MCP wrapper              | `bin/caido-mcp.py`                              | vendor for post-MVP bridge |

Rebuild from scratch:
- **Kuzu writer.** internal-upstream stores SQLite per target; ASTRA needs an embedded graph DB.
- **Coverage capture + join.** chrome-devtools `Profiler.takePreciseCoverage`, labeled per feature run.
- **Web UI.** internal-upstream is a TUI on Claude Code; ASTRA needs a browser frontend.
- **Auth + multi-tenant isolation + key vault.** internal-upstream is single-operator.
- **LLM proxy.** Free-tier Gemini key never reaches the client.
- **Memory engine write path.** internal-upstream's RAG is read-mostly.

---

## 7. Tech stack (locked)

- **Backend:** Python 3.12 + FastAPI + Pydantic v2 + Uvicorn.
- **Workers:** RQ or Dramatiq on Redis.
- **Embedded graph DB:** Kuzu (Cypher dialect, file-backed).
- **Embedded vector store:** LanceDB.
- **Metadata DB:** SQLite (FastAPI lifespan-managed).
- **AST:** swc (via Python bindings).
- **Crawler:** Playwright + chrome-devtools MCP.
- **Frontend:** Next.js 15 + React 19 + cytoscape.js + shadcn/ui + Tailwind.
- **Auth:** magic-link email (Resend/Postmark) or OAuth (GitHub/Google). Pick one at scaffold time.
- **Deploy:** Docker images on Fly.io or Railway (decide at infra step).
- **LLM:** Gemini Flash + `text-embedding-004` (free tier); Anthropic Sonnet → Opus (Pro tier).

---

## 8. Operating principles

- One folder = one unit of reproducibility. One **run** = `runs/<user_id>/<run_id>/` containing raw JS, sourcemap reconstruction, callgraph snapshot, coverage snapshots per feature, graph DB file, advisor transcripts (Pro only). Retained ≤24h unless pinned.
- Skills are the smallest unit of orchestration. The agent chains them; skills do not chain each other.
- LLM use is rule-bounded, logged, and **opt-in**. Core pipeline runs with zero LLM calls. No silent escalations, no degraded-mode fallbacks.
- Per-run isolation enforced at the filesystem and DB level. No cross-run leakage.
- Never write code for unbuilt components without explicit go-ahead. Ask first.

---

## 9. Workflow tools to use (Claude Code skills / plugins)

This project will lean on the following Claude Code skills and plugins. Future sessions should invoke them by name when the situation matches.

- **`/graphify`** — once the codebase grows past ~30 files, run graphify to maintain a navigable knowledge graph of source + docs. Treat any "where does X live" question as a `/graphify` query.
- **`superpowers:brainstorming`** + **`superpowers:writing-plans`** + **`superpowers:executing-plans`** — for any non-trivial feature or infra change, brainstorm → plan → execute through the superpowers skills rather than ad-hoc.
- **`superpowers:dispatching-parallel-agents`** — **default for any session containing ≥2 independent tasks.** See §10 below.
- **`superpowers:subagent-driven-development`** — when a session's plan has both parallel and sequential tasks, use this skill to coordinate subagent dispatch and merge.
- **`superpowers:using-git-worktrees`** — isolate parallel work streams on separate worktrees. One worktree per subagent when they touch overlapping file regions.
- **`superpowers:test-driven-development`** — every analysis-layer feature gets a failing test first. Graph + taint logic is too easy to get subtly wrong without TDD.
- **`superpowers:verification-before-completion`** — never claim a pipeline stage is done without running it end-to-end on a real bundle.
- **`frontend-design:frontend-design`** — UI work for the graph explorer, code panel, and auth pages goes through this skill. Avoid generic AI-aesthetic shadcn dashboards.
- **`/goal`** — high-level goal tracking plugin (user's setup). Use when scoping a multi-day milestone.
- **`git`** — every shippable change lands on a feature branch, reviewed via PR. See §10 git protocol.

When a task matches a skill above, **invoke the skill** before writing code. Don't reinvent the workflow.

---

## 10. Execution model (sessions, tasks, subagents, git)

### Session = one feature

A **session** is the unit of work for one shippable feature (e.g., "JS acquisition pipeline", "Kuzu writer", "graph viewer page", "auth + magic link", "Gemini LLM proxy"). One session → one git branch → one PR.

Plan each session to contain multiple **tasks**. Classify each task as:

- **PARALLEL** — independent of every other task in the session. Dispatch via subagent.
- **SEQUENTIAL** — depends on a prior task's output. Run in order, main agent.
- **BLOCKING** — depends on user decision or external resource. Pause, ask, resume.

### Subagent dispatch rules

Default to subagents for parallel work. Rules:

1. **Any session plan with ≥2 PARALLEL tasks dispatches them as concurrent subagents** in a single message (multiple Agent tool-use blocks). Do not serialize what can parallelize.
2. **Pick the right subagent type per task:**
   - `Explore` — read-only codebase search, "where does X live" questions.
   - `general-purpose` — multi-step research with no specialized fit.
   - `feature-dev:code-explorer` — deep-dive into an existing module before touching it.
   - `feature-dev:code-architect` — design before implementation when a feature crosses ≥2 layers.
   - `feature-dev:code-reviewer` — pre-PR review against project conventions.
   - `code-simplifier:code-simplifier` — refactor pass after a feature lands.
3. **Subagents touching overlapping files** → spawn each in an isolated git worktree (`superpowers:using-git-worktrees`) to avoid merge conflicts.
4. **Each subagent prompt is self-contained.** Brief like a colleague who hasn't seen the conversation: file paths, line numbers, goal, expected output format, length cap.
5. **After all parallel subagents return**, the main agent merges their outputs (synthesis is never delegated).

### Session plan template

Every session starts with a written plan in this shape (use `superpowers:writing-plans`):

```
# Session: <feature name>
Branch: feat/<kebab-name>
Goal: <one sentence>

## Tasks

1. [PARALLEL] <task>
   - Subagent: <type>
   - Output: <file paths or summary>

2. [PARALLEL] <task>
   - Subagent: <type>
   - Output: ...

3. [SEQUENTIAL, depends on 1,2] <task>
   - Main agent
   - Output: ...

4. [BLOCKING] <user decision>
   - Ask: ...

5. [SEQUENTIAL, depends on 3,4] <task>
   - ...

## Verification

- [ ] tests pass
- [ ] end-to-end smoke on real fixture
- [ ] PR opened
```

### Git protocol

- **One session = one branch.** Name `feat/<kebab>`, `fix/<kebab>`, `chore/<kebab>`, `infra/<kebab>`.
- **No direct commits to `main`.** Ever.
- **Commit early, commit often** within a session — small atomic commits are reviewable.
- **One PR per session.** Title = session goal. Body = session plan + verification checklist.
- **Feature branches use worktrees** when running parallel subagents that touch overlapping files (`git worktree add ../astra-<branch> <branch>`).
- **Rebase, don't merge** when syncing a feature branch with `main`. Keep history linear.
- **Squash on merge to `main`** so each feature lands as one commit.
- **Never force-push to `main`.** Force-push to a feature branch is allowed only before review starts.
- **No `--no-verify` commits.** Pre-commit hooks exist for reasons.

### Example session breakdown

> Session: **"Acquisition pipeline (URL → JS files + sourcemaps)"**
>
> 1. **[PARALLEL]** Vendor `js-harvest` skill from internal-upstream → `backend/pillars/sast/acquisition/harvester.py`. Subagent: `general-purpose`.
> 2. **[PARALLEL]** Vendor `sourcemap-explode` skill → `backend/pillars/sast/acquisition/sourcemap.py`. Subagent: `general-purpose`.
> 3. **[PARALLEL]** Write fixture: minimal React app with sourcemap published → `tests/fixtures/react-min/`. Subagent: `general-purpose`.
> 4. **[SEQUENTIAL, after 1+2+3]** Wire harvester + sourcemap into one async pipeline; test on fixture. Main agent.
> 5. **[SEQUENTIAL]** Open PR `feat/acquisition-pipeline`. Main agent.

---

## 11. `astra-mcp` bridge (post-MVP)

Planned but not MVP: an MCP server exposing ASTRA + Caido as tools to an external Claude Code session. Lets the operator drive ASTRA from the same conversational surface used to investigate.

Tool surface:
- **Read ASTRA:** `astra_query_graph(cypher)`, `astra_get_chain(id)`, `astra_list_features()`, `astra_semantic_search(q)`.
- **Write ASTRA:** `astra_mark_finding(id, verdict, note)`, `astra_request_recrawl(url)`, `astra_tag_node(id, tag)`.
- **Push Caido:** `caido_send_to_replay(request)`, `caido_run_payload(req, payload)`, `caido_export_curl(req_id)`.

Rules:
- All tools typed and schema-validated. No free-form cypher to write transactions.
- Write tools require explicit assent (session token or per-call confirmation).
- Caido instance is user-supplied (URL + API token). Same BYO pattern as Anthropic key.
- Every call logged to memory engine with action, chain_id, result.

Implementation seed: vendor `bin/caido-mcp.py`, slim to needed tools, mount alongside a thin FastAPI client for ASTRA's API.

---

## 12. Roadmap by session

Each session is one feature, one branch, one PR. Tasks within a session are dispatched as parallel subagents wherever possible.

### Session 0 — `infra/bootstrap` (sequential, foundational)

Tasks (all SEQUENTIAL because each depends on prior layout):

1. Init git, `main` branch protected, `.gitignore` (Python + Node + `runs/`).
2. Create monorepo layout: `backend/`, `backend/pillars/{memory,sast,coverage,runtime}/`, `frontend/`, `infra/`, `tests/`, `runs/`.
3. `justfile` with stub targets: `dev-backend`, `dev-frontend`, `dev-worker`, `test`, `deploy`.
4. `VENDORED.md` with upstream internal-upstream SHA template.

### Session 1 — `chore/vendor-internal-upstream` (parallel-heavy)

Tasks:

1. **[PARALLEL]** Vendor `tlx/modules/js_analyzer/` → `backend/pillars/sast/`. Subagent: `general-purpose`.
2. **[PARALLEL]** Vendor `tlx/modules/rag/` → `backend/pillars/memory/`. Subagent: `general-purpose`.
3. **[PARALLEL]** Vendor `tlx/mcp_server/` → `backend/mcp/`. Subagent: `general-purpose`.
4. **[PARALLEL]** Vendor `tlx/prompts/` → `backend/prompts/`. Subagent: `general-purpose`.
5. **[SEQUENTIAL]** Record SHAs + license headers in `VENDORED.md`. Main agent.

### Session 2 — `feat/embedded-stores`

Tasks:

1. **[PARALLEL]** Kuzu writer wrapper + smoke test (node + edge roundtrip). Subagent: `general-purpose`.
2. **[PARALLEL]** Swap RAG's ChromaDB for LanceDB. Subagent: `feature-dev:code-explorer` first to read current ChromaDB use, then implement.
3. **[SEQUENTIAL]** Per-run folder layout helper + tests.

### Session 3 — `feat/acquisition-pipeline`

Tasks:

1. **[PARALLEL]** Vendor `js-harvest` skill → `backend/pillars/sast/acquisition/harvester.py`.
2. **[PARALLEL]** Vendor `sourcemap-explode` → `backend/pillars/sast/acquisition/sourcemap.py`.
3. **[PARALLEL]** Build fixture: minimal React + Vite app with sourcemap → `tests/fixtures/react-min/`.
4. **[SEQUENTIAL]** Wire harvester + sourcemap into one async pipeline; smoke test on fixture.

### Session 4 — `feat/auth-and-quota`

(Auth + per-user metering. **Must land before LLM endpoints.**)

Tasks:

1. **[BLOCKING]** Decide magic-link vs OAuth. Ask user.
2. **[PARALLEL]** SQLite schema (users, sessions, quota_counters, api_keys_encrypted). Subagent: `feature-dev:code-architect`.
3. **[PARALLEL]** Auth routes + middleware. Subagent: `general-purpose`.
4. **[PARALLEL]** Quota counter middleware + Redis-backed daily reset. Subagent: `general-purpose`.
5. **[SEQUENTIAL]** Anthropic-key vault (envelope encryption). Main agent.

### Session 5 — `feat/llm-proxy`

(Gemini for free, Anthropic for Pro. **Must follow Session 4.**)

Tasks:

1. **[PARALLEL]** Gemini client + retry/budget. Subagent: `general-purpose`.
2. **[PARALLEL]** Anthropic client w/ Sonnet → Opus cascade. Subagent: `general-purpose`.
3. **[PARALLEL]** Global daily-spend kill-switch. Subagent: `general-purpose`.
4. **[SEQUENTIAL]** Wire tier routing + per-call logging to memory engine.

### Session 6 — `feat/callgraph-and-taint-api`

Tasks:

1. **[PARALLEL]** Adapt vendored `js_analyzer` to emit Kuzu-compatible nodes/edges.
2. **[PARALLEL]** REST endpoint `POST /runs` → enqueue analysis job.
3. **[PARALLEL]** Worker handler: acquire → AST → callgraph → taint → write Kuzu.
4. **[SEQUENTIAL]** End-to-end test: URL → run → Kuzu file populated.

### Session 7 — `feat/feature-coverage`

Tasks:

1. **[PARALLEL]** chrome-devtools `Profiler.takePreciseCoverage` wrapper.
2. **[PARALLEL]** Feature-run scripting helpers + recording UI.
3. **[SEQUENTIAL]** Static ∩ dynamic join → write `EXECUTED_IN` edges + `live_in[]` labels.

### Session 8 — `feat/frontend-shell` (`frontend-design:frontend-design`)

Tasks:

1. **[BLOCKING]** Visual design pass via `frontend-design` skill. Decide layout, colors, typography.
2. **[PARALLEL]** Next.js app scaffold + auth pages.
3. **[PARALLEL]** Upload + URL-paste page (no graph yet).
4. **[SEQUENTIAL]** Graph canvas (cytoscape.js) + code panel + query bar.

### Session 9 — `feat/cypher-and-nl-query`

Tasks:

1. **[PARALLEL]** Cypher REST endpoint + schema validation.
2. **[PARALLEL]** Canned-query catalog (5 starter playbooks).
3. **[PARALLEL]** NL → Cypher translator (free-tier Gemini Flash).
4. **[SEQUENTIAL]** Pro-tier chain-triage cascade wiring.

### Session 10 — `infra/deploy`

Tasks:

1. **[BLOCKING]** Pick host: Fly.io or Railway.
2. **[PARALLEL]** Dockerfiles (backend, worker, frontend).
3. **[PARALLEL]** Privacy policy + ToS drafts.
4. **[SEQUENTIAL]** Smoke deploy to staging; end-to-end test.
5. **[SEQUENTIAL]** Production deploy.

### Post-MVP sessions (not in initial roadmap)

- `feat/astra-mcp-bridge` — MCP server exposing ASTRA + Caido as Claude Code tools.
- `feat/sarif-export` — only if a real user asks.
- `feat/multi-language` — Python, Go.

---

Do not invent commands, file paths, or test runners that do not yet exist. When in doubt, ask.
