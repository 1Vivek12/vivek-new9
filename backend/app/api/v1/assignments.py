"""Assignment Desk API endpoints."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.models.assignment import Assignment
from app.db.models.audit import AuditLog
from app.db.session import get_db_session
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
)

router = APIRouter(prefix="/assignments", tags=["Assignment Desk"])


@router.get("", response_model=List[AssignmentResponse])
async def list_assignments(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    priority_filter: Optional[str] = Query(default=None, alias="priority"),
    limit: int = Query(default=50, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[AssignmentResponse]:
    """List assignments strictly scoped to caller's authorized tenant."""
    check_permission(context, "VIEW_EDITORIAL")
    stmt = (
        select(Assignment)
        .where(Assignment.tenant_id == context.tenant_id)
        .order_by(desc(Assignment.created_at))
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(Assignment.status == status_filter.upper())
    if priority_filter:
        stmt = stmt.where(Assignment.priority == priority_filter.upper())

    result = await db.execute(stmt)
    return [AssignmentResponse.model_validate(a) for a in result.scalars().all()]


@router.post("", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: AssignmentCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AssignmentResponse:
    """Create an assignment within caller's authorized tenant."""
    check_permission(context, "CREATE_ASSIGNMENT")

    assignment = Assignment(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority.upper(),
        status="PENDING",
        assigned_to_user_id=payload.assigned_to_user_id,
        created_by_user_id=context.user_id,
        due_date=payload.due_date,
    )
    db.add(assignment)

    # Audit logging
    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="ASSIGNMENT_CREATED",
        resource_type="assignment",
        resource_id=assignment.id,
        metadata_payload={
            "title": assignment.title,
            "assigned_to": assignment.assigned_to_user_id,
            "priority": assignment.priority,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(assignment)
    return AssignmentResponse.model_validate(assignment)


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AssignmentResponse:
    """Fetch assignment detail, strictly enforcing tenant boundary (IDOR protection)."""
    check_permission(context, "VIEW_EDITORIAL")
    stmt = select(Assignment).where(
        Assignment.id == assignment_id,
        Assignment.tenant_id == context.tenant_id,
    )
    result = await db.execute(stmt)
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found in this workspace",
        )
    return AssignmentResponse.model_validate(assignment)


@router.patch("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AssignmentResponse:
    """Update assignment attributes, strictly enforcing tenant boundary."""
    check_permission(context, "EDIT_ASSIGNMENT")
    stmt = select(Assignment).where(
        Assignment.id == assignment_id,
        Assignment.tenant_id == context.tenant_id,
    )
    result = await db.execute(stmt)
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment '{assignment_id}' not found in this workspace",
        )

    if payload.title is not None:
        assignment.title = payload.title
    if payload.description is not None:
        assignment.description = payload.description
    if payload.priority is not None:
        assignment.priority = payload.priority.upper()
    if payload.status is not None:
        assignment.status = payload.status.upper()
    if payload.assigned_to_user_id is not None:
        assignment.assigned_to_user_id = payload.assigned_to_user_id
    if payload.due_date is not None:
        assignment.due_date = payload.due_date

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="ASSIGNMENT_UPDATED",
        resource_type="assignment",
        resource_id=assignment.id,
        metadata_payload={
            "status": assignment.status,
            "assigned_to": assignment.assigned_to_user_id,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(assignment)
    return AssignmentResponse.model_validate(assignment)
