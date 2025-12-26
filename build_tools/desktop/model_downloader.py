#!/usr/bin/env python3
"""
First-Run Model Downloader for TermiVoxed

This module handles downloading AI models on first run:
- Edge-TTS (no download needed - uses Microsoft's API)
- Coqui TTS models (optional - for voice cloning)
- Future: Whisper models for transcription

Design Philosophy:
- Models are NOT bundled in the installer (would make it 2+ GB)
- Downloaded on-demand when features are first used
- Stored in user's data directory (persists across updates)
- Includes hash verification for integrity
"""

import os
import sys
import json
import hashlib
import urllib.request
import ssl
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class ModelInfo:
    """Information about a downloadable model."""
    name: str
    description: str
    url: str
    size_mb: float
    sha256: str
    required: bool = False
    category: str = "tts"


# Model registry - all downloadable models
# ============================================================================
# SECURITY: Model Integrity Verification
# ============================================================================
# All models should have SHA256 checksums for integrity verification.
# Empty checksums will still allow download but with a warning.
#
# HOW TO GET SHA256 FOR HUGGING FACE MODELS:
# 1. Go to the model's "Files" tab on Hugging Face
# 2. Click on the file to see its details, including SHA256
# 3. Or download and run: shasum -a 256 <file>
#
# IMPORTANT: Always verify checksums match official sources before updating.
# ============================================================================

MODELS = {
    # Coqui TTS models (for voice cloning - Pro feature)
    "coqui_xtts_v2": ModelInfo(
        name="XTTS v2",
        description="High-quality voice cloning model (English, multilingual)",
        url="https://huggingface.co/coqui/XTTS-v2/resolve/main/model.pth",
        size_mb=1800,  # ~1.8 GB
        # SHA256 from HuggingFace model page - verify at:
        # https://huggingface.co/coqui/XTTS-v2/blob/main/model.pth
        sha256="",  # TODO: Add actual SHA256 from HuggingFace
        required=False,
        category="tts"
    ),

    # Smaller fallback voice model
    "coqui_tts_vits": ModelInfo(
        name="VITS (Fast)",
        description="Fast text-to-speech model",
        url="https://huggingface.co/coqui/TTS/resolve/main/tts_models--en--vctk--vits.zip",
        size_mb=150,
        # SHA256 from HuggingFace - verify at:
        # https://huggingface.co/coqui/TTS/tree/main
        sha256="",  # TODO: Add actual SHA256 from HuggingFace
        required=False,
        category="tts"
    ),
}


class ModelDownloader:
    """
    Manages downloading and verifying AI models.

    This runs on first application launch and when users
    enable features that require additional models.
    """

    def __init__(self, models_dir: Optional[Path] = None):
        """
        Initialize downloader.

        Args:
            models_dir: Directory to store models.
                       Defaults to TERMIVOXED_MODELS_DIR env var or platform-specific location.
        """
        if models_dir:
            self.models_dir = Path(models_dir)
        else:
            env_dir = os.environ.get('TERMIVOXED_MODELS_DIR')
            if env_dir:
                self.models_dir = Path(env_dir)
            else:
                # Platform-specific default
                if sys.platform == 'win32':
                    base = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
                    self.models_dir = base / 'TermiVoxed' / 'models'
                elif sys.platform == 'darwin':
                    self.models_dir = Path.home() / 'Library' / 'Application Support' / 'TermiVoxed' / 'models'
                else:
                    self.models_dir = Path.home() / '.local' / 'share' / 'termivoxed' / 'models'

        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._download_progress: dict = {}
        self._cancel_requested = False

    def get_model_path(self, model_id: str) -> Path:
        """Get the local path where a model should be stored."""
        model = MODELS.get(model_id)
        if not model:
            raise ValueError(f"Unknown model: {model_id}")

        category_dir = self.models_dir / model.category
        category_dir.mkdir(exist_ok=True)

        # Use model name as filename
        filename = Path(model.url).name
        return category_dir / filename

    def is_model_downloaded(self, model_id: str) -> bool:
        """Check if a model is already downloaded."""
        model_path = self.get_model_path(model_id)
        return model_path.exists()

    def get_required_disk_space(self, model_ids: list[str]) -> float:
        """Get required disk space in MB for models not yet downloaded."""
        total = 0.0
        for model_id in model_ids:
            if model_id in MODELS and not self.is_model_downloaded(model_id):
                total += MODELS[model_id].size_mb
        return total

    def download_model(
        self,
        model_id: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> bool:
        """
        Download a single model.

        Args:
            model_id: ID of model to download
            progress_callback: Called with (model_id, progress 0-1, status_message)

        Returns:
            True if successful
        """
        model = MODELS.get(model_id)
        if not model:
            if progress_callback:
                progress_callback(model_id, 0, f"Error: Unknown model {model_id}")
            return False

        dest_path = self.get_model_path(model_id)

        # Skip if already downloaded
        if dest_path.exists():
            if progress_callback:
                progress_callback(model_id, 1.0, "Already downloaded")
            return True

        if progress_callback:
            progress_callback(model_id, 0, f"Downloading {model.name}...")

        try:
            # Create temp file for atomic download
            temp_path = dest_path.with_suffix('.tmp')

            # Download with progress
            self._download_file(
                model.url,
                temp_path,
                lambda p: progress_callback(model_id, p * 0.95, "Downloading...") if progress_callback else None
            )

            if self._cancel_requested:
                temp_path.unlink(missing_ok=True)
                if progress_callback:
                    progress_callback(model_id, 0, "Cancelled")
                return False

            # Verify hash if provided
            if progress_callback:
                progress_callback(model_id, 0.95, "Verifying...")

            actual_hash = self._compute_hash(temp_path)

            if model.sha256:
                if actual_hash != model.sha256:
                    temp_path.unlink()
                    if progress_callback:
                        progress_callback(model_id, 0, "Hash verification failed")
                    print(f"\nSECURITY WARNING: Hash mismatch for {model_id}!")
                    print(f"  Expected: {model.sha256}")
                    print(f"  Actual:   {actual_hash}")
                    return False
            else:
                # No hash provided - log warning
                print(f"\nWARNING: No SHA256 checksum provided for {model_id}")
                print(f"  Computed hash: {actual_hash}")
                print("  For security, add this hash to model_downloader.py after verification")

            # Atomic rename
            temp_path.rename(dest_path)

            if progress_callback:
                progress_callback(model_id, 1.0, "Complete")

            return True

        except Exception as e:
            if progress_callback:
                progress_callback(model_id, 0, f"Error: {str(e)}")
            return False

    def _download_file(
        self,
        url: str,
        dest: Path,
        progress_callback: Optional[Callable[[float], None]] = None
    ):
        """Download a file with progress tracking."""
        # Create SSL context that works everywhere
        ctx = ssl.create_default_context()

        # Create request with User-Agent (some servers require it)
        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'TermiVoxed/1.0'}
        )

        with urllib.request.urlopen(request, context=ctx) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 8192 * 4  # 32KB chunks

            with open(dest, 'wb') as f:
                while True:
                    if self._cancel_requested:
                        break

                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback and total_size > 0:
                        progress_callback(downloaded / total_size)

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def cancel_downloads(self):
        """Request cancellation of ongoing downloads."""
        self._cancel_requested = True

    def get_models_status(self) -> dict:
        """Get status of all models."""
        status = {}
        for model_id, model in MODELS.items():
            status[model_id] = {
                'name': model.name,
                'description': model.description,
                'size_mb': model.size_mb,
                'required': model.required,
                'category': model.category,
                'downloaded': self.is_model_downloaded(model_id)
            }
        return status


