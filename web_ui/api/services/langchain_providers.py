"""
LangChain Providers - Unified LLM interface using LangChain
============================================================

Supports multiple AI providers through LangChain's unified interface:
- Ollama (local, free)
- OpenAI (GPT-4, GPT-4o, GPT-3.5)
- Anthropic (Claude 3, Claude 3.5)
- Azure OpenAI (GPT models on Azure)
- Google Gemini (Gemini Pro, Gemini Flash)
- AWS Bedrock (Claude, Llama, Titan, etc.)
- HuggingFace (Various open-source models)
- Custom OpenAI-compatible endpoints

Each provider implements a common interface for:
- Text generation
- Chat-based generation
- Structured output (JSON schema)
- Availability checking
- Model listing (where applicable)

Reference Documentation:
- LangChain: https://python.langchain.com/docs/
- Provider-specific docs are in /documentation/langchain/
"""

import os
import asyncio
import base64
import json
import re
import socket
import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Tuple, Any, Type, Literal
from urllib.parse import urlparse
import ipaddress
from pydantic import BaseModel
from enum import Enum

import httpx

# Import logger
from utils.logger import logger


# =============================================================================
# SSRF Protection - URL Validation
# =============================================================================

# Allowed URL schemes for custom endpoints
ALLOWED_SCHEMES = {"http", "https"}

# Known internal/private IP ranges to block
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),       # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),    # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),   # Private Class C
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local (AWS metadata, etc.)
    ipaddress.ip_network("100.64.0.0/10"),    # Carrier-grade NAT
    ipaddress.ip_network("0.0.0.0/8"),        # "This" network
    ipaddress.ip_network("224.0.0.0/4"),      # Multicast
    ipaddress.ip_network("240.0.0.0/4"),      # Reserved
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
    ipaddress.ip_network("::ffff:0:0/96"),    # IPv4-mapped IPv6
]

# Blocked hostnames (case-insensitive)
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",      # GCP metadata
    "metadata",                       # Generic cloud metadata
}

# Cloud provider metadata endpoints - always blocked
CLOUD_METADATA_IPS = {
    "169.254.169.254",  # AWS, GCP, Azure metadata
    "169.254.170.2",    # AWS ECS metadata
    "fd00:ec2::254",    # AWS IPv6 metadata
}


def validate_endpoint_url(url: str, allow_localhost: bool = False) -> Tuple[bool, str]:
    """
    Validate a URL to prevent SSRF attacks.

    Args:
        url: The URL to validate
        allow_localhost: If True, allow localhost (for development only)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL is required"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"

    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"Invalid URL scheme: {parsed.scheme}. Only http and https are allowed."

    # Get hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    # Check blocked hostnames
    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES and not allow_localhost:
        return False, f"Blocked hostname: {hostname}"

    # Try to resolve hostname to IP
    try:
        # Get all IP addresses for the hostname
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ip_addresses = set()

        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip_addresses.add(ip_str)

    except socket.gaierror as e:
        # Hostname resolution failed - could be a valid external hostname
        # that we just can't resolve right now, or an internal hostname
        # For security, block unresolvable hostnames
        return False, f"Cannot resolve hostname: {hostname}"

    # Check each resolved IP against blocked ranges
    for ip_str in ip_addresses:
        # Check cloud metadata IPs explicitly
        if ip_str in CLOUD_METADATA_IPS and not allow_localhost:
            return False, f"Cloud metadata endpoint blocked: {ip_str}"

        try:
            ip = ipaddress.ip_address(ip_str)

            for blocked_range in BLOCKED_IP_RANGES:
                if ip in blocked_range:
                    if allow_localhost and (ip.is_loopback or str(ip).startswith("127.")):
                        continue  # Allow localhost in dev mode
                    return False, f"IP address {ip_str} is in blocked range: {blocked_range}"

        except ValueError:
            return False, f"Invalid IP address: {ip_str}"

    # Check for suspicious port (very high or very low)
    port = parsed.port
    if port is not None:
        if port < 1 or port > 65535:
            return False, f"Invalid port: {port}"
        # Block ports commonly used by internal services
        blocked_ports = {22, 23, 25, 53, 111, 135, 137, 138, 139, 445, 514, 873}
        if port in blocked_ports:
            return False, f"Blocked port: {port} (commonly used by internal services)"

    return True, ""


def is_development_mode() -> bool:
    """Check if running in development mode."""
    env = os.getenv("ENVIRONMENT", "").lower()
    debug = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
    return env in ("development", "dev", "local") or debug


# =============================================================================
# Provider Type Enum and Configuration
# =============================================================================

class ProviderType(str, Enum):
    """Supported LLM provider types"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    GOOGLE = "google"
    AWS_BEDROCK = "aws_bedrock"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider"""
    type: Literal["ollama", "openai", "anthropic", "azure_openai", "google",
                  "aws_bedrock", "huggingface", "custom"]
    model: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None

    # Azure OpenAI specific
    azure_deployment: Optional[str] = None
    azure_api_version: Optional[str] = None

    # AWS Bedrock specific
    aws_region: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None

    # HuggingFace specific
    huggingface_provider: Optional[str] = None  # "auto", "hyperbolic", "nebius", "together"

    # Additional options
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None


# =============================================================================
# Base Provider Abstract Class
# =============================================================================

class BaseLangChainProvider(ABC):
    """
    Base class for all LangChain-based providers.

    Provides a unified interface for text generation, chat, and structured output
    across all supported LLM providers.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.model = config.model
        self._chat_model = None
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the LangChain model. Call before first use."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text from a prompt."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Generate response from a list of chat messages."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available and properly configured."""
        pass

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> BaseModel:
        """
        Generate structured output conforming to a Pydantic schema.

        Default implementation uses JSON mode with schema validation.
        Providers may override for native structured output support.
        """
        # Build a prompt that requests JSON output
        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
        structured_prompt = f"""{prompt}

You MUST respond with valid JSON that matches this schema:
{schema_json}

Respond with ONLY the JSON object, no other text."""

        response = await self.generate(
            prompt=structured_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system
        )

        # Parse and validate the response
        try:
            # Clean the response
            cleaned = self._clean_json_response(response)
            return response_schema.model_validate_json(cleaned)
        except Exception as e:
            logger.error(f"Failed to parse structured output: {e}")
            logger.debug(f"Response was: {response[:500]}")
            raise ValueError(f"Failed to parse LLM response as {response_schema.__name__}: {e}")

    def _clean_json_response(self, response: str) -> str:
        """Clean JSON from LLM response, removing thinking tags and markdown."""
        # Remove thinking tags
        cleaned = re.sub(r'<think>[\s\S]*?</think>', '', response, flags=re.IGNORECASE)
        cleaned = re.sub(r'<\|.*?\|>', '', cleaned)

        # Remove markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned)
        if json_match:
            cleaned = json_match.group(1)

        # Try to find JSON object or array
        json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
        if json_match:
            cleaned = json_match.group(1)

        return cleaned.strip()


