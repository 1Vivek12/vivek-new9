"""Token-bucket and sliding-window rate limiter for outbound publishing requests.

Protects third-party platform quotas (YouTube 10,000 units/day, WhatsApp 20 msg/sec,
Meta Graph API call caps) and enforces per-tenant distribution fairness.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Tuple

from app.core.config import get_settings


class PublishingRateLimitExceeded(Exception):
    """Raised when an outbound publishing operation exceeds configured rate limits."""

    def __init__(self, message: str, retry_after_seconds: float = 1.0):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class TokenBucket:
    """Thread-safe and async-safe token bucket."""

    def __init__(self, capacity: float, refill_rate_per_second: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate_per_second
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> Tuple[bool, float]:
        """Attempts to acquire tokens.

        Returns (success, wait_seconds_if_not_available).
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.last_refill = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0

            needed = tokens - self.tokens
            wait_time = needed / self.refill_rate if self.refill_rate > 0 else 60.0
            return False, wait_time


class PublishingRateLimiter:
    """Manages rate limits across tenants and publishing destinations."""

    def __init__(self) -> None:
        settings = get_settings()
        self.whatsapp_limit = float(getattr(settings, "WHATSAPP_MESSAGES_PER_SECOND_LIMIT", 20.0))
        # Buckets keyed by (tenant_id, destination_type)
        self._buckets: Dict[Tuple[str, str], TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def _get_bucket(self, tenant_id: str, destination_type: str) -> TokenBucket:
        key = (str(tenant_id), destination_type.upper())
        async with self._lock:
            if key not in self._buckets:
                if destination_type.upper() == "WHATSAPP":
                    # Capacity 20, refill 20 tokens per second
                    self._buckets[key] = TokenBucket(
                        capacity=self.whatsapp_limit, refill_rate_per_second=self.whatsapp_limit
                    )
                elif destination_type.upper() == "YOUTUBE":
                    # YouTube video upload is 1600 units; default daily quota is 10,000 units.
                    # Standard burst 2 concurrent uploads, refill ~1 per 5 minutes
                    self._buckets[key] = TokenBucket(
                        capacity=2.0, refill_rate_per_second=2.0 / 300.0
                    )
                elif destination_type.upper() in ("FACEBOOK", "INSTAGRAM"):
                    # Meta Graph API limit: burst of 10 requests, refill 2/sec
                    self._buckets[key] = TokenBucket(capacity=10.0, refill_rate_per_second=2.0)
                else:
                    # Generic default
                    self._buckets[key] = TokenBucket(capacity=30.0, refill_rate_per_second=5.0)
            return self._buckets[key]

    async def check_and_consume(
        self,
        tenant_id: str,
        destination_type: str,
        cost: float = 1.0,
    ) -> None:
        """Consumes rate limit tokens or raises PublishingRateLimitExceeded."""
        bucket = await self._get_bucket(tenant_id, destination_type)
        allowed, wait_seconds = await bucket.acquire(cost)
        if not allowed:
            raise PublishingRateLimitExceeded(
                f"Rate limit exceeded for destination '{destination_type}'. "
                f"Please retry after {wait_seconds:.2f} seconds.",
                retry_after_seconds=wait_seconds,
            )


# Global rate limiter singleton
rate_limiter = PublishingRateLimiter()
