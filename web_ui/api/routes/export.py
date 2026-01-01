"""Export API routes with WebSocket progress"""

import sys
import asyncio
import uuid
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
import subprocess as sp
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.logger import logger
from web_ui.api.middleware.auth import (
    get_current_user,
    require_feature,
    AuthenticatedUser,
)

from models import Project
from core.export_pipeline import ExportPipeline
from backend.tts_service import TTSService
from backend.tts_providers import get_default_provider
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
from web_ui.api.utils.security import validate_path, validate_output_path, sanitize_filename
from web_ui.api.utils.usage_tracker import track_usage, check_usage_limit, UsageAction

router = APIRouter()


def _verify_project_ownership(project: Project, user: AuthenticatedUser) -> None:
    """
    Verify that the user owns the project.

    SECURITY: Prevents users from accessing other users' projects.

    Rules:
    1. If project has user_id, only that user (or admin) can access
    2. If project has no user_id (legacy), only admin can access
    3. Admins can access any project
    """
    # Admins can access any project
    if user.is_admin:
        return

    # Legacy projects (no user_id) - require admin access
    if project.user_id is None:
        raise HTTPException(
            status_code=403,
            detail="This is a legacy project. Admin access required."
        )

    # Regular ownership check
    if project.user_id != user.uid:
        raise HTTPException(status_code=404, detail="Project not found")


# Track active exports
active_exports: Dict[str, ExportQueueItem] = {}
# WebSocket connections for progress updates
progress_connections: Dict[str, WebSocket] = {}
# Track active export processes
active_processes: Dict[str, asyncio.subprocess.Process] = {}
# Path to export worker script (in parent api/ directory)
EXPORT_WORKER_PATH = Path(__file__).parent.parent / "export_worker.py"

