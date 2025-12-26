"""Subtitle utilities - Proven patterns from existing system"""

import subprocess
import os
from typing import Dict, Optional
from utils.logger import logger
from config import settings


class SubtitleUtils:
    """Wraps proven subtitle styling patterns from existing system"""

    # Language-specific fonts (from existing system)
    LANGUAGE_FONTS = {
        'en': 'Roboto',
        'english': 'Roboto',
        'hi': 'Noto Sans Devanagari',
        'hindi': 'Noto Sans Devanagari',
        'ta': 'Noto Sans Tamil',
        'tamil': 'Noto Sans Tamil',
        'te': 'Noto Sans Telugu',
        'telugu': 'Noto Sans Telugu',
        'kn': 'Noto Sans Kannada',
        'kannada': 'Noto Sans Kannada',
        'ml': 'Noto Sans Malayalam',
        'malayalam': 'Noto Sans Malayalam',
        'ko': 'Noto Sans KR',
        'korean': 'Noto Sans KR',
        'fr': 'Roboto',
        'french': 'Roboto',
    }

    @staticmethod
    def convert_srt_to_ass(srt_path: str, ass_path: str) -> bool:
        """
        PROVEN: Convert SRT subtitle file to ASS format using FFmpeg
        From: FFmpeg_Video_Generation_Documentation.md
        """
        try:
            # Validate SRT file exists and has content
            if not os.path.exists(srt_path):
                logger.error(f"SRT file not found: {srt_path}")
                return False

            # Check if SRT file is empty
            if os.path.getsize(srt_path) == 0:
                logger.error(f"SRT file is empty: {srt_path}")
                return False

            # Read and validate SRT content
            try:
                with open(srt_path, 'r', encoding='utf-8') as f:
                    srt_content = f.read().strip()
                    if not srt_content:
                        logger.error(f"SRT file has no content: {srt_path}")
                        return False
            except Exception as e:
                logger.error(f"Cannot read SRT file: {e}")
                return False

            cmd = [
                settings.FFMPEG_PATH,
                '-i', srt_path,
                '-y',
                ass_path
            ]

            logger.info(f"Converting SRT to ASS: {srt_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if os.path.exists(ass_path):
                logger.info("SRT to ASS conversion completed")
                return True
            else:
                logger.error("ASS file not created")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"SRT to ASS conversion failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error converting SRT to ASS: {e}")
            return False

    @staticmethod
    def get_language_specific_font(language: str) -> str:
        """Get appropriate font for language"""
        return SubtitleUtils.LANGUAGE_FONTS.get(
            language.lower(),
            'Arial'
        )

    @staticmethod
    def create_custom_ass_style(
        srt_path: str,
        ass_path: str,
        style_options: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        PROVEN: Convert SRT to ASS with custom styling
        From: FFmpeg_Video_Generation_Documentation.md
        """
        # Default style
        default_style = {
            'fontname': 'Roboto',
            'fontsize': '20',
            'primarycolour': '&H00FFFFFF',  # White
            'secondarycolour': '&H000000FF',  # Red
            'outlinecolour': '&H00000000',  # Black outline
            'backcolour': '&H80000000',  # Semi-transparent black background
            'bold': '-1',
            'italic': '0',
            'underline': '0',
            'strikeout': '0',
            'scalex': '100',
            'scaley': '100',
            'spacing': '0',
            'angle': '0',
            'borderstyle': '1',
            'outline': '0.5',  # Reduced from 1 to 0.5 for thinner border
            'shadow': '0',
            'alignment': '2',  # Bottom center
            'marginl': '10',
            'marginr': '10',
            'marginv': '30'
        }

        # Update with custom options
        if style_options:
            default_style.update(style_options)

        # First convert SRT to basic ASS
        if not SubtitleUtils.convert_srt_to_ass(srt_path, ass_path):
            return False

        # Read the generated ASS file
        try:
            with open(ass_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Build style line
            style_line = (
                f"Style: Default,{default_style['fontname']},{default_style['fontsize']},"
                f"{default_style['primarycolour']},{default_style['secondarycolour']},"
                f"{default_style['outlinecolour']},{default_style['backcolour']},"
                f"{default_style['bold']},{default_style['italic']},{default_style['underline']},"
                f"{default_style['strikeout']},{default_style['scalex']},{default_style['scaley']},"
                f"{default_style['spacing']},{default_style['angle']},{default_style['borderstyle']},"
                f"{default_style['outline']},{default_style['shadow']},{default_style['alignment']},"
                f"{default_style['marginl']},{default_style['marginr']},{default_style['marginv']},0"
            )

            # Find and replace the style line
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('Style: Default,'):
                    lines[i] = style_line
                    break

            # Write back the modified content
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            logger.info("Custom ASS styling applied")
            return True

        except Exception as e:
            logger.error(f"Error applying custom styling: {e}")
            return False

    @staticmethod
    def get_default_style_for_language(language: str) -> Dict[str, str]:
        """
        Get default subtitle style for a language
        Based on proven patterns from existing system
        """
        font = SubtitleUtils.get_language_specific_font(language)

        return {
            'fontname': font,
            'fontsize': '20',
            'primarycolour': '&H00FFFFFF',  # White
            'secondarycolour': '&H000000FF',  # Red
            'outlinecolour': '&H00000000',  # Black outline
            'backcolour': '&H80000000',  # Semi-transparent black
            'bold': '-1',
            'italic': '0',
            'underline': '0',
            'strikeout': '0',
            'scalex': '100',
            'scaley': '100',
            'spacing': '0',
            'angle': '0',
            'borderstyle': '1',
            'outline': '0.5',  # Reduced from 1 to 0.5 for thinner border
            'shadow': '0',
            'alignment': '2',  # Bottom center
            'marginl': '10',
            'marginr': '10',
            'marginv': '30'  # For landscape videos
        }

    @staticmethod
    def adjust_subtitle_for_audio_offset(
        subtitle_path: str,
        audio_offset: float,
        segment_duration: float,
        output_path: str
    ) -> Optional[str]:
        """
        Adjust subtitle timing when audio is trimmed from start.

        When audio_offset > 0, the audio starts later in the file, so subtitles
        need to be shifted earlier by that amount (and trimmed to segment duration).

        Args:
            subtitle_path: Path to original subtitle file (SRT or ASS)
            audio_offset: Seconds to skip from start of audio
            segment_duration: Duration of the segment on timeline
            output_path: Path for adjusted subtitle file

        Returns:
            Path to adjusted subtitle file, or None on failure
        """
        try:
            if not os.path.exists(subtitle_path):
                logger.warning(f"Subtitle file not found: {subtitle_path}")
                return None

            # Read the subtitle file
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()

            is_ass = subtitle_path.lower().endswith('.ass')

            if is_ass:
                adjusted = SubtitleUtils._adjust_ass_timing(content, audio_offset, segment_duration)
            else:
                adjusted = SubtitleUtils._adjust_srt_timing(content, audio_offset, segment_duration)

            if adjusted:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(adjusted)
                logger.info(f"Adjusted subtitle timing: offset={audio_offset:.3f}s, duration={segment_duration:.3f}s")
                return output_path

            return None

        except Exception as e:
            logger.error(f"Failed to adjust subtitle timing: {e}")
            return None

    @staticmethod
    def _parse_srt_time(time_str: str) -> float:
        """Parse SRT timestamp (HH:MM:SS,mmm) to seconds"""
        time_str = time_str.strip()
        parts = time_str.replace(',', '.').split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """Format seconds to SRT timestamp (HH:MM:SS,mmm)"""
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

    @staticmethod
    def _parse_ass_time(time_str: str) -> float:
        """Parse ASS timestamp (H:MM:SS.cc) to seconds"""
        time_str = time_str.strip()
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        """Format seconds to ASS timestamp (H:MM:SS.cc)"""
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    @staticmethod
    def _adjust_srt_timing(content: str, audio_offset: float, segment_duration: float) -> Optional[str]:
        """Adjust SRT subtitle timing"""
        import re

        # Pattern for SRT timestamp line: 00:00:01,000 --> 00:00:03,500
        timestamp_pattern = re.compile(
            r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})'
        )

        lines = content.split('\n')
        adjusted_lines = []
        subtitle_index = 1
        skip_until_next_index = False

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if this is a subtitle index line
            if line.strip().isdigit():
                # Next line should be timestamp
                if i + 1 < len(lines):
                    timestamp_match = timestamp_pattern.match(lines[i + 1])
                    if timestamp_match:
                        start_time = SubtitleUtils._parse_srt_time(timestamp_match.group(1))
                        end_time = SubtitleUtils._parse_srt_time(timestamp_match.group(2))

                        # Adjust times by subtracting audio_offset
                        new_start = start_time - audio_offset
                        new_end = end_time - audio_offset

                        # Skip subtitles that end before the segment starts
                        if new_end <= 0:
                            # Skip this subtitle entry
                            skip_until_next_index = True
                            i += 1
                            continue

                        # Clamp to segment duration
                        new_start = max(0, new_start)
                        new_end = min(new_end, segment_duration)

                        # Skip if start is past segment duration
                        if new_start >= segment_duration:
                            skip_until_next_index = True
                            i += 1
                            continue

                        # Add adjusted subtitle
                        adjusted_lines.append(str(subtitle_index))
                        adjusted_lines.append(
                            f"{SubtitleUtils._format_srt_time(new_start)} --> {SubtitleUtils._format_srt_time(new_end)}"
                        )
                        subtitle_index += 1
                        skip_until_next_index = False
                        i += 2  # Skip index and timestamp lines

                        # Add text lines until empty line
                        while i < len(lines) and lines[i].strip():
                            adjusted_lines.append(lines[i])
                            i += 1
                        adjusted_lines.append('')  # Empty line separator
                        continue

            if not skip_until_next_index:
                # Keep non-timestamp lines as-is (for headers, etc.)
                pass

            i += 1

        return '\n'.join(adjusted_lines) if adjusted_lines else None

    @staticmethod
    def _adjust_ass_timing(content: str, audio_offset: float, segment_duration: float) -> Optional[str]:
        """Adjust ASS subtitle timing"""
        import re

        lines = content.split('\n')
        adjusted_lines = []

        # Pattern for Dialogue line: Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,Text
        dialogue_pattern = re.compile(
            r'^(Dialogue:\s*\d+,)(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2})(,.*)$'
        )

        for line in lines:
            match = dialogue_pattern.match(line)
            if match:
                prefix = match.group(1)
                start_time = SubtitleUtils._parse_ass_time(match.group(2))
                end_time = SubtitleUtils._parse_ass_time(match.group(3))
                suffix = match.group(4)

                # Adjust times
                new_start = start_time - audio_offset
                new_end = end_time - audio_offset

                # Skip if ends before segment starts
                if new_end <= 0:
                    continue

                # Clamp to segment duration
                new_start = max(0, new_start)
                new_end = min(new_end, segment_duration)

                # Skip if starts after segment ends
                if new_start >= segment_duration:
                    continue

                # Build adjusted line
                adjusted_line = (
                    f"{prefix}{SubtitleUtils._format_ass_time(new_start)},"
                    f"{SubtitleUtils._format_ass_time(new_end)}{suffix}"
                )
                adjusted_lines.append(adjusted_line)
            else:
                # Keep non-dialogue lines (headers, styles, etc.)
                adjusted_lines.append(line)

        return '\n'.join(adjusted_lines)
