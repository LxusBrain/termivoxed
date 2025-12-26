"""Project management API routes"""

import os
import sys
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from models import Project
from web_ui.api.schemas.project_schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectListItem,
    ProjectStats,
    AddVideoRequest,
    ReorderVideosRequest,
    SetActiveVideoRequest,
    VideoInfo,
    BGMTrackInfo,
    AddBGMTrackRequest,
    UpdateBGMTrackRequest,
    ReorderBGMTracksRequest,
    UpdateVolumeSettingsRequest,
)

router = APIRouter()


def _project_to_response(project: Project) -> ProjectResponse:
    """Convert Project model to API response"""
    videos = []
    total_segments = 0

    for video in project.videos:
        seg_count = len(video.timeline.segments)
        total_segments += seg_count
        # Check if video file exists on disk
        video_file_exists = os.path.exists(video.path)
        videos.append(VideoInfo(
            id=video.id,
            name=video.name,
            path=video.path,
            order=video.order,
            duration=video.duration,
            width=video.width,
            height=video.height,
            fps=video.fps,
            codec=video.codec,
            aspect_ratio=video.aspect_ratio,
            orientation=video.orientation,
            segments_count=seg_count,
            file_exists=video_file_exists,
            timeline_start=video.timeline_start,
            timeline_end=video.timeline_end
        ))

    # Convert BGM tracks to response format
    bgm_tracks = [
        BGMTrackInfo(
            id=track.id,
            name=track.name,
            path=track.path,
            start_time=track.start_time,
            end_time=track.end_time,
            volume=track.volume,
            fade_in=track.fade_in,
            fade_out=track.fade_out,
            loop=track.loop,
            muted=track.muted,
            order=track.order,
            duration=track.duration
        )
        for track in project.bgm_tracks
    ]

    return ProjectResponse(
        name=project.name,
        videos=videos,
        active_video_id=project.active_video_id,
        created_at=project.created_at,
        modified_at=project.modified_at,
        background_music_path=project.background_music_path,
        bgm_tracks=bgm_tracks,
        bgm_volume=project.bgm_volume,
        tts_volume=project.tts_volume,
        export_quality=project.export_quality,
        include_subtitles=project.include_subtitles,
        total_segments=total_segments
    )


@router.get("", response_model=List[ProjectListItem])
@router.get("/", response_model=List[ProjectListItem], include_in_schema=False)
async def list_projects():
    """List all projects"""
    projects = Project.list_projects()
    return [ProjectListItem(**p) for p in projects]


@router.post("", response_model=ProjectResponse)
@router.post("/", response_model=ProjectResponse, include_in_schema=False)
async def create_project(request: ProjectCreate):
    """Create a new project"""
    # Validate video paths exist
    for path in request.video_paths:
        if not os.path.exists(path):
            raise HTTPException(status_code=400, detail=f"Video file not found: {path}")

    try:
        project = Project(name=request.name, video_paths=request.video_paths)
        project.save()
        return _project_to_response(project)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}", response_model=ProjectResponse)
async def get_project(project_name: str):
    """Get project details"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project)


@router.delete("/{project_name}")
async def delete_project(project_name: str):
    """Delete a project"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.delete():
        return {"message": "Project deleted successfully"}
    raise HTTPException(status_code=500, detail="Failed to delete project")


@router.get("/{project_name}/stats", response_model=ProjectStats)
async def get_project_stats(project_name: str):
    """Get project statistics"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stats = project.get_stats()
    return ProjectStats(**stats)


@router.post("/{project_name}/videos")
async def add_video_to_project(project_name: str, request: AddVideoRequest):
    """Add a video to an existing project"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not os.path.exists(request.video_path):
        raise HTTPException(status_code=400, detail="Video file not found")

    try:
        video = project.add_video(request.video_path, request.name)
        project.save()
        return {
            "message": "Video added successfully",
            "video_id": video.id,
            "video_name": video.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_name}/videos/{video_id}")
async def remove_video_from_project(project_name: str, video_id: str):
    """Remove a video from project"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.remove_video(video_id):
        project.save()
        return {"message": "Video removed successfully"}
    raise HTTPException(status_code=404, detail="Video not found in project")


@router.post("/{project_name}/videos/reorder")
async def reorder_videos(project_name: str, request: ReorderVideosRequest):
    """Reorder videos in project"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.reorder_videos(request.video_ids):
        project.save()
        return {"message": "Videos reordered successfully"}
    raise HTTPException(status_code=400, detail="Invalid video IDs")


@router.post("/{project_name}/active-video")
async def set_active_video(project_name: str, request: SetActiveVideoRequest):
    """Set the active video for editing"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.set_active_video(request.video_id):
        project.save()
        return {"message": "Active video set successfully"}
    raise HTTPException(status_code=404, detail="Video not found in project")


from pydantic import BaseModel
from typing import Optional as PydanticOptional

class ProjectSettingsUpdate(BaseModel):
    export_quality: PydanticOptional[str] = None
    include_subtitles: PydanticOptional[bool] = None
    background_music_path: PydanticOptional[str] = None

@router.put("/{project_name}/settings")
async def update_project_settings(
    project_name: str,
    settings: ProjectSettingsUpdate
):
    """Update project settings"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if settings.export_quality is not None:
        if settings.export_quality not in ["lossless", "high", "balanced"]:
            raise HTTPException(status_code=400, detail="Invalid quality setting")
        project.export_quality = settings.export_quality

    if settings.include_subtitles is not None:
        project.include_subtitles = settings.include_subtitles

    if settings.background_music_path is not None:
        if settings.background_music_path:
            # Handle both relative and absolute paths
            music_path = Path(settings.background_music_path)
            if not music_path.exists():
                raise HTTPException(status_code=400, detail=f"Background music file not found: {settings.background_music_path}")
        project.background_music_path = settings.background_music_path

    project.save()
    return {"message": "Settings updated successfully"}