# =============================================================================
# Ollama Provider
# =============================================================================

class OllamaLangChainProvider(BaseLangChainProvider):
    """
    Ollama provider using LangChain's ChatOllama.

    Supports:
    - Local model execution
    - Structured outputs via format parameter
    - Vision models for video analysis
    - Thinking mode for reasoning models (via httpx fallback for reliable output)

    Environment Variables:
    - OLLAMA_HOST: Ollama server URL (default: http://localhost:11434)
    """

    DEFAULT_ENDPOINT = "http://localhost:11434"
    THINKING_MODELS = ['qwen3', 'deepseek-r1', 'qwq']

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.endpoint = config.endpoint or os.getenv("OLLAMA_HOST", self.DEFAULT_ENDPOINT)
        self._supports_thinking = any(m in self.model.lower() for m in self.THINKING_MODELS)

    async def initialize(self) -> None:
        """Initialize the Ollama ChatModel."""
        if self._initialized:
            return

        try:
            from langchain_ollama import ChatOllama

            self._chat_model = ChatOllama(
                model=self.model,
                base_url=self.endpoint,
                temperature=self.config.temperature or 0.7,
                num_predict=self.config.max_tokens or 1000,
            )
            self._initialized = True
            logger.info(f"[Ollama] Initialized with model: {self.model} at {self.endpoint} (thinking model: {self._supports_thinking})")

        except ImportError:
            logger.error("[Ollama] langchain-ollama not installed. Run: pip install langchain-ollama")
            raise RuntimeError("langchain-ollama package not installed")
        except Exception as e:
            logger.error(f"[Ollama] Failed to initialize: {e}")
            raise

    async def _generate_via_httpx(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system: Optional[str] = None
    ) -> str:
        """
        Direct generation using httpx - used for thinking models where
        LangChain may not properly extract content.
        """
        timeout = httpx.Timeout(300.0, connect=10.0)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # For thinking models, use higher token count to allow for thinking + answer
        effective_tokens = max_tokens
        if self._supports_thinking:
            effective_tokens = max(max_tokens * 3, 1000)  # Triple for thinking overhead

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": effective_tokens,
            }
        }

        # For thinking models, disable thinking to get direct response
        if self._supports_thinking:
            payload["think"] = False

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.endpoint}/api/chat",
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            content = data.get("message", {}).get("content", "")

            # Clean thinking tags if still present
            content = self._clean_thinking_tags(content)
            return content

    def _clean_thinking_tags(self, text: str) -> str:
        """
        Clean thinking tags from model output.

        For thinking models like qwen3, the response may be:
        1. All content inside <think>...</think> followed by answer
        2. Only <think>...</think> content (incomplete response)
        3. No thinking tags at all

        We need to handle all cases and extract useful content.
        """
        if not text:
            return ""

        # First, check if there's content AFTER the </think> tag - that's the actual answer
        after_think_match = re.search(r'</think>\s*([\s\S]+)$', text, flags=re.IGNORECASE)
        if after_think_match:
            answer = after_think_match.group(1).strip()
            if answer and len(answer) > 3:  # Has meaningful content after thinking
                return self._clean_special_tokens(answer)

        # If the response is just <think>content without closing tag (truncated),
        # or <think>content</think> with no answer after, extract content from thinking
        think_content_match = re.search(r'<think>\s*([\s\S]*?)(?:</think>|$)', text, flags=re.IGNORECASE)
        if think_content_match:
            thinking_content = think_content_match.group(1).strip()
            # Try to extract useful answer from thinking
            # Often the model states the answer clearly in its thinking
            # Look for patterns like "equals X", "is X", "answer is X", "= X"
            answer_patterns = [
                r'(?:answer|result|equals?)\s*(?:is|:)?\s*["\']?([^\n.,]+)',
                r'(\d+)\s*(?:is the answer|is correct)',
                r'=\s*(\d+)',
            ]
            for pattern in answer_patterns:
                match = re.search(pattern, thinking_content, re.IGNORECASE)
                if match:
                    extracted = match.group(1).strip().strip('"\'')
                    if extracted and len(extracted) < 100:  # Reasonable answer length
                        return self._clean_special_tokens(extracted)

            # If no pattern matched, return the thinking content cleaned up
            # Remove meta-commentary that's clearly not the answer
            meta_patterns = [
                r"(?:Okay|OK|Alright),?\s*(let's|let me|I'll|I will|I should)\s+[^.]*\.\s*",
                r"(?:First|Starting|Hmm|Well),?\s+[^.]*\.\s*",
                r"The user\s+(?:asked|wants|is asking)[^.]*\.\s*",
            ]
            for pattern in meta_patterns:
                thinking_content = re.sub(pattern, '', thinking_content, flags=re.IGNORECASE)

            return self._clean_special_tokens(thinking_content.strip())

        # No thinking tags - just clean special tokens
        return self._clean_special_tokens(text)

    def _clean_special_tokens(self, text: str) -> str:
        """Remove special tokens and clean up text."""
        if not text:
            return ""
        # Remove special tokens like <|...|>
        cleaned = re.sub(r'<\|.*?\|>', '', text)
        return cleaned.strip()

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text using Ollama."""
        await self.initialize()

        logger.info(f"[Ollama] Generating with model {self.model}, {len(prompt)} char prompt")

        # Check if model exists first
        try:
            available_models = await self.list_models()
            model_names = [m.get('name', '').split(':')[0] for m in available_models]
            base_model = self.model.split(':')[0]
            if base_model not in model_names and self.model not in [m.get('name') for m in available_models]:
                logger.warning(f"[Ollama] Model '{self.model}' may not be installed. Available: {', '.join(m.get('name', '') for m in available_models[:5])}...")
        except Exception as e:
            logger.debug(f"[Ollama] Could not check model availability: {e}")

        # For thinking models, use httpx directly for more reliable output
        if self._supports_thinking:
            try:
                result = await self._generate_via_httpx(prompt, max_tokens, temperature, system)
                logger.info(f"[Ollama] Generation complete (httpx): {len(result)} chars")
                return result
            except Exception as e:
                logger.warning(f"[Ollama] httpx fallback failed, trying LangChain: {e}")

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            # Update model parameters for this call
            self._chat_model.temperature = temperature
            self._chat_model.num_predict = max_tokens

            # Use ainvoke for async operation
            response = await self._chat_model.ainvoke(messages)
            result = response.content

            # Clean thinking tags if present
            result = self._clean_thinking_tags(result)

            if not result or not result.strip():
                logger.warning(f"[Ollama] Model '{self.model}' returned empty response")
                logger.warning("[Ollama] This usually means the model is too small or doesn't understand the prompt")

            logger.info(f"[Ollama] Generation complete: {len(result)} chars")
            return result

        except Exception as e:
            error_msg = f"Ollama generation failed: {type(e).__name__}: {str(e)}"
            logger.error(f"[Ollama] {error_msg}")
            raise RuntimeError(error_msg)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Chat-based generation."""
        await self.initialize()

        # For thinking models, use httpx directly
        if self._supports_thinking:
            try:
                # Build prompt from messages for httpx fallback
                system = None
                user_content = ""
                for msg in messages:
                    if msg.get("role") == "system":
                        system = msg.get("content", "")
                    elif msg.get("role") == "user":
                        user_content = msg.get("content", "")

                result = await self._generate_via_httpx(user_content, max_tokens, temperature, system)
                return result
            except Exception as e:
                logger.warning(f"[Ollama] httpx chat fallback failed: {e}")

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            self._chat_model.temperature = temperature
            self._chat_model.num_predict = max_tokens

            response = await self._chat_model.ainvoke(lc_messages)
            result = self._clean_thinking_tags(response.content)
            return result

        except Exception as e:
            logger.error(f"[Ollama] Chat error: {e}")
            raise

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> BaseModel:
        """
        Generate structured output using Ollama's native format parameter.

        This is more reliable than text-based JSON extraction.
        """
        try:
            from langchain_ollama import ChatOllama
            from langchain_core.messages import HumanMessage, SystemMessage

            # Create a new model instance with format parameter
            structured_model = ChatOllama(
                model=self.model,
                base_url=self.endpoint,
                temperature=temperature,
                num_predict=max_tokens,
                format=response_schema.model_json_schema(),  # Native structured output
            )

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            logger.info(f"[Ollama] Structured generation with schema: {response_schema.__name__}")

            response = await structured_model.ainvoke(messages)
            content = response.content

            # Parse and validate
            result = response_schema.model_validate_json(content)
            logger.info(f"[Ollama] Structured output parsed successfully")
            return result

        except Exception as e:
            logger.error(f"[Ollama] Structured generation failed: {e}")
            # Fallback to base implementation
            return await super().generate_structured(
                prompt, response_schema, max_tokens, temperature, system
            )

    async def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.endpoint}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[Dict[str, str]]:
        """List available Ollama models."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.endpoint}/api/tags")
                response.raise_for_status()
                data = response.json()

                models = []
                for model in data.get("models", []):
                    size_bytes = model.get("size", 0)
                    size_str = self._format_size(size_bytes)

                    models.append({
                        "name": model.get("name", "unknown"),
                        "size": size_str,
                        "modified_at": model.get("modified_at", ""),
                        "digest": model.get("digest", "")[:12]
                    })
                return models
        except Exception as e:
            logger.error(f"[Ollama] Failed to list models: {e}")
            return []

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    # =========================================================================
    # Video Analysis Methods
    # =========================================================================

    async def extract_video_frames(
        self,
        video_path: str,
        num_frames: int = 4,
        max_dimension: int = 1280
    ) -> Tuple[List[str], float]:
        """Extract key frames from a video for analysis."""
        # Get video duration using ffprobe
        probe_cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        probe_data = json.loads(result.stdout)
        duration = float(probe_data['format']['duration'])

        # Calculate frame extraction timestamps
        interval = duration / (num_frames + 1)
        frames_base64 = []

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(num_frames):
                timestamp = interval * (i + 1)
                frame_path = os.path.join(tmpdir, f"frame_{i}.jpg")

                # Extract frame using ffmpeg
                cmd = [
                    'ffmpeg', '-y', '-ss', str(timestamp), '-i', video_path,
                    '-vframes', '1',
                    '-vf', f'scale=min({max_dimension}\\,iw):min({max_dimension}\\,ih):force_original_aspect_ratio=decrease',
                    '-q:v', '2', frame_path
                ]
                subprocess.run(cmd, capture_output=True)

                if os.path.exists(frame_path):
                    with open(frame_path, 'rb') as f:
                        frame_base64 = base64.b64encode(f.read()).decode('utf-8')
                        frames_base64.append(frame_base64)

        logger.info(f"[Ollama] Extracted {len(frames_base64)} frames from {duration:.2f}s video")
        return frames_base64, duration

    async def analyze_video(
        self,
        video_path: str,
        prompt: Optional[str] = None,
        num_frames: int = 4,
        vision_model: str = "qwen3-vl:8b"
    ) -> Dict[str, Any]:
        """Analyze a video using a vision-language model."""
        result = {
            "description": "",
            "duration": 0.0,
            "frames_analyzed": 0,
            "success": False,
            "error": None
        }

        try:
            frames_base64, duration = await self.extract_video_frames(video_path, num_frames)
            result["duration"] = duration
            result["frames_analyzed"] = len(frames_base64)

            if not frames_base64:
                result["error"] = "Failed to extract frames from video"
                return result

            if prompt is None:
                prompt = f"""Analyze these {len(frames_base64)} frames extracted from a video and provide:
