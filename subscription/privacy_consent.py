"""
Privacy Consent Management for TermiVoxed

This module handles user consent for:
- Device fingerprinting
- Data collection and processing
- Analytics and usage tracking

Compliant with:
- GDPR (EU General Data Protection Regulation)
- CCPA (California Consumer Privacy Act)
- India DPDP Act 2023 (Digital Personal Data Protection)

Usage:
    consent_manager = PrivacyConsentManager()

    # Check if consent is needed
    if consent_manager.needs_consent():
        # Show consent dialog to user
        user_consent = show_consent_dialog()
        consent_manager.record_consent(user_consent)

    # Check specific consent
    if consent_manager.has_consent("device_fingerprinting"):
        fingerprint = get_device_fingerprint()
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ConsentType(str, Enum):
    """Types of consent that can be given or withdrawn"""

    # Required for app functionality
    DEVICE_FINGERPRINTING = "device_fingerprinting"
    LICENSE_VERIFICATION = "license_verification"

    # Required for TTS functionality
    THIRD_PARTY_TTS = "third_party_tts"

    # Optional
    USAGE_ANALYTICS = "usage_analytics"
    ERROR_REPORTING = "error_reporting"
    MARKETING_EMAILS = "marketing_emails"


class ConsentStatus(str, Enum):
    """Status of consent"""

    NOT_ASKED = "not_asked"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"


@dataclass
class ConsentRecord:
    """Record of a single consent decision"""

    consent_type: str
    status: str
    timestamp: str  # ISO format
    version: str  # Privacy policy version
    method: str  # How consent was collected: "explicit_click", "implied", "api"
    ip_hash: Optional[str] = None  # Hashed IP for audit (not identifying)


@dataclass
class UserConsent:
    """Complete user consent state"""

    user_id: Optional[str] = None
    consents: Dict[str, ConsentRecord] = field(default_factory=dict)
    privacy_policy_version: str = "1.0.0"
    first_consent_date: Optional[str] = None
    last_updated: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "user_id": self.user_id,
            "consents": {k: asdict(v) for k, v in self.consents.items()},
            "privacy_policy_version": self.privacy_policy_version,
            "first_consent_date": self.first_consent_date,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserConsent":
        """Create from dictionary"""
        consents = {}
        for k, v in data.get("consents", {}).items():
            consents[k] = ConsentRecord(**v)

        return cls(
            user_id=data.get("user_id"),
            consents=consents,
            privacy_policy_version=data.get("privacy_policy_version", "1.0.0"),
            first_consent_date=data.get("first_consent_date"),
            last_updated=data.get("last_updated"),
        )


# Consent requirements per region
CONSENT_REQUIREMENTS = {
    "default": {
        ConsentType.DEVICE_FINGERPRINTING: {
            "required_for_app": True,
            "requires_explicit_consent": True,
            "description": "We collect hardware identifiers to verify your license and prevent unauthorized use.",
            "description_simple": "Device ID for license verification",
        },
        ConsentType.LICENSE_VERIFICATION: {
            "required_for_app": True,
            "requires_explicit_consent": True,
            "description": "We verify your license with our servers to ensure authorized use.",
            "description_simple": "License check with our servers",
        },
        ConsentType.THIRD_PARTY_TTS: {
            "required_for_app": False,
            "required_for_feature": True,
            "feature_name": "Text-to-Speech",
            "requires_explicit_consent": True,
            "description": (
                "Your script text is sent to Microsoft's servers for voice generation. "
                "Microsoft processes this data according to their privacy policy. "
                "We do not control how Microsoft stores or uses this data. "
                "Do not include sensitive personal information in your scripts."
            ),
            "description_simple": "Text sent to Microsoft for voice generation",
            "third_party": {
                "name": "Microsoft",
                "service": "Edge Text-to-Speech",
                "privacy_policy": "https://privacy.microsoft.com/privacystatement",
                "data_sent": ["Script text", "Voice selection", "Speech parameters"],
                "data_retention": "Unknown (Microsoft controlled)",
            },
            "warning": (
                "Your script content will be transmitted to external servers. "
                "Avoid including passwords, personal data, or confidential information."
            ),
        },
        ConsentType.USAGE_ANALYTICS: {
            "required_for_app": False,
            "requires_explicit_consent": True,
            "description": "We collect anonymous usage data to improve the app.",
            "description_simple": "Anonymous usage statistics",
        },
        ConsentType.ERROR_REPORTING: {
            "required_for_app": False,
            "requires_explicit_consent": True,
            "description": "We collect crash reports to fix bugs faster.",
            "description_simple": "Crash reports for bug fixes",
        },
        ConsentType.MARKETING_EMAILS: {
            "required_for_app": False,
            "requires_explicit_consent": True,
            "description": "Receive updates about new features and special offers.",
            "description_simple": "Product updates and offers",
        },
    },
    # GDPR (EU) - stricter requirements
    "eu": {
        # Same as default but with stricter enforcement
    },
    # India DPDP - requires explicit consent
    "india": {
        # Same as default
    },
}


class PrivacyConsentManager:
    """
    Manages user privacy consent.

    Features:
    - Persistent storage of consent decisions
    - Audit trail of consent changes
    - Region-specific consent requirements
    - Easy integration with UI
    """

    CONSENT_FILE = ".termivoxed_consent.json"
    CURRENT_POLICY_VERSION = "1.0.0"

    # Required consents for app to function
    REQUIRED_CONSENTS = [
        ConsentType.DEVICE_FINGERPRINTING,
        ConsentType.LICENSE_VERIFICATION,
    ]

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize consent manager.

        Args:
            storage_path: Path to store consent file. Defaults to user home.
        """
        self._storage_path = storage_path or self._get_default_storage_path()
        self._consent: Optional[UserConsent] = None
        self._load_consent()

    def _get_default_storage_path(self) -> Path:
        """Get default path for consent storage"""
        home = Path.home()
        consent_dir = home / ".termivoxed"
        consent_dir.mkdir(parents=True, exist_ok=True)
        return consent_dir / self.CONSENT_FILE

    def _load_consent(self) -> None:
        """Load consent from disk"""
        try:
            if self._storage_path.exists():
                data = json.loads(self._storage_path.read_text())
                self._consent = UserConsent.from_dict(data)
                logger.debug("Loaded consent from disk")
            else:
                self._consent = UserConsent()
        except Exception as e:
            logger.warning(f"Failed to load consent: {e}")
            self._consent = UserConsent()

    def _save_consent(self) -> None:
        """Save consent to disk"""
        try:
            self._storage_path.write_text(
                json.dumps(self._consent.to_dict(), indent=2)
            )
            logger.debug("Saved consent to disk")
        except Exception as e:
            logger.error(f"Failed to save consent: {e}")

    def needs_consent(self) -> bool:
        """
        Check if user needs to provide consent.

        Returns True if:
        - No consent has been recorded
        - Privacy policy version has changed
        - Required consents are missing
        """
        if not self._consent.first_consent_date:
            return True

        # Check if policy version changed
        if self._consent.privacy_policy_version != self.CURRENT_POLICY_VERSION:
            return True

        # Check required consents
        for consent_type in self.REQUIRED_CONSENTS:
            if not self.has_consent(consent_type.value):
                return True

        return False

    def has_consent(self, consent_type: str) -> bool:
        """
        Check if user has granted a specific consent.

        Args:
            consent_type: Type of consent to check

        Returns:
            True if consent is granted, False otherwise
        """
        record = self._consent.consents.get(consent_type)
        if not record:
            return False

        return record.status == ConsentStatus.GRANTED.value

    def get_consent_status(self, consent_type: str) -> ConsentStatus:
        """Get the current status of a consent type"""
        record = self._consent.consents.get(consent_type)
        if not record:
            return ConsentStatus.NOT_ASKED

        return ConsentStatus(record.status)

    def record_consent(
        self,
        consent_type: str,
        granted: bool,
        method: str = "explicit_click",
        user_id: Optional[str] = None,
    ) -> None:
        """
        Record a user's consent decision.

        Args:
            consent_type: Type of consent
            granted: Whether consent was granted
            method: How consent was collected
            user_id: Optional user ID to associate
        """
        now = datetime.now(timezone.utc).isoformat()

        record = ConsentRecord(
            consent_type=consent_type,
            status=ConsentStatus.GRANTED.value if granted else ConsentStatus.DENIED.value,
            timestamp=now,
            version=self.CURRENT_POLICY_VERSION,
            method=method,
        )

        self._consent.consents[consent_type] = record
        self._consent.last_updated = now

        if not self._consent.first_consent_date:
            self._consent.first_consent_date = now

        if user_id:
            self._consent.user_id = user_id

        self._consent.privacy_policy_version = self.CURRENT_POLICY_VERSION

        self._save_consent()

        logger.info(
            f"Recorded consent: {consent_type} = {'granted' if granted else 'denied'}"
        )

    def record_all_consents(
        self,
        consents: Dict[str, bool],
        method: str = "explicit_click",
        user_id: Optional[str] = None,
    ) -> None:
        """
        Record multiple consent decisions at once.

        Args:
            consents: Dict mapping consent types to granted status
            method: How consent was collected
            user_id: Optional user ID
        """
        for consent_type, granted in consents.items():
            self.record_consent(consent_type, granted, method, user_id)

    def withdraw_consent(self, consent_type: str) -> None:
        """
        Withdraw a previously granted consent.

        Args:
            consent_type: Type of consent to withdraw
        """
        now = datetime.now(timezone.utc).isoformat()

        record = ConsentRecord(
            consent_type=consent_type,
            status=ConsentStatus.WITHDRAWN.value,
            timestamp=now,
            version=self.CURRENT_POLICY_VERSION,
            method="user_withdrawal",
        )

        self._consent.consents[consent_type] = record
        self._consent.last_updated = now
        self._save_consent()

        logger.info(f"Consent withdrawn: {consent_type}")

    def get_all_consents(self) -> Dict[str, Dict[str, Any]]:
        """Get all consent statuses for display"""
        result = {}

        for consent_type in ConsentType:
            record = self._consent.consents.get(consent_type.value)
            requirement = CONSENT_REQUIREMENTS["default"].get(consent_type, {})

            result[consent_type.value] = {
                "status": record.status if record else ConsentStatus.NOT_ASKED.value,
                "timestamp": record.timestamp if record else None,
                "required_for_app": requirement.get("required_for_app", False),
                "description": requirement.get("description", ""),
                "description_simple": requirement.get("description_simple", ""),
            }

        return result

    def get_consent_summary(self) -> str:
        """Get a human-readable summary of consent status"""
        lines = ["Privacy Consent Status:", "=" * 40]

        for consent_type, info in self.get_all_consents().items():
            status = info["status"]
            required = " (Required)" if info["required_for_app"] else ""
            lines.append(f"  {consent_type}: {status}{required}")

        lines.append("=" * 40)
        lines.append(f"Policy Version: {self._consent.privacy_policy_version}")
        lines.append(f"Last Updated: {self._consent.last_updated or 'Never'}")

        return "\n".join(lines)

    def export_consent_data(self) -> Dict[str, Any]:
        """
        Export all consent data for GDPR data portability.

        Returns a complete record of all consent decisions.
        """
        return {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "user_id": self._consent.user_id,
            "policy_version": self._consent.privacy_policy_version,
            "first_consent_date": self._consent.first_consent_date,
            "last_updated": self._consent.last_updated,
            "consents": [
                {
                    "type": k,
                    "status": v.status,
                    "timestamp": v.timestamp,
                    "policy_version": v.version,
                    "method": v.method,
                }
                for k, v in self._consent.consents.items()
            ],
        }

    def clear_all_consent(self) -> None:
        """
        Clear all consent data.

        Used when user requests data deletion.
        """
        self._consent = UserConsent()
        if self._storage_path.exists():
            self._storage_path.unlink()

        logger.info("All consent data cleared")

    def can_use_app(self) -> tuple[bool, List[str]]:
        """
        Check if app can be used based on required consents.

        Returns:
            Tuple of (can_use, list of missing required consents)
        """
        missing = []

        for consent_type in self.REQUIRED_CONSENTS:
            if not self.has_consent(consent_type.value):
                missing.append(consent_type.value)

        return len(missing) == 0, missing


