"""Role-based editorial permissions scoped to tenant context."""

from typing import Set

from fastapi import HTTPException, status

from app.core.tenant import TenantContext

# Role permissions mapping
ROLE_PERMISSIONS = {
    "PLATFORM_ADMIN": {
        "VIEW_EDITORIAL",
        "CREATE_ASSIGNMENT",
        "EDIT_ASSIGNMENT",
        "CREATE_STORY",
        "EDIT_STORY",
        "ADD_SOURCE",
        "CREATE_VERSION",
        "REQUEST_APPROVAL",
        "APPROVE_CONTENT",
        "REJECT_CONTENT",
        "MANAGE_CATEGORIES",
    },
    "TENANT_OWNER": {
        "VIEW_EDITORIAL",
        "CREATE_ASSIGNMENT",
        "EDIT_ASSIGNMENT",
        "CREATE_STORY",
        "EDIT_STORY",
        "ADD_SOURCE",
        "CREATE_VERSION",
        "REQUEST_APPROVAL",
        "APPROVE_CONTENT",
        "REJECT_CONTENT",
        "MANAGE_CATEGORIES",
    },
    "TENANT_ADMIN": {
        "VIEW_EDITORIAL",
        "CREATE_ASSIGNMENT",
        "EDIT_ASSIGNMENT",
        "CREATE_STORY",
        "EDIT_STORY",
        "ADD_SOURCE",
        "CREATE_VERSION",
        "REQUEST_APPROVAL",
        "APPROVE_CONTENT",
        "REJECT_CONTENT",
        "MANAGE_CATEGORIES",
    },
    "EDITOR": {
        "VIEW_EDITORIAL",
        "CREATE_ASSIGNMENT",
        "EDIT_ASSIGNMENT",
        "CREATE_STORY",
        "EDIT_STORY",
        "ADD_SOURCE",
        "CREATE_VERSION",
        "REQUEST_APPROVAL",
        "APPROVE_CONTENT",
        "REJECT_CONTENT",
        "MANAGE_CATEGORIES",
    },
    "CONTENT_MANAGER": {
        "VIEW_EDITORIAL",
        "CREATE_ASSIGNMENT",
        "EDIT_ASSIGNMENT",
        "CREATE_STORY",
        "EDIT_STORY",
        "ADD_SOURCE",
        "CREATE_VERSION",
        "REQUEST_APPROVAL",
        "APPROVE_CONTENT",
        "REJECT_CONTENT",
    },
    "REPORTER": {
        "VIEW_EDITORIAL",
        "CREATE_STORY",
        "EDIT_STORY",
        "ADD_SOURCE",
        "CREATE_VERSION",
        "REQUEST_APPROVAL",
    },
    "CREATOR": {
        "VIEW_EDITORIAL",
        "CREATE_STORY",
        "EDIT_STORY",
        "ADD_SOURCE",
        "CREATE_VERSION",
        "REQUEST_APPROVAL",
    },
    "ANALYST": {
        "VIEW_EDITORIAL",
    },
    "VIEWER": {
        "VIEW_EDITORIAL",
    },
}


def get_permissions_for_role(role: str) -> Set[str]:
    """Get the set of granted permission strings for a given role."""
    return ROLE_PERMISSIONS.get(role.upper(), set())


def check_permission(context: TenantContext, required_permission: str) -> None:
    """Enforce that the caller's authorized role within the tenant possesses the permission."""
    if context.is_platform_admin:
        return

    permissions = get_permissions_for_role(context.role)
    if required_permission not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Permission denied: Role '{context.role}' lacks required permission "
                f"'{required_permission}' in tenant {context.tenant_id}"
            ),
        )
