"""Tier-routing + per-call audit logging for ASTRA LLM calls.

Free tier  → ASTRA's Gemini key (with global daily kill-switch).
Pro tier   → user's Anthropic key from the vault (user pays; no killswitch).
"""
from __future__ import annotations

import time
from typing import Literal

import aiosqlite

from backend.config import Settings
from backend.db.connection import connect
from backend.llm.anthropic import AnthropicClient
from backend.llm.base import KillSwitchTripped, LLMError, LLMResponse, Provider, Reason
from backend.llm.gemini import GeminiClient
from backend.llm.killswitch import KillSwitch
from backend.vault.envelope import KeyVault

Tier = Literal["free", "pro"]


async def _detect_tier(vault: KeyVault, db: aiosqlite.Connection, user_id: int) -> Tier:
    return "pro" if (await vault.get(db, user_id, "anthropic")) is not None else "free"


async def _write_audit(
    db_path: str,
    *,
    user_id: int | None,
    provider: Provider,
    model: str,
    reason: Reason,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    outcome: str,
    duration_ms: int,
) -> None:
    db = await connect(db_path)
    try:
        await db.execute(
            "INSERT INTO audit_llm_calls "
            "(user_id, provider, model, reason, prompt_tokens, completion_tokens, "
            " cost_usd, outcome, duration_ms, at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%s', 'now'))",
            (
                user_id,
                provider,
                model,
                reason,
                prompt_tokens,
                completion_tokens,
                cost_usd,
                outcome,
                duration_ms,
            ),
        )
        await db.commit()
    finally:
        await db.close()


class LLMRouter:
    def __init__(
        self,
        settings: Settings,
        redis_client,  # type: ignore[no-untyped-def]
        vault: KeyVault,
    ) -> None:
        self._settings = settings
        self._vault = vault
        self._killswitch = KillSwitch(redis_client, settings.daily_spend_cap_usd)

    async def _free_call(
        self,
        *,
        user_id: int,
        prompt: str,
        system: str | None,
        reason: Reason,
    ) -> LLMResponse:
        await self._killswitch.check("gemini")
        client = GeminiClient(
            api_key=self._settings.gemini_api_key,
            model=self._settings.gemini_model,
            embed_model=self._settings.gemini_embed_model,
        )
        t0 = time.monotonic()
        try:
            resp = await client.complete(prompt, system=system)
            outcome = "ok"
            try:
                await self._killswitch.add_and_check("gemini", resp.cost_usd)
            except KillSwitchTripped:
                # Call already succeeded; subsequent pre-flight check() will block.
                pass
            return resp
        except KillSwitchTripped:
            outcome = "killswitch"
            duration_ms = int((time.monotonic() - t0) * 1000)
            await _write_audit(
                self._settings.db_path,
                user_id=user_id,
                provider="gemini",
                model=self._settings.gemini_model,
                reason=reason,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                outcome=outcome,
                duration_ms=duration_ms,
            )
            raise
        except LLMError:
            outcome = "error"
            duration_ms = int((time.monotonic() - t0) * 1000)
            await _write_audit(
                self._settings.db_path,
                user_id=user_id,
                provider="gemini",
                model=self._settings.gemini_model,
                reason=reason,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                outcome=outcome,
                duration_ms=duration_ms,
            )
            raise
        finally:
            if outcome == "ok":
                await _write_audit(
                    self._settings.db_path,
                    user_id=user_id,
                    provider="gemini",
                    model=resp.model,
                    reason=reason,
                    prompt_tokens=resp.usage.prompt_tokens,
                    completion_tokens=resp.usage.completion_tokens,
                    cost_usd=resp.cost_usd,
                    outcome=outcome,
                    duration_ms=resp.duration_ms,
                )

    async def _pro_call(
        self,
        *,
        user_id: int,
        prompt: str,
        system: str | None,
        reason: Reason,
        cascade: bool,
        prefer_opus: bool,
    ) -> LLMResponse:
        db = await connect(self._settings.db_path)
        try:
            key = await self._vault.get(db, user_id, "anthropic")
        finally:
            await db.close()
        if key is None:
            raise LLMError("no anthropic key in vault for user", provider="anthropic")

        client = AnthropicClient(
            api_key=key,
            default_model=self._settings.anthropic_default_model,
            opus_model=self._settings.anthropic_opus_model,
        )
        outcome: str
        try:
            if cascade:
                resp = await client.advise(prompt, system=system, prefer_opus=prefer_opus)
            else:
                resp = await client.complete(prompt, system=system)
            outcome = "ok"
            await _write_audit(
                self._settings.db_path,
                user_id=user_id,
                provider="anthropic",
                model=resp.model,
                reason=reason,
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
                cost_usd=resp.cost_usd,
                outcome=outcome,
                duration_ms=resp.duration_ms,
            )
            return resp
        except LLMError as e:
            outcome = "error"
            await _write_audit(
                self._settings.db_path,
                user_id=user_id,
                provider="anthropic",
                model=self._settings.anthropic_default_model,
                reason=reason,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                outcome=outcome,
                duration_ms=0,
            )
            raise

    async def nl_to_cypher(self, user_id: int, prompt: str) -> LLMResponse:
        db = await connect(self._settings.db_path)
        try:
            tier = await _detect_tier(self._vault, db, user_id)
        finally:
            await db.close()
        if tier == "pro":
            return await self._pro_call(
                user_id=user_id,
                prompt=prompt,
                system=None,
                reason="nl_to_cypher",
                cascade=False,
                prefer_opus=False,
            )
        return await self._free_call(
            user_id=user_id,
            prompt=prompt,
            system=None,
            reason="nl_to_cypher",
        )

    async def advise(
        self, user_id: int, prompt: str, *, prefer_opus: bool = False
    ) -> LLMResponse:
        return await self._pro_call(
            user_id=user_id,
            prompt=prompt,
            system=None,
            reason="chain_triage",
            cascade=True,
            prefer_opus=prefer_opus,
        )

    async def spend_today(self) -> dict[str, float]:
        return {
            "gemini": await self._killswitch.spent("gemini"),
            "anthropic": await self._killswitch.spent("anthropic"),
            "cap_usd": self._settings.daily_spend_cap_usd,
        }
