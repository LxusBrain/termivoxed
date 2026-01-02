"""Video management API routes"""

import os
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pydantic import BaseModel
from typing import Optional

from models import Project
from backend.ffmpeg_utils import FFmpegUtils
from config import settings
from web_ui.api.utils.security import (
    validate_video_path,
    validate_audio_path,
    sanitize_filename,
)
from web_ui.api.middleware.auth import get_current_user, AuthenticatedUser


def _verify_project_ownership(project: Project, user: AuthenticatedUser) -> None:
    """
    Verify that the user owns the project.

    SECURITY: Prevents users from accessing other users' projects.

    Rules:
    1. If project has user_id, only that user (or admin) can access
    2. If project has no user_id (legacy), only admin can access
    3. Admins can access any project

    Args:
        project: The project to check
        user: The authenticated user

    Raises:
        HTTPException: 404 if user doesn't own the project
        HTTPException: 403 if legacy project and user is not admin
    """
    # Admins can access any project
    if user.is_admin:
        return

    # Legacy projects (no user_id) - require admin access
    if project.user_id is None:
        raise HTTPException(
            status_code=403,
            detail="This is a legacy project. Admin access required to modify."
        )

    # Regular ownership check
    if project.user_id != user.uid:
        # User doesn't own this project - return 404 to not leak existence
        raise HTTPException(status_code=404, detail="Project not found")


class ReplaceVideoPathRequest(BaseModel):
    """Request body for replacing video file path"""
    new_path: str

router = APIRouter()


