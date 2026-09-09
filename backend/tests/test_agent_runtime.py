"""Agent Runtime security and safety boundary tests."""

import pytest

from app.services.agent.base import AgentSession, AgentTaskSpec
from app.services.agent.prime_agent import PrimeAgentRuntime


@pytest.mark.asyncio
async def test_prime_agent_runtime_blocks_execution_in_phase1():
    """Verifies that PrimeAgentRuntime rejects task execution with clear error."""
    runtime = PrimeAgentRuntime()

    session = AgentSession(
        session_id="session-123",
        tenant_id="tenant-news9",
        user_id="user-1",
        created_at=0.0,
    )
    spec = AgentTaskSpec(
        task_id="task-001",
        tenant_id="tenant-news9",
        task_name="generate_story_outline",
        instructions="Analyze topic",
    )

    with pytest.raises(NotImplementedError) as exc_info:
        await runtime.run_task(session, spec)
    assert "Prime Agent runtime execution is pending verification" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prime_agent_runtime_health_reports_pending():
    """Verifies that health check honestly reports pending verification and non-executable."""
    runtime = PrimeAgentRuntime()
    health = await runtime.health_check()
    assert health["status"] == "pending_verification"
    assert health["executable"] is False
    assert health["runtime_type"] == "prime_agent"
