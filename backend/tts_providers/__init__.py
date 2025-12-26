"""
TTS Providers Package

Multi-provider TTS architecture supporting:
- edge-tts (cloud, Microsoft) - requires user consent
- Coqui TTS (local, MPL-2.0) - no consent required
- Piper (local, subprocess only for GPL-3.0 safety) - optional

Provider Selection:
- User can choose default provider in Settings
- Cloud providers require explicit privacy consent
- Local providers run entirely on-device
"""

from .base import (
    TTSProvider,
    TTSProviderType,
    TTSResult,
    TTSCapabilities,
    TTSVoice,
    ProviderNotAvailableError,
    ProviderConfigError,
)
from .registry import (
    get_provider,
    get_available_providers,
    get_provider_status,
    register_provider,
    get_default_provider,
    set_default_provider,
)
from .resilience import (
    TTSResilienceManager,
    CircuitBreaker,
    TTSHealthMonitor,
    TTSRetryQueue,
    ProviderHealth,
    RetryableRequest,
    get_resilience_manager,
)

__all__ = [
    # Base classes
    "TTSProvider",
    "TTSProviderType",
    "TTSResult",
    "TTSCapabilities",
    "TTSVoice",
    "ProviderNotAvailableError",
    "ProviderConfigError",
    # Registry functions
    "get_provider",
    "get_available_providers",
    "get_provider_status",
    "register_provider",
    "get_default_provider",
    "set_default_provider",
    # Resilience
    "TTSResilienceManager",
    "CircuitBreaker",
    "TTSHealthMonitor",
    "TTSRetryQueue",
    "ProviderHealth",
    "RetryableRequest",
    "get_resilience_manager",
]
