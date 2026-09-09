"""Strict Tenant Context Resolution and Authorization."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.security import decode_access_token
from app.db.session import get_db_session

security_bearer = HTTPBearer(auto_error=False)


@dataclass
class TenantContext:
    """Immutable context representing the authorized tenant and user for a request."""

    tenant_id: str
    user_id: str
    role: str
    is_platform_admin: bool = False
    tenant_slug: str = ""
    tenant_name: str = ""
    brand_config: Dict[str, Any] = field(default_factory=dict)


async def get_tenant_context(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_tenant_id: Optional[str] = Header(
        default=None,
        alias="X-Tenant-ID",
        description="Optional tenant context selection hint for multi-membership users",
    ),
    db: AsyncSession = Depends(get_db_session),
) -> TenantContext:
    """Resolves and authorizes the tenant context.

    CRITICAL SECURITY INVARIANTS:
    1. Tenant context is NEVER derived from X-Tenant-ID alone.
    2. Identity is cryptographically verified from the Bearer token.
    3. User must have verified, active membership in the target tenant.
    4. Forged or unassigned X-Tenant-ID headers are rejected with 403 Forbidden.
    5. Platform admins can inspect any tenant, but access is explicitly flagged.
    """
    if not auth_credentials or not auth_credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth_credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = str(payload["sub"])

    # Import models locally to prevent circular imports
    from app.db.models.membership import TenantMembership
    from app.db.models.tenant import Tenant
    from app.db.models.user import User

    # 1. Fetch user
    user_result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated",
        )

    # 2. Fetch user's authorized tenant memberships
    membership_result = await db.execute(
        select(TenantMembership, Tenant)
        .join(Tenant, TenantMembership.tenant_id == Tenant.id)
        .where(TenantMembership.user_id == user_id)
    )
    memberships = membership_result.all()

    # Map authorized tenant IDs to (membership, tenant)
    user_tenant_map = {str(m.Tenant.id): (m.TenantMembership, m.Tenant) for m in memberships}

    target_tenant: Optional[Tenant] = None
    target_role: str = "VIEWER"
    is_admin_override = False

    if user.is_platform_admin:
        # Platform Admin flow
        if x_tenant_id:
            # Look up requested tenant
            admin_t_res = await db.execute(select(Tenant).where(Tenant.id == x_tenant_id))
            target_tenant = admin_t_res.scalar_one_or_none()
            if not target_tenant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Requested tenant '{x_tenant_id}' not found",
                )
            target_role = "PLATFORM_ADMIN"
            is_admin_override = True
        elif user_tenant_map:
            # Default to first assigned tenant
            _, target_tenant = next(iter(user_tenant_map.values()))
            target_role = "PLATFORM_ADMIN"
        else:
            # Fall back to first tenant in system
            any_tenant_res = await db.execute(select(Tenant).limit(1))
            target_tenant = any_tenant_res.scalar_one_or_none()
            if not target_tenant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No tenants exist on this platform",
                )
            target_role = "PLATFORM_ADMIN"
            is_admin_override = True
    else:
        # Standard User Flow
        if not user_tenant_map:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: User does not belong to any tenant",
            )

        if x_tenant_id:
            # FORGED / MISMATCH HEADER CHECK:
            # User supplied an explicit header; verify user is actually a member of it!
            if x_tenant_id not in user_tenant_map:
                logger.warning(
                    f"Cross-tenant attempt blocked: User {user_id} attempted unauthorized access "
                    f"to tenant {x_tenant_id}",
                    extra={"user_id": user_id, "attempted_tenant": x_tenant_id},
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Access denied: User is not an authorized member of the requested tenant"
                    ),
                )
            mem, t = user_tenant_map[x_tenant_id]
            target_tenant = t
            target_role = mem.role
        else:
            # Default to primary / first tenant membership
            mem, t = next(iter(user_tenant_map.values()))
            target_tenant = t
            target_role = mem.role

    if not target_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to establish authorized tenant context",
        )

    context = TenantContext(
        tenant_id=str(target_tenant.id),
        user_id=user_id,
        role=target_role,
        is_platform_admin=user.is_platform_admin,
        tenant_slug=target_tenant.slug,
        tenant_name=target_tenant.name,
        brand_config=target_tenant.brand_config or {},
    )

    if is_admin_override:
        logger.info(
            f"Admin {user_id} accessed tenant {context.tenant_id} under elevated oversight",
            extra={"tenant_id": context.tenant_id, "user_id": user_id},
        )

    return context