@router.get("/{project_name}/compatibility")
async def check_video_compatibility(project_name: str):
    """Check if videos in project are compatible for combination"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    is_compatible, warnings = project.check_video_compatibility()
    return {
        "compatible": is_compatible,
        "warnings": warnings
    }


# ============================================================
# BGM Track Endpoints
# ============================================================

@router.get("/{project_name}/bgm-tracks", response_model=List[BGMTrackInfo])
async def get_bgm_tracks(project_name: str):
    """Get all BGM tracks for a project"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return [
        BGMTrackInfo(
            id=track.id,
            name=track.name,
            path=track.path,
            start_time=track.start_time,
            end_time=track.end_time,
            volume=track.volume,
            fade_in=track.fade_in,
            fade_out=track.fade_out,
            loop=track.loop,
            muted=track.muted,
            order=track.order,
            duration=track.duration
        )
        for track in project.bgm_tracks
    ]


@router.post("/{project_name}/bgm-tracks", response_model=BGMTrackInfo)
async def add_bgm_track(project_name: str, request: AddBGMTrackRequest):
    """Add a new BGM track to the project"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate the audio file exists
    if not os.path.exists(request.path):
        raise HTTPException(status_code=400, detail=f"Audio file not found: {request.path}")

    try:
        track = project.add_bgm_track(
            path=request.path,
            name=request.name,
            start_time=request.start_time,
            end_time=request.end_time,
            volume=request.volume
        )
        project.save()

        return BGMTrackInfo(
            id=track.id,
            name=track.name,
            path=track.path,
            start_time=track.start_time,
            end_time=track.end_time,
            volume=track.volume,
            fade_in=track.fade_in,
            fade_out=track.fade_out,
            loop=track.loop,
            muted=track.muted,
            order=track.order,
            duration=track.duration
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}/bgm-tracks/{track_id}", response_model=BGMTrackInfo)
async def get_bgm_track(project_name: str, track_id: str):
    """Get a specific BGM track"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    track = project.get_bgm_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="BGM track not found")

    return BGMTrackInfo(
        id=track.id,
        name=track.name,
        path=track.path,
        start_time=track.start_time,
        end_time=track.end_time,
        volume=track.volume,
        fade_in=track.fade_in,
        fade_out=track.fade_out,
        loop=track.loop,
        muted=track.muted,
        order=track.order,
        duration=track.duration
    )


@router.put("/{project_name}/bgm-tracks/{track_id}", response_model=BGMTrackInfo)
async def update_bgm_track(project_name: str, track_id: str, request: UpdateBGMTrackRequest):
    """Update a BGM track"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate path if provided
    if request.path and not os.path.exists(request.path):
        raise HTTPException(status_code=400, detail=f"Audio file not found: {request.path}")

    # Build update kwargs from non-None values
    update_kwargs = {k: v for k, v in request.model_dump().items() if v is not None}

    track = project.update_bgm_track(track_id, **update_kwargs)
    if not track:
        raise HTTPException(status_code=404, detail="BGM track not found")

    project.save()

    return BGMTrackInfo(
        id=track.id,
        name=track.name,
        path=track.path,
        start_time=track.start_time,
        end_time=track.end_time,
        volume=track.volume,
        fade_in=track.fade_in,
        fade_out=track.fade_out,
        loop=track.loop,
        muted=track.muted,
        order=track.order,
        duration=track.duration
    )


@router.delete("/{project_name}/bgm-tracks/{track_id}")
async def delete_bgm_track(project_name: str, track_id: str):
    """Delete a BGM track"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.remove_bgm_track(track_id):
        project.save()
        return {"message": "BGM track deleted successfully"}

    raise HTTPException(status_code=404, detail="BGM track not found")


@router.post("/{project_name}/bgm-tracks/reorder")
async def reorder_bgm_tracks(project_name: str, request: ReorderBGMTracksRequest):
    """Reorder BGM tracks"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.reorder_bgm_tracks(request.track_ids):
        project.save()
        return {"message": "BGM tracks reordered successfully"}

    raise HTTPException(status_code=400, detail="Invalid track IDs")


@router.put("/{project_name}/volume-settings")
async def update_volume_settings(project_name: str, request: UpdateVolumeSettingsRequest):
    """Update global BGM and TTS volume settings"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.bgm_volume is not None:
        if not 0 <= request.bgm_volume <= 200:
            raise HTTPException(status_code=400, detail="BGM volume must be between 0 and 200")
        project.bgm_volume = request.bgm_volume

    if request.tts_volume is not None:
        if not 0 <= request.tts_volume <= 200:
            raise HTTPException(status_code=400, detail="TTS volume must be between 0 and 200")
        project.tts_volume = request.tts_volume

    project.save()
    return {
        "message": "Volume settings updated successfully",
        "bgm_volume": project.bgm_volume,
        "tts_volume": project.tts_volume
    }
