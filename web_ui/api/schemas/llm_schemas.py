"""LLM/AI-related API schemas for script generation"""

from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field


class LLMProvider(BaseModel):
    """
    LLM Provider configuration

    Supported Providers:
    - ollama: Local models via Ollama
    - openai: OpenAI GPT models
    - anthropic: Anthropic Claude models
    - azure_openai: OpenAI models on Azure
    - google: Google Gemini models
    - aws_bedrock: AWS Bedrock models
    - huggingface: HuggingFace Hub models
    - custom: Any OpenAI-compatible endpoint
    """
    type: Literal["ollama", "openai", "anthropic", "azure_openai", "google",
                  "aws_bedrock", "huggingface", "custom"]
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    model: str

    # Azure OpenAI specific
    azure_deployment: Optional[str] = None
    azure_api_version: Optional[str] = None

    # AWS Bedrock specific
    aws_region: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # HuggingFace specific
    huggingface_provider: Optional[str] = None  # "auto", "hyperbolic", "nebius", "together"


class OllamaModel(BaseModel):
    """Ollama model information"""
    name: str
    size: str
    modified_at: str
    digest: str


class OllamaModelListResponse(BaseModel):
    """Response with available Ollama models"""
    models: List[OllamaModel]
    connected: bool


class SegmentDescription(BaseModel):
    """Description of a video segment for script generation"""
    start_time: float
    end_time: float
    description: str
    keywords: Optional[List[str]] = None


# =============================================================================
# Structured Output Schemas for LLM
# =============================================================================
# These schemas are used with LangChain's structured output features to ensure
# reliable JSON generation from any LLM provider. Using these schemas:
# - OpenAI/Anthropic: Uses native with_structured_output()
# - Ollama: Uses native format parameter with JSON schema
# - Others: Falls back to tool calling or schema-in-prompt
#
# Reference: https://docs.langchain.com/docs/oss/langchain/structured-output


class LLMScriptItem(BaseModel):
    """
    Single script item from LLM structured output.

    This schema matches the expected output format for script generation
    and is used with provider.generate_structured() for reliable parsing.
    """
    segment: int = Field(
        description="The segment number (1-indexed)"
    )
    script: str = Field(
        description="The complete narration script text for this segment. "
        "Must be natural, speakable text without placeholders."
    )


class LLMScriptGenerationOutput(BaseModel):
    """
    Structured output schema for LLM script generation.

    Used with LangChain's structured output to ensure reliable JSON
    from any provider (Ollama, OpenAI, Anthropic, etc.).

    Example output:
    {
      "scripts": [
        {"segment": 1, "script": "Welcome to this tutorial..."},
        {"segment": 2, "script": "In this section, we'll explore..."}
      ]
    }
    """
    scripts: List[LLMScriptItem] = Field(
        description="List of narration scripts, one for each requested segment. "
        "Each script must match the target word count for its segment duration."
    )


class LLMAutoSegmentItem(BaseModel):
    """
    Single auto-generated segment from LLM structured output.

    Used for auto-segmentation where the LLM determines both
    timing and content for video segments.
    """
    name: str = Field(
        description="Short descriptive name for the segment (e.g., 'Introduction', 'Key Features')"
    )
    start_time: float = Field(
        description="Start time of the segment in seconds",
        ge=0.0
    )
    end_time: float = Field(
        description="End time of the segment in seconds",
        gt=0.0
    )
    description: str = Field(
        description="Brief description of what happens in this segment"
    )
    script: str = Field(
        description="Complete narration script text for this segment. "
        "Must be natural, speakable text without placeholders."
    )


class LLMAutoSegmentOutput(BaseModel):
    """
    Structured output schema for LLM auto-segment generation.

    Used when the LLM automatically creates segment boundaries
    and scripts based on video description.
    """
    segments: List[LLMAutoSegmentItem] = Field(
        description="List of video segments with timing, descriptions, and narration scripts. "
        "Segments should cover the key parts of the video without overlapping."
    )


class ExistingSegmentContext(BaseModel):
    """
    Context from an existing segment for narrative continuity.

    Used when generating new segments to provide the AI with context about
    surrounding segments, enabling better narrative flow and coherence.
    """
    name: str
    start_time: float
    end_time: float
    script: str  # The existing script text
    position: Literal["before", "after"]  # Relative to the segment being generated


class ScriptStyle(BaseModel):
    """Style configuration for script generation"""
    tone: Literal["professional", "casual", "dramatic", "humorous", "educational", "documentary"] = "documentary"
    style: Literal["narrative", "conversational", "instructional", "promotional", "storytelling"] = "narrative"
    audience: Literal["general", "technical", "children", "business", "creative"] = "general"
    length: Literal["concise", "moderate", "detailed"] = "moderate"
    language: str = "en"


class ScriptGenerationRequest(BaseModel):
    """Request to generate script using LLM"""
    provider: LLMProvider
    segments: List[SegmentDescription]
    style: ScriptStyle = Field(default_factory=ScriptStyle)
    video_title: Optional[str] = None
    video_context: Optional[str] = None
    custom_instructions: Optional[str] = None

    # Contextual awareness - existing segments for narrative continuity
    context_segments: Optional[List[ExistingSegmentContext]] = None

    # Smart fitting options
    fit_to_duration: bool = True  # Auto-adjust text length to fit segment duration
    words_per_second: float = 2.5  # Average speaking rate for duration estimation
    max_retries: int = 2  # Retry if text doesn't fit


class GeneratedScript(BaseModel):
    """Single generated script for a segment"""
    segment_index: int
    start_time: float
    end_time: float
    text: str
    estimated_duration: float
    word_count: int
    fits_duration: bool
    confidence: float  # 0-1 confidence in script quality


