from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from backend.cypher.validate import assert_read_only
from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout


class CypherResult(BaseModel):
    cypher: str
    rows: list[dict[str, Any]]
    row_count: int
    duration_ms: int


def run_cypher(
    layout: RunLayout,
    cypher: str,
    params: dict[str, Any] | None = None,
) -> CypherResult:
    assert_read_only(cypher)
    t0 = time.monotonic()
    with GraphStore(layout.graph_path) as g:
        rows = g.query(cypher, params or {})
    dur = int((time.monotonic() - t0) * 1000)
    return CypherResult(
        cypher=cypher,
        rows=rows,
        row_count=len(rows),
        duration_ms=dur,
    )
