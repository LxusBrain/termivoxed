"""Export API routes with WebSocket progress"""

import sys
import asyncio
import uuid
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import subprocess as sp
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.logger import logger

from models import Project
from core.export_pipeline import ExportPipeline
from backend.tts_service import TTSService
from backend.ffmpeg_utils import FFmpegUtils
from web_ui.api.schemas.export_schemas import (
    ExportConfig,
    ExportRequest,
    ExportProgress,
    ExportResult,
    ExportQueueItem,
    PreviewRequest,
    PreviewResponse,
    SegmentAudioRequest,
    SegmentAudioResponse,
    PreviewSegmentAudioRequest,
    PreviewSegmentAudioResponse,
)
from config import settings

router = APIRouter()

# Track active exports
active_exports: Dict[str, ExportQueueItem] = {}
# WebSocket connections for progress updates
progress_connections: Dict[str, WebSocket] = {}
# Track active export processes
active_processes: Dict[str, asyncio.subprocess.Process] = {}
# Path to export worker script (in parent api/ directory)
EXPORT_WORKER_PATH = Path(__file__).parent.parent / "export_worker.py"


async def send_progress(
    export_id: str,
    stage: str,
    message: str,
    progress: int,
    current_step: int = 0,
    total_steps: int = 0,
    current_segment: Optional[str] = None,
    current_voice: Optional[str] = None,
    detail: Optional[str] = None,
    eta_seconds: Optional[float] = None,
    eta_formatted: Optional[str] = None,
    elapsed_seconds: Optional[float] = None,
    processing_speed: Optional[float] = None
):
    """Send detailed progress update via WebSocket"""
    if export_id in progress_connections:
        try:
            await progress_connections[export_id].send_json({
                "stage": stage,
                "message": message,
                "progress": progress,
                "current_step": current_step,
                "total_steps": total_steps,
                "current_segment": current_segment,
                "current_voice": current_voice,
                "detail": detail,
                "eta_seconds": eta_seconds,
                "eta_formatted": eta_formatted,
                "elapsed_seconds": elapsed_seconds,
                "processing_speed": processing_speed
            })
        except Exception:
            pass

    # Also update the queue item
    if export_id in active_exports:
        active_exports[export_id].progress = progress
        active_exports[export_id].current_stage = stage
        active_exports[export_id].current_detail = message


@router.post("/start")
async def start_export(request: ExportRequest):
    """Start a video export job"""
    project = Project.load(request.project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Generate export ID
    export_id = str(uuid.uuid4())[:8]

    # Determine output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Use custom filename if provided, otherwise use default with timestamp
    if request.config.output_filename:
        # Sanitize filename (remove invalid characters)
        safe_filename = "".join(c for c in request.config.output_filename if c.isalnum() or c in (' ', '-', '_')).strip()
        if safe_filename:
            output_filename = f"{safe_filename}.mp4"
        else:
            output_filename = f"{request.project_name}_{timestamp}.mp4"
    else:
        output_filename = f"{request.project_name}_{timestamp}.mp4"

    # Determine output directory and path
    if request.config.output_path:
        provided_path = Path(request.config.output_path)
        # Check if the provided path is a directory or a file path
        if provided_path.is_dir() or (not provided_path.suffix and not provided_path.exists()):
            # It's a directory - use it with our filename
            provided_path.mkdir(parents=True, exist_ok=True)
            output_path = str(provided_path / output_filename)
        else:
            # It's a full file path - use custom filename if provided, else use the path as-is
            if request.config.output_filename:
                # Use the directory from provided path but with custom filename
                Path(provided_path).parent.mkdir(parents=True, exist_ok=True)
                output_path = str(Path(provided_path).parent / output_filename)
            else:
                output_path = request.config.output_path
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)

    # Use project's background music if not explicitly provided in config
    # This allows the Timeline BGM upload to be automatically included
    effective_config = ExportConfig(
        quality=request.config.quality,
        include_subtitles=request.config.include_subtitles,
        background_music_path=request.config.background_music_path or project.background_music_path,
        output_path=request.config.output_path
    )

    # Create queue item
    queue_item = ExportQueueItem(
        id=export_id,
        project_name=request.project_name,
        status="queued",
        progress=0,
        output_path=output_path,
        started_at=datetime.now().isoformat()
    )
    active_exports[export_id] = queue_item

    # Start export in background task (non-blocking)
    asyncio.create_task(
        run_export(
            export_id,
            project,
            output_path,
            effective_config,  # Use the config with project BGM fallback
            request.export_type,
            request.video_id
        )
    )

    # Build BGM tracks info for response
    bgm_tracks_info = []
    if hasattr(project, 'bgm_tracks') and project.bgm_tracks:
        for track in project.bgm_tracks:
            if not track.muted and track.path:
                bgm_tracks_info.append({
                    "name": track.name,
                    "path": track.path,
                    "start_time": track.start_time,
                    "end_time": track.end_time,
                    "volume": track.volume
                })

    return {
        "export_id": export_id,
        "status": "queued",
        "output_path": output_path,
        "background_music": effective_config.background_music_path,  # Legacy single BGM (if any)
        "bgm_tracks": bgm_tracks_info,  # New multi-track BGM info
        "bgm_tracks_count": len(bgm_tracks_info),
        "message": f"Export started with {len(bgm_tracks_info)} BGM track(s). Connect to WebSocket for progress updates."
    }


