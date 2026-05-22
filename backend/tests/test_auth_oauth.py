from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from backend.auth.oauth import GitHubOAuth
from backend.config import Settings


@pytest.fixture
def oauth(settings: Settings) -> GitHubOAuth:
    return GitHubOAuth(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        redirect_uri=settings.github_redirect_uri,
    )


def test_authorize_url_has_required_params(oauth: GitHubOAuth, settings: Settings) -> None:
    url = oauth.authorize_url(state="state-xyz")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "github.com"
    assert parsed.path == "/login/oauth/authorize"
    qs = parse_qs(parsed.query)
    assert qs["client_id"] == [settings.github_client_id]
    assert qs["redirect_uri"] == [settings.github_redirect_uri]
    assert qs["state"] == ["state-xyz"]
    assert qs["response_type"] == ["code"]
    assert "scope" in qs


async def test_exchange_code_success(httpx_mock, oauth: GitHubOAuth) -> None:
    httpx_mock.add_response(
        url="https://github.com/login/oauth/access_token",
        method="POST",
        json={"access_token": "tok", "token_type": "bearer"},
    )
    token = await oauth.exchange_code("c")
    assert token == "tok"


async def test_exchange_code_error_raises(httpx_mock, oauth: GitHubOAuth) -> None:
    httpx_mock.add_response(
        url="https://github.com/login/oauth/access_token",
        method="POST",
        json={"error": "bad_verification_code"},
    )
    with pytest.raises(ValueError):
        await oauth.exchange_code("c")


async def test_fetch_user_with_public_email(httpx_mock, oauth: GitHubOAuth) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/user",
        method="GET",
        json={"id": 42, "login": "octocat", "email": "octo@example.com"},
    )
    user = await oauth.fetch_user("tok")
    assert user.id == 42
    assert user.login == "octocat"
    assert user.email == "octo@example.com"


async def test_fetch_user_emails_fallback(httpx_mock, oauth: GitHubOAuth) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/user",
        method="GET",
        json={"id": 99, "login": "nomail", "email": None},
    )
    httpx_mock.add_response(
        url="https://api.github.com/user/emails",
        method="GET",
        json=[
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
            {"email": "unverified@example.com", "primary": False, "verified": False},
        ],
    )
    user = await oauth.fetch_user("tok")
    assert user.email == "primary@example.com"


async def test_fetch_user_emails_none_verified(httpx_mock, oauth: GitHubOAuth) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/user",
        method="GET",
        json={"id": 7, "login": "ghost", "email": None},
    )
    httpx_mock.add_response(
        url="https://api.github.com/user/emails",
        method="GET",
        json=[
            {"email": "x@example.com", "primary": True, "verified": False},
        ],
    )
    user = await oauth.fetch_user("tok")
    assert user.email is None
