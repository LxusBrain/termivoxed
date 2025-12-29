#!/usr/bin/env python3
"""
Comprehensive TTS Provider Tests

Tests for the multi-provider TTS system including:
- Provider base class and data structures
- Edge TTS provider (cloud)
- Coqui TTS provider (local)
- Provider registry and selection
- Fallback mechanisms

Author: TermiVoxed Team
"""

import pytest
import asyncio
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import asdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.tts_providers.base import (
    TTSProvider,
    TTSProviderType,
    TTSResult,
    TTSCapabilities,
    TTSVoice,
    WordTiming,
    StreamChunk,
    ProviderNotAvailableError,
    ProviderConfigError,
)
from backend.tts_providers.edge_tts_provider import EdgeTTSProvider
from backend.tts_providers.coqui_provider import CoquiTTSProvider
from backend.tts_providers.registry import (
    TTSProviderRegistry,
    get_registry,
    get_provider,
    get_default_provider,
    set_default_provider,
)


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

EPSILON = 0.001


def assert_close(actual, expected, msg=""):
    """Assert two values are close within tolerance"""
    assert abs(actual - expected) < EPSILON, f"{msg}: Expected {expected}, got {actual}"


# ============================================================================
# BASE CLASS TESTS
# ============================================================================

class TestTTSProviderType:
    """Tests for TTSProviderType enum"""

    def test_provider_types_exist(self):
        """Test that all expected provider types exist"""
        assert TTSProviderType.EDGE_TTS.value == "edge_tts"
        assert TTSProviderType.COQUI.value == "coqui"
        assert TTSProviderType.PIPER.value == "piper"

    def test_provider_type_string_conversion(self):
        """Test string conversion of provider types"""
        assert str(TTSProviderType.EDGE_TTS) == "TTSProviderType.EDGE_TTS"
        assert TTSProviderType.EDGE_TTS.value == "edge_tts"


class TestTTSVoice:
    """Tests for TTSVoice data class"""

    def test_voice_creation(self):
        """Test creating a voice object"""
        voice = TTSVoice(
            id="en-US-AvaMultilingualNeural",
            name="Ava (Multilingual)",
            language="en",
            locale="en-US",
            gender="Female",
            provider="edge_tts"
        )
        assert voice.id == "en-US-AvaMultilingualNeural"
        assert voice.language == "en"
        assert voice.gender == "Female"
        assert voice.sample_rate == 22050  # Default

    def test_voice_with_extra_data(self):
        """Test voice with extra metadata"""
        voice = TTSVoice(
            id="coqui_custom",
            name="Custom Voice",
            language="en",
            locale="en-US",
            gender="Neutral",
            provider="coqui",
            extra={"speaker": "custom_speaker", "style": "casual"}
        )
        assert voice.extra["speaker"] == "custom_speaker"


class TestTTSCapabilities:
    """Tests for TTSCapabilities data class"""

    def test_default_capabilities(self):
        """Test default capability values"""
        caps = TTSCapabilities()
        assert caps.supports_streaming is False
        assert caps.supports_word_timing is False
        assert caps.max_text_length == 5000
        assert caps.requires_consent is False
        assert caps.is_local is False

    def test_edge_tts_like_capabilities(self):
        """Test capabilities matching Edge TTS"""
        caps = TTSCapabilities(
            supports_streaming=True,
            supports_word_timing=True,
            supports_ssml=True,
            requires_consent=True,
            is_local=False,
            estimated_latency_ms=200
        )
        assert caps.supports_word_timing is True
        assert caps.requires_consent is True

    def test_coqui_like_capabilities(self):
        """Test capabilities matching Coqui TTS"""
        caps = TTSCapabilities(
            supports_streaming=True,
            supports_word_timing=False,
            supports_voice_cloning=True,
            requires_consent=False,
            is_local=True,
            estimated_latency_ms=1000
        )
        assert caps.is_local is True
        assert caps.supports_voice_cloning is True


class TestWordTiming:
    """Tests for WordTiming data class"""

    def test_word_timing_creation(self):
        """Test creating word timing"""
        timing = WordTiming(
            text="Hello",
            offset_ms=0,
            duration_ms=500
        )
        assert timing.text == "Hello"
        assert timing.offset_ms == 0
        assert timing.duration_ms == 500

    def test_word_timing_seconds_conversion(self):
        """Test conversion to seconds"""
        timing = WordTiming(
            text="World",
            offset_ms=1500,
            duration_ms=750
        )
        assert_close(timing.start_seconds, 1.5)
        assert_close(timing.end_seconds, 2.25)


