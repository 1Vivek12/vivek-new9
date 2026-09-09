"""Publishing approval gate and deterministic state machine tests."""

import pytest

from app.services.publishing.base import (
    ContentState,
    MockPublishingBoundary,
    PublishingPayload,
    UnapprovedContentPublicationError,
)


@pytest.mark.asyncio
async def test_publishing_draft_content_raises_error():
    """Verifies that publishing content in DRAFT state is strictly blocked."""
    boundary = MockPublishingBoundary()
    payload = PublishingPayload(
        content_id="cont-001",
        tenant_id="tenant-news9",
        title="Gorakhpur Express Update",
        body="Draft story text",
        state=ContentState.DRAFT,
        approved_by_user_id=None,
    )

    with pytest.raises(UnapprovedContentPublicationError) as exc_info:
        await boundary.publish(payload)
    assert "Verified human approval is strictly required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_publishing_without_approver_raises_error():
    """Verifies that state=APPROVED with approved_by_user_id=None is blocked."""
    boundary = MockPublishingBoundary()
    payload = PublishingPayload(
        content_id="cont-002",
        tenant_id="tenant-news9",
        title="AI News Roundup",
        body="Story text",
        state=ContentState.APPROVED,
        approved_by_user_id=None,  # Missing valid human approver ID
    )

    with pytest.raises(UnapprovedContentPublicationError):
        await boundary.publish(payload)


@pytest.mark.asyncio
async def test_publishing_approved_content_passes_gate():
    """Verifies that verified human approval allows content to pass the approval gate."""
    boundary = MockPublishingBoundary()
    payload = PublishingPayload(
        content_id="cont-003",
        tenant_id="tenant-news9",
        title="Verified Headline",
        body="Approved article text",
        state=ContentState.APPROVED,
        approved_by_user_id="usr-editor-99",
    )

    result = await boundary.publish(payload)
    assert result["status"] == "simulated_success"
    assert result["approved_by"] == "usr-editor-99"
