#!/usr/bin/env python3
"""vendor_stamp.py — prepend provenance header to vendored files in place.

Usage:
    python3 tools/vendor_stamp.py \
        --target backend/pillars/sast \
        --upstream-path tlx/modules/js_analyzer \
        --sha 83cae232b94e7998ef543c72e8e7302617d438a0 \
        --imported-on 2026-05-22

Idempotent: skips files that already carry a `vendored-from:` marker.
Stamps .py and .md. Skips __pycache__, .pytest_cache, .mypy_cache, .ruff_cache, hidden files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

STAMPED_MARKER = "vendored-from:"
UPSTREAM_URL = "https://github.com/cuhawk/tlxkull"

EXT_COMMENT = {".py": "#", ".md": "<!--", ".js": "//", ".mjs": "//", ".cjs": "//", ".ts": "//"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"}


def make_line_header(rel_path: str, sha: str, imported_on: str, tok: str) -> str:
    return (
        f"{tok} vendored-from: {UPSTREAM_URL}\n"
        f"{tok} upstream-path: {rel_path}\n"
        f"{tok} upstream-sha:  {sha}\n"
        f"{tok} imported-on:   {imported_on}\n"
        f"{tok} license:       proprietary — see upstream repo\n"
        f"{tok} modifications: none\n"
        f"\n"
    )


def make_md_header(rel_path: str, sha: str, imported_on: str) -> str:
    return (
        f"<!--\n"
        f"vendored-from: {UPSTREAM_URL}\n"
        f"upstream-path: {rel_path}\n"
        f"upstream-sha:  {sha}\n"
        f"imported-on:   {imported_on}\n"
        f"license:       proprietary — see upstream repo\n"
        f"modifications: none\n"
        f"-->\n\n"
    )


def stamp_one(path: Path, upstream_rel: str, sha: str, imported_on: str) -> bool:
    ext = path.suffix
    if ext not in EXT_COMMENT:
        return False
    body = path.read_text(encoding="utf-8", errors="replace")
    if STAMPED_MARKER in body[:1024]:
        return False
    if ext == ".md":
        header = make_md_header(upstream_rel, sha, imported_on)
        new_body = header + body
    else:
        tok = EXT_COMMENT[ext]
        header = make_line_header(upstream_rel, sha, imported_on, tok)
        if body.startswith("#!"):
            first_nl = body.find("\n") + 1
            new_body = body[:first_nl] + header + body[first_nl:]
        else:
            new_body = header + body
    path.write_text(new_body, encoding="utf-8")
    return True


def walk_and_stamp(target: Path, upstream_path: str, sha: str, imported_on: str) -> int:
    stamped = 0
    for p in target.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name.startswith("."):
            continue
        rel = p.relative_to(target).as_posix()
        full_upstream_rel = f"{upstream_path}/{rel}"
        if stamp_one(p, full_upstream_rel, sha, imported_on):
            stamped += 1
    return stamped


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
