#!/usr/bin/env python3
"""
Comprehensive Timeline Calculation Tests

This test suite validates ALL timeline-related calculations in the video editor:
- Video positioning (timeline_start, timeline_end, source_start, source_end)
- Segment timing (start_time, end_time, audio_offset)
- BGM track timing (start_time, end_time, audio_offset, fade, loop)
- All combinations and edge cases

Designed by a professional video editor timeline tester with experience in
Adobe Premiere Pro and After Effects timeline calculations.
"""

import pytest
import math
import sys
import os
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Optional, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.segment import Segment
from models.bgm_track import BGMTrack

# ============================================================================
# TEST CONFIGURATION AND HELPERS
# ============================================================================

EPSILON = 0.001  # Tolerance for floating point comparisons

def assert_close(actual, expected, msg=""):
    """Assert two values are close within EPSILON tolerance"""
    assert abs(actual - expected) < EPSILON, f"{msg}: Expected {expected}, got {actual}"


# ============================================================================
# MOCK CLASSES FOR TESTING WITHOUT FFMPEG
# ============================================================================

@dataclass
class MockTimeline:
    """Mock Timeline that doesn't require FFmpeg"""
    video_path: str = "/mock/video.mp4"
    video_id: Optional[str] = None
    video_duration: float = 60.0
    video_info: dict = field(default_factory=lambda: {
        'width': 1920, 'height': 1080, 'fps': 30.0, 'codec': 'h264'
    })
    segments: List = field(default_factory=list)

    def to_dict(self):
        return {
            "video_path": self.video_path,
            "video_id": self.video_id,
            "video_duration": self.video_duration,
            "video_info": self.video_info,
            "segments": [s.to_dict() for s in self.segments]
        }


@dataclass
class MockVideo:
    """
    Mock Video class that mimics the real Video model calculations
    without requiring actual video files or FFmpeg.
    """
    id: str
    name: str
    path: str
    order: int = 1

    # Video metadata
    duration: Optional[float] = None
    width: Optional[int] = 1920
    height: Optional[int] = 1080
    fps: Optional[float] = 30.0
    codec: Optional[str] = 'h264'

    # Timeline position
    timeline_start: Optional[float] = None
    timeline_end: Optional[float] = None

    # Source trimming
    source_start: float = 0.0
    source_end: Optional[float] = None

    def get_effective_duration(self) -> float:
        """
        Get the effective duration after source trimming.
        This is the actual playable length of the video clip.
        """
        end = self.source_end if self.source_end is not None else (self.duration or 0)
        return max(0, end - self.source_start)


# ============================================================================
# SECTION 1: VIDEO MODEL CALCULATIONS
# ============================================================================

class TestVideoEffectiveDuration:
    """Tests for Video.get_effective_duration() calculation"""

    def test_full_video_no_trim(self):
        """Full video without any trimming"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            source_start=0.0,
            source_end=None  # None means use full duration
        )
        # Expected: source_end (or duration if None) - source_start = 60 - 0 = 60
        assert_close(video.get_effective_duration(), 60.0, "Full video duration")

    def test_trim_from_start(self):
        """Video trimmed from start only"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            source_start=10.0,
            source_end=None  # Use to end of video
        )
        # Expected: 60 - 10 = 50
        assert_close(video.get_effective_duration(), 50.0, "Trim from start")

    def test_trim_from_end(self):
        """Video trimmed from end only"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            source_start=0.0,
            source_end=45.0
        )
        # Expected: 45 - 0 = 45
        assert_close(video.get_effective_duration(), 45.0, "Trim from end")

    def test_trim_both_ends(self):
        """Video trimmed from both start and end"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            source_start=10.0,
            source_end=50.0
        )
        # Expected: 50 - 10 = 40
        assert_close(video.get_effective_duration(), 40.0, "Trim both ends")

    def test_minimal_trim(self):
        """Extremely small trim values"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            source_start=0.001,
            source_end=59.999
        )
        # Expected: 59.999 - 0.001 = 59.998
        assert_close(video.get_effective_duration(), 59.998, "Minimal trim")

    def test_source_end_equals_duration(self):
        """source_end explicitly set to full duration"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            source_start=0.0,
            source_end=60.0  # Explicit full duration
        )
        # Expected: 60 - 0 = 60
        assert_close(video.get_effective_duration(), 60.0, "source_end equals duration")

    def test_zero_duration_edge_case(self):
        """Edge case: video with zero effective duration"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            source_start=30.0,
            source_end=30.0  # Same values
        )
        # Expected: max(0, 30 - 30) = 0
        assert_close(video.get_effective_duration(), 0.0, "Zero effective duration")

    def test_no_duration_metadata(self):
        """Video with no duration metadata (None)"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=None,  # Unknown duration
            source_start=0.0,
            source_end=None
        )
        # Expected: When duration is None, use 0 as fallback
        # end = source_end if source_end is not None else (duration or 0) = 0
        # result = max(0, 0 - 0) = 0
        assert_close(video.get_effective_duration(), 0.0, "No duration metadata")


class TestVideoTimelinePositioning:
    """Tests for video timeline positioning logic"""

    def test_sequential_positioning_single(self):
        """Single video starts at 0"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            timeline_start=0.0,
            timeline_end=60.0
        )
        assert_close(video.timeline_start, 0.0)
        assert_close(video.timeline_end, 60.0)

    def test_sequential_positioning_multiple(self):
        """Multiple videos positioned sequentially"""
        videos = [
            MockVideo(id="v1", name="video1", path="/v1.mp4", duration=30.0,
                  timeline_start=0.0, timeline_end=30.0, order=1),
            MockVideo(id="v2", name="video2", path="/v2.mp4", duration=45.0,
                  timeline_start=30.0, timeline_end=75.0, order=2),
            MockVideo(id="v3", name="video3", path="/v3.mp4", duration=20.0,
                  timeline_start=75.0, timeline_end=95.0, order=3)
        ]

        # Video 1: 0 to 30
        assert_close(videos[0].timeline_start, 0.0)
        assert_close(videos[0].timeline_end, 30.0)

        # Video 2: 30 to 75
        assert_close(videos[1].timeline_start, 30.0)
        assert_close(videos[1].timeline_end, 75.0)

        # Video 3: 75 to 95
        assert_close(videos[2].timeline_start, 75.0)
        assert_close(videos[2].timeline_end, 95.0)

    def test_trimmed_video_timeline_duration(self):
        """Trimmed video has shorter timeline duration"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            timeline_start=0.0,
            timeline_end=40.0,  # Only 40s on timeline
            source_start=10.0,  # Starting from 10s in source
            source_end=50.0     # Ending at 50s in source
        )

        timeline_duration = video.timeline_end - video.timeline_start
        source_duration = video.source_end - video.source_start

        # Timeline duration should match source trim duration
        assert_close(timeline_duration, 40.0)
        assert_close(source_duration, 40.0)
        assert_close(timeline_duration, source_duration, "Timeline matches source trim")

    def test_overlapping_videos(self):
        """Videos with overlapping timeline positions (layered)"""
        videos = [
            MockVideo(id="v1", name="background", path="/bg.mp4", duration=100.0,
                  timeline_start=0.0, timeline_end=100.0, order=2),  # Lower layer
            MockVideo(id="v2", name="overlay", path="/overlay.mp4", duration=20.0,
                  timeline_start=40.0, timeline_end=60.0, order=1)   # Upper layer
        ]

        # Test overlap detection
        v1_start, v1_end = videos[0].timeline_start, videos[0].timeline_end
        v2_start, v2_end = videos[1].timeline_start, videos[1].timeline_end

        # Check if v2 overlaps v1
        overlaps = not (v2_end <= v1_start or v1_end <= v2_start)
        assert overlaps, "Videos should overlap"

        # Overlap range
        overlap_start = max(v1_start, v2_start)
        overlap_end = min(v1_end, v2_end)
        overlap_duration = overlap_end - overlap_start

        assert_close(overlap_start, 40.0)
        assert_close(overlap_end, 60.0)
        assert_close(overlap_duration, 20.0)


