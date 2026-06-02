"""FastAPI entrypoint for Opora Monitor."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from db.session import verify_async_db_on_startup
from monitoring.api.routes import chats, sandbox, traces
from monitoring.api.schemas import HealthResponse


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Opora Monitor",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.monitoring_cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chats.router)
    app.include_router(sandbox.router)
    app.include_router(traces.router)

    @app.on_event("startup")
    async def _startup() -> None:
        await verify_async_db_on_startup()

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
