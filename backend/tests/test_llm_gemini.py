from __future__ import annotations

import json

import pytest

from backend.llm.base import LLMError
from backend.llm.gemini import GeminiClient

BASE_URL = "https://generativelanguage.googleapis.com"
MODEL = "gemini-3.1-flash-lite"
EMBED_MODEL = "text-embedding-004"
API_KEY = "test-gemini-key"


def _client(api_key: str = API_KEY) -> GeminiClient:
    return GeminiClient(
        api_key=api_key,
        model=MODEL,
        embed_model=EMBED_MODEL,
        timeout_s=5.0,
        base_url=BASE_URL,
    )


@pytest.mark.asyncio
async def test_complete_happy_path(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/v1beta/models/{MODEL}:generateContent?key={API_KEY}",
        json={
            "candidates": [
                {"content": {"parts": [{"text": "hello"}]}, "finishReason": "STOP"}
            ],
            "usageMetadata": {
                "promptTokenCount": 12,
                "candidatesTokenCount": 3,
            },
        },
    )

    resp = await _client().complete("ping")

    assert resp.text == "hello"
    assert resp.usage.prompt_tokens == 12
    assert resp.usage.completion_tokens == 3
    assert resp.cost_usd > 0
    assert resp.duration_ms >= 0
    assert resp.provider == "gemini"
    assert resp.model == MODEL


@pytest.mark.asyncio
async def test_complete_with_system_instruction(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/v1beta/models/{MODEL}:generateContent?key={API_KEY}",
        json={
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
        },
    )

    await _client().complete("hi", system="be terse")

    request = httpx_mock.get_request()
    body = json.loads(request.content)
    assert body["systemInstruction"]["parts"][0]["text"] == "be terse"
    assert body["contents"][0]["parts"][0]["text"] == "hi"


@pytest.mark.asyncio
async def test_complete_missing_api_key_raises():
    client = _client(api_key="")
    with pytest.raises(LLMError) as info:
        await client.complete("x")
    assert "api_key" in str(info.value).lower() or "api key" in str(info.value).lower()
    assert info.value.provider == "gemini"


@pytest.mark.asyncio
async def test_complete_http_error_raises(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/v1beta/models/{MODEL}:generateContent?key={API_KEY}",
        status_code=429,
        json={"error": {"message": "rate limited"}},
    )

    with pytest.raises(LLMError) as info:
        await _client().complete("x")
    assert info.value.status == 429
    assert info.value.provider == "gemini"
    assert "rate limited" in str(info.value)


@pytest.mark.asyncio
async def test_embed_batch(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/v1beta/models/{EMBED_MODEL}:batchEmbedContents?key={API_KEY}",
        json={
            "embeddings": [
                {"values": [0.1, 0.2, 0.3]},
                {"values": [0.4, 0.5, 0.6]},
                {"values": [0.7, 0.8, 0.9]},
            ]
        },
    )

    out = await _client().embed(["a", "b", "c"])
    assert isinstance(out, list)
    assert len(out) == 3
    assert out[0] == [0.1, 0.2, 0.3]
    assert all(isinstance(v, float) for v in out[1])


@pytest.mark.asyncio
async def test_embed_empty_input():
    out = await _client().embed([])
    assert out == []


@pytest.mark.asyncio
async def test_complete_no_candidates_raises(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/v1beta/models/{MODEL}:generateContent?key={API_KEY}",
        json={"candidates": []},
    )

    with pytest.raises(LLMError) as info:
        await _client().complete("x")
    assert "no candidates" in str(info.value).lower()
    assert info.value.provider == "gemini"
