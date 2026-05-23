from __future__ import annotations

import base64
import secrets
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from backend.audit.events import emit as emit_event
from backend.auth.deps import get_db, get_settings_dep, require_user
from backend.auth.oauth import GitHubOAuth
from backend.auth.sessions import (
    create_session,
    delete_session,
    make_signer,
    sign_sid,
    upsert_github_user,
    verify_signed,
)
from backend.config import Settings

router = APIRouter()

_STATE_COOKIE = "astra_oauth_state"


def _new_state() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


@router.get("/auth/github/login")
async def github_login(
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    state = _new_state()
    oauth = GitHubOAuth(
        settings.github_client_id,
        settings.github_client_secret,
        settings.github_redirect_uri,
    )
    url = oauth.authorize_url(state)
    resp = RedirectResponse(url=url, status_code=302)
    resp.set_cookie(
        key=_STATE_COOKIE,
        value=state,
        max_age=600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/auth/github/callback")
async def github_callback(
    request: Request,
    code: str,
    state: str,
    settings: Settings = Depends(get_settings_dep),
    db: aiosqlite.Connection = Depends(get_db),
) -> Response:
    cookie_state = request.cookies.get(_STATE_COOKIE)
    if not cookie_state or not secrets.compare_digest(cookie_state, state):
        raise HTTPException(status_code=400, detail="state mismatch")

    oauth = GitHubOAuth(
        settings.github_client_id,
        settings.github_client_secret,
        settings.github_redirect_uri,
    )
    token = await oauth.exchange_code(code)
    gh_user = await oauth.fetch_user(token)
    user_id = await upsert_github_user(db, gh_user)
    session = await create_session(db, user_id, settings.session_max_age_s)
    await emit_event(
        db,
        user_id=user_id,
        action="auth.login",
        entity="session",
        entity_id=session.id[:12],
        payload={"login": gh_user.login},
    )

    signer = make_signer(settings.session_secret)
    signed = sign_sid(signer, session.id)

    resp = RedirectResponse(url=settings.base_url, status_code=302)
    resp.set_cookie(
        key=settings.session_cookie_name,
        value=signed,
        max_age=settings.session_max_age_s,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    resp.delete_cookie(_STATE_COOKIE, path="/")
    return resp


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    db: aiosqlite.Connection = Depends(get_db),
) -> Response:
    signed = request.cookies.get(settings.session_cookie_name)
    if signed:
        signer = make_signer(settings.session_secret)
        sid = verify_signed(signer, signed)
        if sid:
            await delete_session(db, sid)
    resp = Response(status_code=204)
    resp.delete_cookie(settings.session_cookie_name, path="/")
    return resp


@router.get("/auth/me")
async def me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return user
