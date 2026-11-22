# Session 0 — `infra/bootstrap` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize the ASTRA repo with a git baseline, monorepo directory layout, `justfile` task runner stubs, and a `VENDORED.md` provenance file so all future sessions have a stable scaffold to land work on.

**Architecture:** Single git repo, monorepo layout split by pillar under `backend/pillars/`, plus `frontend/`, `infra/`, `tests/`, `runs/`. `runs/` is gitignored (per-user, per-run scratch). All package managers / language toolchains (Python 3.12 via `uv`, Node via Next.js) are deferred to their owning sessions — Session 0 lays only directories, ignores, task runner, and provenance.

**Tech Stack:** git, `just` (task runner), markdown. No language runtimes installed in this session.

**Pre-flight check:**
- Confirm `just` is installed: `command -v just`. If missing: `brew install just`.
- Confirm we are running inside `/path/to/ASTRA`: `pwd`.
- Confirm repo is NOT already a git repo: `git rev-parse --is-inside-work-tree 2>&1` should print "fatal: not a git repository".

**Out of scope (defer to later sessions):**
- Python virtualenv / `pyproject.toml` — Session 1.
- Node / Next.js scaffold — Session 8.
- Dockerfiles — Session 10.
- `main` branch GitHub protection rules — applied once remote exists (end of Session 0 or Session 10).

---

## File Structure

Files this session creates:

```
ASTRA/
├── .gitignore                          # ignores Python, Node, runs/, env, OS cruft
├── VENDORED.md                         # provenance ledger for <private-upstream-repo> vendored code
├── justfile                            # task runner with stub recipes
├── backend/
│   ├── .gitkeep
│   ├── pillars/
│   │   ├── memory/.gitkeep
│   │   ├── sast/.gitkeep
│   │   ├── coverage/.gitkeep
│   │   └── runtime/.gitkeep
│   └── mcp/.gitkeep
├── frontend/.gitkeep
├── infra/.gitkeep
├── tests/.gitkeep
└── runs/                               # NOT committed — .gitignore covers it
```

Files this session leaves alone (already exist):
- `CLAUDE.md` — design contract.
- `README.md` — user-facing intro.
- `memory.md` — session memory; we will add it to `.gitignore` so it does not get committed.
- `docs/superpowers/plans/2026-05-22-infra-bootstrap.md` — this plan; committed.

---

## Task 1: Initialize git repository

**Files:**
- Create: `.git/` (via `git init`)
- Modify: none

- [ ] **Step 1: Initialize repo on `main`**

```bash
cd /path/to/ASTRA
git init -b main
```

Expected output: `Initialized empty Git repository in /path/to/ASTRA/.git/`

- [ ] **Step 2: Verify branch is `main`**

```bash
git symbolic-ref --short HEAD
```

Expected output: `main`

- [ ] **Step 3: Configure repo-local identity (only if global git identity is unset)**

Check first:

```bash
git config --global user.email && git config --global user.name
```

If both print values, skip. If either is empty, set repo-local values:

```bash
git config user.email "you@example.com"
git config user.name "Your Name"
```

- [ ] **Step 4: Do NOT commit yet**

Wait until `.gitignore` is in place (Task 2) so unwanted files never enter history.

---

## Task 2: Write `.gitignore`

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Write `.gitignore`**

Create `/path/to/ASTRA/.gitignore` with this exact content:

```gitignore
# ===== ASTRA-specific =====
# Per-run user data: raw JS, sourcemaps, Kuzu DB, LanceDB, coverage snapshots, advisor transcripts.
runs/
# Session-local memory scratchpad (not source of truth)
memory.md

# ===== Secrets =====
.env
.env.*
!.env.example
*.pem
*.key

# ===== Python =====
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
env/
.eggs/
*.egg-info/
*.egg
dist/
build/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
.tox/

# ===== Node / Next.js =====
node_modules/
.next/
out/
.turbo/
.pnpm-store/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# ===== Embedded DB artifacts =====
*.kuzu
*.kuzu-wal
*.lance
lancedb/
*.sqlite
*.sqlite-journal
*.db
*.db-journal

# ===== Editor / OS =====
.DS_Store
.idea/
.vscode/
*.swp
*.swo
*~

# ===== Logs =====
*.log
logs/
```

- [ ] **Step 2: Verify ignore patterns work**

```bash
mkdir -p runs/test_user/test_run && touch runs/test_user/test_run/foo.kuzu
git status --short
```

