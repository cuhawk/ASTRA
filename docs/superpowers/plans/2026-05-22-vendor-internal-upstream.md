# Session 1 — `chore/vendor-internal-upstream` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Replace `<private-upstream-repo>` and `<pinned-sha>` with the authorized upstream URL and commit before running these commands.

**Goal:** Vendor four `<private-upstream-repo>` modules (`tlx/modules/js_analyzer/`, `tlx/modules/rag/`, `tlx/mcp_server/`, `tlx/prompts/`) into the ASTRA tree, with per-file provenance headers, and record SHAs in `VENDORED.md`.

**Architecture:** Shallow-clone upstream `<private-upstream-repo>` once into a scratch dir at a pinned SHA. Copy (do not `git subtree`) each module into its ASTRA target. Prepend a provenance header to every vendored source file via a single deterministic stamper script. Commit one module per commit on a feature branch. Update `VENDORED.md` table in a final commit.

**Tech Stack:** git, Python 3 (system, for stamper script — no project deps needed), shell.

**Pre-flight:**
- `git ls-remote '<private-upstream-repo>' HEAD` returns SHA `<pinned-sha>` (pinned in this plan).
- Upstream has no `LICENSE` file at root → record as `proprietary — see upstream repo` in `VENDORED.md`.
- Module paths confirmed: `tlx/modules/js_analyzer`, `tlx/modules/rag`, `tlx/mcp_server`, `tlx/prompts`.

**Why copy, not `git subtree`:**
- `git subtree add` mutates HEAD per call; running four in parallel collides on the index.
- We retain full upstream provenance via header + `VENDORED.md` table without dragging upstream history into ours.
- Re-vendor protocol = re-run stamper at a new SHA + append a new `VENDORED.md` row.

---

## File Structure

Created/modified by this session:

```
ASTRA/
├── tools/
│   └── vendor_stamp.py                              # header stamper script
├── backend/
│   ├── pillars/
│   │   ├── sast/                                    # ← tlx/modules/js_analyzer/
│   │   └── memory/                                  # ← tlx/modules/rag/
│   ├── mcp/                                         # ← tlx/mcp_server/
│   └── prompts/                                     # ← tlx/prompts/
├── VENDORED.md                                      # table updated with 4 rows
└── docs/superpowers/plans/2026-05-22-vendor-internal-upstream.md
```

Existing `.gitkeep` files inside `backend/pillars/{sast,memory}/` and `backend/mcp/` are removed when each dir is populated (real content makes them redundant).

Pinned upstream SHA constant (used in every commit, header, VENDORED.md row):
```
<pinned-sha>
```

---

## Task 1: Create feature branch

**Files:** none (branch only)

- [ ] **Step 1: Branch from `main`**

```bash
cd /path/to/ASTRA
git checkout -b chore/vendor-internal-upstream
git symbolic-ref --short HEAD
```

Expected: `chore/vendor-internal-upstream`.

---

## Task 2: Clone `<private-upstream-repo>` to scratch at pinned SHA

**Files:** none in repo; scratch lives at `/tmp/internal-upstream-vendor/`

- [ ] **Step 1: Clean any prior scratch + clone at pinned SHA**

```bash
rm -rf /tmp/internal-upstream-vendor
git clone --depth 1 '<private-upstream-repo>' /tmp/internal-upstream-vendor
cd /tmp/internal-upstream-vendor
git fetch --depth 1 origin '<pinned-sha>'
git checkout '<pinned-sha>'
git rev-parse HEAD
```

Expected last line: `<pinned-sha>`.

- [ ] **Step 2: Confirm module paths exist**

```bash
ls -d /tmp/internal-upstream-vendor/tlx/modules/js_analyzer \
      /tmp/internal-upstream-vendor/tlx/modules/rag \
      /tmp/internal-upstream-vendor/tlx/mcp_server \
      /tmp/internal-upstream-vendor/tlx/prompts
```

Expected: all four paths print, none error.

---

## Task 3: Write `tools/vendor_stamp.py`

**Files:**
- Create: `tools/vendor_stamp.py`

- [ ] **Step 1: Write stamper script**

