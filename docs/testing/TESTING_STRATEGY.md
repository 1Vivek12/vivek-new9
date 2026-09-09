# Testing Strategy & Quality Assurance Plan

## 1. Test Levels & Objectives

The testing pyramid ensures production robustness across unit, integration, and security layers:

```text
               / \
              /   \
             / E2E \       <-- Future Phase
            /-------\
           / Service \     <-- Integration & Security Isolation
          /-----------\
         /    Unit     \   <-- Fast, In-Memory Component Tests
        /---------------\
```

---

## 2. Test Suites (Phase 1)

### 2.1 Tenant Security & Cross-Tenant Isolation Tests (`test_tenant_isolation.py`)
- **Case 1**: Authenticated user accessing their own authorized tenant (`200 OK`).
- **Case 2**: Authenticated user attempting to access a tenant where they have no membership (`403 Forbidden`).
- **Case 3**: Platform admin accessing tenant with elevated oversight (`200 OK` + audit log entry).
- **Case 4**: Unauthenticated request / missing tenant context (`401 Unauthorized`).
- **Case 5**: Forged `X-Tenant-ID` header where user is not a member (`403 Forbidden`).
- **Case 6**: Tenant membership mismatch (valid user, valid tenant, but no relation) (`403 Forbidden`).
- **Case 7**: Cross-tenant data isolation (queries strictly return only current tenant rows).

### 2.2 Health & Readiness Tests (`test_health.py`)
- Liveness check (`GET /health`) verifies service is accepting HTTP traffic.
- Readiness check (`GET /ready`) verifies database connectivity and Redis broker responsiveness.

### 2.3 Configuration & Failure Mode Tests (`test_config.py`)
- Missing essential environment variables raise clean, typed Pydantic validation errors.
- Unreachable database or Redis produces graceful HTTP 503 degraded status instead of unhandled exceptions.

### 2.4 Agent Runtime Safety Tests (`test_agent_runtime.py`)
- `PrimeAgentRuntime` raises `NotImplementedError` on task execution attempts.
- Verifies absence of arbitrary shell execution methods.

### 2.5 Storage Boundary Tests (`test_storage.py`)
- File uploads are constrained to `/data/storage/tenants/{tenant_id}/`.
- Directory traversal attacks (`../../etc/passwd` or `../../other_tenant`) are caught and raise `PermissionError` / `ValueError`.

### 2.6 Publishing Approval Guard Tests (`test_publishing_guard.py`)
- Verifies that invoking `publish_content()` without prior human approval raises `UnapprovedContentPublicationError`.
