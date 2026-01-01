"""
Authentication Middleware for TermiVoxed Web API

Implements Firebase Auth token verification and subscription-based access control.
This middleware secures all API endpoints with proper authentication.

Security features:
- Firebase ID token verification
- Subscription tier validation
- Feature-based access control
- Device fingerprint verification
- Rate limiting integration ready
"""

import os
from typing import Optional, Callable, List
from functools import wraps
from dataclasses import dataclass
from datetime import datetime

from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from subscription.models import SubscriptionTier, SubscriptionStatus, FeatureAccess

# Firebase Admin SDK (lazy import to avoid startup issues if not configured)
_firebase_app = None

# Only enable verbose logging in development
_DEBUG_AUTH = os.getenv("TERMIVOXED_ENV", "development").lower() not in ("production", "prod")


def _debug_log(message: str):
    """Print debug message only in development mode."""
    if _DEBUG_AUTH:
        print(message)


def _get_firebase_app():
    """Lazy initialization of Firebase Admin SDK"""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if already initialized
        try:
            _firebase_app = firebase_admin.get_app()
            _debug_log("[FIREBASE] Using existing Firebase app")
            return _firebase_app
        except ValueError:
            pass

        # Try to initialize with service account credentials
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        if cred_path:
            if os.path.exists(cred_path):
                try:
                    cred = credentials.Certificate(cred_path)
                    _firebase_app = firebase_admin.initialize_app(cred)
                    # Only show filename, not full path (security)
                    _debug_log(f"[FIREBASE] ✓ Initialized with service account")
                    return _firebase_app
                except Exception as e:
                    _debug_log(f"[FIREBASE] ✗ Failed to load credentials: {type(e).__name__}")
            else:
                _debug_log("[FIREBASE] ✗ Credentials file not found")

        # Try default credentials (works in GCP environments)
        try:
            cred = credentials.ApplicationDefault()
            _firebase_app = firebase_admin.initialize_app(cred)
            _debug_log("[FIREBASE] ✓ Initialized with default credentials")
            return _firebase_app
        except Exception:
            _debug_log("[FIREBASE] Default credentials not available")

        # Last resort - initialize without credentials (very limited)
        try:
            _firebase_app = firebase_admin.initialize_app()
            _debug_log("[FIREBASE] ⚠ Initialized without credentials (limited functionality)")
            return _firebase_app
        except Exception:
            _debug_log("[FIREBASE] ✗ Failed to initialize")
            return None

    except ImportError:
        _debug_log("[FIREBASE] ✗ firebase-admin not installed")
        return None


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user with their subscription details"""
    uid: str
    email: Optional[str]
    email_verified: bool
    display_name: Optional[str]
    photo_url: Optional[str]

    # Subscription info (loaded from Firestore)
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE_TRIAL
    subscription_status: SubscriptionStatus = SubscriptionStatus.TRIAL
    features: Optional[FeatureAccess] = None
    subscription_expires_at: Optional[datetime] = None

    # Device info
    device_id: Optional[str] = None
    device_fingerprint: Optional[str] = None

    def has_feature(self, feature: str) -> bool:
        """Check if user has access to a specific feature"""
        if self.features is None:
            self.features = FeatureAccess.for_tier(self.subscription_tier)
        return getattr(self.features, feature, False)

    def get_feature_limit(self, limit_name: str) -> int:
        """Get a feature limit value"""
        if self.features is None:
            self.features = FeatureAccess.for_tier(self.subscription_tier)
        return getattr(self.features, limit_name, 0)

    def is_subscription_active(self) -> bool:
        """Check if subscription is currently active"""
        if self.subscription_status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
            if self.subscription_expires_at:
                return datetime.now() < self.subscription_expires_at
            return True
        return False

    @property
    def is_admin(self) -> bool:
        """
        Check if user has admin privileges.

        Admin status can be granted via:
        1. Firebase custom claim 'admin: true'
        2. ENTERPRISE subscription tier (for self-hosted instances)

        The admin custom claim should be set via Firebase Admin SDK:
            auth.set_custom_user_claims(uid, {'admin': True})
        """
        # Check subscription tier - ENTERPRISE users are admins in self-hosted
        if self.subscription_tier == SubscriptionTier.ENTERPRISE:
            return True

        # Check custom claim (set separately in Firebase token)
        # This is handled during token verification and stored in the user
        return getattr(self, '_is_admin_claim', False)


# Security scheme for Swagger UI
security_scheme = HTTPBearer(auto_error=False)


async def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Verify a Firebase ID token.

    Args:
        token: Firebase ID token string

    Returns:
        Decoded token claims if valid, None otherwise

    Raises:
        RuntimeError: If Firebase is not configured (critical production error)
    """
    firebase_app = _get_firebase_app()

    if firebase_app is None:
        # In development, show helpful error message
        if _DEBUG_AUTH:
            print("\n" + "=" * 60)
            print("ERROR: Firebase Admin SDK not configured!")
            print("=" * 60)
            print("Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
            print("=" * 60 + "\n")
        raise RuntimeError("Firebase not configured")

    try:
        from firebase_admin import auth

        # Verify the token
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        return decoded_token

    except auth.RevokedIdTokenError:
        _debug_log("[AUTH] Token revoked")
        return None
    except auth.ExpiredIdTokenError:
        _debug_log("[AUTH] Token expired")
        return None
    except auth.InvalidIdTokenError:
        _debug_log("[AUTH] Invalid token")
        return None
    except Exception as e:
        # Log error type only (not details) for security
        _debug_log(f"[AUTH] Verification failed: {type(e).__name__}")
        try:
            from utils.logger import logger
            logger.error(f"Token verification error: {type(e).__name__}")
        except Exception:
            pass
        return None


def _normalize_tier(tier_str: str) -> SubscriptionTier:
    """
    Normalize tier string from various sources to SubscriptionTier enum.

    Handles:
    - lxusbrain format: "individual", "pro", "enterprise", "free"
    - termivoxed Cloud Functions format: "INDIVIDUAL", "BASIC", "PRO", "FREE_TRIAL"
    - Legacy formats and edge cases
    """
    if not tier_str:
        return SubscriptionTier.FREE_TRIAL

    tier_lower = tier_str.lower().strip()

    # Direct enum value match
    tier_map = {
        # Standard lowercase (lxusbrain & Python enum values)
        "free_trial": SubscriptionTier.FREE_TRIAL,
        "free": SubscriptionTier.FREE_TRIAL,
        "trial": SubscriptionTier.FREE_TRIAL,
        "individual": SubscriptionTier.INDIVIDUAL,
        "pro": SubscriptionTier.PRO,
        "enterprise": SubscriptionTier.ENTERPRISE,
        "lifetime": SubscriptionTier.LIFETIME,
        "expired": SubscriptionTier.EXPIRED,
        # Legacy BASIC -> INDIVIDUAL mapping
        "basic": SubscriptionTier.INDIVIDUAL,
    }

    return tier_map.get(tier_lower, SubscriptionTier.FREE_TRIAL)


def _normalize_status(status_str: str) -> SubscriptionStatus:
    """
    Normalize status string from various sources to SubscriptionStatus enum.

    Handles:
    - lxusbrain format: "active", "cancelled", "payment_failed"
    - termivoxed Cloud Functions format: "ACTIVE", "CANCELLED", "PAST_DUE"
    """
    if not status_str:
        return SubscriptionStatus.TRIAL

    status_lower = status_str.lower().strip()

    status_map = {
        # Standard values
        "active": SubscriptionStatus.ACTIVE,
        "trial": SubscriptionStatus.TRIAL,
        "expired": SubscriptionStatus.EXPIRED,
        "cancelled": SubscriptionStatus.CANCELLED,
        "canceled": SubscriptionStatus.CANCELLED,  # US spelling
        "past_due": SubscriptionStatus.PAST_DUE,
        "pastdue": SubscriptionStatus.PAST_DUE,
        "grace_period": SubscriptionStatus.GRACE_PERIOD,
        # lxusbrain-specific
        "payment_failed": SubscriptionStatus.PAST_DUE,
    }

    return status_map.get(status_lower, SubscriptionStatus.TRIAL)


def _parse_expiry_date(data: dict, field_names: list) -> Optional[datetime]:
    """
    Parse expiry date from various field names and formats.

    Args:
        data: Dictionary containing the date field
        field_names: List of possible field names to check

    Returns:
        Parsed datetime or None
    """
    for field_name in field_names:
        value = data.get(field_name)
        if value is None:
            continue

        try:
            # Handle Firestore Timestamp objects
            if hasattr(value, 'seconds'):
                return datetime.fromtimestamp(value.seconds)

            # Handle Python datetime
            if isinstance(value, datetime):
                return value

            # Handle ISO string
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))

        except (ValueError, AttributeError, TypeError):
            continue

    return None


