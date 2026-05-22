"""End-to-end smoke: serve the react-min fixture → run Pipeline → assert reconstructed App.tsx."""
from __future__ import annotations

import socket
import threading
from http.server import (
    BaseHTTPRequestHandler,
    SimpleHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path

import pytest

from backend.pillars.memory.runs import RunLayout
from backend.pillars.sast.acquisition import Pipeline

_FIXTURE_DIST = (
    Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "react-min" / "dist"
)
_MARKER = "ASTRA_FIXTURE_MARKER"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return


def _serve(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = type(
        "Bound",
        (_QuietHandler,),
        {"__init__": lambda self, *a, **kw: SimpleHTTPRequestHandler.__init__(
            self, *a, directory=str(directory), **kw
        )},
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.mark.asyncio
async def test_pipeline_reconstructs_app_tsx(tmp_path: Path) -> None:
    assert _FIXTURE_DIST.is_dir(), f"fixture missing: {_FIXTURE_DIST}"

    port = _free_port()
    server = _serve(_FIXTURE_DIST, port)
    try:
        layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1")
        pipeline = Pipeline(scope=[f"127.0.0.1:{port}"], depth=1)
        result = await pipeline.acquire(f"http://127.0.0.1:{port}/", layout)
    finally:
        server.shutdown()

    assert result.harvest.files >= 1, result.harvest
    assert result.harvest.maps_public >= 1, result.harvest
    assert result.sourcemap.original_files >= 1, result.sourcemap

    app_tsx = layout.sourcemap_dir / "src" / "App.tsx"
    assert app_tsx.is_file(), f"expected reconstructed App.tsx at {app_tsx}; sourcemap dir = {list(layout.sourcemap_dir.rglob('*'))}"
    assert _MARKER in app_tsx.read_text()


def _serve_handler(handler_cls: type, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.mark.asyncio
async def test_pipeline_hidden_recon_runs_when_harvester_misses_map(
    tmp_path: Path,
) -> None:
    """Tighter assertion: build a fixture where the harvester definitively
    misses the map (no pragma, probe path returns 404) but hidden-map recon
    finds it at one of the per-host template paths. Confirms recon is wired
    in and contributes when harvester alone is not enough."""

    class _RecoverableHandler(BaseHTTPRequestHandler):
        INDEX = (
            b"<!doctype html><html><body>"
            b"<script src=\"/app.js\"></script>"
            b"</body></html>"
        )
        # No pragma.
        JS = b"console.log('hi');\n"
        # Map lives at one of the per-host brute templates:
        # ``static/js/bundle.js.map`` (CRA legacy). Harvester would never
        # find this without recon.
        MAP = (
            b'{"version":3,"file":"app.js","sources":["src/recovered.ts"],'
            b'"sourcesContent":["// RECOVERED_BY_HIDDEN_MAP_RECON\\n"],'
            b'"mappings":"AAAA"}'
        )

        def log_message(self, *_args: object) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(self.INDEX, "text/html")
            elif path == "/app.js":
                self._send(self.JS, "application/javascript")
            elif path == "/static/js/bundle.js.map":
                self._send(self.MAP, "application/json")
            else:
                # Including /app.js.map → 404 so the harvester probe fails
                # and only the recon per-host brute can succeed.
                self.send_error(404)

        def _send(self, body: bytes, ctype: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    port = _free_port()
    server = _serve_handler(_RecoverableHandler, port)
    try:
        host = f"127.0.0.1:{port}"
        layout = RunLayout(root=tmp_path, user_id="u1", run_id="r1")
        pipeline = Pipeline(scope=[host], depth=1)

        from backend.pillars.sast.acquisition.hidden_map_recon import HiddenMapRecon

        original_init = HiddenMapRecon.__init__

        def _http_init(self: HiddenMapRecon, *a: object, **kw: object) -> None:
            original_init(self, *a, **kw)
            self._scheme = "http"

        HiddenMapRecon.__init__ = _http_init  # type: ignore[method-assign]
        try:
            result = await pipeline.acquire(f"http://{host}/", layout)
        finally:
            HiddenMapRecon.__init__ = original_init  # type: ignore[method-assign]
    finally:
        server.shutdown()

    # Harvester probe path returned 404 for /app.js.map.
    assert result.harvest.maps_public == 0, result.harvest
    # Hidden-map recon must have recovered exactly 1 map via the per-host
    # ``static/js/bundle.js.map`` template.
    assert result.hidden_map_recon.maps_recovered >= 1, result.hidden_map_recon
    # Sourcemap explode picked the recovered map up and reconstructed.
    recovered = list(layout.sourcemap_dir.rglob("recovered.ts"))
    assert recovered, (
        f"expected src/recovered.ts; sourcemap dir: "
        f"{list(layout.sourcemap_dir.rglob('*'))}"
    )
    assert b"RECOVERED_BY_HIDDEN_MAP_RECON" in recovered[0].read_bytes()