class TestVideoGapDetection:
    """Tests for detecting gaps between videos"""

    def test_no_gap_sequential(self):
        """No gap when videos are sequential"""
        videos = [
            MockVideo(id="v1", name="v1", path="/v1.mp4", duration=30.0,
                  timeline_start=0.0, timeline_end=30.0),
            MockVideo(id="v2", name="v2", path="/v2.mp4", duration=30.0,
                  timeline_start=30.0, timeline_end=60.0)
        ]

        gap = videos[1].timeline_start - videos[0].timeline_end
        assert_close(gap, 0.0, "No gap between sequential videos")

    def test_gap_between_videos(self):
        """Gap detected between non-adjacent videos"""
        videos = [
            MockVideo(id="v1", name="v1", path="/v1.mp4", duration=30.0,
                  timeline_start=0.0, timeline_end=30.0),
            MockVideo(id="v2", name="v2", path="/v2.mp4", duration=30.0,
                  timeline_start=50.0, timeline_end=80.0)  # 20s gap
        ]

        gap = videos[1].timeline_start - videos[0].timeline_end
        assert_close(gap, 20.0, "20 second gap between videos")

    def test_gap_at_start(self):
        """Gap at the beginning (video doesn't start at 0)"""
        video = MockVideo(
            id="v1", name="v1", path="/v1.mp4", duration=30.0,
            timeline_start=10.0, timeline_end=40.0  # Starts at 10s
        )

        gap_at_start = video.timeline_start - 0.0
        assert_close(gap_at_start, 10.0, "10 second gap at start")


# ============================================================================
# SECTION 2: SEGMENT CALCULATIONS
# ============================================================================

class TestSegmentDuration:
    """Tests for Segment duration calculations"""

    def test_basic_segment_duration(self):
        """Basic segment duration calculation"""
        segment = Segment(
            id="s1", video_id="v1", name="seg1",
            start_time=0.0, end_time=10.0,
            text="Test", language="en"
        )
        assert_close(segment.duration, 10.0, "Basic duration")

    def test_segment_at_video_middle(self):
        """Segment in the middle of a video"""
        segment = Segment(
            id="s1", video_id="v1", name="seg1",
            start_time=30.0, end_time=45.0,
            text="Test", language="en"
        )
        assert_close(segment.duration, 15.0)
        assert_close(segment.start_time, 30.0)
        assert_close(segment.end_time, 45.0)

    def test_minimal_segment(self):
        """Minimal duration segment (1 second)"""
        segment = Segment(
            id="s1", video_id="v1", name="seg1",
            start_time=10.0, end_time=11.0,
            text="Test", language="en"
        )
        assert_close(segment.duration, 1.0, "Minimal 1 second segment")

    def test_subsecond_precision(self):
        """Segment with subsecond precision"""
        segment = Segment(
            id="s1", video_id="v1", name="seg1",
            start_time=10.123, end_time=15.456,
            text="Test", language="en"
        )
        assert_close(segment.duration, 5.333, "Subsecond precision")


class TestSegmentAudioOffset:
    """Tests for segment audio_offset calculations"""

    def test_no_audio_offset(self):
        """Segment with no audio offset (default)"""
        segment = Segment(
            id="s1", video_id="v1", name="seg1",
            start_time=0.0, end_time=10.0,
            audio_offset=0.0,
            text="Test", language="en"
        )
        assert_close(segment.audio_offset, 0.0)

    def test_trimmed_audio_start(self):
        """Segment with trimmed audio start"""
        segment = Segment(
            id="s1", video_id="v1", name="seg1",
            start_time=0.0, end_time=5.0,
            audio_offset=2.0,  # Skip first 2 seconds of audio
            text="Test", language="en"
        )
        # If audio is 7 seconds total and we play from offset 2.0,
        # we get 5 seconds of audio (2.0 to 7.0)
        audio_duration = 7.0
        playable_audio = audio_duration - segment.audio_offset
        assert_close(playable_audio, 5.0, "Playable audio after offset")

    def test_audio_offset_with_resize(self):
        """Simulating segment resize from start (increases audio_offset)"""
        # Original segment: 0-10, audio_offset=0
        # After resizing start to 3: segment becomes 3-10, audio_offset=3
        original_start = 0.0
        original_offset = 0.0
        new_start = 3.0

        start_delta = new_start - original_start
        new_offset = original_offset + start_delta

        assert_close(new_offset, 3.0, "Audio offset increases with start resize")


class TestSegmentToAbsoluteTimeline:
    """Tests for converting segment times to absolute timeline"""

    def test_segment_on_first_video(self):
        """Segment on first video (no offset)"""
        video_timeline_start = 0.0
        segment_start = 5.0
        segment_end = 15.0

        absolute_start = video_timeline_start + segment_start
        absolute_end = video_timeline_start + segment_end

        assert_close(absolute_start, 5.0)
        assert_close(absolute_end, 15.0)

    def test_segment_on_second_video(self):
        """Segment on second video (with offset)"""
        video1_duration = 30.0
        video2_timeline_start = 30.0  # Starts after video 1
        segment_start = 5.0  # Local to video 2
        segment_end = 15.0

        absolute_start = video2_timeline_start + segment_start
        absolute_end = video2_timeline_start + segment_end

        assert_close(absolute_start, 35.0)  # 30 + 5
        assert_close(absolute_end, 45.0)    # 30 + 15

    def test_segment_spanning_trimmed_video(self):
        """Segment on a trimmed video"""
        # Video: source 10-50 (40s duration), timeline 0-40
        video_timeline_start = 0.0
        video_source_start = 10.0
        segment_local_start = 5.0   # Local to video
        segment_local_end = 25.0

        # Absolute position
        absolute_start = video_timeline_start + segment_local_start
        absolute_end = video_timeline_start + segment_local_end

        # Corresponding source position
        source_position = video_source_start + segment_local_start

        assert_close(absolute_start, 5.0)
        assert_close(absolute_end, 25.0)
        assert_close(source_position, 15.0, "Source position = source_start + local")


