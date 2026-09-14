# Phase 6 — Publishing & Distribution Architecture

## 1. System Overview

The **Publishing & Distribution Subsystem** provides a secure, multi-tenant editorial syndication and broadcast engine for the News 9 AI Content & Newsroom Automation Platform. It connects vetted news stories and media packages with third-party social media networks, messaging broadcasts, and internal content management systems.

### Target Destinations
- **YouTube**: Resumable video uploads, YouTube Shorts formatting, thumbnail attachment, News & Politics categorization.
- **Facebook**: Meta Graph API Page posts, captions, and videos.
- **Instagram**: Two-step media container publishing, Reels formatting, caption limits, and secure media ingestion.
- **WhatsApp**: Meta Cloud API recipient broadcast, 20 msg/sec token-bucket throttle, international E.164 compliance.
- **News 9 Website**: Phase 2 Story lifecycle transition to `EditorialState.PUBLISHED` and canonical web URL generation.

---

## 2. Core Architectural Invariants

```
                                    +-----------------------------------------+
                                    |         Phase 2 / Phase 5 Story         |
                                    +-----------------------------------------+
                                                         |
                                                         v
                                    +-----------------------------------------+
                                    |       PublishingPackage (DRAFT)         |
                                    |    - Canonical Title & Description      |
                                    |    - Media Assets & Rights Metadata     |
                                    +-----------------------------------------+
                                                         |
                              +--------------------------+--------------------------+
                              |                          |                          |
                              v                          v                          v
                     PlatformPayload            PlatformPayload            PlatformPayload
                        (YouTube)                  (Instagram)                (WhatsApp)
                              |                          |                          |
                              +--------------------------+--------------------------+
                                                         |
                                                         v
                                    +-----------------------------------------+
                                    |      Deterministic Manifest & Hash      |
                                    |       SHA-256(canonical_json)           |
                                    +-----------------------------------------+
                                                         |
                                                         v
                                    +-----------------------------------------+
                                    |   Mandatory Human Editorial Approval    |
                                    |      (PublishingApprovalEvent)          |
                                    +-----------------------------------------+
                                                         |
                                                         v
                                    +-----------------------------------------+
                                    |     Pre-Flight Dispatch Reverification  |
                                    |   Recomputed Hash == Approved Hash?     |
                                    +-----------------------------------------+
                                                         |
                                                         v
                                    +-----------------------------------------+
                                    |   PublishingJob & PublishingAttempts    |
                                    |  - Stable publication_idempotency_key   |
                                    |  - Rate-limited dispatch (TokenBucket)  |
                                    +-----------------------------------------+
                                                         |
                                                         v
                                    +-----------------------------------------+
                                    |      PublishedItem (Permanent Audit)    |
                                    |       external_id & canonical_url       |
                                    +-----------------------------------------+
```

### 1. Deterministic Publication Manifest & SHA-256 Invariant
Every publishing package generates a canonical UTF-8 JSON publication manifest covering:
- Tenant ID & Package ID
- Linked Story ID & Version ID
- Canonical Title, Description, and Caption
- Tags (sorted)
- Media Assets (sorted by ID with SHA-256 checksums and storage paths)
- Platform Payloads (sorted by destination type and account ID)

Any modification to content, media, or adaptations invalidates the cryptographic hash.

### 2. Append-Only Human Approval Ledger
- **Strict Prohibition of Autonomous AI Self-Approval**: Approvals must be executed by authenticated human editors (`user_id`).
- All decisions (`APPROVED`, `REJECTED`, `INVALIDATED`) are appended to the immutable `PublishingApprovalEvent` ledger.
- **Approval Invalidation on Mutation**: Modifying any platform adaptation or package field automatically resets package status to `DRAFT`, clears `current_approval_id`, and appends an `INVALIDATED` event to the ledger.

### 3. Pre-Flight Dispatch-Time Reverification
Prior to outbound network requests, the system recomputes the live manifest from current database entities and verifies:
$$\text{Recomputed Live Hash} \equiv \text{Approved Manifest Hash}$$
If any tampering, stale edit, or missing approval is detected, the dispatch aborts with `ManifestTamperedError`.

### 4. AES-256-GCM Authenticated Credential Vault
- Encrypts access tokens and refresh tokens using authenticated AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
- Fresh 96-bit random nonce (`os.urandom(12)`) per encryption.
- Authenticated Additional Data (AAD) bound to `tenant_id:account_id:key_version`.
- Cross-tenant tampering or context modification results in immediate authentication tag verification failure (`VaultDecryptionError`).

### 5. Controlled Resurrection of Connected Accounts
- Soft-deleted connected accounts (`is_deleted=True`) preserve historical audit logs and published items.
- When an account is reconnected, the existing record is resurrected and updated rather than creating duplicate rows or violating the `uq_connected_account_identity` unique constraint.

### 6. External Media Delivery Bridge (Instagram Ingestion)
- Provides secure, time-limited download URLs for Instagram Graph API video ingestion (`/api/v1/publishing/delivery/{token}`).
- Signed with HMAC-SHA256 and expires strictly after 15 minutes.
- Strict path containment checks verify that files are contained within `STORAGE_ROOT` and prohibit directory traversal attacks (`../`).
- Verifies server-side media rights clearance before serving.

### 7. Application Safety Limits & Token-Bucket Rate Limiter
- **WhatsApp**: Token-bucket throttle enforcing `WHATSAPP_MESSAGES_PER_SECOND_LIMIT = 20`.
- **YouTube Shorts**: Newsroom editorial ceiling of 180 seconds.
- **Instagram Reels**: Newsroom editorial ceiling of 90 seconds.
- **Meta Webhooks**: Verified via `X-Hub-Signature-256` and deduplicated on `UNIQUE(destination_type, external_event_id)`.
