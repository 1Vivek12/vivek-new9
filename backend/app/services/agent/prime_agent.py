"""Prime Agent Runtime Adapter (Pending Verification / Non-Executing in Phase 1)."""

import time
import uuid
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.agent.base import (
    AgentRuntime,
    AgentSession,
    AgentTaskSpec,
    AgentTaskStatus,
)


class PrimeAgentRuntime(AgentRuntime):
    """Prime Agent orchestration adapter.

    CRITICAL SECURITY POSTURE:
    - Status: PENDING_VERIFICATION (NON-EXECUTING / SAFE in Phase 1)
    - Host execution is disabled.
    - No access to host shell, Docker socket, root filesystem, or platform secrets.
    """

    def __init__(self) -> None:
        self.enabled = settings.AGENT_EXECUTION_ENABLED

    async def start_session(
        self, tenant_id: str, user_id: str, config: Optional[Dict[str, Any]] = None
    ) -> AgentSession:
        if not self.enabled:
            logger.info(
                f"Agent session creation for tenant {tenant_id} - runtime is in safe pending mode"
            )
            return AgentSession(
                session_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                created_at=time.time(),
                metadata={"status": "pending_verification", "engine": "prime_agent"},
            )
        raise NotImplementedError("Live Prime Agent sessions are disabled in Phase 1.")

    async def run_task(self, session: AgentSession, spec: AgentTaskSpec) -> AgentTaskStatus:
        """Strict non-execution guard."""
        logger.warning(
            f"Blocked task execution attempt '{spec.task_name}' on tenant {spec.tenant_id}. "
            "Prime Agent runtime execution is pending verification."
        )
        raise NotImplementedError(
            "Prime Agent runtime execution is pending verification and disabled in Phase 1."
        )

    async def resume_task(self, task_id: str, input_data: Dict[str, Any]) -> AgentTaskStatus:
        raise NotImplementedError("Task resumption is disabled in Phase 1.")

    async def stop_task(self, task_id: str) -> bool:
        logger.info(f"Agent task {task_id} stop requested - no active tasks in Phase 1.")
        return True

    async def inspect_task(self, task_id: str) -> AgentTaskStatus:
        return AgentTaskStatus(
            task_id=task_id,
            status="PENDING_VERIFICATION",
            error="Agent runtime execution pending verification.",
        )

    async def health_check(self) -> Dict[str, Any]:
        """Honest health status reporting non-executing verification state."""
        return {
            "status": "pending_verification",
            "executable": False,
            "runtime_type": "prime_agent",
            "security_sandbox": "architectural_isolation_only",
            "message": "Prime Agent runtime registered; execution blocked until verified.",
        }
