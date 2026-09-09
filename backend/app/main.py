"""FastAPI application factory and lifecycle management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_root_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.middleware import CorrelationIdMiddleware
from app.db.base import Base
from app.db.seeds import seed_news9_tenant
from app.db.session import async_session_factory, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and graceful shutdown lifecycle."""
    setup_logging(level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info(f"Starting {settings.APP_NAME} ({settings.ENVIRONMENT})")

    # In development or test environments, auto-create base tables and seed initial tenant
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_factory() as session:
            await seed_news9_tenant(session)
    except Exception as e:
        logger.warning(
            f"Database initialization warning on startup (will be verified via /ready): {e}"
        )

    yield

    logger.info(f"Shutting down {settings.APP_NAME}")
    await engine.dispose()


def create_application() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # Middlewares
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        logger.error(
            f"Unhandled exception during {request.method} {request.url.path}: {exc}",
            exc_info=True,
            extra={"correlation_id": correlation_id},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": (
                    "An unexpected error occurred. "
                    "Please contact support with the correlation ID."
                ),
                "correlation_id": correlation_id,
            },
        )

    # Root health and readiness routes (for Docker/k8s probes)
    app.include_router(health_root_router)

    # Versioned API routes
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
