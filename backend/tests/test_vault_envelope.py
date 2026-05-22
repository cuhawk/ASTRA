from __future__ import annotations

import aiosqlite
import pytest

from backend.vault.envelope import KekInvalid, KeyVault, VaultError


async def _make_user(db: aiosqlite.Connection, github_id: int = 999) -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, ?, ?, strftime('%s', 'now'), strftime('%s', 'now'))",
        (github_id, f"test-{github_id}", None),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = ?", (github_id,))
    row = await cur.fetchone()
    assert row is not None
    return row["id"]


@pytest.mark.asyncio
async def test_put_get_roundtrip(db: aiosqlite.Connection, vault_kek_hex: str) -> None:
    user_id = await _make_user(db)
    vault = KeyVault(vault_kek_hex)
    await vault.put(db, user_id, "anthropic", "sk-ant-test")
    got = await vault.get(db, user_id, "anthropic")
    assert got == "sk-ant-test"


@pytest.mark.asyncio
async def test_get_missing_returns_none(db: aiosqlite.Connection, vault_kek_hex: str) -> None:
    user_id = await _make_user(db)
    vault = KeyVault(vault_kek_hex)
    assert await vault.get(db, user_id, "anthropic") is None


@pytest.mark.asyncio
async def test_put_overwrites(db: aiosqlite.Connection, vault_kek_hex: str) -> None:
    user_id = await _make_user(db)
    vault = KeyVault(vault_kek_hex)
    await vault.put(db, user_id, "anthropic", "k1")
    await vault.put(db, user_id, "anthropic", "k2")
    assert await vault.get(db, user_id, "anthropic") == "k2"
    cur = await db.execute(
        "SELECT COUNT(*) AS c FROM api_keys_encrypted WHERE user_id = ? AND provider = ?",
        (user_id, "anthropic"),
    )
    row = await cur.fetchone()
    assert row["c"] == 1


@pytest.mark.asyncio
async def test_delete_returns_true_when_present(
    db: aiosqlite.Connection, vault_kek_hex: str
) -> None:
    user_id = await _make_user(db)
    vault = KeyVault(vault_kek_hex)
    await vault.put(db, user_id, "anthropic", "sk-ant-test")
    assert await vault.delete(db, user_id, "anthropic") is True
    assert await vault.get(db, user_id, "anthropic") is None


@pytest.mark.asyncio
async def test_delete_returns_false_when_absent(
    db: aiosqlite.Connection, vault_kek_hex: str
) -> None:
    user_id = await _make_user(db)
    vault = KeyVault(vault_kek_hex)
    assert await vault.delete(db, user_id, "anthropic") is False


@pytest.mark.asyncio
async def test_aad_isolation_user_id(
    db: aiosqlite.Connection, vault_kek_hex: str
) -> None:
    user_a = await _make_user(db, github_id=1001)
    user_b = await _make_user(db, github_id=1002)
    vault = KeyVault(vault_kek_hex)
    await vault.put(db, user_a, "anthropic", "sk-ant-A")

    await db.execute(
        "DELETE FROM api_keys_encrypted WHERE user_id = ? AND provider = ?",
        (user_b, "anthropic"),
    )
    await db.execute(
        "UPDATE api_keys_encrypted SET user_id = ? WHERE user_id = ? AND provider = ?",
        (user_b, user_a, "anthropic"),
    )
    await db.commit()

    with pytest.raises(VaultError):
        await vault.get(db, user_b, "anthropic")


@pytest.mark.asyncio
async def test_aad_isolation_provider(
    db: aiosqlite.Connection, vault_kek_hex: str
) -> None:
    user_id = await _make_user(db)
    vault = KeyVault(vault_kek_hex)
    await vault.put(db, user_id, "anthropic", "sk-ant-A")

    await db.execute(
        "UPDATE api_keys_encrypted SET provider = ? WHERE user_id = ? AND provider = ?",
        ("openai", user_id, "anthropic"),
    )
    await db.commit()

    with pytest.raises(VaultError):
        await vault.get(db, user_id, "openai")


def test_kek_invalid_hex_raises() -> None:
    with pytest.raises(KekInvalid):
        KeyVault("not-hex")


def test_kek_wrong_length_raises() -> None:
    with pytest.raises(KekInvalid):
        KeyVault("00" * 16)


@pytest.mark.asyncio
async def test_plaintext_not_in_ciphertext(
    db: aiosqlite.Connection, vault_kek_hex: str
) -> None:
    user_id = await _make_user(db)
    vault = KeyVault(vault_kek_hex)
    marker = "supersecret-marker-abcdef"
    await vault.put(db, user_id, "anthropic", marker)
    cur = await db.execute(
        "SELECT dek_ciphertext, key_ciphertext FROM api_keys_encrypted "
        "WHERE user_id = ? AND provider = ?",
        (user_id, "anthropic"),
    )
    row = await cur.fetchone()
    assert row is not None
    dek_ct = bytes(row["dek_ciphertext"])
    key_ct = bytes(row["key_ciphertext"])
    assert marker.encode() not in key_ct
    assert marker.encode() not in dek_ct
