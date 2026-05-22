from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.auth.deps import require_user
from backend.config import Settings
from backend.llm.base import KillSwitchTripped, LLMError
from backend.llm.router import LLMRouter
from backend.vault.envelope import KeyVault


def _router(request: Request) -> LLMRouter:
    settings: Settings = request.app.state.settings
    vault = KeyVault(settings.vault_kek_hex)
    return LLMRouter(settings=settings, redis_client=request.app.state.redis, vault=vault)


router = APIRouter()


class CompletionRequest(BaseModel):
    prompt: str


class CompletionOut(BaseModel):
    text: str
    provider: str
    model: str
    cost_usd: float
    duration_ms: int


@router.post("/llm/nl_to_cypher", response_model=CompletionOut)
async def nl_to_cypher(
    body: CompletionRequest, request: Request, user=Depends(require_user)
) -> CompletionOut:
    r = _router(request)
    try:
        resp = await r.nl_to_cypher(user["id"], body.prompt)
    except KillSwitchTripped as e:
        raise HTTPException(status_code=503, detail=f"killswitch: {e}") from e
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return CompletionOut(
        text=resp.text,
        provider=resp.provider,
        model=resp.model,
        cost_usd=resp.cost_usd,
        duration_ms=resp.duration_ms,
    )


class AdviseRequest(BaseModel):
    prompt: str
    prefer_opus: bool = False


@router.post("/llm/advise", response_model=CompletionOut)
async def advise(
    body: AdviseRequest, request: Request, user=Depends(require_user)
) -> CompletionOut:
    r = _router(request)
    try:
        resp = await r.advise(user["id"], body.prompt, prefer_opus=body.prefer_opus)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return CompletionOut(
        text=resp.text,
        provider=resp.provider,
        model=resp.model,
        cost_usd=resp.cost_usd,
        duration_ms=resp.duration_ms,
    )


@router.get("/llm/spend")
async def spend(request: Request, user=Depends(require_user)) -> dict[str, float]:
    r = _router(request)
    return await r.spend_today()
