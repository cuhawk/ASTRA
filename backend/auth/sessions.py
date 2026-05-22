from __future__ import annotations

import base64
import secrets
from datetime import UTC, datetime

import aiosqlite
from itsdangerous import BadSignature, Signer
from pydantic import BaseModel

from backend.auth.oauth import GitHubUser


class SessionRecord(BaseModel):
    id: str
    user_id: int
    created_at: int
    expires_at: int


def _now() -> int:
    return int(datetime.now(UTC).timestamp())


def make_signer(secret: str) -> Signer:
    return Signer(secret, salt="astra-session")


def new_sid() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def sign_sid(signer: Signer, sid: str) -> str:
    return signer.sign(sid.encode("ascii")).decode("ascii")


def verify_signed(signer: Signer, signed: str) -> str | None:
    try:
        return signer.unsign(signed.encode("ascii")).decode("ascii")
    except BadSignature:
        return None


async def create_session(
    db: aiosqlite.Connection, user_id: int, max_age_s: int
) -> SessionRecord:
    sid = new_sid()
    now = _now()
    expires = now + max_age_s
    await db.execute(
        "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (sid, user_id, now, expires),
    )
    await db.commit()
    return SessionRecord(id=sid, user_id=user_id, created_at=now, expires_at=expires)


async def get_session(db: aiosqlite.Connection, sid: str) -> SessionRecord | None:
    cur = await db.execute(
        "SELECT id, user_id, created_at, expires_at FROM sessions WHERE id = ?",
        (sid,),
    )
    row = await cur.fetchone()
    await cur.close()
    if row is None:
        return None
    if row["expires_at"] <= _now():
        return None
    return SessionRecord(
        id=row["id"],
        user_id=row["user_id"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


async def delete_session(db: aiosqlite.Connection, sid: str) -> None:
    await db.execute("DELETE FROM sessions WHERE id = ?", (sid,))
    await db.commit()


async def upsert_github_user(db: aiosqlite.Connection, gh: GitHubUser) -> int:
    now = _now()
    await db.execute(
        """
        INSERT INTO users (github_id, github_login, email, created_at, last_login_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(github_id) DO UPDATE SET
            github_login = excluded.github_login,
            email = excluded.email,
            last_login_at = excluded.last_login_at
        """,
        (gh.id, gh.login, gh.email, now, now),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = ?", (gh.id,))
    row = await cur.fetchone()
    await cur.close()
    return int(row["id"])
