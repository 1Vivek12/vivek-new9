"""Phase 6 Publishing & Distribution schema.

Revision ID: 006_phase6_publishing_distribution
Revises: 005_phase5_media_production
Create Date: 2026-09-14 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_phase6_publishing_distribution"
down_revision: Union[str, None] = "005_phase5_media_production"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. publishing_destinations
    op.create_table(
        "publishing_destinations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_type", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "destination_type", name="uq_publishing_dest_tenant_type"),
    )
    op.create_index("ix_publishing_destinations_tenant_id", "publishing_destinations", ["tenant_id"])
    op.create_index("ix_publishing_destinations_destination_type", "publishing_destinations", ["destination_type"])

    # 2. connected_accounts
    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("destination_id", sa.String(36), sa.ForeignKey("publishing_destinations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("platform_account_id", sa.String(128), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("account_metadata", sa.JSON(), nullable=False),
        sa.Column("connection_status", sa.String(32), nullable=False, server_default="CONNECTED"),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "destination_id", "platform_account_id", name="uq_connected_account_identity"),
    )
    op.create_index("ix_connected_accounts_tenant_id", "connected_accounts", ["tenant_id"])
    op.create_index("ix_connected_accounts_destination_id", "connected_accounts", ["destination_id"])
    op.create_index("ix_connected_accounts_platform_account_id", "connected_accounts", ["platform_account_id"])
    op.create_index("ix_connected_accounts_is_deleted", "connected_accounts", ["is_deleted"])

    # 3. account_credentials
    op.create_table(
        "account_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("access_token_nonce", sa.String(32), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("refresh_token_nonce", sa.String(32), nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_account_credentials_tenant_id", "account_credentials", ["tenant_id"])
    op.create_index("ix_account_credentials_account_id", "account_credentials", ["account_id"])

    # 4. oauth_states
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("initiating_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_type", sa.String(32), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_oauth_states_tenant_id", "oauth_states", ["tenant_id"])
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])

    # 5. publishing_packages
    op.create_table(
        "publishing_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_version_id", sa.String(36), sa.ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("primary_media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("primary_derivative_id", sa.String(36), sa.ForeignKey("media_derivatives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visual_asset_id", sa.String(36), sa.ForeignKey("visual_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subtitle_track_id", sa.String(36), sa.ForeignKey("subtitle_tracks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("canonical_title", sa.String(255), nullable=False),
        sa.Column("canonical_description", sa.Text(), nullable=False),
        sa.Column("canonical_caption", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("current_approval_id", sa.String(36), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_publishing_packages_tenant_id", "publishing_packages", ["tenant_id"])
    op.create_index("ix_publishing_packages_story_id", "publishing_packages", ["story_id"])
    op.create_index("ix_publishing_packages_status", "publishing_packages", ["status"])

    # 6. platform_payloads
    op.create_table(
        "platform_payloads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("package_id", sa.String(36), sa.ForeignKey("publishing_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_type", sa.String(32), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("adapted_title", sa.String(255), nullable=False),
        sa.Column("adapted_description", sa.Text(), nullable=False),
        sa.Column("adapted_caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_aspect_ratio", sa.String(16), nullable=False, server_default="16:9"),
        sa.Column("selected_derivative_id", sa.String(36), sa.ForeignKey("media_derivatives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("selected_thumbnail_id", sa.String(36), sa.ForeignKey("visual_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("custom_metadata", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("package_id", "destination_type", "account_id", name="uq_platform_payload_target"),
    )
    op.create_index("ix_platform_payloads_tenant_id", "platform_payloads", ["tenant_id"])
    op.create_index("ix_platform_payloads_package_id", "platform_payloads", ["package_id"])

    # 7. publishing_approval_events
    op.create_table(
        "publishing_approval_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("package_id", sa.String(36), sa.ForeignKey("publishing_packages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("decided_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("publication_manifest_hash", sa.String(64), nullable=False),
        sa.Column("manifest_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_publishing_approval_events_tenant_id", "publishing_approval_events", ["tenant_id"])
    op.create_index("ix_publishing_approval_events_package_id", "publishing_approval_events", ["package_id"])
    op.create_index("ix_publishing_approval_events_event_type", "publishing_approval_events", ["event_type"])
    op.create_index("ix_publishing_approval_events_manifest_hash", "publishing_approval_events", ["publication_manifest_hash"])

    # 8. publishing_jobs
    op.create_table(
        "publishing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("package_id", sa.String(36), sa.ForeignKey("publishing_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("publication_idempotency_key", sa.String(64), unique=True, nullable=False),
        sa.Column("job_status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("safe_error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_publishing_jobs_tenant_id", "publishing_jobs", ["tenant_id"])
    op.create_index("ix_publishing_jobs_package_id", "publishing_jobs", ["package_id"])
    op.create_index("ix_publishing_jobs_job_status", "publishing_jobs", ["job_status"])
    op.create_index("ix_publishing_jobs_scheduled_at", "publishing_jobs", ["scheduled_at"])
    op.create_index("ix_publishing_jobs_idempotency_key", "publishing_jobs", ["publication_idempotency_key"])

    # 9. publishing_attempts
    op.create_table(
        "publishing_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("publishing_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("platform_error_code", sa.String(64), nullable=True),
        sa.Column("sanitized_error_message", sa.String(500), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_publishing_attempt_step"),
    )
    op.create_index("ix_publishing_attempts_tenant_id", "publishing_attempts", ["tenant_id"])
    op.create_index("ix_publishing_attempts_job_id", "publishing_attempts", ["job_id"])

    # 10. published_items
    op.create_table(
        "published_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("package_id", sa.String(36), sa.ForeignKey("publishing_packages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("destination_type", sa.String(32), nullable=False),
        sa.Column("external_item_id", sa.String(255), nullable=False),
        sa.Column("external_url", sa.String(500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("visibility", sa.String(32), nullable=False, server_default="PUBLIC"),
        sa.Column("platform_state", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("account_id", "external_item_id", name="uq_published_account_external_item"),
    )
    op.create_index("ix_published_items_tenant_id", "published_items", ["tenant_id"])
    op.create_index("ix_published_items_package_id", "published_items", ["package_id"])
    op.create_index("ix_published_items_external_item_id", "published_items", ["external_item_id"])

    # 11. webhook_events
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("destination_type", sa.String(32), nullable=False),
        sa.Column("external_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processing_status", sa.String(32), nullable=False, server_default="PROCESSED"),
        sa.Column("sanitized_payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("destination_type", "external_event_id", name="uq_webhook_events_destination_external_id"),
    )
    op.create_index("ix_webhook_events_tenant_id", "webhook_events", ["tenant_id"])
    op.create_index("ix_webhook_events_external_event_id", "webhook_events", ["external_event_id"])


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("published_items")
    op.drop_table("publishing_attempts")
    op.drop_table("publishing_jobs")
    op.drop_table("publishing_approval_events")
    op.drop_table("platform_payloads")
    op.drop_table("publishing_packages")
    op.drop_table("oauth_states")
    op.drop_table("account_credentials")
    op.drop_table("connected_accounts")
    op.drop_table("publishing_destinations")
