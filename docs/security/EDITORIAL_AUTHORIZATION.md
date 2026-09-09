# Editorial Content Authorization & Security Specification

## Security Principles
1. **Authenticated Context as Authority**: The authenticated user session (`UserSession`) and verified tenant membership (`TenantContext`) dictate access permissions.
2. **Zero Trust for Client-Supplied Identifiers**: `tenant_id` provided in request bodies, path parameters, query parameters, or forged `X-Tenant-ID` headers is never trusted as an authorization override.
3. **Defense Against IDOR / BOLA**: In every endpoint, queries explicitly filter by `Model.id == resource_id` AND `Model.tenant_id == context.tenant_id`. Accessing a resource belonging to another tenant yields `404 Not Found` (to avoid leaking resource existence) or `403 Forbidden`.

## Role-Based Permissions Matrix (Phase 2)
The permission framework maps tenant roles (`OWNER`, `ADMIN`, `EDITOR`, `REPORTER`, `VIEWER`) to fine-grained editorial permissions:

| Permission | OWNER | ADMIN | EDITOR | REPORTER | VIEWER |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `editorial:view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `editorial:create` | ✓ | ✓ | ✓ | ✓ | ✗ |
| `editorial:edit` | ✓ | ✓ | ✓ | ✓ | ✗ |
| `editorial:request_approval` | ✓ | ✓ | ✓ | ✓ | ✗ |
| `editorial:approve` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `editorial:publish` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `assignment:view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `assignment:create` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `assignment:edit` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `category:view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `category:manage` | ✓ | ✓ | ✗ | ✗ | ✗ |

## BOLA / IDOR Defense Verification
The test suite in `tests/test_editorial_authorization.py` explicitly tests and proves:
- Authenticated user in Tenant A cannot read Story in Tenant B (`404 Not Found`).
- Authenticated user in Tenant A cannot update Story status in Tenant B (`404 Not Found`).
- Authenticated user in Tenant A cannot inject `tenant_id` of Tenant B in request body.
- Authenticated user in Tenant A cannot bypass tenant isolation via forged `X-Tenant-ID` header.
- Cross-tenant category uniqueness constraints prevent collisions across workspaces.
- Version snapshots cannot be forged or accessed cross-tenant.

## Audit Trail Invariant
Every significant editorial state modification emits a tenant-isolated audit log (`AuditEvent`):
- `ASSIGNMENT_CREATED`
- `ASSIGNMENT_ASSIGNED`
- `STORY_CREATED`
- `STORY_UPDATED`
- `STORY_STATUS_CHANGED`
- `SOURCE_ADDED`
- `VERSION_CREATED`
- `APPROVAL_REQUESTED`
- `CONTENT_APPROVED`
- `CONTENT_REJECTED`

Each event records `tenant_id`, `user_id`, `action`, `resource_type`, `resource_id`, and `details` payload.
