"""
Payment API Routes for TermiVoxed

Handles payment processing with:
- Razorpay for India (INR)
- Stripe for International (USD)

Includes:
- Subscription creation
- Payment webhooks
- Invoice generation
- Subscription management
"""

import os
import sys
import hmac
import hashlib
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request, status, Header
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from subscription.invoice_generator import get_invoice_generator
from utils.logger import logger

from web_ui.api.middleware.auth import get_current_user, AuthenticatedUser
from subscription.currency_handler import (
    Currency,
    BillingPeriod,
    SubscriptionPlan,
    detect_user_currency,
    get_pricing_for_currency,
    get_pricing_display_data,
    get_price_id,
    calculate_gst_breakdown,
)

router = APIRouter()

# In-memory cache for webhook idempotency (use Redis in production)
# Stores event_id -> processing status to prevent duplicate processing
_processed_webhooks: dict = {}
_WEBHOOK_CACHE_SIZE = 1000  # Max events to keep in memory
_WEBHOOK_CACHE_TTL_SECONDS = 86400  # 24 hours


async def _check_webhook_idempotency(event_id: str, processor: str) -> bool:
    """
    Check if webhook event has already been processed.
    Returns True if this is a new event, False if already processed.

    This prevents duplicate processing when webhooks are retried.
    """
    if not event_id:
        return True  # No event ID, allow processing but log warning

    cache_key = f"{processor}:{event_id}"

    # Check in-memory cache first
    if cache_key in _processed_webhooks:
        cached_time = _processed_webhooks[cache_key]
        # Check if still within TTL
        if (datetime.now() - cached_time).total_seconds() < _WEBHOOK_CACHE_TTL_SECONDS:
            logger.warning(f"Duplicate webhook detected (cache): {cache_key}")
            return False

    # Check Firestore for persistence across restarts
    try:
        from firebase_admin import firestore
        db = firestore.client()

        webhook_ref = db.collection("processed_webhooks").document(cache_key)
        webhook_doc = webhook_ref.get()

        if webhook_doc.exists:
            logger.warning(f"Duplicate webhook detected (Firestore): {cache_key}")
            # Update in-memory cache
            _processed_webhooks[cache_key] = datetime.now()
            return False

    except Exception as e:
        logger.error(f"Failed to check webhook idempotency in Firestore: {e}")
        # Continue processing if Firestore check fails, in-memory check already passed

    return True