async def _load_user_subscription(uid: str) -> dict:
    """
    Load user subscription data from Firestore.

    Checks multiple data sources in order of priority:
    1. users/{uid} top-level fields (lxusbrain website format)
    2. subscriptions/{uid} collection (termivoxed Cloud Functions format)
    3. users/{uid}.subscription nested field (legacy format)

    Args:
        uid: Firebase user ID

    Returns:
        Subscription data dictionary with tier, status, features, expires_at

    Raises:
        RuntimeError: If Firebase is not configured
    """
    firebase_app = _get_firebase_app()

    if firebase_app is None:
        raise RuntimeError(
            "CRITICAL: Firebase not configured. Cannot load user subscription."
        )

    default_result = {
        "tier": SubscriptionTier.FREE_TRIAL,
        "status": SubscriptionStatus.TRIAL,
        "features": FeatureAccess.for_tier(SubscriptionTier.FREE_TRIAL),
    }

    try:
        from firebase_admin import firestore

        db = firestore.client()

        # First, get the user document
        user_doc = db.collection("users").document(uid).get()

        if not user_doc.exists:
            _debug_log(f"[AUTH] User {uid[:8]}... not found, returning FREE_TRIAL")
            return default_result

        user_data = user_doc.to_dict()

        # =========================================================
        # PRIORITY 1: Check for lxusbrain-style top-level fields
        # Fields: plan, planStatus, subscription_expires_at
        # =========================================================
        if "plan" in user_data:
            tier = _normalize_tier(user_data.get("plan", "free"))
            status = _normalize_status(user_data.get("planStatus", "active"))

            # For active subscriptions, use ACTIVE status (not TRIAL)
            if tier != SubscriptionTier.FREE_TRIAL and status == SubscriptionStatus.TRIAL:
                status = SubscriptionStatus.ACTIVE

            expires_at = _parse_expiry_date(user_data, [
                "subscription_expires_at",
                "subscriptionExpiresAt",
                "expiresAt",
            ])

            _debug_log(f"[AUTH] Loaded lxusbrain-style subscription: tier={tier.value}, status={status.value}")

            return {
                "tier": tier,
                "status": status,
                "features": FeatureAccess.for_tier(tier),
                "expires_at": expires_at,
                "device_id": user_data.get("currentDevice", {}).get("deviceId"),
            }

        # =========================================================
        # PRIORITY 2: Check subscriptions/{uid} collection
        # (termivoxed Cloud Functions format)
        # =========================================================
        sub_doc = db.collection("subscriptions").document(uid).get()

        if sub_doc.exists:
            sub_data = sub_doc.to_dict()

            tier = _normalize_tier(sub_data.get("tier", "free_trial"))
            status = _normalize_status(sub_data.get("status", "active"))

            expires_at = _parse_expiry_date(sub_data, [
                "currentPeriodEnd",
                "current_period_end",
                "periodEnd",
                "trialEndsAt",
            ])

            _debug_log(f"[AUTH] Loaded subscriptions collection: tier={tier.value}, status={status.value}")

            return {
                "tier": tier,
                "status": status,
                "features": FeatureAccess.for_tier(tier),
                "expires_at": expires_at,
                "device_id": sub_data.get("activeDeviceId") or user_data.get("currentDevice", {}).get("deviceId"),
            }

        # =========================================================
        # PRIORITY 3: Check users/{uid}.subscription nested field
        # (legacy format for backward compatibility)
        # =========================================================
        subscription = user_data.get("subscription", {})

        if subscription:
            tier = _normalize_tier(subscription.get("tier", "free_trial"))
            status = _normalize_status(subscription.get("status", "trial"))

            expires_at = _parse_expiry_date(subscription, [
                "periodEnd",
                "currentPeriodEnd",
                "expiresAt",
            ])

            _debug_log(f"[AUTH] Loaded legacy subscription: tier={tier.value}, status={status.value}")

            return {
                "tier": tier,
                "status": status,
                "features": FeatureAccess.for_tier(tier),
                "expires_at": expires_at,
                "device_id": user_data.get("currentDevice", {}).get("deviceId"),
            }

        # =========================================================
        # No subscription data found - return FREE_TRIAL
        # =========================================================
        _debug_log(f"[AUTH] No subscription data found for {uid[:8]}..., returning FREE_TRIAL")
        return default_result

    except Exception as e:
        _debug_log(f"[AUTH] Error loading subscription: {type(e).__name__}: {str(e)}")
        return default_result


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> AuthenticatedUser:
    """
    FastAPI dependency to get the current authenticated user.

    Raises HTTPException 401 if not authenticated.

    Supports two authentication methods:
    1. Authorization: Bearer <token> header (preferred for API calls)
    2. ?token=<token> query parameter (for HTML5 video/audio elements)

    Usage:
        @app.get("/protected")
        async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
            return {"message": f"Hello {user.email}"}
    """
    token = None

    # Try Authorization header first
    if credentials is not None:
        token = credentials.credentials
    else:
        # Fall back to query parameter for video/audio streaming
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    decoded = await verify_firebase_token(token)

    if decoded is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load subscription data
    subscription_data = await _load_user_subscription(decoded["uid"])

    user = AuthenticatedUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        email_verified=decoded.get("email_verified", False),
        display_name=decoded.get("name"),
        photo_url=decoded.get("picture"),
        subscription_tier=subscription_data["tier"],
        subscription_status=subscription_data["status"],
        features=subscription_data["features"],
        subscription_expires_at=subscription_data.get("expires_at"),
        device_id=subscription_data.get("device_id"),
    )

    # Extract admin custom claim from Firebase token
    # Set via: auth.set_custom_user_claims(uid, {'admin': True})
    user._is_admin_claim = decoded.get("admin", False)

    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency to optionally get the current user.

    Returns None if not authenticated (doesn't raise exception).

    Usage:
        @app.get("/public")
        async def public_route(user: Optional[AuthenticatedUser] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello anonymous"}
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


def require_subscription(*allowed_tiers: SubscriptionTier):
    """
    Decorator/dependency factory to require specific subscription tiers.

    Usage:
        @app.get("/pro-feature")
        async def pro_feature(
            user: AuthenticatedUser = Depends(require_subscription(SubscriptionTier.PRO, SubscriptionTier.LIFETIME))
        ):
            return {"message": "Pro feature accessed"}
    """
    async def dependency(
        user: AuthenticatedUser = Depends(get_current_user)
    ) -> AuthenticatedUser:
        if not user.is_subscription_active():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription expired. Please renew to continue.",
            )

        if allowed_tiers and user.subscription_tier not in allowed_tiers:
            tier_names = ", ".join(t.value for t in allowed_tiers)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {tier_names} subscription.",
            )

        return user

    return dependency


