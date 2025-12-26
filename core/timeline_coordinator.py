"""
Timeline Coordinator - Handles absolute timeline positioning for multi-video projects

This module implements proven algorithms for calculating segment positions
across multiple videos, handling edge cases like:
- Segments spanning multiple videos
- Video gaps and overlaps
- BGM track positioning with absolute timestamps
- Audio stream presence/absence

Based on industry-standard NLE (Non-Linear Editing) timeline algorithms.
"""

import os
from typing import List, Dict, Optional, Tuple, NamedTuple
from dataclasses import dataclass, field
from uuid import uuid4

from utils.logger import logger
from backend.ffmpeg_utils import FFmpegUtils


@dataclass
class TimelinePosition:
    """
    Represents an absolute position in the timeline.
    All times are in seconds from the start of the combined output.
    """
    absolute_start: float  # Start time in final output
    absolute_end: float    # End time in final output
    video_id: str          # Source video ID
    video_local_start: float  # Start time within the source video
    video_local_end: float    # End time within the source video

    @property
    def duration(self) -> float:
        return self.absolute_end - self.absolute_start


@dataclass
class VideoTimelineInfo:
    """
    Information about a video's position in the absolute timeline.
    """
    video_id: str
    video_path: str
    video_name: str
    local_duration: float      # Duration of the video file
    trimmed_start: float       # Where the video starts (for trimmed videos)
    trimmed_end: float         # Where the video ends (for trimmed videos)
    trimmed_duration: float    # Effective duration after trimming
    absolute_offset: float     # Start position in absolute timeline
    absolute_end: float        # End position in absolute timeline
    has_audio: bool            # Whether video has audio stream
    width: int
    height: int
    fps: float
    order: int


@dataclass
class SegmentTimelineInfo:
    """
    Information about a segment's position in the absolute timeline.
    """
    segment_id: str
    segment_name: str
    video_id: str

    # Local positions (within the source video)
    local_start: float
    local_end: float

    # Absolute positions (in final combined output)
    absolute_start: float
    absolute_end: float

    # Audio information
    audio_path: Optional[str]
    audio_duration: Optional[float]

    # Subtitle information
    subtitle_path: Optional[str]
    subtitle_enabled: bool

    # For cross-video segments
    spans_videos: bool = False
    continuation_video_ids: List[str] = field(default_factory=list)


@dataclass
class BGMTimelineInfo:
    """
    Information about a BGM track's position in the absolute timeline.
    """
    track_id: str
    track_name: str
    track_path: str

    # Absolute positions
    absolute_start: float
    absolute_end: float

    # Track properties
    volume: int
    fade_in: float
    fade_out: float
    loop: bool
    muted: bool

    # Computed
    audio_duration: Optional[float]
    needs_loop: bool
    loop_count: int


