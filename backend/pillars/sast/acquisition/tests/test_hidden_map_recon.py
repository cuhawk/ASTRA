from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backend.pillars.sast.acquisition.hidden_map_recon import (
    HiddenMapRecon,
    detect_sentry,
)

VALID_MAP_BODY = (
    b'{"version":3,"file":"app.js","sources":["app.ts"],'
    b'"sourcesContent":["x"],"mappings":""}'
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _serve(handler_cls, port: int) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def _write_bundle(raw_dir: Path, host: str, rel: str, body: bytes) -> Path:
    p = raw_dir / host / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return p


class _SiblingMapHandler(BaseHTTPRequestHandler):
    """Serves a valid .map at /app.js.map; 404 for everything else."""

    requests_seen: list[str] = []

    def log_message(self, format, *args):  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        self.__class__.requests_seen.append(self.path)
        if self.path == "/app.js.map":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(VALID_MAP_BODY)))
            self.end_headers()
            self.wfile.write(VALID_MAP_BODY)
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


class _SpaFallbackHandler(BaseHTTPRequestHandler):
    """Netlify-style: 200+HTML for every .map path."""

    SPA_HTML = (
        b"<!doctype html><html><body><div id=\"root\"></div>"
        b"<script src=\"/app.js\"></script></body></html>"
    )

    def log_message(self, format, *args):  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        # ALL paths return SPA HTML with 200 — including .map probes.
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.SPA_HTML)))
        self.end_headers()
        self.wfile.write(self.SPA_HTML)


class _BackoffHandler(BaseHTTPRequestHandler):
    """First .map probe returns 429, subsequent .map probes return 200+valid map."""

    map_calls = 0

    def log_message(self, format, *args):  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path.endswith(".map"):
            self.__class__.map_calls += 1
            if self.__class__.map_calls == 1:
                self.send_response(429)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(VALID_MAP_BODY)))
            self.end_headers()
            self.wfile.write(VALID_MAP_BODY)
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


class _AllNotFoundHandler(BaseHTTPRequestHandler):
    """Returns 404 for everything. Counts every request."""

    requests_seen: list[str] = []

    def log_message(self, format, *args):  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        self.__class__.requests_seen.append(self.path)
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


async def test_recovers_hidden_map_at_bundle_sibling(tmp_path: Path) -> None:
    _SiblingMapHandler.requests_seen = []
    port = _free_port()
    server = _serve(_SiblingMapHandler, port)
    try:
        host = f"127.0.0.1:{port}"
        raw_dir = tmp_path / "raw"
        # Bundle with NO sourceMappingURL pragma; harvester left it map-less.
        _write_bundle(raw_dir, host, "app.js", b"console.log('hi');\n")

        recon = HiddenMapRecon(scope=[host], rate_limit_ms=0)
        # Override scheme to http for local testing.
        recon._scheme = "http"
        result = await recon.run(raw_dir)
    finally:
        server.shutdown()

    assert result.bundles_processed == 1
    assert result.maps_recovered == 1
    saved = raw_dir / host / "app.js.map"
    assert saved.exists()
    assert saved.read_bytes() == VALID_MAP_BODY


async def test_rejects_spa_html_fallback(tmp_path: Path) -> None:
    port = _free_port()
    server = _serve(_SpaFallbackHandler, port)
    try:
        host = f"127.0.0.1:{port}"
        raw_dir = tmp_path / "raw"
        _write_bundle(raw_dir, host, "app.js", b"console.log('hi');\n")

        recon = HiddenMapRecon(scope=[host], rate_limit_ms=0)
        recon._scheme = "http"
        result = await recon.run(raw_dir)
    finally:
        server.shutdown()

    assert result.maps_recovered == 0
    map_files = list(raw_dir.rglob("*.map"))
    assert map_files == [], f"unexpected .map files written: {map_files}"


async def test_429_backoff(tmp_path: Path) -> None:
    _BackoffHandler.map_calls = 0
    port = _free_port()
    server = _serve(_BackoffHandler, port)
    try:
        host = f"127.0.0.1:{port}"
        raw_dir = tmp_path / "raw"
        _write_bundle(raw_dir, host, "app.js", b"console.log('hi');\n")

        # Use a short backoff to keep test fast.
        recon = HiddenMapRecon(
            scope=[host], rate_limit_ms=0, backoff_429_s=0.05
        )
        recon._scheme = "http"
        result = await recon.run(raw_dir)
    finally:
        server.shutdown()

    # Handler returns 429 once then 200+valid map; recon must recover at
    # least one map (the backoff path was exercised on the first probe).
    assert result.maps_recovered >= 1, (
        f"expected recovery after 429 backoff, got {result}"
    )
    assert _BackoffHandler.map_calls >= 2, "backoff path must retry after 429"


async def test_per_bundle_cap(tmp_path: Path) -> None:
    _AllNotFoundHandler.requests_seen = []
    port = _free_port()
    server = _serve(_AllNotFoundHandler, port)
    try:
        host = f"127.0.0.1:{port}"
        raw_dir = tmp_path / "raw"
        _write_bundle(raw_dir, host, "app.js", b"console.log('hi');\n")

        cap = 1
        recon = HiddenMapRecon(
            scope=[host],
            rate_limit_ms=0,
            max_attempts_per_bundle=cap,
        )
        recon._scheme = "http"
        result = await recon.run(raw_dir)
    finally:
        server.shutdown()

    # Per-bundle attempts must respect the cap. With dedupe in the recon,
    # the same URL appearing as both a per-bundle candidate and a per-host
    # template fires once — so the count of probes to a per-bundle sibling
    # path is bounded by the cap.
    assert result.maps_recovered == 0
    siblings = [
        p for p in _AllNotFoundHandler.requests_seen
        if p in ("/app.js.map", "/app.min.js.map")
    ]
    assert len(siblings) <= cap, (
        f"per-bundle attempts {len(siblings)} exceeded cap {cap}: {siblings}"
    )


async def test_out_of_scope_hosts_skipped(tmp_path: Path) -> None:
    _SiblingMapHandler.requests_seen = []
    port = _free_port()
    server = _serve(_SiblingMapHandler, port)
    try:
        host_in = f"127.0.0.1:{port}"
        host_out = "out-of-scope.invalid"
        raw_dir = tmp_path / "raw"
        _write_bundle(raw_dir, host_in, "app.js", b"console.log('hi');\n")
        _write_bundle(raw_dir, host_out, "app.js", b"console.log('hi');\n")

        recon = HiddenMapRecon(scope=[host_in], rate_limit_ms=0)
        recon._scheme = "http"
        result = await recon.run(raw_dir)
    finally:
        server.shutdown()

    assert host_out in result.out_of_scope_hosts_skipped
    # Only the in-scope bundle should have produced HTTP requests for siblings.
    # The local server only sees in-scope traffic by construction (out-of-scope
    # host isn't routed to it); just assert recon recorded the skip and only
    # processed the in-scope bundle.
    assert result.bundles_processed == 1
    assert result.maps_recovered == 1


def test_detect_sentry_finds_dsn(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    host = "example.com"
    bundle = raw_dir / host / "app.js"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    # Realistic-looking DSN embedded in a bundle.
    bundle.write_text(
        "var s = {dsn:'https://deadbeef0123@sentry.example.com/42'};"
        "Sentry.init(s);",
        encoding="utf-8",
    )
    found = detect_sentry(raw_dir)
    hosts = {h for h, _ in found}
    assert "sentry.example.com" in hosts
