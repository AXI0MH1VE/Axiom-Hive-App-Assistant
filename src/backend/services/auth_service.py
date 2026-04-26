"""
Auth Service: Optional API key and rate limiting enforcement.
Designed for programmatic access, not full user accounts.
"""

import logging
import time
from typing import Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import secrets

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter per API key or IP address.
    """

    def __init__(
        self,
        enabled: bool = True,
        requests_per_minute: int = 100,
        burst_limit: int = 10,
    ):
        self.enabled = enabled
        self.rpm = requests_per_minute
        self.burst = burst_limit
        self.buckets: Dict[str, dict] = defaultdict(lambda: {"tokens": burst_limit, "last_update": time.time()})

    def consume(self, key: str) -> Tuple[bool, int]:
        """
        Attempt to consume one token from key's bucket.

        Returns:
            (allowed, remaining_tokens)
        """
        if not self.enabled:
            return True, self.burst

        bucket = self.buckets[key]
        now = time.time()
        elapsed = now - bucket["last_update"]

        # Refill tokens (rate = rpm / 60 per second)
        refill_rate = self.rpm / 60.0
        new_tokens = elapsed * refill_rate
        bucket["tokens"] = min(self.burst, bucket["tokens"] + new_tokens)
        bucket["last_update"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True, int(bucket["tokens"])
        else:
            return False, int(bucket["tokens"])


class AuthService:
    """
    Simple API key authentication and rate limiting.
    No user accounts; keys are opaque tokens issued by admin.
    """

    def __init__(
        self,
        api_key_required: bool = False,
        valid_keys: Optional[set] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Args:
            api_key_required: If True, reject requests without X-API-Key header
            valid_keys: Set of known API keys (or load from DB)
            rate_limiter: RateLimiter instance
        """
        self.api_key_required = api_key_required
        self.valid_keys = valid_keys or set()
        self.rate_limiter = rate_limiter or RateLimiter(enabled=True)

        self.usage_log: list = []  # For audit

    def validate_request(
        self,
        api_key: Optional[str],
        client_ip: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Validate incoming request.

        Returns:
            (is_authorized, reason_if_not)
        """
        if self.api_key_required:
            if not api_key:
                return False, "API key required"
            if api_key not in self.valid_keys:
                return False, "Invalid API key"

        # Apply rate limiting per key or IP
        limiter_key = api_key or (client_ip or "anonymous")
        allowed, remaining = self.rate_limiter.consume(limiter_key)

        self.usage_log.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "key": api_key,
                "ip": client_ip,
                "allowed": allowed,
                "remaining_tokens": remaining,
            }
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for {limiter_key}")
            return False, "Rate limit exceeded"

        return True, "OK"

    def add_key(self, key: Optional[str] = None) -> str:
        """
        Add a new valid API key.

        Args:
            key: Specific key to add (otherwise generate)

        Returns:
            The API key
        """
        if key is None:
            key = secrets.token_urlsafe(32)
        self.valid_keys.add(key)
        logger.info(f"Added API key: {key[:8]}...")
        return key

    def revoke_key(self, key: str) -> bool:
        """Revoke an API key."""
        if key in self.valid_keys:
            self.valid_keys.remove(key)
            logger.info(f"Revoked API key: {key[:8]}...")
            return True
        return False

    def generate_key_pair(
        self,
        label: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        Generate new API key with metadata.

        Returns:
            {"key": "...", "label": "...", "expires": "..."}
        """
        key = secrets.token_urlsafe(32)
        record = {
            "key_prefix": key[:8],
            "label": label or "unnamed",
            "created": datetime.utcnow().isoformat() + "Z",
            "expires": (
                (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat() + "Z"
                if expires_in_days
                else None
            ),
        }
        self.valid_keys.add(key)

        self.usage_log.append(
            {"event": "key_created", "key_prefix": key[:8], "record": record}
        )

        return {"key": key, **record}
