"""Tenant profile and workspace management endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.core.tenant import TenantContext, get_tenant_context

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("/current")
async def get_current_tenant_profile(
    context: TenantContext = Depends(get_tenant_context),
) -> Dict[str, Any]:
    """Returns the authenticated workspace profile and branding preferences."""
    return {
        "tenant_id": context.tenant_id,
        "slug": context.tenant_slug,
        "name": context.tenant_name,
        "user_id": context.user_id,
        "role": context.role,
        "is_platform_admin": context.is_platform_admin,
        "branding": context.brand_config,
    }
