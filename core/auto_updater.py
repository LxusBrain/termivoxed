"""
Auto-Update System for TermiVoxed Desktop Application

Provides secure automatic updates with:
- Version checking against remote manifest
- Secure download with signature verification
- Differential updates when possible
- Rollback capability on failure
- Enterprise scheduling support
"""

import os
import sys
import json
import hashlib
import hmac
import shutil
import tempfile
import subprocess
import platform
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import time

from utils.logger import logger

# Ed25519 signature verification
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    logger.warning("cryptography library not available - update signature verification disabled")


# TermiVoxed Update Signing Public Key (Ed25519)
# This is the public key used to verify update signatures.
# The corresponding private key should be kept secure and used only for signing releases.
# To generate a new keypair, run: python build_tools/generate_update_keys.py
#
# CRITICAL: The public key MUST be set via environment variable for production!
# There is NO fallback - updates will fail if not configured.
UPDATE_SIGNING_PUBLIC_KEY_B64 = os.environ.get("TERMIVOXED_UPDATE_PUBLIC_KEY", "")


def _load_update_public_key() -> Optional[Ed25519PublicKey]:
    """Load the Ed25519 public key for update verification."""
    if not HAS_CRYPTOGRAPHY:
        logger.error("cryptography library required for update verification")
        return None

    if not UPDATE_SIGNING_PUBLIC_KEY_B64 or UPDATE_SIGNING_PUBLIC_KEY_B64 == "REPLACE_WITH_YOUR_ED25519_PUBLIC_KEY_BASE64":
        logger.error(
            "CRITICAL: TERMIVOXED_UPDATE_PUBLIC_KEY environment variable not set! "
            "Auto-updates are DISABLED. Generate keys with: python build_tools/generate_update_keys.py"
        )
        return None

    try:
        public_key_bytes = base64.b64decode(UPDATE_SIGNING_PUBLIC_KEY_B64)
        if len(public_key_bytes) != 32:
            logger.error(f"Invalid public key length: {len(public_key_bytes)} (expected 32)")
            return None
        logger.info("Update signing public key loaded successfully")
        return Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except Exception as e:
        logger.error(f"Failed to load update public key: {e}")
        return None


# Load the public key at module load time
_UPDATE_PUBLIC_KEY = _load_update_public_key()


class UpdateChannel(str, Enum):
    """Update channels"""
    STABLE = "stable"
    BETA = "beta"
    ALPHA = "alpha"


class UpdateStatus(str, Enum):
    """Update status"""
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    INSTALLING = "installing"
    INSTALLED = "installed"
    FAILED = "failed"
    ROLLBACK = "rollback"


@dataclass
class UpdateInfo:
    """Information about an available update"""
    version: str
    channel: UpdateChannel
    release_date: datetime
    download_url: str
    download_size: int
    checksum_sha256: str
    signature: str
    release_notes: str
    min_version: Optional[str] = None
    is_critical: bool = False
    requires_restart: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateInfo":
        return cls(
            version=data["version"],
            channel=UpdateChannel(data.get("channel", "stable")),
            release_date=datetime.fromisoformat(data["release_date"]),
            download_url=data["download_url"],
            download_size=data["download_size"],
            checksum_sha256=data["checksum_sha256"],
            signature=data["signature"],
            release_notes=data.get("release_notes", ""),
            min_version=data.get("min_version"),
            is_critical=data.get("is_critical", False),
            requires_restart=data.get("requires_restart", True),
        )


@dataclass
class UpdateProgress:
    """Progress of update download/installation"""
    status: UpdateStatus
    percent: float = 0.0
    bytes_downloaded: int = 0
    total_bytes: int = 0
    message: str = ""
    error: Optional[str] = None