class ScriptGenerationResponse(BaseModel):
    """Response with generated scripts"""
    scripts: List[GeneratedScript]
    total_segments: int
    all_fit: bool
    warnings: List[str]
    provider_used: str
    model_used: str


class ScriptRefinementRequest(BaseModel):
    """Request to refine a generated script"""
    provider: LLMProvider
    original_text: str
    target_duration: float
    current_duration: float
    instruction: Literal["shorten", "lengthen", "rephrase", "simplify", "make_formal", "make_casual"]
    custom_feedback: Optional[str] = None


class ScriptRefinementResponse(BaseModel):
    """Response with refined script"""
    refined_text: str
    estimated_duration: float
    word_count: int
    fits_duration: bool


class TextDurationEstimate(BaseModel):
    """Estimate audio duration for text"""
    text: str
    language: str = "en"


class TextDurationResponse(BaseModel):
    """Response with duration estimate"""
    text: str
    word_count: int
    char_count: int
    estimated_duration: float
    words_per_second: float
    recommended_segment_duration: float


class LLMHealthCheck(BaseModel):
    """Health check for LLM providers"""
    ollama_available: bool
    ollama_models: List[str]
    openai_configured: bool
    anthropic_configured: bool
    google_configured: bool
    azure_openai_configured: bool = False
    aws_bedrock_configured: bool = False
    huggingface_configured: bool = False
    langchain_available: bool = False


class CustomPromptRequest(BaseModel):
    """Request for custom LLM prompt"""
    provider: LLMProvider
    prompt: str
    max_tokens: int = 1000
    temperature: float = 0.7


class CustomPromptResponse(BaseModel):
    """Response from custom prompt"""
    response: str
    tokens_used: int
    model: str


class AutoSegmentRequest(BaseModel):
    """Request for AI to automatically create segments from video description"""
    provider: LLMProvider
    video_duration: float  # Total video duration in seconds
    video_description: str  # User's description of the video content
    video_title: Optional[str] = None
    style: ScriptStyle = Field(default_factory=ScriptStyle)
    min_segment_duration: float = 5.0  # Minimum segment duration in seconds
    max_segment_duration: float = 30.0  # Maximum segment duration in seconds
    custom_instructions: Optional[str] = None


class AutoGeneratedSegment(BaseModel):
    """AI-generated segment with timing and script"""
    segment_index: int
    name: str
    start_time: float
    end_time: float
    description: str  # What happens in this segment
    script: str  # Narration script
    estimated_duration: float
    word_count: int
    fits_duration: bool


class AutoSegmentResponse(BaseModel):
    """Response with auto-generated segments"""
    segments: List[AutoGeneratedSegment]
    total_segments: int
    total_duration: float
    coverage_percent: float  # What percentage of video is covered
    all_fit: bool
    warnings: List[str]
    provider_used: str
    model_used: str


class IntelligentAutoSegmentRequest(BaseModel):
    """
    Request for intelligent AI script generation with advanced prompt engineering.

    This uses the new intelligent script generation pipeline that:
    1. Detects video content type automatically
    2. Optionally analyzes video content using AI vision model (qwen3-vl)
    3. Crafts optimized prompts based on video characteristics
    4. Generates scripts with precise word count for timing
    5. Validates and iteratively refines scripts that don't fit
    """
    provider: LLMProvider
    video_duration: float  # Total video duration in seconds
    video_description: str  # User's description of the video content
    video_title: Optional[str] = None
    style: Optional[ScriptStyle] = None
    min_segment_duration: float = 5.0  # Minimum segment duration in seconds
    max_segment_duration: float = 30.0  # Maximum segment duration in seconds
    custom_instructions: Optional[str] = None
    max_refinement_iterations: int = 3  # How many times to refine scripts that don't fit
    stream: bool = False  # If True, returns SSE stream with progress updates
    # Video Analysis Options (experimental - uses vision model to understand video content)
    video_path: Optional[str] = None  # Path to video file for AI vision analysis
    vision_model: Optional[str] = None  # Vision model to use (default: qwen3-vl:8b)
    use_video_analysis: bool = False  # Enable AI video analysis before script generation


class IntelligentSegmentResult(BaseModel):
    """Result for a segment from intelligent generation"""
    segment_index: int
    name: str
    start_time: float
    end_time: float
    description: str
    script: str
    estimated_duration: float
    word_count: int
    fits_duration: bool
    fit_percentage: float  # How well the script fits (100% = perfect)
    refinement_applied: bool  # Was this script refined after initial generation


class IntelligentAutoSegmentResponse(BaseModel):
    """Response from intelligent auto-segment generation"""
    success: bool
    segments: List[IntelligentSegmentResult]
    total_segments: int
    total_duration: float
    coverage_percent: float
    all_fit: bool
    warnings: List[str]
    provider_used: str
    model_used: str
    generation_time: float  # Time taken in seconds
    refinement_iterations: int  # How many refinement passes were done


class GenerationProgressUpdate(BaseModel):
    """Real-time progress update for SSE streaming"""
    type: Literal["progress", "complete", "error", "heartbeat"]
    stage: Optional[str] = None  # Current pipeline stage
    message: Optional[str] = None
    progress: Optional[int] = None  # 0-100
    detail: Optional[str] = None
    segment_count: Optional[int] = None
    segments_validated: Optional[int] = None
    segments_refined: Optional[int] = None
    current_refinement_attempt: Optional[int] = None
    max_refinement_attempts: Optional[int] = None
    timestamp: Optional[str] = None
