import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Plus, AlertTriangle, GripVertical, Music, Upload, Loader2, Volume2, VolumeX, Trash2, Film, Layers, ChevronDown, AlertCircle, Mic, ZoomIn, ZoomOut, Maximize2, ArrowRight } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { videosApi, projectsApi, type BGMTrack } from '../api/client'
import type { Segment, VideoInfo, TimelineViewMode } from '../types'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import VoiceOverBlock from './VoiceOverBlock'
import { detectVoiceOverOverlaps, hasAudioOvershoot, getOvershootAmount } from '../utils/voiceOverUtils'
import { useTimelineWebSocket } from '../hooks/useTimelineWebSocket'

interface TimelineProps {
  duration: number
  projectName: string
  onAddSegment: (startTime: number, videoId?: string) => void
  backgroundMusicPath?: string | null
  onBackgroundMusicChange?: (path: string | null) => void
  bgmTracks?: BGMTrack[]
  bgmVolume?: number
  ttsVolume?: number
  onBGMTracksChange?: () => void
  // Callback for instant BGM track updates (position, volume, mute) for preview sync
  onBGMTrackUpdate?: (trackId: string, updates: { start_time?: number; end_time?: number; audio_offset?: number; volume?: number; muted?: boolean }) => void
  // Multi-video support
  videos?: VideoInfo[]
  activeVideoId?: string | null
  onSetActiveVideo?: (videoId: string) => void
  // Callback when video positions change (for syncing with parent)
  onVideoPositionChange?: () => void
  // Callback for instant video position updates (optimistic updates for preview sync)
  onVideoPositionUpdate?: (videoId: string, updates: { timeline_start?: number; timeline_end?: number; source_start?: number; source_end?: number | null }) => void
  // Callback to trigger preview playback at specific time
  onPlayPreview?: (timelineTime: number, segmentId: string) => void
}

function formatTime(seconds: number, showMs = false): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (showMs) {
    // Show millisecond precision: m:ss.sss
    return `${mins}:${secs.toFixed(3).padStart(6, '0')}`
  }
  // Show decisecond precision: m:ss.s (for cleaner display)
  const wholeSecs = Math.floor(secs)
  const fraction = Math.round((secs - wholeSecs) * 10) / 10
  if (fraction > 0 && fraction < 1) {
    return `${mins}:${wholeSecs.toString().padStart(2, '0')}.${Math.round(fraction * 10)}`
  }
  return `${mins}:${wholeSecs.toString().padStart(2, '0')}`
}

type DragMode = 'none' | 'move' | 'resize-start' | 'resize-end'

interface DragState {
  segmentId: string
  mode: DragMode
  initialMouseX: number
  initialStartTime: number
  initialEndTime: number
  // For video source trimming
  initialSourceStart?: number
  initialSourceEnd?: number | null
  // For segment audio trimming
  initialAudioOffset?: number
}

function SegmentBlock({
  segment,
  duration,
  isSelected,
  onClick,
  onDragStart,
  isDragging,
  previewTimes,
  rowIndex = 0,
  rowHeight = 36,
}: {
  segment: Segment
  duration: number
  isSelected: boolean
  onClick: () => void
  onDragStart: (e: React.MouseEvent, mode: DragMode) => void
  isDragging: boolean
  previewTimes?: { start: number; end: number }
  rowIndex?: number
  rowHeight?: number
}) {
  // Use preview times if available (during drag), otherwise use actual segment times
  const startTime = previewTimes?.start ?? segment.start_time
  const endTime = previewTimes?.end ?? segment.end_time

  const leftPercent = (startTime / duration) * 100
  const widthPercent = ((endTime - startTime) / duration) * 100
  const hasOverflow = segment.audio_fits_segment === false

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      className={clsx(
        'absolute rounded transition-colors group',
        'border-2 flex items-center overflow-hidden',
        isDragging && 'opacity-80',
        isSelected
          ? 'bg-accent-red/30 border-accent-red shadow-glow-red-sm z-10'
          : 'bg-terminal-elevated border-terminal-border hover:border-accent-red/50'
      )}
      style={{
        top: `${rowIndex * rowHeight + 4}px`,
        height: `${rowHeight - 8}px`,
        left: `${leftPercent}%`,
        width: `${widthPercent}%`,
        minWidth: '20px',
        cursor: 'grab',
      }}
    >
      {/* Left resize handle */}
      <div
        className={clsx(
          'absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize z-20',
          'flex items-center justify-center',
          'hover:bg-accent-red/30 transition-colors'
        )}
        onMouseDown={(e) => {
          e.stopPropagation()
          onDragStart(e, 'resize-start')
        }}
      >
        <div className="w-0.5 h-4 bg-accent-red/50 rounded opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Center content - drag to move */}
      <div
        className="flex-1 h-full flex items-center justify-center cursor-grab active:cursor-grabbing px-2"
        onMouseDown={(e) => {
          e.stopPropagation()
          onDragStart(e, 'move')
        }}
      >
        {widthPercent > 8 && (
          <span className="text-[10px] font-mono truncate text-text-primary select-none">
            {segment.name}
          </span>
        )}
        {widthPercent <= 8 && widthPercent > 4 && (
          <GripVertical className="w-3 h-3 text-text-muted" />
        )}
      </div>

      {/* Right resize handle */}
      <div
        className={clsx(
          'absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize z-20',
          'flex items-center justify-center',
          'hover:bg-accent-red/30 transition-colors'
        )}
        onMouseDown={(e) => {
          e.stopPropagation()
          onDragStart(e, 'resize-end')
        }}
      >
        <div className="w-0.5 h-4 bg-accent-red/50 rounded opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Overflow warning */}
      {hasOverflow && (
        <div className="absolute top-0.5 right-2">
          <AlertTriangle className="w-3 h-3 text-yellow-500" />
        </div>
      )}

      {/* Cross-video extension indicator */}
      {segment.extends_to_next_video && (
        <div className="absolute top-0.5 left-2 flex items-center gap-1" title={`Extends into ${segment.next_video_name || 'next video'}`}>
          <ArrowRight className="w-3 h-3 text-purple-400" />
          {segment.overflow_duration && segment.overflow_duration > 0 && widthPercent > 10 && (
            <span className="text-[8px] text-purple-400">+{segment.overflow_duration.toFixed(1)}s</span>
          )}
        </div>
      )}

      {/* Time display on hover/drag */}
      {(isSelected || isDragging) && (
        <div className="absolute -bottom-5 left-0 right-0 flex justify-between text-[9px] font-mono text-text-muted pointer-events-none">
          <span>{startTime.toFixed(1)}s</span>
          <span>{endTime.toFixed(1)}s</span>
        </div>
      )}
    </motion.div>
  )
}

// BGM Track Block Component - with trim visualization like VoiceOverBlock
// Horizontal Volume Meter Component for BGM Tracks
// - button on left, + button on right, colored bars in between
// Color: Yellow (low) → Green (optimal) → Red (high)
// Uses optimistic updates for instant UI feedback
function BGMVolumeMeter({
  volume,
  onChange,
  disabled = false,
}: {
  volume: number
  onChange: (volume: number) => void
  disabled?: boolean
}) {
  const NUM_BARS = 8 // Number of bars in the meter
  const STEP = 25 // Volume change per click (0-200 range)

  // Get color for each bar based on its position (left to right)
  const getBarColor = (barIndex: number, isActive: boolean): string => {
    if (!isActive) return 'bg-white/15'

    const position = barIndex / (NUM_BARS - 1) // 0 to 1

    if (position <= 0.25) {
      return 'bg-yellow-400' // Low (first 2 bars)
    } else if (position <= 0.625) {
      return 'bg-green-500' // Optimal (middle 3 bars)
    } else if (position <= 0.875) {
      return 'bg-orange-500' // Above default (next 2 bars)
    } else {
      return 'bg-red-500' // High (last bar)
    }
  }

  // Calculate how many bars should be lit based on volume (0-200)
  const activeBars = Math.round((volume / 200) * NUM_BARS)

  // Direct onChange call - parent handles instant update via local override + WebSocket
  const handleIncrease = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (disabled) return
    onChange(Math.min(200, volume + STEP))
  }

  const handleDecrease = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (disabled) return
    onChange(Math.max(0, volume - STEP))
  }

  // Convert volume to dB for tooltip
  const getVolumeDB = (vol: number): string => {
    if (vol === 0) return '-∞ dB'
    const db = -20 + 20 * Math.log10(vol / 100)
    return `${db > 0 ? '+' : ''}${db.toFixed(1)} dB`
  }

  return (
    <div
      className={clsx(
        'flex items-center gap-0.5 select-none',
        disabled && 'opacity-40'
      )}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      title={`Volume: ${volume}% (${getVolumeDB(volume)})`}
    >
      {/* Minus button */}
      <button
        onClick={handleDecrease}
        disabled={disabled || volume <= 0}
        className={clsx(
          'w-3.5 h-3.5 flex items-center justify-center rounded text-[9px] font-bold transition-colors',
          'bg-black/30 hover:bg-black/50 text-white/60 hover:text-white',
          (disabled || volume <= 0) && 'opacity-30 cursor-not-allowed'
        )}
      >
        −
      </button>

      {/* Volume bars - horizontal (thinner bars) */}
      <div className="flex items-center gap-0.5" title={`${volume}%`}>
        {Array.from({ length: NUM_BARS }).map((_, index) => {
          const isActive = index < activeBars
          return (
            <div
              key={index}
              className={clsx(
                'w-1 h-2.5 rounded-[1px] transition-colors duration-75',
                getBarColor(index, isActive)
              )}
            />
          )
        })}
      </div>

      {/* Plus button */}
      <button
        onClick={handleIncrease}
        disabled={disabled || volume >= 200}
        className={clsx(
          'w-3.5 h-3.5 flex items-center justify-center rounded text-[9px] font-bold transition-colors',
          'bg-black/30 hover:bg-black/50 text-white/60 hover:text-white',
          (disabled || volume >= 200) && 'opacity-30 cursor-not-allowed'
        )}
      >
        +
      </button>
    </div>
  )
}

