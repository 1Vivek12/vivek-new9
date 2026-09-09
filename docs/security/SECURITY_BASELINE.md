# Security Baseline & Hardening Standards

## 1. Zero Secrets in Version Control

1. **Rule**: Under no circumstances may credentials, private keys, API tokens, database passwords, or secret salts be committed to Git.
2. **Implementation**:
   - `.env` files and certificates are strictly included in `.gitignore`.
   - `.env.example` contains only explicit, safe placeholders.
   - Pre-commit scanning and CI pipelines execute automated secret detection (e.g., regex pattern matching for keys, tokens, and passwords).

---

## 2. Principle of Least Privilege

1. **Database Privileges**: The application connects to PostgreSQL via a dedicated database user granted CRUD permissions only on application tables. Under no circumstances does the application use the `postgres` superuser in production.
2. **Container Security**:
   - All Docker images run as dedicated non-root users (`appuser` with UID `10001`).
   - Root filesystem is read-only where practical; writable areas are limited to designated storage paths or ephemeral `tmpfs`.
3. **Agent Runtime Lockdown**:
   - AI agent runtimes are explicitly forbidden from accessing:
     - The Docker socket (`/var/run/docker.sock`).
     - The host filesystem root.
     - SSH keys and system certificates.
     - Production environment secrets or database superuser credentials.

---

## 3. Tenant Isolation & Authorization Architecture

1. **Identity-Driven Context**: The client cannot declare its own tenant via headers alone. All requests resolve identity through cryptographic authentication (session/JWT) and confirm active membership in PostgreSQL.
2. **Cross-Tenant Prevention**: Any attempt by User A (belonging to Tenant 1) to access resources tagged with Tenant 2 is rejected at the backend service layer with HTTP 403 Forbidden.
3. **Storage Boundary**: Files are partitioned by `/data/storage/tenants/{tenant_id}/`. Storage providers enforce path traversal checks (`os.path.commonpath`) to prevent directory escape attacks.

---

## 4. Deterministic Publishing Safeguards

AI agents and automated pipelines must **never** possess direct publishing capabilities to public platforms (YouTube, Facebook, Instagram, websites).
- The publishing service enforces a strict state machine: `DRAFT -> AI_PROCESSING -> VALIDATION -> APPROVAL_REQUIRED -> APPROVED -> PUBLISHED`.
- A transition to `PUBLISHED` without a verified human approval signature raises an unrecoverable `UnapprovedContentPublicationError`.

---

## 5. Audit Logging Architecture

Every security-sensitive event is captured in an append-only `AuditLog` table with:
- `tenant_id` (mandatory, except for platform-wide events)
- `user_id` (or `SYSTEM_SERVICE`)
- `action` (e.g., `LOGIN_SUCCESS`, `TENANT_SWITCH`, `CONTENT_APPROVAL`, `AGENT_TASK_START`)
- `resource_type` & `resource_id`
- `ip_address` & correlation `request_id`
- `timestamp`
Audit logs cannot be updated or deleted through standard application endpoints.
