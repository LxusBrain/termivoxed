#!/usr/bin/env python3
"""
Simple test for voice cloning with a real audio sample.
"""

# CRITICAL: Set MPS fallback before ANY imports
import os
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['COQUI_TOS_AGREED'] = '1'

import asyncio
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_voice_cloning():
    """Test voice cloning with Coqui TTS"""
    print("=" * 60)
    print("Voice Cloning Test")
    print("=" * 60)

    from backend.tts_providers.coqui_provider import CoquiTTSProvider

    # Check installation
    info = CoquiTTSProvider.check_installation()
    print(f"\nInstallation:")
    print(f"  Coqui TTS: {info.get('version', 'not installed')}")
    print(f"  PyTorch: {info.get('torch_version', 'not installed')}")
    print(f"  MPS available: {info.get('mps_available', False)}")
    print(f"  Recommended device: {info.get('recommended_device', 'cpu')}")

    # Check torchaudio (no longer need torchcodec with 2.5.x)
    try:
        import torchaudio
        print(f"  torchaudio: {torchaudio.__version__}")
    except ImportError:
        print(f"  torchaudio: NOT INSTALLED - voice cloning will fail!")
        return False

    # Create test directory
    test_dir = Path("storage/test_clone")
    test_dir.mkdir(parents=True, exist_ok=True)

    # We need a real audio file for voice cloning
    # Let's use TTS to generate a sample first
    print("\n1. Generating voice sample using standard TTS...")

    provider = CoquiTTSProvider(config={"use_gpu": True})
    await provider.initialize()

    sample_path = test_dir / "voice_sample.wav"

    # Generate a sample with standard TTS
    result = await provider.generate_audio(
        text="Hello, my name is John and I am creating a voice sample for cloning.",
        voice_id="coqui_default_en",
        output_path=sample_path,
        language="en"
    )

    print(f"   Generated sample: {sample_path}")
    print(f"   Duration: {result.duration_seconds:.2f}s")

    # Now test voice cloning with this sample
    print("\n2. Testing voice cloning with the generated sample...")

    clone_output = test_dir / "cloned_output.wav"
    test_text = "This is a test of voice cloning. The cloned voice should sound similar to the original."

    try:
        clone_result = await provider.clone_voice(
            audio_sample_path=sample_path,
            text=test_text,
            output_path=clone_output,
            language="en",
            voice_sample_name="Test Sample"
        )

        print(f"\n   ✅ Voice cloning successful!")
        print(f"   Output: {clone_result.audio_path}")
        print(f"   Duration: {clone_result.duration_seconds:.2f}s")
        print(f"   Word timings: {len(clone_result.word_timings)} words")
        print(f"   Timing type: {clone_result.metadata.get('timing_type', 'N/A')}")

        if clone_result.word_timings:
            print("\n   Sample word timings:")
            for wt in clone_result.word_timings[:5]:
                print(f"     '{wt.text}' at {wt.offset_ms}ms")

        success = True

    except Exception as e:
        print(f"\n   ❌ Voice cloning failed: {e}")
        import traceback
        traceback.print_exc()
        success = False

    # Cleanup
    print("\n3. Cleaning up test files...")
    shutil.rmtree(test_dir)
    print("   Done!")

    return success


if __name__ == "__main__":
    success = asyncio.run(test_voice_cloning())
    print("\n" + "=" * 60)
    print("RESULT:", "✅ PASSED" if success else "❌ FAILED")
    print("=" * 60)
    sys.exit(0 if success else 1)
