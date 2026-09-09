"""Deterministic, explainable Trend Scoring Engine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.db.base import utc_now


@dataclass
class TrendScoreResult:
    """Detailed score result with transparent, explainable factor breakdown."""

    total_score: float
    confidence_score: float
    urgency: str
    reasons: List[str]
    breakdown: Dict[str, float]
    risk_indicators: List[str] = field(default_factory=list)


def calculate_freshness_score(
    published_at: Optional[datetime], now: Optional[datetime] = None
) -> float:
    """
    Freshness scoring (0 to 25 points).
    More recent news items receive significantly higher priority.
    """
    if not published_at:
        return 3.0

    if now is None:
        now = utc_now()

    # Ensure timezone awareness
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    diff_seconds = max(0.0, (now - published_at).total_seconds())
    diff_hours = diff_seconds / 3600.0

    if diff_hours <= 2.0:
        return 25.0
    elif diff_hours <= 6.0:
        return 20.0
    elif diff_hours <= 12.0:
        return 15.0
    elif diff_hours <= 24.0:
        return 10.0
    elif diff_hours <= 48.0:
        return 5.0
    else:
        return 2.0


def calculate_velocity_score(item_count_recent: int) -> float:
    """
    Velocity / Momentum score (0 to 20 points).
    Measures rapid arrival of items in recent time window.
    """
    if item_count_recent >= 5:
        return 20.0
    elif item_count_recent >= 3:
        return 15.0
    elif item_count_recent == 2:
        return 10.0
    elif item_count_recent == 1:
        return 5.0
    return 2.0


def calculate_diversity_score(independent_publishers_count: int) -> float:
    """
    Source diversity score (0 to 25 points).
    Corroboration across independent editorial organizations.
    """
    if independent_publishers_count >= 4:
        return 25.0
    elif independent_publishers_count == 3:
        return 20.0
    elif independent_publishers_count == 2:
        return 14.0
    elif independent_publishers_count == 1:
        return 7.0
    return 2.0


def calculate_reliability_score(
    mean_reliability: float, has_official_or_wire: bool
) -> float:
    """
    Source reliability and authority score (0 to 20 points).
    """
    # Base score: average reliability (0-100) scaled to 0-15
    base = min(15.0, max(0.0, (mean_reliability / 100.0) * 15.0))
    # Bonus for verified government, official or wire service
    bonus = 5.0 if has_official_or_wire else 0.0
    return min(20.0, round(base + bonus, 1))


def calculate_relevance_score(
    query: Optional[str], headline: str, summary: Optional[str]
) -> float:
    """
    Topic relevance score (0 to 10 points).
    """
    if not query or not query.strip():
        return 5.0  # neutral relevance when searching broad trends

    query_tokens = set(query.lower().strip().split())
    if not query_tokens:
        return 5.0

    headline_lower = headline.lower()
    summary_lower = (summary or "").lower()

    headline_matches = sum(1 for tok in query_tokens if tok in headline_lower)
    summary_matches = sum(1 for tok in query_tokens if tok in summary_lower)

    score = 0.0
    if headline_matches > 0:
        score += min(6.0, (headline_matches / len(query_tokens)) * 6.0)
    if summary_matches > 0:
        score += min(4.0, (summary_matches / len(query_tokens)) * 4.0)

    return round(score, 1)


def score_trend(
    headline: str,
    summary: Optional[str],
    published_at: Optional[datetime],
    independent_publishers: List[str],
    source_reliabilities: List[float],
    has_official_or_wire: bool,
    recent_item_count: int,
    query: Optional[str] = None,
    rights_types: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> TrendScoreResult:
    """
    Compute a transparent, deterministic trend score with explainable reasons.
    """
    publisher_count = len(set(p for p in independent_publishers if p))
    avg_reliability = (
        sum(source_reliabilities) / len(source_reliabilities)
        if source_reliabilities
        else 70.0
    )

    freshness = calculate_freshness_score(published_at, now=now)
    velocity = calculate_velocity_score(recent_item_count)
    diversity = calculate_diversity_score(publisher_count)
    reliability = calculate_reliability_score(avg_reliability, has_official_or_wire)
    relevance = calculate_relevance_score(query, headline, summary)

    total_score = min(100.0, round(freshness + velocity + diversity + reliability + relevance, 1))

    # Urgency determination
    if total_score >= 80.0:
        urgency = "URGENT"
    elif total_score >= 60.0:
        urgency = "HIGH"
    elif total_score >= 40.0:
        urgency = "NORMAL"
    else:
        urgency = "LOW"

    # Confidence calculation (0.50 to 0.95)
    base_conf = 0.50
    if publisher_count >= 3:
        base_conf += 0.20
    elif publisher_count >= 2:
        base_conf += 0.10
    if avg_reliability >= 85.0:
        base_conf += 0.15
    elif avg_reliability >= 70.0:
        base_conf += 0.10
    confidence = min(0.95, round(base_conf, 2))

    # Explainable reasons list
    reasons: List[str] = []
    if freshness >= 20.0:
        reasons.append("Item published within last 6 hours (high freshness)")
    elif freshness >= 10.0:
        reasons.append("Item published within last 24 hours")

    if publisher_count > 1:
        reasons.append(f"{publisher_count} independent publishers reporting")
    else:
        reasons.append("Single publisher reporting")

    if has_official_or_wire:
        reasons.append("Corroborated by official government or wire service")

    if velocity >= 15.0:
        reasons.append(f"Rapid increase in coverage ({recent_item_count} recent updates)")

    if relevance >= 6.0:
        reasons.append("Strong headline match for searched topic")

    # Risk indicators
    risk_indicators: List[str] = []
    if publisher_count == 1:
        risk_indicators.append("Single-source story: corroboration recommended")
    if avg_reliability < 65.0:
        risk_indicators.append("Lower publisher reliability score: editorial verification required")
    if rights_types:
        for rt in rights_types:
            if rt in ("restricted", "unknown"):
                risk_indicators.append(
                    f"Third-party rights metadata '{rt}': verify license before citation"
                )

    return TrendScoreResult(
        total_score=total_score,
        confidence_score=confidence,
        urgency=urgency,
        reasons=reasons,
        breakdown={
            "freshness": freshness,
            "velocity": velocity,
            "source_diversity": diversity,
            "source_reliability": reliability,
            "topic_relevance": relevance,
        },
        risk_indicators=risk_indicators,
    )
