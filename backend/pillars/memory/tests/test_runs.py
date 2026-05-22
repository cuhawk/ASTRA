from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.pillars.memory.runs import RunLayout


def test_create_makes_full_tree(tmp_path: Path) -> None:
    layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1").create()
    assert layout.run_dir.is_dir()
    assert layout.raw_dir.is_dir()
    assert layout.sourcemap_dir.is_dir()
    assert layout.coverage_dir.is_dir()
    assert layout.advisor_dir.is_dir()
    # graph_path + vectors_path + meta_db_path are owned by kuzu/lancedb/sqlite
    # respectively. They must NOT exist until those libs create them.
    assert not layout.graph_path.exists()
    assert not layout.vectors_path.exists()
    assert not layout.meta_db_path.exists()


def test_create_is_idempotent(tmp_path: Path) -> None:
    layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1")
    layout.create()
    layout.create()
    assert layout.raw_dir.is_dir()
    assert layout.sourcemap_dir.is_dir()
    assert layout.coverage_dir.is_dir()
    assert layout.advisor_dir.is_dir()


def test_purge_removes_run_dir(tmp_path: Path) -> None:
    layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1").create()
    (layout.raw_dir / "dummy.js").write_text("console.log('hi');")
    layout.purge()
    assert not layout.run_dir.exists()
    assert (tmp_path / "u1").is_dir()
    assert tmp_path.is_dir()


def test_purge_idempotent_when_missing(tmp_path: Path) -> None:
    layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1")
    layout.purge()


def test_exists_reflects_state(tmp_path: Path) -> None:
    layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1")
    assert layout.exists() is False
    layout.create()
    assert layout.exists() is True
    layout.purge()
    assert layout.exists() is False


def test_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        RunLayout(root=tmp_path, user_id="../etc", run_id="r1")
    with pytest.raises(ValidationError):
        RunLayout(root=tmp_path, user_id="u1", run_id="..")


def test_rejects_uppercase(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        RunLayout(root=tmp_path, user_id="UpperCase", run_id="r1")


def test_requires_absolute_root() -> None:
    with pytest.raises(ValidationError):
        RunLayout(root=Path("relative/path"), user_id="u1", run_id="r1")


def test_frozen(tmp_path: Path) -> None:
    layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1")
    with pytest.raises(ValidationError):
        layout.user_id = "other"
