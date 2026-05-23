"""Background worker: acquire → callgraph → Kuzu writes.

Runs as a FastAPI BackgroundTask in-process for MVP. Production should swap
this in for an RQ/Dramatiq handler — the function signature is queue-agnostic.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from backend.audit.events import emit as emit_event
from backend.config import Settings
from backend.db.connection import connect
from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout
from backend.pillars.sast.acquisition import Pipeline
from backend.pillars.sast.callgraph_native import extract_tree
from backend.runs.service import RunRecord, set_status, write_metrics


def _scope_for(url: str) -> list[str]:
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    return [host.lower()]


async def execute_run(rec: RunRecord, settings: Settings) -> None:
    db_path = settings.db_path
    layout = RunLayout(
        root=Path(settings.runs_root).resolve(),
        user_id=f"u{rec.user_id}",
        run_id=rec.id,
    )

    db = await connect(db_path)
    try:
        await set_status(db, rec.id, "acquiring")
    finally:
        await db.close()

    try:
        if rec.url:
            pipeline = Pipeline(scope=_scope_for(rec.url))
            await pipeline.acquire(rec.url, layout)
    except Exception as e:
        db = await connect(db_path)
        try:
            await set_status(db, rec.id, "failed", error=f"acquire: {type(e).__name__}: {e}")
            await emit_event(
                db,
                user_id=rec.user_id,
                action="run.failed",
                entity="run",
                entity_id=rec.id,
                payload={"stage": "acquire", "error": f"{type(e).__name__}: {e}"},
            )
        finally:
            await db.close()
        return

    db = await connect(db_path)
    try:
        await set_status(db, rec.id, "analyzing")
    finally:
        await db.close()

    try:
        file_results = extract_tree(layout.sourcemap_dir)
        function_count = 0
        edge_count = 0
        function_id_set: set[str] = set()
        with GraphStore(layout.graph_path) as g:
            for fr in file_results:
                for fn in fr.functions:
                    g.add_node(
                        "Function",
                        {
                            "id": fn.id,
                            "name": fn.name,
                            "path": fn.path,
                            "kind": fn.kind,
                            "start_line": fn.start_line,
                            "end_line": fn.end_line,
                        },
                    )
                    function_id_set.add(fn.id)
                    function_count += 1
                for edge in fr.edges:
                    if not edge.from_id or edge.from_id not in function_id_set:
                        continue
                    target = next(
                        (f for f in fr.functions if f.name == edge.callee_name),
                        None,
                    )
                    if target is None:
                        continue
                    g.add_edge("Function", edge.from_id, "Function", target.id, "CALLS")
                    edge_count += 1
    except Exception as e:
        db = await connect(db_path)
        try:
            await set_status(db, rec.id, "failed", error=f"analyze: {type(e).__name__}: {e}")
            await emit_event(
                db,
                user_id=rec.user_id,
                action="run.failed",
                entity="run",
                entity_id=rec.id,
                payload={"stage": "analyze", "error": f"{type(e).__name__}: {e}"},
            )
        finally:
            await db.close()
        return

    db = await connect(db_path)
    try:
        await write_metrics(
            db,
            rec.id,
            files=len(file_results),
            functions=function_count,
            edges=edge_count,
        )
        await set_status(db, rec.id, "done")
        await emit_event(
            db,
            user_id=rec.user_id,
            action="run.done",
            entity="run",
            entity_id=rec.id,
            payload={
                "files": len(file_results),
                "functions": function_count,
                "edges": edge_count,
            },
        )
    finally:
        await db.close()


def make_executor(settings: Settings):
    async def _run(rec: RunRecord) -> None:
        await execute_run(rec, settings)

    return _run