class UpdateManifest:
    """
    Handles fetching and parsing update manifests.

    Manifest format:
    {
        "latest": {
            "stable": "1.2.3",
            "beta": "1.3.0-beta.1"
        },
        "versions": {
            "1.2.3": {
                "version": "1.2.3",
                "channel": "stable",
                "release_date": "2025-01-15T00:00:00Z",
                "download_url": "https://...",
                "download_size": 123456789,
                "checksum_sha256": "abc123...",
                "signature": "...",
                "release_notes": "...",
                "platforms": {
                    "windows": { ... },
                    "darwin": { ... },
                    "linux": { ... }
                }
            }
        }
    }
    """

    def __init__(
        self,
        manifest_url: str,
        public_key: Optional[bytes] = None
    ):
        self.manifest_url = manifest_url
        self.public_key = public_key
        self._cached_manifest: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(hours=1)

    async def fetch(self, force: bool = False) -> Dict[str, Any]:
        """Fetch the update manifest"""
        # Return cached if available and not forced
        if not force and self._cached_manifest and self._cache_time:
            if datetime.now() - self._cache_time < self._cache_duration:
                return self._cached_manifest

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.manifest_url,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to fetch manifest: {response.status}")

                    data = await response.json()

                    # Verify manifest signature if public key is provided
                    if self.public_key:
                        if not self._verify_manifest(data):
                            raise Exception("Manifest signature verification failed")

                    self._cached_manifest = data
                    self._cache_time = datetime.now()
                    return data

        except Exception as e:
            logger.error(f"Failed to fetch update manifest: {e}")
            raise

    def _verify_manifest(self, data: Dict[str, Any]) -> bool:
        """
        Verify manifest signature using Ed25519.

        The manifest should contain a 'signature' field with a base64-encoded
        Ed25519 signature of the canonical JSON representation of the manifest
        (excluding the signature field itself).

        Args:
            data: The manifest dict, including the 'signature' field

        Returns:
            True if signature is valid, False otherwise
        """
        if not HAS_CRYPTOGRAPHY:
            logger.error("Cryptography library not available - cannot verify manifest")
            return False

        if _UPDATE_PUBLIC_KEY is None:
            logger.error("Update public key not configured - cannot verify manifest")
            return False

        # Extract and remove signature for verification
        signature_b64 = data.get("signature")
        if not signature_b64:
            logger.error("Manifest has no signature field")
            return False

        try:
            # Decode signature
            try:
                signature_bytes = base64.b64decode(signature_b64)
            except Exception as e:
                logger.error(f"Invalid manifest signature encoding: {e}")
                return False

            if len(signature_bytes) != 64:
                logger.error(f"Invalid manifest signature length: {len(signature_bytes)}")
                return False

            # Create a copy without the signature for verification
            data_to_verify = {k: v for k, v in data.items() if k != "signature"}

            # Create canonical JSON representation (sorted keys, no extra whitespace)
            canonical_json = json.dumps(data_to_verify, sort_keys=True, separators=(",", ":"))
            message_bytes = canonical_json.encode("utf-8")

            # Verify the signature
            try:
                _UPDATE_PUBLIC_KEY.verify(signature_bytes, message_bytes)
                logger.info("Manifest signature verified successfully")
                return True
            except InvalidSignature:
                logger.error("Manifest signature verification FAILED")
                return False

        except Exception as e:
            logger.error(f"Manifest verification error: {e}")
            return False

    def get_latest_version(
        self,
        channel: UpdateChannel = UpdateChannel.STABLE
    ) -> Optional[str]:
        """Get the latest version for a channel"""
        if not self._cached_manifest:
            return None
        return self._cached_manifest.get("latest", {}).get(channel.value)

    def get_update_info(
        self,
        version: str,
        platform_name: Optional[str] = None
    ) -> Optional[UpdateInfo]:
        """Get update info for a specific version"""
        if not self._cached_manifest:
            return None

        versions = self._cached_manifest.get("versions", {})
        version_data = versions.get(version)

        if not version_data:
            return None

        # Get platform-specific data
        platform_name = platform_name or platform.system().lower()
        platforms = version_data.get("platforms", {})

        if platform_name in platforms:
            platform_data = platforms[platform_name]
            # Merge platform-specific data
            version_data = {**version_data, **platform_data}

        return UpdateInfo.from_dict(version_data)


