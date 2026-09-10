"""Phase 4 AI Research & Content Intelligence schema.

Revision ID: 004_phase4_ai_research
Revises: 003_phase3_trend_radar
Create Date: 2026-09-10 01:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_phase4_ai_research"
down_revision: Union[str, None] = "003_phase3_trend_radar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. research_jobs
    op.create_table(
        "research_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("content_opportunities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_topic", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("requested_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_research_jobs_tenant_id", "research_jobs", ["tenant_id"])
    op.create_index("ix_research_jobs_story_id", "research_jobs", ["story_id"])
    op.create_index("ix_research_jobs_opportunity_id", "research_jobs", ["opportunity_id"])
    op.create_index("ix_research_jobs_status", "research_jobs", ["status"])

    # 2. research_evidence (Bounded storage: max 750 snippet, max 500 claim summary)
    op.create_table(
        "research_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_job_id", sa.String(36), sa.ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_item_id", sa.String(36), sa.ForeignKey("source_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("evidence_snippet", sa.String(750), nullable=False),
        sa.Column("normalized_claim_summary", sa.String(500), nullable=False),
        sa.Column("source_reliability", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("rights_metadata", sa.JSON(), nullable=False),
        sa.Column("adversarial_instruction_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_research_evidence_tenant_id", "research_evidence", ["tenant_id"])
    op.create_index("ix_research_evidence_research_job_id", "research_evidence", ["research_job_id"])
    op.create_index("ix_research_evidence_source_item_id", "research_evidence", ["source_item_id"])

    # 3. research_claims
    op.create_table(
        "research_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_job_id", sa.String(36), sa.ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_text", sa.String(500), nullable=False),
        sa.Column("claim_type", sa.String(32), nullable=False, server_default="FACT"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("status", sa.String(32), nullable=False, server_default="NEEDS_REVIEW"),
        sa.Column("supporting_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("contradicting_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("verification_notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_research_claims_tenant_id", "research_claims", ["tenant_id"])
    op.create_index("ix_research_claims_research_job_id", "research_claims", ["research_job_id"])

    # 4. research_briefs
    op.create_table(
        "research_briefs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_job_id", sa.String(36), sa.ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("what_happened", sa.Text(), nullable=False),
        sa.Column("who_involved", sa.JSON(), nullable=False),
        sa.Column("when_timeline", sa.JSON(), nullable=False),
        sa.Column("where_locations", sa.JSON(), nullable=False),
        sa.Column("why_causes", sa.Text(), nullable=True),
        sa.Column("confirmed_facts", sa.JSON(), nullable=False),
        sa.Column("disputed_facts", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("key_entities", sa.JSON(), nullable=False),
        sa.Column("source_confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("editorial_warnings", sa.JSON(), nullable=False),
        sa.Column("suggested_angles", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_research_briefs_tenant_id", "research_briefs", ["tenant_id"])
    op.create_index("ix_research_briefs_research_job_id", "research_briefs", ["research_job_id"])
    op.create_index("ix_research_briefs_story_id", "research_briefs", ["story_id"])

    # 5. ai_content_plans
    op.create_table(
        "ai_content_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_job_id", sa.String(36), sa.ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposed_angle", sa.String(255), nullable=False),
        sa.Column("target_audience", sa.String(255), nullable=False),
        sa.Column("key_message", sa.Text(), nullable=False),
        sa.Column("narrative_structure", sa.JSON(), nullable=False),
        sa.Column("suggested_format", sa.String(64), nullable=False, server_default="DIGITAL_EXPLAINER"),
        sa.Column("editorial_caveats", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ai_content_plans_tenant_id", "ai_content_plans", ["tenant_id"])
    op.create_index("ix_ai_content_plans_research_job_id", "ai_content_plans", ["research_job_id"])
    op.create_index("ix_ai_content_plans_story_id", "ai_content_plans", ["story_id"])

    # 6. ai_outputs (Immutable versioned assets with review state)
    op.create_table(
        "ai_outputs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_job_id", sa.String(36), sa.ForeignKey("research_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("output_type", sa.String(32), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("model_provider", sa.String(64), nullable=False, server_default="ollama"),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("prompt_template_version", sa.String(32), nullable=False, server_default="v1.0"),
        sa.Column("source_references", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="GENERATED"),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("actioned_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ai_outputs_tenant_id", "ai_outputs", ["tenant_id"])
    op.create_index("ix_ai_outputs_story_id", "ai_outputs", ["story_id"])
    op.create_index("ix_ai_outputs_research_job_id", "ai_outputs", ["research_job_id"])
    op.create_index("ix_ai_outputs_output_type", "ai_outputs", ["output_type"])
    op.create_index("ix_ai_outputs_status", "ai_outputs", ["status"])


def downgrade() -> None:
    op.drop_table("ai_outputs")
    op.drop_table("ai_content_plans")
    op.drop_table("research_briefs")
    op.drop_table("research_claims")
    op.drop_table("research_evidence")
    op.drop_table("research_jobs")
