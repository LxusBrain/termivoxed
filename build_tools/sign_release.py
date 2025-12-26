#!/usr/bin/env python3
"""
Release Signing Script for TermiVoxed Updates

Signs update packages with Ed25519 for secure distribution.

Usage:
    python sign_release.py <release_file> [--key <private_key_path>]

Examples:
    python sign_release.py TermiVoxed-1.2.0-win64.exe
    python sign_release.py TermiVoxed-1.2.0-macos.dmg --key /secure/signing_key.pem
"""

import os
import sys
import argparse
import hashlib
import base64
import json
from pathlib import Path
from datetime import datetime

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("ERROR: cryptography library not installed.")
    print("Install with: pip install cryptography")
    sys.exit(1)


def load_private_key(key_path: str) -> Ed25519PrivateKey:
    """Load the Ed25519 private key from a PEM file."""
    path = Path(key_path)
    if not path.exists():
        raise FileNotFoundError(f"Private key not found: {key_path}")

    pem_data = path.read_bytes()
    private_key = serialization.load_pem_private_key(pem_data, password=None)

    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("Key is not an Ed25519 private key")

    return private_key


def sign_file(file_path: str, private_key: Ed25519PrivateKey) -> tuple[str, str]:
    """
    Sign a file with Ed25519.

    Returns:
        Tuple of (sha256_hash, signature_base64)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Calculate SHA256 hash
    sha256_hash = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256_hash.update(chunk)

    hash_bytes = sha256_hash.digest()
    hash_hex = sha256_hash.hexdigest()

    # Sign the hash
    signature = private_key.sign(hash_bytes)
    signature_b64 = base64.b64encode(signature).decode('utf-8')

    return hash_hex, signature_b64


def create_manifest(
    file_path: str,
    version: str,
    hash_hex: str,
    signature: str,
    channel: str = "stable"
) -> dict:
    """Create an update manifest for the release."""
    path = Path(file_path)
    file_size = path.stat().st_size

    # Determine platform from filename
    filename = path.name.lower()
    if 'win' in filename or filename.endswith('.exe'):
        platform = 'windows'
    elif 'mac' in filename or filename.endswith('.dmg'):
        platform = 'macos'
    elif 'linux' in filename:
        platform = 'linux'
    else:
        platform = 'unknown'

    manifest = {
        "version": version,
        "channel": channel,
        "platform": platform,
        "filename": path.name,
        "size": file_size,
        "sha256": hash_hex,
        "signature": signature,
        "release_date": datetime.utcnow().isoformat() + "Z",
        "min_app_version": None,  # Optional: minimum version that can update
        "release_notes_url": f"https://github.com/luxusbrain/termivoxed/releases/tag/v{version}",
        "download_url": f"https://github.com/luxusbrain/termivoxed/releases/download/v{version}/{path.name}"
    }

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Sign a TermiVoxed release with Ed25519"
    )
    parser.add_argument("release_file", help="Path to the release file to sign")
    parser.add_argument(
        "--key", "-k",
        default=None,
        help="Path to private key PEM file (default: signing_keys/update_signing_key.pem)"
    )
    parser.add_argument(
        "--version", "-v",
        default=None,
        help="Version string (e.g., 1.2.0). Auto-detected from filename if not provided."
    )
    parser.add_argument(
        "--channel", "-c",
        default="stable",
        choices=["stable", "beta", "alpha"],
        help="Release channel (default: stable)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output manifest path (default: <release_file>.manifest.json)"
    )

    args = parser.parse_args()

    # Find private key
    if args.key:
        key_path = args.key
    else:
        # Try default location
        default_key = Path(__file__).parent / "signing_keys" / "update_signing_key.pem"
        if default_key.exists():
            key_path = str(default_key)
        else:
            # Try environment variable
            key_path = os.environ.get("UPDATE_SIGNING_KEY_PATH")
            if not key_path:
                print("ERROR: No private key found.")
                print("Specify with --key or set UPDATE_SIGNING_KEY_PATH environment variable")
                print("Or run generate_update_keys.py first")
                sys.exit(1)

    # Extract version from filename if not provided
    version = args.version
    if not version:
        import re
        match = re.search(r'(\d+\.\d+\.\d+)', Path(args.release_file).name)
        if match:
            version = match.group(1)
        else:
            print("ERROR: Could not detect version from filename.")
            print("Please provide --version argument")
            sys.exit(1)

    print(f"{'='*60}")
    print("TermiVoxed Release Signer")
    print(f"{'='*60}")
    print(f"\nFile: {args.release_file}")
    print(f"Version: {version}")
    print(f"Channel: {args.channel}")
    print(f"Key: {key_path}")

    try:
        # Load private key
        print("\nLoading private key...")
        private_key = load_private_key(key_path)

        # Sign the file
        print("Signing file...")
        hash_hex, signature = sign_file(args.release_file, private_key)

        print(f"\nSHA256: {hash_hex}")
        print(f"Signature: {signature[:32]}...{signature[-32:]}")

        # Create manifest
        manifest = create_manifest(
            args.release_file,
            version,
            hash_hex,
            signature,
            args.channel
        )

        # Write manifest
        output_path = args.output or f"{args.release_file}.manifest.json"
        with open(output_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        print(f"\nManifest written: {output_path}")
        print(f"\n{'='*60}")
        print("SIGNING COMPLETE")
        print(f"{'='*60}")

        # Print verification command
        print("\nTo verify this signature, use:")
        print(f"  python verify_signature.py {args.release_file} --manifest {output_path}")

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
