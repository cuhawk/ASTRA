# Session 6: Callgraph + taint API

Branch: `feat/callgraph-and-taint-api`
Goal: Wire the acquisition pipeline (Session 3) through a static callgraph extractor and into the Kuzu graph DB (Session 2). Expose `POST /runs` so the frontend can kick off an analysis from a URL, and `GET /runs/{id}` to track it.

## Decisions (locked 2026-05-22)

- **Scope reduction vs CLAUDE.md §12 Session 6:** the vendored `<private-upstream-repo>` `js_analyzer` carries a deep kernel/MCP dependency tree (`structlog`, `kernel.modules`, ChromaDB, etc.) that we don't want to pull into ASTRA wholesale. For MVP we ship an ASTRA-native tree-sitter-based callgraph extractor that emits Function nodes + CALLS edges. Interprocedural taint, framework detect, async edges are deferred to a later "ports" session.
- **Worker queue:** also deferred. Use FastAPI `BackgroundTasks` for in-process background execution. RQ on Redis is the right answer for production scale (CLAUDE.md §5); switching the entry point later is a 30-LOC change. Documented as follow-up.
- **AST:** `tree-sitter` + `tree-sitter-typescript` (lightweight, pure Python wheel ships the .so).
- **Run lifecycle:** new `runs` SQLite table tracks `id`, `user_id`, `url`, `status` (`pending|acquiring|analyzing|done|failed`), timestamps, error message. `RunLayout` from Session 2 still owns the filesystem layout.

## Schema delta

Append to `backend/db/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS runs (
    id           TEXT    PRIMARY KEY,             -- short slug; same as RunLayout.run_id
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url          TEXT,                            -- nullable for zip uploads later
    status       TEXT    NOT NULL,                -- 'pending'|'acquiring'|'analyzing'|'done'|'failed'
    error        TEXT,
    created_at   INTEGER NOT NULL,
    started_at   INTEGER,
    finished_at  INTEGER,
    files        INTEGER NOT NULL DEFAULT 0,
    functions    INTEGER NOT NULL DEFAULT 0,
    edges        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_runs_user_status ON runs(user_id, status);
```

## Layout

```
backend/pillars/sast/
└── callgraph_native.py    tree-sitter JS/TS extractor (Function + CALLS)

backend/runs/
├── __init__.py
├── service.py             new_run / get_run / set_status / write_metrics
├── worker.py              async execute_run(user_id, run_id, url, scope, root) — Pipeline + callgraph + Kuzu
└── routes.py              POST /runs, GET /runs/{id}

backend/tests/
├── test_callgraph_native.py
├── test_runs_service.py
└── test_runs_e2e.py       react-min fixture → POST /runs → wait → assert Kuzu has Function nodes
```

## Tasks

1. **[SEQUENTIAL]** Add deps `tree-sitter`, `tree-sitter-typescript`. Append `runs` table. Settings: `runs_root: Path` (default `./runs`).

2. **[PARALLEL after 1]** `callgraph_native.py`. Subagent.

3. **[PARALLEL after 1]** `backend/runs/service.py` + `routes.py` + tests for both. Subagent.

4. **[SEQUENTIAL after 2+3]** `worker.py` glues `acquisition.Pipeline` → `callgraph_native` → `GraphStore` writes → `runs` row updates. E2E test in `test_runs_e2e.py`. Main agent.

5. **[SEQUENTIAL]** Commit + squash-merge.

## Verification

- [ ] `POST /runs {url}` returns 202 + `{run_id, status: "pending"}`.
- [ ] Background task completes; `GET /runs/{id}` eventually returns `{status: "done", files: N, functions: M, edges: K}`.
- [ ] Kuzu DB at `RunLayout.graph_path` contains at least one `Function` node from the react-min fixture's `App.tsx`.
- [ ] `just test` passes — at least 5 callgraph + 3 runs/service + 1 e2e = 9 new tests, ~110 total.
- [ ] No real network in tests (fixture served by stdlib `http.server`).

## Out of scope (= follow-up sessions)

- Real `js_analyzer` port (interprocedural taint, framework detect, async edges).
- Real RQ/Dramatiq queue on Redis (FastAPI BackgroundTasks is the MVP shim).
- jsluice merging, closure expansion.
- Sourcemap-aware coverage join (Session 7).
- Per-run quota deduction (LLM-only quota for now; static analysis is free).
- Cancellation / re-run / pin.
