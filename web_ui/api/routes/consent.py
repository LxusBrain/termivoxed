"""
Privacy Consent API Routes

Handles user consent for data processing, including:
- Third-party TTS (Microsoft Edge TTS)
- Device fingerprinting
- Analytics and error reporting

All endpoints require authentication for per-user consent storage.
"""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Add parent directory to path to import existing modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from subscription.privacy_consent import (
    get_user_consent_manager,
    get_tts_consent_dialog_content,
    get_tts_warning_banner,
    get_consent_dialog_content,
    ConsentType,
    ConsentStatus,
)
from utils.logger import logger
from web_ui.api.middleware.auth import AuthenticatedUser, get_current_user

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class ConsentRequest(BaseModel):
    """Request to record a consent decision"""
    consent_type: str
    granted: bool
    method: str = "explicit_click"


class TTSConsentRequest(BaseModel):
    """Request specifically for TTS consent"""
    granted: bool
    remember_choice: bool = True


class ConsentStatusResponse(BaseModel):
    """Response with consent status"""
    consent_type: str
    status: str
    granted: bool
    timestamp: Optional[str] = None


class TTSConsentStatusResponse(BaseModel):
    """Response for TTS consent status check"""
    has_consent: bool
    needs_consent: bool
    status: str
    can_use_tts: bool


class AllConsentsResponse(BaseModel):
    """Response with all consent statuses"""
    consents: Dict[str, Any]
    needs_initial_consent: bool
    can_use_app: bool
    missing_required: list


# ============================================================================
# TTS Consent Endpoints (Primary use case)
# ============================================================================

@router.get("/tts/status", response_model=TTSConsentStatusResponse)
async def get_tts_consent_status(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Check if user has consented to third-party TTS usage.

    Call this before any TTS operation to determine if consent dialog
    should be shown.

    Requires authentication.
    """
    manager = get_user_consent_manager(user.uid)
    status = manager.get_consent_status(ConsentType.THIRD_PARTY_TTS.value)
    has_consent = manager.has_consent(ConsentType.THIRD_PARTY_TTS.value)
    needs_consent = status == ConsentStatus.NOT_ASKED

    return TTSConsentStatusResponse(
        has_consent=has_consent,
        needs_consent=needs_consent,
        status=status.value,
        can_use_tts=has_consent,
    )


@router.post("/tts/record")
async def record_tts_consent_decision(
    request: TTSConsentRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Record user's TTS consent decision.

    Called when user accepts or declines TTS consent dialog.

    Requires authentication.
    """
    try:
        manager = get_user_consent_manager(user.uid)
        manager.record_consent(
            ConsentType.THIRD_PARTY_TTS.value,
            request.granted,
            method="explicit_click",
            user_id=user.uid
        )

        action = "granted" if request.granted else "declined"
        logger.info(f"TTS consent {action} by user {user.uid}")

        return {
            "success": True,
            "message": f"TTS consent {action}",
            "can_use_tts": request.granted,
        }
    except Exception as e:
        logger.error(f"Failed to record TTS consent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tts/dialog-content")
async def get_tts_dialog_content():
    """
    Get content for TTS consent dialog.

    Returns structured data for rendering the consent UI,
    including all text, warnings, and button labels.
    """
    return get_tts_consent_dialog_content()


@router.get("/tts/warning-banner")
async def get_tts_warning_banner_content():
    """
    Get content for inline TTS warning banner.

    This is shown in voice/audio sections to remind users
    that their text is sent to external servers.
    """
    return get_tts_warning_banner()


# ============================================================================
# General Consent Endpoints
# ============================================================================

@router.get("/status")
async def get_all_consent_status(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get status of all consent types.

    Returns comprehensive consent status for all categories.

    Requires authentication.
    """
    manager = get_user_consent_manager(user.uid)
    can_use, missing = manager.can_use_app()

    return AllConsentsResponse(
        consents=manager.get_all_consents(),
        needs_initial_consent=manager.needs_consent(),
        can_use_app=can_use,
        missing_required=missing,
    )


@router.post("/record")
async def record_consent_decision(
    request: ConsentRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Record a consent decision for any consent type.

    Requires authentication.
    """
    try:
        # Validate consent type
        valid_types = [ct.value for ct in ConsentType]
        if request.consent_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid consent type. Valid types: {valid_types}"
            )

        manager = get_user_consent_manager(user.uid)
        manager.record_consent(
            request.consent_type,
            request.granted,
            request.method,
            user_id=user.uid
        )

        action = "granted" if request.granted else "declined"
        logger.info(f"Consent {request.consent_type} {action} for user {user.uid}")

        return {
            "success": True,
            "consent_type": request.consent_type,
            "status": action,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record consent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record-all")
async def record_all_consents(
    consents: Dict[str, bool],
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Record multiple consent decisions at once.

    Used when user completes the full consent dialog.

    Requires authentication.
    """
    try:
        manager = get_user_consent_manager(user.uid)
        manager.record_all_consents(consents, user_id=user.uid)

        logger.info(f"Recorded {len(consents)} consent decisions for user {user.uid}")

        can_use, missing = manager.can_use_app()

        return {
            "success": True,
            "recorded_count": len(consents),
            "can_use_app": can_use,
            "missing_required": missing,
        }
    except Exception as e:
        logger.error(f"Failed to record consents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/withdraw/{consent_type}")
async def withdraw_consent(
    consent_type: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Withdraw a previously granted consent.

    GDPR/CCPA compliant - users can withdraw consent anytime.

    Requires authentication.
    """
    try:
        valid_types = [ct.value for ct in ConsentType]
        if consent_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid consent type. Valid types: {valid_types}"
            )

        manager = get_user_consent_manager(user.uid)
        manager.withdraw_consent(consent_type)

        logger.info(f"Consent withdrawn: {consent_type} for user {user.uid}")

        return {
            "success": True,
            "consent_type": consent_type,
            "status": "withdrawn",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to withdraw consent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dialog-content")
async def get_full_consent_dialog_content():
    """
    Get content for the full consent dialog.

    Returns structured data for the initial consent dialog
    shown when app first launches.
    """
    return get_consent_dialog_content()


@router.get("/export")
async def export_consent_data(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Export all consent data for GDPR data portability.

    Returns a complete record of all consent decisions
    for the user to download.

    Requires authentication.
    """
    manager = get_user_consent_manager(user.uid)
    return manager.export_consent_data()


@router.delete("/clear")
async def clear_all_consent_data(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Clear all consent data.

    GDPR right to erasure - deletes all stored consent records.
    User will need to re-consent on next use.

    Requires authentication.
    """
    try:
        manager = get_user_consent_manager(user.uid)
        manager.clear_all_consent()

        logger.info(f"All consent data cleared for user {user.uid}")

        return {
            "success": True,
            "message": "All consent data has been deleted",
        }
    except Exception as e:
        logger.error(f"Failed to clear consent data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Consent Check Middleware Helper
# ============================================================================

@router.get("/check/{consent_type}")
async def check_specific_consent(
    consent_type: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Quick check if a specific consent is granted.

    Returns simple boolean for use in API guards.

    Requires authentication.
    """
    valid_types = [ct.value for ct in ConsentType]
    if consent_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid consent type. Valid types: {valid_types}"
        )

    manager = get_user_consent_manager(user.uid)
    has_consent = manager.has_consent(consent_type)

    return {
        "consent_type": consent_type,
        "has_consent": has_consent,
    }