class TestTTSResult:
    """Tests for TTSResult data class"""

    def test_result_creation(self):
        """Test creating a TTS result"""
        result = TTSResult(
            audio_path="/path/to/audio.mp3",
            subtitle_path="/path/to/subtitles.srt",
            duration_seconds=5.5,
            cached=False,
            provider="edge_tts",
            voice_id="en-US-AvaMultilingualNeural"
        )
        assert result.audio_path == "/path/to/audio.mp3"
        assert result.duration_seconds == 5.5
        assert result.provider == "edge_tts"

    def test_result_with_word_timings(self):
        """Test result with word timing data"""
        timings = [
            WordTiming("Hello", 0, 500),
            WordTiming("World", 600, 500),
        ]
        result = TTSResult(
            audio_path="/path/to/audio.mp3",
            duration_seconds=1.1,
            word_timings=timings
        )
        assert len(result.word_timings) == 2
        assert result.word_timings[0].text == "Hello"


# ============================================================================
# EDGE TTS PROVIDER TESTS
# ============================================================================

class TestEdgeTTSProvider:
    """Tests for Edge TTS Provider"""

    @pytest.fixture
    def provider(self):
        """Create a fresh Edge TTS provider for each test"""
        return EdgeTTSProvider()

    def test_provider_type(self, provider):
        """Test provider type is correct"""
        assert provider.provider_type == TTSProviderType.EDGE_TTS
        assert provider.display_name == "Microsoft Edge TTS"

    def test_capabilities(self, provider):
        """Test provider capabilities"""
        caps = provider.capabilities
        assert caps.supports_streaming is True
        assert caps.supports_word_timing is True
        assert caps.requires_consent is True
        assert caps.is_local is False

    def test_best_voice_lookup(self, provider):
        """Test best voice for language lookup"""
        assert provider.get_best_voice("en") == "en-US-AvaMultilingualNeural"
        assert provider.get_best_voice("fr") == "fr-FR-VivienneMultilingualNeural"
        assert provider.get_best_voice("unknown") == "en-US-AvaMultilingualNeural"

    def test_config_with_proxy(self):
        """Test provider configuration with proxy"""
        provider = EdgeTTSProvider(config={"proxy_url": "http://proxy:8080"})
        assert provider.proxy_url == "http://proxy:8080"

    @pytest.mark.asyncio
    async def test_get_status(self, provider):
        """Test getting provider status"""
        status = provider.get_status()
        assert status["provider"] == "edge_tts"
        assert status["name"] == "Microsoft Edge TTS"
        assert "capabilities" in status
        assert status["capabilities"]["requires_consent"] is True


