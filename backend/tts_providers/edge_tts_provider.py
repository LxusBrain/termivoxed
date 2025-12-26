"""
Edge TTS Provider

Cloud-based TTS using Microsoft Edge Text-to-Speech.
Requires user consent due to data being sent to Microsoft servers.

Features:
- 400+ voices across 100+ languages
- Word-level timing for precise subtitles
- SSML support for advanced speech control
- Proxy support for network restrictions
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator

import edge_tts
import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .base import (
    TTSProvider,
    TTSProviderType,
    TTSResult,
    TTSCapabilities,
    TTSVoice,
    WordTiming,
    StreamChunk,
    ProviderNotAvailableError,
)

from utils.logger import logger


class EdgeTTSProvider(TTSProvider):
    """
    Microsoft Edge TTS Provider.

    This provider sends text to Microsoft's servers for voice synthesis.
    User consent is required before use.
    """

    # Best voices per language (curated selection)
    BEST_VOICES = {
        'en': 'en-US-AvaMultilingualNeural',
        'fr': 'fr-FR-VivienneMultilingualNeural',
        'ko': 'ko-KR-HyunsuMultilingualNeural',
        'hi': 'hi-IN-MadhurNeural',
        'kn': 'kn-IN-GaganNeural',
        'ta': 'ta-IN-ValluvarNeural',
        'te': 'te-IN-ShrutiNeural',
        'ml': 'ml-IN-SobhanaNeural',
        'es': 'es-ES-ElviraNeural',
        'de': 'de-DE-KatjaNeural',
        'it': 'it-IT-ElsaNeural',
        'pt': 'pt-BR-FranciscaNeural',
        'zh': 'zh-CN-XiaoxiaoNeural',
        'ja': 'ja-JP-NanamiNeural',
        'ar': 'ar-SA-ZariyahNeural',
        'ru': 'ru-RU-SvetlanaNeural',
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.proxy_url = config.get("proxy_url") if config else None
        self._voices_cache: Optional[List[TTSVoice]] = None

    @property
    def provider_type(self) -> TTSProviderType:
        return TTSProviderType.EDGE_TTS

    @property
    def display_name(self) -> str:
        return "Microsoft Edge TTS"

    @property
    def description(self) -> str:
        return (
            "Cloud-based TTS powered by Microsoft. Offers 400+ high-quality "
            "neural voices with precise word timing for subtitles. "
            "Requires internet connection and data is processed by Microsoft."
        )

    @property
    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_streaming=True,
            supports_word_timing=True,
            supports_ssml=True,
            supports_voice_cloning=False,
            supports_rate_control=True,
            supports_pitch_control=True,
            supports_volume_control=True,
            max_text_length=10000,
            supported_languages=list(self.BEST_VOICES.keys()),
            requires_consent=True,  # Data sent to Microsoft
            is_local=False,
            estimated_latency_ms=200,
        )

    async def initialize(self) -> bool:
        """Initialize the Edge TTS provider"""
        try:
            # Test connectivity
            available = await self.is_available()
            self._initialized = available
            return available
        except Exception as e:
            logger.error(f"Failed to initialize Edge TTS: {e}")
            self._initialized = False
            return False

    async def is_available(self) -> bool:
        """Check if Edge TTS is available"""
        try:
            # Quick connectivity test
            communicate = edge_tts.Communicate(
                text="test",
                voice="en-US-AvaMultilingualNeural",
                proxy=self.proxy_url
            )
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    return True
                break
            return True
        except Exception as e:
            logger.warning(f"Edge TTS connectivity check failed: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            aiohttp.ClientTimeout,
            aiohttp.ServerTimeoutError,
            aiohttp.ClientConnectorError,
            asyncio.TimeoutError,
            ConnectionError,
        ))
    )
    async def get_voices(self, language: Optional[str] = None) -> List[TTSVoice]:
        """Get available voices from Edge TTS"""
        try:
            # Try to use cached voices
            if self._voices_cache and not language:
                return self._voices_cache

            # Fetch voices using appropriate API version
            try:
                from edge_tts import VoicesManager
                voices_manager = await VoicesManager.create()
                raw_voices = voices_manager.voices
            except (ImportError, AttributeError):
                raw_voices = await edge_tts.list_voices()

            voices = []
            for voice in raw_voices:
                try:
                    locale = (
                        voice.get('Locale') or
                        voice.get('locale') or
                        voice.get('Language')
                    )
                    if not locale:
                        continue

                    if language and not locale.lower().startswith(language.lower()):
                        continue

                    voice_obj = TTSVoice(
                        id=voice.get('ShortName') or voice.get('Name', 'Unknown'),
                        name=voice.get('FriendlyName') or voice.get('Name', 'Unknown'),
                        language=locale.split('-')[0],
                        locale=locale,
                        gender=voice.get('Gender', 'Unknown'),
                        provider=self.provider_type.value,
                        sample_rate=24000,
                        extra={
                            "voice_type": voice.get('VoiceType', 'Neural'),
                            "style_list": voice.get('StyleList', []),
                        }
                    )
                    voices.append(voice_obj)
                except Exception as e:
                    logger.debug(f"Skipping voice due to parse error: {e}")
                    continue

            # Cache if fetching all
            if not language:
                self._voices_cache = voices

            return voices

        except Exception as e:
            logger.error(f"Failed to get Edge TTS voices: {e}")
            raise ProviderNotAvailableError(f"Cannot fetch voices: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((
            aiohttp.ClientTimeout,
            aiohttp.ServerTimeoutError,
            aiohttp.ClientConnectorError,
            asyncio.TimeoutError,
            ConnectionError,
        ))
    )
    async def generate_audio(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
        **kwargs
    ) -> TTSResult:
        """Generate audio using Edge TTS"""
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_id,
                rate=rate,
                volume=volume,
                pitch=pitch,
                proxy=self.proxy_url
            )

            audio_data = bytearray()
            word_timings: List[WordTiming] = []

            async def stream_with_timeout():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data.extend(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        word_timings.append(WordTiming(
                            text=chunk.get('text', ''),
                            offset_ms=chunk.get('offset', 0) // 10000,  # 100-ns to ms
                            duration_ms=chunk.get('duration', 0) // 10000,
                        ))

            await asyncio.wait_for(stream_with_timeout(), timeout=60.0)

            # Write audio file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_data)

            # Calculate duration from word timings or estimate
            duration = 0.0
            if word_timings:
                last = word_timings[-1]
                duration = (last.offset_ms + last.duration_ms) / 1000.0
            else:
                # Estimate from audio size (rough: MP3 ~128kbps)
                duration = len(audio_data) / (128 * 1024 / 8)

            return TTSResult(
                audio_path=str(output_path),
                duration_seconds=duration,
                word_timings=word_timings,
                cached=False,
                provider=self.provider_type.value,
                voice_id=voice_id,
                metadata={
                    "rate": rate,
                    "volume": volume,
                    "pitch": pitch,
                    "word_count": len(word_timings),
                }
            )

        except asyncio.TimeoutError:
            raise ProviderNotAvailableError("Audio generation timed out after 60 seconds")
        except Exception as e:
            logger.error(f"Edge TTS generation failed: {e}")
            raise

    async def generate_with_subtitles(
        self,
        text: str,
        voice_id: str,
        audio_path: Path,
        subtitle_path: Path,
        orientation: str = "horizontal",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
        **kwargs
    ) -> TTSResult:
        """Generate audio with word-timed subtitles"""
        result = await self.generate_audio(
            text=text,
            voice_id=voice_id,
            output_path=audio_path,
            rate=rate,
            volume=volume,
            pitch=pitch,
            **kwargs
        )

        # Generate subtitles from word timing
        if result.word_timings:
            subtitle_content = self._generate_word_timed_subtitles(
                result.word_timings, text, orientation
            )
        else:
            subtitle_content = self._generate_estimated_subtitles(
                text, result.duration_seconds, orientation
            )

        subtitle_path.write_text(subtitle_content, encoding="utf-8")
        result.subtitle_path = str(subtitle_path)

        logger.info(
            f"Generated Edge TTS audio with {len(result.word_timings)} word timings"
        )
        return result

    async def stream_audio(
        self,
        text: str,
        voice_id: str,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Stream audio generation for real-time playback"""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate,
            volume=volume,
            pitch=pitch,
            proxy=self.proxy_url
        )

        sequence = 0
        current_word: Optional[WordTiming] = None

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield StreamChunk(
                    data=chunk["data"],
                    is_final=False,
                    word_timing=current_word,
                    sequence=sequence
                )
                sequence += 1
                current_word = None

            elif chunk["type"] == "WordBoundary":
                current_word = WordTiming(
                    text=chunk.get('text', ''),
                    offset_ms=chunk.get('offset', 0) // 10000,
                    duration_ms=chunk.get('duration', 0) // 10000,
                )

        # Final chunk
        yield StreamChunk(
            data=b"",
            is_final=True,
            sequence=sequence
        )

    async def check_connectivity(self) -> Dict[str, Any]:
        """Check connectivity with and without proxy"""
        status = {
            "provider": self.provider_type.value,
            "direct_connection": False,
            "proxy_connection": False,
            "proxy_url": self.proxy_url,
            "recommended_mode": "unknown",
        }

        # Test direct connection
        try:
            communicate = edge_tts.Communicate(
                text="Hello",
                voice="en-US-AvaMultilingualNeural",
                proxy=None
            )
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    status["direct_connection"] = True
                    break
        except Exception as e:
            logger.debug(f"Direct connection failed: {e}")

        # Test proxy if configured
        if self.proxy_url:
            try:
                communicate = edge_tts.Communicate(
                    text="Hello",
                    voice="en-US-AvaMultilingualNeural",
                    proxy=self.proxy_url
                )
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        status["proxy_connection"] = True
                        break
            except Exception as e:
                logger.debug(f"Proxy connection failed: {e}")

        # Determine recommendation
        if status["direct_connection"]:
            status["recommended_mode"] = "direct"
        elif status["proxy_connection"]:
            status["recommended_mode"] = "proxy"
        else:
            status["recommended_mode"] = "none"

        return status

    def get_best_voice(self, language: str) -> str:
        """Get the recommended voice for a language"""
        return self.BEST_VOICES.get(language, "en-US-AvaMultilingualNeural")
