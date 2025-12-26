"""
Subscription Routes - API endpoints for subscription management

These endpoints integrate the subscription system with the web UI.
SECURITY: Usage tracking endpoints require authentication.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional

from subscription.license_manager import get_license_manager
from subscription.feature_gate import FeatureGate
from subscription.models import SubscriptionTier, FeatureAccess, PRICING
from subscription.usage_tracker import get_usage_tracker, UsageType
from web_ui.api.middleware.auth import get_current_user, AuthenticatedUser


router = APIRouter(prefix="/subscription", tags=["subscription"])


# ========== Pydantic Models ==========

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[dict] = None
    subscription: Optional[dict] = None


class SubscriptionStatusResponse(BaseModel):
    is_licensed: bool
    is_logged_in: bool
    user_email: Optional[str]
    tier: str
    tier_display: str
    status_message: str
    features: dict
    needs_refresh: bool


class FeatureCheckResponse(BaseModel):
    has_feature: bool
    feature_name: str
    upgrade_message: Optional[str] = None


class LimitCheckResponse(BaseModel):
    can_proceed: bool
    limit_name: str
    current_value: int
    max_value: int
    error_message: Optional[str] = None


# ========== Routes ==========

@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status():
    """
    Get current subscription status.

    Returns comprehensive subscription info for the UI.
    """
    license_manager = get_license_manager()

    is_licensed = license_manager.is_licensed()
    tier = license_manager.get_subscription_tier()
    features = license_manager.get_features()
    user_email = license_manager.get_user_email()
    status_message = license_manager.get_subscription_status()

    return SubscriptionStatusResponse(
        is_licensed=is_licensed,
        is_logged_in=user_email is not None,
        user_email=user_email,
        tier=tier.value,
        tier_display=tier.value.replace('_', ' ').title(),
        status_message=status_message,
        features=features.to_dict(),
        needs_refresh=license_manager.needs_online_check()
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login to activate subscription on this device.

    Implements single-device enforcement.
    """
    license_manager = get_license_manager()

    success, message = await license_manager.login(
        email=request.email,
        password=request.password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": message}
        )

    tier = license_manager.get_subscription_tier()
    features = license_manager.get_features()

    return LoginResponse(
        success=True,
        message=message,
        user={
            "email": request.email
        },
        subscription={
            "tier": tier.value,
            "features": features.to_dict()
        }
    )


@router.post("/logout")
async def logout():
    """
    Logout from this device.

    Clears local license cache and notifies cloud.
    """
    license_manager = get_license_manager()
    success, message = await license_manager.logout()

    return {"success": success, "message": message}


@router.post("/force-logout-others")
async def force_logout_others():
    """
    Force logout from all other devices.

    Keeps current device logged in.
    """
    license_manager = get_license_manager()
    success, message = await license_manager.force_logout_other_devices()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": message}
        )

    return {"success": success, "message": message}


@router.post("/verify")
async def verify_license():
    """
    Verify license with cloud server.

    Called periodically to refresh license token.
    """
    license_manager = get_license_manager()
    success, message = await license_manager.verify_license_online()

    return {
        "success": success,
        "message": message,
        "is_licensed": license_manager.is_licensed()
    }


@router.get("/features")
async def get_features():
    """
    Get all available features for current subscription.
    """
    features = FeatureGate.get_features()
    return features.to_dict()


@router.get("/feature/{feature_name}", response_model=FeatureCheckResponse)
async def check_feature(feature_name: str):
    """
    Check if a specific feature is available.
    """
    has_feature = FeatureGate.has_feature(feature_name)

    response = FeatureCheckResponse(
        has_feature=has_feature,
        feature_name=feature_name
    )

    if not has_feature:
        response.upgrade_message = FeatureGate.get_upgrade_message(feature_name)

    return response


@router.get("/limit/{limit_name}/{current_value}", response_model=LimitCheckResponse)
async def check_limit(limit_name: str, current_value: int):
    """
    Check if a limit would be exceeded.
    """
    features = FeatureGate.get_features()
    max_value = getattr(features, limit_name, 999)

    can_proceed, error_message = FeatureGate.check_limit(limit_name, current_value)

    return LimitCheckResponse(
        can_proceed=can_proceed,
        limit_name=limit_name,
        current_value=current_value,
        max_value=max_value,
        error_message=error_message
    )


@router.get("/pricing")
async def get_pricing():
    """
    Get subscription pricing information.
    """
    pricing_info = {}

    for tier, info in PRICING.items():
        features = FeatureAccess.for_tier(tier)
        pricing_info[tier.value] = {
            **info,
            "features": FeatureGate.get_available_features_for_tier(tier)
        }

    return pricing_info


