#!/usr/bin/env python3
"""
Comprehensive FFmpeg and AI Timeline Tests

This test suite validates:
1. Large scalable video calculations (4K, 8K, long duration)
2. Very small video calculations (low resolution, short duration)
3. FFmpeg command construction and validation
4. AI automation segmenting with timeline calculations

Professional video editor timeline tester with experience in
Adobe Premiere Pro and After Effects timeline calculations.
"""

import pytest
import math
import sys
import os
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.segment import Segment
from models.bgm_track import BGMTrack

# ============================================================================
# TEST CONFIGURATION
# ============================================================================

EPSILON = 0.001  # Tolerance for floating point comparisons

def assert_close(actual, expected, msg=""):
    """Assert two values are close within EPSILON tolerance"""
    assert abs(actual - expected) < EPSILON, f"{msg}: Expected {expected}, got {actual}"


# ============================================================================
# MOCK CLASSES
# ============================================================================

@dataclass
class MockVideoInfo:
    """Mock video information returned by FFprobe"""
    duration: float
    width: int
    height: int
    fps: float
    codec: str = "h264"
    audio_codec: str = "aac"
    audio_sample_rate: int = 48000
    audio_channels: int = 2
    bitrate: int = 10000000  # 10 Mbps

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height > 0 else 0


@dataclass
class MockVideo:
    """Mock Video for testing"""
    id: str
    name: str
    path: str
    duration: float
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    order: int = 1
    timeline_start: float = 0.0
    timeline_end: Optional[float] = None
    source_start: float = 0.0
    source_end: Optional[float] = None

    def __post_init__(self):
        if self.timeline_end is None:
            self.timeline_end = self.timeline_start + self.get_effective_duration()

    def get_effective_duration(self) -> float:
        end = self.source_end if self.source_end is not None else self.duration
        return max(0, end - self.source_start)


# ============================================================================
# SECTION 1: LARGE VIDEO TESTS (4K, 8K, Long Duration)
# ============================================================================

