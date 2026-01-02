"""Export Pipeline - Orchestrates video export using proven patterns"""

import asyncio
import os
import time
from pathlib import Path
from typing import Optional, Callable, List, Any
from uuid import uuid4
import copy

from models import Project
from models.video import Video
from models.segment import Segment
from backend.tts_service import TTSService
from backend.ffmpeg_utils import FFmpegUtils, FFmpegProgressTracker
from backend.subtitle_utils import SubtitleUtils
from utils.logger import logger
from utils.font_manager import FontManager
from config import settings
from core.video_combiner import VideoCombiner
from core.timeline_coordinator import TimelineCoordinator
from core.layer_compositor import LayerCompositor
from core.watermark import get_watermark_service


class ExportPipeline:
    """
    Orchestrates video export using proven FFmpeg patterns
    """

    def __init__(self, project: Project):
        self.project = project
        self.tts_service = TTSService()
        self.temp_dir = Path(settings.TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # Reference height for scaling - FFmpeg's default PlayRes when converting SRT to ASS
    REFERENCE_PLAYRES_HEIGHT = 288

    @staticmethod
    def _scale_for_resolution(value: float, play_res_y: int) -> float:
        """
        Scale a subtitle parameter from reference resolution to target PlayRes.

        FFmpeg's default ASS conversion uses PlayRes 384x288. User's subtitle settings
        (font size, margins, outline, shadow) are specified relative to this reference.
        When we create ASS files with different PlayRes, we must scale these values
        to maintain consistent visual appearance.

        Formula: scaled_value = value × (play_res_y / 288)

        Examples for font_size=20:
          - 720p (720):  20 × (720/288)  = 50px  (6.9% of height)
          - 1080p (1080): 20 × (1080/288) = 75px  (6.9% of height)
          - 4K (2160):   20 × (2160/288) = 150px (6.9% of height)
          - Vertical 1080 (1920): 20 × (1920/288) = 133px (6.9% of height)

        Args:
            value: Original value (font size, margin, outline, shadow)
            play_res_y: Target PlayRes height

        Returns:
            Scaled value for target resolution
        """
        return value * play_res_y / ExportPipeline.REFERENCE_PLAYRES_HEIGHT

    def _get_cross_video_continuations(self, video: Video) -> List[Segment]:
        """
        Get continuation segments from the previous video that extend into this video.

        For cross-video segments:
        - Original segment in Video A has extends_to_next_video=True
        - This creates a continuation in Video B starting at 0:00

        Returns list of continuation Segment objects ready for processing.
        """
        continuations = []

        # Get previous video in order
        prev_video = self.project.get_previous_video(video.id)
        if not prev_video:
            return continuations

        # Check each segment in previous video
        for segment in prev_video.timeline.segments:
            if not getattr(segment, 'extends_to_next_video', False):
                continue

            # Calculate overflow into this video
            overflow = segment.end_time - (prev_video.duration or 0)
            if overflow <= 0:
                continue

            # Create continuation segment
            continuation = self._create_continuation_segment(
                original_segment=segment,
                overflow_duration=overflow,
                source_video_duration=prev_video.duration or 0,
                target_video=video
            )
            continuations.append(continuation)
            logger.info(f"Created continuation segment for '{segment.name}' in {video.name}")

        return continuations

    def _create_continuation_segment(
        self,
        original_segment: Segment,
        overflow_duration: float,
        source_video_duration: float,
        target_video: Video
    ) -> Segment:
        """
        Create a continuation segment for the next video.

        The continuation:
        - Starts at 0:00 of the next video
        - Ends at overflow_duration
        - Uses the SAME audio file (will be trimmed during processing)
        - Has adjusted subtitle timing
        """
        # Deep copy to avoid modifying original
        continuation = Segment(
            id=f"{original_segment.id}_continuation_{uuid4().hex[:8]}",
            name=f"{original_segment.name} (cont.)",
            video_id=target_video.id,
            start_time=0.0,
            end_time=overflow_duration,
            text=original_segment.text,
            language=original_segment.language,
            voice_id=original_segment.voice_id,
            rate=original_segment.rate,
            volume=original_segment.volume,
            pitch=original_segment.pitch,
            # Reuse same audio/subtitle files - will be trimmed during processing
            audio_path=original_segment.audio_path,
            subtitle_path=original_segment.subtitle_path,
            # Copy subtitle styling
            subtitle_enabled=original_segment.subtitle_enabled,
            subtitle_font=original_segment.subtitle_font,
            subtitle_size=original_segment.subtitle_size,
            subtitle_color=original_segment.subtitle_color,
            subtitle_position=original_segment.subtitle_position,
            subtitle_border_enabled=getattr(original_segment, 'subtitle_border_enabled', True),
            subtitle_border_style=getattr(original_segment, 'subtitle_border_style', 1),
            subtitle_outline_width=getattr(original_segment, 'subtitle_outline_width', 0.5),
            subtitle_outline_color=getattr(original_segment, 'subtitle_outline_color', '&H00000000'),
            subtitle_shadow=getattr(original_segment, 'subtitle_shadow', 0.0),
            subtitle_shadow_color=getattr(original_segment, 'subtitle_shadow_color', '&H80000000'),
            sync_mode=original_segment.sync_mode,
            extends_to_next_video=False  # Continuation doesn't extend further
        )

        # Store metadata for audio/subtitle offset processing
        continuation._is_continuation = True
        continuation._audio_offset = source_video_duration  # Skip this much of the audio
        continuation._original_segment_id = original_segment.id

        return continuation

    async def _prepare_continuation_segment(self, segment: Segment) -> Segment:
        """
        Prepare a continuation segment by trimming audio and adjusting subtitles.

        The continuation needs:
        1. Audio trimmed to start at the offset point
        2. Subtitles time-shifted to start at 0
        """
        if not hasattr(segment, '_is_continuation') or not segment._is_continuation:
            return segment

        audio_offset = getattr(segment, '_audio_offset', 0)
        continuation_duration = segment.end_time - segment.start_time

        # Trim audio for continuation
        if segment.audio_path and os.path.exists(segment.audio_path):
            trimmed_audio = await self._trim_audio_for_continuation(
                segment.audio_path,
                audio_offset,
                continuation_duration
            )
            if trimmed_audio:
                segment.audio_path = trimmed_audio
                logger.info(f"Trimmed audio for continuation: offset={audio_offset:.1f}s, duration={continuation_duration:.1f}s")

        # Adjust subtitle timing for continuation
        if segment.subtitle_path and os.path.exists(segment.subtitle_path):
            adjusted_subtitle = await self._adjust_subtitle_for_continuation(
                segment.subtitle_path,
                audio_offset,
                continuation_duration
            )
            if adjusted_subtitle:
                segment.subtitle_path = adjusted_subtitle
                logger.info(f"Adjusted subtitles for continuation")

        return segment

    async def _trim_audio_for_continuation(
        self,
        audio_path: str,
        start_offset: float,
        duration: float
    ) -> Optional[str]:
        """
        Trim audio file to extract the continuation portion.
        Uses FFmpeg -ss (seek) and -t (duration).
        """
        try:
            output_path = self.temp_dir / f"continuation_audio_{uuid4().hex[:8]}.mp3"

            # Use FFmpeg to extract the audio portion
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start_offset),
                '-i', audio_path,
                '-t', str(duration),
                '-acodec', 'libmp3lame',
                '-q:a', '2',
                str(output_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            if process.returncode == 0 and output_path.exists():
                return str(output_path)
            else:
                logger.warning(f"Failed to trim audio for continuation")
                return None

        except Exception as e:
            logger.error(f"Error trimming audio for continuation: {e}")
            return None

    async def _adjust_subtitle_for_continuation(
        self,
        subtitle_path: str,
        start_offset: float,
        duration: float
    ) -> Optional[str]:
        """
        Adjust subtitle file timing for continuation segment.

        The continuation portion of subtitles starts mid-way through the original,
        so we need to:
        1. Filter to only subtitles after start_offset
        2. Shift their timing to start at 0
        """
        try:
            output_path = self.temp_dir / f"continuation_subtitle_{uuid4().hex[:8]}.srt"

            # Read original subtitle
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse and adjust SRT timing
            adjusted_lines = []
            subtitle_blocks = content.strip().split('\n\n')

            for block in subtitle_blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # Parse timing line (format: 00:00:00,000 --> 00:00:00,000)
                    timing_line = lines[1]
                    try:
                        start_str, end_str = timing_line.split(' --> ')
                        start_secs = self._srt_time_to_seconds(start_str)
                        end_secs = self._srt_time_to_seconds(end_str)

                        # Check if this subtitle is in the continuation portion
                        if end_secs > start_offset:
                            # Adjust timing (shift back by start_offset)
                            new_start = max(0, start_secs - start_offset)
                            new_end = min(duration, end_secs - start_offset)

                            if new_end > new_start:
                                # Rebuild block with adjusted timing
                                adjusted_lines.append(lines[0])  # Index
                                adjusted_lines.append(
                                    f"{self._seconds_to_srt_time(new_start)} --> {self._seconds_to_srt_time(new_end)}"
                                )
                                adjusted_lines.extend(lines[2:])  # Text
                                adjusted_lines.append('')  # Blank line separator
                    except Exception as e:
                        logger.warning(f"Could not parse subtitle timing: {e}")
                        continue

            if adjusted_lines:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(adjusted_lines))
                return str(output_path)
            else:
                logger.warning("No subtitles in continuation range")
                return None

        except Exception as e:
            logger.error(f"Error adjusting subtitle for continuation: {e}")
            return None

    def _srt_time_to_seconds(self, time_str: str) -> float:
        """Convert SRT time format (00:00:00,000) to seconds"""
        time_str = time_str.strip().replace(',', '.')
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (00:00:00,000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

    async def export(
        self,
        output_path: str,
        quality: str = "balanced",
        include_subtitles: bool = True,
        background_music_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        detailed_callback: Optional[Callable[[dict], Any]] = None,
        user_tier: str = "free_trial"
    ) -> bool:
        """
        Export final video with voice-overs and subtitles

        Process:
        1. Generate all TTS audio (if not cached)
        2. Process each segment
        3. Combine segments
        4. Add background music (optional)
        5. Apply watermark (for free tier users)

        Args:
            output_path: Path to save the final video
            quality: Quality preset (lossless, high, balanced)
            include_subtitles: Whether to burn subtitles into video
            background_music_path: Optional path to background music file
            progress_callback: Callback function(message: str, progress: int)
            detailed_callback: Detailed async callback for FFmpeg progress with ETA
            user_tier: User's subscription tier (REQUIRED for watermark logic)

        Returns:
            True if export successful, False otherwise

        Raises:
            ValueError: If user_tier is not provided
        """
        # SECURITY: user_tier is REQUIRED to ensure proper watermark enforcement
        if not user_tier:
            raise ValueError("user_tier is required for export. Cannot export without knowing user subscription tier.")

        import sys

        # Initialize temp file tracking for cleanup on failure
        # These are set to None and populated as export progresses
        preprocessed_video_path = None
        segment_videos = []
        combined_path = None
        active_video = None
        original_video_path = None

        try:
            logger.info(f"Starting export: {output_path}")
            print(f"[DEBUG] export() started for {output_path}", file=sys.stderr, flush=True)

            # Step 0: Preprocess video if it has no audio
            # Add silent audio track to ensure compatibility with TTS/BGM
            active_video = self.project.get_active_video()
            if not active_video:
                logger.error("No active video found")
                return False

            original_video_path = active_video.path

            if not FFmpegUtils.has_audio_stream(original_video_path):
                if progress_callback:
                    progress_callback("Preprocessing video (adding silent audio track)...", 0)

                logger.warning("Video has no audio track - adding silent audio for TTS compatibility")
                preprocessed_video_path = self.temp_dir / f"preprocessed_{active_video.id}.mp4"

                success = FFmpegUtils.add_silent_audio_track(
                    original_video_path,
                    str(preprocessed_video_path)
                )

                if success:
                    # Temporarily modify video path for export
                    active_video.path = str(preprocessed_video_path)
                    logger.info("✅ Video preprocessed with silent audio track")
                else:
                    logger.error("Failed to add silent audio track, continuing with original video")
                    preprocessed_video_path = None

            # Step 1: Ensure all required fonts are available
            if include_subtitles:
                if progress_callback:
                    progress_callback("Checking font availability...", 2)
                self._ensure_fonts_available()

            # Step 2: Generate all TTS audio
            if progress_callback:
                progress_callback("Generating audio for segments...", 5)

            await self._generate_all_audio(progress_callback)

            # Step 3: Process each segment
            print(f"[DEBUG] Step 3: Processing segments", file=sys.stderr, flush=True)
            if progress_callback:
                progress_callback("Processing video segments...", 30)

            segment_videos = await self._process_segments(
                include_subtitles,
                quality,
                progress_callback
            )
            print(f"[DEBUG] _process_segments returned {len(segment_videos) if segment_videos else 0} videos", file=sys.stderr, flush=True)

            if not segment_videos:
                logger.error("No segments processed")
                return False

            # Step 4: Combine segments
            if progress_callback:
                progress_callback("Combining video segments...", 70)

            combined_path = self.temp_dir / f"combined_{self.project.name}.mp4"

            # Create async progress callback for concatenation
            async def concat_progress(info: dict):
                if detailed_callback:
                    await detailed_callback({
                        'stage': 'concatenating',
                        'message': f"Combining segments: {info['progress']}%",
                        'progress': 70 + int(info['progress'] * 0.15),  # 70-85%
                        'detail': f"ETA: {info.get('eta_formatted', 'calculating...')}",
                        'ffmpeg_progress': info
                    })
                if progress_callback:
                    progress_callback(f"Combining: {info['progress']}% (ETA: {info.get('eta_formatted', '...')})", 70 + int(info['progress'] * 0.15))

            success = await FFmpegUtils.concatenate_videos_async(
                segment_videos,
                str(combined_path),
                concat_progress
            )

            if not success:
                logger.error("Failed to concatenate segments")
                return False

            # Step 5: Add background music (optional)
            # First, check if we have multi-BGM tracks in the project
            has_bgm_tracks = hasattr(self.project, 'bgm_tracks') and len(self.project.bgm_tracks) > 0

            if has_bgm_tracks:
                # Use new multi-BGM track system
                if progress_callback:
                    progress_callback(f"Adding {len(self.project.bgm_tracks)} background music track(s)...", 85)

                video_duration = FFmpegUtils.get_media_duration(str(combined_path))

                # Create async progress callback for BGM mixing
                async def bgm_progress(info: dict):
                    if detailed_callback:
                        await detailed_callback({
                            'stage': 'bgm',
                            'message': f"Adding background music: {info['progress']}%",
                            'progress': 85 + int(info['progress'] * 0.12),  # 85-97%
                            'detail': f"ETA: {info.get('eta_formatted', 'calculating...')}",
                            'ffmpeg_progress': info
                        })
                    if progress_callback:
                        progress_callback(f"Adding BGM: {info['progress']}% (ETA: {info.get('eta_formatted', '...')})", 85 + int(info['progress'] * 0.12))

                success = await FFmpegUtils.add_multiple_bgm_tracks_async(
                    str(combined_path),
                    self.project.bgm_tracks,
                    output_path,
                    video_duration,
                    global_tts_volume=getattr(self.project, 'tts_volume', 100),
                    global_bgm_volume=getattr(self.project, 'bgm_volume', 100),
                    progress_callback=bgm_progress
                )

                if not success:
                    return False
            elif background_music_path and os.path.exists(background_music_path):
                # Legacy single BGM path
                if progress_callback:
                    progress_callback("Adding background music...", 85)

                # Create async progress callback for BGM mixing
                async def legacy_bgm_progress(info: dict):
                    if detailed_callback:
                        await detailed_callback({
                            'stage': 'bgm',
                            'message': f"Adding background music: {info['progress']}%",
                            'progress': 85 + int(info['progress'] * 0.12),  # 85-97%
                            'detail': f"ETA: {info.get('eta_formatted', 'calculating...')}",
                            'ffmpeg_progress': info
                        })
                    if progress_callback:
                        progress_callback(f"Adding BGM: {info['progress']}% (ETA: {info.get('eta_formatted', '...')})", 85 + int(info['progress'] * 0.12))

                success = await FFmpegUtils.add_background_music_async(
                    str(combined_path),
                    background_music_path,
                    output_path,
                    tts_boost=15,  # Boost TTS to make it clearly audible
                    bgm_reduction=20,  # Reduce BGM for better speech clarity
                    fade_duration=3.0,
                    progress_callback=legacy_bgm_progress
                )

                if not success:
                    return False
            else:
                # Just copy combined to output
                import shutil
                shutil.copy(combined_path, output_path)

            # Step 5: Apply watermark for free tier users (if applicable)
            # This is a POST-PROCESSING step that does NOT modify any existing FFmpeg commands
            if user_tier:
                watermark_service = get_watermark_service()
                if watermark_service.should_add_watermark(user_tier):
                    if progress_callback:
                        progress_callback("Applying watermark...", 95)

                    logger.info(f"Applying watermark for tier: {user_tier}")

                    # Rename output to temp for watermarking
                    temp_prewatermark = output_path + ".prewatermark.mp4"
                    try:
                        os.rename(output_path, temp_prewatermark)

                        # Apply watermark with matching quality settings
                        success, message = await watermark_service.add_watermark(
                            input_path=temp_prewatermark,
                            output_path=output_path,
                            tier=user_tier,
                            quality=quality  # Preserve export quality
                        )

                        if success:
                            logger.info("Watermark applied successfully")
                            # Cleanup temp file
                            if os.path.exists(temp_prewatermark):
                                os.unlink(temp_prewatermark)
                        else:
                            # SECURITY: Watermark REQUIRED for free tier - fail export if watermark fails
                            # Do NOT allow unwatermarked exports for free tier users
                            logger.error(f"CRITICAL: Watermark failed for tier {user_tier}: {message}")
                            # Cleanup both files - do not leave unwatermarked video
                            if os.path.exists(temp_prewatermark):
                                os.unlink(temp_prewatermark)
                            if os.path.exists(output_path):
                                os.unlink(output_path)
                            raise RuntimeError(
                                f"Export failed: Watermark required for {user_tier} tier but watermark application failed. "
                                f"Reason: {message}"
                            )

                    except RuntimeError:
                        # Re-raise our own RuntimeError for watermark failure
                        raise
                    except Exception as e:
                        # SECURITY: Watermark REQUIRED - fail export if any error occurs
                        logger.error(f"CRITICAL: Watermark error for tier {user_tier}: {e}")
                        # Cleanup both files - do not leave unwatermarked video
                        if os.path.exists(temp_prewatermark):
                            os.unlink(temp_prewatermark)
                        if os.path.exists(output_path):
                            os.unlink(output_path)
                        raise RuntimeError(
                            f"Export failed: Watermark required for {user_tier} tier but an error occurred. "
                            f"Error: {e}"
                        )

            if progress_callback:
                progress_callback("Export complete!", 100)

            # Cleanup temp files
            self._cleanup_temp_files(segment_videos, combined_path)

            # Cleanup preprocessed video if created
            if preprocessed_video_path and os.path.exists(preprocessed_video_path):
                try:
                    os.unlink(preprocessed_video_path)
                    logger.info("Cleaned up preprocessed video file")
                except Exception as e:
                    logger.warning(f"Could not delete preprocessed video: {e}")

            # Restore original video path
            active_video.path = original_video_path

            logger.info(f"Export completed: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Export failed: {e}")

            # Restore original video path on error
            if active_video and original_video_path:
                active_video.path = original_video_path

            # COMPREHENSIVE CLEANUP: Remove ALL temp files to prevent disk fill-up
            # Each failed export can leave 500MB-2GB of temp files

            # 1. Cleanup preprocessed video
            if preprocessed_video_path and os.path.exists(str(preprocessed_video_path)):
                try:
                    os.unlink(str(preprocessed_video_path))
                    logger.info("Cleaned up preprocessed video on failure")
                except Exception as cleanup_err:
                    logger.warning(f"Could not delete preprocessed video: {cleanup_err}")

            # 2. Cleanup segment videos
            if segment_videos:
                for video_path in segment_videos:
                    try:
                        if video_path and os.path.exists(video_path):
                            os.unlink(video_path)
                    except Exception as cleanup_err:
                        logger.warning(f"Could not delete segment video {video_path}: {cleanup_err}")
                logger.info(f"Cleaned up {len(segment_videos)} segment videos on failure")

            # 3. Cleanup combined path
            if combined_path and os.path.exists(str(combined_path)):
                try:
                    os.unlink(str(combined_path))
                    logger.info("Cleaned up combined video on failure")
                except Exception as cleanup_err:
                    logger.warning(f"Could not delete combined video: {cleanup_err}")

            # 4. Cleanup any partial output file
            if output_path and os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                    logger.info("Cleaned up partial output file on failure")
                except Exception as cleanup_err:
                    logger.warning(f"Could not delete partial output: {cleanup_err}")

            # 5. Cleanup any prewatermark temp file
            prewatermark_path = output_path + ".prewatermark.mp4" if output_path else None
            if prewatermark_path and os.path.exists(prewatermark_path):
                try:
                    os.unlink(prewatermark_path)
                    logger.info("Cleaned up prewatermark temp file on failure")
                except Exception as cleanup_err:
                    logger.warning(f"Could not delete prewatermark file: {cleanup_err}")

            if progress_callback:
                progress_callback(f"Export failed: {e}", 0)
            return False

    async def _generate_all_audio(self, progress_callback: Optional[Callable]):
        """Generate TTS audio for all segments"""
        total = len(self.project.timeline.segments)

        # Get video orientation for subtitle chunking
        # In multi-video projects, get orientation from the segment's video
        # In single-video projects, get from the active video
        active_video = self.project.get_active_video()
        default_orientation = active_video.orientation if active_video and active_video.orientation else 'horizontal'

        for i, segment in enumerate(self.project.timeline.segments):
            # Check if audio already exists
            if segment.audio_path and os.path.exists(segment.audio_path):
                # Audio exists - check if subtitle needs to be generated
                subtitle_missing = not segment.subtitle_path or not os.path.exists(segment.subtitle_path)

                if subtitle_missing and segment.subtitle_enabled:
                    # Generate missing subtitle for existing audio
                    logger.info(f"Generating missing subtitle for cached audio: {segment.name}")
                    try:
                        # Determine orientation for this segment
                        segment_orientation = default_orientation
                        if hasattr(segment, 'video_id') and segment.video_id:
                            segment_video = self.project.get_video(segment.video_id)
                            if segment_video and segment_video.orientation:
                                segment_orientation = segment_video.orientation

                        # Get audio duration for fallback subtitle generation
                        audio_duration = FFmpegUtils.get_media_duration(segment.audio_path) or 10.0

                        # Generate subtitle path
                        audio_path_obj = Path(segment.audio_path)
                        subtitle_path = audio_path_obj.with_suffix('.srt')

                        # Use fallback subtitle generation (estimated timing based on audio duration)
                        subtitle_content = self.tts_service._generate_accurate_subtitles_fallback(
                            segment.text, audio_duration, segment_orientation
                        )
                        subtitle_path.write_text(subtitle_content, encoding="utf-8")
                        segment.subtitle_path = str(subtitle_path)
                        logger.info(f"Generated fallback subtitle for cached audio: {segment.name}")
                    except Exception as e:
                        logger.warning(f"Failed to generate subtitle for cached audio {segment.name}: {e}")
                else:
                    logger.info(f"Using cached audio for segment: {segment.name}")
                continue

            logger.info(f"Generating audio for segment: {segment.name}")

            # Determine orientation for this segment
            # If segment has video_id, look up that video's orientation
            segment_orientation = default_orientation
            if hasattr(segment, 'video_id') and segment.video_id:
                segment_video = self.project.get_video(segment.video_id)
                if segment_video and segment_video.orientation:
                    segment_orientation = segment_video.orientation
                    logger.info(f"Using {segment_orientation} orientation for segment subtitle chunking")

            try:
                # Generate audio using TTS service (supports voice cloning)
                # Pass orientation to adjust subtitle formatting
                audio_path, subtitle_path = await self.tts_service.generate_audio_with_provider(
                    text=segment.text,
                    language=segment.language,
                    voice=segment.voice_id,
                    project_name=self.project.name,
                    segment_name=segment.name.replace(" ", "_"),
                    rate=segment.rate,
                    volume=segment.volume,
                    pitch=segment.pitch,
                    orientation=segment_orientation,
                    voice_sample_id=getattr(segment, 'voice_sample_id', None),
                )

                segment.audio_path = audio_path
                segment.subtitle_path = subtitle_path

                logger.info(f"Generated audio: {audio_path}")

            except Exception as e:
                logger.error(f"Failed to generate audio for segment {segment.name}: {e}")
                raise

            if progress_callback:
                progress = int(30 * (i + 1) / total)
                progress_callback(f"Generated audio {i+1}/{total}", progress)

    async def _process_segments(
        self,
        include_subtitles: bool,
        quality: str,
        progress_callback: Optional[Callable]
    ) -> List[str]:
        """
        Process video with voice-over segments while preserving full video

        Strategy:
        1. Split video into parts (before segment, segment, after segment, etc.)
        2. Process only segment parts with audio/subtitles
        3. Keep other parts untouched
        4. Concatenate all parts to create full output
        """
        import sys
        print(f"[DEBUG] _process_segments started", file=sys.stderr, flush=True)

        # Get video duration
        print(f"[DEBUG] Getting video duration for: {self.project.video_path}", file=sys.stderr, flush=True)
        video_duration = FFmpegUtils.get_media_duration(self.project.video_path)
        print(f"[DEBUG] Video duration: {video_duration}", file=sys.stderr, flush=True)
        if not video_duration:
            logger.error("Could not get video duration")
            return []

        # Validate audio lengths and get user confirmation if needed
        await self._validate_audio_lengths(video_duration)

        # Sort segments by start time
        sorted_segments = sorted(self.project.timeline.segments, key=lambda s: s.start_time)
        print(f"[DEBUG] Processing {len(sorted_segments)} segments", file=sys.stderr, flush=True)

        all_parts = []
        current_time = 0.0
        total = len(sorted_segments)

        # Process each segment and gaps between them
        for i, segment in enumerate(sorted_segments):
            # Handle cross-video segments: truncate end_time to video duration
            effective_end_time = segment.end_time
            if getattr(segment, 'extends_to_next_video', False) and segment.end_time > video_duration:
                effective_end_time = video_duration
                logger.info(f"Truncating cross-video segment '{segment.name}' to video duration: {video_duration:.1f}s")

            print(f"[DEBUG] Processing segment {i+1}/{total}: {segment.name} ({segment.start_time}s - {effective_end_time}s)", file=sys.stderr, flush=True)
            # Extract part BEFORE segment (if any gap exists)
            if current_time < segment.start_time:
                gap_duration = segment.start_time - current_time
                logger.info(f"Extracting pre-segment part: {current_time}s - {segment.start_time}s ({gap_duration:.1f}s)")
                print(f"[DEBUG] Extracting pre-segment: {current_time}s - {segment.start_time}s", file=sys.stderr, flush=True)
                part_path = self.temp_dir / f"part_before_{i}.mp4"
                # Use async version to avoid blocking the event loop
                # Use stream copy (fast) for gap segments - they don't need audio/subtitle processing
                success = await FFmpegUtils.extract_video_segment_async(
                    self.project.video_path,
                    current_time,
                    segment.start_time,
                    str(part_path),
                    re_encode=False  # Use stream copy for speed - no audio/subtitle changes needed
                )
                print(f"[DEBUG] Pre-segment extraction: {success}", file=sys.stderr, flush=True)
                if success:
                    all_parts.append(str(part_path))

            # Process the SEGMENT with audio and subtitles
            logger.info(f"Processing segment: {segment.name}")
            print(f"[DEBUG] Extracting segment video: {segment.start_time}s - {effective_end_time}s", file=sys.stderr, flush=True)

            try:
                # Extract video segment using async version
                # Note: We don't re-encode here because it will be processed with audio/subtitles
                segment_video_path = self.temp_dir / f"segment_{i}_video.mp4"
                success = await FFmpegUtils.extract_video_segment_async(
                    self.project.video_path,
                    segment.start_time,
                    effective_end_time,  # Use effective end time for cross-video segments
                    str(segment_video_path),
                    re_encode=False  # Will be re-encoded during process_segment_video
                )
                print(f"[DEBUG] Segment extraction: {success}", file=sys.stderr, flush=True)

                if not success:
                    logger.error(f"Failed to extract segment: {segment.name}")
                    continue

                # Prepare subtitle file if needed
                subtitle_path = None
                if include_subtitles and segment.subtitle_enabled and segment.subtitle_path:
                    ass_path = segment.subtitle_path.replace('.srt', '.ass')
                    style_options = self._get_subtitle_style(segment)
                    success = SubtitleUtils.create_custom_ass_style(
                        segment.subtitle_path,
                        ass_path,
                        style_options
                    )
                    if success:
                        subtitle_path = ass_path
                    else:
                        logger.warning(f"Failed to style subtitles for segment: {segment.name}")

                # Process segment with audio and subtitles using async version
                processed_video_path = self.temp_dir / f"segment_{i}_processed.mp4"

                # Calculate segment duration (use effective end time for cross-video segments)
                segment_duration = effective_end_time - segment.start_time
                print(f"[DEBUG] Calling process_segment_video_async for {segment.name}", file=sys.stderr, flush=True)

                success = await FFmpegUtils.process_segment_video_async(
                    str(segment_video_path),
                    segment.audio_path,
                    subtitle_path,
                    str(processed_video_path),
                    quality,
                    segment_duration  # Pass expected duration
                )
                print(f"[DEBUG] process_segment_video_async returned: {success}", file=sys.stderr, flush=True)

                if success:
                    all_parts.append(str(processed_video_path))
                    logger.info(f"Processed segment: {segment.name}")
                else:
                    logger.error(f"Failed to process segment: {segment.name}")

            except Exception as e:
                logger.error(f"Error processing segment {segment.name}: {e}")

            # Update current time (use effective end time for cross-video segments)
            current_time = effective_end_time

            if progress_callback:
                progress = 30 + int(40 * (i + 1) / total)
                progress_callback(f"Processed segment {i+1}/{total}", progress)

        # Extract part AFTER last segment (if any remaining video)
        if current_time < video_duration:
            remaining_duration = video_duration - current_time
            logger.info(f"Extracting post-segment part: {current_time}s - {video_duration}s ({remaining_duration:.1f}s)")
            print(f"[DEBUG] Extracting post-segment: {current_time}s - {video_duration}s", file=sys.stderr, flush=True)
            part_path = self.temp_dir / f"part_after_last.mp4"
            # Use async version for post-segment - no audio/subtitle changes needed
            success = await FFmpegUtils.extract_video_segment_async(
                self.project.video_path,
                current_time,
                video_duration,
                str(part_path),
                re_encode=False  # Use stream copy for speed
            )
            print(f"[DEBUG] Post-segment extraction: {success}", file=sys.stderr, flush=True)
            if success:
                all_parts.append(str(part_path))

        return all_parts

    async def _validate_audio_lengths(self, video_duration: float):
        """
        Validate that audio lengths are appropriate for their segments
        Automatically extend segments when possible to fit audio
        """
        sorted_segments = sorted(self.project.timeline.segments, key=lambda s: s.start_time)

        for i, segment in enumerate(sorted_segments):
            if not segment.audio_path or not os.path.exists(segment.audio_path):
                continue

            audio_duration = FFmpegUtils.get_media_duration(segment.audio_path)
            if not audio_duration:
                continue

            segment_duration = segment.end_time - segment.start_time

            # Check if audio is significantly longer than segment
            if audio_duration > segment_duration + 1.0:  # 1 second tolerance
                # Calculate how much we need to extend
                needed_duration = audio_duration
                new_end_time = segment.start_time + needed_duration

                # Check if we can extend
                can_extend = False
                max_allowed_end = video_duration

                # If not the last segment, check gap to next segment
                if i < len(sorted_segments) - 1:
                    next_segment = sorted_segments[i + 1]
                    max_allowed_end = next_segment.start_time

                # Check if extension fits
                if new_end_time <= max_allowed_end:
                    can_extend = True

                if can_extend:
                    # EXTEND THE SEGMENT AUTOMATICALLY
                    old_end = segment.end_time
                    segment.end_time = new_end_time

                    logger.warning(
                        f"Audio length mismatch in segment '{segment.name}': "
                        f"Audio={audio_duration:.1f}s, Original Segment={segment_duration:.1f}s"
                    )
                    logger.info(
                        f"✓ Auto-extended segment '{segment.name}' from "
                        f"{old_end:.1f}s to {new_end_time:.1f}s to fit audio"
                    )

                    # Save the project with updated segment
                    self.project.save()
                else:
                    # Cannot extend - audio will be truncated
                    logger.warning(
                        f"Audio length mismatch in segment '{segment.name}': "
                        f"Audio={audio_duration:.1f}s, Segment={segment_duration:.1f}s"
                    )
                    logger.warning(
                        f"⚠ Cannot extend segment - would overlap with next segment or exceed video. "
                        f"Audio will be TRUNCATED to {segment_duration:.1f}s"
                    )
                    logger.info(
                        f"  Tip: Shorten the text for segment '{segment.name}' or adjust segment times"
                    )

    def _ensure_fonts_available(self):
        """
        Ensure all fonts used in segments are available on the system
        Downloads and installs fonts from Google Fonts if needed
        """
        # Collect unique fonts used in segments
        required_fonts = set()
        for segment in self.project.timeline.segments:
            if segment.subtitle_enabled and segment.subtitle_font:
                required_fonts.add(segment.subtitle_font)

        if not required_fonts:
            logger.info("No custom fonts required for subtitles")
            return

        logger.info(f"Checking availability of {len(required_fonts)} font(s)...")

        # Ensure each font is available
        for font_name in required_fonts:
            try:
                FontManager.ensure_font_available(font_name)
            except Exception as e:
                logger.warning(f"Could not ensure font '{font_name}' is available: {e}")
                logger.warning(f"Video will use system default font instead of '{font_name}'")

    def _get_subtitle_style(self, segment) -> dict:
        """Get subtitle style options for segment"""
        # Start with default style for language
        style = SubtitleUtils.get_default_style_for_language(segment.language)

        # Override with segment-specific settings
        style['fontname'] = segment.subtitle_font
        style['fontsize'] = str(segment.subtitle_size)
        style['primarycolour'] = segment.subtitle_color
        style['marginv'] = str(segment.subtitle_position)

        # Apply border/outline settings if available
        if hasattr(segment, 'subtitle_border_enabled'):
            if segment.subtitle_border_enabled:
                style['borderstyle'] = str(segment.subtitle_border_style)
                style['outline'] = str(segment.subtitle_outline_width)
                style['outlinecolour'] = segment.subtitle_outline_color
                style['shadow'] = str(segment.subtitle_shadow)
                # Shadow color (backcolour in ASS is used for shadow when borderstyle=1)
                if hasattr(segment, 'subtitle_shadow_color') and segment.subtitle_shadow > 0:
                    style['backcolour'] = segment.subtitle_shadow_color
            else:
                # No border/outline - use opaque box background for visibility
                # borderstyle=3 creates a background box without outline
                style['borderstyle'] = '3'
                style['outline'] = '0'
                style['shadow'] = '0'
                # Ensure semi-transparent background for contrast
                style['backcolour'] = '&H80000000'  # Semi-transparent black

        return style

    def _cleanup_temp_files(self, segment_videos: List[str], combined_path: Path):
        """Clean up temporary files"""
        try:
            # Clean up segment videos
            for video_path in segment_videos:
                try:
                    if os.path.exists(video_path):
                        os.unlink(video_path)
                except Exception as e:
                    logger.warning(f"Could not delete temp file {video_path}: {e}")

            # Clean up combined video
            try:
                if combined_path.exists():
                    os.unlink(combined_path)
            except Exception as e:
                logger.warning(f"Could not delete combined file: {e}")

            logger.info("Cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def generate_preview(
        self,
        segment_index: int,
        output_path: str
    ) -> bool:
        """Generate a preview for a single segment"""
        try:
            if segment_index < 0 or segment_index >= len(self.project.timeline.segments):
                logger.error(f"Invalid segment index: {segment_index}")
                return False

            segment = self.project.timeline.segments[segment_index]

            # Generate audio if not already done
            if not segment.audio_path or not os.path.exists(segment.audio_path):
                # Get video orientation for subtitle chunking
                active_video = self.project.get_active_video()
                orientation = active_video.orientation if active_video and active_video.orientation else 'horizontal'

                audio_path, subtitle_path = await self.tts_service.generate_audio_with_provider(
                    text=segment.text,
                    language=segment.language,
                    voice=segment.voice_id,
                    project_name=self.project.name,
                    segment_name=f"preview_{segment.name}",
                    rate=segment.rate,
                    volume=segment.volume,
                    pitch=segment.pitch,
                    orientation=orientation,
                    voice_sample_id=getattr(segment, 'voice_sample_id', None),
                )
                segment.audio_path = audio_path
                segment.subtitle_path = subtitle_path

            # Extract video segment using async version
            segment_video = self.temp_dir / f"preview_segment.mp4"
            await FFmpegUtils.extract_video_segment_async(
                self.project.video_path,
                segment.start_time,
                segment.end_time,
                str(segment_video)
            )

            # Process with audio and subtitles
            subtitle_path = None
            if segment.subtitle_enabled and segment.subtitle_path:
                ass_path = segment.subtitle_path.replace('.srt', '.ass')
                style_options = self._get_subtitle_style(segment)
                SubtitleUtils.create_custom_ass_style(
                    segment.subtitle_path,
                    ass_path,
                    style_options
                )
                subtitle_path = ass_path

            success = await FFmpegUtils.process_segment_video_async(
                str(segment_video),
                segment.audio_path,
                subtitle_path,
                output_path,
                "balanced"
            )

            logger.info(f"Preview generated: {output_path}")
            return success

        except Exception as e:
            logger.error(f"Failed to generate preview: {e}")
            return False

    async def export_single_video(
        self,
        video: Video,
        output_path: str,
        quality: str = "balanced",
        include_subtitles: bool = True,
        background_music_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        detailed_callback: Optional[Callable[[dict], Any]] = None,
        user_tier: str = "free_trial"
    ) -> bool:
        """
        Export a single video from a multi-video project

        Args:
            video: Video instance to export
            output_path: Path to save the exported video
            quality: Quality preset
            include_subtitles: Whether to burn subtitles
            background_music_path: Optional background music
            progress_callback: Progress callback
            detailed_callback: Detailed async callback for FFmpeg progress with ETA
            user_tier: User's subscription tier (REQUIRED for watermark enforcement)

        Returns:
            True if successful

        Raises:
            ValueError: If user_tier is not provided
        """
        # SECURITY: user_tier is REQUIRED to ensure proper watermark enforcement
        if not user_tier:
            raise ValueError("user_tier is required for export. Cannot export without knowing user subscription tier.")

        import sys
        try:
            logger.info(f"Exporting single video: {video.name}")
            print(f"[DEBUG] export_single_video: {video.name}, path: {video.path}", file=sys.stderr, flush=True)
            print(f"[DEBUG] video has {len(video.timeline.segments) if video.timeline else 0} segments", file=sys.stderr, flush=True)

            # Get continuation segments from previous video (cross-video segments)
            continuation_segments = self._get_cross_video_continuations(video)
            original_segments = list(video.timeline.segments)  # Save original

            if continuation_segments:
                logger.info(f"Adding {len(continuation_segments)} continuation segment(s) to {video.name}")
                # Prepare each continuation segment (trim audio, adjust subtitles)
                for i, cont_seg in enumerate(continuation_segments):
                    prepared_seg = await self._prepare_continuation_segment(cont_seg)
                    continuation_segments[i] = prepared_seg

                # Inject continuation segments at the start of the timeline
                video.timeline.segments = continuation_segments + list(video.timeline.segments)
                print(f"[DEBUG] Injected {len(continuation_segments)} continuation segments", file=sys.stderr, flush=True)

            # Temporarily set this video as the only one in project for export
            original_videos = self.project.videos
            original_active = self.project.active_video_id

            self.project.videos = [video]
            self.project.active_video_id = video.id

            print(f"[DEBUG] Calling self.export() for {video.name}", file=sys.stderr, flush=True)
            # Use standard export with user_tier for watermark enforcement
            success = await self.export(
                output_path,
                quality,
                include_subtitles,
                background_music_path,
                progress_callback,
                user_tier=user_tier
            )

            # Restore original state
            self.project.videos = original_videos
            self.project.active_video_id = original_active

            # Restore original segments (remove continuation segments)
            if continuation_segments:
                video.timeline.segments = original_segments

            return success

        except Exception as e:
            logger.error(f"Failed to export single video: {e}")
            return False

    async def _process_visibility_segment(
        self,
        video: Video,
        vis_seg,  # VisibilitySegment from LayerCompositor
        compositor,  # LayerCompositor instance
        output_path: str,
        quality: str,
        include_subtitles: bool
    ) -> bool:
        """
        Process a single visibility segment from the compositor.

        This extracts the exact portion of the video that's visible on the timeline,
        processes any voice-over segments that fall within this range, and burns
        subtitles with correct timing.

        Args:
            video: The Video object
            vis_seg: VisibilitySegment from the compositor
            compositor: LayerCompositor instance for timing calculations
            output_path: Where to save the processed segment
            quality: Quality preset
            include_subtitles: Whether to burn subtitles

        Returns:
            True if successful
        """
        try:
            import sys
            print(f"[DEBUG] _process_visibility_segment: {video.name}, source={vis_seg.source_start:.2f}s-{vis_seg.source_end:.2f}s", file=sys.stderr, flush=True)

            # First, extract the exact portion we need from the source video
            segment_duration = vis_seg.source_end - vis_seg.source_start

            # In combined multi-video export, voice-overs are added AFTER concatenation
            # using compositor.segment_placements which have correct timeline positions.
            # This ensures cross-video segments are placed correctly.
            # Here we just extract the raw video portion.
            logger.info(f"Extracting raw video portion for visibility segment: {video.name}")
            return await self._extract_video_segment(
                video.path,
                vis_seg.source_start,
                vis_seg.source_end,
                output_path,
                quality
            )

        except Exception as e:
            logger.error(f"Failed to process visibility segment: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def _extract_video_segment(
        self,
        video_path: str,
        start: float,
        end: float,
        output_path: str,
        quality: str,
        target_fps: float = 30.0,
        target_width: int = 1920,
        target_height: int = 1080
    ) -> bool:
        """
        Extract a segment from a video without any voice-over processing.

        Uses filter_complex with trim/setpts for FRAME-ACCURATE extraction.
        This ensures:
        1. Exact cut points (not keyframe-dependent)
        2. Timestamps reset to 0 (for clean concatenation)
        3. Normalized frame rate and resolution
        4. Proper A/V sync
        """
        try:
            import sys
            duration = end - start

            logger.info(f"Extracting segment: {start:.3f}s - {end:.3f}s (duration: {duration:.3f}s)")
            print(f"[DEBUG] _extract_video_segment: {video_path} [{start:.3f}s - {end:.3f}s]", file=sys.stderr, flush=True)

            # Get quality settings (with hardware acceleration if available)
            quality_settings = FFmpegUtils.get_quality_preset(quality)

            # Check if video has audio
            has_audio = FFmpegUtils.has_audio_stream(video_path)

            # Build filter_complex for frame-accurate extraction with timestamp reset
            # This uses trim/atrim with setpts/asetpts to ensure clean timestamps
            # Also normalizes frame rate and resolution for consistent concatenation

            # Video filter chain:
            # 1. trim: Extract exact time range (frame-accurate, not keyframe-dependent)
            # 2. setpts: Reset timestamps to start at 0
            # 3. fps: Normalize frame rate for consistent concatenation
            # 4. scale+pad: Normalize resolution with letterboxing
            # 5. setsar: Set sample aspect ratio to 1:1
            video_filter = (
                f"[0:v]trim=start={start:.6f}:end={end:.6f},"
                f"setpts=PTS-STARTPTS,"
                f"fps={target_fps},"
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1[outv]"
            )

            if has_audio:
                # Audio filter chain:
                # 1. atrim: Extract exact time range
                # 2. asetpts: Reset audio timestamps to start at 0
                # 3. aresample: Ensure consistent sample rate
                audio_filter = (
                    f"[0:a]atrim=start={start:.6f}:end={end:.6f},"
                    f"asetpts=PTS-STARTPTS,"
                    f"aresample=48000[outa]"
                )
                filter_complex = f"{video_filter};{audio_filter}"
                map_args = ['-map', '[outv]', '-map', '[outa]']
            else:
                # Generate silent audio for videos without audio track
                # This ensures all segments have consistent stream structure
                silent_audio = f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={duration:.6f}[outa]"
                filter_complex = f"{video_filter};{silent_audio}"
                map_args = ['-map', '[outv]', '-map', '[outa]']

            # Build video encoder arguments (handles both software and hardware encoders)
            video_encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

            cmd = [
                settings.FFMPEG_PATH,
                '-y',
                '-i', video_path,
                '-filter_complex', filter_complex,
                *map_args,
                *video_encoder_args,
                # Force first frame to be keyframe for clean segment boundaries
                '-force_key_frames', 'expr:eq(n,0)',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '48000',  # Consistent audio sample rate
                output_path
            ]

            print(f"[DEBUG] FFmpeg filter_complex: {filter_complex}", file=sys.stderr, flush=True)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                error_text = stderr.decode()[-500:] if stderr else "Unknown error"
                logger.error(f"FFmpeg segment extraction failed: {error_text}")
                print(f"[DEBUG] FFmpeg extraction failed: {error_text}", file=sys.stderr, flush=True)
                return False

            # Verify the output has correct duration and starts at 0
            output_duration = FFmpegUtils.get_media_duration(output_path)
            if output_duration:
                drift = abs(output_duration - duration)
                if drift > 0.1:  # More than 100ms drift
                    logger.warning(f"Duration drift detected: expected {duration:.3f}s, got {output_duration:.3f}s (drift: {drift:.3f}s)")
                else:
                    logger.info(f"Segment extracted successfully: {output_duration:.3f}s")

            return True

        except Exception as e:
            logger.error(f"Video segment extraction failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def _add_voiceovers_by_timeline(
        self,
        video_path: str,
        segment_placements: list,
        output_path: str,
        quality: str,
        include_subtitles: bool = True,
        video_start_offset: float = 0.0
    ) -> bool:
        """
        Add voice-over audio to a combined video based on timeline positions.

        This is used in multi-video export where voice-overs need to be placed
        at their correct timeline positions, not source positions.

        Args:
            video_path: Path to the combined video
            segment_placements: List of SegmentPlacement from LayerCompositor
            output_path: Path for output video with voice-overs
            quality: Quality preset
            include_subtitles: Whether to burn subtitles
            video_start_offset: The timeline start of the combined video (first visibility segment)

        Returns:
            True if successful
        """
        try:
            import sys
            from core.layer_compositor import SegmentPlacement

            # Filter placements that have audio
            # SegmentPlacement has audio_path directly, not via a segment object
            placements_with_audio = []
            for placement in segment_placements:
                if placement.audio_path and os.path.exists(placement.audio_path):
                    placements_with_audio.append(placement)
                    logger.info(f"Voice-over: {placement.segment_name} at timeline {placement.timeline_start:.2f}s - {placement.timeline_end:.2f}s")

            if not placements_with_audio:
                logger.info("No voice-overs with audio to add")
                import shutil
                shutil.copy(video_path, output_path)
                return True

            # Get quality settings (with hardware acceleration if available)
            quality_settings = FFmpegUtils.get_quality_preset(quality)

            # Build FFmpeg command with multiple audio inputs
            # Input 0: Video file
            # Input 1+: Voice-over audio files
            input_args = ['-i', video_path]
            for placement in placements_with_audio:
                input_args.extend(['-i', placement.audio_path])

            # Build filter complex:
            # 1. Boost video audio
            # 2. Add delay to each voice-over to position at timeline time
            # 3. Mix all audio together
            filter_parts = []

            # Get video duration for reference
            video_duration = FFmpegUtils.get_media_duration(video_path) or 0
            logger.info(f"Combined video duration: {video_duration:.2f}s, timeline offset: {video_start_offset:.2f}s")

            # Boost original video audio
            filter_parts.append("[0:a]volume=0.7[video_audio]")

            # Process each voice-over
            audio_labels = ["[video_audio]"]
            for idx, placement in enumerate(placements_with_audio, 1):
                # Calculate delay in milliseconds
                # Subtract the video start offset since the combined video starts from that point
                adjusted_time = max(0, placement.timeline_start - video_start_offset)
                delay_ms = int(adjusted_time * 1000)

                # Get audio_offset for trimming (how much to skip from start of audio)
                # This is used for cross-video segments where part of the audio was already used
                audio_offset = getattr(placement, 'audio_offset', 0) or 0
                segment_duration = placement.timeline_end - placement.timeline_start

                logger.info(f"  Voice-over '{placement.segment_name}': timeline={placement.timeline_start:.3f}s, "
                           f"adjusted={adjusted_time:.3f}s, delay={delay_ms}ms, "
                           f"audio_offset={audio_offset:.3f}s, duration={segment_duration:.3f}s")

                # Build audio filter chain:
                # 1. atrim: Skip audio_offset and limit to segment duration
                # 2. asetpts: Reset timestamps after trim
                # 3. volume: Boost TTS audio
                # 4. adelay: Position at correct timeline time
                if audio_offset > 0.001:
                    # Trim from start and limit duration
                    trim_filter = f"atrim=start={audio_offset:.3f}:duration={segment_duration:.3f},asetpts=PTS-STARTPTS"
                else:
                    # Just limit duration
                    trim_filter = f"atrim=duration={segment_duration:.3f},asetpts=PTS-STARTPTS"

                filter_parts.append(
                    f"[{idx}:a]{trim_filter},volume=2.0,adelay={delay_ms}|{delay_ms}[vo{idx}]"
                )
                audio_labels.append(f"[vo{idx}]")

            # Mix all audio streams
            num_inputs = len(audio_labels)
            mix_inputs = "".join(audio_labels)
            filter_parts.append(f"{mix_inputs}amix=inputs={num_inputs}:duration=first:dropout_transition=0[aout]")

            filter_complex = ";".join(filter_parts)

            # Build video encoder arguments (handles both software and hardware encoders)
            video_encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

            # Build FFmpeg command
            cmd = [
                settings.FFMPEG_PATH,
                '-y',
                *input_args,
                '-filter_complex', filter_complex,
                '-map', '0:v',
                '-map', '[aout]',
                *video_encoder_args,
                '-c:a', 'aac',
                '-b:a', '192k',
                output_path
            ]

            logger.info(f"Adding {len(placements_with_audio)} voice-over(s) using timeline positions")
            print(f"[DEBUG] Voice-over filter: {filter_complex}", file=sys.stderr, flush=True)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"FFmpeg voice-over mixing failed: {stderr.decode()[-500:]}")
                return False

            logger.info("Voice-overs added successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to add voice-overs by timeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def _process_segment_with_voiceovers(
        self,
        video_path: str,
        source_start: float,
        source_end: float,
        voiceover_info: list,
        output_path: str,
        quality: str,
        include_subtitles: bool
    ) -> bool:
        """
        Process a video segment with voice-over audio and subtitles.

        This handles the complex case where we need to:
        1. Extract a specific portion of the video
        2. Mix in voice-over audio at the correct positions
        3. Burn subtitles with adjusted timing
        """
        try:
            import sys
            segment_duration = source_end - source_start

            # Build filter_complex for audio mixing
            filter_parts = []
            audio_inputs = []
            input_files = ['-ss', str(source_start), '-i', video_path, '-t', str(segment_duration)]
            audio_index = 1  # 0 is the video

            # Check if video has audio
            has_video_audio = FFmpegUtils.has_audio_stream(video_path)

            # Collect voice-over audio files
            for info in voiceover_info:
                seg = info['segment']
                if seg.audio_path and os.path.exists(seg.audio_path):
                    input_files.extend(['-i', seg.audio_path])
                    audio_inputs.append({
                        'index': audio_index,
                        'start': info['adjusted_start'],
                        'end': info['adjusted_end'],
                        'segment': seg
                    })
                    audio_index += 1

            if not audio_inputs:
                # No voice-over audio, just extract segment
                return await self._extract_video_segment(
                    video_path, source_start, source_end, output_path, quality
                )

            # Build audio mixing filter
            if has_video_audio:
                # Start with video's audio
                filter_parts.append(f"[0:a]volume=0.3[va]")  # Lower original audio

                # Mix in each voice-over with delay
                for i, ai in enumerate(audio_inputs):
                    delay_ms = int(ai['start'] * 1000)
                    filter_parts.append(
                        f"[{ai['index']}:a]adelay={delay_ms}|{delay_ms},apad=whole_dur={segment_duration}[vo{i}]"
                    )

                # Mix all together
                mix_inputs = "[va]" + "".join(f"[vo{i}]" for i in range(len(audio_inputs)))
                filter_parts.append(
                    f"{mix_inputs}amix=inputs={len(audio_inputs) + 1}:duration=first:dropout_transition=0[aout]"
                )
            else:
                # No video audio, mix only voice-overs
                for i, ai in enumerate(audio_inputs):
                    delay_ms = int(ai['start'] * 1000)
                    filter_parts.append(
                        f"[{ai['index']}:a]adelay={delay_ms}|{delay_ms},apad=whole_dur={segment_duration}[vo{i}]"
                    )

                mix_inputs = "".join(f"[vo{i}]" for i in range(len(audio_inputs)))
                filter_parts.append(
                    f"{mix_inputs}amix=inputs={len(audio_inputs)}:duration=longest[aout]"
                )

            # Handle subtitles
            subtitle_filter = ""
            if include_subtitles:
                for info in voiceover_info:
                    seg = info['segment']
                    if seg.subtitle_path and os.path.exists(seg.subtitle_path):
                        # We need to adjust subtitle timing
                        # Create adjusted subtitle file
                        adjusted_sub = await self._create_adjusted_subtitle(
                            seg.subtitle_path,
                            -info['adjusted_start'],  # Offset to shift
                            info['adjusted_start'],
                            info['adjusted_end']
                        )
                        if adjusted_sub:
                            escaped_path = adjusted_sub.replace("\\", "/").replace(":", "\\:")
                            subtitle_filter = f",subtitles='{escaped_path}'"
                            break  # Use first available subtitle for now

            # Build video filter
            video_filter = f"[0:v]setpts=PTS-STARTPTS{subtitle_filter}[vout]"
            filter_parts.insert(0, video_filter)

            filter_complex = ";".join(filter_parts)

            # Build FFmpeg command with hardware acceleration if available
            quality_settings = FFmpegUtils.get_quality_preset(quality)
            video_encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

            cmd = [
                settings.FFMPEG_PATH,
                '-y',
            ]
            cmd.extend(input_files)
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[vout]',
                '-map', '[aout]',
                *video_encoder_args,
                '-c:a', 'aac',
                '-b:a', '192k',
                '-t', str(segment_duration),
                output_path
            ])

            print(f"[DEBUG] FFmpeg command: {' '.join(cmd)}", file=sys.stderr, flush=True)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"FFmpeg segment processing failed: {stderr.decode()}")
                return False

            return True

        except Exception as e:
            logger.error(f"Segment with voiceovers processing failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def _create_adjusted_subtitle(
        self,
        subtitle_path: str,
        time_offset: float,
        clip_start: float,
        clip_end: float
    ) -> Optional[str]:
        """
        Create a subtitle file with adjusted timing for a video segment.

        For cross-video segments and visibility segments, subtitles need to be
        shifted to match the new position in the output video.

        Args:
            subtitle_path: Original subtitle file path (SRT or ASS)
            time_offset: Time offset to apply (negative = shift earlier)
            clip_start: Start of the visible range in the segment
            clip_end: End of the visible range in the segment

        Returns:
            Path to adjusted subtitle file or None on failure
        """
        try:
            if not os.path.exists(subtitle_path):
                logger.warning(f"Subtitle file not found: {subtitle_path}")
                return None

            # Determine subtitle format
            is_ass = subtitle_path.lower().endswith('.ass')
            output_path = self.temp_dir / f"adjusted_sub_{uuid4().hex[:8]}{'.ass' if is_ass else '.srt'}"

            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if is_ass:
                # Process ASS subtitle format
                adjusted_content = self._adjust_ass_timing(content, time_offset, clip_start, clip_end)
            else:
                # Process SRT subtitle format
                adjusted_content = self._adjust_srt_timing(content, time_offset, clip_start, clip_end)

            if adjusted_content:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(adjusted_content)
                logger.info(f"Created adjusted subtitle: {output_path}")
                return str(output_path)
            else:
                logger.warning("No subtitle content after adjustment")
                return None

        except Exception as e:
            logger.error(f"Failed to adjust subtitle: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _adjust_ass_timing(
        self,
        content: str,
        time_offset: float,
        clip_start: float,
        clip_end: float
    ) -> Optional[str]:
        """
        Adjust timing in ASS subtitle format.

        ASS format uses timing in format: H:MM:SS.CC (centiseconds)
        Example: Dialogue: 0,0:00:01.50,0:00:05.20,Default,,0,0,0,,Text here
        """
        import re

        lines = content.split('\n')
        adjusted_lines = []
        clip_duration = clip_end - clip_start

        for line in lines:
            # Check if this is a Dialogue line
            if line.startswith('Dialogue:'):
                # Parse ASS dialogue line
                # Format: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
                match = re.match(
                    r'(Dialogue:\s*\d+,)(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2})(,.+)',
                    line
                )
                if match:
                    prefix = match.group(1)
                    start_str = match.group(2)
                    end_str = match.group(3)
                    suffix = match.group(4)

                    # Convert ASS time to seconds
                    start_secs = self._ass_time_to_seconds(start_str)
                    end_secs = self._ass_time_to_seconds(end_str)

                    # Apply offset (shift by time_offset, which can be negative)
                    # time_offset is typically the negative of clip_start to shift subtitles
                    # to start at 0 in the output
                    new_start = start_secs + time_offset
                    new_end = end_secs + time_offset

                    # Clamp to clip range (0 to clip_duration in output space)
                    new_start = max(0, new_start)
                    new_end = min(clip_duration, new_end)

                    # Skip if subtitle is completely outside visible range
                    if new_end <= 0 or new_start >= clip_duration:
                        continue

                    # Convert back to ASS time format
                    new_start_str = self._seconds_to_ass_time(new_start)
                    new_end_str = self._seconds_to_ass_time(new_end)

                    adjusted_lines.append(f"{prefix}{new_start_str},{new_end_str}{suffix}")
                else:
                    # Couldn't parse, keep original
                    adjusted_lines.append(line)
            else:
                # Non-dialogue lines (style info, etc.) - keep as-is
                adjusted_lines.append(line)

        return '\n'.join(adjusted_lines)

    def _adjust_srt_timing(
        self,
        content: str,
        time_offset: float,
        clip_start: float,
        clip_end: float
    ) -> Optional[str]:
        """
        Adjust timing in SRT subtitle format.

        SRT format uses timing: HH:MM:SS,mmm --> HH:MM:SS,mmm
        """
        adjusted_lines = []
        subtitle_blocks = content.strip().split('\n\n')
        clip_duration = clip_end - clip_start
        new_index = 1

        for block in subtitle_blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 2:
                # First line is index (skip it, we'll renumber)
                # Second line is timing
                timing_line = lines[1] if len(lines) >= 2 else ""

                try:
                    start_str, end_str = timing_line.split(' --> ')
                    start_secs = self._srt_time_to_seconds(start_str)
                    end_secs = self._srt_time_to_seconds(end_str)

                    # Apply offset
                    new_start = start_secs + time_offset
                    new_end = end_secs + time_offset

                    # Clamp to clip range
                    new_start = max(0, new_start)
                    new_end = min(clip_duration, new_end)

                    # Skip if completely outside
                    if new_end <= 0 or new_start >= clip_duration:
                        continue

                    # Rebuild block with new timing
                    adjusted_lines.append(str(new_index))
                    adjusted_lines.append(
                        f"{self._seconds_to_srt_time(new_start)} --> {self._seconds_to_srt_time(new_end)}"
                    )
                    # Add text lines (everything after timing)
                    if len(lines) >= 3:
                        adjusted_lines.extend(lines[2:])
                    adjusted_lines.append('')  # Blank line between blocks

                    new_index += 1
                except Exception as e:
                    logger.warning(f"Could not parse SRT timing: {e}")
                    continue

        return '\n'.join(adjusted_lines)

    def _ass_time_to_seconds(self, time_str: str) -> float:
        """Convert ASS time format (H:MM:SS.CC) to seconds"""
        time_str = time_str.strip()
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        # Seconds can have centiseconds (e.g., 05.20)
        seconds_parts = parts[2].split('.')
        seconds = int(seconds_parts[0])
        centiseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
        return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0

    def _seconds_to_ass_time(self, seconds: float) -> str:
        """Convert seconds to ASS time format (H:MM:SS.CC)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        # ASS uses centiseconds (2 decimal places)
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    async def _concatenate_visibility_segments(
        self,
        segment_paths: List[str],
        output_path: str,
        quality: str
    ) -> bool:
        """
        Concatenate processed visibility segments into final video.

        Since segments are already normalized (same fps, resolution, codec, timestamps starting at 0),
        we use concat demuxer with stream copy for speed.

        If stream copy fails (edge case with incompatible streams), falls back to re-encoding.
        """
        try:
            import sys

            if len(segment_paths) == 1:
                # Just one segment, copy it
                import shutil
                shutil.copy(segment_paths[0], output_path)
                return True

            logger.info(f"Concatenating {len(segment_paths)} visibility segments")
            print(f"[DEBUG] Concatenating {len(segment_paths)} segments", file=sys.stderr, flush=True)

            # Create concat file with absolute paths
            concat_file = self.temp_dir.resolve() / f"concat_list_{uuid4().hex[:8]}.txt"
            with open(concat_file, 'w') as f:
                for path in segment_paths:
                    # Use absolute path and escape for concat demuxer
                    abs_path = str(Path(path).resolve())
                    escaped = abs_path.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            # First try: Stream copy (fast, lossless since segments are already encoded)
            # This works because _extract_video_segment now normalizes all segments to:
            # - Same frame rate (30fps by default)
            # - Same resolution (1920x1080 by default)
            # - Same codec (libx264)
            # - Timestamps starting at 0
            cmd_copy = [
                settings.FFMPEG_PATH,
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file.resolve()),
                '-c', 'copy',  # Stream copy - fast and lossless
                '-movflags', '+faststart',  # Enable progressive download
                output_path
            ]

            print(f"[DEBUG] Trying concat with stream copy...", file=sys.stderr, flush=True)

            process = await asyncio.create_subprocess_exec(
                *cmd_copy,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("Concatenation successful (stream copy)")

                # Verify output timestamps start at or near 0
                # Threshold of 0.1s (100ms) allows for small encoder delays from frame rate conversion
                # while still catching significant timestamp issues
                output_info = await self._verify_video_timestamps(output_path)
                video_start = output_info.get('video_start', 0) if output_info else 0
                if video_start < 0.1:
                    if video_start > 0.01:
                        logger.info(f"Stream copy output has small start offset: {video_start:.3f}s (acceptable)")
                    # Cleanup concat file
                    try:
                        os.remove(str(concat_file))
                    except:
                        pass
                    return True
                else:
                    logger.warning(f"Output has significant non-zero start time ({video_start:.3f}s), re-encoding to fix...")

            # Fallback: Re-encode if stream copy failed or produced bad timestamps
            logger.warning("Stream copy failed or produced bad timestamps, falling back to re-encode")
            print(f"[DEBUG] Stream copy failed, falling back to re-encode", file=sys.stderr, flush=True)

            # Get quality settings with hardware acceleration if available
            quality_settings = FFmpegUtils.get_quality_preset(quality)
            video_encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

            # Use filter_complex to ensure proper timestamp handling
            # Read all inputs and use concat filter
            input_args = []
            for path in segment_paths:
                input_args.extend(['-i', path])

            # Build concat filter
            n = len(segment_paths)
            filter_parts = []

            # Reset timestamps for each input before concat
            for i in range(n):
                filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
                filter_parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")

            # Build concat inputs - MUST BE INTERLEAVED: [v0][a0][v1][a1]... not [v0][v1][a0][a1]
            # This is the correct syntax for FFmpeg concat filter
            interleaved_inputs = ''.join(f"[v{i}][a{i}]" for i in range(n))

            # Concat filter
            filter_parts.append(f"{interleaved_inputs}concat=n={n}:v=1:a=1[outv][outa]")

            filter_complex = ';'.join(filter_parts)

            cmd_reencode = [
                settings.FFMPEG_PATH,
                '-y',
                *input_args,
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '[outa]',
                *video_encoder_args,
                '-c:a', 'aac',
                '-b:a', '192k',
                '-movflags', '+faststart',
                output_path
            ]

            print(f"[DEBUG] Re-encoding with concat filter...", file=sys.stderr, flush=True)

            process = await asyncio.create_subprocess_exec(
                *cmd_reencode,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            # Cleanup concat file
            try:
                os.remove(str(concat_file))
            except:
                pass

            if process.returncode != 0:
                error_text = stderr.decode()[-500:] if stderr else "Unknown error"
                logger.error(f"FFmpeg concatenation failed: {error_text}")
                return False

            logger.info("Concatenation successful (re-encoded)")
            return True

        except Exception as e:
            logger.error(f"Visibility segment concatenation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def _verify_video_timestamps(self, video_path: str) -> Optional[dict]:
        """Verify that a video has proper timestamps starting at or near 0."""
        try:
            import json

            cmd = [
                settings.FFPROBE_PATH,
                '-v', 'quiet',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=start_time',
                '-of', 'json',
                video_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()

            if process.returncode == 0 and stdout:
                data = json.loads(stdout.decode())
                if 'streams' in data and len(data['streams']) > 0:
                    start_time = float(data['streams'][0].get('start_time', 0))
                    return {'video_start': start_time}

            return None
        except Exception as e:
            logger.warning(f"Could not verify video timestamps: {e}")
            return None

    def _find_segment_by_id(self, segment_id: str) -> Optional[Segment]:
        """
        Find the original segment by ID from all sources in the project.

        This checks:
        1. Generic/project-level segments (video_id=null)
        2. Video-specific segments

        This is used to retrieve subtitle styling info for segment placements.
        """
        # First check generic segments (project-level, video_id=null)
        if hasattr(self.project, 'generic_segments'):
            for segment in self.project.generic_segments:
                if segment.id == segment_id:
                    return segment
                # Also check for continuation segments
                if segment_id.startswith(segment.id):
                    return segment

        # Then check all videos for video-specific segments
        for video in self.project.videos:
            if video.timeline and video.timeline.segments:
                for segment in video.timeline.segments:
                    if segment.id == segment_id:
                        return segment
                    # Also check for continuation segments
                    if segment_id.startswith(segment.id):
                        return segment

        return None

    async def _create_combined_ass_file(
        self,
        subtitles_info: List[dict],
        output_path: str,
        play_res_x: int = 1920,
        play_res_y: int = 1080
    ) -> bool:
        """
        Create a combined ASS subtitle file from multiple segments.

        Each subtitle gets proper timing and styling based on its segment.

        Args:
            subtitles_info: List of dicts with:
                - subtitle_path: Path to original SRT/ASS file
                - adjusted_start: Start time in combined video (seconds)
                - segment: Original Segment object for styling
            output_path: Path to save combined ASS file
            play_res_x: Video width for PlayResX (default 1920)
            play_res_y: Video height for PlayResY (default 1080)

        Returns:
            True if successful
        """
        try:
            import sys
            print(f"[DEBUG] Creating combined ASS file with {len(subtitles_info)} subtitle(s), PlayRes: {play_res_x}x{play_res_y}", file=sys.stderr, flush=True)

            # ASS file header with dynamic PlayRes based on actual video resolution
            # This ensures font sizes scale correctly regardless of video resolution
            ass_header = f"""[Script Info]
