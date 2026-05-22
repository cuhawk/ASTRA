# Session 3: Acquisition pipeline (URL → JS files + sourcemaps)

Branch: `feat/acquisition-pipeline`
Goal: Given a URL + scope, fetch every reachable JS asset (script tags, dynamic imports, webpack chunks) plus its `.js.map` siblings, then reconstruct the original source tree from `sourcesContent`. Output lands in a `RunLayout`'s `raw_dir` + `sourcemap_dir`.

## Decisions (locked 2026-05-22)

- **Crawler runtime:** Playwright headless Chromium. Matches CLAUDE.md §3 Pillar 2 spec. Browser install one-shot via `playwright install chromium`. ~300MB price worth paying — Session 7 (coverage) needs it anyway.
- **Sourcemap recon (hidden-map brute force):** **deferred**. Port only `bin/explode_sourcemap.py` (114 LOC, stdlib). Defer `bin/sourcemap_recon.py` (Sentry artifact API + per-host attempt cap) to a later session.
- **Source of upstream code:** `~/Documents/TLX` at SHA `83cae232b94e7998ef543c72e8e7302617d438a0` (already-verified vendor source per memory).

## Layout

```
backend/pillars/sast/acquisition/
├── __init__.py        — Pipeline(scope).acquire(url, run_layout) → AcquisitionResult
├── harvester.py       — Playwright-backed JS + sourcemap crawler
├── sourcemap.py       — ported sourcemap exploder
└── tests/
    ├── test_harvester.py
    ├── test_sourcemap.py
    └── test_pipeline.py     (integration on react-min fixture)
```

```
tests/fixtures/react-min/
├── dist/              — pre-built Vite output, checked in
│   ├── index.html
│   └── assets/
│       ├── index-*.js
│       └── index-*.js.map
└── README.md          — how it was built (for re-gen if needed)
```

## Tasks

1. **[SEQUENTIAL]** Add `playwright>=1.48` to `pyproject.toml`. Install via `uv pip install -e ".[dev]"`. Run `.venv/bin/playwright install chromium` (one-shot). Main agent.

2. **[PARALLEL after 1]** Build fixture under `tests/fixtures/react-min/`. Minimal Vite + React 19 + TS app. `vite build` with `sourcemap: true`. Commit the `dist/` output (no npm at test time). Subagent: `general-purpose`.

3. **[PARALLEL after 1]** Port `bin/explode_sourcemap.py` → `backend/pillars/sast/acquisition/sourcemap.py`. Pure stdlib. API: `explode_sourcemaps(raw_dir: Path, sources_dir: Path) -> SourcemapResult` (pydantic model with `original_files`, `nomap_files`, `conflicts`, `malformed`). Subagent: `general-purpose`.

4. **[SEQUENTIAL after 1+2]** Build harvester. API: `Harvester(scope: list[str], depth: int = 2).acquire(url: str, raw_dir: Path) -> HarvestResult`. Async. Walks pages with Playwright, enumerates `<script src>` + dynamic `import()` + webpack chunks (via `Page.on("request")` for completeness), fetches every in-scope JS asset, probes for `.js.map` (sourceMappingURL pragma + `X-SourceMap` header + `<url>.map` fallback). Saves under `raw_dir/<host>/<path>.js[.map]`. Out-of-scope and missing maps logged. Subagent: `general-purpose`.

5. **[SEQUENTIAL after 3+4]** Wire pipeline in `backend/pillars/sast/acquisition/__init__.py`: `Pipeline(scope).acquire(url, run_layout) -> AcquisitionResult`. Internally: serve fixture's `dist/` via stdlib `http.server` on a free port → harvest into `run_layout.raw_dir` → explode into `run_layout.sourcemap_dir`. Smoke test asserts the original `.tsx` source (from `sourcesContent`) is reconstructed.

6. **[SEQUENTIAL]** Commit. Squash-merge to `main`.

## Verification

- [ ] `playwright install chromium` succeeded (verified by `.venv/bin/playwright --version`)
- [ ] `just test` passes — at least 1 harvester test + 4 sourcemap tests + 1 pipeline integration test
- [ ] Pipeline integration test runs end-to-end on `tests/fixtures/react-min/` via a transient `http.server`
- [ ] Out-of-scope hosts are logged + skipped, not fetched
- [ ] No edits to vendored sast files (`backend/pillars/sast/audit_engine.py` etc.)

## Out of scope

- Hidden-map brute-force recon (tlxkull `bin/sourcemap_recon.py`) — later session.
- Sentry artifact API enumeration — never on by default.
- Caido-aware auth-walled crawling — Session 8 / post-MVP.
- Persistent cookie / login flow — caller's job.
- Sourcemap fetched-by-URL recovery when `sourcesContent` is absent (we deliberately don't follow CDN URLs to avoid scope leakage).
