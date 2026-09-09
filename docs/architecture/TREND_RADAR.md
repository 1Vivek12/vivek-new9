# Trend Radar Architecture Specification

## Overview

The **Trend Radar** is an editorial discovery and source-monitoring subsystem designed to enable newsrooms and editors to detect emerging content opportunities from verified, approved external and internal information sources.

> [!IMPORTANT]
> **Human Editorial Invariant**: The Trend Radar is strictly an informational discovery and editorial research system. It does **NOT** automatically publish content, generate public output, or bypass human editorial review. Every content opportunity must be explicitly reviewed, accepted, or converted by an editor into a Phase 2 Story in the initial `IDEA` state.

---

## Core Pipeline Architecture

```
Topic Search Query
    ↓
Source Registry (Tenant-Scoped, Rights & Trust Level)
    ↓
Network Safety & SSRF Guard (Blocked Private IPs, Schemes, Timeouts)
    ↓
RSS / Atom Ingestion & Normalization (Safe XML Parsing, Payload Cap 2MB)
    ↓
Source Items (Canonical URL, SHA-256 Fingerprint, Summaries Only)
    ↓
Duplicate & Similar Story Grouping (Deterministic Token Jaccard Overlap)
    ↓
Explainable Trend Scoring (Freshness + Velocity + Diversity + Authority + Relevance)
    ↓
Content Opportunity (Urgency, Confidence, Risk Signals, Explanation)
    ↓
Human Editorial Action (Accept / Reject / Convert to Phase 2 Story)
    ↓
Phase 2 Story in 'IDEA' Status (Attached StorySources, Full Audit Isolation)
```

---

## Scoring Formula & Deterministic Signals

The platform rejects opaque black-box metrics. Every trend score is deterministic, transparent, and explainable on a 0–100 scale:

$$\text{Trend Score} = \min(100.0, S_{\text{freshness}} + S_{\text{velocity}} + S_{\text{diversity}} + S_{\text{reliability}} + S_{\text{relevance}})$$

### Component Weights

| Component | Points | Calculation / Heuristic |
|---|---|---|
| **Freshness** | 0 – 25 | $\le 2\text{h}: 25$, $\le 6\text{h}: 20$, $\le 12\text{h}: 15$, $\le 24\text{h}: 10$, $\le 48\text{h}: 5$, older: $2$ |
| **Velocity** | 0 – 20 | Burst rate of items over rolling window ($5+: 20$, $3-4: 15$, $2: 10$, $1: 5$) |
| **Source Diversity** | 0 – 25 | Corroboration across distinct independent publishers ($4+: 25$, $3: 20$, $2: 14$, $1: 7$) |
| **Source Authority** | 0 – 20 | Base: $(\text{mean reliability} / 100) \times 15$ + 5 bonus points for official/wire sources |
| **Topic Relevance** | 0 – 10 | Lexical density matching in headline (up to 6 pts) and summary (up to 4 pts) |

### Explainability Payload

Every Content Opportunity produces a structured explanation payload:
```json
{
  "total_score": 82.5,
  "confidence_score": 0.85,
  "urgency": "URGENT",
  "reasons": [
    "Item published within last 6 hours (high freshness)",
    "4 independent publishers reporting",
    "Corroborated by official government or wire service",
    "Rapid increase in coverage (4 recent updates)",
    "Strong headline match for searched topic"
  ],
  "breakdown": {
    "freshness": 25.0,
    "velocity": 15.0,
    "source_diversity": 25.0,
    "source_reliability": 17.5,
    "topic_relevance": 6.0
  },
  "risk_indicators": []
}
```

---

## Duplicate Detection & Grouping

1. **Lightweight Fingerprinting**: A deterministic SHA-256 fingerprint is calculated for every source item:
   $$\text{Fingerprint} = \text{SHA256}(\text{normalized\_title\_tokens} \parallel \text{canonical\_url})$$
   Enforced via unique constraint `uq_source_item_tenant_fingerprint` in database.
2. **Similar Story Groups**: Items within a 48-hour temporal window sharing token Jaccard similarity $\ge 0.30$ are clustered into `SimilarStoryGroup` entities, labeled transparently as **"Potentially related"** (never claiming factual identity).

---

## Content Opportunity Lifecycle

```
                ┌───────────────┐
                │  DISCOVERED   │
                └───────┬───────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
 ┌──────────────┐                ┌──────────────┐
 │   ACCEPTED   │                │   REJECTED   │
 └──────┬───────┘                └──────────────┘
        │
        ▼
 ┌──────────────────────┐
 │  CONVERTED_TO_STORY  │ ──► Phase 2 Story Created (status: IDEA)
 └──────────────────────┘
```

When converted:
- Story created strictly in `IDEA` status (never auto-approved or published).
- Tenant ownership preserved.
- Source citations attached as `StorySource` records.
- Immutable audit record `OPPORTUNITY_CONVERTED_TO_STORY` created.

---

## Future Roadmap

- **Phase 4**: Vector embedding models (e.g. pgvector or local embeddings) for semantic clustering across multilingual Indian languages.
- **Phase 5**: Supervised AI research assistant operating strictly within the human editorial sandbox.
