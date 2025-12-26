import { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import { Play, Pause, Volume2, VolumeX, Maximize, SkipBack, SkipForward, Headphones, Film } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import clsx from 'clsx'
import type { VideoInfo } from '../types'

interface VideoPosition {
  id: string
  name: string
  url: string
  timelineStart: number
  timelineEnd: number
  duration: number
}

interface MultiVideoPlayerProps {
  projectName: string
  videos: VideoInfo[]
  totalDuration: number
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export default function MultiVideoPlayer({ projectName, videos, totalDuration }: MultiVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const segmentAudioRef = useRef<HTMLAudioElement | null>(null)
  const lastPlayedSegmentRef = useRef<string | null>(null)
  const [isMuted, setIsMuted] = useState(false)
  const [volume, setVolume] = useState(1)
  const [audioSyncEnabled, setAudioSyncEnabled] = useState(false)
  const [playingSegmentAudio, setPlayingSegmentAudio] = useState<string | null>(null)
  const [currentVideoId, setCurrentVideoId] = useState<string | null>(null)
  const lastVideoIdRef = useRef<string | null>(null)
  const isSwitchingRef = useRef(false)

  const { currentTime, setCurrentTime, isPlaying, setIsPlaying, segments, selectedSegmentId } =
    useAppStore()

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
          duration: videoDuration
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
          duration: videoDuration
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
  const { activeVideo, isInGap, nextVideo } = useMemo(() => {
    // First, find ALL videos that contain the current time
    const videosAtCurrentTime = videoPositions.filter(
      video => currentTime >= video.timelineStart && currentTime < video.timelineEnd
    )

    if (videosAtCurrentTime.length > 0) {
      // Multiple videos at this time? Pick the one with LOWEST order (topmost track in timeline)
      // In video editing, top track = foreground layer = should be visible
      const videosWithOrder = videosAtCurrentTime.map(vp => {
        const videoInfo = videos.find(v => v.id === vp.id)
        return { ...vp, order: videoInfo?.order ?? 0 }
      })
      // Lower order = top row in timeline = foreground = should show
      videosWithOrder.sort((a, b) => a.order - b.order)
      return { activeVideo: videosWithOrder[0], isInGap: false, nextVideo: null }
    }

    // Not in any video - check if we're in a gap or past the end
    if (videoPositions.length > 0) {
      const lastVideo = videoPositions[videoPositions.length - 1]

      // If past all videos, show the last one (paused at end)
      if (currentTime >= lastVideo.timelineEnd) {
        return { activeVideo: lastVideo, isInGap: false, nextVideo: null }
      }

      // If before the first video, show the first one
      const firstVideo = videoPositions[0]
      if (currentTime < firstVideo.timelineStart) {
        return { activeVideo: firstVideo, isInGap: true, nextVideo: firstVideo }
      }

      // We're in a gap between videos - find the next video
      const next = videoPositions.find(v => v.timelineStart > currentTime)
      // Show the previous video (frozen at its end) while in gap
      const prev = [...videoPositions].reverse().find(v => v.timelineEnd <= currentTime)
      return {
        activeVideo: prev || firstVideo,
        isInGap: true,
        nextVideo: next || null
      }
    }

    // No videos at all
    return { activeVideo: null, isInGap: false, nextVideo: null }
  }, [currentTime, videoPositions, videos])

  // Switch video when active video changes
  useEffect(() => {
    if (!activeVideo || !videoRef.current) return

    if (activeVideo.id !== lastVideoIdRef.current) {
      console.log('[MultiVideoPlayer] Switching to video:', activeVideo.name)
      isSwitchingRef.current = true
      lastVideoIdRef.current = activeVideo.id
      setCurrentVideoId(activeVideo.id)

      const video = videoRef.current
      const wasPlaying = isPlaying

      // Load new video
      video.src = activeVideo.url
      video.load()

      // Seek to correct position and resume if was playing
      video.onloadeddata = () => {
        const targetTime = currentTime - activeVideo.timelineStart
        video.currentTime = Math.max(0, Math.min(targetTime, activeVideo.duration))

        if (wasPlaying) {
          video.play().catch(e => console.warn('Failed to resume playback:', e))
        }

        isSwitchingRef.current = false
      }
    }
  }, [activeVideo, isPlaying, currentTime])

  // Note: We intentionally don't auto-skip gaps during playback
  // The video will naturally end and the handleEnded/handleTimeUpdate will transition to next video
  // This avoids jarring jumps when videos have gaps between them
  void isInGap  // Mark as intentionally unused
  void nextVideo  // Mark as intentionally unused

  // Sync video with store - report absolute timeline time
  useEffect(() => {
    const video = videoRef.current
    if (!video || !activeVideo) return

    const handleTimeUpdate = () => {
      if (isSwitchingRef.current) return

      // Report absolute timeline time (video time + offset)
      const absoluteTime = video.currentTime + activeVideo.timelineStart
      setCurrentTime(absoluteTime)

      // Check if we've reached the end of this video and should switch to next
      if (video.currentTime >= activeVideo.duration - 0.1) {
        const nextVideo = videoPositions.find(v => v.timelineStart >= activeVideo.timelineEnd)
        if (nextVideo && isPlaying) {
          // Move to next video
          setCurrentTime(nextVideo.timelineStart)
        }
      }
    }

    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => {
      if (!isSwitchingRef.current) setIsPlaying(false)
    }
    const handleEnded = () => {
      // Check if there's a next video
      const nextVideo = videoPositions.find(v => v.timelineStart >= activeVideo.timelineEnd)
      if (nextVideo) {
        setCurrentTime(nextVideo.timelineStart)
      } else {
        setIsPlaying(false)
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
  }, [activeVideo, videoPositions, isPlaying, setCurrentTime, setIsPlaying])

  // Handle external time changes (e.g., clicking on timeline or dragging playhead)
  useEffect(() => {
    const video = videoRef.current
    if (!video || !activeVideo || isSwitchingRef.current) return

    const targetRelativeTime = currentTime - activeVideo.timelineStart

    // Only seek if within this video's range and significantly different
    if (targetRelativeTime >= 0 && targetRelativeTime <= activeVideo.duration) {
      if (Math.abs(video.currentTime - targetRelativeTime) > 0.2) {
        video.currentTime = targetRelativeTime
      }
    }
  }, [currentTime, activeVideo])

  // Stop segment audio when video stops
  const stopSegmentAudio = useCallback(() => {
    if (segmentAudioRef.current) {
      segmentAudioRef.current.pause()
      segmentAudioRef.current = null
    }
    setPlayingSegmentAudio(null)
  }, [])

  // Handle segment audio sync (same as original VideoPlayer)
  useEffect(() => {
    if (!audioSyncEnabled || !isPlaying) {
      stopSegmentAudio()
      lastPlayedSegmentRef.current = null
      return
    }

    const currentSegment = segments.find(
      (s) => currentTime >= s.start_time && currentTime <= s.end_time
    )

    if (currentSegment && currentSegment.audio_path) {
      const timeSinceSegmentStart = currentTime - currentSegment.start_time
      const shouldStartAudio =
        lastPlayedSegmentRef.current !== currentSegment.id ||
        (timeSinceSegmentStart < 0.5 && playingSegmentAudio !== currentSegment.id)

      if (shouldStartAudio) {
        stopSegmentAudio()

        let audioUrl = currentSegment.audio_path
        if (audioUrl.includes('storage/')) {
          audioUrl = `/storage/${audioUrl.split('storage/').pop()}`
        } else if (!audioUrl.startsWith('/')) {
          audioUrl = `/storage/${audioUrl}`
        }

        const audio = new Audio(audioUrl)
        audio.volume = volume

        if (timeSinceSegmentStart > 0.3) {
          audio.currentTime = timeSinceSegmentStart
        }

        segmentAudioRef.current = audio
        lastPlayedSegmentRef.current = currentSegment.id
        setPlayingSegmentAudio(currentSegment.id)

        audio.play().catch((e) => {
          console.warn('Failed to play segment audio:', e)
          setPlayingSegmentAudio(null)
        })

        audio.onended = () => setPlayingSegmentAudio(null)
        audio.onerror = () => setPlayingSegmentAudio(null)
      }
    } else {
      if (playingSegmentAudio) stopSegmentAudio()
      if (!currentSegment) lastPlayedSegmentRef.current = null
    }
  }, [currentTime, segments, audioSyncEnabled, isPlaying, volume, stopSegmentAudio, playingSegmentAudio])

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

  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return

    if (video.paused) {
      video.play()
    } else {
      video.pause()
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

  // Get segment at current time
  const currentSegment = segments.find(
    (s) => currentTime >= s.start_time && currentTime <= s.end_time
  )

  // Initial video load
  useEffect(() => {
    if (videoPositions.length > 0 && !currentVideoId) {
      const firstVideo = videoPositions[0]
      setCurrentVideoId(firstVideo.id)
      lastVideoIdRef.current = firstVideo.id
      if (videoRef.current) {
        videoRef.current.src = firstVideo.url
      }
    }
  }, [videoPositions, currentVideoId])

  if (videos.length === 0) {
    return (
      <div className="relative bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center">
        <div className="text-text-muted">No videos in project</div>
      </div>
    )
  }

  return (
    <div className="relative bg-black rounded-lg overflow-hidden group">
      {/* Video element */}
      <video
        ref={videoRef}
        className="w-full aspect-video"
        onClick={togglePlay}
      />

      {/* Current video indicator */}
      {activeVideo && videos.length > 1 && (
        <div className="absolute top-4 right-4 flex items-center gap-2">
          <div className="bg-purple-500/90 text-white text-xs px-2 py-1 rounded font-mono flex items-center gap-1">
            <Film className="w-3 h-3" />
            {activeVideo.name}
          </div>
        </div>
      )}

      {/* Current segment indicator */}
      {currentSegment && (
        <div className="absolute top-4 left-4 flex items-center gap-2">
          <div className="bg-accent-red/90 text-white text-xs px-2 py-1 rounded font-mono">
            {currentSegment.name}
          </div>
          {playingSegmentAudio === currentSegment.id && (
            <div className="bg-green-500/90 text-white text-xs px-2 py-1 rounded font-mono flex items-center gap-1">
              <Headphones className="w-3 h-3" />
              Playing Audio
            </div>
          )}
        </div>
      )}

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

          {/* Segment markers */}
          {segments.map((segment) => (
            <div
              key={segment.id}
              className={clsx(
                'absolute top-0 h-full rounded-full',
                segment.id === selectedSegmentId
                  ? 'bg-accent-red'
                  : 'bg-accent-red/50'
              )}
              style={{
                left: `${(segment.start_time / totalDuration) * 100}%`,
                width: `${((segment.end_time - segment.start_time) / totalDuration) * 100}%`,
              }}
            />
          ))}

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

          {/* Audio Sync Toggle */}
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
