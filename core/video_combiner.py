"""
Video Combiner - Combines multiple edited videos into a single output
"""

import asyncio
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Callable
from utils.logger import logger
from backend.ffmpeg_utils import FFmpegUtils, run_ffmpeg_with_progress, escape_concat_path
from models.video import Video
from config import settings


class VideoCombiner:
    """
    Handles combination of multiple processed videos with aspect ratio validation
    Based on the FFmpeg techniques from reference/FFmpeg_Video_Generation_Documentation.md
    """

    @staticmethod
    def check_compatibility(videos: List[Video]) -> Tuple[bool, List[str], dict]:
        """
        Check if videos are compatible for combination

        Args:
            videos: List of Video instances to check

        Returns:
            Tuple of (is_compatible, warnings, common_specs)
        """
        if len(videos) <= 1:
            return True, [], {}

        warnings = []
        reference = videos[0]

        # Check orientation compatibility
        orientations = {v.orientation for v in videos}
        if len(orientations) > 1:
            return (
                False,
                [f"INCOMPATIBLE: Cannot combine videos with different orientations: {orientations}"],
                {}
            )

        # Check aspect ratio similarity (within 5% tolerance)
        aspect_ratios = [v.aspect_ratio for v in videos if v.aspect_ratio]
        if aspect_ratios:
            min_ar = min(aspect_ratios)
            max_ar = max(aspect_ratios)
            diff = abs(max_ar - min_ar)

            if diff > 0.05:  # 5% tolerance
                warnings.append(
                    f"Different aspect ratios detected (range: {min_ar:.3f} to {max_ar:.3f}). "
                    "Videos will be scaled to match, which may cause quality loss or black bars."
                )

        # Determine common specifications
        resolutions = [(v.width, v.height) for v in videos if v.width and v.height]
        fps_values = [v.fps for v in videos if v.fps]
        codecs = {v.codec for v in videos if v.codec}

        # Find target resolution (highest)
        if resolutions:
            target_width = max(r[0] for r in resolutions)
            target_height = max(r[1] for r in resolutions)
        else:
            target_width, target_height = 1920, 1080

        # Find target FPS (highest common)
        target_fps = max(fps_values) if fps_values else 30.0

        # Check if all resolutions match
        if len(set(resolutions)) > 1:
            warnings.append(
                f"Different resolutions detected. Videos will be scaled to {target_width}x{target_height}."
            )

        # Check if all FPS match
        if len(set(fps_values)) > 1:
            warnings.append(
                f"Different frame rates detected. Videos will be converted to {target_fps} FPS."
            )

        # Check if all codecs match
        if len(codecs) > 1:
            warnings.append(
                f"Different codecs detected ({codecs}). Videos will be re-encoded."
            )

        common_specs = {
            'width': target_width,
            'height': target_height,
            'fps': target_fps,
            'orientation': reference.orientation,
            'needs_scaling': len(set(resolutions)) > 1,
            'needs_fps_conversion': len(set(fps_values)) > 1,
            'needs_reencoding': len(codecs) > 1
        }

        return True, warnings, common_specs

    @staticmethod
    def combine_videos_simple(
        video_paths: List[str],
        output_path: str,
        temp_dir: Path
    ) -> bool:
        """
        Combine videos using concat demuxer (fast, requires same specs)
        SYNC version - use combine_videos_simple_async for non-blocking operation

        Args:
            video_paths: List of video file paths to combine
            output_path: Output file path
            temp_dir: Temporary directory for concat file

        Returns:
            True if successful
        """
        try:
            # Create concat file
            concat_file = temp_dir / "concat_list.txt"

            with open(concat_file, 'w') as f:
                for video_path in video_paths:
                    # Escape path for FFmpeg concat demuxer (handles special chars)
                    escaped_path = escape_concat_path(video_path)
                    f.write(f"file '{escaped_path}'\n")

            logger.info(f"Created concat file with {len(video_paths)} videos")

            # Combine using concat demuxer
            command = [
                settings.FFMPEG_PATH,
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',  # Copy without re-encoding
                '-y',
                output_path
            ]

            logger.info("Combining videos (fast mode - no re-encoding)...")
            # Add timeout to prevent infinite hang
            result = subprocess.run(command, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                duration = FFmpegUtils.get_media_duration(output_path)
                size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                logger.info(f"✅ Videos combined successfully! Duration: {duration:.2f}s, Size: {size_mb:.1f}MB")
                return True
            else:
                logger.error(f"❌ Video combination failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ Video combination timed out after 600 seconds")
            return False
        except Exception as e:
            logger.error(f"❌ Error combining videos: {e}")
            return False

    @staticmethod
    async def combine_videos_simple_async(
        video_paths: List[str],
        output_path: str,
        temp_dir: Path,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Combine videos using concat demuxer (fast, requires same specs)
        ASYNC version - non-blocking for server operations

        Args:
            video_paths: List of video file paths to combine
            output_path: Output file path
            temp_dir: Temporary directory for concat file
            progress_callback: Optional async progress callback

        Returns:
            True if successful
        """
        try:
            # Calculate total duration for progress tracking
            total_duration = 0
            for video_path in video_paths:
                duration = FFmpegUtils.get_media_duration(video_path)
                if duration:
                    total_duration += duration

            if total_duration == 0:
                logger.error("Could not calculate total duration for progress tracking")
                total_duration = 60  # Fallback estimate

            # Create concat file
            concat_file = temp_dir / "concat_list.txt"

            with open(concat_file, 'w') as f:
                for video_path in video_paths:
                    # Escape path for FFmpeg concat demuxer (handles special chars)
                    escaped_path = escape_concat_path(video_path)
                    f.write(f"file '{escaped_path}'\n")

            logger.info(f"Created concat file with {len(video_paths)} videos")

            # Combine using concat demuxer
            command = [
                settings.FFMPEG_PATH,
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',  # Copy without re-encoding
                '-y',
                output_path
            ]

            logger.info("Combining videos async (fast mode - no re-encoding)...")

            success, error = await run_ffmpeg_with_progress(
                command,
                total_duration,
                progress_callback,
                "Combining videos",
                timeout=600
            )

            if success:
                duration = FFmpegUtils.get_media_duration(output_path)
                size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                logger.info(f"✅ Videos combined successfully! Duration: {duration:.2f}s, Size: {size_mb:.1f}MB")
                return True
            else:
                logger.error(f"❌ Video combination failed: {error}")
                return False

        except Exception as e:
            logger.error(f"❌ Error combining videos: {e}")
            return False

    @staticmethod
    def combine_videos_complex(
        video_paths: List[str],
        output_path: str,
        common_specs: dict,
        quality: str = "balanced"
    ) -> bool:
        """
        Combine videos with scaling/fps conversion (slower, handles different specs)
        SYNC version - use combine_videos_complex_async for non-blocking operation

        Args:
            video_paths: List of video file paths to combine
            output_path: Output file path
            common_specs: Common specifications dictionary
            quality: Export quality (lossless, high, balanced)

        Returns:
            True if successful
        """
        try:
            target_width = common_specs['width']
            target_height = common_specs['height']
            target_fps = common_specs['fps']

            logger.info(f"Combining videos with normalization:")
            logger.info(f"  Target resolution: {target_width}x{target_height}")
            logger.info(f"  Target FPS: {target_fps}")

            # Build filter complex for each input
            # First, check which videos have audio streams
            video_audio_info = []
            for idx, video_path in enumerate(video_paths):
                has_audio = FFmpegUtils.has_audio_stream(video_path)
                video_audio_info.append((idx, has_audio))
                logger.debug(f"Video {idx} ({video_path}): has_audio={has_audio}")

            filter_parts = []
            for idx, video_path in enumerate(video_paths):
                # Scale and set FPS for each input
                filter_parts.append(
                    f"[{idx}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                    f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
                    f"fps={target_fps},setsar=1[v{idx}]"
                )

                # Handle audio - generate silent audio for videos without audio stream
                has_audio = video_audio_info[idx][1]
                if has_audio:
                    # Video has audio - pass through with anull (maintains format)
                    filter_parts.append(f"[{idx}:a]anull[a{idx}]")
                else:
                    # Video has no audio - generate silent audio matching video duration
                    # Use aevalsrc to create silent audio: aevalsrc=0:d=duration
                    video_duration = FFmpegUtils.get_media_duration(video_path) or 10
                    filter_parts.append(
                        f"aevalsrc=0:d={video_duration:.3f}:s=44100:c=stereo[a{idx}]"
                    )
                    logger.info(f"Generated silent audio for video {idx} (duration: {video_duration:.2f}s)")

            # Concatenate all normalized streams
            # FFmpeg concat expects interleaved video/audio pairs: [v0][a0][v1][a1]...
            interleaved_inputs = ''.join(f"[v{i}][a{i}]" for i in range(len(video_paths)))

            filter_complex = ';'.join(filter_parts) + ';'
            filter_complex += f"{interleaved_inputs}concat=n={len(video_paths)}:v=1:a=1[outv][outa]"

            # Get quality preset settings from FFmpegUtils (consistent with segment processing)
            quality_preset = FFmpegUtils.get_quality_preset(quality)
            crf = str(quality_preset.get('crf', 23))
            preset = quality_preset.get('preset', 'medium')
            audio_bitrate = quality_preset.get('audio_bitrate', '192k')

            logger.info(f"Using quality preset: {quality} -> crf={crf}, preset={preset}")

            # Build FFmpeg command
            command = [settings.FFMPEG_PATH]

            # Add all input files
            for video_path in video_paths:
                command.extend(['-i', video_path])

            # Add filter complex and output settings
            command.extend([
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', 'libx264',
                '-preset', preset,
                '-crf', crf,
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', audio_bitrate,
                '-y',
                output_path
            ])

            logger.info("Combining videos with scaling/normalization (this may take a while)...")
            # Add timeout to prevent infinite hang (30 minutes for complex operations)
            result = subprocess.run(command, capture_output=True, text=True, timeout=1800)

            if result.returncode == 0:
                duration = FFmpegUtils.get_media_duration(output_path)
                size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                logger.info(f"✅ Videos combined successfully! Duration: {duration:.2f}s, Size: {size_mb:.1f}MB")
                return True
            else:
                logger.error(f"❌ Video combination failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ Video combination timed out after 1800 seconds")
            return False
        except Exception as e:
            logger.error(f"❌ Error combining videos: {e}")
            return False

    @staticmethod
    async def combine_videos_complex_async(
        video_paths: List[str],
        output_path: str,
        common_specs: dict,
        quality: str = "balanced",
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Combine videos with scaling/fps conversion (slower, handles different specs)
        ASYNC version - non-blocking for server operations

        Args:
            video_paths: List of video file paths to combine
            output_path: Output file path
            common_specs: Common specifications dictionary
            quality: Export quality (lossless, high, balanced)
            progress_callback: Optional async progress callback

        Returns:
            True if successful
        """
        try:
            # Calculate total duration for progress tracking
            total_duration = 0
            for video_path in video_paths:
                duration = FFmpegUtils.get_media_duration(video_path)
                if duration:
                    total_duration += duration

            if total_duration == 0:
                logger.error("Could not calculate total duration for progress tracking")
                total_duration = 60  # Fallback estimate

            target_width = common_specs['width']
            target_height = common_specs['height']
            target_fps = common_specs['fps']

            logger.info(f"Combining videos with normalization (async):")
            logger.info(f"  Target resolution: {target_width}x{target_height}")
            logger.info(f"  Target FPS: {target_fps}")

            # Build filter complex for each input
            # First, check which videos have audio streams
            video_audio_info = []
            for idx, video_path in enumerate(video_paths):
                has_audio = FFmpegUtils.has_audio_stream(video_path)
                video_audio_info.append((idx, has_audio))
                logger.debug(f"Video {idx} ({video_path}): has_audio={has_audio}")

            filter_parts = []
            for idx, video_path in enumerate(video_paths):
                # Scale and set FPS for each input
                filter_parts.append(
                    f"[{idx}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                    f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
                    f"fps={target_fps},setsar=1[v{idx}]"
                )

                # Handle audio - generate silent audio for videos without audio stream
                has_audio = video_audio_info[idx][1]
                if has_audio:
                    # Video has audio - pass through with anull (maintains format)
                    filter_parts.append(f"[{idx}:a]anull[a{idx}]")
                else:
                    # Video has no audio - generate silent audio matching video duration
                    video_duration = FFmpegUtils.get_media_duration(video_path) or 10
                    filter_parts.append(
                        f"aevalsrc=0:d={video_duration:.3f}:s=44100:c=stereo[a{idx}]"
                    )
                    logger.info(f"Generated silent audio for video {idx} (duration: {video_duration:.2f}s)")

            # Concatenate all normalized streams
            interleaved_inputs = ''.join(f"[v{i}][a{i}]" for i in range(len(video_paths)))

            filter_complex = ';'.join(filter_parts) + ';'
            filter_complex += f"{interleaved_inputs}concat=n={len(video_paths)}:v=1:a=1[outv][outa]"

            # Quality settings
            if quality == "lossless":
                crf = "0"
                preset = "slow"
            elif quality == "high":
                crf = "18"
                preset = "slow"
            else:  # balanced
                crf = "23"
                preset = "medium"

            # Build FFmpeg command
            command = [settings.FFMPEG_PATH]

            # Add all input files
            for video_path in video_paths:
                command.extend(['-i', video_path])

            # Add filter complex and output settings
            command.extend([
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', 'libx264',
                '-preset', preset,
                '-crf', crf,
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-y',
                output_path
            ])

            logger.info("Combining videos async with scaling/normalization...")

            success, error = await run_ffmpeg_with_progress(
                command,
                total_duration,
                progress_callback,
                "Combining videos (complex)",
                timeout=1800  # 30 minutes for complex operations
            )

            if success:
                duration = FFmpegUtils.get_media_duration(output_path)
                size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                logger.info(f"✅ Videos combined successfully! Duration: {duration:.2f}s, Size: {size_mb:.1f}MB")
                return True
            else:
                logger.error(f"❌ Video combination failed: {error}")
                return False

        except Exception as e:
            logger.error(f"❌ Error combining videos: {e}")
            return False

    @classmethod
    def combine_project_videos(
        cls,
        videos: List[Video],
        processed_video_paths: List[str],
        output_path: str,
        temp_dir: Path,
        quality: str = "balanced",
        force_export: bool = False
    ) -> bool:
        """
        Combine multiple processed videos from a project
        SYNC version - use combine_project_videos_async for non-blocking operation

        Args:
            videos: List of Video model instances (for compatibility checking)
            processed_video_paths: List of processed video file paths (in order)
            output_path: Output file path
            temp_dir: Temporary directory
            quality: Export quality
            force_export: Force export even if videos are incompatible

        Returns:
            True if successful
        """
        # Check compatibility
        is_compatible, warnings, common_specs = cls.check_compatibility(videos)

        if not is_compatible:
            if force_export:
                logger.warning("Videos are not compatible but forcing combination:")
                for warning in warnings:
                    logger.warning(f"  • {warning}")
                # Calculate common specs even for incompatible videos
                if not common_specs:
                    # Build common specs for force export
                    resolutions = [(v.width, v.height) for v in videos if v.width and v.height]
                    fps_values = [v.fps for v in videos if v.fps]

                    if resolutions:
                        target_width = max(r[0] for r in resolutions)
                        target_height = max(r[1] for r in resolutions)
                    else:
                        target_width, target_height = 1920, 1080

                    target_fps = max(fps_values) if fps_values else 30.0

                    common_specs = {
                        'width': target_width,
                        'height': target_height,
                        'fps': target_fps,
                        'orientation': videos[0].orientation if videos else 'horizontal',
                        'needs_scaling': True,
                        'needs_fps_conversion': True,
                        'needs_reencoding': True
                    }
            else:
                logger.error("Videos are not compatible for combination:")
                for warning in warnings:
                    logger.error(f"  • {warning}")
                return False

        # Display warnings
        if warnings:
            logger.warning("Video combination warnings:")
            for warning in warnings:
                logger.warning(f"  • {warning}")

        # Decide combination strategy
        if force_export or common_specs.get('needs_scaling') or common_specs.get('needs_fps_conversion') or common_specs.get('needs_reencoding'):
            # Use complex filter for normalization
            logger.info("Using advanced combination (with normalization)")
            return cls.combine_videos_complex(processed_video_paths, output_path, common_specs, quality)
        else:
            # Use simple concat for speed
            logger.info("Using fast combination (direct concatenation)")
            success = cls.combine_videos_simple(processed_video_paths, output_path, temp_dir)

            # If simple concat fails, fall back to complex
            if not success:
                logger.warning("Fast combination failed, trying advanced method...")
                return cls.combine_videos_complex(processed_video_paths, output_path, common_specs, quality)

            return success

    @classmethod
    async def combine_project_videos_async(
        cls,
        videos: List[Video],
        processed_video_paths: List[str],
        output_path: str,
        temp_dir: Path,
        quality: str = "balanced",
        force_export: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Combine multiple processed videos from a project
        ASYNC version - non-blocking for server operations

        Args:
            videos: List of Video model instances (for compatibility checking)
            processed_video_paths: List of processed video file paths (in order)
            output_path: Output file path
            temp_dir: Temporary directory
            quality: Export quality
            force_export: Force export even if videos are incompatible
            progress_callback: Optional async progress callback

        Returns:
            True if successful
        """
        # Check compatibility
        is_compatible, warnings, common_specs = cls.check_compatibility(videos)

        if not is_compatible:
            if force_export:
                logger.warning("Videos are not compatible but forcing combination:")
                for warning in warnings:
                    logger.warning(f"  • {warning}")
                # Calculate common specs even for incompatible videos
                if not common_specs:
                    # Build common specs for force export
                    resolutions = [(v.width, v.height) for v in videos if v.width and v.height]
                    fps_values = [v.fps for v in videos if v.fps]

                    if resolutions:
                        target_width = max(r[0] for r in resolutions)
                        target_height = max(r[1] for r in resolutions)
                    else:
                        target_width, target_height = 1920, 1080

                    target_fps = max(fps_values) if fps_values else 30.0

                    common_specs = {
                        'width': target_width,
                        'height': target_height,
                        'fps': target_fps,
                        'orientation': videos[0].orientation if videos else 'horizontal',
                        'needs_scaling': True,
                        'needs_fps_conversion': True,
                        'needs_reencoding': True
                    }
            else:
                logger.error("Videos are not compatible for combination:")
                for warning in warnings:
                    logger.error(f"  • {warning}")
                return False

        # Display warnings
        if warnings:
            logger.warning("Video combination warnings:")
            for warning in warnings:
                logger.warning(f"  • {warning}")

        # Decide combination strategy
        if force_export or common_specs.get('needs_scaling') or common_specs.get('needs_fps_conversion') or common_specs.get('needs_reencoding'):
            # Use complex filter for normalization
            logger.info("Using advanced combination async (with normalization)")
            return await cls.combine_videos_complex_async(
                processed_video_paths, output_path, common_specs, quality, progress_callback
            )
        else:
            # Use simple concat for speed
            logger.info("Using fast combination async (direct concatenation)")
            success = await cls.combine_videos_simple_async(
                processed_video_paths, output_path, temp_dir, progress_callback
            )

            # If simple concat fails, fall back to complex
            if not success:
                logger.warning("Fast combination failed, trying advanced method...")
                return await cls.combine_videos_complex_async(
                    processed_video_paths, output_path, common_specs, quality, progress_callback
                )

            return success
