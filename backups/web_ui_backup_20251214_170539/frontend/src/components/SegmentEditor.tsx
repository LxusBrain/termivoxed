import { useState, useEffect, useRef } from 'react'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Save,
  Trash2,
  Clock,
  AlertTriangle,
  Check,
  PlayCircle,
  Loader2,
  Gauge,
  Music,
  StopCircle,
  ChevronDown,
  ChevronUp,
  Type,
  Search,
  ArrowRight,
} from 'lucide-react'
import { segmentsApi, ttsApi, exportApi, fontsApi } from '../api/client'
import { useAppStore } from '../stores/appStore'
import type { Segment, Voice } from '../types'
import toast from 'react-hot-toast'
import clsx from 'clsx'

interface SegmentEditorProps {
  projectName: string
  segment: Segment | null
  onClose: () => void
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const ms = Math.floor((seconds % 1) * 10)
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`
}

// Convert BGR ASS color format (&HAABBGGRR) to hex (#RRGGBB)
function bgrToHex(bgr: string): string {
  // Handle format like &H00FFFFFF or &H80000000
  const match = bgr.match(/&H([0-9A-Fa-f]{2})?([0-9A-Fa-f]{6})/)
  if (!match) return '#FFFFFF'
  const color = match[2]
  const r = color.substring(4, 6)
  const g = color.substring(2, 4)
  const b = color.substring(0, 2)
  return `#${r}${g}${b}`.toUpperCase()
}

// Convert hex (#RRGGBB) to BGR ASS format (&H00BBGGRR)
function hexToBgr(hex: string, alpha = '00'): string {
  const clean = hex.replace('#', '')
  const r = clean.substring(0, 2)
  const g = clean.substring(2, 4)
  const b = clean.substring(4, 6)
  return `&H${alpha}${b}${g}${r}`.toUpperCase()
}

// Fallback fonts if API is not available
const FALLBACK_FONTS = [
  'Roboto',
  'Open Sans',
  'Lato',
  'Montserrat',
  'Poppins',
  'Oswald',
  'Source Sans Pro',
  'Raleway',
  'Ubuntu',
  'Nunito',
  'Merriweather',
  'PT Sans',
  'Noto Sans',
  'Bebas Neue',
  'Anton',
  'Playfair Display',
]

interface GoogleFont {
  family: string
  category: string
  variants: string[]
  subsets: string[]
}

