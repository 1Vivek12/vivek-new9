"""Tests for Media Rights Policy and Copyright Restrictions Enforcement."""

import io

import pytest

from app.services.media.rights import RightsViolationError, validate_rights_for_derivative


def test_rights_policy_rules():
    """Verify core business rules for media rights."""
    # 1. OWNED is always allowed
    assert validate_rights_for_derivative({"rights_type": "OWNED", "reuse_permitted": True}) is True

    # 2. RESTRICTED is strictly blocked
    with pytest.raises(RightsViolationError, match="RESTRICTED"):
        validate_rights_for_derivative({"rights_type": "RESTRICTED", "reuse_permitted": True})

    # 3. UNKNOWN requires human clearance
    with pytest.raises(RightsViolationError, match="UNKNOWN"):
        validate_rights_for_derivative({"rights_type": "UNKNOWN", "reuse_permitted": True})

    # 4. USER_PROVIDED requires reuse_permitted flag
    meta_user = {"rights_type": "USER_PROVIDED", "reuse_permitted": True}
    assert validate_rights_for_derivative(meta_user) is True

    with pytest.raises(RightsViolationError, match="reuse permission"):
        validate_rights_for_derivative({"rights_type": "USER_PROVIDED", "reuse_permitted": False})


@pytest.mark.asyncio
async def test_api_blocks_derivative_for_restricted_media(client, seeded_environment):
    """Verify POST /api/v1/media/{id}/derivatives rejects RESTRICTED media with HTTP 403."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    # Upload an asset with RESTRICTED rights
    fake_mp4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 100
    upload_res = await client.post(
        "/api/v1/media/upload",
        headers=headers,
        files={"file": ("classified_footage.mp4", io.BytesIO(fake_mp4), "video/mp4")},
        data={"rights_type": "RESTRICTED", "reuse_permitted": "false"},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    # Attempt to request a vertical video derivative -> 403 Forbidden
    deriv_res = await client.post(
        f"/api/v1/media/{asset_id}/derivatives",
        headers=headers,
        json={"derivative_type": "VERTICAL_9_16"},
    )
    assert deriv_res.status_code == 403
    assert "RESTRICTED" in deriv_res.json()["detail"]
