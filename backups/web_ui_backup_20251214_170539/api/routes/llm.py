"""LLM/AI API routes for script generation"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from web_ui.api.schemas.llm_schemas import (
    LLMProvider,
    OllamaModelListResponse,
    SegmentDescription,
    ScriptStyle,
    ScriptGenerationRequest,
    ScriptGenerationResponse,
    ScriptRefinementRequest,
    ScriptRefinementResponse,
    TextDurationEstimate,
    TextDurationResponse,
    LLMHealthCheck,
    CustomPromptRequest,
    CustomPromptResponse,
    AutoSegmentRequest,
    AutoSegmentResponse,
    IntelligentAutoSegmentRequest,
)
from web_ui.api.services.llm_service import llm_service, OllamaProvider
from web_ui.api.services.script_fitter import script_fitter
from web_ui.api.services.intelligent_script_generator import (
    intelligent_generator,
    GenerationProgress,
)

router = APIRouter()


@router.get("/health", response_model=LLMHealthCheck)
async def check_llm_health():
    """Check availability of LLM providers"""
    try:
        health = await llm_service.check_health()
        return LLMHealthCheck(**health)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ollama/models", response_model=OllamaModelListResponse)
async def list_ollama_models():
    """List available Ollama models"""
    try:
        provider = OllamaProvider(model="")
        is_available = await provider.is_available()

        if not is_available:
            return OllamaModelListResponse(models=[], connected=False)

        models = await provider.list_models()
        return OllamaModelListResponse(models=models, connected=True)

    except Exception as e:
        return OllamaModelListResponse(models=[], connected=False)


@router.get("/ollama/vision-models")
async def check_vision_models():
    """
    Check availability of vision models for video analysis.
    Returns list of available vision models and installation instructions if none found.
    """
    try:
        provider = OllamaProvider(model="")
        is_available = await provider.is_available()

        if not is_available:
            return {
                "available": False,
                "connected": False,
                "vision_models": [],
                "recommended_model": "qwen3-vl:8b",
                "install_command": "ollama pull qwen3-vl:8b",
                "message": "Ollama is not running. Start with: ollama serve"
            }

        models = await provider.list_models()

        # Filter for vision-capable models
        vision_model_patterns = ['qwen3-vl', 'qwen2.5-vl', 'llava', 'bakllava', 'moondream']
        vision_models = [
            m for m in models
            if any(pattern in m.name.lower() for pattern in vision_model_patterns)
        ]

        if vision_models:
            return {
                "available": True,
                "connected": True,
                "vision_models": [{"name": m.name, "size": m.size} for m in vision_models],
                "recommended_model": vision_models[0].name,
                "install_command": None,
                "message": f"Found {len(vision_models)} vision model(s)"
            }
        else:
            return {
                "available": False,
                "connected": True,
                "vision_models": [],
                "recommended_model": "qwen3-vl:8b",
                "install_command": "ollama pull qwen3-vl:8b",
                "message": "No vision models found. Install one to enable video analysis."
            }

    except Exception as e:
        return {
            "available": False,
            "connected": False,
            "vision_models": [],
            "recommended_model": "qwen3-vl:8b",
            "install_command": "ollama pull qwen3-vl:8b",
            "message": f"Error checking models: {str(e)}"
        }


@router.post("/analyze-video")
async def analyze_video(
    video_path: str,
    vision_model: str = "qwen3-vl:8b",
    num_frames: int = 4
):
    """
    Analyze a video using AI vision model.
    Extracts frames and sends to vision model for content understanding.
    """
    try:
        provider = OllamaProvider(model=vision_model)

        if not await provider.is_available():
            raise HTTPException(
                status_code=503,
                detail="Ollama is not running. Please start Ollama and try again."
            )

        # Check if the video file exists
        from pathlib import Path
        if not Path(video_path).exists():
            raise HTTPException(
                status_code=404,
                detail=f"Video file not found: {video_path}"
            )

        result = await provider.analyze_video(
            video_path=video_path,
            num_frames=num_frames,
            vision_model=vision_model
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-script", response_model=ScriptGenerationResponse)
async def generate_script(request: ScriptGenerationRequest):
    """Generate narration scripts for video segments using AI"""
    try:
        # Validate provider configuration
        if request.provider.type == "ollama":
            provider = OllamaProvider(model=request.provider.model)
            if not await provider.is_available():
                raise HTTPException(
                    status_code=503,
                    detail="Ollama is not running. Please start Ollama and try again."
                )

        elif request.provider.type in ["openai", "anthropic", "google"]:
            if not request.provider.api_key:
                raise HTTPException(
                    status_code=400,
                    detail=f"API key required for {request.provider.type}"
                )

        elif request.provider.type == "custom":
            if not request.provider.endpoint:
                raise HTTPException(
                    status_code=400,
                    detail="Endpoint URL required for custom provider"
                )

        # Generate scripts
        scripts, warnings = await llm_service.generate_scripts(
            provider_config=request.provider,
            segments=request.segments,
            style=request.style,
            video_title=request.video_title,
            video_context=request.video_context,
            custom_instructions=request.custom_instructions,
            fit_to_duration=request.fit_to_duration,
            max_retries=request.max_retries
        )

        all_fit = all(s.fits_duration for s in scripts)

        return ScriptGenerationResponse(
            scripts=scripts,
            total_segments=len(scripts),
            all_fit=all_fit,
            warnings=warnings,
            provider_used=request.provider.type,
            model_used=request.provider.model
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refine-script", response_model=ScriptRefinementResponse)
async def refine_script(request: ScriptRefinementRequest):
    """Refine a generated script based on feedback"""
    try:
        refined_text, estimated_duration = await llm_service.refine_script(
            provider_config=request.provider,
            original_text=request.original_text,
            target_duration=request.target_duration,
            current_duration=request.current_duration,
            instruction=request.instruction,
            custom_feedback=request.custom_feedback
        )

        fits = estimated_duration <= request.target_duration * 1.1

        return ScriptRefinementResponse(
            refined_text=refined_text,
            estimated_duration=estimated_duration,
            word_count=len(refined_text.split()),
            fits_duration=fits
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/estimate-duration", response_model=TextDurationResponse)
async def estimate_text_duration(request: TextDurationEstimate):
    """Estimate audio duration for text"""
    duration = script_fitter.estimate_duration(request.text)
    word_count = len(request.text.split())
    wps = script_fitter.rates.get("normal", 2.5)

    return TextDurationResponse(
        text=request.text,
        word_count=word_count,
        char_count=len(request.text),
        estimated_duration=duration,
        words_per_second=wps,
        recommended_segment_duration=duration + 0.5  # Add padding
    )


@router.post("/custom-prompt", response_model=CustomPromptResponse)
async def custom_prompt(request: CustomPromptRequest):
    """Send a custom prompt to an LLM"""
    try:
        provider = llm_service.get_provider(request.provider)

        if not await provider.is_available():
            raise HTTPException(
                status_code=503,
                detail=f"Provider {request.provider.type} is not available"
            )

        response = await provider.generate(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )

        return CustomPromptResponse(
            response=response,
            tokens_used=len(response.split()),  # Approximate
            model=request.provider.model
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers")
async def get_available_providers():
    """Get list of available LLM providers with status"""
    health = await llm_service.check_health()

    providers = [
        {
            "type": "ollama",
            "name": "Ollama (Local)",
            "available": health["ollama_available"],
            "models": health["ollama_models"],
            "requires_api_key": False,
            "description": "Run AI models locally on your machine"
        },
        {
            "type": "openai",
            "name": "OpenAI",
            "available": True,  # Always available if API key provided
            "models": ["gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
            "requires_api_key": True,
            "description": "GPT-4 and GPT-3.5 models from OpenAI"
        },
        {
            "type": "anthropic",
            "name": "Anthropic",
            "available": True,
            "models": ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
            "requires_api_key": True,
            "description": "Claude models from Anthropic"
        },
        {
            "type": "google",
            "name": "Google Gemini",
            "available": True,
            "models": ["gemini-pro", "gemini-pro-vision"],
            "requires_api_key": True,
            "description": "Gemini models from Google"
        },
        {
            "type": "custom",
            "name": "Custom Endpoint",
            "available": True,
            "models": [],
            "requires_api_key": False,
            "description": "Use your own OpenAI-compatible API endpoint"
        }
    ]

    return {"providers": providers}


@router.get("/prompt-templates")
async def get_prompt_templates():
    """Get available prompt templates for different script styles"""
    templates = [
        {
            "id": "documentary",
            "name": "Documentary",
            "description": "Professional, informative narration",
            "style": {
                "tone": "documentary",
                "style": "narrative",
                "audience": "general"
            }
        },
        {
            "id": "educational",
            "name": "Educational",
            "description": "Clear, instructional content",
            "style": {
                "tone": "educational",
                "style": "instructional",
                "audience": "general"
            }
        },
        {
            "id": "promotional",
            "name": "Promotional",
            "description": "Engaging, persuasive content",
            "style": {
                "tone": "professional",
                "style": "promotional",
                "audience": "business"
            }
        },
        {
            "id": "storytelling",
            "name": "Storytelling",
            "description": "Engaging narrative with emotion",
            "style": {
                "tone": "dramatic",
                "style": "storytelling",
                "audience": "general"
            }
        },
        {
            "id": "casual",
            "name": "Casual/Vlog",
            "description": "Friendly, conversational tone",
            "style": {
                "tone": "casual",
                "style": "conversational",
                "audience": "general"
            }
        },
        {
            "id": "technical",
            "name": "Technical",
            "description": "Precise, technical explanations",
            "style": {
                "tone": "professional",
                "style": "instructional",
                "audience": "technical"
            }
        }
    ]

    return {"templates": templates}


@router.post("/auto-segment", response_model=AutoSegmentResponse)
async def auto_generate_segments(request: AutoSegmentRequest):
    """
    Automatically generate segments with timing and scripts from video description.

    This endpoint uses AI to analyze the video description and create optimal
    segment breakdowns with narration scripts that fit within each segment's duration.
    """
    try:
        # Validate provider configuration
        if request.provider.type == "ollama":
            provider = OllamaProvider(model=request.provider.model)
            if not await provider.is_available():
                raise HTTPException(
                    status_code=503,
                    detail="Ollama is not running. Please start Ollama and try again."
                )

        elif request.provider.type in ["openai", "anthropic", "google"]:
            if not request.provider.api_key:
                raise HTTPException(
                    status_code=400,
                    detail=f"API key required for {request.provider.type}"
                )

        elif request.provider.type == "custom":
            if not request.provider.endpoint:
                raise HTTPException(
                    status_code=400,
                    detail="Endpoint URL required for custom provider"
                )

        # Validate duration constraints
        if request.min_segment_duration > request.max_segment_duration:
            raise HTTPException(
                status_code=400,
                detail="Minimum segment duration cannot exceed maximum duration"
            )

        if request.video_duration < request.min_segment_duration:
            raise HTTPException(
                status_code=400,
                detail="Video duration is shorter than minimum segment duration"
            )

        # Generate segments
        segments, warnings = await llm_service.auto_generate_segments(
            provider_config=request.provider,
            video_duration=request.video_duration,
            video_description=request.video_description,
            style=request.style,
            video_title=request.video_title,
            min_segment_duration=request.min_segment_duration,
            max_segment_duration=request.max_segment_duration,
            custom_instructions=request.custom_instructions
        )

        # Calculate coverage
        total_covered = sum(s.end_time - s.start_time for s in segments)
        coverage_percent = (total_covered / request.video_duration) * 100 if request.video_duration > 0 else 0
        all_fit = all(s.fits_duration for s in segments)

        return AutoSegmentResponse(
            segments=segments,
            total_segments=len(segments),
            total_duration=total_covered,
            coverage_percent=min(coverage_percent, 100),
            all_fit=all_fit,
            warnings=warnings,
            provider_used=request.provider.type,
            model_used=request.provider.model
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intelligent-auto-segment")
async def intelligent_auto_segment(request: IntelligentAutoSegmentRequest):
    """
    Intelligently generate segments with scripts using advanced prompt engineering
    and iterative refinement.

    This endpoint uses the new intelligent script generation pipeline that:
    1. Analyzes video context to detect content type
    2. Crafts optimized prompts based on video characteristics
    3. Generates scripts with precise timing constraints
    4. Validates and refines scripts iteratively
    5. Returns production-ready segments

    Returns SSE stream with progress updates if stream=True, otherwise JSON response.
    """
    try:
        # Validate provider
        if request.provider.type == "ollama":
            provider = OllamaProvider(model=request.provider.model)
            if not await provider.is_available():
                raise HTTPException(
                    status_code=503,
                    detail="Ollama is not running. Please start Ollama and try again."
                )
        elif request.provider.type in ["openai", "anthropic", "google"]:
            if not request.provider.api_key:
                raise HTTPException(
                    status_code=400,
                    detail=f"API key required for {request.provider.type}"
                )
        elif request.provider.type == "custom":
            if not request.provider.endpoint:
                raise HTTPException(
                    status_code=400,
                    detail="Endpoint URL required for custom provider"
                )

        # Validate constraints
        if request.min_segment_duration > request.max_segment_duration:
            raise HTTPException(
                status_code=400,
                detail="Minimum segment duration cannot exceed maximum duration"
            )

        if request.video_duration < request.min_segment_duration:
            raise HTTPException(
                status_code=400,
                detail="Video duration is shorter than minimum segment duration"
            )

        # Build style config
        style_config = {
            "tone": request.style.tone if request.style else "documentary",
            "style": request.style.style if request.style else "narrative",
            "audience": request.style.audience if request.style else "general",
            "language": request.style.language if request.style else "en",
        }

        if request.stream:
            # SSE streaming response
            return StreamingResponse(
                _stream_intelligent_generation(
                    provider_config=request.provider,
                    video_duration=request.video_duration,
                    video_description=request.video_description,
                    video_title=request.video_title,
                    style_config=style_config,
                    min_segment_duration=request.min_segment_duration,
                    max_segment_duration=request.max_segment_duration,
                    custom_instructions=request.custom_instructions,
                    max_refinement_iterations=request.max_refinement_iterations,
                    # Video analysis options
                    video_path=request.video_path,
                    vision_model=request.vision_model,
                    use_video_analysis=request.use_video_analysis,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            # Standard JSON response
            result = await intelligent_generator.generate_auto_segments(
                provider_config=request.provider,
                video_duration=request.video_duration,
                video_description=request.video_description,
                video_title=request.video_title,
                style_config=style_config,
                min_segment_duration=request.min_segment_duration,
                max_segment_duration=request.max_segment_duration,
                custom_instructions=request.custom_instructions,
                max_refinement_iterations=request.max_refinement_iterations,
                # Video analysis options
                video_path=request.video_path,
                vision_model=request.vision_model,
                use_video_analysis=request.use_video_analysis,
            )

            # Convert to response format
            segments = [
                {
                    "segment_index": s.index,
                    "name": s.name,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "description": s.description,
                    "script": s.script,
                    "estimated_duration": s.estimated_duration,
                    "word_count": s.word_count,
                    "fits_duration": s.fits_duration,
                    "fit_percentage": s.fit_percentage,
                    "refinement_applied": s.refinement_applied,
                }
                for s in result.segments
            ]

            return {
                "success": result.success,
                "segments": segments,
                "total_segments": result.total_segments,
                "total_duration": result.total_duration,
                "coverage_percent": result.overall_coverage,
                "all_fit": result.all_fit,
                "warnings": result.warnings,
                "provider_used": result.provider_used,
                "model_used": result.model_used,
                "generation_time": result.generation_time,
                "refinement_iterations": result.refinement_iterations,
            }

    except HTTPException:
        raise
    except Exception as e:
        error_detail = str(e) if str(e) else f"{type(e).__name__}: Unknown error occurred"
        logger.error(f"Intelligent auto-segment failed: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


async def _stream_intelligent_generation(
    provider_config,
    video_duration: float,
    video_description: str,
    video_title: Optional[str],
    style_config: dict,
    min_segment_duration: float,
    max_segment_duration: float,
    custom_instructions: Optional[str],
    max_refinement_iterations: int,
    # Video analysis options
    video_path: Optional[str] = None,
    vision_model: Optional[str] = None,
    use_video_analysis: bool = False,
):
    """Stream progress updates during intelligent generation"""
    progress_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()  # Use get_running_loop() instead of deprecated get_event_loop()

    def progress_callback(progress: GenerationProgress):
        # Thread-safe queue put using the running loop
        loop.call_soon_threadsafe(
            progress_queue.put_nowait,
            progress
        )

    # Start generation in background task
    async def run_generation():
        try:
            result = await intelligent_generator.generate_auto_segments(
                provider_config=provider_config,
                video_duration=video_duration,
                video_description=video_description,
                video_title=video_title,
                style_config=style_config,
                min_segment_duration=min_segment_duration,
                max_segment_duration=max_segment_duration,
                custom_instructions=custom_instructions,
                max_refinement_iterations=max_refinement_iterations,
                progress_callback=progress_callback,
                # Video analysis options
                video_path=video_path,
                vision_model=vision_model,
                use_video_analysis=use_video_analysis,
            )
            # Signal completion with result
            await progress_queue.put(("complete", result))
        except Exception as e:
            await progress_queue.put(("error", str(e)))

    # Start the task
    task = asyncio.create_task(run_generation())

    try:
        heartbeat_count = 0
        max_heartbeats = 60  # Maximum 60 heartbeats (10 minutes total with 10s interval)

        while True:
            try:
                # Use shorter timeout (10s) for more responsive heartbeats
                item = await asyncio.wait_for(progress_queue.get(), timeout=10.0)

                # Reset heartbeat count on any real message
                heartbeat_count = 0

                if isinstance(item, tuple):
                    event_type, data = item

                    if event_type == "complete":
                        # Send final result
                        result = data
                        segments = [
                            {
                                "segment_index": s.index,
                                "name": s.name,
                                "start_time": s.start_time,
                                "end_time": s.end_time,
                                "description": s.description,
                                "script": s.script,
                                "estimated_duration": s.estimated_duration,
                                "word_count": s.word_count,
                                "fits_duration": s.fits_duration,
                                "fit_percentage": s.fit_percentage,
                                "refinement_applied": s.refinement_applied,
                            }
                            for s in result.segments
                        ]
                        final_data = {
                            "type": "complete",
                            "success": result.success,
                            "segments": segments,
                            "total_segments": result.total_segments,
                            "total_duration": result.total_duration,
                            "coverage_percent": result.overall_coverage,
                            "all_fit": result.all_fit,
                            "warnings": result.warnings,
                            "provider_used": result.provider_used,
                            "model_used": result.model_used,
                            "generation_time": result.generation_time,
                            "refinement_iterations": result.refinement_iterations,
                        }
                        yield f"data: {json.dumps(final_data)}\n\n"
                        break

                    elif event_type == "error":
                        error_data = {
                            "type": "error",
                            "message": data,
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                        break

                elif isinstance(item, GenerationProgress):
                    # Send progress update
                    progress_data = {
                        "type": "progress",
                        "stage": item.stage.value,
                        "message": item.message,
                        "progress": item.progress,
                        "detail": item.detail,
                        "segment_count": item.segment_count,
                        "segments_validated": item.segments_validated,
                        "segments_refined": item.segments_refined,
                        "current_refinement_attempt": item.current_refinement_attempt,
                        "max_refinement_attempts": item.max_refinement_attempts,
                        "timestamp": item.timestamp,
                    }
                    yield f"data: {json.dumps(progress_data)}\n\n"

            except asyncio.TimeoutError:
                heartbeat_count += 1

                # Check if task is still running
                if task.done():
                    # Task finished but we didn't get a message - check for exception
                    try:
                        task.result()  # This will raise if task had an exception
                    except Exception as e:
                        error_data = {"type": "error", "message": str(e)}
                        yield f"data: {json.dumps(error_data)}\n\n"
                    break

                # Send heartbeat to keep connection alive
                yield f"data: {json.dumps({'type': 'heartbeat', 'count': heartbeat_count})}\n\n"

                # Check if we've exceeded max heartbeats (prevent infinite waiting)
                if heartbeat_count >= max_heartbeats:
                    error_data = {"type": "error", "message": "Generation timed out after 10 minutes"}
                    yield f"data: {json.dumps(error_data)}\n\n"
                    break

    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
