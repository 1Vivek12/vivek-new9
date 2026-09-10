"""Phase 5 Media & Video Production API endpoints."""

import hmac
import os
import time
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.models.media import (
    ClipCandidate,
    MediaAsset,
    MediaDerivative,
    MediaProcessingJob,
    OCRResult,
    Scene,
    SubtitleTrack,
    Transcript,
    VisualAsset,
)
from app.db.session import get_db_session
from app.schemas.media import (
    ClipCandidateResponse,
    CreateDerivativeRequest,
    DownloadTokenResponse,
    MediaAssetResponse,
    MediaDerivativeResponse,
    MediaProcessingJobResponse,
    OCRResultResponse,
    ReviewActionRequest,
    SceneResponse,
    SubtitleTrackResponse,
    TranscriptResponse,
    VisualAssetResponse,
)
from app.services.media.production_engine import MediaProductionEngine
from app.services.media.rights import RightsViolationError, validate_rights_for_derivative
from app.services.media.validator import MediaValidationError
from app.services.storage.local import LocalStorageProvider

router = APIRouter(tags=["Media & Video Production"])
engine = MediaProductionEngine()
storage = LocalStorageProvider()


def generate_download_token(tenant_id: str, media_id: str, user_id: str) -> str:
    """Generate a tamper-proof short-lived signed token (valid for 15 minutes)."""
    exp = int(time.time()) + 900
    payload = f"{tenant_id}:{media_id}:{user_id}:{exp}"
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), "sha256"
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_download_token(token: str, expected_tenant_id: str, expected_media_id: str) -> bool:
    """Verify validity, expiration, and tenant binding of download token."""
    try:
        parts = token.split(":")
        if len(parts) != 5:
            return False
        tenant_id, media_id, user_id, exp_str, sig = parts
        if tenant_id != expected_tenant_id or media_id != expected_media_id:
            return False
        if int(exp_str) < time.time():
            return False
        expected_payload = f"{tenant_id}:{media_id}:{user_id}:{exp_str}"
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"), expected_payload.encode("utf-8"), "sha256"
        ).hexdigest()
        return hmac.compare_digest(sig, expected_sig)
    except Exception:
        return False