Title: Combined Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""
            # Collect all events with unique styles
            styles = []
            events = []
            style_names = set()

            for idx, sub_info in enumerate(subtitles_info):
                segment = sub_info['segment']
                subtitle_path = sub_info['subtitle_path']
                adjusted_start = sub_info['adjusted_start']
                segment_duration = sub_info.get('duration', 0)
                # Get audio_offset - for continuation segments, subtitles must be trimmed just like audio
                audio_offset = sub_info.get('audio_offset', 0) or 0

                if not os.path.exists(subtitle_path):
                    logger.warning(f"Subtitle file not found: {subtitle_path}")
                    continue

                if audio_offset > 0:
                    print(f"[DEBUG] Segment {idx}: applying audio_offset={audio_offset:.3f}s to subtitle timing", file=sys.stderr, flush=True)

                # Create unique style name for this segment
                style_name = f"Seg{idx}"
                if style_name in style_names:
                    style_name = f"Seg{idx}_{segment.id[:8]}"
                style_names.add(style_name)

                # Get segment styling
                font_name = getattr(segment, 'subtitle_font', 'Roboto')

                # Map private/platform-specific fonts to cross-platform equivalents
                # - macOS: dot-prefixed fonts are internal system fonts FFmpeg cannot access
                # - Windows: Apple fonts don't exist, need fallbacks
                # - Cross-platform safe fonts: Arial, Roboto, Helvetica, Times New Roman
                import platform
                is_macos = platform.system() == 'Darwin'
                is_windows = platform.system() == 'Windows'

                font_mapping = {
                    # macOS private fonts -> public equivalents
                    '.Apple SD Gothic NeoI': 'Apple SD Gothic Neo' if is_macos else 'Arial',
                    '.AppleSystemUIFont': 'Helvetica Neue' if is_macos else 'Segoe UI',
                    '.SF NS': 'Helvetica Neue' if is_macos else 'Segoe UI',
                    '.SF NS Text': 'Helvetica Neue' if is_macos else 'Segoe UI',
                    '.SF NS Display': 'Helvetica Neue' if is_macos else 'Segoe UI',
                    '.Helvetica Neue DeskInterface': 'Helvetica Neue' if is_macos else 'Segoe UI',
                    # macOS-only fonts -> Windows alternatives
                    'Apple SD Gothic Neo': 'Apple SD Gothic Neo' if is_macos else 'Malgun Gothic',
                    'Helvetica Neue': 'Helvetica Neue' if is_macos else 'Arial',
                    'Helvetica': 'Helvetica' if is_macos else 'Arial',
                }

                if font_name in font_mapping:
                    mapped = font_mapping[font_name]
                    if mapped != font_name:
                        logger.debug(f"Mapping font '{font_name}' to '{mapped}'")
                        font_name = mapped
                elif font_name.startswith('.'):
                    # Generic fallback for any other dot-prefixed font
                    fallback = 'Helvetica Neue' if is_macos else 'Arial'
                    logger.warning(f"Unknown private font '{font_name}', falling back to '{fallback}'")
                    font_name = fallback

                # Get raw values from segment
                raw_font_size = getattr(segment, 'subtitle_size', 20)
                primary_color = getattr(segment, 'subtitle_color', '&H00FFFFFF')
                outline_color = getattr(segment, 'subtitle_outline_color', '&H00000000')
                shadow_color = getattr(segment, 'subtitle_shadow_color', '&H80000000')
                raw_outline_width = getattr(segment, 'subtitle_outline_width', 0.5)
                raw_shadow_depth = getattr(segment, 'subtitle_shadow', 0.0)
                border_style = getattr(segment, 'subtitle_border_style', 1)
                raw_margin_v = getattr(segment, 'subtitle_position', 30)

                # Scale values for target resolution
                # User's values are relative to FFmpeg's default PlayRes (288)
                # We must scale them to match the actual video PlayRes
                font_size = int(self._scale_for_resolution(raw_font_size, play_res_y))
                outline_width = round(self._scale_for_resolution(raw_outline_width, play_res_y), 2)
                shadow_depth = round(self._scale_for_resolution(raw_shadow_depth, play_res_y), 2)
                margin_v = int(self._scale_for_resolution(raw_margin_v, play_res_y))
                margin_l = int(self._scale_for_resolution(10, play_res_y))  # Default marginl
                margin_r = int(self._scale_for_resolution(10, play_res_y))  # Default marginr

                # Create style line with scaled values
                style_line = f"Style: {style_name},{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{shadow_color},0,0,0,0,100,100,0,0,{border_style},{outline_width},{shadow_depth},2,{margin_l},{margin_r},{margin_v},1"
                styles.append(style_line)

                # Read and parse subtitle file
                with open(subtitle_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse based on format
                if subtitle_path.lower().endswith('.ass'):
                    # Parse ASS events
                    in_events = False
                    for line in content.split('\n'):
                        if '[Events]' in line:
                            in_events = True
                            continue
                        if in_events and line.startswith('Dialogue:'):
                            # Parse and adjust timing
                            parts = line.split(',', 9)
                            if len(parts) >= 10:
                                try:
                                    orig_start = self._ass_time_to_seconds(parts[1].strip())
                                    orig_end = self._ass_time_to_seconds(parts[2].strip())

                                    # Apply audio_offset for continuation segments
                                    # (skip already-played portion, just like atrim does for audio)
                                    if audio_offset > 0:
                                        # Skip subtitles that end before audio_offset
                                        if orig_end <= audio_offset:
                                            continue
                                        # Adjust timing by subtracting audio_offset
                                        orig_start = max(0, orig_start - audio_offset)
                                        orig_end = orig_end - audio_offset

                                    # Adjust timing relative to combined video
                                    new_start = adjusted_start + orig_start
                                    new_end = adjusted_start + orig_end

                                    # Limit to segment duration if specified
                                    if segment_duration > 0:
                                        if orig_start >= segment_duration:
                                            continue  # Skip subtitles after segment end
                                        new_end = min(new_end, adjusted_start + segment_duration)

                                    new_start_str = self._seconds_to_ass_time(new_start)
                                    new_end_str = self._seconds_to_ass_time(new_end)

                                    # Use our style instead of original
                                    text = parts[9]
                                    events.append(f"Dialogue: 0,{new_start_str},{new_end_str},{style_name},,0,0,0,,{text}")
                                except Exception as e:
                                    logger.warning(f"Failed to parse ASS dialogue: {e}")
                else:
                    # Parse SRT format
                    blocks = content.strip().split('\n\n')
                    for block in blocks:
                        lines = block.strip().split('\n')
                        if len(lines) >= 3:
                            try:
                                # Parse timing line (format: 00:00:00,000 --> 00:00:00,000)
                                timing_line = lines[1]
                                if '-->' in timing_line:
                                    parts = timing_line.split('-->')
                                    orig_start = self._srt_time_to_seconds(parts[0].strip())
                                    orig_end = self._srt_time_to_seconds(parts[1].strip())

                                    # Apply audio_offset for continuation segments
                                    # (skip already-played portion, just like atrim does for audio)
                                    if audio_offset > 0:
                                        # Skip subtitles that end before audio_offset
                                        if orig_end <= audio_offset:
                                            continue
                                        # Adjust timing by subtracting audio_offset
                                        orig_start = max(0, orig_start - audio_offset)
                                        orig_end = orig_end - audio_offset

                                    # Adjust timing relative to combined video
                                    new_start = adjusted_start + orig_start
                                    new_end = adjusted_start + orig_end

                                    # Limit to segment duration if specified
                                    if segment_duration > 0:
                                        if orig_start >= segment_duration:
                                            continue  # Skip subtitles after segment end
                                        new_end = min(new_end, adjusted_start + segment_duration)

                                    new_start_str = self._seconds_to_ass_time(new_start)
                                    new_end_str = self._seconds_to_ass_time(new_end)

                                    # Get subtitle text (may be multiple lines)
                                    text = '\\N'.join(lines[2:])  # ASS uses \N for newlines
                                    events.append(f"Dialogue: 0,{new_start_str},{new_end_str},{style_name},,0,0,0,,{text}")
                            except Exception as e:
                                logger.warning(f"Failed to parse SRT block: {e}")

            if not events:
                logger.warning("No subtitle events after processing")
                return False

            # Write combined ASS file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ass_header)
                for style in styles:
                    f.write(style + '\n')
                f.write('\n[Events]\n')
                f.write('Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')
                for event in events:
                    f.write(event + '\n')

            logger.info(f"Created combined ASS file with {len(events)} dialogue events")
            print(f"[DEBUG] Combined ASS file created: {output_path}", file=sys.stderr, flush=True)
            return True

        except Exception as e:
            logger.error(f"Failed to create combined ASS file: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _srt_time_to_seconds(self, time_str: str) -> float:
        """Convert SRT time format (00:00:00,000) to seconds."""
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    def _ass_time_to_seconds(self, time_str: str) -> float:
        """Convert ASS time format (0:00:00.00) to seconds."""
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    async def _burn_subtitles_by_timeline(
        self,
        video_path: str,
        segment_placements: list,
        output_path: str,
        quality: str,
        video_start_offset: float = 0.0
    ) -> bool:
        """
        Burn subtitles onto a combined video based on timeline positions.

        This creates a single combined ASS file with all subtitles properly
        timed relative to the combined video, then burns it in one FFmpeg pass.

        Args:
            video_path: Path to the combined video (with voice-overs already added)
            segment_placements: List of SegmentPlacement from LayerCompositor
            output_path: Path for output video with subtitles
            quality: Quality preset
            video_start_offset: The timeline start of the combined video

        Returns:
            True if successful
        """
        try:
            import sys
            print(f"[DEBUG] _burn_subtitles_by_timeline: processing {len(segment_placements)} placements", file=sys.stderr, flush=True)

            # Collect subtitle-enabled segments
            subtitles_to_burn = []

            for placement in segment_placements:
                # Find the original segment to get subtitle_enabled and styling
                original_segment = self._find_segment_by_id(placement.segment_id)

                if not original_segment:
                    logger.warning(f"Could not find original segment: {placement.segment_id}")
                    continue

                # Check if subtitle is enabled and path exists
                if not getattr(original_segment, 'subtitle_enabled', True):
                    logger.info(f"Subtitles disabled for segment: {placement.segment_name}")
                    continue

                # Get subtitle path from placement or original segment
                subtitle_path = placement.subtitle_path or original_segment.subtitle_path

                if not subtitle_path or not os.path.exists(subtitle_path):
                    logger.info(f"No subtitle file for segment: {placement.segment_name}")
                    continue

                # Calculate adjusted start time in combined video
                adjusted_start = max(0, placement.timeline_start - video_start_offset)

                # Get audio_offset for continuation segments (subtitle should also be trimmed)
                audio_offset = getattr(placement, 'audio_offset', 0) or 0

                # Calculate segment duration for limiting subtitle display
                segment_duration = placement.timeline_end - placement.timeline_start

                logger.info(f"Subtitle: '{placement.segment_name}' at {adjusted_start:.3f}s "
                           f"(timeline: {placement.timeline_start:.3f}s, duration: {segment_duration:.3f}s, "
                           f"audio_offset: {audio_offset:.3f}s)")

                subtitles_to_burn.append({
                    'subtitle_path': subtitle_path,
                    'adjusted_start': adjusted_start,
                    'segment': original_segment,
                    'duration': segment_duration,
                    'audio_offset': audio_offset
                })

            if not subtitles_to_burn:
                logger.info("No subtitles to burn - copying video as-is")
                import shutil
                shutil.copy(video_path, output_path)
                return True

            # Get actual resolution of the combined video for correct subtitle scaling
            # PlayRes must match video resolution for font sizes to render correctly
            video_info = FFmpegUtils.get_video_info(video_path)
            play_res_x = video_info.get('width', 1920) if video_info else 1920
            play_res_y = video_info.get('height', 1080) if video_info else 1080
            logger.info(f"Burning subtitles with PlayRes: {play_res_x}x{play_res_y}")

            # Create combined ASS file
            combined_ass_path = self.temp_dir / f"combined_subtitles_{uuid4().hex[:8]}.ass"

            success = await self._create_combined_ass_file(
                subtitles_to_burn,
                str(combined_ass_path),
                play_res_x=play_res_x,
                play_res_y=play_res_y
            )

            if not success:
                logger.warning("Failed to create combined ASS file - copying video without subtitles")
                import shutil
                shutil.copy(video_path, output_path)
                return True

            # Burn subtitles using FFmpeg with hardware acceleration if available
            quality_settings = FFmpegUtils.get_quality_preset(quality)
            video_encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

            # Escape path for FFmpeg filter (handle special characters)
            escaped_ass_path = str(combined_ass_path.resolve()).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")

            cmd = [
                settings.FFMPEG_PATH,
                '-y',
                '-i', video_path,
                '-vf', f"subtitles='{escaped_ass_path}'",
                *video_encoder_args,
                '-c:a', 'copy',  # Audio already processed, just copy
                output_path
            ]

            logger.info(f"Burning {len(subtitles_to_burn)} subtitle(s) onto video")
            print(f"[DEBUG] Subtitle burn command: subtitles='{escaped_ass_path}'", file=sys.stderr, flush=True)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            # Cleanup temp ASS file
            try:
                os.remove(str(combined_ass_path))
            except:
                pass

            if process.returncode != 0:
                error_text = stderr.decode()[-500:] if stderr else "Unknown error"
                logger.error(f"FFmpeg subtitle burning failed: {error_text}")
                # Fall back to copying without subtitles
                import shutil
                shutil.copy(video_path, output_path)
                logger.warning("Copied video without subtitles due to burn failure")
                return True

            logger.info("Subtitles burned successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to burn subtitles by timeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fall back to copying without subtitles
            try:
                import shutil
                shutil.copy(video_path, output_path)
                return True
            except:
                return False

    async def export_combined_videos(
        self,
        output_path: str,
        quality: str = "balanced",
        include_subtitles: bool = True,
        background_music_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        force_export: bool = False,
        detailed_callback: Optional[Callable[[dict], Any]] = None,
        user_tier: str = "free_trial"
    ) -> bool:
        """
        Export all videos in project combined in order

        Args:
            output_path: Path to save combined video
            quality: Quality preset
            include_subtitles: Whether to burn subtitles
            background_music_path: Optional background music
            progress_callback: Progress callback
            force_export: Force export even if videos are incompatible
            detailed_callback: Detailed async callback for FFmpeg progress with ETA
            user_tier: User's subscription tier (REQUIRED for watermark enforcement)

        Returns:
            True if successful

        Raises:
            ValueError: If user_tier is not provided
        """
        # SECURITY: user_tier is REQUIRED to ensure proper watermark enforcement
        if not user_tier:
            raise ValueError("user_tier is required for export. Cannot export without knowing user subscription tier.")

        try:
            if len(self.project.videos) == 0:
                logger.error("No videos in project to export")
                return False

            if len(self.project.videos) == 1:
                # Single video, use standard export with user_tier for watermark
                return await self.export(
                    output_path,
                    quality,
                    include_subtitles,
                    background_music_path,
                    progress_callback,
                    user_tier=user_tier
                )

            logger.info(f"Exporting combined video with {len(self.project.videos)} videos")
            import sys
            print(f"[DEBUG] export_combined_videos started with {len(self.project.videos)} videos", file=sys.stderr, flush=True)

            # Initialize LayerCompositor for layer-based timeline handling
            # This properly handles stack priority and visibility calculations
            compositor = LayerCompositor(self.project)
            if not compositor.build():
                logger.error("Failed to build layer compositor")
                return False

            # Log compositor debug info
            logger.info(compositor.get_debug_info())

            # Check compatibility
            is_compatible, warnings = self.project.check_video_compatibility()
            if not is_compatible:
                if force_export:
                    logger.warning("Videos are not compatible but forcing export:")
                    for warning in warnings:
                        logger.warning(f"  {warning}")
                else:
                    logger.error("Videos are not compatible for combination:")
                    for warning in warnings:
                        logger.error(f"  {warning}")
                    # Raise exception with user-friendly error message
                    error_details = "\n".join(f"• {w}" for w in warnings)
                    raise ValueError(
                        f"Cannot combine videos with different properties:\n{error_details}\n\n"
                        f"Tip: Use videos with the same orientation (all landscape or all portrait) for best results."
                    )

            if warnings:
                logger.warning("Video compatibility warnings:")
                for warning in warnings:
                    logger.warning(f"  {warning}")

            # Process each VISIBILITY SEGMENT (not each video)
            # This ensures proper layer-based compositing
            visibility_map = compositor.visibility_map
            if not visibility_map:
                logger.error("No visibility segments found")
                return False

            processed_segments = []
            total_segments = len(visibility_map)

            logger.info(f"Processing {total_segments} visibility segment(s)")

            for idx, vis_seg in enumerate(visibility_map, 1):
                print(f"[DEBUG] Processing visibility segment {idx}/{total_segments}: {vis_seg.video_name} ({vis_seg.timeline_start:.2f}s - {vis_seg.timeline_end:.2f}s)", file=sys.stderr, flush=True)

                # Calculate progress: visibility segments span 45-60%
                segment_progress = 45 + int((idx - 1) / total_segments * 15)

                if progress_callback:
                    progress_callback(f"Processing segment {idx}/{total_segments}: {vis_seg.video_name}", segment_progress)

                # Emit detailed progress for frontend
                if detailed_callback:
                    await detailed_callback({
                        'stage': 'segments',
                        'message': f"Processing segment {idx}/{total_segments}: {vis_seg.video_name}",
                        'progress': segment_progress,
                        'current_step': idx,
                        'total_steps': total_segments,
                        'current_segment': vis_seg.video_name
                    })

                # Find the video object for this segment
                video = self.project.get_video(vis_seg.video_id)
                if not video:
                    logger.error(f"Video not found: {vis_seg.video_id}")
                    return False

                # Process this specific visibility segment
                temp_output = self.temp_dir / f"{self.project.name}_vseg_{idx}_{vis_seg.video_id[:8]}.mp4"

                success = await self._process_visibility_segment(
                    video=video,
                    vis_seg=vis_seg,
                    compositor=compositor,
                    output_path=str(temp_output),
                    quality=quality,
                    include_subtitles=include_subtitles
                )

                print(f"[DEBUG] _process_visibility_segment returned: {success}", file=sys.stderr, flush=True)
                if not success:
                    logger.error(f"Failed to process visibility segment {idx}: {vis_seg.video_name}")
                    return False

                processed_segments.append(str(temp_output))

            # Combine all processed visibility segments
            if progress_callback:
                progress_callback("Combining all segments...", 60)
            if detailed_callback:
                await detailed_callback({
                    'stage': 'combining',
                    'message': 'Combining all video segments...',
                    'progress': 60
                })

            combine_output = self.temp_dir / f"{self.project.name}_combined_temp.mp4"

            # Simple concatenation since segments are already normalized
            success = await self._concatenate_visibility_segments(
                processed_segments,
                str(combine_output),
                quality
            )

            if not success:
                logger.error("Failed to combine videos")
                return False

            # Add voice-overs using timeline positions from compositor
            # This ensures cross-video segments are placed correctly
            segment_placements = compositor.segment_placements
            if segment_placements:
                if progress_callback:
                    progress_callback(f"Adding {len(segment_placements)} voice-over(s)...", 65)
                if detailed_callback:
                    await detailed_callback({
                        'stage': 'voiceover',
                        'message': f'Adding {len(segment_placements)} voice-over(s)...',
                        'progress': 65
                    })

                # Get the timeline start offset from the first visibility segment
                # This is when the combined video actually starts
                video_start_offset = visibility_map[0].timeline_start if visibility_map else 0

                voiceover_output = self.temp_dir / f"{self.project.name}_with_voiceover.mp4"
                success = await self._add_voiceovers_by_timeline(
                    str(combine_output),
                    segment_placements,
                    str(voiceover_output),
                    quality,
                    include_subtitles,
                    video_start_offset=video_start_offset
                )

                if success:
                    combine_output = voiceover_output
                else:
                    logger.warning("Failed to add voice-overs, continuing without them")

            # Burn subtitles if requested
            # This happens AFTER voice-overs so timing is correct, BEFORE BGM
            if include_subtitles and segment_placements:
                if progress_callback:
                    progress_callback("Burning subtitles...", 75)
                if detailed_callback:
                    await detailed_callback({
                        'stage': 'subtitles',
                        'message': 'Burning subtitles into video...',
                        'progress': 75
                    })

                # Calculate video_start_offset (may have been set in voice-over section already)
                subtitle_video_start_offset = visibility_map[0].timeline_start if visibility_map else 0

                subtitle_output = self.temp_dir / f"{self.project.name}_with_subtitles.mp4"
                success = await self._burn_subtitles_by_timeline(
                    str(combine_output),
                    segment_placements,
                    str(subtitle_output),
                    quality,
                    video_start_offset=subtitle_video_start_offset
                )

                if success and os.path.exists(str(subtitle_output)):
                    combine_output = subtitle_output
                    logger.info("Subtitles burned successfully")
                else:
                    logger.warning("Failed to burn subtitles, continuing without them")

            # Add background music if requested
            final_output = output_path

            # Check for multi-BGM tracks first
            has_bgm_tracks = hasattr(self.project, 'bgm_tracks') and len(self.project.bgm_tracks) > 0

            if has_bgm_tracks:
                if progress_callback:
                    progress_callback(f"Adding {len(self.project.bgm_tracks)} background music track(s)...", 85)

                video_duration = FFmpegUtils.get_media_duration(str(combine_output))

                # CRITICAL: Adjust BGM track times relative to the combined video
                # The BGM tracks have times in absolute timeline coordinates,
                # but the combined video starts from video_start_offset (not 0)
                # So we need to subtract video_start_offset from the track times
                from copy import deepcopy
                adjusted_bgm_tracks = []
                for track in self.project.bgm_tracks:
                    adjusted_track = deepcopy(track)
                    # Adjust start_time relative to combined video
                    adjusted_track.start_time = max(0, track.start_time - video_start_offset)
                    # Adjust end_time relative to combined video (if set)
                    if track.end_time > 0:
                        adjusted_track.end_time = max(0, track.end_time - video_start_offset)
                    logger.info(f"BGM '{track.name}': timeline {track.start_time:.2f}s-{track.end_time:.2f}s -> adjusted {adjusted_track.start_time:.2f}s-{adjusted_track.end_time:.2f}s")
                    adjusted_bgm_tracks.append(adjusted_track)

                # Create async progress callback for BGM mixing
                async def combined_bgm_progress(info: dict):
                    if detailed_callback:
                        await detailed_callback({
                            'stage': 'bgm',
                            'message': f"Adding background music: {info['progress']}%",
                            'progress': 85 + int(info['progress'] * 0.12),
                            'detail': f"ETA: {info.get('eta_formatted', 'calculating...')}",
                            'ffmpeg_progress': info
                        })
                    if progress_callback:
                        progress_callback(f"Adding BGM: {info['progress']}% (ETA: {info.get('eta_formatted', '...')})", 85 + int(info['progress'] * 0.12))

                success = await FFmpegUtils.add_multiple_bgm_tracks_async(
                    str(combine_output),
                    adjusted_bgm_tracks,  # Use adjusted tracks with corrected times
                    final_output,
                    video_duration,
                    global_tts_volume=getattr(self.project, 'tts_volume', 100),
                    global_bgm_volume=getattr(self.project, 'bgm_volume', 100),
                    progress_callback=combined_bgm_progress
                )

                if not success:
                    logger.error("Failed to add background music tracks")
                    return False
            elif background_music_path and os.path.exists(background_music_path):
                if progress_callback:
                    progress_callback("Adding background music...", 85)

                # Create async progress callback for BGM mixing
                async def combined_legacy_bgm_progress(info: dict):
                    if detailed_callback:
                        await detailed_callback({
                            'stage': 'bgm',
                            'message': f"Adding background music: {info['progress']}%",
                            'progress': 85 + int(info['progress'] * 0.12),
                            'detail': f"ETA: {info.get('eta_formatted', 'calculating...')}",
                            'ffmpeg_progress': info
                        })
                    if progress_callback:
                        progress_callback(f"Adding BGM: {info['progress']}% (ETA: {info.get('eta_formatted', '...')})", 85 + int(info['progress'] * 0.12))

                success = await FFmpegUtils.add_background_music_async(
                    str(combine_output),
                    background_music_path,
                    final_output,
                    tts_boost=15,
                    bgm_reduction=20,
                    fade_duration=3.0,
                    progress_callback=combined_legacy_bgm_progress
                )

                if not success:
                    logger.error("Failed to add background music")
                    return False
            else:
                # Copy combined output to final
                import shutil
                shutil.copy(str(combine_output), final_output)

            # Apply watermark for free tier users (if applicable)
            if user_tier:
                watermark_service = get_watermark_service()
                if watermark_service.should_add_watermark(user_tier):
                    if progress_callback:
                        progress_callback("Applying watermark...", 95)

                    logger.info(f"Applying watermark for tier: {user_tier}")

                    # Rename output to temp for watermarking
                    temp_prewatermark = final_output + ".prewatermark.mp4"
                    try:
                        os.rename(final_output, temp_prewatermark)

                        # Apply watermark with matching quality settings
                        success, message = await watermark_service.add_watermark(
                            input_path=temp_prewatermark,
                            output_path=final_output,
                            tier=user_tier,
                            quality=quality
                        )
                        if success:
                            logger.info("Watermark applied successfully")
                            # Remove temp file
                            if os.path.exists(temp_prewatermark):
                                os.unlink(temp_prewatermark)
                        else:
                            # SECURITY: Watermark REQUIRED for free tier - fail export if watermark fails
                            # Do NOT allow unwatermarked exports for free tier users
                            logger.error(f"CRITICAL: Watermark failed for tier {user_tier}: {message}")
                            # Cleanup both files - do not leave unwatermarked video
                            if os.path.exists(temp_prewatermark):
                                os.unlink(temp_prewatermark)
                            if os.path.exists(final_output):
                                os.unlink(final_output)
                            raise RuntimeError(
                                f"Export failed: Watermark required for {user_tier} tier but watermark application failed. "
                                f"Reason: {message}"
                            )

                    except RuntimeError:
                        # Re-raise our own RuntimeError for watermark failure
                        raise
                    except Exception as e:
                        # SECURITY: Watermark REQUIRED - fail export if any error occurs
                        logger.error(f"CRITICAL: Watermark error for tier {user_tier}: {e}")
                        # Cleanup both files - do not leave unwatermarked video
                        if os.path.exists(temp_prewatermark):
                            os.unlink(temp_prewatermark)
                        if os.path.exists(final_output):
                            os.unlink(final_output)
                        raise RuntimeError(
                            f"Export failed: Watermark required for {user_tier} tier but an error occurred. "
                            f"Error: {e}"
                        )

            # Cleanup temp files
            if progress_callback:
                progress_callback("Cleaning up temporary files...", 97)

            for temp_seg in processed_segments:
                try:
                    os.remove(temp_seg)
                except:
                    pass

            try:
                os.remove(str(combine_output))
            except:
                pass

            if progress_callback:
                progress_callback("Export complete!", 100)

            logger.info(f"✅ Combined video export successful: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export combined videos: {e}")
            return False
