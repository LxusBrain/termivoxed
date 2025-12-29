"""FFmpeg utilities - Proven patterns from existing system"""

import subprocess
import os
import re
import time
import asyncio
from typing import Optional, List, Tuple, Callable
from pathlib import Path
from utils.logger import logger
from config import settings


def escape_ffmpeg_filter_path(path: str) -> str:
    """
    Properly escape a file path for use in FFmpeg filter expressions.

    FFmpeg filter syntax requires escaping of special characters:
    - Backslash must be escaped as \\\\
    - Colon must be escaped as \\:
    - Single quote must be escaped as \\'
    - Brackets and other special chars in the filter graph syntax

    Reference: https://ffmpeg.org/ffmpeg-filters.html#Filtering-Introduction

    Args:
        path: The file path to escape

    Returns:
        Escaped path safe for FFmpeg filter expressions
    """
    if not path:
        return path

    # Order matters: escape backslash first, then other characters
    escaped = path.replace('\\', '\\\\\\\\')  # \ -> \\\\
    escaped = escaped.replace(':', '\\:')      # : -> \:
    escaped = escaped.replace("'", "\\'")      # ' -> \'
    escaped = escaped.replace('[', '\\[')      # [ -> \[
    escaped = escaped.replace(']', '\\]')      # ] -> \]
    escaped = escaped.replace(';', '\\;')      # ; -> \;
    escaped = escaped.replace(',', '\\,')      # , -> \,

    return escaped


def escape_concat_path(path: str) -> str:
    """
    Escape a file path for FFmpeg concat demuxer file list.

    The concat demuxer expects paths in single quotes, with single quotes
    in the path escaped.

    Args:
        path: The file path to escape

    Returns:
        Escaped path safe for concat demuxer
    """
    if not path:
        return path

    # Convert to forward slashes for cross-platform compatibility
    escaped = str(Path(path).absolute()).replace('\\', '/')

    # Escape single quotes within the path
    escaped = escaped.replace("'", "'\\''")

    return escaped


class FFmpegProgressTracker:
    """
    Tracks FFmpeg progress by parsing stderr output.

    FFmpeg outputs progress information like:
    frame=  180 fps= 30 q=28.0 size=    1024kB time=00:00:06.00 bitrate= 139.8kbits/s speed=1.2x

    We parse the 'time' field to calculate progress percentage.
    """

    def __init__(self, total_duration: float):
        self.total_duration = total_duration
        self.current_time = 0.0
        self.start_time = time.time()
        self.speed = 1.0
        self.last_update_time = 0.0

    def parse_progress(self, line: str) -> Optional[dict]:
        """Parse FFmpeg progress line and return progress info"""
        # Match time=HH:MM:SS.ms pattern
        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
        speed_match = re.search(r'speed=\s*([\d.]+)x', line)

        if time_match:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            seconds = int(time_match.group(3))
            centiseconds = int(time_match.group(4))

            self.current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100

            if speed_match:
                self.speed = float(speed_match.group(1))

            # Calculate progress percentage
            progress = min(100, int((self.current_time / self.total_duration) * 100)) if self.total_duration > 0 else 0

            # Calculate ETA
            elapsed = time.time() - self.start_time
            remaining_duration = self.total_duration - self.current_time

            if self.speed > 0:
                eta_seconds = remaining_duration / self.speed
            elif elapsed > 0 and self.current_time > 0:
                eta_seconds = (elapsed / self.current_time) * remaining_duration
            else:
                eta_seconds = 0

            return {
                'progress': progress,
                'current_time': self.current_time,
                'total_duration': self.total_duration,
                'speed': self.speed,
                'eta_seconds': max(0, eta_seconds),
                'elapsed_seconds': elapsed
            }

        return None

    @staticmethod
    def format_eta(seconds: float) -> str:
        """Format seconds into human-readable ETA string"""
        if seconds <= 0:
            return "almost done"
        elif seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


async def run_ffmpeg_with_progress(
    cmd: List[str],
    total_duration: float,
    progress_callback: Optional[Callable[[dict], None]] = None,
    stage_name: str = "Processing",
    timeout: int = 600
) -> Tuple[bool, str]:
    """
    Run FFmpeg command asynchronously with real-time progress updates.

    Uses communicate() to properly handle pipe buffers and avoid deadlocks.

    Args:
        cmd: FFmpeg command as list of strings
        total_duration: Expected output duration in seconds
        progress_callback: Async callback function(progress_info) called with progress updates
        stage_name: Name of current processing stage
        timeout: Timeout in seconds (default 10 minutes)

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    import sys
    print(f"[DEBUG] run_ffmpeg_with_progress: starting, duration={total_duration}", file=sys.stderr, flush=True)

    try:
        # Use start_new_session=True to prevent signal propagation issues
        # when running as a nested subprocess (e.g., from export_worker)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True
        )
        print(f"[DEBUG] run_ffmpeg_with_progress: process created, pid={process.pid}", file=sys.stderr, flush=True)

        # Use communicate() which properly handles pipe buffers to avoid deadlocks
        # This reads both stdout and stderr completely while waiting for the process
        print(f"[DEBUG] run_ffmpeg_with_progress: calling communicate()...", file=sys.stderr, flush=True)
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            print(f"[DEBUG] run_ffmpeg_with_progress: communicate() completed, returncode={process.returncode}", file=sys.stderr, flush=True)
        except asyncio.TimeoutError:
            print(f"[DEBUG] run_ffmpeg_with_progress: TIMEOUT!", file=sys.stderr, flush=True)
            process.kill()
            await process.wait()
            return False, f"FFmpeg timed out after {timeout} seconds"

        # Parse stderr for progress info (for callbacks) and error messages
        stderr_text = stderr_data.decode('utf-8', errors='ignore') if stderr_data else ""
        stderr_lines = stderr_text.strip().split('\n') if stderr_text else []

        # If we have a progress callback, parse the final output and send one update
        if progress_callback and stderr_text:
            tracker = FFmpegProgressTracker(total_duration)
            for line in stderr_lines:
                progress_info = tracker.parse_progress(line)
                if progress_info:
                    progress_info['stage'] = stage_name
                    progress_info['eta_formatted'] = FFmpegProgressTracker.format_eta(progress_info.get('eta_seconds', 0))
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(progress_info)
                        else:
                            progress_callback(progress_info)
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")

        print(f"[DEBUG] run_ffmpeg_with_progress: done, returncode={process.returncode}", file=sys.stderr, flush=True)

        if process.returncode == 0:
            return True, ""
        else:
            # Return last 20 lines of stderr as error message
            error_text = '\n'.join(stderr_lines[-20:])
            return False, error_text

    except Exception as e:
        logger.error(f"Error running FFmpeg: {e}")
        print(f"[DEBUG] run_ffmpeg_with_progress: EXCEPTION: {e}", file=sys.stderr, flush=True)
        return False, str(e)


async def run_ffmpeg_with_live_progress(
    cmd: List[str],
    total_duration: float,
    progress_callback: Optional[Callable[[dict], None]] = None,
    stage_name: str = "Processing",
    timeout: int = 600,
    update_interval: float = 0.5
) -> Tuple[bool, str]:
    """
    Run FFmpeg command with REAL-TIME progress streaming.

    Unlike run_ffmpeg_with_progress, this function:
    - Adds -progress pipe:1 to get structured progress output
    - Streams progress updates as they happen (not after completion)
    - Provides accurate ETA and encoding stats

    Args:
        cmd: FFmpeg command as list of strings (will add -progress flag)
        total_duration: Expected output duration in seconds
        progress_callback: Callback function(progress_info) for progress updates
        stage_name: Name of current processing stage
        timeout: Timeout in seconds (default 10 minutes)
        update_interval: Minimum seconds between progress updates (default 0.5)

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    import sys

    # Insert -progress pipe:1 after ffmpeg command to get structured output on stdout
    # Also add -stats_period to control update frequency
    modified_cmd = list(cmd)
    if '-progress' not in modified_cmd:
        # Find position after 'ffmpeg' to insert progress flags
        insert_pos = 1
        for i, arg in enumerate(modified_cmd):
            if arg == '-y':
                insert_pos = i + 1
                break
        modified_cmd.insert(insert_pos, '-progress')
        modified_cmd.insert(insert_pos + 1, 'pipe:1')
        modified_cmd.insert(insert_pos + 2, '-stats_period')
        modified_cmd.insert(insert_pos + 3, str(update_interval))

    logger.debug(f"FFmpeg live progress: {stage_name}, duration={total_duration:.1f}s")

    try:
        process = await asyncio.create_subprocess_exec(
            *modified_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True
        )

        start_time = time.time()
        last_update_time = 0
        stderr_lines = []
        current_progress = {}

        async def read_stderr():
            """Read stderr for error messages"""
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                stderr_lines.append(line.decode('utf-8', errors='ignore').strip())

        # Start reading stderr in background
        stderr_task = asyncio.create_task(read_stderr())

        # Read stdout for progress updates
        try:
            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    process.kill()
                    await process.wait()
                    return False, f"FFmpeg timed out after {timeout} seconds"

                # Read progress line
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Check if process ended
                    if process.returncode is not None:
                        break
                    continue

                if not line:
                    break

                line_text = line.decode('utf-8', errors='ignore').strip()

                # Parse structured progress output
                # Format: key=value
                if '=' in line_text:
                    key, _, value = line_text.partition('=')
                    current_progress[key] = value

                    # When we get 'progress=continue' or 'progress=end', emit update
                    if key == 'progress':
                        now = time.time()
                        if progress_callback and (now - last_update_time >= update_interval or value == 'end'):
                            last_update_time = now

                            # Parse out_time to get current position
                            out_time = current_progress.get('out_time_ms', '0')
                            try:
                                current_time_sec = float(out_time) / 1000000.0
                            except (ValueError, TypeError):
                                current_time_sec = 0

                            # Calculate progress percentage
                            progress_pct = min(100, int((current_time_sec / total_duration) * 100)) if total_duration > 0 else 0

                            # Get speed
                            speed_str = current_progress.get('speed', '0x').replace('x', '').strip()
                            try:
                                speed = float(speed_str) if speed_str and speed_str != 'N/A' else 1.0
                            except ValueError:
                                speed = 1.0

                            # Calculate ETA
                            elapsed = now - start_time
                            if speed > 0 and current_time_sec > 0:
                                remaining_duration = total_duration - current_time_sec
                                eta_seconds = remaining_duration / speed
                            else:
                                eta_seconds = 0

                            progress_info = {
                                'progress': progress_pct,
                                'current_time': current_time_sec,
                                'total_duration': total_duration,
                                'speed': speed,
                                'eta_seconds': eta_seconds,
                                'eta_formatted': FFmpegProgressTracker.format_eta(eta_seconds),
                                'stage': stage_name,
                                'fps': current_progress.get('fps', 'N/A'),
                                'bitrate': current_progress.get('bitrate', 'N/A'),
                                'frame': current_progress.get('frame', '0'),
                                'size': current_progress.get('total_size', '0'),
                            }

                            try:
                                if asyncio.iscoroutinefunction(progress_callback):
                                    await progress_callback(progress_info)
                                else:
                                    progress_callback(progress_info)
                            except Exception as e:
                                logger.warning(f"Progress callback error: {e}")

                        # Clear progress dict for next update cycle
                        if value == 'continue':
                            current_progress = {}

        except Exception as e:
            logger.warning(f"Error reading FFmpeg progress: {e}")

        # Wait for stderr reader and process to finish
        await stderr_task
        await process.wait()

        if process.returncode == 0:
            # Send final 100% progress
            if progress_callback:
                final_info = {
                    'progress': 100,
                    'current_time': total_duration,
                    'total_duration': total_duration,
                    'speed': 0,
                    'eta_seconds': 0,
                    'eta_formatted': '0s',
                    'stage': stage_name,
                    'completed': True
                }
                try:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(final_info)
                    else:
                        progress_callback(final_info)
                except Exception:
                    pass
            return True, ""
        else:
            error_text = '\n'.join(stderr_lines[-20:]) if stderr_lines else "Unknown error"
            return False, error_text

    except Exception as e:
        logger.error(f"Error running FFmpeg with live progress: {e}")
        return False, str(e)


