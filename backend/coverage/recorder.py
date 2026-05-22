from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from pydantic import BaseModel


class Action(BaseModel):
    type: Literal["goto", "click", "fill", "wait"]
    selector: str | None = None
    value: str | None = None
    ms: int | None = None
    url: str | None = None


class CoverageEntry(BaseModel):
    url: str
    functions: list[dict]
    source_text: str | None = None


class CoverageResult(BaseModel):
    feature_name: str
    captured_at: int
    entries: list[CoverageEntry]


class CoverageRecorder:
    def __init__(self, scope: list[str], timeout_ms: int = 15000) -> None:
        self._scope = {host.lower() for host in scope}
        self._timeout_ms = timeout_ms

    def _in_scope(self, url: str) -> bool:
        try:
            netloc = urlparse(url).netloc.lower()
        except ValueError:
            return False
        return netloc in self._scope

    async def record(
        self,
        start_url: str,
        actions: list[Action],
        feature_name: str,
        save_to: Path,
    ) -> CoverageResult:
        save_to.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(self._timeout_ms)
            cdp = await context.new_cdp_session(page)
            try:
                await cdp.send("Profiler.enable")
                await cdp.send(
                    "Profiler.startPreciseCoverage",
                    {"callCount": True, "detailed": True},
                )
                await page.goto(start_url, wait_until="networkidle")

                for action in actions:
                    if action.type == "goto":
                        target = action.url or ""
                        await page.goto(target, wait_until="networkidle")
                    elif action.type == "click":
                        await page.click(action.selector or "")
                    elif action.type == "fill":
                        await page.fill(action.selector or "", action.value or "")
                    elif action.type == "wait":
                        await asyncio.sleep((action.ms or 100) / 1000)

                raw: dict[str, Any] = await cdp.send("Profiler.takePreciseCoverage")
                results: list[dict[str, Any]] = raw.get("result", [])
            finally:
                try:
                    await cdp.send("Profiler.stopPreciseCoverage")
                except Exception:
                    pass
                try:
                    await cdp.detach()
                except Exception:
                    pass
                await page.close()
                await context.close()
                await browser.close()

        entries: list[CoverageEntry] = []
        for script in results:
            url = script.get("url") or ""
            if not self._in_scope(url):
                continue
            entries.append(
                CoverageEntry(
                    url=url,
                    functions=list(script.get("functions") or []),
                    source_text=script.get("scriptSource"),
                )
            )

        result = CoverageResult(
            feature_name=feature_name,
            captured_at=int(time.time()),
            entries=entries,
        )
        out_path = save_to / f"{feature_name}.json"
        out_path.write_text(
            json.dumps(result.model_dump(), indent=2, default=str),
            encoding="utf-8",
        )
        return result
