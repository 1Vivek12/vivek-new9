"""Publishing abstraction and deterministic human approval state machine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from app.core.logging import logger


class ContentState(str, Enum):
    DRAFT = "DRAFT"
    AI_PROCESSING = "AI_PROCESSING"
    VALIDATION = "VALIDATION"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"


class UnapprovedContentPublicationError(Exception):
    """Raised when an attempt is made to publish content without human approval."""

    pass


@dataclass
class PublishingPayload:
    content_id: str
    tenant_id: str
    title: str
    body: str
    state: ContentState
    approved_by_user_id: Optional[str] = None
    approval_timestamp: Optional[float] = None
    target_channels: Optional[list] = None


class PublishingProvider(ABC):
    """Abstract interface for multi-channel publishing adapters (YouTube, FB, etc.).

    Guarantees: Content can NEVER be dispatched to an external network without
    verified prior human approval in the state machine.
    """

    @abstractmethod
    async def publish(self, payload: PublishingPayload) -> Dict[str, Any]:
        """Dispatch content to external platform."""
        pass


class MockPublishingBoundary(PublishingProvider):
    """Safe Phase 1 boundary verifying deterministic human approval enforcement."""

    async def publish(self, payload: PublishingPayload) -> Dict[str, Any]:
        # MANDATORY GATE: Content state must be APPROVED with a non-null approver
        if payload.state != ContentState.APPROVED or not payload.approved_by_user_id:
            logger.error(
                f"Blocked unapproved publication attempt for content {payload.content_id} "
                f"(state: {payload.state}, approver: {payload.approved_by_user_id})"
            )
            raise UnapprovedContentPublicationError(
                f"Content {payload.content_id} cannot be published: "
                f"State is '{payload.state.value}'. Verified human approval is strictly required."
            )

        logger.info(
            f"Content {payload.content_id} approved by {payload.approved_by_user_id} "
            f"for tenant {payload.tenant_id} (Phase 1 boundary: External dispatch disabled)"
        )
        return {
            "status": "simulated_success",
            "content_id": payload.content_id,
            "tenant_id": payload.tenant_id,
            "approved_by": payload.approved_by_user_id,
            "message": "Approval gate verified. External channel dispatch is deferred to Phase 2.",
        }
