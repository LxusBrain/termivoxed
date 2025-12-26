"""Configuration management using Pydantic settings"""

import platform
import os
import sys
import json
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


# App settings file location (in user's home config directory)
def get_app_settings_path() -> Path:
    """Get the path to the app settings file (OS-specific config location)"""
    system = platform.system()
    home = Path.home()

    if system == "Darwin":  # macOS
        config_dir = home / "Library" / "Application Support" / "TermiVoxed"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            config_dir = Path(appdata) / "TermiVoxed"
        else:
            config_dir = home / "AppData" / "Roaming" / "TermiVoxed"
    else:  # Linux
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            config_dir = Path(xdg_config) / "termivoxed"
        else:
            config_dir = home / ".config" / "termivoxed"

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "app_settings.json"


def get_default_storage_path() -> str:
    """
    Get OS-specific default storage path for TermiVoxed.

    Returns:
        - macOS: ~/Library/Application Support/TermiVoxed
        - Linux: ~/.local/share/termivoxed
        - Windows: %APPDATA%/TermiVoxed
    """
    system = platform.system()
    home = Path.home()

    if system == "Darwin":  # macOS
        return str(home / "Library" / "Application Support" / "TermiVoxed")
    elif system == "Windows":
        # Use APPDATA environment variable, fallback to home
        appdata = os.environ.get("APPDATA")
        if appdata:
            return str(Path(appdata) / "TermiVoxed")
        return str(home / "AppData" / "Roaming" / "TermiVoxed")
    else:  # Linux and others
        # Follow XDG Base Directory specification
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return str(Path(xdg_data) / "termivoxed")
        return str(home / ".local" / "share" / "termivoxed")


def load_app_settings() -> dict:
    """Load app settings from JSON file"""
    settings_path = get_app_settings_path()
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_app_settings(data: dict) -> bool:
    """Save app settings to JSON file"""
    settings_path = get_app_settings_path()
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def get_configured_storage_path() -> str:
    """Get storage path from app settings, or default if not set"""
    app_settings = load_app_settings()
    return app_settings.get("storage_path") or get_default_storage_path()


def get_bundled_ffmpeg_path() -> tuple[Optional[str], Optional[str]]:
    """
    Get path to bundled FFmpeg binaries if available.

    Returns:
        Tuple of (ffmpeg_path, ffprobe_path) or (None, None) if not bundled
    """
    import shutil

    # Determine platform
    system = platform.system()
    if system == "Darwin":
        plat = "macos"
    elif system == "Windows":
        plat = "windows"
    else:
        plat = "linux"

    # Check bundled location
    # When running from source
    source_vendor = Path(__file__).parent / "vendor" / "ffmpeg" / plat / "bin"
    # When running from PyInstaller bundle
    if getattr(sys, 'frozen', False):
        bundle_vendor = Path(sys._MEIPASS) / "vendor" / "ffmpeg" / "bin"
    else:
        bundle_vendor = None

    # FFmpeg binary names
    ffmpeg_name = "ffmpeg.exe" if system == "Windows" else "ffmpeg"
    ffprobe_name = "ffprobe.exe" if system == "Windows" else "ffprobe"

    # Check source vendor directory
    if source_vendor.exists():
        ffmpeg = source_vendor / ffmpeg_name
        ffprobe = source_vendor / ffprobe_name
        if ffmpeg.exists() and ffprobe.exists():
            return str(ffmpeg), str(ffprobe)

    # Check bundle vendor directory
    if bundle_vendor and bundle_vendor.exists():
        ffmpeg = bundle_vendor / ffmpeg_name
        ffprobe = bundle_vendor / ffprobe_name
        if ffmpeg.exists() and ffprobe.exists():
            return str(ffmpeg), str(ffprobe)

    # Check if FFmpeg is in system PATH
    ffmpeg_system = shutil.which("ffmpeg")
    ffprobe_system = shutil.which("ffprobe")

    if ffmpeg_system and ffprobe_system:
        return ffmpeg_system, ffprobe_system

    # Default to command names (will fail if not in PATH)
    return "ffmpeg", "ffprobe"