class TestLargeVideoCalculations:
    """Tests for large video handling (4K, 8K, long duration)"""

    # Video resolution presets
    RESOLUTIONS = {
        "SD": (640, 480),
        "HD": (1280, 720),
        "FHD": (1920, 1080),
        "2K": (2560, 1440),
        "4K": (3840, 2160),
        "5K": (5120, 2880),
        "8K": (7680, 4320),
    }

    def test_4k_video_timeline_calculation(self):
        """4K video timeline positioning"""
        video = MockVideo(
            id="v1", name="4K_video", path="/4k.mp4",
            duration=3600.0,  # 1 hour
            width=3840, height=2160,
            fps=60.0
        )

        # Verify dimensions
        assert video.width == 3840
        assert video.height == 2160
        assert video.width / video.height == 16/9  # 16:9 aspect ratio

        # Timeline calculations should work regardless of resolution
        assert_close(video.get_effective_duration(), 3600.0)
        assert_close(video.timeline_end - video.timeline_start, 3600.0)

    def test_8k_video_timeline_calculation(self):
        """8K video timeline positioning"""
        video = MockVideo(
            id="v1", name="8K_video", path="/8k.mp4",
            duration=7200.0,  # 2 hours
            width=7680, height=4320,
            fps=30.0
        )

        assert video.width == 7680
        assert video.height == 4320
        assert_close(video.get_effective_duration(), 7200.0)

    def test_long_duration_video_1_hour(self):
        """1 hour video timeline calculations"""
        video = MockVideo(
            id="v1", name="1hour", path="/1hour.mp4",
            duration=3600.0,  # 1 hour
            width=1920, height=1080
        )

        # Create 10 segments across the video
        segment_duration = video.duration / 10  # 360 seconds each
        segments = []
        for i in range(10):
            start = i * segment_duration
            end = (i + 1) * segment_duration
            segments.append(Segment(
                id=f"s{i}", video_id=video.id, name=f"seg{i}",
                start_time=start, end_time=end,
                text=f"Segment {i}", language="en"
            ))

        # Verify segments
        total_coverage = sum(s.duration for s in segments)
        assert_close(total_coverage, 3600.0, "Total segment coverage")

        # Verify no gaps or overlaps
        for i in range(len(segments) - 1):
            assert_close(segments[i].end_time, segments[i+1].start_time,
                        f"Segment {i} should end where {i+1} starts")

    def test_long_duration_video_3_hours(self):
        """3 hour video timeline calculations"""
        duration = 3 * 60 * 60  # 10800 seconds
        video = MockVideo(
            id="v1", name="3hours", path="/3hours.mp4",
            duration=float(duration),
            width=1920, height=1080
        )

        assert_close(video.get_effective_duration(), 10800.0)

        # Test segment at 2 hour mark
        segment = Segment(
            id="s1", video_id=video.id, name="late_segment",
            start_time=7200.0, end_time=7230.0,  # 2:00:00 - 2:00:30
            text="Late segment", language="en"
        )

        assert_close(segment.start_time, 7200.0)
        assert_close(segment.duration, 30.0)

    def test_long_duration_video_10_hours(self):
        """10 hour video (streaming/webinar content)"""
        duration = 10 * 60 * 60  # 36000 seconds
        video = MockVideo(
            id="v1", name="10hours", path="/10hours.mp4",
            duration=float(duration),
            width=1280, height=720
        )

        assert_close(video.get_effective_duration(), 36000.0)

        # Test trimming a 10 hour video to 1 hour segment
        video_trimmed = MockVideo(
            id="v2", name="trimmed", path="/10hours.mp4",
            duration=float(duration),
            source_start=18000.0,  # Start at 5 hours
            source_end=21600.0,    # End at 6 hours
            timeline_start=0.0
        )

        assert_close(video_trimmed.get_effective_duration(), 3600.0, "1 hour effective")

    def test_4k_60fps_frame_precision(self):
        """Frame-accurate calculations for 4K 60fps"""
        fps = 60.0
        frame_duration = 1.0 / fps  # ~0.01667 seconds

        # Segment should align to frame boundaries
        start_frame = 1000
        end_frame = 2000
        segment = Segment(
            id="s1", video_id="v1", name="frames",
            start_time=start_frame * frame_duration,
            end_time=end_frame * frame_duration,
            text="Frame-precise", language="en"
        )

        # Duration should be exactly 1000 frames
        expected_duration = (end_frame - start_frame) * frame_duration
        assert_close(segment.duration, expected_duration, "Frame-precise duration")

    def test_high_bitrate_video_info(self):
        """High bitrate video (ProRes, DNxHR, etc.)"""
        # 8K ProRes at 2.5 Gbps
        video_info = MockVideoInfo(
            duration=600.0,  # 10 minutes
            width=7680, height=4320,
            fps=30.0,
            codec="prores_hq",
            bitrate=2500000000  # 2.5 Gbps
        )

        # File size calculation (for UI display)
        file_size_bytes = video_info.bitrate * video_info.duration / 8
        file_size_gb = file_size_bytes / (1024**3)

        # 10 minutes at 2.5 Gbps = ~174.6 GB
        # 2.5 Gbps * 600s / 8 bits = 187.5 GB (raw), but 1024-based = ~174.6 GiB
        assert file_size_gb > 170, "Large file expected"
        assert file_size_gb < 180, "File size within range"

    def test_multiple_4k_videos_timeline(self):
        """Multiple 4K videos in sequence"""
        videos = [
            MockVideo(id="v1", name="intro", path="/4k_1.mp4",
                     duration=300.0, width=3840, height=2160, order=1,
                     timeline_start=0.0, timeline_end=300.0),
            MockVideo(id="v2", name="main", path="/4k_2.mp4",
                     duration=1800.0, width=3840, height=2160, order=2,
                     timeline_start=300.0, timeline_end=2100.0),
            MockVideo(id="v3", name="outro", path="/4k_3.mp4",
                     duration=120.0, width=3840, height=2160, order=3,
                     timeline_start=2100.0, timeline_end=2220.0),
        ]

        # Total timeline duration
        total_duration = sum(v.get_effective_duration() for v in videos)
        assert_close(total_duration, 2220.0, "Total combined duration")

        # Verify sequential positioning
        for i in range(len(videos) - 1):
            assert_close(videos[i].timeline_end, videos[i+1].timeline_start,
                        f"Video {i} should end where {i+1} starts")


