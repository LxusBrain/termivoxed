#!/usr/bin/env python3
"""
Export Worker - Standalone process for video export

This script is called as a subprocess from the API to handle
blocking FFmpeg operations without blocking the main server.

Usage:
    python export_worker.py <project_name> <output_path> <quality> <include_subtitles> <export_type> [video_id]
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models import Project
from core.export_pipeline import ExportPipeline
from backend.tts_service import TTSService
from backend.tts_providers import get_default_provider
from backend.ffmpeg_utils import FFmpegUtils
from utils.logger import logger


async def generate_tts_for_segments(project: Project, segments_with_video: list):
    """Generate TTS audio for all segments that need it"""
    from pathlib import Path

    tts_service = TTSService()

    for i, (segment, video) in enumerate(segments_with_video):
        # Check if audio already exists
        if segment.audio_path and os.path.exists(segment.audio_path):
            # Audio exists - check if subtitle needs to be generated
            subtitle_missing = not segment.subtitle_path or not os.path.exists(segment.subtitle_path)

            if subtitle_missing and getattr(segment, 'subtitle_enabled', True):
                # Generate missing subtitle for existing audio
                print(json.dumps({
                    "type": "progress",
                    "stage": "tts",
                    "message": f"Generating subtitle for cached audio: {segment.name}",
                    "progress": 10 + int(30 * i / max(len(segments_with_video), 1)),
                    "current_step": i + 1,
                    "total_steps": len(segments_with_video)
                }), flush=True)

                try:
                    orientation = video.orientation if video and video.orientation else 'horizontal'
                    audio_duration = FFmpegUtils.get_media_duration(segment.audio_path) or 10.0

                    # Generate subtitle path
                    audio_path_obj = Path(segment.audio_path)
                    subtitle_path = audio_path_obj.with_suffix('.srt')

                    # Use fallback subtitle generation
                    subtitle_content = tts_service._generate_accurate_subtitles_fallback(
                        segment.text, audio_duration, orientation
                    )
                    subtitle_path.write_text(subtitle_content, encoding="utf-8")
                    segment.subtitle_path = str(subtitle_path)
                    logger.info(f"Generated fallback subtitle for cached audio: {segment.name}")
                except Exception as e:
                    logger.warning(f"Failed to generate subtitle for cached audio {segment.name}: {e}")

            print(json.dumps({
                "type": "progress",
                "stage": "tts",
                "message": f"Using cached audio for: {segment.name}",
                "progress": 10 + int(30 * i / max(len(segments_with_video), 1)),
                "current_step": i + 1,
                "total_steps": len(segments_with_video)
            }), flush=True)
        else:
            print(json.dumps({
                "type": "progress",
                "stage": "tts",
                "message": f"Generating audio: {segment.name}",
                "progress": 10 + int(30 * i / max(len(segments_with_video), 1)),
                "current_step": i + 1,
                "total_steps": len(segments_with_video),
                "current_voice": segment.voice_id
            }), flush=True)

            orientation = video.orientation if video and video.orientation else 'horizontal'
            # Get voice cloning parameters if present
            voice_sample_id = getattr(segment, 'voice_sample_id', None)
            additional_sample_ids = getattr(segment, 'additional_sample_ids', None)

            audio_path, subtitle_path = await tts_service.generate_audio_with_provider(
                text=segment.text,
                language=segment.language,
                voice=segment.voice_id,
                project_name=project.name,
                segment_name=segment.name.replace(" ", "_"),
                rate=segment.rate,
                volume=segment.volume,
                pitch=segment.pitch,
                orientation=orientation,
                voice_sample_id=voice_sample_id,
                additional_sample_ids=additional_sample_ids
            )
            segment.audio_path = audio_path
            segment.subtitle_path = subtitle_path
            # Store the TTS provider used
            if voice_sample_id:
                segment.tts_provider = 'coqui'  # Voice cloning uses Coqui
            else:
                segment.tts_provider = get_default_provider().value

    # Save updated audio paths
    if segments_with_video:
        project.save()


def validate_project_data(project: 'Project', export_type: str, video_id: str = None) -> tuple[bool, str]:
    """
    Validate project data before export to prevent hangs and errors.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check project has videos
    if not project.videos:
        return False, "Project has no videos"

    # Validate video files exist
    for video in project.videos:
        if not os.path.exists(video.path):
            return False, f"Video file not found: {video.path}"

    # Validate specific video if single export
    if export_type == "single" and video_id:
        video = project.get_video(video_id)
        if not video:
            return False, f"Video {video_id} not found in project"

    # Validate BGM tracks if present
    if hasattr(project, 'bgm_tracks') and project.bgm_tracks:
        for track in project.bgm_tracks:
            if not track.muted and track.path:
                if not os.path.exists(track.path):
                    logger.warning(f"BGM track file not found, will skip: {track.path}")
                # Validate time ranges
                if track.end_time > 0 and track.start_time >= track.end_time:
                    logger.warning(f"BGM track has invalid time range: {track.name}")

    # Validate segments have valid time ranges
    for video in project.videos:
        if hasattr(video, 'timeline') and video.timeline:
            for segment in video.timeline.segments:
                if segment.start_time >= segment.end_time:
                    return False, f"Segment '{segment.name}' has invalid time range: {segment.start_time} >= {segment.end_time}"
                if segment.start_time < 0:
                    return False, f"Segment '{segment.name}' has negative start time"

    # Validate generic/project-level segments (multi-video projects)
    if hasattr(project, 'generic_segments') and project.generic_segments:
        for segment in project.generic_segments:
            if segment.start_time >= segment.end_time:
                return False, f"Generic segment '{segment.name}' has invalid time range: {segment.start_time} >= {segment.end_time}"
            if segment.start_time < 0:
                return False, f"Generic segment '{segment.name}' has negative start time"

    return True, ""


