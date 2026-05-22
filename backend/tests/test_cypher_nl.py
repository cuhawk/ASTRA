from __future__ import annotations

import json
import re

import pytest

from backend.config import Settings
from backend.cypher.nl import NLToCypher
from backend.llm.base import LLMError

GEMINI_URL_RE = re.compile(
    r"https://generativelanguage\.googleapis\.com/.+generateContent.*"
)


def _gemini_ok(text: str, in_tok: int = 12, out_tok: int = 6) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {
            "promptTokenCount": in_tok,
            "candidatesTokenCount": out_tok,
        },
    }


def _with_key(settings: Settings) -> Settings:
    return settings.model_copy(update={"gemini_api_key": "test-key"})


@pytest.mark.asyncio
async def test_translate_returns_cypher(httpx_mock, settings: Settings):
    httpx_mock.add_response(
        method="POST",
        url=GEMINI_URL_RE,
        json=_gemini_ok("MATCH (f:Function) RETURN f.name"),
    )

    translator = NLToCypher(_with_key(settings))
    cypher, resp = await translator.translate("show all functions")

    assert cypher == "MATCH (f:Function) RETURN f.name"
    assert resp.provider == "gemini"


@pytest.mark.asyncio
async def test_translate_strips_markdown_fences(httpx_mock, settings: Settings):
    httpx_mock.add_response(
        method="POST",
        url=GEMINI_URL_RE,
        json=_gemini_ok("```cypher\nMATCH (n) RETURN n\n```"),
    )

    translator = NLToCypher(_with_key(settings))
    cypher, _ = await translator.translate("anything")

    assert cypher == "MATCH (n) RETURN n"


@pytest.mark.asyncio
async def test_translate_strips_plain_fences(httpx_mock, settings: Settings):
    httpx_mock.add_response(
        method="POST",
        url=GEMINI_URL_RE,
        json=_gemini_ok("```\nMATCH (n) RETURN n\n```"),
    )

    translator = NLToCypher(_with_key(settings))
    cypher, _ = await translator.translate("anything")

    assert cypher == "MATCH (n) RETURN n"


@pytest.mark.asyncio
async def test_translate_sends_system_prompt_with_schema(
    httpx_mock, settings: Settings
):
    httpx_mock.add_response(
        method="POST",
        url=GEMINI_URL_RE,
        json=_gemini_ok("MATCH (n) RETURN n"),
    )

    translator = NLToCypher(_with_key(settings))
    await translator.translate("anything")

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    system_text = body["systemInstruction"]["parts"][0]["text"]
    assert "Function(id" in system_text
    assert "EXECUTED_IN" in system_text


@pytest.mark.asyncio
async def test_translate_missing_api_key_raises(settings: Settings):
    translator = NLToCypher(settings.model_copy(update={"gemini_api_key": ""}))
    with pytest.raises(LLMError) as info:
        await translator.translate("x")
    assert info.value.provider == "gemini"


@pytest.mark.asyncio
async def test_translate_low_temperature(httpx_mock, settings: Settings):
    httpx_mock.add_response(
        method="POST",
        url=GEMINI_URL_RE,
        json=_gemini_ok("MATCH (n) RETURN n"),
    )

    translator = NLToCypher(_with_key(settings))
    await translator.translate("anything")

    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["generationConfig"]["temperature"] == 0.0
