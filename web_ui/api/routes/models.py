"""Model Management API Routes

Handles TTS model download, status checking, and management.
Uses subprocess worker for non-blocking operations.

SECURITY: Model download and cancellation require authentication.
"""

import sys
import os
import json
import asyncio
import uuid
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.logger import logger
from web_ui.api.middleware.auth import get_current_user, AuthenticatedUser

router = APIRouter()

# Path to model worker script
MODEL_WORKER_PATH = Path(__file__).parent.parent / "model_worker.py"

# Global state for tracking model operations
active_downloads: Dict[str, dict] = {}
progress_connections: Dict[str, WebSocket] = {}
active_processes: Dict[str, asyncio.subprocess.Process] = {}

# Supported models for voice cloning
VOICE_CLONING_MODELS = {
    "xtts_v2": {
        "name": "XTTS v2",
        "model_id": "tts_models/multilingual/multi-dataset/xtts_v2",
        "description": "Multilingual voice cloning model supporting 17 languages",
        "size_mb": 1800,
        "languages": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"],
        "recommended": True
    }
}


class ModelDownloadRequest(BaseModel):
    """Request to download a model"""
    model_id: str


class ModelStatusResponse(BaseModel):
    """Model status information"""
    model_id: str
    name: str
    description: str
    size_mb: int
    downloaded: bool
    downloading: bool
    download_progress: int
    languages: List[str]
    recommended: bool
    error: Optional[str] = None


async def send_progress(download_id: str, data: dict):
    """Send progress update via WebSocket"""
    if download_id in progress_connections:
        try:
            await progress_connections[download_id].send_json(data)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket update: {e}")

    # Also update the active download record
    if download_id in active_downloads:
        active_downloads[download_id].update({
            "progress": data.get("progress", 0),
            "stage": data.get("stage", "unknown"),
            "message": data.get("message", ""),
            "last_update": datetime.now().isoformat()
        })


async def run_model_download(download_id: str, model_id: str):
    """Run model download in subprocess"""
    logger.info(f"[Download {download_id}] Starting download for {model_id}")

    cmd = [
        sys.executable,
        str(MODEL_WORKER_PATH),
        "download",
        model_id
    ]

    try:
        # Start subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True  # Prevent signal propagation
        )

        active_processes[download_id] = process
        active_downloads[download_id]["status"] = "downloading"
        active_downloads[download_id]["pid"] = process.pid

        # Read stdout for progress updates
        while True:
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=600  # 10 minute timeout for large downloads
                )
            except asyncio.TimeoutError:
                logger.error(f"[Download {download_id}] Timed out waiting for progress")
                process.kill()
                await process.wait()
                active_downloads[download_id]["status"] = "failed"
                active_downloads[download_id]["error"] = "Download timed out"
                await send_progress(download_id, {
                    "type": "error",
                    "stage": "error",
                    "message": "Download timed out after 10 minutes",
                    "progress": 0
                })
                return

            if not line:
                break

            try:
                line_text = line.decode('utf-8').strip()
                if line_text:
                    data = json.loads(line_text)

                    if data.get("type") == "progress":
                        await send_progress(download_id, data)
                        logger.info(f"[Download {download_id}] {data.get('stage')}: {data.get('message')} ({data.get('progress')}%)")

                    elif data.get("type") == "error":
                        logger.error(f"[Download {download_id}] Error: {data.get('message')}")
                        active_downloads[download_id]["status"] = "failed"
                        active_downloads[download_id]["error"] = data.get("message")
                        await send_progress(download_id, {
                            "type": "error",
                            "stage": "error",
                            "message": data.get("message"),
                            "details": data.get("details"),
                            "progress": 0
                        })

                    elif data.get("type") == "result":
                        if data.get("success"):
                            active_downloads[download_id]["status"] = "completed"
                            active_downloads[download_id]["completed_at"] = datetime.now().isoformat()
                            await send_progress(download_id, {
                                "type": "complete",
                                "stage": "complete",
                                "message": "Model downloaded successfully",
                                "progress": 100,
                                "size_mb": data.get("size_mb")
                            })
                        else:
                            active_downloads[download_id]["status"] = "failed"
                            active_downloads[download_id]["error"] = data.get("error", "Unknown error")

            except json.JSONDecodeError:
                # Non-JSON output, log it
                logger.debug(f"[Download {download_id}] Non-JSON output: {line_text}")

        # Wait for process to complete
        await process.wait()

        if process.returncode != 0:
            stderr = await process.stderr.read()
            error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
            logger.error(f"[Download {download_id}] Process exited with code {process.returncode}: {error_msg}")

            if active_downloads[download_id]["status"] != "failed":
                active_downloads[download_id]["status"] = "failed"
                active_downloads[download_id]["error"] = error_msg[:200]

    except Exception as e:
        logger.exception(f"[Download {download_id}] Exception during download: {e}")
        active_downloads[download_id]["status"] = "failed"
        active_downloads[download_id]["error"] = str(e)
        await send_progress(download_id, {
            "type": "error",
            "stage": "error",
            "message": str(e),
            "progress": 0
        })

    finally:
        if download_id in active_processes:
            del active_processes[download_id]


