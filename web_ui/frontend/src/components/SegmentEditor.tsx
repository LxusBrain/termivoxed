import { useState, useEffect, useRef, useCallback } from 'react'
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
  Sparkles,
  Settings,
  Heart,
  Mic,
} from 'lucide-react'
import { segmentsApi, ttsApi, exportApi, fontsApi, llmApi, VoiceSample } from '../api/client'
import { useAppStore } from '../stores/appStore'
import { useAuthStore } from '../stores/authStore'
import { useFavoritesStore } from '../stores/favoritesStore'
import { useConsentStore, useTTSConsentGate } from '../stores/consentStore'
import { TTSWarningBanner, TTSConsentRequired } from './TTSConsentModal'
import VoiceCloning from './shared/VoiceCloning'

import { LANGUAGES, getSampleText } from '../constants/languages'
import { AI_PROVIDER_CONFIG, AIProviderType } from '../constants/aiProviders'
import { bgrToHex, hexToBgr } from '../utils/colors'
import { formatVoiceName, formatTime } from '../utils/voice'

import type { Segment, Voice } from '../types'
import toast from 'react-hot-toast'
import clsx from 'clsx'

// Providers that process locally and don't require consent
const LOCAL_PROVIDERS = ['coqui', 'piper']

interface SegmentEditorProps {
  projectName: string
  segment: Segment | null
  onClose: () => void
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
  const { updateSegment, removeSegment, setCurrentTime, segments: allSegments } = useAppStore()
  const { favoriteVoices, toggleFavoriteVoice, isFavoriteVoice, fetchFavorites, isInitialized: favoritesInitialized } = useFavoritesStore()
  const { checkConsent: checkTTSConsent, showConsentModal } = useTTSConsentGate()
  const { hasTTSConsent } = useConsentStore()

  // Fetch favorites on mount
  useEffect(() => {
    if (!favoritesInitialized) {
      fetchFavorites()
    }
  }, [favoritesInitialized, fetchFavorites])

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

  // Voice cloning (Coqui TTS only)
  const [selectedVoiceSample, setSelectedVoiceSample] = useState<VoiceSample | null>(null)

  // Per-segment TTS provider (null = use global, string = use this provider)
  const [segmentProvider, setSegmentProvider] = useState<string | null>(null)
  const [useGlobalProvider, setUseGlobalProvider] = useState(false)

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

  // AI Script Generation
  const [showAIGenerate, setShowAIGenerate] = useState(false)
  const [aiDescription, setAiDescription] = useState('')
  const [aiProvider, setAiProvider] = useState<AIProviderType>('ollama')
  const [aiModel, setAiModel] = useState('')
  const [aiApiKey, setAiApiKey] = useState('')
  const [customEndpoint, setCustomEndpoint] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  // Azure OpenAI specific
  const [azureEndpoint, setAzureEndpoint] = useState('')
  const [azureDeployment, setAzureDeployment] = useState('')
  // AWS Bedrock specific
  const [awsRegion, setAwsRegion] = useState('us-east-1')

  // Fetch Google Fonts
  const { data: googleFontsData } = useQuery({
    queryKey: ['google-fonts', fontSearch, fontCategory],
    queryFn: () => fontsApi.getGoogleFonts(),
    staleTime: 1000 * 60 * 60, // Cache for 1 hour
  })

  const googleFonts: GoogleFont[] = googleFontsData?.data?.fonts || []

  // Fetch Local System Fonts
  const { data: localFontsData } = useQuery({
    queryKey: ['local-fonts'],
    queryFn: () => fontsApi.getLocalFonts(),
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
  })

  const localFonts: { family: string; style: string }[] = localFontsData?.data?.fonts || []
  const localFontFamilies = new Set(localFonts.map(f => f.family.toLowerCase()))

  // Fetch Ollama models for AI generation
  const { data: ollamaData } = useQuery({
    queryKey: ['ollama-models'],
    queryFn: () => llmApi.listOllamaModels(),
    enabled: aiProvider === 'ollama' && showAIGenerate,
  })

  const ollamaModels = ollamaData?.data?.models || []
  const ollamaConnected = ollamaData?.data?.connected ?? false

  // Reset model when provider changes
  useEffect(() => {
    if (aiProvider === 'ollama') {
      if (ollamaModels.length > 0) {
        setAiModel(ollamaModels[0].name)
      }
    } else if (aiProvider === 'azure_openai') {
      // For Azure, use deployment name if set, otherwise first model
      if (azureDeployment) {
        setAiModel(azureDeployment)
      } else {
        setAiModel(AI_PROVIDER_CONFIG.azure_openai.models[0].id)
      }
    } else if (aiProvider === 'custom') {
      setAiModel('')
    } else {
      // For other providers, use first model from config
      const config = AI_PROVIDER_CONFIG[aiProvider]
      if (config.models.length > 0) {
        setAiModel(config.models[0].id)
      }
    }
  }, [aiProvider, ollamaModels, azureDeployment])

