"""
Currency Detection and Pricing Configuration for TermiVoxed

Handles multi-currency pricing with:
- India (INR) via Razorpay - 2% fee
- International (USD) via Stripe - 2.9% + $0.30 fee

Pricing Strategy: Penetration pricing to gain market share
- No lifetime plans (recurring revenue is SaaS lifeline)
- Clear value differentiation between tiers
- GST inclusive for India
"""

import os
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any
from datetime import datetime

import aiohttp

# Import SubscriptionTier and FeatureAccess from models for consistency
# FeatureAccess is the single source of truth for tier limits
from subscription.models import SubscriptionTier, FeatureAccess

logger = logging.getLogger(__name__)


class Currency(str, Enum):
    """Supported currencies"""
    INR = "INR"
    USD = "USD"


class BillingPeriod(str, Enum):
    """Billing period options"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


# DEPRECATED: Use SubscriptionTier from models.py instead
# Keeping for backward compatibility
class SubscriptionPlan(str, Enum):
    """Subscription plan types - DEPRECATED, use SubscriptionTier instead"""
    FREE_TRIAL = "free_trial"
    INDIVIDUAL = "individual"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    LIFETIME = "lifetime"  # Added for consistency


@dataclass
class PlanPricing:
    """Pricing for a specific plan"""
    monthly: float
    quarterly: float
    yearly: float
    monthly_savings_percent: int = 0
    quarterly_savings_percent: int = 0
    yearly_savings_percent: int = 0

    def get_price(self, period: BillingPeriod) -> float:
        """Get price for billing period"""
        if period == BillingPeriod.MONTHLY:
            return self.monthly
        elif period == BillingPeriod.QUARTERLY:
            return self.quarterly
        return self.yearly

    def get_monthly_equivalent(self, period: BillingPeriod) -> float:
        """Get monthly equivalent price"""
        if period == BillingPeriod.MONTHLY:
            return self.monthly
        elif period == BillingPeriod.QUARTERLY:
            return self.quarterly / 3
        return self.yearly / 12

    def get_savings_percent(self, period: BillingPeriod) -> int:
        """Get savings percentage for billing period"""
        if period == BillingPeriod.MONTHLY:
            return self.monthly_savings_percent
        elif period == BillingPeriod.QUARTERLY:
            return self.quarterly_savings_percent
        return self.yearly_savings_percent


@dataclass
class PricingConfig:
    """Complete pricing configuration for a currency"""
    currency: Currency
    currency_symbol: str
    individual: PlanPricing
    pro: PlanPricing
    enterprise: PlanPricing
    enterprise_per_seat: float
    processor: str
    processor_fee_percent: float
    processor_fixed_fee: float
    gst_included: bool
    gst_percent: float = 18.0

    def get_plan_pricing(self, plan: SubscriptionPlan) -> Optional[PlanPricing]:
        """Get pricing for a specific plan"""
        if plan == SubscriptionPlan.INDIVIDUAL:
            return self.individual
        elif plan == SubscriptionPlan.PRO:
            return self.pro
        elif plan == SubscriptionPlan.ENTERPRISE:
            return self.enterprise
        return None


# ============================================================================
# PRICING CONFIGURATION
# ============================================================================

# India Pricing (INR - All prices GST inclusive)
PRICING_INR = PricingConfig(
    currency=Currency.INR,
    currency_symbol="₹",
    individual=PlanPricing(
        monthly=149,
        quarterly=399,
        yearly=1499,
        quarterly_savings_percent=11,
        yearly_savings_percent=16,
    ),
    pro=PlanPricing(
        monthly=299,
        quarterly=799,
        yearly=2999,
        quarterly_savings_percent=11,
        yearly_savings_percent=16,
    ),
    enterprise=PlanPricing(
        monthly=4999,
        quarterly=0,  # No quarterly for enterprise
        yearly=49999,
        yearly_savings_percent=17,
    ),
    enterprise_per_seat=99,
    processor="razorpay",
    processor_fee_percent=2.0,
    processor_fixed_fee=0,
    gst_included=True,
    gst_percent=18.0,
)

# International Pricing (USD)
PRICING_USD = PricingConfig(
    currency=Currency.USD,
    currency_symbol="$",
    individual=PlanPricing(
        monthly=4.99,
        quarterly=12.99,
        yearly=49.99,
        quarterly_savings_percent=13,
        yearly_savings_percent=16,
    ),
    pro=PlanPricing(
        monthly=9.99,
        quarterly=26.99,
        yearly=99.99,
        quarterly_savings_percent=10,
        yearly_savings_percent=17,
    ),
    enterprise=PlanPricing(
        monthly=59,
        quarterly=0,  # No quarterly for enterprise
        yearly=599,
        yearly_savings_percent=15,
    ),
    enterprise_per_seat=2.99,
    processor="stripe",
    processor_fee_percent=2.9,
    processor_fixed_fee=0.30,
    gst_included=False,
    gst_percent=0,
)

# Pricing lookup
PRICING: Dict[Currency, PricingConfig] = {
    Currency.INR: PRICING_INR,
    Currency.USD: PRICING_USD,
}

def _build_tier_limits_from_features(tier: SubscriptionTier) -> Dict[str, Any]:
    """
    Build tier limits dict from FeatureAccess (single source of truth).

    The limits are derived from subscription/models.py FeatureAccess to ensure
    consistency across the entire application.
    """
    features = FeatureAccess.for_tier(tier)

    # Build feature list from boolean flags
    feature_list = []
    if features.basic_export:
        feature_list.append("basic_export")
    if features.subtitle_generation:
        feature_list.append("subtitle_generation")
    if features.basic_tts_voices:
        feature_list.append("basic_tts_voices")
    if features.export_720p:
        feature_list.append("export_720p")
    if features.export_1080p:
        feature_list.append("export_1080p")
    if features.multi_video_projects:
        feature_list.append("multi_video_projects")
    if features.custom_fonts:
        feature_list.append("custom_fonts")
    if features.basic_bgm:
        feature_list.append("basic_bgm")
    if features.advanced_tts_voices:
        feature_list.append("advanced_tts_voices")
    if features.multiple_bgm_tracks:
        feature_list.append("multiple_bgm_tracks")
    if features.export_4k:
        feature_list.append("export_4k")
    if features.batch_export:
        feature_list.append("batch_export")
    if features.custom_subtitle_styles:
        feature_list.append("custom_subtitle_styles")
    if features.cross_video_segments:
        feature_list.append("cross_video_segments")
    if features.priority_support:
        feature_list.append("priority_support")

    # Enterprise-specific features
    if tier == SubscriptionTier.ENTERPRISE:
        feature_list.extend(["sso", "team_management", "api_access", "custom_branding"])

    # Max projects calculated from tier (not in FeatureAccess yet)
    max_projects_map = {
        SubscriptionTier.FREE_TRIAL: 3,
        SubscriptionTier.INDIVIDUAL: 10,
        SubscriptionTier.PRO: 50,
        SubscriptionTier.LIFETIME: 50,
        SubscriptionTier.ENTERPRISE: 999,
        SubscriptionTier.EXPIRED: 1,
    }

    return {
        "exports_per_month": features.max_exports_per_month,
        "max_video_duration_minutes": features.max_export_duration_minutes,
        "max_projects": max_projects_map.get(tier, 3),
        "max_devices": features.max_devices,
        "tts_minutes_per_month": features.max_tts_minutes_per_month,
        "ai_generations_per_month": features.max_ai_requests_per_month,
        "max_videos_per_project": features.max_videos_per_project,
        "features": feature_list,
    }


# Feature limits by tier - derived from FeatureAccess (single source of truth)
# See subscription/models.py FeatureAccess for authoritative limit values
TIER_LIMITS: Dict[Any, Dict[str, Any]] = {
    tier: _build_tier_limits_from_features(tier)
    for tier in [
        SubscriptionTier.FREE_TRIAL,
        SubscriptionTier.INDIVIDUAL,
        SubscriptionTier.PRO,
        SubscriptionTier.LIFETIME,
        SubscriptionTier.ENTERPRISE,
        SubscriptionTier.EXPIRED,
    ]
}

# Backward compatibility: Also index by SubscriptionPlan
TIER_LIMITS[SubscriptionPlan.FREE_TRIAL] = TIER_LIMITS[SubscriptionTier.FREE_TRIAL]
TIER_LIMITS[SubscriptionPlan.INDIVIDUAL] = TIER_LIMITS[SubscriptionTier.INDIVIDUAL]
TIER_LIMITS[SubscriptionPlan.PRO] = TIER_LIMITS[SubscriptionTier.PRO]
TIER_LIMITS[SubscriptionPlan.ENTERPRISE] = TIER_LIMITS[SubscriptionTier.ENTERPRISE]
TIER_LIMITS[SubscriptionPlan.LIFETIME] = TIER_LIMITS[SubscriptionTier.LIFETIME]


# ============================================================================
# CURRENCY DETECTION
# ============================================================================

# IP Geolocation API (free tier)
GEOLOCATION_API_URL = "http://ip-api.com/json/{ip}?fields=countryCode"

# Cache for currency detection (in-memory, use Redis in production)
_currency_cache: Dict[str, Tuple[Currency, datetime]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


async def detect_user_currency(ip_address: str) -> Currency:
    """
    Detect user's preferred currency based on IP geolocation.

    Args:
        ip_address: User's IP address

    Returns:
        Currency enum (INR for India, USD for international)
    """
    # Check cache first
    if ip_address in _currency_cache:
        cached_currency, cached_at = _currency_cache[ip_address]
        if (datetime.now() - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return cached_currency

    # Default to USD
    detected_currency = Currency.USD

    try:
        # Skip geolocation for localhost/private IPs
        if ip_address in ("127.0.0.1", "localhost", "::1") or ip_address.startswith(("10.", "192.168.", "172.")):
            # Check environment override for development
            dev_currency = os.environ.get("TERMIVOXED_DEV_CURRENCY", "USD").upper()
            detected_currency = Currency.INR if dev_currency == "INR" else Currency.USD
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    GEOLOCATION_API_URL.format(ip=ip_address),
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        country_code = data.get("countryCode", "")
                        if country_code == "IN":
                            detected_currency = Currency.INR

    except Exception as e:
        logger.warning(f"Currency detection failed for {ip_address}: {e}")

    # Cache the result
    _currency_cache[ip_address] = (detected_currency, datetime.now())

    return detected_currency


def get_pricing_for_currency(currency: Currency) -> PricingConfig:
    """Get pricing configuration for a currency"""
    return PRICING.get(currency, PRICING_USD)


def format_price(amount: float, currency: Currency) -> str:
    """Format price with currency symbol"""
    config = get_pricing_for_currency(currency)
    if currency == Currency.INR:
        return f"{config.currency_symbol}{amount:,.0f}"
    return f"{config.currency_symbol}{amount:.2f}"


def format_price_per_day(monthly_price: float, currency: Currency) -> str:
    """Format daily equivalent price (for marketing)"""
    daily = monthly_price / 30
    config = get_pricing_for_currency(currency)
    if currency == Currency.INR:
        return f"{config.currency_symbol}{daily:.0f}"
    return f"{config.currency_symbol}{daily:.2f}"


# ============================================================================
# REVENUE CALCULATION
# ============================================================================

def calculate_net_revenue(price: float, currency: Currency) -> Tuple[float, float, float]:
    """
    Calculate net revenue after payment processor fees.

    Args:
        price: Gross price
        currency: Currency for fee calculation

    Returns:
        Tuple of (gross, fee, net)
    """
    config = get_pricing_for_currency(currency)
    fee = (price * config.processor_fee_percent / 100) + config.processor_fixed_fee
    return (price, round(fee, 2), round(price - fee, 2))


def calculate_gst_breakdown(price: float, currency: Currency) -> Tuple[float, float, float]:
    """
    Calculate GST breakdown for India (prices are GST-inclusive).

    Args:
        price: GST-inclusive price
        currency: Currency

    Returns:
        Tuple of (base_price, gst_amount, total)
    """
    config = get_pricing_for_currency(currency)

    if not config.gst_included or config.gst_percent == 0:
        return (price, 0, price)

    # Extract base from GST-inclusive price
    base_price = price / (1 + config.gst_percent / 100)
    gst_amount = price - base_price

    return (round(base_price, 2), round(gst_amount, 2), price)


# ============================================================================
# PRICE ID MAPPING (for Razorpay/Stripe)
# ============================================================================

# Environment-based price IDs (configure in .env or Firebase config)
def get_price_ids() -> Dict[str, Dict[str, str]]:
    """
    Get payment processor price IDs.

    In production, these should come from environment variables or
    a configuration system like Firebase Remote Config.
    """
    return {
        "razorpay": {
            # LIVE MODE - Production Plan IDs
            "individual_monthly": os.environ.get("RAZORPAY_PRICE_INDIVIDUAL_MONTHLY", "plan_RyKRBwY9cpeDxq"),
            "individual_quarterly": os.environ.get("RAZORPAY_PRICE_INDIVIDUAL_QUARTERLY", ""),  # Not available
            "individual_yearly": os.environ.get("RAZORPAY_PRICE_INDIVIDUAL_YEARLY", "plan_RyKSNpXx4eJQKq"),
            "pro_monthly": os.environ.get("RAZORPAY_PRICE_PRO_MONTHLY", "plan_RyKT7aXL8NDQPF"),
            "pro_quarterly": os.environ.get("RAZORPAY_PRICE_PRO_QUARTERLY", ""),  # Not available
            "pro_yearly": os.environ.get("RAZORPAY_PRICE_PRO_YEARLY", "plan_RyKTcZY7W7WtqL"),
            "enterprise_monthly": os.environ.get("RAZORPAY_PRICE_ENTERPRISE_MONTHLY", ""),  # Contact sales
            "enterprise_yearly": os.environ.get("RAZORPAY_PRICE_ENTERPRISE_YEARLY", ""),  # Contact sales
        },
        "stripe": {
            "individual_monthly": os.environ.get("STRIPE_PRICE_INDIVIDUAL_MONTHLY", "price_test_individual_monthly"),
            "individual_quarterly": os.environ.get("STRIPE_PRICE_INDIVIDUAL_QUARTERLY", "price_test_individual_quarterly"),
            "individual_yearly": os.environ.get("STRIPE_PRICE_INDIVIDUAL_YEARLY", "price_test_individual_yearly"),
            "pro_monthly": os.environ.get("STRIPE_PRICE_PRO_MONTHLY", "price_test_pro_monthly"),
            "pro_quarterly": os.environ.get("STRIPE_PRICE_PRO_QUARTERLY", "price_test_pro_quarterly"),
            "pro_yearly": os.environ.get("STRIPE_PRICE_PRO_YEARLY", "price_test_pro_yearly"),
            "enterprise_monthly": os.environ.get("STRIPE_PRICE_ENTERPRISE_MONTHLY", "price_test_enterprise_monthly"),
            "enterprise_yearly": os.environ.get("STRIPE_PRICE_ENTERPRISE_YEARLY", "price_test_enterprise_yearly"),
        },
    }


def get_price_id(plan: SubscriptionPlan, period: BillingPeriod, currency: Currency) -> str:
    """
    Get the payment processor price ID for a plan/period/currency combination.

    Args:
        plan: Subscription plan
        period: Billing period
        currency: Currency (determines processor)

    Returns:
        Price ID string for Razorpay or Stripe
    """
    if plan == SubscriptionPlan.FREE_TRIAL:
        return ""  # No price ID for free trial

    processor = "razorpay" if currency == Currency.INR else "stripe"
    price_key = f"{plan.value}_{period.value}"

    price_ids = get_price_ids()
    return price_ids.get(processor, {}).get(price_key, "")


# ============================================================================
# API RESPONSE HELPERS
# ============================================================================

def get_pricing_display_data(currency: Currency) -> Dict[str, Any]:
    """
    Get pricing data formatted for frontend display.

    Args:
        currency: User's currency

    Returns:
        Dict with all pricing information for display
    """
    config = get_pricing_for_currency(currency)

    return {
        "currency": currency.value,
        "currency_symbol": config.currency_symbol,
        "processor": config.processor,
        "gst_included": config.gst_included,
        "gst_percent": config.gst_percent if config.gst_included else 0,
        "plans": {
            "free_trial": {
                "name": "Free Trial",
                "description": "Try all Pro features free for 7 days",
                "price": 0,
                "period": "7 days",
                "limits": TIER_LIMITS[SubscriptionPlan.FREE_TRIAL],
            },
            "individual": {
                "name": "Individual",
                "description": "Essential features for content creators",
                "prices": {
                    "monthly": {
                        "price": config.individual.monthly,
                        "formatted": format_price(config.individual.monthly, currency),
                        "per_day": format_price_per_day(config.individual.monthly, currency),
                        "savings_percent": config.individual.monthly_savings_percent,
                    },
                    "quarterly": {
                        "price": config.individual.quarterly,
                        "formatted": format_price(config.individual.quarterly, currency),
                        "monthly_equivalent": format_price(config.individual.get_monthly_equivalent(BillingPeriod.QUARTERLY), currency),
                        "savings_percent": config.individual.quarterly_savings_percent,
                    },
                    "yearly": {
                        "price": config.individual.yearly,
                        "formatted": format_price(config.individual.yearly, currency),
                        "monthly_equivalent": format_price(config.individual.get_monthly_equivalent(BillingPeriod.YEARLY), currency),
                        "savings_percent": config.individual.yearly_savings_percent,
                    },
                },
                "limits": TIER_LIMITS[SubscriptionPlan.INDIVIDUAL],
            },
            "pro": {
                "name": "Pro",
                "description": "All features for professional creators",
                "recommended": True,
                "prices": {
                    "monthly": {
                        "price": config.pro.monthly,
                        "formatted": format_price(config.pro.monthly, currency),
                        "per_day": format_price_per_day(config.pro.monthly, currency),
                        "savings_percent": config.pro.monthly_savings_percent,
                    },
                    "quarterly": {
                        "price": config.pro.quarterly,
                        "formatted": format_price(config.pro.quarterly, currency),
                        "monthly_equivalent": format_price(config.pro.get_monthly_equivalent(BillingPeriod.QUARTERLY), currency),
                        "savings_percent": config.pro.quarterly_savings_percent,
                    },
                    "yearly": {
                        "price": config.pro.yearly,
                        "formatted": format_price(config.pro.yearly, currency),
                        "monthly_equivalent": format_price(config.pro.get_monthly_equivalent(BillingPeriod.YEARLY), currency),
                        "savings_percent": config.pro.yearly_savings_percent,
                    },
                },
                "limits": TIER_LIMITS[SubscriptionPlan.PRO],
            },
            "enterprise": {
                "name": "Enterprise",
                "description": "For teams and businesses",
                "contact_sales": True,
                "per_seat_price": config.enterprise_per_seat,
                "per_seat_formatted": format_price(config.enterprise_per_seat, currency),
                "prices": {
                    "monthly": {
                        "price": config.enterprise.monthly,
                        "formatted": format_price(config.enterprise.monthly, currency),
                        "savings_percent": 0,
                    },
                    "yearly": {
                        "price": config.enterprise.yearly,
                        "formatted": format_price(config.enterprise.yearly, currency),
                        "monthly_equivalent": format_price(config.enterprise.get_monthly_equivalent(BillingPeriod.YEARLY), currency),
                        "savings_percent": config.enterprise.yearly_savings_percent,
                    },
                },
                "limits": TIER_LIMITS[SubscriptionPlan.ENTERPRISE],
            },
        },
    }
