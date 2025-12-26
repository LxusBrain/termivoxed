"""Project-related API schemas"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class VideoInfo(BaseModel):
    """Video metadata information"""
    id: str
    name: str
    path: str
    order: int
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    aspect_ratio: Optional[float] = None
    orientation: Optional[str] = None
    segments_count: int = 0
    file_exists: bool = True  # Whether the video file exists on disk
    # Timeline position for repositioning videos on the timeline
    timeline_start: Optional[float] = None
    timeline_end: Optional[float] = None


class ProjectCreate(BaseModel):
    """Request to create a new project"""
    name: str = Field(..., min_length=1, max_length=100)
    video_paths: List[str] = Field(default_factory=list)


class BGMTrackInfo(BaseModel):
    """BGM track information"""
    id: str
    name: str
    path: str
    start_time: float = 0.0
    end_time: float = 0.0  # 0 = until video end
    volume: int = 100  # 0-200%
    fade_in: float = 0.0
    fade_out: float = 3.0
    loop: bool = True
    muted: bool = False
    order: int = 1
    duration: Optional[float] = None


class ProjectResponse(BaseModel):
    """Project response with full details"""
    name: str
    videos: List[VideoInfo]
    active_video_id: Optional[str] = None
    created_at: datetime
    modified_at: datetime
    background_music_path: Optional[str] = None
    bgm_tracks: List[BGMTrackInfo] = []
    bgm_volume: int = 100  # Global BGM volume (0-200%)
    tts_volume: int = 100  # Global TTS volume (0-200%)
    export_quality: str = "balanced"
    include_subtitles: bool = True
    total_segments: int = 0


class ProjectListItem(BaseModel):
    """Project list item (summary)"""
    name: str
    video_count: int
    created_at: str
    modified_at: str
    segments_count: int


class ProjectStats(BaseModel):
    """Project statistics"""
    name: str
    video_count: int
    total_video_duration: float
    segments_count: int
    created_at: str
    modified_at: str


class AddVideoRequest(BaseModel):
    """Request to add a video to project"""
    video_path: str
    name: Optional[str] = None


class ReorderVideosRequest(BaseModel):
    """Request to reorder videos"""
    video_ids: List[str]


class SetActiveVideoRequest(BaseModel):
    """Request to set active video"""
    video_id: str


# BGM Track request schemas
class AddBGMTrackRequest(BaseModel):
    """Request to add a BGM track"""
    path: str
    name: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    volume: int = 100


class UpdateBGMTrackRequest(BaseModel):
    """Request to update a BGM track"""
    name: Optional[str] = None
    path: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    volume: Optional[int] = None
    fade_in: Optional[float] = None
    fade_out: Optional[float] = None
    loop: Optional[bool] = None
    muted: Optional[bool] = None


class ReorderBGMTracksRequest(BaseModel):
    """Request to reorder BGM tracks"""
    track_ids: List[str]


class UpdateVolumeSettingsRequest(BaseModel):
    """Request to update global volume settings"""
    bgm_volume: Optional[int] = None  # 0-200%
    tts_volume: Optional[int] = None  # 0-200%
