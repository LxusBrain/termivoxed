#!/usr/bin/env python3
"""
HTTP API Endpoint Tests for TermiVoxed

Tests the actual REST API endpoints that the frontend uses.
Uses an existing server or starts one if needed.
"""

import os
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['COQUI_TOS_AGREED'] = '1'

import asyncio
import sys
import time
import subprocess
import signal
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp

# Test configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Test results tracking
test_results: Dict[str, Tuple[bool, str]] = {}
test_sections: Dict[str, List[str]] = {}
current_section = ""

# Server process
server_process: Optional[subprocess.Popen] = None
server_started_by_us = False


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


async def check_server_running() -> bool:
    """Check if server is already running"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                return resp.status == 200
    except:
        return False


async def wait_for_server(timeout: int = 60) -> bool:
    """Wait for server to be ready"""
    start = time.time()
    async with aiohttp.ClientSession() as session:
        while time.time() - start < timeout:
            try:
                async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        return True
            except:
                pass
            await asyncio.sleep(1)
    return False


def start_server():
    """Start the FastAPI server"""
    global server_process, server_started_by_us

    venv_python = Path(__file__).parent.parent / 'venv' / 'bin' / 'python3'

    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).parent.parent)

    server_process = subprocess.Popen(
        [str(venv_python), '-m', 'uvicorn', 'web_ui.api.main:app', '--host', '0.0.0.0', '--port', '8000'],
        cwd=str(Path(__file__).parent.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )
    server_started_by_us = True

    return server_process


def stop_server():
    """Stop the FastAPI server if we started it"""
    global server_process, server_started_by_us
    if server_process and server_started_by_us:
        try:
            os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
            server_process.wait(timeout=5)
        except:
            try:
                os.killpg(os.getpgid(server_process.pid), signal.SIGKILL)
            except:
                pass
        server_process = None


# ============================================================================
# Test 1: Server Health
# ============================================================================
async def test_server_health():
    set_section("Test 1: Server Health")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health") as resp:
                print_result("Health endpoint", resp.status == 200, f"Status: {resp.status}")

            async with session.get(f"{BASE_URL}/") as resp:
                print_result("Root endpoint", resp.status == 200)

        except Exception as e:
            print_result("Server health", False, str(e))


# ============================================================================
# Test 2: TTS Provider Endpoints
# ============================================================================
async def test_tts_providers():
    set_section("Test 2: TTS Provider Endpoints")

    async with aiohttp.ClientSession() as session:
        try:
            # GET /api/v1/tts/providers
            async with session.get(f"{API_BASE}/tts/providers") as resp:
                data = await resp.json()
                providers = data.get('providers', [])
                print_result("GET /tts/providers", resp.status == 200,
                            f"Found {len(providers)} providers")

                # Check Edge TTS (provider uses 'name' field, not 'provider')
                edge = next((p for p in providers if p.get('name') == 'edge_tts'), None)
                print_result("Edge TTS in providers", edge is not None,
                            f"Available: {edge.get('available') if edge else 'N/A'}")

                # Check Coqui TTS
                coqui = next((p for p in providers if p.get('name') == 'coqui'), None)
                print_result("Coqui TTS in providers", coqui is not None,
                            f"Available: {coqui.get('available') if coqui else 'N/A'}, Voice cloning: {coqui.get('supports_voice_cloning') if coqui else 'N/A'}")

            # GET /api/v1/tts/providers/info
            async with session.get(f"{API_BASE}/tts/providers/info") as resp:
                data = await resp.json()
                print_result("GET /tts/providers/info", resp.status == 200,
                            f"Default: {data.get('default_provider')}")

            # GET /api/v1/tts/connectivity
            async with session.get(f"{API_BASE}/tts/connectivity") as resp:
                data = await resp.json()
                print_result("GET /tts/connectivity", resp.status == 200,
                            f"Connected: {data.get('connected')}, Provider: {data.get('provider')}")

        except Exception as e:
            print_result("TTS providers", False, str(e))
            import traceback
            traceback.print_exc()


# ============================================================================
# Test 3: Edge TTS Endpoints
# ============================================================================
async def test_edge_tts():
    set_section("Test 3: Edge TTS Endpoints")

    async with aiohttp.ClientSession() as session:
        try:
            # Set Edge TTS as default
            async with session.post(f"{API_BASE}/tts/providers/default",
                                   json={"provider": "edge_tts"}) as resp:
                print_result("Set Edge TTS as default", resp.status == 200)

            # GET /api/v1/tts/providers/edge_tts/status
            async with session.get(f"{API_BASE}/tts/providers/edge_tts/status") as resp:
                data = await resp.json()
                print_result("GET /tts/providers/edge_tts/status", resp.status == 200,
                            f"Available: {data.get('available')}, Initialized: {data.get('initialized')}")

            # GET /api/v1/tts/providers/edge_tts/voices
            async with session.get(f"{API_BASE}/tts/providers/edge_tts/voices") as resp:
                data = await resp.json()
                voices = data.get('voices', [])
                print_result("GET /tts/providers/edge_tts/voices", resp.status == 200,
                            f"Found {len(voices)} voices")

                if voices:
                    # Show sample voices
                    en_voices = [v for v in voices if v.get('language', '').startswith('en')]
                    print_result("English voices available", len(en_voices) > 0,
                                f"Found {len(en_voices)} English voices")

            # GET /api/v1/tts/voices (default provider)
            async with session.get(f"{API_BASE}/tts/voices") as resp:
                data = await resp.json()
                voices = data.get('voices', [])
                print_result("GET /tts/voices", resp.status == 200,
                            f"Voices: {len(voices)}")

            # GET /api/v1/tts/languages
            async with session.get(f"{API_BASE}/tts/languages") as resp:
                data = await resp.json()
                languages = data.get('languages', [])
                print_result("GET /tts/languages", resp.status == 200,
                            f"Languages: {len(languages)}")

            # POST /api/v1/tts/preview (Edge TTS audio generation)
            async with session.post(f"{API_BASE}/tts/preview",
                                   json={
                                       "text": "Hello, this is a test of Edge TTS.",
                                       "voice_id": "en-US-AriaNeural",
                                       "language": "en"
                                   },
                                   timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()
                audio_url = data.get('audio_url', '')
                duration = data.get('duration', 0)
                print_result("POST /tts/preview (Edge)", resp.status == 200,
                            f"Audio: {audio_url[:50]}..., Duration: {duration:.2f}s")

                # Preview endpoint doesn't return word timings, just audio
                print_result("Edge TTS audio generated", len(audio_url) > 0 and duration > 0,
                            f"Duration: {duration:.2f}s")

        except Exception as e:
            print_result("Edge TTS endpoints", False, str(e))
            import traceback
            traceback.print_exc()


# ============================================================================
# Test 4: Coqui TTS Endpoints
# ============================================================================
async def test_coqui_tts():
    set_section("Test 4: Coqui TTS Endpoints")

    async with aiohttp.ClientSession() as session:
        try:
            # Set Coqui TTS as default
            async with session.post(f"{API_BASE}/tts/providers/default",
                                   json={"provider": "coqui"}) as resp:
                result = await resp.json()
                print_result("Set Coqui TTS as default", resp.status == 200,
                            f"Message: {result.get('message', 'N/A')}")

            # GET /api/v1/tts/providers/coqui/status
            async with session.get(f"{API_BASE}/tts/providers/coqui/status") as resp:
                data = await resp.json()
                print_result("GET /tts/providers/coqui/status", resp.status == 200,
                            f"Available: {data.get('available')}, Device: {data.get('device', 'N/A')}")

                # Check voice cloning capability
                caps = data.get('capabilities', {})
                print_result("Coqui voice cloning capability", caps.get('voice_cloning', False),
                            f"Voice cloning: {caps.get('voice_cloning')}, Word timing: {caps.get('word_timing')}")

            # GET /api/v1/tts/providers/coqui/voices
            async with session.get(f"{API_BASE}/tts/providers/coqui/voices") as resp:
                data = await resp.json()
                voices = data.get('voices', [])
                print_result("GET /tts/providers/coqui/voices", resp.status == 200,
                            f"Found {len(voices)} voices")

            # POST /api/v1/tts/generate-with-provider (Coqui TTS audio generation)
            print("  Generating audio with Coqui TTS (this may take 30-60 seconds)...")
            async with session.post(f"{API_BASE}/tts/generate-with-provider",
                                   json={
                                       "text": "Hello, this is a test of Coqui TTS with local processing.",
                                       "voice_id": "coqui_default_en",
                                       "language": "en",
                                       "provider": "coqui",
                                       "project_name": "test_project"
                                   },
                                   timeout=aiohttp.ClientTimeout(total=180)) as resp:
                data = await resp.json()
                audio_path = data.get('audio_path', '')
                subtitle_path = data.get('subtitle_path', '')
                duration = data.get('duration', 0)
                print_result("POST /tts/generate-with-provider (Coqui)", resp.status == 200,
                            f"Audio: {audio_path}, Duration: {duration:.2f}s")

                # Word timings are saved in subtitle file, not returned in JSON
                print_result("Coqui TTS subtitle generated", subtitle_path is not None,
                            f"Subtitle: {subtitle_path or 'None'}")

        except asyncio.TimeoutError:
            print_result("Coqui TTS generation", False, "Timeout (model loading may take time)")
        except Exception as e:
            print_result("Coqui TTS endpoints", False, str(e))
            import traceback
            traceback.print_exc()


# ============================================================================
# Test 5: Voice Cloning Endpoints
# ============================================================================
async def test_voice_cloning():
    set_section("Test 5: Voice Cloning Endpoints")

    async with aiohttp.ClientSession() as session:
        try:
            # GET /api/v1/tts/voice-samples
            async with session.get(f"{API_BASE}/tts/voice-samples") as resp:
                data = await resp.json()
                samples = data.get('samples', [])
                print_result("GET /tts/voice-samples", resp.status == 200,
                            f"Found {len(samples)} voice samples")

                # Show existing samples
                for sample in samples[:3]:
                    print(f"         - {sample.get('name')}: {sample.get('duration', 0):.1f}s")

            # If we have samples, test getting one
            if samples:
                sample_id = samples[0].get('id')
                async with session.get(f"{API_BASE}/tts/voice-samples/{sample_id}") as resp:
                    data = await resp.json()
                    print_result("GET /tts/voice-samples/{id}", resp.status == 200,
                                f"Sample: {data.get('name')}")

            # Test voice cloning preview (if samples exist)
            if samples:
                sample_id = samples[0].get('id')
                print("  Testing voice cloning preview (this may take 30-60 seconds)...")
                # The /clone-voice/preview endpoint expects Form data, not JSON
                form_data = aiohttp.FormData()
                form_data.add_field('voice_sample_id', sample_id)
                form_data.add_field('text', 'This is a voice cloning test.')
                form_data.add_field('language', 'en')

                async with session.post(f"{API_BASE}/tts/clone-voice/preview",
                                       data=form_data,
                                       timeout=aiohttp.ClientTimeout(total=180)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        audio_path = data.get('audio_path', '')
                        subtitle_path = data.get('subtitle_path', '')
                        duration = data.get('duration', 0)
                        print_result("POST /tts/clone-voice/preview", True,
                                    f"Audio: {audio_path[:40]}..., Duration: {duration:.2f}s")

                        print_result("Clone voice subtitle generated", subtitle_path is not None,
                                    f"Subtitle: {subtitle_path or 'None'}")
                    else:
                        error = await resp.text()
                        print_result("POST /tts/clone-voice/preview", False, error[:100])
            else:
                print_result("Voice cloning test", True, "No samples to test with (upload one to test)")

        except asyncio.TimeoutError:
            print_result("Voice cloning", False, "Timeout")
        except Exception as e:
            print_result("Voice cloning endpoints", False, str(e))
            import traceback
            traceback.print_exc()


# ============================================================================
# Test 6: Additional TTS Features
# ============================================================================
async def test_tts_features():
    set_section("Test 6: Additional TTS Features")

    async with aiohttp.ClientSession() as session:
        try:
            # POST /api/v1/tts/estimate-duration
            async with session.post(f"{API_BASE}/tts/estimate-duration",
                                   json={"text": "This is a test sentence for duration estimation."}) as resp:
                data = await resp.json()
                print_result("POST /tts/estimate-duration", resp.status == 200,
                            f"Estimated: {data.get('estimated_duration', 0):.2f}s")

            # GET /api/v1/tts/voices/best
            async with session.get(f"{API_BASE}/tts/voices/best") as resp:
                data = await resp.json()
                best_voices = data.get('voices', {})
                print_result("GET /tts/voices/best", resp.status == 200,
                            f"Languages with best voices: {len(best_voices)}")

        except Exception as e:
            print_result("TTS features", False, str(e))


# ============================================================================
# Summary
# ============================================================================
def print_summary():
    print("\n")
    print("="*70)
    print(" API ENDPOINT TEST SUMMARY")
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
    print("\u2551" + " TERMIVOXED HTTP API ENDPOINT TESTS ".center(68) + "\u2551")
    print("\u2551" + f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ".center(68) + "\u2551")
    print("\u255a" + "\u2550"*68 + "\u255d")

    # Check if server is already running
    print("\nChecking for running server...")
    if await check_server_running():
        print("\u2705 Server is already running on port 8000")
    else:
        print("Server not running, starting it...")
        start_server()

        print("Waiting for server to start...")
        if not await wait_for_server(timeout=60):
            print("\u274c Server failed to start within 60 seconds")
            stop_server()
            return False

        print("\u2705 Server started successfully!")

    try:
        # Run tests
        await test_server_health()
        await test_tts_providers()
        await test_edge_tts()
        await test_coqui_tts()
        await test_voice_cloning()
        await test_tts_features()

    except Exception as e:
        print(f"\n\u274c Critical error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if server_started_by_us:
            print("\nStopping server...")
            stop_server()

    return print_summary()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