class Settings(BaseSettings):
    """Application settings"""

    # Storage paths - use configured path or OS-specific default
    STORAGE_DIR: str = get_configured_storage_path()

    # Derived paths (will be computed from STORAGE_DIR)
    PROJECTS_DIR: Optional[str] = None
    TEMP_DIR: Optional[str] = None
    CACHE_DIR: Optional[str] = None
    OUTPUT_DIR: Optional[str] = None
    FONTS_DIR: Optional[str] = None

    # FFmpeg settings - auto-detect bundled or system FFmpeg
    _bundled_ffmpeg = get_bundled_ffmpeg_path()
    FFMPEG_PATH: str = _bundled_ffmpeg[0]
    FFPROBE_PATH: str = _bundled_ffmpeg[1]

    # TTS settings
    TTS_CACHE_ENABLED: bool = True
    MAX_CONCURRENT_TTS: int = 2
    TTS_PROXY_ENABLED: bool = False
    TTS_PROXY_URL: Optional[str] = None

    # Export settings
    DEFAULT_VIDEO_CODEC: str = "libx264"
    DEFAULT_AUDIO_CODEC: str = "aac"
    DEFAULT_CRF: int = 23
    DEFAULT_PRESET: str = "medium"

    # Quality presets
    LOSSLESS_CRF: int = 0
    HIGH_CRF: int = 18
    BALANCED_CRF: int = 23

    # Audio mixing
    # Based on proven reference implementation (cl_vid_gen_2.py)
    # TTS boost: +3dB ensures voice-over is clear and audible
    # BGM reduction: -16dB creates 19dB difference favoring speech over background music
    TTS_VOLUME_BOOST: int = 3
    BGM_VOLUME_REDUCTION: int = 16
    FADE_DURATION: float = 3.0

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

    def model_post_init(self, __context) -> None:
        """Initialize derived paths after model creation"""
        self._update_derived_paths()

    def _update_derived_paths(self) -> None:
        """Update all derived paths based on STORAGE_DIR"""
        storage = Path(self.STORAGE_DIR)

        # Only set if not explicitly configured via env
        if self.PROJECTS_DIR is None:
            object.__setattr__(self, 'PROJECTS_DIR', str(storage / "projects"))
        if self.TEMP_DIR is None:
            object.__setattr__(self, 'TEMP_DIR', str(storage / "temp"))
        if self.CACHE_DIR is None:
            object.__setattr__(self, 'CACHE_DIR', str(storage / "cache"))
        if self.OUTPUT_DIR is None:
            object.__setattr__(self, 'OUTPUT_DIR', str(storage / "output"))
        if self.FONTS_DIR is None:
            object.__setattr__(self, 'FONTS_DIR', str(storage / "fonts"))

    def create_directories(self):
        """Create necessary directories"""
        for dir_path in [
            self.STORAGE_DIR,
            self.PROJECTS_DIR,
            self.TEMP_DIR,
            self.CACHE_DIR,
            self.OUTPUT_DIR,
            self.FONTS_DIR,
            str(Path(self.STORAGE_DIR) / "uploads"),
            str(Path(self.STORAGE_DIR) / "audio"),
        ]:
            if dir_path:
                Path(dir_path).mkdir(parents=True, exist_ok=True)

    def get_storage_info(self) -> dict:
        """Get storage path information for API"""
        return {
            "storage_path": self.STORAGE_DIR,
            "default_path": get_default_storage_path(),
            "is_default": self.STORAGE_DIR == get_default_storage_path(),
            "platform": platform.system(),
            "config_file": str(get_app_settings_path()),
        }

    def update_storage_path(self, new_path: str) -> None:
        """
        Update storage path and all derived paths.
        Changes take effect immediately without restart.
        """
        # Update main storage path
        object.__setattr__(self, 'STORAGE_DIR', new_path)

        # Update all derived paths
        storage = Path(new_path)
        object.__setattr__(self, 'PROJECTS_DIR', str(storage / "projects"))
        object.__setattr__(self, 'TEMP_DIR', str(storage / "temp"))
        object.__setattr__(self, 'CACHE_DIR', str(storage / "cache"))
        object.__setattr__(self, 'OUTPUT_DIR', str(storage / "output"))
        object.__setattr__(self, 'FONTS_DIR', str(storage / "fonts"))

        # Create directories
        self.create_directories()

        # Save to persistent config
        app_settings = load_app_settings()
        app_settings["storage_path"] = new_path
        save_app_settings(app_settings)

    def reset_storage_path(self) -> str:
        """Reset storage path to OS-specific default"""
        default_path = get_default_storage_path()

        # Update in memory
        self.update_storage_path(default_path)

        # Remove from config file to use default
        app_settings = load_app_settings()
        if "storage_path" in app_settings:
            del app_settings["storage_path"]
            save_app_settings(app_settings)

        return default_path


# Global settings instance
settings = Settings()
settings.create_directories()
