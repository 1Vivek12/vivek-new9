# System Architecture: News 9 AI Content & Newsroom Automation Platform

## 1. Architectural Philosophy

The platform is designed as a **modular monolith with explicit service boundaries**. While running as a unified codebase in Phase 1 to minimize operational complexity on lightweight VPS infrastructure, services are strictly decoupled through domain interfaces:

```text
                                  +---------------------------------------+
                                  |            Client Browser             |
                                  |        (React / Vite Frontend)        |
                                  +-------------------+-------------------+
                                                      |
                                             HTTPS / JSON APIs
                                                      |
                                                      v
+-----------------------------------------------------+-------------------------------------------------------+
|                                              FastAPI Backend                                                |
|                                                                                                             |
|   +-----------------------------------------------------------------------------------------------------+   |
|   |                                          Middleware Stack                                           |   |
|   |             Correlation ID  |  Structured Logging  |  Tenant Context & Auth Resolver                 |   |
|   +---------------------------------------------------+-------------------------------------------------+   |
|                                                       |                                                     |
|                     +---------------------------------+---------------------------------+                   |
|                     v                                 v                                 v                   |
|           +-------------------+             +-------------------+             +-------------------+         |
|           |   API Endpoints   |             | Service Registry  |             | Security / Auth   |         |
|           |  /api/v1/health   |             | (AI, Storage,     |             | (JWT, RBAC,       |         |
|           |  /api/v1/tenants  |             |  Publishing,      |             |  Tenant Guards)   |         |
|           |  /api/v1/audit    |             |  AgentRuntime)    |             +-------------------+         |
|           +---------+---------+             +---------+---------+                                           |
|                     |                                 |                                                     |
|                     v                                 v                                                     |
|           +-------------------+             +-------------------+                                           |
|           |   SQLAlchemy ORM  |             | Abstraction Layer |                                           |
|           |  (asyncpg driver) |             | AIProvider (Ollama|                                           |
|           +---------+---------+             | Storage (Local/S3)|                                           |
|                     |                       | AgentRuntime      |                                           |
|                     |                       +---------+---------+                                           |
+---------------------|---------------------------------|-----------------------------------------------------+
                      |                                 |
                      v                                 v
        +---------------------------+     +---------------------------+     +---------------------------+
        |        PostgreSQL         |     |       Redis 7 / Queue     |     |   Local Inference Host    |
        |  (Multi-tenant scoped DB) |     | (Task broker & cache)     |     |    (Ollama / Llama 3)     |
        +---------------------------+     +-------------+-------------+     +---------------------------+
                                                        |
                                                        v
                                          +---------------------------+
                                          |       Celery Worker       |
                                          | (Async background tasks)  |
                                          +---------------------------+
```

---

## 2. Core Architectural Invariants

1. **Multi-Tenancy by Default**: Every stateful entity (content, projects, media, audit logs) belongs to a `tenant_id`. No entity is orphan or global unless explicitly classified as system-wide platform metadata.
2. **Deterministic Publishing Guard**: Content generation and AI analysis cannot bypass human review. An explicit state machine enforces that no content can reach `PUBLISHED` state without an approved human sign-off recorded in the audit trail.
3. **Local Inference Priority**: The primary AI target is self-hosted Ollama (e.g., Llama 3, Mistral) or local OpenAI-compatible endpoints. Paid cloud APIs are treated as non-core, optional future plugins.
4. **Isolated Agent Execution**: AI agents run inside tightly bounded runtime adapters. AI agents have zero direct access to the host filesystem, Docker daemon socket, root privileges, or platform database credentials.
5. **Brand Agnostic Core**: The core business logic contains no references to "News 9". News 9 is provisioned as an initial tenant with its own branding configuration (logo, palette, typography, locale, editorial guidelines).
