"""Server-side rights and copyright policy enforcement."""

from typing import Any, Dict


class RightsViolationError(PermissionError):
    """Raised when an operation violates media rights or copyright policy."""

    pass


VALID_RIGHTS_TYPES = {
    "OWNED",
    "LICENSED",
    "USER_PROVIDED",
    "RESTRICTED",
    "UNKNOWN",
}


def validate_rights_for_derivative(rights_metadata: Dict[str, Any]) -> bool:
    """Enforces server-side rights policy before generating derivatives.

    Rules:
    - OWNED / LICENSED: Permitted.
    - USER_PROVIDED: Requires explicit editorial flag `reuse_permitted: True`.
    - UNKNOWN: Blocked until human editorial review clears rights.
    - RESTRICTED: Strictly blocked from derivative creation.

    Raises:
        RightsViolationError: If rights policy forbids derivative generation.
    """
    if not rights_metadata:
        raise RightsViolationError(
            "Derivative generation is blocked: MediaAsset has UNKNOWN rights "
            "and requires human editorial review."
        )

    rights_type = rights_metadata.get("rights_type", "UNKNOWN").upper()

    if rights_type not in VALID_RIGHTS_TYPES:
        raise RightsViolationError(
            f"Derivative generation is blocked: Invalid rights type '{rights_type}'."
        )

    if rights_type == "RESTRICTED":
        raise RightsViolationError(
            "Derivative generation is blocked: MediaAsset is marked RESTRICTED."
        )

    if rights_type == "UNKNOWN":
        raise RightsViolationError(
            "Derivative generation is blocked: MediaAsset has UNKNOWN rights "
            "and requires human editorial review."
        )

    if rights_type == "USER_PROVIDED":
        reuse_permitted = rights_metadata.get("reuse_permitted", False)
        if not reuse_permitted:
            raise RightsViolationError(
                "Derivative generation is blocked: USER_PROVIDED media requires "
                "explicit reuse permission."
            )

    return True
