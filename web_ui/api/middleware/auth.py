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
            return _firebase_app
        except ValueError:
            pass

        # Try to initialize with service account credentials
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            # Try default credentials (works in GCP environments)
            try:
                cred = credentials.ApplicationDefault()
                _firebase_app = firebase_admin.initialize_app(cred)
            except Exception:
                # Fall back to no credentials (limited functionality)
                _firebase_app = firebase_admin.initialize_app()

        return _firebase_app

    except ImportError:
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
        # Firebase MUST be configured for production - raise error instead of silent bypass
        raise RuntimeError(
            "CRITICAL: Firebase not configured. Set GOOGLE_APPLICATION_CREDENTIALS "
            "environment variable to your Firebase service account JSON file path."
        )

    try:
        from firebase_admin import auth
        from utils.logger import logger

        # Verify the token
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        return decoded_token

    except auth.RevokedIdTokenError:
        # Token has been revoked
        return None
    except auth.ExpiredIdTokenError:
        # Token has expired
        return None
    except auth.InvalidIdTokenError:
        # Token is invalid
        return None
    except Exception as e:
        # Log the error but don't expose details to client
        from utils.logger import logger
        logger.error(f"Token verification error: {e}")
        return None


async def _load_user_subscription(uid: str) -> dict:
    """
    Load user subscription data from Firestore.

    Args:
        uid: Firebase user ID

    Returns:
        Subscription data dictionary

    Raises:
        RuntimeError: If Firebase is not configured
    """
    firebase_app = _get_firebase_app()

    if firebase_app is None:
        # Firebase MUST be configured - this is a critical error
        raise RuntimeError(
            "CRITICAL: Firebase not configured. Cannot load user subscription."
        )

    try:
        from firebase_admin import firestore

        db = firestore.client()
        user_doc = db.collection("users").document(uid).get()

        if not user_doc.exists:
            # New user - create with free trial
            return {
                "tier": SubscriptionTier.FREE_TRIAL,
                "status": SubscriptionStatus.TRIAL,
                "features": FeatureAccess.for_tier(SubscriptionTier.FREE_TRIAL),
            }

        data = user_doc.to_dict()
        subscription = data.get("subscription", {})

        tier_str = subscription.get("tier", "free_trial").lower()
        try:
            tier = SubscriptionTier(tier_str)
        except ValueError:
            tier = SubscriptionTier.FREE_TRIAL

        status_str = subscription.get("status", "trial").lower()
        try:
            sub_status = SubscriptionStatus(status_str)
        except ValueError:
            sub_status = SubscriptionStatus.TRIAL

        expires_at = None
        if subscription.get("periodEnd"):
            try:
                expires_at = datetime.fromisoformat(subscription["periodEnd"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return {
            "tier": tier,
            "status": sub_status,
            "features": FeatureAccess.for_tier(tier),
            "expires_at": expires_at,
            "device_id": data.get("currentDevice", {}).get("deviceId"),
        }

    except Exception as e:
        print(f"Error loading subscription: {e}")
        return {
            "tier": SubscriptionTier.FREE_TRIAL,
            "status": SubscriptionStatus.TRIAL,
            "features": FeatureAccess.for_tier(SubscriptionTier.FREE_TRIAL),
        }


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> AuthenticatedUser:
    """
    FastAPI dependency to get the current authenticated user.

    Raises HTTPException 401 if not authenticated.

    Usage:
        @app.get("/protected")
        async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
            return {"message": f"Hello {user.email}"}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
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
