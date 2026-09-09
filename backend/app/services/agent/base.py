"""AgentRuntime interface definition."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentSession:
    session_id: str
    tenant_id: str
    user_id: str
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTaskSpec:
    task_id: str
    tenant_id: str
    task_name: str
    instructions: str
    allowed_tools: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTaskStatus:
    task_id: str
    status: str  # PENDING, RUNNING, COMPLETED, FAILED, STOPPED, PENDING_VERIFICATION
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentRuntime(ABC):
    """Abstract interface isolating agent orchestrators from the platform."""

    @abstractmethod
    async def start_session(
        self, tenant_id: str, user_id: str, config: Optional[Dict[str, Any]] = None
    ) -> AgentSession:
        """Initialize an isolated agent session scoped to a tenant."""
        pass

    @abstractmethod
    async def run_task(self, session: AgentSession, spec: AgentTaskSpec) -> AgentTaskStatus:
        """Run a task within an authorized tenant session."""
        pass

    @abstractmethod
    async def resume_task(self, task_id: str, input_data: Dict[str, Any]) -> AgentTaskStatus:
        """Resume an awaiting task."""
        pass

    @abstractmethod
    async def stop_task(self, task_id: str) -> bool:
        """Terminate a running task."""
        pass

    @abstractmethod
    async def inspect_task(self, task_id: str) -> AgentTaskStatus:
        """Inspect the current state of a task."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check runtime service health and verification status."""
        pass
