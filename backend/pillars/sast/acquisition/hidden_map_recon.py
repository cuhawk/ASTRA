# vendored-from: https://github.com/cuhawk/tlxkull
# upstream-path: bin/sourcemap_recon.py
# upstream-sha:  83cae232b94e7998ef543c72e8e7302617d438a0
# imported-on:   2026-05-23
# license:       proprietary — see upstream repo
# modifications: dropped status.json/_lib (replaced with HiddenMapReconResult pydantic model); scope passed via constructor like Harvester._in_scope; httpx async client in place of urllib (stays consistent with rest of acquisition layer); private is_sourcemap_body kept (mirrors TLX byte-level behavior; harvester has an equivalent _looks_like_sourcemap but takes headers and is HTML-aware — different contract); brute templates / Sentry / 429 backoff / per-bundle cap behavior unchanged; added per-run URL dedupe so bundle-sibling and per-host-template probes that resolve to the same URL fire once
"""Hidden-sourcemap brute + Sentry release-artifact recon.

Augments :mod:`backend.pillars.sast.acquisition.harvester` by brute-forcing
common Webpack/Vite/Next/Nuxt hidden-map filenames next to each bundled .js,
and by pulling .map files from any in-scope Sentry release-artifact API.

Run after :class:`Harvester.acquire` against the same ``raw_dir``. Walks
``raw_dir/<host>/<path>/*.js`` files that lack a sibling ``.map``, tries
brute paths, and writes recovered maps alongside the bundle.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from pathlib import Path

import httpx
from pydantic import BaseModel

# Brute templates: kept VERBATIM from TLX bin/sourcemap_recon.py:45-60. Do not
# invent new ones — the upstream list is the list.
BRUTE_TEMPLATES_PER_BUNDLE = (
    "{base}.js.map",
    "{base}.min.js.map",
)

BRUTE_TEMPLATES_PER_HOST = (
    "assets/index.js.map",
    "static/js/main.chunk.js.map",
    "static/js/bundle.js.map",
    "debug.js.map",
    "app.js.map",
    "main.js.map",
    "vendor.js.map",
    "runtime.js.map",
    "polyfills.js.map",
)

SENTRY_HOST_REGEX = re.compile(
    r"https?://([a-z0-9.-]*sentry[a-z0-9.-]*)/", re.IGNORECASE
)
SENTRY_DSN_REGEX = re.compile(
    r"https?://([a-f0-9]+)@([a-z0-9.-]+)/(\d+)", re.IGNORECASE
)
# Private duplicate of harvester._SOURCEMAP_VERSION_REGEX — kept here so this
# module mirrors TLX bin/sourcemap_recon.py:68 byte-for-byte. Importing the
# harvester would couple the recon module to harvester internals; the regex is
# one line, so duplication is cheaper than coupling.
SOURCE_MAP_VERSION_REGEX = re.compile(rb'"version"\s*:\s*3')


class HiddenMapReconResult(BaseModel):
    """Mirrors what TLX's ``status.json.phases.sourcemap_recon`` records."""

    status: str
    bundles_processed: int
    maps_recovered: int
    maps_missing: int
    requests_total: int
    out_of_scope_hosts_skipped: list[str]
    sentry: dict
    found: list[dict]


def is_sourcemap_body(body: bytes) -> bool:
    """Sniff a candidate response body for source-map-v3 shape.

    Verbatim from TLX bin/sourcemap_recon.py:111. First 4 KiB only — the v3
    ``"version":3`` marker is enough; the JSON-with-``"sources"`` fallback
    handles minified maps that don't put version first.
    """
    if not body:
        return False
    head = body[:4096]
    if SOURCE_MAP_VERSION_REGEX.search(head):
        return True
    return head.lstrip().startswith(b"{") and b'"sources"' in head


def _bundle_local_candidates(js_path: Path) -> Iterable[str]:
    """Yield per-bundle brute filenames, in TLX order."""
    name = js_path.name
    if not name.endswith(".js"):
        return
    base_no_ext = name[:-3]
    for tpl in BRUTE_TEMPLATES_PER_BUNDLE:
        cand = tpl.format(base=base_no_ext)
        if cand != name:
            yield cand


def _build_candidate_url(scheme: str, host: str, rel_dir: Path, filename: str) -> str:
    rel_str = "" if str(rel_dir) == "." else str(rel_dir).replace("\\", "/").strip("/")
    if rel_str:
        return f"{scheme}://{host}/{rel_str}/{filename}"
    return f"{scheme}://{host}/{filename}"


