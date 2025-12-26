"""
Feature Gate System - Controls access to features based on subscription

Implements proven feature gating patterns:
- Decorator-based access control
- Runtime feature checks
- Graceful degradation
- Upgrade prompts

Usage:
    # Decorator-based (for functions)
    @feature_required('multiple_bgm_tracks')
    async def add_bgm_track(...):
        ...

    # Runtime check
    if FeatureGate.has_feature('export_4k'):
        enable_4k_option()

    # Limit check
    can_add, reason = FeatureGate.check_limit('max_videos_per_project', current_count)
"""

from functools import wraps
from typing import Optional, Tuple, Callable, Any
from subscription.license_manager import get_license_manager
from subscription.models import FeatureAccess, SubscriptionTier
from utils.logger import logger


class FeatureGateError(Exception):
    """Raised when a feature is not available"""

    def __init__(self, feature: str, required_tier: str, message: str):
        self.feature = feature
        self.required_tier = required_tier
        self.message = message
        super().__init__(message)


class FeatureGate:
    """
    Controls access to features based on subscription tier.

    This is the central point for all feature access checks.
    """

    # Feature to tier mapping (minimum tier required)
    # Aligned with PRODUCTION_PLAN.md tier structure
    FEATURE_REQUIREMENTS = {
        # Individual tier features (was BASIC)
        'multi_video_projects': SubscriptionTier.INDIVIDUAL,
        'custom_fonts': SubscriptionTier.INDIVIDUAL,
        'basic_bgm': SubscriptionTier.INDIVIDUAL,
        'export_1080p': SubscriptionTier.INDIVIDUAL,
        'custom_subtitle_styles': SubscriptionTier.INDIVIDUAL,

        # Pro tier features
        'advanced_tts_voices': SubscriptionTier.PRO,
        'multiple_bgm_tracks': SubscriptionTier.PRO,
        'export_4k': SubscriptionTier.PRO,
        'batch_export': SubscriptionTier.PRO,
        'cross_video_segments': SubscriptionTier.PRO,
        'voice_cloning': SubscriptionTier.PRO,
        'priority_support': SubscriptionTier.PRO,

        # Enterprise tier features
        'sso': SubscriptionTier.ENTERPRISE,
        'team_management': SubscriptionTier.ENTERPRISE,
        'api_access': SubscriptionTier.ENTERPRISE,
        'custom_branding': SubscriptionTier.ENTERPRISE,
    }

    # Tier hierarchy for comparison (higher = more features)
    # CORRECTED: Trial should NOT have more features than paid tiers
    TIER_HIERARCHY = {
        SubscriptionTier.EXPIRED: 0,
        SubscriptionTier.FREE_TRIAL: 1,  # Trial = limited features
        SubscriptionTier.INDIVIDUAL: 2,  # Was BASIC
        SubscriptionTier.BASIC: 2,  # Alias for INDIVIDUAL
        SubscriptionTier.PRO: 3,
        SubscriptionTier.LIFETIME: 3,  # Lifetime = Pro
        SubscriptionTier.ENTERPRISE: 4,  # Enterprise = highest
    }

    @classmethod
    def get_features(cls) -> FeatureAccess:
        """Get current feature access"""
        license_manager = get_license_manager()
        return license_manager.get_features()

    @classmethod
    def has_feature(cls, feature_name: str) -> bool:
        """
        Check if a specific feature is available.

        Args:
            feature_name: Name of the feature to check

        Returns:
            True if feature is available
        """
        features = cls.get_features()

        # Check if feature exists on FeatureAccess
        if hasattr(features, feature_name):
            return getattr(features, feature_name)

        # Check by required tier
        if feature_name in cls.FEATURE_REQUIREMENTS:
            required_tier = cls.FEATURE_REQUIREMENTS[feature_name]
            current_tier = get_license_manager().get_subscription_tier()

            current_level = cls.TIER_HIERARCHY.get(current_tier, 0)
            required_level = cls.TIER_HIERARCHY.get(required_tier, 0)

            return current_level >= required_level

        # Default to allowed if not restricted
        return True

    @classmethod
    def check_limit(cls, limit_name: str, current_value: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a limit would be exceeded.

        Args:
            limit_name: Name of the limit (e.g., 'max_videos_per_project')
            current_value: Current count

        Returns:
            Tuple of (is_allowed, error_message)
        """
        features = cls.get_features()

        if hasattr(features, limit_name):
            max_value = getattr(features, limit_name)
            if current_value >= max_value:
                return False, f"Limit reached: maximum {limit_name.replace('_', ' ')} is {max_value}. Upgrade to increase."
            return True, None

        return True, None

    @classmethod
    def get_required_tier(cls, feature_name: str) -> Optional[SubscriptionTier]:
        """Get the minimum tier required for a feature"""
        return cls.FEATURE_REQUIREMENTS.get(feature_name)

    @classmethod
    def get_upgrade_message(cls, feature_name: str) -> str:
        """Get a user-friendly upgrade message for a feature"""
        required_tier = cls.get_required_tier(feature_name)

        feature_display = feature_name.replace('_', ' ').title()

        if required_tier in (SubscriptionTier.INDIVIDUAL, SubscriptionTier.BASIC):
            return f"'{feature_display}' requires an Individual subscription. Upgrade now to unlock this feature!"
        elif required_tier == SubscriptionTier.PRO:
            return f"'{feature_display}' requires a Pro subscription. Upgrade now to unlock all features!"
        elif required_tier == SubscriptionTier.ENTERPRISE:
            return f"'{feature_display}' requires an Enterprise subscription. Contact sales for team features!"
        else:
            return f"'{feature_display}' is not available with your current subscription."

    @classmethod
    def get_available_features_for_tier(cls, tier: SubscriptionTier) -> dict:
        """
        Get all features available for a specific tier.

        Returns a dictionary with feature categories.
        """
        features = FeatureAccess.for_tier(tier)

        return {
            'core': {
                'basic_export': features.basic_export,
                'subtitle_generation': features.subtitle_generation,
                'single_video_project': features.single_video_project,
                'basic_tts_voices': features.basic_tts_voices,
            },
            'basic': {
                'multi_video_projects': features.multi_video_projects,
                'custom_fonts': features.custom_fonts,
                'basic_bgm': features.basic_bgm,
                'export_720p': features.export_720p,
                'export_1080p': features.export_1080p,
            },
            'pro': {
                'advanced_tts_voices': features.advanced_tts_voices,
                'multiple_bgm_tracks': features.multiple_bgm_tracks,
                'export_4k': features.export_4k,
                'batch_export': features.batch_export,
                'custom_subtitle_styles': features.custom_subtitle_styles,
                'cross_video_segments': features.cross_video_segments,
                'priority_support': features.priority_support,
            },
            'limits': {
                'max_videos_per_project': features.max_videos_per_project,
                'max_segments_per_video': features.max_segments_per_video,
                'max_export_duration_minutes': features.max_export_duration_minutes,
                'max_bgm_tracks': features.max_bgm_tracks,
            }
        }


def feature_required(feature_name: str, raise_error: bool = True):
    """
    Decorator to require a feature for a function.

    Args:
        feature_name: Name of the required feature
        raise_error: If True, raise FeatureGateError. If False, return None.

    Usage:
        @feature_required('multiple_bgm_tracks')
        async def add_bgm_track(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            if not FeatureGate.has_feature(feature_name):
                required_tier = FeatureGate.get_required_tier(feature_name)
                message = FeatureGate.get_upgrade_message(feature_name)

                if raise_error:
                    raise FeatureGateError(
                        feature=feature_name,
                        required_tier=required_tier.value if required_tier else 'unknown',
                        message=message
                    )
                else:
                    logger.warning(f"Feature '{feature_name}' not available: {message}")
                    return None

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            if not FeatureGate.has_feature(feature_name):
                required_tier = FeatureGate.get_required_tier(feature_name)
                message = FeatureGate.get_upgrade_message(feature_name)

                if raise_error:
                    raise FeatureGateError(
                        feature=feature_name,
                        required_tier=required_tier.value if required_tier else 'unknown',
                        message=message
                    )
                else:
                    logger.warning(f"Feature '{feature_name}' not available: {message}")
                    return None

            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def limit_check(limit_name: str, count_getter: Callable[..., int]):
    """
    Decorator to check a limit before executing a function.

    Args:
        limit_name: Name of the limit to check
        count_getter: Function to get current count from args

    Usage:
        @limit_check('max_bgm_tracks', lambda self: len(self.project.bgm_tracks))
        def add_bgm_track(self, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            current_count = count_getter(*args, **kwargs)
            can_proceed, error_msg = FeatureGate.check_limit(limit_name, current_count)

            if not can_proceed:
                raise FeatureGateError(
                    feature=limit_name,
                    required_tier='higher',
                    message=error_msg
                )

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            current_count = count_getter(*args, **kwargs)
            can_proceed, error_msg = FeatureGate.check_limit(limit_name, current_count)

            if not can_proceed:
                raise FeatureGateError(
                    feature=limit_name,
                    required_tier='higher',
                    message=error_msg
                )

            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Convenience functions for common checks

def can_add_video(project) -> Tuple[bool, Optional[str]]:
    """Check if user can add another video to project"""
    current_count = len(project.videos) if hasattr(project, 'videos') else 0
    return FeatureGate.check_limit('max_videos_per_project', current_count)


def can_add_segment(video) -> Tuple[bool, Optional[str]]:
    """Check if user can add another segment to video"""
    current_count = len(video.timeline.segments) if hasattr(video, 'timeline') else 0
    return FeatureGate.check_limit('max_segments_per_video', current_count)


def can_add_bgm_track(project) -> Tuple[bool, Optional[str]]:
    """Check if user can add another BGM track"""
    current_count = len(project.bgm_tracks) if hasattr(project, 'bgm_tracks') else 0
    return FeatureGate.check_limit('max_bgm_tracks', current_count)


def can_export_duration(duration_minutes: float) -> Tuple[bool, Optional[str]]:
    """Check if user can export a video of given duration"""
    features = FeatureGate.get_features()
    max_duration = features.max_export_duration_minutes

    if duration_minutes > max_duration:
        return False, f"Export duration ({duration_minutes:.1f} min) exceeds limit ({max_duration} min). Upgrade to export longer videos."
    return True, None


def can_export_resolution(width: int, height: int) -> Tuple[bool, Optional[str]]:
    """Check if user can export at given resolution"""
    features = FeatureGate.get_features()

    # 4K check (3840x2160 or higher)
    if width >= 3840 or height >= 2160:
        if not features.export_4k:
            return False, "4K export requires Pro subscription. Upgrade to export in 4K."
        return True, None

    # 1080p check
    if width >= 1920 or height >= 1080:
        if not features.export_1080p:
            return False, "1080p export requires Basic subscription. Upgrade to export in Full HD."
        return True, None

    # 720p and below - always allowed
    return True, None
