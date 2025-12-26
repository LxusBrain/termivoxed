"""
Rate Limiting Middleware for TermiVoxed Web API

Implements sliding window rate limiting to prevent API abuse.
Different limits for different endpoint categories and subscription tiers.

For production, consider using Redis for distributed rate limiting.
"""

import time
import logging
from typing import Optional, Dict, Callable
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from subscription.models import SubscriptionTier

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 20  # Max requests in 10 seconds


# Tier-based rate limits
TIER_LIMITS: Dict[str, RateLimitConfig] = {
    "anonymous": RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=300,
        burst_limit=10,
    ),
    "free_trial": RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=600,
        burst_limit=15,
    ),
    "basic": RateLimitConfig(
        requests_per_minute=120,
        requests_per_hour=2000,
        burst_limit=30,
    ),
    "pro": RateLimitConfig(
        requests_per_minute=300,
        requests_per_hour=5000,
        burst_limit=50,
    ),
    "lifetime": RateLimitConfig(
        requests_per_minute=300,
        requests_per_hour=5000,
        burst_limit=50,
    ),
    "enterprise": RateLimitConfig(
        requests_per_minute=1000,
        requests_per_hour=20000,
        burst_limit=100,
    ),
}

# Endpoint-specific limits (override tier limits)
ENDPOINT_LIMITS: Dict[str, RateLimitConfig] = {
    # Expensive operations
    "/api/v1/export/start": RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=50,
        burst_limit=2,
    ),
    "/api/v1/tts/generate": RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=300,
        burst_limit=10,
    ),
    "/api/v1/tts/clone-voice": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_limit=3,
    ),
    "/api/v1/llm/generate-script": RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=200,
        burst_limit=5,
    ),
    "/api/v1/llm/intelligent-auto-segment": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_limit=3,
    ),
    # Auth endpoints (prevent brute force)
    "/api/v1/auth/login": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=50,
        burst_limit=5,
    ),
    # Webhook endpoints (no limit - called by payment providers)
    "/api/v1/payments/webhooks/stripe": RateLimitConfig(
        requests_per_minute=1000,
        requests_per_hour=10000,
        burst_limit=100,
    ),
    "/api/v1/payments/webhooks/razorpay": RateLimitConfig(
        requests_per_minute=1000,
        requests_per_hour=10000,
        burst_limit=100,
    ),
}

# Paths to skip rate limiting
SKIP_PATHS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


