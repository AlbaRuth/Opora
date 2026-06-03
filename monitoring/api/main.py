"""FastAPI entrypoint for Opora Monitor."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from core.config import get_settings
from db.session import verify_async_db_on_startup
from monitoring.api.routes import chats, sandbox, traces
from monitoring.api.schemas import HealthResponse

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Opora Monitor",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )
    cors_origins = list(dict.fromkeys(settings.monitoring_cors_origins_list))
    if settings.is_development:
        for origin in (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ):
            if origin not in cors_origins:
                cors_origins.append(origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    app.include_router(chats.router)
    app.include_router(sandbox.router)
    app.include_router(traces.router)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_request: Request, exc: IntegrityError) -> JSONResponse:
        logger.exception("monitor_api_integrity_error", error=str(exc))
        return JSONResponse(status_code=409, content={"detail": "Database integrity error during request."})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("monitor_api_unhandled_error", error=str(exc))
        detail = str(exc) if settings.is_development else "Internal server error"
        return JSONResponse(status_code=500, content={"detail": detail})

    @app.on_event("startup")
    async def _startup() -> None:
        await verify_async_db_on_startup()

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app

app = create_app()
