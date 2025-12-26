"""Settings API routes with persistent LLM configuration

SECURITY: All settings endpoints require authentication.
Settings modification requires admin-level access.
"""

import sys
import os
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def validate_ollama_endpoint(endpoint: str) -> tuple[bool, str]:
    """
    Validate Ollama endpoint to prevent SSRF attacks.

    SECURITY: Only allows:
    - localhost (127.0.0.1, ::1)
    - Local network addresses (192.168.x.x, 10.x.x.x, 172.16-31.x.x)

    Blocks:
    - Cloud metadata endpoints (169.254.169.254)
    - External URLs
    - File:// and other dangerous schemes

    Returns:
        (is_valid, error_message)
    """
    if not endpoint:
        return False, "Endpoint is required"

    try:
        parsed = urlparse(endpoint)

        # Only allow http and https schemes
        if parsed.scheme not in ('http', 'https'):
            return False, f"Invalid scheme '{parsed.scheme}'. Only http and https are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: no hostname"

        hostname_lower = hostname.lower()

        # Allow localhost
        if hostname_lower in ('localhost', '127.0.0.1', '::1'):
            return True, ""

        # Block cloud metadata endpoints (AWS, GCP, Azure)
        blocked_hosts = [
            '169.254.169.254',  # AWS/Azure metadata
            'metadata.google.internal',  # GCP metadata
            '100.100.100.200',  # Alibaba metadata
        ]
        if hostname_lower in blocked_hosts:
            return False, "Access to cloud metadata endpoints is not allowed"

        # Check for private network ranges
        # This allows local Ollama instances on other machines in the same network
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)

            # Allow private networks
            if ip.is_private:
                return True, ""

            # Block loopback (should be caught by localhost check, but be safe)
            if ip.is_loopback:
                return True, ""

            # Block link-local (169.254.x.x - includes metadata endpoints)
            if ip.is_link_local:
                return False, "Link-local addresses are not allowed"

            # Block all other IPs (public internet)
            return False, "Only localhost and private network addresses are allowed for Ollama"

        except ValueError:
            # Not an IP address, check if it's a hostname
            # Allow .local domains (mDNS/Bonjour)
            if hostname_lower.endswith('.local'):
                return True, ""

            # Block external domains
            return False, "Only localhost, private IPs, and .local domains are allowed for Ollama"

    except Exception as e:
        return False, f"Invalid endpoint URL: {e}"

from config import settings, load_app_settings, save_app_settings, get_default_storage_path
from utils.logger import logger
from web_ui.api.middleware.auth import get_current_user, require_admin, AuthenticatedUser

router = APIRouter()

# Settings file paths
LLM_SETTINGS_FILE = Path(settings.STORAGE_DIR) / "llm_settings.json"
APP_CONFIG_FILE = Path(settings.STORAGE_DIR) / "app_config.json"


# ============================================================================
# App Configuration Models
# ============================================================================

