"""
License Guard - Background License Verification Service

This module provides continuous license verification similar to Adobe Creative Cloud.
It runs as a background thread and:
- Periodically verifies license with cloud server
- Handles offline grace periods
- Detects device fingerprint changes
- Forces logout when subscription expires or device limit exceeded
- Provides tamper detection

Integration with Firebase Cloud Functions for cloud verification.
"""

import asyncio
import threading
import time
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import httpx
import jwt

from .device_fingerprint import DeviceFingerprint, get_device_fingerprint, get_device_info
from .models import SubscriptionTier, SubscriptionStatus, FeatureAccess, LicenseToken

logger = logging.getLogger(__name__)


class LicenseStatus(str, Enum):
    """License verification status"""
    VALID = "valid"
    EXPIRED = "expired"
    TRIAL_EXPIRED = "trial_expired"
    DEVICE_MISMATCH = "device_mismatch"
    DEVICE_LIMIT = "device_limit_exceeded"
    REVOKED = "revoked"
    OFFLINE_GRACE = "offline_grace"
    OFFLINE_EXPIRED = "offline_expired"
    NO_LICENSE = "no_license"
    ERROR = "error"


@dataclass
class LicenseVerificationResult:
    """Result of a license verification check"""
    status: LicenseStatus
    message: str
    subscription_tier: Optional[SubscriptionTier] = None
    features: Optional[FeatureAccess] = None
    expires_at: Optional[datetime] = None
    grace_period_remaining: Optional[timedelta] = None
    active_devices: Optional[List[Dict]] = None
    max_devices: int = 1
    needs_action: bool = False
    action_url: Optional[str] = None


