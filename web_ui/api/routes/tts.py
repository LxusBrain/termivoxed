"""TTS (Text-to-Speech) API routes

Multi-provider TTS endpoints supporting:
- edge-tts (cloud, Microsoft) - requires consent
- Coqui TTS (local) - no consent required
- Voice cloning (Coqui only) - clone voices from audio samples
"""

import sys
import os
import uuid
import json
import shutil
import asyncio
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from web_ui.api.middleware.auth import get_current_user, AuthenticatedUser

from backend.tts_service import TTSService
from backend.ffmpeg_utils import FFmpegUtils
from backend.tts_providers import TTSProviderType
from web_ui.api.schemas.tts_schemas import (
    VoiceInfo,
    VoiceListResponse,
    VoicePreviewRequest,
    VoicePreviewResponse,
    TTSGenerateRequest,
    TTSGenerateResponse,
    TTSConnectivityStatus,
    BestVoicesResponse,
)
from config import settings
from utils.logger import logger

router = APIRouter()

# Shared TTS service instance
tts_service = TTSService()

# ============================================================================
# Voice Cloning Subprocess Management
# ============================================================================

# Track active voice cloning jobs
active_clone_jobs: Dict[str, dict] = {}
# WebSocket connections for voice cloning progress
clone_progress_connections: Dict[str, WebSocket] = {}
# Track active clone processes
active_clone_processes: Dict[str, asyncio.subprocess.Process] = {}
# Path to voice clone worker script
VOICE_CLONE_WORKER_PATH = Path(__file__).parent.parent / "voice_clone_worker.py"


# ============================================================================
# Provider Management Schemas
# ============================================================================

class ProviderInfo(BaseModel):
    """TTS Provider information"""
    name: str
    display_name: str
    description: str
    is_local: bool
    requires_consent: bool
    supports_word_timing: bool
    supports_voice_cloning: bool
    available: bool = False
    is_default: bool = False


class ProviderStatusResponse(BaseModel):
    """Response for provider status"""
    default_provider: str
    providers: List[ProviderInfo]


class SetProviderRequest(BaseModel):
    """Request to set default provider"""
    provider: str


class ProviderVoicesRequest(BaseModel):
    """Request for voices from a provider"""
    provider: Optional[str] = None
    language: Optional[str] = None


@router.get("/voices", response_model=VoiceListResponse)
async def list_voices(language: str = None):
    """Get list of available TTS voices"""
    try:
        voices = await tts_service.get_available_voices(language)
        voice_infos = [VoiceInfo(**v) for v in voices]
        return VoiceListResponse(voices=voice_infos, total=len(voice_infos))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices/best", response_model=BestVoicesResponse)
async def get_best_voices():
    """Get recommended best voices per language"""
    return BestVoicesResponse(voices=tts_service.best_voices)


