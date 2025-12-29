#!/usr/bin/env python3
"""
TTS API Integration Tests

Tests for the TTS API endpoints including:
- Provider management endpoints
- Voice listing endpoints
- Audio generation endpoints
- Consent integration

Author: TermiVoxed Team
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import FastAPI testing utilities
try:
    from fastapi.testclient import TestClient
    from httpx import AsyncClient, ASGITransport
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None
    AsyncClient = None


# ============================================================================
# SKIP IF FASTAPI NOT AVAILABLE
# ============================================================================

pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI test dependencies not installed"
)


# ============================================================================
# MOCK AUTHENTICATION FOR TESTING
# ============================================================================

def create_mock_authenticated_user():
    """
    Create a mock authenticated user for testing.

    This provides a security-compliant way to test authenticated endpoints
    by using FastAPI's dependency override mechanism rather than bypassing
    authentication entirely.

    The mock user represents a valid authenticated user with appropriate
    subscription tier for testing all features.
    """
    from web_ui.api.middleware.auth import AuthenticatedUser
    from subscription.models import SubscriptionTier, SubscriptionStatus, FeatureAccess
    from datetime import datetime, timedelta

    return AuthenticatedUser(
        uid="test-user-uid-12345",
        email="test@example.com",
        email_verified=True,
        display_name="Test User",
        photo_url=None,
        subscription_tier=SubscriptionTier.PRO,
        subscription_status=SubscriptionStatus.ACTIVE,
        features=FeatureAccess.for_tier(SubscriptionTier.PRO),
        subscription_expires_at=datetime.now() + timedelta(days=30),
        device_id="test-device-id",
    )


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_user():
    """Fixture providing a mock authenticated user"""
    return create_mock_authenticated_user()


@pytest.fixture
def app():
    """Create FastAPI app for testing with auth override"""
    from web_ui.api.main import app
    from web_ui.api.middleware.auth import get_current_user

    # Store original dependency
    original_dependency = app.dependency_overrides.copy()

    # Override authentication dependency with mock user
    async def get_mock_user():
        return create_mock_authenticated_user()

    app.dependency_overrides[get_current_user] = get_mock_user

    yield app

    # Restore original dependencies after test
    app.dependency_overrides = original_dependency


@pytest.fixture
def client(app):
    """Create sync test client with mocked authentication"""
    if TestClient is None:
        pytest.skip("TestClient not available")
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Create async test client with mocked authentication"""
    if AsyncClient is None:
        pytest.skip("AsyncClient not available")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# ============================================================================
# PROVIDER ENDPOINT TESTS
# ============================================================================

