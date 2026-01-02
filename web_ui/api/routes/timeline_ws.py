"""WebSocket endpoint for real-time timeline synchronization

SECURITY: WebSocket connections require authentication via token query parameter.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from models import Project
from utils.logger import logger
from web_ui.api.middleware.auth import verify_firebase_token
from web_ui.api.utils.security import sanitize_project_name

router = APIRouter()


def _verify_project_ownership_for_ws(project: Project, user_uid: str, is_admin: bool = False) -> bool:
    """
    Verify that the user owns the project for WebSocket connections.

    SECURITY: Prevents users from accessing other users' projects via WebSocket.

    Returns:
        True if access is allowed, False otherwise
    """
    # Admins can access any project
    if is_admin:
        return True

    # Legacy projects (no user_id) - require admin access
    if project.user_id is None:
        return False

    # Regular ownership check
    return project.user_id == user_uid


class ConnectionManager:
    """Manages WebSocket connections per project"""

    def __init__(self):
        # project_name -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_name: str):
        await websocket.accept()
        if project_name not in self.active_connections:
            self.active_connections[project_name] = set()
        self.active_connections[project_name].add(websocket)
        logger.info(f"WebSocket connected for project: {project_name}")

    def disconnect(self, websocket: WebSocket, project_name: str):
        if project_name in self.active_connections:
            self.active_connections[project_name].discard(websocket)
            if not self.active_connections[project_name]:
                del self.active_connections[project_name]
        logger.info(f"WebSocket disconnected for project: {project_name}")

    async def broadcast_to_project(self, project_name: str, message: dict, exclude: Optional[WebSocket] = None):
        """Broadcast message to all connections for a project except the sender"""
        if project_name in self.active_connections:
            for connection in self.active_connections[project_name]:
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to WebSocket: {e}")


manager = ConnectionManager()


@router.websocket("/ws/timeline/{project_name}")
async def timeline_websocket(
    websocket: WebSocket,
    project_name: str,
    token: Optional[str] = Query(None, description="Firebase auth token")
):
    """
    WebSocket endpoint for real-time timeline updates.

    SECURITY: Requires authentication via ?token=<firebase_id_token> query parameter.

    Supported message types:
    - video_position: Update video timeline position
    - video_resize: Update video start/end trim
    - bgm_update: Update BGM track timing/settings
    - segment_update: Update segment timing (start_time, end_time, audio_offset)
    - get_state: Request current timeline state
    """
    # Verify authentication before accepting connection
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    decoded = await verify_firebase_token(token)
    if decoded is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Sanitize project name to prevent path traversal
    try:
        safe_project_name = sanitize_project_name(project_name)
    except Exception:
        await websocket.close(code=4002, reason="Invalid project name")
        return

    await manager.connect(websocket, safe_project_name)

    try:
        # Send initial state
        project = Project.load(safe_project_name)
        if project:
            # SECURITY: Verify ownership before granting access
            user_uid = decoded.get("uid", "")
            is_admin = decoded.get("admin", False)
            if not _verify_project_ownership_for_ws(project, user_uid, is_admin):
                await websocket.send_json({
                    "type": "error",
                    "message": "Access denied"
                })
                await websocket.close(code=4003, reason="Access denied")
                return

            await websocket.send_json({
                "type": "state",
                "data": get_timeline_state(project)
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Project not found"
            })
            await websocket.close()
            return

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type")
            msg_data = message.get("data", {})

            if msg_type == "video_position":
                result = await handle_video_position(safe_project_name, msg_data)
                await websocket.send_json(result)
                if result.get("success"):
                    # Broadcast VALIDATED data to other clients (not raw input)
                    await manager.broadcast_to_project(safe_project_name, {
                        "type": "video_position_update",
                        "data": result.get("data", msg_data)
                    }, exclude=websocket)

            elif msg_type == "video_resize":
                result = await handle_video_resize(safe_project_name, msg_data)
                await websocket.send_json(result)
                if result.get("success"):
                    # Broadcast VALIDATED data to other clients (not raw input)
                    await manager.broadcast_to_project(safe_project_name, {
                        "type": "video_resize_update",
                        "data": result.get("data", msg_data)
                    }, exclude=websocket)

            elif msg_type == "bgm_update":
                result = await handle_bgm_update(safe_project_name, msg_data)
                await websocket.send_json(result)
                if result.get("success"):
                    # Broadcast VALIDATED data to other clients (not raw input)
                    await manager.broadcast_to_project(safe_project_name, {
                        "type": "bgm_update",
                        "data": result.get("data", msg_data)
                    }, exclude=websocket)

            elif msg_type == "segment_update":
                result = await handle_segment_update(safe_project_name, msg_data)
                await websocket.send_json(result)
                if result.get("success"):
                    # Broadcast VALIDATED data to other clients (not raw input)
                    await manager.broadcast_to_project(safe_project_name, {
                        "type": "segment_update",
                        "data": result.get("data", msg_data)
                    }, exclude=websocket)

            elif msg_type == "get_state":
                project = Project.load(safe_project_name)
                if project:
                    await websocket.send_json({
                        "type": "state",
                        "data": get_timeline_state(project)
                    })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, safe_project_name)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, safe_project_name)


def get_timeline_state(project: Project) -> dict:
    """Get current timeline state for all videos and BGM tracks"""
    videos = []
    for video in project.videos:
        videos.append({
            "id": video.id,
            "name": video.name,
            "duration": video.duration,
            "order": video.order,
            "timeline_start": video.timeline_start,
            "timeline_end": video.timeline_end,
            "source_start": video.source_start,
            "source_end": video.source_end,
            "width": video.width,
            "height": video.height,
            "orientation": video.orientation
        })

    bgm_tracks = []
    for track in project.bgm_tracks:
        bgm_tracks.append({
            "id": track.id,
            "name": track.name,
            "start_time": track.start_time,
            "end_time": track.end_time,
            "volume": track.volume,
            "fade_in": track.fade_in,
            "fade_out": track.fade_out,
            "loop": track.loop,
            "muted": track.muted,
            "duration": track.duration
        })

    return {
        "videos": videos,
        "bgm_tracks": bgm_tracks,
        "active_video_id": project.active_video_id
    }


async def handle_video_position(project_name: str, data: dict) -> dict:
    """Handle video timeline position update with file locking to prevent race conditions"""
    video_id = data.get("video_id")
    timeline_start = data.get("timeline_start")
    timeline_end = data.get("timeline_end")

    if not video_id:
        return {"type": "error", "message": "Missing video_id"}

    # Minimum clip duration in seconds
    MIN_CLIP_DURATION = 1.0

    # Result variables to capture from locked context
    result_data = {}

    # Use locked_update for thread-safe read-modify-write
    with Project.locked_update(project_name) as project:
        if not project:
            return {"type": "error", "message": "Project not found"}

        video = project.get_video(video_id)
        if not video:
            return {"type": "error", "message": "Video not found"}

        # Validate and update timeline position
        if timeline_start is not None:
            # Negative timeline_start is allowed for positioning trimmed videos before 00:00
            # Round to millisecond precision
            timeline_start = round(float(timeline_start), 3)
            video.timeline_start = timeline_start

        if timeline_end is not None:
            timeline_end = float(timeline_end)
            # Ensure minimum clip duration
            current_start = video.timeline_start or 0
            min_end = current_start + MIN_CLIP_DURATION
            timeline_end = max(min_end, timeline_end)
            # Can't exceed video duration from start
            video_duration = video.duration or 0
            if video_duration > 0:
                max_end = current_start + video_duration
                timeline_end = min(max_end, timeline_end)
            # Round to millisecond precision
            video.timeline_end = round(timeline_end, 3)

        # Capture result data (save happens automatically when exiting context)
        result_data = {
            "video_id": video_id,
            "timeline_start": video.timeline_start,
            "timeline_end": video.timeline_end
        }

    logger.info(f"Updated video {video_id} position: start={result_data.get('timeline_start')}, end={result_data.get('timeline_end')}")

    return {
        "type": "ack",
        "success": True,
        "message": "Video position updated",
        "data": result_data
    }


async def handle_video_resize(project_name: str, data: dict) -> dict:
    """
    Handle video resize (trim) update with file locking to prevent race conditions.

    When trimming from start: source_start changes (skips beginning of source)
    When trimming from end: source_end changes (cuts off end of source)
    """
    video_id = data.get("video_id")
    timeline_start = data.get("timeline_start")
    timeline_end = data.get("timeline_end")
    source_start = data.get("source_start")
    source_end = data.get("source_end")

    if not video_id:
        return {"type": "error", "message": "Missing video_id"}

    # Minimum clip duration in seconds
    MIN_CLIP_DURATION = 1.0

    # Result variables to capture from locked context
    result_data = {}

    # Use locked_update for thread-safe read-modify-write
    with Project.locked_update(project_name) as project:
        if not project:
            return {"type": "error", "message": "Project not found"}

        video = project.get_video(video_id)
        if not video:
            return {"type": "error", "message": "Video not found"}

        video_duration = video.duration or 0

        # Get current values for validation
        current_start = video.timeline_start or 0
        current_end = video.timeline_end or (current_start + video_duration)

        # Validate and update timeline position
        if timeline_start is not None:
            timeline_start = float(timeline_start)
            # Negative timeline_start is allowed for positioning trimmed videos before 00:00
            # Can't make clip shorter than minimum duration
            max_start = current_end - MIN_CLIP_DURATION
            timeline_start = min(timeline_start, max_start)
            # Round to millisecond precision
            video.timeline_start = round(timeline_start, 3)

        if timeline_end is not None:
            timeline_end = float(timeline_end)
            # Ensure minimum clip duration
            current_start = video.timeline_start or 0
            min_end = current_start + MIN_CLIP_DURATION
            timeline_end = max(min_end, timeline_end)
            # Can't exceed video duration from source start
            if video_duration > 0:
                current_source_start = video.source_start if hasattr(video, 'source_start') else 0
                max_end = current_start + (video_duration - current_source_start)
                timeline_end = min(max_end, timeline_end)
            # Round to millisecond precision
            video.timeline_end = round(timeline_end, 3)

        # Update source trim values (the actual in/out points in the source video)
        if source_start is not None:
            source_start = float(source_start)
            # Can't go below 0
            source_start = max(0, source_start)
            # Can't exceed video duration
            source_start = min(source_start, video_duration - MIN_CLIP_DURATION)
            video.source_start = round(source_start, 3)

        if source_end is not None:
            source_end = float(source_end)
            # Must be at least MIN_CLIP_DURATION after source_start
            current_source_start = video.source_start if hasattr(video, 'source_start') else 0
            min_source_end = current_source_start + MIN_CLIP_DURATION
            source_end = max(min_source_end, source_end)
            # Can't exceed video duration
            source_end = min(source_end, video_duration)
            video.source_end = round(source_end, 3)

        # Capture result data (save happens automatically when exiting context)
        result_data = {
            "video_id": video_id,
            "timeline_start": video.timeline_start,
            "timeline_end": video.timeline_end,
            "source_start": video.source_start,
            "source_end": video.source_end
        }

    logger.info(f"Resized video {video_id}: timeline={result_data.get('timeline_start')}-{result_data.get('timeline_end')}, source={result_data.get('source_start')}-{result_data.get('source_end')}")

    return {
        "type": "ack",
        "success": True,
        "message": "Video resized",
        "data": result_data
    }


async def handle_bgm_update(project_name: str, data: dict) -> dict:
    """Handle BGM track update with file locking to prevent race conditions"""
    track_id = data.get("track_id")

    if not track_id:
        return {"type": "error", "message": "Missing track_id"}

    # Build update kwargs from provided data
    update_fields = {}
    for field in ["start_time", "end_time", "audio_offset", "volume", "fade_in", "fade_out", "loop", "muted"]:
        if field in data and data[field] is not None:
            update_fields[field] = data[field]

    if not update_fields:
        return {"type": "error", "message": "No update fields provided"}

    # Result variables to capture from locked context
    result_data = {}

    # Use locked_update for thread-safe read-modify-write
    with Project.locked_update(project_name) as project:
        if not project:
            return {"type": "error", "message": "Project not found"}

        track = project.update_bgm_track(track_id, **update_fields)
        if not track:
            return {"type": "error", "message": "BGM track not found"}

        # Capture result data (save happens automatically when exiting context)
        result_data = {
            "track_id": track_id,
            "start_time": track.start_time,
            "end_time": track.end_time,
            "audio_offset": track.audio_offset,
            "volume": track.volume,
            "muted": track.muted
        }

    logger.info(f"Updated BGM track {track_id}: {update_fields}")

    return {
        "type": "ack",
        "success": True,
        "message": "BGM track updated",
        "data": result_data
    }


async def handle_segment_update(project_name: str, data: dict) -> dict:
    """Handle segment timeline update (position, audio_offset) with file locking"""
    segment_id = data.get("segment_id")

    if not segment_id:
        return {"type": "error", "message": "Missing segment_id"}

    # Build update kwargs from provided data (timeline-relevant fields only)
    update_fields = {}
    for field in ["start_time", "end_time", "audio_offset"]:
        if field in data and data[field] is not None:
            update_fields[field] = data[field]

    if not update_fields:
        return {"type": "error", "message": "No update fields provided"}

    # Result variables to capture from locked context
    result_data = {}

    # Use locked_update for thread-safe read-modify-write
    with Project.locked_update(project_name) as project:
        if not project:
            return {"type": "error", "message": "Project not found"}

        # Find segment - check generic segments first, then video-specific
        target_segment = None

        # Check generic segments
        for segment in project.generic_segments:
            if segment.id == segment_id:
                target_segment = segment
                break

        # Check video-specific segments
        if not target_segment:
            for video in project.videos:
                for segment in video.timeline.segments:
                    if segment.id == segment_id:
                        target_segment = segment
                        break
                if target_segment:
                    break

        if not target_segment:
            return {"type": "error", "message": "Segment not found"}

        # Apply updates
        if "start_time" in update_fields:
            target_segment.start_time = update_fields["start_time"]
        if "end_time" in update_fields:
            target_segment.end_time = update_fields["end_time"]
        if "audio_offset" in update_fields:
            target_segment.audio_offset = update_fields["audio_offset"]

        # Capture result data (save happens automatically when exiting context)
        result_data = {
            "segment_id": segment_id,
            "start_time": target_segment.start_time,
            "end_time": target_segment.end_time,
            "audio_offset": target_segment.audio_offset
        }

    logger.info(f"Updated segment {segment_id}: {update_fields}")

    return {
        "type": "ack",
        "success": True,
        "message": "Segment updated",
        "data": result_data
    }
