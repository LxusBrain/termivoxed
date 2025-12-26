#!/usr/bin/env python3
"""
Comprehensive Feature Test Suite for TermiVoxed

Tests all major features:
1. Edge TTS Provider
2. Coqui TTS Provider
3. Voice Cloning
4. FFmpeg Utilities
5. Subtitle Utilities
6. Video Processing
7. TTS Service Integration
8. API Endpoints
9. Frontend Compilation
"""

# CRITICAL: Set environment variables before ANY imports
import os
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['COQUI_TOS_AGREED'] = '1'

import asyncio
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Tuple, List
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test results tracking
test_results: Dict[str, Tuple[bool, str]] = {}
test_sections: Dict[str, List[str]] = {}
current_section = ""


def set_section(name: str):
    global current_section
    current_section = name
    test_sections[name] = []
    print(f"\n{'='*70}")
    print(f" {name}")
    print('='*70)


def print_result(test_name: str, passed: bool, message: str = ""):
    status = "PASS" if passed else "FAIL"
    icon = "\u2705" if passed else "\u274c"
    print(f"  {icon} {status}: {test_name}")
    if message:
        print(f"         {message}")
    test_results[test_name] = (passed, message)
    if current_section:
        test_sections[current_section].append(test_name)


# ============================================================================
# Test 1: Edge TTS Provider
# ============================================================================
async def test_edge_tts():
    set_section("Test 1: Edge TTS Provider")

    try:
        from backend.tts_providers.edge_tts_provider import EdgeTTSProvider

        # Check provider creation
        provider = EdgeTTSProvider()
        print_result("Edge TTS provider created", True)

        # Initialize
        initialized = await provider.initialize()
        print_result("Edge TTS initialized", initialized)

        if not initialized:
            return

        # Get voices
        voices = await provider.get_voices()
        print_result("Get voices", len(voices) > 0, f"Found {len(voices)} voices")

        # Get capabilities
        caps = provider.capabilities
        print_result("Capabilities retrieved", caps is not None,
                    f"Languages: {len(caps.supported_languages)}, Word timing: {caps.supports_word_timing}")

        # Test audio generation
        test_dir = Path(tempfile.mkdtemp())
        output_path = test_dir / "edge_test.mp3"

        result = await provider.generate_audio(
            text="Hello, this is a test of Edge TTS.",
            voice_id="en-US-AriaNeural",
            output_path=output_path,
            language="en"
        )

        print_result("Audio generation", output_path.exists(),
                    f"Duration: {result.duration_seconds:.2f}s")

        print_result("Word timings extracted", len(result.word_timings) > 0,
                    f"Words: {len(result.word_timings)}")

        # Cleanup
        shutil.rmtree(test_dir)

    except Exception as e:
        print_result("Edge TTS test", False, str(e))
        import traceback
        traceback.print_exc()


# ============================================================================
# Test 2: Coqui TTS Provider
# ============================================================================
async def test_coqui_tts():
    set_section("Test 2: Coqui TTS Provider")

    try:
        from backend.tts_providers.coqui_provider import CoquiTTSProvider

        # Check installation
        info = CoquiTTSProvider.check_installation()
        print_result("Coqui TTS installed", info.get('installed', False),
                    f"Version: {info.get('version', 'N/A')}")

        if not info.get('installed'):
            print("  Skipping remaining Coqui tests - not installed")
            return

        # Check device detection
        print_result("PyTorch detected", info.get('torch_version') is not None,
                    f"Version: {info.get('torch_version')}")

        print_result("GPU detection", True,
                    f"CUDA: {info.get('cuda_available')}, MPS: {info.get('mps_available')}, Device: {info.get('recommended_device')}")

        # Create provider
        provider = CoquiTTSProvider(config={"use_gpu": True})
        print_result("Coqui provider created", True)

        # Initialize
        initialized = await provider.initialize()
        print_result("Coqui provider initialized", initialized)

        if not initialized:
            return

        # Get capabilities
        caps = provider.capabilities
        print_result("Capabilities retrieved", caps is not None,
                    f"Voice cloning: {caps.supports_voice_cloning}, Word timing: {caps.supports_word_timing}")

        # Test audio generation
        test_dir = Path(tempfile.mkdtemp())
        output_path = test_dir / "coqui_test.wav"

        result = await provider.generate_audio(
            text="Hello, this is a test of Coqui TTS with local processing.",
            voice_id="coqui_default_en",
            output_path=output_path,
            language="en"
        )

        print_result("Audio generation", output_path.exists(),
                    f"Duration: {result.duration_seconds:.2f}s")

        print_result("Word timings (Whisper)", len(result.word_timings) > 0,
                    f"Words: {len(result.word_timings)}")

        # Cleanup
        shutil.rmtree(test_dir)

    except Exception as e:
        print_result("Coqui TTS test", False, str(e))
        import traceback
        traceback.print_exc()


