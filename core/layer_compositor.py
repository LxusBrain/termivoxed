"""
Layer Compositor - Handles layer-based video compositing with stack priority

This module implements a proper NLE-style layer compositor that:
- Tracks video positions on timeline (timeline_start, timeline_end)
- Uses stack priority (order) to determine visibility
- Calculates exact visibility ranges for each video
- Handles segments that cross video boundaries
- Manages BGM tracks with their own timeline positions

The key insight: In a layer-based timeline:
- Videos can overlap in time
- Only the TOP video (lowest order) is visible at any given time
- Videos below only show when there's no video above them

Example:
  Video A: timeline_start=0, duration=10s, order=1 (TOP)
  Video B: timeline_start=7, duration=15s, order=2 (BELOW)

  Visibility:
  - 0-10s: Video A is visible
  - 10-22s: Video B is visible (starts from its 3s mark, since 7-10s was covered by A)
"""

import os
from typing import List, Dict, Optional, Tuple, NamedTuple
from dataclasses import dataclass, field
from collections import defaultdict

from utils.logger import logger
from backend.ffmpeg_utils import FFmpegUtils


@dataclass
class TimeRange:
    """A time range with start and end"""
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0, self.end - self.start)

    def overlaps(self, other: 'TimeRange') -> bool:
        """Check if this range overlaps with another"""
        return self.start < other.end and other.start < self.end

    def intersection(self, other: 'TimeRange') -> Optional['TimeRange']:
        """Get intersection with another range, or None if no overlap"""
        if not self.overlaps(other):
            return None
        return TimeRange(
            start=max(self.start, other.start),
            end=min(self.end, other.end)
        )

    def __repr__(self):
        return f"[{self.start:.2f}s-{self.end:.2f}s]"


@dataclass
class VideoLayer:
    """
    Represents a video layer on the timeline.

    Timeline positioning:
    - timeline_start: Where this video appears on the absolute timeline
    - timeline_end: Where this video ends on the absolute timeline

    Source video info:
    - source_start: Start point within the source video (for trimming)
    - source_end: End point within the source video (for trimming)
    - source_duration: Full duration of the source video file

    Stack info:
    - order: Stack position (lower = top = higher priority)
    """
    video_id: str
    video_name: str
    video_path: str

    # Timeline position (absolute)
    timeline_start: float
    timeline_end: float

    # Source video trimming
    source_start: float = 0.0  # Where to start reading from source
    source_end: float = 0.0    # Where to stop reading from source
    source_duration: float = 0.0

    # Stack position (lower = top = visible first)
    order: int = 1

    # Video properties
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    has_audio: bool = True

    @property
    def timeline_duration(self) -> float:
        """Duration on the timeline"""
        return self.timeline_end - self.timeline_start

    @property
    def source_used_duration(self) -> float:
        """Duration of source video being used"""
        return self.source_end - self.source_start

    def get_timeline_range(self) -> TimeRange:
        """Get timeline range for this video"""
        return TimeRange(self.timeline_start, self.timeline_end)

    def timeline_to_source(self, timeline_time: float) -> Optional[float]:
        """
        Convert timeline time to source video time.

        Returns None if timeline_time is outside this video's range.
        """
        if timeline_time < self.timeline_start or timeline_time > self.timeline_end:
            return None

        # Offset within this video's timeline range
        offset = timeline_time - self.timeline_start
        # Convert to source time
        return self.source_start + offset

    def source_to_timeline(self, source_time: float) -> Optional[float]:
        """
        Convert source video time to timeline time.

        Returns None if source_time is outside the used range.
        """
        if source_time < self.source_start or source_time > self.source_end:
            return None

        # Offset within source
        offset = source_time - self.source_start
        # Convert to timeline
        return self.timeline_start + offset


