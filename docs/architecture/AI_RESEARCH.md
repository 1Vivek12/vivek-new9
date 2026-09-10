# Architecture Specification — Phase 4: AI Research & Content Intelligence

## 1. Executive Summary

Phase 4 introduces local, evidence-backed AI research and editorial synthesis into the Multi-Tenant AI Content & Newsroom Automation Platform.

Operating within the News 9 workspace, the subsystem ingests verified story sources, enforces copyright and fair-dealing boundaries, executes fact and context synthesis via local Ollama models (with deterministic structured fallbacks), generates multimodal advisory assets, and enforces an uncompromised human editorial review gate.

---

## 2. Architectural Principles

1. **Passive Untrusted Data Model**:
   External content is treated as untrusted data. External text cannot execute functions, alter workflow states, or gain credential access.
2. **Strict Copyright Boundary**:
   The system never stores complete copyrighted competitor articles or full source web pages. Direct quote snippets are strictly capped at maximum 750 characters; claim summaries are capped at maximum 500 characters. Canonical URLs, publisher attribution, and rights metadata (`reuse_permitted: false`) are preserved.
3. **Mandatory Human Editorial Gate**:
   All AI-generated content defaults to status `GENERATED` / `REVIEW_REQUIRED`. AI has zero authority to approve or publish content. Acceptance or rejection requires human editor intervention. Rejections mandate an explicit reason.
4. **Tenant Isolation**:
   Every research job, evidence record, claim, brief, and AI output is strictly partitioned by `tenant_id` with foreign key CASCADE and tenant context verification.
5. **Deterministic Resilience**:
   If local inference engines are unreachable or output malformed data, deterministic newsroom extractors fulfill the pipeline without blocking journalists or corrupting database state.

---

## 3. Data Model Hierarchy

```
Story (Editorial Core)
  │
  ├── ResearchJob (Orchestrator)
  │     ├── ResearchEvidence (Capped Snippet ≤750 chars, Claim Summary ≤500 chars)
  │     ├── ResearchClaim (FACT, STATISTIC, QUOTE, ATTRIBUTION; SUPPORTED / CONFLICTING)
  │     ├── ResearchBrief (5W1H Journalistic Synthesis)
  │     └── AIContentPlan (Editorial Angles & Narrative Structure)
  │
  └── AIOutput (Immutable Versioned Asset)
        ├── output_type: HEADLINE, SCRIPT, SEO, VISUAL_PLAN, CONTENT_PLAN
        ├── version_number: 1, 2, 3... (Append-only)
        ├── status: GENERATED, ACCEPTED, REJECTED, EDITED
        └── review_metadata: actioned_by_user_id, rejection_reason
```

---

## 4. API Endpoints

- `POST /api/v1/stories/{id}/research`: Initiate research job
- `GET /api/v1/stories/{id}/research`: List research jobs
- `GET /api/v1/research/{id}/evidence`: List bounded evidence items
- `GET /api/v1/research/{id}/claims`: List verified claims matrix
- `GET /api/v1/research/{id}/brief`: Retrieve 5W1H structured brief
- `POST /api/v1/stories/{id}/content-plan`: Generate content plan
- `POST /api/v1/stories/{id}/headlines`: Generate headline variants
- `POST /api/v1/stories/{id}/script`: Generate broadcast news script
- `POST /api/v1/stories/{id}/seo`: Generate search engine metadata
- `POST /api/v1/stories/{id}/visual-plan`: Generate textual visual cue plan
- `POST /api/v1/ai-outputs/{id}/accept`: Human accept
- `POST /api/v1/ai-outputs/{id}/reject`: Human reject with mandatory reason
- `POST /api/v1/ai-outputs/{id}/edit`: Human revision
