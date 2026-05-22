from __future__ import annotations

import fakeredis.aioredis as fakeredis
import pytest

from backend.quota.counter import QuotaCounter, QuotaExceeded, _key, _today_utc


async def test_used_starts_at_zero(fake_redis: fakeredis.FakeRedis) -> None:
    c = QuotaCounter(fake_redis, daily_limit=10)
    assert await c.used(42) == 0
    assert await c.remaining(42) == 10


async def test_deduct_increments_and_returns_new(fake_redis: fakeredis.FakeRedis) -> None:
    c = QuotaCounter(fake_redis, daily_limit=10)
    assert await c.deduct(1) == 1
    assert await c.used(1) == 1
    assert await c.deduct(1) == 2
    assert await c.used(1) == 2
    assert await c.remaining(1) == 8


async def test_deduct_sets_ttl(fake_redis: fakeredis.FakeRedis) -> None:
    c = QuotaCounter(fake_redis, daily_limit=10, ttl_s=26 * 60 * 60)
    await c.deduct(7)
    ttl = await fake_redis.ttl(_key(7))
    assert ttl > 0
    assert ttl <= 26 * 60 * 60


async def test_deduct_at_limit_raises(fake_redis: fakeredis.FakeRedis) -> None:
    c = QuotaCounter(fake_redis, daily_limit=3)
    await c.deduct(99)
    await c.deduct(99)
    await c.deduct(99)
    with pytest.raises(QuotaExceeded):
        await c.deduct(99)
    assert await c.used(99) == 3


async def test_deduct_n_at_once(fake_redis: fakeredis.FakeRedis) -> None:
    c = QuotaCounter(fake_redis, daily_limit=10)
    assert await c.deduct(5, n=5) == 5
    with pytest.raises(QuotaExceeded):
        await c.deduct(5, n=6)
    assert await c.used(5) == 5


async def test_key_format(fake_redis: fakeredis.FakeRedis) -> None:
    c = QuotaCounter(fake_redis, daily_limit=10)
    await c.deduct(123)
    today = _today_utc()
    raw = await fake_redis.get(f"quota:123:{today}")
    assert raw == "1"
