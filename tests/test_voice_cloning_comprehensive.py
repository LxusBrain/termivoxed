#!/usr/bin/env python3
"""
Comprehensive Test Suite for Voice Cloning Feature

Tests:
1. MPS detection on Apple Silicon
2. Voice sample upload API
3. Voice sample management (list, get, delete)
4. Voice cloning generation with Whisper timing
5. Full API integration
"""

import asyncio
import os
import sys
import json
import tempfile
import wave
import struct
from pathlib import Path
from typing import Dict, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Accept Coqui TOS automatically
os.environ['COQUI_TOS_AGREED'] = '1'

# Test results tracking
test_results: Dict[str, Tuple[bool, str]] = {}


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_result(test_name: str, passed: bool, message: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {test_name}")
    if message:
        print(f"         {message}")
    test_results[test_name] = (passed, message)


def create_test_audio_file(duration_seconds: float = 3.0, sample_rate: int = 22050) -> Path:
    """Create a simple test WAV file with a sine wave"""
    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)

    # Generate a simple sine wave
    import math
    frequency = 440  # Hz
    num_samples = int(sample_rate * duration_seconds)

    with wave.open(temp_file.name, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        for i in range(num_samples):
            t = i / sample_rate
            value = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * t))
            wav_file.writeframes(struct.pack('<h', value))

    return Path(temp_file.name)


async def test_mps_detection():
    """Test 1: MPS detection on Apple Silicon"""
    print_header("Test 1: MPS Detection on Apple Silicon")

    try:
        import torch

        # Check PyTorch version
        print_result(
            "PyTorch installed",
            True,
            f"Version: {torch.__version__}"
        )

        # Check CUDA
        cuda_available = torch.cuda.is_available()
        print_result(
            "CUDA availability check",
            True,
            f"CUDA available: {cuda_available}"
        )

        # Check MPS
        mps_available = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        mps_built = hasattr(torch.backends, 'mps') and torch.backends.mps.is_built()

        print_result(
            "MPS availability check",
            mps_available or cuda_available,  # One should be available
            f"MPS available: {mps_available}, MPS built: {mps_built}"
        )

        # Test Coqui provider detection
        from backend.tts_providers.coqui_provider import CoquiTTSProvider

        install_info = CoquiTTSProvider.check_installation()

        print_result(
            "Coqui TTS installed",
            install_info.get('installed', False),
            f"Version: {install_info.get('version', 'unknown')}"
        )

        print_result(
            "Recommended device detected",
            install_info.get('recommended_device') in ['mps', 'cuda', 'cpu'],
            f"Recommended: {install_info.get('recommended_device')}"
        )

        # Verify MPS is detected on Apple Silicon
        if mps_available:
            print_result(
                "Apple Silicon MPS enabled",
                install_info.get('mps_available', False),
                "MPS acceleration will be used"
            )

    except Exception as e:
        print_result("MPS detection", False, str(e))


async def test_voice_sample_upload():
    """Test 2: Voice sample upload API"""
    print_header("Test 2: Voice Sample Upload API")

    try:
        # Import the API functions
        from web_ui.api.routes.tts import (
            upload_voice_sample,
            list_voice_samples,
            _load_voice_samples_metadata,
            VOICE_SAMPLES_DIR
        )
        from fastapi import UploadFile
        from io import BytesIO

        # Create a test audio file
        test_audio_path = create_test_audio_file(duration_seconds=2.0)

        print_result(
            "Test audio file created",
            test_audio_path.exists(),
            f"Path: {test_audio_path}"
        )

        # Read the file content
        with open(test_audio_path, 'rb') as f:
            content = f.read()

        # Create a mock UploadFile
        class MockUploadFile:
            def __init__(self, content: bytes, filename: str):
                self._content = content
                self.filename = filename

            async def read(self):
                return self._content

        mock_file = MockUploadFile(content, "test_voice_sample.wav")

        # Test upload
        response = await upload_voice_sample(
            file=mock_file,
            name="Test Voice Sample",
            language="en"
        )

        # Response is a dict with 'success' and 'sample' keys
        # 'sample' is a VoiceSampleInfo Pydantic model
        sample_obj = response.get('sample') if isinstance(response, dict) else None
        sample_id = sample_obj.id if sample_obj else None

        print_result(
            "Voice sample upload",
            response.get('success', False) if isinstance(response, dict) else False,
            f"Sample ID: {sample_id or 'N/A'}"
        )

        # Verify file was saved
        metadata = _load_voice_samples_metadata()
        sample_exists = sample_id in metadata.get('samples', {}) if sample_id else False

        print_result(
            "Sample saved to metadata",
            sample_exists,
            f"Samples in storage: {len(metadata.get('samples', {}))}"
        )

        # Cleanup test audio
        test_audio_path.unlink()

        return sample_id

    except Exception as e:
        print_result("Voice sample upload", False, str(e))
        import traceback
        traceback.print_exc()
        return None