def get_consent_dialog_content() -> Dict[str, Any]:
    """
    Get content for the consent dialog UI.

    Returns structured data for rendering consent UI.
    """
    return {
        "title": "Privacy & Data Collection",
        "introduction": (
            "TermiVoxed collects certain data to provide and improve our service. "
            "Please review and consent to the following:"
        ),
        "required_section": {
            "title": "Required for App Functionality",
            "description": "These are necessary for the app to work properly.",
            "items": [
                {
                    "id": ConsentType.DEVICE_FINGERPRINTING.value,
                    "title": "Device Identification",
                    "description": (
                        "We collect hardware identifiers (device ID, serial numbers) "
                        "to verify your license and prevent unauthorized use. "
                        "This data is hashed and cannot identify you personally."
                    ),
                    "required": True,
                },
                {
                    "id": ConsentType.LICENSE_VERIFICATION.value,
                    "title": "License Verification",
                    "description": (
                        "We verify your subscription status with our servers "
                        "to ensure you have access to the features you paid for."
                    ),
                    "required": True,
                },
            ],
        },
        "feature_consent_section": {
            "title": "Feature-Specific Consent",
            "description": "These features require sending data to third-party services.",
            "items": [
                {
                    "id": ConsentType.THIRD_PARTY_TTS.value,
                    "title": "Text-to-Speech (Voice Generation)",
                    "description": (
                        "Your script text is sent to Microsoft's servers for voice generation. "
                        "Microsoft processes this data according to their privacy policy. "
                        "We do not control how Microsoft stores or uses this data."
                    ),
                    "warning": (
                        "Do not include passwords, personal data, or confidential "
                        "business information in your scripts."
                    ),
                    "required": False,
                    "required_for_feature": True,
                    "feature_name": "Voice Generation",
                    "default": False,
                    "third_party": {
                        "name": "Microsoft",
                        "privacy_policy": "https://privacy.microsoft.com/privacystatement",
                    },
                },
            ],
        },
        "optional_section": {
            "title": "Optional (Help Us Improve)",
            "description": "These help us make the app better but are not required.",
            "items": [
                {
                    "id": ConsentType.USAGE_ANALYTICS.value,
                    "title": "Usage Analytics",
                    "description": (
                        "Anonymous data about how you use the app helps us "
                        "understand which features are popular and what to improve."
                    ),
                    "required": False,
                    "default": True,
                },
                {
                    "id": ConsentType.ERROR_REPORTING.value,
                    "title": "Error Reporting",
                    "description": (
                        "Automatic crash reports help us identify and fix bugs faster."
                    ),
                    "required": False,
                    "default": True,
                },
                {
                    "id": ConsentType.MARKETING_EMAILS.value,
                    "title": "Product Updates",
                    "description": (
                        "Receive occasional emails about new features and special offers."
                    ),
                    "required": False,
                    "default": False,
                },
            ],
        },
        "privacy_policy_link": "https://termivoxed.com/privacy",
        "terms_link": "https://termivoxed.com/terms",
        "buttons": {
            "accept_all": "Accept All",
            "accept_required": "Accept Required Only",
            "customize": "Customize",
            "decline": "Decline & Exit",
        },
        "legal_text": (
            "By clicking 'Accept', you agree to our Privacy Policy and Terms of Service. "
            "You can change these settings anytime in Settings > Privacy."
        ),
    }