def detect_sentry(raw_root: Path) -> set[tuple[str, str | None]]:
    """Scan every ``*.js`` under ``raw_root`` for Sentry host references.

    Returns ``{(host, project_id_or_None)}``. DSN secrets are dropped — only
    the host and numeric project id are retained, matching TLX behavior. The
    caller is responsible for scope-checking the host before any network call.
    """
    found: set[tuple[str, str | None]] = set()
    for js in raw_root.rglob("*.js"):
        try:
            content = js.read_bytes().decode("utf-8", errors="ignore")
        except OSError:
            continue
        for m in SENTRY_HOST_REGEX.finditer(content):
            found.add((m.group(1).lower(), None))
        for m in SENTRY_DSN_REGEX.finditer(content):
            # m.group(1) is the DSN key — explicitly NOT stored or logged.
            found.add((m.group(2).lower(), m.group(3)))
    return found


def _host_from_raw_path(rel: Path, raw_root: Path) -> str | None:
    try:
        parts = rel.relative_to(raw_root).parts
    except ValueError:
        return None
    return parts[0] if parts else None


class HiddenMapRecon:
    """Brute-force hidden sourcemap recovery + Sentry artifact pull.

    Public surface:
        recon = HiddenMapRecon(scope=["example.com"])
        result = await recon.run(raw_dir)

    ``raw_dir`` is the same directory ``Harvester.acquire`` writes into;
    layout is ``raw_dir/<host>/<path>/file.js``. Recovered ``.map`` files
    are written alongside the bundle.
    """

    def __init__(
        self,
        scope: list[str],
        timeout_s: float = 8.0,
        rate_limit_ms: int = 200,
        max_attempts_per_bundle: int = 40,
        user_agent: str = "Mozilla/5.0 (compatible; astra-hidden-map-recon/1.0)",
        sentry_enabled: bool = True,
        backoff_429_s: float = 2.0,
    ) -> None:
        self.scope = [s.lower() for s in scope]
        self.timeout_s = timeout_s
        self.rate_limit_ms = rate_limit_ms
        self.max_attempts_per_bundle = max_attempts_per_bundle
        self.user_agent = user_agent
        self.sentry_enabled = sentry_enabled
        self.backoff_429_s = backoff_429_s
        # Default to https; tests flip to http for local ThreadingHTTPServer.
        self._scheme = "https"

    def _host_in_scope(self, host: str) -> bool:
        """Mirrors Harvester._in_scope: lowercased host[:port] exact match."""
        return host.lower() in self.scope

    async def _http_get(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        max_bytes: int | None = None,
    ) -> tuple[int, bytes, dict]:
        """Async equivalent of TLX bin/sourcemap_recon.py:97 http_get.

        Returns ``(status, body, headers)``. On transport error, status is 0.
        ``max_bytes`` caps the read.
        """
        try:
            r = await client.get(url, timeout=self.timeout_s)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            return 0, b"", {"_err": str(e)}
        body = r.content[:max_bytes] if max_bytes else r.content
        return r.status_code, body, dict(r.headers)

    def _save_map(self, raw_root: Path, host: str, rel_path: str, body: bytes) -> Path:
        out = raw_root / host / rel_path.lstrip("/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(body)
        return out

    async def run(self, raw_dir: Path) -> HiddenMapReconResult:
        """Walk ``raw_dir``, brute-force hidden maps, optionally pull Sentry artifacts.

        Idempotent re: bundles that already have a sibling ``.map`` — those are
        skipped.
        """
        if not raw_dir.exists():
            return HiddenMapReconResult(
                status="error",
                bundles_processed=0,
                maps_recovered=0,
                maps_missing=0,
                requests_total=0,
                out_of_scope_hosts_skipped=[],
                sentry={"hosts_seen": [], "releases_enumerated": [], "files_pulled": 0},
                found=[],
            )

        found: list[dict] = []
        missing_bundles: list[str] = []
        skipped_oos: set[str] = set()
        bundles_processed = 0
        requests_total = 0
        rate = self.rate_limit_ms / 1000
        host_root_done: set[str] = set()
        # Dedupe URL probes within a single run — same URL appearing as both
        # a bundle-sibling candidate AND a per-host template should fire once.
        probed_urls: set[str] = set()

        headers = {"User-Agent": self.user_agent}
        async with httpx.AsyncClient(
            headers=headers, follow_redirects=True
        ) as client:
            for js in sorted(raw_dir.rglob("*.js")):
                if js.suffix != ".js":
                    continue
                if js.with_suffix(".js.map").exists():
                    continue
                host = _host_from_raw_path(js, raw_dir)
                if not host:
                    continue
                if not self._host_in_scope(host):
                    skipped_oos.add(host)
                    continue

                bundles_processed += 1
                rel_dir = js.relative_to(raw_dir / host).parent
                bundle_rel = str(js.relative_to(raw_dir))
                attempts = 0
                recovered = False

                for cand_name in _bundle_local_candidates(js):
                    if attempts >= self.max_attempts_per_bundle:
                        break
                    cand_url = _build_candidate_url(
                        self._scheme, host, rel_dir, cand_name
                    )
                    attempts += 1
                    if cand_url in probed_urls:
                        continue
                    probed_urls.add(cand_url)
                    requests_total += 1
                    if rate:
                        await asyncio.sleep(rate)
                    code, body, _ = await self._http_get(
                        client, cand_url, max_bytes=8 * 1024 * 1024
                    )
                    if code == 429:
                        await asyncio.sleep(self.backoff_429_s)
                        # TLX semantics: 429 consumes the slot, move on to the
                        # next candidate. The per-host-root loop below will
                        # also exercise the backoff for the same host.
                        continue
                    if code == 200 and is_sourcemap_body(body):
                        rel_path = (
                            f"{rel_dir}/{cand_name}"
                            if str(rel_dir) != "."
                            else cand_name
                        )
                        self._save_map(raw_dir, host, rel_path, body)
                        found.append(
                            {
                                "url": cand_url,
                                "saved_to": rel_path,
                                "bundle": bundle_rel,
                            }
                        )
                        recovered = True
                        break

                if not recovered:
                    missing_bundles.append(bundle_rel)

                if host not in host_root_done:
                    host_root_done.add(host)
                    for tpl in BRUTE_TEMPLATES_PER_HOST:
                        # Skip per-host templates whose target path already
                        # exists on disk — either pre-existing (harvested
                        # earlier) or just recovered via a bundle-sibling
                        # probe in this run. Prevents double-counting the
                        # same .map and saves a network request.
                        target_path = raw_dir / host / tpl.lstrip("/")
                        if target_path.exists():
                            continue
                        cand_url = f"{self._scheme}://{host}/{tpl}"
                        if cand_url in probed_urls:
                            continue
                        probed_urls.add(cand_url)
                        requests_total += 1
                        if rate:
                            await asyncio.sleep(rate)
                        code, body, _ = await self._http_get(
                            client, cand_url, max_bytes=8 * 1024 * 1024
                        )
                        if code == 429:
                            await asyncio.sleep(self.backoff_429_s)
                            # Retry once after backoff to mirror TLX's "sleep
                            # and continue scanning" semantics — a 429 should
                            # not block recovery of a real map served at the
                            # next probe.
                            code, body, _ = await self._http_get(
                                client, cand_url, max_bytes=8 * 1024 * 1024
                            )
                            if code == 429:
                                continue
                        if code == 200 and is_sourcemap_body(body):
                            self._save_map(raw_dir, host, tpl, body)
                            found.append(
                                {
                                    "url": cand_url,
                                    "saved_to": tpl,
                                    "bundle": "<host-root>",
                                }
                            )

            sentry_results: dict = {
                "hosts_seen": [],
                "releases_enumerated": [],
                "files_pulled": 0,
            }
            if self.sentry_enabled:
                for sentry_host, _proj in detect_sentry(raw_dir):
                    in_scope = self._host_in_scope(sentry_host)
                    sentry_results["hosts_seen"].append(
                        {"host": sentry_host, "in_scope": in_scope}
                    )
                    if not in_scope:
                        continue
                    requests_total += 1
                    if rate:
                        await asyncio.sleep(rate)
                    versions = await self._enumerate_sentry_releases(
                        client, sentry_host
                    )
                    sentry_results["releases_enumerated"].extend(versions)

        return HiddenMapReconResult(
            status="done",
            bundles_processed=bundles_processed,
            maps_recovered=len(found),
            maps_missing=len(missing_bundles),
            requests_total=requests_total,
            out_of_scope_hosts_skipped=sorted(skipped_oos),
            sentry=sentry_results,
            found=found,
        )

    async def _enumerate_sentry_releases(
        self, client: httpx.AsyncClient, host: str
    ) -> list[str]:
        """Best-effort Sentry release listing. Ported from TLX:134.

        Returns release tags as ``"<org>/<project>::<version>"``. No DSN keys
        are accepted or transmitted — public-API only.
        """
        code, body, _ = await self._http_get(
            client, f"{self._scheme}://{host}/api/0/projects/"
        )
        if code != 200 or not body:
            return []
        try:
            projects = json.loads(body)
        except json.JSONDecodeError:
            return []
        versions: list[str] = []
        rate = self.rate_limit_ms / 1000
        for proj in projects[:5]:
            org = proj.get("organization", {}).get("slug")
            slug = proj.get("slug")
            if not (org and slug):
                continue
            if rate:
                await asyncio.sleep(rate)
            code, body, _ = await self._http_get(
                client,
                f"{self._scheme}://{host}/api/0/projects/{org}/{slug}/releases/?per_page=20",
            )
            if code != 200:
                continue
            try:
                for rel in json.loads(body):
                    versions.append(f"{org}/{slug}::{rel['version']}")
            except (json.JSONDecodeError, KeyError):
                continue
        return versions
