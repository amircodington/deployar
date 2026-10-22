"""FastAPI app factory and the `deployar-agent` entry point."""

import uvicorn
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Deployar agent")

    @app.get("/api/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()


def run() -> None:
    # Host process for the ~/.claude login; loopback only, Docker Desktop's host.docker.internal reaches it.
    uvicorn.run("deployar.main:app", host="127.0.0.1", port=8000, reload=True)