@router.post("/preview", response_model=VoicePreviewResponse)
async def preview_voice(
    request: VoicePreviewRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate a preview audio for a voice"""
    try:
        # Generate a unique segment name including parameters for proper caching
        # This ensures different parameter combinations get separate audio files
        param_hash = hash(f"{request.rate}_{request.volume}_{request.pitch}_{request.text}") % 100000
        segment_name = f"preview_{request.voice_id[:20]}_{param_hash}"

        # Generate preview audio using RESILIENT method with automatic fallback
        # Uses circuit breaker, health monitoring, and fallback to other providers
        audio_path, _ = await tts_service.generate_with_resilience(
            text=request.text,
            language="en",  # Preview always uses the voice's language
            voice=request.voice_id,
            project_name="_previews",
            segment_name=segment_name,
            rate=request.rate,
            volume=request.volume,
            pitch=request.pitch,
            fallback_providers=["edge_tts", "coqui"],
        )

        # Get audio duration
        duration = FFmpegUtils.get_media_duration(audio_path)

        return VoicePreviewResponse(
            audio_url=f"/storage/{Path(audio_path).relative_to(settings.STORAGE_DIR)}",
            duration=duration or 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_tts(
    request: TTSGenerateRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate TTS audio for text

    Supports both standard TTS and voice cloning (when voice_sample_id is provided).
    Voice cloning requires Coqui TTS provider.
    """
    try:
        # Skip cache check if using voice cloning (unique per sample)
        if not request.voice_sample_id:
            # Check cache first
            cache_key = tts_service._generate_cache_key(
                request.text,
                request.voice_id,
                request.rate,
                request.volume,
                request.pitch
            )

            cached_audio, cached_subtitle = tts_service.find_cached_files(cache_key)

            if cached_audio:
                duration = FFmpegUtils.get_media_duration(cached_audio)
                return TTSGenerateResponse(
                    audio_path=cached_audio,
                    subtitle_path=cached_subtitle,
                    duration=duration or 0,
                    cached=True
                )

        # Generate new audio using RESILIENT method with automatic fallback
        # Uses circuit breaker, health monitoring, and fallback to other providers
        # When voice_sample_id is provided, uses voice cloning with Coqui TTS
        if request.voice_sample_id:
            # Voice cloning requires Coqui - use direct provider call
            audio_path, subtitle_path = await tts_service.generate_audio_with_provider(
                text=request.text,
                language=request.language,
                voice=request.voice_id,
                project_name=request.project_name,
                segment_name=request.segment_name,
                rate=request.rate,
                volume=request.volume,
                pitch=request.pitch,
                orientation=request.orientation,
                voice_sample_id=request.voice_sample_id,
                additional_sample_ids=request.additional_sample_ids,
            )
        else:
            # Use resilient method with automatic fallback on failure
            audio_path, subtitle_path = await tts_service.generate_with_resilience(
                text=request.text,
                language=request.language,
                voice=request.voice_id,
                project_name=request.project_name,
                segment_name=request.segment_name,
                rate=request.rate,
                volume=request.volume,
                pitch=request.pitch,
                orientation=request.orientation,
                fallback_providers=["edge_tts", "coqui"],
            )

        duration = FFmpegUtils.get_media_duration(audio_path)

        return TTSGenerateResponse(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            duration=duration or 0,
            cached=False
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connectivity", response_model=TTSConnectivityStatus)
async def check_connectivity(user: AuthenticatedUser = Depends(get_current_user)):
    """Check TTS service connectivity (requires authentication - consumes network resources)"""
    try:
        status = await tts_service.check_tts_connectivity()
        return TTSConnectivityStatus(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/{project_name}/{filename}")
async def get_audio_file(
    project_name: str,
    filename: str,
    language: str = "en",
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Serve generated audio file (requires authentication)"""
    # Sanitize project_name and filename to prevent path traversal
    from web_ui.api.utils.security import sanitize_project_name, sanitize_filename

    safe_project_name = sanitize_project_name(project_name)
    safe_filename = sanitize_filename(filename)
    safe_language = sanitize_filename(language)  # Also sanitize language

    audio_path = Path(settings.PROJECTS_DIR) / safe_project_name / safe_language / safe_filename

    # Additional security check: ensure path is within PROJECTS_DIR
    try:
        audio_path = audio_path.resolve()
        projects_dir = Path(settings.PROJECTS_DIR).resolve()
        if not str(audio_path).startswith(str(projects_dir)):
            logger.warning(f"Path traversal attempt in audio endpoint: {project_name}/{filename}")
            raise HTTPException(status_code=400, detail="Invalid path")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(audio_path, media_type="audio/mpeg")


@router.post("/estimate-duration")
async def estimate_duration(request: dict):
    """Estimate audio duration for text (without generating audio)

    Uses POST to handle long text content without URL length limits.
    """
    text = request.get("text", "")
    language = request.get("language", "en")

    # Average words per second by language
    wps = {
        "en": 2.5, "es": 2.3, "fr": 2.4, "de": 2.2,
        "hi": 2.8, "zh": 3.5, "ja": 3.0, "ko": 2.8
    }.get(language, 2.5)

    word_count = len(text.split())
    estimated_duration = word_count / wps

    return {
        "text_length": len(text),
        "word_count": word_count,
        "estimated_duration": round(estimated_duration, 2),
        "words_per_second": wps,
        "language": language
    }


@router.get("/languages")
async def get_supported_languages():
    """Get list of supported languages with best voices (for default/edge-tts)"""
    languages = [
        {"code": "en", "name": "English", "best_voice": "en-US-AvaMultilingualNeural"},
        {"code": "es", "name": "Spanish", "best_voice": "es-ES-ElviraNeural"},
        {"code": "fr", "name": "French", "best_voice": "fr-FR-VivienneMultilingualNeural"},
        {"code": "de", "name": "German", "best_voice": "de-DE-KatjaNeural"},
        {"code": "it", "name": "Italian", "best_voice": "it-IT-ElsaNeural"},
        {"code": "pt", "name": "Portuguese", "best_voice": "pt-BR-FranciscaNeural"},
        {"code": "zh", "name": "Chinese", "best_voice": "zh-CN-XiaoxiaoNeural"},
        {"code": "ja", "name": "Japanese", "best_voice": "ja-JP-NanamiNeural"},
        {"code": "ko", "name": "Korean", "best_voice": "ko-KR-HyunsuMultilingualNeural"},
        {"code": "hi", "name": "Hindi", "best_voice": "hi-IN-MadhurNeural"},
        {"code": "ta", "name": "Tamil", "best_voice": "ta-IN-ValluvarNeural"},
        {"code": "te", "name": "Telugu", "best_voice": "te-IN-ShrutiNeural"},
        {"code": "kn", "name": "Kannada", "best_voice": "kn-IN-GaganNeural"},
        {"code": "ml", "name": "Malayalam", "best_voice": "ml-IN-SobhanaNeural"},
        {"code": "ar", "name": "Arabic", "best_voice": "ar-SA-ZariyahNeural"},
        {"code": "ru", "name": "Russian", "best_voice": "ru-RU-SvetlanaNeural"},
    ]
    return {"languages": languages}


# Provider-specific language lists
COQUI_LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "es", "name": "Spanish"},
    {"code": "fr", "name": "French"},
    {"code": "de", "name": "German"},
    {"code": "it", "name": "Italian"},
    {"code": "pt", "name": "Portuguese"},
    {"code": "pl", "name": "Polish"},
    {"code": "tr", "name": "Turkish"},
    {"code": "ru", "name": "Russian"},
    {"code": "nl", "name": "Dutch"},
    {"code": "cs", "name": "Czech"},
    {"code": "ar", "name": "Arabic"},
    {"code": "zh-cn", "name": "Chinese (Simplified)"},
    {"code": "ja", "name": "Japanese"},
    {"code": "hu", "name": "Hungarian"},
    {"code": "ko", "name": "Korean"},
]

# Full edge-tts languages (commonly used subset)
EDGE_TTS_LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "es", "name": "Spanish"},
    {"code": "fr", "name": "French"},
    {"code": "de", "name": "German"},
    {"code": "it", "name": "Italian"},
    {"code": "pt", "name": "Portuguese"},
    {"code": "zh", "name": "Chinese"},
    {"code": "ja", "name": "Japanese"},
    {"code": "ko", "name": "Korean"},
    {"code": "hi", "name": "Hindi"},
    {"code": "ta", "name": "Tamil"},
    {"code": "te", "name": "Telugu"},
    {"code": "kn", "name": "Kannada"},
    {"code": "ml", "name": "Malayalam"},
    {"code": "bn", "name": "Bengali"},
    {"code": "gu", "name": "Gujarati"},
    {"code": "mr", "name": "Marathi"},
    {"code": "ar", "name": "Arabic"},
    {"code": "ru", "name": "Russian"},
    {"code": "nl", "name": "Dutch"},
    {"code": "pl", "name": "Polish"},
    {"code": "tr", "name": "Turkish"},
    {"code": "vi", "name": "Vietnamese"},
    {"code": "th", "name": "Thai"},
    {"code": "id", "name": "Indonesian"},
    {"code": "ms", "name": "Malay"},
    {"code": "fil", "name": "Filipino"},
    {"code": "sv", "name": "Swedish"},
    {"code": "da", "name": "Danish"},
    {"code": "nb", "name": "Norwegian"},
    {"code": "fi", "name": "Finnish"},
    {"code": "el", "name": "Greek"},
    {"code": "he", "name": "Hebrew"},
    {"code": "uk", "name": "Ukrainian"},
    {"code": "cs", "name": "Czech"},
    {"code": "hu", "name": "Hungarian"},
    {"code": "ro", "name": "Romanian"},
    {"code": "sk", "name": "Slovak"},
    {"code": "bg", "name": "Bulgarian"},
    {"code": "hr", "name": "Croatian"},
    {"code": "sr", "name": "Serbian"},
    {"code": "sl", "name": "Slovenian"},
    {"code": "af", "name": "Afrikaans"},
    {"code": "sw", "name": "Swahili"},
]


@router.get("/providers/{provider}/languages")
async def get_provider_languages(provider: str):
    """
    Get supported languages for a specific TTS provider.

    Different providers support different languages:
    - edge_tts: 40+ languages
    - coqui: 16 languages (XTTS v2)
    """
    provider_lower = provider.lower()

    if provider_lower == "coqui":
        return {"provider": provider, "languages": COQUI_LANGUAGES}
    elif provider_lower in ["edge_tts", "edge-tts", "edgetts"]:
        return {"provider": provider, "languages": EDGE_TTS_LANGUAGES}
    else:
        # Default to edge-tts languages
        return {"provider": provider, "languages": EDGE_TTS_LANGUAGES}


# ============================================================================
# Provider Management Endpoints
# ============================================================================

@router.get("/providers", response_model=ProviderStatusResponse)
async def get_providers():
    """
    Get all available TTS providers and their status.

    Returns information about each provider including:
    - Whether it's local or cloud-based
    - Whether it requires consent
    - Current availability status
    - Which is the default provider
    """
    try:
        statuses = await tts_service.get_provider_status()
        default_provider = tts_service.get_current_provider()

        providers = []
        for status in statuses:
            providers.append(ProviderInfo(
                name=status["provider"],
                display_name=status["name"],
                description=status.get("description", ""),
                is_local=status["capabilities"]["is_local"],
                requires_consent=status["capabilities"]["requires_consent"],
                supports_word_timing=status["capabilities"]["word_timing"],
                supports_voice_cloning=status["capabilities"]["voice_cloning"],
                available=status.get("available", False),
                is_default=status.get("is_default", False),
            ))

        return ProviderStatusResponse(
            default_provider=default_provider,
            providers=providers
        )

    except Exception as e:
        logger.error(f"Failed to get providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/providers/default")
async def set_default_provider(
    request: SetProviderRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Set the default TTS provider.

    Valid providers:
    - 'edge_tts': Microsoft Edge TTS (cloud, requires consent)
    - 'coqui': Coqui TTS (local, no consent required)
    """
    try:
        # Validate provider
        try:
            TTSProviderType(request.provider)
        except ValueError:
            valid_providers = [p.value for p in TTSProviderType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider. Valid options: {valid_providers}"
            )

        success = tts_service.set_provider(request.provider)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to set provider"
            )

        return {
            "success": True,
            "default_provider": request.provider,
            "message": f"Default TTS provider set to {request.provider}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/{provider}/voices")
async def get_provider_voices(
    provider: str,
    language: Optional[str] = Query(None, description="Filter by language code")
):
    """
    Get available voices for a specific provider.

    Args:
        provider: Provider name ('edge_tts' or 'coqui')
        language: Optional language filter (e.g., 'en', 'es')
    """
    try:
        # Validate provider
        try:
            TTSProviderType(provider)
        except ValueError:
            valid_providers = [p.value for p in TTSProviderType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider. Valid options: {valid_providers}"
            )

        voices = await tts_service.get_voices_for_provider(provider, language)

        return {
            "provider": provider,
            "language": language,
            "voices": voices,
            "total": len(voices)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provider voices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/{provider}/status")
async def get_provider_status(provider: str):
    """
    Get detailed status for a specific provider.

    Includes installation status, availability, and capabilities.
    """
    try:
        # Validate provider
        try:
            TTSProviderType(provider)
        except ValueError:
            valid_providers = [p.value for p in TTSProviderType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider. Valid options: {valid_providers}"
            )

        statuses = await tts_service.get_provider_status()

        for status in statuses:
            if status["provider"] == provider:
                return status

        raise HTTPException(status_code=404, detail="Provider not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provider status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/info")
async def get_provider_info():
    """
    Get static information about all providers.

    This is a lightweight endpoint that doesn't check availability.
    """
    return tts_service.get_provider_info()


@router.post("/generate-with-provider")
async def generate_with_provider(
    request: TTSGenerateRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Generate TTS audio using a specific provider.

    If no provider is specified, uses the default provider.
    Falls back to Edge TTS if the specified provider is unavailable.
    """
    try:
        # Use provider-aware generation
        audio_path, subtitle_path = await tts_service.generate_audio_with_provider(
            text=request.text,
            language=request.language,
            voice=request.voice_id,
            project_name=request.project_name,
            segment_name=request.segment_name,
            rate=request.rate,
            volume=request.volume,
            pitch=request.pitch,
            orientation=request.orientation,
            provider=getattr(request, 'provider', None)
        )

        duration = FFmpegUtils.get_media_duration(audio_path)

        return TTSGenerateResponse(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            duration=duration or 0,
            cached=False
        )

    except Exception as e:
        logger.error(f"Provider generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Voice Cloning Endpoints (Coqui TTS only)
# ============================================================================

# Voice samples storage directory
VOICE_SAMPLES_DIR = Path(settings.STORAGE_DIR) / "voice_samples"
VOICE_SAMPLES_METADATA_FILE = VOICE_SAMPLES_DIR / "metadata.json"

# Supported audio formats for voice samples
SUPPORTED_AUDIO_FORMATS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}

# Maximum file size (10MB)
MAX_VOICE_SAMPLE_SIZE = 10 * 1024 * 1024


class VoiceSampleInfo(BaseModel):
    """Voice sample information"""
    id: str
    name: str
    filename: str
    duration: float
    created_at: str
    language: str
    file_size: int
    audio_url: str


class VoiceSampleListResponse(BaseModel):
    """Response for voice samples list"""
    samples: List[VoiceSampleInfo]
    total: int


class VoiceCloneRequest(BaseModel):
    """Request for voice cloning generation"""
    voice_sample_id: str  # Primary sample ID
    additional_sample_ids: List[str] = []  # Additional samples for better quality
    text: str
    language: str = "en"
    project_name: str = "default"
    segment_name: Optional[str] = None
    orientation: str = "horizontal"
    # XTTS inference parameters
    temperature: float = 0.65  # Softmax temperature (lower = more deterministic)
    speed: float = 1.0  # Speech speed (1.0 = normal)


class VoiceCloneResponse(BaseModel):
    """Response for voice cloning generation"""
    audio_url: str
    subtitle_url: Optional[str] = None
    duration: float
    voice_sample_name: str


class VoiceCloneStartResponse(BaseModel):
    """Response for starting a voice clone job"""
    clone_id: str
    status: str
    message: str


class VoiceCloneStatusResponse(BaseModel):
    """Response for voice clone job status"""
    clone_id: str
    status: str
    progress: int
    stage: str
    message: str
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[str] = None


async def send_clone_progress(
    clone_id: str,
    stage: str,
    message: str,
    progress: int,
    status: str = "processing",
    **kwargs
):
    """Send progress update via WebSocket for voice cloning"""
    if clone_id in clone_progress_connections:
        try:
            await clone_progress_connections[clone_id].send_json({
                "stage": stage,
                "message": message,
                "progress": progress,
                "status": status,
                **kwargs
            })
        except Exception:
            pass

    # Update job status
    if clone_id in active_clone_jobs:
        active_clone_jobs[clone_id]["progress"] = progress
        active_clone_jobs[clone_id]["stage"] = stage
        active_clone_jobs[clone_id]["message"] = message
        active_clone_jobs[clone_id]["status"] = status


async def run_voice_cloning(
    clone_id: str,
    voice_sample_path: str,
    text: str,
    output_path: str,
    language: str,
    voice_sample_name: str
):
    """
    Run voice cloning in a separate subprocess for true non-blocking behavior.

    The worker runs as a completely separate Python process,
    communicating progress via JSON lines on stdout.
    """
    stderr_log_path = None
    stderr_file = None

    try:
        active_clone_jobs[clone_id]["status"] = "processing"

        # Build command for voice clone worker subprocess
        cmd = [
            sys.executable,  # Use same Python interpreter
            str(VOICE_CLONE_WORKER_PATH),
            voice_sample_path,
            text,
            output_path,
            language
        ]

        logger.info(f"[VoiceClone {clone_id}] Starting worker: {cmd[0]} {cmd[1]}")

        # Create a log file for stderr
        stderr_log_path = Path(settings.TEMP_DIR) / f"clone_{clone_id}_stderr.log"
        Path(settings.TEMP_DIR).mkdir(parents=True, exist_ok=True)
        stderr_file = open(stderr_log_path, 'w')

        # Start subprocess with detached process group
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=stderr_file,
            cwd=str(Path(__file__).parent.parent.parent.parent),  # Project root
            start_new_session=True  # Detach from parent process group
        )

        active_clone_processes[clone_id] = process
        logger.info(f"[VoiceClone {clone_id}] Worker started with PID: {process.pid}")

        # Read stdout for real-time progress updates
        result_data = None
        try:
            while True:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=600  # 10 minute timeout
                )
                if not line:
                    break

                try:
                    line_text = line.decode('utf-8').strip()
                    if line_text:
                        data = json.loads(line_text)

                        if data.get('type') == 'progress':
                            stage = data.get('stage', 'processing')
                            message = data.get('message', 'Processing...')
                            progress = data.get('progress', 0)

                            logger.info(f"[VoiceClone {clone_id}] {stage}: {message} ({progress}%)")

                            await send_clone_progress(
                                clone_id,
                                stage,
                                message,
                                progress
                            )

                        elif data.get('type') == 'result':
                            result_data = data

                        elif data.get('type') == 'error':
                            logger.error(f"[VoiceClone {clone_id}] Error: {data.get('message')}")
                            raise Exception(data.get('message', 'Unknown error'))

                except json.JSONDecodeError:
                    # Not JSON, might be log output - ignore
                    pass

        except asyncio.TimeoutError:
            logger.error(f"[VoiceClone {clone_id}] Worker timed out")
            process.kill()
            raise Exception("Voice cloning timed out")

        # Wait for process to complete
        await process.wait()

        logger.info(f"[VoiceClone {clone_id}] Worker finished with return code: {process.returncode}")

        # Check exit code and result
        if process.returncode == 0 and result_data and result_data.get('success'):
            duration = result_data.get('duration', 0)
            output_file = Path(output_path)

            if output_file.exists():
                # Calculate audio URL
                audio_url = f"/storage/{output_file.relative_to(settings.STORAGE_DIR)}"

                active_clone_jobs[clone_id].update({
                    "status": "completed",
                    "progress": 100,
                    "audio_url": audio_url,
                    "duration": duration,
                    "voice_sample_name": voice_sample_name
                })

                logger.info(f"[VoiceClone {clone_id}] COMPLETED - File: {output_path} ({duration:.1f}s)")

                await send_clone_progress(
                    clone_id, "completed",
                    "Voice cloning completed!", 100,
                    status="completed",
                    audio_url=audio_url,
                    duration=duration
                )
            else:
                raise Exception("Output file was not created")
        else:
            # Read stderr from log file for error message
            error_msg = "Voice cloning failed"
            if result_data and result_data.get('error'):
                error_msg = result_data.get('error')
            elif stderr_log_path and stderr_log_path.exists():
                stderr_file.close()
                stderr_file = None
                with open(stderr_log_path, 'r') as f:
                    stderr_lines = f.readlines()
                    if stderr_lines:
                        error_msg = "".join(stderr_lines[-10:])
            raise Exception(error_msg)

    except Exception as e:
        active_clone_jobs[clone_id].update({
            "status": "failed",
            "error": str(e)
        })
        await send_clone_progress(
            clone_id, "error", f"Voice cloning failed: {str(e)}", 0,
            status="failed"
        )
    finally:
        # Clean up
        if stderr_file:
            stderr_file.close()
        if stderr_log_path and stderr_log_path.exists():
            try:
                stderr_log_path.unlink()
            except Exception:
                pass
        if clone_id in active_clone_processes:
            del active_clone_processes[clone_id]


def _load_voice_samples_metadata() -> dict:
    """Load voice samples metadata from file"""
    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    if VOICE_SAMPLES_METADATA_FILE.exists():
        try:
            return json.loads(VOICE_SAMPLES_METADATA_FILE.read_text())
        except Exception:
            return {"samples": {}}
    return {"samples": {}}


def _save_voice_samples_metadata(metadata: dict):
    """Save voice samples metadata to file"""
    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    VOICE_SAMPLES_METADATA_FILE.write_text(json.dumps(metadata, indent=2))


@router.get("/voice-samples", response_model=VoiceSampleListResponse)
async def list_voice_samples(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get all uploaded voice samples (requires authentication).

    Voice samples can be used for voice cloning with Coqui TTS.
    """
    try:
        metadata = _load_voice_samples_metadata()
        samples = []

        for sample_id, info in metadata.get("samples", {}).items():
            sample_path = VOICE_SAMPLES_DIR / info["filename"]
            if sample_path.exists():
                samples.append(VoiceSampleInfo(
                    id=sample_id,
                    name=info["name"],
                    filename=info["filename"],
                    duration=info.get("duration", 0),
                    created_at=info["created_at"],
                    language=info.get("language", "en"),
                    file_size=info.get("file_size", 0),
                    audio_url=f"/storage/voice_samples/{info['filename']}"
                ))

        # Sort by creation date, newest first
        samples.sort(key=lambda x: x.created_at, reverse=True)

        return VoiceSampleListResponse(samples=samples, total=len(samples))

    except Exception as e:
        logger.error(f"Failed to list voice samples: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice-samples")
async def upload_voice_sample(
    file: UploadFile = File(..., description="Audio file for voice cloning (WAV, MP3, FLAC, OGG, M4A)"),
    name: str = Form(..., description="Display name for the voice sample"),
    language: str = Form("en", description="Language of the speaker"),
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Upload a voice sample for voice cloning.

    Requirements:
    - Audio file (WAV, MP3, FLAC, OGG, or M4A)
    - 5-30 seconds of clear speech recommended
    - Single speaker, minimal background noise
    - Maximum file size: 10MB

    The voice sample will be used to clone the speaker's voice
    when generating TTS audio with Coqui TTS.
    """
    try:
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_AUDIO_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format. Supported: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
            )

        # Read file content
        content = await file.read()

        # Check file size
        if len(content) > MAX_VOICE_SAMPLE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_VOICE_SAMPLE_SIZE // (1024*1024)}MB"
            )

        # Generate unique ID and filename
        sample_id = str(uuid.uuid4())[:8]
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        filename = f"{safe_name}_{sample_id}{file_ext}"

        # Save file
        VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        sample_path = VOICE_SAMPLES_DIR / filename

        with open(sample_path, "wb") as f:
            f.write(content)

        # Get audio duration
        duration = FFmpegUtils.get_media_duration(str(sample_path)) or 0

        # Update metadata
        metadata = _load_voice_samples_metadata()
        metadata["samples"][sample_id] = {
            "name": name,
            "filename": filename,
            "duration": duration,
            "created_at": datetime.now().isoformat(),
            "language": language,
            "file_size": len(content),
        }
        _save_voice_samples_metadata(metadata)

        logger.info(f"Uploaded voice sample: {name} ({filename}, {duration:.1f}s)")

        return {
            "success": True,
            "sample": VoiceSampleInfo(
                id=sample_id,
                name=name,
                filename=filename,
                duration=duration,
                created_at=metadata["samples"][sample_id]["created_at"],
                language=language,
                file_size=len(content),
                audio_url=f"/storage/voice_samples/{filename}"
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload voice sample: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/voice-samples/{sample_id}")
async def delete_voice_sample(
    sample_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Delete a voice sample.

    This permanently removes the voice sample and it cannot be recovered.
    """
    try:
        metadata = _load_voice_samples_metadata()

        if sample_id not in metadata.get("samples", {}):
            raise HTTPException(status_code=404, detail="Voice sample not found")

        sample_info = metadata["samples"][sample_id]
        sample_path = VOICE_SAMPLES_DIR / sample_info["filename"]

        # Delete file
        if sample_path.exists():
            sample_path.unlink()

        # Remove from metadata
        del metadata["samples"][sample_id]
        _save_voice_samples_metadata(metadata)

        logger.info(f"Deleted voice sample: {sample_info['name']} ({sample_id})")

        return {
            "success": True,
            "message": f"Voice sample '{sample_info['name']}' deleted"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete voice sample: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voice-samples/{sample_id}")
async def get_voice_sample(
    sample_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get details for a specific voice sample (requires authentication).
    """
    try:
        metadata = _load_voice_samples_metadata()

        if sample_id not in metadata.get("samples", {}):
            raise HTTPException(status_code=404, detail="Voice sample not found")

        info = metadata["samples"][sample_id]
        sample_path = VOICE_SAMPLES_DIR / info["filename"]

        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="Voice sample file not found")

        return VoiceSampleInfo(
            id=sample_id,
            name=info["name"],
            filename=info["filename"],
            duration=info.get("duration", 0),
            created_at=info["created_at"],
            language=info.get("language", "en"),
            file_size=info.get("file_size", 0),
            audio_url=f"/storage/voice_samples/{info['filename']}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice sample: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clone-voice", response_model=VoiceCloneResponse)
async def clone_voice(
    request: VoiceCloneRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Generate audio using a cloned voice.

    This uses Coqui TTS to clone the voice from the specified sample
    and generate speech with that voice.

    Requirements:
    - Coqui TTS must be installed and available
    - A valid voice sample must be uploaded first
    - Text to synthesize

    The cloned voice maintains the characteristics of the original
    speaker while speaking the new text.
    """
    try:
        # Check if Coqui is available
        current_provider = tts_service.get_current_provider()
        if current_provider != "coqui":
            raise HTTPException(
                status_code=400,
                detail="Voice cloning requires Coqui TTS. Please set it as the default provider."
            )

        # Get voice sample info
        metadata = _load_voice_samples_metadata()

        if request.voice_sample_id not in metadata.get("samples", {}):
            raise HTTPException(status_code=404, detail="Voice sample not found")

        sample_info = metadata["samples"][request.voice_sample_id]
        sample_path = VOICE_SAMPLES_DIR / sample_info["filename"]

        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="Voice sample file not found")

        # Collect all sample paths (primary + additional)
        all_sample_paths = [sample_path]
        for additional_id in request.additional_sample_ids:
            if additional_id in metadata.get("samples", {}):
                additional_info = metadata["samples"][additional_id]
                additional_path = VOICE_SAMPLES_DIR / additional_info["filename"]
                if additional_path.exists():
                    all_sample_paths.append(additional_path)
                else:
                    logger.warning(f"Additional voice sample not found: {additional_id}")

        # Get Coqui provider
        from backend.tts_providers import get_provider
        provider = get_provider("coqui")  # get_provider is not async

        if not provider:
            raise HTTPException(
                status_code=503,
                detail="Coqui TTS provider not found"
            )

        # is_available is async, need to await it
        if not await provider.is_available():
            raise HTTPException(
                status_code=503,
                detail="Coqui TTS is not available. Please ensure it is installed."
            )

        # Generate unique output path
        segment_name = request.segment_name or f"cloned_{request.voice_sample_id}_{uuid.uuid4().hex[:8]}"
        project_dir = Path(settings.PROJECTS_DIR) / request.project_name / request.language
        project_dir.mkdir(parents=True, exist_ok=True)

        output_path = project_dir / f"{segment_name}.wav"
        subtitle_path = project_dir / f"{segment_name}.srt"

        # Generate audio with cloned voice
        # Pass all sample paths for better cloning quality (per Coqui XTTS docs)
        result = await provider.clone_voice(
            audio_sample_paths=all_sample_paths,
            text=request.text,
            output_path=output_path,
            language=request.language,
            voice_sample_name=sample_info["name"],
            temperature=request.temperature,
            speed=request.speed,
        )

        # Generate subtitles from word timings
        if result.word_timings:
            from backend.tts_providers.base import TTSProvider
            # Use the base provider's subtitle generation
            subtitle_content = provider._generate_word_timed_subtitles(
                result.word_timings,
                request.text,
                request.orientation
            )
            subtitle_path.write_text(subtitle_content, encoding="utf-8")
            subtitle_url = f"/storage/{subtitle_path.relative_to(settings.STORAGE_DIR)}"
        else:
            subtitle_url = None

        logger.info(f"Generated cloned voice audio: {output_path} ({result.duration_seconds:.1f}s)")

        return VoiceCloneResponse(
            audio_url=f"/storage/{output_path.relative_to(settings.STORAGE_DIR)}",
            subtitle_url=subtitle_url,
            duration=result.duration_seconds,
            voice_sample_name=sample_info["name"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice cloning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clone-voice/preview", response_model=VoiceCloneStartResponse)
async def preview_cloned_voice(
    voice_sample_id: str = Form(...),
    text: str = Form(default="Hello, this is a preview of my cloned voice."),
    language: str = Form(default="en"),
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Start a voice cloning preview job (non-blocking).

    Returns immediately with a clone_id. Connect to the WebSocket endpoint
    /api/v1/tts/clone-voice/progress/{clone_id} or poll /api/v1/tts/clone-voice/status/{clone_id}
    to get progress updates.

    Uses a short text to quickly demonstrate how the cloned voice sounds.
    """
    try:
        # Validate voice sample
        metadata = _load_voice_samples_metadata()

        if voice_sample_id not in metadata.get("samples", {}):
            raise HTTPException(status_code=404, detail="Voice sample not found")

        sample_info = metadata["samples"][voice_sample_id]
        sample_path = VOICE_SAMPLES_DIR / sample_info["filename"]

        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="Voice sample file not found")

        # Generate clone job ID
        clone_id = str(uuid.uuid4())[:8]

        # Generate unique output path
        segment_name = f"clone_preview_{voice_sample_id}_{hash(text) % 10000}"
        project_dir = Path(settings.PROJECTS_DIR) / "_previews" / language
        project_dir.mkdir(parents=True, exist_ok=True)
        output_path = project_dir / f"{segment_name}.wav"

        # Create job entry
        active_clone_jobs[clone_id] = {
            "status": "queued",
            "progress": 0,
            "stage": "initializing",
            "message": "Starting voice cloning...",
            "voice_sample_id": voice_sample_id,
            "voice_sample_name": sample_info["name"],
            "text": text[:200],
            "language": language,
            "output_path": str(output_path),
            "started_at": datetime.now().isoformat()
        }

        # Start voice cloning in background (non-blocking)
        asyncio.create_task(
            run_voice_cloning(
                clone_id=clone_id,
                voice_sample_path=str(sample_path),
                text=text[:200],
                output_path=str(output_path),
                language=language,
                voice_sample_name=sample_info["name"]
            )
        )

        logger.info(f"[VoiceClone {clone_id}] Preview job started for sample: {sample_info['name']}")

        return VoiceCloneStartResponse(
            clone_id=clone_id,
            status="queued",
            message=f"Voice cloning started. Connect to WebSocket for progress updates."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clone preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clone-voice/status/{clone_id}", response_model=VoiceCloneStatusResponse)
async def get_clone_status(clone_id: str):
    """
    Get the status of a voice cloning job.

    Poll this endpoint to check progress if not using WebSocket.
    """
    if clone_id not in active_clone_jobs:
        raise HTTPException(status_code=404, detail="Clone job not found")

    job = active_clone_jobs[clone_id]

    return VoiceCloneStatusResponse(
        clone_id=clone_id,
        status=job.get("status", "unknown"),
        progress=job.get("progress", 0),
        stage=job.get("stage", ""),
        message=job.get("message", ""),
        audio_url=job.get("audio_url"),
        duration=job.get("duration"),
        error=job.get("error")
    )


@router.websocket("/clone-voice/progress/{clone_id}")
async def clone_progress_websocket(websocket: WebSocket, clone_id: str):
    """WebSocket endpoint for voice cloning progress updates."""
    await websocket.accept()
    clone_progress_connections[clone_id] = websocket
    logger.info(f"[VoiceClone {clone_id}] WebSocket connected")

    try:
        # Send current status immediately
        if clone_id in active_clone_jobs:
            job = active_clone_jobs[clone_id]
            await websocket.send_json({
                "stage": job.get("stage", "initializing"),
                "message": job.get("message", "Starting..."),
                "progress": job.get("progress", 0),
                "status": job.get("status", "queued"),
                "audio_url": job.get("audio_url"),
                "duration": job.get("duration")
            })

            # If already completed, send completion
            if job.get("status") == "completed":
                await websocket.send_json({
                    "stage": "completed",
                    "message": "Voice cloning completed!",
                    "progress": 100,
                    "status": "completed",
                    "audio_url": job.get("audio_url"),
                    "duration": job.get("duration")
                })

        # Keep connection alive
        ping_failures = 0
        max_ping_failures = 3

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "pong":
                    ping_failures = 0
                elif data == "status":
                    if clone_id in active_clone_jobs:
                        job = active_clone_jobs[clone_id]
                        await websocket.send_json({
                            "stage": job.get("stage", ""),
                            "message": job.get("message", ""),
                            "progress": job.get("progress", 0),
                            "status": job.get("status", ""),
                            "audio_url": job.get("audio_url"),
                            "duration": job.get("duration")
                        })
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text("ping")
                    ping_failures += 1
                    if ping_failures >= max_ping_failures:
                        logger.warning(f"[VoiceClone {clone_id}] WebSocket ping failures exceeded")
                        break
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"[VoiceClone {clone_id}] WebSocket disconnected by client")
    except Exception as e:
        logger.warning(f"[VoiceClone {clone_id}] WebSocket error: {e}")
    finally:
        if clone_id in clone_progress_connections:
            del clone_progress_connections[clone_id]
        logger.info(f"[VoiceClone {clone_id}] WebSocket closed")


@router.delete("/clone-voice/cancel/{clone_id}")
async def cancel_clone_job(
    clone_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Cancel a voice cloning job."""
    if clone_id not in active_clone_jobs:
        raise HTTPException(status_code=404, detail="Clone job not found")

    job = active_clone_jobs[clone_id]

    if job.get("status") == "processing":
        # Kill the subprocess if running
        if clone_id in active_clone_processes:
            process = active_clone_processes[clone_id]
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
            except Exception:
                pass

        job["status"] = "failed"
        job["error"] = "Cancelled by user"
        await send_clone_progress(clone_id, "error", "Voice cloning cancelled", 0)

    return {"message": "Clone job cancelled", "clone_id": clone_id}