async def test_voice_sample_management(sample_id: str = None):
    """Test 3: Voice sample list and management"""
    print_header("Test 3: Voice Sample Management")

    try:
        from web_ui.api.routes.tts import (
            list_voice_samples,
            get_voice_sample,
            delete_voice_sample
        )

        # Test list
        list_response = await list_voice_samples()

        print_result(
            "List voice samples",
            hasattr(list_response, 'samples'),
            f"Found {list_response.total} samples"
        )

        if sample_id:
            # Test get single sample
            try:
                sample = await get_voice_sample(sample_id)
                print_result(
                    "Get single sample",
                    sample.id == sample_id,
                    f"Name: {sample.name}"
                )
            except Exception as e:
                print_result("Get single sample", False, str(e))

            # Test delete
            try:
                delete_response = await delete_voice_sample(sample_id)
                print_result(
                    "Delete voice sample",
                    delete_response.get('success', False),
                    f"Message: {delete_response.get('message', 'N/A')}"
                )
            except Exception as e:
                print_result("Delete voice sample", False, str(e))

            # Verify deletion
            list_response_after = await list_voice_samples()
            sample_deleted = sample_id not in [s.id for s in list_response_after.samples]

            print_result(
                "Sample actually deleted",
                sample_deleted,
                f"Remaining samples: {list_response_after.total}"
            )

    except Exception as e:
        print_result("Voice sample management", False, str(e))
        import traceback
        traceback.print_exc()


async def test_voice_cloning_generation():
    """Test 4: Voice cloning generation with Whisper timing"""
    print_header("Test 4: Voice Cloning Generation")

    try:
        from backend.tts_providers.coqui_provider import CoquiTTSProvider
        from pathlib import Path
        import shutil

        # Create test directory
        test_dir = Path("storage/test_voice_cloning")
        test_dir.mkdir(parents=True, exist_ok=True)

        # Create a test voice sample
        sample_path = create_test_audio_file(duration_seconds=5.0)
        voice_sample_path = test_dir / "test_sample.wav"
        shutil.copy(sample_path, voice_sample_path)
        sample_path.unlink()

        print_result(
            "Voice sample prepared",
            voice_sample_path.exists(),
            f"Duration: 5 seconds"
        )

        # Initialize provider
        provider = CoquiTTSProvider(config={"use_gpu": True})
        initialized = await provider.initialize()

        print_result(
            "Coqui provider initialized",
            initialized,
            "Provider ready for voice cloning"
        )

        if not initialized:
            print("  ⚠️ Skipping clone test - provider not available")
            return

        # Test voice cloning
        output_path = test_dir / "cloned_output.wav"
        test_text = "Hello, this is a test of voice cloning with word timing."

        print("  Generating cloned voice audio (this may take a moment)...")

        result = await provider.clone_voice(
            audio_sample_path=voice_sample_path,
            text=test_text,
            output_path=output_path,
            language="en",
            voice_sample_name="Test Sample"
        )

        print_result(
            "Voice cloning generation",
            output_path.exists(),
            f"Output: {result.audio_path}"
        )

        print_result(
            "Audio duration valid",
            result.duration_seconds > 0,
            f"Duration: {result.duration_seconds:.2f}s"
        )

        print_result(
            "Word timings extracted",
            len(result.word_timings) > 0,
            f"Words: {len(result.word_timings)}"
        )

        print_result(
            "Voice cloning metadata",
            result.metadata.get('voice_cloning') == True,
            f"Timing type: {result.metadata.get('timing_type', 'N/A')}"
        )

        # Show sample word timings
        if result.word_timings:
            print("\n  Sample word timings:")
            for wt in result.word_timings[:5]:
                print(f"    - '{wt.text}' at {wt.offset_ms}ms for {wt.duration_ms}ms")

        # Cleanup
        shutil.rmtree(test_dir)

    except Exception as e:
        print_result("Voice cloning generation", False, str(e))
        import traceback
        traceback.print_exc()


