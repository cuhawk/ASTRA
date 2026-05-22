"""End-to-end smoke: serve the react-min fixture → run Pipeline → assert reconstructed App.tsx."""
from __future__ import annotations

import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
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
