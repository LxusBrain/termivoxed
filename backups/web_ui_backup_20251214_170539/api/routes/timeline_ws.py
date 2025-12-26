"""WebSocket endpoint for real-time timeline synchronization"""

import json
import sys
from pathlib import Path
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from models import Project
from utils.logger import logger

router = APIRouter()


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
async def timeline_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for real-time timeline updates.

    Supported message types:
    - video_position: Update video timeline position
    - video_resize: Update video start/end trim
    - bgm_update: Update BGM track timing/settings
    - get_state: Request current timeline state
    """
    await manager.connect(websocket, project_name)

    try:
        # Send initial state
        project = Project.load(project_name)
        if project:
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
                result = await handle_video_position(project_name, msg_data)
                await websocket.send_json(result)
                if result.get("success"):
                    # Broadcast to other clients
                    await manager.broadcast_to_project(project_name, {
                        "type": "video_position_update",
                        "data": msg_data
                    }, exclude=websocket)

            elif msg_type == "video_resize":
                result = await handle_video_resize(project_name, msg_data)
                await websocket.send_json(result)
                if result.get("success"):
                    await manager.broadcast_to_project(project_name, {
                        "type": "video_resize_update",
                        "data": msg_data
                    }, exclude=websocket)

            elif msg_type == "bgm_update":
                result = await handle_bgm_update(project_name, msg_data)
                await websocket.send_json(result)
                if result.get("success"):
                    await manager.broadcast_to_project(project_name, {
                        "type": "bgm_update",
                        "data": msg_data
                    }, exclude=websocket)

            elif msg_type == "get_state":
                project = Project.load(project_name)
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
        manager.disconnect(websocket, project_name)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, project_name)


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
    """Handle video timeline position update"""
    video_id = data.get("video_id")
    timeline_start = data.get("timeline_start")
    timeline_end = data.get("timeline_end")

    if not video_id:
        return {"type": "error", "message": "Missing video_id"}

    project = Project.load(project_name)
    if not project:
        return {"type": "error", "message": "Project not found"}

    video = project.get_video(video_id)
    if not video:
        return {"type": "error", "message": "Video not found"}

    # Minimum clip duration in seconds
    MIN_CLIP_DURATION = 1.0

    # Validate and update timeline position
    if timeline_start is not None:
        # Can't go below 0, round to millisecond precision
        timeline_start = round(max(0, float(timeline_start)), 3)
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

    project.save()

    logger.info(f"Updated video {video_id} position: start={timeline_start}, end={timeline_end}")

    return {
        "type": "ack",
        "success": True,
        "message": "Video position updated",
        "data": {
            "video_id": video_id,
            "timeline_start": video.timeline_start,
            "timeline_end": video.timeline_end
        }
    }


async def handle_video_resize(project_name: str, data: dict) -> dict:
    """Handle video resize (trim) update"""
    video_id = data.get("video_id")
    timeline_start = data.get("timeline_start")
    timeline_end = data.get("timeline_end")

    if not video_id:
        return {"type": "error", "message": "Missing video_id"}

    project = Project.load(project_name)
    if not project:
        return {"type": "error", "message": "Project not found"}

    video = project.get_video(video_id)
    if not video:
        return {"type": "error", "message": "Video not found"}

    # Minimum clip duration in seconds
    MIN_CLIP_DURATION = 1.0
    video_duration = video.duration or 0

    # Get current values for validation
    current_start = video.timeline_start or 0
    current_end = video.timeline_end or (current_start + video_duration)

    # Validate and update timeline position
    if timeline_start is not None:
        timeline_start = float(timeline_start)
        # Can't go below 0
        timeline_start = max(0, timeline_start)
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
        # Can't exceed video duration from start
        if video_duration > 0:
            max_end = current_start + video_duration
            timeline_end = min(max_end, timeline_end)
        # Round to millisecond precision
        video.timeline_end = round(timeline_end, 3)

    project.save()

    logger.info(f"Resized video {video_id}: start={video.timeline_start}, end={video.timeline_end}")

    return {
        "type": "ack",
        "success": True,
        "message": "Video resized",
        "data": {
            "video_id": video_id,
            "timeline_start": video.timeline_start,
            "timeline_end": video.timeline_end
        }
    }


async def handle_bgm_update(project_name: str, data: dict) -> dict:
    """Handle BGM track update"""
    track_id = data.get("track_id")

    if not track_id:
        return {"type": "error", "message": "Missing track_id"}

    project = Project.load(project_name)
    if not project:
        return {"type": "error", "message": "Project not found"}

    # Build update kwargs from provided data
    update_fields = {}
    for field in ["start_time", "end_time", "volume", "fade_in", "fade_out", "loop", "muted"]:
        if field in data and data[field] is not None:
            update_fields[field] = data[field]

    if not update_fields:
        return {"type": "error", "message": "No update fields provided"}

    track = project.update_bgm_track(track_id, **update_fields)
    if not track:
        return {"type": "error", "message": "BGM track not found"}

    project.save()

    logger.info(f"Updated BGM track {track_id}: {update_fields}")

    return {
        "type": "ack",
        "success": True,
        "message": "BGM track updated",
        "data": {
            "track_id": track_id,
            "start_time": track.start_time,
            "end_time": track.end_time,
            "volume": track.volume
        }
    }