function BGMTrackBlock({
  track,
  duration,
  isSelected,
  onClick,
  onDragStart,
  isDragging,
  previewTimes,
  onMuteToggle,
  onVolumeChange,
  onDelete,
}: {
  track: BGMTrack
  duration: number
  isSelected: boolean
  onClick: (e: React.MouseEvent) => void // Supports multi-selection with modifier keys
  onDragStart: (e: React.MouseEvent, mode: DragMode) => void
  isDragging: boolean
  previewTimes?: { start: number; end: number; audioOffset?: number }
  onMuteToggle: () => void
  onVolumeChange: (volume: number) => void
  onDelete: () => void
}) {
  // Use preview times during drag
  const startTime = previewTimes?.start ?? track.start_time
  const endTime = previewTimes?.end ?? (track.end_time === 0 ? duration : track.end_time)
  const audioOffset = previewTimes?.audioOffset ?? track.audio_offset ?? 0
  const trackDurationOnTimeline = endTime - startTime

  // Get audio file duration
  const audioDuration = track.duration || 0
  const hasAudioDuration = audioDuration > 0

  // Calculate trim states
  const isTrimmedFromStart = audioOffset > 0.1
  const remainingAudio = Math.max(0, audioDuration - audioOffset)
  const isTrimmedFromEnd = hasAudioDuration && trackDurationOnTimeline < remainingAudio - 0.1
  const unusedAtEnd = Math.max(0, remainingAudio - trackDurationOnTimeline)

  // Calculate position
  const leftPercent = (startTime / duration) * 100

  // For the visual, show the FULL audio as the block width, with active portion highlighted
  const activeWidthPercent = (trackDurationOnTimeline / duration) * 100

  // If trimmed, we want to show the trimmed portions visually
  const trimmedStartWidthPercent = isTrimmedFromStart && hasAudioDuration ? (audioOffset / duration) * 100 : 0
  const trimmedEndWidthPercent = isTrimmedFromEnd && hasAudioDuration ? (unusedAtEnd / duration) * 100 : 0

  // Total block width includes trimmed portions for visual reference
  const totalVisualWidth = activeWidthPercent + trimmedStartWidthPercent + trimmedEndWidthPercent
  const displayWidthPercent = Math.max(totalVisualWidth, 1) // min 1% for visibility

  // Adjust left position to account for trimmed start portion
  const adjustedLeftPercent = leftPercent - trimmedStartWidthPercent

  // Proportions within the block
  const trimmedStartPortion = displayWidthPercent > 0 ? (trimmedStartWidthPercent / displayWidthPercent) * 100 : 0
  const activePortion = displayWidthPercent > 0 ? (activeWidthPercent / displayWidthPercent) * 100 : 100
  const trimmedEndPortion = displayWidthPercent > 0 ? (trimmedEndWidthPercent / displayWidthPercent) * 100 : 0

  // Extract filename from path
  const fileName = track.path.split('/').pop() || track.name

  const getTooltipText = (): string => {
    const parts: string[] = [fileName]
    if (hasAudioDuration) {
      parts.push(`Audio: ${audioDuration.toFixed(1)}s`)
      parts.push(`Active: ${trackDurationOnTimeline.toFixed(1)}s`)
      if (isTrimmedFromStart) parts.push(`Start trim: ${audioOffset.toFixed(1)}s`)
      if (isTrimmedFromEnd) parts.push(`End trim: ${unusedAtEnd.toFixed(1)}s`)
    }
    if (track.loop) parts.push('Looping')
    return parts.join(' | ')
  }

  const handleMouseDown = (e: React.MouseEvent, mode: DragMode) => {
    e.preventDefault()
    e.stopPropagation()
    onDragStart(e, mode)
  }

  return (
    <div
      className={clsx(
        'absolute top-0.5 bottom-0.5 group select-none',
        isDragging && 'z-50',
        track.muted && 'opacity-50'
      )}
      style={{
        left: `${Math.max(0, adjustedLeftPercent)}%`,
        width: `${displayWidthPercent}%`,
        minWidth: '120px',
      }}
    >
      {/* Container for all portions */}
      <div className="absolute inset-0 flex rounded overflow-hidden">

        {/* Trimmed START portion - striped/faded */}
        {isTrimmedFromStart && trimmedStartPortion > 0 && (
          <div
            className="h-full relative border border-teal-600/30 rounded-l"
            style={{
              width: `${trimmedStartPortion}%`,
              background: 'repeating-linear-gradient(45deg, rgba(20,184,166,0.1), rgba(20,184,166,0.1) 2px, rgba(20,184,166,0.2) 2px, rgba(20,184,166,0.2) 4px)',
            }}
            title={`Trimmed: ${audioOffset.toFixed(1)}s from start`}
          >
            <span className="absolute inset-0 flex items-center justify-center text-[8px] text-teal-500/60 font-mono">
              -{audioOffset.toFixed(1)}s
            </span>
          </div>
        )}

        {/* ACTIVE portion - solid color */}
        <div
          onClick={(e) => { e.stopPropagation(); onClick(e) }}
          title={getTooltipText()}
          className={clsx(
            'h-full relative flex items-center',
            isDragging ? 'cursor-grabbing shadow-lg' : '',
            isSelected
              ? 'bg-teal-600/40 border-y-2 border-teal-500 shadow-[0_0_8px_rgba(20,184,166,0.3)]'
              : 'bg-gradient-to-r from-teal-600/30 to-teal-700/30 border-y border-teal-600/50 hover:border-teal-500/70',
            // Round corners based on trim state
            !isTrimmedFromStart && 'rounded-l border-l-2',
            !isTrimmedFromEnd && 'rounded-r border-r-2',
            isTrimmedFromStart && 'border-l border-l-teal-400/50',
            isTrimmedFromEnd && 'border-r border-r-teal-400/50',
          )}
          style={{ width: `${activePortion}%` }}
        >
          {/* Left resize handle */}
          <div
            className="absolute left-0 top-0 bottom-0 w-3 cursor-ew-resize z-20 flex items-center justify-center hover:bg-teal-500/40 active:bg-teal-500/60"
            onMouseDown={(e) => handleMouseDown(e, 'resize-start')}
          >
            <div className="w-0.5 h-5 bg-teal-400/80 rounded" />
          </div>

          {/* Content */}
          <div
            className={clsx(
              'flex-1 h-full flex items-center gap-1.5 px-3',
              isDragging ? 'cursor-grabbing' : 'cursor-grab'
            )}
            onMouseDown={(e) => handleMouseDown(e, 'move')}
          >
            <Music className="w-3 h-3 text-teal-300 shrink-0" />
            <span className="text-[10px] text-teal-200 truncate flex-1 font-medium">
              {fileName}
            </span>

            {/* Loop indicator */}
            {track.loop && (
              <span className="text-[8px] text-teal-400/70 font-mono">∞</span>
            )}

            {/* Volume Meter - inline before mute */}
            <BGMVolumeMeter
              volume={track.volume}
              onChange={onVolumeChange}
              disabled={track.muted}
            />

            {/* Mute button */}
            <button
              onClick={(e) => {
                e.stopPropagation()
                onMuteToggle()
              }}
              onMouseDown={(e) => e.stopPropagation()}
              className="p-0.5 rounded hover:bg-teal-600/40 text-teal-300 shrink-0"
              title={track.muted ? 'Unmute' : 'Mute'}
            >
              {track.muted ? (
                <VolumeX className="w-3 h-3" />
              ) : (
                <Volume2 className="w-3 h-3" />
              )}
            </button>

            {/* Delete button */}
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
              onMouseDown={(e) => e.stopPropagation()}
              className="p-0.5 rounded hover:bg-red-600/30 text-teal-300 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
              title="Delete track"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>

          {/* Right resize handle */}
          <div
            className="absolute right-0 top-0 bottom-0 w-3 cursor-ew-resize z-20 flex items-center justify-center hover:bg-teal-500/40 active:bg-teal-500/60"
            onMouseDown={(e) => handleMouseDown(e, 'resize-end')}
          >
            <div className="w-0.5 h-5 bg-teal-400/80 rounded" />
          </div>

          {/* Audio progress bar at bottom - shows how much of remaining audio is used */}
          {hasAudioDuration && remainingAudio > 0 && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-black/30">
              <div
                className="h-full bg-cyan-400/70"
                style={{ width: `${Math.min((trackDurationOnTimeline / remainingAudio) * 100, 100)}%` }}
              />
            </div>
          )}
        </div>

        {/* Trimmed END portion - striped/faded */}
        {isTrimmedFromEnd && trimmedEndPortion > 0 && (
          <div
            className="h-full relative border border-teal-600/30 rounded-r"
            style={{
              width: `${trimmedEndPortion}%`,
              background: 'repeating-linear-gradient(-45deg, rgba(20,184,166,0.1), rgba(20,184,166,0.1) 2px, rgba(20,184,166,0.2) 2px, rgba(20,184,166,0.2) 4px)',
            }}
            title={`Trimmed: ${unusedAtEnd.toFixed(1)}s from end`}
          >
            <span className="absolute inset-0 flex items-center justify-center text-[8px] text-teal-500/60 font-mono">
              -{unusedAtEnd.toFixed(1)}s
            </span>
          </div>
        )}
      </div>

      {/* Time display on hover/drag */}
      {(isSelected || isDragging) && (
        <div className="absolute -bottom-5 left-0 right-0 flex justify-between text-[9px] font-mono text-teal-400 pointer-events-none px-1">
          <span>{startTime.toFixed(1)}s</span>
          <span>{endTime.toFixed(1)}s</span>
        </div>
      )}
    </div>
  )
}