async def run_export(
    export_id: str,
    project: Project,
    output_path: str,
    config: ExportConfig,
    export_type: str,
    video_id: str = None
):
    """
    Run export in a separate subprocess for true non-blocking behavior.

    The export worker runs as a completely separate Python process,
    communicating progress via JSON lines on stdout.

    Stderr is redirected to a log file to avoid pipe buffer deadlocks,
    allowing real-time progress streaming via stdout.
    """
    stderr_log_path = None
    stderr_file = None

    try:
        active_exports[export_id].status = "processing"

        # Build command for export worker subprocess
        cmd = [
            sys.executable,  # Use same Python interpreter
            str(EXPORT_WORKER_PATH),
            project.name,
            output_path,
            config.quality,
            str(config.include_subtitles),
            export_type,
            str(video_id) if video_id else 'None',
            str(config.background_music_path) if config.background_music_path else 'None'
        ]

        logger.info(f"Starting export worker: {' '.join(cmd)}")

        # Create a log file for stderr - keeps logs for debugging
        stderr_log_path = Path(settings.TEMP_DIR) / f"export_{export_id}_stderr.log"
        stderr_file = open(stderr_log_path, 'w')

        # Start subprocess - stdout is PIPE for real-time progress, stderr goes to file
        # Using start_new_session=True to detach from parent's process group
        # This can help avoid signal propagation issues
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=stderr_file,
            cwd=str(Path(__file__).parent.parent.parent.parent),  # Project root
            start_new_session=True  # Detach from parent process group
        )

        active_processes[export_id] = process
        logger.info(f"Export worker started with PID: {process.pid}")

        # Read stdout for real-time progress updates
        # Since stderr goes to file, stdout won't block
        try:
            while True:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=3600  # 1 hour timeout
                )
                if not line:
                    break

                try:
                    line_text = line.decode('utf-8').strip()
                    if line_text:
                        data = json.loads(line_text)

                        if data.get('type') == 'progress':
                            stage = data.get('stage', 'processing')
                            message = data.get('message', 'Processing...')
                            progress = data.get('progress', 0)

                            # Log progress to server logs
                            logger.info(f"[Export {export_id}] {stage}: {message} ({progress}%)")

                            await send_progress(
                                export_id,
                                stage,
                                message,
                                progress,
                                current_step=data.get('current_step'),
                                total_steps=data.get('total_steps'),
                                current_segment=data.get('current_segment'),
                                current_voice=data.get('current_voice'),
                                detail=data.get('detail')
                            )

                            # Update active_exports
                            if export_id in active_exports:
                                active_exports[export_id].progress = progress
                                active_exports[export_id].current_stage = stage
                                active_exports[export_id].current_detail = message

                        elif data.get('type') == 'error':
                            logger.error(f"[Export {export_id}] Error: {data.get('message')}")
                            raise Exception(data.get('message', 'Unknown error'))

                except json.JSONDecodeError:
                    # Not JSON, might be log output - ignore
                    pass

        except asyncio.TimeoutError:
            logger.error("Export worker timed out")
            process.kill()
            raise Exception("Export timed out")

        # Wait for process to complete
        await process.wait()

        logger.info(f"Export worker finished with return code: {process.returncode}")

        # Check exit code
        if process.returncode == 0:
            # Get file size
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            file_size_mb = file_size / (1024 * 1024)

            active_exports[export_id].status = "completed"
            active_exports[export_id].progress = 100
            active_exports[export_id].output_path = output_path
            active_exports[export_id].completed_at = datetime.now().isoformat()

            logger.info(f"[Export {export_id}] COMPLETED - File: {output_path} ({file_size_mb:.1f} MB)")

            await send_progress(
                export_id, "completed",
                f"Export completed! File size: {file_size_mb:.1f} MB", 100,
                detail=f"Saved to: {output_path}"
            )
        else:
            # Read stderr from log file for error message
            error_msg = "Export failed"
            if stderr_log_path and stderr_log_path.exists():
                stderr_file.close()
                stderr_file = None
                with open(stderr_log_path, 'r') as f:
                    stderr_lines = f.readlines()
                    if stderr_lines:
                        error_msg = "".join(stderr_lines[-10:])
            raise Exception(error_msg)

    except Exception as e:
        active_exports[export_id].status = "failed"
        active_exports[export_id].error = str(e)
        await send_progress(
            export_id, "error", f"Export failed: {str(e)}", 0,
            detail="Check server logs for more details"
        )
    finally:
        # Clean up
        if stderr_file:
            stderr_file.close()
        if stderr_log_path and stderr_log_path.exists():
            try:
                stderr_log_path.unlink()  # Delete temp log file
            except Exception:
                pass
        if export_id in active_processes:
            del active_processes[export_id]


