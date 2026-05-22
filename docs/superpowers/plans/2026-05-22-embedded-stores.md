# Session 2: Embedded stores

Branch: `feat/embedded-stores`
Goal: Stand up the per-run substrate — Kuzu (graph) + LanceDB (vectors) + per-run folder layout — so later sessions have a place to write callgraphs, embeddings, and run artifacts.

## Decisions (locked 2026-05-22)

- **LanceDB swap strategy:** new ASTRA-native `backend/pillars/memory/vectors.py`. Leave vendored `module.py` / `tools.py` untouched as reference. No kernel/Tool/MCP coupling. Re-wire to ASTRA MCP in Session 9.
- **Kuzu writer location:** `backend/pillars/memory/graph.py`. Memory pillar owns all three stores (Kuzu + LanceDB + SQLite) per CLAUDE.md §1.
- **Per-run layout:** `runs/<user_id>/<run_id>/` containing `graph.kuzu/`, `vectors.lance/`, `meta.sqlite`, `raw/`, `sourcemap/`, `coverage/`, `advisor/` subdirs. Helper lives in `backend/pillars/memory/runs.py`.

## Tasks

1. **[SEQUENTIAL]** Scaffold `pyproject.toml` (root) with deps: `kuzu`, `lancedb`, `pydantic>=2`, `pytest`, `pytest-asyncio`, `anyio`. Main agent.
   - Output: `pyproject.toml`, `.python-version` (3.12).

2. **[PARALLEL after 1]** `backend/pillars/memory/graph.py` — Kuzu writer wrapper. Subagent: `general-purpose`.
   - API: `GraphStore(path: Path)` with `add_node(label, props)`, `add_edge(from_id, to_id, rel_type, props)`, `query(cypher)`, `close()`.
   - Idempotent node insert (keyed by `id` prop).
   - Test: roundtrip — write 3 nodes + 2 edges, query them back, assert shape.

3. **[PARALLEL after 1]** `backend/pillars/memory/vectors.py` — LanceDB-backed RAG. Subagent: `general-purpose`.
   - API: `VectorStore(path: Path, embed_fn: Callable[[list[str]], list[list[float]]])` with `upsert(collection, ids, docs, metas)`, `query(collection, query_text, top_k)`, `list_collections()`.
   - No kernel coupling. `embed_fn` is injected — defaults to a deterministic dummy embedder in tests.
   - Test: upsert 5 docs, query, top-1 returns expected doc.

4. **[PARALLEL after 1]** `backend/pillars/memory/runs.py` — per-run folder layout helper. Subagent: `general-purpose`.
   - API: `RunLayout(root: Path, user_id: str, run_id: str)` with `create()`, `graph_path`, `vectors_path`, `meta_db_path`, `raw_dir`, `sourcemap_dir`, `coverage_dir`, `advisor_dir`, `purge()`.
   - `create()` makes the dir tree. `purge()` deletes the whole `<run_id>/`.
   - Test: create layout, assert all 4 subdirs + 3 file-targets exist; purge, assert gone.

5. **[SEQUENTIAL after 2+3+4]** Wire all three into one smoke test in `backend/pillars/memory/tests/test_session2_integration.py`. Main agent.
   - Create RunLayout → instantiate GraphStore at `graph_path` → instantiate VectorStore at `vectors_path` → write 1 node + 1 doc → readback both → purge.

6. **[SEQUENTIAL]** Wire `just test` to run pytest. Commit. Squash-merge to `main`. Main agent.

## Verification

- [ ] `pyproject.toml` installs cleanly (`uv sync` or `pip install -e .`)
- [ ] `pytest backend/pillars/memory/tests/ -v` passes (graph, vectors, runs, integration)
- [ ] `just test` invokes pytest and exits 0
- [ ] All new files (non-vendored) have no provenance header (they're ours)
- [ ] No edits to vendored `module.py` / `tools.py` / `tests/test_docs_tools.py`
- [ ] Branch squash-merged to `main`, branch deleted

## Out of scope

- SQLite metadata schema (Session 4 owns this — auth/quota tables).
- Embedder service wiring (Session 5 — LLM proxy + Gemini `text-embedding-004`).
- Multi-tenant isolation enforcement at the FS level (Session 4).
- Any MCP tool re-exposure of these stores (Session 9).