export default function Timeline({
  duration,
  projectName,
  onAddSegment,
  // Legacy props - kept for backward compatibility but not used when bgmTracks are present
  backgroundMusicPath: _backgroundMusicPath,
  onBackgroundMusicChange: _onBackgroundMusicChange,
  bgmTracks = [],
  bgmVolume: _bgmVolume = 100,
  ttsVolume: _ttsVolume = 100,
  onBGMTracksChange,
  onBGMTrackUpdate,
  // Multi-video props
  videos = [],
  activeVideoId,
  onSetActiveVideo,
  onVideoPositionChange,
  onVideoPositionUpdate,
  onPlayPreview,
}: TimelineProps) {
  // Legacy props are prefixed with _ to indicate they're not used in this implementation
  // but kept for API compatibility. The new BGM tracks system handles all BGM functionality.
  void _backgroundMusicPath
  void _onBackgroundMusicChange
  void _bgmVolume
  void _ttsVolume
  void onSetActiveVideo // Active video selection is mainly for export, not used in timeline UI
  const { segments, currentTime, setCurrentTime, selectedSegmentId, setSelectedSegmentId, updateSegment, isPlaying, setIsPlaying } =
    useAppStore()

  // Multi-video timeline state
  const [viewMode, setViewMode] = useState<TimelineViewMode>('combined')
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null) // For single video mode
  const [viewDropdownOpen, setViewDropdownOpen] = useState(false)
  const hasMultipleVideos = videos.length > 1

  // Optimistic local state for video positions - kept for backward compatibility
  // When onVideoPositionUpdate is provided, updates go directly to parent state instead
  const [localVideoOverrides, _setLocalVideoOverrides] = useState<{ [videoId: string]: { timeline_start: number; timeline_end: number } }>({})
  void _setLocalVideoOverrides // Unused when using onVideoPositionUpdate callback

  // Stable sorted videos to prevent ordering changes during re-renders
  const sortedVideos = useMemo(() => {
    return [...videos].sort((a, b) => a.order - b.order)
  }, [videos])

  // Minimum clip duration in seconds - must match the constant in drag handler
  const MIN_CLIP_DURATION = 1.0

  // Calculate video timeline positions
  // Uses local overrides first (optimistic), then backend values, then falls back to sequential layout
  // Also validates data to handle corrupted values (e.g., timeline_end < timeline_start + MIN_CLIP_DURATION)
  const videoPositions = useMemo(() => {
    const positions: { [videoId: string]: { start: number; end: number; duration: number } } = {}

    // First, calculate sequential fallback positions for ALL videos
    // This is used when a video doesn't have explicit positions set
    const sequentialPositions: { [videoId: string]: { start: number; end: number } } = {}
    let currentStart = 0
    for (const video of sortedVideos) {
      const videoDuration = video.duration || 0
      sequentialPositions[video.id] = {
        start: currentStart,
        end: currentStart + videoDuration
      }
      currentStart += videoDuration
    }

    // Check if any video has explicit timeline positions set (including local overrides)
    const hasExplicitPositions = sortedVideos.some(v =>
      localVideoOverrides[v.id] || (v.timeline_start !== null && v.timeline_start !== undefined)
    )

    if (hasExplicitPositions) {
      // Use local overrides first, then backend timeline positions when available
      // IMPORTANT: For videos WITHOUT explicit positions, use their sequential fallback
      // This prevents other videos from jumping to 0 when one video is moved
      for (const video of sortedVideos) {
        const videoDuration = video.duration || 0
        const override = localVideoOverrides[video.id]
        const hasBackendPosition = video.timeline_start !== null && video.timeline_start !== undefined
        const hasOverride = override !== undefined

        let start: number
        let end: number

        if (hasOverride) {
          // Use local override (optimistic update)
          start = override.timeline_start
          end = override.timeline_end
        } else if (hasBackendPosition) {
          // Use backend position
          start = video.timeline_start!
          end = video.timeline_end ?? (start + videoDuration)
        } else {
          // No explicit position - use sequential fallback to maintain layout
          start = sequentialPositions[video.id].start
          end = sequentialPositions[video.id].end
        }

        // Validate data: if corrupted (end - start < MIN_CLIP_DURATION), use video duration
        const clipDuration = end - start
        if (clipDuration < MIN_CLIP_DURATION || clipDuration > videoDuration * 2) {
          // Data appears corrupted - reset to full video duration from current start
          console.warn(`[Timeline] Corrupted video position detected for ${video.name}: start=${start}, end=${end}, duration=${videoDuration}. Resetting.`)
          end = start + videoDuration
        }

        positions[video.id] = {
          start,
          end,
          duration: videoDuration
        }
      }
    } else {
      // All videos use sequential layout based on order
      for (const video of sortedVideos) {
        const videoDuration = video.duration || 0
        positions[video.id] = {
          start: sequentialPositions[video.id].start,
          end: sequentialPositions[video.id].end,
          duration: videoDuration
        }
      }
    }
    return positions
  }, [sortedVideos, localVideoOverrides])

  // Total duration = max of video end times (considering timeline positions AND local overrides)
  // This properly handles when videos are repositioned on the timeline
  // Uses videoPositions which already includes localVideoOverrides for consistency
  const totalDuration = useMemo(() => {
    let maxEnd = 0
    for (const videoId in videoPositions) {
      const pos = videoPositions[videoId]
      if (pos.end > maxEnd) {
        maxEnd = pos.end
      }
    }
    // Ensure we have at least the sum of durations if videoPositions is empty
    if (maxEnd === 0) {
      return videos.reduce((sum, v) => sum + (v.duration || 0), 0)
    }
    return maxEnd
  }, [videoPositions, videos])

  // For single video mode, use selected video or active video
  const singleVideoId = selectedVideoId || activeVideoId || videos[0]?.id
  const singleVideo = videos.find(v => v.id === singleVideoId)
  const singleVideoDuration = singleVideo?.duration || duration

  // Base timeline duration: sum of videos for combined view, single video for single view
  const baseTimelineDuration = hasMultipleVideos && viewMode === 'combined' ? totalDuration : singleVideoDuration

  const [isUploadingBgm, setIsUploadingBgm] = useState(false)
  const bgmFileInputRef = useRef<HTMLInputElement>(null)

  // BGM track state - supports multi-selection with Ctrl/Cmd+click and Shift+click
  const [selectedBgmTrackIds, setSelectedBgmTrackIds] = useState<Set<string>>(new Set())
  const [lastSelectedBgmTrackId, setLastSelectedBgmTrackId] = useState<string | null>(null) // For shift+click range selection
  const [bgmDragState, setBgmDragState] = useState<DragState | null>(null)
  const [bgmPreviewTimes, setBgmPreviewTimes] = useState<{ [trackId: string]: { start: number; end: number; audioOffset?: number } }>({})
  // Optimistic local state for BGM tracks - kept for backward compatibility
  // When onBGMTrackUpdate is provided, updates go directly to parent state instead
  const [localBgmOverrides, _setLocalBgmOverrides] = useState<{ [trackId: string]: { start_time: number; end_time: number; audio_offset?: number } }>({})
  void _setLocalBgmOverrides // Unused when using onBGMTrackUpdate callback
  // Separate property overrides for instant updates via WebSocket
  const [localVolumeOverrides, setLocalVolumeOverrides] = useState<{ [trackId: string]: number }>({})
  const [localMuteOverrides, setLocalMuteOverrides] = useState<{ [trackId: string]: boolean }>({})
  const bgmTimelineRef = useRef<HTMLDivElement>(null)

  // Clear overrides when bgmTracks prop changes (server data refreshed)
  const prevBgmTracksRef = useRef(bgmTracks)
  useEffect(() => {
    if (bgmTracks !== prevBgmTracksRef.current) {
      prevBgmTracksRef.current = bgmTracks
      // Clear overrides since we have fresh server data
      setLocalVolumeOverrides({})
      setLocalMuteOverrides({})
    }
  }, [bgmTracks])

  // Merge bgmTracks with local optimistic overrides (position, volume, mute)
  const effectiveBgmTracks = useMemo(() => {
    return bgmTracks.map(track => {
      const posOverride = localBgmOverrides[track.id]
      const volOverride = localVolumeOverrides[track.id]
      const muteOverride = localMuteOverrides[track.id]

      let result = track
      if (posOverride) {
        result = {
          ...result,
          start_time: posOverride.start_time,
          end_time: posOverride.end_time,
          audio_offset: posOverride.audio_offset ?? track.audio_offset
        }
      }
      if (volOverride !== undefined) {
        result = { ...result, volume: volOverride }
      }
      if (muteOverride !== undefined) {
        result = { ...result, muted: muteOverride }
      }
      return result
    })
  }, [bgmTracks, localBgmOverrides, localVolumeOverrides, localMuteOverrides])

  // Playhead drag state
  const [isPlayheadDragging, setIsPlayheadDragging] = useState(false)
  const playheadContainerRef = useRef<HTMLDivElement>(null)

  // Video track drag state (for dragging/trimming video clips)
  const [selectedVideoTrackId, setSelectedVideoTrackId] = useState<string | null>(null)
  const [videoDragState, setVideoDragState] = useState<DragState | null>(null)
  const [videoPreviewPositions, setVideoPreviewPositions] = useState<{ [videoId: string]: { start: number; end: number; sourceStart?: number; sourceEnd?: number | null } }>({})
  // CRITICAL: Use ref to track preview positions for mouseup handler (avoids stale closure)
  const videoPreviewPositionsRef = useRef<{ [videoId: string]: { start: number; end: number; sourceStart?: number; sourceEnd?: number | null } }>({})
  const videoTracksRef = useRef<HTMLDivElement>(null)

  // Snap line state for video and BGM tracks
  const [videoSnapLine, setVideoSnapLine] = useState<{ time: number; type: 'start' | 'end' } | null>(null)
  const [bgmSnapLine, setBgmSnapLine] = useState<{ time: number; type: 'start' | 'end' } | null>(null)
  const VIDEO_SNAP_THRESHOLD_SECONDS = 0.5 // Snap when within 0.5 seconds of another video/BGM edge

  // Pending drag state - only becomes a real drag after mouse moves a threshold distance
  // This allows double-clicks to work without triggering drag
  const pendingVideoDragRef = useRef<{ videoId: string; mode: DragMode; initialX: number; initialY: number } | null>(null)
  const DRAG_THRESHOLD = 5 // pixels

  // WebSocket for real-time timeline synchronization
  const {
    isConnected: _wsConnected,
    updateVideoPosition: wsUpdateVideoPosition,
    updateVideoResize: wsUpdateVideoResize,
    updateBGMTrack: wsUpdateBGMTrack,
    updateSegment: wsUpdateSegment,
  } = useTimelineWebSocket(projectName, {
    onVideoPositionUpdate: useCallback((_data: { video_id: string; timeline_start: number | null; timeline_end: number | null }) => {
      // Handle incoming video position update from other clients
      // Instead of updating preview state, trigger a refetch so parent gets fresh data
      // The preview positions will be cleared as they're not needed for external updates
      console.log('[Timeline] External video position update received, triggering refetch')
      onVideoPositionChange?.()
    }, [onVideoPositionChange]),
    onBGMUpdate: useCallback((_data: { track_id: string; start_time: number; end_time: number }) => {
      // Handle incoming BGM update from other clients - trigger refetch
      console.log('[Timeline] External BGM update received, triggering refetch')
      onBGMTracksChange?.()
    }, [onBGMTracksChange]),
    onError: useCallback((error: string) => {
      console.error('[Timeline] WebSocket error:', error)
    }, [])
  })

  // Calculate effective timeline duration that extends based on content
  // This makes the timeline container dynamically grow when videos/BGM are moved beyond the original duration
  const timelineDuration = useMemo(() => {
    let maxDuration = baseTimelineDuration

    // Consider BGM track end times (including optimistic local overrides)
    for (const track of effectiveBgmTracks) {
      const endTime = track.end_time === 0 ? baseTimelineDuration : track.end_time
      if (endTime > maxDuration) {
        maxDuration = endTime
      }
    }

    // Consider video preview positions (when dragging videos)
    for (const videoId in videoPreviewPositions) {
      const preview = videoPreviewPositions[videoId]
      if (preview.end > maxDuration) {
        maxDuration = preview.end
      }
    }

    // Consider BGM preview times (when dragging BGM tracks)
    for (const trackId in bgmPreviewTimes) {
      const preview = bgmPreviewTimes[trackId]
      if (preview.end > maxDuration) {
        maxDuration = preview.end
      }
    }

    return Math.max(baseTimelineDuration, maxDuration)
  }, [baseTimelineDuration, effectiveBgmTracks, videoPreviewPositions, bgmPreviewTimes])

  // Timeline zoom/pan state - Premiere Pro style
  const [zoomLevel, setZoomLevel] = useState(1) // 1 = fit to view, >1 = zoomed in
  const timelineScrollRef = useRef<HTMLDivElement>(null)
  const MIN_ZOOM = 0.5
  const MAX_ZOOM = 10

  // Zoom handlers
  const handleZoomIn = useCallback(() => {
    setZoomLevel(prev => Math.min(MAX_ZOOM, prev * 1.25))
  }, [])

  const handleZoomOut = useCallback(() => {
    setZoomLevel(prev => Math.max(MIN_ZOOM, prev / 1.25))
  }, [])

  const handleZoomReset = useCallback(() => {
    setZoomLevel(1)
    if (timelineScrollRef.current) {
      timelineScrollRef.current.scrollLeft = 0
    }
  }, [])

  // Ctrl+Scroll to zoom
  useEffect(() => {
    const container = timelineScrollRef.current
    if (!container) return

    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault()
        const delta = e.deltaY > 0 ? 0.9 : 1.1
        setZoomLevel(prev => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, prev * delta)))
      }
    }

    container.addEventListener('wheel', handleWheel, { passive: false })
    return () => container.removeEventListener('wheel', handleWheel)
  }, [])

  // Auto-scroll to keep playhead visible when zoomed
  useEffect(() => {
    if (!timelineScrollRef.current || zoomLevel <= 1) return

    const container = timelineScrollRef.current
    const containerWidth = container.clientWidth
    const totalWidth = containerWidth * zoomLevel
    const playheadPosition = (currentTime / timelineDuration) * totalWidth

    // Only scroll if playhead is outside visible area
    const scrollLeft = container.scrollLeft
    const visibleStart = scrollLeft
    const visibleEnd = scrollLeft + containerWidth

    if (playheadPosition < visibleStart + 50 || playheadPosition > visibleEnd - 50) {
      // Center playhead in view
      container.scrollLeft = playheadPosition - containerWidth / 2
    }
  }, [currentTime, zoomLevel, timelineDuration])

  // Handle BGM file upload - now adds as a track
  const handleBgmUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setIsUploadingBgm(true)
    try {
      const response = await videosApi.uploadAudio(file)
      // Add as a new BGM track
      await projectsApi.addBGMTrack(projectName, {
        path: response.data.path,
        name: file.name.replace(/\.[^/.]+$/, ''), // Remove extension
        start_time: 0,
        end_time: 0, // 0 means until end of video
        volume: 100,
      })
      onBGMTracksChange?.()
      toast.success(`Background music track added: ${file.name}`)
    } catch (error) {
      console.error('Failed to upload audio:', error)
      toast.error('Failed to upload audio file')
    } finally {
      setIsUploadingBgm(false)
      if (bgmFileInputRef.current) {
        bgmFileInputRef.current.value = ''
      }
    }
  }, [projectName, onBGMTracksChange])

  // Handle BGM track mute toggle - WebSocket only, instant local update
  const handleBgmMuteToggle = useCallback((trackId: string) => {
    // Get current mute state (check override first, then original track)
    const currentMuted = localMuteOverrides[trackId] ?? bgmTracks.find(t => t.id === trackId)?.muted ?? false
    const newMuted = !currentMuted

    // Apply local override immediately for instant UI feedback
    setLocalMuteOverrides(prev => ({ ...prev, [trackId]: newMuted }))

    // Notify parent for preview sync (VideoPlayer needs updated bgmTracks)
    onBGMTrackUpdate?.(trackId, { muted: newMuted })

    // Send via WebSocket only - server saves and returns ack
    wsUpdateBGMTrack(trackId, { muted: newMuted })
  }, [bgmTracks, localMuteOverrides, onBGMTrackUpdate, wsUpdateBGMTrack])

  // Handle BGM track volume change - WebSocket only, instant local update
  // Auto-mutes when volume reaches 0, auto-unmutes when volume increases from 0
  const handleBgmVolumeChange = useCallback((trackId: string, volume: number) => {
    // Apply local override immediately for instant UI feedback
    setLocalVolumeOverrides(prev => ({ ...prev, [trackId]: volume }))

    // Get current track state to check muted status
    const track = bgmTracks.find(t => t.id === trackId)
    const currentMuted = localMuteOverrides[trackId] ?? track?.muted ?? false

    // Auto-mute when volume reaches 0
    if (volume === 0 && !currentMuted) {
      setLocalMuteOverrides(prev => ({ ...prev, [trackId]: true }))
      onBGMTrackUpdate?.(trackId, { volume, muted: true })
      wsUpdateBGMTrack(trackId, { volume, muted: true })
      return
    }

    // Auto-unmute when volume increases from 0 (if was auto-muted)
    if (volume > 0 && currentMuted) {
      setLocalMuteOverrides(prev => ({ ...prev, [trackId]: false }))
      onBGMTrackUpdate?.(trackId, { volume, muted: false })
      wsUpdateBGMTrack(trackId, { volume, muted: false })
      return
    }

    // Normal volume change (not at 0 boundary)
    onBGMTrackUpdate?.(trackId, { volume })
    wsUpdateBGMTrack(trackId, { volume })
  }, [wsUpdateBGMTrack, onBGMTrackUpdate, bgmTracks, localMuteOverrides])

  // Handle BGM track delete (single or bulk)
  const handleBgmDelete = useCallback(async (trackId: string) => {
    try {
      await projectsApi.deleteBGMTrack(projectName, trackId)
      setSelectedBgmTrackIds(prev => {
        const next = new Set(prev)
        next.delete(trackId)
        return next
      })
      onBGMTracksChange?.()
      toast.success('Track removed')
    } catch (error) {
      toast.error('Failed to remove track')
    }
  }, [projectName, onBGMTracksChange])

  // Handle bulk delete of selected BGM tracks
  const handleBulkBgmDelete = useCallback(async () => {
    if (selectedBgmTrackIds.size === 0) return

    const trackIds = Array.from(selectedBgmTrackIds)
    const count = trackIds.length

    try {
      // Delete all selected tracks
      await Promise.all(trackIds.map(id => projectsApi.deleteBGMTrack(projectName, id)))
      setSelectedBgmTrackIds(new Set())
      setLastSelectedBgmTrackId(null)
      onBGMTracksChange?.()
      toast.success(`${count} track${count > 1 ? 's' : ''} removed`)
    } catch (error) {
      toast.error('Failed to remove tracks')
    }
  }, [projectName, selectedBgmTrackIds, onBGMTracksChange])

  // Handle BGM track selection with multi-select support (Ctrl/Cmd + click, Shift + click)
  const handleBgmTrackSelect = useCallback((trackId: string, e: React.MouseEvent) => {
    setSelectedSegmentId(null) // Deselect segments when selecting BGM

    if (e.shiftKey && lastSelectedBgmTrackId) {
      // Shift+click: select range
      const trackIds = effectiveBgmTracks.map(t => t.id)
      const lastIndex = trackIds.indexOf(lastSelectedBgmTrackId)
      const currentIndex = trackIds.indexOf(trackId)

      if (lastIndex !== -1 && currentIndex !== -1) {
        const start = Math.min(lastIndex, currentIndex)
        const end = Math.max(lastIndex, currentIndex)
        const rangeIds = trackIds.slice(start, end + 1)

        setSelectedBgmTrackIds(prev => {
          const next = new Set(prev)
          rangeIds.forEach(id => next.add(id))
          return next
        })
      }
    } else if (e.ctrlKey || e.metaKey) {
      // Ctrl/Cmd+click: toggle selection
      setSelectedBgmTrackIds(prev => {
        const next = new Set(prev)
        if (next.has(trackId)) {
          next.delete(trackId)
        } else {
          next.add(trackId)
        }
        return next
      })
      setLastSelectedBgmTrackId(trackId)
    } else {
      // Regular click: select only this track
      setSelectedBgmTrackIds(new Set([trackId]))
      setLastSelectedBgmTrackId(trackId)
    }
  }, [lastSelectedBgmTrackId, effectiveBgmTracks, setSelectedSegmentId])

  // Handle bulk mute/unmute of selected BGM tracks
  const handleBulkBgmMute = useCallback(async (mute: boolean) => {
    if (selectedBgmTrackIds.size === 0) return

    try {
      await Promise.all(
        Array.from(selectedBgmTrackIds).map(id =>
          projectsApi.updateBGMTrack(projectName, id, { muted: mute })
        )
      )
      onBGMTracksChange?.()
      toast.success(`${selectedBgmTrackIds.size} track${selectedBgmTrackIds.size > 1 ? 's' : ''} ${mute ? 'muted' : 'unmuted'}`)
    } catch (error) {
      toast.error('Failed to update tracks')
    }
  }, [projectName, selectedBgmTrackIds, onBGMTracksChange])

  // Clear BGM selection
  const clearBgmSelection = useCallback(() => {
    setSelectedBgmTrackIds(new Set())
    setLastSelectedBgmTrackId(null)
  }, [])

  // Handle BGM track drag start
  const handleBgmDragStart = useCallback((trackId: string, e: React.MouseEvent, mode: DragMode) => {
    const track = bgmTracks.find(t => t.id === trackId)
    if (!track) return

    // Stop playback when starting drag to prevent audio sync issues
    if (isPlaying) setIsPlaying(false)

    setBgmDragState({
      segmentId: trackId, // Reusing segmentId field for trackId
      mode,
      initialMouseX: e.clientX,
      initialStartTime: track.start_time,
      initialEndTime: track.end_time === 0 ? timelineDuration : track.end_time,
      initialAudioOffset: track.audio_offset ?? 0,
    })

    // When dragging, select only this track (unless already selected in multi-select)
    if (!selectedBgmTrackIds.has(trackId)) {
      setSelectedBgmTrackIds(new Set([trackId]))
      setLastSelectedBgmTrackId(trackId)
    }
    setSelectedSegmentId(null) // Deselect any selected segment
  }, [bgmTracks, timelineDuration, setSelectedSegmentId, isPlaying, setIsPlaying, selectedBgmTrackIds])

  // Handle BGM track drag
  useEffect(() => {
    if (!bgmDragState) return

    // Get the track being dragged for audio duration info
    const track = bgmTracks.find(t => t.id === bgmDragState.segmentId)
    const audioDuration = track?.duration || null

    const handleMouseMove = (e: MouseEvent) => {
      if (!bgmTimelineRef.current) return

      const rect = bgmTimelineRef.current.getBoundingClientRect()
      const deltaX = e.clientX - bgmDragState.initialMouseX
      // Account for zoom level when calculating delta time (matches video drag behavior)
      const effectiveWidth = rect.width * zoomLevel
      const deltaTime = (deltaX / effectiveWidth) * timelineDuration

      let newStart = bgmDragState.initialStartTime
      let newEnd = bgmDragState.initialEndTime
      let newAudioOffset = bgmDragState.initialAudioOffset ?? 0
      const currentAudioOffset = bgmDragState.initialAudioOffset ?? 0

      // Collect snap points from other BGM tracks and video edges
      const bgmSnapPoints: number[] = []
      bgmTracks.forEach(t => {
        if (t.id === bgmDragState.segmentId) return
        bgmSnapPoints.push(t.start_time)
        bgmSnapPoints.push(t.end_time === 0 ? timelineDuration : t.end_time)
      })
      // Also add video edges as snap points
      videos.forEach(v => {
        const vPos = videoPositions[v.id]
        if (vPos) {
          bgmSnapPoints.push(vPos.start)
          bgmSnapPoints.push(vPos.end)
        }
      })
      // Add timeline boundaries
      bgmSnapPoints.push(0)
      bgmSnapPoints.push(timelineDuration)

      if (bgmDragState.mode === 'move') {
        const trackDuration = bgmDragState.initialEndTime - bgmDragState.initialStartTime
        newStart = bgmDragState.initialStartTime + deltaTime
        newEnd = newStart + trackDuration

        // Only prevent going below 0, allow extending past timeline end (it will grow)
        if (newStart < 0) {
          newStart = 0
          newEnd = trackDuration
        }

        // Check for snap points - snap track start or end to nearby edges
        let snappedTo: { time: number; type: 'start' | 'end' } | null = null

        // Check if track START is near any snap point
        for (const snapPoint of bgmSnapPoints) {
          if (Math.abs(newStart - snapPoint) < VIDEO_SNAP_THRESHOLD_SECONDS) {
            newStart = snapPoint
            newEnd = newStart + trackDuration
            snappedTo = { time: snapPoint, type: 'start' }
            break
          }
        }

        // If not snapped by start, check if track END is near any snap point
        if (!snappedTo) {
          for (const snapPoint of bgmSnapPoints) {
            if (Math.abs(newEnd - snapPoint) < VIDEO_SNAP_THRESHOLD_SECONDS) {
              newEnd = snapPoint
              newStart = newEnd - trackDuration
              snappedTo = { time: snapPoint, type: 'end' }
              break
            }
          }
        }

        setBgmSnapLine(snappedTo)
        // audio_offset stays the same when moving
      } else if (bgmDragState.mode === 'resize-start') {
        // Resizing from start: adjust both start time and audio_offset
        newStart = bgmDragState.initialStartTime + deltaTime
        const startDelta = newStart - bgmDragState.initialStartTime
        newAudioOffset = (bgmDragState.initialAudioOffset ?? 0) + startDelta

        // Clamp audio offset to valid range
        if (audioDuration !== null) {
          newAudioOffset = Math.max(0, newAudioOffset)
          newAudioOffset = Math.min(audioDuration - 1, newAudioOffset)
        } else {
          newAudioOffset = Math.max(0, newAudioOffset)
        }

        // Recalculate newStart based on clamped audio offset
        newStart = bgmDragState.initialStartTime + (newAudioOffset - (bgmDragState.initialAudioOffset ?? 0))
        newStart = Math.max(0, newStart)
        newStart = Math.min(newStart, bgmDragState.initialEndTime - 1)

        // Check for snap on resize-start
        let snappedTo: { time: number; type: 'start' | 'end' } | null = null
        for (const snapPoint of bgmSnapPoints) {
          if (Math.abs(newStart - snapPoint) < VIDEO_SNAP_THRESHOLD_SECONDS) {
            const snapDelta = snapPoint - newStart
            const proposedAudioOffset = newAudioOffset + snapDelta

            // Only apply snap if resulting audio offset is valid
            const minOffset = 0
            const maxOffset = audioDuration !== null ? audioDuration - 1 : Infinity

            if (proposedAudioOffset >= minOffset && proposedAudioOffset <= maxOffset) {
              newStart = snapPoint
              newAudioOffset = proposedAudioOffset
              snappedTo = { time: snapPoint, type: 'start' }
            }
            break
          }
        }
        setBgmSnapLine(snappedTo)
      } else if (bgmDragState.mode === 'resize-end') {
        newEnd = bgmDragState.initialEndTime + deltaTime
        // Only prevent making the track too short
        newEnd = Math.max(newEnd, bgmDragState.initialStartTime + 1)

        // Limit extension to audio duration (can't extend beyond available audio)
        if (audioDuration !== null) {
          const maxEndBasedOnAudio = bgmDragState.initialStartTime + (audioDuration - currentAudioOffset)
          newEnd = Math.min(newEnd, maxEndBasedOnAudio)
        }

        // Check for snap on resize-end
        let snappedTo: { time: number; type: 'start' | 'end' } | null = null
        for (const snapPoint of bgmSnapPoints) {
          if (Math.abs(newEnd - snapPoint) < VIDEO_SNAP_THRESHOLD_SECONDS) {
            newEnd = snapPoint
            snappedTo = { time: snapPoint, type: 'end' }
            break
          }
        }
        setBgmSnapLine(snappedTo)
      }

      // Round to millisecond precision
      newStart = Math.round(newStart * 1000) / 1000
      newEnd = Math.round(newEnd * 1000) / 1000
      newAudioOffset = Math.round(newAudioOffset * 1000) / 1000

      setBgmPreviewTimes(prev => ({
        ...prev,
        [bgmDragState.segmentId]: { start: newStart, end: newEnd, audioOffset: newAudioOffset }
      }))
    }

    const handleMouseUp = () => {
      if (!bgmDragState) return

      // Clear snap line
      setBgmSnapLine(null)

      const preview = bgmPreviewTimes[bgmDragState.segmentId]
      if (preview) {
        const trackId = bgmDragState.segmentId
        const newStart = preview.start
        const newEnd = preview.end
        const newAudioOffset = preview.audioOffset ?? bgmDragState.initialAudioOffset ?? 0

        // OPTIMISTIC UI: Update parent state immediately for instant feedback
        // This avoids the lag caused by waiting for refetch
        onBGMTrackUpdate?.(trackId, {
          start_time: newStart,
          end_time: newEnd,
          audio_offset: newAudioOffset
        })

        // Clear drag state and preview immediately for responsive UI
        setBgmDragState(null)
        setBgmPreviewTimes(prev => {
          const next = { ...prev }
          delete next[trackId]
          return next
        })

        // Send update via WebSocket - this persists to server
        wsUpdateBGMTrack(trackId, { start_time: newStart, end_time: newEnd, audio_offset: newAudioOffset })
        console.log(`[Timeline] BGM track updated via WebSocket: ${newStart.toFixed(1)}s - ${newEnd.toFixed(1)}s, offset: ${newAudioOffset.toFixed(1)}s`)
      } else {
        setBgmDragState(null)
      }
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [bgmDragState, duration, bgmPreviewTimes, onBGMTrackUpdate, wsUpdateBGMTrack, bgmTracks, timelineDuration, zoomLevel, videos, videoPositions])

  // Handle video track drag start - uses pending drag to allow double-clicks
  const handleVideoTrackDragStart = useCallback((videoId: string, e: React.MouseEvent, mode: DragMode) => {
    const video = videos.find(v => v.id === videoId)
    if (!video) return

    setSelectedVideoTrackId(videoId)
    setSelectedSegmentId(null)
    clearBgmSelection()

    // For resize operations, start immediately (no threshold needed)
    // This makes trim handles feel more responsive
    if (mode === 'resize-start' || mode === 'resize-end') {
      const videoPos = videoPositions[videoId]
      setVideoDragState({
        segmentId: videoId,
        mode: mode,
        initialMouseX: e.clientX,
        initialStartTime: videoPos?.start || 0,
        initialEndTime: videoPos?.end || (video.duration || 0),
        // Capture source trim values for proper trimming
        initialSourceStart: video.source_start ?? 0,
        initialSourceEnd: video.source_end ?? video.duration,
      })
      return
    }

    // For move operations, use pending drag with threshold (to allow double-click)
    pendingVideoDragRef.current = {
      videoId,
      mode,
      initialX: e.clientX,
      initialY: e.clientY
    }
  }, [videos, videoPositions, setSelectedSegmentId])

  // Activate pending video drag when mouse moves beyond threshold
  const activatePendingVideoDrag = useCallback(() => {
    const pending = pendingVideoDragRef.current
    if (!pending) return

    const video = videos.find(v => v.id === pending.videoId)
    if (!video) return

    const videoPos = videoPositions[pending.videoId]
    setVideoDragState({
      segmentId: pending.videoId,
      mode: pending.mode,
      initialMouseX: pending.initialX,
      initialStartTime: videoPos?.start || 0,
      initialEndTime: videoPos?.end || (video.duration || 0),
      // Capture source trim values for consistency (even for move operations)
      // Move operations don't modify these, but having them ensures data integrity
      initialSourceStart: video.source_start ?? 0,
      initialSourceEnd: video.source_end ?? video.duration,
    })

    pendingVideoDragRef.current = null
  }, [videos, videoPositions])

  // Handle pending video drag - check threshold before activating real drag
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const pending = pendingVideoDragRef.current
      if (!pending) return

      // Check if mouse has moved beyond threshold
      const dx = Math.abs(e.clientX - pending.initialX)
      const dy = Math.abs(e.clientY - pending.initialY)
      if (dx > DRAG_THRESHOLD || dy > DRAG_THRESHOLD) {
        activatePendingVideoDrag()
      }
    }

    const handleMouseUp = () => {
      // Clear pending drag on mouseup (click without drag)
      pendingVideoDragRef.current = null
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [activatePendingVideoDrag])

  // Handle video track drag effect (actual dragging)
  useEffect(() => {
    if (!videoDragState) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!videoTracksRef.current) return

      const rect = videoTracksRef.current.getBoundingClientRect()
      const deltaX = e.clientX - videoDragState.initialMouseX
      // Account for zoom level when calculating delta time
      const effectiveWidth = rect.width * zoomLevel
      const deltaTime = (deltaX / effectiveWidth) * timelineDuration

      const video = videos.find(v => v.id === videoDragState.segmentId)
      if (!video) return

      const videoDuration = video.duration || 0
      let newStart = videoDragState.initialStartTime
      let newEnd = videoDragState.initialEndTime
      const currentClipDuration = videoDragState.initialEndTime - videoDragState.initialStartTime

      // Track source trim changes for proper in/out point trimming
      let newSourceStart = videoDragState.initialSourceStart ?? 0
      let newSourceEnd = videoDragState.initialSourceEnd ?? videoDuration

      // Collect snap points from other videos and BGM tracks
      const videoSnapPoints: number[] = []
      videos.forEach(v => {
        if (v.id === videoDragState.segmentId) return
        const vPos = videoPositions[v.id]
        if (vPos) {
          videoSnapPoints.push(vPos.start)
          videoSnapPoints.push(vPos.end)
        }
      })
      // Also add BGM track edges as snap points
      bgmTracks.forEach(t => {
        videoSnapPoints.push(t.start_time)
        videoSnapPoints.push(t.end_time === 0 ? timelineDuration : t.end_time)
      })
      // Add timeline boundaries
      videoSnapPoints.push(0)
      videoSnapPoints.push(timelineDuration)

      if (videoDragState.mode === 'move') {
        // Move preserves clip duration, just shifts position
        newStart = videoDragState.initialStartTime + deltaTime
        newEnd = newStart + currentClipDuration

        // Clamp to timeline bounds (can't go negative)
        if (newStart < 0) {
          newStart = 0
          newEnd = currentClipDuration
        }
        // Allow extending timeline by moving video to the right (no max clamp)

        // Check for snap points - snap video start or end to nearby edges
        let snappedTo: { time: number; type: 'start' | 'end' } | null = null

        // Check if video START is near any snap point
        for (const snapPoint of videoSnapPoints) {
          if (Math.abs(newStart - snapPoint) < VIDEO_SNAP_THRESHOLD_SECONDS) {
            newStart = snapPoint
            newEnd = newStart + currentClipDuration
            snappedTo = { time: snapPoint, type: 'start' }
            break
          }
        }

        // If not snapped by start, check if video END is near any snap point
        if (!snappedTo) {
          for (const snapPoint of videoSnapPoints) {
            if (Math.abs(newEnd - snapPoint) < VIDEO_SNAP_THRESHOLD_SECONDS) {
              newEnd = snapPoint
              newStart = newEnd - currentClipDuration
              snappedTo = { time: snapPoint, type: 'end' }
              break
            }
          }
        }

        setVideoSnapLine(snappedTo)
        // Move doesn't change source trim - same content, different position
      } else if (videoDragState.mode === 'resize-start') {
        // Trim from start - adjust in-point, keep out-point fixed
        // IMPORTANT: Source start moves by same delta to skip that content
        newStart = videoDragState.initialStartTime + deltaTime

        // Can't go below 0
        newStart = Math.max(0, newStart)
        // Can't make clip shorter than minimum duration
        newStart = Math.min(newStart, videoDragState.initialEndTime - MIN_CLIP_DURATION)

        // Calculate how much timeline start moved
        const startDelta = newStart - videoDragState.initialStartTime
        // Source start moves by same amount (to skip that portion of source video)
        newSourceStart = (videoDragState.initialSourceStart ?? 0) + startDelta
        // Clamp source start to valid range (0 to source_end - MIN_CLIP_DURATION)
        newSourceStart = Math.max(0, newSourceStart)
        if (newSourceEnd !== null) {
          newSourceStart = Math.min(newSourceStart, newSourceEnd - MIN_CLIP_DURATION)
        }

        // Check for snap on resize-start
        let snappedTo: { time: number; type: 'start' | 'end' } | null = null
        for (const snapPoint of videoSnapPoints) {
          if (Math.abs(newStart - snapPoint) < VIDEO_SNAP_THRESHOLD_SECONDS) {
            const snapDelta = snapPoint - newStart
            newStart = snapPoint
            newSourceStart = newSourceStart + snapDelta
            snappedTo = { time: snapPoint, type: 'start' }
            break
          }
        }
        setVideoSnapLine(snappedTo)

        // newEnd stays at initial value (preserving out-point)
      } else if (videoDragState.mode === 'resize-end') {
        // Trim from end - adjust out-point, keep in-point fixed
        // IMPORTANT: Source end moves by same delta to cut that content
        newEnd = videoDragState.initialEndTime + deltaTime

        // Can't make clip shorter than minimum duration
        newEnd = Math.max(newEnd, videoDragState.initialStartTime + MIN_CLIP_DURATION)
        // Can extend up to the video's actual remaining duration
        const maxExtension = videoDuration - (videoDragState.initialSourceStart ?? 0)
        const maxEnd = videoDragState.initialStartTime + maxExtension
        newEnd = Math.min(newEnd, maxEnd)

        // Calculate how much timeline end moved
        const endDelta = newEnd - videoDragState.initialEndTime
        // Source end moves by same amount
        const initialSourceEnd = videoDragState.initialSourceEnd ?? videoDuration
        newSourceEnd = initialSourceEnd + endDelta
        // Clamp source end to valid range (source_start + MIN_CLIP_DURATION to video duration)
        newSourceEnd = Math.max(newSourceEnd, (videoDragState.initialSourceStart ?? 0) + MIN_CLIP_DURATION)
        newSourceEnd = Math.min(newSourceEnd, videoDuration)

        // Check for snap on resize-end
        let snappedTo: { time: number; type: 'start' | 'end' } | null = null
        for (const snapPoint of videoSnapPoints) {
          if (Math.abs(newEnd - snapPoint) < VIDEO_SNAP_THRESHOLD_SECONDS) {
            const snapDelta = snapPoint - newEnd
            newEnd = snapPoint
            newSourceEnd = (newSourceEnd ?? videoDuration) + snapDelta
            snappedTo = { time: snapPoint, type: 'end' }
            break
          }
        }
        setVideoSnapLine(snappedTo)

        // newStart stays at initial value (preserving in-point)
      }

      // Round to millisecond precision (0.001s) for accurate timeline control
      newStart = Math.round(newStart * 1000) / 1000
      newEnd = Math.round(newEnd * 1000) / 1000
      newSourceStart = Math.round(newSourceStart * 1000) / 1000
      if (newSourceEnd !== null) {
        newSourceEnd = Math.round(newSourceEnd * 1000) / 1000
      }

      // Update both state AND ref (ref is critical for mouseup handler to read latest value)
      const newPreview = { start: newStart, end: newEnd, sourceStart: newSourceStart, sourceEnd: newSourceEnd }
      videoPreviewPositionsRef.current = {
        ...videoPreviewPositionsRef.current,
        [videoDragState.segmentId]: newPreview
      }
      setVideoPreviewPositions(prev => ({
        ...prev,
        [videoDragState.segmentId]: newPreview
      }))
    }

    const handleMouseUp = () => {
      if (!videoDragState) return

      // Clear snap line
      setVideoSnapLine(null)

      // CRITICAL: Read from ref, not state - state may be stale due to closure
      const preview = videoPreviewPositionsRef.current[videoDragState.segmentId]
      if (preview) {
        const videoId = videoDragState.segmentId
        const newStart = preview.start
        const newEnd = preview.end
        const sourceStart = preview.sourceStart
        const sourceEnd = preview.sourceEnd

        // OPTIMISTIC UI: Update parent state immediately for instant feedback
        // This avoids the lag caused by waiting for refetch
        onVideoPositionUpdate?.(videoId, {
          timeline_start: newStart,
          timeline_end: newEnd,
          source_start: sourceStart,
          source_end: sourceEnd
        })

        // Clear drag state and preview immediately for responsive UI
        setVideoDragState(null)
        // Clear from both ref and state
        const refNext = { ...videoPreviewPositionsRef.current }
        delete refNext[videoId]
        videoPreviewPositionsRef.current = refNext
        setVideoPreviewPositions(prev => {
          const next = { ...prev }
          delete next[videoId]
          return next
        })

        // Send update via WebSocket for real-time sync with backend
        const isResize = videoDragState.mode === 'resize-start' || videoDragState.mode === 'resize-end'

        // Send update via WebSocket - this persists to server
        if (isResize) {
          wsUpdateVideoResize(videoId, newStart, newEnd, sourceStart, sourceEnd)
          console.log(`[Timeline] Video resized via WebSocket: timeline=${newStart.toFixed(1)}s-${newEnd.toFixed(1)}s, source=${sourceStart?.toFixed(1) ?? 0}s-${sourceEnd?.toFixed(1) ?? '?'}s`)
        } else {
          wsUpdateVideoPosition(videoId, newStart, newEnd)
          console.log(`[Timeline] Video moved via WebSocket: ${newStart.toFixed(1)}s - ${newEnd.toFixed(1)}s`)
        }
      } else {
        setVideoDragState(null)
      }
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  // Note: videoPreviewPositions removed from deps - we read from videoPreviewPositionsRef instead to avoid stale closure
  }, [videoDragState, timelineDuration, videos, wsUpdateVideoPosition, wsUpdateVideoResize, onVideoPositionUpdate, zoomLevel])

  const timelineRef = useRef<HTMLDivElement>(null)
  const voiceOverTrackRef = useRef<HTMLDivElement>(null)
  const [dragState, setDragState] = useState<DragState | null>(null)
  const [previewTimes, setPreviewTimes] = useState<{ [segmentId: string]: { start: number; end: number; audioOffset?: number } }>({})

  // Snap line state for visual indicator when dragging near segment edges
  const [snapLine, setSnapLine] = useState<{ time: number; type: 'start' | 'end' } | null>(null)
  const SNAP_THRESHOLD_SECONDS = 0.5 // Snap when within 0.5 seconds of another segment edge

  // Generate time markers
  const markers = useMemo(() => {
    const interval = timelineDuration > 300 ? 60 : timelineDuration > 60 ? 10 : 5
    const count = Math.floor(timelineDuration / interval)
    return Array.from({ length: count + 1 }, (_, i) => i * interval)
  }, [timelineDuration])

  // Handle drag start
  const handleDragStart = useCallback((segmentId: string, e: React.MouseEvent, mode: DragMode) => {
    const segment = segments.find(s => s.id === segmentId)
    if (!segment) return

    // Stop playback when starting to drag/trim - prevents audio confusion
    if (isPlaying) {
      setIsPlaying(false)
    }

    setDragState({
      segmentId,
      mode,
      initialMouseX: e.clientX,
      initialStartTime: segment.start_time,
      initialEndTime: segment.end_time,
      initialAudioOffset: segment.audio_offset ?? 0,
    })

    setSelectedSegmentId(segmentId)
  }, [segments, setSelectedSegmentId, isPlaying, setIsPlaying])

  // Handle mouse move during drag
  useEffect(() => {
    if (!dragState) return

    const handleMouseMove = (e: MouseEvent) => {
      const currentSegment = segments.find(s => s.id === dragState.segmentId)
      if (!currentSegment) return

      // Use correct ref based on view mode - Voice Over track for combined mode, timeline for single
      const trackRef = (hasMultipleVideos && viewMode === 'combined') ? voiceOverTrackRef : timelineRef
      if (!trackRef.current) return

      const rect = trackRef.current.getBoundingClientRect()
      const deltaX = e.clientX - dragState.initialMouseX
      // Use timelineDuration for combined multi-video mode, otherwise use single video duration
      const effectiveDuration = (hasMultipleVideos && viewMode === 'combined') ? timelineDuration : duration
      // Account for zoom level when calculating delta time (matches video/BGM drag behavior)
      const effectiveWidth = rect.width * zoomLevel
      const deltaTime = (deltaX / effectiveWidth) * effectiveDuration

      let newStart = dragState.initialStartTime
      let newEnd = dragState.initialEndTime
      let newAudioOffset = dragState.initialAudioOffset ?? 0

      // For multi-video mode, get the segment's video bounds (segment times are relative to video)
      const segmentVideoPos = currentSegment.video_id ? videoPositions[currentSegment.video_id] : null
      const maxSegmentTime = segmentVideoPos?.duration ?? effectiveDuration

      // Get audio duration for limiting extension (use estimated_audio_duration if available)
      const audioDuration = currentSegment.estimated_audio_duration ?? null
      const currentAudioOffset = currentSegment.audio_offset ?? 0

      // Collect snap points from other segments
      const snapPoints: number[] = []
      const isGenericSegment = !currentSegment.video_id
      segments.forEach(s => {
        if (s.id === dragState.segmentId) return
        // For generic segments, snap to all other generic segments
        // For video-specific segments, snap to same video only
        if (isGenericSegment) {
          if (!s.video_id) {
            // Snap to other generic segments
            snapPoints.push(s.start_time)
            snapPoints.push(s.end_time)
          }
        } else {
          if (s.video_id === currentSegment.video_id) {
            snapPoints.push(s.start_time)
            snapPoints.push(s.end_time)
          }
        }
      })
      // For generic segments in multi-video mode, also add video edges as snap points
      if (isGenericSegment && hasMultipleVideos) {
        videos.forEach(v => {
          const vPos = videoPositions[v.id]
          if (vPos) {
            snapPoints.push(vPos.start)
            snapPoints.push(vPos.end)
          }
        })
      }
      // Also add timeline boundaries
      snapPoints.push(0)
      snapPoints.push(maxSegmentTime)

      // Calculate new times based on drag mode
      if (dragState.mode === 'move') {
        const segmentDuration = dragState.initialEndTime - dragState.initialStartTime
        newStart = dragState.initialStartTime + deltaTime
        newEnd = newStart + segmentDuration

        // Clamp to bounds (video duration for multi-video, timeline duration for single)
        if (newStart < 0) {
          newStart = 0
          newEnd = segmentDuration
        }
        if (newEnd > maxSegmentTime) {
          newEnd = maxSegmentTime
          newStart = maxSegmentTime - segmentDuration
        }

        // Check for snap points - snap segment start or end to nearby segment edges
        let snappedTo: { time: number; type: 'start' | 'end' } | null = null

        // Check if segment START is near any snap point
        for (const snapPoint of snapPoints) {
          if (Math.abs(newStart - snapPoint) < SNAP_THRESHOLD_SECONDS) {
            newStart = snapPoint
            newEnd = newStart + segmentDuration
            snappedTo = { time: snapPoint, type: 'start' }
            break
          }
        }

        // If not snapped by start, check if segment END is near any snap point
        if (!snappedTo) {
          for (const snapPoint of snapPoints) {
            if (Math.abs(newEnd - snapPoint) < SNAP_THRESHOLD_SECONDS) {
              newEnd = snapPoint
              newStart = newEnd - segmentDuration
              snappedTo = { time: snapPoint, type: 'end' }
              break
            }
          }
        }

        setSnapLine(snappedTo)
        // Move doesn't change audio offset
      } else if (dragState.mode === 'resize-start') {
        // Trimming from start - this adjusts both timeline position AND audio offset
        newStart = dragState.initialStartTime + deltaTime

        // Calculate how much the start moved
        const startDelta = newStart - dragState.initialStartTime

        // Update audio offset - skip more audio when trimming from start
        newAudioOffset = (dragState.initialAudioOffset ?? 0) + startDelta

        // Clamp audio offset to valid range (0 to audio duration - 1 second minimum)
        if (audioDuration !== null) {
          newAudioOffset = Math.max(0, newAudioOffset)
          newAudioOffset = Math.min(audioDuration - 1, newAudioOffset)

          // Recalculate newStart based on clamped audio offset
          const actualStartDelta = newAudioOffset - (dragState.initialAudioOffset ?? 0)
          newStart = dragState.initialStartTime + actualStartDelta
        } else {
          // No audio duration info - just clamp to reasonable bounds
          newAudioOffset = Math.max(0, newAudioOffset)
        }

        // Minimum segment duration of 1 second
        newStart = Math.min(newStart, dragState.initialEndTime - 1)
        newStart = Math.max(0, newStart)
      } else if (dragState.mode === 'resize-end') {
        newEnd = dragState.initialEndTime + deltaTime
        // Minimum segment duration of 1 second
        newEnd = Math.max(newEnd, dragState.initialStartTime + 1)

        // Limit extension to audio duration (can't extend beyond what audio exists)
        if (audioDuration !== null) {
          const maxEndBasedOnAudio = dragState.initialStartTime + (audioDuration - currentAudioOffset)
          newEnd = Math.min(newEnd, maxEndBasedOnAudio)
        }

        newEnd = Math.min(maxSegmentTime, newEnd)
      }

      // Round to millisecond precision (3 decimal places)
      newStart = Math.round(newStart * 1000) / 1000
      newEnd = Math.round(newEnd * 1000) / 1000
      newAudioOffset = Math.round(newAudioOffset * 1000) / 1000

      // Update preview
      setPreviewTimes(prev => ({
        ...prev,
        [dragState.segmentId]: { start: newStart, end: newEnd, audioOffset: newAudioOffset }
      }))
    }

    const handleMouseUp = async () => {
      if (!dragState) return

      // Clear snap line
      setSnapLine(null)

      const preview = previewTimes[dragState.segmentId]
      const currentSegment = segments.find(s => s.id === dragState.segmentId)
      if (preview && currentSegment) {
        // Check for overlaps with other segments
        // For generic segments (video_id = null): check against all other generic segments using absolute times
        // For video-specific segments: check only against same-video segments using relative times
        const isGenericSegment = !currentSegment.video_id

        // IMPORTANT: Use epsilon tolerance to allow edge-to-edge contact (magnetic snap)
        // Without this, floating-point precision issues cause false overlap detection
        // when segments are snapped exactly to each other's edges
        const OVERLAP_EPSILON = 0.01 // 10ms tolerance for edge contact

        const hasOverlap = segments.some(s => {
          if (s.id === dragState.segmentId) return false

          if (isGenericSegment) {
            // Generic segment: only check against other generic segments
            // Both use absolute timeline times, so direct comparison works
            if (s.video_id) return false // Skip video-specific segments
            // Use epsilon: segments can touch (within 10ms) without overlapping
            return preview.start < (s.end_time - OVERLAP_EPSILON) && preview.end > (s.start_time + OVERLAP_EPSILON)
          } else {
            // Video-specific segment: only check against same-video segments
            if (s.video_id !== currentSegment.video_id) return false
            // Use epsilon: segments can touch (within 10ms) without overlapping
            return preview.start < (s.end_time - OVERLAP_EPSILON) && preview.end > (s.start_time + OVERLAP_EPSILON)
          }
        })

        if (hasOverlap) {
          toast.error('Segment overlaps with another segment')
          setPreviewTimes(prev => {
            const next = { ...prev }
            delete next[dragState.segmentId]
            return next
          })
          setDragState(null)
          return
        }

        // Build update data - include audio_offset if it changed
        const updateData: { start_time: number; end_time: number; audio_offset?: number } = {
          start_time: preview.start,
          end_time: preview.end,
        }
        // Only include audio_offset if it was actually changed (resize-start operation)
        if (preview.audioOffset !== undefined && preview.audioOffset !== (currentSegment.audio_offset ?? 0)) {
          updateData.audio_offset = preview.audioOffset
        }

        // Optimistically update local store with preview data
        updateSegment({
          ...currentSegment,
          start_time: preview.start,
          end_time: preview.end,
          audio_offset: updateData.audio_offset ?? currentSegment.audio_offset ?? 0
        })

        // Send update via WebSocket - this persists to server
        wsUpdateSegment(dragState.segmentId, updateData)

        // Clear preview
        setPreviewTimes(prev => {
          const next = { ...prev }
          delete next[dragState.segmentId]
          return next
        })
      }

      setDragState(null)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [dragState, duration, segments, previewTimes, updateSegment, wsUpdateSegment, hasMultipleVideos, viewMode, timelineDuration, videoPositions, zoomLevel, videos])

  // Handle playhead drag
  const handlePlayheadDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsPlayheadDragging(true)
  }, [])

  // Playhead drag effect
  useEffect(() => {
    if (!isPlayheadDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!playheadContainerRef.current) return
      const rect = playheadContainerRef.current.getBoundingClientRect()
      const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
      const newTime = pos * timelineDuration
      setCurrentTime(newTime)
    }

    const handleMouseUp = () => {
      setIsPlayheadDragging(false)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isPlayheadDragging, timelineDuration, setCurrentTime])

  // Handle scrubber/ruler click to position playhead
  const handleScrubberClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const newTime = pos * timelineDuration
    setCurrentTime(newTime)
  }, [timelineDuration, setCurrentTime])

  // Handle scrubber drag for continuous scrubbing
  const handleScrubberMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    handleScrubberClick(e)
    setIsPlayheadDragging(true)
  }, [handleScrubberClick])

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>, videoId?: string) => {
    if (dragState) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width

    // In combined view with specific video, calculate project time
    if (hasMultipleVideos && viewMode === 'combined' && videoId) {
      const videoPos = videoPositions[videoId]
      const videoDuration = videoPos?.duration || duration
      const videoRelativeTime = pos * videoDuration
      // Convert to project timeline position
      const projectTime = (videoPos?.start || 0) + videoRelativeTime
      setCurrentTime(projectTime)
    } else {
      const newTime = pos * timelineDuration
      setCurrentTime(newTime)
    }
  }

  const playheadPercent = (currentTime / timelineDuration) * 100

  // Detect which videos are at the current playhead position (for smart Add button)
  const videosAtPlayhead = useMemo(() => {
    if (!hasMultipleVideos || viewMode === 'single') {
      // Single video mode - use the single video
      return singleVideoId ? [{ id: singleVideoId, name: videos.find(v => v.id === singleVideoId)?.name || 'Video' }] : []
    }
    // Combined view - find all videos at current playhead position
    const atPlayhead: { id: string; name: string; localTime: number }[] = []
    for (const video of videos) {
      const pos = videoPositions[video.id]
      if (pos && currentTime >= pos.start && currentTime < pos.end) {
        // Playhead is within this video's timeline range
        const localTime = Math.max(0, Math.min(currentTime - pos.start, pos.duration))
        atPlayhead.push({ id: video.id, name: video.name, localTime })
      }
    }
    return atPlayhead
  }, [hasMultipleVideos, viewMode, singleVideoId, videos, videoPositions, currentTime])


  // Video track colors for differentiation
  const videoTrackColors = [
    { bg: 'bg-purple-600/20', border: 'border-purple-500', accent: 'purple' },
    { bg: 'bg-blue-600/20', border: 'border-blue-500', accent: 'blue' },
    { bg: 'bg-emerald-600/20', border: 'border-emerald-500', accent: 'emerald' },
    { bg: 'bg-orange-600/20', border: 'border-orange-500', accent: 'orange' },
    { bg: 'bg-pink-600/20', border: 'border-pink-500', accent: 'pink' },
  ]

  // Voice Over track: detect overlaps and overshoots
  const voiceOverOverlaps = useMemo(() => {
    return detectVoiceOverOverlaps(segments)
  }, [segments])

  // Get segments to display in voice over track based on view mode
  const voiceOverSegments = useMemo(() => {
    if (hasMultipleVideos && viewMode === 'single') {
      return segments.filter(s => s.video_id === singleVideoId)
    }
    return segments
  }, [segments, hasMultipleVideos, viewMode, singleVideoId])

  // Calculate row assignments for stacked segment display
  // Each segment gets its own row, similar to how videos are displayed in a stacked view
  const segmentRowAssignments = useMemo(() => {
    const assignments: Record<string, number> = {}

    // Sort segments by their absolute start time on the timeline
    const sortedSegments = [...voiceOverSegments].sort((a, b) => {
      const aOffset = (hasMultipleVideos && viewMode === 'combined' && a.video_id)
        ? (videoPositions[a.video_id]?.start || 0) : 0
      const bOffset = (hasMultipleVideos && viewMode === 'combined' && b.video_id)
        ? (videoPositions[b.video_id]?.start || 0) : 0
      return (aOffset + a.start_time) - (bOffset + b.start_time)
    })

    // Assign each segment to its own row based on its sorted index
    sortedSegments.forEach((segment, index) => {
      assignments[segment.id] = index
    })

    return {
      assignments,
      rowCount: Math.max(1, sortedSegments.length) // At least 1 row, or number of segments
    }
  }, [voiceOverSegments, hasMultipleVideos, viewMode, videoPositions])

  return (
    <div className="console-card p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="section-header">Timeline</div>
          {/* View mode dropdown - only show when multiple videos */}
          {hasMultipleVideos && (
            <div className="relative">
              <button
                onClick={() => setViewDropdownOpen(!viewDropdownOpen)}
                className={clsx(
                  'flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors',
                  viewMode === 'combined'
                    ? 'bg-purple-600/20 text-purple-400 border border-purple-500/50'
                    : 'bg-terminal-elevated text-text-muted border border-terminal-border hover:border-purple-500/50'
                )}
              >
                {viewMode === 'combined' ? (
                  <>
                    <Layers className="w-3 h-3" />
                    All Videos (Sequential)
                  </>
                ) : (
                  <>
                    <Film className="w-3 h-3" />
                    {singleVideo?.name || 'Single Video'}
                  </>
                )}
                <ChevronDown className={clsx('w-3 h-3 transition-transform', viewDropdownOpen && 'rotate-180')} />
              </button>

              {/* Dropdown menu */}
              {viewDropdownOpen && (
                <>
                  {/* Backdrop to close dropdown */}
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setViewDropdownOpen(false)}
                  />
                  <div className="absolute top-full left-0 mt-1 bg-terminal-elevated border border-terminal-border rounded shadow-lg z-40 min-w-[180px]">
                    {/* All Videos option */}
                    <button
                      onClick={() => {
                        setViewMode('combined')
                        setViewDropdownOpen(false)
                      }}
                      className={clsx(
                        'w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors',
                        viewMode === 'combined'
                          ? 'bg-purple-600/20 text-purple-400'
                          : 'hover:bg-terminal-border text-text-primary'
                      )}
                    >
                      <Layers className="w-3 h-3" />
                      All Videos (Sequential)
                    </button>

                    <div className="border-t border-terminal-border my-1" />
                    <div className="px-3 py-1 text-[10px] text-text-muted">Single Video</div>

                    {/* Individual video options */}
                    {videos.map((video) => (
                      <button
                        key={video.id}
                        onClick={() => {
                          setViewMode('single')
                          setSelectedVideoId(video.id)
                          setViewDropdownOpen(false)
                        }}
                        className={clsx(
                          'w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors',
                          viewMode === 'single' && singleVideoId === video.id
                            ? 'bg-purple-600/20 text-purple-400'
                            : 'hover:bg-terminal-border text-text-primary'
                        )}
                      >
                        <Film className="w-3 h-3" />
                        <span className="truncate flex-1">{video.name}</span>
                        {!video.file_exists && (
                          <span title="File missing">
                            <AlertCircle className="w-3 h-3 text-red-500 shrink-0" />
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Zoom controls */}
          <div className="flex items-center gap-1 border-r border-terminal-border pr-3">
            <button
              onClick={handleZoomOut}
              className="p-1 rounded hover:bg-terminal-elevated text-text-muted hover:text-text-primary transition-colors"
              title="Zoom out (Ctrl+Scroll)"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[10px] font-mono text-text-muted w-8 text-center">
              {Math.round(zoomLevel * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              className="p-1 rounded hover:bg-terminal-elevated text-text-muted hover:text-text-primary transition-colors"
              title="Zoom in (Ctrl+Scroll)"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleZoomReset}
              className="p-1 rounded hover:bg-terminal-elevated text-text-muted hover:text-text-primary transition-colors ml-0.5"
              title="Fit to view"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>

          <span className="text-xs font-mono text-text-muted">
            {formatTime(currentTime)} / {formatTime(timelineDuration)}
          </span>
        </div>
      </div>

      {/* Instructions */}
      {segments.length > 0 && (
        <div className="text-[10px] text-text-muted mb-2">
          Drag edges to resize • Drag center to move • Ctrl+Scroll to zoom
        </div>
      )}

      {/* Scrollable Timeline Container */}
      <div
        ref={timelineScrollRef}
        className="overflow-x-auto overflow-y-hidden scrollbar-thin scrollbar-track-terminal-bg scrollbar-thumb-terminal-border hover:scrollbar-thumb-terminal-border-hover"
      >
        {/* Zoomable Inner Content */}
        <div style={{ width: `${100 * zoomLevel}%`, minWidth: '100%' }}>

      {/* Scrubber / Time ruler - Click and drag to position playhead */}
      <div
        ref={playheadContainerRef}
        className={clsx(
          'relative h-7 mb-1 bg-terminal-bg rounded-t border border-b-0 border-terminal-border select-none',
          isPlayheadDragging ? 'cursor-grabbing' : 'cursor-pointer'
        )}
        onMouseDown={handleScrubberMouseDown}
      >
        {/* Time markers */}
        {markers.map((time) => (
          <div
            key={time}
            className="absolute top-1 text-[10px] font-mono text-text-muted transform -translate-x-1/2 pointer-events-none"
            style={{ left: `${(time / timelineDuration) * 100}%` }}
          >
            {formatTime(time)}
          </div>
        ))}

        {/* Tick marks */}
        {markers.map((time) => (
          <div
            key={`tick-${time}`}
            className="absolute bottom-0 w-px h-2 bg-terminal-border pointer-events-none"
            style={{ left: `${(time / timelineDuration) * 100}%` }}
          />
        ))}

        {/* Playhead indicator on scrubber */}
        <div
          className={clsx(
            'absolute top-0 bottom-0 w-4 -translate-x-1/2 z-30 group',
            isPlayheadDragging ? 'cursor-grabbing' : 'cursor-grab'
          )}
          style={{ left: `${playheadPercent}%` }}
          onMouseDown={handlePlayheadDragStart}
        >
          {/* Playhead handle */}
          <div className="absolute top-0.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-accent-red rounded-sm shadow-md hover:scale-110 transition-transform" />
          {/* Playhead line extending down */}
          <div className="absolute top-3 bottom-0 left-1/2 w-0.5 -translate-x-1/2 bg-accent-red" />
        </div>

        {/* Current time indicator */}
        <div className="absolute right-2 top-1 text-[10px] font-mono text-accent-red pointer-events-none">
          {formatTime(currentTime)}
        </div>
      </div>

      {/* Video Tracks - Multi-video Combined View */}
      {hasMultipleVideos && viewMode === 'combined' ? (
        <div className="mb-1">
          <div className="text-[10px] text-text-muted mb-1 flex items-center gap-1">
            <Film className="w-3 h-3" />
            Video Tracks ({sortedVideos.length} videos) - Drag edges to trim, center to move
          </div>
          <div
            ref={videoTracksRef}
            className="relative bg-terminal-bg rounded border border-terminal-border"
            style={{ height: `${Math.max(48, sortedVideos.length * 48 + 8)}px` }}
          >
            {/* Time grid */}
            {markers.map((time) => (
              <div
                key={time}
                className="absolute top-0 bottom-0 w-px bg-terminal-border/50"
                style={{ left: `${(time / timelineDuration) * 100}%` }}
              />
            ))}

            {/* Video Snap Line Indicator */}
            {videoSnapLine && videoDragState && (
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-green-400 z-50 pointer-events-none"
                style={{ left: `${(videoSnapLine.time / timelineDuration) * 100}%` }}
              >
                <div className="absolute -top-5 left-1/2 -translate-x-1/2 bg-green-500 text-white text-[10px] px-1 rounded whitespace-nowrap">
                  {videoSnapLine.time.toFixed(1)}s
                </div>
                <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-3 flex items-center justify-center">
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                </div>
              </div>
            )}

            {/* Video tracks - Sequential Layout with drag handles and trim visualization */}
            {/* Note: In multi-video mode, segments are shown on the Voice Over track, not here */}
            {sortedVideos.map((video, index) => {
              const trackColor = videoTrackColors[index % videoTrackColors.length]
              const isSelectedTrack = video.id === selectedVideoTrackId
              const isDraggingThis = videoDragState?.segmentId === video.id
              const videoPos = videoPositions[video.id]

              // Use preview position if dragging, otherwise use calculated position
              const previewPos = videoPreviewPositions[video.id]
              const displayStart = previewPos?.start ?? videoPos?.start ?? 0
              const displayEnd = previewPos?.end ?? videoPos?.end ?? (video.duration || 0)

              // Video trim state (source_start and source_end)
              const videoDuration = video.duration || 0
              const sourceStart = video.source_start ?? 0
              const sourceEnd = video.source_end ?? videoDuration

              // Calculate trim states like VoiceOverBlock
              const isTrimmedFromStart = sourceStart > 0.1
              const isTrimmedFromEnd = videoDuration > 0 && sourceEnd < videoDuration - 0.1
              const trimmedStartAmount = sourceStart
              const trimmedEndAmount = Math.max(0, videoDuration - sourceEnd)

              // Active portion is what's actually shown on timeline
              const activeWidthOnTimeline = displayEnd - displayStart

              // Calculate width percentages for trim visualization
              const activeWidthPercent = (activeWidthOnTimeline / timelineDuration) * 100
              const trimmedStartWidthPercent = isTrimmedFromStart ? (trimmedStartAmount / timelineDuration) * 100 : 0
              const trimmedEndWidthPercent = isTrimmedFromEnd ? (trimmedEndAmount / timelineDuration) * 100 : 0

              // Total block width includes trimmed portions for visual reference
              const totalVisualWidth = activeWidthPercent + trimmedStartWidthPercent + trimmedEndWidthPercent
              const displayWidthPercent = Math.max(totalVisualWidth, 2)

              // Adjust left position to account for trimmed start portion
              const baseLeftPercent = (displayStart / timelineDuration) * 100
              const adjustedLeftPercent = baseLeftPercent - trimmedStartWidthPercent

              // Proportions within the block
              const trimmedStartPortion = displayWidthPercent > 0 ? (trimmedStartWidthPercent / displayWidthPercent) * 100 : 0
              const activePortion = displayWidthPercent > 0 ? (activeWidthPercent / displayWidthPercent) * 100 : 100
              const trimmedEndPortion = displayWidthPercent > 0 ? (trimmedEndWidthPercent / displayWidthPercent) * 100 : 0

              // For very short videos, we still show them but with a minimum visual width
              const isVeryShort = displayWidthPercent < 3

              return (
                <div
                  key={video.id}
                  className="absolute group"
                  style={{
                    top: `${index * 48 + 4}px`,
                    height: '44px',
                    left: `${Math.max(0, adjustedLeftPercent)}%`,
                    width: `${displayWidthPercent}%`,
                  }}
                >
                  {/* Video track container with trim visualization */}
                  <div className="absolute inset-0 flex rounded overflow-hidden">

                    {/* Trimmed START portion - striped/faded */}
                    {isTrimmedFromStart && trimmedStartPortion > 0 && (
                      <div
                        className="h-full relative border border-purple-600/30 rounded-l"
                        style={{
                          width: `${trimmedStartPortion}%`,
                          background: 'repeating-linear-gradient(45deg, rgba(147,51,234,0.1), rgba(147,51,234,0.1) 2px, rgba(147,51,234,0.2) 2px, rgba(147,51,234,0.2) 4px)',
                        }}
                        title={`Trimmed: ${trimmedStartAmount.toFixed(1)}s from start`}
                      >
                        <span className="absolute inset-0 flex items-center justify-center text-[8px] text-purple-500/60 font-mono">
                          -{trimmedStartAmount.toFixed(1)}s
                        </span>
                      </div>
                    )}

                    {/* ACTIVE portion - solid color with content */}
                    <div
                      className={clsx(
                        'h-full relative flex items-stretch transition-colors overflow-hidden',
                        'border-2',
                        isDraggingThis && 'opacity-80 z-20',
                        isSelectedTrack
                          ? `${trackColor.bg} ${trackColor.border}`
                          : 'bg-terminal-elevated/50 border-terminal-border hover:border-terminal-border-hover',
                        // Round corners based on trim state
                        !isTrimmedFromStart && 'rounded-l',
                        !isTrimmedFromEnd && 'rounded-r',
                        isTrimmedFromStart && 'border-l border-l-purple-400/50',
                        isTrimmedFromEnd && 'border-r border-r-purple-400/50',
                      )}
                      style={{ width: `${activePortion}%` }}
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedVideoTrackId(video.id)
                        handleTimelineClick(e, video.id)
                      }}
                    >
                      {/* Left resize handle - trim from start */}
                      <div
                        className={clsx(
                          'absolute -left-2 top-0 bottom-0 w-5 cursor-ew-resize z-30',
                          'flex items-center justify-center',
                          'hover:bg-purple-500/40 active:bg-purple-500/60 transition-colors rounded-l'
                        )}
                        onMouseDown={(e) => {
                          e.stopPropagation()
                          e.preventDefault()
                          handleVideoTrackDragStart(video.id, e, 'resize-start')
                      }}
                    >
                      <div className="w-1.5 h-10 bg-purple-400/70 rounded group-hover:bg-purple-400 transition-colors" />
                    </div>

                    {/* Video label - drag to move */}
                    <div
                      className={clsx(
                        'flex items-center gap-1 pl-3 pr-1 py-1 shrink-0 overflow-hidden',
                        'border-r transition-colors',
                        isDraggingThis ? 'cursor-grabbing' : 'cursor-grab',
                        'border-terminal-border hover:bg-terminal-elevated',
                        // For very short videos, show minimal label
                        isVeryShort ? 'max-w-[40px]' : 'min-w-[50px] max-w-[100px]'
                      )}
                      onMouseDown={(e) => {
                        e.stopPropagation()
                        handleVideoTrackDragStart(video.id, e, 'move')
                      }}
                      title={`${video.name} (${formatTime(video.duration || 0)}) - Drag to move`}
                    >
                      <Film className="w-3 h-3 shrink-0 text-text-muted" />
                      {!isVeryShort && (
                        <span className="text-[10px] truncate text-text-muted">
                          {video.name}
                        </span>
                      )}
                      {!video.file_exists && (
                        <span title="File missing">
                          <AlertCircle className="w-3 h-3 text-red-500 shrink-0" />
                        </span>
                      )}
                    </div>

                    {/* Video content area - drag to move video, double-click to set playhead */}
                    {/* In multi-video mode, segments are shown on the Voice Over track instead */}
                    <div
                      className={clsx(
                        'relative flex-1 pr-3 overflow-hidden',
                        isDraggingThis ? 'cursor-grabbing' : 'cursor-pointer'
                      )}
                      onMouseDown={(e) => {
                        e.stopPropagation()
                        handleVideoTrackDragStart(video.id, e, 'move')
                      }}
                    >
                      {/* Duration indicator */}
                      {!isVeryShort && (
                        <div className="absolute right-2 top-1/2 -translate-y-1/2 text-[9px] text-text-muted/60 pointer-events-none">
                          {formatTime(displayEnd - displayStart)}
                        </div>
                      )}
                    </div>

                    {/* Right resize handle - trim from end */}
                    <div
                      className={clsx(
                        'absolute -right-2 top-0 bottom-0 w-5 cursor-ew-resize z-30',
                        'flex items-center justify-center',
                        'hover:bg-purple-500/40 active:bg-purple-500/60 transition-colors rounded-r'
                      )}
                      onMouseDown={(e) => {
                        e.stopPropagation()
                        e.preventDefault()
                        handleVideoTrackDragStart(video.id, e, 'resize-end')
                      }}
                    >
                      <div className="w-1.5 h-10 bg-purple-400/70 rounded group-hover:bg-purple-400 transition-colors" />
                    </div>
                  </div>

                  {/* Trimmed END portion - striped/faded */}
                  {isTrimmedFromEnd && trimmedEndPortion > 0 && (
                    <div
                      className="h-full relative border border-purple-600/30 rounded-r"
                      style={{
                        width: `${trimmedEndPortion}%`,
                        background: 'repeating-linear-gradient(-45deg, rgba(147,51,234,0.1), rgba(147,51,234,0.1) 2px, rgba(147,51,234,0.2) 2px, rgba(147,51,234,0.2) 4px)',
                      }}
                      title={`Trimmed: ${trimmedEndAmount.toFixed(1)}s from end`}
                    >
                      <span className="absolute inset-0 flex items-center justify-center text-[8px] text-purple-500/60 font-mono">
                        -{trimmedEndAmount.toFixed(1)}s
                      </span>
                    </div>
                  )}
                </div>

                {/* Time display on hover/drag */}
                {(isSelectedTrack || isDraggingThis) && (
                  <div className="absolute -bottom-5 left-0 right-0 flex justify-between text-[9px] font-mono text-purple-400 pointer-events-none px-1">
                    <span>{formatTime(displayStart)}</span>
                    <span className="text-text-muted">{formatTime(video.duration || 0)}</span>
                    <span>{formatTime(displayEnd)}</span>
                  </div>
                )}
              </div>
            )
            })}

            {/* Playhead - Interactive, extends from scrubber */}
            <div
              className={clsx(
                'absolute top-0 bottom-0 w-4 -translate-x-1/2 z-30 group',
                isPlayheadDragging ? 'cursor-grabbing' : 'cursor-grab'
              )}
              style={{ left: `${playheadPercent}%` }}
              onMouseDown={handlePlayheadDragStart}
            >
              {/* Playhead line */}
              <div className="absolute top-0 bottom-0 left-1/2 w-0.5 -translate-x-1/2 bg-accent-red shadow-glow-red-sm" />
              {/* Bottom handle */}
              <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-accent-red rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>
        </div>
      ) : hasMultipleVideos && viewMode === 'single' ? (
        /* Single Video View Mode (for multi-video projects viewing one video) */
        <div className="mb-1">
          <div className="text-[10px] text-text-muted mb-1 flex items-center gap-1">
            <div className="w-2 h-2 rounded-sm bg-accent-red/50" />
            Segments
            {singleVideo && (
              <span className="text-purple-400 ml-1">
                ({singleVideo.name})
              </span>
            )}
          </div>
          <div
            ref={timelineRef}
            className={clsx(
              'relative bg-terminal-bg rounded border border-terminal-border',
              dragState ? 'cursor-grabbing' : 'cursor-crosshair'
            )}
            style={{ height: `${Math.max(48, segmentRowAssignments.rowCount * 36 + 8)}px` }}
            onClick={(e) => handleTimelineClick(e, singleVideoId || undefined)}
          >
            {/* Time grid */}
            {markers.map((time) => (
              <div
                key={time}
                className="absolute top-0 bottom-0 w-px bg-terminal-border"
                style={{ left: `${(time / timelineDuration) * 100}%` }}
              />
            ))}

            {/* Snap Line Indicator for single video mode */}
            {snapLine && dragState && (
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-green-400 z-50 pointer-events-none"
                style={{ left: `${(snapLine.time / timelineDuration) * 100}%` }}
              >
                <div className="absolute -top-5 left-1/2 -translate-x-1/2 bg-green-500 text-white text-[10px] px-1 rounded whitespace-nowrap">
                  {snapLine.time.toFixed(1)}s
                </div>
              </div>
            )}

            {/* Segments - filter by selected video */}
            {segments.filter(s => s.video_id === singleVideoId).map((segment) => (
              <SegmentBlock
                key={segment.id}
                segment={segment}
                duration={timelineDuration}
                isSelected={segment.id === selectedSegmentId}
                rowIndex={segmentRowAssignments.assignments[segment.id] ?? 0}
                rowHeight={36}
                onClick={() => {
                  setSelectedSegmentId(segment.id)
                  setCurrentTime(segment.start_time)
                }}
                onDragStart={(e, mode) => handleDragStart(segment.id, e, mode)}
                isDragging={dragState?.segmentId === segment.id}
                previewTimes={previewTimes[segment.id]}
              />
            ))}

            {/* Playhead - Interactive */}
            <div
              className={clsx(
                'absolute top-0 bottom-0 w-4 -translate-x-1/2 z-30 group',
                isPlayheadDragging ? 'cursor-grabbing' : 'cursor-grab'
              )}
              style={{ left: `${playheadPercent}%` }}
              onMouseDown={handlePlayheadDragStart}
            >
              {/* Playhead line */}
              <div className="absolute top-0 bottom-0 left-1/2 w-0.5 -translate-x-1/2 bg-accent-red shadow-glow-red-sm" />
              {/* Bottom handle */}
              <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-accent-red rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>

            {/* Empty state hint */}
            {segments.filter(s => s.video_id === singleVideoId).length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center text-text-muted text-sm">
                Click "+ Add Segment" to add a voice over segment
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* Voice Over Track */}
      <div className="mt-2">
        <div className="text-[10px] text-text-muted mb-1 flex items-center gap-1">
          <div className="w-2 h-2 rounded-sm bg-amber-500/50" />
          <Mic className="w-3 h-3 text-amber-400" />
          Voice Over ({voiceOverSegments.length} segment{voiceOverSegments.length !== 1 ? 's' : ''})
          {voiceOverOverlaps.size > 0 && (
            <span className="text-orange-400 ml-1 flex items-center gap-0.5">
              <AlertTriangle className="w-3 h-3" />
              {voiceOverOverlaps.size} overlap{voiceOverOverlaps.size !== 1 ? 's' : ''}
            </span>
          )}
          {/* Add Segment Button - positioned at the end */}
          <div className="ml-auto relative">
            {videosAtPlayhead.length === 0 ? (
              <button
                disabled
                className="text-[10px] py-0.5 px-1.5 rounded bg-terminal-elevated border border-terminal-border text-text-muted opacity-50 cursor-not-allowed flex items-center gap-1"
                title="Move playhead to a video to add segment"
              >
                <Plus className="w-3 h-3" />
                Add Segment
              </button>
            ) : (
              // In multi-video combined view, add generic segments with absolute timeline time
              <button
                onClick={() => onAddSegment(currentTime)} // No videoId = generic segment with absolute time
                className="text-[10px] py-0.5 px-1.5 rounded bg-terminal-elevated border border-terminal-border text-amber-400 hover:bg-amber-500/20 hover:border-amber-500/50 flex items-center gap-1 transition-colors"
                title={`Add segment at ${formatTime(currentTime)}`}
              >
                <Plus className="w-3 h-3" />
                Add Segment
              </button>
            )}
          </div>
        </div>
        <div
          ref={voiceOverTrackRef}
          className="relative bg-terminal-bg rounded border border-terminal-border overflow-hidden"
          style={{ height: `${Math.max(40, segmentRowAssignments.rowCount * 32 + 8)}px` }}
        >
          {/* Time grid */}
          {markers.map((time) => (
            <div
              key={time}
              className="absolute top-0 bottom-0 w-px bg-terminal-border/50"
              style={{ left: `${(time / timelineDuration) * 100}%` }}
            />
          ))}

          {/* Snap Line Indicator */}
          {snapLine && dragState && (
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-green-400 z-50 pointer-events-none"
              style={{ left: `${(snapLine.time / timelineDuration) * 100}%` }}
            >
              {/* Snap indicator labels */}
              <div className="absolute -top-5 left-1/2 -translate-x-1/2 bg-green-500 text-white text-[10px] px-1 rounded whitespace-nowrap">
                {snapLine.time.toFixed(1)}s
              </div>
              <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-3 flex items-center justify-center">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              </div>
            </div>
          )}

          {/* Voice Over Blocks */}
          {voiceOverSegments.map((segment) => {
            const segmentOvershoot = hasAudioOvershoot(segment)
            const overshootAmount = getOvershootAmount(segment)
            const overlapsWith = voiceOverOverlaps.get(segment.id) || []

            // Calculate video offset for combined multi-video view
            const videoOffset = (hasMultipleVideos && viewMode === 'combined' && segment.video_id)
              ? (videoPositions[segment.video_id]?.start || 0)
              : 0

            return (
              <VoiceOverBlock
                key={segment.id}
                segment={segment}
                duration={timelineDuration}
                videoOffset={videoOffset}
                isSelected={segment.id === selectedSegmentId}
                isMultiVideo={hasMultipleVideos}
                rowIndex={segmentRowAssignments.assignments[segment.id] ?? 0}
                rowHeight={32}
                onClick={() => {
                  setSelectedSegmentId(segment.id)
                  clearBgmSelection()
                  // Set current time to absolute position in timeline
                  setCurrentTime(videoOffset + segment.start_time)
                }}
                onPlayPreview={() => {
                  // Set current time and trigger preview playback
                  const absoluteTime = videoOffset + segment.start_time
                  console.log('[Timeline] onPlayPreview called:', { absoluteTime, segmentId: segment.id })
                  setCurrentTime(absoluteTime)
                  setSelectedSegmentId(segment.id)
                  setIsPlaying(true) // Start playback directly
                  if (onPlayPreview) {
                    onPlayPreview(absoluteTime, segment.id)
                  }
                }}
                onPausePreview={() => {
                  // Stop playback
                  console.log('[Timeline] onPausePreview called:', { segmentId: segment.id })
                  setIsPlaying(false)
                }}
                isPlayingPreview={isPlaying && segment.id === selectedSegmentId}
                onDragStart={(e, mode) => handleDragStart(segment.id, e, mode)}
                isDragging={dragState?.segmentId === segment.id}
                previewTimes={previewTimes[segment.id]}
                hasOvershoot={segmentOvershoot}
                overshootAmount={overshootAmount}
                overlapsWith={overlapsWith}
              />
            )
          })}

          {/* Empty state */}
          {voiceOverSegments.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-text-muted text-[10px]">
              No segments with voice over
            </div>
          )}

          {/* Playhead */}
          <div
            className={clsx(
              'absolute top-0 bottom-0 w-4 -translate-x-1/2 z-30 group',
              isPlayheadDragging ? 'cursor-grabbing' : 'cursor-grab'
            )}
            style={{ left: `${playheadPercent}%` }}
            onMouseDown={handlePlayheadDragStart}
          >
            <div className="absolute top-0 bottom-0 left-1/2 w-0.5 -translate-x-1/2 bg-accent-red/60 shadow-glow-red-sm" />
            <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-accent-red rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
        <div className="mt-1 text-[10px] text-text-muted">
          Click to select segment • Orange warning = audio exceeds segment • Red warning = overlaps with next
        </div>
      </div>

      {/* Background Music Tracks */}
      <div className="mt-2">
        <div className="text-[10px] text-text-muted mb-1 flex items-center justify-between">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-sm bg-teal-600/50" />
            Background Music ({bgmTracks.length} track{bgmTracks.length !== 1 ? 's' : ''})
            {selectedBgmTrackIds.size > 0 && (
              <span className="text-teal-400 ml-1">
                • {selectedBgmTrackIds.size} selected
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Bulk operations when tracks are selected */}
            {selectedBgmTrackIds.size > 0 && (
              <div className="flex items-center gap-1 border-r border-terminal-border pr-2">
                <button
                  onClick={() => handleBulkBgmMute(true)}
                  className="text-[10px] text-text-muted hover:text-teal-400 flex items-center gap-0.5 px-1"
                  title="Mute selected"
                >
                  <VolumeX className="w-3 h-3" />
                </button>
                <button
                  onClick={() => handleBulkBgmMute(false)}
                  className="text-[10px] text-text-muted hover:text-teal-400 flex items-center gap-0.5 px-1"
                  title="Unmute selected"
                >
                  <Volume2 className="w-3 h-3" />
                </button>
                <button
                  onClick={handleBulkBgmDelete}
                  className="text-[10px] text-text-muted hover:text-red-400 flex items-center gap-0.5 px-1"
                  title="Delete selected"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
                <button
                  onClick={clearBgmSelection}
                  className="text-[10px] text-text-muted hover:text-white px-1"
                  title="Clear selection"
                >
                  ✕
                </button>
              </div>
            )}
            <button
              onClick={() => bgmFileInputRef.current?.click()}
              className="text-[10px] text-teal-400 hover:text-teal-300 flex items-center gap-0.5"
              disabled={isUploadingBgm}
            >
              {isUploadingBgm ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Plus className="w-3 h-3" />
                  Add Track
                </>
              )}
            </button>
          </div>
        </div>

        {/* Hidden file input for BGM upload - supports all FFmpeg audio formats */}
        <input
          ref={bgmFileInputRef}
          type="file"
          accept="audio/*,.mp3,.wav,.wave,.aac,.m4a,.m4b,.ogg,.oga,.opus,.flac,.wma,.amr,.ac3,.eac3,.dts,.alac,.aiff,.aif,.aifc,.ape,.wv,.tta,.w64,.au,.snd,.caf,.mka,.ra,.mid,.midi,.mod,.s3m,.xm,.it,.mmf,.gsm,.spx,.webm"
          onChange={handleBgmUpload}
          className="hidden"
          id="bgm-upload"
        />

        <div
          ref={bgmTimelineRef}
          className={clsx(
            'relative bg-terminal-bg rounded border border-terminal-border transition-colors',
            bgmTracks.length === 0 ? 'h-8' : 'min-h-[2rem]',
            bgmTracks.length === 0 && !isUploadingBgm && 'cursor-pointer hover:border-teal-600/50'
          )}
          onClick={() => {
            if (bgmTracks.length === 0 && !isUploadingBgm) {
              bgmFileInputRef.current?.click()
            }
          }}
          style={{ height: effectiveBgmTracks.length > 0 ? `${Math.max(32, effectiveBgmTracks.length * 28 + 8)}px` : undefined }}
        >
          {/* Time grid */}
          {markers.map((time) => (
            <div
              key={time}
              className="absolute top-0 bottom-0 w-px bg-terminal-border/50"
              style={{ left: `${(time / timelineDuration) * 100}%` }}
            />
          ))}

          {/* BGM Snap Line Indicator */}
          {bgmSnapLine && bgmDragState && (
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-green-400 z-50 pointer-events-none"
              style={{ left: `${(bgmSnapLine.time / timelineDuration) * 100}%` }}
            >
              <div className="absolute -top-5 left-1/2 -translate-x-1/2 bg-green-500 text-white text-[10px] px-1 rounded whitespace-nowrap">
                {bgmSnapLine.time.toFixed(1)}s
              </div>
              <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-3 flex items-center justify-center">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              </div>
            </div>
          )}

          {/* BGM Tracks */}
          {effectiveBgmTracks.length > 0 ? (
            effectiveBgmTracks.map((track, index) => (
              <div
                key={track.id}
                className="absolute left-0 right-0"
                style={{ top: `${index * 28 + 4}px`, height: '24px' }}
              >
                <BGMTrackBlock
                  track={track}
                  duration={timelineDuration}
                  isSelected={selectedBgmTrackIds.has(track.id)}
                  onClick={(e) => handleBgmTrackSelect(track.id, e)}
                  onDragStart={(e, mode) => handleBgmDragStart(track.id, e, mode)}
                  isDragging={bgmDragState?.segmentId === track.id}
                  previewTimes={bgmPreviewTimes[track.id]}
                  onMuteToggle={() => handleBgmMuteToggle(track.id)}
                  onVolumeChange={(volume) => handleBgmVolumeChange(track.id, volume)}
                  onDelete={() => handleBgmDelete(track.id)}
                />
              </div>
            ))
          ) : isUploadingBgm ? (
            /* Uploading state */
            <div className="absolute inset-0 flex items-center justify-center text-teal-400 text-[10px]">
              <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
              Uploading audio...
            </div>
          ) : (
            /* Empty state - click to upload */
            <div className="absolute inset-0 flex items-center justify-center text-text-muted text-[10px] hover:text-teal-400 transition-colors">
              <Upload className="w-3 h-3 mr-1" />
              Click to add background music
            </div>
          )}

          {/* Playhead - Interactive */}
          <div
            className={clsx(
              'absolute top-0 bottom-0 w-4 -translate-x-1/2 z-30 group',
              isPlayheadDragging ? 'cursor-grabbing' : 'cursor-grab'
            )}
            style={{ left: `${playheadPercent}%` }}
            onMouseDown={handlePlayheadDragStart}
          >
            {/* Playhead line */}
            <div className="absolute top-0 bottom-0 left-1/2 w-0.5 -translate-x-1/2 bg-accent-red/60 shadow-glow-red-sm" />
            {/* Bottom handle */}
            <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-accent-red rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>

        {/* Volume controls when tracks exist */}
        {bgmTracks.length > 0 && (
          <div className="mt-1 flex items-center gap-3 text-[10px] text-text-muted">
            <span>Drag tracks to position • Hover for volume control</span>
          </div>
        )}
      </div>

        </div>{/* End Zoomable Inner Content */}
      </div>{/* End Scrollable Timeline Container */}

      {/* Coverage info */}
      <div className="mt-2 flex items-center gap-4 text-xs text-text-muted">
        <span>
          {segments.length} segment{segments.length !== 1 ? 's' : ''}
        </span>
        <span>
          Coverage:{' '}
          {(
            (segments.reduce((acc, s) => acc + (s.end_time - s.start_time), 0) / duration) *
            100
          ).toFixed(1)}
          %
        </span>
        {dragState && (
          <span className="text-accent-red">
            {dragState.mode === 'move' ? 'Moving' : 'Resizing'}...
          </span>
        )}
      </div>
    </div>
  )
}
