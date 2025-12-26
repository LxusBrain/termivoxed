"""Project model - Manages project data and persistence"""

import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from uuid import uuid4

from .video import Video
from .timeline import Timeline
from .segment import Segment
from .bgm_track import BGMTrack
from utils.logger import logger
from config import settings
from backend.ffmpeg_utils import FFmpegUtils

# Cross-platform file locking
if sys.platform == 'win32':
    import msvcrt

    @contextmanager
    def _file_lock(f, exclusive=True):
        """Windows file locking using msvcrt"""
        try:
            if exclusive:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            yield
        finally:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
else:
    import fcntl

    @contextmanager
    def _file_lock(f, exclusive=True):
        """Unix file locking using fcntl"""
        try:
            if exclusive:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            yield
        finally:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


class Project:
    """Manages multi-video project data and persistence"""

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """
        Sanitize project name to prevent path traversal attacks.

        Args:
            name: Raw project name

        Returns:
            Sanitized project name safe for use in file paths
        """
        import re

        if not name:
            raise ValueError("Project name cannot be empty")

        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[/\\<>:"|?*\x00-\x1f]', "_", name)

        # Remove leading/trailing dots and spaces (prevents ".." traversal)
        sanitized = sanitized.strip(". ")

        # Prevent double-dot traversal even if it's obfuscated
        while ".." in sanitized:
            sanitized = sanitized.replace("..", "_")

        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        if not sanitized:
            raise ValueError("Project name contains only invalid characters")

        return sanitized

    def __init__(self, name: str, video_paths: Optional[List[str]] = None, user_id: Optional[str] = None):
        """
        Initialize project with optional video paths

        Args:
            name: Project name
            video_paths: List of video file paths (for multi-video) or None
            user_id: Owner's user ID (required for multi-user isolation)
        """
        self.name = self._sanitize_name(name)
        self.user_id = user_id  # Owner's user ID for access control
        self.videos: List[Video] = []
        self.active_video_id: Optional[str] = None
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        self.background_music_path: Optional[str] = None  # Legacy single BGM (backward compat)
        self.bgm_tracks: List[BGMTrack] = []  # New: multiple BGM tracks
        self.bgm_volume: int = 100  # Global BGM volume (0-200%, 100 = default -20dB)
        self.tts_volume: int = 100  # Global TTS volume boost (0-200%, 100 = default +15dB)
        self.export_quality = "balanced"  # lossless, high, balanced
        self.include_subtitles = True
        # Generic segments - project-level segments for multi-video projects
        # These use timeline positions (absolute) rather than video-local positions
        self.generic_segments: List[Segment] = []

        # If video paths provided, create Video instances
        if video_paths:
            for idx, video_path in enumerate(video_paths, 1):
                self.add_video(video_path, order=idx)

    @property
    def project_dir(self) -> Path:
        """Get project directory path"""
        return Path(settings.PROJECTS_DIR) / self.name

    @property
    def project_file(self) -> Path:
        """Get project file path"""
        return self.project_dir / "project.json"

    def add_video(self, video_path: str, name: Optional[str] = None, order: Optional[int] = None) -> Video:
        """
        Add a new video to the project

        Args:
            video_path: Path to video file
            name: Optional custom name (defaults to filename)
            order: Optional order position (defaults to end)

        Returns:
            Created Video instance
        """
        if name is None:
            name = Path(video_path).stem

        if order is None:
            order = len(self.videos) + 1

        video = Video.create(name=name, video_path=video_path, order=order)
        self.videos.append(video)

        # Set as active if it's the first video
        if len(self.videos) == 1:
            self.active_video_id = video.id

        logger.info(f"Added video to project: {name} (order: {order})")
        return video

    def remove_video(self, video_id: str) -> bool:
        """
        Remove a video from the project

        Args:
            video_id: ID of video to remove

        Returns:
            True if removed, False if not found
        """
        original_count = len(self.videos)
        self.videos = [v for v in self.videos if v.id != video_id]
        removed = len(self.videos) < original_count

        if removed:
            # Reorder remaining videos
            for idx, video in enumerate(sorted(self.videos, key=lambda v: v.order), 1):
                video.order = idx

            # Update active video if needed
            if self.active_video_id == video_id:
                self.active_video_id = self.videos[0].id if self.videos else None

            logger.info(f"Removed video from project: {video_id}")

        return removed

    def get_video(self, video_id: str) -> Optional[Video]:
        """Get video by ID"""
        for video in self.videos:
            if video.id == video_id:
                return video
        return None

    def get_active_video(self) -> Optional[Video]:
        """Get currently active video"""
        if self.active_video_id:
            return self.get_video(self.active_video_id)
        return None

    def get_next_video(self, current_video_id: str) -> Optional[Video]:
        """
        Get the next video in order sequence after the specified video.
        Used for cross-video segments that extend into the next video.

        Args:
            current_video_id: ID of the current video

        Returns:
            Next Video in order, or None if current video is last
        """
        current_video = self.get_video(current_video_id)
        if not current_video:
            return None

        # Sort videos by order and find the next one
        sorted_videos = sorted(self.videos, key=lambda v: v.order)
        for i, video in enumerate(sorted_videos):
            if video.id == current_video_id and i + 1 < len(sorted_videos):
                return sorted_videos[i + 1]
        return None

    def get_previous_video(self, current_video_id: str) -> Optional[Video]:
        """
        Get the previous video in order sequence before the specified video.
        Used for detecting cross-video segments coming from the previous video.

        Args:
            current_video_id: ID of the current video

        Returns:
            Previous Video in order, or None if current video is first
        """
        current_video = self.get_video(current_video_id)
        if not current_video:
            return None

        # Sort videos by order and find the previous one
        sorted_videos = sorted(self.videos, key=lambda v: v.order)
        for i, video in enumerate(sorted_videos):
            if video.id == current_video_id and i > 0:
                return sorted_videos[i - 1]
        return None

    def set_active_video(self, video_id: str) -> bool:
        """
        Set the active video for editing

        Args:
            video_id: ID of video to set as active

        Returns:
            True if successful, False if video not found
        """
        if self.get_video(video_id):
            self.active_video_id = video_id
            logger.info(f"Active video set to: {video_id}")
            return True
        return False

    def reorder_videos(self, video_ids_in_order: List[str]) -> bool:
        """
        Reorder videos based on provided ID list

        Args:
            video_ids_in_order: List of video IDs in desired order

        Returns:
            True if successful
        """
        # Validate all IDs exist
        if set(video_ids_in_order) != {v.id for v in self.videos}:
            logger.error("Invalid video IDs provided for reordering")
            return False

        # Create new order mapping
        for new_order, video_id in enumerate(video_ids_in_order, 1):
            video = self.get_video(video_id)
            if video:
                video.order = new_order

        # Re-sort videos list
        self.videos.sort(key=lambda v: v.order)
        logger.info("Videos reordered successfully")
        return True

    def check_video_compatibility(self) -> tuple[bool, List[str]]:
        """
        Check if all videos in project are compatible for combination

        Returns:
            Tuple of (all_compatible: bool, warnings: List[str])
        """
        if len(self.videos) <= 1:
            return True, []

        warnings = []
        reference_video = self.videos[0]

        for idx, video in enumerate(self.videos[1:], 2):
            is_compatible, reason = reference_video.is_compatible_with(video)
            if not is_compatible:
                warnings.append(f"Video {idx} ({video.name}): {reason}")

        return len(warnings) == 0, warnings

    # BGM Track Management Methods
    def add_bgm_track(
        self,
        path: str,
        name: Optional[str] = None,
        start_time: float = 0.0,
        end_time: float = 0.0,
        volume: int = 100
    ) -> BGMTrack:
        """
        Add a new BGM track to the project

        Args:
            path: Path to audio file
            name: Optional name (defaults to filename)
            start_time: Start time in seconds
            end_time: End time in seconds (0 = until video end)
            volume: Volume percentage (0-200)

        Returns:
            Created BGMTrack instance
        """
        if name is None:
            name = Path(path).stem

        # Probe the audio file for duration
        audio_duration = FFmpegUtils.get_media_duration(path)
        if audio_duration:
            logger.info(f"Probed audio duration for '{name}': {audio_duration:.2f}s")
        else:
            logger.warning(f"Could not probe audio duration for: {path}")

        track = BGMTrack(
            name=name,
            path=path,
            start_time=start_time,
            end_time=end_time,
            volume=volume,
            order=len(self.bgm_tracks) + 1,
            duration=audio_duration  # Set probed duration
        )

        self.bgm_tracks.append(track)
        logger.info(f"Added BGM track: {name} ({start_time}s - {end_time}s, duration: {audio_duration}s)")
        return track

    def get_bgm_track(self, track_id: str) -> Optional[BGMTrack]:
        """Get BGM track by ID"""
        for track in self.bgm_tracks:
            if track.id == track_id:
                return track
        return None

    def update_bgm_track(self, track_id: str, **kwargs) -> Optional[BGMTrack]:
        """
        Update a BGM track

        Args:
            track_id: ID of track to update
            **kwargs: Fields to update (name, path, start_time, end_time, volume, etc.)

        Returns:
            Updated track or None if not found
        """
        track = self.get_bgm_track(track_id)
        if not track:
            return None

        for key, value in kwargs.items():
            if hasattr(track, key):
                setattr(track, key, value)

        logger.info(f"Updated BGM track: {track.name}")
        return track

    def remove_bgm_track(self, track_id: str) -> bool:
        """
        Remove a BGM track

        Args:
            track_id: ID of track to remove

        Returns:
            True if removed, False if not found
        """
        original_count = len(self.bgm_tracks)
        self.bgm_tracks = [t for t in self.bgm_tracks if t.id != track_id]
        removed = len(self.bgm_tracks) < original_count

        if removed:
            # Reorder remaining tracks
            for idx, track in enumerate(sorted(self.bgm_tracks, key=lambda t: t.order), 1):
                track.order = idx
            logger.info(f"Removed BGM track: {track_id}")

        return removed

    def reorder_bgm_tracks(self, track_ids_in_order: List[str]) -> bool:
        """
        Reorder BGM tracks

        Args:
            track_ids_in_order: List of track IDs in desired order

        Returns:
            True if successful
        """
        if set(track_ids_in_order) != {t.id for t in self.bgm_tracks}:
            logger.error("Invalid track IDs provided for reordering")
            return False

        for new_order, track_id in enumerate(track_ids_in_order, 1):
            track = self.get_bgm_track(track_id)
            if track:
                track.order = new_order

        self.bgm_tracks.sort(key=lambda t: t.order)
        logger.info("BGM tracks reordered successfully")
        return True

    def get_active_bgm_tracks(self, video_duration: float) -> List[BGMTrack]:
        """
        Get all non-muted BGM tracks that have valid time ranges

        Args:
            video_duration: Duration of the video

        Returns:
            List of active BGM tracks, sorted by order
        """
        active_tracks = []
        for track in sorted(self.bgm_tracks, key=lambda t: t.order):
            if not track.muted and track.path:
                # Check if track time range is within video
                if track.start_time < video_duration:
                    active_tracks.append(track)
        return active_tracks

    # Generic Segment Management Methods (for multi-video project-level segments)
    def add_generic_segment(
        self,
        name: str,
        start_time: float,
        end_time: float,
        text: str = "",
        language: str = "en",
        voice_id: str = ""
    ) -> Segment:
        """
        Add a generic segment to the project timeline.
        Generic segments use absolute timeline positions and are not tied to any specific video.

        Args:
            name: Segment name
            start_time: Start time on the TIMELINE (absolute position)
            end_time: End time on the TIMELINE (absolute position)
            text: Segment text/script
            language: Language code
            voice_id: Voice ID for TTS

        Returns:
            Created Segment instance
        """
        segment = Segment(
            name=name,
            video_id=None,  # Generic segments have no video_id
            start_time=start_time,
            end_time=end_time,
            text=text,
            language=language,
            voice_id=voice_id
        )

        self.generic_segments.append(segment)
        logger.info(f"Added generic segment: {name} ({start_time}s - {end_time}s)")
        return segment

    def get_generic_segment(self, segment_id: str) -> Optional[Segment]:
        """Get generic segment by ID"""
        for segment in self.generic_segments:
            if segment.id == segment_id:
                return segment
        return None

    def update_generic_segment(self, segment_id: str, **kwargs) -> Optional[Segment]:
        """
        Update a generic segment

        Args:
            segment_id: ID of segment to update
            **kwargs: Fields to update

        Returns:
            Updated segment or None if not found
        """
        segment = self.get_generic_segment(segment_id)
        if not segment:
            return None

        for key, value in kwargs.items():
            if hasattr(segment, key) and value is not None:
                setattr(segment, key, value)

        logger.info(f"Updated generic segment: {segment.name}")
        return segment

    def remove_generic_segment(self, segment_id: str) -> bool:
        """
        Remove a generic segment

        Args:
            segment_id: ID of segment to remove

        Returns:
            True if removed, False if not found
        """
        original_count = len(self.generic_segments)
        self.generic_segments = [s for s in self.generic_segments if s.id != segment_id]
        removed = len(self.generic_segments) < original_count

        if removed:
            logger.info(f"Removed generic segment: {segment_id}")

        return removed

    def get_all_segments_for_timeline(self) -> List[Segment]:
        """
        Get all segments for the project timeline.
        In multi-video mode, this includes both video-specific and generic segments.

        Returns:
            List of all segments sorted by start_time
        """
        all_segments = list(self.generic_segments)

        # Also include video-specific segments
        for video in self.videos:
            all_segments.extend(video.timeline.segments)

        return sorted(all_segments, key=lambda s: s.start_time)

    # Backward compatibility properties
    @property
    def video_path(self) -> str:
        """Backward compatibility: Get first video's path"""
        if self.videos:
            return self.videos[0].path
        return ""

    @property
    def timeline(self) -> Optional[Timeline]:
        """Backward compatibility: Get active video's timeline"""
        active_video = self.get_active_video()
        return active_video.timeline if active_video else None

    def save(self) -> bool:
        """
        Save project to disk using atomic write.

        Uses a temp file + rename strategy to prevent data corruption
        if the write fails mid-operation.
        """
        try:
            # Create project directory
            self.project_dir.mkdir(parents=True, exist_ok=True)

            # Update modified time
            self.modified_at = datetime.now()

            # Serialize project data
            project_data = {
                "name": self.name,
                "user_id": self.user_id,  # Owner's user ID for access control
                "videos": [video.to_dict() for video in self.videos],
                "active_video_id": self.active_video_id,
                "created_at": self.created_at.isoformat(),
                "modified_at": self.modified_at.isoformat(),
                "background_music_path": self.background_music_path,
                "bgm_tracks": [track.to_dict() for track in self.bgm_tracks],
                "bgm_volume": self.bgm_volume,
                "tts_volume": self.tts_volume,
                "export_quality": self.export_quality,
                "include_subtitles": self.include_subtitles,
                # Generic segments - project-level segments for multi-video timeline
                "generic_segments": [seg.to_dict() for seg in self.generic_segments],
                "version": 5  # Version 5 = adds user_id for multi-user access control
            }

            # Atomic write: write to temp file, then rename
            # This prevents data corruption if write fails mid-operation
            temp_file = self.project_file.with_suffix('.json.tmp')

            try:
                # Write to temp file
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, indent=2)

                # Atomic rename (on most filesystems this is atomic)
                temp_file.replace(self.project_file)

            except Exception as write_error:
                # Clean up temp file if it exists
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                raise write_error

            logger.info(f"Project saved: {self.name} ({len(self.videos)} videos)")
            return True

        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            return False

    @classmethod
    @contextmanager
    def locked_update(cls, name: str, timeout: float = 5.0):
        """
        Context manager for atomic project updates with file locking.

        This prevents race conditions when multiple WebSocket updates
        occur simultaneously. Usage:

            with Project.locked_update("my_project") as project:
                if project:
                    project.videos[0].timeline_start = 10.0
                    # save() is called automatically on success

        Args:
            name: Project name
            timeout: Maximum time to wait for lock (seconds)

        Yields:
            Project instance (already locked) or None if not found
        """
        # Sanitize project name to prevent path traversal
        safe_name = cls._sanitize_name(name)
        project_dir = Path(settings.PROJECTS_DIR) / safe_name
        lock_file = project_dir / ".project.lock"

        # Create project directory if needed
        project_dir.mkdir(parents=True, exist_ok=True)

        project = None
        lock_handle = None

        try:
            # Open/create lock file
            lock_handle = open(lock_file, 'w')

            # Acquire exclusive lock with timeout
            start_time = time.time()
            while True:
                try:
                    with _file_lock(lock_handle, exclusive=True):
                        # Load project while holding lock
                        project = cls.load(name)
                        if project is None:
                            yield None
                            return

                        # Yield project to caller for modifications
                        yield project

                        # Save after modifications (still under lock)
                        if project is not None:
                            project.save()
                        return

                except (IOError, OSError) as e:
                    # Lock acquisition failed, retry with timeout
                    if time.time() - start_time > timeout:
                        logger.error(f"Timeout waiting for project lock: {name}")
                        yield None
                        return
                    time.sleep(0.05)  # Small delay before retry

        except Exception as e:
            logger.error(f"Error during locked update: {e}")
            yield None

        finally:
            if lock_handle:
                try:
                    lock_handle.close()
                except Exception:
                    pass

    @classmethod
    def load(cls, name: str) -> Optional['Project']:
        """Load project from disk with backward compatibility"""
        try:
            # Sanitize project name to prevent path traversal
            safe_name = cls._sanitize_name(name)
            project_dir = Path(settings.PROJECTS_DIR) / safe_name
            project_file = project_dir / "project.json"

            if not project_file.exists():
                logger.error(f"Project file not found: {project_file}")
                return None

            # Read project data
            with open(project_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            # Check version for backward compatibility
            version = project_data.get("version", 1)

            if version == 1 or "video_path" in project_data:
                # Old format: single video
                logger.info(f"Migrating project '{name}' from v1 (single-video) to v3 (multi-video + multi-BGM)")
                project = cls._load_v1_project(project_data)
            else:
                # Version 2 or 3: multi-video format (v3 adds multi-BGM)
                project = cls._load_v2_project(project_data)

            logger.info(f"Project loaded: {name} ({len(project.videos)} videos)")
            return project

        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            return None

    @classmethod
    def _load_v1_project(cls, data: dict) -> 'Project':
        """Load old single-video project format and migrate to multi-video"""
        project = cls(data["name"])

        # Create single Video from old format
        video_path = data["video_path"]
        video = Video.create(
            name="Main Video",
            video_path=video_path,
            order=1
        )

        # Load timeline into the video
        timeline_data = data["timeline"]
        video.timeline = Timeline.from_dict(timeline_data)
        video.timeline.video_id = video.id

        # Update all segments with video_id
        for segment in video.timeline.segments:
            segment.video_id = video.id

        project.videos = [video]
        project.active_video_id = video.id

        # Load metadata
        project.created_at = datetime.fromisoformat(data["created_at"])
        project.modified_at = datetime.fromisoformat(data["modified_at"])
        project.background_music_path = data.get("background_music_path")
        project.export_quality = data.get("export_quality", "balanced")
        project.include_subtitles = data.get("include_subtitles", True)

        return project

    @classmethod
    def _load_v2_project(cls, data: dict) -> 'Project':
        """Load multi-video project format (v2, v3, v4, v5)"""
        project = cls(data["name"], user_id=data.get("user_id"))

        # Load videos
        for video_data in data["videos"]:
            video = Video.from_dict(video_data)
            project.videos.append(video)

        project.active_video_id = data.get("active_video_id")

        # Load metadata
        project.created_at = datetime.fromisoformat(data["created_at"])
        project.modified_at = datetime.fromisoformat(data["modified_at"])
        project.background_music_path = data.get("background_music_path")
        project.export_quality = data.get("export_quality", "balanced")
        project.include_subtitles = data.get("include_subtitles", True)

        # Load BGM tracks (v3+)
        bgm_tracks_data = data.get("bgm_tracks", [])
        for track_data in bgm_tracks_data:
            track = BGMTrack.from_dict(track_data)
            # Probe duration if not set (for older projects)
            if track.duration is None and track.path:
                import os
                if os.path.exists(track.path):
                    track.duration = FFmpegUtils.get_media_duration(track.path)
                    if track.duration:
                        logger.info(f"Probed missing duration for BGM track '{track.name}': {track.duration:.2f}s")
            project.bgm_tracks.append(track)

        # Load volume settings (v3+)
        project.bgm_volume = data.get("bgm_volume", 100)
        project.tts_volume = data.get("tts_volume", 100)

        # Load generic segments (v4+) - project-level segments for multi-video timeline
        generic_segments_data = data.get("generic_segments", [])
        for seg_data in generic_segments_data:
            project.generic_segments.append(Segment.from_dict(seg_data))

        return project

    @classmethod
    def list_projects(cls, user_id: Optional[str] = None) -> list:
        """
        List available projects, optionally filtered by user_id.

        Args:
            user_id: If provided, only returns projects owned by this user.
                     If None, returns all projects (for backward compatibility).

        Returns:
            List of project metadata dictionaries.
        """
        projects = []
        projects_dir = Path(settings.PROJECTS_DIR)

        if not projects_dir.exists():
            return projects

        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                project_file = project_dir / "project.json"
                if project_file.exists():
                    try:
                        with open(project_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        # SECURITY: Filter by user_id if provided
                        project_user_id = data.get("user_id")
                        if user_id is not None:
                            # Only return projects owned by this user
                            # Projects without user_id are legacy - treat as unowned
                            if project_user_id is None or project_user_id != user_id:
                                continue

                        # Handle both v1 and v2 formats
                        version = data.get("version", 1)

                        if version == 1 or "video_path" in data:
                            # Old format
                            video_count = 1
                            segments_count = len(data["timeline"]["segments"])
                        else:
                            # New format (v2, v3, v4, v5)
                            video_count = len(data["videos"])
                            # Count video-specific segments
                            segments_count = sum(
                                len(v["timeline"]["segments"])
                                for v in data["videos"]
                            )
                            # Also count generic/project-level segments (v4+)
                            segments_count += len(data.get("generic_segments", []))

                        projects.append({
                            "name": data["name"],
                            "user_id": project_user_id,
                            "video_count": video_count,
                            "created_at": data["created_at"],
                            "modified_at": data["modified_at"],
                            "segments_count": segments_count
                        })
                    except Exception as e:
                        logger.warning(f"Could not read project {project_dir.name}: {e}")

        # Sort by modified date (most recent first)
        projects.sort(key=lambda p: p["modified_at"], reverse=True)
        return projects

    def delete(self) -> bool:
        """Delete project and all associated files"""
        try:
            import shutil

            if self.project_dir.exists():
                shutil.rmtree(self.project_dir)
                logger.info(f"Project deleted: {self.name}")
                return True
            else:
                logger.warning(f"Project directory not found: {self.project_dir}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete project: {e}")
            return False

    def get_stats(self) -> dict:
        """Get project statistics"""
        total_segments = sum(len(v.timeline.segments) for v in self.videos)
        total_video_duration = sum(v.duration or 0 for v in self.videos)

        return {
            "name": self.name,
            "video_count": len(self.videos),
            "total_video_duration": total_video_duration,
            "segments_count": total_segments,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "videos": [v.get_display_info() for v in self.videos]
        }

    def __str__(self) -> str:
        """String representation"""
        return f"Project(name={self.name}, videos={len(self.videos)})"
