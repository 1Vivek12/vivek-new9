"""Comprehensive test suite for Phase 6 Publishing & Distribution Subsystem.

Covers:
1. Multi-Tenant Isolation & Account Ownership
2. AES-256-GCM Credential Vault, Nonce Freshness, and AAD Context Binding
3. Tamper Detection & Cross-Tenant Decryption Rejection
4. Controlled Resurrection of Soft-Deleted ConnectedAccount
5. Deterministic Publication Manifest & SHA-256 Hash Invariant
6. Append-Only PublishingApprovalEvent Ledger & Approval Invalidation on Mutation
7. Pre-Flight Dispatch-Time Manifest Re-verification & Tamper Defense
8. ExternalMediaDelivery HMAC-Signed Token, Expiration, and Path Traversal Defense
9. Platform-Specific Constraints & Editorial Ceilings (Shorts 180s, Reels 90s, WhatsApp 20 msg/s)
10. Strict Real vs Mock Provider Isolation
11. Meta Webhook Signature Verification & Event Deduplication
12. End-to-End API Workflow (Package -> Payload -> Approval -> Dispatch -> Published Item)
"""

import hashlib
import hmac
import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.publishing import (
    ConnectedAccount,
    DestinationType,
    PlatformPayload,
    PublishingDestination,
    WebhookEvent,
)
from app.db.models.story import Story
from app.db.models.version import StoryVersion
from app.services.publishing.delivery import DeliverySecurityError, ExternalMediaDeliveryService
from app.services.publishing.manifest import build_publication_manifest
from app.services.publishing.package_builder import (
    ManifestTamperedError,
    PublishingPackageService,
)
from app.services.publishing.providers.base import ProviderNotConfiguredError
from app.services.publishing.providers.mock import MockPublishingProvider
from app.services.publishing.providers.registry import provider_registry
from app.services.publishing.rate_limiter import TokenBucket
from app.services.publishing.validator import PrePublishValidator
from app.services.publishing.vault import (
    VaultDecryptionError,
    get_credential_vault,
)

# ==============================================================================
# 1. AES-256-GCM CREDENTIAL VAULT & AAD SECURITY TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_credential_vault_encryption_and_nonce_freshness():
    """Vault must use authenticated AES-256-GCM and generate unique nonces per encryption."""
    vault = get_credential_vault()
    tenant_id = "tenant-vault-1"
    account_id = "acc-vault-1"
    token = "secret_oauth_access_token_xyz123"

    c1, n1, v1 = vault.encrypt_credential(
        {"access_token": token}, tenant_id=tenant_id, account_id=account_id
    )
    c2, n2, v2 = vault.encrypt_credential(
        {"access_token": token}, tenant_id=tenant_id, account_id=account_id
    )

    assert c1 != c2, "Identical plaintexts must produce different ciphertexts"
    assert n1 != n2, "Nonces must be fresh and unique per encryption"

    # Verify decryption
    decrypted = vault.decrypt_credential(c1, tenant_id=tenant_id, account_id=account_id, nonce=n1)
    assert decrypted["access_token"] == token


@pytest.mark.asyncio
async def test_credential_vault_aad_context_binding_and_tamper_rejection():
    """Vault must bind to tenant and account AAD; cross-tenant decryption or tampering must fail."""
    vault = get_credential_vault()
    tenant_a = "tenant-a"
    tenant_b = "tenant-b"
    account_1 = "acc-1"

    c_a, n_a, _ = vault.encrypt_credential(
        {"access_token": "token_a"}, tenant_id=tenant_a, account_id=account_1
    )

    # Attempt to decrypt under tenant B's context must fail
    with pytest.raises(VaultDecryptionError):
        vault.decrypt_credential(c_a, tenant_id=tenant_b, account_id=account_1, nonce=n_a)

    # Attempt to decrypt with tampered ciphertext must fail
    tampered_c = c_a[:-4] + "AAAA"
    with pytest.raises(VaultDecryptionError):
        vault.decrypt_credential(tampered_c, tenant_id=tenant_a, account_id=account_1, nonce=n_a)


