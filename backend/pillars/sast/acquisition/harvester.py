# vendored-from: internal-upstream
# upstream-path: .claude/skills/js-harvest/SKILL.md
# upstream-sha:  83cae232b94e7998ef543c72e8e7302617d438a0
# imported-on:   2026-05-22
# license:       proprietary — see upstream repo
# modifications: port from chrome-devtools MCP recipe to a Playwright-driven async Python module; hidden-map brute-force recon (upstream Step 7) deliberately deferred; webpack lazy-chunk enumeration integrated post-navigation (2026-05-23)

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

from playwright.async_api import async_playwright
from pydantic import BaseModel

from backend.pillars.sast.acquisition.webpack_chunk_enum import enumerate_webpack_chunks

_JS_SUFFIXES = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")
_SOURCEMAP_PRAGMA = re.compile(rb"(?m)^[ \t]*//[#@][ \t]*sourceMappingURL=([^\s]+)[ \t]*$")
_PRAGMA_TAIL_BYTES = 2048

# Source map v3 marker. Validated against the first 4 KiB of any candidate map
# body to reject SPA index.html fallbacks (200 OK + HTML) before writing to
# disk. See TLX bin/sourcemap_recon.py:111 — same validator, ported verbatim.
_SOURCEMAP_VERSION_REGEX = re.compile(rb'"version"\s*:\s*3')


def _looks_like_sourcemap(body: bytes, headers: dict[str, str]) -> bool:
    if not body:
        return False
    ctype = (headers.get("content-type") or "").lower()
    # Hard reject obvious HTML — SPA catch-all routes (Netlify, Vercel, CRA)
    # return 200 + index.html for missing .map paths.
    if "html" in ctype:
        return False
    head = body[:4096]
    if _SOURCEMAP_VERSION_REGEX.search(head):
        return True
    stripped = head.lstrip()
    return stripped.startswith(b"{") and b'"sources"' in head


class HarvestedAsset(BaseModel):
    url: str
    saved_to: Path
    map_saved_to: Path | None
    map_source: str | None


class HarvestResult(BaseModel):
    assets: list[HarvestedAsset]
    files: int
    maps_public: int
    maps_missing: list[str]
    hosts_seen: list[str]
    out_of_scope_skipped: list[str]
    pages_visited: list[str]
    webpack_chunks_found: int = 0
    webpack_diag: dict | None = None


def _host_port(parsed) -> str:
    if parsed.port is not None:
        return f"{parsed.hostname}:{parsed.port}"
    return parsed.hostname or ""


def _is_js_url(url: str, resource_type: str | None) -> bool:
    if resource_type == "script":
        return True
    path = urlparse(url).path.lower()
    return path.endswith(_JS_SUFFIXES)


