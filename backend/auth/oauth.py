from __future__ import annotations

from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"
_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubUser(BaseModel):
    id: int
    login: str
    email: str | None


class GitHubOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def authorize_url(self, state: str, scope: str = "read:user user:email") -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": scope,
            "response_type": "code",
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> str:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _TOKEN_URL,
                data=payload,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            body = resp.json()
        if "error" in body:
            raise ValueError(f"GitHub token exchange failed: {body.get('error')}")
        token = body.get("access_token")
        if not token:
            raise ValueError("GitHub token exchange returned no access_token")
        return token

    async def fetch_user(self, access_token: str) -> GitHubUser:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(_USER_URL, headers=headers)
            resp.raise_for_status()
            user = resp.json()
            email = user.get("email")
            if email is None:
                emails_resp = await client.get(_EMAILS_URL, headers=headers)
                emails_resp.raise_for_status()
                emails = emails_resp.json()
                email = _pick_primary_verified(emails)
        return GitHubUser(id=user["id"], login=user["login"], email=email)


def _pick_primary_verified(emails: list[dict]) -> str | None:
    for entry in emails:
        if entry.get("primary") and entry.get("verified"):
            return entry.get("email")
    for entry in emails:
        if entry.get("verified"):
            return entry.get("email")
    return None