@dataclass
class RateLimitState:
    """Track rate limit state for a single key"""
    minute_requests: list = field(default_factory=list)
    hour_requests: list = field(default_factory=list)
    burst_requests: list = field(default_factory=list)

    def cleanup(self, now: float):
        """Remove expired entries"""
        minute_ago = now - 60
        hour_ago = now - 3600
        burst_window = now - 10

        self.minute_requests = [t for t in self.minute_requests if t > minute_ago]
        self.hour_requests = [t for t in self.hour_requests if t > hour_ago]
        self.burst_requests = [t for t in self.burst_requests if t > burst_window]

    def add_request(self, now: float):
        """Record a new request"""
        self.minute_requests.append(now)
        self.hour_requests.append(now)
        self.burst_requests.append(now)

    def check_limit(self, config: RateLimitConfig) -> tuple[bool, str, int]:
        """
        Check if rate limit is exceeded.

        Returns: (is_allowed, limit_type, retry_after_seconds)
        """
        if len(self.burst_requests) >= config.burst_limit:
            return False, "burst", 10

        if len(self.minute_requests) >= config.requests_per_minute:
            return False, "minute", 60

        if len(self.hour_requests) >= config.requests_per_hour:
            return False, "hour", 3600

        return True, "", 0


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    For production with multiple server instances, replace with Redis-based implementation.
    """

    def __init__(self):
        self._state: Dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Cleanup every 5 minutes

    def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate rate limit key"""
        return f"{identifier}:{endpoint}"

    def _periodic_cleanup(self, now: float):
        """Periodically clean up expired entries to prevent memory growth"""
        if now - self._last_cleanup > self._cleanup_interval:
            keys_to_remove = []
            for key, state in self._state.items():
                state.cleanup(now)
                # Remove empty states
                if not state.minute_requests and not state.hour_requests:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._state[key]

            self._last_cleanup = now

    def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        tier: str = "anonymous"
    ) -> tuple[bool, Optional[str], int, Dict[str, int]]:
        """
        Check if request is allowed under rate limits.

        Args:
            identifier: User ID or IP address
            endpoint: API endpoint path
            tier: Subscription tier

        Returns:
            (is_allowed, limit_type, retry_after, headers)
        """
        now = time.time()
        self._periodic_cleanup(now)

        # Get config - endpoint-specific overrides tier config
        if endpoint in ENDPOINT_LIMITS:
            config = ENDPOINT_LIMITS[endpoint]
        else:
            config = TIER_LIMITS.get(tier, TIER_LIMITS["anonymous"])

        # Get or create state for this key
        key = self._get_key(identifier, endpoint)
        state = self._state[key]
        state.cleanup(now)

        # Check limits
        is_allowed, limit_type, retry_after = state.check_limit(config)

        # Calculate headers
        headers = {
            "X-RateLimit-Limit-Minute": config.requests_per_minute,
            "X-RateLimit-Remaining-Minute": max(0, config.requests_per_minute - len(state.minute_requests)),
            "X-RateLimit-Limit-Hour": config.requests_per_hour,
            "X-RateLimit-Remaining-Hour": max(0, config.requests_per_hour - len(state.hour_requests)),
        }

        if is_allowed:
            state.add_request(now)

        return is_allowed, limit_type, retry_after, headers


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_client_identifier(request: Request) -> tuple[str, str]:
    """
    Get client identifier and tier from request.

    Returns: (identifier, tier)
    """
    # Try to get user from request state (set by auth middleware)
    user = getattr(request.state, "user", None)

    if user:
        tier = getattr(user, "subscription_tier", SubscriptionTier.FREE_TRIAL)
        if hasattr(tier, "value"):
            tier = tier.value
        return user.uid, str(tier)

    # Fall back to IP address for anonymous users
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")

    return ip, "anonymous"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Applies rate limits based on:
    - User subscription tier (for authenticated users)
    - IP address (for anonymous users)
    - Endpoint-specific limits for expensive operations
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip rate limiting for certain paths
        if path in SKIP_PATHS or path.startswith("/storage/"):
            return await call_next(request)

        # Get client identifier and tier
        identifier, tier = get_client_identifier(request)

        # Normalize endpoint path (remove trailing slashes, path parameters)
        endpoint = self._normalize_endpoint(path)

        # Check rate limit
        is_allowed, limit_type, retry_after, headers = rate_limiter.check_rate_limit(
            identifier, endpoint, tier
        )

        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded: {identifier} on {endpoint} ({limit_type} limit)"
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded ({limit_type}). Please slow down.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    **{k: str(v) for k, v in headers.items()},
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = str(value)

        return response

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for rate limiting"""
        # Remove trailing slash
        path = path.rstrip("/")

        # Replace path parameters with placeholders
        parts = path.split("/")
        normalized = []

        for i, part in enumerate(parts):
            # Check if this looks like a UUID or ID
            if self._looks_like_id(part):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)

    def _looks_like_id(self, part: str) -> bool:
        """Check if a path part looks like an ID"""
        if not part:
            return False

        # UUID pattern
        if len(part) == 36 and part.count("-") == 4:
            return True

        # Short UUID (8 chars)
        if len(part) == 8 and all(c.isalnum() for c in part):
            return True

        # Numeric ID
        if part.isdigit():
            return True

        return False


def rate_limit(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_limit: int = 20,
):
    """
    Decorator for custom rate limiting on specific endpoints.

    Usage:
        @router.post("/expensive-operation")
        @rate_limit(requests_per_minute=5, requests_per_hour=50)
        async def expensive_operation():
            ...
    """
    config = RateLimitConfig(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        burst_limit=burst_limit,
    )

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            if request is None:
                # Try to find request in args
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                identifier, tier = get_client_identifier(request)
                endpoint = request.url.path

                # Use custom config instead of default
                key = rate_limiter._get_key(identifier, endpoint)
                state = rate_limiter._state[key]
                now = time.time()
                state.cleanup(now)

                is_allowed, limit_type, retry_after = state.check_limit(config)

                if not is_allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded ({limit_type}). Please slow down.",
                        headers={"Retry-After": str(retry_after)},
                    )

                state.add_request(now)

            return await func(*args, **kwargs)

        return wrapper

    return decorator