class TestProviderEndpoints:
    """Tests for /api/v1/tts/providers/* endpoints"""

    def test_get_providers(self, client):
        """Test GET /api/v1/tts/providers"""
        response = client.get("/api/v1/tts/providers")
        assert response.status_code == 200

        data = response.json()
        assert "default_provider" in data
        assert "providers" in data
        assert isinstance(data["providers"], list)

        # Check provider structure
        for provider in data["providers"]:
            assert "name" in provider
            assert "display_name" in provider
            assert "is_local" in provider
            assert "requires_consent" in provider
            assert "available" in provider

    def test_get_provider_info(self, client):
        """Test GET /api/v1/tts/providers/info"""
        response = client.get("/api/v1/tts/providers/info")
        assert response.status_code == 200

        data = response.json()
        assert "default_provider" in data
        assert "providers" in data
        assert "edge_tts" in data["providers"]

    def test_set_default_provider_valid(self, client):
        """Test POST /api/v1/tts/providers/default with valid provider"""
        response = client.post(
            "/api/v1/tts/providers/default",
            json={"provider": "edge_tts"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["default_provider"] == "edge_tts"

    def test_set_default_provider_invalid(self, client):
        """Test POST /api/v1/tts/providers/default with invalid provider"""
        response = client.post(
            "/api/v1/tts/providers/default",
            json={"provider": "invalid_provider"}
        )
        assert response.status_code == 400

    def test_get_provider_status(self, client):
        """Test GET /api/v1/tts/providers/{provider}/status"""
        response = client.get("/api/v1/tts/providers/edge_tts/status")
        assert response.status_code == 200

        data = response.json()
        assert "provider" in data
        assert data["provider"] == "edge_tts"

    def test_get_provider_status_invalid(self, client):
        """Test GET /api/v1/tts/providers/{provider}/status with invalid provider"""
        response = client.get("/api/v1/tts/providers/invalid/status")
        assert response.status_code == 400


# ============================================================================
# VOICE ENDPOINT TESTS
# ============================================================================

class TestVoiceEndpoints:
    """Tests for voice-related endpoints"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_voices(self, client):
        """Test GET /api/v1/tts/voices"""
        response = client.get("/api/v1/tts/voices")
        # May timeout without network, but endpoint should exist
        assert response.status_code in [200, 500]

    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_voices_by_language(self, client):
        """Test GET /api/v1/tts/voices with language filter"""
        response = client.get("/api/v1/tts/voices", params={"language": "en"})
        assert response.status_code in [200, 500]

    def test_get_best_voices(self, client):
        """Test GET /api/v1/tts/voices/best"""
        response = client.get("/api/v1/tts/voices/best")
        assert response.status_code == 200

        data = response.json()
        assert "voices" in data
        assert "en" in data["voices"]

    def test_get_languages(self, client):
        """Test GET /api/v1/tts/languages"""
        response = client.get("/api/v1/tts/languages")
        assert response.status_code == 200

        data = response.json()
        assert "languages" in data
        assert len(data["languages"]) > 0

        # Check language structure
        lang = data["languages"][0]
        assert "code" in lang
        assert "name" in lang
        assert "best_voice" in lang

    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_provider_voices(self, client):
        """Test GET /api/v1/tts/providers/{provider}/voices"""
        response = client.get("/api/v1/tts/providers/edge_tts/voices")
        assert response.status_code in [200, 500]

    def test_get_provider_voices_with_language(self, client):
        """Test GET /api/v1/tts/providers/{provider}/voices with language"""
        response = client.get(
            "/api/v1/tts/providers/edge_tts/voices",
            params={"language": "en"}
        )
        assert response.status_code in [200, 500]


# ============================================================================
# GENERATION ENDPOINT TESTS
# ============================================================================

class TestGenerationEndpoints:
    """Tests for audio generation endpoints"""

    def test_estimate_duration(self, client):
        """Test POST /api/v1/tts/estimate-duration"""
        response = client.post(
            "/api/v1/tts/estimate-duration",
            json={
                "text": "Hello world, this is a test sentence.",
                "language": "en"
            }
        )
        assert response.status_code == 200

        data = response.json()
        assert "text_length" in data
        assert "word_count" in data
        assert "estimated_duration" in data
        assert data["word_count"] == 7

    @pytest.mark.integration
    @pytest.mark.slow
    def test_preview_voice(self, client):
        """Test POST /api/v1/tts/preview"""
        response = client.post(
            "/api/v1/tts/preview",
            json={
                "voice_id": "en-US-AvaMultilingualNeural",
                "text": "Hello, this is a test.",
                "rate": "+0%",
                "volume": "+0%",
                "pitch": "+0Hz"
            }
        )
        # May fail without network
        assert response.status_code in [200, 500]

    @pytest.mark.integration
    @pytest.mark.slow
    def test_generate_tts(self, client):
        """Test POST /api/v1/tts/generate"""
        response = client.post(
            "/api/v1/tts/generate",
            json={
                "text": "Hello, this is a test.",
                "language": "en",
                "voice_id": "en-US-AvaMultilingualNeural",
                "project_name": "_test_project",
                "segment_name": "test_segment",
                "rate": "+0%",
                "volume": "+0%",
                "pitch": "+0Hz",
                "orientation": "horizontal"
            }
        )
        # May fail without network
        assert response.status_code in [200, 500]


# ============================================================================
# CONNECTIVITY TESTS
# ============================================================================

class TestConnectivityEndpoints:
    """Tests for connectivity check endpoints"""

    @pytest.mark.integration
    def test_check_connectivity(self, client):
        """Test GET /api/v1/tts/connectivity"""
        response = client.get("/api/v1/tts/connectivity")
        assert response.status_code == 200

        data = response.json()
        assert "proxy_enabled" in data
        assert "direct_connection" in data
        assert "proxy_connection" in data


# ============================================================================
# CONSENT ENDPOINT TESTS
# ============================================================================

class TestConsentEndpoints:
    """Tests for consent-related endpoints"""

    def test_get_tts_consent_status(self, client):
        """Test GET /api/v1/consent/tts/status"""
        response = client.get("/api/v1/consent/tts/status")
        assert response.status_code == 200

        data = response.json()
        assert "has_consent" in data
        assert "needs_consent" in data
        assert "status" in data

    def test_record_tts_consent(self, client):
        """Test POST /api/v1/consent/tts/record"""
        response = client.post(
            "/api/v1/consent/tts/record",
            json={
                "granted": True,
                "remember_choice": True
            }
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

    def test_get_tts_dialog_content(self, client):
        """Test GET /api/v1/consent/tts/dialog-content"""
        response = client.get("/api/v1/consent/tts/dialog-content")
        assert response.status_code == 200

        data = response.json()
        assert "title" in data
        assert "details" in data

    def test_get_tts_warning_banner(self, client):
        """Test GET /api/v1/consent/tts/warning-banner"""
        response = client.get("/api/v1/consent/tts/warning-banner")
        assert response.status_code == 200

        data = response.json()
        assert "icon" in data
        assert "message" in data


# ============================================================================
# ASYNC TESTS
# ============================================================================

class TestAsyncEndpoints:
    """Async tests for TTS endpoints with mocked authentication"""

    @pytest.mark.asyncio
    async def test_async_get_providers(self, app):
        """Test async GET /api/v1/tts/providers"""
        try:
            from httpx import AsyncClient, ASGITransport
            # Note: app fixture already has auth override applied
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/tts/providers")
                assert response.status_code == 200
                data = response.json()
                assert "providers" in data
        except ImportError:
            pytest.skip("httpx not available")

    @pytest.mark.asyncio
    async def test_async_get_languages(self, app):
        """Test async GET /api/v1/tts/languages"""
        try:
            from httpx import AsyncClient, ASGITransport
            # Note: app fixture already has auth override applied
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/tts/languages")
                assert response.status_code == 200
        except ImportError:
            pytest.skip("httpx not available")


# ============================================================================
# MOCK TESTS (No Network Required)
# ============================================================================

class TestMockedEndpoints:
    """Tests with mocked external dependencies"""

    @pytest.fixture
    def mock_tts_service(self):
        """Mock TTS service for testing without network"""
        with patch('web_ui.api.routes.tts.tts_service') as mock:
            mock.get_current_provider.return_value = "edge_tts"
            mock.get_provider_info.return_value = {
                "default_provider": "edge_tts",
                "providers": {
                    "edge_tts": {
                        "display_name": "Microsoft Edge TTS",
                        "is_local": False,
                        "requires_consent": True,
                    },
                    "coqui": {
                        "display_name": "Coqui TTS (Local)",
                        "is_local": True,
                        "requires_consent": False,
                    }
                }
            }
            mock.get_provider_status = AsyncMock(return_value=[
                {
                    "provider": "edge_tts",
                    "name": "Microsoft Edge TTS",
                    "available": True,
                    "is_default": True,
                    "capabilities": {
                        "is_local": False,
                        "requires_consent": True,
                        "word_timing": True,
                        "voice_cloning": False,
                    }
                }
            ])
            yield mock

    def test_mocked_provider_info(self, client, mock_tts_service):
        """Test provider info with mocked service"""
        response = client.get("/api/v1/tts/providers/info")
        assert response.status_code == 200

        data = response.json()
        assert data["default_provider"] == "edge_tts"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for API error handling"""

    def test_invalid_json(self, client):
        """Test handling of invalid JSON"""
        response = client.post(
            "/api/v1/tts/providers/default",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_missing_required_field(self, client):
        """Test handling of missing required fields"""
        response = client.post(
            "/api/v1/tts/generate",
            json={"text": "Hello"}  # Missing required fields
        )
        assert response.status_code == 422


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not integration"])
