# Trend Radar & Topic-to-Content Architecture

## 1. Vision & Purpose

Trend Radar is a future intelligent intelligence-gathering and topic-evaluation engine for newsrooms, YouTube creators, and media publishers. It enables a tenant to monitor regional, national, or niche topics (e.g., "Gorakhpur", "Uttar Pradesh", "AI", "Technology", "Cricket", "Jobs") and uncover genuine, verifiable content opportunities.

> **Phase 1 Boundary**: The Trend Radar is **NOT** implemented in Phase 1. Only architectural interfaces, domain boundaries, data contracts, and anti-scraping principles are established in this document.

---

## 2. Topic-to-Content Pipeline (Future Workflow)

```text
Topic Query / Alert
       ↓
Trend Detection (Velocity & Social Signals)
       ↓
Source Discovery (Official / Public / Licensed)
       ↓
Duplicate Detection & Cluster Grouping
       ↓
Fact / Context Verification
       ↓
Trend Scoring Engine (0 - 100)
       ↓
Story Opportunity & Editorial Brief
       ↓
Human Editorial Decision (MAKE NOW / VERIFY FIRST / DO NOT PUBLISH)
       ↓
AI Content Generation (Script, Hook, Storyboard)
       ↓
Deterministic Backend Validation
       ↓
Mandatory Human Approval Sign-off
       ↓
Multi-Platform Publishing
```

---

## 3. Strict Anti-Scraping & Legal Rights Policy

**Topic-to-Content does NOT mean content scraping or unauthorized aggregation.**

The platform strictly prohibits scraping copyrighted articles or videos for verbatim republication. The architecture enforces:
1. **Source Provenance**: Every content proposal must maintain clear metadata tracking:
   - Primary source type: `OFFICIAL_GOVERNMENT_RELEASE`, `PUBLIC_STATEMENT`, `LICENSED_WIRE_FEED`, `USER_OWNED_MEDIA`, `VERIFIED_PUBLIC_DATA`.
   - Source URL, timestamp, and confidence rating.
2. **Original Synthesis**: AI models generate original reporting angles, scripts, and analyses based on raw facts, never duplicating protected expression.
3. **Rights Clearance**: Output content tracks rights metadata for video clips, audio tracks, and still images before any publication step.

---

## 4. Trend Score Formulation (Future Data Contract)

The future Trend Scoring Engine evaluates potential topics across multi-factor dimensions:

```python
class TrendScoreBreakdown:
    velocity: float          # Speed of conversation acceleration (0-100)
    relevance: float         # Alignment with tenant's audience & beat (0-100)
    source_confidence: float # Quality and authority of original sources (0-100)
    audience_potential: float# Estimated reach and engagement opportunity (0-100)
    urgency_level: str       # "LOW", "MEDIUM", "HIGH", "BREAKING"
    recommendation: str      # "MAKE NOW", "VERIFY FIRST", "DO NOT PUBLISH"
    misinformation_risk: str # "LOW", "ELEVATED", "HIGH"
```

### Example Future Output (Gorakhpur Regional Beat):
- **Topic**: Gorakhpur Railway Infrastructure Modernization
- **Trend Score**: 87 / 100
- **Relevance**: 94 / 100
- **Source Confidence**: 91 / 100 (Official Indian Railways Gazette & Press Bureau)
- **Audience Potential**: 89 / 100
- **Urgency**: HIGH
- **Recommendation**: MAKE NOW
