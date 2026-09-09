# Trend Radar Security & SSRF Defense Specification

## Threat Model & Attack Surface

The introduction of external feed ingestion creates specific security considerations:
1. **Server-Side Request Forgery (SSRF)**: Malicious or manipulated feed URLs attempting to probe internal infrastructure (cloud metadata services, internal databases, local loopbacks).
2. **Denial-of-Service via Oversized Feeds**: Massive XML files or decompression bombs exhausting server memory.
3. **XML External Entity (XXE) Attacks**: Exploitation of XML parsers resolving remote external entities or local file system resources (`file:///etc/passwd`).
4. **Tenant Escape / IDOR**: Cross-tenant tampering with source feeds, opportunities, or editorial content.
5. **Copyright Infringement / Content Scraping**: Storing proprietary competitor articles.

---

## SSRF Defense Implementation

All URL processing in `app/services/trend/network_safety.py` enforces multi-layer defense:

### 1. Scheme Whitelisting
Only `http` and `https` schemes are permitted. Schemes such as `file://`, `ftp://`, `gopher://`, `data:`, and `javascript:` are immediately rejected.

### 2. Prohibited IP Ranges & Hostnames

The following CIDR blocks and hostnames are rejected:

- **Loopback**: `127.0.0.0/8`, `localhost`, `[::1]/128`
- **RFC 1918 Private IPv4**:
  - `10.0.0.0/8`
  - `172.16.0.0/12`
  - `192.168.0.0/16`
- **Cloud Metadata / Link-Local**:
  - `169.254.0.0/16` (AWS / GCP metadata `169.254.169.254`)
  - `metadata.google.internal`
  - `fe80::/10` (IPv6 link-local)
- **IPv6 Private & Multicast**:
  - `fc00::/7` (ULA)
  - `ff00::/8` (Multicast)
- **Special / Reserved**:
  - `0.0.0.0/8`, `224.0.0.0/4`, `240.0.0.0/4`
- **Internal Domain Suffixes**: `*.local`, `*.internal`

### 3. Sensitive Port Blocking
Direct connections to internal administrative and storage ports (e.g., 22, 25, 3306, 5432, 6379, 8080, 9200, 27017) are blocked even if using public IP hostnames.

### 4. DNS Pre-flight Resolution
Hostnames are resolved using `socket.getaddrinfo` prior to initiating the HTTP request. Every resolved IP address is verified against the blocked network list.

### 5. Redirect Guard
HTTP redirects are limited to a maximum of 3 hops. Before following any redirect, the target destination URL is re-validated through the SSRF security policy.

### 6. Payload Limits & Timeouts
- Maximum HTTP response size: 2MB (`MAX_FEED_PAYLOAD_BYTES`).
- Connection timeout: 5.0 seconds.
- Read timeout: 10.0 seconds.

---

## XXE & XML Parser Hardening

Python standard library `xml.etree.ElementTree` is used with entity resolution disabled:
```python
parser = ET.XMLParser()
root = ET.fromstring(content_bytes, parser=parser)
```
The parser does not load DTD external entities or execute remote schemas.

---

## Authorization & Tenant Isolation (IDOR/BOLA Prevention)

Every new resource (`Source`, `SourceItem`, `SimilarStoryGroup`, `ContentOpportunity`):
- Is tied directly to `context.tenant_id` derived exclusively from the authenticated JWT token.
- Ignores `tenant_id` or `X-Tenant-ID` supplied in request bodies or query parameters.
- Rejects cross-tenant access with `404 Not Found` to prevent resource enumeration.

---

## Audit Trail

All administrative and ingestion events produce immutable records in `audit_logs`:
- `SOURCE_CREATED`
- `SOURCE_UPDATED`
- `SOURCE_ENABLED`
- `SOURCE_DISABLED`
- `SOURCE_FETCHED`
- `TREND_SEARCHED`
- `OPPORTUNITY_CREATED`
- `OPPORTUNITY_ACCEPTED`
- `OPPORTUNITY_REJECTED`
- `OPPORTUNITY_CONVERTED_TO_STORY`

---

## Known Security Limitations & Operational Recommendations

1. **DNS Rebinding Window**: A time-of-check to time-of-use (TOCTOU) gap exists between pre-flight DNS resolution and socket connection. For high-security military or enterprise deployments, a dedicated outbound egress HTTP proxy (e.g. Squid / Smokescreen) with IP pinning should be deployed at the network perimeter.
2. **Feed Authenticity**: While feeds are restricted to configured URLs, external publishers may still publish incorrect or misleading claims. Hence, human editorial review remains strictly mandatory.
