"""
Phone Verification Service for TermiVoxed

Provides phone number verification to prevent:
- Trial abuse (multiple free trials with same phone)
- Bot signups
- Fraudulent accounts

Supports multiple providers:
- Twilio (primary)
- Firebase Phone Auth (fallback)
- SMS Gateway (backup)

Author: Santhosh T
Security: Phone numbers are hashed before storage
"""

import os
import re
import time
import random
import string
import hashlib
import hmac
import asyncio
from typing import Optional, Dict, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    """Status of phone verification"""
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"
    BLOCKED = "blocked"


class VerificationProvider(Enum):
    """Supported verification providers"""
    TWILIO = "twilio"
    FIREBASE = "firebase"
    SMS_GATEWAY = "sms_gateway"
    MOCK = "mock"  # For testing


@dataclass
class VerificationAttempt:
    """Tracks verification attempts"""
    phone_hash: str
    phone_number: str  # Store the actual phone number for Twilio verification
    code: str
    provider: VerificationProvider
    created_at: datetime
    expires_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    status: VerificationStatus = VerificationStatus.PENDING
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class PhoneRecord:
    """Record of verified phone number"""
    phone_hash: str
    verified_at: datetime
    user_id: str
    country_code: str
    trial_used: bool = False
    abuse_flags: int = 0
    last_verification: Optional[datetime] = None


class RateLimiter:
    """Rate limiting for verification attempts"""

    def __init__(self):
        self._attempts: Dict[str, list] = {}
        self._blocked: Dict[str, datetime] = {}

        # Rate limits
        self.max_per_minute = 2
        self.max_per_hour = 5
        self.max_per_day = 10
        self.block_duration = timedelta(hours=24)

    def is_blocked(self, identifier: str) -> Tuple[bool, Optional[datetime]]:
        """Check if identifier is blocked"""
        if identifier in self._blocked:
            block_until = self._blocked[identifier]
            if datetime.utcnow() < block_until:
                return True, block_until
            else:
                del self._blocked[identifier]
        return False, None

    def check_rate_limit(self, identifier: str) -> Tuple[bool, str]:
        """
        Check if request is within rate limits

        Returns: (allowed, reason)
        """
        # Check if blocked
        blocked, until = self.is_blocked(identifier)
        if blocked:
            return False, f"Blocked until {until.isoformat()}"

        now = datetime.utcnow()
        attempts = self._attempts.get(identifier, [])

        # Clean old attempts
        attempts = [t for t in attempts if now - t < timedelta(days=1)]
        self._attempts[identifier] = attempts

        # Check limits
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        minute_count = sum(1 for t in attempts if t > minute_ago)
        hour_count = sum(1 for t in attempts if t > hour_ago)
        day_count = sum(1 for t in attempts if t > day_ago)

        if minute_count >= self.max_per_minute:
            return False, "Too many attempts per minute"
        if hour_count >= self.max_per_hour:
            return False, "Too many attempts per hour"
        if day_count >= self.max_per_day:
            # Block for 24 hours
            self._blocked[identifier] = now + self.block_duration
            return False, "Daily limit exceeded, blocked for 24 hours"

        return True, ""

    def record_attempt(self, identifier: str) -> None:
        """Record a verification attempt"""
        if identifier not in self._attempts:
            self._attempts[identifier] = []
        self._attempts[identifier].append(datetime.utcnow())


class TwilioProvider:
    """Twilio SMS verification provider"""

    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.verify_service_sid = os.getenv('TWILIO_VERIFY_SERVICE_SID')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')
        self._client = None

    @property
    def is_configured(self) -> bool:
        """Check if Twilio is configured"""
        return all([self.account_sid, self.auth_token, self.verify_service_sid])

    def _get_client(self):
        """Get or create Twilio client"""
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.warning("Twilio SDK not installed")
                return None
        return self._client

    async def send_verification(self, phone_number: str) -> Tuple[bool, str]:
        """
        Send verification code via Twilio Verify

        Returns: (success, message_or_error)
        """
        client = self._get_client()
        if not client:
            return False, "Twilio not configured"

        try:
            verification = client.verify.v2.services(
                self.verify_service_sid
            ).verifications.create(
                to=phone_number,
                channel='sms'
            )
            return True, verification.sid
        except Exception as e:
            logger.error(f"Twilio send error: {e}")
            return False, str(e)

    async def check_verification(self, phone_number: str, code: str) -> Tuple[bool, str]:
        """
        Check verification code via Twilio Verify

        Returns: (success, status)
        """
        client = self._get_client()
        if not client:
            return False, "Twilio not configured"

        try:
            verification_check = client.verify.v2.services(
                self.verify_service_sid
            ).verification_checks.create(
                to=phone_number,
                code=code
            )
            return verification_check.status == 'approved', verification_check.status
        except Exception as e:
            logger.error(f"Twilio verify error: {e}")
            return False, str(e)


