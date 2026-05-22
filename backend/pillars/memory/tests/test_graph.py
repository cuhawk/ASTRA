from __future__ import annotations

from pathlib import Path

import pytest

from backend.pillars.memory.graph import GraphStore


def test_node_edge_roundtrip(tmp_path: Path) -> None:
    g = GraphStore(tmp_path / "g.kuzu")
    try:
        g.add_node("Function", {"id": "f1", "name": "main"})
        g.add_node("Function", {"id": "f2", "name": "helper"})
        g.add_node("Function", {"id": "f3", "name": "sink"})
        g.add_edge("Function", "f1", "Function", "f2", "CALLS")
        g.add_edge("Function", "f2", "Function", "f3", "CALLS")

        rows = g.query(
            "MATCH (a:Function)-[:CALLS]->(b:Function) "
            "RETURN a.id AS a_id, b.id AS b_id ORDER BY a.id"
        )
        assert rows == [
            {"a_id": "f1", "b_id": "f2"},
            {"a_id": "f2", "b_id": "f3"},
        ]
    finally:
        g.close()


def test_idempotent_node_upsert(tmp_path: Path) -> None:
    g = GraphStore(tmp_path / "g.kuzu")
    try:
        g.add_node("Function", {"id": "f1", "name": "first"})
        g.add_node("Function", {"id": "f1", "name": "second"})

        rows = g.query("MATCH (n:Function) RETURN n.id AS id, n.name AS name")
        assert rows == [{"id": "f1", "name": "second"}]
    finally:
        g.close()


def test_context_manager(tmp_path: Path) -> None:
    p = tmp_path / "g.kuzu"
    with GraphStore(p) as g:
        g.add_node("X", {"id": "x1"})

    with GraphStore(p) as g2:
        rows = g2.query("MATCH (n:X) RETURN n.id AS id")
        assert rows == [{"id": "x1"}]


def test_rejects_unsupported_prop_type(tmp_path: Path) -> None:
    g = GraphStore(tmp_path / "g.kuzu")
    try:
        with pytest.raises(ValueError):
            g.add_node("Function", {"id": "f1", "tags": ["a", "b"]})
    finally:
        g.close()