async def _mark_webhook_processed(event_id: str, processor: str, event_type: str):
    """
    Mark a webhook event as processed.
    Stores in both memory and Firestore for durability.
    """
    if not event_id:
        return

    cache_key = f"{processor}:{event_id}"

    # Add to in-memory cache
    _processed_webhooks[cache_key] = datetime.now()

    # Cleanup old entries if cache is too large
    if len(_processed_webhooks) > _WEBHOOK_CACHE_SIZE:
        # Remove oldest entries
        oldest_keys = sorted(
            _processed_webhooks.keys(),
            key=lambda k: _processed_webhooks[k]
        )[:_WEBHOOK_CACHE_SIZE // 2]
        for key in oldest_keys:
            del _processed_webhooks[key]

    # Store in Firestore for persistence
    try:
        from firebase_admin import firestore
        db = firestore.client()

        webhook_ref = db.collection("processed_webhooks").document(cache_key)
        webhook_ref.set({
            "event_id": event_id,
            "processor": processor,
            "event_type": event_type,
            "processed_at": datetime.now().isoformat(),
            # Firestore TTL field - document will be auto-deleted after 7 days
            "expire_at": datetime.now() + timedelta(days=7),
        })

    except Exception as e:
        logger.error(f"Failed to mark webhook as processed in Firestore: {e}")


# ============================================================================
# Configuration
# ============================================================================

# Razorpay configuration
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

# Stripe configuration
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

# App URLs
APP_SUCCESS_URL = os.environ.get("APP_URL", "http://localhost:5173") + "/payment/success"
APP_CANCEL_URL = os.environ.get("APP_URL", "http://localhost:5173") + "/payment/cancel"


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSubscriptionRequest(BaseModel):
    """Request to create a new subscription"""
    plan: str = Field(..., description="Plan: individual, pro, enterprise")
    period: str = Field(..., description="Period: monthly, quarterly, yearly")
    currency: Optional[str] = Field(None, description="Currency override: INR or USD")


class CreateSubscriptionResponse(BaseModel):
    """Response with payment session details"""
    processor: str
    subscription_id: Optional[str] = None
    checkout_url: Optional[str] = None
    order_id: Optional[str] = None
    key_id: Optional[str] = None  # For Razorpay frontend
    amount: float
    currency: str
    plan: str
    period: str


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription"""
    reason: Optional[str] = None
    immediate: bool = Field(False, description="Cancel immediately vs at period end")


class UpdatePaymentMethodRequest(BaseModel):
    """Request to update payment method"""
    return_url: str = Field(..., description="URL to redirect after update")


class PricingResponse(BaseModel):
    """Pricing information response"""
    currency: str
    currency_symbol: str
    processor: str
    gst_included: bool
    gst_percent: float
    plans: dict


# ============================================================================
# Helper Functions
# ============================================================================

def get_client_ip(request: Request) -> str:
    """Get client IP from request, handling proxies"""
    # Check X-Forwarded-For header (for proxied requests)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "127.0.0.1"


async def _get_razorpay_client():
    """Get Razorpay client instance"""
    try:
        import razorpay
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            return None
        return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    except ImportError:
        return None


async def _get_stripe():
    """Get Stripe module with configured API key"""
    try:
        import stripe
        if not STRIPE_SECRET_KEY:
            return None
        stripe.api_key = STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        return None


async def _update_user_subscription(
    user_id: str,
    plan: SubscriptionPlan,
    period: BillingPeriod,
    processor: str,
    subscription_id: str,
    status: str = "active",
    period_end: Optional[datetime] = None
):
    """Update user subscription in Firestore"""
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_ref = db.collection("users").document(user_id)

        # Calculate period end if not provided
        if period_end is None:
            if period == BillingPeriod.MONTHLY:
                period_end = datetime.now() + timedelta(days=30)
            elif period == BillingPeriod.QUARTERLY:
                period_end = datetime.now() + timedelta(days=90)
            else:
                period_end = datetime.now() + timedelta(days=365)

        subscription_data = {
            "subscription": {
                "tier": plan.value,
                "status": status,
                "processor": processor,
                "subscriptionId": subscription_id,
                "periodEnd": period_end.isoformat(),
                "updatedAt": datetime.now().isoformat(),
            }
        }

        user_ref.update(subscription_data)
        return True

    except Exception as e:
        print(f"Error updating subscription: {e}")
        return False


# ============================================================================
# Pricing Endpoints
# ============================================================================

@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(request: Request):
    """
    Get pricing information based on user's location.

    Currency is auto-detected from IP:
    - India → INR (Razorpay)
    - International → USD (Stripe)
    """
    ip = get_client_ip(request)
    currency = await detect_user_currency(ip)
    pricing_data = get_pricing_display_data(currency)

    return PricingResponse(**pricing_data)


@router.get("/pricing/{currency_code}")
async def get_pricing_by_currency(currency_code: str):
    """Get pricing for a specific currency"""
    try:
        currency = Currency(currency_code.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid currency: {currency_code}. Supported: INR, USD"
        )

    return get_pricing_display_data(currency)


# ============================================================================
# Subscription Endpoints
# ============================================================================

@router.post("/subscriptions/create", response_model=CreateSubscriptionResponse)
async def create_subscription(
    request_data: CreateSubscriptionRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Create a new subscription.

    Returns payment session URL for Stripe or order details for Razorpay.
    """
    # Parse plan and period
    try:
        plan = SubscriptionPlan(request_data.plan.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {request_data.plan}"
        )

    try:
        period = BillingPeriod(request_data.period.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period: {request_data.period}"
        )

    if plan == SubscriptionPlan.FREE_TRIAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free trial doesn't require payment"
        )

    # Determine currency
    if request_data.currency:
        try:
            currency = Currency(request_data.currency.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid currency: {request_data.currency}"
            )
    else:
        ip = get_client_ip(request)
        currency = await detect_user_currency(ip)

    pricing_config = get_pricing_for_currency(currency)
    plan_pricing = pricing_config.get_plan_pricing(plan)

    if not plan_pricing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {plan.value}"
        )

    price = plan_pricing.get_price(period)
    price_id = get_price_id(plan, period, currency)

    # Route to appropriate payment processor
    if currency == Currency.INR:
        return await _create_razorpay_subscription(user, plan, period, price, price_id)
    else:
        return await _create_stripe_subscription(user, plan, period, price, price_id, currency)


async def _create_razorpay_subscription(
    user: AuthenticatedUser,
    plan: SubscriptionPlan,
    period: BillingPeriod,
    price: float,
    price_id: str
) -> CreateSubscriptionResponse:
    """Create Razorpay subscription"""
    client = await _get_razorpay_client()

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay not configured. Please contact support."
        )

    try:
        # Create subscription
        subscription_data = {
            "plan_id": price_id,
            "customer_notify": 1,
            "quantity": 1,
            "total_count": 12 if period == BillingPeriod.YEARLY else (4 if period == BillingPeriod.QUARTERLY else 12),
            "notes": {
                "user_id": user.uid,
                "email": user.email,
                "plan": plan.value,
                "period": period.value,
            }
        }

        subscription = client.subscription.create(subscription_data)

        return CreateSubscriptionResponse(
            processor="razorpay",
            subscription_id=subscription["id"],
            order_id=subscription.get("short_url"),  # Razorpay provides a short URL
            key_id=RAZORPAY_KEY_ID,
            amount=price,
            currency="INR",
            plan=plan.value,
            period=period.value,
        )

    except Exception as e:
        print(f"Razorpay error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subscription. Please try again."
        )


