"""Pre-publish validation pipeline.

Executes comprehensive pre-flight verification across story state, media assets,
rights clearance, destination account health, platform-specific technical constraints,
and editorial policies before any package can be approved or dispatched.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.db.models.publishing import DestinationType
from app.services.publishing.rights_guard import (
    PublishingRightsViolationError,
    validate_media_rights_for_publishing,
)


class ValidationIssue(BaseModel):
    category: str  # "STORY", "MEDIA", "RIGHTS", "ACCOUNT", "PLATFORM", "POLICY"
    severity: str  # "ERROR", "WARNING"
    field: Optional[str] = None
    destination_type: Optional[str] = None
    message: str


class ValidationResult(BaseModel):
    is_valid: bool
    issues: List[ValidationIssue] = Field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "WARNING")


class PrePublishValidator:
    """Performs pre-flight checks against publication packages and platform payloads."""

    E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")

    def __init__(self):
        self.settings = get_settings()

    def validate_package(
        self,
        *,
        canonical_title: str,
        canonical_description: str,
        media_assets: List[Dict[str, Any]],
        platform_payloads: List[Dict[str, Any]],
        account_status_map: Optional[Dict[str, str]] = None,
    ) -> ValidationResult:
        issues: List[ValidationIssue] = []

        # 1. Core Content Checks
        if not canonical_title or not canonical_title.strip():
            issues.append(
                ValidationIssue(
                    category="STORY",
                    severity="ERROR",
                    field="canonical_title",
                    message="Publication package must have a non-empty canonical title.",
                )
            )

        if not platform_payloads:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    message="Publication package must have at least one target platform payload.",
                )
            )

        # 2. Rights & Media Checks
        try:
            validate_media_rights_for_publishing(media_assets)
        except PublishingRightsViolationError as exc:
            issues.append(
                ValidationIssue(
                    category="RIGHTS",
                    severity="ERROR",
                    field="media_assets",
                    message=str(exc),
                )
            )

        # 3. Account Health Checks
        if account_status_map:
            for payload in platform_payloads:
                acc_id = payload.get("account_id")
                dest_type = payload.get("destination_type", "UNKNOWN")
                status = account_status_map.get(str(acc_id))
                if status and status != "CONNECTED":
                    issues.append(
                        ValidationIssue(
                            category="ACCOUNT",
                            severity="ERROR",
                            destination_type=dest_type,
                            message=(
                                f"Connected account '{acc_id}' for destination '{dest_type}' "
                                f"is not CONNECTED (status: {status})."
                            ),
                        )
                    )

        # 4. Platform-Specific Constraints
        for payload in platform_payloads:
            dest_type = (payload.get("destination_type") or "").upper()
            title = payload.get("adapted_title") or canonical_title or ""
            p_desc = payload.get("adapted_description") or canonical_description or ""
            p_caption = payload.get("adapted_caption") or ""
            target_aspect_ratio = payload.get("target_aspect_ratio") or "16:9"
            custom = payload.get("custom_metadata") or {}

            if dest_type == DestinationType.YOUTUBE.value:
                self._validate_youtube(title, p_desc, media_assets, custom, issues)
            elif dest_type == DestinationType.FACEBOOK.value:
                self._validate_facebook(title, p_desc or p_caption, issues)
            elif dest_type == DestinationType.INSTAGRAM.value:
                self._validate_instagram(
                    p_caption or p_desc, target_aspect_ratio, media_assets, custom, issues
                )
            elif dest_type == DestinationType.WHATSAPP.value:
                self._validate_whatsapp(p_desc or p_caption or title, custom, issues)
            elif dest_type == DestinationType.WEBSITE.value:
                self._validate_website(title, p_desc, custom, issues)

        is_valid = not any(i.severity == "ERROR" for i in issues)
        return ValidationResult(is_valid=is_valid, issues=issues)

    def _validate_youtube(
        self,
        title: str,
        description: str,
        media_assets: List[Dict[str, Any]],
        custom: Dict[str, Any],
        issues: List[ValidationIssue],
    ):
        if len(title) > 100:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="YOUTUBE",
                    field="adapted_title",
                    message=(
                        f"YouTube title exceeds maximum allowed length of 100 characters "
                        f"(got {len(title)})."
                    ),
                )
            )

        if len(description) > 5000:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="YOUTUBE",
                    field="adapted_description",
                    message=(
                        f"YouTube description exceeds maximum allowed length of 5000 characters "
                        f"(got {len(description)})."
                    ),
                )
            )

        if not media_assets:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="YOUTUBE",
                    field="media_assets",
                    message="YouTube publication requires at least one video asset.",
                )
            )

        # Check Shorts limits if flagged as short
        is_short = custom.get("is_short", False)
        if is_short:
            max_short_sec = getattr(
                self.settings, "NEWS9_YOUTUBE_SHORTS_EDITORIAL_MAX_SECONDS", 180
            )
            for m in media_assets:
                duration = m.get("duration_seconds")
                if duration and duration > max_short_sec:
                    issues.append(
                        ValidationIssue(
                            category="POLICY",
                            severity="ERROR",
                            destination_type="YOUTUBE",
                            field="duration_seconds",
                            message=(
                                f"YouTube Short duration ({duration:.1f}s) exceeds editorial "
                                f"ceiling of {max_short_sec}s."
                            ),
                        )
                    )

    def _validate_facebook(
        self,
        title: str,
        body: str,
        issues: List[ValidationIssue],
    ):
        if len(title) > 255:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="FACEBOOK",
                    field="adapted_title",
                    message="Facebook video title cannot exceed 255 characters.",
                )
            )
        if len(body) > 63206:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="FACEBOOK",
                    field="adapted_description",
                    message="Facebook post message cannot exceed 63,206 characters.",
                )
            )

    def _validate_instagram(
        self,
        caption: str,
        aspect_ratio: str,
        media_assets: List[Dict[str, Any]],
        custom: Dict[str, Any],
        issues: List[ValidationIssue],
    ):
        if len(caption) > 2200:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="INSTAGRAM",
                    field="adapted_caption",
                    message=(
                        f"Instagram caption exceeds maximum length of 2,200 characters "
                        f"(got {len(caption)})."
                    ),
                )
            )

        if not media_assets:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="INSTAGRAM",
                    field="media_assets",
                    message="Instagram publication requires media (image or video).",
                )
            )

        is_reel = custom.get("is_reel", True)
        if is_reel:
            max_reel_sec = getattr(self.settings, "NEWS9_INSTAGRAM_EDITORIAL_MAX_SECONDS", 90)
            for m in media_assets:
                duration = m.get("duration_seconds")
                if duration and duration > max_reel_sec:
                    issues.append(
                        ValidationIssue(
                            category="POLICY",
                            severity="ERROR",
                            destination_type="INSTAGRAM",
                            field="duration_seconds",
                            message=(
                                f"Instagram Reel duration ({duration:.1f}s) exceeds editorial "
                                f"ceiling of {max_reel_sec}s."
                            ),
                        )
                    )

    def _validate_whatsapp(
        self,
        body: str,
        custom: Dict[str, Any],
        issues: List[ValidationIssue],
    ):
        recipients = custom.get("recipients", [])
        if not recipients:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="WHATSAPP",
                    field="recipients",
                    message="WhatsApp dispatch requires at least one recipient phone number.",
                )
            )
        else:
            for r in recipients:
                phone = str(r).strip()
                if not self.E164_REGEX.match(phone):
                    issues.append(
                        ValidationIssue(
                            category="PLATFORM",
                            severity="ERROR",
                            destination_type="WHATSAPP",
                            field="recipients",
                            message=(
                                f"WhatsApp recipient '{phone}' is not in valid E.164 "
                                f"international format (e.g. +1234567890)."
                            ),
                        )
                    )

        if len(body) > 4096:
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="WHATSAPP",
                    field="body",
                    message="WhatsApp message body cannot exceed 4,096 characters.",
                )
            )

    def _validate_website(
        self,
        title: str,
        body: str,
        custom: Dict[str, Any],
        issues: List[ValidationIssue],
    ):
        if not title or not title.strip():
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="WEBSITE",
                    field="adapted_title",
                    message="Website article requires a valid title.",
                )
            )
        if not body or not body.strip():
            issues.append(
                ValidationIssue(
                    category="PLATFORM",
                    severity="ERROR",
                    destination_type="WEBSITE",
                    field="adapted_description",
                    message="Website article requires body content.",
                )
            )