export default function SegmentEditor({ projectName, segment, onClose }: SegmentEditorProps) {
  const queryClient = useQueryClient()
  const { updateSegment, removeSegment, setCurrentTime } = useAppStore()

  // Form state
  const [name, setName] = useState('')
  const [startTime, setStartTime] = useState(0)
  const [endTime, setEndTime] = useState(0)
  const [text, setText] = useState('')
  const [language, setLanguage] = useState('en')
  const [voiceId, setVoiceId] = useState('')
  const [isPreviewPlaying, setIsPreviewPlaying] = useState(false)

  // Voice parameters
  const [rate, setRate] = useState('+0%')
  const [volume, setVolume] = useState('+0%')
  const [pitch, setPitch] = useState('+0Hz')
  const [showVoiceParams, setShowVoiceParams] = useState(false)

  // Cross-video extension
  const [extendsToNextVideo, setExtendsToNextVideo] = useState(false)

  // Subtitle settings
  const [showSubtitleSettings, setShowSubtitleSettings] = useState(false)
  const [subtitleEnabled, setSubtitleEnabled] = useState(true)
  const [subtitleFont, setSubtitleFont] = useState('Roboto')
  const [subtitleSize, setSubtitleSize] = useState(20)
  const [subtitleColor, setSubtitleColor] = useState('#FFFFFF')
  const [subtitlePosition, setSubtitlePosition] = useState(30)
  const [subtitleBorderEnabled, setSubtitleBorderEnabled] = useState(true)
  const [subtitleBorderStyle, setSubtitleBorderStyle] = useState(1)
  const [subtitleOutlineWidth, setSubtitleOutlineWidth] = useState(0.5)
  const [subtitleOutlineColor, setSubtitleOutlineColor] = useState('#000000')
  const [subtitleShadow, setSubtitleShadow] = useState(0)
  const [subtitleShadowColor, setSubtitleShadowColor] = useState('#000000')

  // Google Fonts search
  const [fontSearch, setFontSearch] = useState('')
  const [showFontSearch, setShowFontSearch] = useState(false)
  const [fontCategory, setFontCategory] = useState<string>('')

  // Fetch Google Fonts
  const { data: googleFontsData } = useQuery({
    queryKey: ['google-fonts', fontSearch, fontCategory],
    queryFn: () => fontsApi.getGoogleFonts(),
    staleTime: 1000 * 60 * 60, // Cache for 1 hour
  })

  const googleFonts: GoogleFont[] = googleFontsData?.data?.fonts || []

  // Audio preview
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isSegmentAudioPlaying, setIsSegmentAudioPlaying] = useState(false)

  // Sync form with segment
  useEffect(() => {
    if (segment) {
      setName(segment.name)
      setStartTime(segment.start_time)
      setEndTime(segment.end_time)
      setText(segment.text)
      setLanguage(segment.language)
      setVoiceId(segment.voice_id)
      setRate(segment.rate || '+0%')
      setVolume(segment.volume || '+0%')
      setPitch(segment.pitch || '+0Hz')
      // Cross-video extension
      setExtendsToNextVideo(segment.extends_to_next_video ?? false)
      // Subtitle settings
      setSubtitleEnabled(segment.subtitle_enabled ?? true)
      setSubtitleFont(segment.subtitle_font || 'Roboto')
      setSubtitleSize(segment.subtitle_size || 20)
      setSubtitleColor(bgrToHex(segment.subtitle_color || '&H00FFFFFF'))
      setSubtitlePosition(segment.subtitle_position || 30)
      setSubtitleBorderEnabled(segment.subtitle_border_enabled ?? true)
      setSubtitleBorderStyle(segment.subtitle_border_style || 1)
      setSubtitleOutlineWidth(segment.subtitle_outline_width || 0.5)
      setSubtitleOutlineColor(bgrToHex(segment.subtitle_outline_color || '&H00000000'))
      setSubtitleShadow(segment.subtitle_shadow || 0)
      setSubtitleShadowColor(bgrToHex(segment.subtitle_shadow_color || '&H80000000'))
    }
  }, [segment])

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  // Dynamically load Google Font for preview
  useEffect(() => {
    if (!subtitleFont) return

    // Check if font is already loaded
    const existingLink = document.querySelector(`link[data-font="${subtitleFont}"]`)
    if (existingLink) return

    // Create a link element to load the font from Google Fonts
    const link = document.createElement('link')
    link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(subtitleFont.replace(/ /g, '+'))}:wght@400;700&display=swap`
    link.rel = 'stylesheet'
    link.setAttribute('data-font', subtitleFont)
    document.head.appendChild(link)

    // Cleanup is not needed as fonts should persist for the session
  }, [subtitleFont])

  // Fetch voices
  const { data: voicesData } = useQuery({
    queryKey: ['voices', language],
    queryFn: () => ttsApi.getVoices(language),
    enabled: !!language,
  })

  // Estimate duration
  const { data: durationData } = useQuery({
    queryKey: ['duration-estimate', text, language],
    queryFn: () => ttsApi.estimateDuration(text, language),
    enabled: text.length > 0,
  })

  const voices: Voice[] = voicesData?.data?.voices || []
  const estimatedDuration = durationData?.data?.estimated_duration || 0
  const segmentDuration = endTime - startTime
  const audioFits = estimatedDuration <= segmentDuration * 1.1
  const overflow = estimatedDuration - segmentDuration

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      segmentsApi.update(projectName, segment!.id, data),
    onSuccess: (response) => {
      updateSegment(segment!.id, response.data)
      toast.success('Segment updated')
      queryClient.invalidateQueries({ queryKey: ['segments', projectName] })
    },
    onError: () => {
      toast.error('Failed to update segment')
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: () => segmentsApi.delete(projectName, segment!.id),
    onSuccess: () => {
      removeSegment(segment!.id)
      toast.success('Segment deleted')
      queryClient.invalidateQueries({ queryKey: ['segments', projectName] })
      onClose()
    },
    onError: () => {
      toast.error('Failed to delete segment')
    },
  })

  // Preview mutation (voice preview with short text and current parameters)
  const previewMutation = useMutation({
    mutationFn: () =>
      ttsApi.preview(voiceId, text.slice(0, 100), rate, volume, pitch),
    onSuccess: (response) => {
      if (audioRef.current) {
        audioRef.current.pause()
      }
      const audio = new Audio(response.data.audio_url)
      audioRef.current = audio
      audio.play()
      setIsPreviewPlaying(true)
      audio.onended = () => setIsPreviewPlaying(false)
    },
    onError: () => {
      toast.error('Failed to generate preview')
    },
  })

  // Generate full segment audio mutation with current form values
  const segmentAudioMutation = useMutation({
    mutationFn: () =>
      exportApi.previewSegmentAudio({
        project_name: projectName,
        text: text,
        voice_id: voiceId,
        language: language,
        rate: rate,
        volume: volume,
        pitch: pitch,
      }),
    onSuccess: (response) => {
      if (audioRef.current) {
        audioRef.current.pause()
      }
      const audio = new Audio(response.data.audio_url)
      audioRef.current = audio
      audio.play()
      setIsSegmentAudioPlaying(true)
      audio.onended = () => setIsSegmentAudioPlaying(false)
      toast.success(`Audio generated (${response.data.duration.toFixed(1)}s)`)
    },
    onError: () => {
      toast.error('Failed to generate segment audio')
    },
  })

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    setIsPreviewPlaying(false)
    setIsSegmentAudioPlaying(false)
  }

  const handleSave = () => {
    if (!segment) return
    updateMutation.mutate({
      name,
      start_time: startTime,
      end_time: endTime,
      text,
      language,
      voice_id: voiceId,
      rate,
      volume,
      pitch,
      // Cross-video extension
      extends_to_next_video: extendsToNextVideo,
      // Subtitle settings
      subtitle_enabled: subtitleEnabled,
      subtitle_font: subtitleFont,
      subtitle_size: subtitleSize,
      subtitle_color: hexToBgr(subtitleColor),
      subtitle_position: subtitlePosition,
      subtitle_border_enabled: subtitleBorderEnabled,
      subtitle_border_style: subtitleBorderStyle,
      subtitle_outline_width: subtitleOutlineWidth,
      subtitle_outline_color: hexToBgr(subtitleOutlineColor),
      subtitle_shadow: subtitleShadow,
      subtitle_shadow_color: hexToBgr(subtitleShadowColor, '80'),
    })
  }

  // Filter fonts based on search and category
  const filteredFonts = (() => {
    let fonts = googleFonts.length > 0 ? googleFonts : FALLBACK_FONTS.map((f) => ({ family: f, category: 'sans-serif', variants: [], subsets: [] }))

    // Apply category filter
    if (fontCategory) {
      fonts = fonts.filter((f) => f.category === fontCategory)
    }

    // Apply search filter
    if (fontSearch) {
      fonts = fonts.filter((f) =>
        f.family.toLowerCase().includes(fontSearch.toLowerCase())
      )
    }

    return fonts
  })()

  const handleDelete = () => {
    if (!segment) return
    if (confirm('Are you sure you want to delete this segment?')) {
      deleteMutation.mutate()
    }
  }

  if (!segment) {
    return (
      <div className="console-card p-6 text-center text-text-muted">
        <p>Select a segment to edit</p>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="console-card overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-terminal-border bg-terminal-bg/50">
        <h3 className="font-medium">Edit Segment</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="p-2 rounded hover:bg-accent-red/20 text-text-muted hover:text-accent-red"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4 max-h-[calc(100vh-300px)] overflow-y-auto">
        {/* Name */}
        <div>
          <label className="section-header">Segment Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input-base w-full"
          />
        </div>

        {/* Timing */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="section-header">Start Time</label>
            <div className="relative">
              <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                type="number"
                step="0.1"
                min="0"
                value={startTime}
                onChange={(e) => setStartTime(parseFloat(e.target.value))}
                className="input-base w-full pl-9 font-mono"
              />
            </div>
          </div>
          <div>
            <label className="section-header">End Time</label>
            <div className="relative">
              <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                type="number"
                step="0.1"
                min="0"
                value={endTime}
                onChange={(e) => setEndTime(parseFloat(e.target.value))}
                className="input-base w-full pl-9 font-mono"
              />
            </div>
          </div>
        </div>

        {/* Duration info */}
        <div
          className={clsx(
            'p-3 rounded-md border text-sm',
            audioFits
              ? 'bg-green-500/10 border-green-500/30 text-green-400'
              : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
          )}
        >
          <div className="flex items-center gap-2">
            {audioFits ? (
              <Check className="w-4 h-4" />
            ) : (
              <AlertTriangle className="w-4 h-4" />
            )}
            <span>
              Segment: {formatTime(segmentDuration)}s | Est. Audio: {formatTime(estimatedDuration)}s
              {!audioFits && ` (+${overflow.toFixed(1)}s overflow)`}
            </span>
          </div>
        </div>

        {/* Cross-video extension toggle */}
        <div className="p-3 rounded-md border border-terminal-border bg-terminal-bg/30">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={extendsToNextVideo}
              onChange={(e) => setExtendsToNextVideo(e.target.checked)}
              className="w-4 h-4 accent-purple-500 rounded"
            />
            <div className="flex items-center gap-2">
              <ArrowRight className="w-4 h-4 text-purple-400" />
              <span className="text-sm">Extend to next video</span>
            </div>
          </label>
          {extendsToNextVideo && (
            <div className="mt-2 ml-7 text-xs text-purple-400">
              {segment.overflow_duration ? (
                <span>
                  {segment.overflow_duration.toFixed(1)}s will continue into{' '}
                  {segment.next_video_name || 'next video'}
                </span>
              ) : (
                <span>
                  Segment can extend past this video&apos;s end into the next video in sequence.
                  Set end time beyond video duration to enable.
                </span>
              )}
            </div>
          )}
        </div>

        {/* Text */}
        <div>
          <label className="section-header">
            Script Text
            <span className="text-text-muted ml-2">({text.split(/\s+/).filter(Boolean).length} words)</span>
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            className="input-base w-full resize-none"
            placeholder="Enter the narration text for this segment..."
          />
        </div>

        {/* Language */}
        <div>
          <label className="section-header">Language</label>
          <select
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value)
              setVoiceId('') // Reset voice when language changes
            }}
            className="input-base w-full"
          >
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="it">Italian</option>
            <option value="pt">Portuguese</option>
            <option value="hi">Hindi</option>
            <option value="zh">Chinese</option>
            <option value="ja">Japanese</option>
            <option value="ko">Korean</option>
          </select>
        </div>

        {/* Voice */}
        <div>
          <label className="section-header">Voice</label>
          <div className="flex gap-2">
            <select
              value={voiceId}
              onChange={(e) => setVoiceId(e.target.value)}
              className="input-base flex-1"
            >
              <option value="">Select a voice...</option>
              {voices.map((voice) => (
                <option key={voice.short_name} value={voice.short_name}>
                  {voice.name} ({voice.gender})
                </option>
              ))}
            </select>
            <button
              onClick={() => previewMutation.mutate()}
              disabled={!voiceId || !text || previewMutation.isPending || isPreviewPlaying}
              className="btn-secondary px-3"
              title="Preview voice with sample text"
            >
              {previewMutation.isPending || isPreviewPlaying ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <PlayCircle className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Voice Parameters (collapsible) */}
        <div className="border border-terminal-border rounded-md overflow-hidden">
          <button
            onClick={() => setShowVoiceParams(!showVoiceParams)}
            className="w-full p-3 flex items-center justify-between bg-terminal-bg/50 hover:bg-terminal-elevated transition-colors"
          >
            <span className="text-sm flex items-center gap-2">
              <Gauge className="w-4 h-4 text-accent-red" />
              Voice Parameters
            </span>
            {showVoiceParams ? (
              <ChevronUp className="w-4 h-4 text-text-muted" />
            ) : (
              <ChevronDown className="w-4 h-4 text-text-muted" />
            )}
          </button>

          {showVoiceParams && (
            <div className="p-3 space-y-3 border-t border-terminal-border">
              {/* Rate */}
              <div>
                <label className="text-xs text-text-muted mb-1 block">
                  Rate: {rate}
                </label>
                <input
                  type="range"
                  min="-50"
                  max="100"
                  value={parseInt(rate) || 0}
                  onChange={(e) => {
                    const val = parseInt(e.target.value)
                    setRate(val >= 0 ? `+${val}%` : `${val}%`)
                  }}
                  className="w-full accent-accent-red"
                />
                <div className="flex justify-between text-[10px] text-text-muted">
                  <span>Slow (-50%)</span>
                  <span>Normal</span>
                  <span>Fast (+100%)</span>
                </div>
              </div>

              {/* Volume */}
              <div>
                <label className="text-xs text-text-muted mb-1 block">
                  Volume: {volume}
                </label>
                <input
                  type="range"
                  min="-50"
                  max="50"
                  value={parseInt(volume) || 0}
                  onChange={(e) => {
                    const val = parseInt(e.target.value)
                    setVolume(val >= 0 ? `+${val}%` : `${val}%`)
                  }}
                  className="w-full accent-accent-red"
                />
                <div className="flex justify-between text-[10px] text-text-muted">
                  <span>Quiet (-50%)</span>
                  <span>Normal</span>
                  <span>Loud (+50%)</span>
                </div>
              </div>

              {/* Pitch */}
              <div>
                <label className="text-xs text-text-muted mb-1 block">
                  Pitch: {pitch}
                </label>
                <input
                  type="range"
                  min="-50"
                  max="50"
                  value={parseInt(pitch) || 0}
                  onChange={(e) => {
                    const val = parseInt(e.target.value)
                    setPitch(val >= 0 ? `+${val}Hz` : `${val}Hz`)
                  }}
                  className="w-full accent-accent-red"
                />
                <div className="flex justify-between text-[10px] text-text-muted">
                  <span>Lower (-50Hz)</span>
                  <span>Normal</span>
                  <span>Higher (+50Hz)</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Generate & Preview Audio */}
        <div className="p-3 rounded-md border border-terminal-border bg-terminal-bg/30">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm flex items-center gap-2">
              <Music className="w-4 h-4 text-accent-red" />
              Segment Audio
            </span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => segmentAudioMutation.mutate()}
              disabled={!text || !voiceId || segmentAudioMutation.isPending}
              className="btn-secondary flex-1 flex items-center justify-center gap-2 text-sm"
            >
              {segmentAudioMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <PlayCircle className="w-4 h-4" />
                  Generate & Play
                </>
              )}
            </button>
            {(isPreviewPlaying || isSegmentAudioPlaying) && (
              <button
                onClick={stopAudio}
                className="btn-secondary px-3"
                title="Stop playback"
              >
                <StopCircle className="w-4 h-4" />
              </button>
            )}
          </div>
          <p className="text-[10px] text-text-muted mt-2">
            Generate and review the full TTS audio before export
          </p>
        </div>

        {/* Subtitle Settings (collapsible) */}
        <div className="border border-terminal-border rounded-md overflow-hidden">
          <button
            onClick={() => setShowSubtitleSettings(!showSubtitleSettings)}
            className="w-full p-3 flex items-center justify-between bg-terminal-bg/50 hover:bg-terminal-elevated transition-colors"
          >
            <span className="text-sm flex items-center gap-2">
              <Type className="w-4 h-4 text-accent-red" />
              Subtitle Settings
              {!subtitleEnabled && (
                <span className="text-[10px] text-text-muted bg-terminal-elevated px-1.5 py-0.5 rounded">
                  Disabled
                </span>
              )}
            </span>
            {showSubtitleSettings ? (
              <ChevronUp className="w-4 h-4 text-text-muted" />
            ) : (
              <ChevronDown className="w-4 h-4 text-text-muted" />
            )}
          </button>

          {showSubtitleSettings && (
            <div className="p-3 space-y-4 border-t border-terminal-border">
              {/* Enable/Disable */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={subtitleEnabled}
                  onChange={(e) => setSubtitleEnabled(e.target.checked)}
                  className="w-4 h-4 accent-accent-red"
                />
                <span className="text-sm">Enable subtitles for this segment</span>
              </label>

              {subtitleEnabled && (
                <>
                  {/* Font Selection with Search */}
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">
                      Font
                      {googleFonts.length > 0 && (
                        <span className="text-accent-red ml-1">({googleFonts.length} fonts available)</span>
                      )}
                    </label>
                    <div className="relative">
                      <button
                        onClick={() => setShowFontSearch(!showFontSearch)}
                        className="input-base w-full text-left flex items-center justify-between"
                      >
                        <span>{subtitleFont}</span>
                        <Search className="w-4 h-4 text-text-muted" />
                      </button>

                      {showFontSearch && (
                        <div className="absolute z-10 mt-1 w-full bg-terminal-surface border border-terminal-border rounded-md shadow-lg max-h-80 overflow-hidden">
                          {/* Search input */}
                          <div className="p-2 border-b border-terminal-border space-y-2">
                            <input
                              type="text"
                              value={fontSearch}
                              onChange={(e) => setFontSearch(e.target.value)}
                              placeholder="Search fonts..."
                              className="input-base w-full text-sm"
                              autoFocus
                            />
                            {/* Category filter */}
                            <div className="flex gap-1 flex-wrap">
                              <button
                                onClick={() => setFontCategory('')}
                                className={clsx(
                                  'text-[10px] px-1.5 py-0.5 rounded',
                                  !fontCategory
                                    ? 'bg-accent-red text-white'
                                    : 'bg-terminal-elevated text-text-muted hover:text-text-primary'
                                )}
                              >
                                All
                              </button>
                              {['sans-serif', 'serif', 'display', 'handwriting', 'monospace'].map((cat) => (
                                <button
                                  key={cat}
                                  onClick={() => setFontCategory(cat === fontCategory ? '' : cat)}
                                  className={clsx(
                                    'text-[10px] px-1.5 py-0.5 rounded capitalize',
                                    fontCategory === cat
                                      ? 'bg-accent-red text-white'
                                      : 'bg-terminal-elevated text-text-muted hover:text-text-primary'
                                  )}
                                >
                                  {cat}
                                </button>
                              ))}
                            </div>
                          </div>
                          {/* Font list */}
                          <div className="max-h-52 overflow-y-auto">
                            {filteredFonts.slice(0, 100).map((font) => (
                              <button
                                key={font.family}
                                onClick={() => {
                                  setSubtitleFont(font.family)
                                  setShowFontSearch(false)
                                  setFontSearch('')
                                }}
                                className={clsx(
                                  'w-full px-3 py-2 text-left text-sm hover:bg-terminal-elevated transition-colors flex items-center justify-between',
                                  font.family === subtitleFont && 'bg-accent-red/20 text-accent-red'
                                )}
                              >
                                <span>{font.family}</span>
                                <span className="text-[10px] text-text-muted capitalize">{font.category}</span>
                              </button>
                            ))}
                            {filteredFonts.length === 0 && (
                              <div className="px-3 py-2 text-sm text-text-muted">
                                No fonts found. You can type a custom font name.
                              </div>
                            )}
                            {filteredFonts.length > 100 && (
                              <div className="px-3 py-2 text-xs text-text-muted text-center">
                                Showing first 100 of {filteredFonts.length} fonts. Use search to narrow down.
                              </div>
                            )}
                          </div>
                          {fontSearch && !filteredFonts.find((f) => f.family.toLowerCase() === fontSearch.toLowerCase()) && (
                            <button
                              onClick={() => {
                                setSubtitleFont(fontSearch)
                                setShowFontSearch(false)
                                setFontSearch('')
                              }}
                              className="w-full px-3 py-2 text-left text-sm border-t border-terminal-border hover:bg-terminal-elevated transition-colors text-accent-red"
                            >
                              Use custom font: "{fontSearch}"
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                    <p className="text-[10px] text-text-muted mt-1">
                      Google Fonts will be auto-downloaded during export. Font must be installed for preview.
                    </p>
                  </div>

                  {/* Size & Position */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">
                        Size: {subtitleSize}px
                      </label>
                      <input
                        type="range"
                        min="10"
                        max="60"
                        value={subtitleSize}
                        onChange={(e) => setSubtitleSize(parseInt(e.target.value))}
                        className="w-full accent-accent-red"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">
                        Position: {subtitlePosition}px
                      </label>
                      <input
                        type="range"
                        min="10"
                        max="100"
                        value={subtitlePosition}
                        onChange={(e) => setSubtitlePosition(parseInt(e.target.value))}
                        className="w-full accent-accent-red"
                      />
                    </div>
                  </div>

                  {/* Text Color */}
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Text Color</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={subtitleColor}
                        onChange={(e) => setSubtitleColor(e.target.value)}
                        className="w-10 h-8 rounded border border-terminal-border cursor-pointer"
                      />
                      <input
                        type="text"
                        value={subtitleColor}
                        onChange={(e) => setSubtitleColor(e.target.value)}
                        className="input-base flex-1 font-mono text-sm"
                      />
                    </div>
                  </div>

                  {/* Border/Outline Settings */}
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={subtitleBorderEnabled}
                        onChange={(e) => setSubtitleBorderEnabled(e.target.checked)}
                        className="w-4 h-4 accent-accent-red"
                      />
                      <span className="text-xs text-text-muted">Enable border/outline</span>
                    </label>

                    {subtitleBorderEnabled && (
                      <div className="pl-6 space-y-3">
                        <div>
                          <label className="text-xs text-text-muted mb-1 block">Border Style</label>
                          <select
                            value={subtitleBorderStyle}
                            onChange={(e) => setSubtitleBorderStyle(parseInt(e.target.value))}
                            className="input-base w-full text-sm"
                          >
                            <option value={1}>Outline + Drop Shadow</option>
                            <option value={3}>Opaque Box</option>
                          </select>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs text-text-muted mb-1 block">
                              Outline Width: {subtitleOutlineWidth}
                            </label>
                            <input
                              type="range"
                              min="0"
                              max="5"
                              step="0.5"
                              value={subtitleOutlineWidth}
                              onChange={(e) => setSubtitleOutlineWidth(parseFloat(e.target.value))}
                              className="w-full accent-accent-red"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-text-muted mb-1 block">Outline Color</label>
                            <input
                              type="color"
                              value={subtitleOutlineColor}
                              onChange={(e) => setSubtitleOutlineColor(e.target.value)}
                              className="w-full h-8 rounded border border-terminal-border cursor-pointer"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Shadow Settings */}
                  <div className="space-y-2">
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">
                        Shadow Distance: {subtitleShadow}px
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="5"
                        step="0.5"
                        value={subtitleShadow}
                        onChange={(e) => setSubtitleShadow(parseFloat(e.target.value))}
                        className="w-full accent-accent-red"
                      />
                    </div>
                    {subtitleShadow > 0 && (
                      <div>
                        <label className="text-xs text-text-muted mb-1 block">Shadow Color</label>
                        <input
                          type="color"
                          value={subtitleShadowColor}
                          onChange={(e) => setSubtitleShadowColor(e.target.value)}
                          className="w-full h-8 rounded border border-terminal-border cursor-pointer"
                        />
                      </div>
                    )}
                  </div>

                  {/* Preview Text */}
                  <div className="p-3 rounded-md bg-black border border-terminal-border">
                    <p className="text-xs text-text-muted mb-2">Preview:</p>
                    <p
                      style={{
                        fontFamily: subtitleFont,
                        fontSize: `${Math.min(subtitleSize, 24)}px`,
                        color: subtitleColor,
                        textShadow: subtitleShadow > 0
                          ? `${subtitleShadow}px ${subtitleShadow}px ${subtitleShadowColor}`
                          : 'none',
                        WebkitTextStroke: subtitleBorderEnabled
                          ? `${subtitleOutlineWidth}px ${subtitleOutlineColor}`
                          : 'none',
                      }}
                      className="text-center"
                    >
                      {text.slice(0, 50) || 'Sample subtitle text'}
                    </p>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-terminal-border bg-terminal-bg/50 flex items-center justify-between">
        <button
          onClick={() => setCurrentTime(startTime)}
          className="btn-ghost text-sm"
        >
          Jump to Start
        </button>
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {updateMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save Changes
        </button>
      </div>
    </motion.div>
  )
}
