from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, HttpUrl

from backend.audit.events import emit as emit_event
from backend.auth.deps import get_db, require_user
from backend.pillars.memory.runs import RunLayout
from backend.runs.service import (
    RunRecord,
    create_run,
    delete_run,
    get_run,
    list_runs,
)

router = APIRouter()


class CreateRunIn(BaseModel):
    url: HttpUrl


@router.post("/runs", status_code=202, response_model=RunRecord)
async def create_run_endpoint(
    body: CreateRunIn,
    bg: BackgroundTasks,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> RunRecord:
    rec = await create_run(db, user_id=user["id"], url=str(body.url))
    await emit_event(
        db,
        user_id=user["id"],
        action="run.created",
        entity="run",
        entity_id=rec.id,
        payload={"url": rec.url},
    )
    executor = getattr(request.app.state, "run_executor", None)
    if executor is not None:
        bg.add_task(executor, rec)
    return rec


@router.get("/runs", response_model=list[RunRecord])
async def list_runs_endpoint(
    user=Depends(require_user), db=Depends(get_db)
) -> list[RunRecord]:
    return await list_runs(db, user["id"])


@router.get("/runs/{run_id}", response_model=RunRecord)
async def get_run_endpoint(
    run_id: str, user=Depends(require_user), db=Depends(get_db)
) -> RunRecord:
    rec = await get_run(db, run_id, user_id=user["id"])
    if rec is None:
        raise HTTPException(status_code=404, detail="run not found")
    return rec


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run_endpoint(
    run_id: str,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> Response:
    deleted = await delete_run(db, run_id, user_id=user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="run not found")
    await emit_event(
        db,
        user_id=user["id"],
        action="run.deleted",
        entity="run",
        entity_id=run_id,
    )
    settings = request.app.state.settings
    try:
        layout = RunLayout(
            root=Path(settings.runs_root).resolve(),
            user_id=f"u{user['id']}",
            run_id=run_id,
        )
        layout.purge()
    except Exception:
        # Filesystem cleanup is best-effort; SQLite row is the source of truth.
        pass
    return Response(status_code=204)