def _path_for_save(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = _host_port(parsed)
    path = parsed.path.lstrip("/")
    if not path:
        path = "_root.js"
    if parsed.query:
        sha8 = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
        if "." in path:
            stem, dot, ext = path.rpartition(".")
            path = f"{stem}__{sha8}.{ext}"
        else:
            path = f"{path}__{sha8}"
    return host, path


def _extract_pragma(body: bytes) -> str | None:
    tail = body[-_PRAGMA_TAIL_BYTES:]
    matches = list(_SOURCEMAP_PRAGMA.finditer(tail))
    if not matches:
        return None
    target = matches[-1].group(1).decode("utf-8", errors="replace").strip()
    if target.startswith("data:"):
        return None
    return target


class Harvester:
    def __init__(
        self,
        scope: list[str],
        depth: int = 2,
        timeout_ms: int = 15000,
        user_agent: str | None = None,
        max_concurrency: int = 8,
        enable_webpack_chunk_enum: bool = False,
    ) -> None:
        self.scope = [s.lower() for s in scope]
        self.depth = depth
        self.timeout_ms = timeout_ms
        self.user_agent = user_agent
        # Concurrent in-flight `_fetch_asset` coroutines per page-load. Each
        # fetch does up to 4 HTTP requests (asset body + pragma/header/probe
        # sourcemap candidates), so the effective network parallelism is
        # ~max_concurrency * 4. Default chosen to saturate a typical CDN
        # without 429-ing single-host targets.
        self.max_concurrency = max(1, max_concurrency)
        # Webpack lazy-chunk enumeration is currently disabled: the brute
        # `wpr.u(0..20000)` walk drags in every numerically-IDed chunk
        # (e.g. 0..200+.bundle.js on Netlify) including ones the app never
        # actually reaches. Re-enable once the snippet does a smarter scan
        # (regex over webpack runtime / chunkLoadingGlobal seed only).
        self.enable_webpack_chunk_enum = enable_webpack_chunk_enum

    def _in_scope(self, url: str) -> bool:
        parsed = urlparse(url)
        return _host_port(parsed).lower() in self.scope

    async def acquire(self, url: str, raw_dir: Path) -> HarvestResult:
        if not self._in_scope(url):
            raise ValueError(f"URL out of scope: {url}")

        raw_dir.mkdir(parents=True, exist_ok=True)

        assets: dict[str, HarvestedAsset] = {}
        maps_missing: list[str] = []
        hosts_seen: set[str] = set()
        out_of_scope_skipped: set[str] = set()
        pages_visited: list[str] = []
        visited_urls: set[str] = set()
        webpack_chunks_found = 0
        webpack_diag: dict | None = None

        queue: list[tuple[str, int]] = [(urldefrag(url)[0], 0)]

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
            try:
                ctx_kwargs: dict = {}
                if self.user_agent:
                    ctx_kwargs["user_agent"] = self.user_agent
                context = await browser.new_context(**ctx_kwargs)
                try:
                    while queue:
                        page_url, page_depth = queue.pop(0)
                        if page_url in visited_urls:
                            continue
                        if not self._in_scope(page_url):
                            out_of_scope_skipped.add(urlparse(page_url).hostname or page_url)
                            continue
                        visited_urls.add(page_url)
                        pages_visited.append(page_url)

                        page = await context.new_page()
                        captured: list[tuple[str, str]] = []

                        def _on_request(req, sink=captured):
                            try:
                                sink.append((req.url, req.resource_type))
                            except Exception:
                                pass

                        page.on("request", _on_request)

                        try:
                            try:
                                await page.goto(
                                    page_url,
                                    wait_until="networkidle",
                                    timeout=self.timeout_ms,
                                )
                            except Exception:
                                pass

                            # Webpack lazy-chunk enumeration is opt-in (see
                            # ctor). The brute `wpr.u(0..20000)` walk drags in
                            # every numerically-IDed chunk Netlify-style apps
                            # have hundreds of, including ones the app never
                            # actually reaches. Disabled by default; re-enable
                            # once the snippet does a smarter scan.
                            if self.enable_webpack_chunk_enum:
                                try:
                                    enum_result = await enumerate_webpack_chunks(page)
                                    webpack_diag = enum_result.diag
                                    for chunk_url in enum_result.urls:
                                        abs_url = urljoin(page_url, chunk_url)
                                        captured.append((abs_url, "script"))
                                        webpack_chunks_found += 1
                                except Exception:
                                    if webpack_diag is None:
                                        webpack_diag = {"error": "enumerate_failed"}
                            else:
                                webpack_diag = {"disabled": True}

                            # Filter + dedupe captured URLs first, then fetch
                            # in parallel under a semaphore. The serial version
                            # of this loop blocked one chunk at a time, which
                            # turns a 200+ chunk SPA into a several-minute
                            # acquire. asset dict insertion / set updates are
                            # safe under asyncio (single-threaded event loop).
                            seen_js: set[str] = set()
                            to_fetch: list[str] = []
                            for req_url, rtype in captured:
                                if not _is_js_url(req_url, rtype):
                                    continue
                                clean = urldefrag(req_url)[0]
                                if clean in seen_js or clean in assets:
                                    continue
                                seen_js.add(clean)
                                if not self._in_scope(clean):
                                    out_of_scope_skipped.add(
                                        urlparse(clean).hostname or clean
                                    )
                                    continue
                                to_fetch.append(clean)

                            if to_fetch:
                                sem = asyncio.Semaphore(self.max_concurrency)

                                async def _fetch_one(
                                    clean_url: str,
                                ) -> tuple[str, HarvestedAsset | None]:
                                    async with sem:
                                        return clean_url, await self._fetch_asset(
                                            context, clean_url, raw_dir, maps_missing
                                        )

                                results = await asyncio.gather(
                                    *(_fetch_one(u) for u in to_fetch),
                                    return_exceptions=False,
                                )
                                for clean_url, asset in results:
                                    if asset is not None:
                                        assets[clean_url] = asset
                                        hosts_seen.add(_host_port(urlparse(clean_url)))

                            if page_depth < self.depth:
                                try:
                                    hrefs = await page.eval_on_selector_all(
                                        "a", "els => els.map(e => e.href)"
                                    )
                                except Exception:
                                    hrefs = []
                                origin = urlparse(page_url)
                                for href in hrefs:
                                    if not href:
                                        continue
                                    clean = urldefrag(href)[0]
                                    parsed = urlparse(clean)
                                    if parsed.scheme not in ("http", "https"):
                                        continue
                                    if not self._in_scope(clean):
                                        out_of_scope_skipped.add(
                                            parsed.hostname or clean
                                        )
                                        continue
                                    if parsed.netloc.lower() != origin.netloc.lower():
                                        continue
                                    if clean in visited_urls:
                                        continue
                                    queue.append((clean, page_depth + 1))
                        finally:
                            await page.close()
                finally:
                    await context.close()
            finally:
                await browser.close()

        sorted_assets = [assets[k] for k in sorted(assets)]
        maps_public = sum(1 for a in sorted_assets if a.map_saved_to is not None)

        return HarvestResult(
            assets=sorted_assets,
            files=len(sorted_assets),
            maps_public=maps_public,
            maps_missing=sorted(set(maps_missing)),
            hosts_seen=sorted(hosts_seen),
            out_of_scope_skipped=sorted(out_of_scope_skipped),
            pages_visited=pages_visited,
            webpack_chunks_found=webpack_chunks_found,
            webpack_diag=webpack_diag,
        )

    async def _fetch_asset(
        self,
        context,
        url: str,
        raw_dir: Path,
        maps_missing: list[str],
    ) -> HarvestedAsset | None:
        try:
            resp = await context.request.fetch(url, timeout=self.timeout_ms)
        except Exception:
            return None
        if not resp.ok:
            return None

        body = await resp.body()
        headers = {k.lower(): v for k, v in (resp.headers or {}).items()}

        host, path = _path_for_save(url)
        js_path = raw_dir / host / path
        js_path.parent.mkdir(parents=True, exist_ok=True)
        js_path.write_bytes(body)

        map_saved_to, map_source = await self._discover_map(
            context, url, body, headers, js_path, maps_missing
        )

        return HarvestedAsset(
            url=url,
            saved_to=js_path.resolve(),
            map_saved_to=map_saved_to,
            map_source=map_source,
        )

    async def _discover_map(
        self,
        context,
        js_url: str,
        body: bytes,
        headers: dict[str, str],
        js_path: Path,
        maps_missing: list[str],
    ) -> tuple[Path | None, str | None]:
        for source, candidate in self._map_candidates(js_url, body, headers):
            if candidate is None:
                continue
            if not self._in_scope(candidate):
                continue
            saved = await self._fetch_map(context, candidate, js_path)
            if saved is not None:
                return saved, source

        maps_missing.append(js_url)
        return None, None

    def _map_candidates(
        self, js_url: str, body: bytes, headers: dict[str, str]
    ):
        pragma = _extract_pragma(body)
        if pragma:
            yield "pragma", urljoin(js_url, pragma)

        hdr = headers.get("sourcemap") or headers.get("x-sourcemap")
        if hdr:
            yield "header", urljoin(js_url, hdr.strip())

        yield "probe", js_url + ".map"

    async def _fetch_map(self, context, map_url: str, js_path: Path) -> Path | None:
        try:
            resp = await context.request.fetch(map_url, timeout=self.timeout_ms)
        except Exception:
            return None
        if not resp.ok:
            return None
        body = await resp.body()
        headers = {k.lower(): v for k, v in (resp.headers or {}).items()}
        if not _looks_like_sourcemap(body, headers):
            return None
        map_path = js_path.with_suffix(js_path.suffix + ".map")
        map_path.write_bytes(body)
        return map_path.resolve()
