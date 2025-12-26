"""BGM Track model - Background music tracks for timeline"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4


@dataclass
class BGMTrack:
    """
    Background music track that spans a time range in the timeline.

    Similar to how video editing software handles audio tracks,
    each BGM track has a start/end time and volume control.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    path: str = ""  # Path to the audio file
    start_time: float = 0.0  # Start time in seconds (position on timeline)
    end_time: float = 0.0  # End time in seconds (0 = until video end)
    audio_offset: float = 0.0  # Offset into audio file for start trimming (like segment.audio_offset)
    volume: int = 100  # Volume percentage (0-100), 100 = default (-20dB reduction)
    fade_in: float = 0.0  # Fade in duration in seconds
    fade_out: float = 3.0  # Fade out duration in seconds
    loop: bool = True  # Whether to loop if track is shorter than time range
    muted: bool = False  # Whether track is muted
    order: int = 1  # Track order (for layering multiple BGM)

    # Computed properties
    duration: Optional[float] = None  # Duration of the audio file (set when loaded)

    def to_dict(self) -> dict:
        """Serialize to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "audio_offset": self.audio_offset,
            "volume": self.volume,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "loop": self.loop,
            "muted": self.muted,
            "order": self.order,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BGMTrack':
        """Deserialize from dictionary"""
        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            path=data.get("path", ""),
            start_time=data.get("start_time", 0.0),
            end_time=data.get("end_time", 0.0),
            audio_offset=data.get("audio_offset", 0.0),
            volume=data.get("volume", 100),
            fade_in=data.get("fade_in", 0.0),
            fade_out=data.get("fade_out", 3.0),
            loop=data.get("loop", True),
            muted=data.get("muted", False),
            order=data.get("order", 1),
            duration=data.get("duration"),
        )

    def get_effective_end_time(self, video_duration: float) -> float:
        """Get the effective end time, using video duration if end_time is 0"""
        return self.end_time if self.end_time > 0 else video_duration

    def get_time_range_duration(self, video_duration: float) -> float:
        """Get the duration of the time range this track covers"""
        return self.get_effective_end_time(video_duration) - self.start_time

    def overlaps_with(self, other: 'BGMTrack', video_duration: float) -> bool:
        """Check if this track overlaps with another track"""
        self_start = self.start_time
        self_end = self.get_effective_end_time(video_duration)
        other_start = other.start_time
        other_end = other.get_effective_end_time(video_duration)

        return not (self_end <= other_start or other_end <= self_start)

    def get_volume_db_reduction(self) -> float:
        """
        Convert volume percentage to dB reduction.

        100% = -20dB (default, good balance with TTS)
        50% = -26dB (quieter)
        0% = muted
        150% = -14dB (louder)
        """
        if self.volume == 0 or self.muted:
            return float('inf')  # Effectively muted

        # Base reduction is 20dB at 100% volume
        # Each halving of volume adds ~6dB reduction
        # Formula: base_reduction + 20 * log10(100/volume)
        import math
        base_reduction = 20.0
        volume_adjustment = 20 * math.log10(100 / self.volume) if self.volume > 0 else 60
        return base_reduction + volume_adjustment

    def __str__(self) -> str:
        return f"BGMTrack({self.name}, {self.start_time}s-{self.end_time}s, vol={self.volume}%)"
