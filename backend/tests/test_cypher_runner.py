from __future__ import annotations

from pathlib import Path

import pytest

from backend.cypher.runner import CypherResult, run_cypher
from backend.cypher.validate import CypherForbidden
from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout


@pytest.fixture
def layout(tmp_path: Path) -> RunLayout:
    lo = RunLayout(root=tmp_path, user_id="u1", run_id="r1").create()
    with GraphStore(lo.graph_path) as g:
        g.add_node(
            "Function",
            {
                "id": "f1",
                "name": "x",
                "path": "p",
                "kind": "function_declaration",
                "start_line": 1,
                "end_line": 1,
            },
        )
        g.add_node(
            "Function",
            {
                "id": "f2",
                "name": "y",
                "path": "p",
                "kind": "function_declaration",
                "start_line": 2,
                "end_line": 2,
            },
        )
        g.add_edge("Function", "f1", "Function", "f2", "CALLS")
    return lo


def test_match_returns_rows(layout: RunLayout) -> None:
    res = run_cypher(layout, "MATCH (f:Function) RETURN f.name AS name ORDER BY name")
    assert isinstance(res, CypherResult)
    assert res.row_count == 2
    assert [r["name"] for r in res.rows] == ["x", "y"]
    assert res.cypher.startswith("MATCH")
    assert res.duration_ms >= 0


def test_mutation_raises(layout: RunLayout) -> None:
    with pytest.raises(CypherForbidden):
        run_cypher(layout, "CREATE (n:Function {id: 'f3'})")


def test_query_with_params(layout: RunLayout) -> None:
    cypher = (
        "MATCH (caller:Function)-[:CALLS]->(target:Function {name: $name}) "
        "RETURN caller.name AS caller"
    )
    res = run_cypher(layout, cypher, {"name": "y"})
    assert res.row_count == 1
    assert res.rows[0]["caller"] == "x"