  // Audio preview
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isSegmentAudioPlaying, setIsSegmentAudioPlaying] = useState(false)

  // Voice cloning preview state
  const [isClonePreviewLoading, setIsClonePreviewLoading] = useState(false)
  const [clonePreviewProgress, setClonePreviewProgress] = useState<{
    stage: string
    message: string
    progress: number
  } | null>(null)
  const cloneWsRef = useRef<WebSocket | null>(null)

  // Voice cloning save progress state (for showing progress during save)
  const [isSaveGeneratingAudio, setIsSaveGeneratingAudio] = useState(false)
  const [saveAudioProgress, setSaveAudioProgress] = useState<{
    stage: string
    message: string
    progress: number
  } | null>(null)
  const saveWsRef = useRef<WebSocket | null>(null)

  // Check if user has voice cloning feature
  const hasVoiceCloning = useAuthStore((state) => state.hasFeature('voice_cloning'))

  // Fetch voice samples for loading saved voice_sample_id (only if user has feature)
  const { data: voiceSamplesData } = useQuery({
    queryKey: ['voice-samples'],
    queryFn: () => ttsApi.getVoiceSamples(),
    staleTime: 30 * 1000,
    enabled: hasVoiceCloning, // Only fetch if user has voice_cloning feature
  })

  const voiceSamples = voiceSamplesData?.data?.samples || []

  // Track the last synced segment ID to avoid re-syncing on unrelated changes
  const lastSyncedSegmentId = useRef<string | null>(null)

  // Sync form with segment - only when segment ID changes (new segment loaded)
  useEffect(() => {
    if (segment && segment.id !== lastSyncedSegmentId.current) {
      lastSyncedSegmentId.current = segment.id
      setName(segment.name)
      setStartTime(segment.start_time)
      setEndTime(segment.end_time)
      setText(segment.text)
      setLanguage(segment.language)
      setVoiceId(segment.voice_id)
      setRate(segment.rate || '+0%')
      setVolume(segment.volume || '+0%')
      setPitch(segment.pitch || '+0Hz')
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
      // TTS provider - use segment's saved provider if available
      setSegmentProvider(segment.tts_provider || null)
      setUseGlobalProvider(false)  // Reset to segment's provider when loading
      // Reset voice sample selection (will be loaded by separate effect)
      setSelectedVoiceSample(null)
    }
  }, [segment])

  // Load voice sample when voiceSamples become available (separate from main sync)
  useEffect(() => {
    if (segment?.voice_sample_id && voiceSamples.length > 0) {
      const savedSample = voiceSamples.find(s => s.id === segment.voice_sample_id)
      if (savedSample) {
        setSelectedVoiceSample(savedSample)
      }
    }
  }, [segment?.voice_sample_id, voiceSamples])

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  // Dynamically load Google Font for preview (only if not a local font)
  useEffect(() => {
    if (!subtitleFont) return

    // Skip loading from Google if font is installed locally
    if (localFontFamilies.has(subtitleFont.toLowerCase())) {
      return
    }

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
  }, [subtitleFont, localFontFamilies])

  // Fetch default TTS provider (global setting)
  const { data: providersData } = useQuery({
    queryKey: ['tts-providers'],
    queryFn: () => ttsApi.getProviders(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  const globalProvider = providersData?.data?.default_provider || 'edge_tts'

  // Effective provider: use segment's provider if set, otherwise use global
  // If user explicitly chose to switch to global, use global
  const effectiveProvider = useGlobalProvider ? globalProvider : (segmentProvider || globalProvider)

  // Check if segment has a different provider than global
  const hasDifferentProvider = segmentProvider && segmentProvider !== globalProvider

  // Check if this provider requires consent (cloud providers like edge_tts)
  const requiresConsent = !LOCAL_PROVIDERS.includes(effectiveProvider?.toLowerCase() || '')
  const needsConsentGate = requiresConsent && !hasTTSConsent

  // Determine voice mode: cloned voice (local Coqui) vs TTS voice (selected provider)
  // When a cloned voice sample is selected, it always uses local Coqui TTS regardless of global provider
  const isUsingClonedVoice = !!selectedVoiceSample

  // Fetch provider-specific languages for the effective provider (only if consent granted for cloud providers)
  const { data: providerLanguagesData } = useQuery({
    queryKey: ['provider-languages', effectiveProvider],
    queryFn: () => ttsApi.getProviderLanguages(effectiveProvider),
    enabled: !!effectiveProvider && !needsConsentGate,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })

  const providerLanguages = providerLanguagesData?.data?.languages || []

  // Fetch voices from the effective provider (only if consent granted for cloud providers)
  const { data: voicesData, isLoading: isLoadingVoices, isFetching: isFetchingVoices } = useQuery({
    queryKey: ['provider-voices', effectiveProvider, language],
    queryFn: () => ttsApi.getProviderVoices(effectiveProvider, language),
    enabled: !!language && !!effectiveProvider && !needsConsentGate,
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

  // Update mutation - also generates audio if text and voice are set
  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      segmentsApi.update(projectName, segment!.id, data),
    onSuccess: async (response) => {
      updateSegment(segment!.id, response.data)

      // Update provider state after successful save
      if (response.data.tts_provider) {
        setSegmentProvider(response.data.tts_provider)
      }
      setUseGlobalProvider(false)  // Reset switch state after save

      // Automatically generate audio if text and voice/voice-sample are set
      const hasText = text && text.trim().length > 0
      const hasVoice = (voiceId && voiceId.trim().length > 0) || selectedVoiceSample !== null

      if (hasText && hasVoice) {
        try {
          const audioResponse = await exportApi.generateSegmentAudio(projectName, segment!.id)

          // Check if this is an async voice cloning job
          if (audioResponse.data.job_id) {
            // Voice cloning - connect to WebSocket for progress
            setIsSaveGeneratingAudio(true)
            setSaveAudioProgress({ stage: 'initializing', message: 'Starting voice cloning...', progress: 0 })

            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
            const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/api/v1/export/segment-audio/progress/${audioResponse.data.job_id}`
            const ws = new WebSocket(wsUrl)
            saveWsRef.current = ws

            ws.onmessage = (event) => {
              if (event.data === 'ping') {
                ws.send('pong')
                return
              }

              try {
                const data = JSON.parse(event.data)
                setSaveAudioProgress({
                  stage: data.stage,
                  message: data.message,
                  progress: data.progress
                })

                // Handle completion
                if (data.status === 'completed') {
                  toast.success('Audio saved with cloned voice!')
                  queryClient.invalidateQueries({ queryKey: ['segments', projectName] })

                  setTimeout(() => {
                    setIsSaveGeneratingAudio(false)
                    setSaveAudioProgress(null)
                    ws.close()
                  }, 1000)
                } else if (data.status === 'failed' || data.stage === 'error') {
                  toast.error(data.message || 'Voice cloning failed')
                  setIsSaveGeneratingAudio(false)
                  setSaveAudioProgress(null)
                  ws.close()
                }
              } catch (e) {
                console.error('Failed to parse WebSocket message:', e)
              }
            }

            ws.onerror = () => {
              toast.error('Connection error during voice cloning')
              setIsSaveGeneratingAudio(false)
              setSaveAudioProgress(null)
            }

            ws.onclose = () => {
              saveWsRef.current = null
            }
          } else {
            // Regular TTS - already completed
            toast.success('Audio saved!')
            queryClient.invalidateQueries({ queryKey: ['segments', projectName] })
          }
        } catch {
          toast.error('Failed to generate audio')
          setIsSaveGeneratingAudio(false)
          setSaveAudioProgress(null)
          queryClient.invalidateQueries({ queryKey: ['segments', projectName] })
        }
      } else {
        toast.success('Segment updated')
        queryClient.invalidateQueries({ queryKey: ['segments', projectName] })
      }
    },
    onError: () => {
      toast.error('Failed to update segment')
      setIsSaveGeneratingAudio(false)
      setSaveAudioProgress(null)
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

  // Generate full segment audio mutation with current form values (preview only - temporary)
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
    // Also stop voice cloning preview
    setIsClonePreviewLoading(false)
    setClonePreviewProgress(null)
    if (cloneWsRef.current) {
      cloneWsRef.current.close()
    }
  }

  // Voice cloning preview handler
  const handleClonePreview = useCallback(async () => {
    if (!selectedVoiceSample || !text) return

    setIsClonePreviewLoading(true)
    setClonePreviewProgress({ stage: 'initializing', message: 'Starting...', progress: 0 })

    try {
      // Start the voice cloning preview
      const response = await ttsApi.previewClonedVoice(
        selectedVoiceSample.id,
        text.slice(0, 200), // Limit text length for preview
        language
      )

      const cloneId = response.data.clone_id
      if (!cloneId) {
        throw new Error('No clone ID returned')
      }

      // Connect to WebSocket for progress
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/api/v1/tts/clone-voice/progress/${cloneId}`
      const ws = new WebSocket(wsUrl)
      cloneWsRef.current = ws

      ws.onmessage = (event) => {
        if (event.data === 'ping') {
          ws.send('pong')
          return
        }

        try {
          const data = JSON.parse(event.data)
          setClonePreviewProgress({
            stage: data.stage,
            message: data.message,
            progress: data.progress
          })

          // Handle completion
          if (data.status === 'completed' && data.audio_url) {
            if (audioRef.current) {
              audioRef.current.pause()
            }
            const audio = new Audio(data.audio_url)
            audioRef.current = audio
            audio.play()
            setIsSegmentAudioPlaying(true)
            audio.onended = () => setIsSegmentAudioPlaying(false)
            toast.success(`Cloned voice audio generated!`)

            // Clean up
            setTimeout(() => {
              setIsClonePreviewLoading(false)
              setClonePreviewProgress(null)
              ws.close()
            }, 1000)
          } else if (data.status === 'failed' || data.stage === 'error') {
            toast.error(data.message || 'Voice cloning failed')
            setIsClonePreviewLoading(false)
            setClonePreviewProgress(null)
            ws.close()
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      ws.onerror = () => {
        toast.error('WebSocket connection error')
        setIsClonePreviewLoading(false)
        setClonePreviewProgress(null)
      }

      ws.onclose = () => {
        cloneWsRef.current = null
      }

    } catch (error) {
      console.error('Clone preview error:', error)
      toast.error('Failed to start voice cloning preview')
      setIsClonePreviewLoading(false)
      setClonePreviewProgress(null)
    }
  }, [selectedVoiceSample, text, language])

  // Cleanup WebSockets on unmount
  useEffect(() => {
    return () => {
      if (cloneWsRef.current) {
        cloneWsRef.current.close()
      }
      if (saveWsRef.current) {
        saveWsRef.current.close()
      }
    }
  }, [])

  const handleSave = () => {
    if (!segment) return

    // Validate: if user switched providers and has text, require a voice selection
    if (useGlobalProvider && text.trim() && !voiceId && !selectedVoiceSample) {
      toast.error('Please select a voice for the new provider before saving')
      return
    }

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
      // Voice cloning (Coqui TTS only)
      voice_sample_id: selectedVoiceSample?.id || null,
      // TTS provider - only send if user switched to global provider
      // This allows the backend to detect provider change and regenerate audio
      tts_provider: useGlobalProvider ? globalProvider : segmentProvider,
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
  // Combines local fonts (installed) with Google fonts, prioritizing local
  const filteredFonts = (() => {
    // Start with Google fonts or fallback
    let googleFontsList = googleFonts.length > 0
      ? googleFonts
      : FALLBACK_FONTS.map((f) => ({ family: f, category: 'sans-serif', variants: [], subsets: [] }))

    // Apply category filter to Google fonts
    if (fontCategory) {
      googleFontsList = googleFontsList.filter((f) => f.category === fontCategory)
    }

    // Apply search filter
    const searchLower = fontSearch.toLowerCase()
    if (fontSearch) {
      googleFontsList = googleFontsList.filter((f) =>
        f.family.toLowerCase().includes(searchLower)
      )
    }

    // Create combined list with isInstalled flag
    const combinedFonts: Array<{ family: string; category: string; isInstalled: boolean }> = []
    const seenFamilies = new Set<string>()

    // First add local fonts that match search (these are guaranteed to work)
    for (const localFont of localFonts) {
      const familyLower = localFont.family.toLowerCase()
      if (!fontSearch || familyLower.includes(searchLower)) {
        if (!seenFamilies.has(familyLower)) {
          seenFamilies.add(familyLower)
          combinedFonts.push({
            family: localFont.family,
            category: 'local',
            isInstalled: true,
          })
        }
      }
    }

    // Then add Google fonts, marking which ones are also installed locally
    for (const gFont of googleFontsList) {
      const familyLower = gFont.family.toLowerCase()
      if (!seenFamilies.has(familyLower)) {
        seenFamilies.add(familyLower)
        combinedFonts.push({
          family: gFont.family,
          category: gFont.category,
          isInstalled: localFontFamilies.has(familyLower),
        })
      }
    }

    return combinedFonts
  })()

  const handleDelete = () => {
    if (!segment) return
    if (confirm('Are you sure you want to delete this segment?')) {
      deleteMutation.mutate()
    }
  }

  // Build provider config with all provider-specific fields
  const buildProviderConfig = () => {
    const baseConfig: Record<string, unknown> = {
      type: aiProvider,
      model: aiModel,
    }

    // Add API key if provided
    if (aiApiKey) {
      baseConfig.api_key = aiApiKey
    }

    // Provider-specific configuration
    switch (aiProvider) {
      case 'azure_openai':
        baseConfig.endpoint = azureEndpoint || undefined
        baseConfig.azure_deployment = azureDeployment || aiModel
        baseConfig.azure_api_version = '2024-05-01-preview'
        break
      case 'aws_bedrock':
        baseConfig.aws_region = awsRegion
        break
      case 'custom':
        baseConfig.endpoint = customEndpoint || undefined
        break
      default:
        break
    }

    return baseConfig
  }

  // AI script generation
  const generateScript = async () => {
    if (!aiDescription.trim()) {
      toast.error('Please provide a description for AI generation')
      return
    }

    if (!aiModel) {
      toast.error('Please select an AI model')
      return
    }

    // Validate API key for providers that require it
    const providerConfig = AI_PROVIDER_CONFIG[aiProvider]
    if (providerConfig.requiresApiKey && !aiApiKey.trim() && aiProvider !== 'aws_bedrock') {
      toast.error(`Please enter your ${providerConfig.name} API key`)
      return
    }

    // Validate Azure endpoint
    if (aiProvider === 'azure_openai' && !azureEndpoint.trim()) {
      toast.error('Please enter your Azure OpenAI endpoint')
      return
    }

    // Validate custom endpoint
    if (aiProvider === 'custom' && !customEndpoint.trim()) {
      toast.error('Please enter a custom endpoint URL')
      return
    }

    setIsGenerating(true)
    try {
      // For Ollama, check if it's available
      if (aiProvider === 'ollama') {
        if (!ollamaConnected) {
          toast.error('Ollama is not running. Please start Ollama first.')
          setIsGenerating(false)
          return
        }
        if (ollamaModels.length === 0) {
          toast.error('No Ollama models available. Please pull a model first.')
          setIsGenerating(false)
          return
        }
      }

      // Build context from existing segments for narrative continuity
      // Exclude the current segment being edited
      const contextSegments = allSegments
        .filter(s => s.id !== segment?.id && s.text && s.text.trim().length > 10)
        .map(s => ({
          name: s.name,
          start_time: s.start_time,
          end_time: s.end_time,
          script: s.text,
          position: s.end_time <= startTime ? 'before' as const : 'after' as const
        }))
        .filter(s => {
          // Keep segments that are clearly before or after the current segment
          return s.position === 'before' || s.start_time >= endTime
        })

      // Generate script
      const response = await llmApi.generateScript({
        provider: buildProviderConfig(),
        segments: [
          {
            start_time: startTime,
            end_time: endTime,
            description: aiDescription,
          },
        ],
        style: {
          tone: 'documentary',
          style: 'narrative',
          audience: 'general',
          length: 'moderate',
          language: language,
        },
        // Provide context for better AI understanding
        video_title: projectName,
        video_context: `This is a ${(endTime - startTime).toFixed(1)} second segment starting at ${startTime.toFixed(1)}s. User description: ${aiDescription}`,
        fit_to_duration: true,
        // Pass existing segments as context for narrative continuity
        context_segments: contextSegments.length > 0 ? contextSegments : undefined,
      })

      if (response.data?.scripts?.length > 0) {
        setText(response.data.scripts[0].text)
        toast.success('Script generated!')
        setShowAIGenerate(false)
        setAiDescription('')
      } else {
        toast.error('No script generated')
      }
    } catch (error) {
      const axiosError = error as { response?: { data?: { detail?: string } } }
      const errorMessage = axiosError?.response?.data?.detail || 'Failed to generate script'
      toast.error(errorMessage)
      console.error('Script generation error:', error)
    } finally {
      setIsGenerating(false)
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

        {/* AI Script Generation (collapsible) */}
        <div className="border border-terminal-border rounded-md overflow-hidden">
          <button
            onClick={() => setShowAIGenerate(!showAIGenerate)}
            className="w-full p-3 flex items-center justify-between bg-terminal-bg/50 hover:bg-terminal-elevated transition-colors"
          >
            <span className="text-sm flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              AI Script Generation
            </span>
            {showAIGenerate ? (
              <ChevronUp className="w-4 h-4 text-text-muted" />
            ) : (
              <ChevronDown className="w-4 h-4 text-text-muted" />
            )}
          </button>

          {showAIGenerate && (
            <div className="p-3 space-y-3 border-t border-terminal-border">
              {/* AI Provider Selection - 8 Providers */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <Settings className="w-3.5 h-3.5" />
                  AI Provider
                </div>

                {/* Provider Grid - All 8 */}
                <div className="grid grid-cols-4 gap-1">
                  {(Object.keys(AI_PROVIDER_CONFIG) as AIProviderType[]).map((p) => {
                    const config = AI_PROVIDER_CONFIG[p]
                    return (
                      <button
                        key={p}
                        onClick={() => setAiProvider(p)}
                        className={clsx(
                          'py-1.5 px-1 rounded text-[10px] transition-colors text-center',
                          aiProvider === p
                            ? 'bg-purple-500 text-white'
                            : 'bg-terminal-elevated text-text-muted hover:text-text-primary'
                        )}
                      >
                        <div className="font-medium">{config.name}</div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Provider-specific Configuration */}
              {/* Ollama */}
              {aiProvider === 'ollama' && (
                <div>
                  <label className="text-xs text-text-muted mb-1 block">Model</label>
                  {ollamaConnected ? (
                    <select
                      value={aiModel}
                      onChange={(e) => setAiModel(e.target.value)}
                      className="input-base w-full text-sm"
                    >
                      {ollamaModels.map((m: { name: string }) => (
                        <option key={m.name} value={m.name}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="text-xs text-red-400 p-2 bg-red-500/10 rounded">
                      Ollama not connected. Please start Ollama.
                    </div>
                  )}
                </div>
              )}

              {/* OpenAI, Anthropic, Google, HuggingFace - Simple API Key + Model */}
              {(aiProvider === 'openai' || aiProvider === 'anthropic' || aiProvider === 'google' || aiProvider === 'huggingface') && (
                <>
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">API Key</label>
                    <input
                      type="password"
                      value={aiApiKey}
                      onChange={(e) => setAiApiKey(e.target.value)}
                      placeholder={`${AI_PROVIDER_CONFIG[aiProvider].name} API key`}
                      className="input-base w-full text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Model</label>
                    <select
                      value={aiModel}
                      onChange={(e) => setAiModel(e.target.value)}
                      className="input-base w-full text-sm"
                    >
                      {AI_PROVIDER_CONFIG[aiProvider].models.map((m) => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {/* Azure OpenAI */}
              {aiProvider === 'azure_openai' && (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">Endpoint</label>
                      <input
                        type="text"
                        value={azureEndpoint}
                        onChange={(e) => setAzureEndpoint(e.target.value)}
                        placeholder="https://....openai.azure.com"
                        className="input-base w-full text-[10px]"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">API Key</label>
                      <input
                        type="password"
                        value={aiApiKey}
                        onChange={(e) => setAiApiKey(e.target.value)}
                        placeholder="API key"
                        className="input-base w-full text-sm"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Deployment Name</label>
                    <input
                      type="text"
                      value={azureDeployment}
                      onChange={(e) => setAzureDeployment(e.target.value)}
                      placeholder="e.g., gpt-35-turbo"
                      className="input-base w-full text-sm"
                    />
                  </div>
                </>
              )}

              {/* AWS Bedrock */}
              {aiProvider === 'aws_bedrock' && (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">Region</label>
                      <select
                        value={awsRegion}
                        onChange={(e) => setAwsRegion(e.target.value)}
                        className="input-base w-full text-sm"
                      >
                        <option value="us-east-1">US East</option>
                        <option value="us-west-2">US West</option>
                        <option value="eu-west-1">EU Ireland</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">Access Key</label>
                      <input
                        type="password"
                        value={aiApiKey}
                        onChange={(e) => setAiApiKey(e.target.value)}
                        placeholder="AKIA..."
                        className="input-base w-full text-sm"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Model</label>
                    <select
                      value={aiModel}
                      onChange={(e) => setAiModel(e.target.value)}
                      className="input-base w-full text-sm"
                    >
                      {AI_PROVIDER_CONFIG.aws_bedrock.models.map((m) => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {/* Custom */}
              {aiProvider === 'custom' && (
                <>
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Endpoint URL</label>
                    <input
                      type="text"
                      value={customEndpoint}
                      onChange={(e) => setCustomEndpoint(e.target.value)}
                      placeholder="https://api.example.com/v1"
                      className="input-base w-full text-sm"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">API Key</label>
                      <input
                        type="password"
                        value={aiApiKey}
                        onChange={(e) => setAiApiKey(e.target.value)}
                        placeholder="Optional"
                        className="input-base w-full text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">Model</label>
                      <input
                        type="text"
                        value={aiModel}
                        onChange={(e) => setAiModel(e.target.value)}
                        placeholder="model-name"
                        className="input-base w-full text-sm"
                      />
                    </div>
                  </div>
                </>
              )}

              {/* Description Input */}
              <div>
                <label className="text-xs text-text-muted mb-1 block">Describe what to generate</label>
                <textarea
                  value={aiDescription}
                  onChange={(e) => setAiDescription(e.target.value)}
                  rows={2}
                  className="input-base w-full resize-none text-sm"
                  placeholder="E.g., 'Describe the beautiful sunset over the ocean with calm waves...'"
                />
              </div>

              {/* Generate Button */}
              <button
                onClick={generateScript}
                disabled={isGenerating || !aiDescription.trim() || !aiModel}
                className="btn-secondary w-full flex items-center justify-center gap-2"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Generate Script
                  </>
                )}
              </button>

              <p className="text-[10px] text-text-muted">
                Generated script will replace the current text above. Uses segment timing to fit duration.
              </p>
            </div>
          )}
        </div>

        {/* TTS Provider Indicator - shows when segment uses a different provider than global */}
        {hasDifferentProvider && !useGlobalProvider && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-md p-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-yellow-400">
                Using <strong>{segmentProvider}</strong> (segment's saved provider)
              </span>
              <button
                type="button"
                onClick={() => {
                  setUseGlobalProvider(true)
                  setVoiceId('')  // Reset voice when switching provider
                }}
                className="text-blue-400 hover:text-blue-300 underline flex items-center gap-1"
              >
                Switch to {globalProvider}
              </button>
            </div>
            <p className="text-text-muted mt-1">
              Global TTS provider is now <strong>{globalProvider}</strong>. Click to switch.
            </p>
          </div>
        )}

        {/* TTS Provider Switch Confirmation - shows when user chose to switch */}
        {hasDifferentProvider && useGlobalProvider && (
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-md p-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-blue-400 flex items-center gap-1">
                {isFetchingVoices && <Loader2 className="w-3 h-3 animate-spin" />}
                Switched to <strong>{globalProvider}</strong>
              </span>
              <button
                type="button"
                onClick={() => {
                  setUseGlobalProvider(false)
                  setVoiceId('')  // Reset voice when reverting
                }}
                className="text-yellow-400 hover:text-yellow-300 underline"
                disabled={isFetchingVoices}
              >
                Keep {segmentProvider}
              </button>
            </div>
            <p className="text-text-muted mt-1">
              {isFetchingVoices
                ? 'Loading voices for new provider...'
                : 'Select a voice below. Audio will regenerate on save.'}
            </p>
          </div>
        )}

        {/* TTS Privacy Warning - only shown for cloud providers */}
        <TTSWarningBanner compact provider={effectiveProvider} />

        {/* Consent Gate - block voice selection for cloud providers without consent */}
        {needsConsentGate ? (
          <TTSConsentRequired onRequestConsent={showConsentModal} />
        ) : (
          <>
        {/* Language */}
        <div>
          <label className="section-header">
            Language
            {effectiveProvider === 'coqui' && (
              <span className="text-xs text-purple-400 ml-2">(16 languages)</span>
            )}
          </label>
          <select
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value)
              setVoiceId('') // Reset voice when language changes
            }}
            className="input-base w-full"
          >
            {/* Use provider-specific languages if available, fallback to LANGUAGES */}
            {(providerLanguages.length > 0 ? providerLanguages : LANGUAGES).map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </select>
        </div>

        {/* Quick Favorites Picker - only show favorites that exist in current provider's voices */}
        {(() => {
          // Filter favorites to only show ones that exist in current provider's voice list
          const validFavorites = favoriteVoices.filter((favId) =>
            voices.some((v) => v.short_name === favId)
          )
          return validFavorites.length > 0 ? (
            <div>
              <label className="section-header flex items-center gap-1">
                <Heart className="w-3 h-3 fill-red-500 text-red-500" />
                Quick Pick
              </label>
              <div className="flex flex-wrap gap-1.5">
                {validFavorites.slice(0, 6).map((favVoiceId) => {
                  const voiceInfo = voices.find((v) => v.short_name === favVoiceId)
                  const displayName = voiceInfo
                    ? formatVoiceName(voiceInfo.name)
                    : favVoiceId.split('-').slice(-2).join(' ')
                  const isSelected = voiceId === favVoiceId

                  return (
                    <button
                      key={favVoiceId}
                      onClick={() => setVoiceId(favVoiceId)}
                      className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
                        isSelected
                          ? 'bg-accent-red border-accent-red text-white'
                          : 'bg-terminal-bg border-terminal-border text-text-secondary hover:border-accent-red/50 hover:text-text-primary'
                      }`}
                      title={voiceInfo ? `${voiceInfo.name} (${voiceInfo.gender})` : favVoiceId}
                    >
                      {displayName}
                    </button>
                  )
                })}
                {validFavorites.length > 6 && (
                  <span className="px-2 py-1 text-xs text-text-muted">
                    +{validFavorites.length - 6} more
                  </span>
                )}
              </div>
            </div>
          ) : null
        })()}

        {/* Voice */}
        <div>
          <label className="section-header flex items-center gap-2">
            Voice
            {(isLoadingVoices || isFetchingVoices) && (
              <Loader2 className="w-3 h-3 animate-spin text-accent-red" />
            )}
          </label>
          <div className="flex gap-2">
            <select
              value={voiceId}
              onChange={(e) => setVoiceId(e.target.value)}
              className="input-base flex-1 min-w-0"
              disabled={isLoadingVoices || isFetchingVoices}
            >
              {isLoadingVoices || isFetchingVoices ? (
                <option value="">Loading voices...</option>
              ) : (
                <>
                  <option value="">Select a voice...</option>
                  {/* Favorites Section - only show favorites that exist in current provider */}
                  {voices.filter(v => favoriteVoices.includes(v.short_name)).length > 0 && (
                    <optgroup label="★ Favorites">
                      {voices.filter(v => favoriteVoices.includes(v.short_name)).map((voice) => (
                        <option key={voice.short_name} value={voice.short_name}>
                          ♥ {formatVoiceName(voice.name)} ({voice.gender})
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {/* All Voices */}
                  <optgroup label="All Voices">
                    {voices.filter(v => !favoriteVoices.includes(v.short_name)).map((voice) => (
                      <option key={voice.short_name} value={voice.short_name}>
                        {formatVoiceName(voice.name)} ({voice.gender})
                      </option>
                    ))}
                  </optgroup>
                </>
              )}
            </select>
            {/* Favorite Toggle Button */}
            {voiceId && (
              <button
                onClick={() => toggleFavoriteVoice(voiceId)}
                className="btn-secondary px-2 shrink-0"
                title={isFavoriteVoice(voiceId) ? 'Remove from favorites' : 'Add to favorites'}
              >
                <Heart
                  className={`w-4 h-4 ${
                    isFavoriteVoice(voiceId)
                      ? 'fill-red-500 text-red-500'
                      : 'text-text-muted hover:text-red-400'
                  }`}
                />
              </button>
            )}
            <button
              onClick={async () => {
                // Only check TTS consent for cloud providers - local providers don't need consent
                if (requiresConsent) {
                  const hasConsent = await checkTTSConsent()
                  if (!hasConsent) return
                }
                previewMutation.mutate()
              }}
              disabled={!voiceId || !text || previewMutation.isPending || isPreviewPlaying}
              className="btn-secondary px-3 shrink-0"
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

        {/* Voice Mode Indicator - shows what will be used for audio generation */}
        {isUsingClonedVoice && (
          <div className="p-3 rounded-md border border-purple-500/40 bg-purple-500/10">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Mic className="w-4 h-4 text-purple-400 shrink-0" />
                <span className="text-sm font-medium text-purple-400 whitespace-nowrap">Cloned Voice</span>
                <span className="text-[10px] px-1.5 py-0.5 bg-purple-500/20 text-purple-300 rounded shrink-0">LOCAL</span>
              </div>
              <button
                onClick={() => setSelectedVoiceSample(null)}
                className="text-[11px] text-purple-400 hover:text-purple-300 underline whitespace-nowrap shrink-0"
              >
                Use TTS Instead
              </button>
            </div>
            <p className="text-[11px] text-text-muted mt-2 truncate">
              Using: <strong className="text-purple-300">{selectedVoiceSample?.name}</strong>
            </p>
          </div>
        )}

        {/* Voice Cloning - Always available (uses local Coqui TTS) */}
        <VoiceCloning
          onSelectSample={setSelectedVoiceSample}
          selectedSampleId={selectedVoiceSample?.id}
          language={language}
          compact={true}
        />

        {/* Voice Parameters (collapsible) - Only show for Edge TTS, not Coqui */}
        {effectiveProvider !== 'coqui' && effectiveProvider !== 'piper' && (
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
        )}

        {/* Preview Audio */}
        <div className={clsx(
          "p-3 rounded-md border",
          isUsingClonedVoice
            ? "border-purple-500/40 bg-purple-500/5"
            : "border-terminal-border bg-terminal-bg/30"
        )}>
          {/* Header */}
          <div className="flex items-center gap-2 mb-3">
            {isUsingClonedVoice ? (
              <Mic className="w-4 h-4 text-purple-400 shrink-0" />
            ) : (
              <Music className="w-4 h-4 text-accent-red shrink-0" />
            )}
            <span className="text-sm font-medium">Preview Audio</span>
            {isUsingClonedVoice ? (
              <span className="text-[10px] text-purple-400 bg-purple-500/20 px-1.5 py-0.5 rounded">
                Cloned
              </span>
            ) : (
              <span className="text-[10px] text-text-muted bg-terminal-elevated px-1.5 py-0.5 rounded">
                {effectiveProvider === 'edge_tts' ? 'Edge TTS' : effectiveProvider}
              </span>
            )}
            {segment.audio_path && (
              <span className="text-[10px] text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                <Check className="w-3 h-3" /> Saved
              </span>
            )}
          </div>

          {/* Voice cloning progress */}
          {clonePreviewProgress && (
            <div className="mb-3 p-2 bg-purple-500/10 border border-purple-500/30 rounded">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-purple-400">
                  {clonePreviewProgress.stage === 'loading' ? 'Loading Model...' :
                   clonePreviewProgress.stage === 'generating' ? 'Generating...' :
                   clonePreviewProgress.stage === 'converting' ? 'Converting...' :
                   'Processing...'}
                </span>
                <span className="text-xs text-text-muted">{clonePreviewProgress.progress}%</span>
              </div>
              <div className="w-full bg-terminal-border rounded-full h-1.5">
                <div
                  className="bg-purple-500 h-1.5 rounded-full transition-all"
                  style={{ width: `${clonePreviewProgress.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2">
            <button
              onClick={async () => {
                // Use voice cloning if a sample is selected (always local, no consent needed)
                if (selectedVoiceSample) {
                  handleClonePreview()
                } else {
                  // Use regular TTS - only check consent for cloud providers
                  if (requiresConsent) {
                    const hasConsent = await checkTTSConsent()
                    if (!hasConsent) return
                  }
                  segmentAudioMutation.mutate()
                }
              }}
              disabled={!text || (!voiceId && !selectedVoiceSample) || segmentAudioMutation.isPending || isClonePreviewLoading}
              className="btn-secondary flex-1 flex items-center justify-center gap-2 text-sm"
            >
              {segmentAudioMutation.isPending || isClonePreviewLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {isClonePreviewLoading ? 'Cloning...' : 'Generating...'}
                </>
              ) : (
                <>
                  <PlayCircle className="w-4 h-4" />
                  {isUsingClonedVoice ? 'Preview Cloned Voice' : 'Preview Audio'}
                </>
              )}
            </button>
            {(isPreviewPlaying || isSegmentAudioPlaying || isClonePreviewLoading) && (
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
            {isUsingClonedVoice
              ? `Voice: ${selectedVoiceSample?.name} (Coqui TTS)`
              : 'Audio generated on save'}
          </p>
        </div>
          </>
        )}

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
                      <span className="text-green-400 ml-1">({localFonts.length} installed)</span>
                      {googleFonts.length > 0 && (
                        <span className="text-text-muted ml-1">+ {googleFonts.length} Google</span>
                      )}
                    </label>
                    <div className="relative">
                      <button
                        onClick={() => setShowFontSearch(!showFontSearch)}
                        className="input-base w-full text-left flex items-center justify-between"
                      >
                        <span className="flex items-center gap-2">
                          {subtitleFont}
                          {localFontFamilies.has(subtitleFont.toLowerCase()) && (
                            <Check className="w-3 h-3 text-green-400" />
                          )}
                        </span>
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
                              <button
                                onClick={() => setFontCategory(fontCategory === 'local' ? '' : 'local')}
                                className={clsx(
                                  'text-[10px] px-1.5 py-0.5 rounded',
                                  fontCategory === 'local'
                                    ? 'bg-green-500 text-white'
                                    : 'bg-terminal-elevated text-green-400 hover:text-green-300'
                                )}
                              >
                                Installed
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
                                <span className="flex items-center gap-2">
                                  {font.family}
                                  {font.isInstalled && (
                                    <Check className="w-3 h-3 text-green-400" />
                                  )}
                                </span>
                                <span className={clsx(
                                  'text-[10px] capitalize',
                                  font.isInstalled ? 'text-green-400' : 'text-text-muted'
                                )}>
                                  {font.isInstalled ? 'installed' : font.category}
                                </span>
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
                      <Check className="w-3 h-3 text-green-400 inline mr-1" />
                      = Installed locally (guaranteed to work). Others require installation.
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
                    <p className="text-xs text-text-muted mb-2">
                      Font Preview:
                      {localFontFamilies.has(subtitleFont.toLowerCase()) ? (
                        <span className="text-green-400 ml-1">(installed locally)</span>
                      ) : (
                        <span className="text-yellow-400 ml-1">(not installed - may not render)</span>
                      )}
                    </p>
                    {/* Always show language-appropriate sample to demonstrate font capability */}
                    <p
                      style={{
                        fontFamily: `"${subtitleFont}", sans-serif`,
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
                      {getSampleText(language)}
                    </p>
                    <p className="text-[10px] text-text-muted mt-2 text-center">
                      {LANGUAGES.find(l => l.code === language)?.name || 'English'} sample
                      {!localFontFamilies.has(subtitleFont.toLowerCase()) && (
                        <span className="text-yellow-400 ml-1">
                          - Install font for accurate preview
                        </span>
                      )}
                    </p>
                    {/* Show actual segment text preview if different from sample */}
                    {text && (
                      <div className="mt-2 pt-2 border-t border-terminal-border">
                        <p className="text-[10px] text-text-muted mb-1">Your text:</p>
                        <p
                          style={{
                            fontFamily: `"${subtitleFont}", sans-serif`,
                            fontSize: `${Math.min(subtitleSize, 18)}px`,
                            color: subtitleColor,
                            textShadow: subtitleShadow > 0
                              ? `${subtitleShadow}px ${subtitleShadow}px ${subtitleShadowColor}`
                              : 'none',
                            WebkitTextStroke: subtitleBorderEnabled
                              ? `${subtitleOutlineWidth}px ${subtitleOutlineColor}`
                              : 'none',
                          }}
                          className="text-center truncate"
                        >
                          {text.slice(0, 40)}...
                        </p>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-terminal-border bg-terminal-bg/50">
        {/* Voice Cloning Save Progress */}
        {isSaveGeneratingAudio && saveAudioProgress && (
          <div className="mb-3 p-3 bg-terminal-bg border border-primary/30 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
              <span className="text-sm font-medium text-primary">
                Generating Audio with Cloned Voice
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-text-muted">
                <span>{saveAudioProgress.message}</span>
                <span>{saveAudioProgress.progress}%</span>
              </div>
              <div className="w-full bg-terminal-border rounded-full h-1.5">
                <div
                  className="bg-primary h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${saveAudioProgress.progress}%` }}
                />
              </div>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between">
          <button
            onClick={() => setCurrentTime(startTime)}
            className="btn-ghost text-sm"
          >
            Jump to Start
          </button>
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending || isSaveGeneratingAudio}
            className="btn-primary flex items-center gap-2"
          >
            {updateMutation.isPending || isSaveGeneratingAudio ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {isSaveGeneratingAudio ? 'Generating Audio...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </motion.div>
  )
}
