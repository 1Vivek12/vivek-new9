"""Deterministic Publication Manifest generator and cryptographic hasher.

Ensures that any human editorial approval binds immutably to the exact canonical
content, media checksums, and platform adaptations. Any change to title, description,
caption, media files, or platform payloads invalidates the manifest hash.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


def compute_manifest_hash(manifest_dict: Dict[str, Any]) -> str:
    """Computes deterministic SHA-256 hash over canonical JSON representation."""
    canonical_json = json.dumps(
        manifest_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def build_publication_manifest(
    *,
    tenant_id: str,
    story_id: str,
    story_version_id: str,
    canonical_title: str,
    canonical_description: str,
    canonical_caption: Optional[str] = None,
    tags: Optional[List[str]] = None,
    media_assets: Optional[List[Dict[str, Any]]] = None,
    platform_payloads: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], str]:
    """Constructs canonical manifest dictionary and its deterministic SHA-256 hash.

    Returns:
        Tuple of (canonical_manifest_dict, sha256_hex_digest).
    """
    sorted_media: List[Dict[str, Any]] = []
    if media_assets:
        for m in media_assets:
            sorted_media.append(
                {
                    "asset_id": str(m.get("asset_id", "")),
                    "asset_type": str(m.get("asset_type", "")),
                    "checksum_sha256": str(m.get("checksum_sha256", "")),
                    "storage_path": str(m.get("storage_path", "")),
                    "duration_seconds": m.get("duration_seconds"),
                    "aspect_ratio": m.get("aspect_ratio"),
                }
            )
        sorted_media.sort(key=lambda item: item["asset_id"])

    sorted_payloads: List[Dict[str, Any]] = []
    if platform_payloads:
        for p in platform_payloads:
            sorted_payloads.append(
                {
                    "destination_type": str(p.get("destination_type", "")).upper(),
                    "account_id": str(p.get("account_id", "")),
                    "adapted_title": p.get("adapted_title") or "",
                    "adapted_description": p.get("adapted_description") or "",
                    "adapted_caption": p.get("adapted_caption") or "",
                    "target_aspect_ratio": p.get("target_aspect_ratio") or "16:9",
                    "selected_derivative_id": str(p.get("selected_derivative_id"))
                    if p.get("selected_derivative_id")
                    else None,
                    "selected_thumbnail_id": str(p.get("selected_thumbnail_id"))
                    if p.get("selected_thumbnail_id")
                    else None,
                    "custom_metadata": p.get("custom_metadata") or {},
                }
            )
        sorted_payloads.sort(key=lambda item: (item["destination_type"], item["account_id"]))

    manifest = {
        "manifest_version": "1.0",
        "tenant_id": str(tenant_id),
        "story_id": str(story_id),
        "story_version_id": str(story_version_id),
        "canonical_title": canonical_title or "",
        "canonical_description": canonical_description or "",
        "canonical_caption": canonical_caption or "",
        "tags": sorted(tags or []),
        "media_assets": sorted_media,
        "platform_payloads": sorted_payloads,
        "metadata": metadata or {},
    }

    manifest_hash = compute_manifest_hash(manifest)
    return manifest, manifest_hash
