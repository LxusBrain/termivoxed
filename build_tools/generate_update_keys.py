#!/usr/bin/env python3
"""
Ed25519 Key Pair Generator for TermiVoxed Updates

This script generates an Ed25519 key pair for signing application updates.
- The PRIVATE key is used to sign updates (keep SECURE - never commit to git)
- The PUBLIC key is embedded in the application to verify updates

Usage:
    python generate_update_keys.py

Output:
    - update_signing_key.pem: Private key (KEEP SECRET!)
    - update_public_key.b64: Public key (base64 encoded, embed in app)
    - .env.signing: Environment variables for CI/CD
"""

import os
import sys
import base64
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("ERROR: cryptography library not installed.")
    print("Install with: pip install cryptography")
    sys.exit(1)


def generate_keypair():
    """Generate a new Ed25519 key pair for update signing."""
    print("=" * 60)
    print("TermiVoxed Update Signing Key Generator")
    print("=" * 60)

    # Generate the private key
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Serialize private key (PEM format for secure storage)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Serialize public key (raw bytes, then base64 for embedding)
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    public_b64 = base64.b64encode(public_raw).decode('utf-8')

    # Output directory
    output_dir = Path(__file__).parent / "signing_keys"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write private key (PEM format)
    private_key_path = output_dir / "update_signing_key.pem"
    private_key_path.write_bytes(private_pem)
    os.chmod(private_key_path, 0o600)  # Restrict permissions

    # Write public key (base64 format for embedding)
    public_key_path = output_dir / "update_public_key.b64"
    public_key_path.write_text(public_b64)

    # Write environment variables for CI/CD
    env_path = output_dir / ".env.signing"
    env_content = f"""# TermiVoxed Update Signing Environment Variables
# Add these to your CI/CD secrets or local environment

# Public key (safe to embed in app and commit)
TERMIVOXED_UPDATE_PUBLIC_KEY={public_b64}

# Private key path (use for signing, NEVER commit to git)
# In CI/CD, use the PEM content directly as a secret
UPDATE_SIGNING_KEY_PATH={private_key_path.absolute()}
"""
    env_path.write_text(env_content)

    # Write gitignore for the signing keys directory
    gitignore_path = output_dir / ".gitignore"
    gitignore_content = """# NEVER commit private signing keys
update_signing_key.pem
.env.signing

# Public key is safe to commit
!update_public_key.b64
"""
    gitignore_path.write_text(gitignore_content)

    print(f"\n{'='*60}")
    print("KEY PAIR GENERATED SUCCESSFULLY")
    print("="*60)
    print(f"\nOutput directory: {output_dir.absolute()}")
    print(f"\nFiles created:")
    print(f"  1. update_signing_key.pem - PRIVATE KEY (KEEP SECRET!)")
    print(f"  2. update_public_key.b64  - Public key (embed in app)")
    print(f"  3. .env.signing           - Environment variables")
    print(f"  4. .gitignore             - Protects private key from git")

    print(f"\n{'='*60}")
    print("PUBLIC KEY (embed in auto_updater.py):")
    print("="*60)
    print(f"\n{public_b64}\n")

    print("="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("""
1. SECURE THE PRIVATE KEY:
   - Store update_signing_key.pem in a secure location
   - Add to CI/CD secrets (e.g., GitHub Actions secrets)
   - NEVER commit to git repository

2. EMBED THE PUBLIC KEY:
   - Set environment variable: TERMIVOXED_UPDATE_PUBLIC_KEY
   - Or update core/auto_updater.py directly

3. SIGN YOUR RELEASES:
   Use the sign_release.py script to sign updates

4. BACKUP THE PRIVATE KEY:
   - Store in a password manager
   - Use hardware security module (HSM) for production
   - Keep offline backup in secure location
""")

    return public_b64


def main():
    # Check if keys already exist
    output_dir = Path(__file__).parent / "signing_keys"
    private_key_path = output_dir / "update_signing_key.pem"

    if private_key_path.exists():
        print("WARNING: Signing keys already exist!")
        print(f"Location: {private_key_path}")
        response = input("\nRegenerate keys? This will INVALIDATE all existing signed updates! [y/N]: ")
        if response.lower() != 'y':
            print("Aborted. Existing keys preserved.")
            return

        # Backup existing keys
        backup_dir = output_dir / "backup"
        backup_dir.mkdir(exist_ok=True)
        import shutil
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(private_key_path, backup_dir / f"update_signing_key_{timestamp}.pem.bak")
        print(f"Backed up existing key to: {backup_dir}")

    public_key = generate_keypair()

    # Ask if user wants to update auto_updater.py
    print("\nWould you like to update auto_updater.py with the new public key?")
    response = input("This sets the TERMIVOXED_UPDATE_PUBLIC_KEY default value [y/N]: ")

    if response.lower() == 'y':
        auto_updater_path = Path(__file__).parent.parent / "core" / "auto_updater.py"
        if auto_updater_path.exists():
            content = auto_updater_path.read_text()
            # Find and replace the placeholder
            if "REPLACE_WITH_YOUR_ED25519_PUBLIC_KEY_BASE64" in content:
                content = content.replace(
                    "REPLACE_WITH_YOUR_ED25519_PUBLIC_KEY_BASE64",
                    public_key
                )
                auto_updater_path.write_text(content)
                print(f"\n Updated: {auto_updater_path}")
            else:
                print("\nNote: Placeholder not found in auto_updater.py (already configured?)")
        else:
            print(f"\nWarning: Could not find {auto_updater_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
