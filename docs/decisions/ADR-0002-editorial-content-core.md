# ADR-0002: Editorial Content Core Architecture

## Status
Accepted

## Context
Following the completion of Phase 1 (Multi-Tenant Production Foundation), Phase 2 requires establishing the internal newsroom core for managing stories, assignments, categories, reference sources, content versions, and editorial lifecycles.
News 9 is the first seeded tenant, but the architecture must remain brand-independent for future tenants (creators, agencies, podcasters, media companies).

## Decisions
1. **Domain Model Entity Structure**:
   - Implemented 5 tenant-scoped relational models: `Category`, `Assignment`, `Story`, `StorySource`, and `StoryVersion`.
   - All models enforce foreign key relationships to `tenants.id`.
   - `Story` connects optionally to `Category` and `Assignment`.
   - `StorySource` and `StoryVersion` enforce `CASCADE` deletion with `Story`.
2. **Deterministic Lifecycle State Machine**:
   - Replaced ad-hoc status mutation with a deterministic transition matrix (`validate_transition`).
   - Defined states: `IDEA`, `ASSIGNED`, `RESEARCHING`, `DRAFT`, `VALIDATION`, `APPROVAL_REQUIRED`, `APPROVED`, `PUBLISHED`, `REJECTED`, `ARCHIVED`.
   - Moving to `APPROVED` requires `approved_by_user_id` and records `approved_at`.
   - Transitioning to `REJECTED` strictly mandates a non-empty `rejection_reason`.
   - Publishing integration remains locked behind human editorial approval.
3. **Reference Sources Without Web Crawling**:
   - `StorySource` persists structured citation metadata (publisher, type, confidence score, licensing/rights notes).
   - No automated URL crawling, scraping, or external content fetching is implemented.
4. **Immutable Content Versioning**:
   - `StoryVersion` records version numbers, headlines, body payload snapshots, and change summaries.
   - Snapshots are immutable (append-only) to preserve complete auditability of editorial draft evolution.
5. **Authorization & IDOR / BOLA Prevention**:
   - Reused Phase 1 `TenantContext` dependency.
   - Resource access unconditionally filters by `(id, tenant_id)`.
   - Cross-tenant requests return 404 (or 403), preventing data leaks or unauthorized updates.
6. **Audit Trail**:
   - Emitted tenant-isolated `AuditEvent` records for all editorial mutations.

## Consequences
- **Positive**: Clean, audit-ready newsroom foundation; robust IDOR/BOLA security; reliable state transitions; complete multi-tenant isolation.
- **Negative / Trade-offs**: In this phase, external CMS/social integrations, collaborative concurrent editing, and AI research agents remain intentionally deferred.