@router.get("/{project_name}/availability")
async def check_videos_availability(
    project_name: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Check availability of all video files in a project.

    Returns detailed status for each video including:
    - Whether the file exists on disk
    - Whether the file is readable
    - Any error messages for unavailable files
    """
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    results = []
    all_available = True

    for video in project.videos:
        exists = os.path.exists(video.path)
        readable = False
        error_message = None

        if exists:
            try:
                # Quick read test to ensure file is accessible
                with open(video.path, 'rb') as f:
                    f.read(1024)  # Read first 1KB
                readable = True
            except PermissionError:
                error_message = "Permission denied"
            except Exception as e:
                error_message = str(e)
        else:
            error_message = "File not found"

        is_available = exists and readable
        if not is_available:
            all_available = False

        results.append({
            "id": video.id,
            "name": video.name,
            "path": video.path,
            "available": is_available,
            "exists": exists,
            "readable": readable,
            "error": error_message
        })

    return {
        "project_name": project_name,
        "all_available": all_available,
        "unavailable_count": sum(1 for r in results if not r["available"]),
        "videos": results
    }


@router.get("/{project_name}/{video_id}")
async def get_video_details(
    project_name: str,
    video_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get detailed information about a video"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    video = project.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "id": video.id,
        "name": video.name,
        "path": video.path,
        "order": video.order,
        "duration": video.duration,
        "width": video.width,
        "height": video.height,
        "fps": video.fps,
        "codec": video.codec,
        "aspect_ratio": video.aspect_ratio,
        "orientation": video.orientation,
        "segments": [
            {
                "id": seg.id,
                "name": seg.name,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "text": seg.text,
                "language": seg.language
            }
            for seg in video.timeline.segments
        ]
    }


@router.get("/{project_name}/{video_id}/stream")
async def stream_video(
    project_name: str,
    video_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Stream video file for preview"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    video = project.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not os.path.exists(video.path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    # Determine correct media type based on file extension
    # Reference: FFmpeg documentation supported container formats
    ext = Path(video.path).suffix.lower()
    media_type_map = {
        # MOV/MP4 family
        ".mp4": "video/mp4",
        ".m4v": "video/x-m4v",
        ".mov": "video/quicktime",
        ".3gp": "video/3gpp",
        ".3g2": "video/3gpp2",
        # Matroska family
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        # AVI
        ".avi": "video/x-msvideo",
        # Flash Video
        ".flv": "video/x-flv",
        ".f4v": "video/x-f4v",
        # MPEG
        ".ts": "video/mp2t",
        ".mts": "video/mp2t",
        ".m2ts": "video/mp2t",
        ".mpg": "video/mpeg",
        ".mpeg": "video/mpeg",
        ".m2v": "video/mpeg",
        ".vob": "video/dvd",
        # Windows Media
        ".wmv": "video/x-ms-wmv",
        ".asf": "video/x-ms-asf",
        # Ogg
        ".ogg": "video/ogg",
        ".ogv": "video/ogg",
        # Other formats
        ".dv": "video/x-dv",
        ".gif": "image/gif",
        ".mxf": "application/mxf",
    }
    media_type = media_type_map.get(ext, "video/mp4")  # Default to video/mp4

    return FileResponse(
        video.path,
        media_type=media_type,
        filename=os.path.basename(video.path)
    )


@router.get("/{project_name}/{video_id}/thumbnail")
async def get_video_thumbnail(
    project_name: str,
    video_id: str,
    time: float = 0,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get video thumbnail at specific time"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    video = project.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Generate thumbnail using ffmpeg
    thumbnail_path = Path(settings.TEMP_DIR) / f"thumb_{video_id}_{int(time)}.jpg"

    if not thumbnail_path.exists():
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(time),
            "-i", video.path,
            "-vframes", "1",
            "-q:v", "2",
            str(thumbnail_path)
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

    return FileResponse(thumbnail_path, media_type="image/jpeg")


@router.get("/{project_name}/{video_id}/keyframes")
async def extract_keyframes(
    project_name: str,
    video_id: str,
    count: int = 5,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Extract keyframes from video for AI description"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    video = project.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.duration:
        raise HTTPException(status_code=400, detail="Video duration unknown")

    # Calculate evenly spaced timestamps
    interval = video.duration / (count + 1)
    timestamps = [interval * (i + 1) for i in range(count)]

    keyframes = []
    for i, ts in enumerate(timestamps):
        thumb_path = Path(settings.TEMP_DIR) / f"keyframe_{video_id}_{i}.jpg"

        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ts),
            "-i", video.path,
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_path)
        ]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode == 0:
            keyframes.append({
                "index": i,
                "timestamp": ts,
                "path": f"/storage/temp/keyframe_{video_id}_{i}.jpg"
            })

    return {"keyframes": keyframes, "video_duration": video.duration}


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Upload a new video file with tier-based size limits"""
    # SECURITY: Enforce file size limits to prevent DoS
    # Tier-based limits (in bytes):
    # - free_trial: 500 MB
    # - individual: 2 GB
    # - pro: 5 GB
    # - enterprise: 10 GB
    tier_limits = {
        "free_trial": 500 * 1024 * 1024,      # 500 MB
        "individual": 2 * 1024 * 1024 * 1024,  # 2 GB
        "pro": 5 * 1024 * 1024 * 1024,         # 5 GB
        "enterprise": 10 * 1024 * 1024 * 1024, # 10 GB
    }
    max_size = tier_limits.get(user.subscription_tier.value, tier_limits["free_trial"])
    max_size_mb = max_size / (1024 * 1024)

    # Check Content-Length header for early rejection
    if hasattr(file, 'size') and file.size:
        if file.size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size for {user.subscription_tier.value} tier: {max_size_mb:.0f} MB"
            )

    # Sanitize filename to prevent directory traversal
    safe_filename = sanitize_filename(file.filename)

    # Validate file type - All formats supported by FFmpeg
    # Reference: FFmpeg documentation (ffmpeg-all demuxers/muxers sections)
    allowed_video_types = [
        # Common containers (MOV/MP4 family - Section 20/21 ffmpeg-all)
        ".mp4", ".m4v", ".mov", ".3gp", ".3g2", ".mj2",
        # Matroska family (Section 21 ffmpeg-all)
        ".mkv", ".webm", ".mka", ".mks",
        # AVI (Section 21 ffmpeg-all)
        ".avi",
        # Flash Video (Section 20/21 ffmpeg-all)
        ".flv", ".f4v",
        # MPEG Transport/Program Stream (Section 20/21 ffmpeg-all)
        ".ts", ".mts", ".m2ts", ".mpg", ".mpeg", ".m2v", ".vob",
        # Windows Media (ASF Section 20/21 ffmpeg-all)
        ".wmv", ".asf",
        # Ogg container (Section 21 ffmpeg-all)
        ".ogg", ".ogv",
        # DV Video (Section 21 ffmpeg-all)
        ".dv",
        # Animated images (Section 20/21 ffmpeg-all)
        ".gif", ".apng",
        # AVIF (Section 21 ffmpeg-all)
        ".avif",
        # NUT container (Section 21 ffmpeg-all)
        ".nut",
        # Material eXchange Format (Section 21 ffmpeg-all)
        ".mxf",
        # RealMedia
        ".rm", ".rmvb",
        # Raw video formats
        ".yuv", ".y4m",
        # Additional common formats
        ".divx", ".xvid", ".264", ".265", ".hevc",
    ]
    ext = Path(safe_filename).suffix.lower()

    if ext not in allowed_video_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Supported video formats: {', '.join(sorted(set(allowed_video_types)))}"
        )

    # Save uploaded file
    upload_dir = Path(settings.STORAGE_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / safe_filename

    # Handle duplicate names
    counter = 1
    while file_path.exists():
        stem = Path(safe_filename).stem
        file_path = upload_dir / f"{stem}_{counter}{ext}"
        counter += 1

    try:
        # Stream file to disk with size limit enforcement
        # Read in 1MB chunks to avoid memory issues with large files
        total_size = 0
        chunk_size = 1024 * 1024  # 1 MB chunks

        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)

                # SECURITY: Enforce size limit during streaming
                if total_size > max_size:
                    f.close()
                    os.unlink(file_path)  # Remove partial file
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size for {user.subscription_tier.value} tier: {max_size_mb:.0f} MB"
                    )
                f.write(chunk)

        # Get video info
        duration = FFmpegUtils.get_media_duration(str(file_path))
        video_info = FFmpegUtils.get_video_info(str(file_path))

        # Calculate orientation from dimensions
        width = video_info.get("width") if video_info else None
        height = video_info.get("height") if video_info else None
        orientation = None
        if width and height:
            aspect_ratio = width / height
            if aspect_ratio > 1.1:
                orientation = "horizontal"
            elif aspect_ratio < 0.9:
                orientation = "vertical"
            else:
                orientation = "square"

        return {
            "path": str(file_path),
            "filename": file_path.name,
            "duration": duration,
            "width": width,
            "height": height,
            "fps": video_info.get("fps") if video_info else None,
            "orientation": orientation
        }

    except Exception as e:
        # Cleanup on failure
        if file_path.exists():
            os.unlink(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Upload an audio file (for background music) with size limits"""
    # SECURITY: Enforce file size limits for audio files
    # Audio files are smaller, so limits are reduced
    max_audio_size = 100 * 1024 * 1024  # 100 MB for all tiers
    max_size_mb = max_audio_size / (1024 * 1024)

    if hasattr(file, 'size') and file.size and file.size > max_audio_size:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large. Maximum size: {max_size_mb:.0f} MB"
        )

    # Sanitize filename to prevent directory traversal
    safe_filename = sanitize_filename(file.filename)
    # Validate file type - All audio formats supported by FFmpeg
    # Reference: FFmpeg documentation (ffmpeg-all demuxers/muxers, ffmpeg-codec audio sections)
    allowed_audio_types = [
        # Common lossy formats
        ".mp3",                    # MPEG-3 audio (Section 21 ffmpeg-all)
        ".aac",                    # Advanced Audio Coding
        ".m4a", ".m4b", ".m4p",    # MPEG-4 Audio containers
        ".ogg", ".oga",            # Ogg Vorbis/Opus (Section 21 ffmpeg-all)
        ".opus",                   # Opus audio (Section 8 ffmpeg-codec)
        ".wma",                    # Windows Media Audio
        ".amr",                    # Adaptive Multi-Rate (Section 21 ffmpeg-all)
        ".ac3", ".eac3",           # Dolby Digital (Section 5/8 ffmpeg-codec)
        ".dts",                    # DTS audio
        # Lossless formats
        ".wav", ".wave",           # WAV audio (Section 20 ffmpeg-all)
        ".flac",                   # Free Lossless Audio Codec (Section 21 ffmpeg-all)
        ".alac",                   # Apple Lossless
        ".aiff", ".aif", ".aifc",  # AIFF audio (Section 21 ffmpeg-all)
        ".ape",                    # Monkey's Audio
        ".wv",                     # WavPack (Section 8 ffmpeg-codec)
        ".tta",                    # True Audio
        ".w64",                    # Sony Wave64 (Section 20 ffmpeg-all)
        # Other formats
        ".au", ".snd",             # Sun AU audio (Section 21 ffmpeg-all)
        ".caf",                    # Core Audio Format (Section 21 ffmpeg-all)
        ".mka",                    # Matroska Audio (Section 21 ffmpeg-all)
        ".ra", ".ram",             # RealAudio
        ".mid", ".midi",           # MIDI
        ".mod", ".s3m", ".xm", ".it",  # Tracker modules (Section 20 ffmpeg-all - libmodplug)
        ".mmf",                    # Yamaha Mobile Audio (Section 21 ffmpeg-all)
        ".gsm",                    # GSM audio (Section 5 ffmpeg-codec)
        ".spx",                    # Speex audio
        ".webm",                   # WebM audio
    ]
    ext = Path(safe_filename).suffix.lower()

    if ext not in allowed_audio_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audio file type '{ext}'. Supported audio formats: {', '.join(sorted(set(allowed_audio_types)))}"
        )

    # Save uploaded file to audio directory
    upload_dir = Path(settings.STORAGE_DIR) / "audio"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / safe_filename

    # Handle duplicate names
    counter = 1
    while file_path.exists():
        stem = Path(safe_filename).stem
        file_path = upload_dir / f"{stem}_{counter}{ext}"
        counter += 1

    try:
        # Stream file to disk with size limit enforcement
        total_size = 0
        chunk_size = 1024 * 1024  # 1 MB chunks

        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)

                # SECURITY: Enforce size limit during streaming
                if total_size > max_audio_size:
                    f.close()
                    os.unlink(file_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Audio file too large. Maximum size: {max_size_mb:.0f} MB"
                    )
                f.write(chunk)

        # Get audio duration
        duration = FFmpegUtils.get_media_duration(str(file_path))

        return {
            "path": str(file_path),
            "filename": file_path.name,
            "duration": duration
        }

    except Exception as e:
        # Cleanup on failure
        if file_path.exists():
            os.unlink(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_video_info(path: str, user: AuthenticatedUser = Depends(get_current_user)):
    """Get information about a video file"""
    # Validate path for security (prevents path traversal)
    validated_path = validate_video_path(path, must_exist=True)

    duration = FFmpegUtils.get_media_duration(validated_path)
    info = FFmpegUtils.get_video_info(validated_path)
    has_audio = FFmpegUtils.has_audio_stream(validated_path)

    return {
        "path": validated_path,
        "duration": duration,
        "has_audio": has_audio,
        "width": info.get("width") if info else None,
        "height": info.get("height") if info else None,
        "fps": info.get("fps") if info else None,
        "codec": info.get("codec") if info else None
    }


@router.put("/{project_name}/{video_id}/path")
async def replace_video_path(
    project_name: str,
    video_id: str,
    request: ReplaceVideoPathRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Replace video file path (for re-linking missing videos).

    Updates the video's file path and re-probes video metadata.
    Use this when a video file has been moved or deleted and you want
    to re-link it to a new file.
    """
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project before allowing modifications
    _verify_project_ownership(project, user)

    video = project.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Validate the new path for security (prevents path traversal)
    validated_path = validate_video_path(request.new_path, must_exist=True)

    # Store old path for reference
    old_path = video.path

    # Update path
    video.path = validated_path

    # Re-probe video metadata
    video_info = FFmpegUtils.get_video_info(validated_path)
    if video_info:
        video.duration = FFmpegUtils.get_media_duration(validated_path)
        video.width = video_info.get("width")
        video.height = video_info.get("height")
        video.fps = video_info.get("fps")
        video.codec = video_info.get("codec")

    # Save project
    project.save()

    return {
        "message": "Video path updated successfully",
        "video_id": video_id,
        "old_path": old_path,
        "new_path": validated_path,
        "duration": video.duration,
        "width": video.width,
        "height": video.height
    }
