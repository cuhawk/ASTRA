"""Session 9 e2e: pre-seeded run + Function nodes → /cypher, /nl, /playbooks, /advise."""
from __future__ import annotations

import re
import time
from pathlib import Path

import aiosqlite
import httpx
import pytest

from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.config import Settings
from backend.db.connection import connect
from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout
from backend.vault.envelope import KeyVault

GEMINI_URL_RE = re.compile(r"https://generativelanguage\.googleapis\.com/.+generateContent.*")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _gemini_ok(text: str, in_tok: int = 12, out_tok: int = 6) -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": in_tok, "candidatesTokenCount": out_tok},
    }


def _anthropic_ok(text: str, model: str) -> dict:
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 4, "output_tokens": 2},
        "model": model,
    }


async def _seed_user(db: aiosqlite.Connection, github_id: int = 5050) -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, 'alice', NULL, strftime('%s','now'), strftime('%s','now'))",
        (github_id,),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = ?", (github_id,))
    return (await cur.fetchone())["id"]


async def _authed(client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings) -> int:
    user_id = await _seed_user(db)
    sess = await create_session(db, user_id, settings.session_max_age_s)
    await db.commit()
    signer = make_signer(settings.session_secret)
    client.cookies.set(settings.session_cookie_name, sign_sid(signer, sess.id))
    return user_id


async def _seed_run(
    db: aiosqlite.Connection, user_id: int, settings: Settings, run_id: str = "cafebabe1234"
) -> RunLayout:
    await db.execute(
        "INSERT INTO runs (id, user_id, url, status, created_at) VALUES (?, ?, ?, 'done', ?)",
        (run_id, user_id, "http://test/", int(time.time())),
    )
    await db.commit()
    layout = RunLayout(
        root=Path(settings.runs_root).resolve(), user_id=f"u{user_id}", run_id=run_id
    )
    layout.create()
    with GraphStore(layout.graph_path) as g:
        for fn_id, name in [("f1", "login"), ("f2", "validate"), ("f3", "lonely")]:
            g.add_node(
                "Function",
                {"id": fn_id, "name": name, "path": "app.js", "kind": "function_declaration", "start_line": 1, "end_line": 1},
            )
        g.add_edge("Function", "f1", "Function", "f2", "CALLS")
        # Seed an unused Feature + EXECUTED_IN edge so the Feature node table
        # AND the rel table both exist. The `dead_functions` playbook walks
        # both; Kuzu raises "Table X does not exist" if the rel table is
        # absent. The edge points at the seed feature; the three real
        # functions remain unexecuted.
        g.add_node("Feature", {"id": "feat_seed", "name": "_seed_"})
        g.add_node(
            "Function",
            {"id": "f_seed", "name": "_seed_fn_", "path": "_seed_.js", "kind": "function_declaration", "start_line": 1, "end_line": 1},
        )
        g.add_edge("Function", "f_seed", "Feature", "feat_seed", "EXECUTED_IN")
    return layout


@pytest.fixture
def settings_for_run(settings: Settings, tmp_path: Path) -> Settings:
    return settings.model_copy(
        update={"runs_root": str(tmp_path / "runs"), "gemini_api_key": "test-key"}
    )


@pytest.mark.asyncio
async def test_cypher_raw_query(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings_for_run: Settings
) -> None:
    app_client._transport.app.state.settings = settings_for_run  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_for_run)
    await _seed_run(db, user_id, settings_for_run)

    r = await app_client.post(
        "/runs/cafebabe1234/cypher",
        json={"query": "MATCH (f:Function) WHERE f.path = 'app.js' RETURN f.name AS name"},
    )
    assert r.status_code == 200, r.text
    names = sorted(row["name"] for row in r.json()["rows"])
    assert names == sorted(["lonely", "login", "validate"])


@pytest.mark.asyncio
async def test_cypher_mutation_rejected(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings_for_run: Settings
) -> None:
    app_client._transport.app.state.settings = settings_for_run  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_for_run)
    await _seed_run(db, user_id, settings_for_run)

    r = await app_client.post(
        "/runs/cafebabe1234/cypher", json={"query": "CREATE (n:X)"}
    )
    assert r.status_code == 400
    assert "CREATE" in r.json()["detail"]


@pytest.mark.asyncio
async def test_nl_translates_and_runs(
    app_client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    settings_for_run: Settings,
    httpx_mock,
) -> None:
    app_client._transport.app.state.settings = settings_for_run  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_for_run)
    await _seed_run(db, user_id, settings_for_run)

    httpx_mock.add_response(
        method="POST",
        url=GEMINI_URL_RE,
        json=_gemini_ok("MATCH (f:Function) WHERE f.path = 'app.js' RETURN count(f) AS n"),
    )

    r = await app_client.post("/runs/cafebabe1234/nl", json={"prompt": "how many fns"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cypher"] == "MATCH (f:Function) WHERE f.path = 'app.js' RETURN count(f) AS n"
    assert body["rows"] == [{"n": 3}]


@pytest.mark.asyncio
async def test_playbook_dead_functions(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings_for_run: Settings
) -> None:
    app_client._transport.app.state.settings = settings_for_run  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_for_run)
    await _seed_run(db, user_id, settings_for_run)

    r = await app_client.post(
        "/runs/cafebabe1234/playbooks/dead_functions", json={"params": {}}
    )
    assert r.status_code == 200, r.text
    # No EXECUTED_IN edges seeded, so all 3 functions are "dead".
    assert r.json()["row_count"] == 3


@pytest.mark.asyncio
async def test_playbook_with_params(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings_for_run: Settings
) -> None:
    app_client._transport.app.state.settings = settings_for_run  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_for_run)
    await _seed_run(db, user_id, settings_for_run)

    r = await app_client.post(
        "/runs/cafebabe1234/playbooks/callers_of",
        json={"params": {"name": "validate"}},
    )
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["caller"] == "login"


@pytest.mark.asyncio
async def test_get_playbook_catalog(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings_for_run: Settings
) -> None:
    app_client._transport.app.state.settings = settings_for_run  # type: ignore[attr-defined]
    await _authed(app_client, db, settings_for_run)

    r = await app_client.get("/playbooks")
    assert r.status_code == 200
    slugs = {pb["slug"] for pb in r.json()}
    assert {"dead_functions", "top_callers", "callers_of", "executed_in_feature", "function_count"} <= slugs


@pytest.mark.asyncio
async def test_advise_pro_tier_only(
    app_client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    settings_for_run: Settings,
    httpx_mock,
) -> None:
    app_client._transport.app.state.settings = settings_for_run  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_for_run)
    await _seed_run(db, user_id, settings_for_run)

    # No vault key → 502.
    r1 = await app_client.post(
        "/runs/cafebabe1234/advise", json={"prompt": "is f1 → f2 dangerous?"}
    )
    assert r1.status_code == 502

    vault = KeyVault(settings_for_run.vault_kek_hex)
    vault_db = await connect(settings_for_run.db_path)
    try:
        await vault.put(vault_db, user_id, "anthropic", "sk-ant-test")
    finally:
        await vault_db.close()

    httpx_mock.add_response(
        method="POST",
        url=ANTHROPIC_URL,
        json=_anthropic_ok('{"verdict":"safe"}', model=settings_for_run.anthropic_default_model),
    )
    r2 = await app_client.post(
        "/runs/cafebabe1234/advise", json={"prompt": "look at f1 → f2"}
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["provider"] == "anthropic"
