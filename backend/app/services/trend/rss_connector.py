"""Feed and Source Ingestion Abstraction: Safe RSS and Atom Connector."""

import email.utils
import hashlib
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.db.base import utc_now
from app.db.models.source_registry import Source
from app.services.trend.network_safety import (
    CONNECT_TIMEOUT_SECONDS,
    MAX_FEED_PAYLOAD_BYTES,
    READ_TIMEOUT_SECONDS,
    SSRFValidationError,
    sanitize_canonical_url,
    validate_source_url,
)


@dataclass
class NormalizedSourceItem:
    """Normalized source feed item ready for ingestion and deduplication."""

    title: str
    canonical_url: str
    summary: Optional[str]
    publisher: Optional[str]
    published_at: Optional[datetime]
    external_id: Optional[str]
    language: str
    reliability_score: Optional[float]
    rights_metadata: Dict[str, Any]
    raw_metadata: Dict[str, Any]
    fingerprint: str
    fetched_at: datetime = field(default_factory=utc_now)


def compute_item_fingerprint(
    title: str, canonical_url: str, external_id: Optional[str] = None
) -> str:
    """
    Compute a deterministic fingerprint for duplicate detection.
    Normalizes title to lower-case alphanumeric tokens and combines with canonical identity.
    """
    # 1. Normalize title tokens
    clean_title = re.sub(r"[^\w\s]", "", title.lower())
    tokens = sorted(set(clean_title.split()))
    token_str = " ".join(tokens)

    # 2. Prefer canonical URL or external ID
    ext_id = external_id.lower().strip() if external_id else ""
    identifier = canonical_url.lower().strip() or ext_id
    raw_key = f"{token_str}::{identifier}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def strip_html_and_truncate(text: Optional[str], max_length: int = 1000) -> Optional[str]:
    """Strip HTML tags and truncate summary text to avoid retaining full copyrighted bodies."""
    if not text:
        return None
    # Remove script and style tags completely
    cleaned = re.sub(r"<(script|style).*?>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Normalize whitespaces
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip() + "..."
    return cleaned or None


def parse_datetime_flexible(date_str: Optional[str]) -> Optional[datetime]:
    """Parse publication dates safely across RFC 822/2822, ISO 8601, and variations."""
    if not date_str:
        return None
    date_str = date_str.strip()

    # Try RFC 822 / 2822 (standard for RSS)
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    # Try ISO 8601 (standard for Atom)
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    return None


class SourceConnector(ABC):
    """Abstract base connector for ingesting information sources."""

    @abstractmethod
    async def fetch_and_normalize(self, source: Source) -> List[NormalizedSourceItem]:
        """Fetch content from the source and return normalized items."""
        pass


class RSSAtomConnector(SourceConnector):
    """Secure, tenant-isolated RSS 2.0, RSS 1.0, and Atom 1.0 Feed Connector."""

    def __init__(self, check_dns: bool = True):
        self.check_dns = check_dns

    async def fetch_and_normalize(self, source: Source) -> List[NormalizedSourceItem]:
        if not source.feed_url:
            raise ValueError(f"Source '{source.id}' has no feed_url configured.")

        # 1. SSRF and Network Security Validation
        is_safe, error_msg = validate_source_url(source.feed_url, check_dns=self.check_dns)
        if not is_safe:
            raise SSRFValidationError(
                f"SSRF policy blocked feed URL '{source.feed_url}': {error_msg}"
            )

        # 2. Fetch feed with bounded timeouts and safe redirect validation
        headers = {
            "User-Agent": "News9-TrendRadar/1.0 (Editorial Discovery Subsystem)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        }

        from urllib.parse import urljoin
        current_url = source.feed_url
        content_bytes = b""

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=CONNECT_TIMEOUT_SECONDS,
                read=READ_TIMEOUT_SECONDS,
                write=5.0,
                pool=5.0,
            ),
            follow_redirects=False,
        ) as client:
            for _ in range(4):  # max 3 redirects
                is_safe, error_msg = validate_source_url(current_url, check_dns=self.check_dns)
                if not is_safe:
                    raise SSRFValidationError(
                        f"SSRF policy blocked feed URL '{current_url}': {error_msg}"
                    )

                try:
                    response = await client.get(current_url, headers=headers)
                except httpx.HTTPError as exc:
                    err_msg = f"Network error fetching feed '{current_url}': {exc}"
                    raise RuntimeError(err_msg) from exc

                if response.is_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        raise RuntimeError(
                            f"Redirect response from '{current_url}' missing Location header."
                        )
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()
                content_bytes = response.content
                break
            else:
                raise RuntimeError(f"Too many redirects fetching feed '{source.feed_url}'.")

            if len(content_bytes) > MAX_FEED_PAYLOAD_BYTES:
                raise ValueError(
                    f"Feed size ({len(content_bytes)}) exceeds limit of {MAX_FEED_PAYLOAD_BYTES}"
                )

        # 3. Parse XML content safely
        return self.parse_feed_content(content_bytes, source)

    def parse_feed_content(
        self, content_bytes: bytes, source: Source
    ) -> List[NormalizedSourceItem]:
        """Safely parse RSS 2.0, RSS 1.0, or Atom 1.0 XML content."""
        clean_upper = content_bytes.upper()
        if b"<!ENTITY" in clean_upper or b"<!DOCTYPE" in clean_upper:
            raise ValueError(
                "XML DOCTYPE and ENTITY declarations are strictly forbidden to prevent XXE."
            )

        try:
            parser = ET.XMLParser()
            root = ET.fromstring(content_bytes, parser=parser)
        except ET.ParseError as pe:
            raise ValueError(f"Malformed XML feed from '{source.feed_url}': {pe}") from pe

        tag = root.tag.lower()
        items: List[NormalizedSourceItem] = []

        # Determine feed format
        if "feed" in tag:
            # Atom Feed
            items = self._parse_atom_feed(root, source)
        else:
            # RSS (2.0 or 1.0/RDF)
            items = self._parse_rss_feed(root, source)

        return items

    def _parse_rss_feed(self, root: ET.Element, source: Source) -> List[NormalizedSourceItem]:
        items: List[NormalizedSourceItem] = []

        # Detect channel or direct items
        channel = root.find("channel")
        feed_channel_title = channel.findtext("title") if channel is not None else None
        publisher = source.publisher_name or feed_channel_title or "Unknown Publisher"

        # Look for <item> nodes in channel (RSS 2.0) or root (RSS 1.0)
        item_nodes = root.findall(".//item")

        default_rights = {"rights_type": "public_information", "reuse_permitted": False}

        for node in item_nodes:
            title = node.findtext("title")
            if not title:
                continue
            title = title.strip()

            raw_link = node.findtext("link") or ""
            canonical_url = sanitize_canonical_url(raw_link)
            if not canonical_url:
                continue

            summary_text = (
                node.findtext("description")
                or node.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
            )
            clean_summary = strip_html_and_truncate(summary_text)

            guid = node.findtext("guid") or canonical_url
            pub_date_str = (
                node.findtext("pubDate")
                or node.findtext("{http://purl.org/dc/elements/1.1/}date")
            )
            published_at = parse_datetime_flexible(pub_date_str)

            fingerprint = compute_item_fingerprint(title, canonical_url, guid)

            item = NormalizedSourceItem(
                title=title,
                canonical_url=canonical_url,
                summary=clean_summary,
                publisher=publisher,
                published_at=published_at,
                external_id=guid,
                language=source.language,
                reliability_score=source.reliability_score,
                rights_metadata=source.rights_metadata or default_rights,
                raw_metadata={"guid": guid, "feed_url": source.feed_url},
                fingerprint=fingerprint,
                fetched_at=utc_now(),
            )
            items.append(item)

        return items

    def _parse_atom_feed(self, root: ET.Element, source: Source) -> List[NormalizedSourceItem]:
        items: List[NormalizedSourceItem] = []

        # Extract namespace if present
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        feed_title_node = root.find(f"{ns}title")
        feed_title = feed_title_node.text if feed_title_node is not None else None
        publisher = source.publisher_name or feed_title or "Unknown Publisher"

        entry_nodes = root.findall(f"{ns}entry")
        default_rights = {"rights_type": "public_information", "reuse_permitted": False}

        for node in entry_nodes:
            title_node = node.find(f"{ns}title")
            title = title_node.text.strip() if (title_node is not None and title_node.text) else ""
            if not title:
                continue

            # In Atom, link can be <link href="..."/>
            link_node = node.find(f"{ns}link")
            raw_link = ""
            if link_node is not None:
                raw_link = link_node.get("href") or link_node.text or ""
            canonical_url = sanitize_canonical_url(raw_link)
            if not canonical_url:
                continue

            summary_node = node.find(f"{ns}summary")
            content_node = node.find(f"{ns}content")
            sum_text = (
                summary_node.text
                if (summary_node is not None and summary_node.text)
                else None
            )
            cnt_text = (
                content_node.text
                if (content_node is not None and content_node.text)
                else None
            )
            summary_text = sum_text or cnt_text
            clean_summary = strip_html_and_truncate(summary_text)

            id_node = node.find(f"{ns}id")
            if id_node is not None and id_node.text:
                external_id = id_node.text.strip()
            else:
                external_id = canonical_url

            date_str = None
            for date_tag in (f"{ns}published", f"{ns}updated"):
                d_node = node.find(date_tag)
                if d_node is not None and d_node.text:
                    date_str = d_node.text.strip()
                    break

            published_at = parse_datetime_flexible(date_str)
            fingerprint = compute_item_fingerprint(title, canonical_url, external_id)

            item = NormalizedSourceItem(
                title=title,
                canonical_url=canonical_url,
                summary=clean_summary,
                publisher=publisher,
                published_at=published_at,
                external_id=external_id,
                language=source.language,
                reliability_score=source.reliability_score,
                rights_metadata=source.rights_metadata or default_rights,
                raw_metadata={"atom_id": external_id, "feed_url": source.feed_url},
                fingerprint=fingerprint,
                fetched_at=utc_now(),
            )
            items.append(item)

        return items
