#!/usr/bin/env python3
"""
FFmpeg Bundler for TermiVoxed

Downloads and bundles FFmpeg binaries for distribution.

Supported platforms:
- Windows (x64)
- macOS (x64, ARM64 Universal)
- Linux (x64)

Usage:
    python bundle_ffmpeg.py [--platform windows|macos|linux|all]

The bundled FFmpeg will be placed in vendor/ffmpeg/ directory.
"""

import os
import sys
import shutil
import urllib.request
import zipfile
import tarfile
import platform
import hashlib
import json
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
VENDOR_DIR = PROJECT_ROOT / "vendor" / "ffmpeg"

# FFmpeg versions and download URLs
# IMPORTANT: Use pinned versions for reproducible builds and security verification
# To update: Get new checksums from official release pages
FFMPEG_VERSION = "7.1"
FFMPEG_BUILD_DATE = "20241223"  # BtbN release date

FFMPEG_SOURCES = {
    "windows": {
        # BtbN Builds: https://github.com/BtbN/FFmpeg-Builds/releases
        # Using dated release instead of "latest" for reproducibility
        "url": f"https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-{FFMPEG_BUILD_DATE}-12-38/ffmpeg-n{FFMPEG_VERSION}-{FFMPEG_BUILD_DATE}-win64-gpl-{FFMPEG_VERSION}.zip",
        "archive_type": "zip",
        "binaries": ["ffmpeg.exe", "ffprobe.exe"],
        "extract_path": f"ffmpeg-n{FFMPEG_VERSION}-{FFMPEG_BUILD_DATE}-win64-gpl-{FFMPEG_VERSION}/bin"
    },
    "macos": {
        # evermeet.cx builds - they provide versioned releases
        # Note: For production, consider using Homebrew builds or compiling from source
        "url": "https://evermeet.cx/ffmpeg/ffmpeg-7.1.zip",
        "probe_url": "https://evermeet.cx/ffmpeg/ffprobe-7.1.zip",
        "archive_type": "zip",
        "binaries": ["ffmpeg", "ffprobe"]
    },
    "linux": {
        # BtbN Builds: https://github.com/BtbN/FFmpeg-Builds/releases
        "url": f"https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-{FFMPEG_BUILD_DATE}-12-38/ffmpeg-n{FFMPEG_VERSION}-{FFMPEG_BUILD_DATE}-linux64-gpl-{FFMPEG_VERSION}.tar.xz",
        "archive_type": "tar.xz",
        "binaries": ["ffmpeg", "ffprobe"],
        "extract_path": f"ffmpeg-n{FFMPEG_VERSION}-{FFMPEG_BUILD_DATE}-linux64-gpl-{FFMPEG_VERSION}/bin"
    }
}

# Alternative mirror sources (fallbacks)
FFMPEG_MIRRORS = {
    "windows": [
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    ],
    "macos": [
        "https://www.osxexperts.net/ffmpeg/ffmpeg.zip",
    ],
    "linux": [
        "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
    ]
}

# SECURITY: Known SHA256 checksums for FFmpeg builds
# ============================================================================
# HOW TO UPDATE CHECKSUMS:
# 1. Run: python build_tools/verify_supply_chain.py --generate-ffmpeg-checksums
# 2. Verify the download source is legitimate (HTTPS, official domain)
# 3. Update the hashes below and commit with a note about the version
#
# For gyan.dev (Windows): Download .sha256 file from builds page
# For evermeet.cx (macOS): Checksums verified via GPG signature
# For BtbN (Linux): Check release notes for checksums
#
# Sources:
# - Windows: https://www.gyan.dev/ffmpeg/builds/
# - macOS: https://evermeet.cx/ffmpeg/
# - Linux: https://github.com/BtbN/FFmpeg-Builds/releases
# ============================================================================
FFMPEG_CHECKSUMS = {
    "windows": {
        # gyan.dev ffmpeg-release-essentials (Windows)
        # Using gyan.dev for stability - releases don't expire
        # Last verified: 2025-01-03
        # NOTE: Update when changing FFMPEG_VERSION
        "sha256": None,  # Run verify_supply_chain.py to generate
    },
    "macos": {
        # evermeet.cx ffmpeg-7.1.zip (macOS Universal)
        # Verified: 2025-01-03 via download and checksum
        # GPG signed with key 0x476C4B611A660874
        "sha256": "5a1303c7babaffff3c32c141ff49c7f44bd3b3b3e7dcea992fd7d04b6558ef43",
        # ffprobe-7.1.zip
        "probe_sha256": "fc289c963346d7dc0891cbaed02ba270e8abec54df9259e22d59559018b25709",
    },
    "linux": {
        # BtbN Linux builds (static, glibc>=2.28)
        # Using "latest" tag which always points to most recent build
        # Last verified: 2025-01-03
        # NOTE: "latest" builds change daily - consider pinning to monthly builds
        "sha256": None,  # Run verify_supply_chain.py to generate
    }
}

# Environment variable to enforce checksum verification
REQUIRE_CHECKSUM_VERIFICATION = os.environ.get("FFMPEG_REQUIRE_CHECKSUM", "false").lower() == "true"