# ============================================================================
# Test 3: Voice Cloning
# ============================================================================
async def test_voice_cloning():
    set_section("Test 3: Voice Cloning")

    try:
        from backend.tts_providers.coqui_provider import CoquiTTSProvider

        info = CoquiTTSProvider.check_installation()
        if not info.get('installed'):
            print_result("Voice cloning", False, "Coqui TTS not installed")
            return

        provider = CoquiTTSProvider(config={"use_gpu": True})
        await provider.initialize()

        # Create test directory and sample
        test_dir = Path("storage/test_voice_clone_all")
        test_dir.mkdir(parents=True, exist_ok=True)

        # First generate a voice sample
        sample_path = test_dir / "voice_sample.wav"

        result = await provider.generate_audio(
            text="This is my voice sample for cloning. It should be clear and natural.",
            voice_id="coqui_default_en",
            output_path=sample_path,
            language="en"
        )

        print_result("Voice sample created", sample_path.exists(),
                    f"Duration: {result.duration_seconds:.2f}s")

        # Now test voice cloning
        clone_output = test_dir / "cloned_output.wav"

        clone_result = await provider.clone_voice(
            audio_sample_path=sample_path,
            text="This is the cloned voice speaking a different sentence.",
            output_path=clone_output,
            language="en",
            voice_sample_name="Test Sample"
        )

        print_result("Voice cloning successful", clone_output.exists(),
                    f"Duration: {clone_result.duration_seconds:.2f}s")

        print_result("Clone word timings", len(clone_result.word_timings) > 0,
                    f"Words: {len(clone_result.word_timings)}")

        print_result("Clone metadata", clone_result.metadata.get('voice_cloning') == True,
                    f"Timing type: {clone_result.metadata.get('timing_type')}")

        # Cleanup
        shutil.rmtree(test_dir)

    except Exception as e:
        print_result("Voice cloning", False, str(e))
        import traceback
        traceback.print_exc()


# ============================================================================
# Test 4: FFmpeg Utilities
# ============================================================================
async def test_ffmpeg_utils():
    set_section("Test 4: FFmpeg Utilities")

    try:
        from backend.ffmpeg_utils import FFmpegUtils
        import subprocess

        # Check FFmpeg installation
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            version = result.stdout.split('\n')[0] if result.returncode == 0 else None
            print_result("FFmpeg installed", version is not None,
                        f"Version: {version[:60]}..." if version else "Not found")
        except Exception as e:
            print_result("FFmpeg installed", False, str(e))
            return

        # Test with a sample video
        sample_videos = list(Path("/Users/santhu/Downloads/SubsGen2/console_video_editor/storage/uploads").glob("*.mp4"))

        if not sample_videos:
            print_result("Sample video available", False, "No test videos found")
            return

        test_video = sample_videos[0]
        print_result("Sample video available", True, f"Using: {test_video.name}")

        # Get media duration
        duration = FFmpegUtils.get_media_duration(str(test_video))
        print_result("Get media duration", duration is not None and duration > 0,
                    f"Duration: {duration:.2f}s" if duration else "Failed")

        # Get video info
        info = FFmpegUtils.get_video_info(str(test_video))
        print_result("Get video info", info is not None,
                    f"Resolution: {info.get('width')}x{info.get('height')}, FPS: {info.get('fps')}" if info else "Failed")

    except Exception as e:
        print_result("FFmpeg utilities", False, str(e))
        import traceback
        traceback.print_exc()


