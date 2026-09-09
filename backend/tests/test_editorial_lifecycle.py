"""Tests for deterministic editorial lifecycle, state transitions, and approval gates."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_valid_editorial_lifecycle_progression(
    client: AsyncClient, seeded_environment: dict
):
    """Test full valid progression:
    IDEA -> DRAFT -> VALIDATION -> APPROVAL_REQUIRED -> APPROVED -> PUBLISHED.
    """
    token = seeded_environment["token_news9"]

    # 1. Create story (starts in IDEA)
    create_res = await client.post(
        "/api/v1/stories",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Gorakhpur AI Hub Launch", "summary": "Initial idea for civic tech story"},
    )
    assert create_res.status_code == 201
    story_id = create_res.json()["id"]
    assert create_res.json()["status"] == "IDEA"

    # 2. IDEA -> DRAFT
    res1 = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "DRAFT"},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "DRAFT"

    # 3. DRAFT -> VALIDATION
    res2 = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "VALIDATION"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "VALIDATION"

    # 4. VALIDATION -> APPROVAL_REQUIRED
    res3 = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "APPROVAL_REQUIRED"},
    )
    assert res3.status_code == 200
    assert res3.json()["status"] == "APPROVAL_REQUIRED"

    # 5. APPROVAL_REQUIRED -> APPROVED (requires human editor approval)
    res4 = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "APPROVED"},
    )
    assert res4.status_code == 200
    assert res4.json()["status"] == "APPROVED"
    assert res4.json()["approved_by_user_id"] == seeded_environment["user_news9"].id
    assert res4.json()["approved_at"] is not None

    # 6. APPROVED -> PUBLISHED (passes Phase 1 publishing guard)
    res5 = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "PUBLISHED"},
    )
    assert res5.status_code == 200
    assert res5.json()["status"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_invalid_state_transition_is_blocked(
    client: AsyncClient, seeded_environment: dict
):
    """Test that illegal skips (e.g. IDEA straight to PUBLISHED) fail deterministically."""
    token = seeded_environment["token_news9"]

    create_res = await client.post(
        "/api/v1/stories",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Unvetted Breaking Alert"},
    )
    story_id = create_res.json()["id"]

    # Direct skip to APPROVED from IDEA must be rejected
    res_skip_approved = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "APPROVED"},
    )
    assert res_skip_approved.status_code == 400
    assert "Invalid editorial transition" in res_skip_approved.json()["detail"]

    # Direct skip to PUBLISHED from IDEA must be rejected
    res_skip_published = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "PUBLISHED"},
    )
    assert res_skip_published.status_code == 400


@pytest.mark.asyncio
async def test_editorial_rejection_requires_reason(
    client: AsyncClient, seeded_environment: dict
):
    """Test that transitioning to REJECTED requires an explicit editorial reason."""
    token = seeded_environment["token_news9"]

    create_res = await client.post(
        "/api/v1/stories",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Dubious Wire Rumor"},
    )
    story_id = create_res.json()["id"]

    # Progress to DRAFT then VALIDATION
    await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "DRAFT"},
    )
    await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "VALIDATION"},
    )

    # Transition to REJECTED without reason -> 400
    fail_res = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "REJECTED"},
    )
    assert fail_res.status_code == 400
    assert "Rejection reason is mandatory" in fail_res.json()["detail"]

    # Transition to REJECTED with reason -> 200
    ok_res = await client.post(
        f"/api/v1/stories/{story_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_status": "REJECTED",
            "rejection_reason": "Single unverified social media claim",
        },
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["status"] == "REJECTED"
    assert ok_res.json()["rejection_reason"] == "Single unverified social media claim"
