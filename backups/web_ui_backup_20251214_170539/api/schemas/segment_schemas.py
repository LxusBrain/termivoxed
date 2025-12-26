"""Segment-related API schemas"""

from typing import Optional
from pydantic import BaseModel, Field


class SubtitleStyle(BaseModel):
    """Subtitle styling configuration"""
    enabled: bool = True
    font: str = "Roboto"
    size: int = 20
    color: str = "&H00FFFFFF"
    position: int = 30
    border_enabled: bool = True
    border_style: int = 1
    outline_width: float = 0.5
    outline_color: str = "&H00000000"
    shadow: float = 0.0
    shadow_color: str = "&H80000000"


class VoiceSettings(BaseModel):
    """Voice configuration for TTS"""
    voice_id: str = ""
    language: str = "en"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


class SegmentCreate(BaseModel):
    """Request to create a new segment"""
    name: str = Field(..., min_length=1)
    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., gt=0)
    text: str = ""  # Optional - can be empty, filled later
    language: str = "en"
    voice_id: Optional[str] = None
    subtitle_style: Optional[SubtitleStyle] = None
    # Cross-video extension
    extends_to_next_video: bool = False  # Allow segment to extend into next video


class SegmentUpdate(BaseModel):
    """Request to update a segment"""
    name: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    text: Optional[str] = None
    language: Optional[str] = None
    voice_id: Optional[str] = None
    rate: Optional[str] = None
    volume: Optional[str] = None
    pitch: Optional[str] = None
    subtitle_style: Optional[SubtitleStyle] = None
    # Direct subtitle fields (alternative to subtitle_style)
    subtitle_enabled: Optional[bool] = None
    subtitle_font: Optional[str] = None
    subtitle_size: Optional[int] = None
    subtitle_color: Optional[str] = None
    subtitle_position: Optional[int] = None
    subtitle_border_enabled: Optional[bool] = None
    subtitle_border_style: Optional[int] = None
    subtitle_outline_width: Optional[float] = None
    subtitle_outline_color: Optional[str] = None
    subtitle_shadow: Optional[float] = None
    subtitle_shadow_color: Optional[str] = None
    # Cross-video extension
    extends_to_next_video: Optional[bool] = None


class SegmentResponse(BaseModel):
    """Segment response"""
    id: str
    name: str
    video_id: Optional[str] = None
    start_time: float
    end_time: float
    duration: float
    text: str
    language: str
    voice_id: str
    rate: str
    volume: str
    pitch: str
    audio_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    # Subtitle settings
    subtitle_enabled: bool = True
    subtitle_font: str = "Roboto"
    subtitle_size: int = 20
    subtitle_color: str = "&H00FFFFFF"
    subtitle_position: int = 30
    subtitle_border_enabled: bool = True
    subtitle_border_style: int = 1
    subtitle_outline_width: float = 0.5
    subtitle_outline_color: str = "&H00000000"
    subtitle_shadow: float = 0.0
    subtitle_shadow_color: str = "&H80000000"
    # Audio duration info for UI display
    estimated_audio_duration: Optional[float] = None
    audio_fits_segment: Optional[bool] = None
    # Cross-video extension info
    extends_to_next_video: bool = False
    overflow_duration: Optional[float] = None  # How much extends into next video
    next_video_name: Optional[str] = None  # Name of next video (for UI display)


class SegmentTimingAnalysis(BaseModel):
    """Analysis of segment timing vs. content"""
    segment_id: str
    segment_duration: float
    text_length: int
    estimated_audio_duration: float
    audio_fits: bool
    overflow_seconds: Optional[float] = None
    recommended_end_time: Optional[float] = None
    suggestion: str
