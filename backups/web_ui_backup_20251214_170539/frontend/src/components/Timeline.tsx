import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Plus, AlertTriangle, GripVertical, Music, Upload, Loader2, Volume2, VolumeX, Trash2, Film, Layers, ChevronDown, AlertCircle, Mic, ZoomIn, ZoomOut, Maximize2, ArrowRight } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { segmentsApi, videosApi, projectsApi, type BGMTrack } from '../api/client'
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
  // Multi-video support
  videos?: VideoInfo[]
  activeVideoId?: string | null
  onSetActiveVideo?: (videoId: string) => void
  // Callback when video positions change (for syncing with parent)
  onVideoPositionChange?: () => void
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
}

function SegmentBlock({
  segment,
  duration,
  isSelected,
  onClick,
  onDragStart,
  isDragging,
  previewTimes,
}: {
  segment: Segment
  duration: number
  isSelected: boolean
  onClick: () => void
  onDragStart: (e: React.MouseEvent, mode: DragMode) => void
  isDragging: boolean
  previewTimes?: { start: number; end: number }
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
        'absolute top-1 bottom-1 rounded transition-colors group',
        'border-2 flex items-center overflow-hidden',
        isDragging && 'opacity-80',
        isSelected
          ? 'bg-accent-red/30 border-accent-red shadow-glow-red-sm z-10'
          : 'bg-terminal-elevated border-terminal-border hover:border-accent-red/50'
      )}
      style={{
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

// BGM Track Block Component
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
  onClick: () => void
  onDragStart: (e: React.MouseEvent, mode: DragMode) => void
  isDragging: boolean
  previewTimes?: { start: number; end: number }
  onMuteToggle: () => void
  onVolumeChange: (volume: number) => void
  onDelete: () => void
}) {
  const [showVolumeSlider, setShowVolumeSlider] = useState(false)

  const startTime = previewTimes?.start ?? track.start_time
  const endTime = previewTimes?.end ?? (track.end_time === 0 ? duration : track.end_time)

  const leftPercent = (startTime / duration) * 100
  const widthPercent = ((endTime - startTime) / duration) * 100

  // Extract filename from path
  const fileName = track.path.split('/').pop() || track.name

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      className={clsx(
        'absolute top-1 bottom-1 rounded transition-colors group',
        'border flex items-center overflow-hidden',
        isDragging && 'opacity-80',
        track.muted && 'opacity-50',
        isSelected
          ? 'bg-teal-600/30 border-teal-500 shadow-[0_0_8px_rgba(20,184,166,0.3)] z-10'
          : 'bg-gradient-to-r from-teal-600/20 to-teal-700/20 border-teal-600/40 hover:border-teal-500/60'
      )}
      style={{
        left: `${leftPercent}%`,
        width: `${widthPercent}%`,
        minWidth: '60px',
        cursor: 'grab',
      }}
    >
      {/* Left resize handle */}
      <div
        className={clsx(
          'absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize z-20',
          'flex items-center justify-center',
          'hover:bg-teal-500/30 transition-colors'
        )}
        onMouseDown={(e) => {
          e.stopPropagation()
          onDragStart(e, 'resize-start')
        }}
      >
        <div className="w-0.5 h-4 bg-teal-500/50 rounded opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Center content - drag to move */}
      <div
        className="flex-1 h-full flex items-center cursor-grab active:cursor-grabbing px-2 gap-1"
        onMouseDown={(e) => {
          e.stopPropagation()
          onDragStart(e, 'move')
        }}
      >
        <Music className="w-3 h-3 text-teal-400 shrink-0" />
        <span className="text-[10px] text-teal-300 truncate flex-1">
          {fileName}
        </span>

        {/* Volume indicator */}
        <div
          className="relative"
          onMouseEnter={() => setShowVolumeSlider(true)}
          onMouseLeave={() => setShowVolumeSlider(false)}
        >
          <button
            onClick={(e) => {
              e.stopPropagation()
              onMuteToggle()
            }}
            className="p-0.5 rounded hover:bg-teal-600/30 text-teal-400"
          >
            {track.muted ? (
              <VolumeX className="w-3 h-3" />
            ) : (
              <Volume2 className="w-3 h-3" />
            )}
          </button>

          {/* Volume slider popup */}
          {showVolumeSlider && !track.muted && (
            <div
              className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 p-2 bg-terminal-elevated border border-terminal-border rounded shadow-lg z-30"
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <div className="flex flex-col items-center gap-1">
                <span className="text-[9px] text-text-muted">{track.volume}%</span>
                <input
                  type="range"
                  min="0"
                  max="200"
                  value={track.volume}
                  onChange={(e) => onVolumeChange(parseInt(e.target.value))}
                  className="w-20 h-1 accent-teal-500"
                  style={{ writingMode: 'horizontal-tb' }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Delete button */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          className="p-0.5 rounded hover:bg-red-600/30 text-teal-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>

      {/* Right resize handle */}
      <div
        className={clsx(
          'absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize z-20',
          'flex items-center justify-center',
          'hover:bg-teal-500/30 transition-colors'
        )}
        onMouseDown={(e) => {
          e.stopPropagation()
          onDragStart(e, 'resize-end')
        }}
      >
        <div className="w-0.5 h-4 bg-teal-500/50 rounded opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Time display on hover/drag */}
      {(isSelected || isDragging) && (
        <div className="absolute -bottom-5 left-0 right-0 flex justify-between text-[9px] font-mono text-teal-400 pointer-events-none">
          <span>{startTime.toFixed(1)}s</span>
          <span>{endTime.toFixed(1)}s</span>
        </div>
      )}
    </motion.div>
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
  // Multi-video props
  videos = [],
  activeVideoId,
  onSetActiveVideo,
  onVideoPositionChange,
}: TimelineProps) {
  // Legacy props are prefixed with _ to indicate they're not used in this implementation
  // but kept for API compatibility. The new BGM tracks system handles all BGM functionality.
  void _backgroundMusicPath
  void _onBackgroundMusicChange
  void _bgmVolume
  void _ttsVolume
  const { segments, currentTime, setCurrentTime, selectedSegmentId, setSelectedSegmentId, updateSegment } =
    useAppStore()

  // Multi-video timeline state
  const [viewMode, setViewMode] = useState<TimelineViewMode>('combined')
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null) // For single video mode
  const [viewDropdownOpen, setViewDropdownOpen] = useState(false)
  const [addSegmentDropdownOpen, setAddSegmentDropdownOpen] = useState(false)
  const hasMultipleVideos = videos.length > 1

  // Optimistic local state for video positions - applied immediately, synced with server
  const [localVideoOverrides, setLocalVideoOverrides] = useState<{ [videoId: string]: { timeline_start: number; timeline_end: number } }>({})

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

    // Check if any video has explicit timeline positions set (including local overrides)
    const hasExplicitPositions = sortedVideos.some(v =>
      localVideoOverrides[v.id] || v.timeline_start !== null && v.timeline_start !== undefined
    )

    if (hasExplicitPositions) {
      // Use local overrides first, then backend timeline positions when available
      for (const video of sortedVideos) {
        const videoDuration = video.duration || 0
        const override = localVideoOverrides[video.id]
        let start = override?.timeline_start ?? video.timeline_start ?? 0
        let end = override?.timeline_end ?? video.timeline_end ?? (start + videoDuration)

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
      // Fall back to sequential layout based on order
      let currentStart = 0
      for (const video of sortedVideos) {
        const videoDuration = video.duration || 0
        positions[video.id] = {
          start: currentStart,
          end: currentStart + videoDuration,
          duration: videoDuration
        }
        currentStart += videoDuration
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

  // BGM track state
  const [selectedBgmTrackId, setSelectedBgmTrackId] = useState<string | null>(null)
  const [bgmDragState, setBgmDragState] = useState<DragState | null>(null)
  const [bgmPreviewTimes, setBgmPreviewTimes] = useState<{ [trackId: string]: { start: number; end: number } }>({})
  // Optimistic local state for BGM tracks - applied immediately, synced with server
  const [localBgmOverrides, setLocalBgmOverrides] = useState<{ [trackId: string]: { start_time: number; end_time: number } }>({})
  const bgmTimelineRef = useRef<HTMLDivElement>(null)

  // Merge bgmTracks with local optimistic overrides
  const effectiveBgmTracks = useMemo(() => {
    return bgmTracks.map(track => {
      const override = localBgmOverrides[track.id]
      if (override) {
        return { ...track, start_time: override.start_time, end_time: override.end_time }
      }
      return track
    })
  }, [bgmTracks, localBgmOverrides])

  // Playhead drag state
  const [isPlayheadDragging, setIsPlayheadDragging] = useState(false)
  const playheadContainerRef = useRef<HTMLDivElement>(null)

  // Video track drag state (for dragging/trimming video clips)
  const [selectedVideoTrackId, setSelectedVideoTrackId] = useState<string | null>(null)
  const [videoDragState, setVideoDragState] = useState<DragState | null>(null)
  const [videoPreviewPositions, setVideoPreviewPositions] = useState<{ [videoId: string]: { start: number; end: number } }>({})
  // CRITICAL: Use ref to track preview positions for mouseup handler (avoids stale closure)
  const videoPreviewPositionsRef = useRef<{ [videoId: string]: { start: number; end: number } }>({})
  const videoTracksRef = useRef<HTMLDivElement>(null)

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

  // Handle BGM track mute toggle
  const handleBgmMuteToggle = useCallback(async (trackId: string) => {
    const track = bgmTracks.find(t => t.id === trackId)
    if (!track) return

    try {
      await projectsApi.updateBGMTrack(projectName, trackId, { muted: !track.muted })
      onBGMTracksChange?.()
    } catch (error) {
      toast.error('Failed to update track')
    }
  }, [projectName, bgmTracks, onBGMTracksChange])

  // Handle BGM track volume change
  const handleBgmVolumeChange = useCallback(async (trackId: string, volume: number) => {
    try {
      await projectsApi.updateBGMTrack(projectName, trackId, { volume })
      onBGMTracksChange?.()
    } catch (error) {
      toast.error('Failed to update volume')
    }
  }, [projectName, onBGMTracksChange])

  // Handle BGM track delete
  const handleBgmDelete = useCallback(async (trackId: string) => {
    try {
      await projectsApi.deleteBGMTrack(projectName, trackId)
      onBGMTracksChange?.()
      toast.success('Track removed')
    } catch (error) {
      toast.error('Failed to remove track')
    }
  }, [projectName, onBGMTracksChange])

  // Handle BGM track drag start
  const handleBgmDragStart = useCallback((trackId: string, e: React.MouseEvent, mode: DragMode) => {
    const track = bgmTracks.find(t => t.id === trackId)
    if (!track) return

    setBgmDragState({
      segmentId: trackId, // Reusing segmentId field for trackId
      mode,
      initialMouseX: e.clientX,
      initialStartTime: track.start_time,
      initialEndTime: track.end_time === 0 ? timelineDuration : track.end_time,
    })

    setSelectedBgmTrackId(trackId)
    setSelectedSegmentId(null) // Deselect any selected segment
  }, [bgmTracks, timelineDuration, setSelectedSegmentId])

  // Handle BGM track drag
  useEffect(() => {
    if (!bgmDragState) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!bgmTimelineRef.current) return

      const rect = bgmTimelineRef.current.getBoundingClientRect()
      const deltaX = e.clientX - bgmDragState.initialMouseX
      const deltaTime = (deltaX / rect.width) * timelineDuration

      let newStart = bgmDragState.initialStartTime
      let newEnd = bgmDragState.initialEndTime

      if (bgmDragState.mode === 'move') {
        const trackDuration = bgmDragState.initialEndTime - bgmDragState.initialStartTime
        newStart = bgmDragState.initialStartTime + deltaTime
        newEnd = newStart + trackDuration

        // Only prevent going below 0, allow extending past timeline end (it will grow)
        if (newStart < 0) {
          newStart = 0
          newEnd = trackDuration
        }
      } else if (bgmDragState.mode === 'resize-start') {
        newStart = bgmDragState.initialStartTime + deltaTime
        newStart = Math.min(newStart, bgmDragState.initialEndTime - 1)
        newStart = Math.max(0, newStart)
      } else if (bgmDragState.mode === 'resize-end') {
        newEnd = bgmDragState.initialEndTime + deltaTime
        // Only prevent making the track too short, allow extending past timeline (it will grow)
        newEnd = Math.max(newEnd, bgmDragState.initialStartTime + 1)
      }

      newStart = Math.round(newStart * 10) / 10
      newEnd = Math.round(newEnd * 10) / 10

      setBgmPreviewTimes(prev => ({
        ...prev,
        [bgmDragState.segmentId]: { start: newStart, end: newEnd }
      }))
    }

    const handleMouseUp = () => {
      if (!bgmDragState) return

      const preview = bgmPreviewTimes[bgmDragState.segmentId]
      if (preview) {
        // OPTIMISTIC UI: Apply changes locally immediately for instant feedback
        const trackId = bgmDragState.segmentId
        const newStart = preview.start
        const newEnd = preview.end

        // Apply optimistic update immediately (no waiting for API)
        setLocalBgmOverrides(prev => ({
          ...prev,
          [trackId]: { start_time: newStart, end_time: newEnd }
        }))

        // Clear drag state and preview immediately for responsive UI
        setBgmDragState(null)
        setBgmPreviewTimes(prev => {
          const next = { ...prev }
          delete next[trackId]
          return next
        })

        // Send update via WebSocket for real-time sync
        wsUpdateBGMTrack(trackId, { start_time: newStart, end_time: newEnd })
        console.log(`[Timeline] BGM track updated via WebSocket: ${newStart.toFixed(1)}s - ${newEnd.toFixed(1)}s`)

        // Also fire REST API call for persistence (WebSocket for real-time, REST for reliability)
        projectsApi.updateBGMTrack(projectName, trackId, {
          start_time: newStart,
          end_time: newEnd,
        })
          .then(() => {
            // On success, clear optimistic override and sync with server
            setLocalBgmOverrides(prev => {
              const next = { ...prev }
              delete next[trackId]
              return next
            })
            onBGMTracksChange?.()
          })
          .catch(() => {
            // On error, clear optimistic override (server state wins)
            setLocalBgmOverrides(prev => {
              const next = { ...prev }
              delete next[trackId]
              return next
            })
            toast.error('Failed to update track timing')
            onBGMTracksChange?.()
          })
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
  }, [bgmDragState, duration, bgmPreviewTimes, projectName, onBGMTracksChange, wsUpdateBGMTrack])

  // Handle video track drag start - uses pending drag to allow double-clicks
  const handleVideoTrackDragStart = useCallback((videoId: string, e: React.MouseEvent, mode: DragMode) => {
    const video = videos.find(v => v.id === videoId)
    if (!video) return

    setSelectedVideoTrackId(videoId)
    setSelectedSegmentId(null)
    setSelectedBgmTrackId(null)

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
      } else if (videoDragState.mode === 'resize-start') {
        // Trim from start - adjust in-point, keep out-point fixed
        newStart = videoDragState.initialStartTime + deltaTime
        // Can't go below 0
        newStart = Math.max(0, newStart)
        // Can't make clip shorter than minimum duration
        newStart = Math.min(newStart, videoDragState.initialEndTime - MIN_CLIP_DURATION)
        // newEnd stays at initial value (preserving out-point)
      } else if (videoDragState.mode === 'resize-end') {
        // Trim from end - adjust out-point, keep in-point fixed
        newEnd = videoDragState.initialEndTime + deltaTime
        // Can't make clip shorter than minimum duration
        newEnd = Math.max(newEnd, videoDragState.initialStartTime + MIN_CLIP_DURATION)
        // Can extend up to the video's actual duration from start point
        const maxEnd = videoDragState.initialStartTime + videoDuration
        newEnd = Math.min(newEnd, maxEnd)
        // newStart stays at initial value (preserving in-point)
      }

      // Round to millisecond precision (0.001s) for accurate timeline control
      newStart = Math.round(newStart * 1000) / 1000
      newEnd = Math.round(newEnd * 1000) / 1000

      // Update both state AND ref (ref is critical for mouseup handler to read latest value)
      const newPreview = { start: newStart, end: newEnd }
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

      // CRITICAL: Read from ref, not state - state may be stale due to closure
      const preview = videoPreviewPositionsRef.current[videoDragState.segmentId]
      if (preview) {
        const videoId = videoDragState.segmentId
        const newStart = preview.start
        const newEnd = preview.end

        // OPTIMISTIC UI: Apply changes locally immediately for instant feedback
        setLocalVideoOverrides(prev => ({
          ...prev,
          [videoId]: { timeline_start: newStart, timeline_end: newEnd }
        }))

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
        // Use video_resize for resize operations to be explicit
        const isResize = videoDragState.mode === 'resize-start' || videoDragState.mode === 'resize-end'
        if (isResize) {
          // For resize, use the dedicated resize handler
          wsUpdateVideoResize(videoId, newStart, newEnd)
          console.log(`[Timeline] Video resized via WebSocket: ${newStart.toFixed(1)}s - ${newEnd.toFixed(1)}s`)
        } else {
          wsUpdateVideoPosition(videoId, newStart, newEnd)
          console.log(`[Timeline] Video moved via WebSocket: ${newStart.toFixed(1)}s - ${newEnd.toFixed(1)}s`)
        }

        // Notify parent to refetch project data
        // Use longer delay to ensure backend has saved before refetch
        setTimeout(() => {
          onVideoPositionChange?.()
        }, 100)

        // Clear optimistic override after a longer delay to ensure data is synced
        // The override provides immediate feedback while we wait for backend confirmation
        setTimeout(() => {
          setLocalVideoOverrides(prev => {
            const next = { ...prev }
            delete next[videoId]
            return next
          })
        }, 800)
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
  }, [videoDragState, timelineDuration, videos, wsUpdateVideoPosition, wsUpdateVideoResize, onVideoPositionChange, zoomLevel])

  const timelineRef = useRef<HTMLDivElement>(null)
  const [dragState, setDragState] = useState<DragState | null>(null)
  const [previewTimes, setPreviewTimes] = useState<{ [segmentId: string]: { start: number; end: number } }>({})

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

    setDragState({
      segmentId,
      mode,
      initialMouseX: e.clientX,
      initialStartTime: segment.start_time,
      initialEndTime: segment.end_time,
    })

    setSelectedSegmentId(segmentId)
  }, [segments, setSelectedSegmentId])

  // Handle mouse move during drag
  useEffect(() => {
    if (!dragState) return

    const handleMouseMove = (e: MouseEvent) => {
      const currentSegment = segments.find(s => s.id === dragState.segmentId)
      if (!currentSegment || !timelineRef.current) return

      const rect = timelineRef.current.getBoundingClientRect()
      const deltaX = e.clientX - dragState.initialMouseX
      const deltaTime = (deltaX / rect.width) * duration

      let newStart = dragState.initialStartTime
      let newEnd = dragState.initialEndTime

      // Calculate new times based on drag mode
      if (dragState.mode === 'move') {
        const segmentDuration = dragState.initialEndTime - dragState.initialStartTime
        newStart = dragState.initialStartTime + deltaTime
        newEnd = newStart + segmentDuration

        // Clamp to timeline bounds
        if (newStart < 0) {
          newStart = 0
          newEnd = segmentDuration
        }
        if (newEnd > duration) {
          newEnd = duration
          newStart = duration - segmentDuration
        }
      } else if (dragState.mode === 'resize-start') {
        newStart = dragState.initialStartTime + deltaTime
        // Minimum segment duration of 1 second
        newStart = Math.min(newStart, dragState.initialEndTime - 1)
        newStart = Math.max(0, newStart)
      } else if (dragState.mode === 'resize-end') {
        newEnd = dragState.initialEndTime + deltaTime
        // Minimum segment duration of 1 second
        newEnd = Math.max(newEnd, dragState.initialStartTime + 1)
        newEnd = Math.min(duration, newEnd)
      }

      // Round to 0.1 second precision
      newStart = Math.round(newStart * 10) / 10
      newEnd = Math.round(newEnd * 10) / 10

      // Update preview
      setPreviewTimes(prev => ({
        ...prev,
        [dragState.segmentId]: { start: newStart, end: newEnd }
      }))
    }

    const handleMouseUp = async () => {
      if (!dragState) return

      const preview = previewTimes[dragState.segmentId]
      const currentSegment = segments.find(s => s.id === dragState.segmentId)
      if (preview && currentSegment) {
        // Check for overlaps with other segments - ONLY check same video
        const hasOverlap = segments.some(s => {
          if (s.id === dragState.segmentId) return false
          // Only check overlaps within the same video
          if (s.video_id !== currentSegment.video_id) return false
          return preview.start < s.end_time && preview.end > s.start_time
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

        // Save to backend
        try {
          const response = await segmentsApi.update(projectName, dragState.segmentId, {
            start_time: preview.start,
            end_time: preview.end,
          })

          // Update store with response data
          updateSegment(response.data)

          // Clear preview
          setPreviewTimes(prev => {
            const next = { ...prev }
            delete next[dragState.segmentId]
            return next
          })
        } catch (error) {
          toast.error('Failed to update segment timing')
          // Revert preview
          setPreviewTimes(prev => {
            const next = { ...prev }
            delete next[dragState.segmentId]
            return next
          })
        }
      }

      setDragState(null)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [dragState, duration, segments, previewTimes, projectName, updateSegment])

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

  // Get segments filtered by video for combined view
  const getSegmentsForVideo = useCallback((videoId: string) => {
    return segments.filter(s => s.video_id === videoId)
  }, [segments])

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

  // Function to add segment at playhead for a specific video
  const handleAddSegmentForVideo = useCallback((videoId: string) => {
    const videoPos = videoPositions[videoId]
    let videoLocalTime = currentTime
    if (videoPos) {
      videoLocalTime = Math.max(0, currentTime - videoPos.start)
      videoLocalTime = Math.min(videoLocalTime, videoPos.duration)
    }
    onAddSegment(videoLocalTime, videoId)
    setAddSegmentDropdownOpen(false)
  }, [currentTime, videoPositions, onAddSegment])

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
          {/* Smart Add Segment Button */}
          <div className="relative">
            {videosAtPlayhead.length === 0 ? (
              // No video at playhead - disabled button with tooltip
              <button
                disabled
                className="btn-secondary text-xs py-1 px-2 flex items-center gap-1 opacity-50 cursor-not-allowed"
                title="Move playhead to a video to add segment"
              >
                <Plus className="w-3 h-3" />
                Add
              </button>
            ) : videosAtPlayhead.length === 1 ? (
              // Single video at playhead - direct add
              <button
                onClick={() => handleAddSegmentForVideo(videosAtPlayhead[0].id)}
                className="btn-secondary text-xs py-1 px-2 flex items-center gap-1"
                title={`Add segment to ${videosAtPlayhead[0].name}`}
              >
                <Plus className="w-3 h-3" />
                Add
              </button>
            ) : (
              // Multiple videos at playhead - show dropdown
              <>
                <button
                  onClick={() => setAddSegmentDropdownOpen(!addSegmentDropdownOpen)}
                  className={clsx(
                    'btn-secondary text-xs py-1 px-2 flex items-center gap-1',
                    addSegmentDropdownOpen && 'ring-1 ring-accent-red/50'
                  )}
                  title={`${videosAtPlayhead.length} videos at playhead`}
                >
                  <Plus className="w-3 h-3" />
                  Add
                  <ChevronDown className={clsx('w-3 h-3 transition-transform', addSegmentDropdownOpen && 'rotate-180')} />
                </button>

                {/* Dropdown to select which video */}
                {addSegmentDropdownOpen && (
                  <>
                    {/* Backdrop */}
                    <div
                      className="fixed inset-0 z-30"
                      onClick={() => setAddSegmentDropdownOpen(false)}
                    />
                    <div className="absolute top-full right-0 mt-1 bg-terminal-elevated border border-terminal-border rounded shadow-lg z-40 min-w-[160px]">
                      <div className="px-3 py-1.5 text-[10px] text-text-muted border-b border-terminal-border">
                        Add segment to:
                      </div>
                      {videosAtPlayhead.map((video, index) => (
                        <button
                          key={video.id}
                          onClick={() => handleAddSegmentForVideo(video.id)}
                          className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-terminal-border text-text-primary transition-colors"
                        >
                          <Film className={clsx('w-3 h-3', videoTrackColors[index % videoTrackColors.length].border.replace('border-', 'text-'))} />
                          <span className="truncate flex-1">{video.name}</span>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
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

            {/* Video tracks - Sequential Layout with drag handles */}
            {sortedVideos.map((video, index) => {
              const trackColor = videoTrackColors[index % videoTrackColors.length]
              const videoSegments = getSegmentsForVideo(video.id)
              const isActive = video.id === activeVideoId
              const isSelectedTrack = video.id === selectedVideoTrackId
              const isDraggingThis = videoDragState?.segmentId === video.id
              const videoPos = videoPositions[video.id]

              // Use preview position if dragging, otherwise use calculated position
              const previewPos = videoPreviewPositions[video.id]
              const displayStart = previewPos?.start ?? videoPos?.start ?? 0
              const displayEnd = previewPos?.end ?? videoPos?.end ?? (video.duration || 0)

              // Calculate position and width as percentage of total timeline
              const videoLeftPercent = (displayStart / timelineDuration) * 100
              const videoWidthPercent = ((displayEnd - displayStart) / timelineDuration) * 100
              // For very short videos, we still show them but with a minimum visual width
              // However, resize handles will be positioned correctly at actual boundaries
              const isVeryShort = videoWidthPercent < 3

              return (
                <div
                  key={video.id}
                  className="absolute group"
                  style={{
                    top: `${index * 48 + 4}px`,
                    height: '44px',
                    left: `${videoLeftPercent}%`,
                    // Use actual percentage width - no artificial minWidth that causes misalignment
                    width: `${Math.max(videoWidthPercent, 2)}%`,
                  }}
                >
                  {/* Video track container */}
                  <div
                    className={clsx(
                      'absolute inset-0 rounded transition-colors overflow-hidden',
                      'border-2 flex items-stretch',
                      isDraggingThis && 'opacity-80 z-20',
                      isActive || isSelectedTrack
                        ? `${trackColor.bg} ${trackColor.border}`
                        : 'bg-terminal-elevated/50 border-terminal-border hover:border-terminal-border-hover'
                    )}
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedVideoTrackId(video.id)
                      handleTimelineClick(e, video.id)
                    }}
                  >
                    {/* Left resize handle - trim from start - extends outside container for easier grabbing */}
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

                    {/* Video label - click to set active, drag to move */}
                    <div
                      className={clsx(
                        'flex items-center gap-1 pl-3 pr-1 py-1 shrink-0 overflow-hidden',
                        'border-r transition-colors',
                        isDraggingThis ? 'cursor-grabbing' : 'cursor-grab',
                        isActive
                          ? `${trackColor.border} bg-black/20`
                          : 'border-terminal-border hover:bg-terminal-elevated',
                        // For very short videos, show minimal label
                        isVeryShort ? 'max-w-[40px]' : 'min-w-[50px] max-w-[100px]'
                      )}
                      onClick={(e) => {
                        e.stopPropagation()
                        onSetActiveVideo?.(video.id)
                      }}
                      onMouseDown={(e) => {
                        e.stopPropagation()
                        handleVideoTrackDragStart(video.id, e, 'move')
                      }}
                      title={`${video.name} (${formatTime(video.duration || 0)}) - Drag to move`}
                    >
                      <Film className={clsx('w-3 h-3 shrink-0', isActive ? 'text-purple-400' : 'text-text-muted')} />
                      {!isVeryShort && (
                        <span className={clsx(
                          'text-[10px] truncate',
                          isActive ? 'text-purple-300 font-medium' : 'text-text-muted'
                        )}>
                          {video.name}
                        </span>
                      )}
                      {!video.file_exists && (
                        <span title="File missing">
                          <AlertCircle className="w-3 h-3 text-red-500 shrink-0" />
                        </span>
                      )}
                    </div>

                    {/* Segments area - drag to move video, double-click to add segment */}
                    <div
                      className={clsx(
                        'relative flex-1 pr-3 overflow-hidden',
                        isDraggingThis ? 'cursor-grabbing' : 'cursor-crosshair'
                      )}
                      onMouseDown={(e) => {
                        // Only start video drag if not clicking on a segment
                        if ((e.target as HTMLElement).closest('.segment-block')) return
                        e.stopPropagation()
                        handleVideoTrackDragStart(video.id, e, 'move')
                      }}
                    >
                      {videoSegments.map((segment) => (
                        <SegmentBlock
                          key={segment.id}
                          segment={segment}
                          duration={videoPos?.duration || duration}
                          isSelected={segment.id === selectedSegmentId}
                          onClick={() => {
                            setSelectedSegmentId(segment.id)
                            // Set current time to project timeline position
                            setCurrentTime((videoPos?.start || 0) + segment.start_time)
                          }}
                          onDragStart={(e, mode) => handleDragStart(segment.id, e, mode)}
                          isDragging={dragState?.segmentId === segment.id}
                          previewTimes={previewTimes[segment.id]}
                        />
                      ))}

                      {/* Empty state for this video track - only show if wide enough */}
                      {videoSegments.length === 0 && !isVeryShort && (
                        <div className="absolute left-2 top-0 bottom-0 flex items-center text-text-muted/50 text-[10px] pointer-events-none">
                          <span>Click + Add to add segment</span>
                        </div>
                      )}
                    </div>

                    {/* Right resize handle - trim from end - extends outside container for easier grabbing */}
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
      ) : (
        /* Single Video Track - Original View */
        <div className="mb-1">
          <div className="text-[10px] text-text-muted mb-1 flex items-center gap-1">
            <div className="w-2 h-2 rounded-sm bg-accent-red/50" />
            Segments
            {hasMultipleVideos && singleVideo && (
              <span className="text-purple-400 ml-1">
                ({singleVideo.name})
              </span>
            )}
          </div>
          <div
            ref={timelineRef}
            className={clsx(
              'relative h-12 bg-terminal-bg rounded border border-terminal-border',
              dragState ? 'cursor-grabbing' : 'cursor-crosshair'
            )}
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

            {/* Segments - filter by selected video if multiple videos */}
            {(hasMultipleVideos ? segments.filter(s => s.video_id === singleVideoId) : segments).map((segment) => (
              <SegmentBlock
                key={segment.id}
                segment={segment}
                duration={timelineDuration}
                isSelected={segment.id === selectedSegmentId}
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
            {(hasMultipleVideos ? segments.filter(s => s.video_id === singleVideoId).length === 0 : segments.length === 0) && (
              <div className="absolute inset-0 flex items-center justify-center text-text-muted text-sm">
                Click + Add button to add a segment
              </div>
            )}
          </div>
        </div>
      )}

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
        </div>
        <div
          className="relative h-10 bg-terminal-bg rounded border border-terminal-border overflow-hidden"
        >
          {/* Time grid */}
          {markers.map((time) => (
            <div
              key={time}
              className="absolute top-0 bottom-0 w-px bg-terminal-border/50"
              style={{ left: `${(time / timelineDuration) * 100}%` }}
            />
          ))}

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
                onClick={() => {
                  setSelectedSegmentId(segment.id)
                  setSelectedBgmTrackId(null)
                  // Set current time to absolute position in timeline
                  setCurrentTime(videoOffset + segment.start_time)
                }}
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
          </div>
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

        {/* Hidden file input for BGM upload */}
        <input
          ref={bgmFileInputRef}
          type="file"
          accept="audio/*,.mp3,.wav,.aac,.ogg,.m4a,.flac"
          onChange={handleBgmUpload}
          className="hidden"
          id="bgm-upload"
        />

        <div
          ref={bgmTimelineRef}
          className={clsx(
            'relative bg-terminal-bg rounded border border-terminal-border transition-colors',
            bgmTracks.length === 0 ? 'h-8' : 'min-h-[2.5rem]',
            bgmTracks.length === 0 && !isUploadingBgm && 'cursor-pointer hover:border-teal-600/50'
          )}
          onClick={() => {
            if (bgmTracks.length === 0 && !isUploadingBgm) {
              bgmFileInputRef.current?.click()
            }
          }}
          style={{ height: effectiveBgmTracks.length > 0 ? `${Math.max(40, effectiveBgmTracks.length * 32 + 8)}px` : undefined }}
        >
          {/* Time grid */}
          {markers.map((time) => (
            <div
              key={time}
              className="absolute top-0 bottom-0 w-px bg-terminal-border/50"
              style={{ left: `${(time / timelineDuration) * 100}%` }}
            />
          ))}

          {/* BGM Tracks */}
          {effectiveBgmTracks.length > 0 ? (
            effectiveBgmTracks.map((track, index) => (
              <div
                key={track.id}
                className="absolute left-0 right-0"
                style={{ top: `${index * 32 + 4}px`, height: '28px' }}
              >
                <BGMTrackBlock
                  track={track}
                  duration={timelineDuration}
                  isSelected={track.id === selectedBgmTrackId}
                  onClick={() => {
                    setSelectedBgmTrackId(track.id)
                    setSelectedSegmentId(null)
                  }}
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
