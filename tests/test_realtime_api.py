#!/usr/bin/env python3
"""
Real-time API Integration Tests

Tests the actual backend server with real API calls.
Run with: python3 tests/test_realtime_api.py
"""

import requests
import json
import time
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000"

def print_result(test_name: str, success: bool, details: str = ""):
    """Print test result with formatting"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"       {details}")

def print_section(title: str):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


class RealTimeAPITest:
    """Real-time API tests against running server"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.generated_audio_path = None
        self.generated_subtitle_path = None

    def check_server(self) -> bool:
        """Check if server is running"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    # =========================================================================
    # Provider Tests
    # =========================================================================

    def test_get_providers(self):
        """Test GET /api/v1/tts/providers"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/providers")
            data = response.json()

            success = (
                response.status_code == 200 and
                "default_provider" in data and
                "providers" in data and
                len(data["providers"]) >= 2
            )

            details = f"Found {len(data['providers'])} providers, default: {data['default_provider']}"
            print_result("GET /api/v1/tts/providers", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/providers", False, str(e))
            self.failed += 1
            return False

    def test_get_provider_info(self):
        """Test GET /api/v1/tts/providers/info"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/providers/info")
            data = response.json()

            success = (
                response.status_code == 200 and
                "edge_tts" in data.get("providers", {}) and
                "coqui" in data.get("providers", {})
            )

            edge = data.get("providers", {}).get("edge_tts", {})
            coqui = data.get("providers", {}).get("coqui", {})

            details = f"edge_tts: local={edge.get('is_local')}, coqui: local={coqui.get('is_local')}"
            print_result("GET /api/v1/tts/providers/info", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/providers/info", False, str(e))
            self.failed += 1
            return False

    def test_edge_tts_status(self):
        """Test Edge TTS provider status"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/providers/edge_tts/status")
            data = response.json()

            success = (
                response.status_code == 200 and
                data.get("provider") == "edge_tts" and
                data.get("available") == True and
                data.get("capabilities", {}).get("word_timing") == True
            )

            details = f"available={data.get('available')}, word_timing={data.get('capabilities', {}).get('word_timing')}"
            print_result("GET /api/v1/tts/providers/edge_tts/status", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/providers/edge_tts/status", False, str(e))
            self.failed += 1
            return False

    def test_coqui_status(self):
        """Test Coqui TTS provider status"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/providers/coqui/status")
            data = response.json()

            # Coqui should report correctly even if not installed
            success = (
                response.status_code == 200 and
                data.get("provider") == "coqui" and
                data.get("capabilities", {}).get("is_local") == True and
                data.get("capabilities", {}).get("voice_cloning") == True
            )

            details = f"available={data.get('available')}, model_loaded={data.get('model_loaded')}"
            print_result("GET /api/v1/tts/providers/coqui/status", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/providers/coqui/status", False, str(e))
            self.failed += 1
            return False

    def test_invalid_provider(self):
        """Test invalid provider returns 400"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/providers/invalid_provider/status")

            success = response.status_code == 400
            details = f"Status code: {response.status_code}"
            print_result("Invalid provider returns 400", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("Invalid provider returns 400", False, str(e))
            self.failed += 1
            return False

    # =========================================================================
    # Voice Tests
    # =========================================================================

    def test_get_voices(self):
        """Test GET /api/v1/tts/voices"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/voices")
            data = response.json()

            success = (
                response.status_code == 200 and
                "voices" in data and
                data.get("total", 0) > 100  # Edge TTS has 300+ voices
            )

            details = f"Total voices: {data.get('total', 0)}"
            print_result("GET /api/v1/tts/voices", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/voices", False, str(e))
            self.failed += 1
            return False

    def test_get_voices_by_language(self):
        """Test voice filtering by language"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/voices", params={"language": "en"})
            data = response.json()

            # Check all voices are English
            all_english = all(
                v.get("language") == "en" or v.get("locale", "").startswith("en")
                for v in data.get("voices", [])
            )

            success = (
                response.status_code == 200 and
                data.get("total", 0) > 20 and
                all_english
            )

            details = f"English voices: {data.get('total', 0)}, all_english={all_english}"
            print_result("GET /api/v1/tts/voices?language=en", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/voices?language=en", False, str(e))
            self.failed += 1
            return False

    def test_get_best_voices(self):
        """Test GET /api/v1/tts/voices/best"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/voices/best")
            data = response.json()

            voices = data.get("voices", {})
            success = (
                response.status_code == 200 and
                "en" in voices and
                "es" in voices and
                "ja" in voices
            )

            details = f"Languages with best voices: {list(voices.keys())}"
            print_result("GET /api/v1/tts/voices/best", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/voices/best", False, str(e))
            self.failed += 1
            return False

    def test_get_languages(self):
        """Test GET /api/v1/tts/languages"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/languages")
            data = response.json()

            languages = data.get("languages", [])
            lang_codes = [l.get("code") for l in languages]

            success = (
                response.status_code == 200 and
                "en" in lang_codes and
                "hi" in lang_codes and
                "ta" in lang_codes  # Indian language support
            )

            details = f"Languages: {len(languages)}, includes: en, hi, ta"
            print_result("GET /api/v1/tts/languages", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/languages", False, str(e))
            self.failed += 1
            return False

    def test_provider_voices(self):
        """Test GET /api/v1/tts/providers/{provider}/voices"""
        try:
            response = requests.get(
                f"{BASE_URL}/api/v1/tts/providers/edge_tts/voices",
                params={"language": "en"}
            )
            data = response.json()

            voices = data.get("voices", [])
            all_have_provider = all(v.get("provider") == "edge_tts" for v in voices)

            success = (
                response.status_code == 200 and
                data.get("provider") == "edge_tts" and
                len(voices) > 20 and
                all_have_provider
            )

            details = f"Provider: {data.get('provider')}, voices: {len(voices)}"
            print_result("GET /api/v1/tts/providers/edge_tts/voices", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/providers/edge_tts/voices", False, str(e))
            self.failed += 1
            return False

    # =========================================================================
    # TTS Generation Tests
    # =========================================================================

    def test_estimate_duration(self):
        """Test POST /api/v1/tts/estimate-duration"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/tts/estimate-duration",
                json={
                    "text": "Hello world, this is a test sentence for duration estimation.",
                    "language": "en"
                }
            )
            data = response.json()

            success = (
                response.status_code == 200 and
                data.get("word_count") == 10 and  # "Hello world, this is a test sentence for duration estimation."
                data.get("estimated_duration", 0) > 0
            )

            details = f"words={data.get('word_count')}, duration={data.get('estimated_duration')}s"
            print_result("POST /api/v1/tts/estimate-duration", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("POST /api/v1/tts/estimate-duration", False, str(e))
            self.failed += 1
            return False

    def test_generate_tts(self):
        """Test POST /api/v1/tts/generate - ACTUAL AUDIO GENERATION"""
        try:
            print("       Generating audio with Edge TTS (this may take a few seconds)...")

            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/api/v1/tts/generate",
                json={
                    "text": "Hello! This is a real-time test of the TermiVoxed text to speech system. We are testing the multi-provider architecture with Microsoft Edge TTS.",
                    "language": "en",
                    "voice_id": "en-US-AvaMultilingualNeural",
                    "project_name": "_realtime_test",
                    "segment_name": "test_segment_001",
                    "rate": "+0%",
                    "volume": "+0%",
                    "pitch": "+0Hz",
                    "orientation": "horizontal"
                },
                timeout=60
            )
            elapsed = time.time() - start_time
            data = response.json()

            audio_path = data.get("audio_path", "")
            subtitle_path = data.get("subtitle_path", "")
            duration = data.get("duration", 0)

            # Store paths for later verification
            self.generated_audio_path = audio_path
            self.generated_subtitle_path = subtitle_path

            success = (
                response.status_code == 200 and
                audio_path and
                audio_path.endswith(".mp3") and
                duration > 0
            )

            details = f"duration={duration:.2f}s, generated in {elapsed:.2f}s, cached={data.get('cached')}"
            print_result("POST /api/v1/tts/generate (Edge TTS)", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
                print(f"       Response: {data}")
            return success
        except Exception as e:
            print_result("POST /api/v1/tts/generate (Edge TTS)", False, str(e))
            self.failed += 1
            return False

    def test_verify_audio_file(self):
        """Verify the generated audio file exists and is valid"""
        try:
            if not self.generated_audio_path:
                print_result("Verify audio file exists", False, "No audio path from previous test")
                self.failed += 1
                return False

            # The path is relative to project root
            full_path = Path("/Users/santhu/Downloads/SubsGen2/console_video_editor") / self.generated_audio_path.lstrip("/")

            exists = full_path.exists()
            size = full_path.stat().st_size if exists else 0

            success = exists and size > 1000  # At least 1KB

            details = f"path={full_path.name}, size={size} bytes"
            print_result("Verify audio file exists", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("Verify audio file exists", False, str(e))
            self.failed += 1
            return False

    def test_verify_subtitle_file(self):
        """Verify the generated subtitle file exists and is valid SRT"""
        try:
            if not self.generated_subtitle_path:
                print_result("Verify subtitle file (SRT)", False, "No subtitle path from previous test")
                self.failed += 1
                return False

            full_path = Path("/Users/santhu/Downloads/SubsGen2/console_video_editor") / self.generated_subtitle_path.lstrip("/")

            exists = full_path.exists()

            if exists:
                content = full_path.read_text()
                # Check SRT format: should have timestamps like 00:00:00,000 --> 00:00:00,000
                has_timestamps = "-->" in content
                has_numbers = content.strip().split("\n")[0].isdigit() if content.strip() else False

                success = has_timestamps and has_numbers
                details = f"path={full_path.name}, has_timestamps={has_timestamps}, valid_format={has_numbers}"
            else:
                success = False
                details = "File does not exist"

            print_result("Verify subtitle file (SRT)", success, details)

            if success:
                self.passed += 1
                # Print first few lines of SRT
                print("       SRT content (first 10 lines):")
                for line in content.split("\n")[:10]:
                    print(f"         {line}")
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("Verify subtitle file (SRT)", False, str(e))
            self.failed += 1
            return False

    def test_generate_hindi_tts(self):
        """Test TTS generation in Hindi"""
        try:
            print("       Generating Hindi audio...")

            response = requests.post(
                f"{BASE_URL}/api/v1/tts/generate",
                json={
                    "text": "नमस्ते! यह हिंदी में टेक्स्ट टू स्पीच टेस्ट है।",
                    "language": "hi",
                    "voice_id": "hi-IN-MadhurNeural",
                    "project_name": "_realtime_test",
                    "segment_name": "test_hindi_001",
                    "rate": "+0%",
                    "volume": "+0%",
                    "pitch": "+0Hz",
                    "orientation": "horizontal"
                },
                timeout=60
            )
            data = response.json()

            success = (
                response.status_code == 200 and
                data.get("audio_path", "").endswith(".mp3") and
                data.get("duration", 0) > 0
            )

            details = f"duration={data.get('duration', 0):.2f}s"
            print_result("POST /api/v1/tts/generate (Hindi)", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("POST /api/v1/tts/generate (Hindi)", False, str(e))
            self.failed += 1
            return False

    def test_generate_japanese_tts(self):
        """Test TTS generation in Japanese"""
        try:
            print("       Generating Japanese audio...")

            response = requests.post(
                f"{BASE_URL}/api/v1/tts/generate",
                json={
                    "text": "こんにちは！これは日本語のテキスト読み上げテストです。",
                    "language": "ja",
                    "voice_id": "ja-JP-NanamiNeural",
                    "project_name": "_realtime_test",
                    "segment_name": "test_japanese_001",
                    "rate": "+0%",
                    "volume": "+0%",
                    "pitch": "+0Hz",
                    "orientation": "horizontal"
                },
                timeout=60
            )
            data = response.json()

            success = (
                response.status_code == 200 and
                data.get("audio_path", "").endswith(".mp3") and
                data.get("duration", 0) > 0
            )

            details = f"duration={data.get('duration', 0):.2f}s"
            print_result("POST /api/v1/tts/generate (Japanese)", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("POST /api/v1/tts/generate (Japanese)", False, str(e))
            self.failed += 1
            return False

    def test_voice_preview(self):
        """Test POST /api/v1/tts/preview"""
        try:
            print("       Generating voice preview...")

            response = requests.post(
                f"{BASE_URL}/api/v1/tts/preview",
                json={
                    "voice_id": "en-US-JennyNeural",
                    "text": "This is a voice preview test.",
                    "rate": "+0%",
                    "volume": "+0%",
                    "pitch": "+0Hz"
                },
                timeout=60
            )
            data = response.json()

            success = (
                response.status_code == 200 and
                data.get("audio_url") and
                data.get("duration", 0) > 0
            )

            details = f"audio_url={data.get('audio_url', 'N/A')[:50]}..., duration={data.get('duration', 0):.2f}s"
            print_result("POST /api/v1/tts/preview", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("POST /api/v1/tts/preview", False, str(e))
            self.failed += 1
            return False

    # =========================================================================
    # Connectivity & Consent Tests
    # =========================================================================

    def test_connectivity(self):
        """Test GET /api/v1/tts/connectivity"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/tts/connectivity", timeout=30)
            data = response.json()

            success = (
                response.status_code == 200 and
                "proxy_enabled" in data and
                "direct_connection" in data
            )

            details = f"proxy_enabled={data.get('proxy_enabled')}, direct={data.get('direct_connection')}"
            print_result("GET /api/v1/tts/connectivity", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/tts/connectivity", False, str(e))
            self.failed += 1
            return False

    def test_consent_status(self):
        """Test GET /api/v1/consent/tts/status"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/consent/tts/status")
            data = response.json()

            success = (
                response.status_code == 200 and
                "has_consent" in data and
                "needs_consent" in data and
                "status" in data
            )

            details = f"has_consent={data.get('has_consent')}, needs_consent={data.get('needs_consent')}"
            print_result("GET /api/v1/consent/tts/status", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/consent/tts/status", False, str(e))
            self.failed += 1
            return False

    def test_consent_record(self):
        """Test POST /api/v1/consent/tts/record"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/consent/tts/record",
                json={
                    "granted": True,
                    "remember_choice": True
                }
            )
            data = response.json()

            success = (
                response.status_code == 200 and
                data.get("success") == True
            )

            details = f"success={data.get('success')}"
            print_result("POST /api/v1/consent/tts/record", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("POST /api/v1/consent/tts/record", False, str(e))
            self.failed += 1
            return False

    def test_consent_dialog_content(self):
        """Test GET /api/v1/consent/tts/dialog-content"""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/consent/tts/dialog-content")
            data = response.json()

            success = (
                response.status_code == 200 and
                "title" in data and
                "details" in data
            )

            details = f"title={data.get('title', 'N/A')[:40]}..."
            print_result("GET /api/v1/consent/tts/dialog-content", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("GET /api/v1/consent/tts/dialog-content", False, str(e))
            self.failed += 1
            return False

    # =========================================================================
    # Provider Switching Tests
    # =========================================================================

    def test_set_default_provider(self):
        """Test POST /api/v1/tts/providers/default"""
        try:
            # Set to edge_tts
            response = requests.post(
                f"{BASE_URL}/api/v1/tts/providers/default",
                json={"provider": "edge_tts"}
            )
            data = response.json()

            success = (
                response.status_code == 200 and
                data.get("success") == True and
                data.get("default_provider") == "edge_tts"
            )

            details = f"success={data.get('success')}, default={data.get('default_provider')}"
            print_result("POST /api/v1/tts/providers/default (edge_tts)", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("POST /api/v1/tts/providers/default", False, str(e))
            self.failed += 1
            return False

    def test_set_invalid_provider(self):
        """Test setting invalid provider returns 400"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/tts/providers/default",
                json={"provider": "invalid_provider"}
            )

            success = response.status_code == 400

            details = f"status_code={response.status_code}"
            print_result("POST /api/v1/tts/providers/default (invalid)", success, details)

            if success:
                self.passed += 1
            else:
                self.failed += 1
            return success
        except Exception as e:
            print_result("POST /api/v1/tts/providers/default (invalid)", False, str(e))
            self.failed += 1
            return False

    # =========================================================================
    # Run All Tests
    # =========================================================================

    def run_all(self):
        """Run all tests"""
        print("\n" + "="*60)
        print("  TERMIVOXED REAL-TIME API TESTS")
        print("="*60)

        # Check server
        print("\nChecking server...")
        if not self.check_server():
            print("❌ Server is not running at http://localhost:8000")
            print("   Please start the server with: python web_ui/api/main.py")
            return False
        print("✅ Server is running\n")

        # Provider Tests
        print_section("PROVIDER ENDPOINTS")
        self.test_get_providers()
        self.test_get_provider_info()
        self.test_edge_tts_status()
        self.test_coqui_status()
        self.test_invalid_provider()

        # Voice Tests
        print_section("VOICE ENDPOINTS")
        self.test_get_voices()
        self.test_get_voices_by_language()
        self.test_get_best_voices()
        self.test_get_languages()
        self.test_provider_voices()

        # Generation Tests
        print_section("TTS GENERATION (REAL AUDIO)")
        self.test_estimate_duration()
        self.test_generate_tts()
        self.test_verify_audio_file()
        self.test_verify_subtitle_file()
        self.test_generate_hindi_tts()
        self.test_generate_japanese_tts()
        self.test_voice_preview()

        # Connectivity & Consent
        print_section("CONNECTIVITY & CONSENT")
        self.test_connectivity()
        self.test_consent_status()
        self.test_consent_record()
        self.test_consent_dialog_content()

        # Provider Switching
        print_section("PROVIDER SWITCHING")
        self.test_set_default_provider()
        self.test_set_invalid_provider()

        # Summary
        print("\n" + "="*60)
        print("  TEST SUMMARY")
        print("="*60)
        total = self.passed + self.failed
        print(f"\n  Total:  {total} tests")
        print(f"  Passed: {self.passed} ✅")
        print(f"  Failed: {self.failed} ❌")
        print(f"  Rate:   {(self.passed/total*100):.1f}%")
        print("="*60 + "\n")

        return self.failed == 0


if __name__ == "__main__":
    tester = RealTimeAPITest()
    success = tester.run_all()
    sys.exit(0 if success else 1)