@dataclass
class VisibilitySegment:
    """
    A segment of time where a specific video is visible.

    This represents the actual output after considering stack priority.
    """
    video_id: str
    video_name: str
    video_path: str

    # Timeline range where this video is visible
    timeline_start: float
    timeline_end: float

    # Corresponding source video range
    source_start: float
    source_end: float

    # For FFmpeg
    video_index: int = 0  # Index in the FFmpeg input list

    @property
    def duration(self) -> float:
        return self.timeline_end - self.timeline_start


@dataclass
class SegmentPlacement:
    """
    Describes where a voice-over segment should be placed in the final output.

    Handles segments that span multiple videos by splitting them.
    """
    segment_id: str
    segment_name: str

    # Original segment timing (relative to its video)
    original_video_id: str
    original_start: float  # Start time within original video
    original_end: float    # End time within original video

    # Absolute timeline timing
    timeline_start: float
    timeline_end: float

    # Audio/subtitle info
    audio_path: Optional[str] = None
    subtitle_path: Optional[str] = None

    # For cross-video segments
    is_continuation: bool = False
    continues_into_next: bool = False
    audio_offset: float = 0.0  # Seconds to skip from audio/subtitle start (for continuations)


@dataclass
class BGMPlacement:
    """
    Describes where a BGM track should be placed in the final output.
    """
    track_id: str
    track_name: str
    track_path: str

    # Timeline position
    timeline_start: float
    timeline_end: float

    # Audio properties
    volume: int = 100
    fade_in: float = 0.0
    fade_out: float = 0.0
    loop: bool = False
    muted: bool = False

    # Computed
    source_duration: Optional[float] = None
    needs_loop: bool = False
    loop_count: int = 0


