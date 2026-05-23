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


@router.get("/runs/{run_id}/files", response_model=list[str])
async def list_run_files_endpoint(
    run_id: str,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> list[str]:
    rec = await get_run(db, run_id, user_id=user["id"])
    if rec is None:
        raise HTTPException(status_code=404, detail="run not found")
    
    settings = request.app.state.settings
    layout = RunLayout(
        root=Path(settings.runs_root).resolve(),
        user_id=f"u{user['id']}",
        run_id=run_id,
    )
    if not layout.sourcemap_dir.is_dir():
        return []
    
    exts = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
    skip_segments = {"node_modules", ".git", "dist", "build", "_nomap"}
    files = []
    for path in sorted(layout.sourcemap_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in exts:
            continue
        rel_parts = path.relative_to(layout.sourcemap_dir).parts
        if any(p in skip_segments for p in rel_parts):
            continue
        files.append(path.relative_to(layout.sourcemap_dir).as_posix())
    return files


@router.get("/runs/{run_id}/files/content", response_model=dict[str, str])
async def get_run_file_content_endpoint(
    run_id: str,
    path: str,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> dict[str, str]:
    rec = await get_run(db, run_id, user_id=user["id"])
    if rec is None:
        raise HTTPException(status_code=404, detail="run not found")
        
    settings = request.app.state.settings
    layout = RunLayout(
        root=Path(settings.runs_root).resolve(),
        user_id=f"u{user['id']}",
        run_id=run_id,
    )
    
    try:
        resolved_root = layout.sourcemap_dir.resolve()
        requested_path = (resolved_root / path).resolve()
        if not requested_path.is_relative_to(resolved_root):
            raise HTTPException(status_code=400, detail="invalid path")
        if not requested_path.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        
        content = requested_path.read_text(encoding="utf-8", errors="replace")
        return {"content": content}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

