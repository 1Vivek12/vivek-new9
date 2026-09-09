"""Audit log querying endpoint (Strictly tenant-scoped)."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext, get_tenant_context
from app.db.models.audit import AuditLog
from app.db.session import get_db_session

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("", response_model=List[Dict[str, Any]])
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[Dict[str, Any]]:
    """Fetch audit log records strictly scoped to the caller's authorized tenant."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == context.tenant_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "tenant_id": log.tenant_id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "metadata": log.metadata_payload,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
