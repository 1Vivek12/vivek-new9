"""Tests for StorySource metadata and legal rights tracking."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_story_source_metadata_attachment(client: AsyncClient, seeded_environment: dict):
    """Test attaching sources with confidence ratings and rights metadata."""
    token = seeded_environment["token_news9"]

    # 1. Create story
    story_res = await client.post(
        "/api/v1/stories",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Uttar Pradesh Expressway Update"},
    )
    story_id = story_res.json()["id"]

    # 2. Attach Official Government Source
    source_res = await client.post(
        f"/api/v1/stories/{story_id}/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "UP Industrial Development Authority Press Release",
            "url": "https://upida.gov.in/press/expressway_expansion_2026",
            "publisher_name": "UPIDA",
            "source_type": "GOVERNMENT",
            "reliability_score": 95.5,
            "rights_metadata": {"license": "Public Document", "reuse_allowed": True},
            "notes": "Verified against official gazette copy",
        },
    )
    assert source_res.status_code == 201
    src_data = source_res.json()
    assert src_data["source_type"] == "GOVERNMENT"
    assert src_data["reliability_score"] == 95.5
    assert src_data["rights_metadata"]["license"] == "Public Document"

    # 3. Retrieve sources list
    list_res = await client.get(
        f"/api/v1/stories/{story_id}/sources",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.status_code == 200
    sources = list_res.json()
    assert len(sources) == 1
    assert sources[0]["publisher_name"] == "UPIDA"