@router.post(
    "/media/upload",
    response_model=MediaAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media_file(
    file: UploadFile = File(...),
    story_id: Optional[str] = Form(None),
    rights_type: str = Form("UNKNOWN"),
    license_details: Optional[str] = Form(None),
    attribution: Optional[str] = Form(None),
    reuse_permitted: bool = Form(False),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> MediaAssetResponse:
    """Upload raw media file with rights metadata declaration and tenant storage containment."""
    check_permission(context, "UPLOAD_MEDIA")

    content = await file.read()
    rights_meta = {
        "rights_type": rights_type.upper(),
        "license_details": license_details,
        "attribution": attribution,
        "reuse_permitted": reuse_permitted,
    }

    try:
        asset = await engine.ingest_media(
            db=db,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            filename=file.filename or "media_upload",
            content=content,
            declared_mime=file.content_type,
            story_id=story_id,
            rights_metadata=rights_meta,
        )
        return MediaAssetResponse.model_validate(asset)
    except MediaValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/media", response_model=List[MediaAssetResponse])
async def list_media_assets(
    story_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    media_type: Optional[str] = Query(None),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[MediaAssetResponse]:
    """List tenant-scoped media assets."""
    check_permission(context, "VIEW_MEDIA")

    stmt = select(MediaAsset).where(MediaAsset.tenant_id == context.tenant_id)
    if story_id:
        stmt = stmt.where(MediaAsset.story_id == story_id)
    if status_filter:
        stmt = stmt.where(MediaAsset.status == status_filter.upper())
    if media_type:
        stmt = stmt.where(MediaAsset.media_type == media_type.upper())

    stmt = stmt.order_by(MediaAsset.created_at.desc())
    res = await db.execute(stmt)
    assets = res.scalars().all()
    return [MediaAssetResponse.model_validate(a) for a in assets]


@router.get("/media/{media_id}", response_model=MediaAssetResponse)
async def get_media_asset(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> MediaAssetResponse:
    """Retrieve single media asset metadata."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")
    return MediaAssetResponse.model_validate(asset)


@router.post("/media/{media_id}/validate", response_model=MediaAssetResponse)
async def validate_media(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> MediaAssetResponse:
    """Run checksum and metadata inspection on uploaded media."""
    check_permission(context, "PROCESS_MEDIA")

    try:
        updated = await engine.validate_media_asset(
            db=db, tenant_id=context.tenant_id, media_id=media_id, user_id=context.user_id
        )
        return MediaAssetResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/media/{media_id}/process", response_model=MediaAssetResponse)
async def process_media(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> MediaAssetResponse:
    """Trigger media processing pipeline (audio, transcription, scenes, subtitles, derivatives)."""
    check_permission(context, "PROCESS_MEDIA")

    try:
        processed = await engine.run_processing_pipeline(
            db=db, tenant_id=context.tenant_id, media_id=media_id, user_id=context.user_id
        )
        return MediaAssetResponse.model_validate(processed)
    except RightsViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/media/{media_id}/jobs", response_model=List[MediaProcessingJobResponse])
async def list_media_jobs(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[MediaProcessingJobResponse]:
    """List processing jobs for media asset."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    stmt = (
        select(MediaProcessingJob)
        .where(
            MediaProcessingJob.tenant_id == context.tenant_id,
            MediaProcessingJob.media_asset_id == media_id,
        )
        .order_by(MediaProcessingJob.created_at.asc())
    )
    res = await db.execute(stmt)
    jobs = res.scalars().all()
    return [MediaProcessingJobResponse.model_validate(j) for j in jobs]


@router.get("/media/{media_id}/transcript", response_model=TranscriptResponse)
async def get_media_transcript(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> TranscriptResponse:
    """Retrieve full transcript and timestamped dialogue segments."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    stmt = select(Transcript).where(
        Transcript.tenant_id == context.tenant_id, Transcript.media_asset_id == media_id
    )
    res = await db.execute(stmt)
    tx = res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found")

    from app.db.models.media import TranscriptSegment

    segs_stmt = (
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == tx.id)
        .order_by(TranscriptSegment.sequence.asc())
    )
    seg_res = await db.execute(segs_stmt)
    segments = seg_res.scalars().all()
    from app.schemas.media import TranscriptSegmentResponse

    seg_responses = [TranscriptSegmentResponse.model_validate(s) for s in segments]
    return TranscriptResponse(
        id=tx.id,
        tenant_id=tx.tenant_id,
        media_asset_id=tx.media_asset_id,
        language=tx.language,
        model_provider=tx.model_provider,
        duration=tx.duration,
        status=tx.status,
        full_text=tx.full_text,
        confidence_score=tx.confidence_score,
        created_at=tx.created_at,
        segments=seg_responses,
    )


@router.get("/media/{media_id}/scenes", response_model=List[SceneResponse])
async def get_media_scenes(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[SceneResponse]:
    """Retrieve detected shot boundaries and keyframe tags."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    stmt = (
        select(Scene)
        .where(Scene.tenant_id == context.tenant_id, Scene.media_asset_id == media_id)
        .order_by(Scene.sequence.asc())
    )
    res = await db.execute(stmt)
    scenes = res.scalars().all()
    return [SceneResponse.model_validate(s) for s in scenes]


@router.get("/media/{media_id}/ocr", response_model=List[OCRResultResponse])
async def get_media_ocr_results(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[OCRResultResponse]:
    """Retrieve machine-extracted on-screen text items."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    stmt = (
        select(OCRResult)
        .where(OCRResult.tenant_id == context.tenant_id, OCRResult.media_asset_id == media_id)
        .order_by(OCRResult.timestamp.asc())
    )
    res = await db.execute(stmt)
    results = res.scalars().all()
    return [OCRResultResponse.model_validate(r) for r in results]


@router.get("/media/{media_id}/moments", response_model=List[ClipCandidateResponse])
@router.get("/media/{media_id}/clip-candidates", response_model=List[ClipCandidateResponse])
async def get_clip_candidates(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[ClipCandidateResponse]:
    """Retrieve important moment clip candidates."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    stmt = (
        select(ClipCandidate)
        .where(
            ClipCandidate.tenant_id == context.tenant_id, ClipCandidate.media_asset_id == media_id
        )
        .order_by(ClipCandidate.start_time.asc())
    )
    res = await db.execute(stmt)
    clips = res.scalars().all()
    return [ClipCandidateResponse.model_validate(c) for c in clips]


@router.get("/media/{media_id}/derivatives", response_model=List[MediaDerivativeResponse])
async def get_media_derivatives(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[MediaDerivativeResponse]:
    """Retrieve generated video variants (vertical 9:16, proxy, audio)."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    stmt = (
        select(MediaDerivative)
        .where(
            MediaDerivative.tenant_id == context.tenant_id,
            MediaDerivative.source_media_id == media_id,
        )
        .order_by(MediaDerivative.created_at.asc())
    )
    res = await db.execute(stmt)
    derivatives = res.scalars().all()
    return [MediaDerivativeResponse.model_validate(d) for d in derivatives]


@router.post("/media/{media_id}/derivatives", response_model=MediaDerivativeResponse)
async def create_media_derivative(
    media_id: str,
    payload: CreateDerivativeRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> MediaDerivativeResponse:
    """Request derivative generation (e.g. 9:16 vertical), enforcing rights policy."""
    check_permission(context, "PROCESS_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    try:
        validate_rights_for_derivative(asset.rights_metadata)
    except RightsViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    rel_key = f"media/{asset.id}/derivatives/{payload.derivative_type.lower()}.mp4"
    der = MediaDerivative(
        tenant_id=context.tenant_id,
        source_media_id=asset.id,
        derivative_type=payload.derivative_type,
        storage_key=rel_key,
        mime_type="video/mp4",
        file_size=5000,
        width=1080 if "9_16" in payload.derivative_type else 1280,
        height=1920 if "9_16" in payload.derivative_type else 720,
        duration=asset.duration or 30.0,
        checksum="derivative_sha256",
        processing_status="READY",
        metadata_payload={"aspect_ratio": "9:16" if "9_16" in payload.derivative_type else "16:9"},
    )
    db.add(der)
    await db.commit()
    await db.refresh(der)
    return MediaDerivativeResponse.model_validate(der)


@router.get("/media/{media_id}/subtitles", response_model=List[SubtitleTrackResponse])
async def get_media_subtitles(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[SubtitleTrackResponse]:
    """Retrieve SRT and WebVTT timed subtitle tracks."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    stmt = (
        select(SubtitleTrack)
        .where(
            SubtitleTrack.tenant_id == context.tenant_id,
            SubtitleTrack.media_asset_id == media_id,
        )
        .order_by(SubtitleTrack.format.asc())
    )
    res = await db.execute(stmt)
    tracks = res.scalars().all()
    return [SubtitleTrackResponse.model_validate(t) for t in tracks]


@router.get("/media/{media_id}/visual-assets", response_model=List[VisualAssetResponse])
async def get_media_visual_assets(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[VisualAssetResponse]:
    """Retrieve thumbnail candidates and visual concept cards."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    stmt = (
        select(VisualAsset)
        .where(
            VisualAsset.tenant_id == context.tenant_id,
            VisualAsset.media_asset_id == media_id,
        )
        .order_by(VisualAsset.created_at.asc())
    )
    res = await db.execute(stmt)
    items = res.scalars().all()
    return [VisualAssetResponse.model_validate(i) for i in items]


# ---------------------------------------------------------------------------
# Human Review Gates
# ---------------------------------------------------------------------------


@router.post("/media/moments/{moment_id}/review", response_model=ClipCandidateResponse)
async def review_clip_candidate(
    moment_id: str,
    payload: ReviewActionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> ClipCandidateResponse:
    """Human editorial review action on clip candidate (ACCEPT or REJECT)."""
    check_permission(context, "REVIEW_MEDIA")

    try:
        updated = await engine.review_clip_candidate(
            db=db,
            tenant_id=context.tenant_id,
            moment_id=moment_id,
            user_id=context.user_id,
            action=payload.action,
            rejection_reason=payload.rejection_reason,
        )
        return ClipCandidateResponse.model_validate(updated)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e


@router.post("/media/visual-assets/{asset_id}/review", response_model=VisualAssetResponse)
async def review_visual_asset(
    asset_id: str,
    payload: ReviewActionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> VisualAssetResponse:
    """Human editorial review action on thumbnail candidate."""
    check_permission(context, "REVIEW_MEDIA")

    try:
        updated = await engine.review_visual_asset(
            db=db,
            tenant_id=context.tenant_id,
            asset_id=asset_id,
            user_id=context.user_id,
            action=payload.action,
            rejection_reason=payload.rejection_reason,
        )
        return VisualAssetResponse.model_validate(updated)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e


# ---------------------------------------------------------------------------
# Secure Media Download & Streaming
# ---------------------------------------------------------------------------


@router.post("/media/{media_id}/download-token", response_model=DownloadTokenResponse)
async def create_download_token(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> DownloadTokenResponse:
    """Generate signed short-lived download token for secure video playback."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    token = generate_download_token(context.tenant_id, asset.id, context.user_id)
    return DownloadTokenResponse(
        download_token=token,
        expires_in_seconds=900,
        stream_url=f"/api/v1/media/{asset.id}/stream?token={token}",
    )


@router.get("/media/{media_id}/download")
async def download_media_file(
    media_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """Authorized direct media download enforcing tenant containment."""
    check_permission(context, "VIEW_MEDIA")

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    abs_path = storage._resolve_tenant_path(context.tenant_id, asset.storage_key)
    if not os.path.exists(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found on disk"
        )

    return FileResponse(
        path=abs_path,
        media_type=asset.mime_type,
        filename=asset.original_filename,
    )


@router.get("/media/{media_id}/stream")
async def stream_media_file(
    media_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """Stream media file using signed short-lived token."""
    parts = token.split(":")
    if len(parts) != 5:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token structure")

    tenant_id = parts[0]
    if not verify_download_token(token, tenant_id, media_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired download token"
        )

    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    abs_path = storage._resolve_tenant_path(tenant_id, asset.storage_key)
    if not os.path.exists(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found on disk"
        )

    return FileResponse(
        path=abs_path,
        media_type=asset.mime_type,
        filename=asset.original_filename,
    )
