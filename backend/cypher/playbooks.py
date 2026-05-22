from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Playbook(BaseModel):
    slug: str
    name: str
    description: str
    cypher: str
    params: list[str] = []


PLAYBOOKS: dict[str, Playbook] = {
    "dead_functions": Playbook(
        slug="dead_functions",
        name="Dead functions",
        description="Function nodes not executed in any recorded feature.",
        cypher=(
            "MATCH (f:Function) WHERE NOT EXISTS { "
            "MATCH (f)-[:EXECUTED_IN]->(:Feature) "
            "} RETURN f.name AS name, f.path AS path LIMIT 200"
        ),
    ),
    "top_callers": Playbook(
        slug="top_callers",
        name="Top callers",
        description="Functions with the most outgoing CALLS edges (likely orchestrators).",
        cypher=(
            "MATCH (f:Function)-[c:CALLS]->() "
            "RETURN f.name AS name, count(c) AS calls "
            "ORDER BY calls DESC LIMIT 20"
        ),
    ),
    "callers_of": Playbook(
        slug="callers_of",
        name="Callers of",
        description="Functions that call a given function by name.",
        cypher=(
            "MATCH (caller:Function)-[:CALLS]->(target:Function {name: $name}) "
            "RETURN caller.name AS caller, caller.path AS path"
        ),
        params=["name"],
    ),
    "executed_in_feature": Playbook(
        slug="executed_in_feature",
        name="Executed in feature",
        description="Functions tied to a given feature via EXECUTED_IN.",
        cypher=(
            "MATCH (f:Function)-[:EXECUTED_IN]->(:Feature {name: $feature}) "
            "RETURN f.name AS name, f.path AS path"
        ),
        params=["feature"],
    ),
    "function_count": Playbook(
        slug="function_count",
        name="Function count",
        description="Total Function nodes in the run.",
        cypher="MATCH (f:Function) RETURN count(f) AS n",
    ),
}


def render(slug: str, params: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    if slug not in PLAYBOOKS:
        raise KeyError(f"unknown playbook: {slug}")
    pb = PLAYBOOKS[slug]
    params = params or {}
    missing = [p for p in pb.params if p not in params]
    if missing:
        raise ValueError(f"playbook {slug} missing params: {missing}")
    return pb.cypher, {p: params[p] for p in pb.params}