Expected: `runs/` does NOT appear in output. Only `.gitignore` (untracked) appears.

- [ ] **Step 3: Clean up test artifact**

```bash
rm -rf runs/
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore for Python, Node, runs/, secrets"
```

Expected: commit succeeds; `git log --oneline` shows one commit.

---

## Task 3: Create monorepo directory layout

**Files:**
- Create: `backend/.gitkeep`
- Create: `backend/pillars/memory/.gitkeep`
- Create: `backend/pillars/sast/.gitkeep`
- Create: `backend/pillars/coverage/.gitkeep`
- Create: `backend/pillars/runtime/.gitkeep`
- Create: `backend/mcp/.gitkeep`
- Create: `frontend/.gitkeep`
- Create: `infra/.gitkeep`
- Create: `tests/.gitkeep`

- [ ] **Step 1: Create directories and `.gitkeep` files**

```bash
cd /path/to/ASTRA
mkdir -p backend/pillars/memory \
         backend/pillars/sast \
         backend/pillars/coverage \
         backend/pillars/runtime \
         backend/mcp \
         frontend \
         infra \
         tests
touch backend/.gitkeep \
      backend/pillars/memory/.gitkeep \
      backend/pillars/sast/.gitkeep \
      backend/pillars/coverage/.gitkeep \
      backend/pillars/runtime/.gitkeep \
      backend/mcp/.gitkeep \
      frontend/.gitkeep \
      infra/.gitkeep \
      tests/.gitkeep
```

- [ ] **Step 2: Verify tree**

```bash
find backend frontend infra tests -type f
```

Expected output (order may differ):

```
backend/.gitkeep
backend/pillars/memory/.gitkeep
backend/pillars/sast/.gitkeep
backend/pillars/coverage/.gitkeep
backend/pillars/runtime/.gitkeep
backend/mcp/.gitkeep
frontend/.gitkeep
infra/.gitkeep
tests/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add backend frontend infra tests
git commit -m "chore: scaffold monorepo layout (backend/pillars, frontend, infra, tests)"
```

---

## Task 4: Write `justfile` with stub recipes

**Files:**
- Create: `justfile`

- [ ] **Step 1: Confirm `just` is installed**

```bash
command -v just || brew install just
just --version
```

Expected: prints a version string (e.g., `just 1.x.x`). If `brew install` runs, re-verify.

- [ ] **Step 2: Write `justfile`**

Create `/path/to/ASTRA/justfile` with this exact content:

```just
# ASTRA task runner. Recipes are stubs in Session 0; each session fills in its targets.

# Default: list available recipes
default:
    @just --list

# Backend FastAPI dev server (wired in Session 4)
dev-backend:
    @echo "[stub] dev-backend — wire FastAPI + uvicorn in Session 4 (auth-and-quota)"

# Frontend Next.js dev server (wired in Session 8)
dev-frontend:
    @echo "[stub] dev-frontend — wire Next.js in Session 8 (frontend-shell)"

# Worker process for analysis jobs (wired in Session 6)
dev-worker:
    @echo "[stub] dev-worker — wire RQ/Dramatiq + Redis in Session 6 (callgraph-and-taint-api)"

# Run all tests
test:
    @echo "[stub] test — wire pytest + vitest aggregator once backend/frontend scaffold lands"

# Deploy to production host (wired in Session 10)
deploy:
    @echo "[stub] deploy — wire Fly.io or Railway pipeline in Session 10 (deploy)"
```

- [ ] **Step 3: Verify recipes list**

```bash
just
```

Expected output:

```
Available recipes:
    default
    dev-backend
    dev-frontend
    dev-worker
    test
    deploy
```

- [ ] **Step 4: Verify a stub runs**

```bash
just dev-backend
```

Expected output:

```
[stub] dev-backend — wire FastAPI + uvicorn in Session 4 (auth-and-quota)
```

- [ ] **Step 5: Commit**

```bash
git add justfile
git commit -m "chore: add justfile with stub recipes for dev/test/deploy"
```

---

## Task 5: Write `VENDORED.md` provenance template

**Files:**
- Create: `VENDORED.md`

- [ ] **Step 1: Write `VENDORED.md`**

Create `/path/to/ASTRA/VENDORED.md` with this exact content:

````markdown
# Vendored Code Provenance

This file tracks every component copied or `git subtree`-imported from an upstream repository. Per `CLAUDE.md` §2 and §6, every vendored file must record its upstream SHA, license, and import date.

## Source repositories

