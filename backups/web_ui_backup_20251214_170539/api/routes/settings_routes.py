"""Settings API routes"""

import sys
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config import settings

router = APIRouter()


class AppSettings(BaseModel):
    """Application settings response"""
    storage_dir: str
    projects_dir: str
    temp_dir: str
    cache_dir: str
    output_dir: str
    ffmpeg_path: str
    ffprobe_path: str
    tts_proxy_enabled: bool
    tts_proxy_url: Optional[str]
    default_quality: str
    tts_volume_boost: int
    bgm_volume_reduction: int


class UpdateSettings(BaseModel):
    """Settings update request"""
    tts_proxy_enabled: Optional[bool] = None
    tts_proxy_url: Optional[str] = None
    default_quality: Optional[str] = None
    tts_volume_boost: Optional[int] = None
    bgm_volume_reduction: Optional[int] = None


class LLMSettings(BaseModel):
    """LLM provider settings"""
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    ollama_endpoint: str = "http://localhost:11434"
    custom_endpoint: Optional[str] = None
    custom_api_key: Optional[str] = None
    default_provider: str = "ollama"
    default_model: str = "llama3.2:3b"


# In-memory LLM settings (would be persisted in a real app)
llm_settings = LLMSettings()


@router.get("/", response_model=AppSettings)
async def get_settings():
    """Get current application settings"""
    return AppSettings(
        storage_dir=settings.STORAGE_DIR,
        projects_dir=settings.PROJECTS_DIR,
        temp_dir=settings.TEMP_DIR,
        cache_dir=settings.CACHE_DIR,
        output_dir=settings.OUTPUT_DIR,
        ffmpeg_path=settings.FFMPEG_PATH,
        ffprobe_path=settings.FFPROBE_PATH,
        tts_proxy_enabled=settings.TTS_PROXY_ENABLED,
        tts_proxy_url=settings.TTS_PROXY_URL,
        default_quality="balanced",
        tts_volume_boost=settings.TTS_VOLUME_BOOST,
        bgm_volume_reduction=settings.BGM_VOLUME_REDUCTION
    )


@router.put("/")
async def update_settings(update: UpdateSettings):
    """Update application settings"""
    # Note: In a real app, these would be persisted to .env or database
    if update.tts_proxy_enabled is not None:
        settings.TTS_PROXY_ENABLED = update.tts_proxy_enabled

    if update.tts_proxy_url is not None:
        settings.TTS_PROXY_URL = update.tts_proxy_url

    if update.tts_volume_boost is not None:
        if not 0 <= update.tts_volume_boost <= 30:
            raise HTTPException(status_code=400, detail="TTS boost must be 0-30 dB")
        settings.TTS_VOLUME_BOOST = update.tts_volume_boost

    if update.bgm_volume_reduction is not None:
        if not 0 <= update.bgm_volume_reduction <= 40:
            raise HTTPException(status_code=400, detail="BGM reduction must be 0-40 dB")
        settings.BGM_VOLUME_REDUCTION = update.bgm_volume_reduction

    return {"message": "Settings updated successfully"}


@router.get("/llm", response_model=LLMSettings)
async def get_llm_settings():
    """Get LLM provider settings (API keys masked)"""
    masked = LLMSettings(
        openai_api_key="***" if llm_settings.openai_api_key else None,
        anthropic_api_key="***" if llm_settings.anthropic_api_key else None,
        google_api_key="***" if llm_settings.google_api_key else None,
        ollama_endpoint=llm_settings.ollama_endpoint,
        custom_endpoint=llm_settings.custom_endpoint,
        custom_api_key="***" if llm_settings.custom_api_key else None,
        default_provider=llm_settings.default_provider,
        default_model=llm_settings.default_model
    )
    return masked


@router.put("/llm")
async def update_llm_settings(update: LLMSettings):
    """Update LLM provider settings"""
    global llm_settings

    if update.openai_api_key and update.openai_api_key != "***":
        llm_settings.openai_api_key = update.openai_api_key

    if update.anthropic_api_key and update.anthropic_api_key != "***":
        llm_settings.anthropic_api_key = update.anthropic_api_key

    if update.google_api_key and update.google_api_key != "***":
        llm_settings.google_api_key = update.google_api_key

    if update.ollama_endpoint:
        llm_settings.ollama_endpoint = update.ollama_endpoint

    if update.custom_endpoint is not None:
        llm_settings.custom_endpoint = update.custom_endpoint

    if update.custom_api_key and update.custom_api_key != "***":
        llm_settings.custom_api_key = update.custom_api_key

    if update.default_provider:
        llm_settings.default_provider = update.default_provider

    if update.default_model:
        llm_settings.default_model = update.default_model

    return {"message": "LLM settings updated successfully"}


@router.get("/system")
async def get_system_info():
    """Get system information"""
    import platform
    import shutil

    # Check FFmpeg
    ffmpeg_available = shutil.which("ffmpeg") is not None
    ffprobe_available = shutil.which("ffprobe") is not None

    # Get disk space
    storage_path = Path(settings.STORAGE_DIR)
    try:
        disk_usage = shutil.disk_usage(storage_path)
        disk_free_gb = disk_usage.free / (1024**3)
        disk_total_gb = disk_usage.total / (1024**3)
    except:
        disk_free_gb = 0
        disk_total_gb = 0

    # Count projects
    projects_path = Path(settings.PROJECTS_DIR)
    project_count = len(list(projects_path.glob("*/project.json"))) if projects_path.exists() else 0

    # Get cache size
    cache_path = Path(settings.CACHE_DIR)
    cache_size_mb = sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file()) / (1024**2) if cache_path.exists() else 0

    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "ffmpeg_available": ffmpeg_available,
        "ffprobe_available": ffprobe_available,
        "disk_free_gb": round(disk_free_gb, 2),
        "disk_total_gb": round(disk_total_gb, 2),
        "project_count": project_count,
        "cache_size_mb": round(cache_size_mb, 2),
        "storage_path": str(storage_path.absolute())
    }


@router.post("/clear-cache")
async def clear_cache():
    """Clear TTS cache"""
    import shutil

    cache_path = Path(settings.CACHE_DIR)
    if cache_path.exists():
        # Count files before clearing
        file_count = len(list(cache_path.rglob("*")))
        size_mb = sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file()) / (1024**2)

        # Clear cache
        shutil.rmtree(cache_path)
        cache_path.mkdir(parents=True, exist_ok=True)

        return {
            "message": "Cache cleared successfully",
            "files_removed": file_count,
            "space_freed_mb": round(size_mb, 2)
        }

    return {"message": "Cache was already empty", "files_removed": 0, "space_freed_mb": 0}


@router.post("/clear-temp")
async def clear_temp():
    """Clear temporary files"""
    import shutil

    temp_path = Path(settings.TEMP_DIR)
    if temp_path.exists():
        file_count = len(list(temp_path.rglob("*")))
        size_mb = sum(f.stat().st_size for f in temp_path.rglob("*") if f.is_file()) / (1024**2)

        shutil.rmtree(temp_path)
        temp_path.mkdir(parents=True, exist_ok=True)

        return {
            "message": "Temp files cleared successfully",
            "files_removed": file_count,
            "space_freed_mb": round(size_mb, 2)
        }

    return {"message": "Temp was already empty", "files_removed": 0, "space_freed_mb": 0}
