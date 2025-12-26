"""Video management API routes"""

import os
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from models import Project
from backend.ffmpeg_utils import FFmpegUtils
from config import settings

router = APIRouter()


@router.get("/{project_name}/{video_id}")
async def get_video_details(project_name: str, video_id: str):
    """Get detailed information about a video"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
async def stream_video(project_name: str, video_id: str):
    """Stream video file for preview"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    video = project.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not os.path.exists(video.path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    return FileResponse(
        video.path,
        media_type="video/mp4",
        filename=os.path.basename(video.path)
    )


@router.get("/{project_name}/{video_id}/thumbnail")
async def get_video_thumbnail(project_name: str, video_id: str, time: float = 0):
    """Get video thumbnail at specific time"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
async def extract_keyframes(project_name: str, video_id: str, count: int = 5):
    """Extract keyframes from video for AI description"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
async def upload_video(file: UploadFile = File(...)):
    """Upload a new video file"""
    # Validate file type
    allowed_types = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
    ext = Path(file.filename).suffix.lower()

    if ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )

    # Save uploaded file
    upload_dir = Path(settings.STORAGE_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / file.filename

    # Handle duplicate names
    counter = 1
    while file_path.exists():
        stem = Path(file.filename).stem
        file_path = upload_dir / f"{stem}_{counter}{ext}"
        counter += 1

    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Get video info
        duration = FFmpegUtils.get_media_duration(str(file_path))
        video_info = FFmpegUtils.get_video_info(str(file_path))

        return {
            "path": str(file_path),
            "filename": file_path.name,
            "duration": duration,
            "width": video_info.get("width") if video_info else None,
            "height": video_info.get("height") if video_info else None,
            "fps": video_info.get("fps") if video_info else None
        }

    except Exception as e:
        # Cleanup on failure
        if file_path.exists():
            os.unlink(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """Upload an audio file (for background music)"""
    # Validate file type
    allowed_types = [".mp3", ".wav", ".aac", ".ogg", ".m4a", ".flac"]
    ext = Path(file.filename).suffix.lower()

    if ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audio file type. Allowed: {', '.join(allowed_types)}"
        )

    # Save uploaded file to audio directory
    upload_dir = Path(settings.STORAGE_DIR) / "audio"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / file.filename

    # Handle duplicate names
    counter = 1
    while file_path.exists():
        stem = Path(file.filename).stem
        file_path = upload_dir / f"{stem}_{counter}{ext}"
        counter += 1

    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

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
async def get_video_info(path: str):
    """Get information about a video file"""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video file not found")

    duration = FFmpegUtils.get_media_duration(path)
    info = FFmpegUtils.get_video_info(path)
    has_audio = FFmpegUtils.has_audio_stream(path)

    return {
        "path": path,
        "duration": duration,
        "has_audio": has_audio,
        "width": info.get("width") if info else None,
        "height": info.get("height") if info else None,
        "fps": info.get("fps") if info else None,
        "codec": info.get("codec") if info else None
    }