# Singleton instance (for backwards compatibility with desktop mode)
_consent_manager: Optional[PrivacyConsentManager] = None

# Per-user consent managers cache
_user_consent_managers: Dict[str, PrivacyConsentManager] = {}


def get_consent_manager() -> PrivacyConsentManager:
    """Get the singleton consent manager instance (desktop mode)"""
    global _consent_manager

    if _consent_manager is None:
        _consent_manager = PrivacyConsentManager()

    return _consent_manager


def get_user_consent_manager(user_id: str) -> PrivacyConsentManager:
    """
    Get a consent manager for a specific user (SaaS mode).

    Uses per-user storage to isolate consent data between users.

    Args:
        user_id: Firebase user ID

    Returns:
        PrivacyConsentManager instance for the user
    """
    if user_id not in _user_consent_managers:
        # Create user-specific storage path
        home = Path.home()
        consent_dir = home / ".termivoxed" / "user_consents"
        consent_dir.mkdir(parents=True, exist_ok=True)
        storage_path = consent_dir / f"{user_id}.json"

        manager = PrivacyConsentManager(storage_path=storage_path)
        manager._consent.user_id = user_id
        _user_consent_managers[user_id] = manager

    return _user_consent_managers[user_id]


# Convenience functions
def has_required_consent() -> bool:
    """Check if all required consents are granted"""
    manager = get_consent_manager()
    can_use, _ = manager.can_use_app()
    return can_use