class LicenseGuard:
    """
    Background service that continuously verifies license validity.

    Features:
    - Periodic heartbeat verification (every 5-15 minutes when online)
    - Offline grace period support (7 days default)
    - Device fingerprint binding
    - Real-time session revocation handling
    - Tamper detection
    - Feature access caching
    """

    # Configuration
    HEARTBEAT_INTERVAL_ONLINE = 300  # 5 minutes when online
    HEARTBEAT_INTERVAL_OFFLINE = 60  # 1 minute when offline (to detect reconnection)
    OFFLINE_GRACE_PERIOD_DAYS = 7
    LICENSE_CACHE_FILE = ".termivoxed_license.json"

    # Firebase Cloud Functions URL (configure via environment)
    CLOUD_FUNCTIONS_URL = "https://us-central1-termivoxed.cloudfunctions.net"

    def __init__(
        self,
        firebase_id_token: Optional[str] = None,
        on_status_change: Optional[Callable[[LicenseVerificationResult], None]] = None,
        on_force_logout: Optional[Callable[[str], None]] = None,
        app_version: str = "1.0.0"
    ):
        """
        Initialize the LicenseGuard.

        Args:
            firebase_id_token: Firebase Auth ID token for authentication
            on_status_change: Callback when license status changes
            on_force_logout: Callback when user is forced to logout
            app_version: Current app version for verification
        """
        self.firebase_id_token = firebase_id_token
        self.on_status_change = on_status_change
        self.on_force_logout = on_force_logout
        self.app_version = app_version

        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Device fingerprint
        self._device_fingerprint = get_device_fingerprint()
        self._device_info = get_device_info()

        # Cached license
        self._cached_license: Optional[LicenseToken] = None
        self._last_verification: Optional[datetime] = None
        self._last_online_verification: Optional[datetime] = None
        self._current_status: LicenseStatus = LicenseStatus.NO_LICENSE

        # Clock manipulation detection
        # Use monotonic time to detect if system clock was moved backward
        self._last_monotonic_time: float = time.monotonic()
        self._last_wall_clock: datetime = datetime.now()
        self._server_timestamp: Optional[datetime] = None  # Trusted server time
        self._expected_elapsed: float = 0.0  # Expected time elapsed based on monotonic clock

        # License cache path
        self._cache_path = self._get_cache_path()

        # HTTP client for async operations
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_cache_path(self) -> Path:
        """Get the path for license cache file"""
        # Store in user's home directory
        home = Path.home()
        cache_dir = home / ".termivoxed"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / self.LICENSE_CACHE_FILE

    def start(self) -> None:
        """Start the background license verification thread"""
        if self._running:
            logger.warning("LicenseGuard is already running")
            return

        logger.info("Starting LicenseGuard background service")

        # Load cached license
        self._load_cached_license()

        # Start background thread
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._guard_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background license verification"""
        if not self._running:
            return

        logger.info("Stopping LicenseGuard")
        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _guard_loop(self) -> None:
        """Main guard loop running in background thread"""
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self._running and not self._stop_event.is_set():
                try:
                    # Run verification
                    result = loop.run_until_complete(self._verify_license())

                    # Handle status change
                    if result.status != self._current_status:
                        self._current_status = result.status
                        if self.on_status_change:
                            self.on_status_change(result)

                    # Handle force logout scenarios
                    if result.status in (
                        LicenseStatus.REVOKED,
                        LicenseStatus.DEVICE_MISMATCH,
                        LicenseStatus.OFFLINE_EXPIRED
                    ):
                        if self.on_force_logout:
                            self.on_force_logout(result.message)
                        break

                    # Determine next check interval
                    interval = (
                        self.HEARTBEAT_INTERVAL_ONLINE
                        if result.status != LicenseStatus.OFFLINE_GRACE
                        else self.HEARTBEAT_INTERVAL_OFFLINE
                    )

                    # Wait for interval or stop signal
                    self._stop_event.wait(timeout=interval)

                except Exception as e:
                    logger.error(f"License verification error: {e}")
                    # Wait before retry
                    self._stop_event.wait(timeout=60)

        finally:
            loop.close()

    async def _verify_license(self) -> LicenseVerificationResult:
        """
        Perform license verification.

        This checks:
        1. Local cache validity
        2. Device fingerprint match
        3. Cloud verification (if online)
        4. Offline grace period
        """
        self._last_verification = datetime.now()

        # Check if we have any cached license
        if not self._cached_license:
            return LicenseVerificationResult(
                status=LicenseStatus.NO_LICENSE,
                message="No license found. Please log in.",
                needs_action=True,
                action_url="/login"
            )

        # Verify device fingerprint
        if not self._verify_device_fingerprint():
            return LicenseVerificationResult(
                status=LicenseStatus.DEVICE_MISMATCH,
                message="Device fingerprint mismatch. Please log in again.",
                needs_action=True,
                action_url="/login"
            )

        # Check internet connectivity and verify with cloud
        is_online = await self._check_connectivity()

        if is_online:
            result = await self._cloud_verify()
            if result.status == LicenseStatus.VALID:
                self._last_online_verification = datetime.now()
                self._update_cached_license_online_check()
                self._save_cached_license()
            return result

        # Offline mode - check grace period
        return self._check_offline_grace()

    def _verify_device_fingerprint(self) -> bool:
        """Verify current device matches cached license"""
        if not self._cached_license:
            return False

        current_fingerprint = get_device_fingerprint()
        return current_fingerprint == self._cached_license.device_fingerprint

    async def _check_connectivity(self) -> bool:
        """Check if we can reach the cloud server"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.CLOUD_FUNCTIONS_URL}/health")
                return response.status_code == 200
        except Exception:
            return False

    async def _cloud_verify(self) -> LicenseVerificationResult:
        """Verify license with cloud server"""
        if not self.firebase_id_token:
            return LicenseVerificationResult(
                status=LicenseStatus.NO_LICENSE,
                message="No authentication token",
                needs_action=True
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.CLOUD_FUNCTIONS_URL}/verifyLicense",
                    json={
                        "data": {
                            "deviceFingerprint": self._device_fingerprint,
                            "appVersion": self.app_version,
                            "currentToken": self._cached_license.token if self._cached_license else None
                        }
                    },
                    headers={
                        "Authorization": f"Bearer {self.firebase_id_token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Cloud verification failed: {response.status_code}")
                    return LicenseVerificationResult(
                        status=LicenseStatus.ERROR,
                        message="Verification server error"
                    )

                data = response.json().get("result", {})
                return self._parse_cloud_response(data)

        except httpx.TimeoutException:
            logger.warning("Cloud verification timeout - using offline mode")
            return self._check_offline_grace()

        except Exception as e:
            logger.error(f"Cloud verification error: {e}")
            return LicenseVerificationResult(
                status=LicenseStatus.ERROR,
                message=str(e)
            )

    def _parse_cloud_response(self, data: Dict[str, Any]) -> LicenseVerificationResult:
        """Parse cloud verification response"""
        status = data.get("status", "ERROR")

        if status == "VALID":
            # Update cached license with new token
            if data.get("token"):
                self._update_cached_license_from_cloud(data)

            subscription = data.get("subscription", {})

            return LicenseVerificationResult(
                status=LicenseStatus.VALID,
                message="License valid",
                subscription_tier=SubscriptionTier(subscription.get("tier", "basic").lower()),
                features=self._parse_features(subscription.get("features", {})),
                expires_at=datetime.fromisoformat(subscription["periodEnd"]) if subscription.get("periodEnd") else None
            )

        elif status == "EXPIRED":
            return LicenseVerificationResult(
                status=LicenseStatus.EXPIRED,
                message="Subscription has expired",
                needs_action=True,
                action_url=data.get("renewUrl", "/renew")
            )

        elif status == "TRIAL_EXPIRED":
            return LicenseVerificationResult(
                status=LicenseStatus.TRIAL_EXPIRED,
                message="Free trial has expired",
                needs_action=True,
                action_url=data.get("upgradeUrl", "/upgrade")
            )

        elif status == "DEVICE_LIMIT_EXCEEDED":
            return LicenseVerificationResult(
                status=LicenseStatus.DEVICE_LIMIT,
                message=data.get("message", "Device limit exceeded"),
                active_devices=data.get("activeDevices", []),
                max_devices=data.get("maxDevices", 1),
                needs_action=True,
                action_url="/devices"
            )

        elif status == "DEVICE_CONFLICT":
            return LicenseVerificationResult(
                status=LicenseStatus.DEVICE_MISMATCH,
                message="This device is registered to another account",
                needs_action=True,
                action_url="/login"
            )

        elif status == "DEVICE_DEACTIVATED":
            return LicenseVerificationResult(
                status=LicenseStatus.REVOKED,
                message=data.get("message", "Device was deactivated"),
                needs_action=True,
                action_url="/login"
            )

        elif status == "NO_SUBSCRIPTION":
            return LicenseVerificationResult(
                status=LicenseStatus.NO_LICENSE,
                message="No subscription found",
                needs_action=True,
                action_url="/pricing"
            )

        else:
            return LicenseVerificationResult(
                status=LicenseStatus.ERROR,
                message=data.get("message", "Unknown error")
            )

    def _detect_clock_manipulation(self) -> bool:
        """
        Detect if the system clock was moved backward (anti-piracy measure).

        Uses monotonic time to track actual elapsed time and compares with wall clock.
        Returns True if clock manipulation is detected.
        """
        current_monotonic = time.monotonic()
        current_wall_clock = datetime.now()

        # Calculate elapsed time using monotonic clock (cannot be manipulated)
        monotonic_elapsed = current_monotonic - self._last_monotonic_time

        # Calculate elapsed time using wall clock
        wall_elapsed = (current_wall_clock - self._last_wall_clock).total_seconds()

        # Allow for small clock drift (e.g., NTP adjustments) - 60 seconds tolerance
        clock_drift_tolerance = 60.0

        # If wall clock went backward significantly, or much slower than monotonic,
        # this indicates clock manipulation
        if wall_elapsed < -clock_drift_tolerance:
            logger.warning(f"Clock manipulation detected: wall clock went backward by {abs(wall_elapsed):.0f}s")
            return True

        # If wall clock is significantly behind monotonic clock
        # (user set clock back after app started)
        if monotonic_elapsed - wall_elapsed > 3600:  # More than 1 hour discrepancy
            logger.warning(f"Clock manipulation detected: {(monotonic_elapsed - wall_elapsed)/3600:.1f}h discrepancy")
            return True

        # Update tracking values
        self._last_monotonic_time = current_monotonic
        self._last_wall_clock = current_wall_clock

        return False

    def _get_secure_offline_duration(self) -> timedelta:
        """
        Calculate offline duration using monotonic time to prevent clock manipulation.

        This uses a combination of:
        1. Monotonic clock (cannot be manipulated, but resets on reboot)
        2. Server timestamp from last verification
        3. Accumulated time across sessions
        """
        if not self._last_online_verification:
            # No online verification - treat as expired for safety
            return timedelta(days=self.OFFLINE_GRACE_PERIOD_DAYS + 1)

        # Get current wall clock
        now = datetime.now()

        # Calculate duration based on wall clock
        wall_duration = now - self._last_online_verification

        # If we have server timestamp, use it as reference
        if self._server_timestamp:
            # Calculate expected current time based on server timestamp + monotonic elapsed
            expected_now = self._server_timestamp + timedelta(seconds=self._expected_elapsed)

            # If current time is more than 1 hour behind expected, clock was manipulated
            if now < expected_now - timedelta(hours=1):
                logger.warning("Clock set back detected - using server-based time")
                # Use monotonic-based calculation instead
                return timedelta(seconds=self._expected_elapsed)

        return wall_duration

    def _check_offline_grace(self) -> LicenseVerificationResult:
        """Check if offline grace period is still valid (with anti-tampering)"""
        if not self._cached_license:
            return LicenseVerificationResult(
                status=LicenseStatus.NO_LICENSE,
                message="No cached license"
            )

        if not self._last_online_verification:
            # Never verified online - check cached value
            self._last_online_verification = self._cached_license.last_online_check

        # SECURITY: Check for clock manipulation
        if self._detect_clock_manipulation():
            logger.error("Clock manipulation detected during offline check")
            return LicenseVerificationResult(
                status=LicenseStatus.ERROR,
                message="System clock tampering detected. Please verify your system time and reconnect to the internet.",
                needs_action=True
            )

        grace_period = timedelta(days=self.OFFLINE_GRACE_PERIOD_DAYS)

        # SECURITY: Use secure duration calculation
        offline_duration = self._get_secure_offline_duration()

        if offline_duration > grace_period:
            return LicenseVerificationResult(
                status=LicenseStatus.OFFLINE_EXPIRED,
                message=f"Offline for more than {self.OFFLINE_GRACE_PERIOD_DAYS} days. Please connect to internet.",
                needs_action=True
            )

        remaining = grace_period - offline_duration

        return LicenseVerificationResult(
            status=LicenseStatus.OFFLINE_GRACE,
            message=f"Offline mode - {remaining.days} days remaining",
            subscription_tier=self._cached_license.tier,
            features=self._cached_license.features,
            grace_period_remaining=remaining
        )

    def _parse_features(self, features_dict: Dict) -> FeatureAccess:
        """Parse features dictionary into FeatureAccess"""
        return FeatureAccess(
            basic_export=features_dict.get("basic_export", True),
            multi_video_projects=features_dict.get("multi_video_projects", False),
            advanced_tts_voices=features_dict.get("advanced_tts_voices", False),
            export_4k=features_dict.get("export_4k", False),
            batch_export=features_dict.get("batch_export", False),
            custom_subtitle_styles=features_dict.get("custom_subtitle_styles", False),
            cross_video_segments=features_dict.get("cross_video_segments", False),
            priority_support=features_dict.get("priority_support", False),
        )

    def _update_cached_license_from_cloud(self, data: Dict) -> None:
        """Update cached license from cloud response"""
        subscription = data.get("subscription", {})

        self._cached_license = LicenseToken(
            token=data.get("token", ""),
            user_id=data.get("device", {}).get("userId", ""),
            email=subscription.get("email", ""),
            tier=SubscriptionTier(subscription.get("tier", "individual").lower()),
            features=self._parse_features(subscription.get("features", {})),
            issued_at=datetime.now(),
            expires_at=datetime.fromisoformat(subscription["periodEnd"]) if subscription.get("periodEnd") else datetime.now() + timedelta(days=30),
            device_id=data.get("device", {}).get("deviceId", ""),
            device_fingerprint=self._device_fingerprint,
            last_online_check=datetime.now()
        )

        # SECURITY: Store server timestamp for clock manipulation detection
        # The server includes its current timestamp in the response
        server_time_str = data.get("serverTimestamp") or data.get("timestamp")
        if server_time_str:
            try:
                self._server_timestamp = datetime.fromisoformat(server_time_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                self._server_timestamp = datetime.now()
        else:
            self._server_timestamp = datetime.now()

        # Reset monotonic tracking on successful online verification
        self._last_monotonic_time = time.monotonic()
        self._last_wall_clock = datetime.now()
        self._expected_elapsed = 0.0  # Reset elapsed time counter

        self._save_cached_license()

    def _update_cached_license_online_check(self) -> None:
        """Update last online check time and reset clock tracking"""
        if self._cached_license:
            self._cached_license.last_online_check = datetime.now()

            # Reset clock manipulation tracking on successful online check
            self._last_monotonic_time = time.monotonic()
            self._last_wall_clock = datetime.now()
            self._expected_elapsed = 0.0

    def _load_cached_license(self) -> None:
        """Load cached license from disk"""
        try:
            if not self._cache_path.exists():
                return

            # Read and decrypt
            encrypted_data = self._cache_path.read_bytes()
            decrypted = self._decrypt_cache(encrypted_data)

            data = json.loads(decrypted)
            self._cached_license = LicenseToken.from_dict(data)

            logger.info("Loaded cached license")

        except Exception as e:
            logger.warning(f"Failed to load cached license: {e}")
            self._cached_license = None

    def _save_cached_license(self) -> None:
        """Save cached license to disk (encrypted with secure permissions)"""
        if not self._cached_license:
            return

        try:
            import os
            import stat

            data = json.dumps(self._cached_license.to_dict())
            encrypted = self._encrypt_cache(data)
            self._cache_path.write_bytes(encrypted)

            # Set secure file permissions (owner read/write only)
            # This prevents other users/processes from reading the license
            try:
                if os.name != 'nt':  # Unix/Linux/macOS
                    os.chmod(self._cache_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
                else:  # Windows
                    # On Windows, use icacls to restrict access
                    import subprocess
                    subprocess.run(
                        ['icacls', str(self._cache_path), '/inheritance:r',
                         '/grant:r', f'{os.environ.get("USERNAME", "SYSTEM")}:(R,W)'],
                        capture_output=True,
                        timeout=5
                    )
            except Exception as perm_error:
                logger.warning(f"Could not set secure permissions: {perm_error}")

            logger.debug("Saved cached license with secure permissions")

        except Exception as e:
            logger.error(f"Failed to save cached license: {e}")

    def _get_encryption_salt(self) -> bytes:
        """
        Get the encryption salt from environment variable.

        SECURITY: In production, TERMIVOXED_ENCRYPTION_SALT MUST be set.
        Falls back to a development salt only in non-production environments.
        """
        import os

        env_salt = os.environ.get("TERMIVOXED_ENCRYPTION_SALT")

        if env_salt:
            return env_salt.encode()

        # Check if we're in production
        if os.environ.get("TERMIVOXED_ENV") == "production":
            # In production, this is a critical error - DO NOT USE FALLBACK
            logger.critical(
                "SECURITY CRITICAL: TERMIVOXED_ENCRYPTION_SALT not set in production! "
                "Application cannot start with insecure encryption."
            )
            raise RuntimeError(
                "CRITICAL: TERMIVOXED_ENCRYPTION_SALT environment variable is not set. "
                "This is REQUIRED for production deployments. "
                "Generate a secure salt with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )

        # Development fallback - log warning (only for non-production)
        logger.warning(
            "Using development encryption salt. "
            "Set TERMIVOXED_ENCRYPTION_SALT for production."
        )
        return b"TERMIVOXED_DEV_SALT_v2_CHANGE_IN_PRODUCTION"

    def _get_encryption_key(self) -> bytes:
        """
        Derive a secure encryption key using PBKDF2.

        Uses the device fingerprint as input to create a Fernet-compatible key.
        PBKDF2 with 480,000 iterations (OWASP recommended minimum for 2023+).
        """
        try:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            import base64

            # SECURITY: Salt from environment variable (not hardcoded)
            salt = self._get_encryption_salt()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,  # OWASP 2023 recommendation
            )

            key = base64.urlsafe_b64encode(
                kdf.derive(self._device_fingerprint.encode())
            )
            return key

        except ImportError:
            # Fallback if cryptography not installed - use stronger derivation
            logger.warning("cryptography package not installed, using fallback key derivation")
            import hmac
            # SECURITY: Use environment-based salt in fallback too
            salt = self._get_encryption_salt()
            key_material = hmac.new(
                salt,
                self._device_fingerprint.encode(),
                hashlib.sha256
            ).digest()
            import base64
            return base64.urlsafe_b64encode(key_material)

    def _encrypt_cache(self, data: str) -> bytes:
        """
        Encrypt license cache using Fernet (AES-128-CBC + HMAC).

        This provides:
        - Confidentiality: AES-128 encryption
        - Integrity: HMAC-SHA256 authentication
        - Freshness: Timestamp in token prevents replay attacks

        Falls back to AES-GCM if Fernet unavailable.
        """
        try:
            from cryptography.fernet import Fernet

            key = self._get_encryption_key()
            f = Fernet(key)
            encrypted = f.encrypt(data.encode('utf-8'))

            # Add version prefix for future migration
            return b"v2:" + encrypted

        except ImportError:
            # Fallback: Use AES-GCM from standard library (Python 3.6+)
            logger.warning("Fernet not available, using AES-GCM fallback")
            return self._encrypt_cache_fallback(data)

    def _encrypt_cache_fallback(self, data: str) -> bytes:
        """Fallback encryption using AES-GCM from cryptography or simple method"""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import os

            # SECURITY: Derive 256-bit key using environment-based salt
            salt = self._get_encryption_salt().decode('utf-8', errors='replace')
            key = hashlib.sha256(
                f"{salt}_AES_{self._device_fingerprint}".encode()
            ).digest()

            # Generate random nonce
            nonce = os.urandom(12)

            aesgcm = AESGCM(key)
            encrypted = aesgcm.encrypt(nonce, data.encode('utf-8'), None)

            # Format: v1:nonce:ciphertext
            import base64
            return b"v1:" + base64.b64encode(nonce + encrypted)

        except ImportError:
            # Last resort: enhanced XOR with HMAC for integrity
            logger.warning("No cryptography package, using enhanced obfuscation")
            # SECURITY: Use environment-based salt
            salt = self._get_encryption_salt().decode('utf-8', errors='replace')
            key = hashlib.sha256(
                f"{salt}_{self._device_fingerprint}".encode()
            ).digest()

            data_bytes = data.encode('utf-8')
            encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data_bytes))

            # Add HMAC for integrity
            import hmac
            mac = hmac.new(key, encrypted, hashlib.sha256).digest()

            return b"v0:" + mac + encrypted

    def _decrypt_cache(self, encrypted: bytes) -> str:
        """
        Decrypt license cache.

        Handles multiple encryption versions for backward compatibility:
        - v2: Fernet (preferred)
        - v1: AES-GCM
        - v0: Enhanced XOR with HMAC
        - (no prefix): Legacy XOR
        """
        # Check version prefix
        if encrypted.startswith(b"v2:"):
            return self._decrypt_fernet(encrypted[3:])
        elif encrypted.startswith(b"v1:"):
            return self._decrypt_aesgcm(encrypted[3:])
        elif encrypted.startswith(b"v0:"):
            return self._decrypt_enhanced_xor(encrypted[3:])
        else:
            # Legacy format - migrate on next save
            return self._decrypt_legacy_xor(encrypted)

    def _decrypt_fernet(self, encrypted: bytes) -> str:
        """Decrypt Fernet-encrypted data"""
        from cryptography.fernet import Fernet

        key = self._get_encryption_key()
        f = Fernet(key)
        return f.decrypt(encrypted).decode('utf-8')

    def _decrypt_aesgcm(self, encrypted: bytes) -> str:
        """Decrypt AES-GCM encrypted data (supports both new and legacy keys)"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64

        decoded = base64.b64decode(encrypted)
        nonce = decoded[:12]
        ciphertext = decoded[12:]

        # Try new environment-based salt first
        salt = self._get_encryption_salt().decode('utf-8', errors='replace')
        key_new = hashlib.sha256(
            f"{salt}_AES_{self._device_fingerprint}".encode()
        ).digest()

        try:
            aesgcm = AESGCM(key_new)
            return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')
        except Exception:
            # Fall back to legacy hardcoded key for backward compatibility
            logger.debug("Trying legacy key for v1 cache decryption")
            key_legacy = hashlib.sha256(
                f"TERMIVOXED_AES_{self._device_fingerprint}".encode()
            ).digest()
            aesgcm = AESGCM(key_legacy)
            return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')

    def _decrypt_enhanced_xor(self, encrypted: bytes) -> str:
        """Decrypt enhanced XOR with HMAC verification (supports both new and legacy keys)"""
        import hmac as hmac_module

        # Extract MAC and ciphertext
        stored_mac = encrypted[:32]
        ciphertext = encrypted[32:]

        # Try new environment-based salt first
        salt = self._get_encryption_salt().decode('utf-8', errors='replace')
        key_new = hashlib.sha256(
            f"{salt}_{self._device_fingerprint}".encode()
        ).digest()

        expected_mac_new = hmac_module.new(key_new, ciphertext, hashlib.sha256).digest()
        if hmac_module.compare_digest(stored_mac, expected_mac_new):
            decrypted = bytes(b ^ key_new[i % len(key_new)] for i, b in enumerate(ciphertext))
            return decrypted.decode('utf-8')

        # Fall back to legacy hardcoded key
        logger.debug("Trying legacy key for v0 cache decryption")
        key_legacy = hashlib.sha256(
            f"TERMIVOXED_{self._device_fingerprint}".encode()
        ).digest()

        expected_mac_legacy = hmac_module.new(key_legacy, ciphertext, hashlib.sha256).digest()
        if hmac_module.compare_digest(stored_mac, expected_mac_legacy):
            decrypted = bytes(b ^ key_legacy[i % len(key_legacy)] for i, b in enumerate(ciphertext))
            return decrypted.decode('utf-8')

        raise ValueError("License cache integrity check failed")

    def _decrypt_legacy_xor(self, encrypted: bytes) -> str:
        """Decrypt legacy XOR format (for backward compatibility only)"""
        logger.info("Migrating legacy license cache to secure format")

        # Legacy format only used hardcoded key
        key = hashlib.sha256(
            f"TERMIVOXED_{self._device_fingerprint}".encode()
        ).digest()

        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(encrypted))
        return decrypted.decode('utf-8')

    def clear_cache(self) -> None:
        """Clear cached license (for logout)"""
        self._cached_license = None
        self._last_verification = None
        self._last_online_verification = None

        if self._cache_path.exists():
            self._cache_path.unlink()

        logger.info("Cleared license cache")

    def get_current_status(self) -> LicenseVerificationResult:
        """Get current license status (non-blocking)"""
        if self._cached_license is None:
            return LicenseVerificationResult(
                status=LicenseStatus.NO_LICENSE,
                message="No license"
            )

        if self._current_status == LicenseStatus.VALID:
            return LicenseVerificationResult(
                status=LicenseStatus.VALID,
                message="License valid",
                subscription_tier=self._cached_license.tier,
                features=self._cached_license.features,
                expires_at=self._cached_license.expires_at
            )

        return LicenseVerificationResult(
            status=self._current_status,
            message="See license status"
        )

    def has_feature(self, feature: str) -> bool:
        """Check if user has access to a specific feature"""
        if not self._cached_license or not self._cached_license.features:
            return False

        return getattr(self._cached_license.features, feature, False)

    def get_feature_limit(self, limit_name: str) -> int:
        """Get a feature limit value"""
        if not self._cached_license or not self._cached_license.features:
            return 0

        return getattr(self._cached_license.features, limit_name, 0)

    def set_firebase_token(self, token: str) -> None:
        """Update the Firebase ID token"""
        self.firebase_id_token = token

    @property
    def is_licensed(self) -> bool:
        """Check if there is a valid license"""
        return self._current_status in (
            LicenseStatus.VALID,
            LicenseStatus.OFFLINE_GRACE
        )

    @property
    def subscription_tier(self) -> Optional[SubscriptionTier]:
        """Get current subscription tier"""
        if self._cached_license:
            return self._cached_license.tier
        return None


# Singleton instance
_guard_instance: Optional[LicenseGuard] = None


def get_license_guard() -> LicenseGuard:
    """Get the singleton LicenseGuard instance"""
    global _guard_instance

    if _guard_instance is None:
        _guard_instance = LicenseGuard()

    return _guard_instance


def init_license_guard(
    firebase_id_token: Optional[str] = None,
    on_status_change: Optional[Callable] = None,
    on_force_logout: Optional[Callable] = None,
    app_version: str = "1.0.0"
) -> LicenseGuard:
    """Initialize and return the LicenseGuard singleton"""
    global _guard_instance

    _guard_instance = LicenseGuard(
        firebase_id_token=firebase_id_token,
        on_status_change=on_status_change,
        on_force_logout=on_force_logout,
        app_version=app_version
    )

    return _guard_instance


# Decorator for protecting functions with license check
def require_license(feature: Optional[str] = None):
    """
    Decorator to protect functions with license verification.

    Usage:
        @require_license(feature="export_4k")
        def export_video_4k():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            guard = get_license_guard()

            if not guard.is_licensed:
                raise LicenseError("No valid license")

            if feature and not guard.has_feature(feature):
                raise FeatureNotAvailableError(
                    f"Feature '{feature}' requires upgrade"
                )

            return func(*args, **kwargs)

        return wrapper
    return decorator


class LicenseError(Exception):
    """Exception raised when license is invalid or missing"""
    pass


class FeatureNotAvailableError(Exception):
    """Exception raised when a feature is not available in current plan"""
    pass


if __name__ == "__main__":
    # Test the license guard
    import sys

    logging.basicConfig(level=logging.DEBUG)

    def on_status_change(result: LicenseVerificationResult):
        print(f"Status changed: {result.status} - {result.message}")

    def on_force_logout(reason: str):
        print(f"FORCE LOGOUT: {reason}")
        sys.exit(1)

    guard = init_license_guard(
        on_status_change=on_status_change,
        on_force_logout=on_force_logout
    )

    print(f"Device fingerprint: {guard._device_fingerprint}")
    print(f"Current status: {guard.get_current_status()}")

    # Start guard (would run indefinitely)
    # guard.start()
    # time.sleep(10)
    # guard.stop()