| Short name | Upstream URL                          | License (as of import) |
|------------|---------------------------------------|------------------------|
| `<private-upstream-repo>` | `<private-upstream-repo>` | (record on first import) |

## Vendored components

> Append one row per vendored component. Do not delete rows — historical provenance is the point. When a component is re-vendored at a newer SHA, append a new row rather than editing the old one.

| ASTRA path                        | Upstream path                       | Upstream SHA | Imported on (UTC) | Method      | Notes |
|-----------------------------------|-------------------------------------|--------------|-------------------|-------------|-------|
| _(none yet — Session 1 fills this)_ |                                   |              |                   |             |       |

## Per-file header convention

Every vendored file MUST start with this header block (adjust comment syntax per language):

```
# vendored-from: <private-upstream-repo>
# upstream-path: tlx/modules/<module>/<file>
# upstream-sha:  <full 40-char SHA>
# imported-on:   YYYY-MM-DD
# license:       <SPDX id or "see LICENSE in upstream repo">
# modifications: <"none" or short description; update on every edit>
```

## Import method

- **Preferred:** `git subtree add --prefix=<astra/path> <private-upstream-repo> <sha> --squash`.
- **Fallback (small, isolated files):** copy + header block.
- Either way, the row in the table above is mandatory.

## When to re-vendor

Re-vendor a component when:
1. Upstream fixes a bug we depend on.
2. Upstream gains a feature we want.
3. Our local modifications have drifted far enough that diffing against upstream is painful.

Never silently re-vendor. Always append a new row.
````

- [ ] **Step 2: Verify file**

```bash
head -5 VENDORED.md
```

Expected: prints the title and first paragraph.

- [ ] **Step 3: Commit**

```bash
git add VENDORED.md
git commit -m "docs: add VENDORED.md provenance template"
```

---

## Task 6: Commit the bootstrap plan itself

**Files:**
- Modify: none (commit existing plan file)

- [ ] **Step 1: Stage and commit the plan**

```bash
git add docs/superpowers/plans/2026-05-22-infra-bootstrap.md
git commit -m "docs: add Session 0 bootstrap plan"
```

- [ ] **Step 2: Final history check**

```bash
git log --oneline
```

Expected: five commits, in this order (newest first):

```
<sha> docs: add Session 0 bootstrap plan
<sha> docs: add VENDORED.md provenance template
<sha> chore: add justfile with stub recipes for dev/test/deploy
<sha> chore: scaffold monorepo layout (backend/pillars, frontend, infra, tests)
<sha> chore: add .gitignore for Python, Node, runs/, secrets
```

---

## Verification

Run all checks from the repo root.

- [ ] **V1: Git repo healthy, on `main`, clean working tree**

```bash
git status && git symbolic-ref --short HEAD
```

Expected: `nothing to commit, working tree clean` and `main`.

- [ ] **V2: Directory layout matches spec**

```bash
find backend frontend infra tests -type d | sort
```

Expected:

```
backend
backend/mcp
backend/pillars
backend/pillars/coverage
backend/pillars/memory
backend/pillars/runtime
backend/pillars/sast
frontend
infra
tests
```

- [ ] **V3: `.gitignore` actually ignores `runs/` and `memory.md`**

```bash
mkdir -p runs/u/r && touch runs/u/r/x.kuzu
git status --short
```

Expected: only changes (if any) related to your test — `runs/` and `memory.md` must NOT appear. Clean up: `rm -rf runs/`.

- [ ] **V4: `just` default recipe lists all stubs**

```bash
just
```

Expected: lists `default`, `dev-backend`, `dev-frontend`, `dev-worker`, `test`, `deploy`.

- [ ] **V5: `VENDORED.md` present and non-empty**

```bash
wc -l VENDORED.md
```

Expected: line count > 30.

- [ ] **V6: Commit count**

```bash
git rev-list --count HEAD
```

Expected: `5`.

---

## Out of band (do NOT do in this session)

- Do not create a GitHub remote yet. The user will decide host (GitHub vs other) and visibility (public vs private) before pushing. Remote setup belongs at end of Session 0 or in Session 10.
- Do not install Python, Node, or any dependencies. Each owning session handles its own toolchain.
- Do not vendor any `<private-upstream-repo>` code yet. That is Session 1.

## Next session

`chore/vendor-internal-upstream` (Session 1). Tasks 1–4 are PARALLEL subagent dispatches; only the SHA-recording step is sequential. Use `superpowers:dispatching-parallel-agents`.
