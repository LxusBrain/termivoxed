"""TTS-related API schemas"""

from typing import Optional, List
from pydantic import BaseModel


class VoiceInfo(BaseModel):
    """Voice information"""
    name: str
    short_name: str
    gender: str
    language: str
    locale: str


class VoiceListResponse(BaseModel):
    """Response containing list of voices"""
    voices: List[VoiceInfo]
    total: int


class VoicePreviewRequest(BaseModel):
    """Request to preview a voice"""
    voice_id: str
    text: str = "Hello, this is a preview of this voice."
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


class VoicePreviewResponse(BaseModel):
    """Response with preview audio URL"""
    audio_url: str
    duration: float


class TTSGenerateRequest(BaseModel):
    """Request to generate TTS audio"""
    text: str
    voice_id: str
    language: str = "en"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"
    project_name: str = "default"
    segment_name: Optional[str] = None
    orientation: str = "horizontal"


class TTSGenerateResponse(BaseModel):
    """Response with generated audio info"""
    audio_path: str
    subtitle_path: Optional[str] = None
    duration: float
    cached: bool = False


class TTSConnectivityStatus(BaseModel):
    """TTS connectivity check result"""
    proxy_enabled: bool
    proxy_url: Optional[str] = None
    direct_connection: bool
    proxy_connection: bool
    recommended_mode: str


class BestVoicesResponse(BaseModel):
    """Best voices per language"""
    voices: dict  # language code -> voice id
