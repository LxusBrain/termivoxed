"""
Usage Tracking Utility for TermiVoxed Web API

Directly updates Firestore with usage data instead of going through Cloud Functions.
This ensures reliable tracking without HTTP call failures or protocol mismatches.

Usage types:
- export: Track export operations (count and duration)
- tts_minute: Track TTS generation (minutes)
- ai_generation: Track AI generation requests
- voice_cloning: Track voice cloning operations
"""

from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from utils.logger import logger


class UsageAction(str, Enum):
    """Types of usage actions that can be tracked"""
    EXPORT = "export"
    TTS_MINUTE = "tts_minute"
    AI_GENERATION = "ai_generation"
    VOICE_CLONING = "voice_cloning"


def track_usage(
    user_id: str,
    action: UsageAction,
    amount: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Track usage for a user by updating Firestore directly.

    Args:
        user_id: The Firebase user ID
        action: Type of usage action (export, tts_minute, ai_generation, voice_cloning)
        amount: Amount of usage (e.g., 1 for an export, 5.5 for minutes)
        metadata: Optional metadata to store with the usage log

    Returns:
        bool: True if tracking was successful, False otherwise
    """
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()

        # Map action to Firestore field
        field_map = {
            UsageAction.EXPORT: "usageThisMonth.exportsCount",
            UsageAction.TTS_MINUTE: "usageThisMonth.ttsMinutes",
            UsageAction.AI_GENERATION: "usageThisMonth.aiGenerations",
            UsageAction.VOICE_CLONING: "usageThisMonth.voiceClonings",
        }

        usage_field = field_map.get(action)
        if not usage_field:
            logger.error(f"Unknown usage action: {action}")
            return False

        # Update subscriptions collection (source of truth for Cloud Functions)
        sub_ref = db.collection("subscriptions").document(user_id)
        sub_doc = sub_ref.get()

        if sub_doc.exists:
            # Increment the usage field
            sub_ref.update({
                usage_field: firestore.Increment(amount)
            })
            logger.info(f"Updated usage for {user_id}: {action.value} +{amount}")
        else:
            # Create subscription document if it doesn't exist
            # This shouldn't happen in normal flow but handles edge cases
            logger.warning(f"No subscription found for {user_id}, creating default")
            sub_ref.set({
                "tier": "free_trial",
                "status": "trial",
                "usageThisMonth": {
                    "exportsCount": amount if action == UsageAction.EXPORT else 0,
                    "ttsMinutes": amount if action == UsageAction.TTS_MINUTE else 0,
                    "aiGenerations": amount if action == UsageAction.AI_GENERATION else 0,
                    "voiceClonings": amount if action == UsageAction.VOICE_CLONING else 0,
                },
                "usageLimits": {
                    "maxExportsPerMonth": 5,
                    "maxTtsMinutesPerMonth": 10,
                    "maxAiGenerationsPerMonth": 10,
                    "maxVoiceCloningsPerMonth": 1,
                },
            })

        # Also log to usage_logs collection for audit trail
        log_data = {
            "action": action.value,
            "amount": amount,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "metadata": metadata or {},
        }

        db.collection("usage_logs").document(user_id).collection("logs").add(log_data)

        return True

    except Exception as e:
        logger.error(f"Failed to track usage for {user_id}: {e}")
        return False


def check_usage_limit(
    user_id: str,
    action: UsageAction,
    amount: float = 1.0
) -> tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Check if a usage action is allowed without exceeding limits.

    Args:
        user_id: The Firebase user ID
        action: Type of usage action
        amount: Amount of usage to check

    Returns:
        Tuple of (allowed: bool, error_message: Optional[str], usage_info: dict)
    """
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()

        # Get subscription document
        sub_ref = db.collection("subscriptions").document(user_id)
        sub_doc = sub_ref.get()

        if not sub_doc.exists:
            return True, None, {"current": 0, "limit": -1, "remaining": -1}

        sub_data = sub_doc.to_dict()
        usage = sub_data.get("usageThisMonth", {})
        limits = sub_data.get("usageLimits", {})

        # Map action to fields
        usage_map = {
            UsageAction.EXPORT: ("exportsCount", "maxExportsPerMonth"),
            UsageAction.TTS_MINUTE: ("ttsMinutes", "maxTtsMinutesPerMonth"),
            UsageAction.AI_GENERATION: ("aiGenerations", "maxAiGenerationsPerMonth"),
            UsageAction.VOICE_CLONING: ("voiceClonings", "maxVoiceCloningsPerMonth"),
        }

        usage_field, limit_field = usage_map.get(action, (None, None))
        if not usage_field:
            return True, None, {"current": 0, "limit": -1, "remaining": -1}

        current = usage.get(usage_field, 0)
        limit = limits.get(limit_field, -1)

        usage_info = {
            "current": current,
            "limit": limit,
            "remaining": max(0, limit - current) if limit >= 0 else -1,
        }

        # Check if limit exceeded
        if limit >= 0 and current + amount > limit:
            return False, f"Usage limit exceeded. Current: {current}, Limit: {limit}", usage_info

        return True, None, usage_info

    except Exception as e:
        logger.error(f"Failed to check usage limit for {user_id}: {e}")
        # Allow on error to not block user
        return True, None, {"current": 0, "limit": -1, "remaining": -1}


def get_usage_summary(user_id: str) -> Dict[str, Any]:
    """
    Get usage summary for a user.

    Args:
        user_id: The Firebase user ID

    Returns:
        Dictionary with usage summary
    """
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()

        sub_ref = db.collection("subscriptions").document(user_id)
        sub_doc = sub_ref.get()

        if not sub_doc.exists:
            return {
                "usageThisMonth": {},
                "usageLimits": {},
                "tier": "unknown",
            }

        sub_data = sub_doc.to_dict()

        return {
            "usageThisMonth": sub_data.get("usageThisMonth", {}),
            "usageLimits": sub_data.get("usageLimits", {}),
            "tier": sub_data.get("tier", "unknown"),
            "status": sub_data.get("status", "unknown"),
        }

    except Exception as e:
        logger.error(f"Failed to get usage summary for {user_id}: {e}")
        return {
            "usageThisMonth": {},
            "usageLimits": {},
            "tier": "unknown",
            "error": str(e),
        }
