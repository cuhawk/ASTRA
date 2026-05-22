from __future__ import annotations

import pytest

from backend.cypher.playbooks import PLAYBOOKS, render


def test_playbook_catalog() -> None:
    assert set(PLAYBOOKS) == {
        "dead_functions",
        "top_callers",
        "callers_of",
        "executed_in_feature",
        "function_count",
    }
    cypher, params = render("function_count")
    assert cypher == PLAYBOOKS["function_count"].cypher
    assert params == {}


def test_render_with_params() -> None:
    cypher, params = render("callers_of", {"name": "foo"})
    assert "$name" in cypher
    assert params == {"name": "foo"}


def test_render_missing_params() -> None:
    with pytest.raises(ValueError) as exc:
        render("callers_of")
    assert "name" in str(exc.value)


def test_render_unknown_playbook() -> None:
    with pytest.raises(KeyError):
        render("nonexistent")


def test_render_drops_extra_params() -> None:
    _, params = render("callers_of", {"name": "foo", "extra": "ignored"})
    assert params == {"name": "foo"}