class FirstRunWizard:
    """
    First-run setup wizard for TermiVoxed.

    This is shown on first launch to:
    1. Accept terms of service
    2. Configure initial settings
    3. Optionally download AI models
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.initialized_marker = data_dir / '.initialized'
        self.downloader = ModelDownloader(data_dir / 'models')

    def is_first_run(self) -> bool:
        """Check if this is the first run."""
        return not self.initialized_marker.exists()

    def mark_initialized(self):
        """Mark first-run setup as complete."""
        self.initialized_marker.write_text(
            json.dumps({
                'initialized_at': __import__('datetime').datetime.now().isoformat(),
                'version': '1.0.0'
            })
        )

    def get_setup_status(self) -> dict:
        """Get current setup status."""
        return {
            'is_first_run': self.is_first_run(),
            'data_dir': str(self.data_dir),
            'models_status': self.downloader.get_models_status(),
            'required_space_mb': self.downloader.get_required_disk_space(
                [m for m, info in MODELS.items() if info.required]
            )
        }


def main():
    """CLI for model management."""
    import argparse

    parser = argparse.ArgumentParser(description="TermiVoxed Model Manager")
    parser.add_argument('--list', action='store_true', help="List all models")
    parser.add_argument('--download', metavar='MODEL_ID', help="Download a specific model")
    parser.add_argument('--download-all', action='store_true', help="Download all models")
    parser.add_argument('--status', action='store_true', help="Show download status")

    args = parser.parse_args()

    downloader = ModelDownloader()

    if args.list:
        print("\nAvailable Models:")
        print("-" * 60)
        for model_id, model in MODELS.items():
            status = "Downloaded" if downloader.is_model_downloaded(model_id) else "Not downloaded"
            required = " (Required)" if model.required else ""
            print(f"\n  {model_id}{required}")
            print(f"    Name: {model.name}")
            print(f"    Description: {model.description}")
            print(f"    Size: {model.size_mb:.1f} MB")
            print(f"    Status: {status}")

    elif args.download:
        def progress(model_id, progress, message):
            bar = "#" * int(progress * 30) + "-" * (30 - int(progress * 30))
            print(f"\r  [{bar}] {int(progress*100)}% {message}", end="", flush=True)

        print(f"\nDownloading {args.download}...")
        success = downloader.download_model(args.download, progress)
        print()
        if success:
            print("Download complete!")
        else:
            print("Download failed!")
            sys.exit(1)

    elif args.download_all:
        print("\nDownloading all models...")
        for model_id in MODELS:
            if not downloader.is_model_downloaded(model_id):
                print(f"\n{model_id}:")
                downloader.download_model(model_id, lambda m, p, s: print(f"  {int(p*100)}% {s}"))

    elif args.status:
        status = downloader.get_models_status()
        print("\nModel Status:")
        print("-" * 40)
        for model_id, info in status.items():
            status_str = "OK" if info['downloaded'] else "Missing"
            print(f"  {model_id}: {status_str}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