```python
#!/usr/bin/env python3
"""
vendor_stamp.py — prepend provenance header to vendored files in place.

Usage:
    python3 tools/vendor_stamp.py \\
        --target backend/pillars/sast \\
        --upstream-path tlx/modules/js_analyzer \\
        --sha '<pinned-sha>' \\
        --imported-on 2026-05-22

Idempotent: skips files that already carry a `vendored-from:` marker.
Only stamps these extensions: .py, .md
Skips: __pycache__, .pyc, hidden dirs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

STAMPED_MARKER = "vendored-from:"
UPSTREAM_URL = "<private-upstream-repo>"

EXT_COMMENT = {
    ".py": "#",
    ".md": "<!--",
}
EXT_CLOSE = {
    ".py": "",
    ".md": "-->",
}

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def make_header(rel_path: str, sha: str, imported_on: str, ext: str) -> str:
    open_tok = EXT_COMMENT[ext]
    close_tok = EXT_CLOSE[ext]
    if ext == ".py":
        lines = [
            f"{open_tok} vendored-from: {UPSTREAM_URL}",
            f"{open_tok} upstream-path: {rel_path}",
            f"{open_tok} upstream-sha:  {sha}",
            f"{open_tok} imported-on:   {imported_on}",
            f"{open_tok} license:       proprietary — see upstream repo",
            f"{open_tok} modifications: none",
            "",
        ]
        return "\n".join(lines)
    # Markdown: single HTML comment block
    return (
        f"{open_tok}\n"
        f"vendored-from: {UPSTREAM_URL}\n"
        f"upstream-path: {rel_path}\n"
        f"upstream-sha:  {sha}\n"
        f"imported-on:   {imported_on}\n"
        f"license:       proprietary — see upstream repo\n"
        f"modifications: none\n"
        f"{close_tok}\n\n"
    )


def stamp_file(path: Path, upstream_root: str, sha: str, imported_on: str) -> bool:
    ext = path.suffix
    if ext not in EXT_COMMENT:
        return False
    body = path.read_text(encoding="utf-8", errors="replace")
    if STAMPED_MARKER in body[:1024]:
        return False
    rel = f"{upstream_root}/{path.name}"
    # If file is nested, build the full upstream rel path
    # path is already under the target dir; we reconstruct based on its position
    header = make_header(rel, sha, imported_on, ext)
    # Preserve leading shebang for .py
    if ext == ".py" and body.startswith("#!"):
        first_nl = body.find("\n") + 1
        new_body = body[:first_nl] + header + body[first_nl:]
    else:
        new_body = header + body
    path.write_text(new_body, encoding="utf-8")
    return True


def walk_and_stamp(target: Path, upstream_path: str, sha: str, imported_on: str) -> int:
    stamped = 0
    for p in target.rglob("*"):
        if p.is_dir() and p.name in SKIP_DIRS:
            # rglob will still descend; we filter on file paths below
            continue
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name.startswith("."):
            continue
        # Build upstream rel path: upstream_path + relative-to-target
        rel = p.relative_to(target).as_posix()
        full_upstream_rel = f"{upstream_path}/{rel}"
        if stamp_one(p, full_upstream_rel, sha, imported_on):
            stamped += 1
    return stamped


def stamp_one(path: Path, upstream_rel: str, sha: str, imported_on: str) -> bool:
    ext = path.suffix
    if ext not in EXT_COMMENT:
        return False
    body = path.read_text(encoding="utf-8", errors="replace")
    if STAMPED_MARKER in body[:1024]:
        return False
    header = make_header(upstream_rel, sha, imported_on, ext)
    if ext == ".py" and body.startswith("#!"):
        first_nl = body.find("\n") + 1
        new_body = body[:first_nl] + header + body[first_nl:]
    else:
        new_body = header + body
    path.write_text(new_body, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="ASTRA dir to stamp (already populated)")
    ap.add_argument("--upstream-path", required=True, help="Upstream dir, e.g. tlx/modules/js_analyzer")
    ap.add_argument("--sha", required=True, help="Upstream commit SHA")
    ap.add_argument("--imported-on", required=True, help="YYYY-MM-DD")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"ERROR: target dir not found: {target}", file=sys.stderr)
        return 2

    n = walk_and_stamp(target, args.upstream_path, args.sha, args.imported_on)
    print(f"stamped {n} files under {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Make executable + smoke test on a temp file**

```bash
mkdir -p tools && chmod +x tools/vendor_stamp.py
mkdir -p /tmp/stamp-smoke && echo "print('hi')" > /tmp/stamp-smoke/x.py
python3 tools/vendor_stamp.py \
  --target /tmp/stamp-smoke \
  --upstream-path tlx/dummy \
  --sha '<pinned-sha>' \
  --imported-on 2026-05-22
