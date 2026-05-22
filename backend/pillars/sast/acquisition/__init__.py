"""Acquisition pipeline: URL → JS bundles + sourcemaps → reconstructed source tree.

One-call orchestration: harvest fires Playwright + webpack lazy-chunk enum,
hidden-map recon back-fills sourcemaps that lack a sourceMappingURL pragma
(Netlify `devtool: 'hidden-source-map'`, CRA, Vite, Next.js), and the
sourcemap exploder decodes everything into an original source tree.

A Gemini Flash chat agent driving a run only needs to call this once.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from backend.pillars.memory.runs import RunLayout
from backend.pillars.sast.acquisition.harvester import Harvester, HarvestResult
from backend.pillars.sast.acquisition.hidden_map_recon import (
    HiddenMapRecon,
    HiddenMapReconResult,
)
from backend.pillars.sast.acquisition.sourcemap import SourcemapResult, explode_sourcemaps


class AcquisitionResult(BaseModel):
    harvest: HarvestResult
    hidden_map_recon: HiddenMapReconResult
    sourcemap: SourcemapResult
    raw_dir: Path
    sources_dir: Path


class Pipeline:
    def __init__(
        self,
        scope: list[str],
        depth: int = 2,
        timeout_ms: int = 15000,
        *,
        hidden_map_sentry: bool = False,
    ) -> None:
        self._scope = scope
        self._depth = depth
        self._timeout_ms = timeout_ms
        # Sentry artifact recon is chatty and only helps misconfigured Sentry
        # instances. Off by default in the pipeline; direct callers of
        # HiddenMapRecon can opt in.
        self._hidden_map_sentry = hidden_map_sentry

    async def acquire(self, url: str, run_layout: RunLayout) -> AcquisitionResult:
        run_layout.create()
        harvester = Harvester(scope=self._scope, depth=self._depth, timeout_ms=self._timeout_ms)
        harvest = await harvester.acquire(url, run_layout.raw_dir)

        recon = HiddenMapRecon(scope=self._scope, sentry_enabled=self._hidden_map_sentry)
        hidden_map_recon = await recon.run(run_layout.raw_dir)

        sourcemap = explode_sourcemaps(run_layout.raw_dir, run_layout.sourcemap_dir)
        return AcquisitionResult(
            harvest=harvest,
            hidden_map_recon=hidden_map_recon,
            sourcemap=sourcemap,
            raw_dir=run_layout.raw_dir,
            sources_dir=run_layout.sourcemap_dir,
        )


__all__ = [
    "AcquisitionResult",
    "HarvestResult",
    "Harvester",
    "HiddenMapRecon",
    "HiddenMapReconResult",
    "Pipeline",
    "SourcemapResult",
    "explode_sourcemaps",
]
