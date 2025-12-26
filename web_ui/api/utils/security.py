"""
Security Utilities for TermiVoxed Web API

Provides path validation, input sanitization, and security helpers
to prevent common vulnerabilities like path traversal.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Set

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


# ============================================================================
# PATH VALIDATION
# ============================================================================

# Allowed base directories for file operations
ALLOWED_BASE_DIRS: Set[str] = set()

# Dangerous path patterns
DANGEROUS_PATTERNS = [
    r"\.\./",           # Parent directory traversal
    r"\.\.\\",          # Windows parent traversal
    r"^/etc/",          # System config
    r"^/var/",          # System var
    r"^/usr/",          # System binaries
    r"^/bin/",          # Binaries
    r"^/sbin/",         # System binaries
    r"^/root/",         # Root home
    r"^/home/(?!.*termivoxed)",  # Other users' homes
    r"^C:\\Windows\\",  # Windows system
    r"^C:\\Program Files",  # Program files
    r"\\\.\.\\",        # Windows traversal with backslash
    r"[\x00-\x1f]",     # Control characters
    r"[<>:\"|?*]",      # Windows invalid chars
]


def init_allowed_dirs(storage_dir: str, temp_dir: str, output_dir: str):
    """
    Initialize allowed base directories.

    Call this at application startup with your configured directories.
    """
    global ALLOWED_BASE_DIRS

    ALLOWED_BASE_DIRS = {
        os.path.abspath(storage_dir),
        os.path.abspath(temp_dir),
        os.path.abspath(output_dir),
    }

    # Also allow home directory for user's videos
    home = os.path.expanduser("~")
    ALLOWED_BASE_DIRS.add(home)

    logger.info(f"Initialized allowed directories: {ALLOWED_BASE_DIRS}")


def is_path_safe(path: str, allowed_dirs: Optional[List[str]] = None) -> bool:
    """
    Check if a path is safe (no traversal attacks).

    Args:
        path: The path to validate
        allowed_dirs: Optional list of allowed base directories

    Returns:
        True if path is safe, False otherwise
    """
    if not path:
        return False

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, path, re.IGNORECASE):
            logger.warning(f"Path matches dangerous pattern: {path}")
            return False

    # Normalize the path
    try:
        normalized = os.path.normpath(os.path.abspath(path))
    except (ValueError, OSError):
        return False

    # Check if the resolved path is within allowed directories
    dirs_to_check = allowed_dirs if allowed_dirs else ALLOWED_BASE_DIRS

    if dirs_to_check:
        is_within_allowed = any(
            normalized.startswith(os.path.abspath(d))
            for d in dirs_to_check
        )

        if not is_within_allowed:
            # Allow common video directories
            common_video_dirs = [
                os.path.expanduser("~/Videos"),
                os.path.expanduser("~/Movies"),
                os.path.expanduser("~/Downloads"),
                os.path.expanduser("~/Desktop"),
                "/tmp",
                os.environ.get("TEMP", ""),
                os.environ.get("TMP", ""),
            ]

            is_within_allowed = any(
                normalized.startswith(os.path.abspath(d))
                for d in common_video_dirs if d
            )

        if not is_within_allowed:
            logger.warning(f"Path outside allowed directories: {normalized}")
            return False

    return True


def validate_path(
    path: str,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
    allowed_extensions: Optional[List[str]] = None,
    allowed_dirs: Optional[List[str]] = None,
) -> str:
    """
    Validate and normalize a file path.

    Args:
        path: The path to validate
        must_exist: If True, raise error if path doesn't exist
        must_be_file: If True, raise error if path is not a file
        must_be_dir: If True, raise error if path is not a directory
        allowed_extensions: List of allowed file extensions (e.g., ['.mp4', '.mov'])
        allowed_dirs: Optional list of allowed base directories

    Returns:
        Normalized absolute path

    Raises:
        HTTPException: If validation fails
    """
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path cannot be empty"
        )

    # Check for path traversal
    if not is_path_safe(path, allowed_dirs):
        logger.error(f"Path traversal attempt detected: {path}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path: Access denied"
        )

    # Normalize path
    try:
        normalized = os.path.normpath(os.path.abspath(path))
    except (ValueError, OSError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid path format: {e}"
        )

    # Check existence
    if must_exist and not os.path.exists(normalized):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Path does not exist"
        )

    # Check file/directory type
    if must_be_file and os.path.exists(normalized) and not os.path.isfile(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path is not a file"
        )

    if must_be_dir and os.path.exists(normalized) and not os.path.isdir(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path is not a directory"
        )

    # Check extension
    if allowed_extensions:
        ext = Path(normalized).suffix.lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"
            )

    return normalized


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent directory traversal and invalid characters.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed"

    # Get just the filename part (no directory)
    filename = os.path.basename(filename)

    # Remove null bytes and control characters
    filename = re.sub(r"[\x00-\x1f]", "", filename)

    # Remove/replace dangerous characters
    # Windows: < > : " / \ | ? *
    # Unix: /
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext

    # Ensure we have something
    if not filename:
        filename = "unnamed"

    return filename


def validate_video_path(path: str, must_exist: bool = True) -> str:
    """
    Validate a video file path.

    Args:
        path: The video path to validate
        must_exist: If True, check that the file exists

    Returns:
        Validated path

    Raises:
        HTTPException: If validation fails
    """
    VIDEO_EXTENSIONS = [
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".mpeg", ".mpg", ".3gp", ".3g2", ".ts", ".mts"
    ]

    return validate_path(
        path,
        must_exist=must_exist,
        must_be_file=must_exist,
        allowed_extensions=VIDEO_EXTENSIONS,
    )


def validate_audio_path(path: str, must_exist: bool = True) -> str:
    """
    Validate an audio file path.

    Args:
        path: The audio path to validate
        must_exist: If True, check that the file exists

    Returns:
        Validated path

    Raises:
        HTTPException: If validation fails
    """
    AUDIO_EXTENSIONS = [
        ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma",
        ".opus", ".aiff", ".alac"
    ]

    return validate_path(
        path,
        must_exist=must_exist,
        must_be_file=must_exist,
        allowed_extensions=AUDIO_EXTENSIONS,
    )


def validate_output_path(path: str) -> str:
    """
    Validate an output file path (for export).

    Args:
        path: The output path to validate

    Returns:
        Validated path

    Raises:
        HTTPException: If validation fails
    """
    # For output, we don't require the file to exist
    # but the parent directory should be writable

    validated = validate_path(path, must_exist=False)

    parent = os.path.dirname(validated)
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot create output directory: {e}"
            )

    return validated


# ============================================================================
# INPUT SANITIZATION
# ============================================================================

def sanitize_project_name(name: str) -> str:
    """
    Sanitize a project name.

    Args:
        name: The project name to sanitize

    Returns:
        Sanitized project name
    """
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name cannot be empty"
        )

    # Remove path separators and dangerous chars
    sanitized = re.sub(r'[/\\<>:"|?*\x00-\x1f]', "_", name)

    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip(". ")

    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]

    if not sanitized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name contains only invalid characters"
        )

    return sanitized


def sanitize_text_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize text input (for TTS, scripts, etc.).

    Args:
        text: The text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace("\x00", "")

    # Limit length
    if len(text) > max_length:
        text = text[:max_length]

    return text