class FirebasePhoneProvider:
    """Firebase Phone Auth provider (for fallback)"""

    def __init__(self):
        self.project_id = os.getenv('FIREBASE_PROJECT_ID')
        self.api_key = os.getenv('FIREBASE_API_KEY')

    @property
    def is_configured(self) -> bool:
        """Check if Firebase is configured"""
        return all([self.project_id, self.api_key])

    async def send_verification(self, phone_number: str) -> Tuple[bool, str]:
        """
        Send verification via Firebase

        Note: Firebase Phone Auth is typically client-side,
        this is a server-side approximation
        """
        if not self.is_configured:
            return False, "Firebase not configured"

        # Firebase phone auth is primarily client-side
        # Server generates a session token, client handles UI
        try:
            import httpx

            url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key={self.api_key}"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={
                    "phoneNumber": phone_number,
                    "recaptchaToken": "RECAPTCHA_TOKEN_REQUIRED"
                })

                if response.status_code == 200:
                    data = response.json()
                    return True, data.get('sessionInfo', '')
                else:
                    return False, response.text

        except Exception as e:
            logger.error(f"Firebase send error: {e}")
            return False, str(e)

    async def check_verification(self, session_info: str, code: str) -> Tuple[bool, str]:
        """Check Firebase verification code"""
        if not self.is_configured:
            return False, "Firebase not configured"

        try:
            import httpx

            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber?key={self.api_key}"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={
                    "sessionInfo": session_info,
                    "code": code
                })

                if response.status_code == 200:
                    return True, "verified"
                else:
                    return False, response.text

        except Exception as e:
            logger.error(f"Firebase verify error: {e}")
            return False, str(e)


class MockProvider:
    """Mock provider for testing"""

    def __init__(self):
        self._codes: Dict[str, str] = {}

    async def send_verification(self, phone_number: str) -> Tuple[bool, str]:
        """Send mock verification code"""
        code = ''.join(random.choices(string.digits, k=6))
        self._codes[phone_number] = code
        logger.info(f"[MOCK] Verification code for {phone_number}: {code}")
        return True, code

    async def check_verification(self, phone_number: str, code: str) -> Tuple[bool, str]:
        """Check mock verification code"""
        expected = self._codes.get(phone_number)
        if expected and expected == code:
            del self._codes[phone_number]
            return True, "verified"
        return False, "invalid_code"


