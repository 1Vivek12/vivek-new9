# ADR-0004: Phase 4 AI Research & Content Intelligence Architecture

## Status
Accepted

## Context
In Phase 4, the platform requires automated research and content intelligence to assist editors and journalists in transforming raw trend opportunities and editorial stories into factual research briefs, multi-angle content plans, broadcast scripts, headline variants, and SEO metadata.

Two critical security and legal challenges were identified during architectural review:
1. **Prompt Injection**: Malicious or adversarial instructions embedded inside third-party sources could manipulate model outputs or attempt tool execution.
2. **Copyright Infringement**: Indiscriminately storing full articles or source web pages from competitor publications would expose the platform to copyright liability.

## Decision
1. **Prompt Injection Defense Architecture**:
   - Classify all external content as untrusted passive data.
   - Enforce a 4-tier prompt separation: System Instructions, Workflow Instructions, Editorial Input, and Untrusted Evidence quarantined inside `<untrusted_source_evidence_boundary>`.
   - Neutralize boundary tags and fake system headers.
   - Run AI inference in a sandboxed completion environment with zero tool execution privileges.
   - Phrase filtering is maintained strictly as an auxiliary telemetry layer and never as the primary security defense.
2. **Bounded Research Evidence Storage**:
   - Completely reject full competitor article or full source page storage.
   - Enforce hard length boundaries on evidence records: `evidence_snippet` maximum 750 characters, `normalized_claim_summary` maximum 500 characters.
   - Preserve canonical URL, publisher, timestamps, and rights metadata (`reuse_permitted: false`).
3. **Mandatory Human Editorial Review**:
   - All AI outputs default to `GENERATED` / `REVIEW_REQUIRED`.
   - The AI engine has zero permission to approve or publish content.
   - Approval requires human role (`EDITOR`, `ADMIN`, `OWNER`).
   - Rejection mandates an explicit reason.
4. **Append-Only Versioning**:
   - AI outputs are versioned immutably. Consecutive generation runs append new versions rather than overwriting existing records.

## Consequences
- The newsroom is protected against indirect prompt injection without censoring factual news text.
- Full competitor articles are never persisted, satisfying copyright limits.
- Editors maintain complete oversight and accountability over all published material.