class TestSegmentOverlapDetection:
    """Tests for detecting overlapping segments"""

    def test_non_overlapping_sequential(self):
        """Non-overlapping sequential segments"""
        segments = [
            Segment(id="s1", video_id="v1", name="s1", start_time=0.0, end_time=10.0, text="", language="en"),
            Segment(id="s2", video_id="v1", name="s2", start_time=10.0, end_time=20.0, text="", language="en"),
        ]

        # Check overlap: not (s1_end <= s2_start or s2_end <= s1_start)
        s1, s2 = segments[0], segments[1]
        overlaps = not (s1.end_time <= s2.start_time or s2.end_time <= s1.start_time)
        assert not overlaps, "Sequential segments should not overlap"

    def test_overlapping_segments(self):
        """Overlapping segments detected"""
        segments = [
            Segment(id="s1", video_id="v1", name="s1", start_time=0.0, end_time=15.0, text="", language="en"),
            Segment(id="s2", video_id="v1", name="s2", start_time=10.0, end_time=25.0, text="", language="en"),
        ]

        s1, s2 = segments[0], segments[1]
        overlaps = not (s1.end_time <= s2.start_time or s2.end_time <= s1.start_time)
        assert overlaps, "Segments should overlap"

        # Overlap range
        overlap_start = max(s1.start_time, s2.start_time)
        overlap_end = min(s1.end_time, s2.end_time)
        overlap_duration = overlap_end - overlap_start

        assert_close(overlap_duration, 5.0, "5 seconds overlap")

    def test_fully_contained_segment(self):
        """One segment fully contains another"""
        outer = Segment(id="s1", video_id="v1", name="outer", start_time=0.0, end_time=30.0, text="", language="en")
        inner = Segment(id="s2", video_id="v1", name="inner", start_time=10.0, end_time=20.0, text="", language="en")

        # Inner is fully within outer
        contained = (inner.start_time >= outer.start_time and inner.end_time <= outer.end_time)
        assert contained, "Inner segment fully contained"

        overlaps = not (outer.end_time <= inner.start_time or inner.end_time <= outer.start_time)
        assert overlaps, "Contained segments overlap"


# ============================================================================
# SECTION 3: BGM TRACK CALCULATIONS
# ============================================================================

class TestBGMEffectiveEndTime:
    """Tests for BGMTrack.get_effective_end_time()"""

    def test_explicit_end_time(self):
        """BGM with explicit end time"""
        track = BGMTrack(
            id="bgm1", name="music", path="/music.mp3",
            start_time=0.0, end_time=30.0
        )
        video_duration = 60.0

        effective_end = track.get_effective_end_time(video_duration)
        assert_close(effective_end, 30.0, "Use explicit end_time")

    def test_end_time_zero_uses_video_duration(self):
        """end_time=0 means play until video ends"""
        track = BGMTrack(
            id="bgm1", name="music", path="/music.mp3",
            start_time=10.0, end_time=0.0  # 0 = play until end
        )
        video_duration = 60.0

        effective_end = track.get_effective_end_time(video_duration)
        assert_close(effective_end, 60.0, "Use video duration when end_time=0")


class TestBGMTimeRangeDuration:
    """Tests for BGMTrack.get_time_range_duration()"""

    def test_explicit_range(self):
        """BGM with explicit start and end"""
        track = BGMTrack(
            id="bgm1", name="music", path="/music.mp3",
            start_time=10.0, end_time=40.0
        )
        video_duration = 60.0

        duration = track.get_time_range_duration(video_duration)
        assert_close(duration, 30.0, "40 - 10 = 30")

    def test_full_video_range(self):
        """BGM covering full video"""
        track = BGMTrack(
            id="bgm1", name="music", path="/music.mp3",
            start_time=0.0, end_time=0.0  # Full video
        )
        video_duration = 60.0

        duration = track.get_time_range_duration(video_duration)
        assert_close(duration, 60.0, "Full video duration")

    def test_partial_coverage(self):
        """BGM covering only part of video"""
        track = BGMTrack(
            id="bgm1", name="music", path="/music.mp3",
            start_time=20.0, end_time=0.0  # From 20s to end
        )
        video_duration = 60.0

        duration = track.get_time_range_duration(video_duration)
        assert_close(duration, 40.0, "60 - 20 = 40")


class TestBGMOverlapDetection:
    """Tests for BGMTrack.overlaps_with()"""

    def test_non_overlapping_sequential(self):
        """Non-overlapping sequential BGM tracks"""
        track1 = BGMTrack(id="bgm1", name="m1", path="/m1.mp3", start_time=0.0, end_time=30.0)
        track2 = BGMTrack(id="bgm2", name="m2", path="/m2.mp3", start_time=30.0, end_time=60.0)
        video_duration = 60.0

        overlaps = track1.overlaps_with(track2, video_duration)
        assert not overlaps, "Sequential tracks don't overlap"

    def test_overlapping_tracks(self):
        """Overlapping BGM tracks"""
        track1 = BGMTrack(id="bgm1", name="m1", path="/m1.mp3", start_time=0.0, end_time=40.0)
        track2 = BGMTrack(id="bgm2", name="m2", path="/m2.mp3", start_time=30.0, end_time=60.0)
        video_duration = 60.0

        overlaps = track1.overlaps_with(track2, video_duration)
        assert overlaps, "Tracks should overlap"

    def test_contained_track(self):
        """One track fully contains another"""
        outer = BGMTrack(id="bgm1", name="outer", path="/outer.mp3", start_time=0.0, end_time=60.0)
        inner = BGMTrack(id="bgm2", name="inner", path="/inner.mp3", start_time=20.0, end_time=40.0)
        video_duration = 60.0

        overlaps = outer.overlaps_with(inner, video_duration)
        assert overlaps, "Contained track overlaps"


class TestBGMVolumeCalculation:
    """Tests for BGMTrack.get_volume_db_reduction()"""

    def test_full_volume(self):
        """100% volume has base reduction only"""
        track = BGMTrack(id="bgm1", name="m1", path="/m1.mp3", volume=100)

        # Base reduction is 20dB
        # volume_adjustment = 20 * log10(100/100) = 20 * 0 = 0
        # Total = 20 + 0 = 20
        reduction = track.get_volume_db_reduction()
        assert_close(reduction, 20.0, "Base 20dB reduction at 100%")

    def test_half_volume(self):
        """50% volume adds ~6dB reduction"""
        track = BGMTrack(id="bgm1", name="m1", path="/m1.mp3", volume=50)

        # volume_adjustment = 20 * log10(100/50) = 20 * log10(2) ≈ 20 * 0.301 ≈ 6.02
        # Total ≈ 20 + 6.02 = 26.02
        reduction = track.get_volume_db_reduction()
        expected = 20.0 + 20 * math.log10(100/50)
        assert_close(reduction, expected, "50% volume reduction")

    def test_quarter_volume(self):
        """25% volume"""
        track = BGMTrack(id="bgm1", name="m1", path="/m1.mp3", volume=25)

        # volume_adjustment = 20 * log10(100/25) = 20 * log10(4) ≈ 20 * 0.602 ≈ 12.04
        # Total ≈ 20 + 12.04 = 32.04
        reduction = track.get_volume_db_reduction()
        expected = 20.0 + 20 * math.log10(100/25)
        assert_close(reduction, expected, "25% volume reduction")

    def test_muted_track(self):
        """Muted track returns infinity"""
        track = BGMTrack(id="bgm1", name="m1", path="/m1.mp3", volume=100, muted=True)

        reduction = track.get_volume_db_reduction()
        assert reduction == float('inf'), "Muted returns infinity"

    def test_zero_volume(self):
        """Zero volume returns infinity"""
        track = BGMTrack(id="bgm1", name="m1", path="/m1.mp3", volume=0)

        reduction = track.get_volume_db_reduction()
        assert reduction == float('inf'), "Zero volume returns infinity"