async def _create_stripe_subscription(
    user: AuthenticatedUser,
    plan: SubscriptionPlan,
    period: BillingPeriod,
    price: float,
    price_id: str,
    currency: Currency
) -> CreateSubscriptionResponse:
    """Create Stripe checkout session for subscription"""
    stripe = await _get_stripe()

    if stripe is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured. Please contact support."
        )

    try:
        # Create checkout session
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=user.email,
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            success_url=APP_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=APP_CANCEL_URL,
            metadata={
                "user_id": user.uid,
                "plan": plan.value,
                "period": period.value,
            },
            subscription_data={
                "metadata": {
                    "user_id": user.uid,
                    "plan": plan.value,
                    "period": period.value,
                }
            }
        )

        return CreateSubscriptionResponse(
            processor="stripe",
            subscription_id=session.id,
            checkout_url=session.url,
            amount=price,
            currency=currency.value,
            plan=plan.value,
            period=period.value,
        )

    except Exception as e:
        print(f"Stripe error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session. Please try again."
        )


@router.post("/subscriptions/cancel")
async def cancel_subscription(
    request_data: CancelSubscriptionRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Cancel the current subscription"""
    # Get user's current subscription from Firestore
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_doc = db.collection("users").document(user.uid).get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        subscription = user_data.get("subscription", {})
        processor = subscription.get("processor")
        subscription_id = subscription.get("subscriptionId")

        if not subscription_id:
            raise HTTPException(status_code=400, detail="No active subscription")

        # Cancel with appropriate processor
        if processor == "razorpay":
            client = await _get_razorpay_client()
            if client:
                client.subscription.cancel(subscription_id)
        elif processor == "stripe":
            stripe = await _get_stripe()
            if stripe:
                if request_data.immediate:
                    stripe.Subscription.delete(subscription_id)
                else:
                    stripe.Subscription.modify(
                        subscription_id,
                        cancel_at_period_end=True
                    )

        # Update user record
        new_status = "cancelled" if request_data.immediate else "cancelling"
        await _update_user_subscription(
            user.uid,
            SubscriptionPlan(subscription.get("tier", "free_trial")),
            BillingPeriod.MONTHLY,
            processor,
            subscription_id,
            status=new_status
        )

        return {
            "message": "Subscription cancelled successfully",
            "immediate": request_data.immediate,
            "status": new_status
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Cancel subscription error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@router.get("/subscriptions/current")
async def get_current_subscription(user: AuthenticatedUser = Depends(get_current_user)):
    """Get current subscription details"""
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_doc = db.collection("users").document(user.uid).get()

        if not user_doc.exists:
            return {"subscription": None}

        user_data = user_doc.to_dict()
        subscription = user_data.get("subscription", {})

        return {
            "subscription": {
                "tier": subscription.get("tier", "free_trial"),
                "status": subscription.get("status", "trial"),
                "processor": subscription.get("processor"),
                "periodEnd": subscription.get("periodEnd"),
                "cancelAtPeriodEnd": subscription.get("cancelAtPeriodEnd", False),
            }
        }

    except Exception as e:
        print(f"Get subscription error: {e}")
        return {"subscription": None}


# ============================================================================
# Webhook Endpoints
# ============================================================================

@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature")
):
    """Handle Razorpay webhook events with idempotency protection"""
    if not RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook not configured")

    body = await request.body()

    # Verify signature
    expected_signature = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_razorpay_signature or ""):
        raise HTTPException(status_code=400, detail="Invalid signature")

    event = json.loads(body)
    event_type = event.get("event")

    # Extract event ID for idempotency - Razorpay uses account_id + entity.id
    event_id = None
    payload = event.get("payload", {})
    if payload.get("payment", {}).get("entity", {}).get("id"):
        event_id = payload["payment"]["entity"]["id"]
    elif payload.get("subscription", {}).get("entity", {}).get("id"):
        event_id = f"{event_type}:{payload['subscription']['entity']['id']}"

    # Check idempotency - skip if already processed
    is_new = await _check_webhook_idempotency(event_id, "razorpay")
    if not is_new:
        logger.info(f"Skipping duplicate Razorpay webhook: {event_id}")
        return {"status": "ok", "message": "duplicate_ignored"}

    # Process the event
    try:
        if event_type == "subscription.activated":
            await _handle_razorpay_subscription_activated(event)
        elif event_type == "subscription.charged":
            await _handle_razorpay_payment(event)
        elif event_type == "subscription.cancelled":
            await _handle_razorpay_cancellation(event)
        elif event_type == "payment.failed":
            await _handle_razorpay_payment_failed(event)

        # Mark as processed after successful handling
        await _mark_webhook_processed(event_id, "razorpay", event_type)

    except Exception as e:
        logger.error(f"Razorpay webhook processing error: {e}")
        # Don't mark as processed so it can be retried
        raise

    return {"status": "ok"}


async def _handle_razorpay_subscription_activated(event: dict):
    """Handle subscription activation"""
    payload = event.get("payload", {}).get("subscription", {}).get("entity", {})
    notes = payload.get("notes", {})
    user_id = notes.get("user_id")

    if user_id:
        plan = SubscriptionPlan(notes.get("plan", "individual"))
        period = BillingPeriod(notes.get("period", "monthly"))

        await _update_user_subscription(
            user_id,
            plan,
            period,
            "razorpay",
            payload.get("id"),
            status="active"
        )


async def _handle_razorpay_payment(event: dict):
    """Handle successful payment - generate invoice and record payment"""
    try:
        payload = event.get("payload", {})
        payment = payload.get("payment", {}).get("entity", {})
        subscription = payload.get("subscription", {}).get("entity", {})

        notes = subscription.get("notes", {})
        user_id = notes.get("user_id")
        user_email = notes.get("email")

        if not user_id:
            logger.warning("Razorpay payment webhook missing user_id in notes")
            return

        # Payment data for invoice
        amount = payment.get("amount", 0) / 100  # Convert from paise
        payment_data = {
            "transaction_id": payment.get("id"),
            "amount": amount,
            "amount_in_cents": False,  # Already converted
            "currency": "INR",
            "plan_name": f"TermiVoxed {notes.get('plan', 'Individual').capitalize()}",
            "billing_period": notes.get("period", "monthly"),
            "payment_method": payment.get("method", "card").capitalize(),
        }

        # Customer data
        customer_data = {
            "email": user_email,
            "name": notes.get("name", user_email.split("@")[0] if user_email else "Customer"),
            "country": "India",
        }

        # Generate invoice
        invoice_generator = get_invoice_generator()
        invoice_path = invoice_generator.generate_from_payment(payment_data, customer_data)

        logger.info(f"Invoice generated for user {user_id}: {invoice_path}")

        # Store payment record in Firestore
        try:
            from firebase_admin import firestore

            db = firestore.client()
            payment_ref = db.collection("users").document(user_id).collection("payments").document()

            payment_ref.set({
                "paymentId": payment.get("id"),
                "subscriptionId": subscription.get("id"),
                "amount": amount,
                "currency": "INR",
                "status": "paid",
                "invoiceNumber": invoice_path.stem.replace("invoice_", ""),
                "invoicePath": str(invoice_path),
                "plan": notes.get("plan"),
                "period": notes.get("period"),
                "processor": "razorpay",
                "createdAt": datetime.now().isoformat(),
            })

            logger.info(f"Payment recorded for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to store payment record: {e}")

        # Send invoice email (async, don't block webhook response)
        asyncio.create_task(_send_invoice_email(user_email, invoice_path, amount, "INR"))

    except Exception as e:
        logger.error(f"Razorpay payment handler error: {e}")


async def _handle_razorpay_cancellation(event: dict):
    """Handle subscription cancellation"""
    payload = event.get("payload", {}).get("subscription", {}).get("entity", {})
    notes = payload.get("notes", {})
    user_id = notes.get("user_id")

    if user_id:
        await _update_user_subscription(
            user_id,
            SubscriptionPlan.FREE_TRIAL,
            BillingPeriod.MONTHLY,
            "razorpay",
            payload.get("id"),
            status="cancelled"
        )


async def _handle_razorpay_payment_failed(event: dict):
    """Handle failed payment - notify user and update status"""
    try:
        payload = event.get("payload", {})
        payment = payload.get("payment", {}).get("entity", {})
        subscription = payload.get("subscription", {}).get("entity", {})

        notes = subscription.get("notes", {})
        user_id = notes.get("user_id")
        user_email = notes.get("email")

        if not user_id:
            logger.warning("Razorpay failed payment webhook missing user_id")
            return

        error_reason = payment.get("error_description", "Payment declined")

        # Update subscription status to past_due
        try:
            from firebase_admin import firestore

            db = firestore.client()
            user_ref = db.collection("users").document(user_id)

            user_ref.update({
                "subscription.status": "past_due",
                "subscription.lastPaymentError": error_reason,
                "subscription.lastPaymentErrorAt": datetime.now().isoformat(),
            })

            logger.info(f"User {user_id} subscription marked as past_due")

        except Exception as e:
            logger.error(f"Failed to update subscription status: {e}")

        # Send notification email
        if user_email:
            asyncio.create_task(_send_payment_failed_email(
                user_email,
                error_reason,
                "razorpay",
                notes.get("plan", "Individual")
            ))

    except Exception as e:
        logger.error(f"Razorpay payment failed handler error: {e}")


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """Handle Stripe webhook events with idempotency protection"""
    stripe = await _get_stripe()

    if stripe is None or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook not configured")

    body = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            body,
            stripe_signature,
            STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    event_type = event["type"]
    event_id = event.get("id")  # Stripe provides unique event ID

    # Check idempotency - skip if already processed
    is_new = await _check_webhook_idempotency(event_id, "stripe")
    if not is_new:
        logger.info(f"Skipping duplicate Stripe webhook: {event_id}")
        return {"status": "ok", "message": "duplicate_ignored"}

    # Process the event
    try:
        if event_type == "checkout.session.completed":
            await _handle_stripe_checkout_completed(event["data"]["object"])
        elif event_type == "customer.subscription.updated":
            await _handle_stripe_subscription_updated(event["data"]["object"])
        elif event_type == "customer.subscription.deleted":
            await _handle_stripe_subscription_deleted(event["data"]["object"])
        elif event_type == "invoice.payment_failed":
            await _handle_stripe_payment_failed(event["data"]["object"])
        elif event_type == "invoice.paid":
            await _handle_stripe_invoice_paid(event["data"]["object"])
        elif event_type == "invoice.payment_succeeded":
            await _handle_stripe_invoice_paid(event["data"]["object"])

        # Mark as processed after successful handling
        await _mark_webhook_processed(event_id, "stripe", event_type)

    except Exception as e:
        logger.error(f"Stripe webhook processing error: {e}")
        # Don't mark as processed so it can be retried
        raise

    return {"status": "ok"}


async def _handle_stripe_checkout_completed(session: dict):
    """Handle completed checkout"""
    metadata = session.get("metadata", {})
    user_id = metadata.get("user_id")
    subscription_id = session.get("subscription")

    if user_id and subscription_id:
        plan = SubscriptionPlan(metadata.get("plan", "individual"))
        period = BillingPeriod(metadata.get("period", "monthly"))

        await _update_user_subscription(
            user_id,
            plan,
            period,
            "stripe",
            subscription_id,
            status="active"
        )


async def _handle_stripe_subscription_updated(subscription: dict):
    """Handle subscription update"""
    metadata = subscription.get("metadata", {})
    user_id = metadata.get("user_id")

    if user_id:
        status_map = {
            "active": "active",
            "past_due": "past_due",
            "canceled": "cancelled",
            "incomplete": "incomplete",
            "trialing": "trial",
        }

        await _update_user_subscription(
            user_id,
            SubscriptionPlan(metadata.get("plan", "individual")),
            BillingPeriod(metadata.get("period", "monthly")),
            "stripe",
            subscription.get("id"),
            status=status_map.get(subscription.get("status"), "active")
        )


async def _handle_stripe_subscription_deleted(subscription: dict):
    """Handle subscription deletion"""
    metadata = subscription.get("metadata", {})
    user_id = metadata.get("user_id")

    if user_id:
        await _update_user_subscription(
            user_id,
            SubscriptionPlan.FREE_TRIAL,
            BillingPeriod.MONTHLY,
            "stripe",
            subscription.get("id"),
            status="cancelled"
        )


async def _handle_stripe_invoice_paid(invoice: dict):
    """Handle successful Stripe invoice payment - generate invoice and record payment"""
    try:
        subscription_id = invoice.get("subscription")
        customer_email = invoice.get("customer_email")
        amount = invoice.get("amount_paid", 0)
        currency = invoice.get("currency", "usd").upper()

        if not subscription_id:
            logger.info("Stripe invoice.paid: No subscription, likely one-time charge")
            return

        # Get user_id from subscription metadata
        stripe = await _get_stripe()
        user_id = None
        plan = "Individual"
        period = "monthly"

        if stripe:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                metadata = subscription.get("metadata", {})
                user_id = metadata.get("user_id")
                plan = metadata.get("plan", "Individual")
                period = metadata.get("period", "monthly")
            except Exception as e:
                logger.error(f"Failed to retrieve Stripe subscription: {e}")

        if not user_id:
            logger.warning("Stripe invoice.paid webhook missing user_id in subscription metadata")
            return

        # Payment data for invoice
        payment_data = {
            "transaction_id": invoice.get("id"),
            "amount": amount,
            "amount_in_cents": True,
            "currency": currency,
            "plan_name": f"TermiVoxed {plan.capitalize()}",
            "billing_period": period,
            "payment_method": "Card",
        }

        # Customer data
        customer_data = {
            "email": customer_email,
            "name": invoice.get("customer_name") or (customer_email.split("@")[0] if customer_email else "Customer"),
            "country": "USA" if currency != "INR" else "India",
        }

        # Generate invoice
        invoice_generator = get_invoice_generator()
        invoice_path = invoice_generator.generate_from_payment(payment_data, customer_data)

        logger.info(f"Invoice generated for user {user_id}: {invoice_path}")

        # Store payment record in Firestore
        try:
            from firebase_admin import firestore

            db = firestore.client()
            payment_ref = db.collection("users").document(user_id).collection("payments").document()

            payment_ref.set({
                "paymentId": invoice.get("id"),
                "subscriptionId": subscription_id,
                "amount": amount / 100,  # Convert from cents
                "currency": currency,
                "status": "paid",
                "invoiceNumber": invoice_path.stem.replace("invoice_", ""),
                "invoicePath": str(invoice_path),
                "plan": plan,
                "period": period,
                "processor": "stripe",
                "createdAt": datetime.now().isoformat(),
            })

            logger.info(f"Payment recorded for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to store payment record: {e}")

        # Send invoice email
        if customer_email:
            asyncio.create_task(_send_invoice_email(customer_email, invoice_path, amount / 100, currency))

    except Exception as e:
        logger.error(f"Stripe invoice.paid handler error: {e}")


async def _handle_stripe_payment_failed(invoice: dict):
    """Handle failed Stripe payment - notify user and update status"""
    try:
        # Get subscription metadata
        subscription_id = invoice.get("subscription")
        customer_email = invoice.get("customer_email")

        if not subscription_id:
            logger.warning("Stripe failed payment webhook missing subscription_id")
            return

        # Try to get user_id from subscription metadata
        stripe = await _get_stripe()
        user_id = None

        if stripe:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                metadata = subscription.get("metadata", {})
                user_id = metadata.get("user_id")
                plan = metadata.get("plan", "Individual")
            except Exception as e:
                logger.error(f"Failed to retrieve Stripe subscription: {e}")
                plan = "Individual"

        error_reason = "Payment could not be processed"
        # Try to get more specific error from invoice
        if invoice.get("last_payment_error"):
            error_reason = invoice["last_payment_error"].get("message", error_reason)

        # Update subscription status
        if user_id:
            try:
                from firebase_admin import firestore

                db = firestore.client()
                user_ref = db.collection("users").document(user_id)

                user_ref.update({
                    "subscription.status": "past_due",
                    "subscription.lastPaymentError": error_reason,
                    "subscription.lastPaymentErrorAt": datetime.now().isoformat(),
                })

                logger.info(f"User {user_id} subscription marked as past_due")

            except Exception as e:
                logger.error(f"Failed to update subscription status: {e}")

        # Send notification email
        if customer_email:
            asyncio.create_task(_send_payment_failed_email(
                customer_email,
                error_reason,
                "stripe",
                plan
            ))

    except Exception as e:
        logger.error(f"Stripe payment failed handler error: {e}")


# ============================================================================
# Payment Method Management
# ============================================================================

@router.post("/payment-methods/update")
async def update_payment_method(
    request_data: UpdatePaymentMethodRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get URL to update payment method"""
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_doc = db.collection("users").document(user.uid).get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        subscription = user_doc.to_dict().get("subscription", {})
        processor = subscription.get("processor")

        if processor == "stripe":
            stripe = await _get_stripe()
            if stripe:
                # Create billing portal session
                session = stripe.billing_portal.Session.create(
                    customer=subscription.get("stripeCustomerId"),
                    return_url=request_data.return_url,
                )
                return {"url": session.url}

        elif processor == "razorpay":
            # Razorpay doesn't have a hosted portal, return instructions
            return {
                "message": "Please contact support to update your payment method",
                "email": "support@luxusbrain.com"
            }

        raise HTTPException(status_code=400, detail="No active subscription")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Update payment method error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate update link"
        )


