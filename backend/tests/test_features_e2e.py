"""Session 7 e2e: pre-seeded run + Function nodes → POST /features → record → EXECUTED_IN edges."""
from __future__ import annotations

import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import aiosqlite
import httpx
import pytest

from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.config import Settings
from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout


INDEX_HTML = """<!doctype html>
<html><body>
<button id="btn">go</button>
<script src="app.js"></script>
</body></html>
"""

APP_JS = """\
function add(a, b) { return a + b; }
function unused() { return 99; }
function run() { return add(1, 2); }
document.getElementById('btn').addEventListener('click', run);
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return


def _serve(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = type(
        "Bound",
        (_Quiet,),
        {
            "__init__": lambda self, *a, **kw: SimpleHTTPRequestHandler.__init__(
                self, *a, directory=str(directory), **kw
            )
        },
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


async def _seed_user(db: aiosqlite.Connection, github_id: int = 7000) -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, 'alice', NULL, strftime('%s','now'), strftime('%s','now'))",
        (github_id,),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = ?", (github_id,))
    return (await cur.fetchone())["id"]


async def _authed(
    client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> int:
    user_id = await _seed_user(db)
    sess = await create_session(db, user_id, settings.session_max_age_s)
    await db.commit()
    signer = make_signer(settings.session_secret)
    client.cookies.set(settings.session_cookie_name, sign_sid(signer, sess.id))
    return user_id


@pytest.mark.asyncio
async def test_feature_record_writes_executed_in_edges(
    app_client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    settings: Settings,
    tmp_path: Path,
) -> None:
    s = settings.model_copy(update={"runs_root": str(tmp_path / "runs")})
    app_client._transport.app.state.settings = s  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, s)

    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(INDEX_HTML)
    (site / "app.js").write_text(APP_JS)
    port = _free_port()
    server = _serve(site, port)
    try:
        run_id = "deadbeefcafe"
        await db.execute(
            "INSERT INTO runs (id, user_id, url, status, created_at) "
            "VALUES (?, ?, ?, 'done', ?)",
            (run_id, user_id, f"http://127.0.0.1:{port}/", int(time.time())),
        )
        await db.commit()

        layout = RunLayout(
            root=Path(s.runs_root).resolve(), user_id=f"u{user_id}", run_id=run_id
        )
        layout.create()
        with GraphStore(layout.graph_path) as g:
            for fn_id, name in [("fn_add", "add"), ("fn_unused", "unused"), ("fn_run", "run")]:
                g.add_node(
                    "Function",
                    {"id": fn_id, "name": name, "path": "app.js", "kind": "function_declaration", "start_line": 1, "end_line": 1},
                )

        cf = await app_client.post(
            f"/runs/{run_id}/features", json={"name": "click_btn"}
        )
        assert cf.status_code == 201, cf.text
        feature_id = cf.json()["id"]

        rec = await app_client.post(
            f"/runs/{run_id}/features/{feature_id}/record",
            json={
                "url": f"http://127.0.0.1:{port}/",
                "actions": [
                    {"type": "click", "selector": "#btn"},
                    {"type": "wait", "ms": 200},
                ],
            },
        )
        assert rec.status_code == 200, rec.text
        body = rec.json()
        assert body["last_status"] == "done"
        assert body["matched_functions"] >= 1, body
    finally:
        server.shutdown()

    with GraphStore(layout.graph_path) as g:
        rows = g.query(
            "MATCH (fn:Function)-[:EXECUTED_IN]->(f:Feature) RETURN fn.name AS name"
        )
    names = sorted(row["name"] for row in rows)
    assert "unused" not in names
    assert any(n in {"add", "run"} for n in names), names
