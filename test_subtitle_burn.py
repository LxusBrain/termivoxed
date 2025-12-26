#!/usr/bin/env python3
"""
Test script for debugging subtitle burning in multi-video exports.
This script provides detailed logging of what FFmpeg is doing.
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from models.project import Project
from core.layer_compositor import LayerCompositor
from backend.ffmpeg_utils import FFmpegUtils
from config import settings

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(msg, color=Colors.ENDC):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Colors.CYAN}[{timestamp}]{Colors.ENDC} {color}{msg}{Colors.ENDC}")

def log_section(title):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{title}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}\n")

async def test_subtitle_burning(project_name: str = "Check3"):
    """Test subtitle burning with detailed logging."""

    log_section(f"SUBTITLE BURN TEST - Project: {project_name}")

    # Step 1: Load project
    log("Loading project...", Colors.BLUE)
    project = Project.load(project_name)
    if not project:
        log(f"ERROR: Could not load project '{project_name}'", Colors.RED)
        return False

    log(f"Project loaded: {project.name} with {len(project.videos)} videos", Colors.GREEN)

    # Step 2: Show all segments (including generic/project-level segments)
    log_section("SEGMENTS IN PROJECT")
    all_segments = []

    # Check generic/project-level segments first
    if hasattr(project, 'generic_segments') and project.generic_segments:
        log(f"Generic/Project-level segments: {len(project.generic_segments)}", Colors.YELLOW)
        for seg in project.generic_segments:
            all_segments.append((seg, None))
            log(f"  [GENERIC] Segment: {seg.name}", Colors.CYAN)
            log(f"    ID: {seg.id}")
            log(f"    video_id: {seg.video_id} (null = project-level)")
            log(f"    Time: {seg.start_time:.2f}s - {seg.end_time:.2f}s")
            log(f"    Text: {seg.text[:50]}..." if len(seg.text) > 50 else f"    Text: {seg.text}")
            log(f"    subtitle_enabled: {seg.subtitle_enabled}", Colors.GREEN if seg.subtitle_enabled else Colors.RED)
            log(f"    subtitle_path: {seg.subtitle_path}")
            if seg.subtitle_path:
                exists = os.path.exists(seg.subtitle_path)
                log(f"    subtitle_path exists: {exists}", Colors.GREEN if exists else Colors.RED)
                if exists:
                    with open(seg.subtitle_path, 'r') as f:
                        content = f.read()[:500]
                    log(f"    Subtitle content preview:\n{content}", Colors.CYAN)
            log("")
    else:
        log("No generic/project-level segments found", Colors.YELLOW)

    # Check video-specific segments
    log(f"\nVideo-specific segments:", Colors.YELLOW)
    for video in project.videos:
        if video.timeline and video.timeline.segments:
            for seg in video.timeline.segments:
                all_segments.append((seg, video))
                log(f"  Video: {video.name}", Colors.YELLOW)
                log(f"    Segment: {seg.name}", Colors.CYAN)
                log(f"    ID: {seg.id}")
                log(f"    Time: {seg.start_time:.2f}s - {seg.end_time:.2f}s")
                log(f"    Text: {seg.text[:50]}..." if len(seg.text) > 50 else f"    Text: {seg.text}")
                log(f"    subtitle_enabled: {seg.subtitle_enabled}", Colors.GREEN if seg.subtitle_enabled else Colors.RED)
                log(f"    subtitle_path: {seg.subtitle_path}")
                if seg.subtitle_path:
                    exists = os.path.exists(seg.subtitle_path)
                    log(f"    subtitle_path exists: {exists}", Colors.GREEN if exists else Colors.RED)
                    if exists:
                        # Show first few lines of subtitle file
                        with open(seg.subtitle_path, 'r') as f:
                            content = f.read()[:500]
                        log(f"    Subtitle content preview:\n{content}", Colors.CYAN)
                log("")

    if not all_segments:
        log("WARNING: No segments found in project!", Colors.RED)

    # Step 3: Build LayerCompositor
    log_section("LAYER COMPOSITOR")
    compositor = LayerCompositor(project)
    if not compositor.build():
        log("ERROR: Failed to build compositor", Colors.RED)
        return False

    log(f"Visibility map: {len(compositor.visibility_map)} segments", Colors.GREEN)
    for i, vis in enumerate(compositor.visibility_map):
        log(f"  [{i}] {vis.video_name}: {vis.timeline_start:.2f}s - {vis.timeline_end:.2f}s")

    log(f"\nSegment placements: {len(compositor.segment_placements)} segments", Colors.GREEN)
    for i, placement in enumerate(compositor.segment_placements):
        log(f"  [{i}] {placement.segment_name}", Colors.YELLOW)
        log(f"      segment_id: {placement.segment_id}")
        log(f"      timeline: {placement.timeline_start:.2f}s - {placement.timeline_end:.2f}s")
        log(f"      subtitle_path: {placement.subtitle_path}")
        if placement.subtitle_path:
            exists = os.path.exists(placement.subtitle_path)
            log(f"      subtitle exists: {exists}", Colors.GREEN if exists else Colors.RED)

    # Step 4: Calculate video_start_offset
    video_start_offset = compositor.visibility_map[0].timeline_start if compositor.visibility_map else 0
    log(f"\nvideo_start_offset: {video_start_offset:.3f}s", Colors.YELLOW)

    # Step 5: Simulate subtitle collection (what _burn_subtitles_by_timeline does)
    log_section("SUBTITLE COLLECTION SIMULATION")

    subtitles_to_burn = []
    for placement in compositor.segment_placements:
        log(f"\nProcessing placement: {placement.segment_name}", Colors.BLUE)

        # Find original segment (check generic segments first, then video-specific)
        original_segment = None

        # Check generic/project-level segments first
        if hasattr(project, 'generic_segments'):
            for segment in project.generic_segments:
                if segment.id == placement.segment_id:
                    original_segment = segment
                    log(f"  Found in generic_segments!", Colors.GREEN)
                    break
                if placement.segment_id.startswith(segment.id):
                    original_segment = segment
                    log(f"  Found in generic_segments (continuation)!", Colors.GREEN)
                    break

        # Then check video-specific segments
        if not original_segment:
            for video in project.videos:
                if video.timeline and video.timeline.segments:
                    for segment in video.timeline.segments:
                        if segment.id == placement.segment_id:
                            original_segment = segment
                            log(f"  Found in video: {video.name}", Colors.GREEN)
                            break
                        if placement.segment_id.startswith(segment.id):
                            original_segment = segment
                            log(f"  Found in video (continuation): {video.name}", Colors.GREEN)
                            break

        if not original_segment:
            log(f"  WARNING: Could not find original segment!", Colors.RED)
            continue

        log(f"  Found original segment: {original_segment.name}", Colors.GREEN)
        log(f"  subtitle_enabled: {original_segment.subtitle_enabled}")

        if not original_segment.subtitle_enabled:
            log(f"  SKIPPING: subtitle_enabled is False", Colors.YELLOW)
            continue

        subtitle_path = placement.subtitle_path or original_segment.subtitle_path
        log(f"  subtitle_path: {subtitle_path}")

        if not subtitle_path:
            log(f"  SKIPPING: No subtitle path", Colors.YELLOW)
            continue

        if not os.path.exists(subtitle_path):
            log(f"  SKIPPING: Subtitle file does not exist!", Colors.RED)
            continue

        adjusted_start = max(0, placement.timeline_start - video_start_offset)
        segment_duration = placement.timeline_end - placement.timeline_start

        log(f"  adjusted_start: {adjusted_start:.3f}s", Colors.GREEN)
        log(f"  segment_duration: {segment_duration:.3f}s", Colors.GREEN)

        subtitles_to_burn.append({
            'subtitle_path': subtitle_path,
            'adjusted_start': adjusted_start,
            'segment': original_segment,
            'duration': segment_duration
        })
        log(f"  ADDED to burn list!", Colors.GREEN)

    log_section("SUBTITLE BURN SUMMARY")
    log(f"Total subtitles to burn: {len(subtitles_to_burn)}", Colors.BOLD)

    if not subtitles_to_burn:
        log("WARNING: No subtitles will be burned!", Colors.RED)
        log("\nPossible causes:", Colors.YELLOW)
        log("  1. subtitle_enabled is False for all segments")
        log("  2. No subtitle_path set on segments")
        log("  3. Subtitle files don't exist")
        return False

    for i, sub in enumerate(subtitles_to_burn):
        log(f"\n  [{i}] {sub['segment'].name}", Colors.CYAN)
        log(f"      Path: {sub['subtitle_path']}")
        log(f"      Adjusted start: {sub['adjusted_start']:.3f}s")
        log(f"      Duration: {sub['duration']:.3f}s")
        log(f"      Font: {sub['segment'].subtitle_font}")
        log(f"      Size: {sub['segment'].subtitle_size}")
        log(f"      Color: {sub['segment'].subtitle_color}")

    # Step 6: Test ASS file creation
    log_section("TEST ASS FILE CREATION")

    temp_dir = Path("storage/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    test_ass_path = temp_dir / "test_combined_subtitles.ass"

    # Create combined ASS file manually for testing
    ass_content = create_test_ass_file(subtitles_to_burn)

    with open(test_ass_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)

    log(f"Created test ASS file: {test_ass_path}", Colors.GREEN)
    log(f"\nASS file content:\n{ass_content}", Colors.CYAN)

    # Step 7: Test FFmpeg subtitle burn command
    log_section("TEST FFMPEG COMMAND")

    # Find a test video to use
    test_video = None
    for video in project.videos:
        if os.path.exists(video.path):
            test_video = video.path
            break

    if not test_video:
        log("ERROR: No valid video file found!", Colors.RED)
        return False

    output_path = temp_dir / "test_subtitle_output.mp4"

    # Escape path for FFmpeg
    escaped_ass_path = str(test_ass_path.resolve()).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")

    cmd = [
        settings.FFMPEG_PATH,
        '-y',
        '-i', test_video,
        '-t', '10',  # Only process 10 seconds for quick test
        '-vf', f"subtitles='{escaped_ass_path}'",
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '28',
        '-c:a', 'copy',
        '-progress', 'pipe:1',  # Output progress to stdout
        str(output_path)
    ]

    log(f"Input video: {test_video}", Colors.BLUE)
    log(f"Output video: {output_path}", Colors.BLUE)
    log(f"\nFFmpeg command:", Colors.YELLOW)
    log(' '.join(cmd))

    log(f"\n{Colors.BOLD}Running FFmpeg with real-time progress...{Colors.ENDC}\n")

    # Run FFmpeg with progress monitoring
    success = await run_ffmpeg_with_logging(cmd)

    if success and os.path.exists(str(output_path)):
        log(f"\nSUCCESS: Output file created: {output_path}", Colors.GREEN)

        # Verify output
        duration = FFmpegUtils.get_media_duration(str(output_path))
        log(f"Output duration: {duration:.2f}s", Colors.GREEN)

        log(f"\n{Colors.BOLD}Please check the output file to verify subtitles are visible!{Colors.ENDC}")
        log(f"File: {output_path}")
    else:
        log(f"\nFAILED: FFmpeg command failed or output not created", Colors.RED)

    return success


def create_test_ass_file(subtitles_to_burn):
    """Create a test ASS file from subtitle info."""

    ass_header = """[Script Info]
