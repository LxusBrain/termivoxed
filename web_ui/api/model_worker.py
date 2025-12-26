#!/usr/bin/env python3
"""
Model Worker - Standalone process for TTS model download/loading

This script is called as a subprocess from the API to handle
blocking model operations without blocking the main server.

Usage:
    python model_worker.py <action> [args...]

Actions:
    check <model_name>     - Check if model is downloaded
    download <model_name>  - Download model with progress
    list                   - List available models
"""

import sys
import os
import json
import time
import signal
from pathlib import Path
from typing import Optional
import io

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logger import logger


def emit_progress(stage: str, message: str, progress: int, **kwargs):
    """Emit progress update as JSON to stdout"""
    data = {
        "type": "progress",
        "stage": stage,
        "message": message,
        "progress": progress,
        "timestamp": time.time(),
        **kwargs
    }
    print(json.dumps(data), flush=True)


def emit_error(message: str, details: Optional[str] = None):
    """Emit error as JSON to stdout"""
    data = {
        "type": "error",
        "message": message,
        "details": details,
        "timestamp": time.time()
    }
    print(json.dumps(data), flush=True)


def emit_result(success: bool, data: dict):
    """Emit final result as JSON to stdout"""
    output = {
        "type": "result",
        "success": success,
        "timestamp": time.time(),
        **data
    }
    print(json.dumps(output), flush=True)


def get_model_path(model_name: str) -> Path:
    """Get the local path where model would be stored"""
    try:
        from trainer.io import get_user_data_dir
        model_dir_name = model_name.replace("/", "--")
        return Path(get_user_data_dir("tts")) / model_dir_name
    except ImportError:
        # Fallback path
        home = Path.home()
        model_dir_name = model_name.replace("/", "--")
        return home / ".local" / "share" / "tts" / model_dir_name


def check_model_downloaded(model_name: str) -> dict:
    """Check if a model is already downloaded"""
    model_path = get_model_path(model_name)

    result = {
        "model_name": model_name,
        "path": str(model_path),
        "downloaded": False,
        "has_model_file": False,
        "has_config_file": False,
        "size_mb": 0
    }

    if model_path.is_dir():
        result["downloaded"] = True

        # Check for key files
        for f in model_path.iterdir():
            if f.suffix == ".pth":
                result["has_model_file"] = True
                result["size_mb"] += f.stat().st_size / (1024 * 1024)
            elif f.name == "config.json":
                result["has_config_file"] = True

        result["size_mb"] = round(result["size_mb"], 2)

    return result


def download_model_with_progress(model_name: str) -> bool:
    """
    Download a TTS model with progress tracking.

    Uses a custom tqdm wrapper to capture progress and emit JSON updates.
    """
    emit_progress("initializing", f"Preparing to download {model_name}...", 0)

    try:
        # Check if already downloaded
        status = check_model_downloaded(model_name)
        if status["downloaded"] and status["has_model_file"] and status["has_config_file"]:
            emit_progress("complete", f"Model {model_name} is already downloaded", 100,
                         size_mb=status["size_mb"])
            emit_result(True, {"action": "download", "model_name": model_name, "cached": True})
            return True

        emit_progress("downloading", "Initializing TTS library...", 5)

        # Import TTS and patch tqdm for progress capture
        import tqdm
        original_tqdm = tqdm.tqdm

        # Track download state
        download_state = {
            "current_file": "",
            "total_files": 0,
            "completed_files": 0,
            "current_progress": 0,
            "total_size": 0,
            "downloaded_size": 0,
            "start_time": time.time()
        }

        class ProgressCaptureTqdm(original_tqdm):
            """Custom tqdm that emits JSON progress updates"""

            def __init__(self, *args, **kwargs):
                # Disable terminal output
                kwargs['file'] = io.StringIO()
                kwargs['disable'] = False
                super().__init__(*args, **kwargs)

                if self.total:
                    download_state["total_size"] = self.total
                    download_state["downloaded_size"] = 0

            def update(self, n=1):
                super().update(n)
                download_state["downloaded_size"] = self.n

                if self.total and self.total > 0:
                    file_progress = (self.n / self.total) * 100

                    # Calculate overall progress (10-90% for download phase)
                    overall_progress = 10 + int(file_progress * 0.8)

                    # Calculate speed and ETA
                    elapsed = time.time() - download_state["start_time"]
                    if elapsed > 0 and self.n > 0:
                        speed_mbps = (self.n / (1024 * 1024)) / elapsed
                        remaining_bytes = self.total - self.n
                        eta_seconds = remaining_bytes / (self.n / elapsed) if self.n > 0 else 0

                        size_mb = self.total / (1024 * 1024)
                        downloaded_mb = self.n / (1024 * 1024)

                        emit_progress(
                            "downloading",
                            f"Downloading model: {downloaded_mb:.1f}MB / {size_mb:.1f}MB",
                            overall_progress,
                            file_progress=round(file_progress, 1),
                            speed_mbps=round(speed_mbps, 2),
                            eta_seconds=round(eta_seconds),
                            downloaded_mb=round(downloaded_mb, 1),
                            total_mb=round(size_mb, 1)
                        )

            def close(self):
                super().close()

        # Patch tqdm
        tqdm.tqdm = ProgressCaptureTqdm

        try:
            emit_progress("downloading", "Starting model download...", 10)

            # Set environment to agree to ToS automatically
            os.environ['COQUI_TOS_AGREED'] = '1'

            from TTS.api import TTS

            # This will trigger the download
            emit_progress("downloading", f"Downloading {model_name}...", 15)

            # Initialize TTS which triggers download
            # Use gpu=False to avoid CUDA initialization issues in subprocess
            tts = TTS(model_name, gpu=False)

            emit_progress("verifying", "Verifying downloaded files...", 92)

            # Verify download
            status = check_model_downloaded(model_name)
            if status["downloaded"] and status["has_model_file"]:
                emit_progress("complete", f"Model downloaded successfully ({status['size_mb']}MB)", 100,
                             size_mb=status["size_mb"])
                emit_result(True, {
                    "action": "download",
                    "model_name": model_name,
                    "size_mb": status["size_mb"],
                    "path": status["path"]
                })
                return True
            else:
                emit_error("Download verification failed", "Model files not found after download")
                emit_result(False, {"action": "download", "model_name": model_name})
                return False

        finally:
            # Restore original tqdm
            tqdm.tqdm = original_tqdm

    except KeyboardInterrupt:
        emit_error("Download cancelled by user")
        emit_result(False, {"action": "download", "model_name": model_name, "cancelled": True})
        return False

    except Exception as e:
        error_msg = str(e)

        # Provide helpful messages for common errors
        if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            emit_error("Network error during download",
                      "Check your internet connection and try again")
        elif "disk" in error_msg.lower() or "space" in error_msg.lower():
            emit_error("Insufficient disk space",
                      "Free up disk space and try again (model requires ~2GB)")
        elif "permission" in error_msg.lower():
            emit_error("Permission denied",
                      f"Cannot write to model directory: {get_model_path(model_name)}")
        else:
            emit_error(f"Download failed: {error_msg}")

        emit_result(False, {"action": "download", "model_name": model_name, "error": error_msg})
        logger.exception(f"Model download failed: {e}")
        return False


