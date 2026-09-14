# News 9 AI Content & Newsroom Automation Platform

> **Status**: Phase 1–6 Complete & Production-Hardened
> **Target**: Scalable, brand-independent multi-tenant AI content, media production, and publishing automation platform.

---

## 1. Overview & Vision

News 9 is the **first tenant and flagship workspace** of an extensible, multi-tenant content automation engine. The underlying architecture is brand-independent and designed from day one to serve:

- News organizations and newsrooms
- YouTube channels and digital video creators
- Podcasters and audio producers
- Educators, agencies, and enterprise brands

The platform addresses two primary categories of automated content generation:
1. **Newsroom Automation**: Real-time topic monitoring, regional/national news updates, fast turnaround reporting, source reliability scoring, and editorial approval workflows.
2. **General Content & Video Automation**: Topic-to-content generation, raw video processing, transcript extraction, automated edit plans, shorts/reels generation, thumbnail generation, and multi-channel distribution.

---

## 2. Completed Implementation Phases (Phases 1–6)

### Phase 1: Multi-Tenant Production Foundation
- Cryptographic authentication & PBKDF2-HMAC-SHA256 password hashing.
- Strict `TenantContext` authorization derived from DB membership (zero trust in `X-Tenant-ID`).
- Local AI provider abstraction (Ollama/OpenAI compatible) and sandboxed runtime boundary.

### Phase 2: Editorial Content Core
- Assignment Desk, Story Lifecycle state machine with mandatory human approval gates.
- Append-only immutable `StoryVersion` snapshots and audit logging.

### Phase 3: Trend Radar & Source Monitoring
- SSRF-protected safe feed connectors (RSS 2.0 / Atom 1.0) with DNS rebinding and redirect hop validation.
- TF-IDF topic clustering, trend scoring, and content opportunity discovery.

### Phase 4: AI Research & Content Intelligence
- Prompt injection defense, untrusted source evidence quarantine, and delimiter neutralization.
- Structured AI claims extraction, evidence tracing, and content plan generation (no AI self-approval).

### Phase 5: Media & Video Production
- FFmpeg/FFprobe subprocess execution strictly via argument arrays without `shell=True`.
- Path traversal containment, media rights policies, subtitles, keyframe extraction, and scene analysis.
- Explicit tool availability enforcement (`TOOL_UNAVAILABLE` when binaries are missing; mocks test-only).

### Phase 6: Publishing & Distribution
- Multi-destination publishing: YouTube (Videos & Shorts), Facebook, Instagram, WhatsApp, and News 9 Website.
- Resumable video chunk upload to YouTube; two-step container flow for Instagram; token-bucket throttle for WhatsApp.
- AES-256-GCM Credential Vault with AAD tenant/account binding and fresh 96-bit nonces.
- Deterministic canonical manifest SHA-256 hashing; post-approval mutation invalidation.
- Human-in-the-loop approval ledger; elimination of fabricated IDs and fake example URLs.

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
