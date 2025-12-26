"""TTS (Text-to-Speech) API routes"""

import sys
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.tts_service import TTSService
from backend.ffmpeg_utils import FFmpegUtils
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

router = APIRouter()

# Shared TTS service instance
tts_service = TTSService()


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
async def preview_voice(request: VoicePreviewRequest):
    """Generate a preview audio for a voice"""
    try:
        # Generate preview audio
        audio_path, _ = await tts_service.generate_audio(
            text=request.text,
            language="en",  # Preview always uses the voice's language
            voice=request.voice_id,
            project_name="_previews",
            segment_name=f"preview_{request.voice_id[:20]}",
            rate=request.rate,
            volume=request.volume,
            pitch=request.pitch
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
async def generate_tts(request: TTSGenerateRequest):
    """Generate TTS audio for text"""
    try:
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

        # Generate new audio
        audio_path, subtitle_path = await tts_service.generate_audio(
            text=request.text,
            language=request.language,
            voice=request.voice_id,
            project_name=request.project_name,
            segment_name=request.segment_name,
            rate=request.rate,
            volume=request.volume,
            pitch=request.pitch,
            orientation=request.orientation
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
async def check_connectivity():
    """Check TTS service connectivity"""
    try:
        status = await tts_service.check_tts_connectivity()
        return TTSConnectivityStatus(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/{project_name}/{filename}")
async def get_audio_file(project_name: str, filename: str, language: str = "en"):
    """Serve generated audio file"""
    audio_path = Path(settings.PROJECTS_DIR) / project_name / language / filename

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
    """Get list of supported languages with best voices"""
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