@router.get("/voice-cloning")
async def get_voice_cloning_models():
    """
    Get list of voice cloning models with their status.

    Returns information about available models including:
    - Whether they are downloaded
    - Download progress if currently downloading
    - Model capabilities and requirements
    """
    models = []

    for key, info in VOICE_CLONING_MODELS.items():
        model_id = info["model_id"]

        # Check if model is downloaded
        downloaded = False
        try:
            # Quick check without loading the model
            cmd = [sys.executable, str(MODEL_WORKER_PATH), "check", model_id]
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)

            if stdout:
                for line in stdout.decode('utf-8').strip().split('\n'):
                    try:
                        data = json.loads(line)
                        if data.get("type") == "result" and data.get("downloaded"):
                            downloaded = True
                            break
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            logger.warning(f"Failed to check model status: {e}")

        # Check if currently downloading
        downloading = False
        download_progress = 0
        error = None

        for download_id, download_info in active_downloads.items():
            if download_info.get("model_id") == model_id:
                if download_info["status"] == "downloading":
                    downloading = True
                    download_progress = download_info.get("progress", 0)
                elif download_info["status"] == "failed":
                    error = download_info.get("error")
                break

        models.append(ModelStatusResponse(
            model_id=model_id,
            name=info["name"],
            description=info["description"],
            size_mb=info["size_mb"],
            downloaded=downloaded,
            downloading=downloading,
            download_progress=download_progress,
            languages=info["languages"],
            recommended=info.get("recommended", False),
            error=error
        ))

    return {"models": models}


