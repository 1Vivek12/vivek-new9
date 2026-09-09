# News 9 AI Content & Newsroom Automation Platform

> **Status**: Phase 2 Editorial Content Core (Verified in test suite)  
> **Target**: Scalable, brand-independent AI content and newsroom automation platform.

---

## 1. Overview & Vision

News 9 is the **first tenant and flagship workspace** of an extensible, multi-tenant content automation engine. The underlying architecture is brand-independent and designed from day one to serve:

- News organizations and newsrooms
- YouTube channels and digital video creators
- Podcasters and audio producers
- Educators, agencies, and enterprise brands

The platform addresses two primary categories of automated content generation:
1. **Newsroom Automation**: Real-time topic monitoring, regional/national news updates, fast turnaround reporting, source reliability scoring, and editorial approval workflows.
2. **General Content & Video Automation**: Topic-to-content generation, raw video processing, transcript extraction, automated edit plans, shorts/reels generation, thumbnail generation, and metadata publishing.

---

## 2. Phase 1 & Phase 2 Scope

### Phase 1 Deliverables (Multi-Tenant Production Foundation):
- **Tenant Isolation**: Backend-enforced authorization deriving tenant context from authenticated user identity and role membership. Rejection of forged headers and cross-tenant leakage.
- **Brand Independence**: Zero hardcoded business logic referencing "News 9". News 9 is seeded as the initial workspace with dynamic branding configuration.
- **AI Provider Abstraction**: Local inference-first design supporting Ollama and OpenAI-compatible endpoints with zero dependency on paid cloud AI APIs.
- **Agent Runtime Boundary**: `AgentRuntime` interface with `PrimeAgentRuntime` adapter marked as `PENDING_VERIFICATION` (non-executing, safe sandbox boundary).
- **Service Boundaries**: FastAPI backend, Celery + Redis worker queue, PostgreSQL persistence via asyncpg, and React frontend shell.

### Phase 2 Deliverables (Editorial Content Core):
- **Editorial Domain Models**: Tenant-scoped models for `Category`, `Assignment`, `Story`, `StorySource`, and `StoryVersion`.
- **Assignment Desk Foundation**: Work orders, priority tracking, due dates, and reporting delegator-assignee relationships.
- **Deterministic Editorial Lifecycle**: State machine with strict transition controls (`IDEA` &rarr; `ASSIGNED` &rarr; `RESEARCHING` &rarr; `DRAFT` &rarr; `VALIDATION` &rarr; `APPROVAL_REQUIRED` &rarr; `APPROVED` &rarr; `PUBLISHED`), mandatory rejection reasons, and human sign-off records.
- **Source & Citation Metadata**: Reliable source tracking, reliability confidence scores, and licensing rights metadata without web scraping or crawling.
- **Immutable Content Versioning**: Append-only draft snapshots capturing revisions, headlines, and change summaries.
- **Tenant Authorization & IDOR/BOLA Protection**: Rigorous backend isolation blocking unauthorized or cross-tenant reads and mutations.
- **Audit Logging**: Comprehensive tenant-isolated audit trail for all editorial actions.
- **Newsroom Frontend Workbench**: Dedicated UI components for the Assignment Desk, Story Management, Sources, Version History, and Lifecycle Actions.
- **Alembic Database Migrations**: Versioned database migrations for Phase 1 and Phase 2 models.

---

## 3. Directory Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Versioned HTTP endpoints (/health, /tenants, /audit, etc.)
│   │   ├── core/           # Configuration, logging, security, tenant context middleware
│   │   ├── db/             # SQLAlchemy async engine, models (Tenant, User, Membership, Audit)
│   │   ├── services/       # Abstraction layers (AIProvider, AgentRuntime, StorageProvider, Publishing)
│   │   └── worker/         # Celery instance, background task definitions
│   ├── tests/              # Pytest suite (health, isolation, security, config, agent safety)
│   └── pyproject.toml      # Pinned dependencies & metadata
├── frontend/
│   ├── src/                # React 18 shell, tenant context, health & status panels
│   ├── package.json        # Frontend dependencies
│   └── vite.config.ts      # Vite build configuration
├── docker/
│   ├── Dockerfile.backend  # Multi-stage non-root Python 3.12 container
│   └── Dockerfile.frontend # Multi-stage unprivileged Nginx container
├── docs/
│   ├── architecture/       # ARCHITECTURE, MULTI_TENANCY, SERVICES, AGENT_RUNTIME, TREND_RADAR
│   ├── security/           # SECURITY_BASELINE
│   ├── development/        # DEVELOPMENT_WORKFLOW
│   ├── testing/            # TESTING_STRATEGY
│   ├── decisions/          # ADR-0001-initial-architecture
│   └── licenses/           # DEPENDENCIES
├── docker-compose.yml      # Orchestration definition for local dev & VPS
├── .env.example            # Environment configuration template
└── README.md               # Platform documentation
```

---

## 4. Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+ & npm
- PostgreSQL 15+ (or Docker)
- Redis 7+ (or Docker)
- Ollama (for local inference testing)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\Activate.ps1
pip install -e .
cp ../.env.example .env
pytest -v tests
```

### Frontend Setup
```bash
cd frontend
npm install
npm run build
npm run dev
```

---

## 5. Non-Negotiable Rules Adherence
1. **No n8n**: All automation pipelines are built as typed Python services.
2. **No Paid AI Dependency**: Ollama and local OpenAI-compatible endpoints are the primary targets.
3. **Strict Human Approval**: Content publication requires verified human approval (`UnapprovedContentPublicationError` guard).
4. **Tenant Security**: All data access is authorized via authenticated tenant membership.
