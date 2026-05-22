from __future__ import annotations

import pytest

from backend.cypher.validate import (
    CypherForbidden,
    assert_read_only,
    is_read_only,
    starts_with_allowed_prefix,
)


@pytest.mark.parametrize(
    "cypher",
    [
        "MATCH (n) RETURN n",
        "OPTIONAL MATCH (a)-->(b) RETURN a, b",
        "WITH 1 AS x RETURN x",
        "UNWIND [1,2,3] AS i RETURN i",
        "RETURN 1 AS one",
        "  MATCH (n) RETURN n  ",
    ],
)
def test_read_only_accepted(cypher: str) -> None:
    assert is_read_only(cypher)
    assert_read_only(cypher)


@pytest.mark.parametrize(
    "cypher, keyword",
    [
        ("CREATE (n:X)", "CREATE"),
        ("MATCH (n) DELETE n", "DELETE"),
        ("CALL db.something()", "CALL"),
        ("MATCH (n) SET n.x = 1", "SET"),
        ("MERGE (n:X {id: '1'})", "MERGE"),
        ("MATCH (n) REMOVE n.label", "REMOVE"),
        ("DROP TABLE Foo", "DROP"),
        ("MATCH (n) DETACH DELETE n", "DETACH"),
        ("FOREACH (x IN [] | MATCH (n) RETURN n)", "FOREACH"),
    ],
)
def test_forbidden_rejected(cypher: str, keyword: str) -> None:
    assert not is_read_only(cypher)
    with pytest.raises(CypherForbidden) as exc:
        assert_read_only(cypher)
    assert keyword in str(exc.value)


def test_case_insensitive_create() -> None:
    assert not is_read_only("create (n:X)")
    with pytest.raises(CypherForbidden):
        assert_read_only("create (n:X)")


def test_case_insensitive_match() -> None:
    assert is_read_only("match (n) return n")


def test_leading_whitespace_classified() -> None:
    assert starts_with_allowed_prefix("\n\t  MATCH (n) RETURN n")
    assert is_read_only("\n\t  MATCH (n) RETURN n")


def test_leading_line_comment() -> None:
    cypher = "// just looking\nMATCH (n) RETURN n"
    assert starts_with_allowed_prefix(cypher)
    assert is_read_only(cypher)


def test_leading_block_comment() -> None:
    cypher = "/* this is a comment */ MATCH (n) RETURN n"
    assert starts_with_allowed_prefix(cypher)
    assert is_read_only(cypher)


def test_prefix_check_only() -> None:
    assert starts_with_allowed_prefix("MATCH (n) RETURN n")
    assert not starts_with_allowed_prefix("CREATE (n)")
    assert not starts_with_allowed_prefix("DELETE n")


def test_prefix_violation_message() -> None:
    with pytest.raises(CypherForbidden) as exc:
        assert_read_only("FOO BAR BAZ")
    assert "MATCH" in str(exc.value)
