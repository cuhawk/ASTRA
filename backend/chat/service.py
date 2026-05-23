"""Per-run chat thread persistence + Gemini Flash invocation.

Conversation is grounded in the run's callgraph (function/edge counts plus a
small sample of top function names). We never feed the LLM the entire graph —
that would dominate the prompt and cost. The transcript itself lives in
audit_llm_calls.prompt_text/response_text; this table only stores the
user-facing turns.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

import aiosqlite
from pydantic import BaseModel

from backend.config import Settings
from backend.llm.base import LLMError
from backend.llm.gemini import GeminiClient
from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout
from backend.runs.service import RunRecord

Role = Literal["user", "assistant"]

MAX_HISTORY_TURNS = 30
MAX_CONTEXT_FUNCTIONS = 25


class ChatMessage(BaseModel):
    id: int
    run_id: str
    role: Role
    content: str
    llm_call_id: int | None
    created_at: int


async def list_messages(
    db: aiosqlite.Connection, run_id: str
) -> list[ChatMessage]:
    cur = await db.execute(
        "SELECT id, run_id, role, content, llm_call_id, created_at "
        "FROM chat_messages WHERE run_id = ? ORDER BY id ASC",
        (run_id,),
    )
    rows = await cur.fetchall()
    await cur.close()
    return [ChatMessage(**dict(r)) for r in rows]


async def append_message(
    db: aiosqlite.Connection,
    *,
    run_id: str,
    role: Role,
    content: str,
    llm_call_id: int | None = None,
) -> ChatMessage:
    now = int(time.time())
    cur = await db.execute(
        "INSERT INTO chat_messages (run_id, role, content, llm_call_id, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, role, content, llm_call_id, now),
    )
    rowid = int(cur.lastrowid or 0)
    await cur.close()
    await db.commit()
    return ChatMessage(
        id=rowid,
        run_id=run_id,
        role=role,
        content=content,
        llm_call_id=llm_call_id,
        created_at=now,
    )


def _build_run_context(run: RunRecord, layout: RunLayout) -> str:
    """Run-scoped facts injected as the first (cacheable) user turn.

    Kept deterministic across calls — same string for the same run state —
    so the implicit context cache hits across chat turns.
    """
    parts: list[str] = []
    parts.append(
        f"[ASTRA RUN CONTEXT]\n"
        f"run_id={run.id} url={run.url or '(none)'} status={run.status}"
    )
    parts.append(
        f"metrics: files={run.files} functions={run.functions} edges={run.edges}"
    )
    try:
        with GraphStore(layout.graph_path) as g:
            rows = g.query(
                "MATCH (f:Function) RETURN f.name AS name, f.path AS path "
                "ORDER BY f.name LIMIT $k",
                {"k": MAX_CONTEXT_FUNCTIONS},
            )
        if rows:
            sample = ", ".join(
                f"{r['name']}@{(r['path'] or '').split('/')[-1] or '?'}"
                for r in rows
                if r.get("name")
            )
            parts.append(f"top_functions({len(rows)}): {sample}")
    except Exception as exc:  # graph read is best-effort
        parts.append(f"graph_read_failed: {type(exc).__name__}: {exc}")
    parts.append(
        "I will answer all questions strictly within this run's scope."
    )
    return "\n".join(parts)


# Static system instruction. Kept short and identical across every chat turn
# so Gemini's implicit cache can include it in the cached prefix.
SYSTEM_PROMPT = (
    "You are ASTRA's run-scoped assistant. Answer questions about the "
    "single JavaScript run described in the user's first message. "
    "Be terse, technical, concrete. Never invent functions or files. "
    "If unknown, say so."
)

PRIMING_ACK = "Acknowledged. Ready for questions about this run."


def _build_contents(
    history: list[ChatMessage], run: RunRecord, layout: RunLayout, user_turn: str
) -> list[dict]:
    """Produce a `contents` array with a stable prefix.

    Layout:
        [user] run-context primer        ← stable per (run, run state)
        [model] PRIMING_ACK              ← stable
        [user] ... persisted history     ← grows turn by turn
        [model] ...
        [user] <new user_turn>           ← changes every call
    Gemini implicit caching keys on the longest repeated prefix, so the
    first two turns + as many prior turns as already happened become cache
    hits on every follow-up call.
    """
    contents: list[dict] = [
        {"role": "user", "parts": [{"text": _build_run_context(run, layout)}]},
        {"role": "model", "parts": [{"text": PRIMING_ACK}]},
    ]
    for m in history[-MAX_HISTORY_TURNS:]:
        role = "user" if m.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.content}]})
    contents.append({"role": "user", "parts": [{"text": user_turn}]})
    return contents


async def ask(
    settings: Settings,
    *,
    db: aiosqlite.Connection,
    run: RunRecord,
    layout: RunLayout,
    user_message: str,
) -> ChatMessage:
    history = await list_messages(db, run.id)
    await append_message(db, run_id=run.id, role="user", content=user_message)

    contents = _build_contents(history, run, layout, user_message)

    client = GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        embed_model=settings.gemini_embed_model,
    )
    try:
        resp = await client.generate(
            contents=contents, system=SYSTEM_PROMPT, max_tokens=2048
        )
    except LLMError:
        await append_message(
            db,
            run_id=run.id,
            role="assistant",
            content="(chat: provider error — see server logs)",
        )
        raise

    transcript_prompt = _render_for_audit(contents)
    call_id = await _write_chat_audit(
        db,
        run=run,
        prompt=transcript_prompt,
        system=SYSTEM_PROMPT,
        resp_text=resp.text,
        resp=resp,
    )
    return await append_message(
        db,
        run_id=run.id,
        role="assistant",
        content=resp.text,
        llm_call_id=call_id,
    )


def _render_for_audit(contents: list[dict]) -> str:
    """Flatten multi-turn contents into a single string for audit storage.
    Only used for forensics; not sent to the model."""
    out: list[str] = []
    for turn in contents:
        role = (turn.get("role") or "?").upper()
        text = "".join(p.get("text", "") for p in (turn.get("parts") or []))
        out.append(f"{role}: {text}")
    return "\n".join(out)


async def _write_chat_audit(
    db: aiosqlite.Connection,
    *,
    run: RunRecord,
    prompt: str,
    system: str,
    resp_text: str,
    resp,  # LLMResponse
) -> int:
    cur = await db.execute(
        "INSERT INTO audit_llm_calls "
        "(user_id, provider, model, reason, prompt_tokens, completion_tokens, "
        " cached_prompt_tokens, cost_usd, outcome, duration_ms, at, "
        " prompt_text, response_text) "
        "VALUES (?, 'gemini', ?, 'chat', ?, ?, ?, ?, 'ok', ?, "
        " strftime('%s','now'), ?, ?)",
        (
            run.user_id,
            resp.model,
            resp.usage.prompt_tokens,
            resp.usage.completion_tokens,
            resp.usage.cached_prompt_tokens,
            resp.cost_usd,
            resp.duration_ms,
            f"[SYSTEM]\n{system}\n\n[PROMPT]\n{prompt}",
            resp_text,
        ),
    )
    call_id = int(cur.lastrowid or 0)
    await cur.close()
    await db.commit()
    return call_id


def layout_for(settings: Settings, user_id: int, run_id: str) -> RunLayout:
    return RunLayout(
        root=Path(settings.runs_root).resolve(),
        user_id=f"u{user_id}",
        run_id=run_id,
    )
