# ported-from: internal-upstream
# upstream-path: bin/explode_sourcemap.py
# upstream-sha:  83cae232b94e7998ef543c72e8e7302617d438a0
# imported-on:   2026-05-22
# license:       proprietary — see upstream repo
# modifications: rewrote as importable API; added pydantic v2 result model;
#                disambiguated missing sourcesContent (logged in missing_content,
#                map still consumes its .js sibling so it stays out of _nomap);
#                idempotent identical-bytes skip; manifest schema unchanged.
"""Reconstruct an original JS source tree from `.js.map` files.

Importable API; CLI surface is intentionally absent (callers wire it into
the acquisition pipeline). Pure stdlib + pydantic.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

WEBPACK_PREFIXES: tuple[str, ...] = (
    "webpack:///",
    "webpack://",
    "webpack-internal:///",
)

_LEADING_DOTSLASH = re.compile(r"^(?:\.+/)+")


class SourcemapResult(BaseModel):
    original_files: int = 0
    nomap_files: int = 0
    conflicts: int = 0
    malformed: list[str] = Field(default_factory=list)
    missing_content: list[str] = Field(default_factory=list)


def _normalize(src_path: str) -> Path:
    p = src_path
    for prefix in WEBPACK_PREFIXES:
        if p.startswith(prefix):
            p = p[len(prefix):]
            break
    p = p.split("?", 1)[0]
    p = _LEADING_DOTSLASH.sub("", p)
    p = p.lstrip("/")
    return Path(p)


def _read_bytes_or_none(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def explode_sourcemaps(raw_dir: Path, sources_dir: Path) -> SourcemapResult:
    """Walk raw_dir for *.js.map, reconstruct source tree into sources_dir.

    Idempotent — running twice with no input changes writes nothing new.
    Writes ``sources_dir/_manifest.json`` describing each map's emitted sources.
    `.js` files lacking a sibling `.js.map` are copied verbatim into
    ``sources_dir/_nomap/<relative-path>.js``.
    """
    sources_dir.mkdir(parents=True, exist_ok=True)
    nomap_dir = sources_dir / "_nomap"

    result = SourcemapResult()
    conflicts = Counter[str]()
    emitted_originals: set[Path] = set()
    emitted_nomap: set[Path] = set()
    manifest_maps: list[dict[str, Any]] = []
    mapped_js: set[Path] = set()

    for mp in sorted(raw_dir.rglob("*.js.map")):
        sibling_js = mp.with_suffix("")  # strips ".map" → "...js"
        if sibling_js.suffix == ".js":
            mapped_js.add(sibling_js.resolve())

        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            result.malformed.append(str(mp))
            continue

        sources = data.get("sources") or []
        contents = data.get("sourcesContent")

        if not contents:
            result.missing_content.append(str(mp))
            manifest_maps.append({"path": str(mp), "sources_emitted": []})
            continue

        if len(contents) != len(sources):
            result.malformed.append(str(mp))
            continue

        emitted: list[str] = []
        for src_path, content in zip(sources, contents, strict=False):
            if content is None:
                continue
            normalized = _normalize(src_path)
            if not normalized.parts:
                continue
            dest = sources_dir / normalized
            try:
                dest.relative_to(sources_dir)
            except ValueError:
                continue

            new_bytes = content.encode("utf-8")
            if dest.exists():
                existing_bytes = _read_bytes_or_none(dest)
                if existing_bytes == new_bytes:
                    emitted_originals.add(dest.resolve())
                    emitted.append(str(normalized))
                    continue
                if existing_bytes is not None and len(new_bytes) > len(existing_bytes):
                    dest.write_bytes(new_bytes)
                conflicts[str(normalized)] += 1
                emitted_originals.add(dest.resolve())
                emitted.append(str(normalized))
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(new_bytes)
            emitted_originals.add(dest.resolve())
            emitted.append(str(normalized))

        manifest_maps.append({"path": str(mp), "sources_emitted": emitted})

    for js in sorted(raw_dir.rglob("*.js")):
        if js.resolve() in mapped_js:
            continue
        if js.with_suffix(".js.map").exists():
            continue
        rel = js.relative_to(raw_dir)
        dest = nomap_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        src_bytes = js.read_bytes()
        if not dest.exists() or _read_bytes_or_none(dest) != src_bytes:
            dest.write_bytes(src_bytes)
        emitted_nomap.add(dest.resolve())

    result.original_files = len(emitted_originals)
    result.nomap_files = len(emitted_nomap)
    result.conflicts = sum(conflicts.values())

    manifest = {
        "maps": manifest_maps,
        "conflicts": [{"path": k, "count": v} for k, v in conflicts.items()],
        "malformed": [{"path": p} for p in result.malformed],
        "missing_content": [{"path": p} for p in result.missing_content],
    }
    (sources_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result