async def create_ffmpeg_progress_callback(base_progress: int = 45, max_progress: int = 95):
    """
    Create an async callback function that emits real-time FFmpeg progress as JSON.

    Args:
        base_progress: The starting progress value (45 = after segment processing)
        max_progress: The maximum progress value before completion (95)

    Returns:
        Async callback function that can be passed to FFmpeg functions
    """
    progress_range = max_progress - base_progress

    async def ffmpeg_progress_callback(progress_info: dict):
        """Callback that receives real-time FFmpeg progress and emits JSON"""

        # Check if this is a pre-formatted stage update (has 'message' but no 'speed')
        # These come from export_pipeline's direct stage updates
        if 'message' in progress_info and 'speed' not in progress_info:
            # Pass through as-is with type field
            output = {
                "type": "progress",
                **progress_info
            }
            print(json.dumps(output), flush=True)
            return

        # This is raw FFmpeg progress data - format it
        ffmpeg_pct = progress_info.get('progress', 0)
        overall_progress = base_progress + int((ffmpeg_pct / 100) * progress_range)

        # Build detailed progress message
        stage = progress_info.get('stage', 'Processing')
        eta = progress_info.get('eta_formatted', 'calculating...')
        eta_seconds = progress_info.get('eta_seconds', 0)
        speed = progress_info.get('speed', 0)
        bitrate = progress_info.get('bitrate', 'N/A')
        fps = progress_info.get('fps', 'N/A')

        # Build detail string for display
        detail_parts = []
        if speed and speed > 0:
            detail_parts.append(f"{speed:.1f}x speed")
        if bitrate and bitrate != 'N/A':
            detail_parts.append(f"{bitrate}")
        if fps and fps != 'N/A':
            detail_parts.append(f"{fps} fps")
        detail_parts.append(f"ETA: {eta}")

        detail = " | ".join(detail_parts)

        print(json.dumps({
            "type": "progress",
            "stage": "ffmpeg",
            "message": f"{stage}: {ffmpeg_pct}%",
            "progress": overall_progress,
            "detail": detail,
            # Top-level fields for frontend UI compatibility
            "eta_formatted": eta,
            "eta_seconds": eta_seconds,
            "processing_speed": speed if speed and speed > 0 else None,
            # Detailed FFmpeg info
            "ffmpeg_progress": {
                "percent": ffmpeg_pct,
                "speed": speed,
                "eta": eta,
                "bitrate": bitrate,
                "current_time": progress_info.get('current_time', 0),
                "total_duration": progress_info.get('total_duration', 0),
                "fps": fps,
                "frame": progress_info.get('frame', '0')
            }
        }), flush=True)

    return ffmpeg_progress_callback


