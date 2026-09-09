"""Categories management endpoints."""

import re
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.models.audit import AuditLog
from app.db.models.category import Category
from app.db.session import get_db_session
from app.schemas.category import CategoryCreate, CategoryResponse

router = APIRouter(prefix="/categories", tags=["Categories"])


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text)


@router.get("", response_model=List[CategoryResponse])
async def list_categories(
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[CategoryResponse]:
    """List all categories strictly scoped to the authorized tenant."""
    stmt = select(Category).where(Category.tenant_id == context.tenant_id).order_by(Category.name)
    result = await db.execute(stmt)
    return [CategoryResponse.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> CategoryResponse:
    """Create a new category scoped to the authorized tenant."""
    check_permission(context, "MANAGE_CATEGORIES")

    slug = payload.slug or slugify(payload.name)

    # Uniqueness check scoped strictly to current tenant
    existing = await db.execute(
        select(Category).where(
            Category.tenant_id == context.tenant_id, Category.slug == slug
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with slug '{slug}' already exists in this tenant workspace",
        )

    category = Category(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
    )
    db.add(category)

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="CATEGORY_CREATED",
        resource_type="category",
        resource_id=category.id,
        metadata_payload={"name": category.name, "slug": category.slug},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(category)
    return CategoryResponse.model_validate(category)
