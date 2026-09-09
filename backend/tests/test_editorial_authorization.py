"""Comprehensive IDOR / BOLA and cross-tenant authorization tests for Editorial domain."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assignment import Assignment
from app.db.models.category import Category
from app.db.models.source import StorySource
from app.db.models.story import Story
from app.db.models.version import StoryVersion


@pytest.fixture
async def cross_tenant_editorial_fixtures(db_session: AsyncSession, seeded_environment: dict):
    """Seed distinct editorial records in Tenant 1 (News 9) and Tenant 2 (Secondary)."""
    tenant_secondary = seeded_environment["tenant_secondary"]
    user_secondary = seeded_environment["user_secondary"]

    # Category for Tenant 2
    cat_secondary = Category(
        id=str(uuid.uuid4()),
        tenant_id=tenant_secondary.id,
        name="Private Enterprise",
        slug="private-enterprise",
    )
    # Assignment for Tenant 2
    assign_secondary = Assignment(
        id=str(uuid.uuid4()),
        tenant_id=tenant_secondary.id,
        title="Confidential Client Audit",
        created_by_user_id=user_secondary.id,
    )
    # Story for Tenant 2
    story_secondary = Story(
        id=str(uuid.uuid4()),
        tenant_id=tenant_secondary.id,
        title="Secondary Tenant Confidential Story",
        slug="secondary-confidential",
        created_by_user_id=user_secondary.id,
    )
    # Source for Tenant 2 Story
    source_secondary = StorySource(
        id=str(uuid.uuid4()),
        tenant_id=tenant_secondary.id,
        story_id=story_secondary.id,
        title="Internal Financial Ledger",
        source_type="OTHER",
        created_by_user_id=user_secondary.id,
    )
    # Version for Tenant 2 Story
    ver_secondary = StoryVersion(
        id=str(uuid.uuid4()),
        tenant_id=tenant_secondary.id,
        story_id=story_secondary.id,
        version_number=1,
        headline="Confidential Findings",
        body_payload={"secret": "value"},
        created_by_user_id=user_secondary.id,
    )

    db_session.add_all(
        [
            cat_secondary,
            assign_secondary,
            story_secondary,
            source_secondary,
            ver_secondary,
        ]
    )
    await db_session.commit()

    return {
        "cat_secondary": cat_secondary,
        "assign_secondary": assign_secondary,
        "story_secondary": story_secondary,
        "source_secondary": source_secondary,
        "ver_secondary": ver_secondary,
    }


@pytest.mark.asyncio
async def test_cross_tenant_story_access_is_blocked(
    client: AsyncClient, seeded_environment: dict, cross_tenant_editorial_fixtures: dict
):
    """IDOR Test: User in News 9 cannot GET Story of Secondary Tenant."""
    token_news9 = seeded_environment["token_news9"]
    story_secondary = cross_tenant_editorial_fixtures["story_secondary"]

    # Attempt to read Tenant 2 story with Tenant 1 credentials
    response = await client.get(
        f"/api/v1/stories/{story_secondary.id}",
        headers={"Authorization": f"Bearer {token_news9}"},
    )
    assert response.status_code == 404
    assert "not found in this workspace" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_story_modification_is_blocked(
    client: AsyncClient, seeded_environment: dict, cross_tenant_editorial_fixtures: dict
):
    """IDOR Test: User in News 9 cannot PATCH Story of Secondary Tenant."""
    token_news9 = seeded_environment["token_news9"]
    story_secondary = cross_tenant_editorial_fixtures["story_secondary"]

    response = await client.patch(
        f"/api/v1/stories/{story_secondary.id}",
        headers={"Authorization": f"Bearer {token_news9}"},
        json={"title": "Malicious Tampering Attempt"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_assignment_access_is_blocked(
    client: AsyncClient, seeded_environment: dict, cross_tenant_editorial_fixtures: dict
):
    """IDOR Test: User in News 9 cannot access or modify Assignment of Secondary Tenant."""
    token_news9 = seeded_environment["token_news9"]
    assign_secondary = cross_tenant_editorial_fixtures["assign_secondary"]

    # GET
    res_get = await client.get(
        f"/api/v1/assignments/{assign_secondary.id}",
        headers={"Authorization": f"Bearer {token_news9}"},
    )
    assert res_get.status_code == 404

    # PATCH
    res_patch = await client.patch(
        f"/api/v1/assignments/{assign_secondary.id}",
        headers={"Authorization": f"Bearer {token_news9}"},
        json={"status": "CANCELLED"},
    )
    assert res_patch.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_source_and_version_access_is_blocked(
    client: AsyncClient, seeded_environment: dict, cross_tenant_editorial_fixtures: dict
):
    """IDOR Test: User in News 9 cannot list or add sources/versions to Tenant 2 story."""
    token_news9 = seeded_environment["token_news9"]
    story_secondary = cross_tenant_editorial_fixtures["story_secondary"]

    # List sources
    res_sources = await client.get(
        f"/api/v1/stories/{story_secondary.id}/sources",
        headers={"Authorization": f"Bearer {token_news9}"},
    )
    assert res_sources.status_code == 404

    # Add source
    res_add_source = await client.post(
        f"/api/v1/stories/{story_secondary.id}/sources",
        headers={"Authorization": f"Bearer {token_news9}"},
        json={"title": "Injected Source"},
    )
    assert res_add_source.status_code == 404

    # List versions
    res_versions = await client.get(
        f"/api/v1/stories/{story_secondary.id}/versions",
        headers={"Authorization": f"Bearer {token_news9}"},
    )
    assert res_versions.status_code == 404

    # Add version
    res_add_version = await client.post(
        f"/api/v1/stories/{story_secondary.id}/versions",
        headers={"Authorization": f"Bearer {token_news9}"},
        json={"headline": "Injected Version", "body_payload": {}},
    )
    assert res_add_version.status_code == 404


@pytest.mark.asyncio
async def test_client_cannot_forge_tenant_in_body_or_header(
    client: AsyncClient, seeded_environment: dict
):
    """Test that specifying a forged tenant_id in payload or header does not bypass context."""
    token_news9 = seeded_environment["token_news9"]
    tenant_secondary = seeded_environment["tenant_secondary"]

    # Attempt to forge header
    res_forged_header = await client.post(
        "/api/v1/stories",
        headers={
            "Authorization": f"Bearer {token_news9}",
            "X-Tenant-ID": tenant_secondary.id,
        },
        json={"title": "Story with Forged Header"},
    )
    assert res_forged_header.status_code == 403

    # Story created without header belongs strictly to caller's tenant
    res_ok = await client.post(
        "/api/v1/stories",
        headers={"Authorization": f"Bearer {token_news9}"},
        json={"title": "Legitimate News 9 Story"},
    )
    assert res_ok.status_code == 201
    assert res_ok.json()["tenant_id"] == seeded_environment["tenant_news9"].id