class TimelineCoordinator:
    """
    Coordinates timeline calculations for multi-video projects.

    Uses a two-phase approach:
    1. Build absolute timeline from videos (video layout phase)
    2. Map segments and BGM tracks to absolute positions (content phase)

    This is the standard approach used in professional NLEs like
    Premiere Pro, Final Cut, and DaVinci Resolve.
    """

    def __init__(self, project):
        """
        Initialize with a Project instance.

        Args:
            project: Project model instance
        """
        self.project = project
        self._video_timeline: Dict[str, VideoTimelineInfo] = {}
        self._segment_timeline: Dict[str, SegmentTimelineInfo] = {}
        self._bgm_timeline: Dict[str, BGMTimelineInfo] = {}
        self._total_duration: float = 0.0
        self._is_built: bool = False

    def build_timeline(self) -> bool:
        """
        Build the complete timeline from project data.

        This is the main entry point. Call this before accessing
        any timeline information.

        Returns:
            True if timeline was built successfully
        """
        try:
            logger.info("Building timeline...")

            # Phase 1: Build video layout
            self._build_video_timeline()

            # Phase 2: Map segments to absolute positions
            self._build_segment_timeline()

            # Phase 3: Map BGM tracks to absolute positions
            self._build_bgm_timeline()

            self._is_built = True

            # Log summary
            logger.info(f"Timeline built successfully:")
            logger.info(f"  Total duration: {self._total_duration:.2f}s")
            logger.info(f"  Videos: {len(self._video_timeline)}")
            logger.info(f"  Segments: {len(self._segment_timeline)}")
            logger.info(f"  BGM tracks: {len(self._bgm_timeline)}")

            return True

        except Exception as e:
            logger.error(f"Failed to build timeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _build_video_timeline(self):
        """
        Build the video layout timeline.

        Videos are laid out sequentially based on their order.
        Each video's position is calculated from the cumulative
        duration of previous videos.

        This implements the "sequence" model used in most NLEs.
        """
        self._video_timeline = {}
        cumulative_offset = 0.0

        # Sort videos by order
        sorted_videos = sorted(self.project.videos, key=lambda v: v.order)

        for video in sorted_videos:
            # Get video file info
            if not os.path.exists(video.path):
                logger.warning(f"Video file not found: {video.path}")
                continue

            # Get actual video duration
            local_duration = FFmpegUtils.get_media_duration(video.path)
            if not local_duration:
                logger.warning(f"Could not get duration for: {video.path}")
                continue

            # Get video info
            video_info = FFmpegUtils.get_video_info(video.path)
            has_audio = FFmpegUtils.has_audio_stream(video.path)

            # Handle trimming
            # timeline_start and timeline_end on the Video model represent
            # the trim points within the source video
            trimmed_start = getattr(video, 'timeline_start', 0.0) or 0.0
            trimmed_end = getattr(video, 'timeline_end', local_duration) or local_duration

            # Clamp to actual duration
            trimmed_start = max(0, min(trimmed_start, local_duration))
            trimmed_end = max(trimmed_start, min(trimmed_end, local_duration))
            trimmed_duration = trimmed_end - trimmed_start

            # Create timeline info
            info = VideoTimelineInfo(
                video_id=video.id,
                video_path=video.path,
                video_name=video.name,
                local_duration=local_duration,
                trimmed_start=trimmed_start,
                trimmed_end=trimmed_end,
                trimmed_duration=trimmed_duration,
                absolute_offset=cumulative_offset,
                absolute_end=cumulative_offset + trimmed_duration,
                has_audio=has_audio,
                width=video_info.get('width', 1920) if video_info else 1920,
                height=video_info.get('height', 1080) if video_info else 1080,
                fps=video_info.get('fps', 30.0) if video_info else 30.0,
                order=video.order
            )

            self._video_timeline[video.id] = info

            logger.debug(
                f"Video '{video.name}': local={local_duration:.2f}s, "
                f"trimmed={trimmed_duration:.2f}s, "
                f"absolute={cumulative_offset:.2f}s-{info.absolute_end:.2f}s"
            )

            # Update cumulative offset
            cumulative_offset += trimmed_duration

        self._total_duration = cumulative_offset

    def _build_segment_timeline(self):
        """
        Build the segment timeline.

        Segments are mapped from their video-local positions to
        absolute timeline positions.

        Cross-video segments (segments that span multiple videos)
        are identified and flagged for special handling.
        """
        self._segment_timeline = {}

        # Process segments from all videos
        for video in self.project.videos:
            video_info = self._video_timeline.get(video.id)
            if not video_info:
                continue

            for segment in video.timeline.segments:
                # Calculate absolute positions
                # Segment times are relative to the video's trimmed start
                local_start = segment.start_time
                local_end = segment.end_time

                # Convert to absolute timeline positions
                absolute_start = video_info.absolute_offset + local_start
                absolute_end = video_info.absolute_offset + local_end

                # Check for cross-video segment
                spans_videos = False
                continuation_video_ids = []

                if absolute_end > video_info.absolute_end:
                    spans_videos = True
                    # Find which videos this segment continues into
                    for other_id, other_info in self._video_timeline.items():
                        if other_id == video.id:
                            continue
                        if (other_info.absolute_offset < absolute_end and
                            other_info.absolute_end > video_info.absolute_end):
                            continuation_video_ids.append(other_id)

                # Get audio info
                audio_duration = None
                if segment.audio_path and os.path.exists(segment.audio_path):
                    audio_duration = FFmpegUtils.get_media_duration(segment.audio_path)

                info = SegmentTimelineInfo(
                    segment_id=segment.id,
                    segment_name=segment.name,
                    video_id=video.id,
                    local_start=local_start,
                    local_end=local_end,
                    absolute_start=absolute_start,
                    absolute_end=absolute_end,
                    audio_path=segment.audio_path,
                    audio_duration=audio_duration,
                    subtitle_path=segment.subtitle_path,
                    subtitle_enabled=segment.subtitle_enabled,
                    spans_videos=spans_videos,
                    continuation_video_ids=continuation_video_ids
                )

                self._segment_timeline[segment.id] = info

                if spans_videos:
                    logger.info(
                        f"Cross-video segment '{segment.name}': "
                        f"continues into videos {continuation_video_ids}"
                    )

    def _build_bgm_timeline(self):
        """
        Build the BGM track timeline.

        BGM tracks use absolute timeline positions directly,
        as they span the entire output.
        """
        self._bgm_timeline = {}

        if not hasattr(self.project, 'bgm_tracks'):
            return

        for track in self.project.bgm_tracks:
            if track.muted or not track.path:
                continue

            if not os.path.exists(track.path):
                logger.warning(f"BGM file not found: {track.path}")
                continue

            # Get audio duration
            audio_duration = FFmpegUtils.get_media_duration(track.path)

            # Calculate absolute positions
            absolute_start = track.start_time
            absolute_end = track.end_time if track.end_time > 0 else self._total_duration

            # Clamp to timeline duration
            absolute_start = max(0, min(absolute_start, self._total_duration))
            absolute_end = max(absolute_start, min(absolute_end, self._total_duration))

            track_duration = absolute_end - absolute_start

            # Calculate looping needs
            needs_loop = False
            loop_count = 0

            if track.loop and audio_duration and track_duration > audio_duration:
                needs_loop = True
                loop_count = int((track_duration / audio_duration) + 1)

            info = BGMTimelineInfo(
                track_id=track.id,
                track_name=track.name,
                track_path=track.path,
                absolute_start=absolute_start,
                absolute_end=absolute_end,
                volume=track.volume,
                fade_in=track.fade_in,
                fade_out=track.fade_out,
                loop=track.loop,
                muted=track.muted,
                audio_duration=audio_duration,
                needs_loop=needs_loop,
                loop_count=loop_count
            )

            self._bgm_timeline[track.id] = info

            logger.debug(
                f"BGM '{track.name}': "
                f"absolute={absolute_start:.2f}s-{absolute_end:.2f}s, "
                f"loop={needs_loop}, count={loop_count}"
            )

    # ========== Query Methods ==========

    @property
    def total_duration(self) -> float:
        """Get total timeline duration in seconds."""
        return self._total_duration

    @property
    def video_count(self) -> int:
        """Get number of videos in timeline."""
        return len(self._video_timeline)

    @property
    def segment_count(self) -> int:
        """Get number of segments in timeline."""
        return len(self._segment_timeline)

    def get_video_info(self, video_id: str) -> Optional[VideoTimelineInfo]:
        """Get timeline info for a video."""
        return self._video_timeline.get(video_id)

    def get_segment_info(self, segment_id: str) -> Optional[SegmentTimelineInfo]:
        """Get timeline info for a segment."""
        return self._segment_timeline.get(segment_id)

    def get_bgm_info(self, track_id: str) -> Optional[BGMTimelineInfo]:
        """Get timeline info for a BGM track."""
        return self._bgm_timeline.get(track_id)

    def get_videos_in_order(self) -> List[VideoTimelineInfo]:
        """Get all videos sorted by absolute position."""
        return sorted(
            self._video_timeline.values(),
            key=lambda v: v.absolute_offset
        )

    def get_segments_in_order(self) -> List[SegmentTimelineInfo]:
        """Get all segments sorted by absolute start time."""
        return sorted(
            self._segment_timeline.values(),
            key=lambda s: s.absolute_start
        )

    def get_active_bgm_tracks(self) -> List[BGMTimelineInfo]:
        """Get active (non-muted) BGM tracks sorted by start time."""
        return sorted(
            [t for t in self._bgm_timeline.values() if not t.muted],
            key=lambda t: t.absolute_start
        )

    def get_segments_for_video(self, video_id: str) -> List[SegmentTimelineInfo]:
        """Get all segments that affect a specific video."""
        return [
            s for s in self._segment_timeline.values()
            if s.video_id == video_id or video_id in s.continuation_video_ids
        ]

    def get_segment_at_time(self, absolute_time: float) -> List[SegmentTimelineInfo]:
        """Get all segments active at a specific absolute time."""
        return [
            s for s in self._segment_timeline.values()
            if s.absolute_start <= absolute_time < s.absolute_end
        ]

    def get_video_at_time(self, absolute_time: float) -> Optional[VideoTimelineInfo]:
        """Get the video at a specific absolute time."""
        for video in self._video_timeline.values():
            if video.absolute_offset <= absolute_time < video.absolute_end:
                return video
        return None

    def absolute_to_local(
        self,
        absolute_time: float,
        video_id: str
    ) -> Optional[float]:
        """
        Convert absolute timeline time to local video time.

        Args:
            absolute_time: Time in absolute timeline
            video_id: Target video ID

        Returns:
            Local time within the video, or None if out of range
        """
        video = self._video_timeline.get(video_id)
        if not video:
            return None

        if absolute_time < video.absolute_offset or absolute_time > video.absolute_end:
            return None

        return absolute_time - video.absolute_offset + video.trimmed_start

    def local_to_absolute(
        self,
        local_time: float,
        video_id: str
    ) -> Optional[float]:
        """
        Convert local video time to absolute timeline time.

        Args:
            local_time: Time within the video
            video_id: Source video ID

        Returns:
            Absolute timeline time, or None if out of range
        """
        video = self._video_timeline.get(video_id)
        if not video:
            return None

        if local_time < video.trimmed_start or local_time > video.trimmed_end:
            return None

        return video.absolute_offset + (local_time - video.trimmed_start)

    # ========== Export Helpers ==========

    def get_common_video_specs(self) -> Dict:
        """
        Get common video specifications for export.

        Determines target resolution and FPS based on all videos.
        Uses highest resolution and FPS as targets.

        Returns:
            Dictionary with width, height, fps, needs_scaling, needs_fps_conversion
        """
        if not self._video_timeline:
            return {
                'width': 1920,
                'height': 1080,
                'fps': 30.0,
                'needs_scaling': False,
                'needs_fps_conversion': False,
                'all_have_audio': True
            }

        videos = list(self._video_timeline.values())

        # Collect unique values
        resolutions = set((v.width, v.height) for v in videos)
        fps_values = set(v.fps for v in videos)

        # Find targets (highest)
        target_width = max(v.width for v in videos)
        target_height = max(v.height for v in videos)
        target_fps = max(v.fps for v in videos)

        # Check if all have audio
        all_have_audio = all(v.has_audio for v in videos)

        return {
            'width': target_width,
            'height': target_height,
            'fps': target_fps,
            'needs_scaling': len(resolutions) > 1,
            'needs_fps_conversion': len(fps_values) > 1,
            'all_have_audio': all_have_audio
        }

    def get_ffmpeg_audio_delay(
        self,
        segment_id: str,
        base_offset: float = 0.0
    ) -> Optional[str]:
        """
        Get the FFmpeg adelay filter value for a segment.

        Args:
            segment_id: Segment ID
            base_offset: Additional offset to apply (for multi-video exports)

        Returns:
            FFmpeg adelay value (e.g., "5000|5000" for 5 second delay)
            or None if no delay needed
        """
        segment = self._segment_timeline.get(segment_id)
        if not segment:
            return None

        delay_ms = int((segment.absolute_start + base_offset) * 1000)

        if delay_ms <= 0:
            return None

        return f"{delay_ms}|{delay_ms}"

    def get_ffmpeg_bgm_filter(
        self,
        track_id: str,
        total_duration: Optional[float] = None
    ) -> Optional[str]:
        """
        Get the FFmpeg filter chain for a BGM track.

        Generates a complete filter chain including:
        - Looping (if needed)
        - Volume adjustment
        - Fade in/out
        - Trim to duration
        - Delay to start time

        Args:
            track_id: BGM track ID
            total_duration: Override total duration (optional)

        Returns:
            FFmpeg filter chain string, or None if track not found
        """
        import math

        track = self._bgm_timeline.get(track_id)
        if not track:
            return None

        duration = total_duration or self._total_duration
        track_duration = track.absolute_end - track.absolute_start

        filters = []

        # Loop if needed
        if track.needs_loop and track.audio_duration:
            sample_size = int(track.audio_duration * 44100)
            filters.append(f"aloop=loop={track.loop_count}:size={sample_size}")

        # Volume adjustment (convert percentage to dB)
        # Check muted flag or zero volume first
        if track.muted or track.volume == 0:
            # Effectively mute the track by setting very low volume
            filters.append("volume=0")
        elif track.volume != 100:
            # Default BGM reduction is 20dB, adjust based on track volume
            # Volume can be 0-200 (200% = louder than default)
            base_reduction = 20.0
            volume_adjustment = 20 * math.log10(track.volume / 100)
            effective_reduction = base_reduction - volume_adjustment
            filters.append(f"volume=-{effective_reduction:.1f}dB")
        else:
            filters.append("volume=-20dB")  # Default reduction at 100%

        # Fade in
        if track.fade_in > 0:
            filters.append(f"afade=t=in:st=0:d={track.fade_in:.1f}")

        # Fade out
        if track.fade_out > 0:
            fade_out_start = track_duration - track.fade_out
            if fade_out_start > 0:
                filters.append(f"afade=t=out:st={fade_out_start:.1f}:d={track.fade_out:.1f}")

        # Trim to duration
        filters.append(f"atrim=duration={track_duration:.3f}")

        # Delay to start time
        if track.absolute_start > 0:
            delay_ms = int(track.absolute_start * 1000)
            filters.append(f"adelay={delay_ms}|{delay_ms}")
            # Pad to total duration for proper mixing
            filters.append(f"apad=whole_dur={duration:.3f}")

        return ','.join(filters)

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the timeline for export.

        Checks for:
        - Missing files
        - Overlapping segments (warning)
        - Cross-video segments without continuation handling
        - Audio length mismatches

        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []
        is_valid = True

        # Check video files
        for video in self._video_timeline.values():
            if not os.path.exists(video.video_path):
                warnings.append(f"Video file missing: {video.video_path}")
                is_valid = False

        # Check segment audio files
        for segment in self._segment_timeline.values():
            if segment.audio_path and not os.path.exists(segment.audio_path):
                warnings.append(
                    f"Audio missing for segment '{segment.segment_name}': "
                    f"{segment.audio_path}"
                )

        # Check for overlapping segments (within same video)
        sorted_segments = self.get_segments_in_order()
        for i in range(len(sorted_segments) - 1):
            current = sorted_segments[i]
            next_seg = sorted_segments[i + 1]

            if (current.video_id == next_seg.video_id and
                current.absolute_end > next_seg.absolute_start):
                warnings.append(
                    f"Overlapping segments: '{current.segment_name}' and "
                    f"'{next_seg.segment_name}'"
                )

        # Check cross-video segments
        for segment in self._segment_timeline.values():
            if segment.spans_videos:
                warnings.append(
                    f"Cross-video segment: '{segment.segment_name}' - "
                    f"will be handled with continuation"
                )

        # Check BGM files
        for track in self._bgm_timeline.values():
            if not os.path.exists(track.track_path):
                warnings.append(f"BGM file missing: {track.track_path}")

        return is_valid, warnings

    def get_debug_info(self) -> str:
        """Get detailed debug information about the timeline."""
        lines = [
            "=" * 60,
            "TIMELINE DEBUG INFO",
            "=" * 60,
            f"Total Duration: {self._total_duration:.2f}s",
            "",
            "VIDEOS:",
            "-" * 40,
        ]

        for video in self.get_videos_in_order():
            lines.append(
                f"  [{video.order}] {video.video_name}: "
                f"{video.absolute_offset:.2f}s - {video.absolute_end:.2f}s "
                f"(duration: {video.trimmed_duration:.2f}s, "
                f"audio: {'yes' if video.has_audio else 'no'})"
            )

        lines.extend([
            "",
            "SEGMENTS:",
            "-" * 40,
        ])

        for segment in self.get_segments_in_order():
            cross = " [CROSS-VIDEO]" if segment.spans_videos else ""
            lines.append(
                f"  {segment.segment_name}: "
                f"{segment.absolute_start:.2f}s - {segment.absolute_end:.2f}s"
                f"{cross}"
            )

        if self._bgm_timeline:
            lines.extend([
                "",
                "BGM TRACKS:",
                "-" * 40,
            ])

            for track in self.get_active_bgm_tracks():
                lines.append(
                    f"  {track.track_name}: "
                    f"{track.absolute_start:.2f}s - {track.absolute_end:.2f}s "
                    f"(vol: {track.volume}%, loop: {track.needs_loop})"
                )

        lines.append("=" * 60)

        return "\n".join(lines)
