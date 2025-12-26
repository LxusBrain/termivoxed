"""
Usage Tracking System for TermiVoxed SaaS

Tracks and enforces usage limits for:
- Exports (count and duration per month)
- TTS generations (characters/minutes per month)
- AI generations (requests per month)
- Storage usage

Usage data is stored locally with HMAC integrity verification and synced
with Firebase cloud for authoritative tracking. Cloud is the source of truth.
"""

import json
import os
import hmac
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
from functools import wraps

from utils.logger import logger


# ============================================================================
# Cloud Sync Service
# ============================================================================

class CloudSyncService:
    """
    Handles synchronization of usage data with Firebase Cloud.
    Cloud is the authoritative source of truth for usage limits.
    """

    def __init__(self):
        self._api_base: Optional[str] = None
        self._auth_token: Optional[str] = None
        self._last_sync: Optional[datetime] = None
        self._sync_interval = 300  # 5 minutes
        self._pending_syncs: list = []
        self._sync_lock = threading.Lock()
        self._offline_mode = False

    def configure(self, api_base: str, auth_token: str):
        """Configure the cloud sync service with API endpoint and auth token"""
        self._api_base = api_base
        self._auth_token = auth_token

    def _is_configured(self) -> bool:
        """Check if cloud sync is properly configured"""
        return bool(self._api_base and self._auth_token)

    def sync_usage_to_cloud(
        self,
        user_id: str,
        action: str,
        amount: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Sync usage action to cloud. Returns (success, cloud_response).
        Cloud response includes current usage and limits.
        """
        if not self._is_configured():
            logger.warning("Cloud sync not configured, operating in offline mode")
            self._offline_mode = True
            return False, None

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json"
            }

            # Map internal action types to cloud function action names
            action_map = {
                "export": "export",
                "tts_generation": "tts_minute",
                "ai_generation": "ai_generation",
            }

            cloud_action = action_map.get(action, action)

            payload = {
                "action": cloud_action,
                "amount": amount,
                "metadata": metadata or {}
            }

            response = requests.post(
                f"{self._api_base}/trackUsage",
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self._last_sync = datetime.now()
                self._offline_mode = False
                return True, data
            elif response.status_code == 401:
                logger.error("Cloud sync authentication failed")
                return False, {"error": "authentication_failed"}
            elif response.status_code == 429:
                logger.warning("Cloud sync rate limited")
                return False, {"error": "rate_limited"}
            else:
                logger.error(f"Cloud sync failed: {response.status_code}")
                return False, None

        except requests.exceptions.Timeout:
            logger.warning("Cloud sync timeout, queuing for retry")
            self._queue_pending_sync(user_id, action, amount, metadata)
            return False, None
        except Exception as e:
            logger.error(f"Cloud sync error: {e}")
            self._offline_mode = True
            return False, None

    def _queue_pending_sync(
        self,
        user_id: str,
        action: str,
        amount: float,
        metadata: Optional[Dict[str, Any]]
    ):
        """Queue a sync operation for retry when connection is restored"""
        with self._sync_lock:
            self._pending_syncs.append({
                "user_id": user_id,
                "action": action,
                "amount": amount,
                "metadata": metadata,
                "timestamp": datetime.now().isoformat(),
                "retries": 0
            })
            # Keep only last 100 pending syncs
            self._pending_syncs = self._pending_syncs[-100:]

    def flush_pending_syncs(self) -> int:
        """Attempt to sync all pending operations. Returns count of successful syncs."""
        if not self._is_configured():
            return 0

        with self._sync_lock:
            pending = list(self._pending_syncs)
            self._pending_syncs = []

        success_count = 0
        failed = []

        for sync in pending:
            success, _ = self.sync_usage_to_cloud(
                sync["user_id"],
                sync["action"],
                sync["amount"],
                sync["metadata"]
            )
            if success:
                success_count += 1
            else:
                sync["retries"] = sync.get("retries", 0) + 1
                if sync["retries"] < 5:  # Max 5 retries
                    failed.append(sync)

        with self._sync_lock:
            self._pending_syncs.extend(failed)

        return success_count

    def fetch_cloud_usage(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch authoritative usage data from cloud.
        Returns None if cloud is unreachable.
        """
        if not self._is_configured():
            return None

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json"
            }

            response = requests.get(
                f"{self._api_base}/usage/{user_id}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            logger.error(f"Failed to fetch cloud usage: {e}")
            return None

    def check_limit_with_cloud(
        self,
        user_id: str,
        action: str,
        amount: float = 1.0
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Check usage limit with cloud as authoritative source.
        Returns (allowed, error_message, usage_info)
        """
        success, response = self.sync_usage_to_cloud(user_id, action, amount)

        if success and response:
            if response.get("allowed", True):
                return True, None, {
                    "current": response.get("currentUsage", 0),
                    "limit": response.get("limit", -1),
                    "source": "cloud"
                }
            else:
                return False, response.get("message", "Limit exceeded"), {
                    "current": response.get("currentUsage", 0),
                    "limit": response.get("limit", -1),
                    "upgrade_url": response.get("upgradeUrl"),
                    "source": "cloud"
                }

        # Cloud unavailable - return None to indicate local check needed
        return True, None, {"source": "local_fallback"}

    @property
    def is_offline(self) -> bool:
        """Check if we're operating in offline mode"""
        return self._offline_mode

    @property
    def pending_sync_count(self) -> int:
        """Get count of pending sync operations"""
        return len(self._pending_syncs)


# Global cloud sync service instance
_cloud_sync: Optional[CloudSyncService] = None

def get_cloud_sync() -> CloudSyncService:
    """Get the global cloud sync service instance"""
    global _cloud_sync
    if _cloud_sync is None:
        _cloud_sync = CloudSyncService()
    return _cloud_sync


# ============================================================================
# HMAC Integrity Verification
# ============================================================================

class UsageIntegrity:
    """
    Provides HMAC-based integrity verification for local usage data.
    Detects if usage files have been tampered with.
    """

    def __init__(self, secret_key: Optional[bytes] = None):
        self._secret_key = secret_key or self._load_or_create_key()

    def _load_or_create_key(self) -> bytes:
        """Load existing HMAC key or create new one"""
        from config import settings
        key_path = Path(settings.STORAGE_DIR) / ".usage_key"

        if key_path.exists():
            try:
                return key_path.read_bytes()
            except Exception:
                pass

        # Generate new 32-byte key
        key = secrets.token_bytes(32)
        try:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(key)
            # Make key file read-only
            os.chmod(key_path, 0o400)
        except Exception as e:
            logger.warning(f"Could not persist HMAC key: {e}")

        return key

    def sign_data(self, data: Dict[str, Any]) -> str:
        """Generate HMAC signature for usage data"""
        # Normalize data for consistent hashing
        normalized = json.dumps(data, sort_keys=True, default=str)
        signature = hmac.new(
            self._secret_key,
            normalized.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def verify_signature(self, data: Dict[str, Any], signature: str) -> bool:
        """Verify HMAC signature of usage data"""
        expected = self.sign_data(data)
        return hmac.compare_digest(expected, signature)

    def detect_tampering(
        self,
        local_data: Dict[str, Any],
        stored_signature: str,
        cloud_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Detect if usage data has been tampered with.
        Returns (is_valid, reason)
        """
        # Check HMAC signature
        if not self.verify_signature(local_data, stored_signature):
            logger.warning("HMAC signature mismatch - possible tampering detected")
            return False, "signature_mismatch"

        # If cloud data available, verify consistency
        if cloud_data:
            # Local usage should never be less than cloud usage
            local_exports = local_data.get("exports", {}).get("count", 0)
            cloud_exports = cloud_data.get("usageThisMonth", {}).get("exportsCount", 0)

            if local_exports < cloud_exports:
                logger.warning(
                    f"Usage discrepancy: local={local_exports}, cloud={cloud_exports}"
                )
                return False, "usage_mismatch"

        return True, "valid"


# Global integrity checker instance
_integrity: Optional[UsageIntegrity] = None

def get_integrity_checker() -> UsageIntegrity:
    """Get the global integrity checker instance"""
    global _integrity
    if _integrity is None:
        _integrity = UsageIntegrity()
    return _integrity


class UsageType(str, Enum):
    """Types of usage that are tracked"""
    EXPORT = "export"
    TTS_GENERATION = "tts_generation"
    AI_GENERATION = "ai_generation"
    VOICE_CLONING = "voice_cloning"
    STORAGE = "storage"


@dataclass
class UsageLimits:
    """
    Usage limits per subscription tier.

    IMPORTANT: This class now derives values from subscription.models.FeatureAccess
    which is the single source of truth for tier limits.
    """
    exports_per_month: int = 5
    export_minutes_per_month: float = 30.0
    tts_characters_per_month: int = 50000
    ai_requests_per_month: int = 100
    voice_clones_per_month: int = 10
    storage_mb: int = 500

    @classmethod
    def for_tier(cls, tier: str) -> "UsageLimits":
        """
        Get usage limits for a subscription tier.

        Uses FeatureAccess from subscription.models as single source of truth.
        See subscription/models.py FeatureAccess for authoritative limit values.
        """
        from subscription.models import SubscriptionTier, FeatureAccess

        # Map string tier to SubscriptionTier enum
        tier_map = {
            "free_trial": SubscriptionTier.FREE_TRIAL,
            "individual": SubscriptionTier.INDIVIDUAL,
            "basic": SubscriptionTier.INDIVIDUAL,  # Alias
            "pro": SubscriptionTier.PRO,
            "lifetime": SubscriptionTier.LIFETIME,
            "enterprise": SubscriptionTier.ENTERPRISE,
            "expired": SubscriptionTier.EXPIRED,
        }

        tier_enum = tier_map.get(tier.lower(), SubscriptionTier.FREE_TRIAL)
        features = FeatureAccess.for_tier(tier_enum)

        # Convert TTS minutes to characters (approx 150 chars/minute)
        tts_chars = features.max_tts_minutes_per_month * 150 * 60  # chars per minute reading

        # Calculate export minutes based on tier
        export_minutes_map = {
            SubscriptionTier.FREE_TRIAL: 30.0,
            SubscriptionTier.INDIVIDUAL: 300.0,
            SubscriptionTier.PRO: 1200.0,
            SubscriptionTier.LIFETIME: 1200.0,
            SubscriptionTier.ENTERPRISE: 6000.0,
            SubscriptionTier.EXPIRED: 5.0,
        }
        export_minutes = export_minutes_map.get(tier_enum, 30.0)

        # Voice clones based on tier
        voice_clones_map = {
            SubscriptionTier.FREE_TRIAL: 0,
            SubscriptionTier.INDIVIDUAL: 10,
            SubscriptionTier.PRO: 50,
            SubscriptionTier.LIFETIME: 50,
            SubscriptionTier.ENTERPRISE: 200,
            SubscriptionTier.EXPIRED: 0,
        }
        voice_clones = voice_clones_map.get(tier_enum, 0)

        return cls(
            exports_per_month=features.max_exports_per_month,
            export_minutes_per_month=export_minutes,
            tts_characters_per_month=int(tts_chars),
            ai_requests_per_month=features.max_ai_requests_per_month,
            voice_clones_per_month=voice_clones,
            storage_mb=features.max_storage_mb,
        )


@dataclass
class UsageRecord:
    """Record of usage for a specific type"""
    count: int = 0
    value: float = 0.0  # e.g., minutes for exports, characters for TTS
    last_reset: str = ""  # ISO date of last monthly reset
    history: list = field(default_factory=list)  # Last N records for analytics


@dataclass
class UserUsage:
    """Complete usage data for a user"""
    user_id: str
    exports: UsageRecord = field(default_factory=UsageRecord)
    tts_generations: UsageRecord = field(default_factory=UsageRecord)
    ai_generations: UsageRecord = field(default_factory=UsageRecord)
    voice_clones: UsageRecord = field(default_factory=UsageRecord)
    storage_mb: float = 0.0
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "user_id": self.user_id,
            "exports": asdict(self.exports),
            "tts_generations": asdict(self.tts_generations),
            "ai_generations": asdict(self.ai_generations),
            "voice_clones": asdict(self.voice_clones),
            "storage_mb": self.storage_mb,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserUsage":
        """Create from dictionary"""
        return cls(
            user_id=data.get("user_id", ""),
            exports=UsageRecord(**data.get("exports", {})),
            tts_generations=UsageRecord(**data.get("tts_generations", {})),
            ai_generations=UsageRecord(**data.get("ai_generations", {})),
            voice_clones=UsageRecord(**data.get("voice_clones", {})),
            storage_mb=data.get("storage_mb", 0.0),
            last_updated=data.get("last_updated", ""),
        )


class UsageTracker:
    """
    Tracks and enforces usage limits for users.

    Usage is tracked per calendar month and automatically resets.
    Data is stored locally with HMAC integrity verification and synced
    to Firebase cloud as the authoritative source of truth.

    Security features:
    - HMAC signatures prevent local file tampering
    - Cloud sync validates usage on the server
    - Discrepancy detection catches manipulation attempts
    - Pending syncs are queued for offline operation
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize the usage tracker"""
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            from config import settings
            self.storage_dir = Path(settings.STORAGE_DIR) / "usage"

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, UserUsage] = {}
        self._signatures: Dict[str, str] = {}  # HMAC signatures for each user
        self._cloud_sync = get_cloud_sync()
        self._integrity = get_integrity_checker()
        self._tampering_detected: Dict[str, bool] = {}  # Track tampered users
        logger.info(f"UsageTracker initialized with storage: {self.storage_dir}")

    def _get_usage_file(self, user_id: str) -> Path:
        """Get the path to a user's usage file"""
        # Sanitize user_id for filename
        safe_id = "".join(c if c.isalnum() or c == "-" else "_" for c in user_id)
        return self.storage_dir / f"{safe_id}.json"

    def _get_current_month(self) -> str:
        """Get current month as YYYY-MM string"""
        return datetime.now().strftime("%Y-%m")

    def _should_reset(self, last_reset: str) -> bool:
        """Check if usage should be reset (new month)"""
        if not last_reset:
            return True
        current_month = self._get_current_month()
        return last_reset != current_month

    def _reset_if_needed(self, usage: UserUsage) -> UserUsage:
        """Reset usage counts if we're in a new month"""
        current_month = self._get_current_month()

        for record_name in ["exports", "tts_generations", "ai_generations", "voice_clones"]:
            record: UsageRecord = getattr(usage, record_name)
            if self._should_reset(record.last_reset):
                # Archive old usage to history (keep last 12 months)
                if record.count > 0 or record.value > 0:
                    record.history.append({
                        "month": record.last_reset or "unknown",
                        "count": record.count,
                        "value": record.value,
                    })
                    record.history = record.history[-12:]  # Keep only last 12 months

                # Reset for new month
                record.count = 0
                record.value = 0.0
                record.last_reset = current_month

        return usage

    def get_usage(self, user_id: str) -> UserUsage:
        """Get usage data for a user"""
        # Check cache first
        if user_id in self._cache:
            return self._reset_if_needed(self._cache[user_id])

        # Load from file
        usage_file = self._get_usage_file(user_id)
        if usage_file.exists():
            try:
                data = json.loads(usage_file.read_text())
                usage = UserUsage.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load usage for {user_id}: {e}")
                usage = UserUsage(user_id=user_id)
        else:
            usage = UserUsage(user_id=user_id)

        # Reset if new month and cache
        usage = self._reset_if_needed(usage)
        self._cache[user_id] = usage
        return usage

    def _save_usage(self, user_id: str, usage: UserUsage):
        """Save usage data to file with HMAC signature"""
        usage.last_updated = datetime.now().isoformat()
        usage_file = self._get_usage_file(user_id)
        signature_file = self.storage_dir / f".sig_{user_id}"

        try:
            # Generate data and signature
            data = usage.to_dict()
            signature = self._integrity.sign_data(data)

            # Save data
            usage_file.write_text(json.dumps(data, indent=2))

            # Save signature separately (harder to find and modify)
            signature_file.write_text(signature)

            # Update cache and signatures
            self._cache[user_id] = usage
            self._signatures[user_id] = signature

        except Exception as e:
            logger.error(f"Failed to save usage for {user_id}: {e}")

    def check_limit(
        self,
        user_id: str,
        usage_type: UsageType,
        tier: str,
        increment: float = 1.0,
        use_cloud: bool = True,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Check if a user can perform an action without exceeding limits.

        Uses cloud validation as the authoritative source when available.
        Falls back to local validation when offline.

        Args:
            user_id: User identifier
            usage_type: Type of usage to check
            tier: User's subscription tier
            increment: How much usage this action would add
            use_cloud: Whether to check with cloud (default True)

        Returns:
            Tuple of (is_allowed, error_message, usage_info)
        """
        # Check for detected tampering - block if tampered
        if self._tampering_detected.get(user_id, False):
            logger.warning(f"Blocking action for tampered user: {user_id}")
            return False, "Usage data integrity error. Please contact support.", {
                "tampered": True,
                "action_required": "contact_support"
            }

        # Try cloud validation first (authoritative)
        if use_cloud and not self._cloud_sync.is_offline:
            allowed, error, cloud_info = self._cloud_sync.check_limit_with_cloud(
                user_id, usage_type.value, increment
            )
            if cloud_info.get("source") == "cloud":
                return allowed, error, cloud_info

        # Verify local data integrity before using it
        usage = self.get_usage(user_id)
        signature_file = self.storage_dir / f".sig_{user_id}"

        if signature_file.exists():
            stored_sig = signature_file.read_text().strip()
            data = usage.to_dict()

            # Fetch cloud data for cross-validation if available
            cloud_data = self._cloud_sync.fetch_cloud_usage(user_id)

            is_valid, reason = self._integrity.detect_tampering(
                data, stored_sig, cloud_data
            )

            if not is_valid:
                self._tampering_detected[user_id] = True
                logger.error(f"Tampering detected for user {user_id}: {reason}")

                # Report to cloud for fraud detection
                try:
                    self._cloud_sync.sync_usage_to_cloud(
                        user_id,
                        "suspicious_activity",
                        0,
                        {"reason": reason, "local_data": data}
                    )
                except Exception:
                    pass

                return False, "Usage data integrity error. Please contact support.", {
                    "tampered": True,
                    "reason": reason
                }

        limits = UsageLimits.for_tier(tier)

        usage_info = {}

        if usage_type == UsageType.EXPORT:
            current_count = usage.exports.count
            count_limit = limits.exports_per_month
            current_minutes = usage.exports.value
            minutes_limit = limits.export_minutes_per_month
            usage_info = {
                "current": current_count,
                "limit": count_limit,
                "remaining": max(0, count_limit - current_count),
                "current_minutes": current_minutes,
                "minutes_limit": minutes_limit,
                "minutes_remaining": max(0, minutes_limit - current_minutes),
            }
            # Check both count and duration limits
            if current_count >= count_limit:
                return False, f"Monthly export limit reached ({count_limit} exports). Upgrade for more.", usage_info
            # Also check duration limit (increment is the video duration in minutes)
            if current_minutes + increment > minutes_limit:
                return False, f"Monthly export duration limit reached ({minutes_limit:.0f} minutes). Upgrade for more.", usage_info

        elif usage_type == UsageType.TTS_GENERATION:
            current = int(usage.tts_generations.value)  # Characters
            limit = limits.tts_characters_per_month
            usage_info = {
                "current": current,
                "limit": limit,
                "remaining": max(0, limit - current),
            }
            if current + increment > limit:
                return False, f"Monthly TTS character limit reached ({limit:,} chars). Upgrade for more.", usage_info

        elif usage_type == UsageType.AI_GENERATION:
            current = usage.ai_generations.count
            limit = limits.ai_requests_per_month
            usage_info = {
                "current": current,
                "limit": limit,
                "remaining": max(0, limit - current),
            }
            if current >= limit:
                return False, f"Monthly AI request limit reached ({limit} requests). Upgrade for more.", usage_info

        elif usage_type == UsageType.VOICE_CLONING:
            current = usage.voice_clones.count
            limit = limits.voice_clones_per_month
            usage_info = {
                "current": current,
                "limit": limit,
                "remaining": max(0, limit - current),
            }
            if current >= limit:
                return False, f"Monthly voice clone limit reached ({limit} clones). Upgrade for more.", usage_info

        elif usage_type == UsageType.STORAGE:
            current = usage.storage_mb
            limit = limits.storage_mb
            usage_info = {
                "current_mb": current,
                "limit_mb": limit,
                "remaining_mb": max(0, limit - current),
            }
            if current + increment > limit:
                return False, f"Storage limit reached ({limit} MB). Upgrade for more storage.", usage_info

        return True, None, usage_info

    def record_usage(
        self,
        user_id: str,
        usage_type: UsageType,
        count: int = 1,
        value: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Record usage for a user with cloud sync.

        Args:
            user_id: User identifier
            usage_type: Type of usage to record
            count: Number of items (e.g., 1 export)
            value: Value amount (e.g., 5.5 minutes, 1000 characters)
            metadata: Optional metadata for the usage record
        """
        # Check for detected tampering - block recording
        if self._tampering_detected.get(user_id, False):
            logger.error(f"Refusing to record usage for tampered user: {user_id}")
            raise ValueError("Usage data integrity error. Please contact support.")

        usage = self.get_usage(user_id)

        if usage_type == UsageType.EXPORT:
            usage.exports.count += count
            usage.exports.value += value  # Duration in minutes
        elif usage_type == UsageType.TTS_GENERATION:
            usage.tts_generations.count += count
            usage.tts_generations.value += value  # Characters
        elif usage_type == UsageType.AI_GENERATION:
            usage.ai_generations.count += count
            usage.ai_generations.value += value  # Tokens or requests
        elif usage_type == UsageType.VOICE_CLONING:
            usage.voice_clones.count += count
            usage.voice_clones.value += value  # Duration processed
        elif usage_type == UsageType.STORAGE:
            usage.storage_mb += value

        # Save locally with HMAC
        self._save_usage(user_id, usage)

        # Sync to cloud (async, with retry on failure)
        sync_amount = value if value > 0 else count
        self._cloud_sync.sync_usage_to_cloud(
            user_id,
            usage_type.value,
            sync_amount,
            metadata or {
                "recorded_at": datetime.now().isoformat(),
                "usage_type": usage_type.value,
            }
        )

        logger.info(f"Recorded usage for {user_id}: {usage_type.value} +{count} (value: {value})")

    def configure_cloud_sync(self, api_base: str, auth_token: str):
        """Configure cloud sync with API endpoint and auth token"""
        self._cloud_sync.configure(api_base, auth_token)
        logger.info(f"Cloud sync configured with endpoint: {api_base}")

    def sync_pending(self) -> int:
        """Sync any pending usage records to cloud. Returns count synced."""
        return self._cloud_sync.flush_pending_syncs()

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            "is_offline": self._cloud_sync.is_offline,
            "pending_syncs": self._cloud_sync.pending_sync_count,
            "tampering_detected_users": list(self._tampering_detected.keys()),
        }

    def get_usage_summary(self, user_id: str, tier: str) -> Dict[str, Any]:
        """
        Get a summary of usage for display in the UI.

        Returns all usage metrics with current values, limits, and percentages.
        """
        usage = self.get_usage(user_id)
        limits = UsageLimits.for_tier(tier)

        def calc_percentage(current: float, limit: float) -> float:
            if limit == 0:
                return 0.0
            return min(100.0, (current / limit) * 100)

        return {
            "period": self._get_current_month(),
            "last_updated": usage.last_updated,
            "exports": {
                "current": usage.exports.count,
                "limit": limits.exports_per_month,
                "percentage": calc_percentage(usage.exports.count, limits.exports_per_month),
                "duration_minutes": usage.exports.value,
                "duration_limit_minutes": limits.export_minutes_per_month,
            },
            "tts": {
                "current_characters": int(usage.tts_generations.value),
                "limit_characters": limits.tts_characters_per_month,
                "percentage": calc_percentage(usage.tts_generations.value, limits.tts_characters_per_month),
                "generations": usage.tts_generations.count,
            },
            "ai": {
                "current": usage.ai_generations.count,
                "limit": limits.ai_requests_per_month,
                "percentage": calc_percentage(usage.ai_generations.count, limits.ai_requests_per_month),
            },
            "voice_cloning": {
                "current": usage.voice_clones.count,
                "limit": limits.voice_clones_per_month,
                "percentage": calc_percentage(usage.voice_clones.count, limits.voice_clones_per_month),
            },
            "storage": {
                "current_mb": usage.storage_mb,
                "limit_mb": limits.storage_mb,
                "percentage": calc_percentage(usage.storage_mb, limits.storage_mb),
            },
        }

    def get_usage_history(self, user_id: str, usage_type: UsageType) -> list:
        """Get historical usage data for charts/analytics"""
        usage = self.get_usage(user_id)

        record_map = {
            UsageType.EXPORT: usage.exports,
            UsageType.TTS_GENERATION: usage.tts_generations,
            UsageType.AI_GENERATION: usage.ai_generations,
            UsageType.VOICE_CLONING: usage.voice_clones,
        }

        record = record_map.get(usage_type)
        if record:
            # Include current month in history
            history = list(record.history)
            history.append({
                "month": self._get_current_month(),
                "count": record.count,
                "value": record.value,
            })
            return history

        return []


# Global singleton instance
_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    """Get the global usage tracker instance"""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker
