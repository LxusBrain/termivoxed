"""Segment management API routes"""

import sys
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config import settings
from models import Project
from web_ui.api.middleware.auth import get_current_user, AuthenticatedUser
from models.segment import Segment
from web_ui.api.schemas.segment_schemas import (
    SegmentCreate,
    SegmentUpdate,
    SegmentResponse,
    SegmentTimingAnalysis,
)
from web_ui.api.services.script_fitter import script_fitter

router = APIRouter()


def _convert_path_to_url(filepath: Optional[str]) -> Optional[str]:
    """
    Convert a filesystem path to a storage URL for frontend consumption.

    Handles:
    - None values (returns None)
    - Already converted URLs (starts with /storage/)
    - Absolute filesystem paths (extracts relative portion)
    - Relative paths (prepends /storage/)
    """
    if not filepath:
        return None

    # Already a URL
    if filepath.startswith('/storage/'):
        return filepath

    # Try to convert using STORAGE_DIR
    try:
        filepath_obj = Path(filepath)
        storage_dir = Path(settings.STORAGE_DIR)
        relative_path = filepath_obj.relative_to(storage_dir)
        return f"/storage/{relative_path}"
    except ValueError:
        pass

    # Fallback: extract from 'projects/' if present
    if '/projects/' in filepath:
        projects_index = filepath.index('/projects/')
        return f"/storage{filepath[projects_index:]}"

    # Last resort: return as-is (may not work but preserves data)
    return filepath


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


def _segment_to_response(
    segment: Segment,
    language: str = "en",
    video=None,
    project=None
) -> SegmentResponse:
    """Convert Segment to API response with timing analysis and cross-video info"""
    # Estimate audio duration
    estimated_duration = script_fitter.estimate_duration(segment.text)
    segment_duration = segment.end_time - segment.start_time
    fits = estimated_duration <= segment_duration * 1.1

    # Calculate cross-video extension info
    extends_to_next = getattr(segment, 'extends_to_next_video', False)
    overflow_duration = None
    next_video_name = None

    if extends_to_next and video and project:
        video_duration = video.duration or 0
        if segment.end_time > video_duration:
            overflow_duration = segment.end_time - video_duration
        next_video = project.get_next_video(video.id)
        if next_video:
            next_video_name = next_video.name

    return SegmentResponse(
        id=segment.id,
        name=segment.name,
        video_id=segment.video_id,
        start_time=segment.start_time,
        end_time=segment.end_time,
        audio_offset=getattr(segment, 'audio_offset', 0.0),
        duration=segment.duration,
        text=segment.text,
        language=segment.language,
        voice_id=segment.voice_id,
        voice_sample_id=getattr(segment, 'voice_sample_id', None),  # Voice cloning
        tts_provider=getattr(segment, 'tts_provider', None),  # TTS provider used
        rate=segment.rate,
        volume=segment.volume,
        pitch=segment.pitch,
        audio_path=_convert_path_to_url(segment.audio_path),
        subtitle_path=_convert_path_to_url(segment.subtitle_path),
        # Subtitle settings
        subtitle_enabled=segment.subtitle_enabled,
        subtitle_font=segment.subtitle_font,
        subtitle_size=segment.subtitle_size,
        subtitle_color=segment.subtitle_color,
        subtitle_position=segment.subtitle_position,
        subtitle_border_enabled=getattr(segment, 'subtitle_border_enabled', True),
        subtitle_border_style=getattr(segment, 'subtitle_border_style', 1),
        subtitle_outline_width=getattr(segment, 'subtitle_outline_width', 0.5),
        subtitle_outline_color=getattr(segment, 'subtitle_outline_color', '&H00000000'),
        subtitle_shadow=getattr(segment, 'subtitle_shadow', 0.0),
        subtitle_shadow_color=getattr(segment, 'subtitle_shadow_color', '&H80000000'),
        # Audio analysis
        estimated_audio_duration=estimated_duration,
        audio_fits_segment=fits,
        # Cross-video extension
        extends_to_next_video=extends_to_next,
        overflow_duration=overflow_duration,
        next_video_name=next_video_name
    )


@router.get("/{project_name}", response_model=List[SegmentResponse])
async def list_segments(
    project_name: str,
    video_id: Optional[str] = None,
    all_videos: bool = Query(False, alias="all", description="Return segments from all videos"),
    user: AuthenticatedUser = Depends(get_current_user)
):
    """List all segments in project or specific video

    Args:
        project_name: Name of the project
        video_id: Optional - filter to specific video's segments
        all_videos: If True, return segments from ALL videos AND generic segments (for multi-video timeline view)
    """
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    if video_id:
        # Specific video requested
        video = project.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        segments = [(seg, video) for seg in video.timeline.segments]
    elif all_videos:
        # Return segments from ALL videos AND generic segments (for combined multi-video view)
        segments = []
        # Add video-specific segments
        for video in project.videos:
            segments.extend([(seg, video) for seg in video.timeline.segments])
        # Add generic/project-level segments (video=None)
        segments.extend([(seg, None) for seg in project.generic_segments])
    else:
        # Get segments from active video (backward compatible behavior)
        video = project.get_active_video()
        if not video:
            raise HTTPException(status_code=400, detail="No active video")
        segments = [(seg, video) for seg in video.timeline.segments]

    return [_segment_to_response(seg, video=vid, project=project) for seg, vid in segments]


@router.get("/{project_name}/validate")
async def validate_timeline(
    project_name: str,
    video_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Validate timeline for overlaps and other issues before export"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    # For multi-video projects, validate all videos
    # For single video or specific video_id, validate that video only
    videos_to_validate = []
    if video_id:
        video = project.get_video(video_id)
        if video:
            videos_to_validate = [video]
    elif len(project.videos) > 1:
        # Multi-video project: validate all videos
        videos_to_validate = project.videos
    elif len(project.videos) == 1:
        # Single video project: use the only video (don't rely on active_video_id)
        videos_to_validate = project.videos
    else:
        # No videos, try active video as fallback
        video = project.get_active_video()
        if video:
            videos_to_validate = [video]

    # Allow validation even with no videos if there are generic segments
    has_generic_segments = hasattr(project, 'generic_segments') and len(project.generic_segments) > 0
    if not videos_to_validate and not has_generic_segments:
        raise HTTPException(status_code=400, detail="No video selected")

    # Collect all segments and issues from all videos
    all_segments = []
    overlap_warnings = []
    timing_warnings = []
    empty_segments = []

    # Include generic/project-level segments (for multi-video projects)
    if hasattr(project, 'generic_segments') and project.generic_segments:
        all_segments.extend(project.generic_segments)

        # Check for timing issues in generic segments
        for seg in project.generic_segments:
            estimated_duration = script_fitter.estimate_duration(seg.text, seg.language)
            segment_duration = seg.end_time - seg.start_time

            if estimated_duration > segment_duration * 1.1:
                overflow = estimated_duration - segment_duration
                timing_warnings.append({
                    "type": "timing",
                    "severity": "warning",
                    "message": f"Script for '{seg.name}' may be ~{overflow:.1f}s too long",
                    "segment_id": seg.id,
                    "estimated_audio": f"{estimated_duration:.1f}s",
                    "segment_duration": f"{segment_duration:.1f}s",
                    "video_name": "(project-level)",
                })

            if not seg.text.strip():
                empty_segments.append({
                    "type": "empty",
                    "severity": "error",
                    "message": f"Segment '{seg.name}' has no text",
                    "segment_id": seg.id,
                    "video_name": "(project-level)",
                })

    for video in videos_to_validate:
        # Collect segments
        all_segments.extend(video.timeline.segments)

        # Check for overlapping segments within this video
        overlaps = video.timeline.check_overlaps()
        for seg1, seg2 in overlaps:
            overlap_warnings.append({
                "type": "overlap",
                "severity": "error",
                "message": f"Segments '{seg1.name}' and '{seg2.name}' overlap",
                "segment1_id": seg1.id,
                "segment2_id": seg2.id,
                "segment1_range": f"{seg1.start_time:.1f}s - {seg1.end_time:.1f}s",
                "segment2_range": f"{seg2.start_time:.1f}s - {seg2.end_time:.1f}s",
                "video_name": video.name,
            })

        # Check for timing issues
        for seg in video.timeline.segments:
            estimated_duration = script_fitter.estimate_duration(seg.text, seg.language)
            segment_duration = seg.end_time - seg.start_time

            if estimated_duration > segment_duration * 1.1:
                overflow = estimated_duration - segment_duration
                timing_warnings.append({
                    "type": "timing",
                    "severity": "warning",
                    "message": f"Script for '{seg.name}' may be ~{overflow:.1f}s too long",
                    "segment_id": seg.id,
                    "estimated_audio": f"{estimated_duration:.1f}s",
                    "segment_duration": f"{segment_duration:.1f}s",
                    "video_name": video.name,
                })

        # Check for missing text
        for seg in video.timeline.segments:
            if not seg.text.strip():
                empty_segments.append({
                    "type": "empty",
                    "severity": "error",
                    "message": f"Segment '{seg.name}' has no text",
                    "segment_id": seg.id,
                    "video_name": video.name,
                })

    all_issues = overlap_warnings + timing_warnings + empty_segments
    has_errors = any(issue["severity"] == "error" for issue in all_issues)

    # Count BGM tracks
    bgm_count = len(project.bgm_tracks) if project.bgm_tracks else 0

    return {
        "valid": len(all_issues) == 0,
        "can_export": not has_errors,
        "segment_count": len(all_segments),
        "bgm_count": bgm_count,
        "issues": all_issues,
        "overlaps": len(overlap_warnings),
        "timing_warnings": len(timing_warnings),
        "empty_segments": len(empty_segments),
    }


@router.post("/{project_name}/batch")
async def create_segments_batch(
    project_name: str,
    segments: List[SegmentCreate],
    video_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Create multiple segments at once (for AI-generated scripts)"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    # Check segment limit based on subscription
    max_segments = user.get_feature_limit("max_segments_per_video") or 5
    current_segment_count = len(project.get_all_segments_for_timeline())
    if current_segment_count + len(segments) > max_segments:
        remaining = max(0, max_segments - current_segment_count)
        raise HTTPException(
            status_code=403,
            detail=f"Your subscription allows maximum {max_segments} segments. You have {current_segment_count} and trying to add {len(segments)}. You can only add {remaining} more."
        )

    if video_id:
        video = project.get_video(video_id)
    else:
        video = project.get_active_video()

    if not video:
        raise HTTPException(status_code=400, detail="No video selected")

    created = []
    errors = []

    # Keep track of newly added segment timings for overlap checking within batch
    added_timings = []  # List of (start_time, end_time, name)

    for i, seg_data in enumerate(segments):
        try:
            # Validate timing
            if seg_data.end_time <= seg_data.start_time:
                errors.append({"index": i, "error": f"End time must be after start time for '{seg_data.name}'"})
                continue

            if video.duration and seg_data.end_time > video.duration:
                if seg_data.extends_to_next_video:
                    # Validate cross-video extension
                    next_video = project.get_next_video(video.id)
                    if not next_video:
                        errors.append({"index": i, "error": f"Segment '{seg_data.name}' cannot extend: no next video"})
                        continue
                    overflow = seg_data.end_time - video.duration
                    if next_video.duration and overflow > next_video.duration:
                        errors.append({"index": i, "error": f"Segment '{seg_data.name}' overflow exceeds next video duration"})
                        continue
                else:
                    errors.append({"index": i, "error": f"Segment '{seg_data.name}' extends beyond video duration"})
                    continue

            # Check for overlaps with existing segments
            overlap_found = False
            for existing in video.timeline.segments:
                if (seg_data.start_time < existing.end_time and seg_data.end_time > existing.start_time):
                    errors.append({
                        "index": i,
                        "error": f"Segment '{seg_data.name}' overlaps with existing segment '{existing.name}' ({existing.start_time:.1f}s - {existing.end_time:.1f}s)"
                    })
                    overlap_found = True
                    break

            if overlap_found:
                continue

            # Check for overlaps with previously added segments in this batch
            for added_start, added_end, added_name in added_timings:
                if (seg_data.start_time < added_end and seg_data.end_time > added_start):
                    errors.append({
                        "index": i,
                        "error": f"Segment '{seg_data.name}' overlaps with segment '{added_name}' in this batch"
                    })
                    overlap_found = True
                    break

            if overlap_found:
                continue

            segment = Segment(
                name=seg_data.name,
                video_id=video.id,
                start_time=seg_data.start_time,
                end_time=seg_data.end_time,
                text=seg_data.text,
                language=seg_data.language,
                voice_id=seg_data.voice_id or "",
                voice_sample_id=getattr(seg_data, 'voice_sample_id', None),  # Voice cloning
                extends_to_next_video=seg_data.extends_to_next_video
            )

            if seg_data.subtitle_style:
                segment.subtitle_enabled = seg_data.subtitle_style.enabled
                segment.subtitle_font = seg_data.subtitle_style.font
                segment.subtitle_size = seg_data.subtitle_style.size

            video.timeline.segments.append(segment)
            created.append(_segment_to_response(segment, video=video, project=project))

            # Track this segment's timing for overlap checking with subsequent segments
            added_timings.append((seg_data.start_time, seg_data.end_time, seg_data.name))

        except Exception as e:
            errors.append({"index": i, "error": str(e)})

    if created:
        project.save()

    return {
        "created": len(created),
        "segments": created,
        "errors": errors
    }


@router.post("/{project_name}", response_model=SegmentResponse)
async def create_segment(
    project_name: str,
    request: SegmentCreate,
    video_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Create a new segment.

    For multi-video projects:
    - If video_id is provided: creates a video-specific segment (times are video-local)
    - If video_id is not provided: creates a generic/project-level segment (times are timeline positions)

    For single-video projects:
    - Always creates video-specific segment using the active video
    """
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    # Check segment limit based on subscription
    max_segments = user.get_feature_limit("max_segments_per_video") or 5
    current_segment_count = len(project.get_all_segments_for_timeline())
    if current_segment_count >= max_segments:
        raise HTTPException(
            status_code=403,
            detail=f"Your subscription allows maximum {max_segments} segments. You have {current_segment_count}. Please upgrade to add more."
        )

    # Validate timing
    if request.end_time <= request.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    is_multi_video = len(project.videos) > 1
    is_generic_segment = video_id is None and is_multi_video

    if is_generic_segment:
        # === GENERIC SEGMENT (multi-video project, no video_id) ===
        # Times are TIMELINE positions (absolute), not video-local

        # Check for overlaps with other generic segments
        for existing in project.generic_segments:
            if (request.start_time < existing.end_time and request.end_time > existing.start_time):
                raise HTTPException(
                    status_code=400,
                    detail=f"Segment overlaps with existing segment '{existing.name}'"
                )

        # Create generic segment (video_id = None)
        segment = Segment(
            name=request.name,
            video_id=None,  # Generic segment - project level
            start_time=request.start_time,
            end_time=request.end_time,
            text=request.text,
            language=request.language,
            voice_id=request.voice_id or "",
            voice_sample_id=request.voice_sample_id,  # Voice cloning
            tts_provider=request.tts_provider,  # TTS provider
            extends_to_next_video=False  # Not applicable for generic segments
        )

        # Apply subtitle style if provided
        if request.subtitle_style:
            segment.subtitle_enabled = request.subtitle_style.enabled
            segment.subtitle_font = request.subtitle_style.font
            segment.subtitle_size = request.subtitle_style.size
            segment.subtitle_color = request.subtitle_style.color
            segment.subtitle_position = request.subtitle_style.position
            segment.subtitle_border_enabled = request.subtitle_style.border_enabled
            segment.subtitle_border_style = request.subtitle_style.border_style
            segment.subtitle_outline_width = request.subtitle_style.outline_width
            segment.subtitle_outline_color = request.subtitle_style.outline_color
            segment.subtitle_shadow = request.subtitle_style.shadow
            segment.subtitle_shadow_color = request.subtitle_style.shadow_color

        # Add to project's generic segments
        project.generic_segments.append(segment)
        project.save()

        return _segment_to_response(segment, video=None, project=project)

    else:
        # === VIDEO-SPECIFIC SEGMENT ===
        # Get target video
        if video_id:
            video = project.get_video(video_id)
        else:
            video = project.get_active_video()

        if not video:
            raise HTTPException(status_code=400, detail="No video selected")

        # Validate cross-video extension
        if video.duration and request.end_time > video.duration:
            if request.extends_to_next_video:
                # Validate next video exists and overflow fits
                next_video = project.get_next_video(video.id)
                if not next_video:
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot extend segment: this is the last video in sequence"
                    )
                overflow = request.end_time - video.duration
                if next_video.duration and overflow > next_video.duration:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Segment overflow ({overflow:.1f}s) exceeds next video duration ({next_video.duration:.1f}s)"
                    )
                # Check for overlaps in next video's start
                for seg in next_video.timeline.segments:
                    if seg.start_time < overflow:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Segment continuation would overlap with '{seg.name}' in {next_video.name}"
                        )
            else:
                raise HTTPException(status_code=400, detail="Segment extends beyond video duration")

        # Check for overlaps in current video
        for existing in video.timeline.segments:
            if (request.start_time < existing.end_time and request.end_time > existing.start_time):
                raise HTTPException(
                    status_code=400,
                    detail=f"Segment overlaps with existing segment '{existing.name}'"
                )

        # Create segment
        segment = Segment(
            name=request.name,
            video_id=video.id,
            start_time=request.start_time,
            end_time=request.end_time,
            text=request.text,
            language=request.language,
            voice_id=request.voice_id or "",
            voice_sample_id=request.voice_sample_id,  # Voice cloning
            tts_provider=request.tts_provider,  # TTS provider
            extends_to_next_video=request.extends_to_next_video
        )

        # Apply subtitle style if provided
        if request.subtitle_style:
            segment.subtitle_enabled = request.subtitle_style.enabled
            segment.subtitle_font = request.subtitle_style.font
            segment.subtitle_size = request.subtitle_style.size
            segment.subtitle_color = request.subtitle_style.color
            segment.subtitle_position = request.subtitle_style.position
            segment.subtitle_border_enabled = request.subtitle_style.border_enabled
            segment.subtitle_border_style = request.subtitle_style.border_style
            segment.subtitle_outline_width = request.subtitle_style.outline_width
            segment.subtitle_outline_color = request.subtitle_style.outline_color
            segment.subtitle_shadow = request.subtitle_style.shadow
            segment.subtitle_shadow_color = request.subtitle_style.shadow_color

        # Add to timeline
        video.timeline.segments.append(segment)
        project.save()

        return _segment_to_response(segment, video=video, project=project)


@router.get("/{project_name}/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    project_name: str,
    segment_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a specific segment"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    # Search generic segments first
    for segment in project.generic_segments:
        if segment.id == segment_id:
            return _segment_to_response(segment, video=None, project=project)

    # Search all videos
    for video in project.videos:
        for segment in video.timeline.segments:
            if segment.id == segment_id:
                return _segment_to_response(segment, video=video, project=project)

    raise HTTPException(status_code=404, detail="Segment not found")


@router.put("/{project_name}/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    project_name: str,
    segment_id: str,
    request: SegmentUpdate,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Update a segment"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    # Find segment - check generic segments first, then video-specific
    target_segment = None
    target_video = None
    is_generic = False

    # Check generic segments
    for segment in project.generic_segments:
        if segment.id == segment_id:
            target_segment = segment
            is_generic = True
            break

    # Check video-specific segments
    if not target_segment:
        for video in project.videos:
            for segment in video.timeline.segments:
                if segment.id == segment_id:
                    target_segment = segment
                    target_video = video
                    break
            if target_segment:
                break

    if not target_segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Update fields
    if request.name is not None:
        target_segment.name = request.name
    if request.start_time is not None:
        target_segment.start_time = request.start_time
    if request.end_time is not None:
        target_segment.end_time = request.end_time
    if request.audio_offset is not None:
        target_segment.audio_offset = request.audio_offset
    if request.text is not None:
        target_segment.text = request.text
        # Clear cached audio when text changes
        target_segment.audio_path = None
        target_segment.subtitle_path = None
    if request.language is not None:
        target_segment.language = request.language
        target_segment.audio_path = None  # Clear cached audio when language changes
        target_segment.subtitle_path = None
    if request.voice_id is not None:
        target_segment.voice_id = request.voice_id
        target_segment.audio_path = None  # Clear cached audio when voice changes
        target_segment.subtitle_path = None
    if request.voice_sample_id is not None:
        target_segment.voice_sample_id = request.voice_sample_id if request.voice_sample_id else None
        target_segment.audio_path = None  # Clear cached audio when voice sample changes
        target_segment.subtitle_path = None
    if request.rate is not None:
        target_segment.rate = request.rate
        target_segment.audio_path = None  # Clear cached audio when rate changes
        target_segment.subtitle_path = None
    if request.volume is not None:
        target_segment.volume = request.volume
        target_segment.audio_path = None  # Clear cached audio when volume changes
        target_segment.subtitle_path = None
    if request.pitch is not None:
        target_segment.pitch = request.pitch
        target_segment.audio_path = None  # Clear cached audio when pitch changes
        target_segment.subtitle_path = None
    if request.tts_provider is not None:
        # Only clear audio if provider actually changed
        old_provider = getattr(target_segment, 'tts_provider', None)
        if old_provider != request.tts_provider:
            target_segment.tts_provider = request.tts_provider
            target_segment.audio_path = None  # Clear cached audio when provider changes
            target_segment.subtitle_path = None

    # Update subtitle style (nested object)
    if request.subtitle_style:
        target_segment.subtitle_enabled = request.subtitle_style.enabled
        target_segment.subtitle_font = request.subtitle_style.font
        target_segment.subtitle_size = request.subtitle_style.size
        target_segment.subtitle_color = request.subtitle_style.color
        target_segment.subtitle_position = request.subtitle_style.position
        target_segment.subtitle_border_enabled = request.subtitle_style.border_enabled
        target_segment.subtitle_border_style = request.subtitle_style.border_style
        target_segment.subtitle_outline_width = request.subtitle_style.outline_width
        target_segment.subtitle_outline_color = request.subtitle_style.outline_color
        target_segment.subtitle_shadow = request.subtitle_style.shadow
        target_segment.subtitle_shadow_color = request.subtitle_style.shadow_color

    # Update individual subtitle fields (from direct params)
    if request.subtitle_enabled is not None:
        target_segment.subtitle_enabled = request.subtitle_enabled
    if request.subtitle_font is not None:
        target_segment.subtitle_font = request.subtitle_font
    if request.subtitle_size is not None:
        target_segment.subtitle_size = request.subtitle_size
    if request.subtitle_color is not None:
        target_segment.subtitle_color = request.subtitle_color
    if request.subtitle_position is not None:
        target_segment.subtitle_position = request.subtitle_position
    if request.subtitle_border_enabled is not None:
        target_segment.subtitle_border_enabled = request.subtitle_border_enabled
    if request.subtitle_border_style is not None:
        target_segment.subtitle_border_style = request.subtitle_border_style
    if request.subtitle_outline_width is not None:
        target_segment.subtitle_outline_width = request.subtitle_outline_width
    if request.subtitle_outline_color is not None:
        target_segment.subtitle_outline_color = request.subtitle_outline_color
    if request.subtitle_shadow is not None:
        target_segment.subtitle_shadow = request.subtitle_shadow
    if request.subtitle_shadow_color is not None:
        target_segment.subtitle_shadow_color = request.subtitle_shadow_color

    # Update cross-video extension flag
    if request.extends_to_next_video is not None:
        target_segment.extends_to_next_video = request.extends_to_next_video

    # Validate timing
    is_valid, error = target_segment.validate()
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Validate cross-video extension if segment extends past video
    # (Only applies to video-specific segments, not generic segments)
    if target_video and target_video.duration and target_segment.end_time > target_video.duration:
        if target_segment.extends_to_next_video:
            next_video = project.get_next_video(target_video.id)
            if not next_video:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot extend segment: this is the last video in sequence"
                )
            overflow = target_segment.end_time - target_video.duration
            if next_video.duration and overflow > next_video.duration:
                raise HTTPException(
                    status_code=400,
                    detail=f"Segment overflow ({overflow:.1f}s) exceeds next video duration ({next_video.duration:.1f}s)"
                )
            # Check for overlaps in next video's start
            for seg in next_video.timeline.segments:
                if seg.start_time < overflow:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Segment continuation would overlap with '{seg.name}' in {next_video.name}"
                    )
        else:
            raise HTTPException(status_code=400, detail="Segment extends beyond video duration")

    project.save()
    return _segment_to_response(target_segment, video=target_video, project=project)


@router.delete("/{project_name}/{segment_id}")
async def delete_segment(
    project_name: str,
    segment_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Delete a segment"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    # First check generic segments (project-level)
    for i, segment in enumerate(project.generic_segments):
        if segment.id == segment_id:
            project.generic_segments.pop(i)
            project.save()
            return {"message": "Segment deleted successfully"}

    # Then check video-specific segments
    for video in project.videos:
        for i, segment in enumerate(video.timeline.segments):
            if segment.id == segment_id:
                video.timeline.segments.pop(i)
                project.save()
                return {"message": "Segment deleted successfully"}

    raise HTTPException(status_code=404, detail="Segment not found")


@router.get("/{project_name}/{segment_id}/analyze", response_model=SegmentTimingAnalysis)
async def analyze_segment_timing(
    project_name: str,
    segment_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Analyze segment timing vs. content length"""
    project = Project.load(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify user owns this project
    _verify_project_ownership(project, user)

    # Find segment - first check generic segments
    target_segment = None
    target_video = None

    for segment in project.generic_segments:
        if segment.id == segment_id:
            target_segment = segment
            break

    # Then check video-specific segments
    if not target_segment:
        for video in project.videos:
            for segment in video.timeline.segments:
                if segment.id == segment_id:
                    target_segment = segment
                    target_video = video
                    break

    if not target_segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Analyze timing
    segment_duration = target_segment.end_time - target_segment.start_time
    estimated_duration = script_fitter.estimate_duration(target_segment.text, target_segment.language)

    fits, overflow, suggestion = script_fitter.analyze_fit(
        target_segment.text,
        target_segment.start_time,
        target_segment.end_time
    )

    recommended_end = None
    if not fits and overflow > 0:
        recommended_end = target_segment.start_time + estimated_duration + 0.3

    return SegmentTimingAnalysis(
        segment_id=target_segment.id,
        segment_duration=segment_duration,
        text_length=len(target_segment.text.split()),
        estimated_audio_duration=estimated_duration,
        audio_fits=fits,
        overflow_seconds=overflow if overflow > 0 else None,
        recommended_end_time=recommended_end,
        suggestion=suggestion
    )
