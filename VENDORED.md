# Vendored Code Provenance

This file tracks every component copied or `git subtree`-imported from an upstream repository. Per `CLAUDE.md` §2 and §6, every vendored file must record its upstream SHA, license, and import date.

## Source repositories

| Short name | Upstream URL                          | License (as of import) |
|------------|---------------------------------------|------------------------|
| tlxkull    | https://github.com/cuhawk/tlxkull     | proprietary — no LICENSE in upstream root |

Local working checkout: `~/Documents/TLX` (use as source for re-vendor; verify SHA before copying).

## Vendored components

> Append one row per vendored component. Do not delete rows — historical provenance is the point. When a component is re-vendored at a newer SHA, append a new row rather than editing the old one.

| ASTRA path                        | Upstream path                       | Upstream SHA | Imported on (UTC) | Method      | Notes |
|-----------------------------------|-------------------------------------|--------------|-------------------|-------------|-------|
| backend/pillars/sast              | tlx/modules/js_analyzer             | 83cae232b94e7998ef543c72e8e7302617d438a0 | 2026-05-22 | copy + stamp | full module; node_modules/ gitignored; JSON taxonomies in `taxonomies/` are unstamped (no comment syntax) — provenance for them is implicit via this row |
| backend/pillars/memory            | tlx/modules/rag                     | 83cae232b94e7998ef543c72e8e7302617d438a0 | 2026-05-22 | copy + stamp | swap ChromaDB → LanceDB pending (Session 2) |
| backend/mcp                       | tlx/mcp_server                      | 83cae232b94e7998ef543c72e8e7302617d438a0 | 2026-05-22 | copy + stamp | adapt tool surface for ASTRA in later session |
| backend/prompts                   | tlx/prompts                         | 83cae232b94e7998ef543c72e8e7302617d438a0 | 2026-05-22 | copy + stamp | upstream contains only `base_system.md`; generalize + extend in Session 5/9 |
| backend/pillars/sast/acquisition/sourcemap.py | bin/explode_sourcemap.py | 83cae232b94e7998ef543c72e8e7302617d438a0 | 2026-05-22 | port (rewrite) | converted CLI script to importable API; pydantic v2 `SourcemapResult`; idempotent identical-bytes skip; missing-sourcesContent disambiguated from malformed; manifest schema preserved + extended with `missing_content` |
| backend/pillars/sast/acquisition/harvester.py | .claude/skills/js-harvest/SKILL.md | 83cae232b94e7998ef543c72e8e7302617d438a0 | 2026-05-22 | port | upstream skill drove chrome-devtools MCP from a TUI; ported to a Playwright async Python module with the same enumeration / sourcemap discovery recipe; hidden-map brute-force recon (upstream Step 7) deferred to a later session |
| backend/pillars/sast/acquisition/hidden_map_recon.py | bin/sourcemap_recon.py | 83cae232b94e7998ef543c72e8e7302617d438a0 | 2026-05-23 | port | TLX's hidden-sourcemap brute + Sentry artifact recon; dropped `status.json`/`_lib` deps in favor of a `HiddenMapReconResult` pydantic model; scope passed via constructor like `Harvester`; httpx async client replaces urllib for consistency with the rest of `acquisition/`; brute templates / 429 backoff / per-bundle cap / `is_sourcemap_body` sniff preserved verbatim from upstream; added per-run URL dedupe so bundle-sibling and per-host probes that resolve to the same URL fire once |
| backend/pillars/sast/acquisition/webpack_chunk_enum.py | bin/webpack_chunk_enum.py | 83cae232b94e7998ef543c72e8e7302617d438a0 | 2026-05-23 | port (snippet only) | only the `JS_SNIPPET` is reused verbatim; the CLI scaffold (`--snippet` / `--persist`) and `targets/<name>/runtime/<ts>/` delta-tracking layout are dropped. ASTRA invokes the snippet directly via `page.evaluate` and returns a `WebpackChunkEnumResult`; the harvester wires it in post-`page.goto` and feeds discovered URLs into the existing scope/dedup/fetch path |

## Per-file header convention

Every vendored file MUST start with this header block (adjust comment syntax per language):

```
# vendored-from: https://github.com/cuhawk/tlxkull
# upstream-path: tlx/modules/<module>/<file>
# upstream-sha:  <full 40-char SHA>
# imported-on:   YYYY-MM-DD
# license:       <SPDX id or "see LICENSE in upstream repo">
# modifications: <"none" or short description; update on every edit>
```

## Import method

- **Preferred:** `git subtree add --prefix=<astra/path> <tlxkull-url> <sha> --squash`.
- **Fallback (small, isolated files):** copy + header block.
- Either way, the row in the table above is mandatory.

## When to re-vendor

Re-vendor a component when:
1. Upstream fixes a bug we depend on.
2. Upstream gains a feature we want.
3. Our local modifications have drifted far enough that diffing against upstream is painful.

Never silently re-vendor. Always append a new row.