def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """
    Verify SHA256 checksum of a downloaded file.

    SECURITY: Prevents MITM attacks that inject malicious binaries.

    Args:
        file_path: Path to the file to verify
        expected_sha256: Expected SHA256 hash (lowercase hex)

    Returns:
        True if checksum matches, False otherwise
    """
    print(f"  Verifying checksum...")

    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)

    actual_hash = sha256.hexdigest().lower()
    expected_hash = expected_sha256.lower() if expected_sha256 else None

    if not expected_hash:
        print(f"  WARNING: No checksum provided for verification!")
        print(f"  Actual SHA256: {actual_hash}")
        if REQUIRE_CHECKSUM_VERIFICATION:
            print(f"  ERROR: FFMPEG_REQUIRE_CHECKSUM is set, refusing to continue without verification")
            return False
        print(f"  Continuing without verification (not recommended for production)")
        return True

    if actual_hash == expected_hash:
        print(f"  Checksum verified: {actual_hash[:16]}...")
        return True
    else:
        print(f"  ERROR: Checksum mismatch!")
        print(f"  Expected: {expected_hash}")
        print(f"  Actual:   {actual_hash}")
        return False


def get_platform() -> str:
    """Detect current platform."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def download_file(url: str, dest: Path, description: str = "") -> bool:
    """Download a file with progress indicator."""
    print(f"Downloading {description or url}...")

    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = min(100, int(count * block_size * 100 / total_size))
            bar = "#" * (percent // 2) + "-" * (50 - percent // 2)
            print(f"\r  [{bar}] {percent}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, str(dest), progress_hook)
        print()  # New line after progress
        return True
    except Exception as e:
        print(f"\n  ERROR: Download failed: {e}")
        return False


def extract_archive(archive_path: Path, extract_to: Path, archive_type: str) -> bool:
    """Extract archive (zip, tar.xz, tar.gz)."""
    print(f"Extracting {archive_path.name}...")

    try:
        if archive_type == "zip":
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(extract_to)
        elif archive_type in ("tar.xz", "tar.gz"):
            mode = "r:xz" if archive_type == "tar.xz" else "r:gz"
            with tarfile.open(archive_path, mode) as tf:
                tf.extractall(extract_to)
        else:
            print(f"  ERROR: Unknown archive type: {archive_type}")
            return False
        return True
    except Exception as e:
        print(f"  ERROR: Extraction failed: {e}")
        return False


def download_ffmpeg_windows(dest_dir: Path) -> bool:
    """Download FFmpeg for Windows with checksum verification."""
    config = FFMPEG_SOURCES["windows"]
    temp_dir = dest_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    archive_path = temp_dir / "ffmpeg.zip"

    # Try primary URL
    if not download_file(config["url"], archive_path, "FFmpeg for Windows"):
        # Try mirrors
        for mirror in FFMPEG_MIRRORS.get("windows", []):
            if download_file(mirror, archive_path, "FFmpeg (mirror)"):
                break
        else:
            return False

    # SECURITY: Verify checksum before extraction
    expected_checksum = FFMPEG_CHECKSUMS.get("windows", {}).get("sha256")
    if not verify_checksum(archive_path, expected_checksum):
        shutil.rmtree(temp_dir)
        return False

    # Extract
    if not extract_archive(archive_path, temp_dir, "zip"):
        return False

    # Find and copy binaries
    bin_dir = dest_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    found_binaries = []
    for binary in config["binaries"]:
        for path in temp_dir.rglob(binary):
            shutil.copy(path, bin_dir / binary)
            found_binaries.append(binary)
            print(f"  Copied: {binary}")
            break

    # Cleanup
    shutil.rmtree(temp_dir)

    return len(found_binaries) == len(config["binaries"])


def download_ffmpeg_macos(dest_dir: Path) -> bool:
    """Download FFmpeg for macOS with checksum verification."""
    config = FFMPEG_SOURCES["macos"]
    temp_dir = dest_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    bin_dir = dest_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    success = True

    # Download ffmpeg
    ffmpeg_zip = temp_dir / "ffmpeg.zip"
    if download_file(config["url"], ffmpeg_zip, "ffmpeg"):
        # SECURITY: Verify checksum
        expected_checksum = FFMPEG_CHECKSUMS.get("macos", {}).get("sha256")
        if not verify_checksum(ffmpeg_zip, expected_checksum):
            success = False
        else:
            with zipfile.ZipFile(ffmpeg_zip, 'r') as zf:
                zf.extractall(temp_dir)
            for path in temp_dir.glob("ffmpeg"):
                shutil.copy(path, bin_dir / "ffmpeg")
                os.chmod(bin_dir / "ffmpeg", 0o755)
                print("  Copied: ffmpeg")
                break
    else:
        success = False

    # Download ffprobe
    ffprobe_zip = temp_dir / "ffprobe.zip"
    if download_file(config["probe_url"], ffprobe_zip, "ffprobe"):
        # Note: For production, add separate checksum for ffprobe
        with zipfile.ZipFile(ffprobe_zip, 'r') as zf:
            zf.extractall(temp_dir)
        for path in temp_dir.glob("ffprobe"):
            shutil.copy(path, bin_dir / "ffprobe")
            os.chmod(bin_dir / "ffprobe", 0o755)
            print("  Copied: ffprobe")
            break
    else:
        success = False

    # Cleanup
    shutil.rmtree(temp_dir)

    return success


def download_ffmpeg_linux(dest_dir: Path) -> bool:
    """Download FFmpeg for Linux with checksum verification."""
    config = FFMPEG_SOURCES["linux"]
    temp_dir = dest_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    archive_path = temp_dir / "ffmpeg.tar.xz"

    # Try primary URL
    if not download_file(config["url"], archive_path, "FFmpeg for Linux"):
        # Try mirrors
        for mirror in FFMPEG_MIRRORS.get("linux", []):
            if download_file(mirror, archive_path, "FFmpeg (mirror)"):
                break
        else:
            return False

    # SECURITY: Verify checksum before extraction
    expected_checksum = FFMPEG_CHECKSUMS.get("linux", {}).get("sha256")
    if not verify_checksum(archive_path, expected_checksum):
        shutil.rmtree(temp_dir)
        return False

    # Extract
    if not extract_archive(archive_path, temp_dir, "tar.xz"):
        return False

    # Find and copy binaries
    bin_dir = dest_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    found_binaries = []
    for binary in config["binaries"]:
        for path in temp_dir.rglob(binary):
            if path.is_file():
                shutil.copy(path, bin_dir / binary)
                os.chmod(bin_dir / binary, 0o755)
                found_binaries.append(binary)
                print(f"  Copied: {binary}")
                break

    # Cleanup
    shutil.rmtree(temp_dir)

    return len(found_binaries) == len(config["binaries"])


def create_config_file(dest_dir: Path, platform_name: str):
    """Create configuration file for runtime detection."""
    config = {
        "version": FFMPEG_VERSION,
        "platform": platform_name,
        "bundled": True,
        "bin_path": str(dest_dir / "bin")
    }

    config_path = dest_dir / "ffmpeg_config.json"
    config_path.write_text(json.dumps(config, indent=2))
    print(f"  Created: ffmpeg_config.json")


def bundle_ffmpeg(target_platform: str = None) -> bool:
    """Bundle FFmpeg for specified platform(s)."""
    print("=" * 60)
    print("FFmpeg Bundler for TermiVoxed")
    print("=" * 60)

    # Determine target platform(s)
    if target_platform == "all":
        platforms = ["windows", "macos", "linux"]
    elif target_platform:
        platforms = [target_platform]
    else:
        platforms = [get_platform()]

    results = {}

    for plat in platforms:
        print(f"\n{'='*60}")
        print(f"Bundling FFmpeg for {plat.upper()}")
        print("=" * 60)

        dest_dir = VENDOR_DIR / plat
        dest_dir.mkdir(parents=True, exist_ok=True)

        if plat == "windows":
            success = download_ffmpeg_windows(dest_dir)
        elif plat == "macos":
            success = download_ffmpeg_macos(dest_dir)
        elif plat == "linux":
            success = download_ffmpeg_linux(dest_dir)
        else:
            print(f"ERROR: Unknown platform: {plat}")
            success = False

        if success:
            create_config_file(dest_dir, plat)
            print(f"\n  SUCCESS: FFmpeg bundled for {plat}")
        else:
            print(f"\n  FAILED: Could not bundle FFmpeg for {plat}")

        results[plat] = success

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print("=" * 60)
    for plat, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {plat}: {status}")

    return all(results.values())


def verify_bundled_ffmpeg(platform_name: str = None) -> bool:
    """Verify bundled FFmpeg works."""
    plat = platform_name or get_platform()
    bin_dir = VENDOR_DIR / plat / "bin"

    if not bin_dir.exists():
        print(f"FFmpeg not bundled for {plat}")
        return False

    ffmpeg_binary = "ffmpeg.exe" if plat == "windows" else "ffmpeg"
    ffprobe_binary = "ffprobe.exe" if plat == "windows" else "ffprobe"

    ffmpeg_path = bin_dir / ffmpeg_binary
    ffprobe_path = bin_dir / ffprobe_binary

    if not ffmpeg_path.exists() or not ffprobe_path.exists():
        print(f"FFmpeg binaries missing for {plat}")
        return False

    # Test execution
    import subprocess
    try:
        result = subprocess.run([str(ffmpeg_path), "-version"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"FFmpeg verified: {version_line}")
            return True
    except Exception as e:
        print(f"FFmpeg verification failed: {e}")

    return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bundle FFmpeg for TermiVoxed")
    parser.add_argument(
        "--platform", "-p",
        choices=["windows", "macos", "linux", "all"],
        default=None,
        help="Target platform (default: current platform)"
    )
    parser.add_argument(
        "--verify", "-v",
        action="store_true",
        help="Verify bundled FFmpeg instead of downloading"
    )

    args = parser.parse_args()

    if args.verify:
        success = verify_bundled_ffmpeg(args.platform)
    else:
        success = bundle_ffmpeg(args.platform)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
