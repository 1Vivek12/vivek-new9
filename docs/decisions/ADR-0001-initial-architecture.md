# ADR-0001: Initial Architecture & Technology Stack Selection

## Status
Accepted (Phase 1)

## Context
The platform requires a multi-tenant, brand-independent foundation capable of automating digital newsrooms and general content creation. The initial deployment environment is constrained (modest, potentially CPU-only VPS), rules out paid AI API lock-in, and demands strict tenant data isolation.

## Decisions

1. **Backend Framework: FastAPI (Python 3.12)**
   - *Rationale*: High performance, native async support, first-class type safety via Pydantic v2, and clean dependency injection for tenant resolution.
2. **Database & Driver: PostgreSQL with SQLAlchemy 2.0 & asyncpg**
   - *Rationale*: `asyncpg` is the fastest async PostgreSQL driver in Python. Redundant sync/compiled drivers (`psycopg2-binary`) are avoided to keep dependencies minimal and prevent build issues.
3. **Queue & Async Processing: Celery + Redis**
   - *Rationale*: Mature, rock-solid ecosystem for background task execution, retries, and scheduled jobs.
4. **Local AI Inference: Ollama Provider Abstraction**
   - *Rationale*: Allows self-hosted LLMs (Llama 3, Mistral) on CPU/GPU without recurring API charges. The `AIProvider` abstraction permits local OpenAI-compatible endpoints as well.
5. **Agent Orchestration: Isolated AgentRuntime Interface**
   - *Rationale*: Prime Agent is isolated behind an `AgentRuntime` interface and marked `PENDING_VERIFICATION`. It remains non-executing in Phase 1 to prevent unauthorized shell or host filesystem access.
6. **Frontend: React + Vite + TypeScript (Foundation Only)**
   - *Rationale*: Fast development, type safety, low overhead. Elaborate design is deferred to future phases.

## Consequences
- **Positive**: Low memory footprint (~350MB idle), zero vendor lock-in, strict tenant boundaries, high maintainability.
- **Negative**: Self-hosted LLM inference on CPU-only VPS has higher latency than cloud APIs; however, this matches the explicit requirement for local inference.
