# ADR-0003: Trend Radar and Source Monitoring Subsystem

## Status
Accepted

## Date
2026-09-09

## Context
In modern newsroom automation, editorial teams require rapid, accurate detection of emerging stories and corroborated developments. Traditional solutions often rely on arbitrary web scrapers, headless browser automation, or third-party paid search APIs. These introduce severe security vulnerabilities (SSRF, IP bans, malicious payloads), legal liabilities (copyright infringement from storing full proprietary articles), and cost predictability issues.

Furthermore, autonomous AI agents that automatically publish content based on unverified trend spikes risk amplifying misinformation.

## Decision

We establish the foundational **Trend Radar and Source Monitoring subsystem** under the following architectural invariants:

1. **Source Registry Over Arbitrary Scraping**: Only explicitly registered, tenant-configured source feeds are monitored. Web crawling, competitor scraping, headless browsers, paywall bypasses, and unauthorized extraction are strictly prohibited.
2. **Standard Library Ingestion Without Dependency Bloat**: We leverage Python standard library `xml.etree.ElementTree` (with entity resolution disabled) and existing `httpx` async networking. No new external parsing libraries, vector stores, or search engines are introduced in Phase 3.
3. **Multi-Layer SSRF Prevention**: Enforce comprehensive IP and scheme blocking across private IPv4 (RFC 1918), loopback, cloud metadata endpoints (169.254.169.254), IPv6 link-local, non-HTTP schemes, and unsafe network ports.
4. **Deterministic, Explainable Trend Scoring**: Scoring is calculated via a transparent 5-factor model (Freshness, Velocity, Source Diversity, Source Authority, Topic Relevance). Every score is accompanied by an explainable reasons list and risk signals.
5. **Deterministic Clustering & Duplicate Detection**: Normalized title token sets and canonical URLs generate deterministic SHA-256 fingerprints. Story grouping utilizes Jaccard token similarity ($\ge 0.30$) within a sliding temporal window (48 hours), explicitly designated as "Potentially related".
6. **Mandatory Human Editorial Review**: Discovered trend opportunities require explicit editorial action (`ACCEPT`, `REJECT`, or `CONVERT_TO_STORY`). Converting an opportunity generates a Phase 2 `Story` strictly in the initial `IDEA` state, preserving source citations and tenant ownership.

## Consequences

### Positive
- Zero external dependency bloat (100% reuse of verified foundation).
- Protection against SSRF and unauthorized intranet probing.
- Safe intellectual property boundary: summaries capped at 1,000 chars; no storage of proprietary copyrighted article bodies.
- Seamless integration with Phase 2 Story lifecycle and assignment desk.
- Complete tenant isolation and immutable audit logging across all discovery actions.

### Negative / Trade-offs
- Semantic and multilingual synonym matching across Indian languages is limited to lexical tokens in Phase 3 (deferred to Phase 4 vector embeddings).
- Dynamic JavaScript-only single page feeds are unsupported (by design, avoiding browser automation overhead).