@router.websocket("/progress/{export_id}")
async def export_progress_websocket(websocket: WebSocket, export_id: str):
    """WebSocket endpoint for export progress updates"""
    await websocket.accept()
    progress_connections[export_id] = websocket
    logger.info(f"[Export {export_id}] WebSocket connected")

    try:
        # Send current status immediately
        if export_id in active_exports:
            item = active_exports[export_id]
            await websocket.send_json({
                "stage": item.current_stage or item.status,
                "message": item.current_detail or f"Export {item.status}",
                "progress": item.progress,
                "output_path": item.output_path
            })

            # If already completed, send completion immediately
            if item.status == "completed":
                await websocket.send_json({
                    "stage": "completed",
                    "message": f"Export completed!",
                    "progress": 100,
                    "output_path": item.output_path
                })

        # Keep connection alive with non-blocking ping/pong
        ping_failures = 0
        max_ping_failures = 3

        while True:
            try:
                # Use shorter timeout for responsiveness
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "pong":
                    ping_failures = 0  # Reset on successful pong
                elif data == "status":
                    # Allow client to request current status
                    if export_id in active_exports:
                        item = active_exports[export_id]
                        await websocket.send_json({
                            "stage": item.current_stage or item.status,
                            "message": item.current_detail or f"Export {item.status}",
                            "progress": item.progress,
                            "output_path": item.output_path
                        })
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_text("ping")
                    ping_failures += 1
                    if ping_failures >= max_ping_failures:
                        logger.warning(f"[Export {export_id}] WebSocket ping failures exceeded, closing")
                        break
                except Exception as e:
                    logger.warning(f"[Export {export_id}] WebSocket ping failed: {e}")
                    break

    except WebSocketDisconnect:
        logger.info(f"[Export {export_id}] WebSocket disconnected by client")
    except Exception as e:
        logger.warning(f"[Export {export_id}] WebSocket error: {e}")
    finally:
        if export_id in progress_connections:
            del progress_connections[export_id]
        logger.info(f"[Export {export_id}] WebSocket closed")


@router.get("/status/{export_id}")
async def get_export_status(export_id: str):
    """Get current export status"""
    if export_id not in active_exports:
        raise HTTPException(status_code=404, detail="Export not found")

    return active_exports[export_id]


@router.get("/queue")
async def get_export_queue():
    """Get all active exports"""
    return {"exports": list(active_exports.values())}


@router.delete("/cancel/{export_id}")
async def cancel_export(export_id: str):
    """Cancel an export job"""
    if export_id not in active_exports:
        raise HTTPException(status_code=404, detail="Export not found")

    item = active_exports[export_id]
    if item.status == "processing":
        # Kill the subprocess if running
        if export_id in active_processes:
            process = active_processes[export_id]
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
            except Exception:
                pass

        item.status = "failed"
        item.error = "Cancelled by user"
        await send_progress(export_id, "error", "Export cancelled by user", 0)

    return {"message": "Export cancelled"}


