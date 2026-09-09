"""Foundational worker tasks enforcing tenant context parameter."""

from typing import Any, Dict

from app.core.logging import logger
from app.worker.celery_app import celery_app


@celery_app.task(name="tasks.audit_archive")
def archive_tenant_audit_logs(tenant_id: str, days_threshold: int = 90) -> Dict[str, Any]:
    """Background task for rotating/archiving old audit records.

    INVARIANT: Requires explicit tenant_id context.
    """
    if not tenant_id:
        raise ValueError("Tenant ID is required for task execution")

    logger.info(f"Archiving audit logs for tenant {tenant_id} older than {days_threshold} days")
    return {
        "status": "COMPLETED",
        "tenant_id": tenant_id,
        "archived_records": 0,
    }