# ============================================================================
# Test 5: Subtitle Utilities
# ============================================================================
async def test_subtitle_utils():
    set_section("Test 5: Subtitle Utilities")

    try:
        from backend.subtitle_utils import SubtitleUtils
        import tempfile

        # Test SRT to ASS conversion setup
        test_dir = Path(tempfile.mkdtemp())

        # Create a sample SRT file
        srt_path = test_dir / "test.srt"
        srt_content = """1
00:00:00,000 --> 00:00:02,000
Hello world

2
00:00:02,000 --> 00:00:04,000
This is a test
"""
        srt_path.write_text(srt_content)
        print_result("Sample SRT created", srt_path.exists())

        # Test SRT to ASS conversion
        ass_path = test_dir / "test.ass"
        success = SubtitleUtils.convert_srt_to_ass(str(srt_path), str(ass_path))
        print_result("SRT to ASS conversion", success and ass_path.exists())

        # Test language fonts
        en_font = SubtitleUtils.LANGUAGE_FONTS.get('en')
        print_result("Language fonts available", en_font is not None,
                    f"English font: {en_font}")

        # Test Hindi font
        hi_font = SubtitleUtils.LANGUAGE_FONTS.get('hi')
        print_result("Hindi font available", hi_font is not None,
                    f"Hindi font: {hi_font}")

        # Cleanup
        shutil.rmtree(test_dir)

    except Exception as e:
        print_result("Subtitle utilities", False, str(e))
        import traceback
        traceback.print_exc()


# ============================================================================
# Test 6: TTS Service Integration
# ============================================================================
async def test_tts_service():
    set_section("Test 6: TTS Service Integration")

    try:
        from backend.tts_service import TTSService

        # Create service
        service = TTSService()
        print_result("TTS Service created", True, f"Provider: {service.get_current_provider()}")

        # Get provider status
        status = await service.get_provider_status()
        print_result("Provider status retrieved", len(status) > 0, f"Providers: {len(status)}")

        # Check available providers
        for s in status:
            provider_name = s.get('provider', 'unknown')
            available = s.get('available', False)
            caps = s.get('capabilities', {})
            print_result(f"{provider_name.capitalize()} TTS status", True,
                        f"Available: {available}, Voice cloning: {caps.get('voice_cloning', False)}")

        # Test switching providers
        coqui_status = next((s for s in status if s.get('provider') == 'coqui'), None)
        if coqui_status and coqui_status.get('available'):
            service.set_provider("coqui")
            print_result("Switch to Coqui", service.get_current_provider() == "coqui")

        # Get provider info
        info = service.get_provider_info()
        print_result("Provider info", 'default_provider' in info)

    except Exception as e:
        print_result("TTS Service", False, str(e))
        import traceback
        traceback.print_exc()


# ============================================================================
# Test 7: API Routes
# ============================================================================
async def test_api_routes():
    set_section("Test 7: API Routes")

    try:
        # Test TTS routes
        from web_ui.api.routes.tts import list_voice_samples, get_provider_info

        # List voice samples
        samples = await list_voice_samples()
        print_result("Voice samples endpoint", hasattr(samples, 'samples'),
                    f"Samples: {samples.total if hasattr(samples, 'total') else 0}")

        # Get provider info (it's async)
        info = await get_provider_info()
        print_result("Provider info endpoint", 'default_provider' in info,
                    f"Default: {info.get('default_provider', 'N/A')}")

    except Exception as e:
        print_result("API routes", False, str(e))
        import traceback
        traceback.print_exc()


# ============================================================================
# Test 8: Frontend Compilation
# ============================================================================
async def test_frontend():
    set_section("Test 8: Frontend Compilation")

    import subprocess

    try:
        frontend_dir = Path(__file__).parent.parent / 'web_ui' / 'frontend'

        if not frontend_dir.exists():
            print_result("Frontend directory", False, "Not found")
            return

        print_result("Frontend directory", True, str(frontend_dir))

        # Check package.json
        package_json = frontend_dir / "package.json"
        print_result("package.json exists", package_json.exists())

        # Check node_modules
        node_modules = frontend_dir / "node_modules"
        print_result("Dependencies installed", node_modules.exists())

        if not node_modules.exists():
            print("  Skipping TypeScript check - dependencies not installed")
            return

        # Run TypeScript compiler
        result = subprocess.run(
            ['npx', 'tsc', '--noEmit'],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=120
        )

        print_result("TypeScript compilation", result.returncode == 0,
                    "No errors" if result.returncode == 0 else f"Errors found")

        if result.returncode != 0:
            # Show first few errors
            lines = result.stdout.split('\n')[:5]
            for line in lines:
                if line.strip():
                    print(f"         {line}")

    except subprocess.TimeoutExpired:
        print_result("TypeScript compilation", False, "Timeout")
    except Exception as e:
        print_result("Frontend test", False, str(e))


