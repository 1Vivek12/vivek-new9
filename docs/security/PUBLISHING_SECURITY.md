# Publishing & Distribution Security Architecture

## 1. Threat Modeling & Defense Strategies

| Threat | Impact | Implemented Mitigation |
| :--- | :--- | :--- |
| **Credential Exfiltration** | Unauthorized access to newsroom YouTube/Meta accounts | AES-256-GCM envelope encryption with unique nonces, tenant/account AAD binding, plaintext tokens transient in memory only, redacted in logs and APIs. |
| **Cross-Tenant Credential Decryption** | Tenant A attempts to use Tenant B's credentials | AAD binding `f"{tenant_id}:{account_id}:{key_version}"` causes `InvalidTag` on cross-tenant decrypt attempts. |
| **Autonomous AI Self-Publishing** | AI agents releasing hallucinated or unverified news | Mandatory human editorial approval gate (`PublishingApprovalEvent`); bot/AI user IDs rejected from approval endpoints. |
| **Stale / Mutated Content Release** | Editor approves package; attacker/bug alters payload prior to dispatch | Pre-flight dispatch-time manifest re-verification. Recomputed live hash must match approved hash; any mutation resets status to `DRAFT`. |
| **Instagram Media Traversal Attack** | Malicious delivery token points to arbitrary host files | HMAC-SHA256 signature verification, 15-minute TTL, strict path containment within `STORAGE_ROOT`, and server-side rights validation. |
| **OAuth CSRF & State Hijacking** | Forged redirect attaches attacker's account to victim tenant | Ephemeral server-side `OAuthState` with PKCE `code_verifier`, 10-minute expiration, and single-use consumption. |
| **Webhook Replay / Spoofing** | Forged delivery statuses or false publishing confirmations | `X-Hub-Signature-256` HMAC validation against `META_APP_SECRET` and deduplication on `UNIQUE(destination_type, external_event_id)`. |
| **Broadcast Spam / Rate Abuse** | Exceeding WhatsApp Cloud API or YouTube quotas | Outbound token-bucket rate limiter enforcing `WHATSAPP_MESSAGES_PER_SECOND_LIMIT = 20` and Meta call caps. |

---

## 2. Cryptographic Specifications

### AES-256-GCM Credential Vault
- **Primitive**: Authenticated Encryption with Associated Data (AEAD) via AESGCM.
- **Key Length**: 256 bits (32 bytes).
- **Nonce**: 96-bit cryptographically secure pseudorandom bytes (`os.urandom(12)`).
- **AAD Structure**:
  $$\text{AAD} = \text{UTF-8}(\text{tenant\_id} \mathbin{\Vert} \text{account\_id} \mathbin{\Vert} \text{key\_version})$$
- **Production Guard**: In `production` environment, the absence of `PUBLISHING_ENCRYPTION_KEY` triggers immediate process exit.

### Canonical Publication Manifest
- Canonical JSON serialization: `json.dumps(manifest_dict, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`.
- Hash algorithm: SHA-256 computed over raw UTF-8 bytes.

### External Media Delivery Bridge
- **URL Pattern**: `/api/v1/publishing/delivery/{token}`
- **Token Payload**:
  $$\text{payload} = \{\text{tid}: \text{tenant\_id}, \text{aid}: \text{asset\_id}, \text{sp}: \text{storage\_path}, \text{exp}: \text{timestamp}\}$$
- **Signature**: $\text{HMAC-SHA256}(\text{SECRET\_KEY}, \text{payload})$
- **Time-to-Live**: 900 seconds (15 minutes).
