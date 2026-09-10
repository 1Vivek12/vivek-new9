"""Tests for Media RBAC and Permission Enforcement."""

import io
import uuid

import pytest

from app.core.security import create_access_token, hash_password
from app.db.models.membership import TenantMembership
from app.db.models.user import User


@pytest.mark.asyncio
async def test_media_rbac_permissions(client, seeded_environment, db_session):
    """Verify role-based access controls for media operations."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id

    # 1. Create a Reporter user
    reporter = User(
        id=str(uuid.uuid4()),
        email="reporter@news9.test",
        full_name="News 9 Field Reporter",
        hashed_password=hash_password("Pass123!"),
        is_active=True,
    )
    # 2. Create a Viewer user
    viewer = User(
        id=str(uuid.uuid4()),
        email="viewer@news9.test",
        full_name="News 9 Intern Viewer",
        hashed_password=hash_password("Pass123!"),
        is_active=True,
    )
    db_session.add_all([reporter, viewer])
    await db_session.flush()

    m_reporter = TenantMembership(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=reporter.id,
        role="REPORTER",
    )
    m_viewer = TenantMembership(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=viewer.id,
        role="VIEWER",
    )
    db_session.add_all([m_reporter, m_viewer])
    await db_session.commit()

    token_reporter = create_access_token({"sub": reporter.id})
    token_viewer = create_access_token({"sub": viewer.id})

    headers_reporter = {"Authorization": f"Bearer {token_reporter}", "X-Tenant-ID": tenant_id}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}", "X-Tenant-ID": tenant_id}
    headers_editor = {"Authorization": f"Bearer {env['token_news9']}", "X-Tenant-ID": tenant_id}

    fake_mp4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 100

    # A. Viewer tries to upload -> 403 Forbidden
    res_v_upload = await client.post(
        "/api/v1/media/upload",
        headers=headers_viewer,
        files={"file": ("clip.mp4", io.BytesIO(fake_mp4), "video/mp4")},
        data={"rights_type": "OWNED"},
    )
    assert res_v_upload.status_code == 403

    # B. Reporter uploads -> Allowed (201)
    res_r_upload = await client.post(
        "/api/v1/media/upload",
        headers=headers_reporter,
        files={"file": ("reporter_clip.mp4", io.BytesIO(fake_mp4), "video/mp4")},
        data={"rights_type": "OWNED"},
    )
    assert res_r_upload.status_code == 201
    asset_id = res_r_upload.json()["id"]

    # C. Viewer can view the media -> 200 OK
    res_v_get = await client.get(f"/api/v1/media/{asset_id}", headers=headers_viewer)
    assert res_v_get.status_code == 200

    # D. Reporter attempts editorial review approval -> 403 Forbidden (Only EDITOR/ADMIN can review)
    res_r_review = await client.post(
        "/api/v1/media/moments/nonexistent-moment/review",
        headers=headers_reporter,
        json={"action": "ACCEPT"},
    )
    assert res_r_review.status_code == 403

    # E. Editor performs editorial review -> Allowed (200 or 404 if mock target_id not found)
    # Notice 403 is NOT returned for editor
    res_e_review = await client.post(
        "/api/v1/media/moments/nonexistent-moment/review",
        headers=headers_editor,
        json={"action": "ACCEPT"},
    )
    assert res_e_review.status_code == 404  # passed RBAC, failed item existence
