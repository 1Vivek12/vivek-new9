"""End-to-end integration test for Media Production Lifecycle, Review Gates, and Audit Trails."""

import io

import pytest
from sqlalchemy import select

from app.db.models.audit import AuditLog
from app.services.media.ocr import MockOCRProvider
from app.services.media.processor import MockMediaProcessor
from app.services.media.production_engine import MediaProductionEngine
from app.services.media.scenes import MockSceneDetector
from app.services.media.transcription import MockTranscriptionProvider


@pytest.mark.asyncio
async def test_media_production_lifecycle_and_review_gates(client, seeded_environment, db_session):
    """Verify full end-to-end media processing using mock providers,
    human review gates, and audit trails.
    """
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    # 1. Upload Raw Video
    fake_mp4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 200
    upload_res = await client.post(
        "/api/v1/media/upload",
        headers=headers,
        files={"file": ("breaking_live.mp4", io.BytesIO(fake_mp4), "video/mp4")},
        data={"rights_type": "OWNED", "attribution": "News 9 Studio"},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    # 2. Process using Engine with test mock providers
    mock_proc = MockMediaProcessor()
    engine = MediaProductionEngine(
        media_processor=mock_proc,
        transcription_provider=MockTranscriptionProvider(),
        scene_detector=MockSceneDetector(),
        ocr_provider=MockOCRProvider(),
    )

    processed_asset = await engine.run_processing_pipeline(
        db=db_session,
        tenant_id=tenant_id,
        media_id=asset_id,
        user_id=env["user_news9"].id,
    )
    assert processed_asset.status == "READY"

    # 3. Verify asset details updated
    get_res = await client.get(f"/api/v1/media/{asset_id}", headers=headers)
    assert get_res.status_code == 200
    asset_data = get_res.json()
    assert asset_data["status"] == "READY"
    assert asset_data["duration"] is not None
    assert asset_data["codec"] == "h264"
    assert asset_data["width"] == 1920

    # 4. Verify transcript exists with neutral speaker labels
    tx_res = await client.get(f"/api/v1/media/{asset_id}/transcript", headers=headers)
    assert tx_res.status_code == 200
    tx_data = tx_res.json()
    assert len(tx_data["segments"]) > 0
    assert tx_data["segments"][0]["speaker_label"] in ("Speaker 1", "SPEAKER_00")

    # 5. Verify scenes detected
    sc_res = await client.get(f"/api/v1/media/{asset_id}/scenes", headers=headers)
    assert sc_res.status_code == 200
    assert len(sc_res.json()) > 0

    # 6. Verify OCR results extracted
    ocr_res = await client.get(f"/api/v1/media/{asset_id}/ocr", headers=headers)
    assert ocr_res.status_code == 200
    assert len(ocr_res.json()) > 0

    # 7. Verify Clip Candidates generated and in SUGGESTED status
    moments_res = await client.get(f"/api/v1/media/{asset_id}/clip-candidates", headers=headers)
    assert moments_res.status_code == 200
    clips = moments_res.json()
    assert len(clips) > 0
    clip_id = clips[0]["id"]
    assert clips[0]["status"] == "SUGGESTED"

    # 8. Human Review Gate: Rejecting without reason fails with 422
    bad_review = await client.post(
        f"/api/v1/media/moments/{clip_id}/review",
        headers=headers,
        json={"action": "REJECT"},
    )
    assert bad_review.status_code == 422
    assert "rejection reason" in bad_review.json()["detail"].lower()

    # 9. Human Review Gate: Rejecting WITH reason succeeds
    rej_review = await client.post(
        f"/api/v1/media/moments/{clip_id}/review",
        headers=headers,
        json={
            "action": "REJECT",
            "rejection_reason": "Audio quality in this section is suboptimal.",
        },
    )
    assert rej_review.status_code == 200
    assert rej_review.json()["status"] == "REJECTED"
    assert rej_review.json()["rejection_reason"] == "Audio quality in this section is suboptimal."

    # 10. Human Review Gate: Approving clip succeeds
    appr_review = await client.post(
        f"/api/v1/media/moments/{clip_id}/review",
        headers=headers,
        json={"action": "ACCEPT"},
    )
    assert appr_review.status_code == 200
    assert appr_review.json()["status"] == "ACCEPTED"

    # 11. Verify Audit Logs created
    audit_records = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.resource_type.in_(["MediaAsset", "media_asset", "ClipCandidate"]),
            )
        )
    ).scalars().all()
    assert len(audit_records) > 0

