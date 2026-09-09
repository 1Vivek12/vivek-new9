"""Integration and security tests for Trend Radar, Source Registry, and Opportunities."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.trend.rss_connector import NormalizedSourceItem


@pytest.mark.asyncio
async def test_source_registry_crud_and_tenant_isolation(
    client: AsyncClient, seeded_environment: dict
):
    """Test full source lifecycle and cross-tenant access prevention."""
    token_1 = seeded_environment["token_news9"]
    token_2 = seeded_environment["token_secondary"]

    # 1. Create Source in Tenant 1
    create_res = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {token_1}"},
        json={
            "name": "Uttar Pradesh Information Department",
            "source_type": "GOVERNMENT",
            "feed_url": "https://information.up.gov.in/feed.xml",
            "publisher_name": "UP Info Dept",
            "reliability_score": 92.0,
            "trust_level": "HIGH",
            "jurisdiction": "IN-UP",
            "language": "en",
            "rights_metadata": {
                "rights_type": "public_information",
                "reuse_permitted": False,
            },
        },
    )
    assert create_res.status_code == 201
    source_1 = create_res.json()
    source_id = source_1["id"]
    assert source_1["source_type"] == "GOVERNMENT"
    assert source_1["reliability_score"] == 92.0

    # 2. Get Source in Tenant 1
    get_res = await client.get(
        f"/api/v1/sources/{source_id}",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert get_res.status_code == 200

    # 3. Cross-tenant isolation: Tenant 2 CANNOT access Tenant 1's source (IDOR check)
    t2_get_res = await client.get(
        f"/api/v1/sources/{source_id}",
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert t2_get_res.status_code == 404

    t2_update_res = await client.put(
        f"/api/v1/sources/{source_id}",
        headers={"Authorization": f"Bearer {token_2}"},
        json={"name": "Hacked Source Name"},
    )
    assert t2_update_res.status_code == 404

    # 4. Update in Tenant 1
    update_res = await client.put(
        f"/api/v1/sources/{source_id}",
        headers={"Authorization": f"Bearer {token_1}"},
        json={"name": "UP Information and Public Relations Department", "is_active": True},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "UP Information and Public Relations Department"


@pytest.mark.asyncio
async def test_ssrf_blocking_on_source_creation(
    client: AsyncClient, seeded_environment: dict
):
    """Test that SSRF URLs are rejected on source creation."""
    token = seeded_environment["token_news9"]

    # Localhost
    res1 = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Localhost Source", "feed_url": "http://127.0.0.1:8080/rss"},
    )
    assert res1.status_code == 400
    detail_lower = res1.json()["detail"].lower()
    assert "prohibited" in detail_lower or "blocked" in detail_lower

    # Private IP
    res2 = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Private IP Source", "feed_url": "http://10.0.0.5/feed"},
    )
    assert res2.status_code == 400

    # File scheme
    res3 = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "File Source", "feed_url": "file:///etc/passwd"},
    )
    assert res3.status_code == 400


@pytest.mark.asyncio
async def test_source_refresh_ingestion_mocked(
    client: AsyncClient, seeded_environment: dict
):
    """Test source refresh, item normalization, and deduplication with mocked feed."""
    token = seeded_environment["token_news9"]

    # 1. Create source
    src_res = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "State Wire Service",
            "source_type": "WIRE",
            "feed_url": "https://wire.state.gov.in/feed.xml",
            "publisher_name": "State Wire",
            "reliability_score": 88.0,
        },
    )
    source_id = src_res.json()["id"]

    # 2. Mock connector fetch_and_normalize
    mock_items = [
        NormalizedSourceItem(
            title="Expressway Extension Survey Completed",
            canonical_url="https://wire.state.gov.in/story/survey-completed",
            summary="Land survey for 140km expressway extension finished ahead of schedule.",
            publisher="State Wire",
            published_at=None,
            external_id="story-101",
            language="en",
            reliability_score=88.0,
            rights_metadata={"rights_type": "public_information", "reuse_permitted": False},
            raw_metadata={"source_type": "WIRE"},
            fingerprint="test-fp-101",
        ),
        NormalizedSourceItem(
            title="Monsoon Rainfall Exceeds Average",
            canonical_url="https://wire.state.gov.in/story/monsoon-average",
            summary="Reservoirs at 85% capacity following continuous showers.",
            publisher="State Wire",
            published_at=None,
            external_id="story-102",
            language="en",
            reliability_score=88.0,
            rights_metadata={"rights_type": "public_information", "reuse_permitted": False},
            raw_metadata={"source_type": "WIRE"},
            fingerprint="test-fp-102",
        ),
    ]

    with patch(
        "app.api.v1.sources.RSSAtomConnector.fetch_and_normalize",
        new_callable=AsyncMock,
        return_value=mock_items,
    ):
        refresh_res = await client.post(
            f"/api/v1/sources/{source_id}/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert refresh_res.status_code == 200
        data = refresh_res.json()
        assert data["items_fetched"] == 2
        assert data["new_items_stored"] == 2

        # Rerun refresh: verify deduplication prevents storing duplicate fingerprints
        refresh_res2 = await client.post(
            f"/api/v1/sources/{source_id}/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert refresh_res2.status_code == 200
        assert refresh_res2.json()["new_items_stored"] == 0


@pytest.mark.asyncio
async def test_topic_search_and_opportunity_conversion_to_story(
    client: AsyncClient, seeded_environment: dict
):
    """
    Test end-to-end Trend Radar flow:
    Topic Search -> Similar Story Group -> Opportunity Generation -> Convert to Phase 2 Story.
    """
    token_1 = seeded_environment["token_news9"]
    token_2 = seeded_environment["token_secondary"]

    # 1. Ingest item in Tenant 1
    src_res = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {token_1}"},
        json={
            "name": "Regional Press",
            "source_type": "PUBLICATION",
            "feed_url": "https://regional.example.com/rss",
            "publisher_name": "Regional Press",
            "reliability_score": 80.0,
        },
    )
    source_id = src_res.json()["id"]

    mock_items = [
        NormalizedSourceItem(
            title="Gorakhpur Industrial Development Accelerates With New Plants",
            canonical_url="https://regional.example.com/art/gorakhpur-industry",
            summary="New manufacturing units sanctioned in the Gorakhpur industrial zone.",
            publisher="Regional Press",
            published_at=None,
            external_id="reg-201",
            language="en",
            reliability_score=80.0,
            rights_metadata={"rights_type": "public_information", "reuse_permitted": False},
            raw_metadata={"source_type": "PUBLICATION"},
            fingerprint="fp-gorakhpur-ind-1",
        )
    ]

    with patch(
        "app.api.v1.sources.RSSAtomConnector.fetch_and_normalize",
        new_callable=AsyncMock,
        return_value=mock_items,
    ):
        await client.post(
            f"/api/v1/sources/{source_id}/refresh",
            headers={"Authorization": f"Bearer {token_1}"},
        )

    # 2. Topic Search for 'Gorakhpur'
    search_res = await client.post(
        "/api/v1/trend/search",
        headers={"Authorization": f"Bearer {token_1}"},
        json={"query": "Gorakhpur Industrial", "time_window_hours": 48},
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_matching_items"] >= 1
    assert len(search_data["opportunities"]) >= 1

    opportunity = search_data["opportunities"][0]
    opp_id = opportunity["id"]
    assert "Gorakhpur" in opportunity["headline"]
    assert opportunity["trend_score"] > 0
    assert "signal_type" in opportunity["score_explanation"]

    # 3. Tenant 2 search should NOT see Tenant 1's items (tenant isolation)
    t2_search_res = await client.post(
        "/api/v1/trend/search",
        headers={"Authorization": f"Bearer {token_2}"},
        json={"query": "Gorakhpur Industrial", "time_window_hours": 48},
    )
    assert t2_search_res.status_code == 200
    assert t2_search_res.json()["total_matching_items"] == 0

    # 4. Accept Opportunity in Tenant 1
    accept_res = await client.post(
        f"/api/v1/opportunities/{opp_id}/accept",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] == "ACCEPTED"

    # Cross-tenant check: Tenant 2 cannot accept Tenant 1's opportunity
    t2_opp_res = await client.post(
        f"/api/v1/opportunities/{opp_id}/accept",
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert t2_opp_res.status_code == 404

    # 5. Convert Opportunity to Phase 2 Story
    convert_res = await client.post(
        f"/api/v1/opportunities/{opp_id}/convert-to-story",
        headers={"Authorization": f"Bearer {token_1}"},
        json={"priority": "HIGH"},
    )
    assert convert_res.status_code == 201
    story = convert_res.json()
    assert story["title"] == opportunity["headline"]
    assert story["status"] == "IDEA"  # Mandatory: initial state
    assert story["priority"] == "HIGH"
    story_id = story["id"]

    # 6. Verify attached sources on the created Story
    sources_res = await client.get(
        f"/api/v1/stories/{story_id}/sources",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert sources_res.status_code == 200
    attached_sources = sources_res.json()
    assert len(attached_sources) >= 1
    assert attached_sources[0]["url"] == "https://regional.example.com/art/gorakhpur-industry"

    # 7. Attempting to convert the opportunity again must be rejected
    reconvert_res = await client.post(
        f"/api/v1/opportunities/{opp_id}/convert-to-story",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert reconvert_res.status_code == 400


@pytest.mark.asyncio
async def test_failure_mode_disabled_source_refresh(
    client: AsyncClient, seeded_environment: dict
):
    """Test that refreshing a disabled source returns a 400 error."""
    token = seeded_environment["token_news9"]

    src_res = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Inactive Source",
            "source_type": "RSS",
            "feed_url": "https://inactive.example.com/rss",
            "is_active": False,
        },
    )
    source_id = src_res.json()["id"]

    res = await client.post(
        f"/api/v1/sources/{source_id}/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "disabled" in res.json()["detail"].lower()
