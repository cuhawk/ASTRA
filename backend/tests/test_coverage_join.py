from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.coverage.join import FeatureRow, join_coverage
from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout


def _layout(tmp_path: Path) -> RunLayout:
    layout = RunLayout(
        root=tmp_path.resolve() / "runs",
        user_id="u1",
        run_id="r1",
    )
    layout.create()
    return layout


def _seed_functions(layout: RunLayout, fns: list[dict]) -> None:
    with GraphStore(layout.graph_path) as g:
        for fn in fns:
            g.add_node(
                "Function",
                {
                    "id": fn["id"],
                    "name": fn["name"],
                    "path": fn["path"],
                    "kind": fn.get("kind", "function_declaration"),
                    "start_line": fn.get("start_line", 1),
                    "end_line": fn.get("end_line", 5),
                },
            )


def _write_manifest(layout: RunLayout, bundle_relpath: str, sources: list[str]) -> None:
    map_full_path = (layout.raw_dir / bundle_relpath).as_posix()
    manifest = {
        "maps": [
            {"path": map_full_path, "sources_emitted": sources},
        ],
        "conflicts": [],
        "malformed": [],
        "missing_content": [],
    }
    (layout.sourcemap_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def _write_coverage(
    path: Path,
    feature_name: str,
    url: str,
    functions: list[dict],
) -> None:
    payload = {
        "feature_name": feature_name,
        "captured_at": 1_716_415_200,
        "entries": [
            {"url": url, "functions": functions, "source_text": None},
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _executed_edges(layout: RunLayout, feature_id: str) -> list[dict]:
    with GraphStore(layout.graph_path) as g:
        try:
            return g.query(
                "MATCH (fn:Function)-[:EXECUTED_IN]->(f:Feature {id: $fid}) "
                "RETURN fn.name AS name, fn.id AS fid",
                params={"fid": feature_id},
            )
        except RuntimeError as exc:
            if "EXECUTED_IN" in str(exc):
                return []
            raise


def test_basic_match_writes_executed_in(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    _seed_functions(
        layout,
        [
            {"id": "fn-add-001", "name": "add", "path": "src/App.tsx"},
            {"id": "fn-unused-002", "name": "unused", "path": "src/App.tsx"},
        ],
    )
    _write_manifest(
        layout,
        "127.0.0.1:8080/assets/index-DXzdPT_J.js.map",
        ["src/App.tsx"],
    )
    cov_path = layout.coverage_dir / "checkout.json"
    _write_coverage(
        cov_path,
        "checkout",
        "http://127.0.0.1:8080/assets/index-DXzdPT_J.js",
        [
            {
                "functionName": "add",
                "ranges": [{"startOffset": 0, "endOffset": 50, "count": 1}],
                "isBlockCoverage": False,
            },
            {
                "functionName": "unused",
                "ranges": [{"startOffset": 51, "endOffset": 100, "count": 0}],
                "isBlockCoverage": False,
            },
        ],
    )

    result = join_coverage(cov_path, layout, FeatureRow(id="checkout", name="checkout"))

    assert result.matched_functions == 1
    assert result.unmatched_v8_functions == 0
    assert result.bundle_urls_seen == 1
    assert result.feature_id == "checkout"

    rows = _executed_edges(layout, "checkout")
    assert len(rows) == 1
    assert rows[0]["name"] == "add"


def test_unmatched_v8_function_counted(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    _seed_functions(
        layout,
        [
            {"id": "fn-add-001", "name": "add", "path": "src/App.tsx"},
        ],
    )
    _write_manifest(
        layout,
        "127.0.0.1:8080/assets/index-DXzdPT_J.js.map",
        ["src/App.tsx"],
    )
    cov_path = layout.coverage_dir / "ghost.json"
    _write_coverage(
        cov_path,
        "ghost",
        "http://127.0.0.1:8080/assets/index-DXzdPT_J.js",
        [
            {
                "functionName": "ghost",
                "ranges": [{"startOffset": 0, "endOffset": 10, "count": 3}],
                "isBlockCoverage": False,
            },
        ],
    )

    result = join_coverage(cov_path, layout, FeatureRow(id="ghost", name="ghost"))

    assert result.matched_functions == 0
    assert result.unmatched_v8_functions == 1
    rows = _executed_edges(layout, "ghost")
    assert rows == []


def test_zero_count_functions_skipped(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    _seed_functions(
        layout,
        [
            {"id": "fn-add-001", "name": "add", "path": "src/App.tsx"},
        ],
    )
    _write_manifest(
        layout,
        "127.0.0.1:8080/assets/index-DXzdPT_J.js.map",
        ["src/App.tsx"],
    )
    cov_path = layout.coverage_dir / "noop.json"
    _write_coverage(
        cov_path,
        "noop",
        "http://127.0.0.1:8080/assets/index-DXzdPT_J.js",
        [
            {
                "functionName": "add",
                "ranges": [{"startOffset": 0, "endOffset": 10, "count": 0}],
                "isBlockCoverage": False,
            },
        ],
    )

    result = join_coverage(cov_path, layout, FeatureRow(id="noop", name="noop"))

    assert result.matched_functions == 0
    assert result.unmatched_v8_functions == 0
    rows = _executed_edges(layout, "noop")
    assert rows == []


def test_idempotent_rerun(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    _seed_functions(
        layout,
        [
            {"id": "fn-add-001", "name": "add", "path": "src/App.tsx"},
        ],
    )
    _write_manifest(
        layout,
        "127.0.0.1:8080/assets/index-DXzdPT_J.js.map",
        ["src/App.tsx"],
    )
    cov_path = layout.coverage_dir / "rerun.json"
    _write_coverage(
        cov_path,
        "rerun",
        "http://127.0.0.1:8080/assets/index-DXzdPT_J.js",
        [
            {
                "functionName": "add",
                "ranges": [{"startOffset": 0, "endOffset": 50, "count": 2}],
                "isBlockCoverage": False,
            },
        ],
    )

    feature = FeatureRow(id="rerun", name="rerun")
    first = join_coverage(cov_path, layout, feature)
    second = join_coverage(cov_path, layout, feature)

    assert first.matched_functions == 1
    assert second.matched_functions == 1

    with GraphStore(layout.graph_path) as g:
        rows = g.query(
            "MATCH (:Function {name: 'add'})-[r:EXECUTED_IN]->(:Feature {id: 'rerun'}) "
            "RETURN count(r) AS c"
        )
    assert rows[0]["c"] == 1


def test_manifest_missing_falls_back_to_name_only(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    _seed_functions(
        layout,
        [
            {"id": "fn-add-only", "name": "add", "path": "deep/nested/whatever.ts"},
        ],
    )
    assert not (layout.sourcemap_dir / "_manifest.json").exists()

    cov_path = layout.coverage_dir / "fallback.json"
    _write_coverage(
        cov_path,
        "fallback",
        "http://127.0.0.1:8080/_nomap/chunk.js",
        [
            {
                "functionName": "add",
                "ranges": [{"startOffset": 0, "endOffset": 10, "count": 1}],
                "isBlockCoverage": False,
            },
        ],
    )

    result = join_coverage(
        cov_path, layout, FeatureRow(id="fallback", name="fallback")
    )

    assert result.matched_functions == 1
    assert result.unmatched_v8_functions == 0
    rows = _executed_edges(layout, "fallback")
    assert len(rows) == 1
    assert rows[0]["name"] == "add"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
