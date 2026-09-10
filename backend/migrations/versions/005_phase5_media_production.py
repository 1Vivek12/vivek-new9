"""Phase 5 Media & Video Production schema.

Revision ID: 005_phase5_media_production
Revises: 004_phase4_ai_research
Create Date: 2026-09-10 13:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_phase5_media_production"
down_revision: Union[str, None] = "004_phase4_ai_research"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. media_assets
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("frame_rate", sa.Float(), nullable=True),
        sa.Column("codec", sa.String(64), nullable=True),
        sa.Column("container", sa.String(32), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="UPLOADED"),
        sa.Column("rights_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_media_assets_tenant_id", "media_assets", ["tenant_id"])
    op.create_index("ix_media_assets_story_id", "media_assets", ["story_id"])
    op.create_index("ix_media_assets_checksum", "media_assets", ["checksum"])
    op.create_index("ix_media_assets_status", "media_assets", ["status"])

    # 2. media_derivatives
    op.create_table(
        "media_derivatives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_media_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("derivative_type", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("processing_status", sa.String(32), nullable=False, server_default="READY"),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_media_derivatives_tenant_id", "media_derivatives", ["tenant_id"])
    op.create_index("ix_media_derivatives_source_media_id", "media_derivatives", ["source_media_id"])
    op.create_index("ix_media_derivatives_derivative_type", "media_derivatives", ["derivative_type"])
    op.create_index("ix_media_derivatives_processing_status", "media_derivatives", ["processing_status"])

    # 3. media_processing_jobs
    op.create_table(
        "media_processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("safe_error_message", sa.String(500), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_media_processing_jobs_tenant_id", "media_processing_jobs", ["tenant_id"])
    op.create_index("ix_media_processing_jobs_media_asset_id", "media_processing_jobs", ["media_asset_id"])
    op.create_index("ix_media_processing_jobs_job_type", "media_processing_jobs", ["job_type"])
    op.create_index("ix_media_processing_jobs_status", "media_processing_jobs", ["status"])

    # 4. transcripts
    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("model_provider", sa.String(64), nullable=False, server_default="whisper_local"),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("duration", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED"),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.9"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_transcripts_tenant_id", "transcripts", ["tenant_id"])
    op.create_index("ix_transcripts_media_asset_id", "transcripts", ["media_asset_id"])

    # 5. transcript_segments
    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transcript_id", sa.String(36), sa.ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("speaker_label", sa.String(64), nullable=False, server_default="Speaker 1"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.9"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_transcript_segments_tenant_id", "transcript_segments", ["tenant_id"])
    op.create_index("ix_transcript_segments_transcript_id", "transcript_segments", ["transcript_id"])

    # 6. scenes
    op.create_table(
        "scenes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("keyframe_storage_key", sa.String(500), nullable=True),
        sa.Column("scene_label", sa.String(128), nullable=False, server_default="Scene Segment"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_scenes_tenant_id", "scenes", ["tenant_id"])
    op.create_index("ix_scenes_media_asset_id", "scenes", ["media_asset_id"])

    # 7. ocr_results
    op.create_table(
        "ocr_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("extracted_text", sa.String(1000), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
        sa.Column("source_frame_key", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ocr_results_tenant_id", "ocr_results", ["tenant_id"])
    op.create_index("ix_ocr_results_media_asset_id", "ocr_results", ["media_asset_id"])

    # 8. clip_candidates
    op.create_table(
        "clip_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="SHORT_CANDIDATE"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("suggested_aspect_ratio", sa.String(16), nullable=False, server_default="9:16"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("status", sa.String(32), nullable=False, server_default="SUGGESTED"),
        sa.Column("actioned_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_clip_candidates_tenant_id", "clip_candidates", ["tenant_id"])
    op.create_index("ix_clip_candidates_media_asset_id", "clip_candidates", ["media_asset_id"])
    op.create_index("ix_clip_candidates_status", "clip_candidates", ["status"])

    # 9. subtitle_tracks
    op.create_table(
        "subtitle_tracks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("format", sa.String(16), nullable=False, server_default="SRT"),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="GENERATED"),
        sa.Column("generated_by", sa.String(64), nullable=False, server_default="TRANSCRIPT_AUTOMATION"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_subtitle_tracks_tenant_id", "subtitle_tracks", ["tenant_id"])
    op.create_index("ix_subtitle_tracks_media_asset_id", "subtitle_tracks", ["media_asset_id"])

    # 10. visual_assets
    op.create_table(
        "visual_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_type", sa.String(64), nullable=False, server_default="KEYFRAME"),
        sa.Column("timestamp", sa.Float(), nullable=True),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("headline_text", sa.String(255), nullable=True),
        sa.Column("visual_concept_description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="CANDIDATE"),
        sa.Column("actioned_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_visual_assets_tenant_id", "visual_assets", ["tenant_id"])
    op.create_index("ix_visual_assets_media_asset_id", "visual_assets", ["media_asset_id"])
    op.create_index("ix_visual_assets_status", "visual_assets", ["status"])


def downgrade() -> None:
    op.drop_table("visual_assets")
    op.drop_table("subtitle_tracks")
    op.drop_table("clip_candidates")
    op.drop_table("ocr_results")
    op.drop_table("scenes")
    op.drop_table("transcript_segments")
    op.drop_table("transcripts")
    op.drop_table("media_processing_jobs")
    op.drop_table("media_derivatives")
    op.drop_table("media_assets")
