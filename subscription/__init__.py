"""
Subscription Management System for Termivoxed

This module implements a proven subscription model based on industry standards:
- Local-first processing (privacy-focused)
- Cloud-verified subscription tracking
- Single device enforcement (like Netflix/Jio Hotstar)
- Device fingerprinting for security
- JWT-based license tokens

Architecture:
- Local app sends subscription verification requests to cloud
- Cloud validates and returns signed license token
- Local app caches license token for offline grace period
- Device fingerprint ensures single-device enforcement
"""

from subscription.models import (
    SubscriptionTier,
    SubscriptionStatus,
    UserSubscription,
    LicenseToken,
    DeviceInfo,
    FeatureAccess
)
from subscription.license_manager import LicenseManager
from subscription.feature_gate import FeatureGate, feature_required, can_export_resolution
from subscription.usage_tracker import (
    UsageTracker,
    UsageType,
    UsageLimits,
    get_usage_tracker,
)
from subscription.phone_verification import (
    PhoneVerificationService,
    VerificationStatus,
    get_phone_verification_service,
)
from subscription.email_service import (
    EmailService,
    EmailTemplates,
    get_email_service,
)
from subscription.invoice_generator import (
    InvoicePDFGenerator,
    Invoice,
    get_invoice_generator,
)

__all__ = [
    # Core subscription
    'SubscriptionTier',
    'SubscriptionStatus',
    'UserSubscription',
    'LicenseToken',
    'DeviceInfo',
    'FeatureAccess',
    'LicenseManager',
    'FeatureGate',
    'feature_required',
    'can_export_resolution',
    # Usage tracking
    'UsageTracker',
    'UsageType',
    'UsageLimits',
    'get_usage_tracker',
    # Phone verification
    'PhoneVerificationService',
    'VerificationStatus',
    'get_phone_verification_service',
    # Email service
    'EmailService',
    'EmailTemplates',
    'get_email_service',
    # Invoice generation
    'InvoicePDFGenerator',
    'Invoice',
    'get_invoice_generator',
]
