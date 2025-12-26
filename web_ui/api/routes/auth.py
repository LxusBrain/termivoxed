"""
Authentication Routes for TermiVoxed Web API

Handles user authentication, registration, and session management.
Integrates with Firebase Authentication for secure user management.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, EmailStr, Field

from web_ui.api.middleware.auth import (
    get_current_user,
    get_current_user_optional,
    verify_firebase_token,
    AuthenticatedUser,
)
from subscription.models import SubscriptionTier, SubscriptionStatus, FeatureAccess
from subscription.device_fingerprint import get_device_fingerprint, get_device_info

router = APIRouter()


# ============ Request/Response Models ============

class LoginRequest(BaseModel):
    """Login request with Firebase ID token"""
    id_token: str = Field(..., description="Firebase ID token from client-side authentication")
    device_fingerprint: Optional[str] = Field(None, description="Device fingerprint for device binding")
    device_name: Optional[str] = Field(None, description="Human-readable device name")


class RegisterDeviceRequest(BaseModel):
    """Request to register a new device"""
    device_fingerprint: str = Field(..., description="Unique device fingerprint")
    device_name: str = Field(..., description="Human-readable device name")
    device_type: str = Field(..., description="Device type: WINDOWS, MACOS, LINUX")
    os_version: Optional[str] = Field(None, description="Operating system version")


class RefreshTokenRequest(BaseModel):
    """Request to refresh authentication token"""
    refresh_token: str = Field(..., description="Firebase refresh token")


class LogoutRequest(BaseModel):
    """Logout request"""
    device_id: Optional[str] = Field(None, description="Device ID to logout (if managing multiple devices)")
    logout_all_devices: bool = Field(False, description="Logout from all devices")


class UserResponse(BaseModel):
    """User information response"""
    uid: str
    email: Optional[str]
    email_verified: bool
    display_name: Optional[str]
    photo_url: Optional[str]
    subscription_tier: str
    subscription_status: str
    features: dict
    subscription_expires_at: Optional[str]
    devices: list = []


class AuthStatusResponse(BaseModel):
    """Authentication status response"""
    authenticated: bool
    user: Optional[UserResponse] = None
    message: str = ""


class DeviceResponse(BaseModel):
    """Device information response"""
    device_id: str
    device_name: str
    device_type: str
    os_version: Optional[str]
    is_current: bool
    last_seen: str
    registered_at: str


# ============ Helper Functions ============

async def _get_or_create_user_subscription(uid: str, email: Optional[str]) -> dict:
    """
    Get or create user subscription in Firestore.

    Args:
        uid: Firebase user ID
        email: User email

    Returns:
        Subscription data dictionary
    """
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()

        if user_doc.exists:
            return user_doc.to_dict().get("subscription", {})

        # Create new user with free trial
        trial_end = datetime.now() + timedelta(days=7)

        new_user_data = {
            "uid": uid,
            "email": email,
            "createdAt": datetime.now().isoformat(),
            "subscription": {
                "tier": SubscriptionTier.FREE_TRIAL.value,
                "status": SubscriptionStatus.TRIAL.value,
                "trialEndsAt": trial_end.isoformat(),
                "periodEnd": trial_end.isoformat(),
                "features": FeatureAccess.pro_features().to_dict(),  # Full features during trial
            },
            "devices": [],
            "settings": {
                "language": "en",
                "theme": "dark",
            }
        }

        user_ref.set(new_user_data)
        return new_user_data["subscription"]

    except ImportError:
        # Firebase not available - return development defaults
        return {
            "tier": SubscriptionTier.FREE_TRIAL.value,
            "status": SubscriptionStatus.TRIAL.value,
            "features": FeatureAccess.pro_features().to_dict(),
        }
    except Exception as e:
        print(f"Error creating user subscription: {e}")
        return {
            "tier": SubscriptionTier.FREE_TRIAL.value,
            "status": SubscriptionStatus.TRIAL.value,
            "features": FeatureAccess.for_tier(SubscriptionTier.FREE_TRIAL).to_dict(),
        }


async def _register_device(uid: str, device_data: dict) -> dict:
    """
    Register a device for a user.

    Args:
        uid: Firebase user ID
        device_data: Device information

    Returns:
        Updated device record
    """
    try:
        import firebase_admin
        from firebase_admin import firestore
        import uuid

        db = firestore.client()
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        user_data = user_doc.to_dict()
        devices = user_data.get("devices", [])
        subscription = user_data.get("subscription", {})

        # Check device limit based on tier
        tier = subscription.get("tier", "free_trial")
        max_devices = {
            "free_trial": 1,
            "basic": 2,
            "pro": 5,
            "lifetime": 10,
        }.get(tier, 1)

        # Check if device already registered
        fingerprint = device_data.get("device_fingerprint")
        existing_device = next(
            (d for d in devices if d.get("fingerprint") == fingerprint),
            None
        )

        now = datetime.now().isoformat()

        if existing_device:
            # Update existing device
            existing_device["lastSeen"] = now
            existing_device["deviceName"] = device_data.get("device_name", existing_device.get("deviceName"))
        else:
            # Check if we can add a new device
            active_devices = [d for d in devices if d.get("active", True)]
            if len(active_devices) >= max_devices:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Device limit reached ({max_devices}). Please remove a device first.",
                    headers={"X-Max-Devices": str(max_devices)}
                )

            # Add new device
            new_device = {
                "deviceId": str(uuid.uuid4()),
                "fingerprint": fingerprint,
                "deviceName": device_data.get("device_name", "Unknown Device"),
                "deviceType": device_data.get("device_type", "UNKNOWN"),
                "osVersion": device_data.get("os_version"),
                "registeredAt": now,
                "lastSeen": now,
                "active": True,
            }
            devices.append(new_device)
            existing_device = new_device

        # Update user document
        user_ref.update({
            "devices": devices,
            "currentDevice": existing_device,
        })

        return existing_device

    except HTTPException:
        raise
    except ImportError:
        # Firebase not available - return mock device
        return {
            "deviceId": "dev-device-001",
            "fingerprint": device_data.get("device_fingerprint"),
            "deviceName": device_data.get("device_name", "Development Device"),
            "deviceType": device_data.get("device_type", "DEVELOPMENT"),
            "registeredAt": datetime.now().isoformat(),
            "lastSeen": datetime.now().isoformat(),
            "active": True,
        }
    except Exception as e:
        print(f"Error registering device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register device"
        )


async def _get_user_devices(uid: str) -> list:
    """Get all devices for a user"""
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_doc = db.collection("users").document(uid).get()

        if not user_doc.exists:
            return []

        return user_doc.to_dict().get("devices", [])

    except ImportError:
        return []
    except Exception:
        return []


async def _deactivate_device(uid: str, device_id: str) -> bool:
    """Deactivate a specific device"""
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return False

        devices = user_doc.to_dict().get("devices", [])

        for device in devices:
            if device.get("deviceId") == device_id:
                device["active"] = False
                device["deactivatedAt"] = datetime.now().isoformat()

        user_ref.update({"devices": devices})
        return True

    except Exception:
        return False


# ============ Routes ============

@router.post("/login", response_model=UserResponse)
async def login(request: LoginRequest):
    """
    Authenticate user with Firebase ID token.

    This endpoint:
    1. Verifies the Firebase ID token
    2. Creates/updates user record in Firestore
    3. Registers device if fingerprint provided
    4. Returns user info with subscription details
    """
    # Verify the token
    decoded_token = await verify_firebase_token(request.id_token)

    if decoded_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    uid = decoded_token["uid"]
    email = decoded_token.get("email")

    # Get or create subscription
    subscription = await _get_or_create_user_subscription(uid, email)

    # Register device if fingerprint provided
    device = None
    if request.device_fingerprint:
        device = await _register_device(uid, {
            "device_fingerprint": request.device_fingerprint,
            "device_name": request.device_name or "Unknown Device",
            "device_type": "WEB",  # Web login
        })

    # Get all devices
    devices = await _get_user_devices(uid)

    # Parse subscription tier
    tier_str = subscription.get("tier", "free_trial")
    try:
        tier = SubscriptionTier(tier_str)
    except ValueError:
        tier = SubscriptionTier.FREE_TRIAL

    features = subscription.get("features", FeatureAccess.for_tier(tier).to_dict())

    return UserResponse(
        uid=uid,
        email=email,
        email_verified=decoded_token.get("email_verified", False),
        display_name=decoded_token.get("name"),
        photo_url=decoded_token.get("picture"),
        subscription_tier=tier.value,
        subscription_status=subscription.get("status", "trial"),
        features=features,
        subscription_expires_at=subscription.get("periodEnd"),
        devices=[
            DeviceResponse(
                device_id=d.get("deviceId", ""),
                device_name=d.get("deviceName", "Unknown"),
                device_type=d.get("deviceType", "UNKNOWN"),
                os_version=d.get("osVersion"),
                is_current=d.get("deviceId") == (device.get("deviceId") if device else None),
                last_seen=d.get("lastSeen", ""),
                registered_at=d.get("registeredAt", ""),
            ).model_dump()
            for d in devices if d.get("active", True)
        ]
    )


@router.post("/register-device", response_model=DeviceResponse)
async def register_device(
    request: RegisterDeviceRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Register a new device for the authenticated user.

    This is called when:
    - User logs in from a new device
    - Desktop app is activated
    """
    device = await _register_device(user.uid, {
        "device_fingerprint": request.device_fingerprint,
        "device_name": request.device_name,
        "device_type": request.device_type,
        "os_version": request.os_version,
    })

    return DeviceResponse(
        device_id=device.get("deviceId", ""),
        device_name=device.get("deviceName", "Unknown"),
        device_type=device.get("deviceType", "UNKNOWN"),
        os_version=device.get("osVersion"),
        is_current=True,
        last_seen=device.get("lastSeen", ""),
        registered_at=device.get("registeredAt", ""),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Returns user profile, subscription details, and feature access.
    """
    devices = await _get_user_devices(user.uid)

    return UserResponse(
        uid=user.uid,
        email=user.email,
        email_verified=user.email_verified,
        display_name=user.display_name,
        photo_url=user.photo_url,
        subscription_tier=user.subscription_tier.value,
        subscription_status=user.subscription_status.value,
        features=user.features.to_dict() if user.features else {},
        subscription_expires_at=user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        devices=[
            DeviceResponse(
                device_id=d.get("deviceId", ""),
                device_name=d.get("deviceName", "Unknown"),
                device_type=d.get("deviceType", "UNKNOWN"),
                os_version=d.get("osVersion"),
                is_current=d.get("deviceId") == user.device_id,
                last_seen=d.get("lastSeen", ""),
                registered_at=d.get("registeredAt", ""),
            ).model_dump()
            for d in devices if d.get("active", True)
        ]
    )


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(user: Optional[AuthenticatedUser] = Depends(get_current_user_optional)):
    """
    Check authentication status.

    Can be called without authentication to check if user is logged in.
    """
    if user is None:
        return AuthStatusResponse(
            authenticated=False,
            message="Not authenticated"
        )

    return AuthStatusResponse(
        authenticated=True,
        user=UserResponse(
            uid=user.uid,
            email=user.email,
            email_verified=user.email_verified,
            display_name=user.display_name,
            photo_url=user.photo_url,
            subscription_tier=user.subscription_tier.value,
            subscription_status=user.subscription_status.value,
            features=user.features.to_dict() if user.features else {},
            subscription_expires_at=user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        ),
        message="Authenticated"
    )


@router.get("/devices", response_model=list[DeviceResponse])
async def get_devices(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get all registered devices for the current user.
    """
    devices = await _get_user_devices(user.uid)

    return [
        DeviceResponse(
            device_id=d.get("deviceId", ""),
            device_name=d.get("deviceName", "Unknown"),
            device_type=d.get("deviceType", "UNKNOWN"),
            os_version=d.get("osVersion"),
            is_current=d.get("deviceId") == user.device_id,
            last_seen=d.get("lastSeen", ""),
            registered_at=d.get("registeredAt", ""),
        )
        for d in devices if d.get("active", True)
    ]


@router.delete("/devices/{device_id}")
async def remove_device(
    device_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Remove a device from the user's account.

    This allows logging out a specific device remotely.
    """
    success = await _deactivate_device(user.uid, device_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    return {"message": "Device removed successfully"}


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Logout user.

    Can logout from:
    - Current device only
    - Specific device (by device_id)
    - All devices (logout_all_devices=True)
    """
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_ref = db.collection("users").document(user.uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return {"message": "Logged out"}

        if request.logout_all_devices:
            # Deactivate all devices
            devices = user_doc.to_dict().get("devices", [])
            now = datetime.now().isoformat()

            for device in devices:
                device["active"] = False
                device["deactivatedAt"] = now

            user_ref.update({
                "devices": devices,
                "currentDevice": None,
            })

            return {"message": "Logged out from all devices"}

        elif request.device_id:
            # Deactivate specific device
            await _deactivate_device(user.uid, request.device_id)
            return {"message": f"Device {request.device_id} logged out"}

        else:
            # Deactivate current device
            if user.device_id:
                await _deactivate_device(user.uid, user.device_id)

            return {"message": "Logged out from current device"}

    except ImportError:
        return {"message": "Logged out (development mode)"}
    except Exception as e:
        print(f"Logout error: {e}")
        return {"message": "Logged out"}


@router.get("/subscription")
async def get_subscription(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get detailed subscription information.
    """
    features = user.features.to_dict() if user.features else FeatureAccess.for_tier(user.subscription_tier).to_dict()

    return {
        "tier": user.subscription_tier.value,
        "status": user.subscription_status.value,
        "expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        "is_active": user.is_subscription_active(),
        "features": features,
        "upgrade_url": "/pricing" if user.subscription_tier == SubscriptionTier.FREE_TRIAL else None,
        "renew_url": "/renew" if not user.is_subscription_active() else None,
    }


@router.post("/verify-license")
async def verify_license(
    user: AuthenticatedUser = Depends(get_current_user),
    device_fingerprint: Optional[str] = None
):
    """
    Verify user's license for desktop app.

    This endpoint is called by the desktop app's LicenseGuard
    to verify the license is still valid.
    """
    if not user.is_subscription_active():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription expired",
            headers={"X-Action-Required": "renew"}
        )

    # Verify device fingerprint if provided
    if device_fingerprint and user.device_fingerprint:
        if device_fingerprint != user.device_fingerprint:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device fingerprint mismatch",
                headers={"X-Action-Required": "reactivate"}
            )

    features = user.features.to_dict() if user.features else FeatureAccess.for_tier(user.subscription_tier).to_dict()

    return {
        "status": "VALID",
        "subscription": {
            "tier": user.subscription_tier.value,
            "status": user.subscription_status.value,
            "periodEnd": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            "features": features,
        },
        "device": {
            "deviceId": user.device_id,
            "verified": True,
        }
    }
