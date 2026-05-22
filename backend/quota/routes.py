from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.auth.deps import require_user
from backend.quota.middleware import enforce_quota, get_quota_counter

router = APIRouter()


@router.get("/probe/quota")
async def probe_quota(
    request: Request, user: dict[str, Any] = Depends(require_user)
) -> dict[str, int]:
    new_used = await enforce_quota(
        user_id=user["id"], reason="probe", units=1, request=request
    )
    counter = get_quota_counter(request)
    remaining = await counter.remaining(user["id"])
    limit = request.app.state.settings.free_tier_daily_limit
    return {"used": new_used, "limit": limit, "remaining": remaining}
