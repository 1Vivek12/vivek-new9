import hmac
import io
import time

import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_signed_download_token_workflow(client, seeded_environment):
    """Verify signed token issuance, verification, and expiration handling."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    # 1. Upload a media asset
    fake_mp4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 100
    upload_res = await client.post(
        "/api/v1/media/upload",
        headers=headers,
        files={"file": ("interview.mp4", io.BytesIO(fake_mp4), "video/mp4")},
        data={"rights_type": "OWNED"},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    # 2. Request signed download token
    tok_res = await client.post(f"/api/v1/media/{asset_id}/download-token", headers=headers)
    assert tok_res.status_code == 200
    token_data = tok_res.json()
    assert "download_token" in token_data
    token = token_data["download_token"]
    assert token_data["expires_in_seconds"] == 900

    # 3. Stream endpoint using valid token (No Authorization header required)
    stream_res = await client.get(f"/api/v1/media/{asset_id}/stream?token={token}")
    assert stream_res.status_code == 200
    assert stream_res.headers["content-type"] == "video/mp4"
    assert len(stream_res.content) == len(fake_mp4)

    # 4. Tampered token -> 403 Forbidden
    tampered_token = token[:-5] + "XXXXX"
    bad_res = await client.get(f"/api/v1/media/{asset_id}/stream?token={tampered_token}")
    assert bad_res.status_code == 403

    # 5. Expired token verification
    past_exp = int(time.time()) - 100
    payload = f"{tenant_id}:{asset_id}:test-user:{past_exp}"
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), "sha256"
    ).hexdigest()
    expired_token = f"{payload}:{sig}"

    exp_res = await client.get(f"/api/v1/media/{asset_id}/stream?token={expired_token}")
    assert exp_res.status_code == 403
    assert "expired" in exp_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cross_tenant_token_rejection(client, seeded_environment):
    """Verify that a token issued for Tenant A cannot be used to stream Tenant B assets."""
    env = seeded_environment
    tenant_1_id = env["tenant_news9"].id
    tenant_2_id = env["tenant_secondary"].id

    headers_1 = {"Authorization": f"Bearer {env['token_news9']}", "X-Tenant-ID": tenant_1_id}
    headers_2 = {"Authorization": f"Bearer {env['token_secondary']}", "X-Tenant-ID": tenant_2_id}

    fake_mp4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 100

    # Tenant 1 uploads asset 1
    res1 = await client.post(
        "/api/v1/media/upload",
        headers=headers_1,
        files={"file": ("asset1.mp4", io.BytesIO(fake_mp4), "video/mp4")},
        data={"rights_type": "OWNED"},
    )
    asset_1_id = res1.json()["id"]

    # Tenant 2 uploads asset 2
    res2 = await client.post(
        "/api/v1/media/upload",
        headers=headers_2,
        files={"file": ("asset2.mp4", io.BytesIO(fake_mp4), "video/mp4")},
        data={"rights_type": "OWNED"},
    )
    asset_2_id = res2.json()["id"]

    # Token generated for Asset 1 (Tenant 1)
    tok_res1 = await client.post(f"/api/v1/media/{asset_1_id}/download-token", headers=headers_1)
    token_1 = tok_res1.json()["download_token"]

    # Attempt to use Token 1 against Asset 2 -> 403/404 (mismatched media_id in token)
    mismatch_res = await client.get(f"/api/v1/media/{asset_2_id}/stream?token={token_1}")
    assert mismatch_res.status_code in (403, 404)
