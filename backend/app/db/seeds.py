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

    # Seed Initial Categories for News 9
    from app.db.models.assignment import Assignment
    from app.db.models.category import Category
    from app.db.models.source import StorySource
    from app.db.models.story import Story
    from app.db.models.version import StoryVersion

    cat_slugs = [
        ("Gorakhpur Region", "gorakhpur-region", "Regional news and civic updates from Gorakhpur"),
        ("Politics", "politics", "State and national political coverage"),
        ("Technology", "technology", "AI, gadgets, and digital media innovations"),
        ("Economy", "economy", "Markets, employment, and fiscal developments"),
    ]
    created_cats = {}
    for name, slug, desc in cat_slugs:
        cat_res = await session.execute(
            select(Category).where(Category.tenant_id == news9.id, Category.slug == slug)
        )
        cat = cat_res.scalar_one_or_none()
        if not cat:
            cat = Category(
                id=str(uuid.uuid4()),
                tenant_id=news9.id,
                name=name,
                slug=slug,
                description=desc,
            )
            session.add(cat)
        created_cats[slug] = cat

    await session.flush()

    # Seed sample assignment
    assign_res = await session.execute(
        select(Assignment).where(
            Assignment.tenant_id == news9.id,
            Assignment.title == "Gorakhpur Railway Modernization Coverage",
        )
    )
    sample_assignment = assign_res.scalar_one_or_none()
    if not sample_assignment:
        sample_assignment = Assignment(
            id=str(uuid.uuid4()),
            tenant_id=news9.id,
            title="Gorakhpur Railway Modernization Coverage",
            description="Investigate platform enhancements and high-speed corridor progress.",
            priority="HIGH",
            status="IN_PROGRESS",
            assigned_to_user_id=editor_user.id,
            created_by_user_id=admin_user.id,
        )
        session.add(sample_assignment)
        await session.flush()

    # Seed sample story with version and official source
    story_res = await session.execute(
        select(Story).where(
            Story.tenant_id == news9.id,
            Story.slug == "gorakhpur-railway-station-overhaul-2026",
        )
    )
    sample_story = story_res.scalar_one_or_none()
    if not sample_story:
        sample_story = Story(
            id=str(uuid.uuid4()),
            tenant_id=news9.id,
            title="Gorakhpur Railway Station Overhaul Set for Mid-2026 Launch",
            slug="gorakhpur-railway-station-overhaul-2026",
            summary="New passenger terminals and world-class concourse nearing completion.",
            category_id=created_cats["gorakhpur-region"].id,
            assignment_id=sample_assignment.id,
            priority="HIGH",
            status="DRAFT",
            editorial_owner_id=editor_user.id,
            created_by_user_id=editor_user.id,
        )
        session.add(sample_story)
        await session.flush()

        # Seed Source (official release)
        sample_source = StorySource(
            id=str(uuid.uuid4()),
            tenant_id=news9.id,
            story_id=sample_story.id,
            title="North Eastern Railway Press Bureau Briefing",
            url="https://ner.indianrailways.gov.in/press_releases/overhaul_2026",
            publisher_name="Ministry of Railways, India",
            source_type="OFFICIAL",
            reliability_score=98.0,
            rights_metadata={"license": "Public Domain / Government Gazette"},
            notes="Verified against official gazette notification.",
            created_by_user_id=editor_user.id,
        )
        session.add(sample_source)

        # Seed Version 1
        sample_version = StoryVersion(
            id=str(uuid.uuid4()),
            tenant_id=news9.id,
            story_id=sample_story.id,
            version_number=1,
            headline="Gorakhpur Railway Station Modernization Reaches 85% Completion",
            body_payload={"lead": "Work on the state-of-the-art terminal is accelerating..."},
            body_text="Work on the state-of-the-art terminal in Gorakhpur is accelerating.",
            change_summary="Initial verified draft with official ministry citations.",
            created_by_user_id=editor_user.id,
        )
        session.add(sample_version)

    await session.commit()
    logger.info("Successfully seeded News 9 workspace and initial users.")
    return news9