# ==============================================================================
# 2. CONTROLLED RESURRECTION & UNIQUE CONSTRAINT TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_connected_account_controlled_resurrection(
    client: AsyncClient, seeded_environment: dict
):
    """Soft-deleted accounts must be resurrected on reconnect without constraint collisions."""
    t_news9 = seeded_environment["tenant_news9"]
    token = seeded_environment["token_news9"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": t_news9.id}

    # 1. Get seeded destinations
    d_res = await client.get("/api/v1/publishing/destinations", headers=headers)
    assert d_res.status_code == 200
    dest_id = d_res.json()[0]["id"]

    # 2. Connect account
    conn_payload = {
        "destination_id": dest_id,
        "account_name": "Official YouTube Channel",
        "platform_account_id": "YT-CHANNEL-999",
        "access_token": "valid_token_abc",
        "account_type": "CHANNEL",
    }
    res1 = await client.post(
        "/api/v1/publishing/accounts/connect", json=conn_payload, headers=headers
    )
    assert res1.status_code == 200
    acc_id = res1.json()["account_id"]

    # 3. Disconnect account (soft-delete)
    del_res = await client.delete(f"/api/v1/publishing/accounts/{acc_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify not in active list
    list_res = await client.get("/api/v1/publishing/accounts", headers=headers)
    active_ids = [a["id"] for a in list_res.json()]
    assert acc_id not in active_ids

    # 4. Reconnect the same account (controlled resurrection)
    conn_payload["account_name"] = "Resurrected YouTube Channel"
    res2 = await client.post(
        "/api/v1/publishing/accounts/connect", json=conn_payload, headers=headers
    )
    assert res2.status_code == 200
    assert res2.json()["account_id"] == acc_id, "Must resurrect existing account record"

    # Verify now in active list
    list_res2 = await client.get("/api/v1/publishing/accounts", headers=headers)
    resurrected = next((a for a in list_res2.json() if a["id"] == acc_id), None)
    assert resurrected is not None
    assert resurrected["account_name"] == "Resurrected YouTube Channel"
    assert resurrected["is_deleted"] is False


# ==============================================================================
# 3. DETERMINISTIC MANIFEST & CRYPTOGRAPHIC HASH INVARIANTS
# ==============================================================================


@pytest.mark.asyncio
async def test_deterministic_manifest_hashing():
    """Publication manifest hash must be 100% deterministic and sensitive to any modification."""
    params = {
        "tenant_id": "tenant-hash-1",
        "story_id": "story-hash-1",
        "story_version_id": "ver-hash-1",
        "canonical_title": "Breaking News: Gorakhpur AI Center",
        "canonical_description": "First comprehensive report on the new AI initiative.",
        "tags": ["tech", "ai", "gorakhpur"],
        "media_assets": [
            {
                "asset_id": "asset-2",
                "storage_path": "tenants/t1/video2.mp4",
                "checksum_sha256": "hash2",
            },
            {
                "asset_id": "asset-1",
                "storage_path": "tenants/t1/video1.mp4",
                "checksum_sha256": "hash1",
            },
        ],
        "platform_payloads": [
            {
                "destination_type": "YOUTUBE",
                "account_id": "acc-yt",
                "adapted_title": "Gorakhpur AI Center",
            },
            {
                "destination_type": "FACEBOOK",
                "account_id": "acc-fb",
                "adapted_title": "AI Initiative Launch",
            },
        ],
    }

    _, hash1 = build_publication_manifest(**params)
    _, hash2 = build_publication_manifest(**params)
    assert hash1 == hash2, "Identical manifest inputs must produce identical SHA-256 hash"

    # Perturb title
    params_mod = dict(params, canonical_title="Breaking News: Gorakhpur AI Center (Updated)")
    _, hash_mod = build_publication_manifest(**params_mod)
    assert hash1 != hash_mod, "Changing title must invalidate the manifest hash"


# ==============================================================================
# 4. APPROVAL LEDGER & AUTOMATIC INVALIDATION ON MUTATION
# ==============================================================================


@pytest.mark.asyncio
async def test_approval_invalidation_on_content_mutation(
    db_session: AsyncSession, seeded_environment: dict
):
    """Mutating a platform payload after human approval must invalidate the approval."""
    t_news9 = seeded_environment["tenant_news9"]
    user_news9 = seeded_environment["user_news9"]

    # Seed story and version
    story = Story(
        id="story-appr-1",
        tenant_id=t_news9.id,
        title="Original Story",
        slug="original-story-appr",
        summary="Summary",
        status="APPROVED",
        created_by_user_id=user_news9.id,
    )
    version = StoryVersion(
        id="ver-appr-1",
        tenant_id=t_news9.id,
        story_id=story.id,
        version_number=1,
        headline="Original Story",
        body_text="Body text",
        body_payload={"text": "Body text"},
        created_by_user_id=user_news9.id,
    )
    dest = PublishingDestination(
        id="dest-yt-1",
        tenant_id=t_news9.id,
        destination_type="YOUTUBE",
        display_name="YouTube",
    )
    acc = ConnectedAccount(
        id="acc-yt-1",
        tenant_id=t_news9.id,
        destination_id=dest.id,
        account_type="CHANNEL",
        platform_account_id="yt-chan-1",
        account_name="Channel 1",
        connected_by_user_id=user_news9.id,
    )
    db_session.add_all([story, version, dest, acc])
    await db_session.commit()

    # Create package
    package = await PublishingPackageService.create_package(
        db_session,
        tenant_id=t_news9.id,
        creator_id=user_news9.id,
        story_id=story.id,
        story_version_id=version.id,
        canonical_title="Original Headline",
        canonical_description="Original Description",
    )
    await db_session.commit()

    # Add payload
    await PublishingPackageService.add_or_update_platform_payload(
        db_session,
        package_id=package.id,
        tenant_id=t_news9.id,
        destination_type="YOUTUBE",
        account_id=acc.id,
        adapted_title="YouTube Title v1",
        adapted_description="YouTube Desc v1",
    )
    await db_session.commit()

    # Human Approval
    approval_event = await PublishingPackageService.approve_package(
        db_session,
        package_id=package.id,
        tenant_id=t_news9.id,
        approver_id=user_news9.id,
        notes="Approved for broadcast",
    )
    await db_session.commit()

    assert package.status == "APPROVED"
    assert package.current_approval_id == approval_event.id

    # Post-approval mutation: edit adapted title
    await PublishingPackageService.add_or_update_platform_payload(
        db_session,
        package_id=package.id,
        tenant_id=t_news9.id,
        destination_type="YOUTUBE",
        account_id=acc.id,
        adapted_title="YouTube Title v2 (Unapproved Edits)",
        adapted_description="YouTube Desc v1",
    )
    await db_session.commit()

    # Verify approval invalidation
    assert (
        package.status == "DRAFT"
    ), "Post-approval payload modification must reset status to DRAFT"
    assert (
        package.current_approval_id is None
    ), "Approval pointer must be cleared upon content mutation"


# ==============================================================================
# 5. PRE-FLIGHT DISPATCH-TIME MANIFEST RE-VERIFICATION
# ==============================================================================


@pytest.mark.asyncio
async def test_preflight_dispatch_reverification_tamper_detection(
    db_session: AsyncSession, seeded_environment: dict
):
    """Dispatch must fail if live content differs from the approved manifest hash."""
    t_news9 = seeded_environment["tenant_news9"]
    user_news9 = seeded_environment["user_news9"]

    story = Story(
        id="story-tamper-1",
        tenant_id=t_news9.id,
        title="Tamper Test Story",
        slug="tamper-test-slug",
        summary="Summary",
        status="APPROVED",
        created_by_user_id=user_news9.id,
    )
    version = StoryVersion(
        id="ver-tamper-1",
        tenant_id=t_news9.id,
        story_id=story.id,
        version_number=1,
        headline="Tamper Test Story",
        body_text="Body",
        body_payload={"text": "Body"},
        created_by_user_id=user_news9.id,
    )
    dest = PublishingDestination(
        id="dest-fb-1",
        tenant_id=t_news9.id,
        destination_type="FACEBOOK",
        display_name="Facebook",
    )
    acc = ConnectedAccount(
        id="acc-fb-1",
        tenant_id=t_news9.id,
        destination_id=dest.id,
        account_type="PAGE",
        platform_account_id="fb-page-1",
        account_name="News 9 FB",
        connected_by_user_id=user_news9.id,
    )
    db_session.add_all([story, version, dest, acc])
    await db_session.commit()

    package = await PublishingPackageService.create_package(
        db_session,
        tenant_id=t_news9.id,
        creator_id=user_news9.id,
        story_id=story.id,
        story_version_id=version.id,
        canonical_title="Valid Title",
        canonical_description="Valid Description",
    )
    await db_session.commit()

    await PublishingPackageService.add_or_update_platform_payload(
        db_session,
        package_id=package.id,
        tenant_id=t_news9.id,
        destination_type="FACEBOOK",
        account_id=acc.id,
        adapted_title="Valid Title",
        adapted_description="Valid Description",
    )
    await db_session.commit()

    await PublishingPackageService.approve_package(
        db_session,
        package_id=package.id,
        tenant_id=t_news9.id,
        approver_id=user_news9.id,
    )
    await db_session.commit()

    # Preflight check passes initially
    assert await PublishingPackageService.reverify_manifest_at_dispatch(db_session, package) is True

    # Tamper with canonical title directly in DB without going through service
    package.canonical_title = "Tampered Title Not In Manifest"
    await db_session.commit()

    # Preflight check MUST detect mismatch and raise ManifestTamperedError
    with pytest.raises(ManifestTamperedError):
        await PublishingPackageService.reverify_manifest_at_dispatch(db_session, package)


# ==============================================================================
# 6. EXTERNAL MEDIA DELIVERY SERVICE & PATH CONTAINMENT
# ==============================================================================


@pytest.mark.asyncio
async def test_external_media_delivery_security_and_path_containment(tmp_path: Path):
    """Delivery service must enforce HMAC signature, 15-min TTL, and reject path traversal."""
    settings = get_settings()
    # Mock storage root in tmp_path
    old_root = settings.STORAGE_ROOT
    settings.STORAGE_ROOT = str(tmp_path)

    try:
        tenant_id = "tenant-delivery-1"
        asset_id = "asset-del-1"

        # Create valid asset file
        tenant_dir = tmp_path / "tenants" / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        valid_file = tenant_dir / "video.mp4"
        valid_file.write_bytes(b"dummy mp4 video content")

        svc = ExternalMediaDeliveryService()

        # 1. Valid Token Generation & Verification
        token = svc.generate_delivery_token(
            tenant_id=tenant_id,
            asset_id=asset_id,
            storage_path=f"tenants/{tenant_id}/video.mp4",
            ttl_seconds=900,
        )
        resolved_path, res_tid, res_aid = svc.verify_and_resolve_file(token)
        assert resolved_path == valid_file.resolve()
        assert res_tid == tenant_id
        assert res_aid == asset_id

        # 2. Path Traversal Rejection
        traversal_token = svc.generate_delivery_token(
            tenant_id=tenant_id,
            asset_id=asset_id,
            storage_path="../../etc/shadow",
            ttl_seconds=900,
        )
        with pytest.raises(DeliverySecurityError, match="Path traversal attempt detected"):
            svc.verify_and_resolve_file(traversal_token)

        # 3. Expired Token Rejection
        expired_token = svc.generate_delivery_token(
            tenant_id=tenant_id,
            asset_id=asset_id,
            storage_path=f"tenants/{tenant_id}/video.mp4",
            ttl_seconds=-10,  # Expired in past
        )
        with pytest.raises(DeliverySecurityError, match="expired"):
            svc.verify_and_resolve_file(expired_token)

        # 4. Forged Token Rejection
        forged_token = token[:-4] + "zzzz"
        with pytest.raises(DeliverySecurityError):
            svc.verify_and_resolve_file(forged_token)

    finally:
        settings.STORAGE_ROOT = old_root


# ==============================================================================
# 7. PLATFORM CONSTRAINTS & RATE LIMITING
# ==============================================================================


@pytest.mark.asyncio
async def test_platform_constraints_and_editorial_ceilings():
    """Validator must enforce platform limits (Shorts 180s, Reels 90s, YouTube title 100)."""
    validator = PrePublishValidator()

    # YouTube title > 100 chars
    long_title = "A" * 105
    res = validator.validate_package(
        canonical_title=long_title,
        canonical_description="desc",
        media_assets=[{"asset_id": "m1", "rights_metadata": {"rights_type": "OWNED"}}],
        platform_payloads=[{"destination_type": "YOUTUBE", "adapted_title": long_title}],
    )
    assert not res.is_valid
    assert any("YouTube title exceeds maximum" in i.message for i in res.issues)

    # Shorts duration > 180 seconds editorial ceiling
    res_short = validator.validate_package(
        canonical_title="Short Title",
        canonical_description="desc",
        media_assets=[
            {
                "asset_id": "m1",
                "rights_metadata": {"rights_type": "OWNED"},
                "duration_seconds": 210.0,
            }
        ],
        platform_payloads=[
            {
                "destination_type": "YOUTUBE",
                "adapted_title": "Short Title",
                "custom_metadata": {"is_short": True},
            }
        ],
    )
    assert not res_short.is_valid
    assert any("editorial ceiling of 180s" in i.message for i in res_short.issues)

    # Instagram Reels duration > 90 seconds editorial ceiling
    res_reel = validator.validate_package(
        canonical_title="Reel Title",
        canonical_description="desc",
        media_assets=[
            {
                "asset_id": "m1",
                "rights_metadata": {"rights_type": "OWNED"},
                "duration_seconds": 105.0,
            }
        ],
        platform_payloads=[
            {
                "destination_type": "INSTAGRAM",
                "adapted_caption": "Caption",
                "custom_metadata": {"is_reel": True},
            }
        ],
    )
    assert not res_reel.is_valid
    assert any("editorial ceiling of 90s" in i.message for i in res_reel.issues)


@pytest.mark.asyncio
async def test_whatsapp_token_bucket_rate_limiter():
    """TokenBucket must strictly enforce WhatsApp 20 messages/second throttle."""
    bucket = TokenBucket(capacity=20.0, refill_rate_per_second=20.0)

    # Acquire 20 tokens immediately -> success
    for _ in range(20):
        ok, _ = await bucket.acquire(1.0)
        assert ok is True

    # 21st token must be rejected
    ok, wait_time = await bucket.acquire(1.0)
    assert ok is False
    assert wait_time > 0


# ==============================================================================
# 8. REAL VS MOCK PROVIDER BOUNDARY
# ==============================================================================


@pytest.mark.asyncio
async def test_real_vs_mock_provider_boundary(db_session: AsyncSession):
    """Real providers must raise ProviderNotConfiguredError when live keys absent;
    Mocks return is_mock=True.
    """
    yt_provider = provider_registry.get_provider(DestinationType.YOUTUBE)
    assert yt_provider.is_mock is False

    # Real provider publish without keys raises ProviderNotConfiguredError
    dummy_acc = ConnectedAccount(
        id="acc-mock-1",
        tenant_id="tenant-1",
        destination_id="dest-1",
        account_type="CHANNEL",
        platform_account_id="yt-1",
        account_name="YT",
        connected_by_user_id="user-1",
    )
    dummy_payload = PlatformPayload(
        id="p-1",
        tenant_id="tenant-1",
        package_id="pkg-1",
        destination_type="YOUTUBE",
        account_id=dummy_acc.id,
        adapted_title="Test",
        adapted_description="Desc",
    )

    with pytest.raises(ProviderNotConfiguredError):
        await yt_provider.publish(
            db=db_session,
            payload=dummy_payload,
            account=dummy_acc,
            vault=get_credential_vault(),
            media_assets=[],
        )

    # Mock provider returns clean mock response with is_mock=True
    mock_p = MockPublishingProvider(destination_type=DestinationType.YOUTUBE)
    res = await mock_p.publish(
        db=db_session,
        payload=dummy_payload,
        account=dummy_acc,
        vault=get_credential_vault(),
        media_assets=[],
    )
    assert res.success is True
    assert res.is_mock is True
    assert res.external_id.startswith("mock_youtube_")


# ==============================================================================
# 9. META WEBHOOK SIGNATURE & DEDUPLICATION
# ==============================================================================


@pytest.mark.asyncio
async def test_meta_webhook_verification_and_deduplication(
    client: AsyncClient, db_session: AsyncSession, seeded_environment: dict
):
    """Meta webhook verification handshake and event deduplication on UNIQUE(dest, external_id)."""
    settings = get_settings()
    secret = "test_meta_webhook_secret_123"
    old_secret = settings.META_APP_SECRET
    settings.META_APP_SECRET = secret
    t_news9 = seeded_environment["tenant_news9"]

    try:
        # 1. GET Handshake
        hs_res = await client.get(
            "/api/v1/webhooks/meta?hub.mode=subscribe&hub.verify_token=news9_meta_verify_token&hub.challenge=challenge_12345"
        )
        assert hs_res.status_code == 200
        assert hs_res.text == "challenge_12345"

        # 2. POST Webhook with valid HMAC-SHA256
        payload = {
            "object": "instagram",
            "entry": [{"id": "ig_entry_1", "time": 1720000000, "status": "FINISHED"}],
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        post_res = await client.post(
            f"/api/v1/webhooks/meta/{t_news9.id}",
            content=raw_body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert post_res.status_code == 200
        assert post_res.json()["status"] == "SUCCESS"

        # 3. Duplicate Delivery (Idempotent ignore)
        dup_res = await client.post(
            f"/api/v1/webhooks/meta/{t_news9.id}",
            content=raw_body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert dup_res.status_code == 200

        # Verify only one row was inserted into webhook_events
        events = await db_session.execute(select(WebhookEvent))
        all_ev = events.scalars().all()
        assert len([e for e in all_ev if e.external_event_id == "ig_entry_1_1720000000"]) == 1

    finally:
        settings.META_APP_SECRET = old_secret


# ==============================================================================
# 10. END-TO-END PUBLISHING DISPATCH PIPELINE
# ==============================================================================


@pytest.mark.asyncio
async def test_end_to_end_publishing_pipeline_api(
    client: AsyncClient, seeded_environment: dict, db_session: AsyncSession
):
    """End-to-End: Connect account -> Create Package -> Validate -> Approve ->
    Dispatch -> PublishedItem.
    """
    # Temporarily activate mock providers for pipeline test
    provider_registry.set_use_mock(True)

    t_news9 = seeded_environment["tenant_news9"]
    user_news9 = seeded_environment["user_news9"]
    token = seeded_environment["token_news9"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": t_news9.id}

    try:
        # 1. Seed Story
        story = Story(
            id="story-e2e-1",
            tenant_id=t_news9.id,
            title="E2E Story",
            slug="e2e-story-slug",
            summary="E2E Summary",
            status="APPROVED",
            created_by_user_id=user_news9.id,
        )
        ver = StoryVersion(
            id="ver-e2e-1",
            tenant_id=t_news9.id,
            story_id=story.id,
            version_number=1,
            headline="E2E Story",
            body_text="E2E Body",
            body_payload={"text": "E2E Body"},
            created_by_user_id=user_news9.id,
        )
        db_session.add_all([story, ver])
        await db_session.commit()

        # 2. Get Destinations and connect account
        d_res = await client.get("/api/v1/publishing/destinations", headers=headers)
        yt_dest = next(d for d in d_res.json() if d["destination_type"] == "YOUTUBE")

        conn_res = await client.post(
            "/api/v1/publishing/accounts/connect",
            json={
                "destination_id": yt_dest["id"],
                "account_name": "E2E YouTube Channel",
                "platform_account_id": "UC_E2E_12345",
                "access_token": "mock_token_pass",
                "account_type": "CHANNEL",
            },
            headers=headers,
        )
        acc_id = conn_res.json()["account_id"]

        # 3. Create Package
        pkg_res = await client.post(
            "/api/v1/publishing/packages",
            json={
                "story_id": story.id,
                "story_version_id": ver.id,
                "destination_types": ["YOUTUBE"],
                "account_ids": [acc_id],
                "canonical_title": "E2E Broadcast Package",
                "canonical_description": "Comprehensive E2E release across digital channels.",
                "tags": ["news", "broadcast"],
            },
            headers=headers,
        )
        assert pkg_res.status_code == 200
        pkg = pkg_res.json()
        assert pkg["status"] == "DRAFT"

        # 4. Run Pre-Publish Validation
        val_res = await client.post(
            f"/api/v1/publishing/packages/{pkg['id']}/validate", headers=headers
        )
        assert val_res.status_code == 200
        assert val_res.json()["manifest_hash"] is not None

        # 5. Human Editorial Approval
        appr_res = await client.post(
            f"/api/v1/publishing/packages/{pkg['id']}/approve",
            json={"action": "APPROVE", "rejection_reason": "Signed off by Senior Editor"},
            headers=headers,
        )
        assert appr_res.status_code == 200
        assert appr_res.json()["event_type"] == "APPROVED"

        # 6. Publish Dispatch
        pub_res = await client.post(
            f"/api/v1/publishing/packages/{pkg['id']}/publish", headers=headers
        )
        assert pub_res.status_code == 200
        job = pub_res.json()
        assert job["job_status"] == "SUCCESS"

        # 7. Check Published Items
        item_res = await client.get("/api/v1/publishing/published-items", headers=headers)
        assert item_res.status_code == 200
        items = item_res.json()
        assert len(items) > 0
        assert items[0]["package_id"] == pkg["id"]
        assert items[0]["destination_type"] == "YOUTUBE"
        assert items[0]["external_item_id"].startswith("mock_youtube_")

    finally:
        provider_registry.set_use_mock(False)
