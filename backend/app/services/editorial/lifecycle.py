"""Deterministic Editorial Lifecycle and state machine transitions."""

from enum import Enum
from typing import Dict, Optional, Set

from fastapi import HTTPException, status

from app.core.permissions import check_permission
from app.core.tenant import TenantContext


class EditorialState(str, Enum):
    IDEA = "IDEA"
    ASSIGNED = "ASSIGNED"
    RESEARCHING = "RESEARCHING"
    DRAFT = "DRAFT"
    VALIDATION = "VALIDATION"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


# Explicit state transition map
VALID_TRANSITIONS: Dict[EditorialState, Set[EditorialState]] = {
    EditorialState.IDEA: {
        EditorialState.ASSIGNED,
        EditorialState.RESEARCHING,
        EditorialState.DRAFT,
        EditorialState.ARCHIVED,
    },
    EditorialState.ASSIGNED: {
        EditorialState.RESEARCHING,
        EditorialState.DRAFT,
        EditorialState.ARCHIVED,
    },
    EditorialState.RESEARCHING: {
        EditorialState.DRAFT,
        EditorialState.ARCHIVED,
    },
    EditorialState.DRAFT: {
        EditorialState.VALIDATION,
        EditorialState.ARCHIVED,
    },
    EditorialState.VALIDATION: {
        EditorialState.APPROVAL_REQUIRED,
        EditorialState.DRAFT,
        EditorialState.REJECTED,
    },
    EditorialState.APPROVAL_REQUIRED: {
        EditorialState.APPROVED,
        EditorialState.REJECTED,
        EditorialState.DRAFT,
    },
    EditorialState.APPROVED: {
        EditorialState.PUBLISHED,
        EditorialState.DRAFT,
        EditorialState.ARCHIVED,
    },
    EditorialState.REJECTED: {
        EditorialState.DRAFT,
        EditorialState.ARCHIVED,
    },
    EditorialState.PUBLISHED: {
        EditorialState.ARCHIVED,
    },
    EditorialState.ARCHIVED: {
        EditorialState.DRAFT,
    },
}


class InvalidStateTransitionError(HTTPException):
    """Raised when an illegal editorial lifecycle state transition is requested."""

    def __init__(self, current_state: str, requested_state: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid editorial transition: Cannot transition from '{current_state}' "
                f"to '{requested_state}'"
            ),
        )


def validate_transition(
    current_state_str: str,
    requested_state_str: str,
    context: TenantContext,
    rejection_reason: Optional[str] = None,
) -> EditorialState:
    """Validates state transition rule adherence, permission, and approval constraints."""
    try:
        current_state = EditorialState(current_state_str)
        requested_state = EditorialState(requested_state_str)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown editorial state: {e}",
        ) from e

    # Check state graph validity
    allowed_next_states = VALID_TRANSITIONS.get(current_state, set())
    if requested_state not in allowed_next_states:
        raise InvalidStateTransitionError(current_state.value, requested_state.value)

    # Check role permissions for specific transitions
    if requested_state == EditorialState.APPROVAL_REQUIRED:
        check_permission(context, "REQUEST_APPROVAL")

    elif requested_state == EditorialState.APPROVED:
        check_permission(context, "APPROVE_CONTENT")

    elif requested_state == EditorialState.REJECTED:
        check_permission(context, "REJECT_CONTENT")
        if not rejection_reason or not rejection_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is mandatory when transitioning to REJECTED",
            )
    elif requested_state == EditorialState.PUBLISHED:
        check_permission(context, "TRIGGER_PUBLISH")

    return requested_state
