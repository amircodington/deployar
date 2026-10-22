"""FastAPI app factory and the `deployar-agent` entry point."""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from deployar.api import approvals, connections, events, runs, session
from deployar.core.errors import DeployarError

# HTTP status per error code; anything unlisted is a 400.
_STATUS = {
    "approval_bad_signature": 403, "approval_not_pending": 409, "no_user": 401, "unauthorized": 401,
    "bad_passphrase": 401, "not_found": 404, "no_liara_connection": 404, "liara_unauthorized": 400,
    "liara_unreachable": 502,
}  # fmt: skip


def create_app() -> FastAPI:
    app = FastAPI(title="Deployar agent")
    for module in (session, runs, events, approvals, connections):
        app.include_router(module.router)

    @app.exception_handler(DeployarError)
    async def deployar_error(_request: Request, e: DeployarError) -> JSONResponse:
        body = {"error": {"code": e.code, "message_fa": e.message_fa, "detail": e.detail}}
        return JSONResponse(body, status_code=_STATUS.get(e.code, 400))

    @app.get("/api/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()


def run() -> None:
    # Host process for the ~/.claude login; loopback only, Docker Desktop's host.docker.internal reaches it.
    uvicorn.run("deployar.main:app", host="127.0.0.1", port=8800, reload=True)