async def test_frontend_compilation():
    """Test 5: Frontend TypeScript compilation"""
    print_header("Test 5: Frontend TypeScript Compilation")

    import subprocess

    try:
        # Run TypeScript compiler
        result = subprocess.run(
            ['npx', 'tsc', '--noEmit'],
            cwd=Path(__file__).parent.parent / 'web_ui' / 'frontend',
            capture_output=True,
            text=True,
            timeout=120
        )

        print_result(
            "TypeScript compilation",
            result.returncode == 0,
            "No errors" if result.returncode == 0 else result.stdout[:100]
        )

        if result.returncode != 0:
            print(f"  Errors:\n{result.stdout[:500]}")

    except subprocess.TimeoutExpired:
        print_result("TypeScript compilation", False, "Timeout")
    except Exception as e:
        print_result("TypeScript compilation", False, str(e))


async def test_api_integration():
    """Test 6: Full API integration"""
    print_header("Test 6: Full API Integration")

    try:
        # Test TTS service integration
        from backend.tts_service import TTSService

        service = TTSService(default_provider="coqui")

        print_result(
            "TTS Service created with Coqui",
            service.get_current_provider() == "coqui",
            f"Provider: {service.get_current_provider()}"
        )

        # Get provider status
        status = await service.get_provider_status()
        coqui_status = next((s for s in status if s.get('provider') == 'coqui'), None)

        print_result(
            "Coqui provider status available",
            coqui_status is not None,
            f"Available: {coqui_status.get('available') if coqui_status else 'N/A'}"
        )

        if coqui_status:
            caps = coqui_status.get('capabilities', {})
            print_result(
                "Voice cloning capability reported",
                caps.get('voice_cloning', False),
                f"Supports: {caps.get('voice_cloning')}"
            )

            print_result(
                "Word timing capability reported",
                caps.get('word_timing', False),
                f"Supports: {caps.get('word_timing')}"
            )

            print_result(
                "Local processing confirmed",
                caps.get('is_local', False),
                "All processing is local"
            )

        # Test provider info
        info = service.get_provider_info()
        print_result(
            "Provider info available",
            'default_provider' in info,
            f"Default: {info.get('default_provider')}"
        )

    except Exception as e:
        print_result("API integration", False, str(e))
        import traceback
        traceback.print_exc()


def print_summary():
    """Print test summary"""
    print("\n")
    print("=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for p, _ in test_results.values() if p)
    failed = sum(1 for p, _ in test_results.values() if not p)
    total = len(test_results)

    print(f"\n  Total Tests: {total}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  Success Rate: {(passed/total)*100:.1f}%" if total > 0 else "  No tests run")

    if failed > 0:
        print("\n  Failed Tests:")
        for name, (passed, msg) in test_results.items():
            if not passed:
                print(f"    - {name}: {msg}")

    print("\n" + "=" * 70)

    return failed == 0


async def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " VOICE CLONING COMPREHENSIVE TEST SUITE ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        # Test 1: MPS detection
        await test_mps_detection()

        # Test 2: Voice sample upload
        sample_id = await test_voice_sample_upload()

        # Test 3: Voice sample management
        await test_voice_sample_management(sample_id)

        # Test 4: Voice cloning generation
        await test_voice_cloning_generation()

        # Test 5: Frontend compilation
        await test_frontend_compilation()

        # Test 6: API integration
        await test_api_integration()

    except Exception as e:
        print(f"\n❌ Critical error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

    return print_summary()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
