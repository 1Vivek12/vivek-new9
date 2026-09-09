"""Phase 3 Trend Radar and Source Monitoring schema.

Revision ID: 003_phase3_trend_radar
Revises: 002_phase2_editorial
Create Date: 2026-09-09 23:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_phase3_trend_radar"
down_revision: Union[str, None] = "002_phase2_editorial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Sources table (Source Registry)
    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="RSS"),
        sa.Column("feed_url", sa.String(2048), nullable=True),
        sa.Column("website_url", sa.String(2048), nullable=True),
        sa.Column("publisher_name", sa.String(255), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True, server_default="70.0"),
        sa.Column("trust_level", sa.String(32), nullable=False, server_default="MEDIUM"),
        sa.Column("jurisdiction", sa.String(100), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("polling_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("rights_metadata", sa.JSON(), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_message", sa.String(500), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sources_tenant_id", "sources", ["tenant_id"])
    op.create_index("ix_sources_source_type", "sources", ["source_type"])

    # 2. Similar Story Groups table
    op.create_table(
        "similar_story_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("representative_title", sa.String(500), nullable=False),
        sa.Column("topic_keywords", sa.JSON(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("independent_publisher_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("strongest_source_reliability", sa.Float(), nullable=False, server_default="70.0"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trend_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_similar_story_groups_tenant_id", "similar_story_groups", ["tenant_id"])
    op.create_index("ix_similar_story_groups_trend_score", "similar_story_groups", ["trend_score"])

    # 3. Source Items table
    op.create_table(
        "source_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.String(36),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "similar_story_group_id",
            sa.String(36),
            sa.ForeignKey("similar_story_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_id", sa.String(512), nullable=True),
        sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("rights_metadata", sa.JSON(), nullable=False),
        sa.Column("raw_metadata", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "fingerprint", name="uq_source_item_tenant_fingerprint"),
    )
    op.create_index("ix_source_items_tenant_id", "source_items", ["tenant_id"])
    op.create_index("ix_source_items_source_id", "source_items", ["source_id"])
    op.create_index("ix_source_items_similar_story_group_id", "source_items", ["similar_story_group_id"])
    op.create_index("ix_source_items_external_id", "source_items", ["external_id"])
    op.create_index("ix_source_items_fingerprint", "source_items", ["fingerprint"])
    op.create_index("ix_source_items_published_at", "source_items", ["published_at"])
    op.create_index("ix_source_items_fetched_at", "source_items", ["fetched_at"])

    # 4. Content Opportunities table
    op.create_table(
        "content_opportunities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "similar_story_group_id",
            sa.String(36),
            sa.ForeignKey("similar_story_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            sa.String(36),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("trend_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("publisher_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("urgency", sa.String(32), nullable=False, server_default="NORMAL"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DISCOVERED"),
        sa.Column("risk_indicators", sa.JSON(), nullable=False),
        sa.Column("score_explanation", sa.JSON(), nullable=False),
        sa.Column(
            "converted_story_id",
            sa.String(36),
            sa.ForeignKey("stories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actioned_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_content_opportunities_tenant_id", "content_opportunities", ["tenant_id"])
    op.create_index("ix_content_opportunities_topic", "content_opportunities", ["topic"])
    op.create_index("ix_content_opportunities_status", "content_opportunities", ["status"])
    op.create_index("ix_content_opportunities_trend_score", "content_opportunities", ["trend_score"])


def downgrade() -> None:
    op.drop_table("content_opportunities")
    op.drop_table("source_items")
    op.drop_table("similar_story_groups")
    op.drop_table("sources")