# ============================================================================
# Session Verification
# ============================================================================

class VerifySessionRequest(BaseModel):
    """Request to verify a checkout session"""
    session_id: str = Field(..., description="Stripe checkout session ID")


@router.post("/verify-session")
async def verify_session(
    request_data: VerifySessionRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Verify a Stripe checkout session after payment.

    This is called by the frontend after redirect from Stripe checkout.
    It ensures the payment was successful and updates the user's subscription.
    """
    stripe = await _get_stripe()

    if stripe is None:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    try:
        # Retrieve the session
        session = stripe.checkout.Session.retrieve(
            request_data.session_id,
            expand=["subscription", "customer"]
        )

        # Verify the session belongs to this user
        metadata = session.get("metadata", {})
        session_user_id = metadata.get("user_id")

        if session_user_id != user.uid:
            logger.warning(f"Session verification mismatch: {session_user_id} != {user.uid}")
            raise HTTPException(status_code=403, detail="Session does not belong to this user")

        # Check payment status
        if session.payment_status != "paid":
            return {
                "verified": False,
                "status": session.payment_status,
                "message": "Payment not completed"
            }

        # Get subscription details
        subscription = session.get("subscription")
        customer = session.get("customer")

        # Store customer ID if we have one
        if customer:
            customer_id = customer.id if hasattr(customer, 'id') else customer
            try:
                from firebase_admin import firestore
                db = firestore.client()
                db.collection("users").document(user.uid).update({
                    "stripeCustomerId": customer_id
                })
            except Exception as e:
                logger.error(f"Failed to save Stripe customer ID: {e}")

        return {
            "verified": True,
            "status": "paid",
            "subscription_id": subscription.id if hasattr(subscription, 'id') else subscription,
            "plan": metadata.get("plan"),
            "period": metadata.get("period")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to verify session"
        )


# ============================================================================
# Invoice Endpoints
# ============================================================================

@router.get("/invoices")
async def list_invoices(user: AuthenticatedUser = Depends(get_current_user)):
    """List user's invoices"""
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()

        # Get invoices from payments subcollection
        invoices = []
        payments_ref = db.collection("users").document(user.uid).collection("payments")
        docs = payments_ref.order_by("createdAt", direction=firestore.Query.DESCENDING).limit(20).stream()

        for doc in docs:
            data = doc.to_dict()
            # Handle different field names from Cloud Functions vs backend webhooks
            # Cloud Functions write: amountRupees, amountPaise
            # Backend webhooks write: amount
            amount = data.get("amountRupees") or data.get("amount") or 0
            invoices.append({
                "id": doc.id,
                "amount": amount,
                "currency": data.get("currency") or "INR",
                "status": data.get("status") or "paid",
                "invoiceNumber": data.get("invoiceNumber"),
                "createdAt": data.get("createdAt"),
                "downloadUrl": data.get("invoiceUrl"),
            })

        return {"invoices": invoices}

    except Exception as e:
        print(f"List invoices error: {e}")
        return {"invoices": []}


@router.get("/invoices/{invoice_id}/download")
async def download_invoice(
    invoice_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Download a specific invoice PDF"""
    from fastapi.responses import FileResponse

    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()

        # Get the payment/invoice record
        payment_doc = db.collection("users").document(user.uid).collection("payments").document(invoice_id).get()

        if not payment_doc.exists:
            raise HTTPException(status_code=404, detail="Invoice not found")

        payment_data = payment_doc.to_dict()
        invoice_path = payment_data.get("invoicePath")

        if not invoice_path:
            raise HTTPException(status_code=404, detail="Invoice file not available")

        invoice_file = Path(invoice_path)

        if not invoice_file.exists():
            # Try to regenerate the invoice
            logger.warning(f"Invoice file missing, attempting regeneration: {invoice_path}")
            raise HTTPException(status_code=404, detail="Invoice file not found")

        return FileResponse(
            path=str(invoice_file),
            media_type="application/pdf",
            filename=f"invoice_{payment_data.get('invoiceNumber', invoice_id)}.pdf"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download invoice error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download invoice")


# ============================================================================
# Subscription Management Endpoints
# ============================================================================

@router.post("/subscriptions/resume")
async def resume_subscription(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Resume a subscription that was set to cancel at period end.

    Only works if the subscription is still active but scheduled to cancel.
    """
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_doc = db.collection("users").document(user.uid).get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        subscription = user_data.get("subscription", {})
        processor = subscription.get("processor")
        subscription_id = subscription.get("subscriptionId")
        status = subscription.get("status")

        if not subscription_id:
            raise HTTPException(status_code=400, detail="No subscription to resume")

        if status not in ["cancelling", "active"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resume subscription with status: {status}"
            )

        # Resume with appropriate processor
        if processor == "stripe":
            stripe = await _get_stripe()
            if stripe:
                # Remove cancel_at_period_end flag
                stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=False
                )

        elif processor == "razorpay":
            # Razorpay doesn't support cancel_at_period_end, so we can't resume
            # The subscription would need to be reactivated
            raise HTTPException(
                status_code=400,
                detail="Razorpay subscriptions cannot be resumed after cancellation. Please create a new subscription."
            )

        # Update user record
        db.collection("users").document(user.uid).update({
            "subscription.status": "active",
            "subscription.cancelAtPeriodEnd": False,
        })

        return {
            "message": "Subscription resumed successfully",
            "status": "active"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume subscription error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to resume subscription"
        )


@router.post("/subscriptions/retry-payment")
async def retry_payment(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Retry payment for a past_due subscription.

    Attempts to charge the customer's default payment method again.
    """
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_doc = db.collection("users").document(user.uid).get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_doc.to_dict()
        subscription = user_data.get("subscription", {})
        processor = subscription.get("processor")
        subscription_id = subscription.get("subscriptionId")
        status = subscription.get("status")

        if status != "past_due":
            raise HTTPException(
                status_code=400,
                detail="Payment retry only available for past_due subscriptions"
            )

        if processor == "stripe":
            stripe = await _get_stripe()
            if stripe:
                # Get the latest invoice and pay it
                sub = stripe.Subscription.retrieve(subscription_id)
                if sub.latest_invoice:
                    try:
                        stripe.Invoice.pay(sub.latest_invoice)
                        return {
                            "success": True,
                            "message": "Payment successful! Your subscription is now active."
                        }
                    except stripe.error.CardError as e:
                        return {
                            "success": False,
                            "message": f"Payment failed: {e.user_message}",
                            "update_payment_required": True
                        }

        elif processor == "razorpay":
            # For Razorpay, user needs to make a new payment
            return {
                "success": False,
                "message": "Please update your payment method and we'll retry automatically.",
                "update_payment_required": True
            }

        raise HTTPException(status_code=400, detail="Unable to retry payment")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retry payment error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retry payment"
        )


@router.post("/subscriptions/start-trial")
async def start_free_trial(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Start or restart a free trial for a user.

    Free trial is 7 days with limited features.
    """
    try:
        import firebase_admin
        from firebase_admin import firestore

        db = firestore.client()
        user_ref = db.collection("users").document(user.uid)
        user_doc = user_ref.get()

        # Check if user already had a trial
        if user_doc.exists:
            user_data = user_doc.to_dict()
            subscription = user_data.get("subscription", {})

            # Check if they've already used their trial
            if subscription.get("trialUsed"):
                raise HTTPException(
                    status_code=400,
                    detail="Free trial already used. Please subscribe to continue."
                )

            # Check if they have an active paid subscription
            current_tier = subscription.get("tier", "")
            if current_tier not in ["", "free_trial", "expired"]:
                raise HTTPException(
                    status_code=400,
                    detail="You already have an active subscription"
                )

        # Start the trial
        trial_end = datetime.now() + timedelta(days=7)

        user_ref.set({
            "subscription": {
                "tier": "free_trial",
                "status": "trial",
                "trialStart": datetime.now().isoformat(),
                "trialEnd": trial_end.isoformat(),
                "periodEnd": trial_end.isoformat(),
                "trialUsed": True,
                "updatedAt": datetime.now().isoformat(),
            }
        }, merge=True)

        return {
            "message": "Free trial started!",
            "trial_ends": trial_end.isoformat(),
            "days_remaining": 7
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start trial error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to start free trial"
        )


# ============================================================================
# Email Helper Functions
# ============================================================================

async def _send_invoice_email(
    email: str,
    invoice_path: Path,
    amount: float,
    currency: str
):
    """Send invoice email to user"""
    try:
        # Use SMTP or email service
        # For now, log the action - integrate with email service in production
        logger.info(f"[EMAIL] Sending invoice to {email}: {invoice_path}")

        # Check if we have email credentials configured
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASSWORD")

        if not all([smtp_host, smtp_user, smtp_pass]):
            logger.warning("SMTP not configured, invoice email not sent")
            return

        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.application import MIMEApplication

        # Create message
        msg = MIMEMultipart()
        msg["From"] = os.environ.get("SMTP_FROM", "billing@termivoxed.com")
        msg["To"] = email
        msg["Subject"] = f"Your TermiVoxed Invoice - {currency} {amount:,.2f}"

        # Email body
        currency_symbol = "₹" if currency == "INR" else "$"
        body = f"""
Dear Customer,

Thank you for your payment of {currency_symbol}{amount:,.2f}.

Your invoice is attached to this email. You can also download it from your TermiVoxed dashboard.

If you have any questions about your invoice, please contact us at billing@termivoxed.com.

Best regards,
The TermiVoxed Team
        """
        msg.attach(MIMEText(body, "plain"))

        # Attach invoice PDF if exists
        if invoice_path.exists():
            with open(invoice_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=invoice_path.name
                )
                msg.attach(attachment)

        # Send email
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(f"Invoice email sent to {email}")

    except Exception as e:
        logger.error(f"Failed to send invoice email: {e}")


async def _send_payment_failed_email(
    email: str,
    error_reason: str,
    processor: str,
    plan: str
):
    """Send payment failed notification email"""
    try:
        logger.info(f"[EMAIL] Sending payment failed notification to {email}")

        smtp_host = os.environ.get("SMTP_HOST")
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASSWORD")

        if not all([smtp_host, smtp_user, smtp_pass]):
            logger.warning("SMTP not configured, payment failed email not sent")
            return

        import smtplib
        from email.mime.text import MIMEText

        # Create message
        msg = MIMEText(f"""
Dear Customer,

We were unable to process your payment for your TermiVoxed {plan.capitalize()} subscription.

Reason: {error_reason}

To avoid service interruption, please update your payment method:
1. Log in to your TermiVoxed account
2. Go to Settings > Subscription
3. Click "Update Payment Method"

If you continue to experience issues, please contact our support team at support@termivoxed.com.

Best regards,
The TermiVoxed Team
        """)

        msg["From"] = os.environ.get("SMTP_FROM", "billing@termivoxed.com")
        msg["To"] = email
        msg["Subject"] = "Action Required: Payment Failed for TermiVoxed"

        # Send email
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(f"Payment failed email sent to {email}")

    except Exception as e:
        logger.error(f"Failed to send payment failed email: {e}")
