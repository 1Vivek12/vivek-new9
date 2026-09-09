"""Tests for RSS/Atom feed parsing, item normalization, and error handling."""

from datetime import datetime

import pytest

from app.db.models.source_registry import Source
from app.services.trend.rss_connector import (
    RSSAtomConnector,
    compute_item_fingerprint,
    strip_html_and_truncate,
)

SAMPLE_RSS_2 = b"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>National News Wire</title>
  <link>https://wire.example.com</link>
  <description>Official News Feed</description>
  <item>
    <title>High Speed Rail Corridor Approved for Uttar Pradesh</title>
    <link>https://wire.example.com/articles/rail-corridor-up?utm_source=rss</link>
    <description><![CDATA[<p>The Union Cabinet has approved a new high-speed rail
    corridor connecting Lucknow and Varanasi.</p>]]></description>
    <pubDate>Wed, 09 Sep 2026 10:00:00 GMT</pubDate>
    <guid>https://wire.example.com/articles/rail-corridor-up</guid>
  </item>
  <item>
    <title>Monsoon Agricultural Yield Forecasts Exceed Target</title>
    <link>https://wire.example.com/articles/monsoon-yield-2026</link>
    <description>Agricultural ministry reports bumper harvests across northern states.</description>
    <pubDate>Wed, 09 Sep 2026 11:30:00 GMT</pubDate>
    <guid>guid-agri-2026-99</guid>
  </item>
</channel>
</rss>
"""

SAMPLE_ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Government Gazette Updates</title>
  <link href="https://gazette.gov.in"/>
  <updated>2026-09-09T12:00:00Z</updated>
  <entry>
    <title>New Industrial Policy Notification 2026</title>
    <link href="https://gazette.gov.in/notifications/ind-pol-2026"/>
    <id>urn:uuid:12345-gazette-notification</id>
    <updated>2026-09-09T11:45:00Z</updated>
    <summary>Notification regarding manufacturing subsidies in special economic zones.</summary>
  </entry>
</feed>
"""

MALFORMED_FEED = b"""<?xml version="1.0"?>
<rss><channel><title>Broken Feed<item><title>Unclosed tag
"""


def test_rss_2_parsing():
    """Verify RSS 2.0 parsing and field normalization."""
    source = Source(
        id="test-src-1",
        tenant_id="tenant-1",
        name="National Wire",
        source_type="WIRE",
        feed_url="https://wire.example.com/rss",
        publisher_name="National News Wire",
        reliability_score=90.0,
        language="en",
        created_by_user_id="user-1",
    )

    connector = RSSAtomConnector(check_dns=False)
    items = connector.parse_feed_content(SAMPLE_RSS_2, source)

    assert len(items) == 2
    item1 = items[0]
    assert item1.title == "High Speed Rail Corridor Approved for Uttar Pradesh"
    assert item1.canonical_url == "https://wire.example.com/articles/rail-corridor-up"
    assert "Union Cabinet has approved" in (item1.summary or "")
    assert "<p>" not in (item1.summary or "")  # Stripped HTML tags
    assert isinstance(item1.published_at, datetime)
    assert item1.reliability_score == 90.0
    assert item1.publisher == "National News Wire"
    assert len(item1.fingerprint) == 64


def test_atom_feed_parsing():
    """Verify Atom 1.0 parsing and namespace handling."""
    source = Source(
        id="test-src-2",
        tenant_id="tenant-1",
        name="Gazette",
        source_type="GOVERNMENT",
        feed_url="https://gazette.gov.in/atom.xml",
        publisher_name="Official Gazette",
        reliability_score=95.0,
        language="en",
        created_by_user_id="user-1",
    )

    connector = RSSAtomConnector(check_dns=False)
    items = connector.parse_feed_content(SAMPLE_ATOM, source)

    assert len(items) == 1
    item = items[0]
    assert item.title == "New Industrial Policy Notification 2026"
    assert item.canonical_url == "https://gazette.gov.in/notifications/ind-pol-2026"
    assert item.external_id == "urn:uuid:12345-gazette-notification"
    assert item.reliability_score == 95.0


def test_malformed_xml_handling():
    """Verify malformed feed raises ValueError safely without application crash."""
    source = Source(
        id="test-src-3",
        tenant_id="tenant-1",
        name="Broken",
        source_type="OTHER",
        feed_url="https://broken.example.com/rss",
        created_by_user_id="user-1",
    )
    connector = RSSAtomConnector(check_dns=False)

    with pytest.raises(ValueError, match="Malformed XML feed"):
        connector.parse_feed_content(MALFORMED_FEED, source)


def test_strip_html_and_truncate():
    """Verify HTML stripping and non-retention of full bodies."""
    raw_html = (
        "<div><h3>Breaking News</h3><p>First paragraph.</p><script>alert('xss')</script></div>"
    )
    clean = strip_html_and_truncate(raw_html, max_length=25)
    assert clean is not None
    assert "<script>" not in clean
    assert "alert" not in clean
    assert "<p>" not in clean
    assert len(clean) <= 28  # 25 chars + possible '...'


def test_deterministic_fingerprint():
    """Verify identical title and canonical URL yield identical fingerprint."""
    fp1 = compute_item_fingerprint("Expressway Expansion Approved", "https://news.com/art1")
    fp2 = compute_item_fingerprint("expressway expansion approved!", "https://news.com/art1")
    assert fp1 == fp2

    fp3 = compute_item_fingerprint("Completely Different Story", "https://news.com/art2")
    assert fp1 != fp3