class PhoneVerificationService:
    """
    Main phone verification service

    Handles:
    - Sending verification codes
    - Verifying codes
    - Rate limiting
    - Phone number hashing/storage
    - Trial abuse detection
    """

    # Security salt for phone hashing (should be from env in production)
    PHONE_SALT = os.getenv('PHONE_HASH_SALT', 'termivoxed-phone-salt-change-in-production')

    def __init__(self, firestore_client=None):
        self.firestore = firestore_client

        # Initialize providers
        self.twilio = TwilioProvider()
        self.firebase = FirebasePhoneProvider()
        self.mock = MockProvider()

        # Rate limiter
        self.rate_limiter = RateLimiter()

        # In-memory verification cache
        self._verifications: Dict[str, VerificationAttempt] = {}

        # Phone number pattern validation
        self.phone_pattern = re.compile(r'^\+[1-9]\d{1,14}$')

        # Blocked country codes (disposable/VoIP heavy regions)
        self.blocked_country_codes = set()  # Configure as needed

        # Minimum phone number length per country
        self.min_lengths = {
            '+1': 11,   # US/Canada
            '+44': 12,  # UK
            '+91': 13,  # India
            '+86': 13,  # China
        }

    def _get_provider(self) -> Tuple[Any, VerificationProvider]:
        """Get best available provider"""
        if self.twilio.is_configured:
            return self.twilio, VerificationProvider.TWILIO
        if self.firebase.is_configured:
            return self.firebase, VerificationProvider.FIREBASE
        # Fall back to mock for development
        return self.mock, VerificationProvider.MOCK

    def hash_phone(self, phone_number: str) -> str:
        """
        Create secure hash of phone number

        Uses HMAC-SHA256 with salt for security
        """
        normalized = self._normalize_phone(phone_number)
        return hmac.new(
            self.PHONE_SALT.encode(),
            normalized.encode(),
            hashlib.sha256
        ).hexdigest()

    def _normalize_phone(self, phone_number: str) -> str:
        """Normalize phone number format"""
        # Remove all non-digit characters except +
        normalized = re.sub(r'[^\d+]', '', phone_number)

        # Ensure + prefix
        if not normalized.startswith('+'):
            # Assume US if no country code
            if len(normalized) == 10:
                normalized = '+1' + normalized
            elif len(normalized) == 11 and normalized.startswith('1'):
                normalized = '+' + normalized
            else:
                normalized = '+' + normalized

        return normalized

    def validate_phone(self, phone_number: str) -> Tuple[bool, str]:
        """
        Validate phone number format and check for suspicious patterns

        Returns: (valid, error_message)
        """
        normalized = self._normalize_phone(phone_number)

        # Basic E.164 format check
        if not self.phone_pattern.match(normalized):
            return False, "Invalid phone number format"

        # Extract country code
        country_code = None
        for code in [normalized[:4], normalized[:3], normalized[:2]]:
            if code.startswith('+'):
                country_code = code
                break

        if not country_code:
            return False, "Could not determine country code"

        # Check blocked countries
        if country_code in self.blocked_country_codes:
            return False, "Phone numbers from this region are not supported"

        # Check minimum length
        min_length = self.min_lengths.get(country_code, 10)
        if len(normalized) < min_length:
            return False, f"Phone number too short for region {country_code}"

        # Check for sequential numbers (likely fake)
        digits = re.sub(r'\D', '', normalized)
        if self._is_sequential(digits):
            return False, "Invalid phone number pattern"

        # Check for repeated numbers (like 111-111-1111)
        if len(set(digits)) < 3:
            return False, "Invalid phone number pattern"

        return True, ""

    def _is_sequential(self, digits: str) -> bool:
        """Check if digits are sequential"""
        if len(digits) < 7:
            return False

        # Check ascending
        asc_count = sum(1 for i in range(len(digits)-1) if int(digits[i+1]) == int(digits[i]) + 1)

        # Check descending
        desc_count = sum(1 for i in range(len(digits)-1) if int(digits[i+1]) == int(digits[i]) - 1)

        # If more than 70% sequential, suspicious
        threshold = len(digits) * 0.7
        return asc_count >= threshold or desc_count >= threshold

    async def send_verification_code(
        self,
        phone_number: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send verification code to phone number

        Args:
            phone_number: Phone number in E.164 format
            user_id: User ID requesting verification
            ip_address: Request IP for rate limiting
            user_agent: User agent for logging

        Returns: (success, message, verification_id)
        """
        # Validate phone number
        valid, error = self.validate_phone(phone_number)
        if not valid:
            return False, error, None

        normalized = self._normalize_phone(phone_number)
        phone_hash = self.hash_phone(normalized)

        # Check rate limits (by phone and IP)
        for identifier in [phone_hash, ip_address]:
            if identifier:
                allowed, reason = self.rate_limiter.check_rate_limit(identifier)
                if not allowed:
                    return False, f"Rate limited: {reason}", None

        # Check if phone already verified by another user
        if self.firestore:
            existing = await self._get_phone_record(phone_hash)
            if existing and existing.user_id != user_id:
                # Phone belongs to another user
                logger.warning(f"Phone already used by another account: {phone_hash[:16]}...")
                return False, "This phone number is already registered", None

        # Get provider and send
        provider, provider_type = self._get_provider()

        try:
            success, result = await provider.send_verification(normalized)

            if success:
                # Create verification attempt
                code = result if provider_type == VerificationProvider.MOCK else ""
                verification_id = hashlib.sha256(f"{phone_hash}{time.time()}".encode()).hexdigest()[:32]

                attempt = VerificationAttempt(
                    phone_hash=phone_hash,
                    phone_number=normalized,  # Store actual phone number for Twilio verification
                    code=code,
                    provider=provider_type,
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(minutes=10),
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                self._verifications[verification_id] = attempt

                # Record attempt for rate limiting
                self.rate_limiter.record_attempt(phone_hash)
                if ip_address:
                    self.rate_limiter.record_attempt(ip_address)

                logger.info(f"Verification sent for phone hash: {phone_hash[:16]}...")
                return True, "Verification code sent", verification_id

            else:
                logger.error(f"Failed to send verification: {result}")
                return False, "Failed to send verification code", None

        except Exception as e:
            logger.error(f"Verification send error: {e}")
            return False, "Service temporarily unavailable", None

    async def verify_code(
        self,
        verification_id: str,
        code: str,
        user_id: str
    ) -> Tuple[bool, str]:
        """
        Verify the code entered by user

        Args:
            verification_id: ID from send_verification_code
            code: 6-digit code entered by user
            user_id: User ID for verification

        Returns: (success, message)
        """
        if not verification_id or verification_id not in self._verifications:
            return False, "Invalid verification request"

        attempt = self._verifications[verification_id]

        # Check expiration
        if datetime.utcnow() > attempt.expires_at:
            attempt.status = VerificationStatus.EXPIRED
            del self._verifications[verification_id]
            return False, "Verification code expired"

        # Check attempts
        attempt.attempts += 1
        if attempt.attempts > attempt.max_attempts:
            attempt.status = VerificationStatus.FAILED
            del self._verifications[verification_id]
            return False, "Too many failed attempts"

        # Verify based on provider
        try:
            if attempt.provider == VerificationProvider.MOCK:
                # Mock verification
                success = code == attempt.code
            elif attempt.provider == VerificationProvider.TWILIO:
                # Twilio Verify checks the code server-side
                provider = self.twilio
                success, _ = await provider.check_verification(
                    attempt.phone_number,  # Use stored phone number
                    code
                )
            elif attempt.provider == VerificationProvider.FIREBASE:
                # Firebase verification
                provider = self.firebase
                # For Firebase, attempt.code contains the session info
                success, _ = await provider.check_verification(
                    attempt.code,  # Session info stored in code field
                    code
                )
            else:
                success = False

            if success:
                attempt.status = VerificationStatus.VERIFIED

                # Store verification record
                if self.firestore:
                    await self._store_phone_record(
                        phone_hash=attempt.phone_hash,
                        user_id=user_id
                    )

                del self._verifications[verification_id]
                logger.info(f"Phone verified for user: {user_id}")
                return True, "Phone number verified successfully"
            else:
                remaining = attempt.max_attempts - attempt.attempts
                return False, f"Invalid code. {remaining} attempts remaining"

        except Exception as e:
            logger.error(f"Verification check error: {e}")
            return False, "Verification failed"

    async def check_phone_verified(self, user_id: str) -> bool:
        """Check if user has a verified phone number"""
        if not self.firestore:
            return False

        try:
            doc = self.firestore.collection('phone_verifications').document(user_id).get()
            return doc.exists and doc.to_dict().get('verified', False)
        except Exception as e:
            logger.error(f"Error checking phone verification: {e}")
            return False

    async def check_trial_eligibility(self, phone_hash: str) -> Tuple[bool, str]:
        """
        Check if phone is eligible for free trial

        Returns: (eligible, reason)
        """
        if not self.firestore:
            return True, "No verification required"

        try:
            # Check if phone has been used for trial before
            record = await self._get_phone_record(phone_hash)

            if record is None:
                return True, "Eligible for trial"

            if record.trial_used:
                return False, "Trial already used with this phone number"

            if record.abuse_flags > 0:
                return False, "Phone number flagged for abuse"

            return True, "Eligible for trial"

        except Exception as e:
            logger.error(f"Error checking trial eligibility: {e}")
            # Fail open for better UX (but log for investigation)
            return True, "Eligible for trial"

    async def mark_trial_used(self, phone_hash: str) -> bool:
        """Mark that trial has been used for this phone"""
        if not self.firestore:
            return True

        try:
            self.firestore.collection('phone_records').document(phone_hash).update({
                'trial_used': True,
                'trial_used_at': datetime.utcnow().isoformat()
            })
            return True
        except Exception as e:
            logger.error(f"Error marking trial used: {e}")
            return False

    async def _get_phone_record(self, phone_hash: str) -> Optional[PhoneRecord]:
        """Get phone record from Firestore"""
        if not self.firestore:
            return None

        try:
            doc = self.firestore.collection('phone_records').document(phone_hash).get()
            if doc.exists:
                data = doc.to_dict()
                return PhoneRecord(
                    phone_hash=phone_hash,
                    verified_at=data.get('verified_at'),
                    user_id=data.get('user_id'),
                    country_code=data.get('country_code', ''),
                    trial_used=data.get('trial_used', False),
                    abuse_flags=data.get('abuse_flags', 0)
                )
            return None
        except Exception as e:
            logger.error(f"Error getting phone record: {e}")
            return None

    async def _store_phone_record(self, phone_hash: str, user_id: str) -> bool:
        """Store phone verification record"""
        if not self.firestore:
            return True

        try:
            self.firestore.collection('phone_records').document(phone_hash).set({
                'user_id': user_id,
                'verified_at': datetime.utcnow().isoformat(),
                'trial_used': False,
                'abuse_flags': 0,
                'created_at': datetime.utcnow().isoformat()
            }, merge=True)

            # Also store in user's profile
            self.firestore.collection('phone_verifications').document(user_id).set({
                'phone_hash': phone_hash,
                'verified': True,
                'verified_at': datetime.utcnow().isoformat()
            })

            return True
        except Exception as e:
            logger.error(f"Error storing phone record: {e}")
            return False


# Singleton instance
_phone_service: Optional[PhoneVerificationService] = None


def get_phone_verification_service(firestore_client=None) -> PhoneVerificationService:
    """Get or create phone verification service instance"""
    global _phone_service
    if _phone_service is None:
        _phone_service = PhoneVerificationService(firestore_client)
    return _phone_service