class TestBGMLoopCalculation:
    """Tests for BGM looping calculations"""

    def test_no_loop_needed(self):
        """Audio longer than timeline range - no loop"""
        audio_duration = 120.0  # 2 minute track
        track_duration = 60.0   # 1 minute needed

        needs_loop = track_duration > audio_duration
        assert not needs_loop, "No loop needed when audio is longer"

    def test_loop_needed(self):
        """Audio shorter than timeline range - loop needed"""
        audio_duration = 30.0   # 30 second track
        track_duration = 60.0   # 60 seconds needed

        needs_loop = track_duration > audio_duration
        loop_count = int((track_duration / audio_duration) + 1) if needs_loop else 1

        assert needs_loop, "Loop needed when audio is shorter"
        assert loop_count == 3, "Need 3 loops to cover 60s with 30s track (30+30+30 > 60)"

    def test_exact_multiple(self):
        """Audio is exact multiple of timeline range"""
        audio_duration = 30.0
        track_duration = 90.0  # Exactly 3x audio

        needs_loop = track_duration > audio_duration
        loop_count = int((track_duration / audio_duration) + 1)

        assert needs_loop
        assert loop_count == 4, "Need 4 loops for safety (3+1)"

    def test_with_audio_offset(self):
        """Looping with audio_offset applied"""
        audio_duration = 60.0
        audio_offset = 20.0     # Skip first 20 seconds
        track_duration = 100.0  # Need 100 seconds

        remaining_audio = audio_duration - audio_offset  # 40 seconds usable
        needs_loop = track_duration > remaining_audio
        loop_count = int((track_duration / remaining_audio) + 1) if needs_loop else 1

        assert needs_loop, "Loop needed with offset"
        assert loop_count == 3, "100/40 + 1 = 3.5, int() = 3"


class TestBGMFadeCalculations:
    """Tests for BGM fade in/out timing calculations"""

    def test_fade_in_at_start(self):
        """Fade in starts at 0"""
        track = BGMTrack(
            id="bgm1", name="m1", path="/m1.mp3",
            start_time=0.0, end_time=60.0,
            fade_in=3.0, fade_out=5.0
        )

        fade_in_start = 0.0
        fade_in_end = fade_in_start + track.fade_in

        assert_close(fade_in_start, 0.0)
        assert_close(fade_in_end, 3.0)

    def test_fade_out_timing(self):
        """Fade out ends at track end"""
        track = BGMTrack(
            id="bgm1", name="m1", path="/m1.mp3",
            start_time=0.0, end_time=60.0,
            fade_in=3.0, fade_out=5.0
        )
        video_duration = 60.0

        track_duration = track.get_time_range_duration(video_duration)
        fade_out_start = track_duration - track.fade_out
        fade_out_end = track_duration

        assert_close(fade_out_start, 55.0, "Fade out starts at 60 - 5 = 55")
        assert_close(fade_out_end, 60.0)

    def test_overlapping_fades(self):
        """Edge case: fade_in + fade_out > duration"""
        track = BGMTrack(
            id="bgm1", name="m1", path="/m1.mp3",
            start_time=0.0, end_time=5.0,
            fade_in=3.0, fade_out=4.0  # 7 seconds of fades in 5 second track
        )
        video_duration = 60.0

        track_duration = track.get_time_range_duration(video_duration)
        total_fade_time = track.fade_in + track.fade_out

        # Fades overlap when total > duration
        fades_overlap = total_fade_time > track_duration
        assert fades_overlap, "Fades should overlap in short track"


# ============================================================================
# SECTION 4: MULTI-VIDEO TIMELINE CALCULATIONS
# ============================================================================

class TestMultiVideoTimeline:
    """Tests for multi-video timeline calculations"""

    def test_cumulative_offset_calculation(self):
        """Calculate cumulative offsets for sequential videos"""
        videos = [
            {"id": "v1", "duration": 30.0},
            {"id": "v2", "duration": 45.0},
            {"id": "v3", "duration": 25.0},
        ]

        cumulative_offset = 0.0
        positions = []

        for video in videos:
            start = cumulative_offset
            end = cumulative_offset + video["duration"]
            positions.append({"id": video["id"], "start": start, "end": end})
            cumulative_offset += video["duration"]

        # Verify positions
        assert_close(positions[0]["start"], 0.0)
        assert_close(positions[0]["end"], 30.0)

        assert_close(positions[1]["start"], 30.0)
        assert_close(positions[1]["end"], 75.0)

        assert_close(positions[2]["start"], 75.0)
        assert_close(positions[2]["end"], 100.0)

        # Total duration
        assert_close(cumulative_offset, 100.0)

    def test_trimmed_video_cumulative_offset(self):
        """Cumulative offset with trimmed videos"""
        videos = [
            {"id": "v1", "source_start": 0.0, "source_end": 30.0},    # Full 30s
            {"id": "v2", "source_start": 10.0, "source_end": 40.0},  # Trimmed: 30s
            {"id": "v3", "source_start": 5.0, "source_end": 20.0},   # Trimmed: 15s
        ]

        cumulative_offset = 0.0
        positions = []

        for video in videos:
            effective_duration = video["source_end"] - video["source_start"]
            start = cumulative_offset
            end = cumulative_offset + effective_duration
            positions.append({
                "id": video["id"],
                "timeline_start": start,
                "timeline_end": end,
                "effective_duration": effective_duration
            })
            cumulative_offset += effective_duration

        # Video 1: 0-30
        assert_close(positions[0]["timeline_start"], 0.0)
        assert_close(positions[0]["timeline_end"], 30.0)

        # Video 2: 30-60 (30s trimmed)
        assert_close(positions[1]["timeline_start"], 30.0)
        assert_close(positions[1]["timeline_end"], 60.0)

        # Video 3: 60-75 (15s trimmed)
        assert_close(positions[2]["timeline_start"], 60.0)
        assert_close(positions[2]["timeline_end"], 75.0)

        # Total: 30 + 30 + 15 = 75
        assert_close(cumulative_offset, 75.0)


class TestTimeConversion:
    """Tests for absolute <-> local time conversion"""

    def test_absolute_to_local_first_video(self):
        """Convert absolute time to local time on first video"""
        video = {
            "timeline_start": 0.0,
            "source_start": 0.0,
        }

        absolute_time = 25.0
        local_time = absolute_time - video["timeline_start"] + video["source_start"]

        assert_close(local_time, 25.0, "First video: absolute = local")

    def test_absolute_to_local_second_video(self):
        """Convert absolute time to local time on second video"""
        video = {
            "timeline_start": 30.0,  # Starts at 30s on timeline
            "source_start": 0.0,
        }

        absolute_time = 45.0  # 15 seconds into video 2
        local_time = absolute_time - video["timeline_start"] + video["source_start"]

        assert_close(local_time, 15.0, "45 - 30 + 0 = 15")

    def test_absolute_to_local_trimmed_video(self):
        """Convert absolute time on trimmed video"""
        video = {
            "timeline_start": 30.0,
            "source_start": 10.0,  # Source trimmed from 10s
        }

        absolute_time = 45.0  # 15 seconds into video on timeline
        offset_in_video = absolute_time - video["timeline_start"]  # 15 seconds
        local_source_time = video["source_start"] + offset_in_video  # 10 + 15 = 25

        assert_close(local_source_time, 25.0, "Timeline 45s = source 25s")

    def test_local_to_absolute(self):
        """Convert local time to absolute time"""
        video = {
            "timeline_start": 30.0,
            "source_start": 10.0,
        }

        source_time = 25.0  # Position in source video
        offset_from_source_start = source_time - video["source_start"]  # 25 - 10 = 15
        absolute_time = video["timeline_start"] + offset_from_source_start  # 30 + 15 = 45

        assert_close(absolute_time, 45.0, "Source 25s = timeline 45s")


# ============================================================================
# SECTION 5: CROSS-VIDEO SEGMENT CALCULATIONS
# ============================================================================

