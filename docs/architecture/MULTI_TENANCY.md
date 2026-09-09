# Multi-Tenancy Architecture & Isolation Strategy

## 1. Multi-Tenant Philosophy

Multi-tenancy is the foundational architectural pillar of the platform. News 9 is merely the first client workspace. The platform must safely host multiple competing news organizations, creators, and commercial clients on shared infrastructure with cryptographic and logical separation.

---

## 2. Tenant Context Resolution & Security Guarantees

### 2.1 Authenticated Derivation (Crucial Security Invariant)
Tenant access is **never** authorized based on unverified headers such as `X-Tenant-ID`. The security boundary operates as follows:

1. **Identity Extraction**: The client presents an authenticated session or Bearer JWT.
2. **User & Membership Lookup**: The backend decodes the authenticated `user_id` and queries the `tenant_memberships` table in PostgreSQL.
3. **Authorized Tenant Set**: The system retrieves all tenants where the user has active membership, along with their role (e.g., `TENANT_OWNER`, `EDITOR`, `REPORTER`).
4. **Context Selection**:
   - If the user belongs to exactly one tenant, that tenant is automatically established as the active `TenantContext`.
   - If the user belongs to multiple tenants, the client may supply an `X-Tenant-ID` header as a selection hint.
   - **Crucial**: The backend verifies that the requested `tenant_id` is present in the user's authorized memberships. If not, the request is immediately aborted with **HTTP 403 Forbidden**.
   - If a client supplies a forged `X-Tenant-ID` for a tenant they do not belong to, it is rejected at the middleware/service boundary.
5. **Platform Admin Override**: Platform administrators with `is_platform_admin=True` may access tenant data for maintenance, but every cross-tenant access is explicitly flagged and recorded in the audit log with administrative rationale.

---

## 3. Data Isolation Mechanisms

### 3.1 Database Isolation (Row-Level Scoping)
Every business table contains a foreign key `tenant_id REFERENCES tenants(id)`:
```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    ...
);
CREATE INDEX idx_projects_tenant ON projects(tenant_id);
```
All service queries must inject the authenticated `TenantContext.tenant_id`:
```python
stmt = select(Project).where(
    Project.tenant_id == tenant_context.tenant_id,
    Project.id == project_id
)
```
Any query without an explicit tenant scope is considered a critical security vulnerability.

### 3.2 Storage Isolation
Storage is organized strictly by tenant root paths:
```text
/data/storage/
├── tenants/
│   ├── a1b2c3d4-tenant-news9/
│   │   ├── raw_media/
│   │   ├── rendered/
│   │   └── exports/
│   └── e5f6g7h8-tenant-client2/
│       ├── raw_media/
│       └── ...
```
The `LocalStorageProvider` enforces path containment checks (`os.path.commonpath`) to prevent path traversal (`../../`) between tenant buckets.

### 3.3 AI Memory & Agent Isolation
AI agents operating on behalf of Tenant A must never access knowledge or memories belonging to Tenant B:
- **Tenant Scope**: Brand voice, vocabulary, local guidelines, and historical facts.
- **Project Scope**: Ephemeral working notes and scripts.
- Memory stores (including future vector databases) must incorporate hard tenant namespace partitioning: `collection = f"tenant_{tenant_id}"`.

### 3.4 Publishing Credentials Isolation
Social media OAuth tokens (YouTube, Facebook, Instagram) are stored encrypted at rest using tenant-specific derived encryption keys. No global key can decrypt all tenant credentials simultaneously.

---

## 4. Brand Independence (News 9 Implementation)

News 9 is not the platform. It is represented as a tenant row in PostgreSQL:
```json
{
  "slug": "news9",
  "name": "News 9",
  "brand_config": {
    "primary_color": "#E50914",
    "secondary_color": "#1A1A1A",
    "logo_url": "/assets/news9-logo.png",
    "locale": "en-IN",
    "timezone": "Asia/Kolkata",
    "editorial_tone": "Authoritative, fast-paced, verified"
  }
}
```
All tenant-specific logic references `tenant.brand_config`, allowing seamless onboarding of new creators and media houses.
