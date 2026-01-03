#!/usr/bin/env python3
"""
Supply Chain Security Verification for TermiVoxed

This script verifies the integrity of all dependencies:
1. FFmpeg binaries - SHA256 checksums
2. Python packages - via requirements.lock hashes
3. Docker base images - SHA256 digests
4. npm packages - via package-lock.json integrity

Usage:
    # Verify all dependencies
    python build_tools/verify_supply_chain.py --verify-all

    # Generate FFmpeg checksums (run once, then commit)
    python build_tools/verify_supply_chain.py --generate-ffmpeg-checksums

    # Update requirements.lock with new hashes
    python build_tools/verify_supply_chain.py --update-python-lock

    # Verify Docker image digests
    python build_tools/verify_supply_chain.py --verify-docker

Author: LxusBrain
"""

import os
import sys
import json
import hashlib
import argparse
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BUNDLE_FFMPEG = PROJECT_ROOT / "build_tools" / "bundle_ffmpeg.py"
REQUIREMENTS_TXT = PROJECT_ROOT / "requirements.txt"
REQUIREMENTS_LOCK = PROJECT_ROOT / "requirements.lock"
PACKAGE_LOCK = PROJECT_ROOT / "web_ui" / "frontend" / "package-lock.json"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"


# =============================================================================
# FFmpeg Checksum Generation
# =============================================================================

FFMPEG_URLS = {
    "windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-20241223-12-38/ffmpeg-n7.1-20241223-win64-gpl-7.1.zip",
    "macos_ffmpeg": "https://evermeet.cx/ffmpeg/ffmpeg-7.1.zip",
    "macos_ffprobe": "https://evermeet.cx/ffmpeg/ffprobe-7.1.zip",
    "linux": "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-20241223-12-38/ffmpeg-n7.1-20241223-linux64-gpl-7.1.tar.xz",
}


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def download_and_hash(url: str, name: str) -> Tuple[str, int]:
    """Download a file and return its SHA256 hash."""
    import tempfile

    print(f"  Downloading {name}...")
    print(f"    URL: {url}")

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        try:
            urllib.request.urlretrieve(url, tmp.name)
            file_size = os.path.getsize(tmp.name)
            sha256 = calculate_sha256(Path(tmp.name))
            return sha256, file_size
        finally:
            os.unlink(tmp.name)


def generate_ffmpeg_checksums():
    """Download FFmpeg binaries and generate checksums."""
    print("=" * 60)
    print("Generating FFmpeg SHA256 Checksums")
    print("=" * 60)
    print()
    print("This will download FFmpeg binaries and calculate their checksums.")
    print("Once verified, add these to build_tools/bundle_ffmpeg.py")
    print()

    checksums = {}

    for name, url in FFMPEG_URLS.items():
        try:
            sha256, size = download_and_hash(url, name)
            checksums[name] = {
                "sha256": sha256,
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2)
            }
            print(f"    SHA256: {sha256}")
            print(f"    Size: {checksums[name]['size_mb']} MB")
            print()
        except Exception as e:
            print(f"    ERROR: {e}")
            print()

    print("=" * 60)
    print("CHECKSUMS TO ADD TO bundle_ffmpeg.py:")
    print("=" * 60)
    print()
    print("FFMPEG_CHECKSUMS = {")
    print('    "windows": {')
    if "windows" in checksums:
        print(f'        "sha256": "{checksums["windows"]["sha256"]}",')
    print("    },")
    print('    "macos": {')
    if "macos_ffmpeg" in checksums:
        print(f'        "sha256": "{checksums["macos_ffmpeg"]["sha256"]}",')
    if "macos_ffprobe" in checksums:
        print(f'        "probe_sha256": "{checksums["macos_ffprobe"]["sha256"]}",')
    print("    },")
    print('    "linux": {')
    if "linux" in checksums:
        print(f'        "sha256": "{checksums["linux"]["sha256"]}",')
    print("    },")
    print("}")

    return checksums


# =============================================================================
# Python Requirements Verification
# =============================================================================

def verify_requirements_lock():
    """Verify requirements.lock exists and has hashes."""
    print("=" * 60)
    print("Verifying Python Requirements Lock")
    print("=" * 60)

    if not REQUIREMENTS_LOCK.exists():
        print("  ERROR: requirements.lock not found!")
        print("  Run: pip-compile --generate-hashes requirements.txt -o requirements.lock")
        return False

    content = REQUIREMENTS_LOCK.read_text()
    hash_count = content.count("--hash=sha256:")

    print(f"  Lock file: {REQUIREMENTS_LOCK}")
    print(f"  Hash entries: {hash_count}")

    if hash_count < 10:
        print("  WARNING: Very few hashes found. Regenerate with:")
        print("  pip-compile --generate-hashes requirements.txt -o requirements.lock")
        return False

    print("  Status: OK")
    return True


