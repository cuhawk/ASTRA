from __future__ import annotations

import re
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

_SLUG_PATTERN = r"^[a-z0-9_-]{1,64}$"
_SLUG_RE = re.compile(_SLUG_PATTERN)


class RunLayout(BaseModel):
    model_config = ConfigDict(frozen=True)

    root: Path
    user_id: str
    run_id: str

    @field_validator("user_id", "run_id")
    @classmethod
    def _check_slug(cls, v: str) -> str:
        return cls.validate_slug(v)

    @field_validator("root")
    @classmethod
    def _check_root_absolute(cls, v: Path) -> Path:
        if not v.is_absolute():
            raise ValueError(f"root must be an absolute path, got: {v!r}")
        return v

    @classmethod
    def validate_slug(cls, s: str) -> str:
        if not isinstance(s, str) or not _SLUG_RE.match(s):
            raise ValueError(
                f"invalid slug {s!r}: must match {_SLUG_PATTERN}"
            )
        return s

    @property
    def run_dir(self) -> Path:
        return self.root / self.user_id / self.run_id

    @property
    def graph_path(self) -> Path:
        return self.run_dir / "graph.kuzu"

    @property
    def vectors_path(self) -> Path:
        return self.run_dir / "vectors.lance"

    @property
    def meta_db_path(self) -> Path:
        return self.run_dir / "meta.sqlite"

    @property
    def raw_dir(self) -> Path:
        return self.run_dir / "raw"

    @property
    def sourcemap_dir(self) -> Path:
        return self.run_dir / "sourcemap"

    @property
    def coverage_dir(self) -> Path:
        return self.run_dir / "coverage"

    @property
    def advisor_dir(self) -> Path:
        return self.run_dir / "advisor"

    def create(self) -> "RunLayout":
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for d in (
            self.raw_dir,
            self.sourcemap_dir,
            self.coverage_dir,
            self.advisor_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        return self

    def purge(self) -> None:
        if self.run_dir.is_dir():
            shutil.rmtree(self.run_dir)

    def exists(self) -> bool:
        return self.run_dir.is_dir()
