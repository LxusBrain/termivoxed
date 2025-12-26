"""
TermiVoxed API Middleware

Authentication, rate limiting, and security middleware for the FastAPI application.
"""

from .auth import (
    get_current_user,
    get_current_user_optional,
    require_subscription,
    require_feature,
    verify_firebase_token,
    AuthenticatedUser,
)

from .rate_limit import (
    RateLimitMiddleware,
    rate_limiter,
    rate_limit,
)

__all__ = [
    # Auth
    "get_current_user",
    "get_current_user_optional",
    "require_subscription",
    "require_feature",
    "verify_firebase_token",
    "AuthenticatedUser",
    # Rate limiting
    "RateLimitMiddleware",
    "rate_limiter",
    "rate_limit",
]
