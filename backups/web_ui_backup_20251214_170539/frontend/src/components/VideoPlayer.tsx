import { useRef, useEffect, useState, useCallback } from 'react'
import { Play, Pause, Volume2, VolumeX, Maximize, SkipBack, SkipForward, Headphones } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import clsx from 'clsx'

interface VideoPlayerProps {
  videoUrl: string
  duration: number
  videoOffset?: number // Offset of this video in combined multi-video timeline (default 0)
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export default function VideoPlayer({ videoUrl, duration, videoOffset = 0 }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const segmentAudioRef = useRef<HTMLAudioElement | null>(null)
  const lastPlayedSegmentRef = useRef<string | null>(null)
  const [isMuted, setIsMuted] = useState(false)
  const [volume, setVolume] = useState(1)
  const [audioSyncEnabled, setAudioSyncEnabled] = useState(false)
  const [playingSegmentAudio, setPlayingSegmentAudio] = useState<string | null>(null)

  const { currentTime, setCurrentTime, isPlaying, setIsPlaying, segments, selectedSegmentId } =
    useAppStore()

  // Convert between absolute timeline time and video-relative time
  // absoluteTime = videoOffset + videoRelativeTime
  // videoRelativeTime = absoluteTime - videoOffset

  // Sync video with store - report absolute time (with offset)
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handleTimeUpdate = () => {
      // Report absolute timeline time (video time + offset)
      setCurrentTime(video.currentTime + videoOffset)
    }

    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)
    const handleEnded = () => setIsPlaying(false)

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
  }, [setCurrentTime, setIsPlaying, videoOffset])

  // Handle external time changes (e.g., clicking on timeline or dragging playhead)
  // Convert absolute timeline time to video-relative time
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    // Calculate video-relative time from absolute timeline time
    const videoRelativeTime = currentTime - videoOffset

    // Only seek if the time is within this video's range
    if (videoRelativeTime >= 0 && videoRelativeTime <= duration) {
      if (Math.abs(video.currentTime - videoRelativeTime) > 0.1) {
        video.currentTime = videoRelativeTime
      }
    }
  }, [currentTime, videoOffset, duration])

  // Stop segment audio when video stops
  const stopSegmentAudio = useCallback(() => {
    if (segmentAudioRef.current) {
      segmentAudioRef.current.pause()
      segmentAudioRef.current = null
    }
    setPlayingSegmentAudio(null)
  }, [])

  // Handle segment audio sync
  useEffect(() => {
    if (!audioSyncEnabled || !isPlaying) {
      stopSegmentAudio()
      lastPlayedSegmentRef.current = null
      return
    }

    // Find current segment
    const currentSegment = segments.find(
      (s) => currentTime >= s.start_time && currentTime <= s.end_time
    )

    // If we're in a segment with audio
    if (currentSegment && currentSegment.audio_path) {
      const timeSinceSegmentStart = currentTime - currentSegment.start_time

      // Start audio if:
      // 1. We haven't played this segment yet
      // 2. OR we're at the start of segment (within 0.5s) and want to sync
      const shouldStartAudio =
        lastPlayedSegmentRef.current !== currentSegment.id ||
        (timeSinceSegmentStart < 0.5 && playingSegmentAudio !== currentSegment.id)

      if (shouldStartAudio) {
        // Stop any existing audio
        stopSegmentAudio()

        // Build audio URL - handle various path formats
        let audioUrl = currentSegment.audio_path
        if (audioUrl.includes('storage/')) {
          audioUrl = `/storage/${audioUrl.split('storage/').pop()}`
        } else if (!audioUrl.startsWith('/')) {
          audioUrl = `/storage/${audioUrl}`
        }

        console.log('Playing segment audio:', currentSegment.name, audioUrl)

        const audio = new Audio(audioUrl)
        audio.volume = volume

        // If we're past the segment start, seek the audio to match
        if (timeSinceSegmentStart > 0.3) {
          audio.currentTime = timeSinceSegmentStart
        }

        segmentAudioRef.current = audio
        lastPlayedSegmentRef.current = currentSegment.id
        setPlayingSegmentAudio(currentSegment.id)

        audio.play().catch((e) => {
          console.warn('Failed to play segment audio:', e, audioUrl)
          setPlayingSegmentAudio(null)
        })

        audio.onended = () => {
          setPlayingSegmentAudio(null)
        }

        audio.onerror = () => {
          console.warn('Audio error for:', audioUrl)
          setPlayingSegmentAudio(null)
        }
      }
    } else {
      // Left the segment or no segment - stop audio
      if (playingSegmentAudio) {
        stopSegmentAudio()
      }
      if (!currentSegment) {
        lastPlayedSegmentRef.current = null
      }
    }
  }, [currentTime, segments, audioSyncEnabled, isPlaying, volume, stopSegmentAudio, playingSegmentAudio])

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      stopSegmentAudio()
    }
  }, [stopSegmentAudio])

  // Sync audio volume with video volume
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
    const video = videoRef.current
    const progress = progressRef.current
    if (!video || !progress) return

    const rect = progress.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width
    video.currentTime = pos * duration
  }

  const skip = (seconds: number) => {
    const video = videoRef.current
    if (!video) return
    video.currentTime = Math.max(0, Math.min(duration, video.currentTime + seconds))
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

  return (
    <div className="relative bg-black rounded-lg overflow-hidden group">
      {/* Video element */}
      <video
        ref={videoRef}
        src={videoUrl}
        className="w-full aspect-video"
        onClick={togglePlay}
      />

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
        {/* Progress bar with segments */}
        <div
          ref={progressRef}
          onClick={handleProgressClick}
          className="relative h-1.5 bg-white/20 rounded-full cursor-pointer mb-3"
        >
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
                left: `${(segment.start_time / duration) * 100}%`,
                width: `${((segment.end_time - segment.start_time) / duration) * 100}%`,
              }}
            />
          ))}

          {/* Progress */}
          <div
            className="absolute top-0 h-full bg-white rounded-full"
            style={{ width: `${(currentTime / duration) * 100}%` }}
          />

          {/* Playhead */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg"
            style={{ left: `${(currentTime / duration) * 100}%` }}
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
            <span>{formatTime(duration)}</span>
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
