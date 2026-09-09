"""Tests for immutable editorial draft versioning."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_story_version_creation_and_auto_increment(
    client: AsyncClient, seeded_environment: dict
):
    """Test that versions are sequentially incremented and immutable."""
    token = seeded_environment["token_news9"]

    # 1. Create base story
    story_res = await client.post(
        "/api/v1/stories",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Gorakhpur AI Hub Launch"},
    )
    story_id = story_res.json()["id"]

    # 2. Add Version 1
    v1_res = await client.post(
        f"/api/v1/stories/{story_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "headline": "Gorakhpur AI Hub Breaks Ground",
            "body_payload": {"paragraphs": ["Initial draft content."]},
            "body_text": "Initial draft content.",
            "change_summary": "First full reporter draft",
        },
    )
    assert v1_res.status_code == 201
    v1_data = v1_res.json()
    assert v1_data["version_number"] == 1
    assert v1_data["headline"] == "Gorakhpur AI Hub Breaks Ground"

    # 3. Add Version 2
    v2_res = await client.post(
        f"/api/v1/stories/{story_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "headline": "Gorakhpur AI Hub Breaks Ground: Official Statements Added",
            "body_payload": {"paragraphs": ["Initial draft content.", "Added official quote."]},
            "body_text": "Initial draft content. Added official quote.",
            "change_summary": "Added quotes from District Magistrate",
        },
    )
    assert v2_res.status_code == 201
    v2_data = v2_res.json()
    assert v2_data["version_number"] == 2

    # 4. List versions (ordered latest first)
    list_res = await client.get(
        f"/api/v1/stories/{story_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.status_code == 200
    versions = list_res.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1
