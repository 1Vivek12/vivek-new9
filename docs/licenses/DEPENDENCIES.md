# Dependency License & Justification Audit

Every dependency in the platform has been evaluated according to necessity, licensing, maintenance activity, and security implications:

## Backend Dependencies

| Package | Version Pin | License | Maintenance | Security Implications | Justification for Phase 1 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **fastapi** | `>=0.115.0,<0.116.0` | MIT | Highly Active | Standard ASGI web framework, strict validation | Core REST API layer and dependency injection. |
| **uvicorn** | `>=0.34.0,<0.35.0` | BSD-3-Clause | Highly Active | Standard ASGI server | Web server to run FastAPI. |
| **pydantic** | `>=2.10.0,<2.11.0` | MIT | Highly Active | Rust-based input validation, zero-copy parsing | Validates all requests, responses, and tenant inputs. |
| **pydantic-settings** | `>=2.7.0,<2.8.0` | MIT | Highly Active | Environment parsing with strict types | Enforces typed configuration and prevents unset secrets. |
| **sqlalchemy** | `>=2.0.36,<2.1.0` | MIT | Highly Active | Parameterized SQL prevents SQL injection | Core ORM for tenant-scoped database modeling. |
| **asyncpg** | `>=0.30.0,<0.31.0` | Apache-2.0 | Active | Pure async protocol, high performance | Sole PostgreSQL driver for async database access. |
| **alembic** | `>=1.14.0,<1.15.0` | MIT | Highly Active | Schema versioning and migration safety | Version-controlled database schema management. |
| **redis** | `>=5.2.0,<5.3.0` | MIT | Highly Active | Standard async Redis client | Broker communication for task queues and caching. |
| **celery** | `>=5.4.0,<5.5.0` | BSD-3-Clause | Active | Robust distributed task execution | Background task orchestration and queue management. |
| **httpx** | `>=0.28.0,<0.29.0` | BSD-3-Clause | Highly Active | Modern async HTTP client | Communicates with local Ollama inference service. |
| **pytest** | `>=8.3.0,<8.4.0` | MIT | Highly Active | Dev/Test framework | Required to run and verify the test suite. |
| **pytest-asyncio** | `>=0.25.0,<0.26.0` | Apache-2.0 | Highly Active | Dev/Test async support | Required to test async FastAPI endpoints and DB queries. |
| **ruff** | `>=0.8.0,<0.9.0` | MIT / Apache-2.0 | Extremely Active | Rust-based linter and formatter | Enforces clean, PEP-compliant, secure Python code. |
| **mypy** | `>=1.13.0,<1.14.0` | MIT | Highly Active | Static typing checker | Verifies type consistency across all modules. |

## Frontend Dependencies

| Package | Version Pin | License | Maintenance | Security Implications | Justification for Phase 1 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **react** | `^18.3.1` | MIT | Industry Standard | XSS escaping by default | Core UI component library. |
| **react-dom** | `^18.3.1` | MIT | Industry Standard | DOM rendering | Mounts React components to the DOM. |
| **lucide-react** | `^0.475.0` | ISC | Active | Pure SVG icons | Minimal clean status icons for health and dashboard. |
| **vite** | `^6.0.0` | MIT | Highly Active | Development server and bundler | Fast production build tooling. |
| **typescript** | `^5.6.0` | Apache-2.0 | Microsoft Standard | Build-time type safety | Enforces type checks across frontend codebase. |

*Zero unvetted or GPL/AGPL dependencies are included in the codebase.*