class FFmpegUtils:
    """Wraps proven FFmpeg commands from existing system"""

    # Cache for detected hardware encoder
    _detected_encoder = None
    _encoder_detection_done = False

    # Software fallback presets (always available)
    SOFTWARE_PRESETS = {
        'lossless': {
            'codec': 'libx264',
            'crf': 1,               # CRF 1 for near-lossless (CRF 0 requires high444 profile which isn't QuickTime compatible)
            'preset': 'veryslow',
            'audio_bitrate': '320k',
            'profile': 'high',      # QuickTime compatible
            'pix_fmt': 'yuv420p'    # Required for compatibility
        },
        'high': {
            'codec': 'libx264',
            'crf': 18,
            'preset': 'slow',
            'audio_bitrate': '256k',
            'profile': 'high',      # QuickTime compatible
            'pix_fmt': 'yuv420p'    # Required for compatibility
        },
        'balanced': {
            'codec': 'libx264',
            'crf': 23,
            'preset': 'medium',
            'audio_bitrate': '192k',
            'profile': 'high',      # QuickTime compatible
            'pix_fmt': 'yuv420p'    # Required for compatibility
        }
    }

    # Hardware encoder presets - keyed by encoder name
    HARDWARE_PRESETS = {
        # Apple VideoToolbox (macOS) - uses quality-based encoding
        'h264_videotoolbox': {
            'lossless': {
                'codec': 'h264_videotoolbox',
                'audio_bitrate': '320k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                # VideoToolbox uses bitrate control, not q:v (q:v is ignored)
                # For near-lossless 1080p: ~100Mbps, for 4K: ~200Mbps
                'crf': None,
                'preset': None,
                'encoder_args': ['-b:v', '100M', '-maxrate', '120M', '-bufsize', '200M', '-allow_sw', '1']
            },
            'high': {
                'codec': 'h264_videotoolbox',
                'audio_bitrate': '256k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                'crf': None,
                'preset': None,
                'encoder_args': ['-b:v', '50M', '-maxrate', '60M', '-bufsize', '100M', '-allow_sw', '1']
            },
            'balanced': {
                'codec': 'h264_videotoolbox',
                'audio_bitrate': '192k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                'crf': None,
                'preset': None,
                'encoder_args': ['-b:v', '25M', '-maxrate', '30M', '-bufsize', '50M', '-allow_sw', '1']
            }
        },
        # NVIDIA NVENC - uses cq (constant quality) mode
        'h264_nvenc': {
            'lossless': {
                'codec': 'h264_nvenc',
                'audio_bitrate': '320k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                'crf': None,
                'preset': None,
                'encoder_args': ['-preset', 'p7', '-tune', 'hq', '-rc', 'constqp', '-qp', '1']
            },
            'high': {
                'codec': 'h264_nvenc',
                'audio_bitrate': '256k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                'crf': None,
                'preset': None,
                'encoder_args': ['-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', '19']
            },
            'balanced': {
                'codec': 'h264_nvenc',
                'audio_bitrate': '192k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                'crf': None,
                'preset': None,
                'encoder_args': ['-preset', 'p4', '-tune', 'hq', '-rc', 'vbr', '-cq', '23']
            }
        },
        # Intel Quick Sync Video - uses global_quality
        'h264_qsv': {
            'lossless': {
                'codec': 'h264_qsv',
                'audio_bitrate': '320k',
                'profile': 'high',
                'pix_fmt': 'nv12',  # QSV prefers nv12
                'crf': None,
                'preset': None,
                'encoder_args': ['-preset', 'veryslow', '-global_quality', '1']
            },
            'high': {
                'codec': 'h264_qsv',
                'audio_bitrate': '256k',
                'profile': 'high',
                'pix_fmt': 'nv12',
                'crf': None,
                'preset': None,
                'encoder_args': ['-preset', 'slow', '-global_quality', '18']
            },
            'balanced': {
                'codec': 'h264_qsv',
                'audio_bitrate': '192k',
                'profile': 'high',
                'pix_fmt': 'nv12',
                'crf': None,
                'preset': None,
                'encoder_args': ['-preset', 'medium', '-global_quality', '23']
            }
        },
        # AMD AMF - uses qp_i/qp_p for quality
        'h264_amf': {
            'lossless': {
                'codec': 'h264_amf',
                'audio_bitrate': '320k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                'crf': None,
                'preset': None,
                'encoder_args': ['-quality', 'quality', '-rc', 'cqp', '-qp_i', '1', '-qp_p', '1']
            },
            'high': {
                'codec': 'h264_amf',
                'audio_bitrate': '256k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                'crf': None,
                'preset': None,
                'encoder_args': ['-quality', 'quality', '-rc', 'vbr_peak', '-qp_i', '18', '-qp_p', '20']
            },
            'balanced': {
                'codec': 'h264_amf',
                'audio_bitrate': '192k',
                'profile': 'high',
                'pix_fmt': 'yuv420p',
                'crf': None,
                'preset': None,
                'encoder_args': ['-quality', 'balanced', '-rc', 'vbr_peak', '-qp_i', '23', '-qp_p', '25']
            }
        },
        # VAAPI (Linux) - uses qp for quality
        'h264_vaapi': {
            'lossless': {
                'codec': 'h264_vaapi',
                'audio_bitrate': '320k',
                'profile': 'high',
                'pix_fmt': 'vaapi',
                'crf': None,
                'preset': None,
                'encoder_args': ['-qp', '1']
            },
            'high': {
                'codec': 'h264_vaapi',
                'audio_bitrate': '256k',
                'profile': 'high',
                'pix_fmt': 'vaapi',
                'crf': None,
                'preset': None,
                'encoder_args': ['-qp', '18']
            },
            'balanced': {
                'codec': 'h264_vaapi',
                'audio_bitrate': '192k',
                'profile': 'high',
                'pix_fmt': 'vaapi',
                'crf': None,
                'preset': None,
                'encoder_args': ['-qp', '23']
            }
        }
    }

    # Priority order for hardware encoder detection
    ENCODER_PRIORITY = [
        'h264_videotoolbox',  # macOS - Apple Silicon / Intel with VideoToolbox
        'h264_nvenc',         # NVIDIA GPU
        'h264_qsv',           # Intel Quick Sync
        'h264_amf',           # AMD GPU
        'h264_vaapi',         # Linux VAAPI
    ]

    @classmethod
    def detect_hardware_encoder(cls) -> Optional[str]:
        """
        Detect the best available hardware encoder.
        Results are cached after first detection.

        Returns:
            Encoder name (e.g., 'h264_videotoolbox') or None if only software available
        """
        if cls._encoder_detection_done:
            return cls._detected_encoder

        cls._encoder_detection_done = True

        try:
            # Get list of available encoders from FFmpeg
            cmd = [settings.FFMPEG_PATH, '-hide_banner', '-encoders']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logger.warning("Could not query FFmpeg encoders, using software encoding")
                return None

            available_encoders = result.stdout

            # Check encoders in priority order
            for encoder in cls.ENCODER_PRIORITY:
                if encoder in available_encoders:
                    # Verify encoder actually works with a quick test
                    if cls._test_encoder(encoder):
                        cls._detected_encoder = encoder
                        logger.info(f"Hardware encoder detected: {encoder}")
                        return encoder
                    else:
                        logger.debug(f"Encoder {encoder} listed but failed test, skipping")

            logger.info("No hardware encoder available, using software encoding (libx264)")
            return None

        except subprocess.TimeoutExpired:
            logger.warning("Timeout detecting hardware encoders, using software encoding")
            return None
        except Exception as e:
            logger.warning(f"Error detecting hardware encoders: {e}, using software encoding")
            return None

    @classmethod
    def _test_encoder(cls, encoder: str) -> bool:
        """
        Test if a hardware encoder actually works by encoding a tiny test frame.
        Some systems list encoders that aren't actually functional.
        """
        try:
            # Generate a 1-frame test encode
            cmd = [
                settings.FFMPEG_PATH,
                '-hide_banner',
                '-f', 'lavfi',
                '-i', 'color=black:s=64x64:d=0.04',  # 1 frame at 25fps
                '-c:v', encoder,
                '-f', 'null',
                '-'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    @classmethod
    def get_quality_preset(cls, quality: str) -> dict:
        """
        Get quality preset with hardware acceleration if available.

        Args:
            quality: 'lossless', 'high', or 'balanced'

        Returns:
            Quality settings dict with codec, crf/encoder_args, preset, etc.
        """
        # Detect hardware encoder (cached after first call)
        hw_encoder = cls.detect_hardware_encoder()

        if hw_encoder and hw_encoder in cls.HARDWARE_PRESETS:
            hw_presets = cls.HARDWARE_PRESETS[hw_encoder]
            if quality in hw_presets:
                logger.debug(f"Using hardware encoder {hw_encoder} for {quality} quality")
                return hw_presets[quality]

        # Fallback to software encoding
        logger.debug(f"Using software encoder libx264 for {quality} quality")
        return cls.SOFTWARE_PRESETS.get(quality, cls.SOFTWARE_PRESETS['balanced'])

    # Keep QUALITY_PRESETS as alias for backwards compatibility
    # But this is now just the software presets - use get_quality_preset() for hw acceleration
    QUALITY_PRESETS = SOFTWARE_PRESETS

    @classmethod
    def get_video_encoder_args(cls, quality_settings: dict) -> List[str]:
        """
        Build FFmpeg video encoder arguments from quality settings.
        Handles both software (libx264) and hardware encoders with their specific args.

        Args:
            quality_settings: Dict from get_quality_preset()

        Returns:
            List of FFmpeg arguments for video encoding
        """
        args = []

        # Codec is always required
        args.extend(['-c:v', quality_settings['codec']])

        # Profile (if specified and codec supports it)
        profile = quality_settings.get('profile')
        if profile and quality_settings['codec'] not in ['h264_vaapi']:  # VAAPI doesn't use -profile:v
            args.extend(['-profile:v', profile])

        # Pixel format
        pix_fmt = quality_settings.get('pix_fmt', 'yuv420p')
        # VAAPI needs special handling - pix_fmt is set via hwupload
        if quality_settings['codec'] != 'h264_vaapi':
            args.extend(['-pix_fmt', pix_fmt])

        # Check if this is a hardware encoder with custom args
        encoder_args = quality_settings.get('encoder_args')
        if encoder_args:
            # Hardware encoder - use the custom encoder_args
            args.extend(encoder_args)
        else:
            # Software encoder (libx264) - use crf and preset
            preset = quality_settings.get('preset')
            if preset:
                args.extend(['-preset', preset])

            crf = quality_settings.get('crf')
            if crf is not None:
                args.extend(['-crf', str(crf)])

        return args

    @staticmethod
    def get_media_duration(file_path: str) -> Optional[float]:
        """
        PROVEN: Get media file duration using ffprobe
        From: FFmpeg_Video_Generation_Documentation.md
        """
        try:
            cmd = [
                settings.FFPROBE_PATH,
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                file_path
            ]
            # Add timeout to prevent hang on corrupted files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return float(result.stdout.strip())
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout getting duration for: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error getting duration: {e}")
            return None

    @staticmethod
    def has_audio_stream(video_path: str) -> bool:
        """
        PROVEN: Check if a video file has an audio stream
        From: FFmpeg_Video_Generation_Documentation.md
        """
        try:
            cmd = [
                settings.FFPROBE_PATH,
                '-v', 'quiet',
                '-select_streams', 'a',
                '-show_entries', 'stream=codec_type',
                '-of', 'csv=p=0',
                video_path
            ]
            # Add timeout to prevent hang on corrupted files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0 and 'audio' in result.stdout
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout checking audio stream for: {video_path}")
            return False
        except Exception as e:
            logger.warning(f"Could not determine audio stream info: {e}")
            return False

    @staticmethod
    def get_video_info(video_path: str) -> Optional[dict]:
        """Get video resolution, codec, and format information"""
        import json

        try:
            # Use JSON output for reliable field parsing
            cmd = [
                settings.FFPROBE_PATH,
                '-v', 'quiet',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,pix_fmt,codec_name,r_frame_rate',
                '-of', 'json',
                video_path
            ]
            # Add timeout to prevent hang on corrupted files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)

                if 'streams' in data and len(data['streams']) > 0:
                    stream = data['streams'][0]

                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    pix_fmt = stream.get('pix_fmt', 'yuv420p')
                    codec = stream.get('codec_name', 'unknown')
                    fps_str = stream.get('r_frame_rate', '30/1')

                    # Parse FPS
                    try:
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            fps_val = float(num) / float(den) if float(den) != 0 else 30.0
                        else:
                            fps_val = float(fps_str)
                    except (ValueError, ZeroDivisionError):
                        fps_val = 30.0

                    logger.debug(f"Video info: {width}x{height}, {codec}, {pix_fmt}, {fps_val:.2f}fps")

                    return {
                        'width': width,
                        'height': height,
                        'pix_fmt': pix_fmt,
                        'codec': codec,
                        'fps': round(fps_val, 2)
                    }

            logger.warning(f"FFprobe returned no stream data for: {video_path}")
            return None

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout getting video info for: {video_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse FFprobe JSON output: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None

    @staticmethod
    def add_silent_audio_track(video_path: str, output_path: str) -> bool:
        """
        Add a silent audio track to a video that has no audio

        This is useful for videos without audio streams to ensure compatibility
        when adding TTS voiceovers or background music later in the pipeline.

        Args:
            video_path: Path to input video (without audio)
            output_path: Path to output video (with silent audio)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if video already has audio
            if FFmpegUtils.has_audio_stream(video_path):
                logger.info(f"Video already has audio, no need to add silent track")
                return False

            # Get video duration to match silent audio length
            duration = FFmpegUtils.get_media_duration(video_path)
            if not duration:
                logger.error("Could not get video duration")
                return False

            logger.info(f"Adding silent audio track to video ({duration:.1f}s)")

            # Use anullsrc to generate silent audio matching video duration
            # Copy video stream, encode silent audio
            cmd = [
                settings.FFMPEG_PATH,
                '-i', video_path,
                '-f', 'lavfi',
                '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                '-t', str(duration),
                '-c:v', 'copy',  # Copy video stream (fast, no re-encoding)
                '-c:a', settings.DEFAULT_AUDIO_CODEC,  # Encode silent audio
                '-shortest',  # Match video duration
                '-y',
                output_path
            ]

            # Add timeout to prevent hang (5 minutes should be enough for copy operation)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"✅ Silent audio track added successfully")

                # Verify output has audio
                if FFmpegUtils.has_audio_stream(output_path):
                    logger.info("✅ Output verified to have audio stream")
                    return True
                else:
                    logger.error("❌ Failed to add audio stream")
                    return False
            else:
                logger.error(f"Failed to add silent audio: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout adding silent audio track to: {video_path}")
            return False
        except Exception as e:
            logger.error(f"Error adding silent audio track: {e}")
            return False

    @staticmethod
    def extract_video_segment(
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
        re_encode: bool = False,
        frame_accurate: bool = True
    ) -> bool:
        """
        Extract a video segment from original video

        Args:
            video_path: Source video path
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Output file path
            re_encode: If True, re-encode to ensure compatibility for concatenation.
                      If False, use stream copy (faster but may cause concat issues)
            frame_accurate: If True (default), use filter_complex with trim/setpts for
                          frame-accurate extraction. If False, use -ss before -i (keyframe seek).

        Note: For multi-video exports, use frame_accurate=True and re_encode=True
              to ensure proper A/V sync and clean concatenation.
        """
        import sys
        print(f"[DEBUG] extract_video_segment: {start_time}s-{end_time}s, re_encode={re_encode}, frame_accurate={frame_accurate}", file=sys.stderr, flush=True)
        try:
            duration = end_time - start_time

            if re_encode and frame_accurate:
                # FRAME-ACCURATE EXTRACTION using filter_complex
                # This ensures exact cut points and timestamps starting at 0
                has_audio = FFmpegUtils.has_audio_stream(video_path)

                # Video filter: trim to exact range, reset timestamps
                video_filter = (
                    f"[0:v]trim=start={start_time:.6f}:end={end_time:.6f},"
                    f"setpts=PTS-STARTPTS[outv]"
                )

                if has_audio:
                    # Audio filter: trim to exact range, reset timestamps
                    audio_filter = (
                        f"[0:a]atrim=start={start_time:.6f}:end={end_time:.6f},"
                        f"asetpts=PTS-STARTPTS[outa]"
                    )
                    filter_complex = f"{video_filter};{audio_filter}"
                    map_args = ['-map', '[outv]', '-map', '[outa]']
                else:
                    # Generate silent audio for consistency
                    silent_audio = f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={duration:.6f}[outa]"
                    filter_complex = f"{video_filter};{silent_audio}"
                    map_args = ['-map', '[outv]', '-map', '[outa]']

                cmd = [
                    settings.FFMPEG_PATH,
                    '-i', video_path,
                    '-filter_complex', filter_complex,
                    *map_args,
                    '-c:v', settings.DEFAULT_VIDEO_CODEC,
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-preset', 'fast',
                    '-crf', str(settings.DEFAULT_CRF),
                    '-pix_fmt', 'yuv420p',
                    '-force_key_frames', 'expr:eq(n,0)',  # First frame is keyframe
                    '-ar', '48000',  # Consistent audio sample rate
                    '-y',
                    output_path
                ]
                logger.info(f"Frame-accurate extraction: {start_time:.3f}s - {end_time:.3f}s (duration: {duration:.3f}s)")

            elif re_encode:
                # Re-encode but use input seeking (faster, less accurate)
                has_audio = FFmpegUtils.has_audio_stream(video_path)

                if has_audio:
                    cmd = [
                        settings.FFMPEG_PATH,
                        '-ss', str(start_time),
                        '-i', video_path,
                        '-t', str(duration),
                        '-c:v', settings.DEFAULT_VIDEO_CODEC,
                        '-c:a', settings.DEFAULT_AUDIO_CODEC,
                        '-preset', 'fast',
                        '-crf', str(settings.DEFAULT_CRF),
                        '-pix_fmt', 'yuv420p',
                        '-y',
                        output_path
                    ]
                    logger.info(f"Extracting and re-encoding segment: {start_time:.1f}s - {end_time:.1f}s (duration: {duration:.1f}s)")
                else:
                    cmd = [
                        settings.FFMPEG_PATH,
                        '-ss', str(start_time),
                        '-i', video_path,
                        '-f', 'lavfi',
                        '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
                        '-t', str(duration),
                        '-c:v', settings.DEFAULT_VIDEO_CODEC,
                        '-c:a', settings.DEFAULT_AUDIO_CODEC,
                        '-preset', 'fast',
                        '-crf', str(settings.DEFAULT_CRF),
                        '-pix_fmt', 'yuv420p',
                        '-shortest',
                        '-y',
                        output_path
                    ]
                    logger.info(f"Extracting and re-encoding segment with silent audio: {start_time:.1f}s - {end_time:.1f}s (duration: {duration:.1f}s)")
            else:
                # Fast stream copy (not frame-accurate, but fastest)
                cmd = [
                    settings.FFMPEG_PATH,
                    '-ss', str(start_time),
                    '-i', video_path,
                    '-t', str(duration),
                    '-c', 'copy',
                    '-y',
                    output_path
                ]
                logger.info(f"Extracting segment (stream copy): {start_time:.1f}s - {end_time:.1f}s")

            # Add timeout to prevent hang (10 minutes for segment extraction)
            print(f"[DEBUG] extract_video_segment: running FFmpeg...", file=sys.stderr, flush=True)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            print(f"[DEBUG] extract_video_segment: FFmpeg returned {result.returncode}", file=sys.stderr, flush=True)

            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Extracted segment: {start_time}s - {end_time}s")
                return True
            else:
                logger.error(f"Failed to extract segment: {result.stderr}")
                print(f"[DEBUG] extract_video_segment FAILED: {result.stderr[:200] if result.stderr else 'no error'}", file=sys.stderr, flush=True)
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout extracting segment: {start_time}s - {end_time}s")
            print(f"[DEBUG] extract_video_segment TIMEOUT!", file=sys.stderr, flush=True)
            return False
        except Exception as e:
            logger.error(f"Error extracting segment: {e}")
            return False

    @staticmethod
    def process_segment_video(
        video_path: str,
        audio_path: str,
        subtitle_path: Optional[str],
        output_path: str,
        quality: str = "balanced",
        expected_duration: Optional[float] = None
    ) -> bool:
        """
        PROVEN: Combine video, TTS audio, and subtitles
        From: FFmpeg_Video_Generation_Documentation.md

        Args:
            video_path: Path to video segment
            audio_path: Path to TTS audio (voice-over)
            subtitle_path: Optional path to ASS subtitle file
            output_path: Path to save processed video
            quality: Quality preset (lossless, high, balanced)
            expected_duration: Expected output duration (segment duration)
                              If provided, output will match this duration
        """
        import sys
        print(f"[DEBUG] process_segment_video START: video={video_path}, audio={audio_path}", file=sys.stderr, flush=True)
        try:
            # Get durations
            print(f"[DEBUG] Getting video duration...", file=sys.stderr, flush=True)
            video_duration = FFmpegUtils.get_media_duration(video_path)
            print(f"[DEBUG] Getting audio duration...", file=sys.stderr, flush=True)
            audio_duration = FFmpegUtils.get_media_duration(audio_path)
            print(f"[DEBUG] Durations: video={video_duration}, audio={audio_duration}", file=sys.stderr, flush=True)

            if not video_duration or not audio_duration:
                logger.error("Could not get video/audio duration")
                return False

            # Use expected duration if provided, otherwise use video duration
            target_duration = expected_duration if expected_duration else video_duration

            logger.info(f"Video: {video_duration:.1f}s, Audio: {audio_duration:.1f}s, Target: {target_duration:.1f}s")

            # Check if original video has audio
            has_video_audio = FFmpegUtils.has_audio_stream(video_path)

            # Quality settings
            crf_map = {
                "lossless": settings.LOSSLESS_CRF,
                "high": settings.HIGH_CRF,
                "balanced": settings.BALANCED_CRF
            }
            crf = crf_map.get(quality, settings.DEFAULT_CRF)

            # Build filter_complex based on audio presence
            # Use PROVEN pattern from documentation - simple and fast
            if has_video_audio:
                # Mix video audio with TTS audio
                # amix automatically handles different durations - no need for apad!
                # duration=first means output duration = first input (video)
                audio_filter = "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                logger.info("Mixing video audio + TTS audio")
            else:
                # Video has no audio, use only TTS audio
                # Just copy TTS audio as output audio
                audio_filter = "[1:a]anull[aout]"
                logger.info("Using only TTS audio (no video audio)")

            # Build command with subtitles if provided
            if subtitle_path and os.path.exists(subtitle_path):
                # WITH SUBTITLES
                # Escape ASS path for FFmpeg filter syntax
                ass_path_escaped = escape_ffmpeg_filter_path(subtitle_path)

                command = [
                    settings.FFMPEG_PATH,
                    '-i', video_path,
                    '-i', audio_path,
                    '-vf', f'ass={ass_path_escaped}',
                    '-filter_complex', audio_filter,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', settings.DEFAULT_VIDEO_CODEC,
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-preset', settings.DEFAULT_PRESET,
                    '-crf', str(crf),
                    '-y',
                    output_path
                ]
                logger.info("Processing with subtitles and voice-over")
            else:
                # WITHOUT SUBTITLES
                command = [
                    settings.FFMPEG_PATH,
                    '-i', video_path,
                    '-i', audio_path,
                    '-filter_complex', audio_filter,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', settings.DEFAULT_VIDEO_CODEC,
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-preset', settings.DEFAULT_PRESET,
                    '-crf', str(crf),
                    '-y',
                    output_path
                ]
                logger.info("Processing with voice-over (no subtitles)")

            # Add timeout to prevent hanging (5 minutes max for any segment)
            print(f"[DEBUG] Running FFmpeg command...", file=sys.stderr, flush=True)
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes timeout
                )
                print(f"[DEBUG] FFmpeg returned: {result.returncode}", file=sys.stderr, flush=True)
            except subprocess.TimeoutExpired:
                logger.error(f"FFmpeg processing timed out after 300 seconds")
                print(f"[DEBUG] FFmpeg TIMEOUT!", file=sys.stderr, flush=True)
                return False

            if result.returncode == 0 and os.path.exists(output_path):
                output_duration = FFmpegUtils.get_media_duration(output_path)
                file_size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"Segment processed: {output_duration:.1f}s, {file_size:.1f}MB")
                return True
            else:
                logger.error(f"Processing failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error processing segment: {e}")
            return False

    @staticmethod
    def concatenate_videos(video_paths: List[str], output_path: str) -> bool:
        """
        PROVEN: Concatenate multiple videos
        From: FFmpeg_Video_Generation_Documentation.md
        """
        try:
            # Create concat file
            concat_file = Path(settings.TEMP_DIR) / "concat_list.txt"

            with open(concat_file, 'w') as f:
                for video_path in video_paths:
                    # Escape path for FFmpeg concat demuxer (handles special chars)
                    escaped_path = escape_concat_path(video_path)
                    f.write(f"file '{escaped_path}'\n")

            logger.info(f"Concatenating {len(video_paths)} videos")

            cmd = [
                settings.FFMPEG_PATH,
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                '-y',
                output_path
            ]

            # Add timeout to prevent hang (10 minutes for concatenation)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0 and os.path.exists(output_path):
                duration = FFmpegUtils.get_media_duration(output_path)
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"Concatenation successful: {duration:.2f}s, {size:.1f}MB")
                return True
            else:
                logger.error(f"Concatenation failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Concatenation timed out after 600 seconds")
            return False
        except Exception as e:
            logger.error(f"Error concatenating videos: {e}")
            return False

    @staticmethod
    def add_background_music(
        video_path: str,
        music_path: str,
        output_path: str,
        tts_boost: Optional[float] = None,
        bgm_reduction: Optional[float] = None,
        fade_duration: Optional[float] = None
    ) -> bool:
        """
        PROVEN: Add looping background music with fade effects
        From: FFmpeg_Video_Generation_Documentation.md

        Args:
            video_path: Path to input video
            music_path: Path to background music
            output_path: Path to output video
            tts_boost: TTS volume boost in dB (default from settings)
            bgm_reduction: BGM volume reduction in dB (default from settings)
            fade_duration: Fade out duration in seconds (default from settings)
        """
        try:
            if not os.path.exists(music_path):
                logger.error(f"Music file not found: {music_path}")
                return False

            # Get durations
            video_duration = FFmpegUtils.get_media_duration(video_path)
            music_duration = FFmpegUtils.get_media_duration(music_path)

            if not video_duration or not music_duration:
                logger.error("Could not get durations")
                return False

            # Use provided values or defaults from settings
            if fade_duration is None:
                fade_duration = settings.FADE_DURATION
            if tts_boost is None:
                tts_boost = settings.TTS_VOLUME_BOOST
            if bgm_reduction is None:
                bgm_reduction = settings.BGM_VOLUME_REDUCTION

            # Check if video has audio with detailed debugging
            has_audio = FFmpegUtils.has_audio_stream(video_path)

            # Additional debug: Get detailed stream info
            try:
                probe_cmd = [
                    settings.FFPROBE_PATH,
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_streams',
                    video_path
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                if probe_result.returncode == 0:
                    import json
                    probe_data = json.loads(probe_result.stdout)
                    audio_streams = [s for s in probe_data.get('streams', []) if s.get('codec_type') == 'audio']
                    logger.info(f"🔍 Video stream analysis:")
                    logger.info(f"   - Audio streams detected: {len(audio_streams)}")
                    if audio_streams:
                        for i, stream in enumerate(audio_streams):
                            logger.info(f"   - Stream {i}: {stream.get('codec_name', 'unknown')} @ {stream.get('sample_rate', 'unknown')}Hz")
            except Exception as e:
                logger.warning(f"Could not get detailed stream info: {e}")

            logger.info(f"🎚️ Volume adjustments: TTS +{tts_boost}dB, BGM -{bgm_reduction}dB")

            # Calculate loops needed
            if video_duration > music_duration:
                loops_needed = int((video_duration / music_duration) + 1)
            else:
                loops_needed = 0

            logger.info(f"🔄 Background music loops needed: {loops_needed}")

            # Build filter based on whether video has audio
            if has_audio:
                # Video has audio - mix it with background music
                # Based on proven reference implementation (cl_vid_gen_2.py lines 859-878)
                # +3dB TTS boost, -16dB BGM reduction = 19dB difference favoring speech
                # duration=first means output duration matches first input (video)
                # dropout_transition=0 prevents sudden transitions
                if loops_needed > 0:
                    filter_complex = (
                        f"[0:a]volume=+{tts_boost}dB[boosted_video];"
                        f"[1:a]aloop=loop={loops_needed}:size={int(music_duration * 44100)},"
                        f"volume=-{bgm_reduction}dB,"
                        f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration},"
                        f"atrim=duration={video_duration}[bg];"
                        f"[boosted_video][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                    )
                else:
                    filter_complex = (
                        f"[0:a]volume=+{tts_boost}dB[boosted_video];"
                        f"[1:a]volume=-{bgm_reduction}dB,"
                        f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration},"
                        f"atrim=duration={video_duration}[bg];"
                        f"[boosted_video][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                    )
                logger.info("🎵 Mixing video audio (TTS) with background music")
                logger.info(f"   TTS boost: +{tts_boost}dB | BGM reduction: -{bgm_reduction}dB")
                logger.info(f"   This creates a {tts_boost + bgm_reduction}dB difference favoring TTS")
                logger.info(f"   Using duration=first to match video duration (reference: cl_vid_gen.py:901)")
            else:
                # Video has no audio - just add background music
                if loops_needed > 0:
                    filter_complex = (
                        f"[1:a]aloop=loop={loops_needed}:size={int(music_duration * 44100)},"
                        f"volume=-{bgm_reduction}dB,"
                        f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration},"
                        f"atrim=duration={video_duration}[aout]"
                    )
                else:
                    filter_complex = (
                        f"[1:a]volume=-{bgm_reduction}dB,"
                        f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration},"
                        f"atrim=duration={video_duration}[aout]"
                    )
                logger.info("🎵 Adding background music (video has no audio)")

            cmd = [
                settings.FFMPEG_PATH,
                '-i', video_path,
                '-i', music_path,
                '-filter_complex', filter_complex,
                '-map', '0:v',
                '-map', '[aout]',
                '-c:v', 'copy',
                '-c:a', settings.DEFAULT_AUDIO_CODEC,
                '-y',
                output_path
            ]

            logger.info("Adding background music with fade effects")
            logger.info(f"🎛️ Filter complex: {filter_complex}")
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            # Add timeout to prevent hang (15 minutes for BGM mixing)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

            if result.returncode == 0 and os.path.exists(output_path):
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"✅ Background music added successfully: {size:.1f}MB")

                # Verify output has audio
                output_has_audio = FFmpegUtils.has_audio_stream(output_path)
                if output_has_audio:
                    logger.info("✅ Output video verified to have audio stream")
                else:
                    logger.error("⚠️ WARNING: Output video has no audio stream!")

                # Get detailed audio info
                try:
                    probe_cmd = [
                        settings.FFPROBE_PATH,
                        '-v', 'quiet',
                        '-print_format', 'json',
                        '-show_streams',
                        '-select_streams', 'a',
                        output_path
                    ]
                    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                    if probe_result.returncode == 0:
                        import json
                        probe_data = json.loads(probe_result.stdout)
                        audio_streams = probe_data.get('streams', [])
                        if audio_streams:
                            for i, stream in enumerate(audio_streams):
                                codec = stream.get('codec_name', 'unknown')
                                sample_rate = stream.get('sample_rate', 'unknown')
                                channels = stream.get('channels', 'unknown')
                                logger.info(f"   Output audio stream {i}: {codec} @ {sample_rate}Hz, {channels} channels")
                        else:
                            logger.warning("   No audio streams found in output")
                except Exception as e:
                    logger.warning(f"Could not probe output audio: {e}")

                return True
            else:
                logger.error(f"❌ Failed to add background music")
                logger.error(f"FFmpeg stderr: {result.stderr}")

                # Log the input file info for debugging
                logger.error(f"Input video path: {video_path}")
                logger.error(f"Input video had audio: {has_audio}")
                logger.error(f"Music path: {music_path}")

                return False

        except subprocess.TimeoutExpired:
            logger.error("Adding background music timed out after 900 seconds")
            return False
        except Exception as e:
            logger.error(f"Error adding background music: {e}")
            return False

    @staticmethod
    def add_multiple_bgm_tracks(
        video_path: str,
        bgm_tracks: list,
        output_path: str,
        video_duration: float,
        global_tts_volume: int = 100,
        global_bgm_volume: int = 100
    ) -> bool:
        """
        Add multiple background music tracks with individual time ranges, volumes, and fade effects.

        Uses PROVEN pattern from add_background_music for reliable audio mixing.

        Args:
            video_path: Path to input video (with TTS audio already mixed)
            bgm_tracks: List of BGMTrack objects with:
                - path: Audio file path
                - start_time: Start time in video (seconds)
                - end_time: End time in video (0 = until end)
                - volume: Track volume (0-200%)
                - fade_in: Fade in duration (seconds)
                - fade_out: Fade out duration (seconds)
                - loop: Whether to loop audio
                - muted: Whether track is muted
            output_path: Output video path
            video_duration: Video duration in seconds
            global_tts_volume: Global TTS volume (0-200%)
            global_bgm_volume: Global BGM volume (0-200%)

        Returns:
            True if successful
        """
        import math

        try:
            # Filter out muted tracks and tracks with no path
            active_tracks = [t for t in bgm_tracks if not t.muted and t.path and os.path.exists(t.path)]

            if not active_tracks:
                logger.info("No active BGM tracks to process")
                import shutil
                shutil.copy(video_path, output_path)
                return True

            logger.info(f"🎵 Processing {len(active_tracks)} BGM track(s)")
            for i, track in enumerate(active_tracks):
                logger.info(f"   Track {i+1}: {track.name} - {track.path}")
                logger.info(f"            Time: {track.start_time}s - {track.end_time}s, Volume: {track.volume}%, Loop: {track.loop}")

            # Use PROVEN volume settings from add_background_music
            tts_boost = settings.TTS_VOLUME_BOOST  # Default: 15
            bgm_reduction = settings.BGM_VOLUME_REDUCTION  # Default: 20
            fade_duration = settings.FADE_DURATION  # Default: 3.0

            # Apply global volume adjustments
            if global_tts_volume != 100 and global_tts_volume > 0:
                tts_adjustment = 20 * math.log10(global_tts_volume / 100)
                tts_boost = tts_boost + tts_adjustment

            if global_bgm_volume != 100 and global_bgm_volume > 0:
                bgm_adjustment = 20 * math.log10(global_bgm_volume / 100)
                bgm_reduction = bgm_reduction - bgm_adjustment

            logger.info(f"🎚️ Global volume: TTS={global_tts_volume}% (+{tts_boost:.1f}dB), BGM={global_bgm_volume}% (-{bgm_reduction:.1f}dB)")

            has_audio = FFmpegUtils.has_audio_stream(video_path)
            logger.info(f"🔍 Input video has audio stream: {has_audio}")

            # If only one BGM track, use the proven simple approach
            if len(active_tracks) == 1:
                track = active_tracks[0]
                music_path = track.path
                music_duration = FFmpegUtils.get_media_duration(music_path)

                if not music_duration:
                    logger.error(f"Could not get duration for: {music_path}")
                    return False

                # Calculate effective time range
                # IMPORTANT: Cap end_time at video_duration to prevent BGM extending beyond video
                start_time = track.start_time
                if track.end_time > 0:
                    end_time = min(track.end_time, video_duration)
                else:
                    end_time = video_duration
                track_duration = end_time - start_time

                # Validate track range
                if track_duration <= 0:
                    logger.warning(f"Invalid BGM track range: start={start_time}, end={end_time}, video_duration={video_duration}")
                    import shutil
                    shutil.copy(video_path, output_path)
                    return True

                # Apply track-specific volume adjustment
                if track.volume != 100 and track.volume > 0:
                    track_volume_adjustment = 20 * math.log10(track.volume / 100)
                    effective_bgm_reduction = bgm_reduction - track_volume_adjustment
                else:
                    effective_bgm_reduction = bgm_reduction

                track_fade_out = track.fade_out if track.fade_out > 0 else fade_duration

                # Calculate loops needed
                if track.loop and track_duration > music_duration:
                    loops_needed = int((track_duration / music_duration) + 1)
                else:
                    loops_needed = 0

                logger.info(f"🎵 Single track mode: {track.name}")
                logger.info(f"   Duration: {track_duration:.1f}s, Music: {music_duration:.1f}s, Loops: {loops_needed}")
                logger.info(f"   Effective BGM reduction: -{effective_bgm_reduction:.1f}dB")

                # Build filter using PROVEN pattern
                # Handle start_time positioning for tracks that don't start at 0
                track_fade_in = track.fade_in if track.fade_in > 0 else 0

                if has_audio:
                    # Build BGM filter chain
                    bgm_filter_parts = []

                    if loops_needed > 0:
                        bgm_filter_parts.append(f"aloop=loop={loops_needed}:size={int(music_duration * 44100)}")

                    bgm_filter_parts.append(f"volume=-{effective_bgm_reduction:.1f}dB")

                    if track_fade_in > 0:
                        bgm_filter_parts.append(f"afade=t=in:st=0:d={track_fade_in:.1f}")

                    # Fade out relative to track duration
                    fade_out_start = track_duration - track_fade_out
                    if fade_out_start > 0:
                        bgm_filter_parts.append(f"afade=t=out:st={fade_out_start:.1f}:d={track_fade_out:.1f}")

                    bgm_filter_parts.append(f"atrim=duration={track_duration:.3f}")

                    # Position at start_time if not starting at 0
                    if start_time > 0:
                        bgm_filter_parts.append(f"adelay={int(start_time * 1000)}|{int(start_time * 1000)}")
                        # Note: apad removed - amix=duration=first handles duration correctly

                    bgm_filter = ','.join(bgm_filter_parts)

                    filter_complex = (
                        f"[0:a]volume=+{tts_boost:.1f}dB[boosted_video];"
                        f"[1:a]{bgm_filter}[bg];"
                        f"[boosted_video][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                    )
                    logger.info("🎵 Mixing TTS audio with background music (PROVEN pattern)")
                    if start_time > 0:
                        logger.info(f"   BGM positioned at {start_time:.1f}s using adelay")
                else:
                    # Build BGM filter chain for video without audio
                    bgm_filter_parts = []

                    if loops_needed > 0:
                        bgm_filter_parts.append(f"aloop=loop={loops_needed}:size={int(music_duration * 44100)}")

                    bgm_filter_parts.append(f"volume=-{effective_bgm_reduction:.1f}dB")

                    if track_fade_in > 0:
                        bgm_filter_parts.append(f"afade=t=in:st=0:d={track_fade_in:.1f}")

                    # Fade out relative to track duration
                    fade_out_start = track_duration - track_fade_out
                    if fade_out_start > 0:
                        bgm_filter_parts.append(f"afade=t=out:st={fade_out_start:.1f}:d={track_fade_out:.1f}")

                    bgm_filter_parts.append(f"atrim=duration={track_duration:.3f}")

                    # Position at start_time if not starting at 0
                    if start_time > 0:
                        bgm_filter_parts.append(f"adelay={int(start_time * 1000)}|{int(start_time * 1000)}")
                        # Note: apad removed - amix=duration=first handles duration correctly

                    bgm_filter = ','.join(bgm_filter_parts)
                    filter_complex = f"[1:a]{bgm_filter}[aout]"

                    logger.info("🎵 Adding background music only (no TTS audio in video)")
                    if start_time > 0:
                        logger.info(f"   BGM positioned at {start_time:.1f}s using adelay")

                cmd = [
                    settings.FFMPEG_PATH,
                    '-i', video_path,
                    '-i', music_path,
                    '-filter_complex', filter_complex,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', 'copy',
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-y',
                    output_path
                ]

                logger.info(f"🎛️ Filter complex: {filter_complex}")

            else:
                # Multiple BGM tracks - build complex filter
                logger.info(f"🎵 Multi-track mode: {len(active_tracks)} tracks")

                inputs = ['-i', video_path]
                for track in active_tracks:
                    inputs.extend(['-i', track.path])

                filter_parts = []
                bgm_labels = []

                if has_audio:
                    filter_parts.append(f"[0:a]volume=+{tts_boost:.1f}dB[tts]")

                for i, track in enumerate(active_tracks):
                    input_idx = i + 1
                    # IMPORTANT: Cap end_time at video_duration to prevent BGM extending beyond video
                    start_time = track.start_time
                    if track.end_time > 0:
                        end_time = min(track.end_time, video_duration)
                    else:
                        end_time = video_duration
                    track_range_duration = end_time - start_time

                    if track_range_duration <= 0:
                        logger.warning(f"Skipping track {track.name}: invalid time range (start={start_time}, end={end_time})")
                        continue

                    music_duration = FFmpegUtils.get_media_duration(track.path)
                    if not music_duration:
                        continue

                    if track.volume != 100 and track.volume > 0:
                        track_volume_adjustment = 20 * math.log10(track.volume / 100)
                        effective_reduction = bgm_reduction - track_volume_adjustment
                    else:
                        effective_reduction = bgm_reduction

                    track_fade_out = track.fade_out if track.fade_out > 0 else fade_duration
                    track_fade_in = track.fade_in if track.fade_in > 0 else 0

                    track_filter_parts = []

                    if track.loop and music_duration < track_range_duration:
                        loops_needed = int((track_range_duration / music_duration) + 1)
                        track_filter_parts.append(f"aloop=loop={loops_needed}:size={int(music_duration * 44100)}")

                    track_filter_parts.append(f"volume=-{effective_reduction:.1f}dB")

                    if track_fade_in > 0:
                        track_filter_parts.append(f"afade=t=in:st=0:d={track_fade_in:.1f}")

                    fade_out_start = track_range_duration - track_fade_out
                    if fade_out_start > 0:
                        track_filter_parts.append(f"afade=t=out:st={fade_out_start:.1f}:d={track_fade_out:.1f}")

                    track_filter_parts.append(f"atrim=duration={track_range_duration:.3f}")

                    if start_time > 0:
                        track_filter_parts.append(f"adelay={int(start_time * 1000)}|{int(start_time * 1000)}")
                        # Note: apad removed - amix=duration=first handles duration correctly

                    filter_chain = ','.join(track_filter_parts)
                    filter_parts.append(f"[{input_idx}:a]{filter_chain}[bgm{i}]")
                    bgm_labels.append(f'[bgm{i}]')

                    logger.info(f"   Track {i+1} ({track.name}): {start_time:.1f}s-{end_time:.1f}s, vol=-{effective_reduction:.1f}dB")

                if has_audio and bgm_labels:
                    all_inputs = '[tts]' + ''.join(bgm_labels)
                    total_inputs = 1 + len(bgm_labels)
                    filter_parts.append(f"{all_inputs}amix=inputs={total_inputs}:duration=first:dropout_transition=0[aout]")
                elif bgm_labels:
                    if len(bgm_labels) > 1:
                        all_inputs = ''.join(bgm_labels)
                        filter_parts.append(f"{all_inputs}amix=inputs={len(bgm_labels)}:duration=longest:dropout_transition=0[aout]")
                    else:
                        last_filter = filter_parts[-1]
                        filter_parts[-1] = last_filter.replace('[bgm0]', '[aout]')
                elif has_audio:
                    filter_parts.append("[tts]acopy[aout]")
                else:
                    logger.error("No audio sources to process")
                    return False

                filter_complex = ';'.join(filter_parts)

                cmd = [
                    settings.FFMPEG_PATH,
                    *inputs,
                    '-filter_complex', filter_complex,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', 'copy',
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-y',
                    output_path
                ]

                logger.info(f"🎛️ Filter complex: {filter_complex}")

            logger.info(f"🎬 Running FFmpeg to add BGM tracks...")
            # Add timeout to prevent hang (15 minutes for multi-BGM mixing)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

            if result.returncode == 0 and os.path.exists(output_path):
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"✅ Multi-BGM tracks added successfully: {size:.1f}MB")

                output_has_audio = FFmpegUtils.has_audio_stream(output_path)
                if output_has_audio:
                    logger.info("✅ Output video verified to have audio stream")
                else:
                    logger.error("⚠️ WARNING: Output video has no audio stream!")

                return True
            else:
                logger.error(f"❌ Failed to add BGM tracks")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Adding multiple BGM tracks timed out after 900 seconds")
            return False
        except Exception as e:
            logger.error(f"Error adding multiple BGM tracks: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    async def concatenate_videos_async(
        video_paths: List[str],
        output_path: str,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Concatenate multiple videos with progress tracking.

        Args:
            video_paths: List of video file paths to concatenate
            output_path: Output file path
            progress_callback: Async callback for progress updates
        """
        try:
            # Calculate total duration
            total_duration = 0
            for video_path in video_paths:
                duration = FFmpegUtils.get_media_duration(video_path)
                if duration:
                    total_duration += duration

            if total_duration == 0:
                logger.error("Could not calculate total duration")
                return False

            # Create concat file
            concat_file = Path(settings.TEMP_DIR) / "concat_list.txt"

            with open(concat_file, 'w') as f:
                for video_path in video_paths:
                    # Escape path for FFmpeg concat demuxer (handles special chars)
                    escaped_path = escape_concat_path(video_path)
                    f.write(f"file '{escaped_path}'\n")

            logger.info(f"Concatenating {len(video_paths)} videos (total: {total_duration:.1f}s)")

            cmd = [
                settings.FFMPEG_PATH,
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                '-y',
                output_path
            ]

            success, error = await run_ffmpeg_with_live_progress(
                cmd,
                total_duration,
                progress_callback,
                "Concatenating segments",
                timeout=600
            )

            if success and os.path.exists(output_path):
                duration = FFmpegUtils.get_media_duration(output_path)
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"Concatenation successful: {duration:.2f}s, {size:.1f}MB")
                return True
            else:
                logger.error(f"Concatenation failed: {error}")
                return False

        except Exception as e:
            logger.error(f"Error concatenating videos: {e}")
            return False

    @staticmethod
    async def add_background_music_async(
        video_path: str,
        music_path: str,
        output_path: str,
        tts_boost: Optional[float] = None,
        bgm_reduction: Optional[float] = None,
        fade_duration: Optional[float] = None,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Add background music with progress tracking.

        Args:
            video_path: Input video path
            music_path: Background music path
            output_path: Output video path
            tts_boost: TTS volume boost in dB
            bgm_reduction: BGM volume reduction in dB
            fade_duration: Fade out duration
            progress_callback: Async callback for progress updates
        """
        try:
            if not os.path.exists(music_path):
                logger.error(f"Music file not found: {music_path}")
                return False

            video_duration = FFmpegUtils.get_media_duration(video_path)
            music_duration = FFmpegUtils.get_media_duration(music_path)

            if not video_duration or not music_duration:
                logger.error("Could not get durations")
                return False

            # Use provided values or defaults
            if fade_duration is None:
                fade_duration = settings.FADE_DURATION
            if tts_boost is None:
                tts_boost = settings.TTS_VOLUME_BOOST
            if bgm_reduction is None:
                bgm_reduction = settings.BGM_VOLUME_REDUCTION

            has_audio = FFmpegUtils.has_audio_stream(video_path)

            # Calculate loops needed
            if video_duration > music_duration:
                loops_needed = int((video_duration / music_duration) + 1)
            else:
                loops_needed = 0

            # Build filter
            if has_audio:
                if loops_needed > 0:
                    filter_complex = (
                        f"[0:a]volume=+{tts_boost}dB[boosted_video];"
                        f"[1:a]aloop=loop={loops_needed}:size={int(music_duration * 44100)},"
                        f"volume=-{bgm_reduction}dB,"
                        f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration},"
                        f"atrim=duration={video_duration}[bg];"
                        f"[boosted_video][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                    )
                else:
                    filter_complex = (
                        f"[0:a]volume=+{tts_boost}dB[boosted_video];"
                        f"[1:a]volume=-{bgm_reduction}dB,"
                        f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration},"
                        f"atrim=duration={video_duration}[bg];"
                        f"[boosted_video][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                    )
            else:
                if loops_needed > 0:
                    filter_complex = (
                        f"[1:a]aloop=loop={loops_needed}:size={int(music_duration * 44100)},"
                        f"volume=-{bgm_reduction}dB,"
                        f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration},"
                        f"atrim=duration={video_duration}[aout]"
                    )
                else:
                    filter_complex = (
                        f"[1:a]volume=-{bgm_reduction}dB,"
                        f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration},"
                        f"atrim=duration={video_duration}[aout]"
                    )

            cmd = [
                settings.FFMPEG_PATH,
                '-i', video_path,
                '-i', music_path,
                '-filter_complex', filter_complex,
                '-map', '0:v',
                '-map', '[aout]',
                '-c:v', 'copy',
                '-c:a', settings.DEFAULT_AUDIO_CODEC,
                '-y',
                output_path
            ]

            logger.info("Adding background music with fade effects")

            success, error = await run_ffmpeg_with_live_progress(
                cmd,
                video_duration,
                progress_callback,
                "Adding background music",
                timeout=600
            )

            if success and os.path.exists(output_path):
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"✅ Background music added successfully: {size:.1f}MB")
                return True
            else:
                logger.error(f"❌ Failed to add background music: {error}")
                return False

        except Exception as e:
            logger.error(f"Error adding background music: {e}")
            return False

    @staticmethod
    async def add_multiple_bgm_tracks_async(
        video_path: str,
        bgm_tracks: list,
        output_path: str,
        video_duration: float,
        global_tts_volume: int = 100,
        global_bgm_volume: int = 100,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Add multiple BGM tracks with progress tracking.

        Uses PROVEN pattern from add_background_music_async for reliable audio mixing.

        Args:
            video_path: Input video path
            bgm_tracks: List of BGMTrack objects
            output_path: Output video path
            video_duration: Total video duration
            global_tts_volume: Global TTS volume (0-200%)
            global_bgm_volume: Global BGM volume (0-200%)
            progress_callback: Async callback for progress updates
        """
        import math

        try:
            # Filter out muted tracks and tracks with no path
            active_tracks = [t for t in bgm_tracks if not t.muted and t.path and os.path.exists(t.path)]

            if not active_tracks:
                logger.info("No active BGM tracks to process")
                import shutil
                shutil.copy(video_path, output_path)
                return True

            logger.info(f"🎵 Processing {len(active_tracks)} BGM track(s)")
            for i, track in enumerate(active_tracks):
                logger.info(f"   Track {i+1}: {track.name} - {track.path}")
                logger.info(f"            Time: {track.start_time}s - {track.end_time}s, Volume: {track.volume}%, Loop: {track.loop}")

            # Use PROVEN volume settings from add_background_music (the working console version)
            # TTS boost: +15dB (makes speech clearly audible)
            # BGM reduction: -20dB (keeps music as background)
            tts_boost = settings.TTS_VOLUME_BOOST  # Default: 15
            bgm_reduction = settings.BGM_VOLUME_REDUCTION  # Default: 20
            fade_duration = settings.FADE_DURATION  # Default: 3.0

            # Apply global volume adjustments
            # For TTS: 100% = default, 50% = -6dB, 200% = +6dB
            if global_tts_volume != 100 and global_tts_volume > 0:
                tts_adjustment = 20 * math.log10(global_tts_volume / 100)
                tts_boost = tts_boost + tts_adjustment

            # For BGM: 100% = default reduction, 50% = more reduction, 200% = less reduction
            if global_bgm_volume != 100 and global_bgm_volume > 0:
                bgm_adjustment = 20 * math.log10(global_bgm_volume / 100)
                bgm_reduction = bgm_reduction - bgm_adjustment

            logger.info(f"🎚️ Global volume: TTS={global_tts_volume}% (+{tts_boost:.1f}dB), BGM={global_bgm_volume}% (-{bgm_reduction:.1f}dB)")

            has_audio = FFmpegUtils.has_audio_stream(video_path)
            logger.info(f"🔍 Input video has audio stream: {has_audio}")

            # For simplicity with multiple tracks, we'll process them one by one
            # This is more reliable than complex filter chains

            # If only one BGM track, use the proven simple approach
            if len(active_tracks) == 1:
                track = active_tracks[0]
                music_path = track.path
                music_duration = FFmpegUtils.get_media_duration(music_path)

                if not music_duration:
                    logger.error(f"Could not get duration for: {music_path}")
                    return False

                # Calculate effective time range for this track
                # IMPORTANT: Cap end_time at video_duration to prevent BGM extending beyond video
                start_time = track.start_time
                if track.end_time > 0:
                    end_time = min(track.end_time, video_duration)
                else:
                    end_time = video_duration
                track_duration = end_time - start_time

                # Validate track range
                if track_duration <= 0:
                    logger.warning(f"Invalid BGM track range: start={start_time}, end={end_time}, video_duration={video_duration}")
                    import shutil
                    shutil.copy(video_path, output_path)
                    return True

                # Apply track-specific volume adjustment
                if track.volume != 100 and track.volume > 0:
                    track_volume_adjustment = 20 * math.log10(track.volume / 100)
                    effective_bgm_reduction = bgm_reduction - track_volume_adjustment
                else:
                    effective_bgm_reduction = bgm_reduction

                # Get track-specific fade settings
                track_fade_out = track.fade_out if track.fade_out > 0 else fade_duration
                track_fade_in = track.fade_in if track.fade_in > 0 else 0

                # Calculate loops needed
                if track.loop and track_duration > music_duration:
                    loops_needed = int((track_duration / music_duration) + 1)
                else:
                    loops_needed = 0

                logger.info(f"🎵 Single track mode: {track.name}")
                logger.info(f"   Duration: {track_duration:.1f}s, Music: {music_duration:.1f}s, Loops: {loops_needed}")
                logger.info(f"   Effective BGM reduction: -{effective_bgm_reduction:.1f}dB")

                # Build filter using PROVEN pattern from add_background_music
                # Handle start_time positioning for tracks that don't start at 0

                if has_audio:
                    # Video has TTS audio - mix it with background music
                    # Build BGM filter chain
                    bgm_filter_parts = []

                    if loops_needed > 0:
                        bgm_filter_parts.append(f"aloop=loop={loops_needed}:size={int(music_duration * 44100)}")

                    bgm_filter_parts.append(f"volume=-{effective_bgm_reduction:.1f}dB")

                    if track_fade_in > 0:
                        bgm_filter_parts.append(f"afade=t=in:st=0:d={track_fade_in:.1f}")

                    # Fade out relative to track duration
                    fade_out_start = track_duration - track_fade_out
                    if fade_out_start > 0:
                        bgm_filter_parts.append(f"afade=t=out:st={fade_out_start:.1f}:d={track_fade_out:.1f}")

                    bgm_filter_parts.append(f"atrim=duration={track_duration:.3f}")

                    # Position at start_time if not starting at 0
                    if start_time > 0:
                        bgm_filter_parts.append(f"adelay={int(start_time * 1000)}|{int(start_time * 1000)}")
                        # Note: apad removed - amix=duration=first handles duration correctly

                    bgm_filter = ','.join(bgm_filter_parts)

                    filter_complex = (
                        f"[0:a]volume=+{tts_boost:.1f}dB[boosted_video];"
                        f"[1:a]{bgm_filter}[bg];"
                        f"[boosted_video][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                    )
                    logger.info("🎵 Mixing TTS audio with background music (PROVEN pattern)")
                    if start_time > 0:
                        logger.info(f"   BGM positioned at {start_time:.1f}s using adelay")
                else:
                    # Video has no audio - just add background music
                    # Build BGM filter chain
                    bgm_filter_parts = []

                    if loops_needed > 0:
                        bgm_filter_parts.append(f"aloop=loop={loops_needed}:size={int(music_duration * 44100)}")

                    bgm_filter_parts.append(f"volume=-{effective_bgm_reduction:.1f}dB")

                    if track_fade_in > 0:
                        bgm_filter_parts.append(f"afade=t=in:st=0:d={track_fade_in:.1f}")

                    # Fade out relative to track duration
                    fade_out_start = track_duration - track_fade_out
                    if fade_out_start > 0:
                        bgm_filter_parts.append(f"afade=t=out:st={fade_out_start:.1f}:d={track_fade_out:.1f}")

                    bgm_filter_parts.append(f"atrim=duration={track_duration:.3f}")

                    # Position at start_time if not starting at 0
                    if start_time > 0:
                        bgm_filter_parts.append(f"adelay={int(start_time * 1000)}|{int(start_time * 1000)}")
                        # Note: apad removed - amix=duration=first handles duration correctly

                    bgm_filter = ','.join(bgm_filter_parts)
                    filter_complex = f"[1:a]{bgm_filter}[aout]"

                    logger.info("🎵 Adding background music only (no TTS audio in video)")
                    if start_time > 0:
                        logger.info(f"   BGM positioned at {start_time:.1f}s using adelay")

                cmd = [
                    settings.FFMPEG_PATH,
                    '-i', video_path,
                    '-i', music_path,
                    '-filter_complex', filter_complex,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', 'copy',
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-y',
                    output_path
                ]

                logger.info(f"🎛️ Filter complex: {filter_complex}")

            else:
                # Multiple BGM tracks - build complex filter
                logger.info(f"🎵 Multi-track mode: {len(active_tracks)} tracks")

                # Build inputs list
                inputs = ['-i', video_path]
                for track in active_tracks:
                    inputs.extend(['-i', track.path])

                # Build filter complex
                filter_parts = []
                bgm_labels = []

                # Process video audio first (if exists)
                if has_audio:
                    filter_parts.append(f"[0:a]volume=+{tts_boost:.1f}dB[tts]")

                # Process each BGM track
                for i, track in enumerate(active_tracks):
                    input_idx = i + 1  # +1 because video is input 0

                    # Calculate effective time range
                    # IMPORTANT: Cap end_time at video_duration to prevent BGM extending beyond video
                    start_time = track.start_time
                    if track.end_time > 0:
                        end_time = min(track.end_time, video_duration)
                    else:
                        end_time = video_duration
                    track_range_duration = end_time - start_time

                    if track_range_duration <= 0:
                        logger.warning(f"Skipping track {track.name}: invalid time range (start={start_time}, end={end_time})")
                        continue

                    # Get music duration
                    music_duration = FFmpegUtils.get_media_duration(track.path)
                    if not music_duration:
                        logger.warning(f"Skipping track {track.name}: could not get duration")
                        continue

                    # Calculate track volume
                    if track.volume != 100 and track.volume > 0:
                        track_volume_adjustment = 20 * math.log10(track.volume / 100)
                        effective_reduction = bgm_reduction - track_volume_adjustment
                    else:
                        effective_reduction = bgm_reduction

                    # Get fade settings
                    track_fade_out = track.fade_out if track.fade_out > 0 else fade_duration
                    track_fade_in = track.fade_in if track.fade_in > 0 else 0

                    # Build filter chain for this track
                    track_filter_parts = []

                    # Loop if needed
                    if track.loop and music_duration < track_range_duration:
                        loops_needed = int((track_range_duration / music_duration) + 1)
                        track_filter_parts.append(f"aloop=loop={loops_needed}:size={int(music_duration * 44100)}")

                    # Apply volume reduction
                    track_filter_parts.append(f"volume=-{effective_reduction:.1f}dB")

                    # Fade in (at the start)
                    if track_fade_in > 0:
                        track_filter_parts.append(f"afade=t=in:st=0:d={track_fade_in:.1f}")

                    # Fade out (at the end of track range)
                    fade_out_start = track_range_duration - track_fade_out
                    if fade_out_start > 0:
                        track_filter_parts.append(f"afade=t=out:st={fade_out_start:.1f}:d={track_fade_out:.1f}")

                    # Trim to track range duration
                    track_filter_parts.append(f"atrim=duration={track_range_duration:.3f}")

                    # Add delay to position track at correct start time (if not starting at 0)
                    if start_time > 0:
                        track_filter_parts.append(f"adelay={int(start_time * 1000)}|{int(start_time * 1000)}")
                        # Note: apad removed - amix=duration=first handles duration correctly

                    # Build complete filter for this track
                    filter_chain = ','.join(track_filter_parts)
                    filter_parts.append(f"[{input_idx}:a]{filter_chain}[bgm{i}]")
                    bgm_labels.append(f'[bgm{i}]')

                    logger.info(f"   Track {i+1} ({track.name}): {start_time:.1f}s-{end_time:.1f}s, vol=-{effective_reduction:.1f}dB")

                # Build final mix
                if has_audio and bgm_labels:
                    # Mix TTS with all BGM tracks
                    all_inputs = '[tts]' + ''.join(bgm_labels)
                    total_inputs = 1 + len(bgm_labels)
                    filter_parts.append(f"{all_inputs}amix=inputs={total_inputs}:duration=first:dropout_transition=0[aout]")
                elif bgm_labels:
                    # Only BGM tracks (no TTS)
                    if len(bgm_labels) > 1:
                        all_inputs = ''.join(bgm_labels)
                        filter_parts.append(f"{all_inputs}amix=inputs={len(bgm_labels)}:duration=longest:dropout_transition=0[aout]")
                    else:
                        # Single BGM track - just rename output
                        last_filter = filter_parts[-1]
                        filter_parts[-1] = last_filter.replace('[bgm0]', '[aout]')
                elif has_audio:
                    # Only TTS audio (no valid BGM tracks)
                    filter_parts.append("[tts]acopy[aout]")
                else:
                    logger.error("No audio sources to process")
                    return False

                filter_complex = ';'.join(filter_parts)

                cmd = [
                    settings.FFMPEG_PATH,
                    *inputs,
                    '-filter_complex', filter_complex,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', 'copy',
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-y',
                    output_path
                ]

                logger.info(f"🎛️ Filter complex: {filter_complex}")

            logger.info(f"🎬 Running FFmpeg to add BGM tracks...")

            success, error = await run_ffmpeg_with_live_progress(
                cmd,
                video_duration,
                progress_callback,
                "Adding background music",
                timeout=600
            )

            if success and os.path.exists(output_path):
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"✅ Multi-BGM tracks added successfully: {size:.1f}MB")

                # Verify output has audio
                output_has_audio = FFmpegUtils.has_audio_stream(output_path)
                if output_has_audio:
                    logger.info("✅ Output video verified to have audio stream")
                else:
                    logger.error("⚠️ WARNING: Output video has no audio stream!")

                return True
            else:
                logger.error(f"❌ Failed to add BGM tracks: {error}")
                return False

        except Exception as e:
            logger.error(f"Error adding multiple BGM tracks: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    async def extract_video_segment_async(
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
        re_encode: bool = False,
        progress_callback: Optional[Callable] = None,
        frame_accurate: bool = True
    ) -> bool:
        """
        Extract a video segment from original video - ASYNC version

        This version uses asyncio subprocess to avoid blocking the event loop.

        Args:
            video_path: Source video path
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Output file path
            re_encode: If True, re-encode to ensure compatibility for concatenation.
                      If False, use stream copy (faster but may cause concat issues)
            progress_callback: Optional async callback for progress updates
            frame_accurate: If True (default), use filter_complex with trim/setpts for
                          frame-accurate extraction. If False, use -ss before -i (keyframe seek).

        Note: For multi-video exports, use frame_accurate=True and re_encode=True
              to ensure proper A/V sync and clean concatenation.
        """
        import sys
        print(f"[DEBUG] extract_video_segment_async: {start_time}s-{end_time}s, re_encode={re_encode}, frame_accurate={frame_accurate}", file=sys.stderr, flush=True)
        try:
            duration = end_time - start_time

            if re_encode and frame_accurate:
                # FRAME-ACCURATE EXTRACTION using filter_complex
                # This ensures exact cut points and timestamps starting at 0
                has_audio = FFmpegUtils.has_audio_stream(video_path)

                # Video filter: trim to exact range, reset timestamps
                video_filter = (
                    f"[0:v]trim=start={start_time:.6f}:end={end_time:.6f},"
                    f"setpts=PTS-STARTPTS[outv]"
                )

                if has_audio:
                    # Audio filter: trim to exact range, reset timestamps
                    audio_filter = (
                        f"[0:a]atrim=start={start_time:.6f}:end={end_time:.6f},"
                        f"asetpts=PTS-STARTPTS[outa]"
                    )
                    filter_complex = f"{video_filter};{audio_filter}"
                    map_args = ['-map', '[outv]', '-map', '[outa]']
                else:
                    # Generate silent audio for consistency
                    silent_audio = f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={duration:.6f}[outa]"
                    filter_complex = f"{video_filter};{silent_audio}"
                    map_args = ['-map', '[outv]', '-map', '[outa]']

                cmd = [
                    settings.FFMPEG_PATH,
                    '-i', video_path,
                    '-filter_complex', filter_complex,
                    *map_args,
                    '-c:v', settings.DEFAULT_VIDEO_CODEC,
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-preset', 'fast',
                    '-crf', str(settings.DEFAULT_CRF),
                    '-pix_fmt', 'yuv420p',
                    '-force_key_frames', 'expr:eq(n,0)',  # First frame is keyframe
                    '-ar', '48000',  # Consistent audio sample rate
                    '-y',
                    output_path
                ]
                logger.info(f"Frame-accurate extraction async: {start_time:.3f}s - {end_time:.3f}s (duration: {duration:.3f}s)")

            elif re_encode:
                # Re-encode but use input seeking (faster, less accurate)
                has_audio = FFmpegUtils.has_audio_stream(video_path)

                if has_audio:
                    cmd = [
                        settings.FFMPEG_PATH,
                        '-ss', str(start_time),
                        '-i', video_path,
                        '-t', str(duration),
                        '-c:v', settings.DEFAULT_VIDEO_CODEC,
                        '-c:a', settings.DEFAULT_AUDIO_CODEC,
                        '-preset', 'fast',
                        '-crf', str(settings.DEFAULT_CRF),
                        '-pix_fmt', 'yuv420p',
                        '-y',
                        output_path
                    ]
                    logger.info(f"Extracting and re-encoding segment async: {start_time:.1f}s - {end_time:.1f}s (duration: {duration:.1f}s)")
                else:
                    cmd = [
                        settings.FFMPEG_PATH,
                        '-ss', str(start_time),
                        '-i', video_path,
                        '-f', 'lavfi',
                        '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
                        '-t', str(duration),
                        '-c:v', settings.DEFAULT_VIDEO_CODEC,
                        '-c:a', settings.DEFAULT_AUDIO_CODEC,
                        '-preset', 'fast',
                        '-crf', str(settings.DEFAULT_CRF),
                        '-pix_fmt', 'yuv420p',
                        '-shortest',
                        '-y',
                        output_path
                    ]
                    logger.info(f"Extracting and re-encoding segment async with silent audio: {start_time:.1f}s - {end_time:.1f}s")
            else:
                # Fast stream copy (not frame-accurate, but fastest)
                cmd = [
                    settings.FFMPEG_PATH,
                    '-ss', str(start_time),
                    '-i', video_path,
                    '-t', str(duration),
                    '-c', 'copy',
                    '-y',
                    output_path
                ]
                logger.info(f"Extracting segment async (stream copy): {start_time:.1f}s - {end_time:.1f}s")

            print(f"[DEBUG] extract_video_segment_async: running FFmpeg...", file=sys.stderr, flush=True)

            success, error = await run_ffmpeg_with_live_progress(
                cmd,
                duration,
                progress_callback,
                f"Extracting {start_time:.1f}s-{end_time:.1f}s",
                timeout=600
            )

            print(f"[DEBUG] extract_video_segment_async: FFmpeg returned success={success}", file=sys.stderr, flush=True)

            if success and os.path.exists(output_path):
                logger.info(f"Extracted segment async: {start_time}s - {end_time}s")
                return True
            else:
                logger.error(f"Failed to extract segment async: {error}")
                print(f"[DEBUG] extract_video_segment_async FAILED: {error[:200] if error else 'no error'}", file=sys.stderr, flush=True)
                return False

        except Exception as e:
            logger.error(f"Error extracting segment async: {e}")
            print(f"[DEBUG] extract_video_segment_async EXCEPTION: {e}", file=sys.stderr, flush=True)
            return False

    @staticmethod
    async def process_segment_video_async(
        video_path: str,
        audio_path: str,
        subtitle_path: Optional[str],
        output_path: str,
        quality: str = "balanced",
        expected_duration: Optional[float] = None,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        ASYNC version: Combine video, TTS audio, and subtitles

        This version uses asyncio subprocess to avoid blocking the event loop.

        Args:
            video_path: Path to video segment
            audio_path: Path to TTS audio (voice-over)
            subtitle_path: Optional path to ASS subtitle file
            output_path: Path to save processed video
            quality: Quality preset (lossless, high, balanced)
            expected_duration: Expected output duration (segment duration)
            progress_callback: Optional async callback for progress updates
        """
        import sys
        print(f"[DEBUG] process_segment_video_async START: video={video_path}, audio={audio_path}", file=sys.stderr, flush=True)
        try:
            # Get durations
            print(f"[DEBUG] Getting video duration...", file=sys.stderr, flush=True)
            video_duration = FFmpegUtils.get_media_duration(video_path)
            print(f"[DEBUG] Getting audio duration...", file=sys.stderr, flush=True)
            audio_duration = FFmpegUtils.get_media_duration(audio_path)
            print(f"[DEBUG] Durations: video={video_duration}, audio={audio_duration}", file=sys.stderr, flush=True)

            if not video_duration or not audio_duration:
                logger.error("Could not get video/audio duration")
                return False

            # Use expected duration if provided, otherwise use video duration
            target_duration = expected_duration if expected_duration else video_duration

            logger.info(f"Video: {video_duration:.1f}s, Audio: {audio_duration:.1f}s, Target: {target_duration:.1f}s")

            # Check if original video has audio
            has_video_audio = FFmpegUtils.has_audio_stream(video_path)

            # Quality settings
            crf_map = {
                "lossless": settings.LOSSLESS_CRF,
                "high": settings.HIGH_CRF,
                "balanced": settings.BALANCED_CRF
            }
            crf = crf_map.get(quality, settings.DEFAULT_CRF)

            # Build filter_complex based on audio presence
            if has_video_audio:
                audio_filter = "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                logger.info("Mixing video audio + TTS audio")
            else:
                audio_filter = "[1:a]anull[aout]"
                logger.info("Using only TTS audio (no video audio)")

            # Build command with subtitles if provided
            if subtitle_path and os.path.exists(subtitle_path):
                ass_path_escaped = escape_ffmpeg_filter_path(subtitle_path)

                command = [
                    settings.FFMPEG_PATH,
                    '-i', video_path,
                    '-i', audio_path,
                    '-vf', f'ass={ass_path_escaped}',
                    '-filter_complex', audio_filter,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', settings.DEFAULT_VIDEO_CODEC,
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-preset', settings.DEFAULT_PRESET,
                    '-crf', str(crf),
                    '-y',
                    output_path
                ]
                logger.info("Processing async with subtitles and voice-over")
            else:
                command = [
                    settings.FFMPEG_PATH,
                    '-i', video_path,
                    '-i', audio_path,
                    '-filter_complex', audio_filter,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', settings.DEFAULT_VIDEO_CODEC,
                    '-c:a', settings.DEFAULT_AUDIO_CODEC,
                    '-preset', settings.DEFAULT_PRESET,
                    '-crf', str(crf),
                    '-y',
                    output_path
                ]
                logger.info("Processing async with voice-over (no subtitles)")

            print(f"[DEBUG] Running FFmpeg command async...", file=sys.stderr, flush=True)

            success, error = await run_ffmpeg_with_live_progress(
                command,
                target_duration,
                progress_callback,
                "Processing segment",
                timeout=300
            )

            print(f"[DEBUG] FFmpeg async returned: success={success}", file=sys.stderr, flush=True)

            if success and os.path.exists(output_path):
                output_duration = FFmpegUtils.get_media_duration(output_path)
                file_size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"Segment processed async: {output_duration:.1f}s, {file_size:.1f}MB")
                return True
            else:
                logger.error(f"Processing async failed: {error}")
                return False

        except Exception as e:
            logger.error(f"Error processing segment async: {e}")
            return False
