# ADR-0006: Multi-Tenant Publishing & Distribution Architecture

## Status
Accepted

## Context
Phase 6 introduces multi-channel publishing and syndication to external platforms (YouTube, Facebook, Instagram, WhatsApp) and internal websites (News 9 Web). The system must operate under multi-tenant isolation, safeguard third-party platform credentials, enforce mandatory human editorial approval, and guarantee cryptographic immutability of broadcast packages.

## Decisions

### 1. Authenticated Credential Encryption via AES-256-GCM
- **Decision**: Use `AESGCM` from Python's standard `cryptography` library with 256-bit keys and fresh 96-bit random nonces per encryption.
- **AAD Context Binding**: Additional Authenticated Data is bound to `f"{tenant_id}:{account_id}:{key_version}"`.
- **Key Rotation**: Model supports key versions, enabling rolling credential re-encryption without downtime.
- **Fail-Fast**: Production environments strictly require `PUBLISHING_ENCRYPTION_KEY` to be set at startup; fallback to derived key is only allowed in development/testing with explicit warnings.

### 2. Ephemeral Server-Side OAuthState with PKCE
- **Decision**: Eliminate browser-provided tenant identities during OAuth callback.
- **State Storage**: The server persists single-use `OAuthState` records keyed by cryptographically secure random tokens with a 10-minute expiration window.
- **PKCE**: Stores `code_verifier` server-side and submits it with authorization code during token exchange.

### 3. Canonical Publication Manifest & SHA-256 Hash
- **Decision**: Prior to approval, all package attributes, media asset checksums, and platform adaptations are serialized into deterministic, key-sorted canonical JSON.
- **Immutable Binding**: The computed SHA-256 hash is stored on the package and recorded in the approval event.
- **Approval Invalidation**: Any post-approval mutation resets package status to `DRAFT` and clears `current_approval_id`.

### 4. Append-Only PublishingApprovalEvent Ledger
- **Decision**: Prevent `UPDATE` or `DELETE` on approval records.
- **Human Gate**: Approvals must come from an authenticated human user ID; autonomous AI bots are strictly rejected.
- **Audit Trail**: Every approval, rejection, and automatic invalidation creates an immutable ledger entry with full snapshot and timestamp.

### 5. Pre-Flight Dispatch-Time Reverification
- **Decision**: When a publishing job is triggered, the worker recalculates the live manifest hash from database entities and verifies it against the approved manifest hash before initiating external API requests.

### 6. Controlled Resurrection of Soft-Deleted Accounts
- **Decision**: Avoid unique constraint violations on `(tenant_id, destination_id, platform_account_id)` by restoring soft-deleted accounts (`is_deleted = False`) upon re-connection rather than attempting duplicate inserts.

### 7. External Media Delivery Bridge for Instagram
- **Decision**: Provide time-limited (15-min TTL) HMAC-SHA256 signed URLs for Instagram container ingestion. Enforce path containment within `STORAGE_ROOT` and verify media rights clearance before serving files.

## Consequences
- Complete defense against unauthorized or AI-hallucinated broadcast releases.
- Strong cryptographic guarantees against credential leakage and cross-tenant tampering.
- Seamless recovery from disconnected social accounts without database constraint failures.
