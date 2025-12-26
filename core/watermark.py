"""
Watermark System for TermiVoxed

Adds watermarks to video exports for free tier users.
Supports:
- Text watermarks with customizable position/style
- Image/logo overlays
- Animated watermarks
- End-screen branding

Author: Santhosh T
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum
import logging

# Import FFmpegUtils for quality presets
from backend.ffmpeg_utils import FFmpegUtils

logger = logging.getLogger(__name__)


class WatermarkPosition(Enum):
    """Watermark position on video"""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    TOP_CENTER = "top_center"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"
    CENTER = "center"


class WatermarkType(Enum):
    """Type of watermark"""
    TEXT = "text"
    IMAGE = "image"
    ANIMATED = "animated"
    END_SCREEN = "end_screen"


@dataclass
class WatermarkConfig:
    """Configuration for watermark"""
    type: WatermarkType = WatermarkType.TEXT
    text: str = "Made with TermiVoxed"
    font: str = "Arial"
    font_size: int = 24
    color: str = "white"
    opacity: float = 0.7
    position: WatermarkPosition = WatermarkPosition.BOTTOM_RIGHT
    margin_x: int = 20
    margin_y: int = 20
    shadow: bool = True
    shadow_color: str = "black"
    shadow_offset: int = 2
    image_path: Optional[str] = None
    image_scale: float = 0.15  # 15% of video width
    end_screen_duration: float = 3.0
    animated: bool = False
    animation_duration: float = 2.0


class WatermarkService:
    """
    Service for adding watermarks to videos

    Used for:
    - Free tier export watermarking
    - Branding for shared exports
    - Trial version identification
    """

    # Default watermark configurations by tier
    TIER_CONFIGS = {
        'free_trial': WatermarkConfig(
            text="TermiVoxed Trial",
            opacity=0.8,
            position=WatermarkPosition.BOTTOM_RIGHT,
            end_screen_duration=5.0
        ),
        'expired': WatermarkConfig(
            text="TermiVoxed - Upgrade for Full Quality",
            opacity=0.85,
            position=WatermarkPosition.CENTER,
            font_size=32
        ),
    }

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._logo_path: Optional[Path] = None
        self._temp_dir = Path(tempfile.gettempdir()) / "termivoxed_watermark"
        self._temp_dir.mkdir(exist_ok=True)

    def _get_position_filter(
        self,
        position: WatermarkPosition,
        margin_x: int,
        margin_y: int,
        overlay_w: str = "overlay_w",
        overlay_h: str = "overlay_h"
    ) -> str:
        """
        Get FFmpeg position expression for watermark

        Args:
            position: Watermark position enum
            margin_x: Horizontal margin in pixels
            margin_y: Vertical margin in pixels
            overlay_w: Width variable name (for image overlays)
            overlay_h: Height variable name (for image overlays)

        Returns:
            FFmpeg position expression (x:y)
        """
        positions = {
            WatermarkPosition.TOP_LEFT: f"{margin_x}:{margin_y}",
            WatermarkPosition.TOP_RIGHT: f"W-{overlay_w}-{margin_x}:{margin_y}",
            WatermarkPosition.TOP_CENTER: f"(W-{overlay_w})/2:{margin_y}",
            WatermarkPosition.BOTTOM_LEFT: f"{margin_x}:H-{overlay_h}-{margin_y}",
            WatermarkPosition.BOTTOM_RIGHT: f"W-{overlay_w}-{margin_x}:H-{overlay_h}-{margin_y}",
            WatermarkPosition.BOTTOM_CENTER: f"(W-{overlay_w})/2:H-{overlay_h}-{margin_y}",
            WatermarkPosition.CENTER: f"(W-{overlay_w})/2:(H-{overlay_h})/2",
        }
        return positions.get(position, positions[WatermarkPosition.BOTTOM_RIGHT])

    def _get_text_position(
        self,
        position: WatermarkPosition,
        margin_x: int,
        margin_y: int
    ) -> str:
        """Get FFmpeg position expression for text watermark"""
        positions = {
            WatermarkPosition.TOP_LEFT: f"x={margin_x}:y={margin_y}",
            WatermarkPosition.TOP_RIGHT: f"x=W-tw-{margin_x}:y={margin_y}",
            WatermarkPosition.TOP_CENTER: f"x=(W-tw)/2:y={margin_y}",
            WatermarkPosition.BOTTOM_LEFT: f"x={margin_x}:y=H-th-{margin_y}",
            WatermarkPosition.BOTTOM_RIGHT: f"x=W-tw-{margin_x}:y=H-th-{margin_y}",
            WatermarkPosition.BOTTOM_CENTER: f"x=(W-tw)/2:y=H-th-{margin_y}",
            WatermarkPosition.CENTER: f"x=(W-tw)/2:y=(H-th)/2",
        }
        return positions.get(position, positions[WatermarkPosition.BOTTOM_RIGHT])

    def _color_to_ffmpeg(self, color: str, opacity: float = 1.0) -> str:
        """Convert color to FFmpeg format with opacity"""
        # Handle named colors
        color_map = {
            'white': 'FFFFFF',
            'black': '000000',
            'red': 'FF0000',
            'green': '00FF00',
            'blue': '0000FF',
            'yellow': 'FFFF00',
            'gray': '808080',
            'grey': '808080',
        }

        hex_color = color_map.get(color.lower(), color.lstrip('#'))

        # Add alpha channel for opacity
        alpha = format(int(opacity * 255), '02x')
        return f"#{hex_color}@{opacity}"

    def _build_text_filter(self, config: WatermarkConfig) -> str:
        """
        Build FFmpeg drawtext filter for text watermark

        Args:
            config: Watermark configuration

        Returns:
            FFmpeg filter string
        """
        position = self._get_text_position(
            config.position,
            config.margin_x,
            config.margin_y
        )

        # Escape special characters in text
        escaped_text = config.text.replace("'", "\\'").replace(":", "\\:")

        # Build filter
        filter_parts = [
            f"fontfile={self._get_font_path(config.font)}",
            f"text='{escaped_text}'",
            f"fontsize={config.font_size}",
            f"fontcolor={config.color}@{config.opacity}",
            position,
        ]

        # Add shadow if enabled
        if config.shadow:
            filter_parts.append(f"shadowcolor={config.shadow_color}@0.5")
            filter_parts.append(f"shadowx={config.shadow_offset}")
            filter_parts.append(f"shadowy={config.shadow_offset}")

        return "drawtext=" + ":".join(filter_parts)

    def _get_font_path(self, font_name: str) -> str:
        """Get font file path for FFmpeg"""
        # Common font paths by OS
        import platform
        system = platform.system()

        if system == "Darwin":  # macOS
            font_dirs = [
                "/System/Library/Fonts",
                "/Library/Fonts",
                Path.home() / "Library" / "Fonts"
            ]
        elif system == "Windows":
            font_dirs = [
                Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
            ]
        else:  # Linux
            font_dirs = [
                "/usr/share/fonts",
                "/usr/local/share/fonts",
                Path.home() / ".fonts"
            ]

        # Font file mappings
        font_files = {
            'arial': 'Arial.ttf',
            'helvetica': 'Helvetica.ttf',
            'times': 'Times.ttf',
            'roboto': 'Roboto-Regular.ttf',
            'sans': 'DejaVuSans.ttf',
        }

        target_file = font_files.get(font_name.lower(), f"{font_name}.ttf")

        # Search for font
        for font_dir in font_dirs:
            font_path = Path(font_dir) / target_file
            if font_path.exists():
                return str(font_path)

        # Fallback to system default
        if system == "Darwin":
            return "/System/Library/Fonts/Helvetica.ttc"
        elif system == "Windows":
            return "C:\\Windows\\Fonts\\arial.ttf"
        else:
            return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    def _build_image_filter(
        self,
        config: WatermarkConfig,
        video_width: int
    ) -> Tuple[str, List[str]]:
        """
        Build FFmpeg filter for image watermark

        Args:
            config: Watermark configuration
            video_width: Width of input video

        Returns:
            Tuple of (filter_string, input_args)
        """
        if not config.image_path or not Path(config.image_path).exists():
            raise ValueError("Image watermark requires valid image path")

        # Calculate overlay size
        overlay_width = int(video_width * config.image_scale)

        position = self._get_position_filter(
            config.position,
            config.margin_x,
            config.margin_y,
            "w",
            "h"
        )

        # Build filter complex
        filter_complex = (
            f"[1:v]scale={overlay_width}:-1,format=rgba,"
            f"colorchannelmixer=aa={config.opacity}[wm];"
            f"[0:v][wm]overlay={position}"
        )

        input_args = ["-i", config.image_path]

        return filter_complex, input_args

    def _build_end_screen_filter(
        self,
        config: WatermarkConfig,
        video_duration: float,
        video_width: int,
        video_height: int
    ) -> str:
        """
        Build end screen filter that appears at the end of video

        Args:
            config: Watermark configuration
            video_duration: Total video duration
            video_width: Video width
            video_height: Video height

        Returns:
            FFmpeg filter string
        """
        start_time = video_duration - config.end_screen_duration

        # Fade in text at end of video
        filter_parts = [
            f"fontfile={self._get_font_path(config.font)}",
            f"text='{config.text}'",
            f"fontsize={config.font_size * 2}",  # Larger for end screen
            f"fontcolor=white",
            f"x=(W-tw)/2",
            f"y=(H-th)/2",
            f"enable='gte(t,{start_time})'",
            f"alpha='if(gte(t,{start_time}),min(1,(t-{start_time})*2),0)'"
        ]

        return "drawtext=" + ":".join(filter_parts)

    async def add_watermark(
        self,
        input_path: str,
        output_path: str,
        config: Optional[WatermarkConfig] = None,
        tier: Optional[str] = None,
        video_info: Optional[Dict] = None,
        quality: str = "balanced"
    ) -> Tuple[bool, str]:
        """
        Add watermark to video

        Args:
            input_path: Input video path
            output_path: Output video path
            config: Watermark configuration (or use tier default)
            tier: Subscription tier for default config
            video_info: Video metadata (width, height, duration)
            quality: Video quality preset ('lossless', 'high', 'balanced')
                     Must match the export quality to preserve video quality

        Returns:
            Tuple of (success, message)
        """
        # Get configuration
        if config is None:
            if tier and tier in self.TIER_CONFIGS:
                config = self.TIER_CONFIGS[tier]
            else:
                config = WatermarkConfig()

        # Validate input
        if not Path(input_path).exists():
            return False, f"Input file not found: {input_path}"

        # Get video info if not provided
        if video_info is None:
            video_info = self._get_video_info(input_path)
            if video_info is None:
                return False, "Could not read video information"

        try:
            # Build FFmpeg command based on watermark type
            if config.type == WatermarkType.TEXT:
                success, message = await self._apply_text_watermark(
                    input_path, output_path, config, video_info, quality
                )
            elif config.type == WatermarkType.IMAGE:
                success, message = await self._apply_image_watermark(
                    input_path, output_path, config, video_info, quality
                )
            elif config.type == WatermarkType.END_SCREEN:
                success, message = await self._apply_end_screen(
                    input_path, output_path, config, video_info, quality
                )
            else:
                # Combined: text + end screen
                success, message = await self._apply_combined_watermark(
                    input_path, output_path, config, video_info, quality
                )

            return success, message

        except Exception as e:
            logger.error(f"Watermark error: {e}")
            return False, str(e)

    async def _apply_text_watermark(
        self,
        input_path: str,
        output_path: str,
        config: WatermarkConfig,
        video_info: Dict,
        quality: str = "balanced"
    ) -> Tuple[bool, str]:
        """Apply text-only watermark with quality preservation"""
        text_filter = self._build_text_filter(config)

        # Get quality settings to match export quality
        quality_settings = FFmpegUtils.get_quality_preset(quality)
        encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

        logger.info(f"Applying text watermark with {quality} quality (codec: {quality_settings['codec']})")

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-vf", text_filter,
            *encoder_args,  # Video encoder args matching export quality
            "-codec:a", "copy",
            "-y",
            output_path
        ]

        return await self._run_ffmpeg(cmd)

    async def _apply_image_watermark(
        self,
        input_path: str,
        output_path: str,
        config: WatermarkConfig,
        video_info: Dict,
        quality: str = "balanced"
    ) -> Tuple[bool, str]:
        """Apply image overlay watermark with quality preservation"""
        filter_complex, input_args = self._build_image_filter(
            config,
            video_info.get('width', 1920)
        )

        # Get quality settings to match export quality
        quality_settings = FFmpegUtils.get_quality_preset(quality)
        encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

        logger.info(f"Applying image watermark with {quality} quality (codec: {quality_settings['codec']})")

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            *input_args,
            "-filter_complex", filter_complex,
            *encoder_args,  # Video encoder args matching export quality
            "-codec:a", "copy",
            "-y",
            output_path
        ]

        return await self._run_ffmpeg(cmd)

    async def _apply_end_screen(
        self,
        input_path: str,
        output_path: str,
        config: WatermarkConfig,
        video_info: Dict,
        quality: str = "balanced"
    ) -> Tuple[bool, str]:
        """Apply end screen branding with quality preservation"""
        end_filter = self._build_end_screen_filter(
            config,
            video_info.get('duration', 60),
            video_info.get('width', 1920),
            video_info.get('height', 1080)
        )

        # Get quality settings to match export quality
        quality_settings = FFmpegUtils.get_quality_preset(quality)
        encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

        logger.info(f"Applying end screen with {quality} quality (codec: {quality_settings['codec']})")

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-vf", end_filter,
            *encoder_args,  # Video encoder args matching export quality
            "-codec:a", "copy",
            "-y",
            output_path
        ]

        return await self._run_ffmpeg(cmd)

    async def _apply_combined_watermark(
        self,
        input_path: str,
        output_path: str,
        config: WatermarkConfig,
        video_info: Dict,
        quality: str = "balanced"
    ) -> Tuple[bool, str]:
        """Apply text watermark + end screen with quality preservation"""
        text_filter = self._build_text_filter(config)
        end_filter = self._build_end_screen_filter(
            config,
            video_info.get('duration', 60),
            video_info.get('width', 1920),
            video_info.get('height', 1080)
        )

        # Combine filters
        combined_filter = f"{text_filter},{end_filter}"

        # Get quality settings to match export quality
        quality_settings = FFmpegUtils.get_quality_preset(quality)
        encoder_args = FFmpegUtils.get_video_encoder_args(quality_settings)

        logger.info(f"Applying combined watermark with {quality} quality (codec: {quality_settings['codec']})")

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-vf", combined_filter,
            *encoder_args,  # Video encoder args matching export quality
            "-codec:a", "copy",
            "-y",
            output_path
        ]

        return await self._run_ffmpeg(cmd)

    async def _run_ffmpeg(self, cmd: List[str]) -> Tuple[bool, str]:
        """Run FFmpeg command"""
        try:
            logger.debug(f"Running FFmpeg: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return True, "Watermark applied successfully"
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False, result.stderr

        except FileNotFoundError:
            return False, "FFmpeg not found"
        except Exception as e:
            return False, str(e)

    def _get_video_info(self, video_path: str) -> Optional[Dict]:
        """Get video metadata using ffprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                stream = data.get('streams', [{}])[0]
                format_info = data.get('format', {})

                return {
                    'width': stream.get('width', 1920),
                    'height': stream.get('height', 1080),
                    'duration': float(format_info.get('duration', 60))
                }
        except Exception as e:
            logger.error(f"ffprobe error: {e}")

        return None

    def should_add_watermark(self, tier: str) -> bool:
        """
        Check if watermark should be added based on subscription tier

        Args:
            tier: User's subscription tier

        Returns:
            True if watermark should be added
        """
        # Tiers that require watermark
        watermark_tiers = {'free_trial', 'expired', 'free'}

        return tier.lower() in watermark_tiers

    def get_watermark_config(self, tier: str) -> WatermarkConfig:
        """
        Get appropriate watermark configuration for tier

        Args:
            tier: User's subscription tier

        Returns:
            WatermarkConfig for the tier
        """
        return self.TIER_CONFIGS.get(tier.lower(), WatermarkConfig())


# Global instance
_watermark_service: Optional[WatermarkService] = None


def get_watermark_service(ffmpeg_path: str = "ffmpeg") -> WatermarkService:
    """Get or create watermark service instance"""
    global _watermark_service
    if _watermark_service is None:
        _watermark_service = WatermarkService(ffmpeg_path)
    return _watermark_service
