"""Clustering, Duplicate Detection, and Similar Story Grouping service."""

import re
from datetime import datetime, timezone
from typing import List, Set

from app.db.base import utc_now
from app.db.models.trend import ContentOpportunity, SimilarStoryGroup, SourceItem
from app.services.trend.scoring import score_trend

# Common stop words for deterministic tokenization
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "at", "from",
    "by", "for", "with", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "to", "of", "in", "on", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "can",
    "could", "will", "would", "shall", "should", "may", "might", "must", "as", "it",
    "its", "they", "them", "their", "this", "that", "these", "those", "which", "who",
}


def tokenize_title(title: str) -> Set[str]:
    """Tokenize and filter stop words from title for deterministic similarity."""
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    tokens = {word for word in cleaned.split() if len(word) > 2 and word not in STOP_WORDS}
    return tokens


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Compute Jaccard similarity coefficient between two token sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def is_potentially_related(
    item_a: SourceItem,
    item_b: SourceItem,
    time_window_hours: int = 48,
    similarity_threshold: float = 0.30,
) -> bool:
    """
    Determine if two source items are 'potentially related' based on deterministic
    token overlap and temporal proximity.
    """
    # Check temporal window if dates are available
    time_a = item_a.published_at or item_a.fetched_at
    time_b = item_b.published_at or item_b.fetched_at

    if time_a and time_b:
        # Normalize timezones
        if time_a.tzinfo is None:
            time_a = time_a.replace(tzinfo=timezone.utc)
        if time_b.tzinfo is None:
            time_b = time_b.replace(tzinfo=timezone.utc)
        hours_diff = abs((time_a - time_b).total_seconds()) / 3600.0
        if hours_diff > time_window_hours:
            return False

    tokens_a = tokenize_title(item_a.title)
    tokens_b = tokenize_title(item_b.title)

    return jaccard_similarity(tokens_a, tokens_b) >= similarity_threshold


def synthesize_group_opportunity(
    group: SimilarStoryGroup,
    items: List[SourceItem],
    topic: str,
    now: datetime | None = None,
) -> ContentOpportunity:
    """
    Synthesize an editorial ContentOpportunity from a SimilarStoryGroup and its items.
    """
    if now is None:
        now = utc_now()

    publishers = list(set(it.publisher for it in items if it.publisher))
    reliabilities = [it.reliability_score for it in items if it.reliability_score is not None]
    if not reliabilities:
        reliabilities = [70.0]

    has_official_or_wire = any(
        it.raw_metadata.get("source_type") in ("OFFICIAL", "GOVERNMENT", "WIRE")
        for it in items
    )

    rights_types = [
        it.rights_metadata.get("rights_type", "unknown")
        for it in items
        if isinstance(it.rights_metadata, dict)
    ]

    latest_pub = max(
        (it.published_at for it in items if it.published_at),
        default=group.latest_seen_at,
    )

    # Calculate deterministic trend score
    score_res = score_trend(
        headline=group.representative_title,
        summary=items[0].summary if items else None,
        published_at=latest_pub,
        independent_publishers=publishers,
        source_reliabilities=reliabilities,
        has_official_or_wire=has_official_or_wire,
        recent_item_count=len(items),
        query=topic,
        rights_types=rights_types,
        now=now,
    )

    # Update group trend score
    group.trend_score = score_res.total_score
    group.source_count = len(items)
    group.independent_publisher_count = len(publishers) or 1
    group.strongest_source_reliability = max(reliabilities) if reliabilities else 70.0

    # Build opportunity summary
    summary_parts = [it.summary for it in items if it.summary]
    opportunity_summary = (
        summary_parts[0] if summary_parts else f"Emerging coverage regarding {topic}."
    )

    opportunity = ContentOpportunity(
        tenant_id=group.tenant_id,
        similar_story_group_id=group.id,
        topic=topic,
        headline=group.representative_title,
        summary=opportunity_summary,
        trend_score=score_res.total_score,
        confidence_score=score_res.confidence_score,
        source_count=len(items),
        publisher_count=len(publishers) or 1,
        urgency=score_res.urgency,
        status="DISCOVERED",
        risk_indicators=score_res.risk_indicators,
        score_explanation={
            "reasons": score_res.reasons,
            "breakdown": score_res.breakdown,
            "signal_type": "TREND_SIGNAL",
        },
    )

    return opportunity
