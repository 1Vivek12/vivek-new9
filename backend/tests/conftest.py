"""Pytest fixtures and test database setup for isolation and security verification."""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.models.audit import AuditLog
from app.db.models.membership import TenantMembership
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import get_db_session
from app.main import app

# Test database: use isolated SQLite async in-memory or file for rapid local execution
TEST_DB_URL = "sqlite+aiosqlite:///./test_foundation.db"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
async def prepare_test_db():
    """Create all tables before test session and drop afterwards."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    if os.path.exists("./test_foundation.db"):
        try:
            os.remove("./test_foundation.db")
        except Exception:
            pass


@pytest.fixture
async def db_session():
    """Provide an isolated transaction for each test."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def seeded_environment(db_session: AsyncSession):
    """Seed tenants and users strictly for isolation testing.

    - Tenant 1: News 9 (First production tenant)
    - Tenant 2: Isolation Test Workspace (Secondary test-only workspace)
    - User 1: News 9 Editor (Member of Tenant 1 only)
    - User 2: Other Tenant Editor (Member of Tenant 2 only)
    - User 3: Platform Super Admin (Global platform administrator)
    - User 4: Unaffiliated User (No memberships)
    """
    # 1. Tenants
    tenant_news9 = Tenant(
        id=str(uuid.uuid4()),
        slug="news9",
        name="News 9",
        status="ACTIVE",
        brand_config={"primary_color": "#D32F2F", "editorial_tone": "Authoritative"},
    )
    tenant_secondary = Tenant(
        id=str(uuid.uuid4()),
        slug="tenant-test-isolation",
        name="Secondary Test Tenant",
        status="ACTIVE",
        brand_config={"primary_color": "#0055FF", "editorial_tone": "Neutral"},
    )
    db_session.add_all([tenant_news9, tenant_secondary])

    # 2. Users
    user_news9 = User(
        id=str(uuid.uuid4()),
        email="news9_editor@example.com",
        full_name="News 9 Journalist",
        hashed_password=hash_password("Pass123!"),
        is_active=True,
        is_platform_admin=False,
    )
    user_secondary = User(
        id=str(uuid.uuid4()),
        email="secondary_editor@example.com",
        full_name="Secondary Tenant Staff",
        hashed_password=hash_password("Pass123!"),
        is_active=True,
        is_platform_admin=False,
    )
    user_admin = User(
        id=str(uuid.uuid4()),
        email="platform_admin@example.com",
        full_name="Platform Administrator",
        hashed_password=hash_password("AdminPass123!"),
        is_active=True,
        is_platform_admin=True,
    )
    user_unaffiliated = User(
        id=str(uuid.uuid4()),
        email="unaffiliated@example.com",
        full_name="Unaffiliated User",
        hashed_password=hash_password("Pass123!"),
        is_active=True,
        is_platform_admin=False,
    )
    db_session.add_all([user_news9, user_secondary, user_admin, user_unaffiliated])
    await db_session.flush()

    # 3. Memberships
    m_news9 = TenantMembership(
        id=str(uuid.uuid4()),
        tenant_id=tenant_news9.id,
        user_id=user_news9.id,
        role="EDITOR",
    )
    m_secondary = TenantMembership(
        id=str(uuid.uuid4()),
        tenant_id=tenant_secondary.id,
        user_id=user_secondary.id,
        role="EDITOR",
    )
    db_session.add_all([m_news9, m_secondary])

    # 4. Audit records to test cross-tenant data isolation
    audit_news9 = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_news9.id,
        user_id=user_news9.id,
        action="CONTENT_CREATED",
        resource_type="article",
        resource_id="art-news9-101",
        metadata_payload={"title": "Gorakhpur Infrastructure Update"},
    )
    audit_secondary = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_secondary.id,
        user_id=user_secondary.id,
        action="CONTENT_CREATED",
        resource_type="article",
        resource_id="art-secondary-202",
        metadata_payload={"title": "Secondary Client Private Notes"},
    )
    db_session.add_all([audit_news9, audit_secondary])
    await db_session.commit()

    return {
        "tenant_news9": tenant_news9,
        "tenant_secondary": tenant_secondary,
        "user_news9": user_news9,
        "user_secondary": user_secondary,
        "user_admin": user_admin,
        "user_unaffiliated": user_unaffiliated,
        "token_news9": create_access_token({"sub": user_news9.id}),
        "token_secondary": create_access_token({"sub": user_secondary.id}),
        "token_admin": create_access_token({"sub": user_admin.id}),
        "token_unaffiliated": create_access_token({"sub": user_unaffiliated.id}),
    }


@pytest.fixture
async def client(db_session: AsyncSession):
    """Async HTTP test client with database dependency override."""

    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
