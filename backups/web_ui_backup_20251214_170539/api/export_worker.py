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
from backend.ffmpeg_utils import FFmpegUtils
from utils.logger import logger


async def generate_tts_for_segments(project: Project, segments_with_video: list):
    """Generate TTS audio for all segments that need it"""
    tts_service = TTSService()

    for i, (segment, video) in enumerate(segments_with_video):
        # Check if audio already exists
        if segment.audio_path and os.path.exists(segment.audio_path):
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
            audio_path, subtitle_path = await tts_service.generate_audio(
                text=segment.text,
                language=segment.language,
                voice=segment.voice_id,
                project_name=project.name,
                segment_name=segment.name.replace(" ", "_"),
                rate=segment.rate,
                volume=segment.volume,
                pitch=segment.pitch,
                orientation=orientation
            )
            segment.audio_path = audio_path
            segment.subtitle_path = subtitle_path

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

    return True, ""


async def run_export(
    project_name: str,
    output_path: str,
    quality: str,
    include_subtitles: bool,
    export_type: str,
    video_id: str = None,
    background_music_path: str = None
):
    """Run the export process"""
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

            for vid in sorted(project.videos, key=lambda v: v.order):
                for seg in vid.timeline.segments:
                    segments_with_video.append((seg, vid))
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

        if export_type == "single" and video_id:
            success = await pipeline.export_single_video(
                video,
                output_path,
                quality,
                include_subtitles,
                background_music_path,
                None
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
                None
            )
        else:
            success = await pipeline.export(
                output_path,
                quality,
                include_subtitles,
                background_music_path,
                None
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
            "message": "Usage: export_worker.py <project_name> <output_path> <quality> <include_subtitles> <export_type> [video_id] [bgm_path]"
        }), flush=True)
        sys.exit(1)

    project_name = sys.argv[1]
    output_path = sys.argv[2]
    quality = sys.argv[3]
    include_subtitles = sys.argv[4].lower() == 'true'
    export_type = sys.argv[5]
    video_id = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != 'None' else None
    background_music_path = sys.argv[7] if len(sys.argv) > 7 and sys.argv[7] != 'None' else None

    success = asyncio.run(run_export(
        project_name,
        output_path,
        quality,
        include_subtitles,
        export_type,
        video_id,
        background_music_path
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
