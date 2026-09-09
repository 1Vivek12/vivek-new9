# Service Topology & Responsibilities

## 1. Overview

The platform is structured into clean service boundaries. Each service encapsulates a specific domain, communicates over well-defined internal interfaces, and manages its own lifecycle.

---

## 2. Service Definitions

### 2.1 API Service (FastAPI)
- **Role**: Primary entry point for HTTP clients (frontend, internal webhooks).
- **Responsibilities**:
  - Request authentication and tenant context resolution.
  - CRUD operations on tenants, users, projects, content, and audit events.
  - Ingestion of manual upload triggers and approval commands.
  - Serving health checks (`/health`, `/ready`).
- **Boundaries**: Stateless; does not execute long-running compute (video rendering or agent iterations) in the request loop.

### 2.2 Worker Service (Celery + Redis)
- **Role**: Asynchronous task processing and background scheduling.
- **Responsibilities**:
  - Long-running tasks: health checks, cache warming, audit log rotation.
  - Future tasks: audio transcription, AI batch generation, video segment encoding.
- **Isolation**: Each Celery task requires an explicit `tenant_id` parameter. Execution without valid tenant context is immediately aborted.

### 2.3 Agent Runtime Service Boundary
- **Role**: Host and orchestrator for autonomous and semi-autonomous AI agents.
- **Security Posture**: Internal-only service; never exposed to public internet.
- **Isolation Restrictions**:
  - Zero access to Docker socket (`/var/run/docker.sock`).
  - Zero access to host root filesystem or host shell execution.
  - Network-restricted egress to avoid data exfiltration.

### 2.4 Data Tier
- **PostgreSQL**: ACID-compliant persistent relational store for tenants, users, permissions, content metadata, and audit logs.
- **Redis**: High-speed in-memory broker for Celery queues and transient session/rate-limiting state.
- **Storage**: Local filesystem abstraction for Phase 1, architected for future S3/MinIO drop-in replacement.
