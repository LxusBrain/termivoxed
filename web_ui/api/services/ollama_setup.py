"""
Ollama Setup and Management Service

Handles Ollama detection, installation guidance, and model management
with user consent tracking.

Author: LxusBrain
"""

import os
import sys
import json
import shutil
import asyncio
import platform
import subprocess
import aiohttp
from pathlib import Path
from typing import Optional, Dict, List, Any, AsyncIterator
from dataclasses import dataclass, asdict
from datetime import datetime

# Default Ollama endpoint
DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Recommended models for TermiVoxed
RECOMMENDED_MODELS = {
    "text": [
        {
            "name": "llama3.2:3b",
            "description": "Fast, lightweight model for quick tasks",
            "size": "2.0 GB",
            "vram": "4 GB",
            "use_case": "Script generation, quick edits"
        },
        {
            "name": "llama3.1:8b",
            "description": "Balanced performance and quality",
            "size": "4.7 GB",
            "vram": "8 GB",
            "use_case": "General purpose, good quality"
        },
        {
            "name": "qwen2.5:7b",
            "description": "Excellent multilingual support",
            "size": "4.4 GB",
            "vram": "8 GB",
            "use_case": "Non-English content, translations"
        },
    ],
    "vision": [
        {
            "name": "llava:7b",
            "description": "Vision-language model for video analysis",
            "size": "4.5 GB",
            "vram": "8 GB",
            "use_case": "Video scene analysis, auto-segmentation"
        },
        {
            "name": "llava:13b",
            "description": "Higher quality vision analysis",
            "size": "8.0 GB",
            "vram": "16 GB",
            "use_case": "Detailed video understanding"
        },
    ]
}

# Ollama download URLs
OLLAMA_DOWNLOAD_URLS = {
    "Windows": "https://ollama.com/download/OllamaSetup.exe",
    "Darwin": "https://ollama.com/download/Ollama-darwin.zip",
    "Linux": "https://ollama.com/download/ollama-linux-amd64"
}

# Consent storage file
def get_consent_file() -> Path:
    """Get path to consent storage file."""
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    config_dir = base / "TermiVoxed"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "ollama_consent.json"


@dataclass
class OllamaStatus:
    """Ollama installation and running status."""
    installed: bool = False
    running: bool = False
    version: Optional[str] = None
    models: List[str] = None
    endpoint: str = DEFAULT_OLLAMA_URL
    install_path: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.models is None:
            self.models = []

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class UserConsent:
    """User consent for local AI processing."""
    consented: bool = False
    consent_date: Optional[str] = None
    consent_version: str = "1.0"
    acknowledged_items: List[str] = None

    def __post_init__(self):
        if self.acknowledged_items is None:
            self.acknowledged_items = []

    def to_dict(self) -> Dict:
        return asdict(self)


