"""Health and readiness endpoints."""

from typing import Any, Dict

import redis.asyncio as aioredis
from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.db.session import check_db_health
from app.services.agent.prime_agent import PrimeAgentRuntime
from app.services.ai.ollama import OllamaProvider

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """Liveness probe: verifies that the HTTP server is running and accepting traffic."""
    return {
        "status": "UP",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ready")
async def readiness_check(response: Response) -> Dict[str, Any]:
    """Readiness probe: verifies operational dependencies (Database, Redis, AI, Agent)."""
    db_ok = await check_db_health()

    # Redis check
    redis_ok = False
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        redis_ok = await r.ping()
        await r.aclose()
    except Exception:
        redis_ok = False

    # AI Provider & Agent Runtime status
    ai_provider = OllamaProvider()
    ai_ok = await ai_provider.health_check()

    agent_runtime = PrimeAgentRuntime()
    agent_status = await agent_runtime.health_check()

    all_critical_healthy = db_ok and redis_ok

    if not all_critical_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "READY" if all_critical_healthy else "DEGRADED",
        "database": {"connected": db_ok, "driver": "asyncpg"},
        "redis": {"connected": redis_ok},
        "ai_provider": {
            "type": settings.AI_PROVIDER_TYPE,
            "connected": ai_ok,
            "target": "local_ollama",
        },
        "agent_runtime": agent_status,
    }
