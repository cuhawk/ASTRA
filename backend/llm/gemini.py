from __future__ import annotations

import time

import httpx

from backend.llm.base import LLMError, LLMResponse, LLMUsage, cost_for


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        embed_model: str,
        timeout_s: float = 30.0,
        base_url: str = "https://generativelanguage.googleapis.com",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._embed_model = embed_model
        self._timeout_s = timeout_s
        self._base_url = base_url.rstrip("/")

    def _require_key(self) -> None:
        if not self._api_key:
            raise LLMError(
                "ASTRA_GEMINI_API_KEY not configured", provider="gemini"
            )

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse:
        return await self.generate(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def generate(
        self,
        contents: list[dict],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Multi-turn generation. `contents` is a list of {role, parts} dicts
        where role is "user" or "model". Used by the chat service so the
        stable prefix (system + run-context-priming turn) can hit Gemini's
        implicit context cache."""
        self._require_key()

        body: dict = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            body["systemInstruction"] = {
                "role": "system",
                "parts": [{"text": system}],
            }

        url = f"{self._base_url}/v1beta/models/{self._model}:generateContent"
        params = {"key": self._api_key}

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as http:
                resp = await http.post(url, params=params, json=body)
        except httpx.HTTPError as exc:
            raise LLMError(f"gemini request failed: {exc}", provider="gemini") from exc

        duration_ms = int((time.perf_counter() - started) * 1000)

        if resp.status_code >= 400:
            msg = _extract_error_message(resp) or f"gemini http {resp.status_code}"
            raise LLMError(msg, provider="gemini", status=resp.status_code)

        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError("no candidates in gemini response", provider="gemini")

        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)

        meta = data.get("usageMetadata") or {}
        usage = LLMUsage(
            prompt_tokens=int(meta.get("promptTokenCount", 0)),
            completion_tokens=int(meta.get("candidatesTokenCount", 0)),
            cached_prompt_tokens=int(meta.get("cachedContentTokenCount", 0)),
        )

        return LLMResponse(
            provider="gemini",
            model=self._model,
            text=text,
            usage=usage,
            cost_usd=cost_for("gemini", self._model, usage),
            duration_ms=duration_ms,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._require_key()

        url = f"{self._base_url}/v1beta/models/{self._embed_model}:batchEmbedContents"
        params = {"key": self._api_key}
        body = {
            "requests": [
                {
                    "model": f"models/{self._embed_model}",
                    "content": {"parts": [{"text": t}]},
                }
                for t in texts
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as http:
                resp = await http.post(url, params=params, json=body)
        except httpx.HTTPError as exc:
            raise LLMError(f"gemini request failed: {exc}", provider="gemini") from exc

        if resp.status_code >= 400:
            msg = _extract_error_message(resp) or f"gemini http {resp.status_code}"
            raise LLMError(msg, provider="gemini", status=resp.status_code)

        data = resp.json()
        items = data.get("embeddings") or []
        return [list(item.get("values") or []) for item in items]


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
