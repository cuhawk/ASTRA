from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.audit.events import ActivityEvent, list_for_user
from backend.auth.deps import get_db, require_user

router = APIRouter()


@router.get("/activity", response_model=list[ActivityEvent])
async def list_activity_endpoint(
    user=Depends(require_user),
    db=Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> list[ActivityEvent]:
    return await list_for_user(db, user["id"], limit=limit)