class AutoUpdater:
    """
    Main auto-update manager.

    Handles checking for updates, downloading, verifying,
    and installing updates with rollback capability.
    """

    # Update server configuration
    DEFAULT_MANIFEST_URL = "https://updates.termivoxed.com/manifest.json"

    def __init__(
        self,
        current_version: str,
        app_dir: Path,
        channel: UpdateChannel = UpdateChannel.STABLE,
        manifest_url: Optional[str] = None,
        check_interval: int = 3600,  # 1 hour
        auto_download: bool = True,
        auto_install: bool = False,
    ):
        self.current_version = current_version
        self.app_dir = Path(app_dir)
        self.channel = channel
        self.check_interval = check_interval
        self.auto_download = auto_download
        self.auto_install = auto_install

        # Initialize manifest
        self.manifest = UpdateManifest(manifest_url or self.DEFAULT_MANIFEST_URL)

        # Update state
        self._status = UpdateStatus.UP_TO_DATE
        self._progress = UpdateProgress(status=UpdateStatus.UP_TO_DATE)
        self._available_update: Optional[UpdateInfo] = None
        self._downloaded_file: Optional[Path] = None

        # Paths
        self.updates_dir = self.app_dir / "updates"
        self.backup_dir = self.app_dir / "backup"
        self.updates_dir.mkdir(parents=True, exist_ok=True)

        # Background check
        self._check_thread: Optional[threading.Thread] = None
        self._running = False

        # Callbacks
        self._on_update_available: Optional[Callable[[UpdateInfo], None]] = None
        self._on_progress: Optional[Callable[[UpdateProgress], None]] = None

        logger.info(f"AutoUpdater initialized: v{current_version}, channel={channel.value}")

    @property
    def status(self) -> UpdateStatus:
        return self._status

    @property
    def progress(self) -> UpdateProgress:
        return self._progress

    @property
    def available_update(self) -> Optional[UpdateInfo]:
        return self._available_update

    def set_callback(
        self,
        on_update_available: Optional[Callable[[UpdateInfo], None]] = None,
        on_progress: Optional[Callable[[UpdateProgress], None]] = None
    ):
        """Set callbacks for update events"""
        self._on_update_available = on_update_available
        self._on_progress = on_progress

    def _update_progress(
        self,
        status: UpdateStatus,
        percent: float = 0.0,
        message: str = "",
        error: Optional[str] = None
    ):
        """Update progress and notify callback"""
        self._status = status
        self._progress = UpdateProgress(
            status=status,
            percent=percent,
            message=message,
            error=error,
            bytes_downloaded=self._progress.bytes_downloaded,
            total_bytes=self._progress.total_bytes,
        )

        if self._on_progress:
            try:
                self._on_progress(self._progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    async def check_for_updates(self) -> Optional[UpdateInfo]:
        """
        Check for available updates.

        Returns UpdateInfo if an update is available, None otherwise.
        """
        try:
            self._update_progress(UpdateStatus.UP_TO_DATE, 0, "Checking for updates...")

            # Fetch manifest
            await self.manifest.fetch()

            # Get latest version for our channel
            latest_version = self.manifest.get_latest_version(self.channel)

            if not latest_version:
                logger.info("No updates available")
                return None

            # Compare versions
            if not self._is_newer_version(latest_version, self.current_version):
                logger.info(f"Already up to date: v{self.current_version}")
                return None

            # Get update info
            update_info = self.manifest.get_update_info(latest_version)

            if not update_info:
                logger.warning(f"Update info not found for v{latest_version}")
                return None

            # Check minimum version requirement
            if update_info.min_version:
                if not self._is_newer_version(self.current_version, update_info.min_version):
                    logger.warning(
                        f"Current version {self.current_version} is below "
                        f"minimum required {update_info.min_version}"
                    )
                    # Could require a full reinstall

            self._available_update = update_info
            self._update_progress(
                UpdateStatus.UPDATE_AVAILABLE,
                0,
                f"Update available: v{latest_version}"
            )

            # Notify callback
            if self._on_update_available:
                try:
                    self._on_update_available(update_info)
                except Exception as e:
                    logger.error(f"Update available callback error: {e}")

            logger.info(f"Update available: v{latest_version}")
            return update_info

        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            self._update_progress(UpdateStatus.FAILED, 0, error=str(e))
            return None

    def _is_newer_version(self, version1: str, version2: str) -> bool:
        """Check if version1 is newer than version2"""
        def parse_version(v: str) -> Tuple:
            # Handle versions like "1.2.3" or "1.2.3-beta.1"
            parts = v.split("-")
            main_parts = tuple(int(x) for x in parts[0].split("."))
            pre_release = parts[1] if len(parts) > 1 else None
            return main_parts, pre_release

        v1 = parse_version(version1)
        v2 = parse_version(version2)

        # Compare main version first
        if v1[0] != v2[0]:
            return v1[0] > v2[0]

        # If main versions are equal, release > pre-release
        if v1[1] is None and v2[1] is not None:
            return True
        if v1[1] is not None and v2[1] is None:
            return False

        # Both are pre-release or both are release
        return v1 > v2

    async def download_update(self) -> bool:
        """
        Download the available update.

        Returns True if download succeeded.
        """
        if not self._available_update:
            logger.warning("No update available to download")
            return False

        update = self._available_update
        self._update_progress(UpdateStatus.DOWNLOADING, 0, "Preparing download...")

        try:
            import aiohttp
            import aiofiles

            # Prepare download path
            filename = f"termivoxed-{update.version}-{platform.system().lower()}.update"
            download_path = self.updates_dir / filename

            # Download with progress
            async with aiohttp.ClientSession() as session:
                async with session.get(update.download_url) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed: HTTP {response.status}")

                    total_size = int(response.headers.get("content-length", 0))
                    self._progress.total_bytes = total_size

                    downloaded = 0
                    hasher = hashlib.sha256()

                    async with aiofiles.open(download_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                            hasher.update(chunk)
                            downloaded += len(chunk)

                            self._progress.bytes_downloaded = downloaded
                            percent = (downloaded / total_size * 100) if total_size else 0
                            self._update_progress(
                                UpdateStatus.DOWNLOADING,
                                percent,
                                f"Downloading... {downloaded // 1024 // 1024}MB / {total_size // 1024 // 1024}MB"
                            )

            # Verify checksum
            actual_checksum = hasher.hexdigest()
            if actual_checksum != update.checksum_sha256:
                download_path.unlink()
                raise Exception(
                    f"Checksum mismatch: expected {update.checksum_sha256}, "
                    f"got {actual_checksum}"
                )

            # Verify signature
            if not self._verify_signature(download_path, update.signature):
                download_path.unlink()
                raise Exception("Signature verification failed")

            self._downloaded_file = download_path
            self._update_progress(
                UpdateStatus.DOWNLOADED,
                100,
                f"Download complete: v{update.version}"
            )

            logger.info(f"Update downloaded: {download_path}")
            return True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            self._update_progress(UpdateStatus.FAILED, 0, error=str(e))
            return False

    def _verify_signature(self, file_path: Path, signature: str) -> bool:
        """
        Verify file signature using Ed25519.

        Args:
            file_path: Path to the downloaded update file
            signature: Base64-encoded Ed25519 signature of the file's SHA256 hash

        Returns:
            True if signature is valid, False otherwise
        """
        if not HAS_CRYPTOGRAPHY:
            logger.error("Cryptography library not available - cannot verify signature")
            return False

        if _UPDATE_PUBLIC_KEY is None:
            logger.error("Update public key not configured - cannot verify signature")
            return False

        try:
            # Decode the signature from base64
            try:
                signature_bytes = base64.b64decode(signature)
            except Exception as e:
                logger.error(f"Invalid signature encoding: {e}")
                return False

            # Ed25519 signatures are always 64 bytes
            if len(signature_bytes) != 64:
                logger.error(f"Invalid signature length: {len(signature_bytes)} (expected 64)")
                return False

            # Read the file and compute its SHA256 hash
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            file_hash = hasher.digest()

            # Verify the signature against the file hash
            # Ed25519 signs the message directly (the hash in this case)
            try:
                _UPDATE_PUBLIC_KEY.verify(signature_bytes, file_hash)
                logger.info(f"Signature verified successfully for {file_path.name}")
                return True
            except InvalidSignature:
                logger.error(f"Signature verification FAILED for {file_path.name}")
                return False

        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    async def install_update(self, restart: bool = True) -> bool:
        """
        Install the downloaded update.

        Args:
            restart: Whether to restart the application after install

        Returns True if installation succeeded.
        """
        if not self._downloaded_file or not self._downloaded_file.exists():
            logger.warning("No downloaded update to install")
            return False

        self._update_progress(UpdateStatus.INSTALLING, 0, "Preparing installation...")

        try:
            # Create backup
            if not self._create_backup():
                raise Exception("Failed to create backup")

            self._update_progress(UpdateStatus.INSTALLING, 25, "Extracting update...")

            # Extract update
            extract_dir = self.updates_dir / "extract"
            extract_dir.mkdir(exist_ok=True)

            # Use appropriate extraction method based on file type
            if self._downloaded_file.suffix in (".zip", ".update"):
                import zipfile
                with zipfile.ZipFile(self._downloaded_file, "r") as zf:
                    zf.extractall(extract_dir)
            elif self._downloaded_file.suffix in (".tar", ".gz", ".tgz"):
                import tarfile
                with tarfile.open(self._downloaded_file, "r:*") as tf:
                    tf.extractall(extract_dir)

            self._update_progress(UpdateStatus.INSTALLING, 50, "Applying update...")

            # Apply update
            self._apply_update(extract_dir)

            self._update_progress(UpdateStatus.INSTALLING, 75, "Cleaning up...")

            # Cleanup
            shutil.rmtree(extract_dir)
            self._downloaded_file.unlink()

            self._update_progress(UpdateStatus.INSTALLED, 100, "Update installed successfully")
            logger.info("Update installed successfully")

            # Restart if requested
            if restart and self._available_update and self._available_update.requires_restart:
                self._restart_application()

            return True

        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self._update_progress(UpdateStatus.FAILED, 0, error=str(e))

            # Attempt rollback
            if self.backup_dir.exists():
                self._rollback()

            return False

    def _create_backup(self) -> bool:
        """Create backup of current installation"""
        try:
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)

            # Backup critical files
            self.backup_dir.mkdir(parents=True)
            backup_manifest = {
                "version": self.current_version,
                "timestamp": datetime.now().isoformat(),
                "files": []
            }

            # List files to backup (customize based on your app structure)
            critical_files = [
                "main.py",
                "config.py",
                # Add other critical files
            ]

            for filename in critical_files:
                src = self.app_dir / filename
                if src.exists():
                    dst = self.backup_dir / filename
                    shutil.copy2(src, dst)
                    backup_manifest["files"].append(filename)

            # Save manifest
            (self.backup_dir / "manifest.json").write_text(
                json.dumps(backup_manifest, indent=2)
            )

            logger.info(f"Backup created: {self.backup_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False

    def _apply_update(self, extract_dir: Path) -> None:
        """Apply extracted update files with path traversal protection"""
        # Resolve the app directory to an absolute path for comparison
        app_dir_resolved = self.app_dir.resolve()

        for item in extract_dir.iterdir():
            # SECURITY: Validate file name to prevent path traversal attacks
            # Reject any names containing '..' or starting with '/'
            if '..' in item.name or item.name.startswith('/') or item.name.startswith('\\'):
                logger.error(f"SECURITY: Invalid path in update package: {item.name}")
                raise ValueError(f"Invalid path in update: {item.name}")

            # Construct the destination path
            dst = self.app_dir / item.name

            # SECURITY: Verify the resolved destination is within app_dir
            # This prevents attacks using symbolic links or complex path manipulation
            try:
                dst_resolved = dst.resolve()
                # Ensure destination is within app directory
                if not str(dst_resolved).startswith(str(app_dir_resolved)):
                    logger.error(f"SECURITY: Path traversal attempt detected: {item.name} -> {dst_resolved}")
                    raise ValueError(f"Path traversal attempt: {item.name}")
            except (OSError, ValueError) as e:
                logger.error(f"SECURITY: Invalid destination path: {e}")
                raise ValueError(f"Invalid path in update: {item.name}")

            # Safe to proceed with copy
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)

    def _rollback(self) -> bool:
        """Rollback to backup version"""
        try:
            self._update_progress(UpdateStatus.ROLLBACK, 0, "Rolling back...")

            manifest_path = self.backup_dir / "manifest.json"
            if not manifest_path.exists():
                logger.error("Backup manifest not found")
                return False

            manifest = json.loads(manifest_path.read_text())

            for filename in manifest["files"]:
                src = self.backup_dir / filename
                dst = self.app_dir / filename
                if src.exists():
                    shutil.copy2(src, dst)

            logger.info(f"Rolled back to v{manifest['version']}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def _restart_application(self) -> None:
        """Restart the application"""
        logger.info("Restarting application...")

        # Get the executable path
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            executable = sys.executable
        else:
            # Running as script
            executable = sys.executable
            args = [executable] + sys.argv
            subprocess.Popen(args)
            sys.exit(0)

    def start_background_check(self) -> None:
        """Start background update checking"""
        if self._running:
            return

        self._running = True
        self._check_thread = threading.Thread(
            target=self._background_check_loop,
            daemon=True
        )
        self._check_thread.start()
        logger.info("Background update checking started")

    def stop_background_check(self) -> None:
        """Stop background update checking"""
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5)
        logger.info("Background update checking stopped")

    def _background_check_loop(self) -> None:
        """Background loop for checking updates"""
        import asyncio

        while self._running:
            try:
                # Run async check in a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    update = loop.run_until_complete(self.check_for_updates())

                    if update and self.auto_download:
                        loop.run_until_complete(self.download_update())

                        if self.auto_install and self._downloaded_file:
                            loop.run_until_complete(self.install_update())

                finally:
                    loop.close()

            except Exception as e:
                logger.error(f"Background update check failed: {e}")

            # Wait for next check
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)


# Singleton instance
_auto_updater: Optional[AutoUpdater] = None


def get_auto_updater(
    current_version: Optional[str] = None,
    app_dir: Optional[Path] = None,
    **kwargs
) -> AutoUpdater:
    """Get or create the auto updater singleton"""
    global _auto_updater

    if _auto_updater is None:
        if current_version is None or app_dir is None:
            raise ValueError("Must provide current_version and app_dir on first call")
        _auto_updater = AutoUpdater(current_version, app_dir, **kwargs)

    return _auto_updater
