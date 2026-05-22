from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from backend.auth.routes import router as auth_router
from backend.config import Settings
from backend.db.connection import init_db


@pytest.fixture
async def auth_app_client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    await init_db(settings.db_path)
    app = FastAPI()
    app.state.settings = settings
    app.include_router(auth_router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


async def test_login_redirects_to_github(auth_app_client: httpx.AsyncClient) -> None:
    resp = await auth_app_client.get("/auth/github/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].startswith(
        "https://github.com/login/oauth/authorize"
    )
    set_cookie = resp.headers.get("set-cookie", "")
    assert "astra_oauth_state=" in set_cookie
    assert "httponly" in set_cookie.lower()


async def test_callback_state_mismatch_400(
    auth_app_client: httpx.AsyncClient,
) -> None:
    auth_app_client.cookies.set("astra_oauth_state", "expected-state")
    resp = await auth_app_client.get(
        "/auth/github/callback",
        params={"code": "abc", "state": "wrong-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


async def test_callback_full_flow(
    auth_app_client: httpx.AsyncClient,
    httpx_mock,
    settings: Settings,
) -> None:
    httpx_mock.add_response(
        url="https://github.com/login/oauth/access_token",
        method="POST",
        json={"access_token": "tok", "token_type": "bearer"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/user",
        method="GET",
        json={"id": 1234, "login": "alice", "email": "alice@example.com"},
    )

    login_resp = await auth_app_client.get(
        "/auth/github/login", follow_redirects=False
    )
    state_value = login_resp.cookies.get("astra_oauth_state")
    assert state_value

    cb_resp = await auth_app_client.get(
        "/auth/github/callback",
        params={"code": "the-code", "state": state_value},
        follow_redirects=False,
    )
    assert cb_resp.status_code == 302
    assert cb_resp.headers["location"] == settings.base_url
    cookie_header = cb_resp.headers.get("set-cookie", "")
    assert settings.session_cookie_name in cookie_header

    me_resp = await auth_app_client.get("/auth/me")
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["github_id"] == 1234
    assert body["github_login"] == "alice"
    assert body["email"] == "alice@example.com"


async def test_me_without_cookie_401(auth_app_client: httpx.AsyncClient) -> None:
    resp = await auth_app_client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_with_bad_signature_401(
    auth_app_client: httpx.AsyncClient, settings: Settings
) -> None:
    auth_app_client.cookies.set(settings.session_cookie_name, "not-a-valid-signed-sid")
    resp = await auth_app_client.get("/auth/me")
    assert resp.status_code == 401


async def test_logout_clears_session(
    auth_app_client: httpx.AsyncClient,
    httpx_mock,
    settings: Settings,
) -> None:
    httpx_mock.add_response(
        url="https://github.com/login/oauth/access_token",
        method="POST",
        json={"access_token": "tok", "token_type": "bearer"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/user",
        method="GET",
        json={"id": 555, "login": "bob", "email": "bob@example.com"},
    )

    login_resp = await auth_app_client.get(
        "/auth/github/login", follow_redirects=False
    )
    state_value = login_resp.cookies.get("astra_oauth_state")
    await auth_app_client.get(
        "/auth/github/callback",
        params={"code": "x", "state": state_value},
        follow_redirects=False,
    )

    me_resp = await auth_app_client.get("/auth/me")
    assert me_resp.status_code == 200

    logout_resp = await auth_app_client.post("/auth/logout")
    assert logout_resp.status_code == 204

    auth_app_client.cookies.delete(settings.session_cookie_name)
    me_after = await auth_app_client.get("/auth/me")
    assert me_after.status_code == 401