1. A detailed description of what the video shows
2. The main subject or topic
3. Key visual elements, text, or objects visible
4. The overall mood or style of the video
5. Any actions or movements occurring

Provide a comprehensive description that would help understand this video without watching it."""

            # Use httpx for vision API call (LangChain vision support varies by version)
            payload = {
                "model": vision_model,
                "messages": [{
                    "role": "user",
                    "content": prompt,
                    "images": frames_base64
                }],
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 2000,
                }
            }

            timeout = httpx.Timeout(180.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.info(f"[Ollama] Sending {len(frames_base64)} frames to {vision_model}")

                response = await client.post(
                    f"{self.endpoint}/api/chat",
                    json=payload
                )
                response.raise_for_status()

                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "") or message.get("thinking", "")

                if content:
                    result["description"] = self._clean_video_description(content)
                    result["success"] = True
                    logger.info(f"[Ollama] Video analysis successful")
                else:
                    result["error"] = "Model returned empty response"

        except Exception as e:
            result["error"] = f"Analysis failed: {str(e)}"
            logger.error(f"[Ollama] Video analysis error: {e}")

        return result

    def _clean_video_description(self, description: str) -> str:
        """Clean up video description from model output."""
        if not description:
            return ""

        # Remove thinking tags
        description = re.sub(r'<think>[\s\S]*?</think>', '', description, flags=re.IGNORECASE)
        description = re.sub(r'<\|.*?\|>', '', description)

        # Remove meta-commentary
        meta_patterns = [
            r"(Got it|Okay|OK|Alright),?\s*(let's|let me|I'll)\s+[^.]*\.\s*",
            r"Looking at\s+(the\s+)?(user's|this|these)\s+[^.]*,?\s*",
        ]
        for pattern in meta_patterns:
            description = re.sub(pattern, '', description, flags=re.IGNORECASE)

        return description.strip()


# =============================================================================
# OpenAI Provider
# =============================================================================

class OpenAILangChainProvider(BaseLangChainProvider):
    """
    OpenAI provider using LangChain's ChatOpenAI.

    Supports:
    - GPT-4, GPT-4o, GPT-4-turbo, GPT-3.5-turbo
    - Structured outputs with strict mode
    - Streaming
    - Tool calling

    Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key
    """

    DEFAULT_MODELS = [
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"
    ]

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        self.endpoint = config.endpoint  # For custom OpenAI-compatible endpoints

    async def initialize(self) -> None:
        """Initialize the OpenAI ChatModel."""
        if self._initialized:
            return

        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY or pass api_key in config.")

        try:
            from langchain_openai import ChatOpenAI

            kwargs = {
                "model": self.model,
                "api_key": self.api_key,
                "temperature": self.config.temperature or 0.7,
                "max_tokens": self.config.max_tokens,
                "timeout": self.config.timeout or 60,
                "max_retries": 2,
            }

            if self.endpoint:
                kwargs["base_url"] = self.endpoint

            self._chat_model = ChatOpenAI(**kwargs)
            self._initialized = True
            logger.info(f"[OpenAI] Initialized with model: {self.model}")

        except ImportError:
            logger.error("[OpenAI] langchain-openai not installed. Run: pip install langchain-openai")
            raise RuntimeError("langchain-openai package not installed")
        except Exception as e:
            logger.error(f"[OpenAI] Failed to initialize: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text using OpenAI."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            # Update parameters
            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            logger.info(f"[OpenAI] Generating with model {self.model}")

            response = await self._chat_model.ainvoke(messages)
            result = response.content

            logger.info(f"[OpenAI] Generation complete: {len(result)} chars")
            return result

        except Exception as e:
            error_msg = f"OpenAI generation failed: {type(e).__name__}: {str(e)}"
            logger.error(f"[OpenAI] {error_msg}")
            raise RuntimeError(error_msg)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Chat-based generation."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            response = await self._chat_model.ainvoke(lc_messages)
            return response.content

        except Exception as e:
            logger.error(f"[OpenAI] Chat error: {e}")
            raise

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> BaseModel:
        """Generate structured output using OpenAI's structured output feature."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            # Use with_structured_output for native support
            structured_model = self._chat_model.with_structured_output(response_schema)

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            logger.info(f"[OpenAI] Structured generation with schema: {response_schema.__name__}")

            result = await structured_model.ainvoke(messages)
            logger.info(f"[OpenAI] Structured output parsed successfully")
            return result

        except Exception as e:
            logger.warning(f"[OpenAI] Native structured output failed, falling back: {e}")
            return await super().generate_structured(
                prompt, response_schema, max_tokens, temperature, system
            )

    async def is_available(self) -> bool:
        """Check if OpenAI API is accessible."""
        if not self.api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                endpoint = self.endpoint or "https://api.openai.com/v1"
                response = await client.get(
                    f"{endpoint}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception:
            return False


# =============================================================================
# Azure OpenAI Provider
# =============================================================================

class AzureOpenAILangChainProvider(BaseLangChainProvider):
    """
    Azure OpenAI provider using LangChain's AzureChatOpenAI.

    Supports:
    - GPT-4, GPT-3.5-turbo on Azure
    - Microsoft Entra ID authentication
    - Custom deployments

    Environment Variables:
    - AZURE_OPENAI_API_KEY: Your Azure OpenAI API key
    - AZURE_OPENAI_ENDPOINT: Your Azure endpoint URL
    - AZURE_OPENAI_API_VERSION: API version (default: 2024-05-01-preview)
    - AZURE_OPENAI_DEPLOYMENT_NAME: Your deployment name
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = config.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment = config.azure_deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") or config.model
        self.api_version = config.azure_api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")

    async def initialize(self) -> None:
        """Initialize the Azure OpenAI ChatModel."""
        if self._initialized:
            return

        if not self.endpoint:
            raise ValueError("Azure OpenAI endpoint is required. Set AZURE_OPENAI_ENDPOINT.")
        if not self.api_key:
            raise ValueError("Azure OpenAI API key is required. Set AZURE_OPENAI_API_KEY.")

        try:
            from langchain_openai import AzureChatOpenAI

            self._chat_model = AzureChatOpenAI(
                azure_deployment=self.deployment,
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
                temperature=self.config.temperature or 0.7,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout or 60,
                max_retries=2,
            )
            self._initialized = True
            logger.info(f"[Azure OpenAI] Initialized deployment: {self.deployment} at {self.endpoint}")

        except ImportError:
            logger.error("[Azure OpenAI] langchain-openai not installed. Run: pip install langchain-openai")
            raise RuntimeError("langchain-openai package not installed")
        except Exception as e:
            logger.error(f"[Azure OpenAI] Failed to initialize: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text using Azure OpenAI."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            logger.info(f"[Azure OpenAI] Generating with deployment {self.deployment}")

            response = await self._chat_model.ainvoke(messages)
            result = response.content

            logger.info(f"[Azure OpenAI] Generation complete: {len(result)} chars")
            return result

        except Exception as e:
            error_msg = f"Azure OpenAI generation failed: {type(e).__name__}: {str(e)}"
            logger.error(f"[Azure OpenAI] {error_msg}")
            raise RuntimeError(error_msg)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Chat-based generation."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            response = await self._chat_model.ainvoke(lc_messages)
            return response.content

        except Exception as e:
            logger.error(f"[Azure OpenAI] Chat error: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if Azure OpenAI is accessible."""
        if not self.endpoint or not self.api_key:
            return False

        try:
            # Try a simple list models call
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.endpoint}/openai/models?api-version={self.api_version}",
                    headers={"api-key": self.api_key}
                )
                return response.status_code == 200
        except Exception:
            return False


