"""Database seeding for initial tenant (News 9) and test fixtures."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.security import hash_password
from app.db.models.membership import TenantMembership
from app.db.models.tenant import Tenant
from app.db.models.user import User

# Stable seed IDs for deterministic references
NEWS9_TENANT_ID = "00000000-0000-0000-0000-000000000001"
NEWS9_ADMIN_USER_ID = "00000000-0000-0000-0000-000000000002"
NEWS9_EDITOR_USER_ID = "00000000-0000-0000-0000-000000000003"


async def seed_news9_tenant(session: AsyncSession) -> Tenant:
    """Seeds News 9 as the first tenant of the platform.

    Demonstrates brand-independence: News 9 is a data record with branding preferences,
    NOT hardcoded platform logic.
    """
    result = await session.execute(select(Tenant).where(Tenant.slug == "news9"))
    existing_tenant = result.scalar_one_or_none()

    if existing_tenant:
        logger.info("News 9 tenant already exists in database.")
        return existing_tenant

    news9 = Tenant(
        id=NEWS9_TENANT_ID,
        slug="news9",
        name="News 9",
        status="ACTIVE",
        brand_config={
            "primary_color": "#D32F2F",
            "secondary_color": "#212121",
            "accent_color": "#FFC107",
            "logo_url": "/assets/branding/news9_logo.svg",
            "typography": {"heading": "Outfit", "body": "Inter"},
            "locale": "en-IN",
            "timezone": "Asia/Kolkata",
            "editorial_tone": "Fast, authoritative, verified regional and national reporting",
            "supported_beats": ["Politics", "Gorakhpur Region", "Technology", "Economy"],
        },
    )
    session.add(news9)

    # Seed News 9 Admin User
    admin_res = await session.execute(select(User).where(User.email == "admin@news9.local"))
    admin_user = admin_res.scalar_one_or_none()
    if not admin_user:
        admin_user = User(
            id=NEWS9_ADMIN_USER_ID,
            email="admin@news9.local",
            full_name="News 9 Chief Editor",
            hashed_password=hash_password("News9Admin_SecurePassword2026!"),
            is_active=True,
            is_platform_admin=False,
        )
        session.add(admin_user)

    # Seed News 9 Editor User
    editor_res = await session.execute(select(User).where(User.email == "editor@news9.local"))
    editor_user = editor_res.scalar_one_or_none()
    if not editor_user:
        editor_user = User(
            id=NEWS9_EDITOR_USER_ID,
            email="editor@news9.local",
            full_name="News 9 Senior Reporter",
            hashed_password=hash_password("News9Reporter_SecurePassword2026!"),
            is_active=True,
            is_platform_admin=False,
        )
        session.add(editor_user)

    await session.flush()

    # Create Memberships
    m1_res = await session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == news9.id,
            TenantMembership.user_id == admin_user.id,
        )
    )
    if not m1_res.scalar_one_or_none():
        session.add(
            TenantMembership(
                id=str(uuid.uuid4()),
                tenant_id=news9.id,
                user_id=admin_user.id,
                role="TENANT_OWNER",
            )
        )

    m2_res = await session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == news9.id,
            TenantMembership.user_id == editor_user.id,
        )
    )
    if not m2_res.scalar_one_or_none():
        session.add(
            TenantMembership(
                id=str(uuid.uuid4()),
                tenant_id=news9.id,
                user_id=editor_user.id,
                role="EDITOR",
            )
        )

    await session.commit()
    logger.info("Successfully seeded News 9 workspace and initial users.")
    return news9