class TestCrossVideoSegments:
    """Tests for segments that span multiple videos"""

    def test_detect_cross_video_segment(self):
        """Detect when segment extends beyond video boundary"""
        video = {
            "id": "v1",
            "timeline_start": 0.0,
            "timeline_end": 30.0,
            "duration": 30.0,
        }

        segment = {
            "video_id": "v1",
            "start_time": 25.0,  # Local to video
            "end_time": 35.0,    # Extends 5s beyond video
        }

        # Calculate overflow
        overflow = segment["end_time"] - video["duration"]
        extends_beyond = overflow > 0

        assert extends_beyond, "Segment extends beyond video"
        assert_close(overflow, 5.0, "5 seconds overflow")

    def test_continuation_segment_calculation(self):
        """Calculate continuation segment for next video"""
        video1 = {
            "id": "v1", "duration": 30.0,
            "timeline_start": 0.0, "timeline_end": 30.0
        }
        video2 = {
            "id": "v2", "duration": 45.0,
            "timeline_start": 30.0, "timeline_end": 75.0
        }

        original_segment = {
            "video_id": "v1",
            "start_time": 25.0,
            "end_time": 35.0,
            "audio_offset": 0.0,
        }

        # Original plays from 25s to 30s on video 1 (5 seconds)
        original_duration_in_v1 = video1["duration"] - original_segment["start_time"]  # 30 - 25 = 5

        # Continuation plays from 0s to 5s on video 2
        overflow = original_segment["end_time"] - video1["duration"]  # 35 - 30 = 5

        continuation = {
            "video_id": "v2",
            "start_time": 0.0,
            "end_time": overflow,
            "audio_offset": original_duration_in_v1,  # Skip the first 5s of audio
            "is_continuation": True,
        }

        assert_close(continuation["start_time"], 0.0)
        assert_close(continuation["end_time"], 5.0)
        assert_close(continuation["audio_offset"], 5.0, "Skip audio already played")

    def test_segment_audio_trim_for_continuation(self):
        """Calculate audio trimming for continuation segment"""
        # Original segment audio: 10 seconds total
        # Plays 5 seconds on video 1, then 5 seconds on video 2
        audio_duration = 10.0
        original_start = 25.0
        video1_end = 30.0

        # Audio already played
        audio_played = video1_end - original_start  # 5 seconds

        # For continuation, skip first 5 seconds
        continuation_audio_offset = audio_played
        continuation_duration = audio_duration - audio_played  # 5 seconds remaining

        assert_close(continuation_audio_offset, 5.0)
        assert_close(continuation_duration, 5.0)


# ============================================================================
# SECTION 6: FFmpeg DELAY CALCULATIONS
# ============================================================================

class TestFFmpegDelayCalculations:
    """Tests for FFmpeg adelay filter calculations"""

    def test_delay_at_start(self):
        """No delay for segment at start"""
        absolute_start = 0.0
        delay_ms = int(absolute_start * 1000)

        assert delay_ms == 0, "No delay at start"

    def test_delay_calculation(self):
        """Delay calculated from absolute position"""
        absolute_start = 25.5  # 25.5 seconds
        delay_ms = int(absolute_start * 1000)

        assert delay_ms == 25500, "25500ms delay"

    def test_delay_with_base_offset(self):
        """Delay with base offset (for video clip processing)"""
        segment_absolute_start = 45.0
        video_start_offset = 30.0  # Video 2 starts at 30s

        adjusted_time = max(0, segment_absolute_start - video_start_offset)
        delay_ms = int(adjusted_time * 1000)

        assert delay_ms == 15000, "15 seconds relative to video 2 start"

    def test_delay_stereo_format(self):
        """FFmpeg adelay format for stereo"""
        delay_ms = 5000
        adelay_filter = f"adelay={delay_ms}|{delay_ms}"

        assert adelay_filter == "adelay=5000|5000"


# ============================================================================
# SECTION 7: SUBTITLE TIMING CALCULATIONS
# ============================================================================

class TestSubtitleTimingAdjustment:
    """Tests for subtitle timing adjustments"""

    def test_subtitle_offset_calculation(self):
        """Calculate subtitle time offset"""
        # Clip starts at 30s in timeline
        clip_start = 30.0

        # Subtitle at 35s absolute should appear at 5s in clip
        subtitle_absolute_time = 35.0

        # Time offset to apply
        time_offset = -clip_start  # -30
        adjusted_time = subtitle_absolute_time + time_offset

        assert_close(adjusted_time, 5.0, "35 - 30 = 5")

    def test_subtitle_clamp_to_clip(self):
        """Clamp subtitle times to clip boundaries"""
        clip_start = 30.0
        clip_duration = 20.0
        time_offset = -clip_start

        # Subtitle that starts before clip (absolute 25s)
        sub_start = 25.0
        adjusted_start = max(0, sub_start + time_offset)
        assert_close(adjusted_start, 0.0, "Clamped to 0")

        # Subtitle that ends after clip (absolute 55s = 25s in clip, but clip is only 20s)
        sub_end = 55.0
        adjusted_end = min(clip_duration, sub_end + time_offset)
        assert_close(adjusted_end, 20.0, "Clamped to clip duration")

    def test_subtitle_outside_clip(self):
        """Detect subtitle completely outside visible range"""
        clip_start = 30.0
        clip_duration = 20.0
        clip_end = clip_start + clip_duration  # 50
        time_offset = -clip_start

        # Subtitle from 10s to 20s (before clip starts at 30s)
        sub_start, sub_end = 10.0, 20.0
        adjusted_start = sub_start + time_offset  # -20
        adjusted_end = sub_end + time_offset      # -10

        # Skip if completely outside [0, clip_duration]
        skip = adjusted_end <= 0 or adjusted_start >= clip_duration
        assert skip, "Subtitle completely before clip should be skipped"

        # Subtitle from 55s to 65s (after clip ends at 50s)
        sub_start2, sub_end2 = 55.0, 65.0
        adjusted_start2 = sub_start2 + time_offset  # 25
        adjusted_end2 = sub_end2 + time_offset      # 35

        skip2 = adjusted_end2 <= 0 or adjusted_start2 >= clip_duration
        assert skip2, "Subtitle completely after clip should be skipped"


# ============================================================================
# SECTION 8: COMPREHENSIVE SCENARIO TESTS
# ============================================================================

class TestScenario_SingleVideoSingleSegment:
    """Scenario: One video, one segment"""

    def test_basic_scenario(self):
        """Basic playback scenario"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            timeline_start=0.0, timeline_end=60.0,
            source_start=0.0, source_end=None
        )

        segment = Segment(
            id="s1", video_id="v1", name="narration",
            start_time=10.0, end_time=25.0,
            text="Hello world", language="en"
        )

        # Video effective duration
        assert_close(video.get_effective_duration(), 60.0)

        # Segment duration
        assert_close(segment.duration, 15.0)

        # Segment absolute times (video at 0)
        segment_absolute_start = video.timeline_start + segment.start_time
        segment_absolute_end = video.timeline_start + segment.end_time

        assert_close(segment_absolute_start, 10.0)
        assert_close(segment_absolute_end, 25.0)


class TestScenario_SingleVideoMultipleSegments:
    """Scenario: One video, multiple segments"""

    def test_sequential_segments(self):
        """Multiple sequential segments on one video"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=120.0,
            timeline_start=0.0, timeline_end=120.0
        )

        segments = [
            Segment(id="s1", video_id="v1", name="intro", start_time=0.0, end_time=15.0, text="", language="en"),
            Segment(id="s2", video_id="v1", name="main", start_time=15.0, end_time=90.0, text="", language="en"),
            Segment(id="s3", video_id="v1", name="outro", start_time=90.0, end_time=120.0, text="", language="en"),
        ]

        # Total coverage
        total_coverage = sum(s.duration for s in segments)
        assert_close(total_coverage, 120.0, "Segments cover full video")

        # No overlaps
        for i in range(len(segments) - 1):
            assert segments[i].end_time == segments[i+1].start_time, "No gaps or overlaps"