@router.post("/preview")
async def generate_preview(request: PreviewRequest):
    """Generate a preview for a single segment"""
    project = Project.load(request.project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    video = project.get_active_video()
    if not video:
        raise HTTPException(status_code=400, detail="No active video")

    segments = video.timeline.segments
    if request.segment_index >= len(segments):
        raise HTTPException(status_code=400, detail="Invalid segment index")

    pipeline = ExportPipeline(project)

    # Generate preview
    output_dir = Path(settings.TEMP_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"preview_{project.name}_{request.segment_index}.mp4"

    success = await pipeline.generate_preview(request.segment_index, str(output_path))

    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate preview")

    duration = FFmpegUtils.get_media_duration(str(output_path))

    return PreviewResponse(
        video_url=f"/storage/temp/preview_{project.name}_{request.segment_index}.mp4",
        duration=duration or 0
    )


@router.post("/segment-audio", response_model=SegmentAudioResponse)
async def generate_segment_audio(request: SegmentAudioRequest):
    """Generate or retrieve audio for a specific segment"""
    project = Project.load(request.project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find segment
    segment = None
    video = None
    for v in project.videos:
        for s in v.timeline.segments:
            if s.id == request.segment_id:
                segment = s
                video = v
                break
        if segment:
            break

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Check if already generated
    if segment.audio_path and os.path.exists(segment.audio_path):
        duration = FFmpegUtils.get_media_duration(segment.audio_path)
        return SegmentAudioResponse(
            audio_url=f"/storage/{Path(segment.audio_path).relative_to(settings.STORAGE_DIR)}",
            duration=duration or 0,
            cached=True
        )

    # Generate audio
    tts_service = TTSService()
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

    # Update segment
    segment.audio_path = audio_path
    segment.subtitle_path = subtitle_path
    project.save()

    duration = FFmpegUtils.get_media_duration(audio_path)

    return SegmentAudioResponse(
        audio_url=f"/storage/{Path(audio_path).relative_to(settings.STORAGE_DIR)}",
        duration=duration or 0,
        cached=False
    )


@router.post("/preview-segment-audio", response_model=PreviewSegmentAudioResponse)
async def preview_segment_audio(request: PreviewSegmentAudioRequest):
    """Preview segment audio with custom voice/language/parameters without saving to project"""
    tts_service = TTSService()

    # Generate preview audio with provided parameters
    audio_path, _ = await tts_service.generate_audio(
        text=request.text,
        language=request.language,
        voice=request.voice_id,
        project_name=request.project_name,
        segment_name=f"preview_{request.voice_id[:20]}_{hash(request.text) % 10000}",
        rate=request.rate,
        volume=request.volume,
        pitch=request.pitch
    )

    duration = FFmpegUtils.get_media_duration(audio_path)

    return PreviewSegmentAudioResponse(
        audio_url=f"/storage/{Path(audio_path).relative_to(settings.STORAGE_DIR)}",
        duration=duration or 0
    )


@router.get("/download/{export_id}")
async def download_export(export_id: str):
    """Download completed export"""
    if export_id not in active_exports:
        raise HTTPException(status_code=404, detail="Export not found")

    item = active_exports[export_id]
    if item.status != "completed" or not item.output_path:
        raise HTTPException(status_code=400, detail="Export not ready for download")

    from fastapi.responses import FileResponse
    return FileResponse(
        item.output_path,
        media_type="video/mp4",
        filename=Path(item.output_path).name
    )


@router.get("/output-dir")
async def get_output_directory():
    """Get the default output directory path"""
    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "output_dir": str(output_dir.absolute()),
        "exists": output_dir.exists()
    }


class BrowseDirectoryRequest(BaseModel):
    """Request for browsing directories"""
    path: Optional[str] = None


class BrowseDirectoryResponse(BaseModel):
    """Response for directory browsing"""
    current_path: str
    parent_path: Optional[str]
    directories: list[str]
    can_go_up: bool


@router.post("/browse-directories")
async def browse_directories(request: BrowseDirectoryRequest = None):
    """Browse directories for output path selection"""
    # Default to output directory or home
    if request and request.path:
        current_path = Path(request.path)
    else:
        current_path = Path(settings.OUTPUT_DIR)

    # Ensure it's absolute
    current_path = current_path.resolve()

    # If path doesn't exist or is a file, go to parent
    if not current_path.exists():
        current_path = current_path.parent
    if current_path.is_file():
        current_path = current_path.parent

    # Get parent path (prevent going above root)
    parent_path = None
    can_go_up = False
    if current_path.parent != current_path:  # Not at root
        parent_path = str(current_path.parent)
        can_go_up = True

    # List directories
    directories = []
    try:
        for item in sorted(current_path.iterdir()):
            if item.is_dir() and not item.name.startswith('.'):
                directories.append(item.name)
    except PermissionError:
        pass

    return {
        "current_path": str(current_path),
        "parent_path": parent_path,
        "directories": directories,
        "can_go_up": can_go_up
    }


@router.post("/set-output-dir")
async def set_output_directory(request: BrowseDirectoryRequest):
    """Set the output directory for exports"""
    if not request.path:
        raise HTTPException(status_code=400, detail="Path is required")

    output_path = Path(request.path)

    # Validate the path
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot create directory: {str(e)}")

    if not output_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    # Check if writable
    try:
        test_file = output_path / ".test_write"
        test_file.touch()
        test_file.unlink()
    except Exception:
        raise HTTPException(status_code=400, detail="Directory is not writable")

    return {
        "output_dir": str(output_path.absolute()),
        "message": "Output directory set successfully"
    }