async def run_export(
    project_name: str,
    output_path: str,
    quality: str,
    include_subtitles: bool,
    export_type: str,
    video_id: str = None,
    background_music_path: str = None,
    user_tier: str = "free_trial"
):
    """Run the export process

    Args:
        project_name: Name of the project to export
        output_path: Path to save the output video
        quality: Export quality (lossless, high, balanced)
        include_subtitles: Whether to include subtitles
        export_type: Type of export (single, combined, etc.)
        video_id: Optional video ID for single export
        background_music_path: Optional path to background music
        user_tier: User's subscription tier for watermark enforcement
    """
    try:
        # Load project
        project = Project.load(project_name)
        if not project:
            print(json.dumps({"type": "error", "message": "Project not found"}), flush=True)
            return False

        # Validate project data before starting
        is_valid, validation_error = validate_project_data(project, export_type, video_id)
        if not is_valid:
            print(json.dumps({"type": "error", "message": f"Validation failed: {validation_error}"}), flush=True)
            return False

        # Get video info and segments based on export type
        segments_with_video = []

        if export_type == "single" and video_id:
            video = project.get_video(video_id)
            if not video:
                print(json.dumps({"type": "error", "message": f"Video {video_id} not found"}), flush=True)
                return False
            segments = video.timeline.segments
            segments_with_video = [(seg, video) for seg in segments]
        elif export_type == "combined":
            video = project.get_active_video()
            if not video and len(project.videos) > 0:
                video = project.videos[0]
            if not video:
                print(json.dumps({"type": "error", "message": "No videos found"}), flush=True)
                return False

            # Add video-specific segments
            for vid in sorted(project.videos, key=lambda v: v.order):
                for seg in vid.timeline.segments:
                    segments_with_video.append((seg, vid))

            # Add generic/project-level segments (for multi-video projects)
            # Use first video as reference for these segments
            if hasattr(project, 'generic_segments') and project.generic_segments:
                first_video = project.videos[0] if project.videos else None
                for seg in project.generic_segments:
                    segments_with_video.append((seg, first_video))

            segments = [s for s, v in segments_with_video]
        else:
            video = project.get_active_video()
            if not video:
                print(json.dumps({"type": "error", "message": "No active video found"}), flush=True)
                return False
            segments = video.timeline.segments if hasattr(video, 'timeline') and video.timeline else []
            segments_with_video = [(seg, video) for seg in segments]

        # Stage 1: Preprocessing
        print(json.dumps({
            "type": "progress",
            "stage": "preprocessing",
            "message": "Checking video properties...",
            "progress": 0
        }), flush=True)

        has_audio = FFmpegUtils.has_audio_stream(video.path)
        if not has_audio:
            print(json.dumps({
                "type": "progress",
                "stage": "preprocessing",
                "message": "Video has no audio - will add silent track",
                "progress": 2
            }), flush=True)

        # Stage 2: Font check
        if include_subtitles:
            print(json.dumps({
                "type": "progress",
                "stage": "fonts",
                "message": "Checking subtitle fonts...",
                "progress": 5
            }), flush=True)

        # Stage 3: TTS Generation
        await generate_tts_for_segments(project, segments_with_video)

        # Stage 4: Video Processing
        print(json.dumps({
            "type": "progress",
            "stage": "segments",
            "message": "Processing video segments...",
            "progress": 40
        }), flush=True)

        pipeline = ExportPipeline(project)

        # Create the FFmpeg progress callback for real-time updates
        ffmpeg_callback = await create_ffmpeg_progress_callback(base_progress=45, max_progress=95)

        if export_type == "single" and video_id:
            success = await pipeline.export_single_video(
                video,
                output_path,
                quality,
                include_subtitles,
                background_music_path,
                None,  # progress_callback
                detailed_callback=ffmpeg_callback,
                user_tier=user_tier  # Pass user tier for watermark
            )
        elif export_type == "combined":
            print(json.dumps({
                "type": "progress",
                "stage": "segments",
                "message": "Combining multiple videos...",
                "progress": 45
            }), flush=True)
            success = await pipeline.export_combined_videos(
                output_path,
                quality,
                include_subtitles,
                background_music_path,
                None,  # progress_callback
                detailed_callback=ffmpeg_callback,
                user_tier=user_tier  # Pass user tier for watermark
            )
        else:
            success = await pipeline.export(
                output_path,
                quality,
                include_subtitles,
                background_music_path,
                None,  # progress_callback
                detailed_callback=ffmpeg_callback,
                user_tier=user_tier  # Pass user tier for watermark
            )

        if success:
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            file_size_mb = file_size / (1024 * 1024)

            print(json.dumps({
                "type": "progress",
                "stage": "completed",
                "message": f"Export completed! File size: {file_size_mb:.1f} MB",
                "progress": 100,
                "output_path": output_path
            }), flush=True)
            return True
        else:
            print(json.dumps({
                "type": "error",
                "message": "Export failed - check logs for details"
            }), flush=True)
            return False

    except Exception as e:
        print(json.dumps({
            "type": "error",
            "message": str(e)
        }), flush=True)
        logger.error(f"Export worker error: {e}")
        return False


def main():
    if len(sys.argv) < 6:
        print(json.dumps({
            "type": "error",
            "message": "Usage: export_worker.py <project_name> <output_path> <quality> <include_subtitles> <export_type> [video_id] [bgm_path] [user_tier]"
        }), flush=True)
        sys.exit(1)

    project_name = sys.argv[1]
    output_path = sys.argv[2]
    quality = sys.argv[3]
    include_subtitles = sys.argv[4].lower() == 'true'
    export_type = sys.argv[5]
    video_id = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != 'None' else None
    background_music_path = sys.argv[7] if len(sys.argv) > 7 and sys.argv[7] != 'None' else None
    # user_tier is required for watermark enforcement - default to free_trial if not provided
    user_tier = sys.argv[8] if len(sys.argv) > 8 and sys.argv[8] != 'None' else 'free_trial'

    success = asyncio.run(run_export(
        project_name,
        output_path,
        quality,
        include_subtitles,
        export_type,
        video_id,
        background_music_path,
        user_tier
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
