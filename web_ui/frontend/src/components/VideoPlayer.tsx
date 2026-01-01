import { useRef, useEffect, useState, useCallback } from 'react'
import { Play, Pause, Volume2, VolumeX, Maximize, SkipBack, SkipForward, Headphones, Music } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import clsx from 'clsx'
import type { BGMTrack } from '../api/client'

interface VideoPlayerProps {
  videoUrl: string
  duration: number
  videoOffset?: number // Offset of this video in combined multi-video timeline (default 0)
  bgmTracks?: BGMTrack[]
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export default function VideoPlayer({ videoUrl, duration, videoOffset = 0, bgmTracks = [] }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const segmentAudioRef = useRef<HTMLAudioElement | null>(null)
  const lastPlayedSegmentRef = useRef<string | null>(null)
  const [isMuted, setIsMuted] = useState(false)
  const [volume, setVolume] = useState(1)
  const [audioSyncEnabled, setAudioSyncEnabled] = useState(true)
  const [bgmSyncEnabled, setBgmSyncEnabled] = useState(true)
  const [playingSegmentAudio, setPlayingSegmentAudio] = useState<string | null>(null)
  const [playingBgmTracks, setPlayingBgmTracks] = useState<Set<string>>(new Set())

  // BGM audio refs - one per track
  const bgmAudioRefs = useRef<Map<string, HTMLAudioElement>>(new Map())
  const bgmFadeIntervals = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())

  // Performance optimization: track last seek time to debounce rapid seeks
  const lastSeekTimeRef = useRef<number>(0)
  const seekDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
  // Uses debouncing to prevent lag when rapidly moving the playhead
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    // Calculate video-relative time from absolute timeline time
    const videoRelativeTime = currentTime - videoOffset

    // Only seek if the time is within this video's range
    if (videoRelativeTime >= 0 && videoRelativeTime <= duration) {
      const timeDiff = Math.abs(video.currentTime - videoRelativeTime)

      // For small differences during normal playback, don't seek
      if (timeDiff < 0.1) return

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
          if (videoRef.current) {
            videoRef.current.currentTime = videoRelativeTime
            lastSeekTimeRef.current = Date.now()
          }
        }, 50)
      } else {
        // Normal seek
        video.currentTime = videoRelativeTime
        lastSeekTimeRef.current = now
      }
    }
  }, [currentTime, videoOffset, duration, isPlaying])

  // Handle external play/pause changes (e.g., clicking segment play button)
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    if (isPlaying && video.paused) {
      video.play().catch(e => console.warn('Failed to play video:', e))
    } else if (!isPlaying && !video.paused) {
      video.pause()
    }
  }, [isPlaying])

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
      // Include audio_offset for trimmed segments
      const audioOffset = currentSegment.audio_offset ?? 0

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
        if (audioUrl.startsWith('/storage/')) {
          // Already a proper URL
          audioUrl = audioUrl
        } else if (audioUrl.includes('/projects/')) {
          // Absolute filesystem path - extract relative portion from 'projects/' onward
          const projectsIndex = audioUrl.indexOf('/projects/')
          audioUrl = `/storage${audioUrl.substring(projectsIndex)}`
        } else if (audioUrl.includes('storage/')) {
          // Legacy format with storage in path
          audioUrl = `/storage/${audioUrl.split('storage/').pop()}`
        } else if (!audioUrl.startsWith('/')) {
          // Relative path - prepend /storage/
          audioUrl = `/storage/${audioUrl}`
        } else {
          // Unknown absolute path - try using as storage relative
          audioUrl = `/storage/projects${audioUrl.substring(audioUrl.lastIndexOf('/'))}`
        }

        console.log('Playing segment audio:', currentSegment.name, audioUrl)

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
  const getTrackVolume = useCallback((track: BGMTrack) => {
    // Return 0 if muted or volume is 0
    if (track.muted || track.volume === 0) return 0
    // Track volume is 0-200 (or 0-100 for legacy), convert to ratio and apply global volume
    // Use nullish coalescing (??) instead of || to properly handle volume = 0
    const trackVolumeRatio = (track.volume ?? 100) / 100
    // Apply a reduction to make BGM sit behind TTS (similar to export -20dB base)
    const bgmReduction = 0.3 // BGM plays at ~30% to not overpower TTS
    return volume * trackVolumeRatio * bgmReduction
  }, [volume])

  // BGM sync effect - manages playback of all BGM tracks
  useEffect(() => {
    if (!bgmSyncEnabled || !isPlaying || bgmTracks.length === 0) {
      stopAllBgmTracks()
      return
    }

    // For each BGM track, determine if it should be playing at currentTime
    bgmTracks.forEach(track => {
      // Get effective end time (0 means until video end)
      const effectiveEndTime = track.end_time > 0 ? track.end_time : duration
      const isInRange = currentTime >= track.start_time && currentTime < effectiveEndTime

      const existingAudio = bgmAudioRefs.current.get(track.id)

      // Check if track should play (in range, not muted, and has volume)
      const shouldPlay = isInRange && !track.muted && track.volume !== 0
      if (shouldPlay) {
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

          audio.play().catch(e => {
            console.warn(`Failed to play BGM track ${track.name}:`, e)
          })

          setPlayingBgmTracks(prev => new Set(prev).add(track.id))

          // Handle track end
          audio.onended = () => {
            if (!track.loop) {
              stopBgmTrack(track.id)
            }
          }
        } else {
          // Track is already playing, update volume
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
        // Track should stop (out of range, muted, or volume is 0)
        stopBgmTrack(track.id)
      }
    })

    // Clean up tracks that no longer exist
    bgmAudioRefs.current.forEach((_, trackId) => {
      if (!bgmTracks.find(t => t.id === trackId)) {
        stopBgmTrack(trackId)
      }
    })
  }, [currentTime, bgmTracks, bgmSyncEnabled, isPlaying, duration, getTrackVolume, stopAllBgmTracks, stopBgmTrack, applyFade])

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

      {/* Current segment and BGM indicators */}
      <div className="absolute top-4 left-4 flex items-center gap-2">
        {currentSegment && (
          <>
            <div className="bg-accent-red/90 text-white text-xs px-2 py-1 rounded font-mono">
              {currentSegment.name}
            </div>
            {playingSegmentAudio === currentSegment.id && (
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
