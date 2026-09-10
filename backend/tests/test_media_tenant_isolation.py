"""Tests for Media Subsystem Cross-Tenant Data Isolation and Access Security."""

import io

import pytest


@pytest.mark.asyncio
async def test_cross_tenant_media_isolation(client, seeded_environment):
    """Ensure media assets belonging to Tenant News 9 cannot be accessed by Secondary Tenant."""
    env = seeded_environment
    tenant_1_id = env["tenant_news9"].id
    tenant_2_id = env["tenant_secondary"].id

    headers_tenant1 = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_1_id,
    }
    headers_tenant2 = {
        "Authorization": f"Bearer {env['token_secondary']}",
        "X-Tenant-ID": tenant_2_id,
    }

    # 1. Tenant 1 uploads a media file
    fake_mp4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 100
    upload_res = await client.post(
        "/api/v1/media/upload",
        headers=headers_tenant1,
        files={"file": ("tenant1_footage.mp4", io.BytesIO(fake_mp4), "video/mp4")},
        data={"rights_type": "OWNED"},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    # 2. Tenant 2 lists media -> must not see Tenant 1's media
    list_res_t2 = await client.get("/api/v1/media", headers=headers_tenant2)
    assert list_res_t2.status_code == 200
    t2_assets = list_res_t2.json()
    assert not any(a["id"] == asset_id for a in t2_assets)

    # 3. Tenant 2 attempts direct GET on Tenant 1's asset -> 404
    get_res_t2 = await client.get(f"/api/v1/media/{asset_id}", headers=headers_tenant2)
    assert get_res_t2.status_code == 404

    # 4. Tenant 2 attempts to trigger processing on Tenant 1's asset -> 404
    proc_res_t2 = await client.post(f"/api/v1/media/{asset_id}/process", headers=headers_tenant2)
    assert proc_res_t2.status_code == 404

    # 5. Tenant 2 attempts to request derivatives on Tenant 1's asset -> 404
    deriv_res_t2 = await client.post(
        f"/api/v1/media/{asset_id}/derivatives",
        headers=headers_tenant2,
        json={"derivative_type": "VERTICAL_9_16"},
    )
    assert deriv_res_t2.status_code == 404

    # 6. Tenant 2 attempts to access transcript, scenes, OCR, moments of Tenant 1 -> 404
    tx_404 = await client.get(f"/api/v1/media/{asset_id}/transcript", headers=headers_tenant2)
    assert tx_404.status_code == 404
    sc_404 = await client.get(f"/api/v1/media/{asset_id}/scenes", headers=headers_tenant2)
    assert sc_404.status_code == 404
    ocr_404 = await client.get(f"/api/v1/media/{asset_id}/ocr", headers=headers_tenant2)
    assert ocr_404.status_code == 404
    cc_404 = await client.get(f"/api/v1/media/{asset_id}/clip-candidates", headers=headers_tenant2)
    assert cc_404.status_code == 404

    # 7. Tenant 1 can access everything successfully
    get_res_t1 = await client.get(f"/api/v1/media/{asset_id}", headers=headers_tenant1)
    assert get_res_t1.status_code == 200
    assert get_res_t1.json()["id"] == asset_id
