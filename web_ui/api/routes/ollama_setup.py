"""
Ollama Setup API Routes

Handles Ollama installation detection, model management, and user consent
for local AI processing.

Author: LxusBrain
"""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.logger import logger
from web_ui.api.services.ollama_setup import (
    get_ollama_service,
    RECOMMENDED_MODELS,
)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class OllamaStatusResponse(BaseModel):
    """Response for Ollama status check"""
    installed: bool
    running: bool
    version: Optional[str] = None
    models: List[str] = []
    endpoint: str
    install_path: Optional[str] = None
    error: Optional[str] = None


class ConsentRequest(BaseModel):
    """Request to grant consent for local AI"""
    acknowledged_items: List[str]


class ConsentResponse(BaseModel):
    """Response after recording consent"""
    consented: bool
    consent_date: Optional[str] = None
    consent_version: str
    acknowledged_items: List[str] = []


class ModelPullRequest(BaseModel):
    """Request to pull/download an Ollama model"""
    model_name: str


class SetupWizardResponse(BaseModel):
    """Response with all setup wizard data"""
    ollama: Dict[str, Any]
    consent: Dict[str, Any]
    recommended_models: Dict[str, List[Dict]]
    system: Dict[str, str]


# ============================================================================
# Status Endpoints
# ============================================================================

@router.get("/status", response_model=OllamaStatusResponse)
async def get_ollama_status():
    """
    Check Ollama installation and running status.

    Returns comprehensive status including:
    - Whether Ollama is installed
    - Whether the Ollama server is running
    - Ollama version (if running)
    - List of installed models
    - Installation path
    """
    try:
        service = get_ollama_service()
        status = await service.get_full_status()
        return OllamaStatusResponse(**status.to_dict())
    except Exception as e:
        logger.error(f"Failed to get Ollama status: {e}")
        return OllamaStatusResponse(
            installed=False,
            running=False,
            endpoint="http://localhost:11434",
            error=str(e)
        )


@router.get("/check-installed")
async def check_ollama_installed():
    """
    Quick check if Ollama is installed.

    Lighter weight than /status - just checks installation.
    """
    service = get_ollama_service()
    installed, path = service.is_ollama_installed()
    return {
        "installed": installed,
        "install_path": path
    }


@router.get("/check-running")
async def check_ollama_running():
    """
    Quick check if Ollama server is running.
    """
    service = get_ollama_service()
    running = await service.is_ollama_running()
    return {"running": running}


# ============================================================================
# Installation Guidance
# ============================================================================

@router.get("/install-instructions")
async def get_install_instructions():
    """
    Get platform-specific installation instructions.

    Returns detailed steps for installing Ollama on the current OS.
    """
    service = get_ollama_service()
    return service.get_install_instructions()


@router.get("/download-url")
async def get_download_url():
    """
    Get the Ollama download URL for the current platform.
    """
    service = get_ollama_service()
    return {"url": service.get_download_url()}


@router.post("/open-download-page")
async def open_download_page():
    """
    Open Ollama download page in the user's default browser.
    """
    service = get_ollama_service()
    success = service.open_download_page()
    return {"success": success}


# ============================================================================
# Model Management
# ============================================================================

@router.get("/recommended-models")
async def get_recommended_models():
    """
    Get recommended models for TermiVoxed.

    Returns categorized models (text and vision) with their
    requirements and use cases.
    """
    return RECOMMENDED_MODELS


@router.get("/installed-models")
async def get_installed_models():
    """
    Get list of currently installed Ollama models.
    """
    service = get_ollama_service()

    if not await service.is_ollama_running():
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Please start Ollama first."
        )

    models = await service.get_installed_models()
    return {"models": models}


@router.post("/pull-model")
async def pull_model(request: ModelPullRequest):
    """
    Start downloading/pulling an Ollama model.

    Returns a streaming response with download progress updates.
    """
    service = get_ollama_service()

    if not await service.is_ollama_running():
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Please start Ollama first."
        )

    async def generate_progress():
        async for update in service.pull_model(request.model_name):
            # Format as SSE
            import json
            yield f"data: {json.dumps(update)}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.delete("/delete-model/{model_name:path}")