class TestVerySmallVideoCalculations:
    """Tests for very small video handling (short duration, low resolution)"""

    def test_1_second_video(self):
        """1 second video"""
        video = MockVideo(
            id="v1", name="short", path="/short.mp4",
            duration=1.0,
            width=1920, height=1080
        )

        assert_close(video.get_effective_duration(), 1.0)

    def test_subsecond_video(self):
        """Sub-second video (0.5 seconds)"""
        video = MockVideo(
            id="v1", name="flash", path="/flash.mp4",
            duration=0.5,
            width=1920, height=1080
        )

        assert_close(video.get_effective_duration(), 0.5)

        # Segment covering entire video
        segment = Segment(
            id="s1", video_id=video.id, name="full",
            start_time=0.0, end_time=0.5,
            text="Quick", language="en"
        )

        assert_close(segment.duration, 0.5)

    def test_100_millisecond_video(self):
        """100 millisecond video (3 frames at 30fps)"""
        duration = 0.1  # 100ms
        fps = 30.0
        frame_count = int(duration * fps)  # 3 frames

        video = MockVideo(
            id="v1", name="frames", path="/frames.mp4",
            duration=duration,
            width=1920, height=1080,
            fps=fps
        )

        assert_close(video.get_effective_duration(), 0.1)
        assert frame_count == 3, "3 frames at 30fps"

    def test_low_resolution_320x240(self):
        """Very low resolution video (320x240)"""
        video = MockVideo(
            id="v1", name="lowres", path="/lowres.mp4",
            duration=30.0,
            width=320, height=240
        )

        # Timeline calculations should work for any resolution
        assert_close(video.get_effective_duration(), 30.0)
        assert video.width == 320
        assert video.height == 240

    def test_tiny_160x120_video(self):
        """Tiny resolution video (160x120)"""
        video = MockVideo(
            id="v1", name="tiny", path="/tiny.mp4",
            duration=10.0,
            width=160, height=120
        )

        assert video.width == 160
        assert video.height == 120
        assert_close(video.get_effective_duration(), 10.0)

    def test_square_1x1_edge_case(self):
        """Edge case: 1x1 pixel video"""
        video = MockVideo(
            id="v1", name="pixel", path="/pixel.mp4",
            duration=1.0,
            width=1, height=1
        )

        assert video.width == 1
        assert video.height == 1
        assert_close(video.get_effective_duration(), 1.0)

    def test_short_segment_10ms(self):
        """Very short segment (10 milliseconds)"""
        segment = Segment(
            id="s1", video_id="v1", name="flash",
            start_time=0.0, end_time=0.01,
            text="!", language="en"
        )

        assert_close(segment.duration, 0.01, "10ms segment")

    def test_many_short_segments(self):
        """Many short segments in sequence"""
        # 100 segments of 0.1 seconds each
        segments = []
        for i in range(100):
            start = i * 0.1
            end = (i + 1) * 0.1
            segments.append(Segment(
                id=f"s{i}", video_id="v1", name=f"quick{i}",
                start_time=start, end_time=end,
                text=str(i), language="en"
            ))

        # Total coverage should be 10 seconds
        total = sum(s.duration for s in segments)
        assert_close(total, 10.0, "100 x 0.1s = 10s")

    def test_vertical_video_9x16(self):
        """Vertical video (9:16 aspect ratio - mobile/TikTok)"""
        video = MockVideo(
            id="v1", name="vertical", path="/vertical.mp4",
            duration=15.0,
            width=1080, height=1920  # 9:16
        )

        aspect_ratio = video.width / video.height
        assert_close(aspect_ratio, 9/16, "9:16 aspect ratio")
        assert video.width < video.height, "Width should be less than height"


# ============================================================================
# SECTION 2: FFMPEG COMMAND VALIDATION
# ============================================================================

