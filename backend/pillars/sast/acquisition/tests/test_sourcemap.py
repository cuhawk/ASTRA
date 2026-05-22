from __future__ import annotations

import json
from pathlib import Path

from backend.pillars.sast.acquisition.sourcemap import (
    SourcemapResult,
    explode_sourcemaps,
)

APP_TSX_CONTENT = "export const App = () => <div>hi</div>;\n"
UTIL_TS_CONTENT = "export const sum = (a: number, b: number) => a + b;\n"


def _write_map(
    path: Path,
    sources: list[str],
    contents: list[str | None] | None,
    *,
    file: str = "app.js",
    version: int = 3,
) -> None:
    payload: dict[str, object] = {
        "version": version,
        "file": file,
        "sources": sources,
        "names": [],
        "mappings": "",
    }
    if contents is not None:
        payload["sourcesContent"] = contents
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_basic_explode(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "sources"
    raw.mkdir()
    _write_map(
        raw / "foo.js.map",
        sources=["webpack:///src/app.tsx", "./util.ts"],
        contents=[APP_TSX_CONTENT, UTIL_TS_CONTENT],
    )
    (raw / "foo.js").write_text("// bundled\n", encoding="utf-8")

    result = explode_sourcemaps(raw, out)

    assert isinstance(result, SourcemapResult)
    assert result.original_files == 2
    assert result.nomap_files == 0
    assert result.conflicts == 0
    assert result.malformed == []
    assert result.missing_content == []
    assert (out / "src/app.tsx").read_text(encoding="utf-8") == APP_TSX_CONTENT
    assert (out / "util.ts").read_text(encoding="utf-8") == UTIL_TS_CONTENT
    assert not (out / "_nomap" / "foo.js").exists()


def test_idempotent(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "sources"
    raw.mkdir()
    _write_map(
        raw / "foo.js.map",
        sources=["src/app.tsx"],
        contents=[APP_TSX_CONTENT],
    )
    (raw / "foo.js").write_text("// bundled\n", encoding="utf-8")
    (raw / "loose.js").write_text("console.log(1);\n", encoding="utf-8")

    first = explode_sourcemaps(raw, out)
    first_mtime = (out / "src/app.tsx").stat().st_mtime_ns
    first_nomap_mtime = (out / "_nomap" / "loose.js").stat().st_mtime_ns

    second = explode_sourcemaps(raw, out)

    assert second.model_dump() == first.model_dump()
    assert (out / "src/app.tsx").stat().st_mtime_ns == first_mtime
    assert (out / "_nomap" / "loose.js").stat().st_mtime_ns == first_nomap_mtime


def test_nomap_fallback(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "sources"
    (raw / "vendor").mkdir(parents=True)
    (raw / "vendor" / "chunk.js").write_text("var a=1;\n", encoding="utf-8")

    result = explode_sourcemaps(raw, out)

    assert result.original_files == 0
    assert result.nomap_files == 1
    nomap_copy = out / "_nomap" / "vendor" / "chunk.js"
    assert nomap_copy.exists()
    assert nomap_copy.read_text(encoding="utf-8") == "var a=1;\n"


def test_malformed_map_logged(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "sources"
    raw.mkdir()
    (raw / "bogus.js.map").write_text("not-a-json {", encoding="utf-8")
    (raw / "bogus.js").write_text("// bundled\n", encoding="utf-8")

    result = explode_sourcemaps(raw, out)

    assert len(result.malformed) == 1
    assert any("bogus.js.map" in p for p in result.malformed)
    assert result.original_files == 0
    assert not (out / "_nomap" / "bogus.js").exists()


def test_missing_sources_content(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "sources"
    raw.mkdir()
    _write_map(
        raw / "headless.js.map",
        sources=["src/app.tsx"],
        contents=None,
    )
    (raw / "headless.js").write_text("// bundled\n", encoding="utf-8")

    result = explode_sourcemaps(raw, out)

    assert len(result.missing_content) == 1
    assert any("headless.js.map" in p for p in result.missing_content)
    assert result.original_files == 0
    assert not (out / "_nomap" / "headless.js").exists()


def test_collision_keeps_longer(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "sources"
    raw.mkdir()
    short_content = "export const x = 1;\n"
    long_content = "export const x = 1;\nexport const y = 2;\nexport const z = 3;\n"

    _write_map(
        raw / "a.js.map",
        sources=["dup.ts"],
        contents=[short_content],
    )
    _write_map(
        raw / "b.js.map",
        sources=["dup.ts"],
        contents=[long_content],
    )

    result = explode_sourcemaps(raw, out)

    assert result.conflicts == 1
    assert (out / "dup.ts").read_text(encoding="utf-8") == long_content


def test_manifest_written(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "sources"
    raw.mkdir()
    _write_map(
        raw / "foo.js.map",
        sources=["webpack:///src/app.tsx", "./util.ts"],
        contents=[APP_TSX_CONTENT, UTIL_TS_CONTENT],
    )
    (raw / "foo.js").write_text("// bundled\n", encoding="utf-8")
    _write_map(
        raw / "bar.js.map",
        sources=["src/other.ts"],
        contents=["export const k = 1;\n"],
    )
    (raw / "bar.js").write_text("// bundled\n", encoding="utf-8")

    explode_sourcemaps(raw, out)

    manifest_path = out / "_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    assert "maps" in manifest
    paths_in_manifest = {entry["path"] for entry in manifest["maps"]}
    assert any("foo.js.map" in p for p in paths_in_manifest)
    assert any("bar.js.map" in p for p in paths_in_manifest)
    by_path = {entry["path"]: entry["sources_emitted"] for entry in manifest["maps"]}
    foo_entry = next(v for k, v in by_path.items() if k.endswith("foo.js.map"))
    bar_entry = next(v for k, v in by_path.items() if k.endswith("bar.js.map"))
    assert len(foo_entry) == 2
    assert len(bar_entry) == 1