async def delete_model(model_name: str):
    """
    Delete an installed Ollama model.
    """
    service = get_ollama_service()

    if not await service.is_ollama_running():
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Please start Ollama first."
        )

    success = await service.delete_model(model_name)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete model: {model_name}"
        )

    return {"success": True, "message": f"Model {model_name} deleted"}


# ============================================================================
# Consent Management
# ============================================================================

@router.get("/consent/status")
async def get_consent_status():
    """
    Check if user has granted consent for local AI processing.
    """
    service = get_ollama_service()
    consent = service.load_consent()
    return consent.to_dict()


@router.get("/consent/has-consent")
async def has_consent():
    """
    Quick check if user has consented to local AI.
    """
    service = get_ollama_service()
    return {"has_consent": service.has_user_consent()}


@router.post("/consent/grant", response_model=ConsentResponse)
async def grant_consent(request: ConsentRequest):
    """
    Grant consent for local AI processing.

    User must acknowledge specific items:
    - local_processing: Data processed on device
    - model_storage: Models stored locally (can be several GB)
    - resource_usage: CPU/GPU/RAM usage during inference
    - no_cloud: No data sent to external servers for Ollama
    """
    service = get_ollama_service()

    # Validate acknowledged items
    valid_items = {"local_processing", "model_storage", "resource_usage", "no_cloud"}
    acknowledged = set(request.acknowledged_items)

    if not acknowledged.issubset(valid_items):
        invalid = acknowledged - valid_items
        raise HTTPException(
            status_code=400,
            detail=f"Invalid acknowledgment items: {invalid}"
        )

    consent = service.grant_consent(request.acknowledged_items)

    logger.info(f"Local AI consent granted with items: {request.acknowledged_items}")

    return ConsentResponse(**consent.to_dict())


@router.post("/consent/revoke")
async def revoke_consent():
    """
    Revoke consent for local AI processing.

    User can revoke consent at any time. This does not delete
    downloaded models - use /delete-model for that.
    """
    service = get_ollama_service()
    success = service.revoke_consent()

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke consent"
        )

    logger.info("Local AI consent revoked")

    return {"success": True, "message": "Consent revoked"}


# ============================================================================
# Setup Wizard
# ============================================================================

@router.get("/wizard-data", response_model=SetupWizardResponse)
async def get_setup_wizard_data():
    """
    Get all data needed for the Ollama setup wizard.

    Returns comprehensive data including:
    - Ollama installation status
    - Installation instructions
    - Consent status
    - Recommended models
    - System information
    """
    service = get_ollama_service()
    data = service.get_setup_wizard_data()

    # Add runtime status
    data["ollama"]["running"] = await service.is_ollama_running()
    if data["ollama"]["running"]:
        data["ollama"]["version"] = await service.get_ollama_version()
        models = await service.get_installed_models()
        data["ollama"]["installed_models"] = [m.get("name", "") for m in models]
    else:
        data["ollama"]["version"] = None
        data["ollama"]["installed_models"] = []

    return SetupWizardResponse(**data)


@router.get("/first-run-check")
async def first_run_check():
    """
    Check if this is the first run and what setup is needed.

    Returns:
    - needs_ollama_setup: Ollama not installed or no models
    - needs_consent: User hasn't granted local AI consent
    - recommended_action: What the user should do next
    """
    service = get_ollama_service()

    installed, _ = service.is_ollama_installed()
    running = await service.is_ollama_running()
    has_consent = service.has_user_consent()

    models = []
    if running:
        models_data = await service.get_installed_models()
        models = [m.get("name", "") for m in models_data]

    needs_ollama = not installed
    needs_models = installed and running and len(models) == 0
    needs_consent = not has_consent

    # Determine recommended action
    if needs_ollama:
        action = "install_ollama"
        message = "Install Ollama to enable local AI features"
    elif not running:
        action = "start_ollama"
        message = "Start Ollama to enable local AI features"
    elif needs_consent:
        action = "grant_consent"
        message = "Review and accept local AI consent"
    elif needs_models:
        action = "download_model"
        message = "Download a model to get started"
    else:
        action = "ready"
        message = "Local AI is ready to use"

    return {
        "needs_setup": needs_ollama or needs_consent or needs_models,
        "needs_ollama_install": needs_ollama,
        "needs_ollama_start": installed and not running,
        "needs_consent": needs_consent,
        "needs_models": needs_models,
        "installed_models": models,
        "recommended_action": action,
        "message": message,
    }