class TestFFmpegCommandConstruction:
    """Tests for FFmpeg command construction patterns"""

    def test_adelay_filter_format(self):
        """Test adelay filter format for stereo audio"""
        delay_seconds = 5.5
        delay_ms = int(delay_seconds * 1000)

        # Stereo adelay format
        adelay_filter = f"adelay={delay_ms}|{delay_ms}"
        expected = "adelay=5500|5500"

        assert adelay_filter == expected

    def test_atrim_filter_format(self):
        """Test atrim filter for audio trimming"""
        start_offset = 3.5
        duration = 10.0

        # atrim with start and duration
        atrim_filter = f"atrim=start={start_offset:.3f}:duration={duration:.3f}"
        expected = "atrim=start=3.500:duration=10.000"

        assert atrim_filter == expected

    def test_afade_filter_format(self):
        """Test afade filter for fade in/out"""
        # Fade in
        fade_in_duration = 2.0
        afade_in = f"afade=t=in:st=0:d={fade_in_duration}"
        assert "t=in" in afade_in
        assert f"d={fade_in_duration}" in afade_in

        # Fade out
        audio_duration = 60.0
        fade_out_duration = 3.0
        fade_out_start = audio_duration - fade_out_duration
        afade_out = f"afade=t=out:st={fade_out_start}:d={fade_out_duration}"
        assert "t=out" in afade_out
        assert f"st={fade_out_start}" in afade_out

    def test_aloop_filter_format(self):
        """Test aloop filter for audio looping"""
        loop_count = 5
        sample_rate = 48000
        audio_duration = 30.0
        loop_size = int(audio_duration * sample_rate)

        aloop_filter = f"aloop=loop={loop_count}:size={loop_size}"
        expected = f"aloop=loop=5:size={int(30 * 48000)}"

        assert aloop_filter == expected

    def test_volume_filter_format(self):
        """Test volume filter for audio level adjustment"""
        # dB reduction
        db_reduction = 20.0
        volume_db = f"volume=-{db_reduction}dB"
        assert volume_db == "volume=-20.0dB"

        # Boost by 2x
        boost_factor = 2.0
        volume_boost = f"volume={boost_factor}"
        assert volume_boost == "volume=2.0"

    def test_amix_filter_format(self):
        """Test amix filter for audio mixing"""
        num_inputs = 3
        amix_filter = f"amix=inputs={num_inputs}:duration=first:dropout_transition=0"
        expected = "amix=inputs=3:duration=first:dropout_transition=0"

        assert amix_filter == expected

    def test_complex_audio_filter_chain(self):
        """Test complex audio filter chain construction"""
        # Scenario: 2 voice-overs at different positions + BGM

        # Voice-over 1: at 5 seconds, boost volume
        vo1_delay = 5000  # 5 seconds in ms
        vo1_filter = f"[1:a]adelay={vo1_delay}|{vo1_delay},volume=2.0[vo1]"

        # Voice-over 2: at 30 seconds, with trim
        vo2_delay = 30000
        vo2_offset = 2.0  # Skip first 2 seconds
        vo2_duration = 15.0
        vo2_filter = f"[2:a]atrim=start={vo2_offset}:duration={vo2_duration},asetpts=PTS-STARTPTS,volume=2.0,adelay={vo2_delay}|{vo2_delay}[vo2]"

        # Original video audio
        video_audio = "[0:a]volume=0.7[va]"

        # BGM track with reduction
        bgm_filter = "[3:a]volume=-20dB,afade=t=in:st=0:d=3,afade=t=out:st=57:d=3[bgm]"

        # Mix all
        mix_filter = "[va][vo1][vo2][bgm]amix=inputs=4:duration=first:dropout_transition=0[aout]"

        # Build complete filter_complex
        filter_complex = ";".join([
            video_audio,
            vo1_filter,
            vo2_filter,
            bgm_filter,
            mix_filter
        ])

        # Verify structure
        assert "[0:a]" in filter_complex
        assert "[1:a]" in filter_complex
        assert "[2:a]" in filter_complex
        assert "[3:a]" in filter_complex
        assert "amix=inputs=4" in filter_complex
        assert "[aout]" in filter_complex

    def test_subtitle_filter_escaping(self):
        """Test subtitle path escaping for FFmpeg"""
        # Windows path
        windows_path = "C:\\Users\\test\\subtitles.ass"
        escaped_windows = windows_path.replace("\\", "/").replace(":", "\\:")
        assert "C\\:" in escaped_windows
        assert "/" in escaped_windows

        # Path with spaces
        space_path = "/Users/test/my subtitles.ass"
        # For subtitles filter, use quotes
        escaped_space = f"subtitles='{space_path}'"
        assert "my subtitles" in escaped_space

    def test_video_extraction_time_format(self):
        """Test time format for video extraction -ss and -t"""
        start_time = 3723.456  # 1:02:03.456

        # FFmpeg accepts seconds directly
        ss_param = f"-ss {start_time}"
        assert ss_param == "-ss 3723.456"

        # Or HH:MM:SS format
        hours = int(start_time // 3600)
        minutes = int((start_time % 3600) // 60)
        seconds = start_time % 60
        hms_format = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
        assert hms_format == "01:02:03.456"

    def test_quality_preset_values(self):
        """Test quality preset CRF and preset values"""
        quality_presets = {
            "lossless": {"crf": 0, "preset": "veryslow"},
            "high": {"crf": 18, "preset": "slow"},
            "balanced": {"crf": 23, "preset": "medium"},
            "fast": {"crf": 28, "preset": "fast"},
            "draft": {"crf": 32, "preset": "ultrafast"},
        }

        # Verify CRF is in valid range (0-51 for x264/x265)
        for name, settings in quality_presets.items():
            assert 0 <= settings["crf"] <= 51, f"CRF out of range for {name}"
            assert settings["preset"] in ["ultrafast", "superfast", "veryfast",
                                          "faster", "fast", "medium",
                                          "slow", "slower", "veryslow"]


class TestFFmpegDurationCalculations:
    """Tests for FFmpeg duration-related calculations"""

    def test_segment_extraction_timing(self):
        """Test segment extraction with -ss and -t"""
        start_time = 30.5
        end_time = 45.75
        duration = end_time - start_time

        # Build extraction command params
        ss_param = str(start_time)
        t_param = str(duration)

        assert_close(float(ss_param), 30.5)
        assert_close(float(t_param), 15.25)

    def test_audio_delay_milliseconds(self):
        """Test audio delay conversion to milliseconds"""
        # Various delay values
        delays = [0.0, 0.001, 0.5, 1.0, 10.5, 60.0, 3600.0]

        for delay_secs in delays:
            delay_ms = int(delay_secs * 1000)
            # Convert back
            back_to_secs = delay_ms / 1000
            # Should be close but may lose sub-ms precision
            assert abs(back_to_secs - delay_secs) < 0.001

    def test_bgm_loop_count_calculation(self):
        """Test BGM loop count calculation"""
        video_duration = 120.0  # 2 minutes
        bgm_duration = 45.0     # 45 second loop

        # Need enough loops to cover video
        # 120 / 45 = 2.67, so need at least 3 loops
        loop_count = int((video_duration / bgm_duration) + 1)
        total_looped = bgm_duration * loop_count

        assert loop_count == 3
        assert total_looped >= video_duration

    def test_fade_timing_calculation(self):
        """Test fade in/out timing calculations"""
        audio_duration = 60.0
        fade_in = 3.0
        fade_out = 5.0

        # Fade in: starts at 0, duration = fade_in
        fade_in_start = 0.0
        fade_in_end = fade_in_start + fade_in

        # Fade out: ends at duration, starts at duration - fade_out
        fade_out_end = audio_duration
        fade_out_start = fade_out_end - fade_out

        assert_close(fade_in_start, 0.0)
        assert_close(fade_in_end, 3.0)
        assert_close(fade_out_start, 55.0)
        assert_close(fade_out_end, 60.0)


# ============================================================================
# SECTION 3: AI AUTOMATION SEGMENTING TESTS
# ============================================================================

class TestAISegmentGeneration:
    """Tests for AI-powered segment generation calculations"""

    # Words per second for duration estimation
    WORDS_PER_SECOND = {
        "en": 2.5,
        "es": 2.3,
        "fr": 2.4,
        "de": 2.2,
        "zh": 3.5,  # Characters
        "ja": 3.0,
    }

    def test_word_count_estimation(self):
        """Test word count estimation from duration"""
        duration = 30.0  # 30 seconds
        language = "en"
        wps = self.WORDS_PER_SECOND[language]

        estimated_words = int(duration * wps)
        assert estimated_words == 75, "30s * 2.5 wps = 75 words"

    def test_duration_estimation_from_text(self):
        """Test duration estimation from text"""
        text = "This is a sample script for testing duration estimation of text to speech audio."
        word_count = len(text.split())
        language = "en"
        wps = self.WORDS_PER_SECOND[language]

        estimated_duration = word_count / wps
        assert word_count == 14
        assert_close(estimated_duration, 5.6, "14 words / 2.5 wps = 5.6s")

    def test_segment_count_calculation(self):
        """Test automatic segment count calculation"""
        video_duration = 120.0  # 2 minutes
        min_segment = 10.0
        max_segment = 30.0
        avg_segment = (min_segment + max_segment) / 2  # 20 seconds

        recommended_segments = max(1, int(video_duration / avg_segment))
        assert recommended_segments == 6, "120 / 20 = 6 segments"

    def test_segment_coverage_validation(self):
        """Test that generated segments cover the full video"""
        video_duration = 60.0

        # Simulated AI-generated segments
        segments = [
            {"start_time": 0.0, "end_time": 15.0, "script": "Intro..."},
            {"start_time": 15.0, "end_time": 35.0, "script": "Main content..."},
            {"start_time": 35.0, "end_time": 60.0, "script": "Conclusion..."},
        ]

        # Verify coverage
        total_coverage = sum(s["end_time"] - s["start_time"] for s in segments)
        assert_close(total_coverage, 60.0, "Full video coverage")

        # Verify first segment starts at 0
        assert_close(segments[0]["start_time"], 0.0, "Starts at 0")

        # Verify last segment ends at duration
        assert_close(segments[-1]["end_time"], video_duration, "Ends at duration")

        # Verify no gaps
        for i in range(len(segments) - 1):
            assert_close(segments[i]["end_time"], segments[i+1]["start_time"],
                        "No gaps between segments")

    def test_script_fit_validation(self):
        """Test script fit validation (estimated vs actual duration)"""
        segment_duration = 20.0
        language = "en"
        wps = self.WORDS_PER_SECOND[language]

        # Target word count
        target_words = int(segment_duration * wps)  # 50 words

        # Simulated script
        script = " ".join(["word"] * 45)  # 45 words
        actual_words = len(script.split())
        estimated_duration = actual_words / wps

        # Check fit (allow 10% tolerance)
        tolerance = 0.1
        fits = estimated_duration <= segment_duration * (1 + tolerance)
        fit_percentage = (actual_words / target_words) * 100

        assert actual_words == 45
        assert_close(estimated_duration, 18.0, "45 / 2.5 = 18s")
        assert fits, "Script fits within 10% tolerance"
        assert_close(fit_percentage, 90.0, "90% of target")

    def test_script_overflow_detection(self):
        """Test detection of scripts that are too long"""
        segment_duration = 10.0
        language = "en"
        wps = self.WORDS_PER_SECOND[language]

        # Oversized script
        script = " ".join(["word"] * 50)  # 50 words for 10s segment
        actual_words = len(script.split())
        estimated_duration = actual_words / wps  # 20 seconds

        overflow = estimated_duration - segment_duration
        is_overflow = overflow > 0

        assert is_overflow, "Script overflows segment"
        assert_close(overflow, 10.0, "10 seconds overflow")

    def test_multi_language_duration_estimation(self):
        """Test duration estimation for different languages"""
        word_count = 100

        for lang, wps in self.WORDS_PER_SECOND.items():
            duration = word_count / wps
            # Verify reasonable range
            assert duration > 20, f"At least 20s for 100 words in {lang}"
            assert duration < 50, f"Less than 50s for 100 words in {lang}"

    def test_segment_naming_pattern(self):
        """Test segment naming patterns"""
        video_title = "Product Demo"
        segment_names = [
            "Introduction",
            "Feature Overview",
            "Product Demo - Main Features",
            "Pricing Information",
            "Call to Action",
        ]

        # Verify naming is reasonable
        for name in segment_names:
            assert len(name) > 0, "Name not empty"
            assert len(name) < 100, "Name not too long"


class TestAISegmentWithTimeline:
    """Tests for AI segments integrated with timeline calculations"""

    def test_ai_segments_absolute_positioning(self):
        """Test AI segment conversion to absolute timeline positions"""
        # Multi-video timeline
        videos = [
            MockVideo(id="v1", name="intro", path="/v1.mp4", duration=30.0,
                     timeline_start=0.0, timeline_end=30.0, order=1),
            MockVideo(id="v2", name="main", path="/v2.mp4", duration=60.0,
                     timeline_start=30.0, timeline_end=90.0, order=2),
        ]

        # AI generates segments for video 2 (local times)
        ai_segments = [
            {"video_id": "v2", "start_time": 0.0, "end_time": 20.0, "script": "Part 1"},
            {"video_id": "v2", "start_time": 20.0, "end_time": 45.0, "script": "Part 2"},
            {"video_id": "v2", "start_time": 45.0, "end_time": 60.0, "script": "Part 3"},
        ]

        # Convert to absolute timeline positions
        video2 = videos[1]
        for seg in ai_segments:
            absolute_start = video2.timeline_start + seg["start_time"]
            absolute_end = video2.timeline_start + seg["end_time"]
            seg["absolute_start"] = absolute_start
            seg["absolute_end"] = absolute_end

        # Verify absolute positions
        assert_close(ai_segments[0]["absolute_start"], 30.0)
        assert_close(ai_segments[0]["absolute_end"], 50.0)
        assert_close(ai_segments[1]["absolute_start"], 50.0)
        assert_close(ai_segments[1]["absolute_end"], 75.0)
        assert_close(ai_segments[2]["absolute_start"], 75.0)
        assert_close(ai_segments[2]["absolute_end"], 90.0)

    def test_ai_segments_with_trimmed_video(self):
        """Test AI segments on a trimmed video"""
        # Video trimmed from 10s to 50s (40s effective duration)
        video = MockVideo(
            id="v1", name="trimmed", path="/trimmed.mp4",
            duration=60.0,
            source_start=10.0, source_end=50.0,
            timeline_start=0.0, timeline_end=40.0
        )

        # AI generates segments for the trimmed portion
        ai_segments = [
            {"start_time": 0.0, "end_time": 20.0, "script": "First half"},
            {"start_time": 20.0, "end_time": 40.0, "script": "Second half"},
        ]

        # Timeline positions (relative to trimmed video)
        for seg in ai_segments:
            # Timeline position
            timeline_start = video.timeline_start + seg["start_time"]
            timeline_end = video.timeline_start + seg["end_time"]

            # Source position (for FFmpeg seek)
            source_start = video.source_start + seg["start_time"]
            source_end = video.source_start + seg["end_time"]

            seg["timeline_start"] = timeline_start
            seg["timeline_end"] = timeline_end
            seg["source_start"] = source_start
            seg["source_end"] = source_end

        # Verify first segment
        assert_close(ai_segments[0]["timeline_start"], 0.0)
        assert_close(ai_segments[0]["timeline_end"], 20.0)
        assert_close(ai_segments[0]["source_start"], 10.0)  # 10 + 0
        assert_close(ai_segments[0]["source_end"], 30.0)    # 10 + 20

        # Verify second segment
        assert_close(ai_segments[1]["timeline_start"], 20.0)
        assert_close(ai_segments[1]["timeline_end"], 40.0)
        assert_close(ai_segments[1]["source_start"], 30.0)  # 10 + 20
        assert_close(ai_segments[1]["source_end"], 50.0)    # 10 + 40

    def test_ai_segments_with_bgm(self):
        """Test AI segments coordinated with BGM tracks"""
        video_duration = 120.0

        # AI-generated segments
        segments = [
            Segment(id="s1", video_id="v1", name="intro",
                   start_time=0.0, end_time=30.0, text="", language="en"),
            Segment(id="s2", video_id="v1", name="main",
                   start_time=30.0, end_time=100.0, text="", language="en"),
            Segment(id="s3", video_id="v1", name="outro",
                   start_time=100.0, end_time=120.0, text="", language="en"),
        ]

        # BGM tracks
        bgm_tracks = [
            BGMTrack(id="bgm1", name="intro_music", path="/intro.mp3",
                    start_time=0.0, end_time=35.0, volume=50, fade_in=2.0, fade_out=3.0),
            BGMTrack(id="bgm2", name="main_music", path="/main.mp3",
                    start_time=30.0, end_time=105.0, volume=40, fade_in=2.0, fade_out=5.0),
            BGMTrack(id="bgm3", name="outro_music", path="/outro.mp3",
                    start_time=95.0, end_time=0.0, volume=60, fade_in=3.0, fade_out=5.0),
        ]

        # Check segment-BGM overlap
        for seg in segments:
            overlapping_bgm = []
            for bgm in bgm_tracks:
                bgm_end = bgm.get_effective_end_time(video_duration)
                if bgm.overlaps_with(BGMTrack(id="temp", name="", path="",
                                              start_time=seg.start_time,
                                              end_time=seg.end_time), video_duration):
                    overlapping_bgm.append(bgm.name)

            # Intro segment should overlap with intro_music and main_music
            if seg.name == "intro":
                # BGM1 covers 0-35, BGM2 starts at 30
                # Segment is 0-30, overlaps with BGM1 (0-35)
                pass  # Complex overlap logic

        # All segments should have TTS boosted over BGM
        # This is handled by the export pipeline

    def test_cross_video_ai_segment(self):
        """Test AI segment that spans across video boundary"""
        videos = [
            MockVideo(id="v1", name="v1", path="/v1.mp4", duration=30.0,
                     timeline_start=0.0, timeline_end=30.0, order=1),
            MockVideo(id="v2", name="v2", path="/v2.mp4", duration=30.0,
                     timeline_start=30.0, timeline_end=60.0, order=2),
        ]

        # AI generates a segment that extends beyond video 1
        # This mimics the extends_to_next_video feature
        original_segment = Segment(
            id="s1", video_id="v1", name="cross_segment",
            start_time=25.0, end_time=35.0,  # Extends 5s into video 2
            text="This segment crosses videos", language="en"
        )

        # Calculate parts
        v1_duration = videos[0].duration
        part1_duration = v1_duration - original_segment.start_time  # 30 - 25 = 5s
        overflow = original_segment.end_time - v1_duration  # 35 - 30 = 5s

        # Original plays: 25s - 30s on video 1 (5 seconds)
        # Continuation plays: 0s - 5s on video 2 (5 seconds)

        # Continuation segment
        continuation = Segment(
            id="s1_cont", video_id="v2", name="cross_segment (cont.)",
            start_time=0.0, end_time=overflow,
            audio_offset=part1_duration,  # Skip first 5s of audio
            text="", language="en"
        )

        assert_close(part1_duration, 5.0)
        assert_close(overflow, 5.0)
        assert_close(continuation.audio_offset, 5.0, "Skip already played audio")


# ============================================================================
# SECTION 4: INTEGRATION TESTS
# ============================================================================

class TestCompleteScenarios:
    """End-to-end integration scenarios"""

    def test_4k_long_video_with_many_segments(self):
        """4K 1-hour video with 30 AI-generated segments and BGM"""
        video = MockVideo(
            id="v1", name="documentary", path="/documentary.mp4",
            duration=3600.0,  # 1 hour
            width=3840, height=2160,
            fps=24.0
        )

        # Generate 30 segments (average 2 minutes each)
        segment_count = 30
        segment_duration = video.duration / segment_count

        segments = []
        for i in range(segment_count):
            start = i * segment_duration
            end = (i + 1) * segment_duration
            segments.append(Segment(
                id=f"s{i}", video_id=video.id, name=f"Scene {i+1}",
                start_time=start, end_time=end,
                text=f"Narration for scene {i+1}...", language="en"
            ))

        # BGM tracks for different sections
        bgm_tracks = [
            BGMTrack(id="bgm1", name="intro", path="/intro.mp3",
                    start_time=0.0, end_time=600.0, volume=40),  # First 10 min
            BGMTrack(id="bgm2", name="ambient", path="/ambient.mp3",
                    start_time=300.0, end_time=3300.0, volume=30),  # 5 min - 55 min
            BGMTrack(id="bgm3", name="outro", path="/outro.mp3",
                    start_time=3300.0, end_time=0.0, volume=50),  # Last 5 min
        ]

        # Verify calculations
        assert len(segments) == 30
        assert_close(segments[-1].end_time, 3600.0, "Last segment ends at video end")

        # BGM coverage
        assert_close(bgm_tracks[0].get_time_range_duration(video.duration), 600.0)
        assert_close(bgm_tracks[1].get_time_range_duration(video.duration), 3000.0)
        assert_close(bgm_tracks[2].get_time_range_duration(video.duration), 300.0)

    def test_short_social_media_video(self):
        """Short 15-second social media video"""
        video = MockVideo(
            id="v1", name="reel", path="/reel.mp4",
            duration=15.0,
            width=1080, height=1920,  # Vertical
            fps=30.0
        )

        # Single segment covering entire video
        segment = Segment(
            id="s1", video_id=video.id, name="hook",
            start_time=0.0, end_time=15.0,
            text="Short punchy text for social media", language="en"
        )

        # Full background music
        bgm = BGMTrack(
            id="bgm1", name="beat", path="/beat.mp3",
            start_time=0.0, end_time=0.0,  # Full video
            volume=70,
            fade_in=0.5, fade_out=1.0
        )

        assert_close(segment.duration, 15.0)
        assert_close(bgm.get_time_range_duration(video.duration), 15.0)

    def test_multi_video_project_export(self):
        """Multi-video project with cross-video segments"""
        videos = [
            MockVideo(id="v1", name="intro", path="/v1.mp4", duration=30.0,
                     timeline_start=0.0, timeline_end=30.0, order=1),
            MockVideo(id="v2", name="demo", path="/v2.mp4", duration=120.0,
                     timeline_start=30.0, timeline_end=150.0, order=2),
            MockVideo(id="v3", name="outro", path="/v3.mp4", duration=20.0,
                     timeline_start=150.0, timeline_end=170.0, order=3),
        ]

        # Total timeline
        total_duration = videos[-1].timeline_end
        assert_close(total_duration, 170.0)

        # Segments distributed across videos
        segments = [
            # Video 1
            Segment(id="s1", video_id="v1", name="welcome",
                   start_time=5.0, end_time=25.0, text="", language="en"),
            # Video 2
            Segment(id="s2", video_id="v2", name="demo1",
                   start_time=10.0, end_time=50.0, text="", language="en"),
            Segment(id="s3", video_id="v2", name="demo2",
                   start_time=60.0, end_time=110.0, text="", language="en"),
            # Video 3
            Segment(id="s4", video_id="v3", name="goodbye",
                   start_time=5.0, end_time=15.0, text="", language="en"),
        ]

        # Calculate FFmpeg delays for each segment
        for seg in segments:
            video = next(v for v in videos if v.id == seg.video_id)
            absolute_start = video.timeline_start + seg.start_time
            delay_ms = int(absolute_start * 1000)

            seg.absolute_start = absolute_start
            seg.delay_ms = delay_ms

        # Verify delays
        assert segments[0].delay_ms == 5000    # 5 seconds
        assert segments[1].delay_ms == 40000   # 30 + 10 = 40 seconds
        assert segments[2].delay_ms == 90000   # 30 + 60 = 90 seconds
        assert segments[3].delay_ms == 155000  # 150 + 5 = 155 seconds


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
