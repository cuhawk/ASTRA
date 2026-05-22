from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.auth.deps import get_db, require_user
from backend.config import Settings
from backend.cypher.nl import NLToCypher
from backend.cypher.playbooks import PLAYBOOKS, Playbook, render
from backend.cypher.runner import run_cypher
from backend.cypher.validate import CypherForbidden
from backend.llm.base import KillSwitchTripped, LLMError
from backend.llm.router import LLMRouter
from backend.pillars.memory.runs import RunLayout
from backend.runs.service import get_run
from backend.vault.envelope import KeyVault

router = APIRouter()


def _layout(request: Request, user_id: int, run_id: str) -> RunLayout:
    settings: Settings = request.app.state.settings
    return RunLayout(
        root=Path(settings.runs_root).resolve(),
        user_id=f"u{user_id}",
        run_id=run_id,
    )


async def _require_run(db, user, run_id):
    run = await get_run(db, run_id, user_id=user["id"])
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


class CypherIn(BaseModel):
    query: str
    params: dict | None = None


class CypherOut(BaseModel):
    cypher: str
    rows: list[dict]
    row_count: int
    duration_ms: int


@router.post("/runs/{run_id}/cypher", response_model=CypherOut)
async def cypher_endpoint(
    run_id: str, body: CypherIn, request: Request, user=Depends(require_user), db=Depends(get_db)
) -> CypherOut:
    await _require_run(db, user, run_id)
    layout = _layout(request, user["id"], run_id)
    try:
        result = run_cypher(layout, body.query, body.params)
    except CypherForbidden as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return CypherOut(**result.model_dump())


class NLIn(BaseModel):
    prompt: str


class NLOut(CypherOut):
    nl_prompt: str


@router.post("/runs/{run_id}/nl", response_model=NLOut)
async def nl_endpoint(
    run_id: str, body: NLIn, request: Request, user=Depends(require_user), db=Depends(get_db)
) -> NLOut:
    await _require_run(db, user, run_id)
    settings: Settings = request.app.state.settings
    nl = NLToCypher(settings)
    try:
        cypher, _llm = await nl.translate(body.prompt)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    layout = _layout(request, user["id"], run_id)
    try:
        result = run_cypher(layout, cypher)
    except CypherForbidden as e:
        raise HTTPException(
            status_code=400,
            detail=f"translated cypher rejected by validator: {e} ({cypher!r})",
        ) from e
    return NLOut(nl_prompt=body.prompt, **result.model_dump())


@router.get("/playbooks", response_model=list[Playbook])
async def list_playbooks_endpoint(user=Depends(require_user)) -> list[Playbook]:
    return list(PLAYBOOKS.values())


class PlaybookExecIn(BaseModel):
    params: dict | None = None


@router.post("/runs/{run_id}/playbooks/{slug}", response_model=CypherOut)
async def execute_playbook_endpoint(
    run_id: str,
    slug: str,
    body: PlaybookExecIn,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> CypherOut:
    await _require_run(db, user, run_id)
    try:
        cypher, params = render(slug, body.params)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    layout = _layout(request, user["id"], run_id)
    try:
        result = run_cypher(layout, cypher, params)
    except CypherForbidden as e:
        raise HTTPException(status_code=500, detail=f"playbook violates validator: {e}") from e
    return CypherOut(**result.model_dump())


class AdviseIn(BaseModel):
    prompt: str
    prefer_opus: bool = False


class AdviseOut(BaseModel):
    text: str
    provider: str
    model: str
    cost_usd: float
    duration_ms: int


@router.post("/runs/{run_id}/advise", response_model=AdviseOut)
async def advise_endpoint(
    run_id: str,
    body: AdviseIn,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> AdviseOut:
    await _require_run(db, user, run_id)
    settings: Settings = request.app.state.settings
    vault = KeyVault(settings.vault_kek_hex)
    llm_router = LLMRouter(settings=settings, redis_client=request.app.state.redis, vault=vault)
    try:
        resp = await llm_router.advise(user["id"], body.prompt, prefer_opus=body.prefer_opus)
    except KillSwitchTripped as e:
        raise HTTPException(status_code=503, detail=f"killswitch: {e}") from e
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AdviseOut(
        text=resp.text,
        provider=resp.provider,
        model=resp.model,
        cost_usd=resp.cost_usd,
        duration_ms=resp.duration_ms,
    )
