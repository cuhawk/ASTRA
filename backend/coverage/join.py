from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from pydantic import BaseModel

from backend.pillars.memory.graph import GraphStore

if TYPE_CHECKING:
    from backend.pillars.memory.runs import RunLayout


_ANON_V8 = ""
_ANON_GRAPH = "<anonymous>"


class FeatureRow(BaseModel):
    id: str
    name: str


class JoinResult(BaseModel):
    feature_id: str
    matched_functions: int
    unmatched_v8_functions: int
    bundle_urls_seen: int


def _url_to_map_key(url: str) -> str | None:
    parsed = urlparse(url)
    netloc = parsed.netloc
    if not netloc:
        return None
    path = parsed.path or ""
    if not path.endswith(".js"):
        # Coverage may also be served for non-.js (e.g. inline) — give up.
        return None
    return f"{netloc}{path}.map"


def _load_url_to_sources(manifest_path: Path) -> dict[str, list[str]] | None:
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    out: dict[str, list[str]] = {}
    for entry in data.get("maps") or []:
        map_path = entry.get("path")
        sources = entry.get("sources_emitted") or []
        if not isinstance(map_path, str):
            continue
        norm = map_path.replace("\\", "/")
        out[norm] = [s for s in sources if isinstance(s, str)]
    return out


def _resolve_sources(
    url: str,
    url_to_sources: dict[str, list[str]] | None,
) -> list[str] | None:
    if url_to_sources is None:
        return None
    key = _url_to_map_key(url)
    if key is None:
        return []
    for map_path, sources in url_to_sources.items():
        if map_path.endswith("/" + key) or map_path == key:
            return sources
    return []


def _function_was_executed(fn: dict[str, Any]) -> bool:
    for r in fn.get("ranges") or []:
        if (r.get("count") or 0) > 0:
            return True
    return False


def _normalize_v8_name(name: str) -> str:
    if name == _ANON_V8:
        return _ANON_GRAPH
    return name


def _match_function_ids(
    graph: GraphStore,
    fn_name: str,
    source_paths: list[str] | None,
) -> list[str]:
    if source_paths is None:
        rows = graph.query(
            "MATCH (f:Function {name: $name}) RETURN f.id",
            params={"name": fn_name},
        )
    elif not source_paths:
        return []
    else:
        rows = graph.query(
            "MATCH (f:Function) WHERE f.name = $name AND f.path IN $paths RETURN f.id",
            params={"name": fn_name, "paths": source_paths},
        )
    ids: list[str] = []
    for row in rows:
        fid = row.get("f.id")
        if isinstance(fid, str):
            ids.append(fid)
    return ids


def join_coverage(
    coverage_json_path: Path,
    layout: "RunLayout",
    feature: FeatureRow,
) -> JoinResult:
    coverage = json.loads(coverage_json_path.read_text(encoding="utf-8"))
    entries = coverage.get("entries") or []

    manifest_path = layout.sourcemap_dir / "_manifest.json"
    url_to_sources = _load_url_to_sources(manifest_path)

    bundle_urls: set[str] = set()
    matched_edges = 0
    unmatched = 0

    with GraphStore(layout.graph_path) as graph:
        graph.add_node("Feature", {"id": feature.id, "name": feature.name})

        for entry in entries:
            url = entry.get("url") or ""
            if url:
                bundle_urls.add(url)
            sources = _resolve_sources(url, url_to_sources)

            for fn in entry.get("functions") or []:
                if not _function_was_executed(fn):
                    continue
                v8_name = fn.get("functionName") or ""
                name = _normalize_v8_name(v8_name)
                ids = _match_function_ids(graph, name, sources)
                if not ids:
                    unmatched += 1
                    continue
                for fid in ids:
                    graph.add_edge(
                        "Function", fid, "Feature", feature.id, "EXECUTED_IN"
                    )
                    matched_edges += 1

    return JoinResult(
        feature_id=feature.id,
        matched_functions=matched_edges,
        unmatched_v8_functions=unmatched,
        bundle_urls_seen=len(bundle_urls),
    )
