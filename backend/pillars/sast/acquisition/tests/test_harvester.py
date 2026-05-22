from __future__ import annotations

import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from backend.pillars.sast.acquisition.harvester import Harvester


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def _serve(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = lambda *a, **kw: _QuietHandler(*a, directory=str(directory), **kw)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def _write_basic_fixture(root: Path, *, with_pragma: bool, with_map: bool) -> None:
    pragma = "//# sourceMappingURL=app.js.map\n" if with_pragma else ""
    (root / "app.js").write_text(f"console.log('hi');\n{pragma}", encoding="utf-8")
    (root / "index.html").write_text(
        "<!doctype html><html><body><script src=\"app.js\"></script></body></html>",
        encoding="utf-8",
    )
    if with_map:
        (root / "app.js.map").write_text(
            '{"version":3,"file":"app.js","sources":["app.ts"],"sourcesContent":["x"],"mappings":""}',
            encoding="utf-8",
        )


async def test_harvest_basic_with_pragma_map(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_basic_fixture(docroot, with_pragma=True, with_map=True)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        harvester = Harvester(scope=[host])
        raw_dir = tmp_path / "raw"
        result = await harvester.acquire(f"http://{host}/", raw_dir)
    finally:
        server.shutdown()

    assert result.files == 1
    assert result.maps_public == 1
    assert len(result.assets) == 1
    asset = result.assets[0]
    assert asset.map_source == "pragma"
    assert asset.saved_to.exists()
    assert asset.map_saved_to is not None
    assert asset.map_saved_to.exists()
    assert result.maps_missing == []


async def test_harvest_map_via_probe(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_basic_fixture(docroot, with_pragma=False, with_map=True)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        harvester = Harvester(scope=[host])
        result = await harvester.acquire(f"http://{host}/", tmp_path / "raw")
    finally:
        server.shutdown()

    assert result.files == 1
    assert result.maps_public == 1
    assert result.assets[0].map_source == "probe"


async def test_missing_map_logged_not_crash(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_basic_fixture(docroot, with_pragma=False, with_map=False)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        harvester = Harvester(scope=[host])
        result = await harvester.acquire(f"http://{host}/", tmp_path / "raw")
    finally:
        server.shutdown()

    assert result.files == 1
    assert result.maps_public == 0
    assert result.maps_missing == [f"http://{host}/app.js"]
    assert result.assets[0].map_source is None


async def test_out_of_scope_skipped(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    (docroot / "app.js").write_text("console.log('hi');\n", encoding="utf-8")
    (docroot / "index.html").write_text(
        "<!doctype html><html><body>"
        "<a href=\"http://example.invalid/\">link</a>"
        "<script src=\"app.js\"></script>"
        "</body></html>",
        encoding="utf-8",
    )
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        harvester = Harvester(scope=[host], depth=2, timeout_ms=8000)
        result = await harvester.acquire(f"http://{host}/", tmp_path / "raw")
    finally:
        server.shutdown()

    assert result.files == 1
    assert "example.invalid" in result.out_of_scope_skipped


async def test_scope_violation_raises(tmp_path: Path) -> None:
    harvester = Harvester(scope=["other.local:80"])
    with pytest.raises(ValueError):
        await harvester.acquire("http://example.invalid/", tmp_path / "raw")


class _SpaFallbackHandler(SimpleHTTPRequestHandler):
    """Simulates an SPA host (Netlify-style) where any .map probe returns
    200 OK + the SPA index.html, not a real sourcemap."""

    SPA_HTML = (
        b"<!doctype html><html lang=\"en\"><head><title>SPA</title></head>"
        b"<body><div id=\"root\"></div><script src=\"/app.js\"></script>"
        b"</body></html>"
    )

    def log_message(self, format, *args):  # noqa: A002 - match base signature
        pass

    def do_GET(self) -> None:  # noqa: N802 - http.server uses do_GET
        if self.path.endswith(".map"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self.SPA_HTML)))
            self.end_headers()
            self.wfile.write(self.SPA_HTML)
            return
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = (
                b"<!doctype html><html><body>"
                b"<script src=\"app.js\"></script></body></html>"
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/app.js":
            body = b"console.log('hi');\n"  # no sourceMappingURL pragma
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # SPA catch-all: anything else returns the index too.
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.SPA_HTML)))
        self.end_headers()
        self.wfile.write(self.SPA_HTML)


def _serve_handler(handler_cls, port: int) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


async def test_spa_html_probe_rejected_as_map(tmp_path: Path) -> None:
    """Netlify-style SPA returns 200+HTML for any .map probe; harvester must
    reject it instead of writing HTML to disk as a fake sourcemap."""
    port = _free_port()
    server = _serve_handler(_SpaFallbackHandler, port)
    try:
        host = f"127.0.0.1:{port}"
        harvester = Harvester(scope=[host])
        raw_dir = tmp_path / "raw"
        result = await harvester.acquire(f"http://{host}/", raw_dir)
    finally:
        server.shutdown()

    assert result.files == 1
    asset = result.assets[0]
    assert asset.map_saved_to is None, (
        "harvester must NOT save HTML SPA fallback as a sourcemap"
    )
    assert asset.map_source is None
    assert result.maps_public == 0
    assert result.maps_missing == [f"http://{host}/app.js"]

    # Defense in depth: no .map file should exist on disk.
    map_files = list(raw_dir.rglob("*.map"))
    assert map_files == [], f"unexpected .map files written: {map_files}"
