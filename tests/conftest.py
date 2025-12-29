#!/usr/bin/env python3
"""
Pytest Configuration and Shared Fixtures

Provides shared fixtures and configuration for all tests.
"""

import pytest
import asyncio
import tempfile
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# ASYNCIO CONFIGURATION
# ============================================================================
# Note: pytest-asyncio is configured with asyncio_mode = "auto" in pyproject.toml
# The event loop is automatically managed per-function by default


# ============================================================================
# TEMPORARY DIRECTORIES
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_storage(temp_dir):
    """Create temporary storage directories mirroring the app structure"""
    storage = temp_dir / "storage"
    (storage / "projects").mkdir(parents=True)
    (storage / "cache").mkdir(parents=True)
    (storage / "temp").mkdir(parents=True)
    (storage / "output").mkdir(parents=True)
    return storage


# ============================================================================
# TTS PROVIDER FIXTURES
# ============================================================================

@pytest.fixture
def mock_edge_tts():
    """Mock edge-tts library for testing without network"""
    with patch('edge_tts.Communicate') as mock_communicate:
        # Mock the stream method
        async def mock_stream():
            yield {"type": "audio", "data": b"fake_audio_data"}
            yield {
                "type": "WordBoundary",
                "text": "Hello",
                "offset": 0,
                "duration": 5000000
            }

        mock_instance = MagicMock()
        mock_instance.stream = mock_stream
        mock_communicate.return_value = mock_instance

        yield mock_communicate


@pytest.fixture
def mock_coqui_tts():
    """Mock Coqui TTS library for testing without installation"""
    mock_tts_module = MagicMock()
    mock_tts_api = MagicMock()

    mock_tts_instance = MagicMock()
    mock_tts_instance.speakers = ["Speaker1", "Speaker2"]
    mock_tts_instance.tts_to_file = MagicMock()

    mock_tts_api.TTS.return_value = mock_tts_instance

    with patch.dict('sys.modules', {
        'TTS': mock_tts_module,
        'TTS.api': mock_tts_api
    }):
        yield mock_tts_instance


# ============================================================================
# FASTAPI TEST CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def app():
    """Create FastAPI application for testing"""
    try:
        from web_ui.api.main import app
        return app
    except ImportError:
        pytest.skip("FastAPI app not available")


@pytest.fixture
def client(app):
    """Create synchronous test client"""
    try:
        from fastapi.testclient import TestClient
        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI TestClient not available")


@pytest.fixture
async def async_client(app):
    """Create asynchronous test client"""
    try:
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            yield ac
    except ImportError:
        pytest.skip("httpx not available")


# ============================================================================
# MOCK SERVICES
# ============================================================================

@pytest.fixture
def mock_tts_service():
    """Mock TTS service for API testing"""
    from backend.tts_service import TTSService

    service = MagicMock(spec=TTSService)
    service.get_current_provider.return_value = "edge_tts"
    service.set_provider.return_value = True
    service.get_provider_info.return_value = {
        "default_provider": "edge_tts",
        "providers": {
            "edge_tts": {
                "display_name": "Microsoft Edge TTS",
                "description": "Cloud-based TTS",
                "is_local": False,
                "requires_consent": True,
                "supports_word_timing": True,
                "supports_voice_cloning": False,
            },
            "coqui": {
                "display_name": "Coqui TTS (Local)",
                "description": "Local TTS",
                "is_local": True,
                "requires_consent": False,
                "supports_word_timing": False,
                "supports_voice_cloning": True,
            }
        }
    }

    service.get_provider_status = AsyncMock(return_value=[
        {
            "provider": "edge_tts",
            "name": "Microsoft Edge TTS",
            "initialized": True,
            "available": True,
            "is_default": True,
            "capabilities": {
                "streaming": True,
                "word_timing": True,
                "voice_cloning": False,
                "is_local": False,
                "requires_consent": True,
            }
        },
        {
            "provider": "coqui",
            "name": "Coqui TTS (Local)",
            "initialized": False,
            "available": False,
            "is_default": False,
            "capabilities": {
                "streaming": True,
                "word_timing": False,
                "voice_cloning": True,
                "is_local": True,
                "requires_consent": False,
            }
        }
    ])

    return service


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_voice():
    """Sample voice data"""
    return {
        "name": "Microsoft Ava (Multilingual)",
        "short_name": "en-US-AvaMultilingualNeural",
        "gender": "Female",
        "language": "en",
        "locale": "en-US"
    }


@pytest.fixture
def sample_text():
    """Sample text for TTS testing"""
    return "Hello, this is a test of the text-to-speech system. It should generate natural sounding audio."


@pytest.fixture
def sample_word_timings():
    """Sample word timing data"""
    from backend.tts_providers.base import WordTiming
    return [
        WordTiming("Hello,", 0, 400),
        WordTiming("this", 500, 300),
        WordTiming("is", 900, 200),
        WordTiming("a", 1200, 100),
        WordTiming("test.", 1400, 400),
    ]


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may require network)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (may take several seconds)"
    )
    config.addinivalue_line(
        "markers", "requires_coqui: marks tests that require Coqui TTS installed"
    )
    config.addinivalue_line(
        "markers", "requires_network: marks tests that require network access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers"""
    # Check if we should skip integration tests
    if config.getoption("--skip-integration", default=False):
        skip_integration = pytest.mark.skip(reason="--skip-integration option provided")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--skip-integration",
        action="store_true",
        default=False,
        help="Skip integration tests"
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests"
    )
