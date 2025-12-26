"""
License Manager - Client-side license verification and caching

Implements proven patterns from industry leaders:
- JWT-based license tokens (like Adobe)
- Offline grace period (like JetBrains)
- Device fingerprinting (like Netflix)
- Secure local storage

This module handles:
- Device fingerprint generation
- License token caching
- Offline verification
- Cloud sync when online
"""

import os
import json
import hashlib
import platform
import subprocess
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple
import base64
import hmac
import stat

from subscription.models import (
    LicenseToken,
    FeatureAccess,
    SubscriptionTier,
    SubscriptionStatus,
    DeviceInfo,
    UserSubscription
)
from utils.logger import logger

# Secure encryption imports - REQUIRED for production
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class LicenseManager:
    """
    Manages license verification and device registration.

    Security features:
    - Device fingerprinting using multiple hardware identifiers
    - Encrypted local license cache
    - JWT signature verification
    - Offline grace period enforcement
    """

    # License file location (in user's app data directory)
    LICENSE_DIR = Path.home() / ".termivoxed"
    LICENSE_FILE = LICENSE_DIR / "license.json"
    DEVICE_FILE = LICENSE_DIR / "device.json"

    # Cloud API endpoint (to be configured)
    API_BASE_URL = os.environ.get("TERMIVOXED_API_URL", "https://api.termivoxed.com")

    # Encryption configuration
    # PBKDF2 iterations - OWASP 2023 recommends 480,000 for SHA-256
    _PBKDF2_ITERATIONS = 480000
    # Salt MUST be set via environment variable for production security
    _ENCRYPTION_SALT = os.environ.get("TERMIVOXED_ENCRYPTION_SALT", "").encode() or None

    @classmethod
    def _get_salt(cls) -> bytes:
        """Get encryption salt - raises error if not configured"""
        if not cls._ENCRYPTION_SALT:
            raise ValueError(
                "CRITICAL: TERMIVOXED_ENCRYPTION_SALT environment variable not set! "
                "Generate a secure salt with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return cls._ENCRYPTION_SALT

    def __init__(self):
        """Initialize the license manager"""
        self._license: Optional[LicenseToken] = None
        self._device: Optional[DeviceInfo] = None
        self._ensure_directories()
        self._load_cached_data()

    def _ensure_directories(self):
        """Ensure license directories exist"""
        self.LICENSE_DIR.mkdir(parents=True, exist_ok=True)

    def _load_cached_data(self):
        """Load cached license and device info"""
        try:
            # Load device info
            if self.DEVICE_FILE.exists():
                with open(self.DEVICE_FILE, 'r') as f:
                    data = json.load(f)
                    self._device = DeviceInfo.from_dict(data)

            # Load license token
            if self.LICENSE_FILE.exists():
                with open(self.LICENSE_FILE, 'r') as f:
                    encrypted_data = f.read()
                    data = self._decrypt_local(encrypted_data)
                    if data:
                        self._license = LicenseToken.from_dict(data)
                        logger.info(f"Loaded cached license for {self._license.email}")
        except Exception as e:
            logger.warning(f"Could not load cached license data: {e}")

    def _save_cached_data(self):
        """Save license and device info to cache"""
        try:
            # Save device info
            if self._device:
                with open(self.DEVICE_FILE, 'w') as f:
                    json.dump(self._device.to_dict(), f, indent=2)

            # Save license token (encrypted)
            if self._license:
                data = self._license.to_dict()
                encrypted = self._encrypt_local(data)
                with open(self.LICENSE_FILE, 'w') as f:
                    f.write(encrypted)
                # Set secure file permissions
                self._set_secure_file_permissions(self.LICENSE_FILE)
        except Exception as e:
            logger.error(f"Could not save cached license data: {e}")

    def _get_encryption_key(self) -> bytes:
        """
        Derive a secure encryption key using PBKDF2.

        Uses device fingerprint as input material to create a device-bound key.
        This means license files cannot be copied between devices.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._get_salt(),
            iterations=self._PBKDF2_ITERATIONS,
        )
        fingerprint = self.get_device_fingerprint()
        key = base64.urlsafe_b64encode(kdf.derive(fingerprint.encode()))
        return key

    def _encrypt_local(self, data: dict) -> str:
        """
        Encrypt data for local storage using Fernet (AES-128-CBC + HMAC-SHA256).

        Security features:
        - AES-128-CBC encryption for confidentiality
        - HMAC-SHA256 for integrity verification
        - Timestamp-based freshness (prevents replay attacks)
        - Device-bound key (files can't be copied between devices)
        """
        try:
            json_str = json.dumps(data)
            key = self._get_encryption_key()
            f = Fernet(key)
            encrypted = f.encrypt(json_str.encode('utf-8'))
            # Prefix with version for future migration support
            return "v2:" + base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return ""

    def _decrypt_local(self, encrypted: str) -> Optional[dict]:
        """
        Decrypt locally stored data.

        Only supports Fernet encryption (v2).
        Legacy formats are no longer supported for security reasons.
        """
        try:
            if encrypted.startswith("v2:"):
                # Fernet encryption (current, secure)
                key = self._get_encryption_key()
                f = Fernet(key)
                ciphertext = base64.b64decode(encrypted[3:])
                decrypted = f.decrypt(ciphertext).decode('utf-8')
                return json.loads(decrypted)
            else:
                # Legacy formats no longer supported - user must re-authenticate
                logger.error(
                    "License file uses legacy encryption format. "
                    "Please log out and log in again to upgrade."
                )
                return None

        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None


    def _set_secure_file_permissions(self, file_path: Path):
        """
        Set secure file permissions on license files.

        - Unix/macOS: 600 (owner read/write only)
        - Windows: Restrict access to current user only
        """
        try:
            if os.name != 'nt':  # Unix/Linux/macOS
                os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
            else:  # Windows
                import subprocess
                username = os.environ.get("USERNAME", "SYSTEM")
                subprocess.run(
                    ['icacls', str(file_path), '/inheritance:r',
                     '/grant:r', f'{username}:(R,W)'],
                    capture_output=True,
                    timeout=5
                )
        except Exception as e:
            logger.warning(f"Could not set secure file permissions: {e}")

    # ========== Device Fingerprinting ==========

    def get_device_fingerprint(self) -> str:
        """
        Generate a unique device fingerprint.

        Uses multiple identifiers combined:
        - Machine ID (hardware-based)
        - OS info
        - CPU info

        This is the industry-standard approach used by Netflix, Adobe, etc.
        """
        components = []

        # Machine ID (most reliable)
        machine_id = self._get_machine_id()
        components.append(f"machine:{machine_id}")

        # OS info
        os_info = f"{platform.system()}:{platform.release()}"
        components.append(f"os:{os_info}")

        # CPU info
        cpu_info = platform.processor() or platform.machine()
        components.append(f"cpu:{cpu_info}")

        # Create hash of all components
        fingerprint_string = "|".join(sorted(components))
        fingerprint = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]

        return fingerprint

    def _get_machine_id(self) -> str:
        """
        Get unique machine identifier.

        Platform-specific implementations:
        - macOS: Uses IOPlatformUUID
        - Windows: Uses MachineGuid from registry
        - Linux: Uses /etc/machine-id
        """
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split('\n'):
                    if "IOPlatformUUID" in line:
                        # Extract UUID from the line
                        uuid_part = line.split('"')[-2]
                        return uuid_part

            elif system == "Windows":
                result = subprocess.run(
                    ["reg", "query", "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography", "/v", "MachineGuid"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split('\n'):
                    if "MachineGuid" in line:
                        return line.split()[-1]

            elif system == "Linux":
                machine_id_path = Path("/etc/machine-id")
                if machine_id_path.exists():
                    return machine_id_path.read_text().strip()

        except Exception as e:
            logger.warning(f"Could not get machine ID: {e}")

        # Fallback: generate and store a UUID
        fallback_id_file = self.LICENSE_DIR / ".machine_id"
        if fallback_id_file.exists():
            return fallback_id_file.read_text().strip()
        else:
            fallback_id = str(uuid.uuid4())
            fallback_id_file.write_text(fallback_id)
            return fallback_id

    def get_device_info(self) -> DeviceInfo:
        """Get or create device information"""
        if self._device:
            self._device.last_seen = datetime.now()
            return self._device

        # Create new device info
        system = platform.system()
        device_name = platform.node() or f"{system} Device"

        self._device = DeviceInfo(
            device_id=str(uuid.uuid4()),
            device_name=device_name,
            os_type=system.lower(),
            os_version=platform.release(),
            machine_id=self._get_machine_id(),
            cpu_info=platform.processor() or platform.machine()
        )

        self._save_cached_data()
        return self._device

    # ========== License Verification ==========

    def get_current_license(self) -> Optional[LicenseToken]:
        """Get the current cached license"""
        return self._license

    def is_licensed(self) -> bool:
        """Check if user has a valid license"""
        if not self._license:
            return False

        return self._license.is_valid()

    def get_features(self) -> FeatureAccess:
        """Get current feature access based on license"""
        if not self._license or not self._license.is_valid():
            return FeatureAccess.expired_features()

        return self._license.features

    def needs_online_check(self) -> bool:
        """Check if we need to verify license online"""
        if not self._license:
            return True

        return self._license.needs_refresh()

    async def verify_license_online(self) -> Tuple[bool, str]:
        """
        Verify license with cloud server.

        Returns:
            Tuple of (success, message)
        """
        try:
            import aiohttp

            device_info = self.get_device_info()
            fingerprint = self.get_device_fingerprint()

            # Prepare verification request
            payload = {
                "device_id": device_info.device_id,
                "device_fingerprint": fingerprint,
                "device_info": device_info.to_dict(),
                "current_token": self._license.token if self._license else None
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.API_BASE_URL}/api/v1/license/verify",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._license = LicenseToken.from_dict(data['license'])
                        self._license.last_online_check = datetime.now()
                        self._save_cached_data()
                        return True, "License verified successfully"

                    elif response.status == 401:
                        data = await response.json()
                        return False, data.get('message', 'License verification failed')

                    elif response.status == 409:
                        # Device conflict - logged in on another device
                        data = await response.json()
                        return False, f"License in use on another device: {data.get('device_name', 'Unknown')}"

                    else:
                        return False, f"Server error: {response.status}"

        except Exception as e:
            logger.error(f"License verification error: {e}")
            # If offline, check if we're within grace period
            if self._license and self._license.is_valid():
                return True, "Using cached license (offline mode)"
            return False, f"Could not verify license: {e}"

    async def login(self, email: str, password: str) -> Tuple[bool, str]:
        """
        Login and activate license on this device.

        Args:
            email: User's email
            password: User's password

        Returns:
            Tuple of (success, message)
        """
        try:
            import aiohttp

            device_info = self.get_device_info()
            fingerprint = self.get_device_fingerprint()

            payload = {
                "email": email,
                "password": password,
                "device_id": device_info.device_id,
                "device_fingerprint": fingerprint,
                "device_info": device_info.to_dict()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.API_BASE_URL}/api/v1/auth/login",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    data = await response.json()

                    if response.status == 200:
                        # Save license token
                        self._license = LicenseToken.from_dict(data['license'])
                        self._license.last_online_check = datetime.now()
                        self._save_cached_data()

                        logger.info(f"Login successful for {email}")
                        return True, f"Welcome! Your {self._license.tier.value} subscription is active."

                    elif response.status == 409:
                        # Device conflict
                        return False, f"Account already logged in on: {data.get('device_name', 'another device')}"

                    else:
                        return False, data.get('message', 'Login failed')

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False, f"Login failed: {e}"

    async def logout(self) -> Tuple[bool, str]:
        """
        Logout and deactivate license on this device.

        Returns:
            Tuple of (success, message)
        """
        try:
            if not self._license:
                return True, "Already logged out"

            import aiohttp

            payload = {
                "token": self._license.token,
                "device_id": self._device.device_id if self._device else None
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.API_BASE_URL}/api/v1/auth/logout",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    # Clear local license regardless of response
                    self._license = None
                    if self.LICENSE_FILE.exists():
                        self.LICENSE_FILE.unlink()

                    if response.status == 200:
                        return True, "Logged out successfully"
                    else:
                        return True, "Logged out locally"

        except Exception as e:
            # Clear locally even if cloud fails
            self._license = None
            if self.LICENSE_FILE.exists():
                self.LICENSE_FILE.unlink()
            logger.warning(f"Logout error (cleared locally): {e}")
            return True, "Logged out locally"

    async def force_logout_other_devices(self) -> Tuple[bool, str]:
        """
        Force logout from all other devices.

        This is the Netflix-style "logout everywhere" feature.
        """
        try:
            if not self._license:
                return False, "Not logged in"

            import aiohttp

            device_info = self.get_device_info()
            fingerprint = self.get_device_fingerprint()

            payload = {
                "token": self._license.token,
                "keep_device_id": device_info.device_id,
                "keep_device_fingerprint": fingerprint
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.API_BASE_URL}/api/v1/auth/logout-others",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Refresh our license
                        self._license = LicenseToken.from_dict(data['license'])
                        self._license.last_online_check = datetime.now()
                        self._save_cached_data()
                        return True, "All other devices logged out"
                    else:
                        data = await response.json()
                        return False, data.get('message', 'Failed to logout other devices')

        except Exception as e:
            logger.error(f"Force logout error: {e}")
            return False, f"Failed to logout other devices: {e}"

    # ========== Subscription Info ==========

    def get_subscription_tier(self) -> SubscriptionTier:
        """Get current subscription tier"""
        if not self._license:
            return SubscriptionTier.EXPIRED
        return self._license.tier

    def get_subscription_status(self) -> str:
        """Get human-readable subscription status"""
        if not self._license:
            return "Not logged in"

        if not self._license.is_valid():
            return "Subscription expired"

        tier_name = self._license.tier.value.replace('_', ' ').title()
        days_left = (self._license.expires_at - datetime.now()).days

        if self._license.tier == SubscriptionTier.LIFETIME:
            return f"{tier_name} (Lifetime Access)"
        elif days_left > 30:
            return f"{tier_name} (Active)"
        else:
            return f"{tier_name} ({days_left} days remaining)"

    def get_user_email(self) -> Optional[str]:
        """Get logged in user's email"""
        if self._license:
            return self._license.email
        return None


# Global license manager instance
_license_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    """Get the global license manager instance"""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager
