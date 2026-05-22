from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite
import redis.asyncio as aioredis
from redis.exceptions import ResponseError


class QuotaExceeded(Exception):
    pass


# Atomic deduct: INCRBY, undo on overflow, set TTL only on the deduct that
# created the key (post-incr == delta). Returns -1 to signal QuotaExceeded.
_DEDUCT_LUA = """
local v = redis.call('INCRBY', KEYS[1], ARGV[1])
if v > tonumber(ARGV[2]) then
  redis.call('DECRBY', KEYS[1], ARGV[1])
  return -1
end
if v == tonumber(ARGV[1]) then
  redis.call('EXPIRE', KEYS[1], ARGV[3])
end
return v
"""


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _key(user_id: int, bucket: str | None = None) -> str:
    bucket = bucket or _today_utc()
    return f"quota:{user_id}:{bucket}"


class QuotaCounter:
    def __init__(
        self,
        redis_client: aioredis.Redis,
        daily_limit: int,
        ttl_s: int = 26 * 60 * 60,
    ) -> None:
        self._r = redis_client
        self._limit = daily_limit
        self._ttl_s = ttl_s

    async def used(self, user_id: int) -> int:
        v = await self._r.get(_key(user_id))
        return int(v) if v is not None else 0

    async def remaining(self, user_id: int) -> int:
        return max(0, self._limit - await self.used(user_id))

    async def deduct(self, user_id: int, n: int = 1, reason: str = "llm") -> int:
        key = _key(user_id)
        try:
            result = await self._r.eval(
                _DEDUCT_LUA, 1, key, n, self._limit, self._ttl_s
            )
        except ResponseError as exc:
            # fakeredis (test env) ships without lupa → no EVAL. Real Redis
            # always has Lua. Fall back to a non-Lua sequence that is
            # functionally equivalent in a single-process test runner.
            if "unknown command" not in str(exc).lower():
                raise
            result = await self._deduct_no_lua(key, n)
        new_used = int(result)
        if new_used == -1:
            raise QuotaExceeded(f"user {user_id} exceeded daily limit {self._limit}")
        return new_used

    async def _deduct_no_lua(self, key: str, n: int) -> int:
        new = int(await self._r.incrby(key, n))
        if new > self._limit:
            await self._r.decrby(key, n)
            return -1
        if new == n:
            await self._r.expire(key, self._ttl_s)
        return new


async def write_audit(
    db: aiosqlite.Connection, user_id: int, delta: int, reason: str
) -> None:
    bucket = _today_utc()
    at = int(datetime.now(timezone.utc).timestamp())
    await db.execute(
        "INSERT INTO audit_quota (user_id, bucket, delta, reason, at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, bucket, delta, reason, at),
    )
