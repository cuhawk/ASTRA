"""Per-user API key management routes.

The vault stores BYO provider keys (Anthropic today; OpenAI/etc. later) under
envelope encryption — see backend.vault.envelope.KeyVault. These routes never
return the plaintext key after it's been stored; callers can only check
presence and replace/remove it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.audit.events import emit as emit_event
from backend.auth.deps import get_db, require_user
from backend.config import Settings
from backend.vault.envelope import KeyVault

router = APIRouter()

# Only providers explicitly allow-listed here are accepted. Keeps the route
# from quietly accumulating storage for typos like "anthrop" or random
# strings supplied by clients.
ALLOWED_PROVIDERS = frozenset({"anthropic"})

_PROVIDER_PREFIXES: dict[str, tuple[str, ...]] = {
    # Anthropic public-API keys begin with "sk-ant-". We're strict on prefix
    # (cheap, catches paste mistakes) but permissive on length, because
    # Anthropic has shipped multiple key formats over time.
    "anthropic": ("sk-ant-",),
}

MIN_KEY_LEN = 20
MAX_KEY_LEN = 256


class VaultStatus(BaseModel):
    provider: str
    present: bool
    updated_at: int | None = None


class PutKeyIn(BaseModel):
    key: str = Field(min_length=MIN_KEY_LEN, max_length=MAX_KEY_LEN)


def _check_provider(provider: str) -> None:
    if provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")


def _check_key_shape(provider: str, key: str) -> None:
    prefixes = _PROVIDER_PREFIXES.get(provider)
    if prefixes and not any(key.startswith(p) for p in prefixes):
        raise HTTPException(
            status_code=422,
            detail=f"{provider} key must start with one of: {', '.join(prefixes)}",
        )


@router.get("/vault/keys/{provider}", response_model=VaultStatus)
async def get_key_status(
    provider: str,
    user=Depends(require_user),
    db=Depends(get_db),
) -> VaultStatus:
    _check_provider(provider)
    cur = await db.execute(
        "SELECT updated_at FROM api_keys_encrypted WHERE user_id = ? AND provider = ?",
        (user["id"], provider),
    )
    row = await cur.fetchone()
    await cur.close()
    if row is None:
        return VaultStatus(provider=provider, present=False)
    return VaultStatus(
        provider=provider, present=True, updated_at=int(row["updated_at"])
    )


@router.put("/vault/keys/{provider}", response_model=VaultStatus)
async def put_key(
    provider: str,
    body: PutKeyIn,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> VaultStatus:
    _check_provider(provider)
    key = body.key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="key cannot be empty")
    _check_key_shape(provider, key)

    settings: Settings = request.app.state.settings
    vault = KeyVault(settings.vault_kek_hex)
    await vault.put(db, user["id"], provider, key)
    await emit_event(
        db,
        user_id=user["id"],
        action="vault.key_saved",
        entity="api_key",
        entity_id=provider,
    )
    cur = await db.execute(
        "SELECT updated_at FROM api_keys_encrypted WHERE user_id = ? AND provider = ?",
        (user["id"], provider),
    )
    row = await cur.fetchone()
    await cur.close()
    return VaultStatus(
        provider=provider,
        present=True,
        updated_at=int(row["updated_at"]) if row else None,
    )


@router.delete("/vault/keys/{provider}", status_code=204)
async def delete_key(
    provider: str,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> Response:
    _check_provider(provider)
    settings: Settings = request.app.state.settings
    vault = KeyVault(settings.vault_kek_hex)
    deleted = await vault.delete(db, user["id"], provider)
    if not deleted:
        raise HTTPException(status_code=404, detail="key not set")
    await emit_event(
        db,
        user_id=user["id"],
        action="vault.key_removed",
        entity="api_key",
        entity_id=provider,
    )
    return Response(status_code=204)
