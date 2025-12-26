"""
Coqui TTS Provider

Local TTS using Coqui TTS (MPL-2.0 license - safe for commercial use).
All processing happens on-device, no data sent to external servers.

Features:
- 16+ languages with XTTS v2
- Voice cloning from audio samples
- Completely local processing (privacy-friendly)
- GPU acceleration supported
- Word-level timing via faster-whisper (local, no network)

Requirements:
- pip install TTS
- pip install faster-whisper (for word timing)
- Large models (1.5-2GB for TTS, ~1.5GB for Whisper)
- GPU recommended for real-time synthesis
"""

# CRITICAL: Must be set before any torch imports for MPS fallback on Apple Silicon
# This allows operations not supported on MPS to fall back to CPU
import os
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['COQUI_TOS_AGREED'] = '1'

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

from .base import (
    TTSProvider,
    TTSProviderType,
    TTSResult,
    TTSCapabilities,
    TTSVoice,
    WordTiming,
    ProviderNotAvailableError,
    ProviderConfigError,
)

from utils.logger import logger


class CoquiTTSProvider(TTSProvider):
    """
    Coqui TTS Provider (Local, MPL-2.0).

    All processing happens locally - no data leaves the device.
    Ideal for users who prefer privacy or have no internet access.

    Note: Coqui TTS has heavy dependencies and requires significant
    disk space and memory. GPU is recommended for reasonable performance.
    """

    # Supported XTTS languages
    SUPPORTED_LANGUAGES = [
        "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru",
        "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"
    ]

    # Default voice mappings (speaker embeddings)
    DEFAULT_SPEAKERS = {
        "en": "Claribel Dervla",
        "es": "Gracie Wise",
        "fr": "Henriette Ulich",
        "de": "Frederik Massmann",
        "it": "Adde Michal",
        "pt": "Baldur Sansen",
        "zh-cn": "Chandra MacFarland",
        "ja": "Viktor Eka",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._tts = None
        self._available = False
        self._model_name = config.get("model_name", "tts_models/multilingual/multi-dataset/xtts_v2") if config else "tts_models/multilingual/multi-dataset/xtts_v2"
        self._use_gpu = config.get("use_gpu", True) if config else True
        self._speakers: List[str] = []

    @property
    def provider_type(self) -> TTSProviderType:
        return TTSProviderType.COQUI

    @property
    def display_name(self) -> str:
        return "Coqui TTS (Local)"

    @property
    def description(self) -> str:
        return (
            "Local TTS powered by Coqui XTTS v2. All processing happens "
            "on your device - no data is sent to external servers. "
            "Supports 16 languages and voice cloning. Requires GPU for best performance."
        )

    @property
    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_streaming=True,
            supports_word_timing=True,  # Sentence-level timing via per-sentence generation
            supports_ssml=False,
            supports_voice_cloning=True,
            supports_rate_control=False,  # XTTS doesn't support rate directly
            supports_pitch_control=False,
            supports_volume_control=False,
            max_text_length=500,  # XTTS works best with shorter chunks
            supported_languages=self.SUPPORTED_LANGUAGES,
            requires_consent=False,  # Local processing
            is_local=True,
            estimated_latency_ms=1000,  # Higher latency than cloud
        )

    async def initialize(self) -> bool:
        """Initialize Coqui TTS (lazy load)"""
        try:
            # Check if TTS package is available
            import importlib.util
            spec = importlib.util.find_spec("TTS")
            if spec is None:
                logger.warning("Coqui TTS not installed. Run: pip install TTS")
                self._available = False
                self._initialized = False
                return False

            # We don't load the model at init time as it's heavy
            # It will be loaded on first use
            self._available = True
            self._initialized = True
            logger.info("Coqui TTS provider initialized (model will load on first use)")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Coqui TTS: {e}")
            self._available = False
            self._initialized = False
            return False

    async def is_available(self) -> bool:
        """Check if Coqui TTS is available"""
        if not self._initialized:
            await self.initialize()
        return self._available

    def _load_model(self):
        """Load the TTS model (called on first use)"""
        if self._tts is not None:
            return

        try:
            from TTS.api import TTS

            logger.info(f"Loading Coqui TTS model: {self._model_name}")

            # Determine device - supports CUDA (NVIDIA), MPS (Apple Silicon), or CPU
            # NOTE: XTTS has a known MPS limitation - HiFi-GAN decoder uses convolutions
            # with >65536 output channels which MPS doesn't support. We use CPU for Apple Silicon.
            device = "cpu"
            mps_available = False

            try:
                import torch
                mps_available = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()

                if self._use_gpu:
                    if torch.cuda.is_available():
                        device = "cuda"
                        logger.info("Using NVIDIA CUDA GPU acceleration")
                    elif mps_available:
                        # XTTS doesn't work with MPS due to HiFi-GAN decoder limitations
                        # The PYTORCH_ENABLE_MPS_FALLBACK env var doesn't help for this case
                        device = "cpu"
                        logger.info("Apple Silicon detected - using CPU for XTTS (MPS has convolution size limits)")
                    else:
                        logger.warning("GPU requested but neither CUDA nor MPS available, using CPU")
                        device = "cpu"
            except ImportError:
                logger.warning("PyTorch not available, using CPU")
                device = "cpu"

            self._tts = TTS(model_name=self._model_name).to(device)
            self._mps_available = mps_available  # Store for status reporting
            self._device = device  # Store for later reference

            # Get available speakers
            if hasattr(self._tts, 'speakers'):
                self._speakers = self._tts.speakers or []

            logger.info(f"Coqui TTS model loaded on {device}")

        except Exception as e:
            logger.error(f"Failed to load Coqui TTS model: {e}")
            raise ProviderNotAvailableError(f"Cannot load model: {e}")

    async def get_voices(self, language: Optional[str] = None) -> List[TTSVoice]:
        """Get available voices (speakers)"""
        if not await self.is_available():
            raise ProviderNotAvailableError("Coqui TTS not available")

        # Load model to get speaker list
        await asyncio.get_event_loop().run_in_executor(
            None, self._load_model
        )

        voices = []

        # Create voices from speakers
        for speaker in self._speakers:
            # Determine language from speaker name (heuristic)
            voice_lang = "en"  # Default
            for lang in self.SUPPORTED_LANGUAGES:
                if lang in speaker.lower():
                    voice_lang = lang
                    break

            if language and voice_lang != language:
                continue

            voices.append(TTSVoice(
                id=f"coqui_{speaker.lower().replace(' ', '_')}",
                name=speaker,
                language=voice_lang,
                locale=voice_lang,
                gender="Neutral",  # XTTS doesn't specify gender
                provider=self.provider_type.value,
                sample_rate=24000,
                extra={"speaker": speaker}
            ))

        # Add default voice per language if no specific speakers
        if not voices:
            for lang in self.SUPPORTED_LANGUAGES:
                if language and lang != language:
                    continue

                speaker = self.DEFAULT_SPEAKERS.get(lang, "Claribel Dervla")
                voices.append(TTSVoice(
                    id=f"coqui_default_{lang}",
                    name=f"Default {lang.upper()} Voice",
                    language=lang,
                    locale=lang,
                    gender="Neutral",
                    provider=self.provider_type.value,
                    sample_rate=24000,
                    extra={"speaker": speaker}
                ))

        return voices

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
        Generate audio using Coqui TTS with word-level timing via Whisper.

        This method:
        1. Generates audio in one pass (preserving natural voice flow)
        2. Uses faster-whisper to extract word-level timestamps
        3. Returns accurate word timing for subtitles
        """
        if not await self.is_available():
            raise ProviderNotAvailableError("Coqui TTS not available")

        try:
            # Load model if needed
            await asyncio.get_event_loop().run_in_executor(
                None, self._load_model
            )

            # Extract speaker from voice_id
            speaker = kwargs.get("speaker")
            if not speaker:
                # Try to extract from voice_id
                if voice_id.startswith("coqui_"):
                    speaker_name = voice_id.replace("coqui_", "").replace("_", " ").title()
                    # Find matching speaker
                    for s in self._speakers:
                        if s.lower() == speaker_name.lower():
                            speaker = s
                            break

                if not speaker:
                    speaker = self.DEFAULT_SPEAKERS.get(
                        kwargs.get("language", "en"),
                        "Claribel Dervla"
                    )

            # Language from kwargs or extract from voice_id
            language = kwargs.get("language", "en")

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate audio in one pass (natural voice flow)
            def generate():
                self._tts.tts_to_file(
                    text=text,
                    speaker=speaker,
                    language=language,
                    file_path=str(output_path)
                )

            await asyncio.get_event_loop().run_in_executor(
                None, generate
            )

            # Get duration
            duration = await self._get_audio_duration(output_path)

            # Extract word timings using Whisper
            word_timings = await self._extract_word_timings_with_whisper(
                output_path, language
            )

            logger.info(f"Generated audio with {len(word_timings)} word timings")

            return TTSResult(
                audio_path=str(output_path),
                duration_seconds=duration,
                word_timings=word_timings,
                cached=False,
                provider=self.provider_type.value,
                voice_id=voice_id,
                metadata={
                    "speaker": speaker,
                    "language": language,
                    "model": self._model_name,
                    "timing_type": "whisper",
                }
            )

        except Exception as e:
            logger.error(f"Coqui TTS generation failed: {e}")
            raise

    async def _extract_word_timings_with_whisper(
        self,
        audio_path: Path,
        language: str = "en"
    ) -> List[WordTiming]:
        """
        Extract word-level timings from audio using faster-whisper.

        This runs 100% locally - no data sent to any server.
        """
        try:
            # Try to import faster-whisper
            from faster_whisper import WhisperModel
        except ImportError:
            logger.warning(
                "faster-whisper not installed. Install with: pip install faster-whisper\n"
                "Falling back to estimated timing."
            )
            return []

        try:
            def transcribe():
                # Use tiny or base model for speed (we just need timing, not accuracy)
                # Models: tiny, base, small, medium, large
                model = WhisperModel("base", device="auto", compute_type="auto")

                # Transcribe with word timestamps
                segments, info = model.transcribe(
                    str(audio_path),
                    language=language if language != "auto" else None,
                    word_timestamps=True,
                    vad_filter=True,  # Voice activity detection for better accuracy
                )

                word_timings = []
                for segment in segments:
                    if segment.words:
                        for word in segment.words:
                            word_timings.append(WordTiming(
                                text=word.word.strip(),
                                offset_ms=int(word.start * 1000),
                                duration_ms=int((word.end - word.start) * 1000)
                            ))

                return word_timings

            # Run in thread pool to avoid blocking
            word_timings = await asyncio.get_event_loop().run_in_executor(
                None, transcribe
            )

            logger.info(f"Extracted {len(word_timings)} word timings with Whisper")
            return word_timings

        except Exception as e:
            logger.warning(f"Whisper timing extraction failed: {e}. Using estimated timing.")
            return []

    async def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(audio_path)
            ]
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                return float(stdout.decode().strip())
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")

        return 0.0

    async def clone_voice(
        self,
        audio_sample_paths: list,
        text: str,
        output_path: Path,
        language: str = "en",
        voice_sample_name: str = "custom",
        temperature: float = 0.65,
        speed: float = 1.0,
    ) -> TTSResult:
        """
        Generate audio using a cloned voice from audio sample(s).

        This method:
        1. Uses the provided audio sample(s) to clone the voice
        2. Generates audio with the cloned voice
        3. Extracts word-level timing using Whisper (if available)

        Args:
            audio_sample_paths: List of Path objects to voice sample audio files.
                               Multiple samples improve cloning quality.
            text: Text to synthesize
            output_path: Path to save the generated audio
            language: Language code (default: "en")
            voice_sample_name: Name of the voice sample for metadata
            temperature: Softmax temperature (0.65 default, lower = more deterministic)
            speed: Speech speed multiplier (1.0 = normal)

        Returns:
            TTSResult with audio path and word timings
        """
        if not await self.is_available():
            raise ProviderNotAvailableError("Coqui TTS not available")

        # Handle both single Path and list of Paths for backward compatibility
        if isinstance(audio_sample_paths, Path):
            audio_sample_paths = [audio_sample_paths]

        # Validate all audio samples exist and convert to WAV if needed
        # XTTS requires WAV format - convert other formats using ffmpeg
        valid_paths = []
        temp_wav_files = []  # Track temp files for cleanup

        for sample_path in audio_sample_paths:
            if isinstance(sample_path, str):
                sample_path = Path(sample_path)
            if not sample_path.exists():
                logger.warning(f"Voice sample not found, skipping: {sample_path}")
                continue

            # Check if conversion to WAV is needed
            if sample_path.suffix.lower() != '.wav':
                # Convert to WAV using ffmpeg
                import subprocess
                import tempfile
                temp_wav = Path(tempfile.gettempdir()) / f"voice_sample_{sample_path.stem}.wav"
                try:
                    cmd = [
                        'ffmpeg', '-y', '-i', str(sample_path),
                        '-ar', '22050',  # XTTS expects 22050 Hz
                        '-ac', '1',      # Mono
                        '-c:a', 'pcm_s16le',  # 16-bit PCM
                        str(temp_wav)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0 and temp_wav.exists():
                        valid_paths.append(str(temp_wav))
                        temp_wav_files.append(temp_wav)
                        logger.info(f"Converted {sample_path.suffix} to WAV: {temp_wav}")
                    else:
                        logger.error(f"Failed to convert {sample_path}: {result.stderr}")
                except Exception as e:
                    logger.error(f"Error converting audio: {e}")
            else:
                valid_paths.append(str(sample_path))

        if not valid_paths:
            raise ProviderConfigError("No valid voice samples found")

        try:
            # Load model if needed
            await asyncio.get_event_loop().run_in_executor(
                None, self._load_model
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)

            def generate():
                # Use list of speaker_wav for better voice cloning (per Coqui docs)
                # Multiple reference files improve voice matching quality
                self._tts.tts_to_file(
                    text=text,
                    speaker_wav=valid_paths,  # Can be single path or list
                    language=language,
                    file_path=str(output_path),
                    split_sentences=True,  # Recommended for long texts
                )

            await asyncio.get_event_loop().run_in_executor(
                None, generate
            )

            duration = await self._get_audio_duration(output_path)

            # Extract word timings using Whisper (same as generate_audio)
            word_timings = await self._extract_word_timings_with_whisper(
                output_path, language
            )

            logger.info(f"Generated cloned voice audio with {len(word_timings)} word timings using {len(valid_paths)} sample(s)")

            return TTSResult(
                audio_path=str(output_path),
                duration_seconds=duration,
                word_timings=word_timings,
                cached=False,
                provider=self.provider_type.value,
                voice_id=f"cloned_{voice_sample_name}",
                metadata={
                    "source_audio": valid_paths,
                    "voice_sample_name": voice_sample_name,
                    "language": language,
                    "voice_cloning": True,
                    "num_samples": len(valid_paths),
                    "temperature": temperature,
                    "speed": speed,
                    "timing_type": "whisper" if word_timings else "none",
                }
            )

        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            raise

        finally:
            # Cleanup temporary WAV files
            for temp_file in temp_wav_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                        logger.debug(f"Cleaned up temp WAV: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get provider status"""
        status = super().get_status()

        # Add Coqui-specific info
        status.update({
            "model_loaded": self._tts is not None,
            "model_name": self._model_name,
            "gpu_enabled": self._use_gpu,
            "speakers_count": len(self._speakers),
            "active_device": getattr(self, '_device', 'unknown'),
        })

        # Check GPU availability (CUDA and MPS)
        try:
            import torch
            status["cuda_available"] = torch.cuda.is_available()
            status["mps_available"] = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()

            if torch.cuda.is_available():
                status["gpu_device"] = torch.cuda.get_device_name(0)
                status["gpu_type"] = "NVIDIA CUDA"
            elif status["mps_available"]:
                status["gpu_device"] = "Apple Silicon"
                status["gpu_type"] = "Apple MPS"
            else:
                status["gpu_device"] = None
                status["gpu_type"] = "CPU only"
        except ImportError:
            status["cuda_available"] = False
            status["mps_available"] = False

        return status

    @staticmethod
    def check_installation() -> Dict[str, Any]:
        """Check if Coqui TTS is properly installed"""
        result = {
            "installed": False,
            "version": None,
            "torch_version": None,
            "cuda_available": False,
            "mps_available": False,
            "recommended_device": "cpu",
            "error": None,
        }

        try:
            import TTS
            result["installed"] = True
            result["version"] = getattr(TTS, "__version__", "unknown")
        except ImportError as e:
            result["error"] = f"TTS not installed: {e}"
            return result

        try:
            import torch
            result["torch_version"] = torch.__version__
            result["cuda_available"] = torch.cuda.is_available()
            result["mps_available"] = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()

            # Determine recommended device
            # Note: XTTS doesn't work with MPS due to HiFi-GAN decoder limitations
            # (convolutions with >65536 output channels not supported on MPS)
            if result["cuda_available"]:
                result["recommended_device"] = "cuda"
            else:
                # Even if MPS is available, we use CPU for XTTS compatibility
                result["recommended_device"] = "cpu"
                if result["mps_available"]:
                    result["mps_note"] = "MPS detected but XTTS uses CPU (HiFi-GAN decoder limitation)"
        except ImportError:
            result["error"] = "PyTorch not installed"

        return result
