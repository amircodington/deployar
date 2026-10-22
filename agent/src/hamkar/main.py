"""FastAPI app factory and the `hamkar-agent` entry point."""

import uvicorn
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Hamkar agent")

    @app.get("/api/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()


def run() -> None:
    # Host process for the ~/.claude login; loopback only, Docker Desktop's host.docker.internal reaches it.
    uvicorn.run("hamkar.main:app", host="127.0.0.1", port=8000, reload=True)