class TestScenario_MultipleVideosMultipleSegments:
    """Scenario: Multiple videos with segments on each"""

    def test_multi_video_segments(self):
        """Segments distributed across multiple videos"""
        videos = [
            MockVideo(id="v1", name="v1", path="/v1.mp4", duration=30.0,
                  timeline_start=0.0, timeline_end=30.0, order=1),
            MockVideo(id="v2", name="v2", path="/v2.mp4", duration=45.0,
                  timeline_start=30.0, timeline_end=75.0, order=2),
        ]

        segments = [
            # Video 1 segments
            Segment(id="s1", video_id="v1", name="v1_intro", start_time=0.0, end_time=15.0, text="", language="en"),
            Segment(id="s2", video_id="v1", name="v1_main", start_time=15.0, end_time=30.0, text="", language="en"),
            # Video 2 segments
            Segment(id="s3", video_id="v2", name="v2_intro", start_time=0.0, end_time=20.0, text="", language="en"),
            Segment(id="s4", video_id="v2", name="v2_outro", start_time=35.0, end_time=45.0, text="", language="en"),
        ]

        # Calculate absolute positions
        for seg in segments:
            video = next(v for v in videos if v.id == seg.video_id)
            absolute_start = video.timeline_start + seg.start_time
            absolute_end = video.timeline_start + seg.end_time

            if seg.id == "s3":
                assert_close(absolute_start, 30.0, "s3 starts at 30 (video 2 offset)")
                assert_close(absolute_end, 50.0, "s3 ends at 50")
            elif seg.id == "s4":
                assert_close(absolute_start, 65.0, "s4 starts at 65")
                assert_close(absolute_end, 75.0, "s4 ends at 75")


class TestScenario_TrimmedVideosWithSegments:
    """Scenario: Trimmed videos with segments"""

    def test_trimmed_video_segment_positioning(self):
        """Segment on a trimmed video"""
        # Video 1: Source 10s-50s (40s effective), Timeline 0-40
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=60.0,
            timeline_start=0.0, timeline_end=40.0,
            source_start=10.0, source_end=50.0
        )

        # Segment at local time 5-15 (in trimmed region)
        segment = Segment(
            id="s1", video_id="v1", name="seg",
            start_time=5.0, end_time=15.0,  # Local to trimmed video
            text="", language="en"
        )

        # Absolute timeline position
        absolute_start = video.timeline_start + segment.start_time  # 0 + 5 = 5
        absolute_end = video.timeline_start + segment.end_time      # 0 + 15 = 15

        # Source file position (for FFmpeg seek)
        source_start_position = video.source_start + segment.start_time  # 10 + 5 = 15
        source_end_position = video.source_start + segment.end_time      # 10 + 15 = 25

        assert_close(absolute_start, 5.0)
        assert_close(absolute_end, 15.0)
        assert_close(source_start_position, 15.0, "Source position offset by trim start")
        assert_close(source_end_position, 25.0)


class TestScenario_MultipleBGMTracks:
    """Scenario: Multiple BGM tracks with different settings"""

    def test_multiple_bgm_mixing(self):
        """Multiple BGM tracks with overlapping and non-overlapping regions"""
        video_duration = 120.0

        tracks = [
            BGMTrack(id="bgm1", name="ambient", path="/ambient.mp3",
                    start_time=0.0, end_time=120.0, volume=30, fade_in=5.0, fade_out=10.0),
            BGMTrack(id="bgm2", name="action", path="/action.mp3",
                    start_time=30.0, end_time=90.0, volume=70, fade_in=2.0, fade_out=3.0),
        ]

        # Track 1: Full video, low volume
        assert_close(tracks[0].get_time_range_duration(video_duration), 120.0)

        # Track 2: Middle section only
        assert_close(tracks[1].get_time_range_duration(video_duration), 60.0)

        # Overlap detection
        assert tracks[0].overlaps_with(tracks[1], video_duration), "Tracks should overlap"

        # Volume difference
        vol1_db = tracks[0].get_volume_db_reduction()
        vol2_db = tracks[1].get_volume_db_reduction()

        # Track 1 (30%) should have higher dB reduction than Track 2 (70%)
        assert vol1_db > vol2_db, "Lower volume = higher dB reduction"


class TestScenario_SegmentsWithBGM:
    """Scenario: Segments and BGM tracks together"""

    def test_segment_bgm_timing_coordination(self):
        """Verify segment and BGM timing align correctly"""
        video_duration = 60.0

        segments = [
            Segment(id="s1", video_id="v1", name="seg1",
                   start_time=10.0, end_time=25.0, text="", language="en"),
        ]

        bgm = BGMTrack(
            id="bgm1", name="music", path="/music.mp3",
            start_time=5.0, end_time=30.0,  # Overlaps with segment
            volume=50, fade_in=2.0, fade_out=3.0
        )

        # BGM starts before segment, ends after segment
        bgm_start = bgm.start_time
        bgm_end = bgm.get_effective_end_time(video_duration)

        # Segment timing
        seg_start = segments[0].start_time
        seg_end = segments[0].end_time

        # Check overlap
        bgm_plays_during_segment = not (bgm_end <= seg_start or bgm_start >= seg_end)
        assert bgm_plays_during_segment, "BGM should play during segment"

        # Overlap region
        overlap_start = max(bgm_start, seg_start)
        overlap_end = min(bgm_end, seg_end)

        assert_close(overlap_start, 10.0)
        assert_close(overlap_end, 25.0)


class TestScenario_CrossVideoSegmentWithBGM:
    """Scenario: Cross-video segment with BGM"""

    def test_complex_cross_video_scenario(self):
        """Cross-video segment with continuous BGM"""
        videos = [
            {"id": "v1", "duration": 30.0, "timeline_start": 0.0, "timeline_end": 30.0},
            {"id": "v2", "duration": 30.0, "timeline_start": 30.0, "timeline_end": 60.0},
        ]

        # Segment that crosses from v1 to v2
        segment = {
            "video_id": "v1",
            "start_time": 25.0,  # Starts 5s before v1 ends
            "end_time": 35.0,    # Extends 5s into v2
            "audio_offset": 0.0,
        }

        # BGM plays through entire timeline
        bgm = BGMTrack(
            id="bgm1", name="music", path="/music.mp3",
            start_time=0.0, end_time=0.0,  # Full timeline
        )

        total_duration = videos[-1]["timeline_end"]  # 60

        # Segment absolute times
        v1_start = videos[0]["timeline_start"]
        segment_absolute_start = v1_start + segment["start_time"]  # 0 + 25 = 25
        segment_absolute_end = v1_start + segment["end_time"]      # 0 + 35 = 35

        # Part 1 on v1: 25-30 (5 seconds)
        # Part 2 on v2: 30-35 (5 seconds)
        part1_duration = videos[0]["timeline_end"] - segment_absolute_start  # 30 - 25 = 5
        part2_duration = segment_absolute_end - videos[1]["timeline_start"]   # 35 - 30 = 5

        assert_close(part1_duration, 5.0)
        assert_close(part2_duration, 5.0)

        # BGM covers entire segment
        bgm_range = bgm.get_time_range_duration(total_duration)
        assert_close(bgm_range, 60.0, "BGM covers full timeline")


