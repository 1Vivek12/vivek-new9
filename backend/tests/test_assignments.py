"""Tests for Assignment Desk functionality and lifecycle."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_assignment_creation_and_filtering(client: AsyncClient, seeded_environment: dict):
    """Test creating assignments with priorities and querying with filters."""
    token = seeded_environment["token_news9"]
    user_id = seeded_environment["user_news9"].id

    # Create Urgent Assignment
    res1 = await client.post(
        "/api/v1/assignments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Breaking Floods in Eastern UP",
            "description": "Urgent field dispatch required",
            "priority": "URGENT",
            "assigned_to_user_id": user_id,
        },
    )
    assert res1.status_code == 201
    assign_id = res1.json()["id"]
    assert res1.json()["priority"] == "URGENT"
    assert res1.json()["status"] == "PENDING"

    # Update Assignment to IN_PROGRESS
    res_patch = await client.patch(
        f"/api/v1/assignments/{assign_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "IN_PROGRESS"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["status"] == "IN_PROGRESS"

    # Filter assignments by status=IN_PROGRESS
    res_filter = await client.get(
        "/api/v1/assignments?status=IN_PROGRESS",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_filter.status_code == 200
    items = res_filter.json()
    assert any(a["id"] == assign_id for a in items)
