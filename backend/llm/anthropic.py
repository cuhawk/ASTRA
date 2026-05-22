from __future__ import annotations

import time

import httpx

from backend.llm.base import LLMError, LLMResponse, LLMUsage, cost_for


_UNCERTAIN_TOKEN = '"verdict":"uncertain"'


class AnthropicClient:
    def __init__(
        self,
        api_key: str,
        default_model: str,
        opus_model: str,
        timeout_s: float = 60.0,
        base_url: str = "https://api.anthropic.com",
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._opus_model = opus_model
        self._timeout_s = timeout_s
        self._base_url = base_url.rstrip("/")

    def _require_key(self) -> None:
        if not self._api_key:
            raise LLMError("anthropic api key missing", provider="anthropic")

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> LLMResponse:
        self._require_key()

        used_model = model or self._default_model
        body: dict = {
            "model": used_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            body["system"] = system

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        url = f"{self._base_url}/v1/messages"

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as http:
                resp = await http.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise LLMError(
                f"anthropic request failed: {exc}", provider="anthropic"
            ) from exc

        duration_ms = int((time.perf_counter() - started) * 1000)

        if resp.status_code >= 400:
            msg = _extract_error_message(resp) or f"anthropic http {resp.status_code}"
            raise LLMError(msg, provider="anthropic", status=resp.status_code)

        data = resp.json()
        blocks = data.get("content") or []
        text = "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        )

        meta = data.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=int(meta.get("input_tokens", 0)),
            completion_tokens=int(meta.get("output_tokens", 0)),
        )

        echoed_model = data.get("model") or used_model

        return LLMResponse(
            provider="anthropic",
            model=echoed_model,
            text=text,
            usage=usage,
            cost_usd=cost_for("anthropic", echoed_model, usage),
            duration_ms=duration_ms,
        )

    async def advise(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        prefer_opus: bool = False,
    ) -> LLMResponse:
        if prefer_opus:
            return await self.complete(
                prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model=self._opus_model,
            )

        sonnet = await self.complete(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            model=self._default_model,
        )
        if _UNCERTAIN_TOKEN not in sonnet.text.replace(" ", ""):
            return sonnet

        return await self.complete(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            model=self._opus_model,
        )


def _extract_error_message(resp: httpx.Response) -> str | None:
    try:
        payload = resp.json()
    except Exception:
        return None
    err = payload.get("error")
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str) and msg:
            return msg
    return None
