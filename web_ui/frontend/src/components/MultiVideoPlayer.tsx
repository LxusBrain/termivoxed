import { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import { Play, Pause, Volume2, VolumeX, Maximize, SkipBack, SkipForward, Headphones, Film, Music, AlertTriangle, Loader2 } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import clsx from 'clsx'
import type { VideoInfo } from '../types'
import type { BGMTrack } from '../api/client'
import toast from 'react-hot-toast'

// Codecs that are reliably supported in modern browsers
const BROWSER_COMPATIBLE_CODECS = [
  'h264', 'avc1', 'avc',  // H.264/AVC - most compatible
  'vp8', 'vp9',            // VP8/VP9 - WebM codecs
  'av01', 'av1',           // AV1 - newer, growing support
  'theora',                // Older Ogg codec
]

// Codecs that have limited or no browser support
const LIMITED_SUPPORT_CODECS = [
  'hevc', 'h265', 'hvc1', 'hev1',  // HEVC - Safari only, some Chromium
  'prores', 'ap4h', 'apch', 'apcn', 'apcs', 'apco',  // ProRes - Safari only
  'dnxhd', 'dnxhr',                // DNxHD/HR - not supported
  'mpeg2video', 'mpeg1video',      // MPEG-2 - limited support
  'mjpeg',                         // Motion JPEG - limited
  'rawvideo', 'v210',              // Raw video - not supported
]

function isCodecBrowserCompatible(codec: string | null | undefined): { compatible: boolean; warning?: string } {
  if (!codec) return { compatible: true } // Unknown codec, let browser try

  const codecLower = codec.toLowerCase()

  if (BROWSER_COMPATIBLE_CODECS.some(c => codecLower.includes(c))) {
    return { compatible: true }
  }

  if (LIMITED_SUPPORT_CODECS.some(c => codecLower.includes(c))) {
    return {
      compatible: false,
      warning: `Codec "${codec}" has limited browser support. Consider transcoding to H.264.`
    }
  }

  return { compatible: true } // Unknown codec, let browser try
}

interface VideoPosition {
  id: string
  name: string
  url: string
  timelineStart: number
  timelineEnd: number
  duration: number
  // Source trim values - which portion of the source file to play
  sourceStart: number  // Where to start in source file (default 0)
  sourceEnd: number | null  // Where to end in source file (null = use duration)
  // Codec info for compatibility checks
  codec?: string | null
}

interface MultiVideoPlayerProps {
  projectName: string
  videos: VideoInfo[]
  totalDuration: number
  bgmTracks?: BGMTrack[]
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export default function MultiVideoPlayer({ projectName, videos, totalDuration, bgmTracks = [] }: MultiVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const segmentAudioRef = useRef<HTMLAudioElement | null>(null)
  const lastPlayedSegmentRef = useRef<string | null>(null)
  const segmentAudioPlayingRef = useRef<boolean>(false)  // Track if a play operation is in progress
  const [isMuted, setIsMuted] = useState(false)
  const [volume, setVolume] = useState(1)
  const [audioSyncEnabled, setAudioSyncEnabled] = useState(true)
  const [bgmSyncEnabled, setBgmSyncEnabled] = useState(true)
  const [playingSegmentAudio, setPlayingSegmentAudio] = useState<string | null>(null)
  const [playingBgmTracks, setPlayingBgmTracks] = useState<Set<string>>(new Set())
  const [currentVideoId, setCurrentVideoId] = useState<string | null>(null)
  const [videoLoadError, setVideoLoadError] = useState<string | null>(null)
  const [isVideoLoading, setIsVideoLoading] = useState(true)
  const [canPlay, setCanPlay] = useState(false)
  const [loadingProgress, setLoadingProgress] = useState(0)
  const lastVideoIdRef = useRef<string | null>(null)
  const isSwitchingRef = useRef(false)
  const hasTriggeredEndStopRef = useRef(false)  // Track if we've already triggered stop at end

  // Performance optimization: track last seek time to debounce rapid seeks
  const lastSeekTimeRef = useRef<number>(0)
  const seekDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastCurrentTimeRef = useRef<number>(0)

  // BGM audio refs - one per track
  const bgmAudioRefs = useRef<Map<string, HTMLAudioElement>>(new Map())
  const bgmFadeIntervals = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())
  const bgmPlayingRef = useRef<Set<string>>(new Set())  // Track BGM tracks with pending play operations

  const { currentTime, setCurrentTime, isPlaying, setIsPlaying, segments, selectedSegmentId } =
    useAppStore()

  // Helper to calculate the effective playable end of a video
  // This accounts for trimming: a video may occupy timeline space but only play a portion
  // Defined here so it's accessible in both useMemo and effects
  const getEffectiveEnd = useCallback((video: VideoPosition) => {
    const sourceStart = video.sourceStart ?? 0
    // Use sourceEnd if set, otherwise duration, otherwise fall back to deriving from timeline
    const sourceEnd = video.sourceEnd ?? video.duration ?? (video.timelineEnd - video.timelineStart)
    const playableDuration = sourceEnd - sourceStart
    // The effective end is the start plus the playable duration
    // This may be less than timelineEnd if the video was trimmed from the end
    // Guard against NaN by falling back to timelineEnd
    const calculatedEnd = video.timelineStart + playableDuration
    return isNaN(calculatedEnd) ? video.timelineEnd : Math.min(video.timelineEnd, calculatedEnd)
  }, [])

  // Build video positions from VideoInfo array
  const videoPositions = useMemo((): VideoPosition[] => {
    const positions: VideoPosition[] = []

    // Check if any video has explicit timeline positions
    const hasExplicitPositions = videos.some(v => v.timeline_start !== null && v.timeline_start !== undefined)

    if (hasExplicitPositions) {
      // Use explicit timeline positions
      for (const video of videos) {
        const videoDuration = video.duration || 0
        const start = video.timeline_start ?? 0
        const end = video.timeline_end ?? (start + videoDuration)
        positions.push({
          id: video.id,
          name: video.name,
          url: `/api/v1/videos/${projectName}/${video.id}/stream`,
          timelineStart: start,
          timelineEnd: end,
          duration: videoDuration,
          // Include source trim values for proper playback of trimmed videos
          sourceStart: video.source_start ?? 0,
          sourceEnd: video.source_end,
          codec: video.codec
        })
      }
    } else {
      // Fall back to sequential layout based on order
      const sortedVideos = [...videos].sort((a, b) => a.order - b.order)
      let currentStart = 0
      for (const video of sortedVideos) {
        const videoDuration = video.duration || 0
        positions.push({
          id: video.id,
          name: video.name,
          url: `/api/v1/videos/${projectName}/${video.id}/stream`,
          timelineStart: currentStart,
          timelineEnd: currentStart + videoDuration,
          duration: videoDuration,
          sourceStart: video.source_start ?? 0,
          sourceEnd: video.source_end,
          codec: video.codec
        })
        currentStart += videoDuration
      }
    }

    // Sort by timeline start for easier lookup
    return positions.sort((a, b) => a.timelineStart - b.timelineStart)
  }, [videos, projectName])

  // Find which video should be playing at the current time
  // Also track if we're in a "gap" between videos
  // When videos overlap (stacked), prefer the one with higher order (topmost in visual stack)
  const { activeVideo, isInGap, nextVideo, isPastAllContent } = useMemo(() => {
    // First, find ALL videos that contain the current time
    // IMPORTANT: Use effectiveEnd instead of timelineEnd to respect trimmed regions
    // This ensures that when a video is trimmed, lower layer videos can show through
    const videosAtCurrentTime = videoPositions.filter(video => {
      const effectiveEnd = getEffectiveEnd(video)
      return currentTime >= video.timelineStart && currentTime < effectiveEnd
    })

    if (videosAtCurrentTime.length > 0) {
      // Multiple videos at this time? Pick the one with LOWEST order (topmost track in timeline)
      // In video editing, top track = foreground layer = should be visible
      const videosWithOrder = videosAtCurrentTime.map(vp => {
        const videoInfo = videos.find(v => v.id === vp.id)
        return { ...vp, order: videoInfo?.order ?? 0 }
      })
      // Lower order = top row in timeline = foreground = should show
      videosWithOrder.sort((a, b) => a.order - b.order)

      // Debug: log when multiple videos overlap
      if (videosWithOrder.length > 1) {
        console.log('[MultiVideoPlayer] Multiple videos at time', currentTime.toFixed(2),
          '- selecting:', videosWithOrder[0].name, '(order:', videosWithOrder[0].order, ')',
          'from:', videosWithOrder.map(v => `${v.name}(${v.order})`).join(', '))
      }

      return { activeVideo: videosWithOrder[0], isInGap: false, nextVideo: null, isPastAllContent: false }
    }

    // Not in any video - check if we're in a gap or past the end
    if (videoPositions.length > 0) {
      // Find the video that ends last (by effective end, accounting for trimming)
      const videosByEffectiveEnd = [...videoPositions].sort((a, b) => getEffectiveEnd(b) - getEffectiveEnd(a))
      const lastEndingVideo = videosByEffectiveEnd[0]
      const lastEffectiveEnd = getEffectiveEnd(lastEndingVideo)

      // If past all videos (by effective end), return a special state indicating timeline end
      // Return lastEndingVideo for display purposes, but mark isPastAllContent = true
      if (currentTime >= lastEffectiveEnd) {
        return { activeVideo: lastEndingVideo, isInGap: false, nextVideo: null, isPastAllContent: true }
      }

      // If before the first video, show BLACK SCREEN (no video)
      const firstVideo = videoPositions[0]
      if (currentTime < firstVideo.timelineStart) {
        return { activeVideo: null, isInGap: true, nextVideo: firstVideo, isPastAllContent: false }
      }

      // We're in a gap between videos - show BLACK SCREEN
      // Find the next video that starts after current time
      const next = videoPositions.find(v => v.timelineStart > currentTime)
      return {
        activeVideo: null,  // Show black screen in gaps
        isInGap: true,
        nextVideo: next || null,
        isPastAllContent: false
      }
    }

    // No videos at all
    return { activeVideo: null, isInGap: false, nextVideo: null, isPastAllContent: false }
  }, [currentTime, videoPositions, videos, getEffectiveEnd])

  // Track current time ref for video switching (to avoid dependency on currentTime)
  const currentTimeRef = useRef(currentTime)
  currentTimeRef.current = currentTime

  // Track isPlaying ref for video switching
  // IMPORTANT: This ref must be updated IMMEDIATELY when isPlaying changes,
  // not just on re-render, to prevent race conditions with async callbacks
  const isPlayingRef = useRef(isPlaying)
  isPlayingRef.current = isPlaying

  // Helper to update isPlaying state AND ref together (prevents race conditions)
  const setIsPlayingWithRef = useCallback((value: boolean) => {
    isPlayingRef.current = value  // Update ref immediately (sync)
    setIsPlaying(value)            // Schedule state update (async)
  }, [setIsPlaying])

  // Switch video when active video changes - NO delay, switch immediately
  useEffect(() => {
    if (!activeVideo || !videoRef.current) return

    const video = videoRef.current

    // Check if we actually need to switch - compare video IDs
    if (activeVideo.id === lastVideoIdRef.current) {
      // Same video - check if it was preloaded and is now ready
      // This handles the case where we preloaded from a gap and now activeVideo is defined
      if (video.readyState >= 2 && isVideoLoading) {
        console.log('[MultiVideoPlayer] Video was preloaded and is ready:', activeVideo.name)
        setIsVideoLoading(false)
        setCanPlay(true)
      }
      return // Same video, no switch needed
    }

    console.log('[MultiVideoPlayer] Switching to video:', activeVideo.name, '(order:', videos.find(v => v.id === activeVideo.id)?.order, ')')
    isSwitchingRef.current = true
    lastVideoIdRef.current = activeVideo.id
    setCurrentVideoId(activeVideo.id)
    setVideoLoadError(null)  // Clear any previous errors
    setIsVideoLoading(true)  // Start loading state
    setCanPlay(false)
    setLoadingProgress(0)

    const capturedCurrentTime = currentTimeRef.current
    const capturedActiveVideo = activeVideo
    let handlerFired = false

    // Define the loadeddata handler
    const handleLoadedData = () => {
      if (handlerFired) return
      handlerFired = true
      setVideoLoadError(null)  // Success - clear any error
      setIsVideoLoading(false)  // Loading complete
      setCanPlay(true)

      const timeIntoClip = capturedCurrentTime - capturedActiveVideo.timelineStart
      // Add sourceStart offset to get actual position in source file
      const targetTime = capturedActiveVideo.sourceStart + timeIntoClip
      const maxTime = capturedActiveVideo.sourceEnd ?? capturedActiveVideo.duration
      video.currentTime = Math.max(capturedActiveVideo.sourceStart, Math.min(targetTime, maxTime))

      // Check CURRENT playing state, not captured wasPlaying
      // User might have paused during the switch
      if (isPlayingRef.current) {
        video.play().catch(e => console.warn('Failed to resume playback:', e))
      }

      // Allow time updates after a small delay
      setTimeout(() => {
        isSwitchingRef.current = false
      }, 100)

      video.removeEventListener('loadeddata', handleLoadedData)
      video.removeEventListener('error', handleError)
      video.removeEventListener('canplay', handleCanPlay)
      video.removeEventListener('progress', handleProgress)
    }

    // Define the canplay handler (video is ready to start playing)
    const handleCanPlay = () => {
      setCanPlay(true)
      setIsVideoLoading(false)
    }

    // Define the progress handler (track buffering progress)
    const handleProgress = () => {
      if (video.buffered.length > 0 && video.duration) {
        const bufferedEnd = video.buffered.end(video.buffered.length - 1)
        const progress = Math.min(100, (bufferedEnd / video.duration) * 100)
        setLoadingProgress(progress)
      }
    }

    // Define the error handler
    const handleError = () => {
      if (handlerFired) return
      handlerFired = true
      isSwitchingRef.current = false
      setIsVideoLoading(false)
      setCanPlay(false)

      const errorMsg = video.error?.message || 'Video failed to load'
      console.error('[MultiVideoPlayer] Video load error:', errorMsg, 'for video:', capturedActiveVideo.name)

      // Check if this is a codec compatibility issue
      const codecCheck = isCodecBrowserCompatible(capturedActiveVideo.codec)
      let displayError: string

      if (!codecCheck.compatible && codecCheck.warning) {
        displayError = `Video "${capturedActiveVideo.name}" cannot play in browser.\n${codecCheck.warning}`
      } else if (errorMsg.includes('NotSupported') || errorMsg.includes('no supported sources')) {
        const codecInfo = capturedActiveVideo.codec ? ` (codec: ${capturedActiveVideo.codec})` : ''
        displayError = `Video "${capturedActiveVideo.name}"${codecInfo} uses a format your browser cannot play. Try transcoding to H.264/MP4.`
      } else {
        displayError = `Video "${capturedActiveVideo.name}" failed to load: ${errorMsg}`
      }

      setVideoLoadError(displayError)

      video.removeEventListener('loadeddata', handleLoadedData)
      video.removeEventListener('error', handleError)
      video.removeEventListener('canplay', handleCanPlay)
      video.removeEventListener('progress', handleProgress)
    }

    // Add listeners and load video
    video.addEventListener('loadeddata', handleLoadedData)
    video.addEventListener('error', handleError)
    video.addEventListener('canplay', handleCanPlay)
    video.addEventListener('progress', handleProgress)
    video.src = activeVideo.url
    video.load()

    // Fallback: ensure isSwitchingRef is reset even if loadeddata doesn't fire
    // This can happen if the video is already cached
    // Use a short timeout (200ms) just to reset the switching flag for cached videos
    const quickFallbackTimeout = setTimeout(() => {
      if (!handlerFired && video.readyState >= 2) {
        // Video loaded from cache - handlers might not have fired
        console.log('[MultiVideoPlayer] Quick fallback: Video ready from cache')
        handlerFired = true
        isSwitchingRef.current = false
        setIsVideoLoading(false)
        setCanPlay(true)
        const timeIntoClip = currentTimeRef.current - capturedActiveVideo.timelineStart
        const targetTime = capturedActiveVideo.sourceStart + timeIntoClip
        const maxTime = capturedActiveVideo.sourceEnd ?? capturedActiveVideo.duration
        video.currentTime = Math.max(capturedActiveVideo.sourceStart, Math.min(targetTime, maxTime))
        // Check CURRENT playing state, not captured wasPlaying
        if (isPlayingRef.current) {
          video.play().catch(e => console.warn('Failed to resume playback:', e))
        }
        video.removeEventListener('loadeddata', handleLoadedData)
        video.removeEventListener('error', handleError)
        video.removeEventListener('canplay', handleCanPlay)
        video.removeEventListener('progress', handleProgress)
      }
    }, 200)

    // Longer fallback: if video still hasn't loaded after 5 seconds, show error
    // This gives network requests enough time to complete
    const longFallbackTimeout = setTimeout(() => {
      if (!handlerFired) {
        console.log('[MultiVideoPlayer] Long fallback: Video still not ready after 5s, readyState:', video.readyState)
        isSwitchingRef.current = false

        if (video.readyState >= 2) {
          // Video eventually loaded
          setIsVideoLoading(false)
          setCanPlay(true)
          const timeIntoClip = currentTimeRef.current - capturedActiveVideo.timelineStart
          const targetTime = capturedActiveVideo.sourceStart + timeIntoClip
          const maxTime = capturedActiveVideo.sourceEnd ?? capturedActiveVideo.duration
          video.currentTime = Math.max(capturedActiveVideo.sourceStart, Math.min(targetTime, maxTime))
          // Check CURRENT playing state, not captured wasPlaying
          if (isPlayingRef.current) {
            video.play().catch(e => {
              console.warn('Failed to resume playback:', e)
              setIsPlayingWithRef(false)
            })
          }
        } else if (video.readyState === 0) {
          // Video never started loading - likely a network or file issue
          console.warn('[MultiVideoPlayer] Video failed to load. readyState: 0')
          setIsPlayingWithRef(false)
          setIsVideoLoading(false)
          setCanPlay(false)

          // Check codec compatibility for better error message
          const codecCheck = isCodecBrowserCompatible(capturedActiveVideo.codec)
          if (!codecCheck.compatible && codecCheck.warning) {
            setVideoLoadError(`Video "${capturedActiveVideo.name}" cannot play in browser.\n${codecCheck.warning}`)
          } else {
            const codecInfo = capturedActiveVideo.codec ? ` (codec: ${capturedActiveVideo.codec})` : ''
            setVideoLoadError(`Video "${capturedActiveVideo.name}"${codecInfo} failed to load. Check if the file exists and is accessible.`)
          }
        } else {
          // Video is loading (readyState 1) - keep waiting, don't stop
          console.log('[MultiVideoPlayer] Video still loading (readyState:', video.readyState, '), continuing to wait...')
          // Keep the loading state, don't clear handlers - let it continue loading
          return
        }

        video.removeEventListener('loadeddata', handleLoadedData)
        video.removeEventListener('error', handleError)
        video.removeEventListener('canplay', handleCanPlay)
        video.removeEventListener('progress', handleProgress)
      }
    }, 5000)

    // Cleanup function
    return () => {
      video.removeEventListener('loadeddata', handleLoadedData)
      video.removeEventListener('error', handleError)
      video.removeEventListener('canplay', handleCanPlay)
      video.removeEventListener('progress', handleProgress)
      clearTimeout(quickFallbackTimeout)
      clearTimeout(longFallbackTimeout)
    }
  }, [activeVideo, videos, setIsPlayingWithRef])

  // Handle gap playback - advance time during gaps until we reach the next video
  const gapIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const gapStartTimeRef = useRef<{ wallTime: number; position: number } | null>(null)

  useEffect(() => {
    // Clean up any existing interval
    if (gapIntervalRef.current) {
      clearInterval(gapIntervalRef.current)
      gapIntervalRef.current = null
    }

    // Only run gap playback if we're truly in a gap (no active video) and playing
    if (isInGap && isPlaying && !activeVideo) {
      if (nextVideo) {
        console.log('[MultiVideoPlayer] In gap, advancing to next video at', nextVideo.timelineStart)

        // ALWAYS re-initialize gap start when entering gap playback
        // This ensures correct timing even after seeking while paused
        gapStartTimeRef.current = {
          wallTime: Date.now(),
          position: currentTimeRef.current
        }

        const nextVideoStart = nextVideo.timelineStart

        gapIntervalRef.current = setInterval(() => {
          if (!gapStartTimeRef.current) return

          const elapsed = (Date.now() - gapStartTimeRef.current.wallTime) / 1000
          const newTime = gapStartTimeRef.current.position + elapsed

          if (newTime >= nextVideoStart) {
            // Reached the next video - set time and the activeVideo change will trigger video loading
            console.log('[MultiVideoPlayer] Gap ended, starting video at', nextVideoStart)
            setCurrentTime(nextVideoStart)
            gapStartTimeRef.current = null
            if (gapIntervalRef.current) {
              clearInterval(gapIntervalRef.current)
              gapIntervalRef.current = null
            }
          } else {
            setCurrentTime(newTime)
          }
        }, 50)
      } else {
        // No next video available - stop playback
        console.log('[MultiVideoPlayer] In gap with no next video, stopping playback')
        setIsPlayingWithRef(false)
      }
    } else {
      gapStartTimeRef.current = null
    }

    return () => {
      if (gapIntervalRef.current) {
        clearInterval(gapIntervalRef.current)
        gapIntervalRef.current = null
      }
    }
  }, [isInGap, isPlaying, nextVideo, activeVideo, setCurrentTime, setIsPlayingWithRef])

  // Track timeline changes to prevent false-positive end-of-content detection
  const lastTimelineChangeRef = useRef<number>(0)
  const lastVideoPositionsRef = useRef<string>('')

  // Detect timeline changes (videos added/removed/modified including trimming)
  // Create a signature string that captures all relevant video position data
  useEffect(() => {
    const signature = videoPositions.map(v =>
      `${v.id}:${v.timelineStart}-${v.timelineEnd}:${v.sourceStart}-${v.sourceEnd}`
    ).join('|')

    if (lastVideoPositionsRef.current !== signature) {
      lastTimelineChangeRef.current = Date.now()
      lastVideoPositionsRef.current = signature
    }
  }, [videoPositions])

  // Also detect when total duration changes
  useEffect(() => {
    lastTimelineChangeRef.current = Date.now()
  }, [totalDuration])

  // Auto-stop playback when past all video content
  // This ensures playback stops when we've reached the end of all trimmed videos
  // Added debounce to prevent false triggers when timeline is being modified
  useEffect(() => {
    // Reset the flag when we're no longer past all content (user seeked back)
    if (!isPastAllContent) {
      hasTriggeredEndStopRef.current = false
      return
    }

    if (isPastAllContent && isPlaying && !hasTriggeredEndStopRef.current) {
      // Don't stop playback immediately after timeline changes (user might be extending video)
      // Wait 200ms to allow the timeline to settle
      const timeSinceTimelineChange = Date.now() - lastTimelineChangeRef.current
      if (timeSinceTimelineChange < 200) {
        // Schedule a re-check after the debounce period
        const timeout = setTimeout(() => {
          // Re-check conditions - they may have changed
          // The effect will re-run naturally if isPastAllContent is still true
        }, 200 - timeSinceTimelineChange)
        return () => clearTimeout(timeout)
      }

      // Mark that we've triggered the stop to prevent repeated logging
      hasTriggeredEndStopRef.current = true
      console.log('[MultiVideoPlayer] Past all video content, stopping playback')
      setIsPlayingWithRef(false)

      // Also pause the video element directly
      if (videoRef.current && !videoRef.current.paused) {
        videoRef.current.pause()
      }
    }
  }, [isPastAllContent, isPlaying, setIsPlayingWithRef])

  // Track store's currentTime for gap detection in handleTimeUpdate
  // This prevents playhead jumps when video plays from a cached position while in a gap
  const storeCurrentTimeRef = useRef(currentTime)
  storeCurrentTimeRef.current = currentTime

  // Sync video with store - report absolute timeline time
  useEffect(() => {
    const video = videoRef.current
    if (!video || !activeVideo) return

    const handleTimeUpdate = () => {
      if (isSwitchingRef.current) return

      // Calculate effective timeline end accounting for trimming
      const sourceEnd = activeVideo.sourceEnd ?? activeVideo.duration
      const playableDuration = sourceEnd - activeVideo.sourceStart
      const effectiveTimelineEnd = Math.min(activeVideo.timelineEnd, activeVideo.timelineStart + playableDuration)

      // Report absolute timeline time accounting for source trimming
      // video.currentTime is position in source file, subtract sourceStart to get time into clip
      const timeIntoClip = video.currentTime - activeVideo.sourceStart
      const absoluteTime = timeIntoClip + activeVideo.timelineStart

      // Always update time - the activeVideo useMemo already handles determining
      // which video should be active at the current time
      setCurrentTime(absoluteTime)

      // Check if we've reached the end of this video and should switch
      // NOTE: We use a small threshold (0.05s) to detect near-end, and only trigger once
      // by checking that we haven't already set time past this video's effective end
      const isNearEnd = video.currentTime >= sourceEnd - 0.05
      const alreadyPastEnd = storeCurrentTimeRef.current >= effectiveTimelineEnd

      // Don't trigger end-of-video transitions if timeline was recently modified
      // This prevents glitching when user extends video while playing
      const timeSinceTimelineChange = Date.now() - lastTimelineChangeRef.current
      if (isNearEnd && !alreadyPastEnd && isPlaying && timeSinceTimelineChange >= 200) {
        // Look for any video that CONTAINS the time right after this video's EFFECTIVE end
        // This handles overlapping videos where one continues after another ends
        // Important: use effectiveTimelineEnd (accounts for trimming), not timelineEnd
        // CRITICAL: Also check that the target video hasn't ended (use getEffectiveEnd)
        const timeAfterEnd = effectiveTimelineEnd + 0.01
        const nextVideo = videoPositions.find(v =>
          v.id !== activeVideo.id &&
          timeAfterEnd >= v.timelineStart &&
          timeAfterEnd < getEffectiveEnd(v)  // Use effective end to account for trimming
        )
        // Also check for video that starts exactly at or after this one's EFFECTIVE end (non-overlapping)
        const subsequentVideo = videoPositions.find(v =>
          v.id !== activeVideo.id &&
          v.timelineStart >= effectiveTimelineEnd
        )
        const targetVideo = nextVideo || subsequentVideo
        if (targetVideo) {
          // Verify the target video can still play at this time
          const targetEffectiveEnd = getEffectiveEnd(targetVideo)
          const targetStartTime = nextVideo ? effectiveTimelineEnd + 0.01 : targetVideo.timelineStart
          if (targetStartTime < targetEffectiveEnd) {
            // Move decisively past this video's effective end to prevent oscillation
            console.log(`[MultiVideoPlayer] Video ${activeVideo.name} ended at effective end ${effectiveTimelineEnd.toFixed(2)}s, transitioning to ${targetVideo.name} at ${targetStartTime.toFixed(2)}s`)
            setCurrentTime(targetStartTime)
          } else {
            // Target video has also ended due to trimming - stop playback (only trigger once)
            if (!hasTriggeredEndStopRef.current) {
              hasTriggeredEndStopRef.current = true
              console.log(`[MultiVideoPlayer] Video ${activeVideo.name} ended, and next video ${targetVideo.name} is also past its effective end (${targetEffectiveEnd.toFixed(2)}s) - stopping playback`)
              setIsPlayingWithRef(false)
            }
          }
        } else {
          // No next video - stop playback (only trigger once)
          if (!hasTriggeredEndStopRef.current) {
            hasTriggeredEndStopRef.current = true
            console.log(`[MultiVideoPlayer] Video ${activeVideo.name} ended at effective end ${effectiveTimelineEnd.toFixed(2)}s, no more videos - stopping playback`)
            setIsPlayingWithRef(false)
          }
        }
      }
    }

    const handlePlay = () => {
      // CRITICAL: Check the ref value (which is updated synchronously) not state
      // If user has paused, don't let any video play event override that
      if (!isPlayingRef.current) {
        // User has paused - don't set isPlaying to true, pause the video instead
        videoRef.current?.pause()
        return
      }
      // If we get here, isPlaying is already true, just ensure sync
      // Don't call setIsPlayingWithRef(true) as it would cause unnecessary re-renders
    }
    const handlePause = () => {
      // Always allow pause - update ref immediately to prevent race conditions
      setIsPlayingWithRef(false)
    }
    const handleEnded = () => {
      // Calculate effective timeline end accounting for trimming
      const sourceEnd = activeVideo.sourceEnd ?? activeVideo.duration
      const playableDuration = sourceEnd - activeVideo.sourceStart
      const effectiveTimelineEnd = Math.min(activeVideo.timelineEnd, activeVideo.timelineStart + playableDuration)

      // Look for any video that CONTAINS the time right after this video's EFFECTIVE end
      // CRITICAL: Use getEffectiveEnd to account for trimming on the target video
      const timeAfterEnd = effectiveTimelineEnd + 0.01
      const nextVideo = videoPositions.find(v =>
        v.id !== activeVideo.id &&
        timeAfterEnd >= v.timelineStart &&
        timeAfterEnd < getEffectiveEnd(v)  // Use effective end to account for trimming
      )
      // Also check for video that starts exactly at or after this one's effective end
      const subsequentVideo = videoPositions.find(v =>
        v.id !== activeVideo.id &&
        v.timelineStart >= effectiveTimelineEnd
      )
      const targetVideo = nextVideo || subsequentVideo
      if (targetVideo) {
        // Verify the target video can still play at the calculated start time
        const targetEffectiveEnd = getEffectiveEnd(targetVideo)
        const targetStartTime = nextVideo ? effectiveTimelineEnd : targetVideo.timelineStart
        if (targetStartTime < targetEffectiveEnd) {
          setCurrentTime(targetStartTime)
        } else {
          // Target video has also ended due to trimming - stop playback
          console.log(`[MultiVideoPlayer] handleEnded: next video ${targetVideo.name} is past its effective end - stopping playback`)
          setIsPlayingWithRef(false)
        }
      } else {
        setIsPlayingWithRef(false)
      }
    }

    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)
    video.addEventListener('ended', handleEnded)

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
      video.removeEventListener('ended', handleEnded)
    }
  }, [activeVideo, videoPositions, isPlaying, setCurrentTime, setIsPlayingWithRef, getEffectiveEnd])

  // Handle external time changes (e.g., clicking on timeline or dragging playhead)
  // Uses debouncing to prevent lag when rapidly moving the playhead
  useEffect(() => {
    const video = videoRef.current
    if (!video || !activeVideo || isSwitchingRef.current) return

    // Calculate target position in source file accounting for source trimming
    const timeIntoClip = currentTime - activeVideo.timelineStart
    const targetSourceTime = activeVideo.sourceStart + timeIntoClip

    // Calculate the effective clip duration (trimmed region)
    const effectiveEnd = activeVideo.sourceEnd ?? activeVideo.duration
    const clipDuration = effectiveEnd - activeVideo.sourceStart

    // Only seek if within this video's trimmed range and significantly different
    if (timeIntoClip >= 0 && timeIntoClip <= clipDuration) {
      const timeDiff = Math.abs(video.currentTime - targetSourceTime)

      // For small differences during normal playback, don't seek (video handles this)
      if (timeDiff < 0.2) return

      // For larger differences (user seeking), debounce to prevent lag
      const now = Date.now()
      const timeSinceLastSeek = now - lastSeekTimeRef.current

      // Clear any pending debounced seek
      if (seekDebounceRef.current) {
        clearTimeout(seekDebounceRef.current)
      }

      // If seeking rapidly (< 50ms between seeks), debounce
      if (timeSinceLastSeek < 50 && !isPlaying) {
        seekDebounceRef.current = setTimeout(() => {
          if (videoRef.current && !isSwitchingRef.current) {
            videoRef.current.currentTime = targetSourceTime
            lastSeekTimeRef.current = Date.now()
          }
        }, 50)
      } else {
        // Normal seek
        video.currentTime = targetSourceTime
        lastSeekTimeRef.current = now
      }
    }

    // Track last currentTime for change detection
    lastCurrentTimeRef.current = currentTime
  }, [currentTime, activeVideo, isPlaying])

  // Handle external play/pause changes (e.g., clicking segment play button)
  useEffect(() => {
    const video = videoRef.current
    if (!video || isSwitchingRef.current) return

    // Don't try to play video element directly when in a gap
    // The gap playback effect handles advancing through gaps
    if (isInGap && !activeVideo) {
      return
    }

    // Don't try to play if video isn't ready yet
    if (isPlaying && video.paused) {
      // Only play if we have a source and video is ready
      if (video.src && canPlay) {
        video.play().catch(e => console.warn('Failed to play video:', e))
      } else if (video.src && !canPlay) {
        // Video has source but not ready yet - will play when loadeddata fires
        console.log('[MultiVideoPlayer] Waiting for video to be ready before playing')
      }
      // If no source, the initial load effect will set it
    } else if (!isPlaying && !video.paused) {
      video.pause()
    }
  }, [isPlaying, isInGap, activeVideo, canPlay])

  // Auto-play when video becomes ready if user already clicked play
  useEffect(() => {
    const video = videoRef.current
    if (!video || isSwitchingRef.current) return

    // If canPlay just became true and we should be playing, start playback
    if (canPlay && isPlaying && video.paused && activeVideo && !isInGap) {
      console.log('[MultiVideoPlayer] Video ready, starting playback')
      video.play().catch(e => console.warn('Failed to auto-play video:', e))
    }
  }, [canPlay, isPlaying, activeVideo, isInGap])

  // Safeguard: Monitor video readyState and correct stale loading state
  // This handles cases where loading state gets stuck due to missed events
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    // If video is ready but loading state is stuck, fix it
    if (isVideoLoading && video.readyState >= 3 && video.src && !isSwitchingRef.current) {
      console.log('[MultiVideoPlayer] Safeguard: Video is ready but isVideoLoading was stuck, fixing...')
      setIsVideoLoading(false)
      setCanPlay(true)
    }

    // Also listen for loadeddata events that might have been missed
    const handleLoadedData = () => {
      if (isVideoLoading && !isSwitchingRef.current) {
        console.log('[MultiVideoPlayer] Safeguard: loadeddata event caught')
        setIsVideoLoading(false)
        setCanPlay(true)
      }
    }

    video.addEventListener('loadeddata', handleLoadedData)
    return () => video.removeEventListener('loadeddata', handleLoadedData)
  }, [isVideoLoading])

  // Stop segment audio when video stops
  const stopSegmentAudio = useCallback(() => {
    segmentAudioPlayingRef.current = false  // Reset play operation flag
    if (segmentAudioRef.current) {
      segmentAudioRef.current.pause()
      segmentAudioRef.current = null
    }
    setPlayingSegmentAudio(null)
  }, [])

  // Helper to convert segment video-relative times to absolute timeline times
  // Segment times are stored relative to their parent video, not absolute timeline
  const getSegmentTimelinePosition = useCallback((segment: typeof segments[0]) => {
    // Find the video this segment belongs to
    const videoPos = segment.video_id ? videoPositions.find(v => v.id === segment.video_id) : null
    const videoOffset = videoPos?.timelineStart ?? 0

    return {
      start: segment.start_time + videoOffset,
      end: segment.end_time + videoOffset
    }
  }, [videoPositions])

  // Handle segment audio sync (same as original VideoPlayer)
  // Optimized to prevent audio recreation during rapid seeking
  useEffect(() => {
    if (!audioSyncEnabled || !isPlaying) {
      stopSegmentAudio()
      lastPlayedSegmentRef.current = null
      return
    }

    // Find current segment - convert video-relative times to absolute timeline times
    const currentSegment = segments.find((s) => {
      const pos = getSegmentTimelinePosition(s)
      return currentTime >= pos.start && currentTime <= pos.end
    })

    if (currentSegment && currentSegment.audio_path) {
      // Use absolute timeline position for time calculation
      const segmentPos = getSegmentTimelinePosition(currentSegment)
      const timeSinceSegmentStart = currentTime - segmentPos.start
      // Include audio_offset for trimmed segments
      const audioOffset = currentSegment.audio_offset ?? 0

      // Check if we need to start new audio
      const isNewSegment = lastPlayedSegmentRef.current !== currentSegment.id
      const isAtSegmentStart = timeSinceSegmentStart < 0.5 && playingSegmentAudio !== currentSegment.id

      // If same segment is already playing, just sync the position if needed
      if (!isNewSegment && segmentAudioRef.current && playingSegmentAudio === currentSegment.id) {
        // Check if audio is significantly out of sync (more than 0.5s)
        const expectedAudioTime = audioOffset + timeSinceSegmentStart
        const actualAudioTime = segmentAudioRef.current.currentTime
        if (Math.abs(expectedAudioTime - actualAudioTime) > 0.5) {
          segmentAudioRef.current.currentTime = expectedAudioTime
        }
        return
      }

      if (isNewSegment || isAtSegmentStart) {
        // Prevent rapid play/pause race conditions
        // If a play operation is already in progress, skip this update
        if (segmentAudioPlayingRef.current) {
          return
        }

        stopSegmentAudio()

        let audioUrl = currentSegment.audio_path
        if (audioUrl.includes('storage/')) {
          audioUrl = `/storage/${audioUrl.split('storage/').pop()}`
        } else if (!audioUrl.startsWith('/')) {
          audioUrl = `/storage/${audioUrl}`
        }

        const audio = new Audio(audioUrl)
        audio.volume = volume

        // Seek to correct position: audio_offset + time since segment start
        const seekPosition = audioOffset + Math.max(0, timeSinceSegmentStart)
        if (seekPosition > 0.1) {
          audio.currentTime = seekPosition
        }

        segmentAudioRef.current = audio
        lastPlayedSegmentRef.current = currentSegment.id
        setPlayingSegmentAudio(currentSegment.id)

        // Mark play operation as in progress
        segmentAudioPlayingRef.current = true
        const currentAudioInstance = audio  // Capture reference to detect stale operations

        audio.play()
          .then(() => {
            // Only reset the flag if this is still the current audio instance
            if (segmentAudioRef.current === currentAudioInstance) {
              segmentAudioPlayingRef.current = false
            }
          })
          .catch((e) => {
            // Only update state if this is still the current audio instance
            // This prevents stale AbortError callbacks from affecting new audio
            if (segmentAudioRef.current === currentAudioInstance) {
              segmentAudioPlayingRef.current = false
              // Only log non-AbortError issues (AbortError is expected when switching)
              if (e.name !== 'AbortError') {
                console.warn('Failed to play segment audio:', e)
              }
              setPlayingSegmentAudio(null)
            }
          })

        audio.onended = () => {
          if (segmentAudioRef.current === audio) {
            setPlayingSegmentAudio(null)
          }
        }
        audio.onerror = () => {
          if (segmentAudioRef.current === audio) {
            setPlayingSegmentAudio(null)
          }
        }
      }
    } else {
      if (playingSegmentAudio) stopSegmentAudio()
      if (!currentSegment) lastPlayedSegmentRef.current = null
    }
  }, [currentTime, segments, audioSyncEnabled, isPlaying, volume, stopSegmentAudio, playingSegmentAudio, getSegmentTimelinePosition])

  // Cleanup audio on unmount
  useEffect(() => {
    return () => stopSegmentAudio()
  }, [stopSegmentAudio])

  // Sync audio volume
  useEffect(() => {
    if (segmentAudioRef.current) {
      segmentAudioRef.current.volume = volume
    }
  }, [volume])

  // BGM Audio Management
  const stopBgmTrack = useCallback((trackId: string) => {
    const audio = bgmAudioRefs.current.get(trackId)
    if (audio) {
      audio.pause()
      audio.currentTime = 0
      bgmAudioRefs.current.delete(trackId)
    }
    const fadeInterval = bgmFadeIntervals.current.get(trackId)
    if (fadeInterval) {
      clearInterval(fadeInterval)
      bgmFadeIntervals.current.delete(trackId)
    }
    bgmPlayingRef.current.delete(trackId)  // Clear pending play operation
    setPlayingBgmTracks(prev => {
      const next = new Set(prev)
      next.delete(trackId)
      return next
    })
  }, [])

  const stopAllBgmTracks = useCallback(() => {
    bgmAudioRefs.current.forEach((audio, trackId) => {
      audio.pause()
      audio.currentTime = 0
      const fadeInterval = bgmFadeIntervals.current.get(trackId)
      if (fadeInterval) {
        clearInterval(fadeInterval)
      }
    })
    bgmAudioRefs.current.clear()
    bgmFadeIntervals.current.clear()
    bgmPlayingRef.current.clear()  // Clear pending play operations
    setPlayingBgmTracks(new Set())
  }, [])

  // Apply fade to a track
  const applyFade = useCallback((audio: HTMLAudioElement, track: BGMTrack, targetVolume: number, fadeType: 'in' | 'out') => {
    const fadeDuration = fadeType === 'in' ? (track.fade_in || 0) : (track.fade_out || 0)
    if (fadeDuration <= 0) {
      audio.volume = targetVolume
      return
    }

    const steps = 20 // Number of volume steps
    const stepDuration = (fadeDuration * 1000) / steps
    const startVolume = fadeType === 'in' ? 0 : targetVolume
    const endVolume = fadeType === 'in' ? targetVolume : 0
    const volumeStep = (endVolume - startVolume) / steps
    let currentStep = 0

    audio.volume = startVolume

    // Clear any existing fade interval for this track
    const existingInterval = bgmFadeIntervals.current.get(track.id)
    if (existingInterval) {
      clearInterval(existingInterval)
    }

    const interval = setInterval(() => {
      currentStep++
      const newVolume = Math.max(0, Math.min(1, startVolume + volumeStep * currentStep))
      audio.volume = newVolume

      if (currentStep >= steps) {
        clearInterval(interval)
        bgmFadeIntervals.current.delete(track.id)
        if (fadeType === 'out') {
          audio.pause()
        }
      }
    }, stepDuration)

    bgmFadeIntervals.current.set(track.id, interval)
  }, [])

  // Calculate track volume based on track settings and global volume
  // Uses dB-based calculation to match export pipeline exactly
  const getTrackVolume = useCallback((track: BGMTrack) => {
    if (track.muted) return 0
    // Track volume is 0-100, convert using dB formula to match backend
    // Backend uses: base_reduction = 20dB, then adds 20*log10(100/volume)
    // Linear equivalent: 10^(-20/20) = 0.1 for base, then multiply by (volume/100)
    const trackVolumeRatio = (track.volume || 100) / 100
    // Base BGM reduction: -20dB = 10^(-20/20) = 0.1 (matches backend BGM_VOLUME_REDUCTION)
    const bgmReduction = 0.1
    return volume * trackVolumeRatio * bgmReduction
  }, [volume])

  // BGM sync effect - manages playback of all BGM tracks
  // Optimized to reduce unnecessary operations during playback
  useEffect(() => {
    if (!bgmSyncEnabled || !isPlaying || bgmTracks.length === 0) {
      stopAllBgmTracks()
      return
    }

    // For each BGM track, determine if it should be playing at currentTime
    bgmTracks.forEach(track => {
      // Get effective end time (0 means until timeline end)
      const effectiveEndTime = track.end_time > 0 ? track.end_time : totalDuration
      const isInRange = currentTime >= track.start_time && currentTime < effectiveEndTime

      const existingAudio = bgmAudioRefs.current.get(track.id)

      if (isInRange && !track.muted) {
        const trackVolume = getTrackVolume(track)

        if (!existingAudio) {
          // Start playing this track
          let audioPath = track.path
          if (audioPath.includes('storage/')) {
            audioPath = `/storage/${audioPath.split('storage/').pop()}`
          } else if (!audioPath.startsWith('/')) {
            audioPath = `/storage/${audioPath}`
          }

          const audio = new Audio(audioPath)
          audio.loop = track.loop || false

          // Calculate where in the audio file we should start
          // Include audio_offset for trimmed tracks (like segment.audio_offset)
          const timeIntoTrack = currentTime - track.start_time
          const audioOffset = track.audio_offset || 0
          const trackDuration = track.duration || 0
          const remainingAudio = Math.max(0, trackDuration - audioOffset)

          // Seek position = audio_offset + time since track started on timeline
          let seekPosition = audioOffset + timeIntoTrack

          if (trackDuration > 0 && track.loop && remainingAudio > 0) {
            // If looping, calculate position within the remaining audio after offset
            seekPosition = audioOffset + (timeIntoTrack % remainingAudio)
          }

          if (seekPosition > 0.1) {
            audio.currentTime = seekPosition
          }

          bgmAudioRefs.current.set(track.id, audio)

          // Apply fade in if configured
          if (track.fade_in && track.fade_in > 0 && timeIntoTrack < track.fade_in) {
            applyFade(audio, track, trackVolume, 'in')
          } else {
            audio.volume = trackVolume
          }

          // Mark play operation as in progress
          bgmPlayingRef.current.add(track.id)
          const currentAudioInstance = audio  // Capture reference to detect stale operations

          audio.play()
            .then(() => {
              // Only clear if this is still the current audio instance
              if (bgmAudioRefs.current.get(track.id) === currentAudioInstance) {
                bgmPlayingRef.current.delete(track.id)
              }
            })
            .catch((e) => {
              // Only process error if this is still the current audio instance
              if (bgmAudioRefs.current.get(track.id) === currentAudioInstance) {
                bgmPlayingRef.current.delete(track.id)
                // AbortError is expected when playback is interrupted - don't warn about it
                if (e.name !== 'AbortError') {
                  console.warn(`Failed to play BGM track ${track.name}:`, e)
                }
              }
            })

          // Only update state if not already in the set (avoids unnecessary re-renders)
          setPlayingBgmTracks(prev => {
            if (prev.has(track.id)) return prev
            const next = new Set(prev)
            next.add(track.id)
            return next
          })

          // Handle track end
          audio.onended = () => {
            if (!track.loop) {
              stopBgmTrack(track.id)
            }
          }
        } else {
          // Track is already playing - check for significant sync drift and correct if needed
          const timeIntoTrack = currentTime - track.start_time
          const audioOffset = track.audio_offset || 0
          const expectedPosition = audioOffset + timeIntoTrack
          const actualPosition = existingAudio.currentTime

          // Only sync if significantly out of sync (> 1 second) to avoid constant seeking
          if (Math.abs(expectedPosition - actualPosition) > 1.0) {
            existingAudio.currentTime = expectedPosition
          }

          // Check if we need to apply fade out near the end
          const timeUntilEnd = effectiveEndTime - currentTime

          if (track.fade_out && track.fade_out > 0 && timeUntilEnd <= track.fade_out) {
            // Start fade out
            applyFade(existingAudio, track, trackVolume, 'out')
          } else if (!bgmFadeIntervals.current.has(track.id)) {
            // Only update volume if not fading
            existingAudio.volume = trackVolume
          }
        }
      } else if (existingAudio) {
        // Track should stop (out of range or muted)
        stopBgmTrack(track.id)
      }
    })

    // Clean up tracks that no longer exist
    bgmAudioRefs.current.forEach((_, trackId) => {
      if (!bgmTracks.find(t => t.id === trackId)) {
        stopBgmTrack(trackId)
      }
    })
  }, [currentTime, bgmTracks, bgmSyncEnabled, isPlaying, totalDuration, getTrackVolume, stopAllBgmTracks, stopBgmTrack, applyFade])

  // Sync BGM volume when global volume changes
  useEffect(() => {
    bgmAudioRefs.current.forEach((audio, trackId) => {
      const track = bgmTracks.find(t => t.id === trackId)
      if (track && !bgmFadeIntervals.current.has(trackId)) {
        audio.volume = getTrackVolume(track)
      }
    })
  }, [volume, bgmTracks, getTrackVolume])

  // Cleanup BGM on unmount
  useEffect(() => {
    return () => stopAllBgmTracks()
  }, [stopAllBgmTracks])

  // Comprehensive cleanup on unmount - ensures ALL resources are freed
  // This catches any resources that might be missed by individual effect cleanups
  useEffect(() => {
    return () => {
      // Stop gap playback interval
      if (gapIntervalRef.current) {
        clearInterval(gapIntervalRef.current)
        gapIntervalRef.current = null
      }

      // Stop any seek debounce timeout
      if (seekDebounceRef.current) {
        clearTimeout(seekDebounceRef.current)
        seekDebounceRef.current = null
      }

      // Pause video element to stop any ongoing streams
      if (videoRef.current) {
        videoRef.current.pause()
        videoRef.current.src = ''  // Release video stream
      }

      // Stop all BGM audio elements directly (in case stopAllBgmTracks missed any)
      bgmAudioRefs.current.forEach((audio) => {
        audio.pause()
        audio.src = ''
      })
      bgmAudioRefs.current.clear()
      bgmPlayingRef.current.clear()  // Clear pending play operations

      // Clear all BGM fade intervals
      bgmFadeIntervals.current.forEach((interval) => clearInterval(interval))
      bgmFadeIntervals.current.clear()

      // Stop segment audio
      if (segmentAudioRef.current) {
        segmentAudioRef.current.pause()
        segmentAudioRef.current.src = ''
        segmentAudioRef.current = null
      }
    }
  }, [])

  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return

    // Handle gap case - when in a gap, we can't play the video element directly
    // Instead, we set isPlaying to true which will trigger the gap playback effect
    if (isInGap && !activeVideo) {
      if (isPlaying) {
        // Pause - stop gap playback
        setIsPlayingWithRef(false)
      } else {
        // Play - start gap playback (the gap effect will advance time)
        setIsPlayingWithRef(true)
      }
      return
    }

    // Block playback if video is not ready yet
    if (!canPlay && !isInGap && isVideoLoading) {
      toast('Video is still loading. Please wait...', { icon: '⏳', duration: 2000 })
      return
    }

    // Normal case - video is available
    // IMPORTANT: Update ref BEFORE calling play/pause to prevent race conditions
    if (video.paused) {
      isPlayingRef.current = true  // Set ref before play so handlePlay sees correct value
      video.play().catch(e => {
        console.warn('Failed to play video:', e)
        isPlayingRef.current = false  // Revert on failure
      })
      setIsPlaying(true)  // Sync state
    } else {
      isPlayingRef.current = false  // Set ref before pause
      video.pause()
      setIsPlaying(false)  // Sync state
    }
  }

  const toggleMute = () => {
    const video = videoRef.current
    if (!video) return

    video.muted = !video.muted
    setIsMuted(video.muted)
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current
    if (!video) return

    const newVolume = parseFloat(e.target.value)
    video.volume = newVolume
    setVolume(newVolume)
    setIsMuted(newVolume === 0)
  }

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const progress = progressRef.current
    if (!progress) return

    const rect = progress.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width
    const newTime = pos * totalDuration
    setCurrentTime(newTime)
  }

  const skip = (seconds: number) => {
    const newTime = Math.max(0, Math.min(totalDuration, currentTime + seconds))
    setCurrentTime(newTime)
  }

  const toggleFullscreen = () => {
    const video = videoRef.current
    if (!video) return
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      video.requestFullscreen()
    }
  }

  // Get segment at current time (using absolute timeline positions)
  const currentSegmentForUI = useMemo(() => {
    return segments.find((s) => {
      const pos = getSegmentTimelinePosition(s)
      return currentTime >= pos.start && currentTime <= pos.end
    })
  }, [segments, currentTime, getSegmentTimelinePosition])

  // Initial video load - preload the first video or active video
  // This ensures we have a video ready even when starting in a gap
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    // If we have an active video, load it (the switch effect will handle it)
    if (activeVideo && !currentVideoId) {
      console.log('[MultiVideoPlayer] Initial load:', activeVideo.name)
      setCurrentVideoId(activeVideo.id)
      lastVideoIdRef.current = activeVideo.id
      video.src = activeVideo.url
      setIsVideoLoading(true)
      setCanPlay(false)
      // Note: Event handlers are attached by the video switch effect
    }
    // If we're in a gap but have a next video, preload it
    else if (isInGap && nextVideo && !currentVideoId) {
      console.log('[MultiVideoPlayer] Preloading next video from gap:', nextVideo.name)
      setCurrentVideoId(nextVideo.id)
      lastVideoIdRef.current = nextVideo.id

      // Define handlers for preload case
      const handlePreloadReady = () => {
        console.log('[MultiVideoPlayer] Preloaded video ready:', nextVideo.name)
        setIsVideoLoading(false)
        setCanPlay(true)
        video.removeEventListener('loadeddata', handlePreloadReady)
        video.removeEventListener('canplay', handlePreloadCanPlay)
        video.removeEventListener('error', handlePreloadError)
      }

      const handlePreloadCanPlay = () => {
        setCanPlay(true)
        setIsVideoLoading(false)
      }

      const handlePreloadError = () => {
        console.error('[MultiVideoPlayer] Preload error for:', nextVideo.name)
        setIsVideoLoading(false)
        setCanPlay(false)
        video.removeEventListener('loadeddata', handlePreloadReady)
        video.removeEventListener('canplay', handlePreloadCanPlay)
        video.removeEventListener('error', handlePreloadError)
      }

      video.addEventListener('loadeddata', handlePreloadReady)
      video.addEventListener('canplay', handlePreloadCanPlay)
      video.addEventListener('error', handlePreloadError)

      video.src = nextVideo.url
      setIsVideoLoading(true)
      setCanPlay(false)

      // Check if video is already ready (from browser cache)
      if (video.readyState >= 3) { // HAVE_FUTURE_DATA or higher
        console.log('[MultiVideoPlayer] Video already ready from cache')
        setIsVideoLoading(false)
        setCanPlay(true)
      }
    }
    // If in a gap with no video to load, clear loading state
    else if (isInGap && !activeVideo && !nextVideo) {
      setIsVideoLoading(false)
      setCanPlay(true) // Can "play" through empty gap
    }
  }, [activeVideo, currentVideoId, isInGap, nextVideo])

  if (videos.length === 0) {
    return (
      <div className="relative bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center">
        <div className="text-text-muted">No videos in project</div>
      </div>
    )
  }

  return (
    <div className="relative bg-black rounded-lg overflow-hidden group">
      {/* Video element - only invisible when in a true gap (no active video) */}
      <video
        ref={videoRef}
        className={clsx("w-full aspect-video", isInGap && !activeVideo && "invisible")}
        onClick={togglePlay}
      />

      {/* Black screen overlay for gaps (when no video at current time) */}
      {isInGap && !activeVideo && (
        <div
          className="absolute inset-0 bg-black flex items-center justify-center cursor-pointer"
          onClick={togglePlay}
        >
          {nextVideo && (
            <div className="text-text-muted text-sm">
              {isPlaying ? (
                <span>Playing through gap... Next video at {formatTime(nextVideo.timelineStart)}</span>
              ) : (
                <span>Gap in timeline • Next video: {nextVideo.name} at {formatTime(nextVideo.timelineStart)}</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Loading overlay - show when video is loading */}
      {isVideoLoading && activeVideo && !videoLoadError && (
        <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center z-10">
          <div className="relative">
            {/* Spinning loader */}
            <Loader2 className="w-12 h-12 animate-spin text-accent-red" />
          </div>
          <div className="mt-4 text-center">
            <p className="text-sm text-text-primary">Loading video...</p>
            <p className="text-xs text-text-muted mt-1">{activeVideo.name}</p>
            {loadingProgress > 0 && (
              <div className="mt-2 w-32 h-1 bg-terminal-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent-red transition-all duration-300"
                  style={{ width: `${loadingProgress}%` }}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error overlay for video load failures */}
      {videoLoadError && (
        <div className="absolute inset-0 bg-black/90 flex items-center justify-center">
          <div className="text-center p-6 max-w-lg">
            <div className="flex items-center justify-center gap-2 text-red-500 mb-3">
              <AlertTriangle className="w-5 h-5" />
              <span className="font-medium">Video Load Error</span>
            </div>
            <div className="text-text-muted text-sm whitespace-pre-line mb-4">
              {videoLoadError}
            </div>
            {activeVideo?.codec && (
              <div className="text-text-muted text-xs mb-4 bg-terminal-bg/50 px-3 py-2 rounded inline-block">
                Codec: <span className="text-accent-primary">{activeVideo.codec}</span>
              </div>
            )}
            <div className="flex gap-2 justify-center">
              <button
                onClick={() => {
                  setVideoLoadError(null)
                  // Try to reload the video
                  if (videoRef.current && activeVideo) {
                    videoRef.current.src = activeVideo.url
                    videoRef.current.load()
                  }
                }}
                className="px-4 py-2 text-sm bg-terminal-elevated hover:bg-terminal-border rounded transition-colors"
              >
                Retry
              </button>
              <button
                onClick={() => setVideoLoadError(null)}
                className="px-4 py-2 text-sm text-text-muted hover:text-text-primary transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Current video indicator */}
      {activeVideo && videos.length > 1 && (
        <div className="absolute top-4 right-4 flex items-center gap-2">
          <div className="bg-purple-500/90 text-white text-xs px-2 py-1 rounded font-mono flex items-center gap-1">
            <Film className="w-3 h-3" />
            {activeVideo.name}
          </div>
        </div>
      )}

      {/* Current segment and BGM indicators */}
      <div className="absolute top-4 left-4 flex items-center gap-2">
        {currentSegmentForUI && (
          <>
            <div className="bg-accent-red/90 text-white text-xs px-2 py-1 rounded font-mono">
              {currentSegmentForUI.name}
            </div>
            {playingSegmentAudio === currentSegmentForUI.id && (
              <div className="bg-green-500/90 text-white text-xs px-2 py-1 rounded font-mono flex items-center gap-1">
                <Headphones className="w-3 h-3" />
                TTS
              </div>
            )}
          </>
        )}
        {playingBgmTracks.size > 0 && (
          <div className="bg-teal-500/90 text-white text-xs px-2 py-1 rounded font-mono flex items-center gap-1">
            <Music className="w-3 h-3" />
            BGM ({playingBgmTracks.size})
          </div>
        )}
      </div>

      {/* Controls overlay */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
        {/* Progress bar with video boundaries and segments */}
        <div
          ref={progressRef}
          onClick={handleProgressClick}
          className="relative h-1.5 bg-white/20 rounded-full cursor-pointer mb-3"
        >
          {/* Video boundary markers */}
          {videoPositions.map((video, index) => (
            index > 0 && (
              <div
                key={`boundary-${video.id}`}
                className="absolute top-0 w-0.5 h-full bg-purple-400/50"
                style={{ left: `${(video.timelineStart / totalDuration) * 100}%` }}
                title={`${video.name} starts here`}
              />
            )
          ))}

          {/* Segment markers - use absolute timeline positions */}
          {segments.map((segment) => {
            const pos = getSegmentTimelinePosition(segment)
            return (
              <div
                key={segment.id}
                className={clsx(
                  'absolute top-0 h-full rounded-full',
                  segment.id === selectedSegmentId
                    ? 'bg-accent-red'
                    : 'bg-accent-red/50'
                )}
                style={{
                  left: `${(pos.start / totalDuration) * 100}%`,
                  width: `${((pos.end - pos.start) / totalDuration) * 100}%`,
                }}
              />
            )
          })}

          {/* Progress */}
          <div
            className="absolute top-0 h-full bg-white rounded-full"
            style={{ width: `${(currentTime / totalDuration) * 100}%` }}
          />

          {/* Playhead */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg"
            style={{ left: `${(currentTime / totalDuration) * 100}%` }}
          />
        </div>

        {/* Controls row */}
        <div className="flex items-center gap-4">
          {/* Play controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => skip(-5)}
              className="p-1.5 rounded hover:bg-white/10 text-white/80 hover:text-white"
            >
              <SkipBack className="w-4 h-4" />
            </button>

            <button
              onClick={togglePlay}
              className="p-2 rounded-full bg-accent-red hover:bg-accent-red-light shadow-glow-red-sm"
            >
              {isPlaying ? (
                <Pause className="w-5 h-5 text-white" />
              ) : (
                <Play className="w-5 h-5 text-white ml-0.5" />
              )}
            </button>

            <button
              onClick={() => skip(5)}
              className="p-1.5 rounded hover:bg-white/10 text-white/80 hover:text-white"
            >
              <SkipForward className="w-4 h-4" />
            </button>
          </div>

          {/* Time display */}
          <div className="font-mono text-sm text-white/80">
            <span>{formatTime(currentTime)}</span>
            <span className="text-white/40 mx-1">/</span>
            <span>{formatTime(totalDuration)}</span>
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Audio Sync Toggles */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setAudioSyncEnabled(!audioSyncEnabled)}
              className={clsx(
                'p-1.5 rounded transition-colors',
                audioSyncEnabled
                  ? 'bg-green-500/30 text-green-400 hover:bg-green-500/40'
                  : 'hover:bg-white/10 text-white/50 hover:text-white/80'
              )}
              title={audioSyncEnabled ? 'Disable TTS audio sync' : 'Enable TTS audio sync'}
            >
              <Headphones className="w-4 h-4" />
            </button>
            {bgmTracks.length > 0 && (
              <button
                onClick={() => setBgmSyncEnabled(!bgmSyncEnabled)}
                className={clsx(
                  'p-1.5 rounded transition-colors',
                  bgmSyncEnabled
                    ? 'bg-teal-500/30 text-teal-400 hover:bg-teal-500/40'
                    : 'hover:bg-white/10 text-white/50 hover:text-white/80'
                )}
                title={bgmSyncEnabled ? 'Disable BGM audio sync' : 'Enable BGM audio sync'}
              >
                <Music className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Volume */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggleMute}
              className="p-1.5 rounded hover:bg-white/10 text-white/80 hover:text-white"
            >
              {isMuted ? (
                <VolumeX className="w-4 h-4" />
              ) : (
                <Volume2 className="w-4 h-4" />
              )}
            </button>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={volume}
              onChange={handleVolumeChange}
              className="w-20 accent-accent-red"
            />
          </div>

          {/* Fullscreen */}
          <button
            onClick={toggleFullscreen}
            className="p-1.5 rounded hover:bg-white/10 text-white/80 hover:text-white"
          >
            <Maximize className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Play button overlay when paused */}
      {!isPlaying && (
        <button
          onClick={togglePlay}
          className="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:bg-black/20 transition-colors"
        >
          <div className="w-16 h-16 rounded-full bg-accent-red/90 flex items-center justify-center shadow-glow-red">
            <Play className="w-8 h-8 text-white ml-1" />
          </div>
        </button>
      )}
    </div>
  )
}
