#!/usr/bin/env python3
"""
Voice Clone Worker - Standalone process for voice cloning operations

This script handles voice cloning in a separate process to prevent
blocking the main server during model loading and inference.

Usage:
    python voice_clone_worker.py <voice_sample_path> <text> <output_path> <language>
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set environment variables before importing torch
os.environ['COQUI_TOS_AGREED'] = '1'
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'


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


def emit_error(message: str, details: str = None):
    """Emit error as JSON to stdout"""
    data = {
        "type": "error",
        "message": message,
        "details": details,
        "timestamp": time.time()
    }
    print(json.dumps(data), flush=True)


def emit_result(success: bool, **kwargs):
    """Emit final result as JSON to stdout"""
    data = {
        "type": "result",
        "success": success,
        "timestamp": time.time(),
        **kwargs
    }
    print(json.dumps(data), flush=True)


def convert_to_wav(input_path: Path, output_path: Path) -> tuple[bool, str]:
    """Convert audio file to WAV format suitable for XTTS

    Returns tuple of (success, error_message)
    """
    try:
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-ar', '22050',  # XTTS expects 22050 Hz
            '-ac', '1',      # Mono
            '-c:a', 'pcm_s16le',  # 16-bit PCM
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            return False, f"FFmpeg error: {result.stderr}"

        if not output_path.exists():
            return False, "Output file was not created"

        # Verify the file is readable and has content
        file_size = output_path.stat().st_size
        if file_size < 1000:  # Less than 1KB is suspicious
            return False, f"Converted file too small: {file_size} bytes"

        return True, ""

    except subprocess.TimeoutExpired:
        return False, "FFmpeg conversion timed out"
    except Exception as e:
        return False, f"Conversion failed: {str(e)}"


def clone_voice(voice_sample_path: str, text: str, output_path: str, language: str = "en"):
    """
    Generate audio using voice cloning.

    This runs in a separate process to avoid blocking the main server.
    """
    import tempfile
    import uuid

    start_time = time.time()

    emit_progress("initializing", "Starting voice cloning...", 0)

    sample_path = Path(voice_sample_path)
    out_path = Path(output_path)

    # Validate input
    if not sample_path.exists():
        emit_error("Voice sample not found", str(sample_path))
        emit_result(False)
        return False

    # Convert to WAV if needed (XTTS requires WAV format)
    temp_wav = None
    working_sample_path = sample_path

    if sample_path.suffix.lower() != '.wav':
        emit_progress("converting", "Converting audio format...", 5)

        # Use UUID for temp filename to avoid special character issues
        temp_wav = Path(tempfile.gettempdir()) / f"xtts_sample_{uuid.uuid4().hex}.wav"

        success, error_msg = convert_to_wav(sample_path, temp_wav)
        if not success:
            emit_error(f"Failed to convert audio to WAV: {error_msg}")
            emit_result(False)
            return False

        working_sample_path = temp_wav
        emit_progress("converting", f"Audio converted successfully ({temp_wav.stat().st_size // 1024}KB)", 8)

    try:
        emit_progress("loading", "Loading TTS model (this may take a minute on first use)...", 10)

        # Import TTS
        from TTS.api import TTS
        import torch

        # Determine device
        if torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

        emit_progress("loading", f"Loading XTTS model on {device}...", 20)

        # Load model
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        emit_progress("generating", "Generating cloned voice audio...", 50)

        # Ensure output directory exists
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate audio using the working sample path (converted WAV if needed)
        tts.tts_to_file(
            text=text,
            speaker_wav=str(working_sample_path),
            language=language,
            file_path=str(out_path),
            split_sentences=True
        )

        emit_progress("finalizing", "Finalizing audio...", 90)

        # Verify output
        if not out_path.exists():
            emit_error("Output file was not created")
            emit_result(False)
            return False

        # Get duration using ffprobe
        duration = 0.0
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                 '-of', 'csv=p=0', str(out_path)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                duration = float(result.stdout.strip())
        except:
            pass

        elapsed = time.time() - start_time

        emit_progress("complete", "Voice cloning completed!", 100)
        emit_result(
            True,
            output_path=str(out_path),
            duration=duration,
            elapsed_seconds=round(elapsed, 1)
        )
        return True

    except Exception as e:
        emit_error(f"Voice cloning failed: {str(e)}")
        emit_result(False, error=str(e))
        return False

    finally:
        # Cleanup temp file
        if temp_wav and temp_wav.exists():
            try:
                temp_wav.unlink()
            except:
                pass


def main():
    """Main entry point"""
    if len(sys.argv) < 5:
        emit_error("Invalid arguments", "Usage: voice_clone_worker.py <sample_path> <text> <output_path> <language>")
        sys.exit(1)

    voice_sample_path = sys.argv[1]
    text = sys.argv[2]
    output_path = sys.argv[3]
    language = sys.argv[4] if len(sys.argv) > 4 else "en"

    success = clone_voice(voice_sample_path, text, output_path, language)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
