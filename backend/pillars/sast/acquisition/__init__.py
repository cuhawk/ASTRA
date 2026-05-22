"""Acquisition pipeline: URL → JS bundles + sourcemaps → reconstructed source tree."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from backend.pillars.memory.runs import RunLayout
from backend.pillars.sast.acquisition.harvester import Harvester, HarvestResult
from backend.pillars.sast.acquisition.sourcemap import SourcemapResult, explode_sourcemaps


class AcquisitionResult(BaseModel):
    harvest: HarvestResult
    sourcemap: SourcemapResult
    raw_dir: Path
    sources_dir: Path


class Pipeline:
    def __init__(self, scope: list[str], depth: int = 2, timeout_ms: int = 15000) -> None:
        self._scope = scope
        self._depth = depth
        self._timeout_ms = timeout_ms

    async def acquire(self, url: str, run_layout: RunLayout) -> AcquisitionResult:
        run_layout.create()
        harvester = Harvester(scope=self._scope, depth=self._depth, timeout_ms=self._timeout_ms)
        harvest = await harvester.acquire(url, run_layout.raw_dir)
        sourcemap = explode_sourcemaps(run_layout.raw_dir, run_layout.sourcemap_dir)
        return AcquisitionResult(
            harvest=harvest,
            sourcemap=sourcemap,
            raw_dir=run_layout.raw_dir,
            sources_dir=run_layout.sourcemap_dir,
        )


__all__ = [
    "AcquisitionResult",
    "HarvestResult",
    "Harvester",
    "Pipeline",
    "SourcemapResult",
    "explode_sourcemaps",
]