@router.post("/voice-cloning/download")
async def start_model_download(
    request: ModelDownloadRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Start downloading a voice cloning model (requires authentication).

    Returns a download_id that can be used to track progress via WebSocket.
    """
    model_id = request.model_id

    # Validate model
    valid_models = [info["model_id"] for info in VOICE_CLONING_MODELS.values()]
    if model_id not in valid_models:
        raise HTTPException(status_code=400, detail=f"Invalid model ID. Valid models: {valid_models}")

    # Check if already downloading
    for download_id, download_info in active_downloads.items():
        if download_info.get("model_id") == model_id and download_info["status"] == "downloading":
            return {
                "download_id": download_id,
                "status": "already_downloading",
                "message": "Model is already being downloaded"
            }

    # Generate download ID
    download_id = str(uuid.uuid4())[:8]

    # Create download record
    active_downloads[download_id] = {
        "id": download_id,
        "model_id": model_id,
        "status": "queued",
        "progress": 0,
        "stage": "initializing",
        "message": "Starting download...",
        "started_at": datetime.now().isoformat(),
        "error": None
    }

    # Start download in background
    asyncio.create_task(run_model_download(download_id, model_id))

    logger.info(f"Started model download: {download_id} for {model_id}")

    return {
        "download_id": download_id,
        "status": "started",
        "message": f"Download started for {model_id}"
    }


@router.websocket("/voice-cloning/progress/{download_id}")
async def model_download_progress(websocket: WebSocket, download_id: str):
    """WebSocket endpoint for model download progress updates"""
    await websocket.accept()
    progress_connections[download_id] = websocket
    logger.info(f"[Download {download_id}] WebSocket connected")

    try:
        # Send current status immediately
        if download_id in active_downloads:
            item = active_downloads[download_id]
            await websocket.send_json({
                "type": "status",
                "stage": item.get("stage", "unknown"),
                "message": item.get("message", ""),
                "progress": item.get("progress", 0),
                "status": item.get("status", "unknown")
            })

            # If already completed or failed, send that
            if item["status"] == "completed":
                await websocket.send_json({
                    "type": "complete",
                    "stage": "complete",
                    "message": "Model downloaded successfully",
                    "progress": 100
                })
            elif item["status"] == "failed":
                await websocket.send_json({
                    "type": "error",
                    "stage": "error",
                    "message": item.get("error", "Download failed"),
                    "progress": 0
                })

        # Keep connection alive with ping/pong
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "status":
                    if download_id in active_downloads:
                        item = active_downloads[download_id]
                        await websocket.send_json({
                            "type": "status",
                            "stage": item.get("stage", "unknown"),
                            "message": item.get("message", ""),
                            "progress": item.get("progress", 0),
                            "status": item.get("status", "unknown")
                        })
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"[Download {download_id}] WebSocket disconnected")
    except Exception as e:
        logger.warning(f"[Download {download_id}] WebSocket error: {e}")
    finally:
        if download_id in progress_connections:
            del progress_connections[download_id]


@router.get("/voice-cloning/status/{download_id}")
async def get_download_status(download_id: str):
    """Get current status of a model download"""
    if download_id not in active_downloads:
        raise HTTPException(status_code=404, detail="Download not found")

    return active_downloads[download_id]


@router.delete("/voice-cloning/cancel/{download_id}")
async def cancel_download(
    download_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Cancel an ongoing model download (requires authentication)"""
    if download_id not in active_downloads:
        raise HTTPException(status_code=404, detail="Download not found")

    item = active_downloads[download_id]

    if item["status"] == "downloading":
        # Kill the subprocess
        if download_id in active_processes:
            process = active_processes[download_id]
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
            except Exception as e:
                logger.warning(f"Failed to kill process: {e}")

        item["status"] = "cancelled"
        item["error"] = "Cancelled by user"

        await send_progress(download_id, {
            "type": "error",
            "stage": "cancelled",
            "message": "Download cancelled by user",
            "progress": 0
        })

    return {"message": "Download cancelled", "status": item["status"]}


@router.get("/voice-cloning/check/{model_key}")
async def check_model_status(model_key: str):
    """
    Quick check if a specific model is ready to use.

    model_key: The short key like 'xtts_v2'
    """
    if model_key not in VOICE_CLONING_MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_key}")

    model_info = VOICE_CLONING_MODELS[model_key]
    model_id = model_info["model_id"]

    try:
        cmd = [sys.executable, str(MODEL_WORKER_PATH), "check", model_id]
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)

        downloaded = False
        size_mb = 0

        if stdout:
            for line in stdout.decode('utf-8').strip().split('\n'):
                try:
                    data = json.loads(line)
                    if data.get("type") == "result":
                        downloaded = data.get("downloaded", False)
                        size_mb = data.get("size_mb", 0)
                        break
                except json.JSONDecodeError:
                    pass

        return {
            "model_key": model_key,
            "model_id": model_id,
            "name": model_info["name"],
            "downloaded": downloaded,
            "ready": downloaded,
            "size_mb": size_mb
        }

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Check timed out")
    except Exception as e:
        logger.exception(f"Failed to check model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
