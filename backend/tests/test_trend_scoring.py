"""Unit tests for deterministic trend scoring and story clustering."""

from datetime import datetime, timedelta, timezone

from app.db.base import utc_now
from app.db.models.trend import SourceItem
from app.services.trend.clustering import is_potentially_related, jaccard_similarity, tokenize_title
from app.services.trend.scoring import (
    calculate_diversity_score,
    calculate_freshness_score,
    calculate_reliability_score,
    calculate_velocity_score,
    score_trend,
)


def test_freshness_scoring_decay():
    """Verify freshness points decrease as publication age increases."""
    now = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)

    # Published 1 hour ago
    pub_1h = now - timedelta(hours=1)
    assert calculate_freshness_score(pub_1h, now=now) == 25.0

    # Published 4 hours ago
    pub_4h = now - timedelta(hours=4)
    assert calculate_freshness_score(pub_4h, now=now) == 20.0

    # Published 10 hours ago
    pub_10h = now - timedelta(hours=10)
    assert calculate_freshness_score(pub_10h, now=now) == 15.0

    # Published 30 hours ago
    pub_30h = now - timedelta(hours=30)
    assert calculate_freshness_score(pub_30h, now=now) == 5.0

    # Published 60 hours ago
    pub_60h = now - timedelta(hours=60)
    assert calculate_freshness_score(pub_60h, now=now) == 2.0


def test_diversity_scoring():
    """Verify score increases with independent publisher corroboration."""
    assert calculate_diversity_score(1) == 7.0
    assert calculate_diversity_score(2) == 14.0
    assert calculate_diversity_score(3) == 20.0
    assert calculate_diversity_score(4) == 25.0


def test_velocity_scoring():
    """Verify velocity score reflects rapid bursts in mentions."""
    assert calculate_velocity_score(1) == 5.0
    assert calculate_velocity_score(2) == 10.0
    assert calculate_velocity_score(3) == 15.0
    assert calculate_velocity_score(6) == 20.0


def test_reliability_scoring():
    """Verify reliability incorporates authority bonus for wire/official sources."""
    # 70 reliability without official source
    score_regular = calculate_reliability_score(70.0, has_official_or_wire=False)
    # 70 reliability with official source (+5 bonus)
    score_official = calculate_reliability_score(70.0, has_official_or_wire=True)

    assert score_official == score_regular + 5.0


def test_full_explainable_score():
    """Verify comprehensive trend score produces explainable reasons and risk signals."""
    now = utc_now()
    published_recent = now - timedelta(minutes=45)

    result = score_trend(
        headline="Cabinet Approves Key Infrastructure Package for Eastern UP",
        summary="Major highway and hospital projects announced by the state government.",
        published_at=published_recent,
        independent_publishers=["Amar Ujala", "Dainik Jagran", "PTI", "Times of India"],
        source_reliabilities=[85.0, 80.0, 95.0, 88.0],
        has_official_or_wire=True,
        recent_item_count=4,
        query="Infrastructure Package",
        rights_types=["public_information"],
        now=now,
    )

    assert result.total_score >= 80.0
    assert result.urgency == "URGENT"
    assert result.confidence_score >= 0.85
    assert any("independent publishers" in r for r in result.reasons)
    assert any("official government or wire" in r for r in result.reasons)
    assert "freshness" in result.breakdown
    assert "velocity" in result.breakdown


def test_single_source_risk_flag():
    """Verify single source generates a risk indicator for editorial review."""
    result = score_trend(
        headline="Rumor regarding local municipal elections",
        summary="Unverified reports suggest schedule change.",
        published_at=utc_now(),
        independent_publishers=["Local Blog"],
        source_reliabilities=[55.0],
        has_official_or_wire=False,
        recent_item_count=1,
        query="municipal",
        rights_types=["unknown"],
    )

    assert any("Single-source story" in risk for risk in result.risk_indicators)
    assert any("Lower publisher reliability" in risk for risk in result.risk_indicators)


def test_jaccard_similarity_and_similar_story_grouping():
    """Verify similar headlines are recognized as 'potentially related'."""
    tokens1 = tokenize_title("Prime Minister Inaugurates New Expressway in Gorakhpur")
    tokens2 = tokenize_title("PM Inaugurates Gorakhpur Expressway Project")
    tokens3 = tokenize_title("Stock Markets Fall Sharply on Inflation Data")

    sim_related = jaccard_similarity(tokens1, tokens2)
    sim_unrelated = jaccard_similarity(tokens1, tokens3)

    assert sim_related > 0.35
    assert sim_unrelated == 0.0

    now = utc_now()
    item_a = SourceItem(
        id="item-a",
        tenant_id="tenant-1",
        source_id="src-1",
        title="Prime Minister Inaugurates New Expressway in Gorakhpur",
        canonical_url="https://news1.com/exp1",
        fingerprint="fp1",
        published_at=now,
    )
    item_b = SourceItem(
        id="item-b",
        tenant_id="tenant-1",
        source_id="src-2",
        title="PM Inaugurates Gorakhpur Expressway Project",
        canonical_url="https://news2.com/exp2",
        fingerprint="fp2",
        published_at=now + timedelta(hours=2),
    )

    assert is_potentially_related(item_a, item_b) is True