Title: Test Combined Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""

    styles = []
    events = []

    for idx, sub_info in enumerate(subtitles_to_burn):
        segment = sub_info['segment']
        subtitle_path = sub_info['subtitle_path']
        adjusted_start = sub_info['adjusted_start']

        # Create style
        style_name = f"Seg{idx}"
        font_name = getattr(segment, 'subtitle_font', 'Roboto')
        font_size = getattr(segment, 'subtitle_size', 20)
        primary_color = getattr(segment, 'subtitle_color', '&H00FFFFFF')
        outline_color = getattr(segment, 'subtitle_outline_color', '&H00000000')
        shadow_color = getattr(segment, 'subtitle_shadow_color', '&H80000000')
        outline_width = getattr(segment, 'subtitle_outline_width', 0.5)
        shadow_depth = getattr(segment, 'subtitle_shadow', 0.0)
        border_style = getattr(segment, 'subtitle_border_style', 1)
        margin_v = getattr(segment, 'subtitle_position', 30)

        style_line = f"Style: {style_name},{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{shadow_color},0,0,0,0,100,100,0,0,{border_style},{outline_width},{shadow_depth},2,10,10,{margin_v},1"
        styles.append(style_line)

        # Parse subtitle file
        if os.path.exists(subtitle_path):
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if subtitle_path.lower().endswith('.srt'):
                # Parse SRT
                blocks = content.strip().split('\n\n')
                for block in blocks:
                    lines = block.strip().split('\n')
                    if len(lines) >= 3 and '-->' in lines[1]:
                        parts = lines[1].split('-->')
                        orig_start = srt_to_seconds(parts[0].strip())
                        orig_end = srt_to_seconds(parts[1].strip())

                        new_start = adjusted_start + orig_start
                        new_end = adjusted_start + orig_end

                        text = '\\N'.join(lines[2:])
                        events.append(f"Dialogue: 0,{seconds_to_ass(new_start)},{seconds_to_ass(new_end)},{style_name},,0,0,0,,{text}")
            else:
                # Parse ASS
                in_events = False
                for line in content.split('\n'):
                    if '[Events]' in line:
                        in_events = True
                        continue
                    if in_events and line.startswith('Dialogue:'):
                        parts = line.split(',', 9)
                        if len(parts) >= 10:
                            orig_start = ass_to_seconds(parts[1].strip())
                            orig_end = ass_to_seconds(parts[2].strip())

                            new_start = adjusted_start + orig_start
                            new_end = adjusted_start + orig_end

                            text = parts[9]
                            events.append(f"Dialogue: 0,{seconds_to_ass(new_start)},{seconds_to_ass(new_end)},{style_name},,0,0,0,,{text}")

    # Build final ASS content
    result = ass_header
    for style in styles:
        result += style + '\n'
    result += '\n[Events]\n'
    result += 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    for event in events:
        result += event + '\n'

    return result