# ============================================================================
# SECTION 9: EDGE CASES AND ERROR CONDITIONS
# ============================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions"""

    def test_zero_duration_video(self):
        """Handle video with zero duration"""
        video = MockVideo(
            id="v1", name="test", path="/test.mp4",
            duration=0.0,
            timeline_start=0.0, timeline_end=0.0
        )

        assert_close(video.get_effective_duration(), 0.0)
        assert_close(video.timeline_end - video.timeline_start, 0.0)

    def test_very_short_segment(self):
        """Very short segment (0.1 seconds)"""
        segment = Segment(
            id="s1", video_id="v1", name="flash",
            start_time=10.0, end_time=10.1,
            text="!", language="en"
        )

        assert_close(segment.duration, 0.1)

    def test_very_long_video(self):
        """Very long video (3 hours)"""
        duration = 3 * 60 * 60  # 3 hours in seconds
        video = MockVideo(
            id="v1", name="movie", path="/movie.mp4",
            duration=float(duration),
            timeline_start=0.0, timeline_end=float(duration)
        )

        assert_close(video.get_effective_duration(), 10800.0)

    def test_precision_at_millisecond_level(self):
        """Precision at millisecond level"""
        segment = Segment(
            id="s1", video_id="v1", name="precise",
            start_time=10.001, end_time=10.999,
            text="", language="en"
        )

        # Duration should be 0.998
        assert_close(segment.duration, 0.998)

    def test_frame_boundary_alignment(self):
        """Timing at typical frame boundaries (30fps)"""
        fps = 30.0
        frame_duration = 1.0 / fps  # ~0.0333

        # 5 frames
        segment_duration = 5 * frame_duration

        segment = Segment(
            id="s1", video_id="v1", name="frames",
            start_time=0.0, end_time=segment_duration,
            text="", language="en"
        )

        assert_close(segment.duration, 5 / 30.0)  # ~0.1667


class TestNegativeAndInvalidInputs:
    """Tests for handling invalid inputs (defensive programming)"""

    def test_negative_times_clamped(self):
        """Negative times should be clamped to 0"""
        # In real implementation, validation should prevent this
        # But calculations should handle it gracefully
        negative_start = -5.0
        clamped_start = max(0, negative_start)

        assert clamped_start == 0.0

    def test_end_before_start(self):
        """End time before start time (invalid but handle gracefully)"""
        start_time = 20.0
        end_time = 10.0  # Invalid

        # Duration would be negative - should return 0 or raise error
        duration = max(0, end_time - start_time)

        assert duration == 0.0, "Negative duration clamped to 0"


# ============================================================================
# SECTION 10: VOLUME AND AUDIO MIXING CALCULATIONS
# ============================================================================

class TestAudioMixingCalculations:
    """Tests for audio mixing and volume calculations"""

    def test_frontend_volume_calculation(self):
        """Frontend volume calculation (0-1 scale with BGM reduction)"""
        global_volume = 0.8  # 80%
        track_volume = 100   # 100%
        bgm_reduction = 0.3  # 30%

        # Frontend calculation: volume * trackVolumeRatio * bgmReduction
        track_volume_ratio = track_volume / 100  # 1.0
        final_volume = global_volume * track_volume_ratio * bgm_reduction

        assert_close(final_volume, 0.24, "0.8 * 1.0 * 0.3 = 0.24")

    def test_backend_db_reduction(self):
        """Backend dB reduction calculation"""
        # 100% volume = 20dB base reduction
        # 50% volume = 20 + 20*log10(2) ≈ 26dB
        # 25% volume = 20 + 20*log10(4) ≈ 32dB

        base_reduction = 20.0

        volume_100 = base_reduction + 20 * math.log10(100/100)
        volume_50 = base_reduction + 20 * math.log10(100/50)
        volume_25 = base_reduction + 20 * math.log10(100/25)

        assert_close(volume_100, 20.0)
        assert_close(volume_50, 26.02, "~6dB louder than 25%")  # Using close comparison
        assert abs(volume_50 - 26.02) < 0.1

    def test_segment_audio_boost(self):
        """Segment TTS audio boost (2.0x in export pipeline)"""
        base_audio_level = 1.0
        tts_boost = 2.0  # volume=2.0 in FFmpeg filter

        boosted_level = base_audio_level * tts_boost
        assert_close(boosted_level, 2.0)


# ============================================================================
# SECTION 11: ADDITIONAL COMPREHENSIVE TESTS
# ============================================================================

class TestComplexMultiVideoScenarios:
    """Additional complex multi-video scenarios"""

    def test_five_videos_with_various_trims(self):
        """5 videos with different trim configurations"""
        videos = [
            # Full video
            MockVideo(id="v1", name="intro", path="/v1.mp4",
                     duration=60.0, source_start=0.0, source_end=None,
                     timeline_start=0.0, timeline_end=60.0),
            # Trimmed from start
            MockVideo(id="v2", name="scene1", path="/v2.mp4",
                     duration=120.0, source_start=30.0, source_end=None,
                     timeline_start=60.0, timeline_end=150.0),  # 90s effective
            # Trimmed from end
            MockVideo(id="v3", name="scene2", path="/v3.mp4",
                     duration=90.0, source_start=0.0, source_end=45.0,
                     timeline_start=150.0, timeline_end=195.0),
            # Trimmed both ends
            MockVideo(id="v4", name="scene3", path="/v4.mp4",
                     duration=180.0, source_start=30.0, source_end=150.0,
                     timeline_start=195.0, timeline_end=315.0),  # 120s effective
            # Short clip
            MockVideo(id="v5", name="outro", path="/v5.mp4",
                     duration=30.0, source_start=5.0, source_end=25.0,
                     timeline_start=315.0, timeline_end=335.0),  # 20s effective
        ]

        # Verify effective durations
        assert_close(videos[0].get_effective_duration(), 60.0)
        assert_close(videos[1].get_effective_duration(), 90.0)
        assert_close(videos[2].get_effective_duration(), 45.0)
        assert_close(videos[3].get_effective_duration(), 120.0)
        assert_close(videos[4].get_effective_duration(), 20.0)

        # Verify total timeline duration
        total = sum(v.get_effective_duration() for v in videos)
        assert_close(total, 335.0)

        # Verify sequential positioning
        for i in range(len(videos) - 1):
            assert_close(videos[i].timeline_end, videos[i+1].timeline_start,
                        f"Video {i} end should match video {i+1} start")

    def test_segments_across_five_videos(self):
        """Segments distributed across 5 videos"""
        video_configs = [
            {"id": "v1", "timeline_start": 0.0, "duration": 60.0},
            {"id": "v2", "timeline_start": 60.0, "duration": 90.0},
            {"id": "v3", "timeline_start": 150.0, "duration": 45.0},
            {"id": "v4", "timeline_start": 195.0, "duration": 120.0},
            {"id": "v5", "timeline_start": 315.0, "duration": 20.0},
        ]

        segments = [
            # Video 1 segments
            Segment(id="s1", video_id="v1", name="s1", start_time=10.0, end_time=30.0, text="", language="en"),
            Segment(id="s2", video_id="v1", name="s2", start_time=40.0, end_time=55.0, text="", language="en"),
            # Video 2 segments
            Segment(id="s3", video_id="v2", name="s3", start_time=0.0, end_time=45.0, text="", language="en"),
            Segment(id="s4", video_id="v2", name="s4", start_time=60.0, end_time=90.0, text="", language="en"),
            # Video 3 segment
            Segment(id="s5", video_id="v3", name="s5", start_time=10.0, end_time=40.0, text="", language="en"),
            # Video 4 segments
            Segment(id="s6", video_id="v4", name="s6", start_time=0.0, end_time=60.0, text="", language="en"),
            Segment(id="s7", video_id="v4", name="s7", start_time=80.0, end_time=120.0, text="", language="en"),
            # Video 5 segment
            Segment(id="s8", video_id="v5", name="s8", start_time=5.0, end_time=15.0, text="", language="en"),
        ]

        # Calculate all absolute positions
        for seg in segments:
            video = next(v for v in video_configs if v["id"] == seg.video_id)
            absolute_start = video["timeline_start"] + seg.start_time
            absolute_end = video["timeline_start"] + seg.end_time

            # Verify specific segments
            if seg.id == "s3":  # First segment on v2
                assert_close(absolute_start, 60.0, "s3 absolute start")
                assert_close(absolute_end, 105.0, "s3 absolute end")
            elif seg.id == "s5":  # Segment on v3
                assert_close(absolute_start, 160.0, "s5 absolute start")
                assert_close(absolute_end, 190.0, "s5 absolute end")
            elif seg.id == "s8":  # Segment on v5
                assert_close(absolute_start, 320.0, "s8 absolute start")
                assert_close(absolute_end, 330.0, "s8 absolute end")


