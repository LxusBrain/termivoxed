"""Export-related API schemas"""

from typing import Optional, List, Literal
from pydantic import BaseModel


class ExportConfig(BaseModel):
    """Export configuration"""
    quality: Literal["lossless", "high", "balanced"] = "balanced"
    include_subtitles: bool = True
    background_music_path: Optional[str] = None
    output_path: Optional[str] = None  # Custom output directory
    output_filename: Optional[str] = None  # Custom output filename (without extension)


class ExportRequest(BaseModel):
    """Request to export a project"""
    project_name: str
    config: ExportConfig = ExportConfig()
    export_type: Literal["single", "all", "combined"] = "single"
    video_id: Optional[str] = None  # For single export


class ExportProgress(BaseModel):
    """Export progress update"""
    stage: str  # preprocessing, fonts, tts, segments, combining, bgm, cleanup, completed, error
    message: str
    progress: int  # 0-100
    current_step: int = 0
    total_steps: int = 0
    # Granular details
    current_segment: Optional[str] = None
    current_voice: Optional[str] = None
    detail: Optional[str] = None  # Additional context like "Using FFmpeg..."
    # ETA and timing info
    eta_seconds: Optional[float] = None  # Estimated time remaining in seconds
    eta_formatted: Optional[str] = None  # Human-readable ETA (e.g., "2m 30s")
    elapsed_seconds: Optional[float] = None  # Time elapsed since start
    processing_speed: Optional[float] = None  # FFmpeg processing speed (e.g., 1.5x)


class ExportResult(BaseModel):
    """Export result"""
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    duration: float  # Time taken in seconds


class ExportQueueItem(BaseModel):
    """Item in export queue"""
    id: str
    project_name: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: int
    current_stage: Optional[str] = None
    current_detail: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_path: Optional[str] = None
    error: Optional[str] = None


class PreviewRequest(BaseModel):
    """Request to generate segment preview"""
    project_name: str
    segment_index: int


class PreviewResponse(BaseModel):
    """Preview response"""
    video_url: str
    duration: float


class SegmentAudioRequest(BaseModel):
    """Request to generate/preview segment audio"""
    project_name: str
    segment_id: str


class SegmentAudioResponse(BaseModel):
    """Response with segment audio"""
    audio_url: str
    duration: float
    cached: bool
    job_id: Optional[str] = None  # For voice cloning - client should connect to WebSocket for progress


class PreviewSegmentAudioRequest(BaseModel):
    """Request to preview segment audio with custom parameters (without saving)"""
    project_name: str
    text: str
    voice_id: str
    language: str = "en"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


class PreviewSegmentAudioResponse(BaseModel):
    """Response with preview audio"""
    audio_url: str
    duration: float