def srt_to_seconds(time_str):
    """Convert SRT time to seconds."""
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

def ass_to_seconds(time_str):
    """Convert ASS time to seconds."""
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

def seconds_to_ass(seconds):
    """Convert seconds to ASS time format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


async def run_ffmpeg_with_logging(cmd):
    """Run FFmpeg with real-time progress logging."""

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Read progress from stdout (due to -progress pipe:1)
    progress_task = asyncio.create_task(read_progress(process.stdout))
    stderr_task = asyncio.create_task(read_stderr(process.stderr))

    await process.wait()

    # Cancel tasks
    progress_task.cancel()
    stderr_task.cancel()

    try:
        await progress_task
    except asyncio.CancelledError:
        pass

    try:
        await stderr_task
    except asyncio.CancelledError:
        pass

    return process.returncode == 0


async def read_progress(stream):
    """Read FFmpeg progress output."""
    current_progress = {}

    try:
        while True:
            line = await stream.readline()
            if not line:
                break

            line = line.decode().strip()
            if '=' in line:
                key, value = line.split('=', 1)
                current_progress[key] = value

                # Log interesting progress updates
                if key == 'out_time_ms':
                    try:
                        ms = int(value)
                        seconds = ms / 1000000
                        log(f"  Progress: {seconds:.2f}s encoded", Colors.CYAN)
                    except:
                        pass
                elif key == 'fps':
                    log(f"  FPS: {value}", Colors.CYAN)
                elif key == 'progress':
                    if value == 'end':
                        log(f"  FFmpeg finished!", Colors.GREEN)
    except asyncio.CancelledError:
        pass


async def read_stderr(stream):
    """Read FFmpeg stderr for errors."""
    try:
        while True:
            line = await stream.readline()
            if not line:
                break

            line = line.decode().strip()

            # Filter and log important stderr messages
            if 'error' in line.lower():
                log(f"  STDERR ERROR: {line}", Colors.RED)
            elif 'warning' in line.lower():
                log(f"  STDERR WARNING: {line}", Colors.YELLOW)
            elif 'subtitle' in line.lower():
                log(f"  STDERR (subtitle): {line}", Colors.CYAN)
            elif line.startswith('frame=') or line.startswith('size='):
                # Progress line
                pass
    except asyncio.CancelledError:
        pass


if __name__ == '__main__':
    project_name = sys.argv[1] if len(sys.argv) > 1 else "Check3"

    print(f"\n{Colors.BOLD}Subtitle Burn Test Script{Colors.ENDC}")
    print(f"Project: {project_name}\n")

    asyncio.run(test_subtitle_burning(project_name))
