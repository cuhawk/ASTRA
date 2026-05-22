from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, HttpUrl

from backend.auth.deps import get_db, require_user
from backend.config import Settings
from backend.coverage.join import FeatureRow, join_coverage
from backend.coverage.recorder import Action, CoverageRecorder
from backend.coverage.service import (
    FeatureRecord,
    create_feature,
    get_feature,
    list_features,
    set_status,
    write_matched,
)
from backend.pillars.memory.runs import RunLayout
from backend.runs.service import get_run

router = APIRouter()


class CreateFeatureIn(BaseModel):
    name: str


class RecordFeatureIn(BaseModel):
    url: HttpUrl
    actions: list[Action]


@router.post("/runs/{run_id}/features", response_model=FeatureRecord, status_code=201)
async def create_feature_endpoint(
    run_id: str,
    body: CreateFeatureIn,
    user=Depends(require_user),
    db=Depends(get_db),
) -> FeatureRecord:
    run = await get_run(db, run_id, user_id=user["id"])
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return await create_feature(db, run_id=run_id, name=body.name)


@router.get("/runs/{run_id}/features", response_model=list[FeatureRecord])
async def list_features_endpoint(
    run_id: str, user=Depends(require_user), db=Depends(get_db)
) -> list[FeatureRecord]:
    run = await get_run(db, run_id, user_id=user["id"])
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return await list_features(db, run_id)


@router.post("/runs/{run_id}/features/{feature_id}/record", response_model=FeatureRecord)
async def record_feature_endpoint(
    run_id: str,
    feature_id: str,
    body: RecordFeatureIn,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> FeatureRecord:
    run = await get_run(db, run_id, user_id=user["id"])
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    feature = await get_feature(db, feature_id)
    if feature is None or feature.run_id != run_id:
        raise HTTPException(status_code=404, detail="feature not found")

    settings: Settings = request.app.state.settings
    layout = RunLayout(
        root=Path(settings.runs_root).resolve(),
        user_id=f"u{user['id']}",
        run_id=run_id,
    )
    layout.create()

    await set_status(db, feature_id, "recording")
    try:
        scope = [str(body.url).split("//", 1)[-1].split("/", 1)[0].lower()]
        recorder = CoverageRecorder(scope=scope)
        coverage = await recorder.record(
            start_url=str(body.url),
            actions=body.actions,
            feature_name=feature.name,
            save_to=layout.coverage_dir,
        )
        join = join_coverage(
            coverage_json_path=layout.coverage_dir / f"{feature.name}.json",
            layout=layout,
            feature=FeatureRow(id=feature.id, name=feature.name),
        )
        await write_matched(db, feature_id, join.matched_functions)
        await set_status(db, feature_id, "done")
    except Exception as e:
        await set_status(db, feature_id, "failed", error=f"{type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    updated = await get_feature(db, feature_id)
    assert updated is not None
    return updated
