from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.audit.events import emit as emit_event
from backend.auth.deps import get_db, require_user
from backend.chat.service import (
    ChatMessage,
    ask,
    layout_for,
    list_messages,
)
from backend.config import Settings
from backend.llm.base import LLMError
from backend.runs.service import get_run

router = APIRouter()


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@router.get("/runs/{run_id}/chat", response_model=list[ChatMessage])
async def list_chat_endpoint(
    run_id: str, user=Depends(require_user), db=Depends(get_db)
) -> list[ChatMessage]:
    run = await get_run(db, run_id, user_id=user["id"])
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return await list_messages(db, run_id)


@router.post("/runs/{run_id}/chat", response_model=ChatMessage)
async def post_chat_endpoint(
    run_id: str,
    body: ChatIn,
    request: Request,
    user=Depends(require_user),
    db=Depends(get_db),
) -> ChatMessage:
    run = await get_run(db, run_id, user_id=user["id"])
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    settings: Settings = request.app.state.settings
    layout = layout_for(settings, user["id"], run_id)
    try:
        reply = await ask(
            settings,
            db=db,
            run=run,
            layout=layout,
            user_message=body.message,
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    await emit_event(
        db,
        user_id=user["id"],
        action="chat.message",
        entity="run",
        entity_id=run_id,
        payload={"len": len(body.message)},
    )
    return reply