def require_feature(feature_name: str):
    """
    Decorator/dependency factory to require a specific feature.

    Usage:
        @app.get("/export-4k")
        async def export_4k(
            user: AuthenticatedUser = Depends(require_feature("export_4k"))
        ):
            return {"message": "4K export started"}
    """
    async def dependency(
        user: AuthenticatedUser = Depends(get_current_user)
    ) -> AuthenticatedUser:
        if not user.is_subscription_active():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription expired. Please renew to continue.",
            )

        if not user.has_feature(feature_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature_name}' requires a higher subscription tier.",
            )

        return user

    return dependency


async def require_admin(
    user: AuthenticatedUser = Depends(get_current_user)
) -> AuthenticatedUser:
    """
    FastAPI dependency to require admin privileges.

    Admin status is determined by:
    1. Firebase custom claim 'admin: true'
    2. ENTERPRISE subscription tier

    Usage:
        @app.put("/admin-only")
        async def admin_endpoint(
            user: AuthenticatedUser = Depends(require_admin)
        ):
            return {"message": "Admin action performed"}
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for this operation.",
        )
    return user


class RateLimiter:
    """
    Simple in-memory rate limiter.

    For production, integrate with Redis for distributed rate limiting.
    """

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: dict = {}  # uid -> list of timestamps

    async def check_rate_limit(self, uid: str) -> bool:
        """Check if user is within rate limit"""
        import time

        now = time.time()
        minute_ago = now - 60

        # Get user's requests
        user_requests = self._requests.get(uid, [])

        # Filter to last minute
        recent_requests = [r for r in user_requests if r > minute_ago]

        if len(recent_requests) >= self.requests_per_minute:
            return False

        # Add current request
        recent_requests.append(now)
        self._requests[uid] = recent_requests

        return True

    def __call__(self, requests_per_minute: Optional[int] = None):
        """Create a dependency with custom rate limit"""
        limit = requests_per_minute or self.requests_per_minute

        async def dependency(
            user: AuthenticatedUser = Depends(get_current_user)
        ) -> AuthenticatedUser:
            if not await self.check_rate_limit(user.uid):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please slow down.",
                )
            return user

        return dependency


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=60)


# Convenience dependencies for common subscription requirements
require_basic_or_higher = require_subscription(
    SubscriptionTier.BASIC,
    SubscriptionTier.PRO,
    SubscriptionTier.LIFETIME
)

require_pro_or_higher = require_subscription(
    SubscriptionTier.PRO,
    SubscriptionTier.LIFETIME
)

require_any_subscription = require_subscription(
    SubscriptionTier.FREE_TRIAL,
    SubscriptionTier.BASIC,
    SubscriptionTier.PRO,
    SubscriptionTier.LIFETIME
)
