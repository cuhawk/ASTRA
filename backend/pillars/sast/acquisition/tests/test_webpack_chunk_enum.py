from __future__ import annotations

import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright

from backend.pillars.sast.acquisition.harvester import Harvester
from backend.pillars.sast.acquisition.webpack_chunk_enum import (
    WebpackChunkEnumResult,
    enumerate_webpack_chunks,
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        pass


def _serve(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = lambda *a, **kw: _QuietHandler(*a, directory=str(directory), **kw)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


# A hand-rolled minimal webpack-shaped runtime. Mimics two things real webpack
# bundles expose:
#   1) window.__webpack_require__ with a .u(id) chunk-URL function and .p public path.
#   2) A webpackChunk_N_E push-array with a seed module-id tuple so the snippet's
#      strategy-2 hijack path is also exercised.
_WEBPACK_RUNTIME_HTML = """<!doctype html>
<html><body>
<script>
  // Strategy-1 surface: direct __webpack_require__
  window.__webpack_require__ = {
    u: function (id) { return "static/js/" + id + ".chunk.js"; },
    p: "/"
  };
  // Strategy-2 surface: chunk push array with seed ids
  window.webpackChunk_N_E = [
    [[42, 7, 1234], { "42": function () {}, "7": function () {} }, function (req) {}]
  ];
</script>
</body></html>
"""


def _write_webpack_fixture(root: Path) -> None:
    (root / "index.html").write_text(_WEBPACK_RUNTIME_HTML, encoding="utf-8")
    chunks_dir = root / "static" / "js"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    # Seed a handful of chunk files at the URLs the runtime claims to know.
    for cid in (0, 1, 7, 42, 1234):
        (chunks_dir / f"{cid}.chunk.js").write_text(
            f"// chunk {cid}\nconsole.log('chunk {cid}');\n",
            encoding="utf-8",
        )


def _write_plain_fixture(root: Path) -> None:
    (root / "index.html").write_text(
        "<!doctype html><html><body><p>no webpack here</p></body></html>",
        encoding="utf-8",
    )


async def test_enum_returns_urls_on_webpack_runtime(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_webpack_fixture(docroot)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
            try:
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(f"http://{host}/", wait_until="networkidle", timeout=15000)
                result = await enumerate_webpack_chunks(page)
            finally:
                await browser.close()
    finally:
        server.shutdown()

    assert isinstance(result, WebpackChunkEnumResult)
    assert result.error is None
    assert result.diag["wpr_present"] is True
    assert result.diag["wpr_u_present"] is True
    assert len(result.urls) > 0
    # snippet joins with wpr.p = "/", so relative chunk URLs become absolute paths.
    assert any(u.endswith("/static/js/0.chunk.js") or u == "/static/js/0.chunk.js" for u in result.urls)


async def test_enum_swallows_missing_webpack(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_plain_fixture(docroot)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
            try:
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(f"http://{host}/", wait_until="networkidle", timeout=15000)
                result = await enumerate_webpack_chunks(page)
            finally:
                await browser.close()
    finally:
        server.shutdown()

    assert isinstance(result, WebpackChunkEnumResult)
    assert result.urls == []
    assert result.diag.get("wpr_present") is False


async def test_harvester_integrates_chunks(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_webpack_fixture(docroot)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        harvester = Harvester(scope=[host], depth=0)
        raw_dir = tmp_path / "raw"
        result = await harvester.acquire(f"http://{host}/", raw_dir)
    finally:
        server.shutdown()

    assert result.webpack_chunks_found > 0
    assert result.webpack_diag is not None
    assert result.webpack_diag.get("wpr_present") is True

    # At least one chunk file actually fetched to disk.
    chunk_files = list(raw_dir.rglob("*.chunk.js"))
    assert len(chunk_files) > 0, "expected at least one webpack chunk fetched to raw_dir"
