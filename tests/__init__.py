"""
TermiVoxed Test Suite

Comprehensive tests for:
- TTS providers (Edge TTS, Coqui TTS)
- TTS API endpoints
- Privacy consent system
- Timeline calculations
- FFmpeg integration

Run tests with:
    pytest tests/ -v

Run fast tests only:
    pytest tests/ -v -m "not slow"

Run without network tests:
    pytest tests/ -v --skip-integration
"""