head -8 /tmp/stamp-smoke/x.py
rm -rf /tmp/stamp-smoke
```

Expected: prints `stamped 1 files under /tmp/stamp-smoke`, then header lines containing `vendored-from:`, `upstream-sha:`, etc., then `print('hi')`.

- [ ] **Step 3: Commit stamper**

```bash
git add tools/vendor_stamp.py
git commit -m "chore(tools): add vendor_stamp.py provenance header injector"
```

---

## Task 4 [PARALLEL via subagents]: Vendor four modules into target dirs

Dispatch four `general-purpose` subagents **in one message** (multiple Agent tool-use blocks). Each:
1. Copies its assigned module from `/tmp/internal-upstream-vendor/<src>` to its ASTRA target.
2. Removes the placeholder `.gitkeep` (if present) inside the target.
3. Runs `tools/vendor_stamp.py` on the target.
4. Reports `stamped N files` count back.

**No git operations from subagents.** Main agent does all commits.

### Subagent A — js_analyzer → backend/pillars/sast

Prompt skeleton:
```
Vendor a `<private-upstream-repo>` module into the ASTRA tree.

Source: /tmp/internal-upstream-vendor/tlx/modules/js_analyzer/
Target: /path/to/ASTRA/backend/pillars/sast/

Steps:
1. rm -f /path/to/ASTRA/backend/pillars/sast/.gitkeep
2. cp -R /tmp/internal-upstream-vendor/tlx/modules/js_analyzer/. /path/to/ASTRA/backend/pillars/sast/
3. find target — DO NOT copy __pycache__, .pyc files (rm -rf any that appear)
4. cd /path/to/ASTRA && python3 tools/vendor_stamp.py \
     --target backend/pillars/sast \
     --upstream-path tlx/modules/js_analyzer \
     --sha '<pinned-sha>' \
     --imported-on 2026-05-22
5. Report: file count in target, stamped count, any errors.

DO NOT run any git commands. DO NOT touch any files outside backend/pillars/sast/.
Report in under 100 words.
```

### Subagent B — rag → backend/pillars/memory

Same prompt with substitutions:
- Source: `/tmp/internal-upstream-vendor/tlx/modules/rag/`
- Target: `/path/to/ASTRA/backend/pillars/memory/`
- `--upstream-path tlx/modules/rag`

### Subagent C — mcp_server → backend/mcp

Same prompt:
- Source: `/tmp/internal-upstream-vendor/tlx/mcp_server/`
- Target: `/path/to/ASTRA/backend/mcp/`
- `--upstream-path tlx/mcp_server`

### Subagent D — prompts → backend/prompts

Same prompt:
- Source: `/tmp/internal-upstream-vendor/tlx/prompts/`
- Target: `/path/to/ASTRA/backend/prompts/`
- `--upstream-path tlx/prompts`
- Note: `backend/prompts/` does not pre-exist; subagent creates it. No `.gitkeep` to remove.

- [ ] **Step 1: Dispatch all four subagents in one message**

- [ ] **Step 2: Verify each subagent reported `stamped N files` with no errors**

- [ ] **Step 3: Spot-check one file from each pillar for a stamped header**

```bash
for d in backend/pillars/sast backend/pillars/memory backend/mcp backend/prompts; do
  echo "=== $d ==="
  f=$(find "$d" -type f \( -name "*.py" -o -name "*.md" \) | head -1)
  head -8 "$f"
  echo
done
```

Expected: each file's first lines contain `vendored-from:`, `upstream-sha: <pinned-sha>`, `imported-on: 2026-05-22`.

---

## Task 5: Commit one pillar at a time

Four atomic commits, in this order. Each commit references the same upstream SHA in its message.

- [ ] **Step 1: Commit sast**

```bash
git add backend/pillars/sast
git commit -m "vendor(sast): import <private-upstream-repo> tlx/modules/js_analyzer @ <pinned-sha>

Source: <private-upstream-repo>
Upstream SHA: <pinned-sha>
Imported: 2026-05-22"
```

- [ ] **Step 2: Commit memory**

```bash
git add backend/pillars/memory
git commit -m "vendor(memory): import <private-upstream-repo> tlx/modules/rag @ <pinned-sha>

Source: <private-upstream-repo>
Upstream SHA: <pinned-sha>
Imported: 2026-05-22"
```

- [ ] **Step 3: Commit mcp**

```bash
git add backend/mcp
git commit -m "vendor(mcp): import <private-upstream-repo> tlx/mcp_server @ <pinned-sha>

