"""End-to-end smoke: RunLayout → GraphStore + VectorStore → readback → purge."""
from __future__ import annotations

import hashlib

from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout
from backend.pillars.memory.vectors import VectorStore


def _dummy_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([b / 255.0 for b in h[:8]])
    return out


def test_full_run_lifecycle(tmp_path):
    layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1").create()

    assert layout.run_dir.is_dir()
    assert layout.raw_dir.is_dir()
    assert not layout.graph_path.exists()
    assert not layout.vectors_path.exists()
    assert not layout.meta_db_path.exists()

    with GraphStore(layout.graph_path) as g:
        g.add_node("Function", {"id": "f1", "name": "login"})
        g.add_node("Function", {"id": "f2", "name": "validate"})
        g.add_edge("Function", "f1", "Function", "f2", "CALLS")
        rows = g.query("MATCH (a:Function)-[:CALLS]->(b:Function) RETURN a.id AS a, b.id AS b")
        assert rows == [{"a": "f1", "b": "f2"}]

    v = VectorStore(layout.vectors_path, _dummy_embed, dim=8)
    v.upsert("chunks", ["c1"], ["login handler source"], [{"path": "auth.js"}])
    hits = v.query("chunks", "login handler source", top_k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == "c1"
    assert hits[0]["meta"] == {"path": "auth.js"}

    layout.purge()
    assert not layout.run_dir.exists()
    assert layout.root.is_dir()
