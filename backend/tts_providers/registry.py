"""
TTS Provider Registry

Central registry for managing TTS providers.
Handles provider registration, initialization, and selection.
"""

import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Type

from .base import (
    TTSProvider,
    TTSProviderType,
    ProviderNotAvailableError,
)
from .edge_tts_provider import EdgeTTSProvider
from .coqui_provider import CoquiTTSProvider

from utils.logger import logger


class TTSProviderRegistry:
    """
    Registry for TTS providers.

    Manages provider instances, handles provider selection,
    and persists user preferences.
    """

    SETTINGS_FILE = ".termivoxed_tts_settings.json"

    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path or self._get_default_storage_path()
        self._providers: Dict[TTSProviderType, TTSProvider] = {}
        self._default_provider: TTSProviderType = TTSProviderType.EDGE_TTS
        self._settings: Dict[str, Any] = {}

        # Load settings
        self._load_settings()

        # Register default providers
        self._register_default_providers()

    def _get_default_storage_path(self) -> Path:
        """Get default path for settings storage"""
        home = Path.home()
        settings_dir = home / ".termivoxed"
        settings_dir.mkdir(parents=True, exist_ok=True)
        return settings_dir / self.SETTINGS_FILE

    def _load_settings(self) -> None:
        """Load settings from disk"""
        try:
            if self._storage_path.exists():
                self._settings = json.loads(self._storage_path.read_text())
                default_str = self._settings.get("default_provider")
                if default_str:
                    try:
                        self._default_provider = TTSProviderType(default_str)
                    except ValueError:
                        pass
                logger.debug(f"Loaded TTS settings: default={self._default_provider.value}")
        except Exception as e:
            logger.warning(f"Failed to load TTS settings: {e}")
            self._settings = {}

    def _save_settings(self) -> None:
        """Save settings to disk"""
        try:
            self._settings["default_provider"] = self._default_provider.value
            self._storage_path.write_text(json.dumps(self._settings, indent=2))
            logger.debug("Saved TTS settings")
        except Exception as e:
            logger.error(f"Failed to save TTS settings: {e}")

    def _register_default_providers(self) -> None:
        """Register the default providers"""
        # Edge TTS (always available if internet works)
        edge_config = self._settings.get("edge_tts", {})
        self.register(
            TTSProviderType.EDGE_TTS,
            EdgeTTSProvider(config=edge_config)
        )

        # Coqui TTS (available if installed)
        coqui_config = self._settings.get("coqui", {})
        self.register(
            TTSProviderType.COQUI,
            CoquiTTSProvider(config=coqui_config)
        )

    def register(
        self,
        provider_type: TTSProviderType,
        provider: TTSProvider
    ) -> None:
        """Register a provider"""
        self._providers[provider_type] = provider
        logger.debug(f"Registered TTS provider: {provider_type.value}")

    def get(
        self,
        provider_type: Optional[TTSProviderType] = None
    ) -> TTSProvider:
        """
        Get a provider instance.

        Args:
            provider_type: Specific provider to get, or None for default

        Returns:
            TTSProvider instance

        Raises:
            ProviderNotAvailableError: If provider not registered
        """
        target_type = provider_type or self._default_provider

        if target_type not in self._providers:
            raise ProviderNotAvailableError(
                f"Provider not registered: {target_type.value}"
            )

        return self._providers[target_type]

    async def get_available(
        self,
        provider_type: Optional[TTSProviderType] = None
    ) -> TTSProvider:
        """
        Get a provider that is available and initialized.

        Falls back to other providers if the requested one is unavailable.

        Args:
            provider_type: Preferred provider, or None for default

        Returns:
            Available TTSProvider instance

        Raises:
            ProviderNotAvailableError: If no providers are available
        """
        target_type = provider_type or self._default_provider

        # Try requested provider first
        if target_type in self._providers:
            provider = self._providers[target_type]
            if not provider._initialized:
                await provider.initialize()
            if await provider.is_available():
                return provider

        # Fall back to other providers
        fallback_order = [
            TTSProviderType.EDGE_TTS,
            TTSProviderType.COQUI,
        ]

        for fallback_type in fallback_order:
            if fallback_type == target_type:
                continue  # Already tried

            if fallback_type in self._providers:
                provider = self._providers[fallback_type]
                if not provider._initialized:
                    await provider.initialize()
                if await provider.is_available():
                    logger.info(
                        f"Using fallback provider: {fallback_type.value}"
                    )
                    return provider

        raise ProviderNotAvailableError("No TTS providers available")

    def get_default(self) -> TTSProviderType:
        """Get the default provider type"""
        return self._default_provider

    def set_default(self, provider_type: TTSProviderType) -> None:
        """Set the default provider"""
        if provider_type not in self._providers:
            raise ProviderNotAvailableError(
                f"Cannot set default: provider not registered: {provider_type.value}"
            )

        self._default_provider = provider_type
        self._save_settings()
        logger.info(f"Default TTS provider set to: {provider_type.value}")

    def get_all_providers(self) -> Dict[str, TTSProvider]:
        """Get all registered providers"""
        return {k.value: v for k, v in self._providers.items()}

    async def get_all_status(self) -> List[Dict[str, Any]]:
        """Get status of all providers"""
        statuses = []

        for provider_type, provider in self._providers.items():
            status = provider.get_status()

            # Check availability
            try:
                if not provider._initialized:
                    await provider.initialize()
                status["available"] = await provider.is_available()
            except Exception as e:
                status["available"] = False
                status["error"] = str(e)

            status["is_default"] = (provider_type == self._default_provider)
            statuses.append(status)

        return statuses

    def update_provider_config(
        self,
        provider_type: TTSProviderType,
        config: Dict[str, Any]
    ) -> None:
        """Update provider configuration"""
        self._settings[provider_type.value] = config
        self._save_settings()

        # Reinitialize provider with new config
        if provider_type in self._providers:
            old_provider = self._providers[provider_type]
            provider_class = type(old_provider)
            self._providers[provider_type] = provider_class(config=config)
            logger.info(f"Updated config for provider: {provider_type.value}")


# Singleton registry instance
_registry: Optional[TTSProviderRegistry] = None


def get_registry() -> TTSProviderRegistry:
    """Get the singleton registry instance"""
    global _registry
    if _registry is None:
        _registry = TTSProviderRegistry()
    return _registry


# Convenience functions
def get_provider(
    provider_type: Optional[TTSProviderType] = None
) -> TTSProvider:
    """Get a provider from the registry"""
    return get_registry().get(provider_type)


async def get_available_providers() -> List[Dict[str, Any]]:
    """Get status of all available providers"""
    return await get_registry().get_all_status()


async def get_provider_status(provider_type: TTSProviderType) -> Dict[str, Any]:
    """Get status of a specific provider"""
    provider = get_registry().get(provider_type)
    status = provider.get_status()

    if not provider._initialized:
        await provider.initialize()
    status["available"] = await provider.is_available()

    return status


def register_provider(
    provider_type: TTSProviderType,
    provider: TTSProvider
) -> None:
    """Register a provider in the registry"""
    get_registry().register(provider_type, provider)


def get_default_provider() -> TTSProviderType:
    """Get the default provider type"""
    return get_registry().get_default()


def set_default_provider(provider_type: TTSProviderType) -> None:
    """Set the default provider"""
    get_registry().set_default(provider_type)
