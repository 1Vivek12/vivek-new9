# Source Monitoring & Ingestion Architecture

## Overview

The **Source Registry and Monitoring subsystem** provides a tenant-isolated directory of verified information feeds and publishers. Rather than scanning or scraping the open web indiscriminately, the system monitors only explicitly approved feeds configured by authorized tenant editors.

---

## Source Registry Data Model

Every source in `sources` is strictly owned by a `tenant_id` and tracks:

- **Identity**: `id`, `tenant_id`, `name`, `publisher_name`, `feed_url`, `website_url`
- **Typology**:
  - `OFFICIAL`: Government portals, official gazettes, press release departments (e.g. PIB, UPPRD).
  - `GOVERNMENT`: Departmental bulletins and regulatory authorities.
  - `WIRE`: Verified news agency syndication (e.g. PTI, ANI, Reuters).
  - `PUBLICATION`: Accredited journalistic publications.
  - `RSS`: General syndicated XML feeds.
  - `SOCIAL`: Public social broadcast channels (metadata only).
  - `USER_PROVIDED`: Reporter-submitted external tips.
  - `OTHER`: Unclassified sources.
- **Reliability & Trust**:
  - `reliability_score`: Float between $0.0$ and $100.0$.
  - `trust_level`: `HIGH`, `MEDIUM`, `LOW`, `UNVERIFIED`.
- **Operational Metrics**:
  - `polling_interval_minutes`: Default 60 minutes.
  - `is_active`: Boolean kill-switch.
  - `last_fetched_at`, `last_success_at`, `last_failure_at`.
  - `failure_count`: Auto-incremented on error; prevents infinite retries.
  - `last_error_message`: Truncated error diagnosis.

---

## Source Rights & Intellectual Property Metadata

The system does NOT assume ownership or free reuse of external material. Every source configuration records explicit rights metadata:

```json
{
  "rights_type": "public_information",
  "reuse_permitted": false,
  "citation_required": true,
  "license_notes": "Discovery and citation research only. Do not duplicate full text."
}
```

Permitted rights types:
- `owned`: Proprietary tenant content.
- `licensed`: Commercial syndication license in place.
- `permissioned`: Express editorial permission granted.
- `public_information`: Official government communications and public gazettes.
- `unknown`: Third-party unverified rights (triggers risk warning).
- `restricted`: Reproduction prohibited (editorial citation only).

---

## Ingestion Abstraction

```
SourceConnector (Abstract Base Class)
    ▲
    │
RSSAtomConnector (Concrete Implementation)
```

1. **Protocols Supported**:
   - RSS 2.0 (`channel -> item`)
   - RSS 1.0 / RDF (`rdf:RDF -> item`)
   - Atom 1.0 (`feed -> entry`)
2. **Payload Protection**:
   - Maximum download size: 2MB (`MAX_FEED_PAYLOAD_BYTES`).
   - Strict connection timeout: 5.0s.
   - Strict read timeout: 10.0s.
   - XML parsing performed using standard library `xml.etree.ElementTree.XMLParser(resolve_entities=False)` to prevent XML Entity Expansion (XXE / Billion Laughs) attacks.
3. **Summarization & Retention Policy**:
   - Full article bodies are **never** crawled or stored.
   - Summaries are sanitized, stripped of HTML markup and scripts, and truncated to a maximum of 1,000 characters.
   - Raw metadata contains only identity markers (GUID, URL, feed source type).
