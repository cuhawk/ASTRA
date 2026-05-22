from __future__ import annotations

import json

import pytest

from backend.llm.anthropic import AnthropicClient
from backend.llm.base import LLMError

BASE_URL = "https://api.anthropic.com"
SONNET = "claude-sonnet-4-5-20250929"
OPUS = "claude-opus-4-5-20250929"
API_KEY = "test-anthropic-key"
MESSAGES_URL = f"{BASE_URL}/v1/messages"


def _client(api_key: str = API_KEY) -> AnthropicClient:
    return AnthropicClient(
        api_key=api_key,
        default_model=SONNET,
        opus_model=OPUS,
        timeout_s=5.0,
        base_url=BASE_URL,
    )


def _ok(text: str, model: str = SONNET, input_tokens: int = 10, output_tokens: int = 5) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": model,
        "stop_reason": "end_turn",
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


@pytest.mark.asyncio
async def test_complete_happy_path(httpx_mock):
    httpx_mock.add_response(method="POST", url=MESSAGES_URL, json=_ok("hi"))

    resp = await _client().complete("ping")

    assert resp.text == "hi"
    assert resp.provider == "anthropic"
    assert resp.model == SONNET
    assert resp.usage.prompt_tokens == 10
    assert resp.usage.completion_tokens == 5
    assert resp.cost_usd > 0
    assert resp.duration_ms >= 0

    req = httpx_mock.get_request()
    assert req.headers["x-api-key"] == API_KEY
    assert req.headers["anthropic-version"] == "2023-06-01"
    body = json.loads(req.content)
    assert body["model"] == SONNET
    assert body["messages"] == [{"role": "user", "content": "ping"}]


@pytest.mark.asyncio
async def test_complete_with_system(httpx_mock):
    httpx_mock.add_response(method="POST", url=MESSAGES_URL, json=_ok("ok"))

    await _client().complete("hi", system="be terse")

    body = json.loads(httpx_mock.get_request().content)
    assert body["system"] == "be terse"
    assert body["messages"][0]["content"] == "hi"


@pytest.mark.asyncio
async def test_complete_missing_api_key():
    client = _client(api_key="")
    with pytest.raises(LLMError) as info:
        await client.complete("x")
    assert info.value.provider == "anthropic"
    assert "api key" in str(info.value).lower()


@pytest.mark.asyncio
async def test_complete_http_error(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=MESSAGES_URL,
        status_code=401,
        json={"error": {"type": "authentication_error", "message": "auth failed"}},
    )

    with pytest.raises(LLMError) as info:
        await _client().complete("x")
    assert info.value.status == 401
    assert info.value.provider == "anthropic"
    assert "auth failed" in str(info.value)


@pytest.mark.asyncio
async def test_advise_calls_sonnet_only_when_confident(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=MESSAGES_URL,
        json=_ok('{"verdict":"vulnerable","reason":"taint reaches sink"}'),
    )

    resp = await _client().advise("analyze chain XYZ")

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["model"] == SONNET
    assert resp.model == SONNET


@pytest.mark.asyncio
async def test_advise_escalates_to_opus_on_uncertain(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=MESSAGES_URL,
        json=_ok('{"verdict":"uncertain","reason":"need deeper look"}', model=SONNET),
    )
    httpx_mock.add_response(
        method="POST",
        url=MESSAGES_URL,
        json=_ok(
            '{"verdict":"vulnerable","reason":"confirmed"}',
            model=OPUS,
            input_tokens=20,
            output_tokens=8,
        ),
    )

    resp = await _client().advise("analyze chain XYZ")

    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    first = json.loads(requests[0].content)
    second = json.loads(requests[1].content)
    assert first["model"] == SONNET
    assert second["model"] == OPUS
    assert resp.model == OPUS
    assert "confirmed" in resp.text


@pytest.mark.asyncio
async def test_advise_prefer_opus_skips_sonnet(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=MESSAGES_URL,
        json=_ok('{"verdict":"vulnerable"}', model=OPUS),
    )

    resp = await _client().advise("deep look", prefer_opus=True)

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["model"] == OPUS
    assert resp.model == OPUS
