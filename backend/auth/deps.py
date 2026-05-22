from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import aiosqlite
from fastapi import Depends, HTTPException, Request

from backend.auth.sessions import get_session, make_signer, verify_signed
from backend.config import Settings
from backend.db.connection import connect


async def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_db(
    settings: Settings = Depends(get_settings_dep),
) -> AsyncIterator[aiosqlite.Connection]:
    conn = await connect(settings.db_path)
    try:
        yield conn
    finally:
        await conn.close()


async def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, Any] | None:
    signed = request.cookies.get(settings.session_cookie_name)
    if not signed:
        return None
    signer = make_signer(settings.session_secret)
    sid = verify_signed(signer, signed)
    if sid is None:
        return None
    session = await get_session(db, sid)
    if session is None:
        return None
    cur = await db.execute(
        "SELECT id, github_id, github_login, email FROM users WHERE id = ?",
        (session.user_id,),
    )
    row = await cur.fetchone()
    await cur.close()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "github_id": int(row["github_id"]),
        "github_login": row["github_login"],
        "email": row["email"],
    }


async def require_user(
    user: dict[str, Any] | None = Depends(get_current_user),
) -> dict[str, Any]:
    if user is None:
        raise HTTPException(status_code=401, detail="auth required")
    return user