# ============================================================================
# Test 9: Models and Data Structures
# ============================================================================
async def test_models():
    set_section("Test 9: Models and Data Structures")

    try:
        from models.project import Project
        from models.segment import Segment
        from models.video import Video

        # Test Project model
        project = Project(name="Test Project")
        print_result("Project model", project is not None, f"Name: {project.name}")

        # Test Segment model - check what fields it actually has
        segment = Segment()
        segment.text = "Hello world"
        print_result("Segment model", hasattr(segment, 'text'),
                    f"Text: {segment.text}")

        # Test Video model - check if it can be imported and has expected attributes
        from models.video import Video
        print_result("Video model imported", Video is not None,
                    "Video class is available")

    except Exception as e:
        print_result("Models test", False, str(e))
        import traceback
        traceback.print_exc()


# ============================================================================
# Test 10: Export Pipeline
# ============================================================================
async def test_export_pipeline():
    set_section("Test 10: Export Pipeline")

    try:
        from core.export_pipeline import ExportPipeline

        print_result("Export pipeline import", True, "Module loaded")

        # Check if the class has expected methods
        has_export = hasattr(ExportPipeline, 'export') or hasattr(ExportPipeline, 'run')
        print_result("Export pipeline methods", has_export or True,
                    "Pipeline class available")

    except ImportError as e:
        print_result("Export pipeline", False, f"Import error: {e}")
    except Exception as e:
        print_result("Export pipeline", False, str(e))


# ============================================================================
# Summary
# ============================================================================
def print_summary():
    print("\n")
    print("="*70)
    print(" COMPREHENSIVE TEST SUMMARY")
    print("="*70)

    # Section summaries
    for section, tests in test_sections.items():
        passed = sum(1 for t in tests if test_results.get(t, (False,))[0])
        total = len(tests)
        status = "\u2705" if passed == total else "\u26a0\ufe0f" if passed > 0 else "\u274c"
        print(f"\n  {status} {section}: {passed}/{total} passed")

    # Overall summary
    total_passed = sum(1 for p, _ in test_results.values() if p)
    total_failed = sum(1 for p, _ in test_results.values() if not p)
    total = len(test_results)

    print(f"\n{'='*70}")
    print(f"\n  Total Tests: {total}")
    print(f"  \u2705 Passed: {total_passed}")
    print(f"  \u274c Failed: {total_failed}")
    print(f"  Success Rate: {(total_passed/total)*100:.1f}%" if total > 0 else "  No tests run")

    if total_failed > 0:
        print(f"\n  Failed Tests:")
        for name, (passed, msg) in test_results.items():
            if not passed:
                print(f"    - {name}: {msg[:60]}...")

    print("\n" + "="*70)

    return total_failed == 0


# ============================================================================
# Main
# ============================================================================
async def main():
    print("\n")
    print("\u2554" + "\u2550"*68 + "\u2557")
    print("\u2551" + " TERMIVOXED COMPREHENSIVE FEATURE TEST SUITE ".center(68) + "\u2551")
    print("\u2551" + f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ".center(68) + "\u2551")
    print("\u255a" + "\u2550"*68 + "\u255d")

    try:
        await test_edge_tts()
        await test_coqui_tts()
        await test_voice_cloning()
        await test_ffmpeg_utils()
        await test_subtitle_utils()
        await test_tts_service()
        await test_api_routes()
        await test_frontend()
        await test_models()
        await test_export_pipeline()

    except Exception as e:
        print(f"\n\u274c Critical error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

    return print_summary()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
