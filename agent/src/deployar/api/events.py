"""GET /api/runs/{id}/events: SSE from the run's Redis stream; resumes after Last-Event-ID."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from deployar.api.deps import get_runtime, require_user
from deployar.api.runs import owned_run
from deployar.runtime.orchestrator import Runtime

router = APIRouter(prefix="/api/runs")


@router.get("/{run_id}/events")
async def events(
    run_id: uuid.UUID,
    request: Request,
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    rt: Annotated[Runtime, Depends(get_runtime)],
    last_event_id: Annotated[str | None, Header()] = None,
    after: str | None = None,  # the web client's own reconnect, when EventSource gave up (no header then)
) -> StreamingResponse:
    await owned_run(rt, run_id, user_id)

    async def stream() -> AsyncIterator[str]:
        cursor = last_event_id or after or "0"
        while not await request.is_disconnected():
            batch = await rt.bus.read(run_id, cursor, block_ms=15000)
            if not batch:
                yield ": ping\n\n"  # keeps proxies from closing an idle stream
                continue
            for entry_id, env in batch:
                cursor = entry_id
                yield f"id: {entry_id}\nevent: {env.type}\ndata: {env.model_dump_json()}\n\n"
                if env.type == "run.done":
                    return

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)
