# Session 7: Feature coverage (static ∩ dynamic)

Branch: `feat/feature-coverage`
Goal: Drive the site through a labeled "feature run" with Playwright, capture V8 precise function coverage, and link executed functions back to the static callgraph via `EXECUTED_IN` edges + `Feature` nodes in Kuzu.

## Decisions

- **Coverage source:** V8 `Profiler.takePreciseCoverage` via Playwright CDP. Function-level granularity (`functions[]` with `callCount`).
- **Matching strategy (MVP):** match coverage entries to graph `Function` nodes by **function name + source path** (after sourcemap-aware url resolution: the CDP script URL is the bundle URL; we map it back to a source file through `RunLayout.sourcemap_dir/_manifest.json`). Exact-name match within the same source file. Sourcemap **byte-range** mapping is deferred — function-name match is sufficient to demo dead-code + feature-scoped attack surface against the react-min fixture.
- **Action DSL:** `{type: "goto"|"click"|"fill"|"wait", selector?, value?, ms?}` list. Crude but enough for scripted golden-path runs.
- **Feature identity:** `features.id` = short slug, scoped to (run_id, name) unique. Each `Feature` node in Kuzu mirrors the SQLite row.
- **EXECUTED_IN edges:** `(Function)-[:EXECUTED_IN]->(Feature)`. Idempotent (Kuzu MERGE).

## Schema delta

Append to `backend/db/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS features (
    id           TEXT    PRIMARY KEY,
    run_id       TEXT    NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    name         TEXT    NOT NULL,
    created_at   INTEGER NOT NULL,
    last_run_at  INTEGER,
    last_status  TEXT,                          -- 'pending' | 'recording' | 'done' | 'failed'
    error        TEXT,
    matched_functions INTEGER NOT NULL DEFAULT 0,
    UNIQUE (run_id, name)
);
```

## Layout

```
backend/coverage/
├── __init__.py
├── recorder.py        Playwright CDP recorder (records actions, dumps precise coverage)
├── join.py            join V8 coverage ↔ Kuzu Function nodes via _manifest.json
└── routes.py          POST /runs/{rid}/features, POST .../record, GET .../features

backend/tests/
├── test_coverage_join.py
├── test_coverage_recorder.py   (live Playwright against react-min fixture)
└── test_features_e2e.py
```

## Tasks

1. **[SEQUENTIAL]** Extend schema (`features` table). Main agent.

2. **[PARALLEL after 1]** `recorder.py` — Playwright CDP coverage capture. Subagent.

3. **[PARALLEL after 1]** `join.py` — read coverage JSON + run layout, write Feature node + EXECUTED_IN edges to Kuzu. Subagent.

4. **[SEQUENTIAL after 2+3]** `routes.py` + `service.py` (CRUD on `features`), wire into main.py. E2E test against react-min fixture. Main agent.

5. **[SEQUENTIAL]** Commit + squash-merge.

## Verification

- [ ] E2E test runs a `goto` + `click` action against `tests/fixtures/react-min/dist/`, records precise coverage, and lands at least one `EXECUTED_IN` edge in the run's Kuzu file pointing at a Function from the static analysis.
- [ ] `just test` passes; ~135 total.

## Out of scope

- Sourcemap byte-range → original-line mapping. Defer.
- jsluice-aware coverage. Defer.
- Interactive UI for feature recording (Session 8 frontend).
- Auto-discovered feature runs (link-walk, heuristic). Manual scripts only.
