from __future__ import annotations

from datetime import datetime, timezone

import fakeredis.aioredis as fakeredis
import pytest

from backend.llm.base import KillSwitchTripped
from backend.llm.killswitch import KillSwitch, _key


pytestmark = pytest.mark.asyncio


async def test_spent_zero_when_empty(fake_redis: fakeredis.FakeRedis) -> None:
    ks = KillSwitch(fake_redis, 10.0)
    assert await ks.spent("gemini") == 0.0


async def test_add_and_check_returns_new_total(fake_redis: fakeredis.FakeRedis) -> None:
    ks = KillSwitch(fake_redis, 10.0)
    total = await ks.add_and_check("gemini", 1.50)
    assert total == pytest.approx(1.5)
    total = await ks.add_and_check("gemini", 2.00)
    assert total == pytest.approx(3.5)


async def test_add_sets_ttl(fake_redis: fakeredis.FakeRedis) -> None:
    ks = KillSwitch(fake_redis, 10.0)
    await ks.add_and_check("gemini", 0.25)
    ttl = await fake_redis.ttl(_key("gemini"))
    assert 0 < ttl <= 26 * 60 * 60


async def test_cap_exceeded_raises_killswitch(fake_redis: fakeredis.FakeRedis) -> None:
    ks = KillSwitch(fake_redis, 1.0)
    assert await ks.add_and_check("gemini", 0.5) == pytest.approx(0.5)
    with pytest.raises(KillSwitchTripped):
        await ks.add_and_check("gemini", 0.6)
    assert await ks.spent("gemini") == pytest.approx(1.1)


async def test_check_raises_when_over(fake_redis: fakeredis.FakeRedis) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await fake_redis.set(f"llm_spend:gemini:{today}", "5.0")
    ks = KillSwitch(fake_redis, 1.0)
    with pytest.raises(KillSwitchTripped):
        await ks.check("gemini")


async def test_check_passes_when_under(fake_redis: fakeredis.FakeRedis) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await fake_redis.set(f"llm_spend:gemini:{today}", "0.5")
    ks = KillSwitch(fake_redis, 1.0)
    assert await ks.check("gemini") is None


async def test_per_provider_isolation(fake_redis: fakeredis.FakeRedis) -> None:
    ks = KillSwitch(fake_redis, 1.0)
    await ks.add_and_check("gemini", 0.5)
    with pytest.raises(KillSwitchTripped):
        await ks.add_and_check("gemini", 0.7)
    assert await ks.check("anthropic") is None
    assert await ks.spent("anthropic") == 0.0


async def test_reset_clears(fake_redis: fakeredis.FakeRedis) -> None:
    ks = KillSwitch(fake_redis, 100.0)
    await ks.add_and_check("gemini", 5.0)
    assert await ks.spent("gemini") == pytest.approx(5.0)
    await ks.reset("gemini")
    assert await ks.spent("gemini") == 0.0


async def test_key_format(fake_redis: fakeredis.FakeRedis) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert _key("gemini") == f"llm_spend:gemini:{today}"
    assert _key("anthropic") == f"llm_spend:anthropic:{today}"
    assert _key("gemini", "2026-01-01") == "llm_spend:gemini:2026-01-01"