def list_available_models() -> list:
    """List available TTS models"""
    try:
        from TTS.api import TTS
        models = TTS().list_models()

        # Filter to voice cloning capable models
        vc_models = [m for m in models if "xtts" in m.lower() or "voice_conversion" in m.lower()]

        emit_result(True, {
            "action": "list",
            "models": vc_models,
            "total": len(vc_models)
        })
        return vc_models

    except Exception as e:
        emit_error(f"Failed to list models: {e}")
        emit_result(False, {"action": "list", "error": str(e)})
        return []


def load_model(model_name: str) -> bool:
    """Load a model into memory (for pre-warming)"""
    emit_progress("loading", f"Loading model {model_name}...", 0)

    try:
        # First check if downloaded
        status = check_model_downloaded(model_name)
        if not status["downloaded"]:
            emit_error("Model not downloaded", "Please download the model first")
            emit_result(False, {"action": "load", "model_name": model_name})
            return False

        emit_progress("loading", "Initializing TTS...", 20)

        os.environ['COQUI_TOS_AGREED'] = '1'
        os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'

        from TTS.api import TTS
        import torch

        # Determine device
        if torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

        emit_progress("loading", f"Loading model on {device}...", 40)

        tts = TTS(model_name).to(device)

        emit_progress("loading", "Model loaded successfully", 100)
        emit_result(True, {
            "action": "load",
            "model_name": model_name,
            "device": device
        })
        return True

    except Exception as e:
        emit_error(f"Failed to load model: {e}")
        emit_result(False, {"action": "load", "model_name": model_name, "error": str(e)})
        return False


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        emit_error("No action specified", "Usage: model_worker.py <action> [args...]")
        sys.exit(1)

    action = sys.argv[1]

    # Handle signals for graceful shutdown
    def signal_handler(signum, frame):
        emit_error("Process interrupted")
        sys.exit(1)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if action == "check":
        if len(sys.argv) < 3:
            emit_error("Model name required")
            sys.exit(1)
        model_name = sys.argv[2]
        result = check_model_downloaded(model_name)
        emit_result(True, {"action": "check", **result})

    elif action == "download":
        if len(sys.argv) < 3:
            emit_error("Model name required")
            sys.exit(1)
        model_name = sys.argv[2]
        success = download_model_with_progress(model_name)
        sys.exit(0 if success else 1)

    elif action == "load":
        if len(sys.argv) < 3:
            emit_error("Model name required")
            sys.exit(1)
        model_name = sys.argv[2]
        success = load_model(model_name)
        sys.exit(0 if success else 1)

    elif action == "list":
        list_available_models()

    else:
        emit_error(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
