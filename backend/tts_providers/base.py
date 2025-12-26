"""
TTS Provider Base Classes

Abstract base class and data structures for TTS providers.
All providers must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, AsyncIterator
from pathlib import Path


class TTSProviderType(str, Enum):
    """Supported TTS provider types"""
    EDGE_TTS = "edge_tts"       # Microsoft Edge TTS (cloud)
    COQUI = "coqui"             # Coqui TTS (local, MPL-2.0)
    PIPER = "piper"             # Piper TTS (local, subprocess for GPL safety)


class ProviderNotAvailableError(Exception):
    """Raised when a provider is not available or not installed"""
    pass


class ProviderConfigError(Exception):
    """Raised when provider configuration is invalid"""
    pass


@dataclass
class TTSVoice:
    """Voice information"""
    id: str                     # Unique voice identifier
    name: str                   # Display name
    language: str               # Language code (e.g., 'en')
    locale: str                 # Full locale (e.g., 'en-US')
    gender: str                 # 'Male', 'Female', 'Neutral'
    provider: str               # Provider type
    description: Optional[str] = None
    sample_rate: int = 22050
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSCapabilities:
    """Provider capabilities"""
    supports_streaming: bool = False
    supports_word_timing: bool = False
    supports_ssml: bool = False
    supports_voice_cloning: bool = False
    supports_rate_control: bool = True
    supports_pitch_control: bool = True
    supports_volume_control: bool = True
    max_text_length: int = 5000
    supported_languages: List[str] = field(default_factory=list)
    requires_consent: bool = False
    is_local: bool = False
    estimated_latency_ms: int = 500


@dataclass
class WordTiming:
    """Word timing information for subtitle generation"""
    text: str
    offset_ms: int      # Start time in milliseconds
    duration_ms: int    # Duration in milliseconds

    @property
    def start_seconds(self) -> float:
        return self.offset_ms / 1000.0

    @property
    def end_seconds(self) -> float:
        return (self.offset_ms + self.duration_ms) / 1000.0


@dataclass
class TTSResult:
    """Result of TTS generation"""
    audio_path: str                     # Path to generated audio file
    subtitle_path: Optional[str] = None # Path to generated subtitle file
    duration_seconds: float = 0.0
    word_timings: List[WordTiming] = field(default_factory=list)
    cached: bool = False
    provider: str = ""
    voice_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamChunk:
    """Chunk of audio data for streaming"""
    data: bytes
    is_final: bool = False
    word_timing: Optional[WordTiming] = None
    sequence: int = 0


class TTSProvider(ABC):
    """
    Abstract base class for TTS providers.

    All TTS providers must implement this interface to be usable
    in the multi-provider TTS system.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize provider with optional configuration.

        Args:
            config: Provider-specific configuration
        """
        self.config = config or {}
        self._initialized = False

    @property
    @abstractmethod
    def provider_type(self) -> TTSProviderType:
        """Return the provider type"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of the provider"""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> TTSCapabilities:
        """Return provider capabilities"""
        pass

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the provider.

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if the provider is available and ready to use.

        Returns:
            True if provider is available
        """
        pass

    @abstractmethod
    async def get_voices(self, language: Optional[str] = None) -> List[TTSVoice]:
        """
        Get available voices, optionally filtered by language.

        Args:
            language: Language code to filter by (e.g., 'en')

        Returns:
            List of available voices
        """
        pass

    @abstractmethod
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
        """
        Generate audio from text.

        Args:
            text: Text to synthesize
            voice_id: Voice identifier
            output_path: Path to save audio file
            rate: Speech rate adjustment
            volume: Volume adjustment
            pitch: Pitch adjustment
            **kwargs: Additional provider-specific options

        Returns:
            TTSResult with audio path and metadata
        """
        pass

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
        """
        Generate audio with synchronized subtitles.

        Default implementation generates audio first, then estimates subtitles.
        Providers with word timing support should override this.

        Args:
            text: Text to synthesize
            voice_id: Voice identifier
            audio_path: Path to save audio file
            subtitle_path: Path to save subtitle file
            orientation: Video orientation ('horizontal' or 'vertical')
            rate: Speech rate adjustment
            volume: Volume adjustment
            pitch: Pitch adjustment

        Returns:
            TTSResult with audio and subtitle paths
        """
        # Default: generate audio, then estimate subtitles
        result = await self.generate_audio(
            text=text,
            voice_id=voice_id,
            output_path=audio_path,
            rate=rate,
            volume=volume,
            pitch=pitch,
            **kwargs
        )

        # Generate estimated subtitles if no word timing
        if not result.word_timings:
            subtitle_content = self._generate_estimated_subtitles(
                text, result.duration_seconds, orientation
            )
            subtitle_path.write_text(subtitle_content, encoding="utf-8")
            result.subtitle_path = str(subtitle_path)
        else:
            subtitle_content = self._generate_word_timed_subtitles(
                result.word_timings, text, orientation
            )
            subtitle_path.write_text(subtitle_content, encoding="utf-8")
            result.subtitle_path = str(subtitle_path)

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
        """
        Stream audio generation for real-time playback.

        Default implementation raises NotImplementedError.
        Providers with streaming support should override this.

        Args:
            text: Text to synthesize
            voice_id: Voice identifier
            rate: Speech rate adjustment
            volume: Volume adjustment
            pitch: Pitch adjustment

        Yields:
            StreamChunk with audio data
        """
        raise NotImplementedError(
            f"{self.display_name} does not support streaming"
        )
        # This yield is needed to make this an async generator
        yield  # type: ignore

    def _generate_estimated_subtitles(
        self,
        text: str,
        duration: float,
        orientation: str = "horizontal"
    ) -> str:
        """
        Generate estimated subtitles based on text length and duration.

        This is a fallback for providers without word timing.
        """
        # Adjust chunk size based on orientation
        target_chunk_size = 100 if orientation == "horizontal" else 45

        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0

        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1

            if current_length >= target_chunk_size:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        if not chunks:
            chunks = [text]

        # Generate SRT with even distribution
        srt_content = ""
        chunk_duration = duration / len(chunks) if chunks else duration

        for i, chunk in enumerate(chunks):
            start_time = i * chunk_duration
            end_time = duration if i == len(chunks) - 1 else (i + 1) * chunk_duration

            srt_content += f"{i + 1}\n"
            srt_content += f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}\n"
            srt_content += f"{chunk}\n\n"

        return srt_content

    def _generate_word_timed_subtitles(
        self,
        word_timings: List[WordTiming],
        text: str,
        orientation: str = "horizontal"
    ) -> str:
        """
        Generate subtitles from word timing data.

        Uses intelligent chunking based on sentence boundaries
        and timing gaps.
        """
        if not word_timings:
            return ""

        # Settings based on orientation
        if orientation == "horizontal":
            max_chunk_duration = 4.0
            min_chunk_duration = 2.0
        else:
            max_chunk_duration = 3.0
            min_chunk_duration = 1.5

        sentence_enders = {'.', '!', '?'}
        pause_words = {',', ';', ':', '-'}

        chunks = []
        current_chunk = []
        chunk_start = word_timings[0].offset_ms if word_timings else 0

        for i, timing in enumerate(word_timings):
            current_chunk.append(timing)

            chunk_duration = (timing.offset_ms + timing.duration_ms - chunk_start) / 1000.0

            is_sentence_end = any(timing.text.endswith(p) for p in sentence_enders)
            is_pause = any(timing.text.endswith(p) for p in pause_words)

            # Check for natural pause
            has_pause_after = False
            if i + 1 < len(word_timings):
                gap = (word_timings[i + 1].offset_ms - (timing.offset_ms + timing.duration_ms)) / 1000.0
                has_pause_after = gap > 0.15

            should_break = (
                (chunk_duration >= max_chunk_duration * 0.7 and is_sentence_end) or
                (chunk_duration >= max_chunk_duration * 0.8 and (is_pause or has_pause_after)) or
                (chunk_duration >= max_chunk_duration * 1.1) or
                (i == len(word_timings) - 1)
            )

            if chunk_duration < min_chunk_duration and i < len(word_timings) - 1:
                should_break = False

            if should_break and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                if i + 1 < len(word_timings):
                    chunk_start = word_timings[i + 1].offset_ms

        if not chunks and word_timings:
            chunks = [word_timings]

        # Generate SRT
        srt_content = ""
        for i, chunk_timings in enumerate(chunks):
            start_time = chunk_timings[0].start_seconds
            end_time = chunk_timings[-1].end_seconds
            chunk_text = " ".join(t.text for t in chunk_timings)

            srt_content += f"{i + 1}\n"
            srt_content += f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}\n"
            srt_content += f"{chunk_text}\n\n"

        return srt_content

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """Format seconds as SRT time (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = round((seconds % 1) * 1000)

        if millis >= 1000:
            millis = 0
            secs += 1
            if secs >= 60:
                secs = 0
                minutes += 1
                if minutes >= 60:
                    minutes = 0
                    hours += 1

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def get_status(self) -> Dict[str, Any]:
        """Get provider status for health checks"""
        return {
            "provider": self.provider_type.value,
            "name": self.display_name,
            "initialized": self._initialized,
            "capabilities": {
                "streaming": self.capabilities.supports_streaming,
                "word_timing": self.capabilities.supports_word_timing,
                "voice_cloning": self.capabilities.supports_voice_cloning,
                "is_local": self.capabilities.is_local,
                "requires_consent": self.capabilities.requires_consent,
            }
        }