class TestBGMWithMultipleVideos:
    """BGM track tests with multi-video timeline"""

    def test_bgm_spanning_multiple_videos(self):
        """BGM track that spans across multiple videos"""
        total_duration = 180.0  # 3 videos totaling 180 seconds

        bgm = BGMTrack(
            id="bgm1", name="theme", path="/theme.mp3",
            start_time=30.0, end_time=150.0,  # Spans from video 1 into video 3
            volume=50, fade_in=5.0, fade_out=10.0
        )

        video_boundaries = [
            {"start": 0.0, "end": 60.0},    # Video 1
            {"start": 60.0, "end": 120.0},  # Video 2
            {"start": 120.0, "end": 180.0}, # Video 3
        ]

        # BGM duration
        bgm_duration = bgm.get_time_range_duration(total_duration)
        assert_close(bgm_duration, 120.0, "BGM spans 120 seconds")

        # Check which videos BGM is active during
        bgm_end = bgm.get_effective_end_time(total_duration)
        active_in_videos = []

        for i, video in enumerate(video_boundaries):
            # Check overlap
            overlaps = not (bgm_end <= video["start"] or bgm.start_time >= video["end"])
            if overlaps:
                active_in_videos.append(i + 1)

        # BGM should be active in videos 1, 2, and 3
        assert active_in_videos == [1, 2, 3], "BGM active in videos 1, 2, and 3"

    def test_multiple_bgm_tracks_per_video(self):
        """Multiple BGM tracks assigned to different sections"""
        total_duration = 120.0

        tracks = [
            BGMTrack(id="bgm1", name="intro_music", path="/intro.mp3",
                    start_time=0.0, end_time=30.0, volume=80),
            BGMTrack(id="bgm2", name="ambient", path="/ambient.mp3",
                    start_time=20.0, end_time=100.0, volume=40),  # Overlaps with bgm1
            BGMTrack(id="bgm3", name="outro_music", path="/outro.mp3",
                    start_time=90.0, end_time=0.0, volume=60),  # 0 = to end
        ]

        # Verify track durations
        assert_close(tracks[0].get_time_range_duration(total_duration), 30.0)
        assert_close(tracks[1].get_time_range_duration(total_duration), 80.0)
        assert_close(tracks[2].get_time_range_duration(total_duration), 30.0)  # 120 - 90

        # Check overlaps
        assert tracks[0].overlaps_with(tracks[1], total_duration), "bgm1 overlaps bgm2"
        assert tracks[1].overlaps_with(tracks[2], total_duration), "bgm2 overlaps bgm3"
        assert not tracks[0].overlaps_with(tracks[2], total_duration), "bgm1 doesn't overlap bgm3"


class TestExportPipelineCalculations:
    """Tests for export pipeline timing calculations"""

    def test_adelay_for_multi_video_segment(self):
        """Calculate adelay filters for segment in multi-video export"""
        # Video 2 starts at 60s in timeline
        video2_start = 60.0

        # Segment at local time 10-25 on video 2
        segment_local_start = 10.0
        segment_local_end = 25.0

        # Absolute times
        segment_absolute_start = video2_start + segment_local_start  # 70
        segment_absolute_end = video2_start + segment_local_end      # 85

        # For video 2's clip, the delay is relative to video 2 start
        delay_in_clip = segment_local_start  # 10 seconds into the clip
        delay_ms = int(delay_in_clip * 1000)

        assert delay_ms == 10000, "10 second delay in clip"

        # For combined timeline export, use absolute timing
        absolute_delay_ms = int(segment_absolute_start * 1000)
        assert absolute_delay_ms == 70000, "70 second absolute delay"

    def test_subtitle_timing_across_videos(self):
        """Calculate subtitle timing for multi-video export"""
        videos = [
            {"id": "v1", "start": 0.0, "end": 60.0},
            {"id": "v2", "start": 60.0, "end": 120.0},
        ]

        # Segment on video 2 with subtitle
        segment = {
            "video_id": "v2",
            "start_time": 20.0,  # Local to video 2
            "end_time": 40.0,
        }

        video = videos[1]

        # Subtitle absolute times
        sub_absolute_start = video["start"] + segment["start_time"]  # 80
        sub_absolute_end = video["start"] + segment["end_time"]      # 100

        # For SRT format (in combined video)
        assert_close(sub_absolute_start, 80.0)
        assert_close(sub_absolute_end, 100.0)

        # For individual clip SRT (relative to clip start)
        clip_sub_start = segment["start_time"]  # 20
        clip_sub_end = segment["end_time"]      # 40

        assert_close(clip_sub_start, 20.0)
        assert_close(clip_sub_end, 40.0)


class TestVolumeNormalization:
    """Tests for volume normalization calculations"""

    def test_segment_voice_volume_normalization(self):
        """Test voice volume normalization for TTS segments"""
        # TTS boost factor
        tts_boost = 2.0

        # Segment volumes (as percentages)
        segment_volumes = [100, 80, 50, 120, 30]  # 120 is above normal

        # Calculate final volumes
        for vol in segment_volumes:
            vol_ratio = vol / 100
            final = tts_boost * vol_ratio

            if vol == 100:
                assert_close(final, 2.0)
            elif vol == 80:
                assert_close(final, 1.6)
            elif vol == 50:
                assert_close(final, 1.0)
            elif vol == 120:
                assert_close(final, 2.4)
            elif vol == 30:
                assert_close(final, 0.6)

    def test_bgm_ducking_during_voiceover(self):
        """Test BGM volume reduction during voiceover"""
        bgm_base_volume = 50  # 50%
        ducking_factor = 0.3  # Reduce to 30% during voice

        base_db = 20.0 + 20 * math.log10(100/bgm_base_volume)  # ~26 dB

        # During voiceover, additional ducking
        ducked_volume = bgm_base_volume * ducking_factor  # 15%
        ducked_db = 20.0 + 20 * math.log10(100/ducked_volume)  # ~36.5 dB

        # Verify ducking increases dB reduction
        assert ducked_db > base_db, "Ducking increases dB reduction"
        assert_close(ducked_db, 36.478, "Ducked volume dB")


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    # Run with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
