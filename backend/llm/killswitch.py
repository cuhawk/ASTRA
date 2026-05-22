from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from backend.llm.base import KillSwitchTripped, Provider


_DEDUCT_LUA = """
local v = redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])
if tonumber(v) > tonumber(ARGV[2]) then
  redis.call('EXPIRE', KEYS[1], ARGV[3])
  return tostring(v) .. ':OVER'
end
redis.call('EXPIRE', KEYS[1], ARGV[3])
return tostring(v)
"""


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _key(provider: Provider, bucket: str | None = None) -> str:
    bucket = bucket or _today_utc()
    return f"llm_spend:{provider}:{bucket}"


class KillSwitch:
    def __init__(
        self,
        redis_client: aioredis.Redis,
        cap_usd: float,
        ttl_s: int = 26 * 60 * 60,
    ) -> None:
        self._r = redis_client
        self._cap = float(cap_usd)
        self._ttl_s = ttl_s

    async def spent(self, provider: Provider) -> float:
        raw = await self._r.get(_key(provider))
        return float(raw) if raw is not None else 0.0

    async def add_and_check(self, provider: Provider, cost_usd: float) -> float:
        key = _key(provider)
        try:
            result = await self._r.eval(
                _DEDUCT_LUA, 1, key, cost_usd, self._cap, self._ttl_s
            )
        except ResponseError as exc:
            if "unknown command" not in str(exc).lower():
                raise
            result = await self._add_no_lua(key, cost_usd)

        text = result.decode() if isinstance(result, bytes) else str(result)
        over = text.endswith(":OVER")
        total = float(text[:-5]) if over else float(text)
        if over:
            raise KillSwitchTripped(
                f"daily spend cap ${self._cap:.2f} exceeded for {provider}: ${total:.4f}"
            )
        return total

    async def _add_no_lua(self, key: str, cost_usd: float) -> str:
        new = float(await self._r.incrbyfloat(key, cost_usd))
        await self._r.expire(key, self._ttl_s)
        if new > self._cap:
            return f"{new}:OVER"
        return str(new)

    async def check(self, provider: Provider) -> None:
        total = await self.spent(provider)
        if total > self._cap:
            raise KillSwitchTripped(
                f"daily spend cap ${self._cap:.2f} exceeded for {provider}: ${total:.4f}"
            )

    async def reset(self, provider: Provider) -> None:
        await self._r.delete(_key(provider))