def needs_consent_dialog() -> bool:
    """Check if consent dialog should be shown"""
    return get_consent_manager().needs_consent()


# TTS-specific consent functions
def has_tts_consent() -> bool:
    """Check if user has consented to third-party TTS usage"""
    return get_consent_manager().has_consent(ConsentType.THIRD_PARTY_TTS.value)


def needs_tts_consent() -> bool:
    """Check if TTS consent dialog should be shown"""
    status = get_consent_manager().get_consent_status(ConsentType.THIRD_PARTY_TTS.value)
    return status == ConsentStatus.NOT_ASKED


def record_tts_consent(granted: bool) -> None:
    """Record user's TTS consent decision"""
    get_consent_manager().record_consent(
        ConsentType.THIRD_PARTY_TTS.value,
        granted,
        method="explicit_click"
    )


def get_tts_consent_dialog_content() -> Dict[str, Any]:
    """
    Get content specifically for TTS consent dialog.

    This is shown when user first attempts to use TTS features.
    """
    return {
        "title": "Text-to-Speech Privacy Notice",
        "icon": "alert_triangle",  # lucide icon name
        "introduction": (
            "Voice generation requires sending your script text to external servers."
        ),
        "details": {
            "what_is_sent": {
                "title": "What data is sent?",
                "items": [
                    "Your script/subtitle text",
                    "Selected voice and language",
                    "Speech parameters (rate, pitch, volume)",
                ],
            },
            "where_is_sent": {
                "title": "Where is it sent?",
                "provider": "Microsoft Edge Text-to-Speech",
                "privacy_policy": "https://privacy.microsoft.com/privacystatement",
                "note": (
                    "This service is provided by Microsoft. We do not control "
                    "how Microsoft processes, stores, or uses your data."
                ),
            },
            "recommendations": {
                "title": "Recommendations",
                "items": [
                    "Do not include passwords or API keys in scripts",
                    "Avoid personal information (names, addresses, phone numbers)",
                    "Do not include confidential business information",
                    "Review scripts before generating audio",
                ],
            },
        },
        "warning_banner": {
            "icon": "shield_alert",
            "text": (
                "Your script content will be transmitted to Microsoft's servers. "
                "This data may be logged and retained according to Microsoft's policies."
            ),
            "style": "warning",  # warning, error, info
        },
        "buttons": {
            "accept": {
                "label": "I Understand, Enable TTS",
                "style": "primary",
            },
            "decline": {
                "label": "No Thanks",
                "style": "secondary",
            },
            "learn_more": {
                "label": "Learn More",
                "url": "https://privacy.microsoft.com/privacystatement",
                "style": "link",
            },
        },
        "remember_choice": {
            "label": "Remember my choice",
            "default": True,
        },
        "footer_text": (
            "You can change this setting anytime in Settings > Privacy. "
            "Declining will disable voice generation features."
        ),
    }


def get_tts_warning_banner() -> Dict[str, str]:
    """Get content for inline TTS warning banner shown in voice sections"""
    return {
        "icon": "cloud_upload",
        "title": "External Processing",
        "message": (
            "Text is sent to Microsoft for voice generation. "
            "Avoid sensitive content."
        ),
        "link_text": "Privacy Info",
        "link_action": "show_tts_consent_details",
    }


if __name__ == "__main__":
    # Test the consent manager
    import sys

    logging.basicConfig(level=logging.DEBUG)

    manager = PrivacyConsentManager()

    print(manager.get_consent_summary())
    print()

    print("Needs consent:", manager.needs_consent())
    print("Can use app:", manager.can_use_app())
    print()

    # Simulate granting consent
    print("Recording consent...")
    manager.record_all_consents({
        ConsentType.DEVICE_FINGERPRINTING.value: True,
        ConsentType.LICENSE_VERIFICATION.value: True,
        ConsentType.USAGE_ANALYTICS.value: True,
        ConsentType.ERROR_REPORTING.value: True,
        ConsentType.MARKETING_EMAILS.value: False,
    })

    print()
    print(manager.get_consent_summary())
    print()
    print("Can use app:", manager.can_use_app())