class TestEdgeTTSProviderIntegration:
    """Integration tests for Edge TTS (requires network)"""

    @pytest.fixture
    def provider(self):
        return EdgeTTSProvider()

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_initialize(self, provider):
        """Test provider initialization with network"""
        result = await provider.initialize()
        # May fail without network, but should not raise
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_get_voices(self, provider):
        """Test fetching available voices"""
        try:
            voices = await provider.get_voices("en")
            assert isinstance(voices, list)
            if voices:
                assert all(isinstance(v, TTSVoice) for v in voices)
        except ProviderNotAvailableError:
            pytest.skip("Edge TTS not available (no network)")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_generate_audio(self, provider):
        """Test audio generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_audio.mp3"

            try:
                result = await provider.generate_audio(
                    text="Hello, this is a test.",
                    voice_id="en-US-AvaMultilingualNeural",
                    output_path=output_path
                )
                assert output_path.exists()
                assert result.audio_path == str(output_path)
                assert result.duration_seconds > 0
                assert len(result.word_timings) > 0
            except (ProviderNotAvailableError, asyncio.TimeoutError):
                pytest.skip("Edge TTS not available (no network)")


# ============================================================================
# COQUI TTS PROVIDER TESTS
# ============================================================================

class TestCoquiTTSProvider:
    """Tests for Coqui TTS Provider"""

    @pytest.fixture
    def provider(self):
        """Create a fresh Coqui TTS provider for each test"""
        return CoquiTTSProvider()

    def test_provider_type(self, provider):
        """Test provider type is correct"""
        assert provider.provider_type == TTSProviderType.COQUI
        assert provider.display_name == "Coqui TTS (Local)"

    def test_capabilities(self, provider):
        """Test provider capabilities"""
        caps = provider.capabilities
        assert caps.supports_streaming is True
        assert caps.supports_word_timing is True  # Sentence-level timing via per-sentence generation
        assert caps.supports_voice_cloning is True
        assert caps.requires_consent is False  # Local processing
        assert caps.is_local is True

    def test_supported_languages(self, provider):
        """Test supported languages"""
        langs = provider.SUPPORTED_LANGUAGES
        assert "en" in langs
        assert "es" in langs
        assert "fr" in langs
        assert "zh-cn" in langs

    def test_default_speakers(self, provider):
        """Test default speaker mappings"""
        assert provider.DEFAULT_SPEAKERS["en"] == "Claribel Dervla"
        assert "fr" in provider.DEFAULT_SPEAKERS

    @pytest.mark.asyncio
    async def test_get_status(self, provider):
        """Test getting provider status"""
        status = provider.get_status()
        assert status["provider"] == "coqui"
        assert status["capabilities"]["is_local"] is True
        assert "model_loaded" in status

    def test_check_installation(self):
        """Test installation check utility"""
        result = CoquiTTSProvider.check_installation()
        assert "installed" in result
        assert "version" in result
        # May or may not be installed


class TestCoquiTTSProviderMocked:
    """Tests for Coqui TTS with mocked TTS library"""

    @pytest.fixture
    def mock_tts(self):
        """Mock the TTS library"""
        with patch.dict('sys.modules', {'TTS': MagicMock(), 'TTS.api': MagicMock()}):
            yield

    @pytest.mark.asyncio
    async def test_initialize_without_tts(self):
        """Test initialization when TTS is not installed"""
        provider = CoquiTTSProvider()

        # Mock the import check to fail
        with patch('importlib.util.find_spec', return_value=None):
            result = await provider.initialize()
            assert result is False
            assert provider._available is False


# ============================================================================
# PROVIDER REGISTRY TESTS
# ============================================================================

class TestTTSProviderRegistry:
    """Tests for TTS Provider Registry"""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry with temp storage"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / ".termivoxed_tts_settings.json"
            yield TTSProviderRegistry(storage_path=storage_path)

    def test_registry_creation(self, registry):
        """Test registry is created with default providers"""
        providers = registry.get_all_providers()
        assert "edge_tts" in providers
        assert "coqui" in providers

    def test_get_default_provider(self, registry):
        """Test getting default provider"""
        default = registry.get_default()
        assert default == TTSProviderType.EDGE_TTS

    def test_set_default_provider(self, registry):
        """Test setting default provider"""
        registry.set_default(TTSProviderType.COQUI)
        assert registry.get_default() == TTSProviderType.COQUI

    def test_get_provider(self, registry):
        """Test getting specific provider"""
        provider = registry.get(TTSProviderType.EDGE_TTS)
        assert provider.provider_type == TTSProviderType.EDGE_TTS

    def test_get_provider_not_found(self, registry):
        """Test getting non-existent provider"""
        with pytest.raises(ProviderNotAvailableError):
            registry.get(TTSProviderType.PIPER)  # Not registered by default

    @pytest.mark.asyncio
    async def test_get_all_status(self, registry):
        """Test getting status of all providers"""
        statuses = await registry.get_all_status()
        assert len(statuses) >= 2
        assert all("provider" in s for s in statuses)
        assert all("available" in s for s in statuses)


class TestRegistryConvenienceFunctions:
    """Tests for registry convenience functions"""

    def test_get_provider_function(self):
        """Test get_provider convenience function"""
        provider = get_provider()  # Gets default
        assert provider is not None
        assert isinstance(provider, TTSProvider)

    def test_get_default_provider_function(self):
        """Test get_default_provider convenience function"""
        default = get_default_provider()
        assert isinstance(default, TTSProviderType)


# ============================================================================
# SUBTITLE GENERATION TESTS
# ============================================================================

class TestSubtitleGeneration:
    """Tests for subtitle generation from word timings"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        return EdgeTTSProvider()

    def test_format_srt_time(self, provider):
        """Test SRT time formatting"""
        assert provider._format_srt_time(0) == "00:00:00,000"
        assert provider._format_srt_time(1.5) == "00:00:01,500"
        assert provider._format_srt_time(61.123) == "00:01:01,123"
        assert provider._format_srt_time(3661.5) == "01:01:01,500"

    def test_estimated_subtitles_horizontal(self, provider):
        """Test estimated subtitle generation for horizontal video"""
        srt = provider._generate_estimated_subtitles(
            "This is a test sentence with multiple words for testing.",
            5.0,
            "horizontal"
        )
        assert "1\n" in srt
        assert "-->" in srt

    def test_estimated_subtitles_vertical(self, provider):
        """Test estimated subtitle generation for vertical video"""
        srt = provider._generate_estimated_subtitles(
            "This is a test sentence with multiple words for testing.",
            5.0,
            "vertical"
        )
        assert "1\n" in srt
        # Vertical should have shorter chunks

    def test_word_timed_subtitles(self, provider):
        """Test word-timed subtitle generation"""
        timings = [
            WordTiming("Hello", 0, 400),
            WordTiming("world,", 500, 400),
            WordTiming("this", 1000, 300),
            WordTiming("is", 1400, 200),
            WordTiming("a", 1700, 100),
            WordTiming("test.", 1900, 400),
        ]
        srt = provider._generate_word_timed_subtitles(timings, "Hello world, this is a test.", "horizontal")
        assert "1\n" in srt
        assert "-->" in srt


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for error handling"""

    def test_provider_not_available_error(self):
        """Test ProviderNotAvailableError"""
        error = ProviderNotAvailableError("Test error")
        assert str(error) == "Test error"

    def test_provider_config_error(self):
        """Test ProviderConfigError"""
        error = ProviderConfigError("Invalid config")
        assert str(error) == "Invalid config"


# ============================================================================
# TTS SERVICE INTEGRATION TESTS
# ============================================================================

class TestTTSServiceIntegration:
    """Tests for TTS Service with providers"""

    @pytest.fixture
    def tts_service(self):
        """Create TTS service instance"""
        # Import here to avoid issues with missing dependencies
        from backend.tts_service import TTSService
        return TTSService()

    def test_service_has_provider_methods(self, tts_service):
        """Test that service has provider management methods"""
        assert hasattr(tts_service, 'get_current_provider')
        assert hasattr(tts_service, 'set_provider')
        assert hasattr(tts_service, 'get_provider_status')
        assert hasattr(tts_service, 'get_provider_info')

    def test_get_current_provider(self, tts_service):
        """Test getting current provider"""
        provider = tts_service.get_current_provider()
        assert provider in ["edge_tts", "coqui"]

    def test_set_provider_valid(self, tts_service):
        """Test setting valid provider"""
        result = tts_service.set_provider("edge_tts")
        assert result is True

    def test_set_provider_invalid(self, tts_service):
        """Test setting invalid provider"""
        result = tts_service.set_provider("invalid_provider")
        assert result is False

    def test_get_provider_info(self, tts_service):
        """Test getting provider info"""
        info = tts_service.get_provider_info()
        assert "default_provider" in info
        assert "providers" in info
        assert "edge_tts" in info["providers"]

    @pytest.mark.asyncio
    async def test_get_provider_status(self, tts_service):
        """Test getting provider status"""
        statuses = await tts_service.get_provider_status()
        assert isinstance(statuses, list)
        assert len(statuses) >= 1


# ============================================================================
# PRIVACY AND CONSENT TESTS
# ============================================================================

class TestPrivacyConsent:
    """Tests for privacy and consent handling"""

    def test_edge_tts_requires_consent(self):
        """Test that Edge TTS requires consent"""
        provider = EdgeTTSProvider()
        assert provider.capabilities.requires_consent is True

    def test_coqui_no_consent(self):
        """Test that Coqui TTS does not require consent"""
        provider = CoquiTTSProvider()
        assert provider.capabilities.requires_consent is False

    def test_provider_is_local_flag(self):
        """Test is_local flag for providers"""
        edge = EdgeTTSProvider()
        coqui = CoquiTTSProvider()

        assert edge.capabilities.is_local is False
        assert coqui.capabilities.is_local is True


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