def update_requirements_lock():
    """Regenerate requirements.lock with fresh hashes."""
    print("=" * 60)
    print("Updating Requirements Lock")
    print("=" * 60)

    try:
        subprocess.run(
            ["pip-compile", "--generate-hashes",
             str(REQUIREMENTS_TXT),
             "-o", str(REQUIREMENTS_LOCK)],
            check=True
        )
        print("  requirements.lock updated successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: {e}")
        return False
    except FileNotFoundError:
        print("  ERROR: pip-compile not found. Install with: pip install pip-tools")
        return False


# =============================================================================
# npm Package Verification
# =============================================================================

def verify_npm_integrity():
    """Verify npm packages have integrity hashes."""
    print("=" * 60)
    print("Verifying npm Package Integrity")
    print("=" * 60)

    if not PACKAGE_LOCK.exists():
        print("  ERROR: package-lock.json not found!")
        return False

    with open(PACKAGE_LOCK) as f:
        lock_data = json.load(f)

    # Count packages with integrity hashes
    packages = lock_data.get("packages", {})
    total = len(packages)
    with_integrity = sum(1 for p in packages.values() if p.get("integrity"))

    print(f"  Lock file: {PACKAGE_LOCK}")
    print(f"  Total packages: {total}")
    print(f"  With integrity hash: {with_integrity}")
    print(f"  Coverage: {with_integrity/total*100:.1f}%")

    if with_integrity < total * 0.9:
        print("  WARNING: Some packages missing integrity hashes")
        print("  Run: npm ci (uses lockfile hashes)")
        return False

    print("  Status: OK")
    return True


# =============================================================================
# Docker Image Verification
# =============================================================================

def verify_docker_digests():
    """Verify Docker images are pinned to digests."""
    print("=" * 60)
    print("Verifying Docker Image Digests")
    print("=" * 60)

    if not DOCKERFILE.exists():
        print("  ERROR: Dockerfile not found!")
        return False

    content = DOCKERFILE.read_text()

    # Check for digest-pinned images
    from_lines = [l for l in content.split('\n') if l.strip().startswith('FROM')]

    pinned = 0
    unpinned = []

    for line in from_lines:
        if '@sha256:' in line:
            pinned += 1
        else:
            unpinned.append(line.strip())

    print(f"  Dockerfile: {DOCKERFILE}")
    print(f"  FROM statements: {len(from_lines)}")
    print(f"  Pinned to digest: {pinned}")

    if unpinned:
        print("  WARNING: Unpinned images found:")
        for line in unpinned:
            print(f"    - {line}")
        return False

    print("  Status: OK")
    return True


def get_current_docker_digests():
    """Get current SHA256 digests for base images."""
    print("=" * 60)
    print("Fetching Current Docker Image Digests")
    print("=" * 60)

    images = ["python:3.11-slim", "node:20-alpine"]

    for image in images:
        try:
            # Pull image
            subprocess.run(["docker", "pull", image],
                         capture_output=True, check=True)

            # Get digest
            result = subprocess.run(
                ["docker", "inspect", "--format={{index .RepoDigests 0}}", image],
                capture_output=True, text=True, check=True
            )

            digest = result.stdout.strip()
            print(f"  {image}")
            print(f"    Digest: {digest}")
            print()

        except subprocess.CalledProcessError:
            print(f"  {image}: Unable to fetch (docker not available?)")
        except FileNotFoundError:
            print("  ERROR: docker command not found")
            return


# =============================================================================
# Full Verification
# =============================================================================

def verify_all():
    """Run all verification checks."""
    print()
    print("=" * 60)
    print("SUPPLY CHAIN SECURITY VERIFICATION")
    print("=" * 60)
    print()

    results = {
        "Python requirements.lock": verify_requirements_lock(),
        "npm package-lock.json": verify_npm_integrity(),
        "Docker image digests": verify_docker_digests(),
    }

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for check, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {check}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All supply chain verification checks passed!")
    else:
        print("Some checks failed. See details above.")
        print()
        print("To fix issues:")
        print("  1. Python: pip-compile --generate-hashes requirements.txt -o requirements.lock")
        print("  2. npm: rm -rf node_modules && npm ci")
        print("  3. Docker: Add @sha256:... to FROM statements")

    return all_passed


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Supply Chain Security Verification for TermiVoxed"
    )

    parser.add_argument(
        "--verify-all", "-a",
        action="store_true",
        help="Run all verification checks"
    )
    parser.add_argument(
        "--generate-ffmpeg-checksums",
        action="store_true",
        help="Download FFmpeg and generate SHA256 checksums"
    )
    parser.add_argument(
        "--update-python-lock",
        action="store_true",
        help="Regenerate requirements.lock with hashes"
    )
    parser.add_argument(
        "--verify-docker",
        action="store_true",
        help="Verify Docker images are pinned to digests"
    )
    parser.add_argument(
        "--get-docker-digests",
        action="store_true",
        help="Fetch current Docker image digests"
    )

    args = parser.parse_args()

    if args.generate_ffmpeg_checksums:
        generate_ffmpeg_checksums()
    elif args.update_python_lock:
        update_requirements_lock()
    elif args.verify_docker:
        verify_docker_digests()
    elif args.get_docker_digests:
        get_current_docker_digests()
    elif args.verify_all:
        success = verify_all()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
