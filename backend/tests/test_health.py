"""Tests for /health and /ready endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness_endpoint(client: AsyncClient):
    """Verifies that the /health liveness probe returns HTTP 200 and UP status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert "News 9 AI Content" in data["app_name"]
    assert "version" in data


@pytest.mark.asyncio
async def test_readiness_probe_returns_dependency_status(client: AsyncClient):
    """Verifies that /ready inspects database, redis, AI, and agent status."""
    response = await client.get("/ready")
    # Response code will be 200 or 503 depending on whether Redis/Ollama are running
    assert response.status_code in (200, 503)
    data = response.json()
    assert "database" in data
    assert data["database"]["driver"] == "asyncpg"
    assert "redis" in data
    assert "agent_runtime" in data
    assert data["agent_runtime"]["runtime_type"] == "prime_agent"
    assert data["agent_runtime"]["status"] == "pending_verification"