# =============================================================================
# Anthropic Provider
# =============================================================================

class AnthropicLangChainProvider(BaseLangChainProvider):
    """
    Anthropic/Claude provider using LangChain's ChatAnthropic.

    Supports:
    - Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku
    - Extended thinking
    - Tool calling with strict mode
    - Image and PDF input

    Environment Variables:
    - ANTHROPIC_API_KEY: Your Anthropic API key
    """

    DEFAULT_MODELS = [
        "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest",
        "claude-3-opus-latest", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"
    ]

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")

    async def initialize(self) -> None:
        """Initialize the Anthropic ChatModel."""
        if self._initialized:
            return

        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY or pass api_key in config.")

        try:
            from langchain_anthropic import ChatAnthropic

            self._chat_model = ChatAnthropic(
                model=self.model,
                api_key=self.api_key,
                temperature=self.config.temperature or 0.7,
                max_tokens=self.config.max_tokens or 4096,
                timeout=self.config.timeout or 60,
                max_retries=2,
            )
            self._initialized = True
            logger.info(f"[Anthropic] Initialized with model: {self.model}")

        except ImportError:
            logger.error("[Anthropic] langchain-anthropic not installed. Run: pip install langchain-anthropic")
            raise RuntimeError("langchain-anthropic package not installed")
        except Exception as e:
            logger.error(f"[Anthropic] Failed to initialize: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text using Anthropic."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            logger.info(f"[Anthropic] Generating with model {self.model}")

            response = await self._chat_model.ainvoke(messages)
            result = response.content

            logger.info(f"[Anthropic] Generation complete: {len(result)} chars")
            return result

        except Exception as e:
            error_msg = f"Anthropic generation failed: {type(e).__name__}: {str(e)}"
            logger.error(f"[Anthropic] {error_msg}")
            raise RuntimeError(error_msg)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Chat-based generation."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            response = await self._chat_model.ainvoke(lc_messages)
            return response.content

        except Exception as e:
            logger.error(f"[Anthropic] Chat error: {e}")
            raise

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> BaseModel:
        """Generate structured output using Anthropic's structured output feature."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            structured_model = self._chat_model.with_structured_output(response_schema)

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            logger.info(f"[Anthropic] Structured generation with schema: {response_schema.__name__}")

            result = await structured_model.ainvoke(messages)
            logger.info(f"[Anthropic] Structured output parsed successfully")
            return result

        except Exception as e:
            logger.warning(f"[Anthropic] Native structured output failed, falling back: {e}")
            return await super().generate_structured(
                prompt, response_schema, max_tokens, temperature, system
            )

    async def is_available(self) -> bool:
        """Check if Anthropic API is accessible."""
        return bool(self.api_key)


# =============================================================================
# Google Gemini Provider
# =============================================================================

class GoogleGeminiLangChainProvider(BaseLangChainProvider):
    """
    Google Gemini provider using LangChain's ChatGoogleGenerativeAI.

    Supports:
    - Gemini Pro, Gemini Flash
    - Multimodal input (images, video, audio, PDF)
    - Thinking support

    Environment Variables:
    - GOOGLE_API_KEY or GEMINI_API_KEY: Your Google API key
    """

    DEFAULT_MODELS = [
        "gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"
    ]

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    async def initialize(self) -> None:
        """Initialize the Google Gemini ChatModel."""
        if self._initialized:
            return

        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY or pass api_key in config.")

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            self._chat_model = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=self.api_key,
                temperature=self.config.temperature or 1.0,  # Gemini defaults to 1.0
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout or 60,
                max_retries=2,
            )
            self._initialized = True
            logger.info(f"[Google Gemini] Initialized with model: {self.model}")

        except ImportError:
            logger.error("[Google Gemini] langchain-google-genai not installed. Run: pip install langchain-google-genai")
            raise RuntimeError("langchain-google-genai package not installed")
        except Exception as e:
            logger.error(f"[Google Gemini] Failed to initialize: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text using Google Gemini."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            logger.info(f"[Google Gemini] Generating with model {self.model}")

            response = await self._chat_model.ainvoke(messages)
            result = response.content

            logger.info(f"[Google Gemini] Generation complete: {len(result)} chars")
            return result

        except Exception as e:
            error_msg = f"Google Gemini generation failed: {type(e).__name__}: {str(e)}"
            logger.error(f"[Google Gemini] {error_msg}")
            raise RuntimeError(error_msg)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Chat-based generation."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            response = await self._chat_model.ainvoke(lc_messages)
            return response.content

        except Exception as e:
            logger.error(f"[Google Gemini] Chat error: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if Google API is accessible."""
        return bool(self.api_key)


# =============================================================================
# AWS Bedrock Provider
# =============================================================================

class AWSBedrockLangChainProvider(BaseLangChainProvider):
    """
    AWS Bedrock provider using LangChain's ChatBedrockConverse.

    Supports:
    - Anthropic Claude models
    - AI21, Cohere, Meta Llama models
    - Extended thinking

    Environment Variables:
    - AWS_ACCESS_KEY_ID: Your AWS access key
    - AWS_SECRET_ACCESS_KEY: Your AWS secret key
    - AWS_SESSION_TOKEN: (Optional) Session token for temporary credentials
    - AWS_DEFAULT_REGION: AWS region (default: us-east-1)
    """

    DEFAULT_MODELS = [
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "anthropic.claude-3-haiku-20240307-v1:0",
        "meta.llama3-70b-instruct-v1:0"
    ]

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.region = config.aws_region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.access_key = config.aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = config.aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.session_token = config.aws_session_token or os.getenv("AWS_SESSION_TOKEN")

    async def initialize(self) -> None:
        """Initialize the AWS Bedrock ChatModel."""
        if self._initialized:
            return

        try:
            from langchain_aws import ChatBedrockConverse

            kwargs = {
                "model_id": self.model,
                "region_name": self.region,
                "temperature": self.config.temperature or 0.7,
                "max_tokens": self.config.max_tokens,
            }

            if self.access_key:
                kwargs["aws_access_key_id"] = self.access_key
            if self.secret_key:
                kwargs["aws_secret_access_key"] = self.secret_key
            if self.session_token:
                kwargs["aws_session_token"] = self.session_token

            self._chat_model = ChatBedrockConverse(**kwargs)
            self._initialized = True
            logger.info(f"[AWS Bedrock] Initialized with model: {self.model} in {self.region}")

        except ImportError:
            logger.error("[AWS Bedrock] langchain-aws not installed. Run: pip install langchain-aws")
            raise RuntimeError("langchain-aws package not installed")
        except Exception as e:
            logger.error(f"[AWS Bedrock] Failed to initialize: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text using AWS Bedrock."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            logger.info(f"[AWS Bedrock] Generating with model {self.model}")

            response = await self._chat_model.ainvoke(messages)
            result = response.content

            logger.info(f"[AWS Bedrock] Generation complete: {len(result)} chars")
            return result

        except Exception as e:
            error_msg = f"AWS Bedrock generation failed: {type(e).__name__}: {str(e)}"
            logger.error(f"[AWS Bedrock] {error_msg}")
            raise RuntimeError(error_msg)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Chat-based generation."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            response = await self._chat_model.ainvoke(lc_messages)
            return response.content

        except Exception as e:
            logger.error(f"[AWS Bedrock] Chat error: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if AWS credentials are configured."""
        return bool(self.access_key and self.secret_key)


# =============================================================================
# HuggingFace Provider
# =============================================================================

class HuggingFaceLangChainProvider(BaseLangChainProvider):
    """
    HuggingFace provider using LangChain's ChatHuggingFace.

    Supports:
    - HuggingFace Hub models
    - Local models via HuggingFacePipeline
    - Inference providers (Hyperbolic, Nebius, Together)

    Environment Variables:
    - HUGGINGFACEHUB_API_TOKEN: Your HuggingFace API token
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        self.provider = config.huggingface_provider or "auto"

    async def initialize(self) -> None:
        """Initialize the HuggingFace ChatModel."""
        if self._initialized:
            return

        if not self.api_key:
            raise ValueError("HuggingFace API token is required. Set HUGGINGFACEHUB_API_TOKEN.")

        try:
            from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

            llm = HuggingFaceEndpoint(
                repo_id=self.model,
                task="text-generation",
                max_new_tokens=self.config.max_tokens or 512,
                do_sample=True,
                temperature=self.config.temperature or 0.7,
                provider=self.provider,
            )

            self._chat_model = ChatHuggingFace(llm=llm)
            self._initialized = True
            logger.info(f"[HuggingFace] Initialized with model: {self.model}")

        except ImportError:
            logger.error("[HuggingFace] langchain-huggingface not installed. Run: pip install langchain-huggingface")
            raise RuntimeError("langchain-huggingface package not installed")
        except Exception as e:
            logger.error(f"[HuggingFace] Failed to initialize: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text using HuggingFace."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            logger.info(f"[HuggingFace] Generating with model {self.model}")

            response = await self._chat_model.ainvoke(messages)
            result = response.content

            logger.info(f"[HuggingFace] Generation complete: {len(result)} chars")
            return result

        except Exception as e:
            error_msg = f"HuggingFace generation failed: {type(e).__name__}: {str(e)}"
            logger.error(f"[HuggingFace] {error_msg}")
            raise RuntimeError(error_msg)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Chat-based generation."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            response = await self._chat_model.ainvoke(lc_messages)
            return response.content

        except Exception as e:
            logger.error(f"[HuggingFace] Chat error: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if HuggingFace API is accessible."""
        return bool(self.api_key)


# =============================================================================
# Custom OpenAI-Compatible Provider
# =============================================================================

class CustomLangChainProvider(BaseLangChainProvider):
    """
    Custom OpenAI-compatible endpoint provider.

    Supports any endpoint that implements the OpenAI Chat Completions API.
    This includes:
    - LM Studio
    - Text Generation Inference (TGI)
    - vLLM
    - LocalAI
    - Any OpenAI-compatible API

    SECURITY: Endpoints are validated against SSRF attacks.
    Internal IPs, localhost, and cloud metadata endpoints are blocked
    unless running in development mode.
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.endpoint = config.endpoint
        self.api_key = config.api_key or "not-needed"  # Some endpoints don't require keys
        self._endpoint_validated = False

    def _validate_endpoint(self) -> None:
        """
        Validate the endpoint URL to prevent SSRF attacks.

        Raises:
            ValueError: If the endpoint is invalid or blocked
        """
        if self._endpoint_validated:
            return

        if not self.endpoint:
            raise ValueError("Custom endpoint URL is required.")

        # Allow localhost in development mode for local LLM servers
        allow_localhost = is_development_mode()

        is_valid, error_msg = validate_endpoint_url(self.endpoint, allow_localhost=allow_localhost)

        if not is_valid:
            logger.warning(f"[Custom] SSRF blocked: {error_msg} for endpoint: {self.endpoint}")
            raise ValueError(f"Invalid endpoint URL: {error_msg}")

        self._endpoint_validated = True
        logger.debug(f"[Custom] Endpoint validated: {self.endpoint}")

    async def initialize(self) -> None:
        """Initialize the Custom ChatModel using OpenAI client."""
        if self._initialized:
            return

        # Validate endpoint BEFORE using it (SSRF protection)
        self._validate_endpoint()

        try:
            from langchain_openai import ChatOpenAI

            self._chat_model = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                base_url=self.endpoint,
                temperature=self.config.temperature or 0.7,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout or 120,
                max_retries=2,
            )
            self._initialized = True
            logger.info(f"[Custom] Initialized with model: {self.model} at {self.endpoint}")

        except ImportError:
            logger.error("[Custom] langchain-openai not installed. Run: pip install langchain-openai")
            raise RuntimeError("langchain-openai package not installed")
        except Exception as e:
            logger.error(f"[Custom] Failed to initialize: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> str:
        """Generate text using Custom endpoint."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            logger.info(f"[Custom] Generating with model {self.model} at {self.endpoint}")

            response = await self._chat_model.ainvoke(messages)
            result = response.content

            logger.info(f"[Custom] Generation complete: {len(result)} chars")
            return result

        except Exception as e:
            error_msg = f"Custom endpoint generation failed: {type(e).__name__}: {str(e)}"
            logger.error(f"[Custom] {error_msg}")
            raise RuntimeError(error_msg)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Chat-based generation."""
        await self.initialize()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            self._chat_model.temperature = temperature
            self._chat_model.max_tokens = max_tokens

            response = await self._chat_model.ainvoke(lc_messages)
            return response.content

        except Exception as e:
            logger.error(f"[Custom] Chat error: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if custom endpoint is accessible."""
        if not self.endpoint:
            return False

        # Validate endpoint before making HTTP request (SSRF protection)
        try:
            self._validate_endpoint()
        except ValueError as e:
            logger.warning(f"[Custom] Endpoint validation failed in is_available: {e}")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {}
                if self.api_key and self.api_key != "not-needed":
                    headers["Authorization"] = f"Bearer {self.api_key}"

                response = await client.get(f"{self.endpoint}/models", headers=headers)
                return response.status_code in [200, 401]  # 401 means endpoint exists
        except Exception:
            return False


# =============================================================================
# Provider Factory
# =============================================================================

class LangChainProviderFactory:
    """
    Factory class for creating LangChain providers.

    Usage:
        config = ProviderConfig(type="openai", model="gpt-4o", api_key="...")
        provider = LangChainProviderFactory.create(config)
        result = await provider.generate("Hello, world!")
    """

    PROVIDER_MAP = {
        "ollama": OllamaLangChainProvider,
        "openai": OpenAILangChainProvider,
        "anthropic": AnthropicLangChainProvider,
        "azure_openai": AzureOpenAILangChainProvider,
        "google": GoogleGeminiLangChainProvider,
        "aws_bedrock": AWSBedrockLangChainProvider,
        "huggingface": HuggingFaceLangChainProvider,
        "custom": CustomLangChainProvider,
    }

    @classmethod
    def create(cls, config: ProviderConfig) -> BaseLangChainProvider:
        """
        Create a provider instance from configuration.

        Args:
            config: Provider configuration

        Returns:
            Initialized provider instance

        Raises:
            ValueError: If provider type is not supported
        """
        provider_class = cls.PROVIDER_MAP.get(config.type)

        if not provider_class:
            supported = ", ".join(cls.PROVIDER_MAP.keys())
            raise ValueError(f"Unknown provider type: {config.type}. Supported: {supported}")

        logger.info(f"[Factory] Creating {config.type} provider with model: {config.model}")
        return provider_class(config)

    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Get list of supported provider types."""
        return list(cls.PROVIDER_MAP.keys())

    @classmethod
    def get_provider_info(cls) -> List[Dict[str, Any]]:
        """Get detailed information about all supported providers."""
        return [
            {
                "type": "ollama",
                "name": "Ollama (Local)",
                "description": "Run AI models locally on your machine",
                "requires_api_key": False,
                "default_models": ["llama3.2:3b", "qwen3:4b", "mistral:7b"],
                "supports_vision": True,
                "supports_structured_output": True,
            },
            {
                "type": "openai",
                "name": "OpenAI",
                "description": "GPT-4, GPT-4o, and GPT-3.5 models",
                "requires_api_key": True,
                "env_var": "OPENAI_API_KEY",
                "default_models": OpenAILangChainProvider.DEFAULT_MODELS,
                "supports_vision": True,
                "supports_structured_output": True,
            },
            {
                "type": "anthropic",
                "name": "Anthropic",
                "description": "Claude 3.5 and Claude 3 models",
                "requires_api_key": True,
                "env_var": "ANTHROPIC_API_KEY",
                "default_models": AnthropicLangChainProvider.DEFAULT_MODELS,
                "supports_vision": True,
                "supports_structured_output": True,
            },
            {
                "type": "azure_openai",
                "name": "Azure OpenAI",
                "description": "OpenAI models on Microsoft Azure",
                "requires_api_key": True,
                "env_vars": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
                "default_models": ["gpt-4", "gpt-4o", "gpt-35-turbo"],
                "supports_vision": True,
                "supports_structured_output": True,
            },
            {
                "type": "google",
                "name": "Google Gemini",
                "description": "Gemini Pro and Gemini Flash models",
                "requires_api_key": True,
                "env_var": "GOOGLE_API_KEY",
                "default_models": GoogleGeminiLangChainProvider.DEFAULT_MODELS,
                "supports_vision": True,
                "supports_structured_output": True,
            },
            {
                "type": "aws_bedrock",
                "name": "AWS Bedrock",
                "description": "Claude, Llama, and other models on AWS",
                "requires_api_key": True,
                "env_vars": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
                "default_models": AWSBedrockLangChainProvider.DEFAULT_MODELS,
                "supports_vision": True,
                "supports_structured_output": True,
            },
            {
                "type": "huggingface",
                "name": "HuggingFace",
                "description": "Open-source models from HuggingFace Hub",
                "requires_api_key": True,
                "env_var": "HUGGINGFACEHUB_API_TOKEN",
                "default_models": ["meta-llama/Llama-3-8B-Instruct", "mistralai/Mistral-7B-Instruct-v0.2"],
                "supports_vision": False,
                "supports_structured_output": False,
            },
            {
                "type": "custom",
                "name": "Custom Endpoint",
                "description": "Any OpenAI-compatible API endpoint",
                "requires_api_key": False,
                "requires_endpoint": True,
                "default_models": [],
                "supports_vision": False,
                "supports_structured_output": True,
            },
        ]
