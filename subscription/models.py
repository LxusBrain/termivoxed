"""
Subscription Data Models

Defines the core data structures for the subscription system.
Uses industry-standard patterns from Netflix, Spotify, and similar services.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json


class SubscriptionTier(str, Enum):
    """
    Subscription tiers with feature access levels.

    Pricing structure (aligned with PRODUCTION_PLAN.md):
    - FREE_TRIAL: 7-day trial with limited features (5 exports, 720p, watermark)
    - INDIVIDUAL: ₹149/$4.99/month - Essential features (200 exports/month)
    - PRO: ₹299/$9.99/month - All features (unlimited exports)
    - ENTERPRISE: ₹4,999/$59/month - Team features (40-50 users, 2000 exports)
    - LIFETIME: One-time Pro access (legacy, kept for existing users)
    """
    FREE_TRIAL = "free_trial"
    INDIVIDUAL = "individual"  # Was BASIC - renamed for clarity
    PRO = "pro"
    ENTERPRISE = "enterprise"  # NEW - for teams 40-50 users
    LIFETIME = "lifetime"
    EXPIRED = "expired"
    # Keep BASIC as alias for backward compatibility
    BASIC = "individual"


class SubscriptionStatus(str, Enum):
    """Subscription status states"""
    ACTIVE = "active"
    TRIAL = "trial"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"


@dataclass
class FeatureAccess:
    """
    Defines feature access per subscription tier.

    This is the core feature gating configuration.
    """
    # Core features (all tiers)
    basic_export: bool = True
    subtitle_generation: bool = True
    single_video_project: bool = True
    basic_tts_voices: bool = True

    # Basic tier features
    multi_video_projects: bool = False
    custom_fonts: bool = False
    basic_bgm: bool = False
    export_720p: bool = True
    export_1080p: bool = False

    # Pro tier features
    advanced_tts_voices: bool = False
    multiple_bgm_tracks: bool = False
    export_4k: bool = False
    batch_export: bool = False
    custom_subtitle_styles: bool = False
    cross_video_segments: bool = False
    priority_support: bool = False
    voice_cloning: bool = False  # Pro+ feature
    api_access: bool = False  # Pro+ feature

    # Enterprise tier features
    custom_branding: bool = False
    sso: bool = False
    team_management: bool = False

    # Project limits
    max_videos_per_project: int = 1
    max_segments_per_video: int = 5
    max_export_duration_minutes: int = 5
    max_bgm_tracks: int = 0

    # USAGE LIMITS PER MONTH - Single source of truth for tier limits
    # These values are authoritative and should be used by all modules:
    # - usage_tracker.py
    # - currency_handler.py
    # - cloud_functions/functions/index.js
    max_exports_per_month: int = 5
    max_tts_minutes_per_month: int = 10
    max_ai_requests_per_month: int = 10
    max_storage_mb: int = 500
    max_devices: int = 1

    @classmethod
    def for_tier(cls, tier: SubscriptionTier) -> 'FeatureAccess':
        """Get feature access for a specific tier"""
        if tier == SubscriptionTier.FREE_TRIAL:
            return cls.free_trial_features()
        elif tier in (SubscriptionTier.INDIVIDUAL, SubscriptionTier.BASIC):
            return cls.individual_features()
        elif tier in (SubscriptionTier.PRO, SubscriptionTier.LIFETIME):
            return cls.pro_features()
        elif tier == SubscriptionTier.ENTERPRISE:
            return cls.enterprise_features()
        else:
            return cls.expired_features()

    @classmethod
    def free_trial_features(cls) -> 'FeatureAccess':
        """Features for Free Trial (7 days, limited)"""
        return cls(
            basic_export=True,
            subtitle_generation=True,
            single_video_project=True,
            basic_tts_voices=True,
            multi_video_projects=False,
            custom_fonts=False,
            basic_bgm=False,
            export_720p=True,
            export_1080p=True,  # Allow 1080p in trial
            advanced_tts_voices=True,  # Full TTS in trial to show value
            multiple_bgm_tracks=False,
            export_4k=False,
            batch_export=False,
            custom_subtitle_styles=False,
            cross_video_segments=False,
            priority_support=False,
            voice_cloning=False,
            api_access=False,
            custom_branding=False,
            sso=False,
            team_management=False,
            max_videos_per_project=3,
            max_segments_per_video=10,
            max_export_duration_minutes=10,
            max_bgm_tracks=0,
            # Usage limits for trial
            max_exports_per_month=5,
            max_tts_minutes_per_month=10,
            max_ai_requests_per_month=10,
            max_storage_mb=500,
            max_devices=1
        )

    @classmethod
    def expired_features(cls) -> 'FeatureAccess':
        """Minimal features for expired subscriptions"""
        return cls(
            basic_export=True,
            subtitle_generation=True,
            single_video_project=True,
            basic_tts_voices=True,
            voice_cloning=False,
            api_access=False,
            custom_branding=False,
            sso=False,
            team_management=False,
            max_videos_per_project=1,
            max_segments_per_video=3,
            max_export_duration_minutes=2,
            max_bgm_tracks=0,
            # Minimal usage for expired - can view but limited exports
            max_exports_per_month=1,
            max_tts_minutes_per_month=1,
            max_ai_requests_per_month=1,
            max_storage_mb=100,
            max_devices=1
        )

    @classmethod
    def basic_features(cls) -> 'FeatureAccess':
        """Alias for individual_features (backward compatibility)"""
        return cls.individual_features()

    @classmethod
    def individual_features(cls) -> 'FeatureAccess':
        """Features for Individual tier (₹199/month) - 200 exports/month

        IMPORTANT: Individual tier must have AT LEAST everything FREE_TRIAL has,
        since paying customers should never have fewer features than trial users.
        """
        return cls(
            basic_export=True,
            subtitle_generation=True,
            single_video_project=True,
            basic_tts_voices=True,
            multi_video_projects=True,
            custom_fonts=True,
            basic_bgm=True,
            export_720p=True,
            export_1080p=True,
            advanced_tts_voices=True,  # Must match FREE_TRIAL - paid users get at least trial features
            multiple_bgm_tracks=False,
            export_4k=False,
            batch_export=False,
            custom_subtitle_styles=True,
            cross_video_segments=False,
            priority_support=True,  # Website says "Priority support" for Individual
            voice_cloning=False,  # PRO feature only
            api_access=False,  # PRO feature only
            custom_branding=False,
            sso=False,
            team_management=False,
            max_videos_per_project=5,
            max_segments_per_video=50,
            max_export_duration_minutes=30,
            max_bgm_tracks=1,
            # Usage limits for Individual tier
            max_exports_per_month=200,
            max_tts_minutes_per_month=60,
            max_ai_requests_per_month=100,
            max_storage_mb=5000,  # 5 GB
            max_devices=2
        )

    @classmethod
    def pro_features(cls) -> 'FeatureAccess':
        """Features for Pro tier (₹399/month) and Lifetime - Truly unlimited exports"""
        return cls(
            basic_export=True,
            subtitle_generation=True,
            single_video_project=True,
            basic_tts_voices=True,
            multi_video_projects=True,
            custom_fonts=True,
            basic_bgm=True,
            export_720p=True,
            export_1080p=True,
            advanced_tts_voices=True,
            multiple_bgm_tracks=True,
            export_4k=True,
            batch_export=True,
            custom_subtitle_styles=True,
            cross_video_segments=True,
            priority_support=True,
            voice_cloning=True,  # Website: "Voice cloning" for Pro
            api_access=True,  # Website: "API access" for Pro
            custom_branding=False,
            sso=False,
            team_management=False,
            max_videos_per_project=20,
            max_segments_per_video=200,
            max_export_duration_minutes=120,
            max_bgm_tracks=10,
            # Usage limits for Pro tier - TRULY UNLIMITED (use large number for compatibility)
            max_exports_per_month=999999,
            max_tts_minutes_per_month=999999,
            max_ai_requests_per_month=999999,
            max_storage_mb=100000,  # 100 GB
            max_devices=3
        )

    @classmethod
    def enterprise_features(cls) -> 'FeatureAccess':
        """Features for Enterprise tier (Custom pricing) - Truly unlimited for teams"""
        return cls(
            basic_export=True,
            subtitle_generation=True,
            single_video_project=True,
            basic_tts_voices=True,
            multi_video_projects=True,
            custom_fonts=True,
            basic_bgm=True,
            export_720p=True,
            export_1080p=True,
            advanced_tts_voices=True,
            multiple_bgm_tracks=True,
            export_4k=True,
            batch_export=True,
            custom_subtitle_styles=True,
            cross_video_segments=True,
            priority_support=True,
            voice_cloning=True,
            api_access=True,
            custom_branding=False,  # NOT IMPLEMENTED - removed from promises
            sso=False,  # NOT IMPLEMENTED - removed from promises
            team_management=False,  # NOT IMPLEMENTED - removed from promises
            max_videos_per_project=100,
            max_segments_per_video=999,
            max_export_duration_minutes=999,
            max_bgm_tracks=50,
            # Usage limits for Enterprise tier - TRULY UNLIMITED
            max_exports_per_month=999999,
            max_tts_minutes_per_month=999999,
            max_ai_requests_per_month=999999,
            max_storage_mb=500000,  # 500 GB
            max_devices=50
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'basic_export': self.basic_export,
            'subtitle_generation': self.subtitle_generation,
            'single_video_project': self.single_video_project,
            'basic_tts_voices': self.basic_tts_voices,
            'multi_video_projects': self.multi_video_projects,
            'custom_fonts': self.custom_fonts,
            'basic_bgm': self.basic_bgm,
            'export_720p': self.export_720p,
            'export_1080p': self.export_1080p,
            'advanced_tts_voices': self.advanced_tts_voices,
            'multiple_bgm_tracks': self.multiple_bgm_tracks,
            'export_4k': self.export_4k,
            'batch_export': self.batch_export,
            'custom_subtitle_styles': self.custom_subtitle_styles,
            'cross_video_segments': self.cross_video_segments,
            'priority_support': self.priority_support,
            'voice_cloning': self.voice_cloning,
            'api_access': self.api_access,
            'custom_branding': self.custom_branding,
            'sso': self.sso,
            'team_management': self.team_management,
            'max_videos_per_project': self.max_videos_per_project,
            'max_segments_per_video': self.max_segments_per_video,
            'max_export_duration_minutes': self.max_export_duration_minutes,
            'max_bgm_tracks': self.max_bgm_tracks,
            # Usage limits - single source of truth
            'max_exports_per_month': self.max_exports_per_month,
            'max_tts_minutes_per_month': self.max_tts_minutes_per_month,
            'max_ai_requests_per_month': self.max_ai_requests_per_month,
            'max_storage_mb': self.max_storage_mb,
            'max_devices': self.max_devices
        }


@dataclass
class DeviceInfo:
    """
    Device fingerprint information for single-device enforcement.

    Uses multiple identifiers to create a unique device fingerprint:
    - Hardware ID (machine-specific)
    - OS info
    - CPU info
    - Network MAC (optional)
    """
    device_id: str  # Unique generated ID for this device
    device_name: str  # User-friendly name (e.g., "John's MacBook Pro")
    os_type: str  # darwin, windows, linux
    os_version: str
    machine_id: str  # Hardware-based ID
    cpu_info: str
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    is_current: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'device_id': self.device_id,
            'device_name': self.device_name,
            'os_type': self.os_type,
            'os_version': self.os_version,
            'machine_id': self.machine_id,
            'cpu_info': self.cpu_info,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'is_current': self.is_current
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceInfo':
        """Create from dictionary"""
        return cls(
            device_id=data['device_id'],
            device_name=data['device_name'],
            os_type=data['os_type'],
            os_version=data['os_version'],
            machine_id=data['machine_id'],
            cpu_info=data['cpu_info'],
            first_seen=datetime.fromisoformat(data['first_seen']) if isinstance(data['first_seen'], str) else data['first_seen'],
            last_seen=datetime.fromisoformat(data['last_seen']) if isinstance(data['last_seen'], str) else data['last_seen'],
            is_current=data.get('is_current', True)
        )


@dataclass
class UserSubscription:
    """
    Complete user subscription information.

    This is the main subscription record stored in the cloud.
    """
    user_id: str
    email: str
    tier: SubscriptionTier
    status: SubscriptionStatus

    # Subscription dates
    started_at: datetime
    expires_at: Optional[datetime]
    trial_ends_at: Optional[datetime]

    # Payment info (for display only, actual payment handled by Stripe/etc)
    payment_method: Optional[str] = None
    next_billing_date: Optional[datetime] = None

    # Device management
    current_device: Optional[DeviceInfo] = None
    device_history: List[DeviceInfo] = field(default_factory=list)

    # Feature access (computed from tier)
    features: Optional[FeatureAccess] = None

    def __post_init__(self):
        """Initialize feature access based on tier"""
        if self.features is None:
            self.features = FeatureAccess.for_tier(self.tier)

    def is_active(self) -> bool:
        """Check if subscription is active"""
        if self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
            if self.expires_at and datetime.now() > self.expires_at:
                return False
            return True
        return False

    def days_remaining(self) -> int:
        """Get days remaining in subscription"""
        if not self.expires_at:
            return 999 if self.tier == SubscriptionTier.LIFETIME else 0

        remaining = (self.expires_at - datetime.now()).days
        return max(0, remaining)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'user_id': self.user_id,
            'email': self.email,
            'tier': self.tier.value,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'payment_method': self.payment_method,
            'next_billing_date': self.next_billing_date.isoformat() if self.next_billing_date else None,
            'current_device': self.current_device.to_dict() if self.current_device else None,
            'device_history': [d.to_dict() for d in self.device_history],
            'features': self.features.to_dict() if self.features else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UserSubscription':
        """Create from dictionary"""
        current_device = None
        if data.get('current_device'):
            current_device = DeviceInfo.from_dict(data['current_device'])

        device_history = []
        if data.get('device_history'):
            device_history = [DeviceInfo.from_dict(d) for d in data['device_history']]

        return cls(
            user_id=data['user_id'],
            email=data['email'],
            tier=SubscriptionTier(data['tier']),
            status=SubscriptionStatus(data['status']),
            started_at=datetime.fromisoformat(data['started_at']) if isinstance(data['started_at'], str) else data['started_at'],
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
            trial_ends_at=datetime.fromisoformat(data['trial_ends_at']) if data.get('trial_ends_at') else None,
            payment_method=data.get('payment_method'),
            next_billing_date=datetime.fromisoformat(data['next_billing_date']) if data.get('next_billing_date') else None,
            current_device=current_device,
            device_history=device_history
        )


@dataclass
class LicenseToken:
    """
    JWT-based license token for offline verification.

    This token is:
    - Issued by the cloud server
    - Signed with server's private key
    - Cached locally for offline use
    - Has a grace period for offline operation

    Based on proven patterns from Adobe, JetBrains, etc.
    """
    token: str  # JWT token string
    user_id: str
    email: str
    tier: SubscriptionTier
    features: FeatureAccess

    # Token validity
    issued_at: datetime
    expires_at: datetime

    # Device binding
    device_id: str
    device_fingerprint: str

    # Offline grace period
    offline_grace_hours: int = 72  # 3 days offline grace
    last_online_check: datetime = field(default_factory=datetime.now)

    def is_valid(self) -> bool:
        """Check if token is still valid"""
        now = datetime.now()

        # Check expiration
        if now > self.expires_at:
            return False

        # Check offline grace period
        offline_duration = now - self.last_online_check
        if offline_duration > timedelta(hours=self.offline_grace_hours):
            return False

        return True

    def needs_refresh(self) -> bool:
        """Check if token should be refreshed"""
        now = datetime.now()

        # Refresh if within 24 hours of expiration
        if (self.expires_at - now) < timedelta(hours=24):
            return True

        # Refresh if offline for more than 24 hours
        if (now - self.last_online_check) > timedelta(hours=24):
            return True

        return False

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'token': self.token,
            'user_id': self.user_id,
            'email': self.email,
            'tier': self.tier.value,
            'features': self.features.to_dict(),
            'issued_at': self.issued_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'device_id': self.device_id,
            'device_fingerprint': self.device_fingerprint,
            'offline_grace_hours': self.offline_grace_hours,
            'last_online_check': self.last_online_check.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'LicenseToken':
        """Create from dictionary"""
        features_data = data.get('features', {})
        features = FeatureAccess(**features_data) if features_data else FeatureAccess.expired_features()

        return cls(
            token=data['token'],
            user_id=data['user_id'],
            email=data['email'],
            tier=SubscriptionTier(data['tier']),
            features=features,
            issued_at=datetime.fromisoformat(data['issued_at']) if isinstance(data['issued_at'], str) else data['issued_at'],
            expires_at=datetime.fromisoformat(data['expires_at']) if isinstance(data['expires_at'], str) else data['expires_at'],
            device_id=data['device_id'],
            device_fingerprint=data['device_fingerprint'],
            offline_grace_hours=data.get('offline_grace_hours', 72),
            last_online_check=datetime.fromisoformat(data['last_online_check']) if isinstance(data.get('last_online_check'), str) else datetime.now()
        )


# Pricing configuration (for reference)
# India-focused affordable pricing strategy
PRICING = {
    SubscriptionTier.FREE_TRIAL: {
        'price': 0,
        'price_inr': 0,
        'duration_days': 7,
        'description': 'Try all Pro features free for 7 days',
        'description_inr': '7 दिन के लिए सभी Pro फीचर्स मुफ्त'
    },
    SubscriptionTier.BASIC: {
        'price_monthly': 2.49,  # ~₹199
        'price_yearly': 24.99,  # ~₹1,999
        'price_monthly_inr': 199,
        'price_yearly_inr': 1999,
        'savings_yearly_inr': 389,  # 2 months free
        'savings_percent': 16,
        'description': 'Essential features for content creators',
        'description_inr': 'कंटेंट क्रिएटर्स के लिए जरूरी फीचर्स'
    },
    SubscriptionTier.PRO: {
        'price_monthly': 4.99,  # ~₹399
        'price_yearly': 49.99,  # ~₹3,999
        'price_monthly_inr': 399,
        'price_yearly_inr': 3999,
        'savings_yearly_inr': 789,  # 2 months free
        'savings_percent': 16,
        'description': 'All features for professional creators',
        'description_inr': 'प्रोफेशनल क्रिएटर्स के लिए सभी फीचर्स'
    },
    SubscriptionTier.LIFETIME: {
        'price': 62.49,  # ~₹4,999
        'price_inr': 4999,
        'equivalent_months': 12,  # Equivalent to ~12 months of Pro
        'description': 'One-time purchase, lifetime Pro access',
        'description_inr': 'एक बार भुगतान, जीवन भर Pro एक्सेस'
    }
}

# Payment processor fees reference
PAYMENT_FEES = {
    'razorpay': {'percent': 2.0, 'fixed': 0},
    'cashfree': {'percent': 1.9, 'fixed': 0},
    'stripe': {'percent': 2.9, 'fixed': 2.5},  # ₹2.5 fixed
    'payu': {'percent': 2.0, 'fixed': 0},
}

def calculate_net_revenue(price_inr: float, processor: str = 'razorpay') -> float:
    """Calculate net revenue after payment processor fees"""
    fees = PAYMENT_FEES.get(processor, PAYMENT_FEES['razorpay'])
    fee_amount = (price_inr * fees['percent'] / 100) + fees['fixed']
    return price_inr - fee_amount

# Net revenue examples:
# Basic Monthly ₹199 → ₹195.02 (after 2% Razorpay)
# Pro Monthly ₹399 → ₹391.02
# Pro Yearly ₹3,999 → ₹3,919.02
# Lifetime ₹4,999 → ₹4,899.02