class LayerCompositor:
    """
    Computes the final composited timeline from layered videos.

    Algorithm:
    1. Build video layers from project data
    2. Calculate visibility ranges (which video is visible when)
    3. Map segments to their final positions
    4. Map BGM tracks to their final positions
    5. Generate FFmpeg commands for export
    """

    def __init__(self, project):
        """
        Initialize with a Project instance.
        """
        self.project = project
        self._layers: List[VideoLayer] = []
        self._visibility_map: List[VisibilitySegment] = []
        self._segment_placements: List[SegmentPlacement] = []
        self._bgm_placements: List[BGMPlacement] = []
        self._total_duration: float = 0.0
        self._is_built: bool = False

    def build(self) -> bool:
        """
        Build the compositor from project data.

        Returns True if successful.
        """
        try:
            logger.info("=" * 60)
            logger.info("LAYER COMPOSITOR: Building timeline")
            logger.info("=" * 60)

            # Step 1: Build video layers
            self._build_layers()

            # Step 2: Calculate visibility map
            self._calculate_visibility()

            # Step 3: Map segments
            self._map_segments()

            # Step 4: Map BGM tracks
            self._map_bgm_tracks()

            self._is_built = True

            # Log summary
            self._log_summary()

            return True

        except Exception as e:
            logger.error(f"Layer compositor build failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _build_layers(self):
        """
        Build video layers from project videos.
        """
        self._layers = []

        for video in self.project.videos:
            # Get video file info
            if not os.path.exists(video.path):
                logger.warning(f"Video file not found: {video.path}")
                continue

            # Get source video duration
            source_duration = FFmpegUtils.get_media_duration(video.path)
            if not source_duration:
                logger.warning(f"Could not get duration for: {video.path}")
                continue

            # Get video info
            video_info = FFmpegUtils.get_video_info(video.path)
            has_audio = FFmpegUtils.has_audio_stream(video.path)

            # Determine timeline position
            # If timeline_start is set, use it; otherwise calculate from order
            if video.timeline_start is not None:
                timeline_start = video.timeline_start
            else:
                # Calculate based on order (sequential layout)
                timeline_start = self._calculate_sequential_start(video.order)

            # Determine source trim points
            # Use explicit source_start/source_end from video if set
            # Otherwise default to full source video
            source_start = getattr(video, 'source_start', 0.0) or 0.0
            source_end = getattr(video, 'source_end', None)
            if source_end is None or source_end <= 0:
                source_end = source_duration
            # Clamp to valid range
            source_start = max(0, min(source_start, source_duration))
            source_end = max(source_start + 0.1, min(source_end, source_duration))

            # Calculate effective duration after source trimming
            effective_duration = source_end - source_start

            # Determine timeline_end
            if video.timeline_end is not None:
                timeline_end = video.timeline_end
            else:
                # Use effective duration (after source trimming)
                timeline_end = timeline_start + effective_duration

            layer = VideoLayer(
                video_id=video.id,
                video_name=video.name,
                video_path=video.path,
                timeline_start=timeline_start,
                timeline_end=timeline_end,
                source_start=source_start,
                source_end=source_end,
                source_duration=source_duration,
                order=video.order,
                width=video_info.get('width', 1920) if video_info else 1920,
                height=video_info.get('height', 1080) if video_info else 1080,
                fps=video_info.get('fps', 30.0) if video_info else 30.0,
                has_audio=has_audio
            )

            self._layers.append(layer)

            logger.info(
                f"Layer: {video.name} | "
                f"timeline={timeline_start:.2f}s-{timeline_end:.2f}s | "
                f"source={source_start:.2f}s-{source_end:.2f}s | "
                f"order={video.order} (stack priority)"
            )

        # Sort by order (stack priority)
        self._layers.sort(key=lambda l: l.order)

        # Calculate total duration
        if self._layers:
            self._total_duration = max(l.timeline_end for l in self._layers)

    def _calculate_sequential_start(self, order: int) -> float:
        """
        Calculate sequential start time for videos without explicit timeline positions.
        """
        total = 0.0
        for layer in self._layers:
            if layer.order < order:
                total += layer.timeline_duration
        return total

    def _calculate_visibility(self):
        """
        Calculate which video is visible at each point in time.

        Algorithm:
        1. Collect all time boundaries (starts and ends)
        2. For each time slice, determine which video is on top
        3. Build visibility segments

        This is O(n log n) where n is number of videos.
        """
        self._visibility_map = []

        if not self._layers:
            return

        # Collect all time boundaries
        boundaries = set()
        for layer in self._layers:
            boundaries.add(layer.timeline_start)
            boundaries.add(layer.timeline_end)

        boundaries = sorted(boundaries)

        # For each time slice, find the top video
        for i in range(len(boundaries) - 1):
            slice_start = boundaries[i]
            slice_end = boundaries[i + 1]

            if slice_end <= slice_start:
                continue

            # Find all videos active in this slice
            active_layers = [
                layer for layer in self._layers
                if layer.timeline_start <= slice_start and layer.timeline_end >= slice_end
            ]

            if not active_layers:
                # Gap in timeline - no video
                logger.debug(f"Gap in timeline: {slice_start:.2f}s - {slice_end:.2f}s")
                continue

            # Top video = lowest order number
            top_layer = min(active_layers, key=lambda l: l.order)

            # Calculate source range for this slice
            source_start = top_layer.timeline_to_source(slice_start)
            source_end = top_layer.timeline_to_source(slice_end)

            if source_start is None or source_end is None:
                logger.warning(f"Could not map timeline to source for {top_layer.video_name}")
                continue

            # Create visibility segment
            vis_seg = VisibilitySegment(
                video_id=top_layer.video_id,
                video_name=top_layer.video_name,
                video_path=top_layer.video_path,
                timeline_start=slice_start,
                timeline_end=slice_end,
                source_start=source_start,
                source_end=source_end
            )

            self._visibility_map.append(vis_seg)

        # Merge consecutive segments from same video
        self._merge_visibility_segments()

        # Assign video indices for FFmpeg
        self._assign_video_indices()

        # Log visibility map
        logger.info("Visibility Map:")
        for seg in self._visibility_map:
            logger.info(
                f"  {seg.timeline_start:.2f}s - {seg.timeline_end:.2f}s: "
                f"{seg.video_name} (source: {seg.source_start:.2f}s - {seg.source_end:.2f}s)"
            )

    def _merge_visibility_segments(self):
        """
        Merge consecutive visibility segments from the same video.
        """
        if len(self._visibility_map) <= 1:
            return

        merged = [self._visibility_map[0]]

        for seg in self._visibility_map[1:]:
            last = merged[-1]

            # Check if can merge (same video, consecutive)
            if (seg.video_id == last.video_id and
                abs(seg.timeline_start - last.timeline_end) < 0.001):
                # Merge by extending the last segment
                merged[-1] = VisibilitySegment(
                    video_id=last.video_id,
                    video_name=last.video_name,
                    video_path=last.video_path,
                    timeline_start=last.timeline_start,
                    timeline_end=seg.timeline_end,
                    source_start=last.source_start,
                    source_end=seg.source_end
                )
            else:
                merged.append(seg)

        self._visibility_map = merged

    def _assign_video_indices(self):
        """
        Assign video indices for FFmpeg input ordering.

        Each unique video file gets an index based on order of first appearance.
        """
        seen_videos = {}
        index = 0

        for seg in self._visibility_map:
            if seg.video_id not in seen_videos:
                seen_videos[seg.video_id] = index
                index += 1
            seg.video_index = seen_videos[seg.video_id]

    def _map_segments(self):
        """
        Map voice-over segments to their final timeline positions.

        Handles segments that span across video boundaries by:
        1. Finding where the segment should be on the absolute timeline
        2. Checking if it crosses into a different video's visible range
        3. Splitting if necessary (for subtitle synchronization)

        Also handles generic/project-level segments (for multi-video projects).
        """
        self._segment_placements = []

        # Process video-specific segments
        for video in self.project.videos:
            layer = self._get_layer(video.id)
            if not layer:
                continue

            for segment in video.timeline.segments:
                # Segment times are video-relative (relative to the trimmed clip start)
                # NOT source positions! e.g., segment.start_time=5 means 5s into the playable clip
                seg_start_in_video = segment.start_time
                seg_end_in_video = segment.end_time

                # Convert video-relative to source position first
                # source_pos = source_start + video_relative_pos
                seg_source_start = layer.source_start + seg_start_in_video
                seg_source_end = layer.source_start + seg_end_in_video

                # Then convert source to absolute timeline
                timeline_start = layer.source_to_timeline(seg_source_start)
                timeline_end = layer.source_to_timeline(seg_source_end)

                # Handle segments that extend beyond this video's timeline range
                if timeline_start is None:
                    # Segment starts before this video's used portion
                    timeline_start = layer.timeline_start

                if timeline_end is None or seg_end_in_video > layer.source_end:
                    # Segment extends beyond this video
                    # Find where it continues
                    timeline_end = layer.timeline_end
                    continues_into_next = True
                else:
                    continues_into_next = False

                # Check if segment crosses into different video's visibility
                # (i.e., another video becomes visible before segment ends)
                crosses_visibility = self._check_crosses_visibility(
                    timeline_start, timeline_end, video.id
                )

                # Get the full segment timeline range (before clamping to first video)
                full_segment_end = timeline_end
                if continues_into_next or crosses_visibility:
                    # Calculate full segment end if it wasn't clamped
                    full_segment_end = timeline_start + (seg_end_in_video - seg_start_in_video)

                # FIX: Clamp first placement's timeline_end to visibility boundary
                # This prevents audio/subtitle overlap when segment crosses into another video
                first_placement_end = timeline_end
                if crosses_visibility:
                    vis_segments = self._get_visibility_segments_in_range(timeline_start, timeline_end)
                    if vis_segments:
                        # Clamp to first visibility segment's end
                        first_placement_end = min(timeline_end, vis_segments[0].timeline_end)
                        logger.debug(
                            f"Segment '{segment.name}' crosses visibility at {vis_segments[0].timeline_end:.2f}s, "
                            f"clamping first placement from {timeline_end:.2f}s to {first_placement_end:.2f}s"
                        )

                placement = SegmentPlacement(
                    segment_id=segment.id,
                    segment_name=segment.name,
                    original_video_id=video.id,
                    original_start=seg_start_in_video,
                    original_end=seg_end_in_video,
                    timeline_start=timeline_start,
                    timeline_end=first_placement_end,  # Use clamped value
                    audio_path=segment.audio_path,
                    subtitle_path=segment.subtitle_path,
                    is_continuation=False,
                    continues_into_next=continues_into_next or crosses_visibility,
                    audio_offset=0.0  # First placement starts at beginning
                )

                self._segment_placements.append(placement)

                logger.debug(
                    f"Segment '{segment.name}': "
                    f"video_local={seg_start_in_video:.2f}s-{seg_end_in_video:.2f}s -> "
                    f"timeline={timeline_start:.2f}s-{timeline_end:.2f}s"
                    f"{' [CROSSES VIDEOS]' if continues_into_next or crosses_visibility else ''}"
                )

                # Create continuation placements for cross-video segments
                if continues_into_next or crosses_visibility:
                    continuations = self._create_continuation_placements(
                        segment, placement,
                        timeline_start, full_segment_end
                    )
                    self._segment_placements.extend(continuations)
                    if continuations:
                        logger.debug(f"  Created {len(continuations)} continuation placement(s)")

        # Process generic/project-level segments (multi-video projects)
        # These segments have ABSOLUTE timeline positions, not video-relative
        if hasattr(self.project, 'generic_segments') and self.project.generic_segments:
            logger.info(f"Processing {len(self.project.generic_segments)} generic segment(s)")

            for segment in self.project.generic_segments:
                # Generic segments use absolute timeline positions directly
                timeline_start = segment.start_time
                timeline_end = segment.end_time

                # Clamp to total duration
                timeline_start = max(0, min(timeline_start, self._total_duration))
                timeline_end = max(timeline_start, min(timeline_end, self._total_duration))

                # Find which video is visible at this segment's start for reference
                visible_video = self.get_visible_video_at(timeline_start)
                original_video_id = visible_video.video_id if visible_video else (
                    self.project.videos[0].id if self.project.videos else None
                )

                # Check if segment crosses visibility boundaries
                crosses_visibility = False
                if original_video_id:
                    crosses_visibility = self._check_crosses_visibility(
                        timeline_start, timeline_end, original_video_id
                    )

                # For generic segments crossing visibility, clamp first placement to first visibility
                first_placement_end = timeline_end
                if crosses_visibility:
                    # Find first visibility segment and clamp to its end
                    vis_segments = self._get_visibility_segments_in_range(timeline_start, timeline_end)
                    if vis_segments:
                        first_placement_end = min(timeline_end, vis_segments[0].timeline_end)

                placement = SegmentPlacement(
                    segment_id=segment.id,
                    segment_name=segment.name,
                    original_video_id=original_video_id,
                    original_start=timeline_start,  # For generic, original = timeline
                    original_end=timeline_end,
                    timeline_start=timeline_start,
                    timeline_end=first_placement_end,
                    audio_path=segment.audio_path,
                    subtitle_path=segment.subtitle_path,
                    is_continuation=False,
                    continues_into_next=crosses_visibility,
                    audio_offset=0.0  # First placement starts at beginning
                )

                self._segment_placements.append(placement)

                logger.debug(
                    f"Generic Segment '{segment.name}': "
                    f"timeline={timeline_start:.2f}s-{timeline_end:.2f}s"
                    f"{' [CROSSES VIDEOS]' if crosses_visibility else ''}"
                )

                # Create continuation placements for cross-video segments
                if crosses_visibility:
                    continuations = self._create_continuation_placements(
                        segment, placement,
                        timeline_start, timeline_end
                    )
                    self._segment_placements.extend(continuations)
                    if continuations:
                        logger.debug(f"  Created {len(continuations)} continuation placement(s)")

        # Sort by timeline start
        self._segment_placements.sort(key=lambda p: p.timeline_start)

    def _check_crosses_visibility(
        self,
        start: float,
        end: float,
        video_id: str
    ) -> bool:
        """
        Check if a time range crosses into a different video's visibility.
        """
        for vis_seg in self._visibility_map:
            # Check if this visibility segment is within our time range
            if vis_seg.timeline_start < end and vis_seg.timeline_end > start:
                # There's overlap - is it a different video?
                if vis_seg.video_id != video_id:
                    return True
        return False

    def _get_visibility_segments_in_range(
        self,
        start: float,
        end: float
    ) -> List[VisibilitySegment]:
        """
        Get all visibility segments that overlap with a time range.
        Returns them sorted by timeline_start.
        """
        overlapping = []
        for vis_seg in self._visibility_map:
            if vis_seg.timeline_start < end and vis_seg.timeline_end > start:
                overlapping.append(vis_seg)
        return sorted(overlapping, key=lambda v: v.timeline_start)

    def _create_continuation_placements(
        self,
        segment,
        first_placement: SegmentPlacement,
        segment_timeline_start: float,
        segment_timeline_end: float
    ) -> List[SegmentPlacement]:
        """
        Create continuation placements for a segment that crosses visibility boundaries.

        When a segment spans multiple videos (crosses visibility boundaries),
        we need to split it into multiple placements:
        - First placement: from segment start to first visibility boundary
        - Continuation placements: for each subsequent visibility segment

        Each continuation has audio_offset set to skip already-played portion.
        """
        continuations = []

        # Get all visibility segments this segment spans
        vis_segments = self._get_visibility_segments_in_range(
            segment_timeline_start, segment_timeline_end
        )

        if len(vis_segments) <= 1:
            # No cross-video - no continuations needed
            return continuations

        # Track how much of the segment has been covered
        covered_duration = 0.0

        for i, vis_seg in enumerate(vis_segments):
            if i == 0:
                # First visibility segment - already handled by first_placement
                # Calculate how much of the segment plays in this visibility
                vis_overlap_start = max(segment_timeline_start, vis_seg.timeline_start)
                vis_overlap_end = min(segment_timeline_end, vis_seg.timeline_end)
                covered_duration = vis_overlap_end - vis_overlap_start
                continue

            # This is a continuation - segment continues into this visibility segment
            vis_overlap_start = max(segment_timeline_start, vis_seg.timeline_start)
            vis_overlap_end = min(segment_timeline_end, vis_seg.timeline_end)

            if vis_overlap_end <= vis_overlap_start:
                continue  # No actual overlap

            # Create continuation placement
            continuation = SegmentPlacement(
                segment_id=first_placement.segment_id,
                segment_name=first_placement.segment_name,
                original_video_id=vis_seg.video_id,  # Now in this video
                original_start=first_placement.original_start,
                original_end=first_placement.original_end,
                timeline_start=vis_overlap_start,
                timeline_end=vis_overlap_end,
                audio_path=first_placement.audio_path,
                subtitle_path=first_placement.subtitle_path,
                is_continuation=True,
                continues_into_next=(i < len(vis_segments) - 1),
                audio_offset=covered_duration  # Skip already-played portion
            )

            continuations.append(continuation)
            logger.debug(
                f"  -> Continuation in {vis_seg.video_id}: "
                f"{vis_overlap_start:.2f}s-{vis_overlap_end:.2f}s "
                f"(audio_offset={covered_duration:.2f}s)"
            )

            # Update covered duration for next continuation
            covered_duration += vis_overlap_end - vis_overlap_start

        return continuations

    def _map_bgm_tracks(self):
        """
        Map BGM tracks to their final positions.
        """
        self._bgm_placements = []

        if not hasattr(self.project, 'bgm_tracks'):
            return

        for track in self.project.bgm_tracks:
            if track.muted or not track.path:
                continue

            if not os.path.exists(track.path):
                logger.warning(f"BGM file not found: {track.path}")
                continue

            # Get audio duration
            source_duration = FFmpegUtils.get_media_duration(track.path)

            # Timeline position
            timeline_start = track.start_time
            timeline_end = track.end_time if track.end_time > 0 else self._total_duration

            # Clamp to timeline
            timeline_start = max(0, min(timeline_start, self._total_duration))
            timeline_end = max(timeline_start, min(timeline_end, self._total_duration))

            track_duration = timeline_end - timeline_start

            # Calculate looping
            needs_loop = False
            loop_count = 0
            if track.loop and source_duration and track_duration > source_duration:
                needs_loop = True
                loop_count = int((track_duration / source_duration) + 1)

            placement = BGMPlacement(
                track_id=track.id,
                track_name=track.name,
                track_path=track.path,
                timeline_start=timeline_start,
                timeline_end=timeline_end,
                volume=track.volume,
                fade_in=track.fade_in,
                fade_out=track.fade_out,
                loop=track.loop,
                muted=track.muted,
                source_duration=source_duration,
                needs_loop=needs_loop,
                loop_count=loop_count
            )

            self._bgm_placements.append(placement)

            logger.debug(
                f"BGM '{track.name}': "
                f"timeline={timeline_start:.2f}s-{timeline_end:.2f}s, "
                f"loop={needs_loop}"
            )

        # Sort by start time
        self._bgm_placements.sort(key=lambda p: p.timeline_start)

    def _get_layer(self, video_id: str) -> Optional[VideoLayer]:
        """Get layer by video ID."""
        for layer in self._layers:
            if layer.video_id == video_id:
                return layer
        return None

    def _log_summary(self):
        """Log a summary of the compositor state."""
        logger.info("=" * 60)
        logger.info("LAYER COMPOSITOR: Summary")
        logger.info("=" * 60)
        logger.info(f"Total Duration: {self._total_duration:.2f}s")
        logger.info(f"Video Layers: {len(self._layers)}")
        logger.info(f"Visibility Segments: {len(self._visibility_map)}")
        logger.info(f"Voice-over Placements: {len(self._segment_placements)}")
        logger.info(f"BGM Placements: {len(self._bgm_placements)}")
        logger.info("=" * 60)

    # ========== Public API ==========

    @property
    def total_duration(self) -> float:
        return self._total_duration

    @property
    def layers(self) -> List[VideoLayer]:
        return self._layers

    @property
    def visibility_map(self) -> List[VisibilitySegment]:
        return self._visibility_map

    @property
    def segment_placements(self) -> List[SegmentPlacement]:
        return self._segment_placements

    @property
    def bgm_placements(self) -> List[BGMPlacement]:
        return self._bgm_placements

    def get_unique_video_paths(self) -> List[str]:
        """Get unique video paths in order of first appearance."""
        seen = set()
        result = []
        for seg in self._visibility_map:
            if seg.video_path not in seen:
                seen.add(seg.video_path)
                result.append(seg.video_path)
        return result

    def get_visible_video_at(self, timeline_time: float) -> Optional[VisibilitySegment]:
        """Get the visible video at a specific timeline time."""
        for seg in self._visibility_map:
            if seg.timeline_start <= timeline_time < seg.timeline_end:
                return seg
        return None

    def get_segments_at(self, timeline_time: float) -> List[SegmentPlacement]:
        """Get all voice-over segments active at a specific time."""
        return [
            p for p in self._segment_placements
            if p.timeline_start <= timeline_time < p.timeline_end
        ]

    def get_bgm_at(self, timeline_time: float) -> List[BGMPlacement]:
        """Get all BGM tracks active at a specific time."""
        return [
            p for p in self._bgm_placements
            if p.timeline_start <= timeline_time < p.timeline_end
        ]

    def generate_ffmpeg_concat_filter(self) -> str:
        """
        Generate FFmpeg filter_complex for concatenating visible segments.

        This creates a filter that:
        1. Extracts the visible portion from each video
        2. Normalizes resolution/fps
        3. Concatenates in timeline order
        """
        if not self._visibility_map:
            return ""

        # Get common specs
        target_width = max(l.width for l in self._layers) if self._layers else 1920
        target_height = max(l.height for l in self._layers) if self._layers else 1080
        target_fps = max(l.fps for l in self._layers) if self._layers else 30.0

        filter_parts = []
        stream_labels = []

        for idx, vis_seg in enumerate(self._visibility_map):
            # Find the input index for this video
            input_idx = vis_seg.video_index

            # Trim to the exact source range
            trim_filter = (
                f"[{input_idx}:v]"
                f"trim=start={vis_seg.source_start:.3f}:end={vis_seg.source_end:.3f},"
                f"setpts=PTS-STARTPTS,"
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fps={target_fps},"
                f"setsar=1"
                f"[v{idx}]"
            )
            filter_parts.append(trim_filter)
            stream_labels.append(f"[v{idx}]")

            # Audio trim (if video has audio)
            layer = self._get_layer(vis_seg.video_id)
            if layer and layer.has_audio:
                audio_filter = (
                    f"[{input_idx}:a]"
                    f"atrim=start={vis_seg.source_start:.3f}:end={vis_seg.source_end:.3f},"
                    f"asetpts=PTS-STARTPTS"
                    f"[a{idx}]"
                )
                filter_parts.append(audio_filter)
            else:
                # Generate silent audio
                duration = vis_seg.source_end - vis_seg.source_start
                audio_filter = f"aevalsrc=0:d={duration:.3f}:s=44100:c=stereo[a{idx}]"
                filter_parts.append(audio_filter)

        # Build concat filter
        n = len(self._visibility_map)
        video_inputs = ''.join(f"[v{i}]" for i in range(n))
        audio_inputs = ''.join(f"[a{i}]" for i in range(n))

        concat_filter = f"{video_inputs}{audio_inputs}concat=n={n}:v=1:a=1[outv][outa]"
        filter_parts.append(concat_filter)

        return ';'.join(filter_parts)

    def get_debug_info(self) -> str:
        """Get detailed debug information."""
        lines = [
            "=" * 70,
            "LAYER COMPOSITOR DEBUG INFO",
            "=" * 70,
            f"Total Duration: {self._total_duration:.2f}s",
            "",
            "VIDEO LAYERS (sorted by stack priority):",
            "-" * 50,
        ]

        for layer in self._layers:
            lines.append(
                f"  [{layer.order}] {layer.video_name}:"
            )
            lines.append(
                f"      Timeline: {layer.timeline_start:.2f}s - {layer.timeline_end:.2f}s"
            )
            lines.append(
                f"      Source: {layer.source_start:.2f}s - {layer.source_end:.2f}s "
                f"(of {layer.source_duration:.2f}s)"
            )
            lines.append(
                f"      Has Audio: {'Yes' if layer.has_audio else 'No'}"
            )

        lines.extend([
            "",
            "VISIBILITY MAP (what actually shows in output):",
            "-" * 50,
        ])

        for seg in self._visibility_map:
            lines.append(
                f"  {seg.timeline_start:.2f}s - {seg.timeline_end:.2f}s: "
                f"{seg.video_name}"
            )
            lines.append(
                f"      Source: {seg.source_start:.2f}s - {seg.source_end:.2f}s"
            )

        if self._segment_placements:
            lines.extend([
                "",
                "SEGMENT PLACEMENTS:",
                "-" * 50,
            ])

            for p in self._segment_placements:
                cross = " [CROSS-VIDEO]" if p.continues_into_next else ""
                lines.append(
                    f"  {p.segment_name}: "
                    f"{p.timeline_start:.2f}s - {p.timeline_end:.2f}s{cross}"
                )

        if self._bgm_placements:
            lines.extend([
                "",
                "BGM PLACEMENTS:",
                "-" * 50,
            ])

            for p in self._bgm_placements:
                lines.append(
                    f"  {p.track_name}: "
                    f"{p.timeline_start:.2f}s - {p.timeline_end:.2f}s "
                    f"(vol: {p.volume}%)"
                )

        lines.append("=" * 70)

        return "\n".join(lines)