class AppConfigModel(BaseModel):
    """User-configurable application settings that persist across restarts"""

    # Server Configuration
    server_host: str = Field(default="localhost", description="Server hostname")
    server_port: int = Field(default=8000, ge=1024, le=65535, description="Server port")

    # TTS Settings
    tts_cache_enabled: bool = Field(default=True, description="Enable TTS audio caching")
    max_concurrent_tts: int = Field(default=2, ge=1, le=10, description="Max concurrent TTS jobs")
    tts_proxy_enabled: bool = Field(default=False, description="Enable TTS proxy")
    tts_proxy_url: Optional[str] = Field(default=None, description="Proxy URL for TTS")

    # Video Export Settings
    default_video_codec: Literal["libx264", "libx265", "libvpx-vp9"] = Field(
        default="libx264", description="Default video codec"
    )
    default_audio_codec: Literal["aac", "mp3", "opus"] = Field(
        default="aac", description="Default audio codec"
    )
    default_crf: int = Field(default=23, ge=0, le=51, description="Default CRF (0=lossless, 51=worst)")
    default_preset: Literal["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"] = Field(
        default="medium", description="Encoding preset (speed vs compression)"
    )

    # Quality Presets
    lossless_crf: int = Field(default=0, ge=0, le=10, description="Lossless quality CRF")
    high_crf: int = Field(default=18, ge=10, le=25, description="High quality CRF")
    balanced_crf: int = Field(default=23, ge=18, le=30, description="Balanced quality CRF")

    # Audio Mixing
    tts_volume_boost: int = Field(default=3, ge=0, le=30, description="TTS volume boost in dB")
    bgm_volume_reduction: int = Field(default=16, ge=0, le=40, description="BGM volume reduction in dB")
    fade_duration: float = Field(default=3.0, ge=0.0, le=10.0, description="Audio fade duration in seconds")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )

    @field_validator('tts_proxy_url')
    @classmethod
    def validate_proxy_url(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('Proxy URL must start with http:// or https://')
        return v


class AppConfigUpdate(BaseModel):
    """Partial update model for app configuration"""
    server_host: Optional[str] = None
    server_port: Optional[int] = Field(default=None, ge=1024, le=65535)
    tts_cache_enabled: Optional[bool] = None
    max_concurrent_tts: Optional[int] = Field(default=None, ge=1, le=10)
    tts_proxy_enabled: Optional[bool] = None
    tts_proxy_url: Optional[str] = None
    default_video_codec: Optional[Literal["libx264", "libx265", "libvpx-vp9"]] = None
    default_audio_codec: Optional[Literal["aac", "mp3", "opus"]] = None
    default_crf: Optional[int] = Field(default=None, ge=0, le=51)
    default_preset: Optional[Literal["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]] = None
    lossless_crf: Optional[int] = Field(default=None, ge=0, le=10)
    high_crf: Optional[int] = Field(default=None, ge=10, le=25)
    balanced_crf: Optional[int] = Field(default=None, ge=18, le=30)
    tts_volume_boost: Optional[int] = Field(default=None, ge=0, le=30)
    bgm_volume_reduction: Optional[int] = Field(default=None, ge=0, le=40)
    fade_duration: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    log_level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR"]] = None


def load_app_config() -> AppConfigModel:
    """Load app configuration from file"""
    try:
        if APP_CONFIG_FILE.exists():
            with open(APP_CONFIG_FILE, 'r') as f:
                data = json.load(f)
                logger.info(f"Loaded app config from {APP_CONFIG_FILE}")
                return AppConfigModel(**data)
    except Exception as e:
        logger.warning(f"Failed to load app config, using defaults: {e}")
    return AppConfigModel()


def save_app_config(config: AppConfigModel) -> bool:
    """Save app configuration to file"""
    try:
        APP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(APP_CONFIG_FILE, 'w') as f:
            json.dump(config.model_dump(), f, indent=2)
        logger.info(f"Saved app config to {APP_CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save app config: {e}")
        return False


def apply_app_config_to_settings(config: AppConfigModel):
    """Apply app config values to the runtime settings object"""
    try:
        # Server settings (these require restart to take effect)
        os.environ['TERMIVOXED_HOST'] = config.server_host
        os.environ['TERMIVOXED_PORT'] = str(config.server_port)

        # TTS settings
        settings.TTS_CACHE_ENABLED = config.tts_cache_enabled
        settings.MAX_CONCURRENT_TTS = config.max_concurrent_tts
        settings.TTS_PROXY_ENABLED = config.tts_proxy_enabled
        settings.TTS_PROXY_URL = config.tts_proxy_url or ""

        # Video export settings
        settings.DEFAULT_VIDEO_CODEC = config.default_video_codec
        settings.DEFAULT_AUDIO_CODEC = config.default_audio_codec
        settings.DEFAULT_CRF = config.default_crf
        settings.DEFAULT_PRESET = config.default_preset

        # Quality presets
        settings.LOSSLESS_CRF = config.lossless_crf
        settings.HIGH_CRF = config.high_crf
        settings.BALANCED_CRF = config.balanced_crf

        # Audio mixing
        settings.TTS_VOLUME_BOOST = config.tts_volume_boost
        settings.BGM_VOLUME_REDUCTION = config.bgm_volume_reduction
        settings.FADE_DURATION = config.fade_duration

        # Logging
        settings.LOG_LEVEL = config.log_level

        logger.info("Applied app config to runtime settings")
    except Exception as e:
        logger.error(f"Failed to apply app config: {e}")


# Load and apply app config on module initialization
app_config = load_app_config()
apply_app_config_to_settings(app_config)


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
    """LLM provider settings - supports all 8 providers"""
    # API Keys for simple providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None

    # Azure OpenAI configuration
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    azure_openai_api_version: Optional[str] = "2024-05-01-preview"

    # AWS Bedrock configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "us-east-1"

    # Ollama configuration
    ollama_endpoint: str = "http://localhost:11434"

    # HuggingFace configuration
    huggingface_inference_provider: str = "auto"

    # Custom endpoint configuration
    custom_endpoint: Optional[str] = None
    custom_api_key: Optional[str] = None

    # Defaults
    default_provider: str = "ollama"
    default_model: str = "llama3.2:3b"


def load_llm_settings() -> LLMSettings:
    """Load LLM settings from file"""
    try:
        if LLM_SETTINGS_FILE.exists():
            with open(LLM_SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                logger.info(f"Loaded LLM settings from {LLM_SETTINGS_FILE}")
                return LLMSettings(**data)
    except Exception as e:
        logger.error(f"Failed to load LLM settings: {e}")
    return LLMSettings()


def save_llm_settings(llm_settings: LLMSettings) -> bool:
    """Save LLM settings to file"""
    try:
        # Ensure directory exists
        LLM_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LLM_SETTINGS_FILE, 'w') as f:
            json.dump(llm_settings.model_dump(), f, indent=2)
        logger.info(f"Saved LLM settings to {LLM_SETTINGS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save LLM settings: {e}")
        return False


# Load settings on module initialization
llm_settings = load_llm_settings()


@router.get("", response_model=AppSettings)
@router.get("/", response_model=AppSettings)
async def get_settings(user: AuthenticatedUser = Depends(get_current_user)):
    """Get current application settings (requires authentication)"""
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


@router.put("")
@router.put("/")
async def update_settings(
    update: UpdateSettings,
    user: AuthenticatedUser = Depends(require_admin)
):
    """Update application settings (requires admin privileges)"""
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
async def get_llm_settings_route(user: AuthenticatedUser = Depends(get_current_user)):
    """Get LLM provider settings (API keys and secrets masked, requires authentication)"""
    masked = LLMSettings(
        # Simple API keys (masked)
        openai_api_key="***" if llm_settings.openai_api_key else None,
        anthropic_api_key="***" if llm_settings.anthropic_api_key else None,
        google_api_key="***" if llm_settings.google_api_key else None,
        huggingface_api_key="***" if llm_settings.huggingface_api_key else None,

        # Azure OpenAI (key masked, endpoint shown)
        azure_openai_api_key="***" if llm_settings.azure_openai_api_key else None,
        azure_openai_endpoint=llm_settings.azure_openai_endpoint,
        azure_openai_deployment=llm_settings.azure_openai_deployment,
        azure_openai_api_version=llm_settings.azure_openai_api_version,

        # AWS Bedrock (keys masked, region shown)
        aws_access_key_id="***" if llm_settings.aws_access_key_id else None,
        aws_secret_access_key="***" if llm_settings.aws_secret_access_key else None,
        aws_region=llm_settings.aws_region,

        # Ollama
        ollama_endpoint=llm_settings.ollama_endpoint,

        # HuggingFace
        huggingface_inference_provider=llm_settings.huggingface_inference_provider,

        # Custom
        custom_endpoint=llm_settings.custom_endpoint,
        custom_api_key="***" if llm_settings.custom_api_key else None,

        # Defaults
        default_provider=llm_settings.default_provider,
        default_model=llm_settings.default_model
    )
    return masked


@router.put("/llm")
async def update_llm_settings(
    update: LLMSettings,
    user: AuthenticatedUser = Depends(require_admin)
):
    """Update LLM provider settings (requires admin privileges)"""
    global llm_settings

    # Simple API keys
    if update.openai_api_key and update.openai_api_key != "***":
        llm_settings.openai_api_key = update.openai_api_key

    if update.anthropic_api_key and update.anthropic_api_key != "***":
        llm_settings.anthropic_api_key = update.anthropic_api_key

    if update.google_api_key and update.google_api_key != "***":
        llm_settings.google_api_key = update.google_api_key

    if update.huggingface_api_key and update.huggingface_api_key != "***":
        llm_settings.huggingface_api_key = update.huggingface_api_key

    # Azure OpenAI
    if update.azure_openai_api_key and update.azure_openai_api_key != "***":
        llm_settings.azure_openai_api_key = update.azure_openai_api_key

    if update.azure_openai_endpoint is not None:
        llm_settings.azure_openai_endpoint = update.azure_openai_endpoint

    if update.azure_openai_deployment is not None:
        llm_settings.azure_openai_deployment = update.azure_openai_deployment

    if update.azure_openai_api_version:
        llm_settings.azure_openai_api_version = update.azure_openai_api_version

    # AWS Bedrock
    if update.aws_access_key_id and update.aws_access_key_id != "***":
        llm_settings.aws_access_key_id = update.aws_access_key_id

    if update.aws_secret_access_key and update.aws_secret_access_key != "***":
        llm_settings.aws_secret_access_key = update.aws_secret_access_key

    if update.aws_region:
        llm_settings.aws_region = update.aws_region

    # Ollama - SECURITY: Validate endpoint to prevent SSRF
    if update.ollama_endpoint:
        is_valid, error = validate_ollama_endpoint(update.ollama_endpoint)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Ollama endpoint: {error}"
            )
        llm_settings.ollama_endpoint = update.ollama_endpoint

    # HuggingFace
    if update.huggingface_inference_provider:
        llm_settings.huggingface_inference_provider = update.huggingface_inference_provider

    # Custom
    if update.custom_endpoint is not None:
        llm_settings.custom_endpoint = update.custom_endpoint

    if update.custom_api_key and update.custom_api_key != "***":
        llm_settings.custom_api_key = update.custom_api_key

    # Defaults
    if update.default_provider:
        llm_settings.default_provider = update.default_provider

    if update.default_model:
        llm_settings.default_model = update.default_model

    # Persist to file
    if save_llm_settings(llm_settings):
        return {"message": "LLM settings saved successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save LLM settings")


@router.get("/llm/configured")
async def get_configured_providers(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get which LLM providers are configured and ready to use (requires authentication).

    Returns a dict showing which providers have saved credentials.
    This helps the frontend know which providers users can use without
    entering credentials each time.
    """
    import httpx

    # Check Ollama availability
    ollama_available = False
    ollama_models = []
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{llm_settings.ollama_endpoint}/api/tags")
            if response.status_code == 200:
                ollama_available = True
                data = response.json()
                ollama_models = [m.get("name", "") for m in data.get("models", [])]
    except:
        pass

    return {
        "ollama": {
            "configured": ollama_available,
            "available_models": ollama_models,
            "endpoint": llm_settings.ollama_endpoint
        },
        "openai": {
            "configured": bool(llm_settings.openai_api_key),
        },
        "anthropic": {
            "configured": bool(llm_settings.anthropic_api_key),
        },
        "google": {
            "configured": bool(llm_settings.google_api_key),
        },
        "huggingface": {
            "configured": bool(llm_settings.huggingface_api_key),
            "inference_provider": llm_settings.huggingface_inference_provider
        },
        "azure_openai": {
            "configured": bool(llm_settings.azure_openai_api_key and llm_settings.azure_openai_endpoint),
            "endpoint": llm_settings.azure_openai_endpoint,
            "deployment": llm_settings.azure_openai_deployment
        },
        "aws_bedrock": {
            "configured": bool(llm_settings.aws_access_key_id and llm_settings.aws_secret_access_key),
            "region": llm_settings.aws_region
        },
        "custom": {
            "configured": bool(llm_settings.custom_endpoint),
            "endpoint": llm_settings.custom_endpoint
        },
        "default_provider": llm_settings.default_provider,
        "default_model": llm_settings.default_model
    }


@router.get("/system")
async def get_system_info(user: AuthenticatedUser = Depends(get_current_user)):
    """Get system information (requires authentication)"""
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

    # Get storage info from config
    storage_info = settings.get_storage_info()

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
        "storage_path": str(storage_path.absolute()),
        "storage_info": storage_info,
    }


@router.post("/clear-cache")
async def clear_cache(user: AuthenticatedUser = Depends(require_admin)):
    """Clear TTS cache (requires admin privileges)"""
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
async def clear_temp(user: AuthenticatedUser = Depends(require_admin)):
    """Clear temporary files (requires admin privileges)"""
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


class StoragePathUpdate(BaseModel):
    """Storage path update request"""
    storage_path: str


@router.get("/storage")
async def get_storage_settings(user: AuthenticatedUser = Depends(get_current_user)):
    """Get current storage path settings (requires authentication)"""
    storage_info = settings.get_storage_info()

    # Check if the path exists and is writable
    storage_path = Path(storage_info["storage_path"])
    path_exists = storage_path.exists()
    path_writable = False

    if path_exists:
        try:
            test_file = storage_path / ".write_test"
            test_file.touch()
            test_file.unlink()
            path_writable = True
        except Exception:
            pass
    else:
        # Check if parent is writable (we could create the directory)
        try:
            parent = storage_path.parent
            if parent.exists():
                test_file = parent / ".write_test"
                test_file.touch()
                test_file.unlink()
                path_writable = True
        except Exception:
            pass

    return {
        **storage_info,
        "path_exists": path_exists,
        "path_writable": path_writable,
    }


@router.put("/storage")
async def update_storage_path(
    update: StoragePathUpdate,
    user: AuthenticatedUser = Depends(require_admin)
):
    """
    Update the storage path (requires admin privileges).
    Changes take effect immediately.
    """
    new_path = update.storage_path.strip()

    if not new_path:
        raise HTTPException(status_code=400, detail="Storage path cannot be empty")

    # Expand user home directory
    if new_path.startswith("~"):
        new_path = str(Path(new_path).expanduser())

    # Convert to absolute path
    new_path = str(Path(new_path).absolute())

    # Check if path is valid (parent directory exists or can be created)
    new_path_obj = Path(new_path)
    try:
        # Try to create the directory
        new_path_obj.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create directory: {str(e)}"
        )

    # Check if directory is writable
    try:
        test_file = new_path_obj / ".write_test"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Directory is not writable: {str(e)}"
        )

    old_path = settings.STORAGE_DIR

    # Update settings in memory and save to config file
    try:
        settings.update_storage_path(new_path)
        logger.info(f"Storage path updated: {old_path} -> {new_path}")
        return {
            "message": "Storage path updated successfully",
            "old_path": old_path,
            "new_path": new_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update storage path: {str(e)}")


@router.post("/storage/reset")
async def reset_storage_path(user: AuthenticatedUser = Depends(require_admin)):
    """Reset storage path to OS-specific default (requires admin privileges)"""
    old_path = settings.STORAGE_DIR

    try:
        new_path = settings.reset_storage_path()
        logger.info(f"Storage path reset: {old_path} -> {new_path}")
        return {
            "message": "Storage path reset to default",
            "old_path": old_path,
            "new_path": new_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset storage path: {str(e)}")


# ============================================================================
# App Configuration Endpoints
# ============================================================================

@router.get("/app-config", response_model=AppConfigModel)
async def get_app_config(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get current application configuration (requires authentication).
    These settings persist across server restarts.
    """
    return app_config


@router.put("/app-config", response_model=AppConfigModel)
async def update_app_config(
    update: AppConfigUpdate,
    user: AuthenticatedUser = Depends(require_admin)
):
    """
    Update application configuration (requires admin privileges).
    Changes are persisted to disk and applied immediately where possible.
    Some settings (server_host, server_port) require a restart to take effect.
    """
    global app_config

    # Get current values as dict
    current_values = app_config.model_dump()

    # Apply updates (only non-None values)
    update_dict = update.model_dump(exclude_none=True)

    if not update_dict:
        raise HTTPException(status_code=400, detail="No values to update")

    # Merge updates
    for key, value in update_dict.items():
        current_values[key] = value

    # Validate the merged config
    try:
        new_config = AppConfigModel(**current_values)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")

    # Check which settings require restart
    restart_required = False
    restart_fields = []

    if 'server_host' in update_dict and update_dict['server_host'] != app_config.server_host:
        restart_required = True
        restart_fields.append('server_host')

    if 'server_port' in update_dict and update_dict['server_port'] != app_config.server_port:
        restart_required = True
        restart_fields.append('server_port')

    # Save to file
    if not save_app_config(new_config):
        raise HTTPException(status_code=500, detail="Failed to save configuration to disk")

    # Update in-memory config
    app_config = new_config

    # Apply to runtime settings
    apply_app_config_to_settings(app_config)

    response = {
        "message": "Configuration updated successfully",
        "config": app_config.model_dump(),
        "restart_required": restart_required,
    }

    if restart_required:
        response["restart_fields"] = restart_fields
        response["restart_message"] = f"Changes to {', '.join(restart_fields)} require a server restart to take effect."

    return app_config


@router.post("/app-config/reset")
async def reset_app_config(user: AuthenticatedUser = Depends(require_admin)):
    """
    Reset all application configuration to defaults (requires admin privileges).
    """
    global app_config

    # Create default config
    default_config = AppConfigModel()

    # Save to file
    if not save_app_config(default_config):
        raise HTTPException(status_code=500, detail="Failed to save default configuration")

    # Update in-memory config
    app_config = default_config

    # Apply to runtime settings
    apply_app_config_to_settings(app_config)

    return {
        "message": "Configuration reset to defaults",
        "config": app_config.model_dump(),
        "restart_required": True,
        "restart_message": "A server restart is recommended after resetting configuration."
    }


@router.get("/app-config/defaults")
async def get_app_config_defaults(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get default values for all configuration options (requires authentication).
    Useful for UI to show default values and reset individual fields.
    """
    default_config = AppConfigModel()
    return {
        "defaults": default_config.model_dump(),
        "schema": {
            "server_host": {"type": "string", "description": "Server hostname for accessing the application"},
            "server_port": {"type": "integer", "min": 1024, "max": 65535, "description": "Server port number"},
            "tts_cache_enabled": {"type": "boolean", "description": "Enable caching of generated TTS audio"},
            "max_concurrent_tts": {"type": "integer", "min": 1, "max": 10, "description": "Maximum concurrent TTS generation jobs"},
            "tts_proxy_enabled": {"type": "boolean", "description": "Enable proxy for TTS requests"},
            "tts_proxy_url": {"type": "string", "description": "Proxy server URL (http:// or https://)"},
            "default_video_codec": {"type": "select", "options": ["libx264", "libx265", "libvpx-vp9"], "description": "Video codec for export"},
            "default_audio_codec": {"type": "select", "options": ["aac", "mp3", "opus"], "description": "Audio codec for export"},
            "default_crf": {"type": "integer", "min": 0, "max": 51, "description": "Constant Rate Factor (lower = better quality, larger file)"},
            "default_preset": {"type": "select", "options": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], "description": "Encoding speed preset"},
            "lossless_crf": {"type": "integer", "min": 0, "max": 10, "description": "CRF for lossless quality preset"},
            "high_crf": {"type": "integer", "min": 10, "max": 25, "description": "CRF for high quality preset"},
            "balanced_crf": {"type": "integer", "min": 18, "max": 30, "description": "CRF for balanced quality preset"},
            "tts_volume_boost": {"type": "integer", "min": 0, "max": 30, "unit": "dB", "description": "Voice-over volume boost"},
            "bgm_volume_reduction": {"type": "integer", "min": 0, "max": 40, "unit": "dB", "description": "Background music volume reduction"},
            "fade_duration": {"type": "number", "min": 0, "max": 10, "unit": "seconds", "description": "Audio fade in/out duration"},
            "log_level": {"type": "select", "options": ["DEBUG", "INFO", "WARNING", "ERROR"], "description": "Logging verbosity level"},
        }
    }