@router.get("/tiers")
async def get_tiers():
    """
    Get subscription tier comparison with India-focused pricing.
    """
    return {
        "free_trial": {
            "name": "Free Trial",
            "price_inr": 0,
            "price_usd": 0,
            "duration": "7 days",
            "description": "Try all Pro features free for 7 days",
            "features": FeatureGate.get_available_features_for_tier(SubscriptionTier.FREE_TRIAL)
        },
        "basic": {
            "name": "Basic",
            "price_monthly_inr": 199,
            "price_yearly_inr": 1999,
            "price_monthly_usd": 2.49,
            "price_yearly_usd": 24.99,
            "savings_yearly_inr": 389,
            "savings_percent": 16,
            "description": "Essential features for content creators",
            "features": FeatureGate.get_available_features_for_tier(SubscriptionTier.BASIC)
        },
        "pro": {
            "name": "Pro",
            "price_monthly_inr": 399,
            "price_yearly_inr": 3999,
            "price_monthly_usd": 4.99,
            "price_yearly_usd": 49.99,
            "savings_yearly_inr": 789,
            "savings_percent": 16,
            "description": "All features for professional creators",
            "recommended": True,
            "features": FeatureGate.get_available_features_for_tier(SubscriptionTier.PRO)
        },
        "lifetime": {
            "name": "Lifetime",
            "price_inr": 4999,
            "price_usd": 62.49,
            "duration": "One-time purchase",
            "description": "Pay once, lifetime Pro access",
            "features": FeatureGate.get_available_features_for_tier(SubscriptionTier.LIFETIME)
        }
    }


# ========== Usage Tracking Endpoints ==========

class UsageSummaryResponse(BaseModel):
    """Usage summary for the current billing period"""
    period: str
    last_updated: str
    exports: dict
    tts: dict
    ai: dict
    voice_cloning: dict
    storage: dict


class UsageCheckResponse(BaseModel):
    """Response for usage limit check"""
    allowed: bool
    current: float
    limit: float
    remaining: float
    error_message: Optional[str] = None


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get usage summary for the current billing period (requires authentication).

    Returns all usage metrics with current values, limits, and percentages.
    """
    # Use authenticated user's email
    user_email = user.email
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User email not available"
        )

    # Use subscription tier from authenticated user
    tier = user.subscription_tier
    usage_tracker = get_usage_tracker()

    summary = usage_tracker.get_usage_summary(user_email, tier.value)
    return UsageSummaryResponse(**summary)


@router.get("/usage/check/{usage_type}", response_model=UsageCheckResponse)
async def check_usage_limit(
    usage_type: str,
    increment: float = 1.0,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Check if a usage action is allowed without exceeding limits (requires authentication).

    Args:
        usage_type: Type of usage (export, tts_generation, ai_generation, voice_cloning, storage)
        increment: Amount of usage to check (e.g., character count for TTS)
    """
    # Use authenticated user's email
    user_email = user.email
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User email not available"
        )

    # Validate usage type
    try:
        usage_type_enum = UsageType(usage_type)
    except ValueError:
        valid_types = [t.value for t in UsageType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid usage type. Valid types: {valid_types}"
        )

    # Use subscription tier from authenticated user
    tier = user.subscription_tier
    usage_tracker = get_usage_tracker()

    allowed, error_msg, usage_info = usage_tracker.check_limit(
        user_id=user_email,
        usage_type=usage_type_enum,
        tier=tier.value,
        increment=increment,
    )

    return UsageCheckResponse(
        allowed=allowed,
        current=usage_info.get("current", 0),
        limit=usage_info.get("limit", 0),
        remaining=usage_info.get("remaining", 0),
        error_message=error_msg,
    )


@router.get("/usage/history/{usage_type}")
async def get_usage_history(
    usage_type: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get historical usage data for a specific type (requires authentication).

    Returns monthly usage data for the last 12 months.
    """
    # Use authenticated user's email
    user_email = user.email
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User email not available"
        )

    # Validate usage type
    try:
        usage_type_enum = UsageType(usage_type)
    except ValueError:
        valid_types = [t.value for t in UsageType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid usage type. Valid types: {valid_types}"
        )

    usage_tracker = get_usage_tracker()
    history = usage_tracker.get_usage_history(user_email, usage_type_enum)

    return {
        "usage_type": usage_type,
        "history": history
    }
