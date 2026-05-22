from __future__ import annotations

import os
import time

import aiosqlite
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class VaultError(Exception):
    pass


class KekInvalid(VaultError):
    pass


class KeyVault:
    """Envelope-encrypts user-supplied secrets (provider API keys).

    Layout in DB row:
      (dek_ciphertext, dek_nonce)  = AES-GCM(KEK, DEK) with random 12-byte nonce
      (key_ciphertext, key_nonce)  = AES-GCM(DEK, plaintext) with random 12-byte nonce

    KEK is operator-supplied at boot (env). DEK is a fresh 32-byte random per
    put(). Rotating the KEK only requires re-wrapping each DEK; the inner
    payload doesn't need to change. (KEK rotation is out of scope for MVP
    but the structure is rotation-friendly.)
    """

    def __init__(self, kek_hex: str) -> None:
        try:
            kek = bytes.fromhex(kek_hex)
        except ValueError as e:
            raise KekInvalid("kek_hex must be hex") from e
        if len(kek) != 32:
            raise KekInvalid(f"kek must be 32 bytes (64 hex), got {len(kek)}")
        self._kek = AESGCM(kek)

    async def put(
        self,
        db: aiosqlite.Connection,
        user_id: int,
        provider: str,
        plaintext: str,
    ) -> None:
        dek_raw = AESGCM.generate_key(bit_length=256)
        dek = AESGCM(dek_raw)
        dek_nonce = os.urandom(12)
        key_nonce = os.urandom(12)
        aad = f"{user_id}:{provider}".encode()
        key_ct = dek.encrypt(key_nonce, plaintext.encode("utf-8"), associated_data=aad)
        dek_ct = self._kek.encrypt(dek_nonce, dek_raw, associated_data=aad)
        now = int(time.time())
        await db.execute(
            "INSERT INTO api_keys_encrypted "
            "(user_id, provider, dek_ciphertext, dek_nonce, key_ciphertext, key_nonce, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, provider) DO UPDATE SET "
            "  dek_ciphertext = excluded.dek_ciphertext, "
            "  dek_nonce      = excluded.dek_nonce, "
            "  key_ciphertext = excluded.key_ciphertext, "
            "  key_nonce      = excluded.key_nonce, "
            "  updated_at     = excluded.updated_at",
            (user_id, provider, dek_ct, dek_nonce, key_ct, key_nonce, now, now),
        )
        await db.commit()

    async def get(
        self,
        db: aiosqlite.Connection,
        user_id: int,
        provider: str,
    ) -> str | None:
        cur = await db.execute(
            "SELECT dek_ciphertext, dek_nonce, key_ciphertext, key_nonce "
            "FROM api_keys_encrypted WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        dek_ct, dek_nonce, key_ct, key_nonce = row[0], row[1], row[2], row[3]
        aad = f"{user_id}:{provider}".encode()
        try:
            dek_raw = self._kek.decrypt(bytes(dek_nonce), bytes(dek_ct), associated_data=aad)
        except Exception as e:
            raise VaultError("DEK unwrap failed") from e
        dek = AESGCM(dek_raw)
        try:
            pt = dek.decrypt(bytes(key_nonce), bytes(key_ct), associated_data=aad)
        except Exception as e:
            raise VaultError("key decrypt failed") from e
        return pt.decode("utf-8")

    async def delete(
        self,
        db: aiosqlite.Connection,
        user_id: int,
        provider: str,
    ) -> bool:
        cur = await db.execute(
            "DELETE FROM api_keys_encrypted WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        )
        await db.commit()
        return cur.rowcount > 0
