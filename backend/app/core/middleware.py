"""HTTP Middlewares: Correlation ID, request tracking, and centralized error handling."""

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import logger


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns or propagates an X-Correlation-ID for every incoming request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        start_time = time.time()
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"

        # Structured request logging
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} ({process_time:.2f}ms)",
            extra={"correlation_id": correlation_id},
        )
        return response