Source: <private-upstream-repo>
Upstream SHA: <pinned-sha>
Imported: 2026-05-22"
```

- [ ] **Step 4: Commit prompts**

```bash
git add backend/prompts
git commit -m "vendor(prompts): import <private-upstream-repo> tlx/prompts @ <pinned-sha>

Source: <private-upstream-repo>
Upstream SHA: <pinned-sha>
Imported: 2026-05-22"
```

---

## Task 6: Update `VENDORED.md` table + commit

- [ ] **Step 1: Replace the placeholder table row with four real rows**

Edit `VENDORED.md`. Replace this row:

```
| _(none yet — Session 1 fills this)_ |                                   |              |                   |             |       |
```

With:

```
| backend/pillars/sast              | tlx/modules/js_analyzer             | <pinned-sha> | 2026-05-22        | copy + stamp | full module |
| backend/pillars/memory            | tlx/modules/rag                     | <pinned-sha> | 2026-05-22        | copy + stamp | swap ChromaDB → LanceDB pending (Session 2) |
| backend/mcp                       | tlx/mcp_server                      | <pinned-sha> | 2026-05-22        | copy + stamp | full module |
| backend/prompts                   | tlx/prompts                         | <pinned-sha> | 2026-05-22        | copy + stamp | generalize allowlist pending |
```

Also update the **Source repositories** table — change `(record on first import)` to `proprietary — no LICENSE in upstream root`.

- [ ] **Step 2: Commit**

```bash
git add VENDORED.md
git commit -m "docs(vendored): record <private-upstream-repo> provenance for 4 modules @ <pinned-sha>"
```

---

## Task 7: Commit the plan itself + cleanup

- [ ] **Step 1: Commit this plan**

```bash
git add docs/superpowers/plans/2026-05-22-vendor-internal-upstream.md
git commit -m "docs: add Session 1 vendor-<private-upstream-repo> plan"
```

- [ ] **Step 2: Remove scratch clone**

```bash
rm -rf /tmp/internal-upstream-vendor
```

---

## Verification

- [ ] **V1: On feature branch, clean tree**

```bash
git status && git symbolic-ref --short HEAD
```

Expected: `nothing to commit, working tree clean` and `chore/vendor-internal-upstream`.

- [ ] **V2: Four pillars populated, no leftover `.gitkeep`**

```bash
for d in backend/pillars/sast backend/pillars/memory backend/mcp backend/prompts; do
  echo "=== $d ==="
  find "$d" -maxdepth 1 -type f | head -10
  test ! -e "$d/.gitkeep" && echo "OK: no .gitkeep" || echo "FAIL: .gitkeep still present"
done
```

Expected: each dir has real files, each prints `OK: no .gitkeep`.

- [ ] **V3: Every .py / .md file in vendored dirs carries a `vendored-from:` header**

```bash
missing=0
for f in $(find backend/pillars/sast backend/pillars/memory backend/mcp backend/prompts -type f \( -name "*.py" -o -name "*.md" \)); do
  if ! head -8 "$f" | grep -q "vendored-from:"; then
    echo "MISSING: $f"
    missing=$((missing+1))
  fi
done
echo "missing=$missing"
```

Expected: `missing=0`.

- [ ] **V4: `VENDORED.md` records 4 rows w/ correct SHA**

```bash
grep -c "<pinned-sha>" VENDORED.md
```

Expected: `4` (or more if also in header convention example).

- [ ] **V5: Commit count on branch since main**

```bash
git rev-list --count main..HEAD
```

Expected: `7` (stamper + 4 vendor commits + VENDORED.md update + plan).

- [ ] **V6: No `__pycache__` slipped in**

```bash
find backend -name "__pycache__" -type d | wc -l
```

Expected: `0`.

---

## Out of band (defer to later sessions)

- Adapt vendored modules to ASTRA conventions (Session 6 for sast, Session 2 for memory ChromaDB→LanceDB swap, Session 5/9 for prompts generalize).
- Branch protection / PR review — no remote yet.
- Vendor `bin/caido-mcp.py` — post-MVP, Session `astra-mcp-bridge`.
- Vendor `tlx/modules/mock_backend/` — only when tests need it.

## Next session

Session 2 — `feat/embedded-stores` (Kuzu writer + LanceDB swap + per-run folder helper).
