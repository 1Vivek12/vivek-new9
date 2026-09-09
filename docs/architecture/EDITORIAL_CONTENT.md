# Editorial Content Core Architecture

## Overview
The Editorial Content Core establishes the internal newsroom domain model for the multi-tenant AI Content & Newsroom Automation Platform. News 9 is seeded as the first tenant, but the domain model is strictly brand-independent and tenant-scoped.

Every editorial object contains a mandatory `tenant_id` foreign key referencing the tenant boundary.

## Domain Model
```
┌────────────────────────────────────────────────────────┐
│                        TENANT                          │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
               ▼                          ▼
       ┌───────────────┐          ┌───────────────┐
       │   CATEGORY    │          │  ASSIGNMENT   │
       └───────┬───────┘          └───────┬───────┘
               │                          │
               └───────────┬──────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │     STORY     │
                   └───────┬───────┘
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
     ┌───────────────┐           ┌───────────────┐
     │  STORY_SOURCE │           │ STORY_VERSION │
     └───────────────┘           └───────────────┘
```

### 1. Story (`stories` table)
Represents an editorial content opportunity.
- **Fields**:
  - `id`: UUID (Primary Key)
  - `tenant_id`: UUID (Foreign Key -> `tenants.id`, indexed)
  - `title`: String(255)
  - `slug`: String(255) (Indexed, unique per tenant)
  - `summary`: Text (Optional overview)
  - `category_id`: UUID (Foreign Key -> `categories.id`, optional)
  - `assignment_id`: UUID (Foreign Key -> `assignments.id`, optional)
  - `priority`: PriorityEnum (`LOW`, `MEDIUM`, `HIGH`, `URGENT`)
  - `status`: StoryStatusEnum (`IDEA`, `ASSIGNED`, `RESEARCHING`, `DRAFT`, `VALIDATION`, `APPROVAL_REQUIRED`, `APPROVED`, `PUBLISHED`, `REJECTED`, `ARCHIVED`)
  - `editorial_owner_id`: UUID (Foreign Key -> `users.id`, optional)
  - `created_by_user_id`: UUID (Foreign Key -> `users.id`, optional)
  - `approved_by_user_id`: UUID (Foreign Key -> `users.id`, optional)
  - `approved_at`: DateTime(timezone=True)
  - `rejection_reason`: Text (Mandatory if transitioning to `REJECTED`)
  - `created_at` / `updated_at`: DateTime(timezone=True)
- **Constraints**:
  - `UniqueConstraint("tenant_id", "slug")`
  - Indexed on `(tenant_id, status)` and `(tenant_id, updated_at)`

### 2. Story Lifecycle State Machine
Editorial progression is strictly deterministic. Arbitrary state jumps are rejected by `validate_transition()`:
- `IDEA` -> `ASSIGNED`, `RESEARCHING`, `DRAFT`, `ARCHIVED`
- `ASSIGNED` -> `RESEARCHING`, `DRAFT`, `ARCHIVED`
- `RESEARCHING` -> `DRAFT`, `ASSIGNED`, `ARCHIVED`
- `DRAFT` -> `VALIDATION`, `ARCHIVED`
- `VALIDATION` -> `APPROVAL_REQUIRED`, `DRAFT`, `REJECTED`, `ARCHIVED`
- `APPROVAL_REQUIRED` -> `APPROVED`, `REJECTED`, `DRAFT`
- `APPROVED` -> `PUBLISHED`, `DRAFT`, `ARCHIVED`
- `PUBLISHED` -> `ARCHIVED`
- `REJECTED` -> `DRAFT`, `ARCHIVED`
- `ARCHIVED` -> `DRAFT` (re-opening archive)

#### Publishing Guard Integration
- Direct transitions to `PUBLISHED` from unapproved states fail deterministically.
- `APPROVED` status records `approved_by_user_id` and timestamp.
- Phase 1 `MockPublishingBoundary` remains authoritative: actual external publishing integrations are deferred; approval only establishes editorial readiness.

### 3. Source / Reference Metadata (`story_sources` table)
Stores verifiable citation metadata without web crawling or scraping:
- **Fields**:
  - `id`: UUID (Primary Key)
  - `tenant_id`: UUID (Foreign Key -> `tenants.id`)
  - `story_id`: UUID (Foreign Key -> `stories.id`, CASCADE delete)
  - `title`: String(255)
  - `url`: String(2048) (Optional link)
  - `publisher_name`: String(255)
  - `source_type`: SourceTypeEnum (`OFFICIAL`, `GOVERNMENT`, `WIRE`, `PUBLICATION`, `SOCIAL`, `USER_PROVIDED`, `OTHER`)
  - `reliability_score`: Integer (0-100 confidence rating)
  - `rights_metadata`: String(500) (Licensing / rights disclosures)
  - `notes`: Text
  - `accessed_at` / `published_at`: DateTime(timezone=True)
- **Security Rule**: URLs are metadata strings only. The backend does NOT perform automated HTTP fetching or crawling in Phase 2.

### 4. Content Versioning Foundation (`story_versions` table)
Preserves immutable snapshots of editorial draft iterations:
- **Fields**:
  - `id`: UUID (Primary Key)
  - `tenant_id`: UUID (Foreign Key -> `tenants.id`)
  - `story_id`: UUID (Foreign Key -> `stories.id`, CASCADE delete)
  - `version_number`: Integer (Auto-incremented per story)
  - `headline`: String(255)
  - `body_payload`: Text (Content draft payload)
  - `change_summary`: String(500)
  - `created_by_user_id`: UUID (Foreign Key -> `users.id`, optional)
  - `created_at`: DateTime(timezone=True)
- **Immutability Invariant**: Versions are append-only. There is no `PATCH` or update endpoint for existing versions.
- **Constraints**:
  - `UniqueConstraint("story_id", "version_number")`

### 5. Categories (`categories` table)
Tenant-specific taxonomy for editorial content:
- **Fields**:
  - `id`: UUID (Primary Key)
  - `tenant_id`: UUID (Foreign Key -> `tenants.id`)
  - `name`: String(100)
  - `slug`: String(100)
  - `description`: Text
- **Constraints**:
  - `UniqueConstraint("tenant_id", "slug")`
- **Seeded News 9 Categories**:
  - `politics`, `gorakhpur-region`, `technology`, `economy`, `uttar-pradesh`, `india`, `world`.

## Deferred Capabilities
- Web scraping, competitor scraping, automated link unfurling.
- Collaborative real-time rich text editing.
- AI automated version generation or Prime Agent direct drafting.
- External social media or CMS publishing adapters.
