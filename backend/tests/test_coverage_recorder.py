from __future__ import annotations

import json
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backend.coverage.recorder import Action, CoverageRecorder, CoverageResult


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


_APP_JS_PASSIVE = """function add(a, b) { return a + b; }
function unused() { return 99; }
window.run = function run() { return add(1, 2); };
"""

_APP_JS_CLICK = """function add(a, b) { return a + b; }
function unused() { return 99; }
window.run = function run() { return add(1, 2); };
document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('run-btn').addEventListener('click', window.run);
});
"""

_INDEX_HTML = """<!doctype html>
<html><body>
<button id="run-btn">go</button>
<script src="app.js"></script>
</body></html>
"""

_INDEX_HTML_WITH_EXTERNAL = """<!doctype html>
<html><body>
<button id="run-btn">go</button>
<script src="app.js"></script>
<script src="https://example.invalid/cdn.js"></script>
</body></html>
"""


def _write_fixture(root: Path, *, app_js: str, html: str = _INDEX_HTML) -> None:
    (root / "app.js").write_text(app_js, encoding="utf-8")
    (root / "index.html").write_text(html, encoding="utf-8")


def _find_app_entry(result: CoverageResult):
    matches = [e for e in result.entries if "app.js" in e.url]
    assert matches, f"no app.js entry in {[e.url for e in result.entries]}"
    return matches[0]


def _function_names(entry) -> set[str]:
    return {fn.get("functionName", "") for fn in entry.functions}


async def test_coverage_captures_declared_functions(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_fixture(docroot, app_js=_APP_JS_PASSIVE)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        rec = CoverageRecorder(scope=[host])
        result = await rec.record(
            start_url=f"http://{host}/index.html",
            actions=[Action(type="wait", ms=100)],
            feature_name="declared",
            save_to=tmp_path / "cov",
        )
    finally:
        server.shutdown()

    app_entry = _find_app_entry(result)
    names = _function_names(app_entry)
    assert {"add", "unused", "run"}.issubset(names), names


async def test_coverage_separates_called_from_uncalled(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_fixture(docroot, app_js=_APP_JS_CLICK)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        rec = CoverageRecorder(scope=[host])
        result = await rec.record(
            start_url=f"http://{host}/index.html",
            actions=[
                Action(type="wait", ms=100),
                Action(type="click", selector="#run-btn"),
                Action(type="wait", ms=100),
            ],
            feature_name="clicked",
            save_to=tmp_path / "cov",
        )
    finally:
        server.shutdown()

    app_entry = _find_app_entry(result)
    by_name = {fn.get("functionName", ""): fn for fn in app_entry.functions}
    assert "add" in by_name, list(by_name)
    assert "unused" in by_name, list(by_name)

    add_count = max(r.get("count", 0) for r in by_name["add"].get("ranges") or [{"count": 0}])
    unused_count = max(
        r.get("count", 0) for r in by_name["unused"].get("ranges") or [{"count": 0}]
    )
    assert add_count > 0, by_name["add"]
    assert unused_count == 0, by_name["unused"]


async def test_out_of_scope_entries_filtered(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_fixture(docroot, app_js=_APP_JS_PASSIVE, html=_INDEX_HTML_WITH_EXTERNAL)
    port = _free_port()
    server = _serve(docroot, port)
    try:
        host = f"127.0.0.1:{port}"
        rec = CoverageRecorder(scope=[host])
        result = await rec.record(
            start_url=f"http://{host}/index.html",
            actions=[Action(type="wait", ms=150)],
            feature_name="scoped",
            save_to=tmp_path / "cov",
        )
    finally:
        server.shutdown()

    assert result.entries, "expected at least one in-scope entry"
    for entry in result.entries:
        from urllib.parse import urlparse

        assert urlparse(entry.url).netloc.lower() == host.lower(), entry.url


async def test_writes_coverage_json(tmp_path: Path) -> None:
    docroot = tmp_path / "site"
    docroot.mkdir()
    _write_fixture(docroot, app_js=_APP_JS_PASSIVE)
    port = _free_port()
    server = _serve(docroot, port)
    save_to = tmp_path / "cov"
    feature = "json_out"
    try:
        host = f"127.0.0.1:{port}"
        rec = CoverageRecorder(scope=[host])
        result = await rec.record(
            start_url=f"http://{host}/index.html",
            actions=[Action(type="wait", ms=100)],
            feature_name=feature,
            save_to=save_to,
        )
    finally:
        server.shutdown()

    out_file = save_to / f"{feature}.json"
    assert out_file.exists(), f"missing {out_file}"
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    parsed = CoverageResult.model_validate(payload)
    assert parsed.feature_name == feature
    assert parsed.captured_at == result.captured_at
    assert len(parsed.entries) == len(result.entries)