# ============================================================================
# Segment Audio Generation Job Tracking (for voice cloning progress)
# ============================================================================
# Track active segment audio generation jobs
active_segment_audio_jobs: Dict[str, dict] = {}
# WebSocket connections for segment audio progress
segment_audio_connections: Dict[str, WebSocket] = {}
# Track active segment audio processes
active_segment_audio_processes: Dict[str, asyncio.subprocess.Process] = {}
# Path to voice clone worker script
VOICE_CLONE_WORKER_PATH = Path(__file__).parent.parent / "voice_clone_worker.py"


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
async def start_export(
    request: ExportRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Start a video export job (requires authentication)"""
    # SECURITY: Check export usage limit BEFORE starting export
    allowed, error_msg, usage_info = check_usage_limit(user.uid, UsageAction.EXPORT, 1)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Export limit reached. You've used {usage_info['current']} of {usage_info['limit']} exports this month. Upgrade your plan for more exports."
        )

    # Check export quality feature access (4K requires Pro tier)
    # Note: ExportConfig uses 'quality' field (lossless/high/balanced), not 'resolution'
    # The 4K check would apply if/when resolution field is added to the schema
    if getattr(request.config, 'resolution', None) == "4k" and not user.has_feature("export_4k"):
        raise HTTPException(
            status_code=403,
            detail="4K export requires Pro subscription or higher"
        )

    # Check export duration limits
    project = Project.load(request.project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify ownership
    _verify_project_ownership(project, user)

    max_duration = user.get_feature_limit("max_export_duration_minutes") or 5
    total_duration = sum(v.duration or 0 for v in project.videos) / 60  # Convert to minutes
    if total_duration > max_duration:
        raise HTTPException(
            status_code=403,
            detail=f"Export duration ({total_duration:.1f} min) exceeds your plan limit ({max_duration} min)"
        )

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
        user_id=user.uid,  # SECURITY: Track ownership
        status="queued",
        progress=0,
        output_path=output_path,
        started_at=datetime.now().isoformat()
    )
    active_exports[export_id] = queue_item

    # Start export in background task (non-blocking)
    # SECURITY: Subscription tier is obtained from Firestore via get_current_user,
    # NOT from client input. This ensures watermark enforcement cannot be bypassed.
    # Flow: Firebase Auth Token → verify_firebase_token() → _load_user_subscription(uid)
    #       → AuthenticatedUser.subscription_tier (from Firestore DB)
    asyncio.create_task(
        run_export(
            export_id,
            project,
            output_path,
            effective_config,  # Use the config with project BGM fallback
            request.export_type,
            request.video_id,
            user.subscription_tier.value,  # Server-verified tier for watermark enforcement
            user.uid  # User ID for usage tracking
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
    video_id: str = None,
    user_tier: str = "free_trial",
    user_id: str = None
):
    """
    Run export in a separate subprocess for true non-blocking behavior.

    The export worker runs as a completely separate Python process,
    communicating progress via JSON lines on stdout.

    Stderr is redirected to a log file to avoid pipe buffer deadlocks,
    allowing real-time progress streaming via stdout.

    Args:
        export_id: Unique export job ID
        project: Project to export
        output_path: Path to save output video
        config: Export configuration
        export_type: Type of export (single, combined, etc.)
        video_id: Optional video ID for single export
        user_tier: User's subscription tier for watermark enforcement
    """
    stderr_log_path = None
    stderr_file = None

    try:
        active_exports[export_id].status = "processing"

        # Build command for export worker subprocess
        # user_tier is passed to enforce watermark on free tier exports
        cmd = [
            sys.executable,  # Use same Python interpreter
            str(EXPORT_WORKER_PATH),
            project.name,
            output_path,
            config.quality,
            str(config.include_subtitles),
            export_type,
            str(video_id) if video_id else 'None',
            str(config.background_music_path) if config.background_music_path else 'None',
            user_tier  # Pass user tier for watermark logic
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

            # Track usage in Firebase
            if user_id:
                # Calculate export duration in minutes
                total_duration = sum(v.duration or 0 for v in project.videos) / 60
                track_usage(
                    user_id=user_id,
                    action=UsageAction.EXPORT,
                    amount=1,  # Count as 1 export
                    metadata={
                        "export_id": export_id,
                        "project_name": project.name,
                        "duration_minutes": total_duration,
                        "file_size_mb": file_size_mb,
                        "quality": config.quality,
                    }
                )
                logger.info(f"[Export {export_id}] Usage tracked for user {user_id}")

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
async def get_export_status(
    export_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get current export status"""
    if export_id not in active_exports:
        raise HTTPException(status_code=404, detail="Export not found")

    item = active_exports[export_id]
    # SECURITY: Verify ownership - users can only see their own exports
    if item.user_id != user.uid and not user.is_admin:
        raise HTTPException(status_code=404, detail="Export not found")

    return item


@router.get("/queue")
async def get_export_queue(user: AuthenticatedUser = Depends(get_current_user)):
    """Get active exports for the current user"""
    # SECURITY: Filter exports by user_id - users can only see their own exports
    user_exports = [
        export for export in active_exports.values()
        if export.user_id == user.uid or user.is_admin
    ]
    return {"exports": user_exports}


@router.delete("/cancel/{export_id}")
async def cancel_export(
    export_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Cancel an export job"""
    if export_id not in active_exports:
        raise HTTPException(status_code=404, detail="Export not found")

    item = active_exports[export_id]
    # SECURITY: Verify ownership - users can only cancel their own exports
    if item.user_id != user.uid and not user.is_admin:
        raise HTTPException(status_code=404, detail="Export not found")
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
async def generate_preview(
    request: PreviewRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate a preview for a single segment"""
    project = Project.load(request.project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify ownership
    _verify_project_ownership(project, user)

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


async def _generate_voice_cloning_audio(
    voice_sample_id: str,
    text: str,
    language: str,
    output_path: Path,
) -> tuple[bool, float, str]:
    """
    Generate audio using voice cloning in a subprocess (non-blocking).

    Returns tuple of (success, duration, error_message)
    """
    import json as json_module

    # Get voice sample path
    voice_samples_dir = Path(settings.STORAGE_DIR) / "voice_samples"
    metadata_file = voice_samples_dir / "metadata.json"

    if not metadata_file.exists():
        return False, 0.0, "No voice samples found"

    metadata = json_module.loads(metadata_file.read_text())
    if voice_sample_id not in metadata.get("samples", {}):
        return False, 0.0, f"Voice sample not found: {voice_sample_id}"

    sample_info = metadata["samples"][voice_sample_id]
    sample_path = voice_samples_dir / sample_info["filename"]

    if not sample_path.exists():
        return False, 0.0, f"Voice sample file not found: {sample_path}"

    # Path to voice clone worker
    worker_path = Path(__file__).parent.parent / "voice_clone_worker.py"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run voice cloning in subprocess
    cmd = [
        sys.executable,
        str(worker_path),
        str(sample_path),
        text,
        str(output_path),
        language
    ]

    logger.info(f"[VoiceClone] Starting subprocess for segment audio: {output_path}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent.parent.parent),
            start_new_session=True
        )

        # Wait for completion with timeout (10 minutes)
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=600
        )

        # Parse output for result
        result_data = None
        for line in stdout.decode('utf-8').strip().split('\n'):
            if line:
                try:
                    data = json_module.loads(line)
                    if data.get('type') == 'result':
                        result_data = data
                    elif data.get('type') == 'progress':
                        logger.info(f"[VoiceClone] {data.get('stage')}: {data.get('message')} ({data.get('progress')}%)")
                except json_module.JSONDecodeError:
                    pass

        if process.returncode == 0 and result_data and result_data.get('success'):
            duration = result_data.get('duration', 0.0)
            logger.info(f"[VoiceClone] Completed: {output_path} ({duration:.1f}s)")
            return True, duration, ""
        else:
            error_msg = "Voice cloning failed"
            if result_data and result_data.get('error'):
                error_msg = result_data.get('error')
            elif stderr:
                error_msg = stderr.decode('utf-8')[-500:]  # Last 500 chars
            logger.error(f"[VoiceClone] Failed: {error_msg}")
            return False, 0.0, error_msg

    except asyncio.TimeoutError:
        logger.error("[VoiceClone] Subprocess timed out")
        return False, 0.0, "Voice cloning timed out"
    except Exception as e:
        logger.error(f"[VoiceClone] Subprocess error: {e}")
        return False, 0.0, str(e)


async def send_segment_audio_progress(
    job_id: str,
    stage: str,
    message: str,
    progress: int,
    status: str = "processing",
    **kwargs
):
    """Send progress update via WebSocket for segment audio generation"""
    if job_id in segment_audio_connections:
        try:
            await segment_audio_connections[job_id].send_json({
                "stage": stage,
                "message": message,
                "progress": progress,
                "status": status,
                **kwargs
            })
        except Exception:
            pass

    # Update job status
    if job_id in active_segment_audio_jobs:
        active_segment_audio_jobs[job_id]["progress"] = progress
        active_segment_audio_jobs[job_id]["stage"] = stage
        active_segment_audio_jobs[job_id]["message"] = message
        active_segment_audio_jobs[job_id]["status"] = status


async def run_segment_voice_cloning(
    job_id: str,
    voice_sample_path: str,
    text: str,
    output_path: str,
    language: str,
    project: 'Project',
    segment,
):
    """
    Run voice cloning for segment audio in a separate subprocess with real-time progress.
    Updates the segment when complete.
    """
    stderr_log_path = None
    stderr_file = None

    try:
        active_segment_audio_jobs[job_id]["status"] = "processing"

        # Build command for voice clone worker subprocess
        cmd = [
            sys.executable,
            str(VOICE_CLONE_WORKER_PATH),
            voice_sample_path,
            text,
            output_path,
            language
        ]

        logger.info(f"[SegmentAudio {job_id}] Starting voice clone worker")

        # Create a log file for stderr
        stderr_log_path = Path(settings.TEMP_DIR) / f"segment_audio_{job_id}_stderr.log"
        Path(settings.TEMP_DIR).mkdir(parents=True, exist_ok=True)
        stderr_file = open(stderr_log_path, 'w')

        # Start subprocess with detached process group
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=stderr_file,
            cwd=str(Path(__file__).parent.parent.parent.parent),
            start_new_session=True
        )

        active_segment_audio_processes[job_id] = process
        logger.info(f"[SegmentAudio {job_id}] Worker started with PID: {process.pid}")

        # Read stdout for real-time progress updates
        result_data = None
        try:
            while True:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=600  # 10 minute timeout
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

                            logger.info(f"[SegmentAudio {job_id}] {stage}: {message} ({progress}%)")

                            await send_segment_audio_progress(
                                job_id,
                                stage,
                                message,
                                progress
                            )

                        elif data.get('type') == 'result':
                            result_data = data

                        elif data.get('type') == 'error':
                            logger.error(f"[SegmentAudio {job_id}] Error: {data.get('message')}")
                            raise Exception(data.get('message', 'Unknown error'))

                except json.JSONDecodeError:
                    pass

        except asyncio.TimeoutError:
            logger.error(f"[SegmentAudio {job_id}] Worker timed out")
            process.kill()
            raise Exception("Voice cloning timed out")

        # Wait for process to complete
        await process.wait()

        logger.info(f"[SegmentAudio {job_id}] Worker finished with return code: {process.returncode}")

        # Check exit code and result
        if process.returncode == 0 and result_data and result_data.get('success'):
            duration = result_data.get('duration', 0)
            output_file = Path(output_path)

            if output_file.exists():
                # Calculate audio URL
                audio_url = f"/storage/{output_file.relative_to(settings.STORAGE_DIR)}"

                # Update segment with audio path and provider (voice cloning uses Coqui)
                segment.audio_path = str(output_path)
                segment.tts_provider = 'coqui'

                # Generate subtitles for the cloned voice audio
                try:
                    tts_service = TTSService()
                    # Get video orientation for subtitle formatting
                    orientation = 'horizontal'
                    if hasattr(segment, 'video_id') and segment.video_id:
                        video = project.get_video(segment.video_id)
                        if video and hasattr(video, 'orientation'):
                            orientation = video.orientation or 'horizontal'

                    # Generate subtitle using fallback method (estimated timing based on duration)
                    subtitle_path = output_file.with_suffix('.srt')
                    subtitle_content = tts_service._generate_accurate_subtitles_fallback(
                        text, duration, orientation
                    )
                    subtitle_path.write_text(subtitle_content, encoding='utf-8')
                    segment.subtitle_path = str(subtitle_path)
                    logger.info(f"[SegmentAudio {job_id}] Generated subtitle: {subtitle_path}")

                    # Store in TTS cache for future lookups
                    # Use voice_sample_id in cache key for proper isolation
                    voice_sample_id = getattr(segment, 'voice_sample_id', None)
                    if voice_sample_id:
                        import hashlib
                        cache_key_content = f"voice_clone_{voice_sample_id}_{text}_{language}"
                        cache_key = hashlib.md5(cache_key_content.encode()).hexdigest()
                        tts_service.store_cache_mapping(cache_key, segment.audio_path, segment.subtitle_path)
                        logger.info(f"[SegmentAudio {job_id}] Cached voice cloning result with key: {cache_key[:8]}")
                except Exception as e:
                    logger.warning(f"[SegmentAudio {job_id}] Failed to generate subtitle: {e}")
                    segment.subtitle_path = None

                project.save()

                active_segment_audio_jobs[job_id].update({
                    "status": "completed",
                    "progress": 100,
                    "audio_url": audio_url,
                    "duration": duration,
                })

                logger.info(f"[SegmentAudio {job_id}] COMPLETED - File: {output_path} ({duration:.1f}s)")

                await send_segment_audio_progress(
                    job_id, "completed",
                    "Audio generated successfully!", 100,
                    status="completed",
                    audio_url=audio_url,
                    duration=duration
                )
            else:
                raise Exception("Output file was not created")
        else:
            # Read stderr from log file for error message
            error_msg = "Voice cloning failed"
            if stderr_log_path and stderr_log_path.exists():
                stderr_file.close()
                stderr_file = None
                with open(stderr_log_path, 'r') as f:
                    stderr_lines = f.readlines()
                    if stderr_lines:
                        error_msg = "".join(stderr_lines[-10:])
            raise Exception(error_msg)

    except Exception as e:
        active_segment_audio_jobs[job_id]["status"] = "failed"
        active_segment_audio_jobs[job_id]["error"] = str(e)
        await send_segment_audio_progress(
            job_id, "error", f"Failed: {str(e)}", 0,
            status="failed"
        )
    finally:
        # Clean up
        if stderr_file:
            stderr_file.close()
        if stderr_log_path and stderr_log_path.exists():
            try:
                stderr_log_path.unlink()
            except Exception:
                pass
        if job_id in active_segment_audio_processes:
            del active_segment_audio_processes[job_id]


@router.websocket("/segment-audio/progress/{job_id}")
async def segment_audio_progress_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for segment audio generation progress"""
    await websocket.accept()
    segment_audio_connections[job_id] = websocket
    logger.info(f"[SegmentAudio {job_id}] WebSocket connected")

    try:
        # Send current status immediately
        if job_id in active_segment_audio_jobs:
            job = active_segment_audio_jobs[job_id]
            await websocket.send_json({
                "stage": job.get("stage", "initializing"),
                "message": job.get("message", "Starting..."),
                "progress": job.get("progress", 0),
                "status": job.get("status", "processing"),
                "audio_url": job.get("audio_url"),
                "duration": job.get("duration"),
            })

            # If already completed, send completion
            if job.get("status") == "completed":
                await websocket.send_json({
                    "stage": "completed",
                    "message": "Audio generated successfully!",
                    "progress": 100,
                    "status": "completed",
                    "audio_url": job.get("audio_url"),
                    "duration": job.get("duration"),
                })

        # Keep connection alive
        ping_failures = 0
        max_ping_failures = 3

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "pong":
                    ping_failures = 0
                elif data == "status":
                    if job_id in active_segment_audio_jobs:
                        job = active_segment_audio_jobs[job_id]
                        await websocket.send_json({
                            "stage": job.get("stage", "processing"),
                            "message": job.get("message", "Processing..."),
                            "progress": job.get("progress", 0),
                            "status": job.get("status", "processing"),
                            "audio_url": job.get("audio_url"),
                            "duration": job.get("duration"),
                        })
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text("ping")
                    ping_failures += 1
                    if ping_failures >= max_ping_failures:
                        logger.warning(f"[SegmentAudio {job_id}] WebSocket ping failures exceeded, closing")
                        break
                except Exception as e:
                    logger.warning(f"[SegmentAudio {job_id}] WebSocket ping failed: {e}")
                    break

    except WebSocketDisconnect:
        logger.info(f"[SegmentAudio {job_id}] WebSocket disconnected by client")
    except Exception as e:
        logger.warning(f"[SegmentAudio {job_id}] WebSocket error: {e}")
    finally:
        if job_id in segment_audio_connections:
            del segment_audio_connections[job_id]
        logger.info(f"[SegmentAudio {job_id}] WebSocket closed")


@router.get("/segment-audio/status/{job_id}")
async def get_segment_audio_status(
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get current segment audio generation status"""
    if job_id not in active_segment_audio_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return active_segment_audio_jobs[job_id]


@router.post("/segment-audio", response_model=SegmentAudioResponse)
async def generate_segment_audio(
    request: SegmentAudioRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate or retrieve audio for a specific segment"""
    project = Project.load(request.project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Verify ownership
    _verify_project_ownership(project, user)

    # Find segment - check generic segments first, then video-specific
    segment = None
    video = None

    # Check generic/project-level segments (multi-video projects)
    for s in project.generic_segments:
        if s.id == request.segment_id:
            segment = s
            # For generic segments, use first video for orientation reference
            video = project.videos[0] if project.videos else None
            break

    # Check video-specific segments
    if not segment:
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

    voice_sample_id = getattr(segment, 'voice_sample_id', None)
    orientation = video.orientation if video and video.orientation else 'horizontal'

    # Use async job with progress for voice cloning
    if voice_sample_id:
        # Get voice sample path
        import json as json_module
        voice_samples_dir = Path(settings.STORAGE_DIR) / "voice_samples"
        metadata_file = voice_samples_dir / "metadata.json"

        if not metadata_file.exists():
            raise HTTPException(status_code=404, detail="No voice samples found")

        metadata = json_module.loads(metadata_file.read_text())
        if voice_sample_id not in metadata.get("samples", {}):
            raise HTTPException(status_code=404, detail=f"Voice sample not found: {voice_sample_id}")

        sample_info = metadata["samples"][voice_sample_id]
        sample_path = voice_samples_dir / sample_info["filename"]

        if not sample_path.exists():
            raise HTTPException(status_code=404, detail=f"Voice sample file not found")

        # Generate output path
        project_dir = Path(settings.PROJECTS_DIR) / project.name / segment.language
        project_dir.mkdir(parents=True, exist_ok=True)
        segment_name = segment.name.replace(" ", "_")
        output_path = project_dir / f"{segment_name}.wav"

        # Create job for progress tracking
        job_id = str(uuid.uuid4())[:8]
        active_segment_audio_jobs[job_id] = {
            "status": "initializing",
            "progress": 0,
            "stage": "initializing",
            "message": "Starting voice cloning...",
            "segment_id": segment.id,
            "project_name": project.name,
        }

        # Start async voice cloning task
        asyncio.create_task(
            run_segment_voice_cloning(
                job_id=job_id,
                voice_sample_path=str(sample_path),
                text=segment.text,
                output_path=str(output_path),
                language=segment.language,
                project=project,
                segment=segment,
            )
        )

        # Return job_id immediately - client should connect to WebSocket for progress
        return SegmentAudioResponse(
            audio_url="",  # Will be available after job completes
            duration=0,
            cached=False,
            job_id=job_id  # Client uses this to connect to WebSocket
        )

    # Regular TTS generation
    tts_service = TTSService()

    # Use segment's saved provider, or detect from voice_id prefix
    segment_provider = getattr(segment, 'tts_provider', None)
    if not segment_provider:
        # Detect provider from voice_id prefix
        if segment.voice_id.startswith("coqui_"):
            segment_provider = "coqui"
        elif segment.voice_id.startswith("piper_"):
            segment_provider = "piper"
        else:
            segment_provider = get_default_provider().value

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
        provider=segment_provider,
    )

    # Update segment with audio paths (keep existing provider)
    segment.audio_path = audio_path
    segment.subtitle_path = subtitle_path
    # Only set provider if not already set
    if not getattr(segment, 'tts_provider', None):
        segment.tts_provider = segment_provider
    project.save()

    duration = FFmpegUtils.get_media_duration(audio_path)

    return SegmentAudioResponse(
        audio_url=f"/storage/{Path(audio_path).relative_to(settings.STORAGE_DIR)}",
        duration=duration or 0,
        cached=False
    )


@router.post("/preview-segment-audio", response_model=PreviewSegmentAudioResponse)
async def preview_segment_audio(
    request: PreviewSegmentAudioRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Preview segment audio with custom voice/language/parameters without saving to project"""
    tts_service = TTSService()

    # Generate unique segment name including all parameters for proper caching
    # This ensures different parameter combinations get separate audio files
    param_hash = hash(f"{request.text}_{request.rate}_{request.volume}_{request.pitch}") % 100000
    segment_name = f"preview_{request.voice_id[:20]}_{param_hash}"

    # Detect provider from voice_id prefix
    if request.voice_id.startswith("coqui_"):
        provider = "coqui"
    elif request.voice_id.startswith("piper_"):
        provider = "piper"
    else:
        provider = None  # Use default

    # Generate preview audio using provider-aware method
    audio_path, _ = await tts_service.generate_audio_with_provider(
        text=request.text,
        language=request.language,
        voice=request.voice_id,
        project_name=request.project_name,
        segment_name=segment_name,
        rate=request.rate,
        volume=request.volume,
        pitch=request.pitch,
        provider=provider,
    )

    duration = FFmpegUtils.get_media_duration(audio_path)

    return PreviewSegmentAudioResponse(
        audio_url=f"/storage/{Path(audio_path).relative_to(settings.STORAGE_DIR)}",
        duration=duration or 0
    )


@router.get("/download/{export_id}")
async def download_export(
    export_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Download completed export"""
    if export_id not in active_exports:
        raise HTTPException(status_code=404, detail="Export not found")

    item = active_exports[export_id]
    # SECURITY: Verify ownership - users can only download their own exports
    if item.user_id != user.uid and not user.is_admin:
        raise HTTPException(status_code=404, detail="Export not found")

    if item.status != "completed" or not item.output_path:
        raise HTTPException(status_code=400, detail="Export not ready for download")

    from fastapi.responses import FileResponse
    return FileResponse(
        item.output_path,
        media_type="video/mp4",
        filename=Path(item.output_path).name
    )


@router.get("/output-dir")
async def get_output_directory(user: AuthenticatedUser = Depends(get_current_user)):
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
async def browse_directories(
    request: BrowseDirectoryRequest = None,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Browse directories for output path selection"""
    # Default to output directory or home
    if request and request.path:
        # Validate path to prevent directory traversal attacks
        try:
            validated_path = validate_path(request.path, must_exist=False)
            current_path = Path(validated_path)
        except HTTPException:
            # If validation fails, fall back to default
            current_path = Path(settings.OUTPUT_DIR)
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
async def set_output_directory(
    request: BrowseDirectoryRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Set the output directory for exports"""
    if not request.path:
        raise HTTPException(status_code=400, detail="Path is required")

    # Validate the path using security utilities
    validated_path = validate_output_path(request.path)
    output_path = Path(validated_path)

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