class OllamaSetupService:
    """Service for managing Ollama setup and configuration."""

    def __init__(self, endpoint: str = DEFAULT_OLLAMA_URL):
        self.endpoint = endpoint
        self._consent: Optional[UserConsent] = None

    # =========================================================================
    # Installation Detection
    # =========================================================================

    def is_ollama_installed(self) -> tuple[bool, Optional[str]]:
        """
        Check if Ollama is installed on the system.

        Returns:
            Tuple of (is_installed, install_path)
        """
        # Check if ollama command is in PATH
        ollama_path = shutil.which("ollama")
        if ollama_path:
            return True, ollama_path

        # Check common installation locations
        system = platform.system()

        if system == "Windows":
            common_paths = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
                Path(os.environ.get("PROGRAMFILES", "")) / "Ollama" / "ollama.exe",
                Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
            ]
        elif system == "Darwin":
            common_paths = [
                Path("/usr/local/bin/ollama"),
                Path("/opt/homebrew/bin/ollama"),
                Path.home() / ".ollama" / "ollama",
                Path("/Applications/Ollama.app/Contents/MacOS/ollama"),
            ]
        else:  # Linux
            common_paths = [
                Path("/usr/local/bin/ollama"),
                Path("/usr/bin/ollama"),
                Path.home() / ".local" / "bin" / "ollama",
            ]

        for path in common_paths:
            if path.exists():
                return True, str(path)

        return False, None

    async def is_ollama_running(self) -> bool:
        """Check if Ollama server is running."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.endpoint}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def get_ollama_version(self) -> Optional[str]:
        """Get Ollama version."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.endpoint}/api/version",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("version")
        except Exception:
            pass
        return None

    async def get_installed_models(self) -> List[Dict[str, Any]]:
        """Get list of installed Ollama models."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.endpoint}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("models", [])
        except Exception:
            pass
        return []

    async def get_full_status(self) -> OllamaStatus:
        """Get comprehensive Ollama status."""
        installed, install_path = self.is_ollama_installed()
        running = await self.is_ollama_running()
        version = await self.get_ollama_version() if running else None
        models_data = await self.get_installed_models() if running else []
        models = [m.get("name", "") for m in models_data]

        return OllamaStatus(
            installed=installed,
            running=running,
            version=version,
            models=models,
            endpoint=self.endpoint,
            install_path=install_path
        )

    # =========================================================================
    # Installation Helpers
    # =========================================================================

    def get_download_url(self) -> str:
        """Get the Ollama download URL for current platform."""
        system = platform.system()
        return OLLAMA_DOWNLOAD_URLS.get(system, "https://ollama.com/download")

    def get_install_instructions(self) -> Dict[str, Any]:
        """Get installation instructions for current platform."""
        system = platform.system()

        if system == "Windows":
            return {
                "platform": "Windows",
                "method": "installer",
                "download_url": OLLAMA_DOWNLOAD_URLS["Windows"],
                "steps": [
                    "Download OllamaSetup.exe from the link below",
                    "Run the installer and follow the prompts",
                    "Ollama will start automatically after installation",
                    "Return here to continue setup"
                ],
                "command": None,
                "post_install": "Ollama starts automatically as a system service"
            }
        elif system == "Darwin":
            return {
                "platform": "macOS",
                "method": "app",
                "download_url": OLLAMA_DOWNLOAD_URLS["Darwin"],
                "steps": [
                    "Download Ollama for macOS from the link below",
                    "Open the downloaded .zip file",
                    "Drag Ollama to your Applications folder",
                    "Launch Ollama from Applications",
                    "Return here to continue setup"
                ],
                "command": "brew install ollama",  # Alternative
                "post_install": "Click the Ollama icon in your menu bar to ensure it's running"
            }
        else:  # Linux
            return {
                "platform": "Linux",
                "method": "script",
                "download_url": "https://ollama.com/install.sh",
                "steps": [
                    "Open a terminal",
                    "Run the installation command below",
                    "Start Ollama with: ollama serve",
                    "Return here to continue setup"
                ],
                "command": "curl -fsSL https://ollama.com/install.sh | sh",
                "post_install": "Run 'ollama serve' to start the server"
            }

    def open_download_page(self) -> bool:
        """Open Ollama download page in default browser."""
        import webbrowser
        try:
            webbrowser.open("https://ollama.com/download")
            return True
        except Exception:
            return False

    # =========================================================================
    # Model Management
    # =========================================================================

    def get_recommended_models(self) -> Dict[str, List[Dict]]:
        """Get recommended models for TermiVoxed."""
        return RECOMMENDED_MODELS

    async def pull_model(self, model_name: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Pull a model from Ollama with progress updates.

        Yields progress updates as dictionaries.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.endpoint}/api/pull",
                    json={"name": model_name, "stream": True},
                    timeout=aiohttp.ClientTimeout(total=3600)  # 1 hour timeout
                ) as response:
                    if response.status != 200:
                        yield {
                            "status": "error",
                            "error": f"Failed to pull model: HTTP {response.status}"
                        }
                        return

                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                yield {
                                    "status": data.get("status", "downloading"),
                                    "digest": data.get("digest"),
                                    "total": data.get("total"),
                                    "completed": data.get("completed"),
                                    "error": data.get("error")
                                }
                            except json.JSONDecodeError:
                                continue

                    yield {"status": "success", "model": model_name}

        except asyncio.TimeoutError:
            yield {"status": "error", "error": "Download timed out"}
        except Exception as e:
            yield {"status": "error", "error": str(e)}

    async def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.endpoint}/api/delete",
                    json={"name": model_name},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    # =========================================================================
    # Consent Management
    # =========================================================================

    def load_consent(self) -> UserConsent:
        """Load user consent from file."""
        consent_file = get_consent_file()

        if consent_file.exists():
            try:
                with open(consent_file, 'r') as f:
                    data = json.load(f)
                    return UserConsent(**data)
            except Exception:
                pass

        return UserConsent()

    def save_consent(self, consent: UserConsent) -> bool:
        """Save user consent to file."""
        consent_file = get_consent_file()

        try:
            with open(consent_file, 'w') as f:
                json.dump(consent.to_dict(), f, indent=2)
            return True
        except Exception:
            return False

    def has_user_consent(self) -> bool:
        """Check if user has given consent for local AI."""
        consent = self.load_consent()
        return consent.consented

    def grant_consent(self, acknowledged_items: List[str]) -> UserConsent:
        """
        Record user consent for local AI processing.

        Args:
            acknowledged_items: List of items user acknowledged
                - "local_processing": Data processed on device
                - "model_storage": Models stored locally
                - "resource_usage": CPU/GPU/RAM usage
                - "no_cloud": No data sent to cloud for Ollama
        """
        consent = UserConsent(
            consented=True,
            consent_date=datetime.utcnow().isoformat(),
            consent_version="1.0",
            acknowledged_items=acknowledged_items
        )

        self.save_consent(consent)
        self._consent = consent
        return consent

    def revoke_consent(self) -> bool:
        """Revoke user consent."""
        consent = UserConsent(consented=False)
        return self.save_consent(consent)

    # =========================================================================
    # Setup Wizard Data
    # =========================================================================

    def get_setup_wizard_data(self) -> Dict[str, Any]:
        """Get all data needed for the setup wizard."""
        installed, install_path = self.is_ollama_installed()
        consent = self.load_consent()

        return {
            "ollama": {
                "installed": installed,
                "install_path": install_path,
                "download_url": self.get_download_url(),
                "instructions": self.get_install_instructions(),
            },
            "consent": consent.to_dict(),
            "recommended_models": RECOMMENDED_MODELS,
            "system": {
                "platform": platform.system(),
                "architecture": platform.machine(),
            }
        }


# Singleton instance
_ollama_service: Optional[OllamaSetupService] = None

def get_ollama_service(endpoint: str = DEFAULT_OLLAMA_URL) -> OllamaSetupService:
    """Get or create the Ollama setup service."""
    global _ollama_service
    if _ollama_service is None or _ollama_service.endpoint != endpoint:
        _ollama_service = OllamaSetupService(endpoint)
    return _ollama_service
