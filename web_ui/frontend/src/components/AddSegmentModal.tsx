/**
 * AddSegmentModal - Enhanced modal for creating segments with full voice/subtitle configuration
 */

import { useEffect, useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Plus,
  Loader2,
  AlertTriangle,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Mic,
  PlayCircle,
  StopCircle,
} from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'

import { segmentsApi, llmApi, ttsApi, exportApi, VoiceSample } from '../api/client'
import { useAppStore } from '../stores/appStore'
import { useTTSConsentGate } from '../stores/consentStore'
import { TTSWarningBanner } from './TTSConsentModal'
import { getSampleText } from '../constants/languages'
import { AI_PROVIDER_CONFIG, AIProviderType } from '../constants/aiProviders'
import { hexToBgr } from '../utils/colors'
import VoiceSelector from './shared/VoiceSelector'
import VoiceParameters from './shared/VoiceParameters'
import VoiceCloning from './shared/VoiceCloning'
import SubtitleStyler from './shared/SubtitleStyler'
import AIProviderSelector from './shared/AIProviderSelector'
import type { Segment } from '../types'

// Providers that process locally and don't require consent
const LOCAL_PROVIDERS = ['coqui', 'piper']

interface AddSegmentModalProps {
  isOpen: boolean
  onClose: () => void
  projectName: string
  videoId: string | null
  startTime: number
  videoDuration: number
  existingSegments: Segment[]
  isMultiVideo?: boolean
}

export default function AddSegmentModal({
  isOpen,
  onClose,
  projectName,
  videoId,
  startTime,
  videoDuration,
  existingSegments,
  isMultiVideo = false,
}: AddSegmentModalProps) {
  const queryClient = useQueryClient()
  const { addSegment, setSelectedSegmentId } = useAppStore()
  const { checkConsent: checkTTSConsent } = useTTSConsentGate()

  // Basic segment info
  const [name, setName] = useState(`Segment ${Date.now()}`)
  const [segmentStartTime, setSegmentStartTime] = useState(startTime)
  const [endTime, setEndTime] = useState(Math.min(startTime + 10, videoDuration))
  const [text, setText] = useState('')
  const [language, setLanguage] = useState('en')
  const [description, setDescription] = useState('')

  // AI generation state
  const [showAIGenerate, setShowAIGenerate] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)

  // AI Provider settings
  const [aiProvider, setAiProvider] = useState<AIProviderType>('ollama')
  const [aiModel, setAiModel] = useState('')
  const [aiApiKey, setAiApiKey] = useState('')
  const [customEndpoint, setCustomEndpoint] = useState('')

  // Azure OpenAI settings
  const [azureEndpoint, setAzureEndpoint] = useState('')
  const [azureDeployment, setAzureDeployment] = useState('')
  const [azureApiVersion, setAzureApiVersion] = useState('2024-05-01-preview')

  // AWS Bedrock settings
  const [awsRegion, setAwsRegion] = useState('us-east-1')
  const [awsAccessKeyId, setAwsAccessKeyId] = useState('')
  const [awsSecretAccessKey, setAwsSecretAccessKey] = useState('')

  // HuggingFace settings
  const [hfInferenceProvider, setHfInferenceProvider] = useState('auto')

  // Voice settings
  const [voiceId, setVoiceId] = useState('')
  const [rate, setRate] = useState('+0%')
  const [volume, setVolume] = useState('+0%')
  const [pitch, setPitch] = useState('+0Hz')

  // Voice cloning (Coqui TTS only)
  const [selectedVoiceSample, setSelectedVoiceSample] = useState<VoiceSample | null>(null)

  // Subtitle settings
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

  // Section visibility
  const [voiceSectionExpanded, setVoiceSectionExpanded] = useState(true)

  // Audio preview
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isPreviewPlaying, setIsPreviewPlaying] = useState(false)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [estimatedDuration, setEstimatedDuration] = useState<number | null>(null)

  // Fetch TTS providers to determine active provider
  const { data: ttsProvidersData } = useQuery({
    queryKey: ['tts-providers'],
    queryFn: () => ttsApi.getProviders(),
    staleTime: 5 * 60 * 1000,
  })
  const activeProvider = ttsProvidersData?.data?.default_provider || 'edge_tts'

  // Fetch Ollama models when provider is ollama
  const { data: ollamaData } = useQuery({
    queryKey: ['ollama-models'],
    queryFn: () => llmApi.listOllamaModels(),
    enabled: aiProvider === 'ollama' && isOpen,
  })

  const ollamaModels = ollamaData?.data?.models || []
  const ollamaConnected = ollamaData?.data?.connected ?? false

  // Estimate duration when text changes
  useEffect(() => {
    if (!text.trim() || !language) {
      setEstimatedDuration(null)
      return
    }

    const estimateDuration = async () => {
      try {
        const response = await ttsApi.estimateDuration(text, language)
        setEstimatedDuration(response.data?.duration || null)
      } catch {
        setEstimatedDuration(null)
      }
    }

    const debounce = setTimeout(estimateDuration, 500)
    return () => clearTimeout(debounce)
  }, [text, language])

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setName(`Segment ${Math.floor(Date.now() / 1000) % 10000}`)
      setSegmentStartTime(startTime)
      const minSegmentDuration = 1.0
      const proposedEnd = startTime + 10
      const maxEnd = Math.max(videoDuration, startTime + minSegmentDuration)
      setEndTime(Math.min(proposedEnd, maxEnd))
      setText('')
      setDescription('')
      setShowAIGenerate(false)
      setVoiceId('')
      setRate('+0%')
      setVolume('+0%')
      setPitch('+0Hz')
      setEstimatedDuration(null)
      stopPreview()
    }
  }, [isOpen, startTime, videoDuration])

  // Set default model when provider changes
  useEffect(() => {
    if (aiProvider === 'ollama' && ollamaModels.length > 0 && !aiModel) {
      setAiModel(ollamaModels[0].name)
    } else if (aiProvider !== 'ollama' && aiProvider !== 'custom' && !aiModel) {
      const providerModels = AI_PROVIDER_CONFIG[aiProvider].models
      if (providerModels.length > 0) {
        setAiModel(providerModels[0].id)
      }
    }
  }, [aiProvider, ollamaModels, aiModel])

  // Reset model when provider changes
  useEffect(() => {
    if (aiProvider === 'ollama' && ollamaModels.length > 0) {
      setAiModel(ollamaModels[0].name)
    } else if (aiProvider === 'custom') {
      setAiModel('')
    } else if (aiProvider !== 'ollama') {
      const providerModels = AI_PROVIDER_CONFIG[aiProvider].models
      if (providerModels.length > 0) {
        setAiModel(providerModels[0].id)
      }
    }
  }, [aiProvider])

  // Stop preview when modal closes
  useEffect(() => {
    if (!isOpen) {
      stopPreview()
    }
  }, [isOpen])

  // Preview audio
  const handlePreview = async (audioUrl: string) => {
    stopPreview()

    try {
      const audio = new Audio(audioUrl)
      audioRef.current = audio

      audio.onended = () => {
        setIsPreviewPlaying(false)
      }

      audio.onerror = () => {
        setIsPreviewPlaying(false)
        toast.error('Failed to play audio preview')
      }

      await audio.play()
      setIsPreviewPlaying(true)
    } catch (error) {
      console.error('Preview error:', error)
      toast.error('Failed to play preview')
    }
  }

  const stopPreview = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setIsPreviewPlaying(false)
  }

  // Generate full audio preview
  const generateFullPreview = async () => {
    if (!text.trim() || !voiceId) {
      toast.error('Please enter text and select a voice')
      return
    }

    // Only check TTS consent for cloud providers - local providers (Coqui, Piper) don't need consent
    const requiresConsent = !LOCAL_PROVIDERS.includes(activeProvider?.toLowerCase() || '')
    if (requiresConsent) {
      const hasConsent = await checkTTSConsent()
      if (!hasConsent) {
        return
      }
    }

    setIsLoadingPreview(true)
    try {
      const response = await exportApi.previewSegmentAudio({
        project_name: projectName,
        text,
        voice_id: voiceId,
        language,
        rate,
        volume,
        pitch,
      })

      if (response.data?.audio_url) {
        handlePreview(response.data.audio_url)
      }
    } catch (error) {
      console.error('Preview error:', error)
      toast.error('Failed to generate preview')
    } finally {
      setIsLoadingPreview(false)
    }
  }

  // AI script generation
  const generateScript = async () => {
    if (!description.trim()) {
      toast.error('Please provide a description for AI generation')
      return
    }

    if (endTime <= segmentStartTime) {
      toast.error('End time must be after start time')
      return
    }

    if (!aiModel) {
      toast.error('Please select an AI model')
      return
    }

    const providerRequiresApiKey = AI_PROVIDER_CONFIG[aiProvider].requiresApiKey
    if (providerRequiresApiKey && aiProvider !== 'aws_bedrock' && !aiApiKey.trim()) {
      toast.error(`Please enter your ${AI_PROVIDER_CONFIG[aiProvider].name} API key`)
      return
    }

    if (aiProvider === 'azure_openai' && !azureEndpoint.trim()) {
      toast.error('Please enter your Azure OpenAI endpoint')
      return
    }

    if (aiProvider === 'aws_bedrock' && (!awsAccessKeyId.trim() || !awsSecretAccessKey.trim())) {
      toast.error('Please enter your AWS credentials')
      return
    }

    if (aiProvider === 'custom' && !customEndpoint.trim()) {
      toast.error('Please enter a custom endpoint URL')
      return
    }

    setIsGenerating(true)
    try {
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

      const providerConfig: Record<string, unknown> = {
        type: aiProvider,
        model: aiModel,
      }

      if (aiApiKey && aiProvider !== 'ollama') {
        providerConfig.api_key = aiApiKey
      }

      switch (aiProvider) {
        case 'azure_openai':
          providerConfig.endpoint = azureEndpoint || undefined
          providerConfig.azure_deployment = azureDeployment || aiModel
          providerConfig.azure_api_version = azureApiVersion
          break
        case 'aws_bedrock':
          providerConfig.aws_region = awsRegion
          providerConfig.aws_access_key_id = awsAccessKeyId || undefined
          providerConfig.aws_secret_access_key = awsSecretAccessKey || undefined
          break
        case 'huggingface':
          providerConfig.huggingface_provider = hfInferenceProvider
          break
        case 'custom':
          providerConfig.endpoint = customEndpoint || undefined
          break
      }

      const contextSegments = existingSegments
        .filter(s => s.text && s.text.trim().length > 10)
        .map(s => ({
          name: s.name,
          start_time: s.start_time,
          end_time: s.end_time,
          script: s.text,
          position: s.end_time <= segmentStartTime ? 'before' as const : 'after' as const
        }))
        .filter(s => s.position === 'before' || s.start_time >= endTime)

      const response = await llmApi.generateScript({
        provider: providerConfig,
        segments: [
          {
            start_time: segmentStartTime,
            end_time: endTime,
            description: description,
          },
        ],
        style: {
          tone: 'documentary',
          style: 'narrative',
          audience: 'general',
          length: 'moderate',
          language: language,
        },
        video_title: projectName,
        video_context: `This is a ${(endTime - segmentStartTime).toFixed(1)} second segment starting at ${segmentStartTime.toFixed(1)}s. User description: ${description}`,
        fit_to_duration: true,
        context_segments: contextSegments.length > 0 ? contextSegments : undefined,
      })

      if (response.data?.scripts?.length > 0) {
        setText(response.data.scripts[0].text)
        toast.success('Script generated!')
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

  // Create segment mutation
  const createMutation = useMutation({
    mutationFn: () => {
      // Build segment data with all fields
      const segmentData: Record<string, unknown> = {
        name,
        start_time: segmentStartTime,
        end_time: endTime,
        text,
        language,
        voice_id: voiceId,
        rate,
        volume,
        pitch,
        // Voice cloning (Coqui TTS only)
        voice_sample_id: selectedVoiceSample?.id || null,
        // Store the TTS provider being used
        tts_provider: activeProvider,
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
        subtitle_shadow_color: hexToBgr(subtitleShadowColor),
      }

      return segmentsApi.create(projectName, segmentData, videoId ?? undefined)
    },
    onSuccess: async (response) => {
      addSegment(response.data)
      setSelectedSegmentId(response.data.id)

      // Check if we have text and voice/voice-sample to generate audio
      const hasText = text && text.trim().length > 0
      const hasVoice = (voiceId && voiceId.trim().length > 0) || selectedVoiceSample !== null

      if (hasText && hasVoice) {
        // Generate audio for the newly created segment
        try {
          const audioResponse = await exportApi.generateSegmentAudio(projectName, response.data.id)

          // Check if this is an async voice cloning job
          if (audioResponse.data.job_id) {
            // Voice cloning - show progress via toast updates
            toast.success('Segment created, generating cloned voice audio...')

            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
            const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/api/v1/export/segment-audio/progress/${audioResponse.data.job_id}`
            const ws = new WebSocket(wsUrl)

            ws.onmessage = (event) => {
              if (event.data === 'ping') {
                ws.send('pong')
                return
              }

              try {
                const data = JSON.parse(event.data)
                if (data.status === 'completed') {
                  toast.success('Audio generated with cloned voice!')
                  queryClient.invalidateQueries({ queryKey: ['segments', projectName] })
                  ws.close()
                } else if (data.status === 'failed' || data.stage === 'error') {
                  toast.error(data.message || 'Voice cloning failed')
                  ws.close()
                }
              } catch (e) {
                console.error('Failed to parse WebSocket message:', e)
              }
            }

            ws.onerror = () => {
              toast.error('Voice cloning connection error')
            }
          } else {
            // Regular TTS - already completed
            toast.success('Audio generated!')
          }
        } catch {
          // Audio generation failed, but segment is still created
          toast.error('Audio generation failed - you can regenerate later')
        }
      } else {
        toast.success('Segment created')
      }

      queryClient.invalidateQueries({ queryKey: ['segments', projectName] })
      onClose()
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { data?: { detail?: string } } }
      const errorMessage = axiosError?.response?.data?.detail || 'Failed to create segment'
      toast.error(errorMessage)
    },
  })

  if (!isOpen) return null

  // Check for overlapping segments
  const overlappingSegments = existingSegments.filter(
    s => segmentStartTime < s.end_time && endTime > s.start_time
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative bg-terminal-surface border border-terminal-border rounded-lg w-full max-w-3xl max-h-[90vh] flex flex-col"
      >
        {/* Fixed header */}
        <div className="p-6 pb-0 shrink-0">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Plus className="w-5 h-5 text-accent-red" />
            Add Segment
            {isMultiVideo && !videoId && (
              <span className="text-xs font-normal text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">
                Project Timeline
              </span>
            )}
          </h3>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-6 pb-2">
          <div className="space-y-4">
            {/* Basic Info Section */}
            <div className="space-y-4">
              <div>
                <label className="section-header">Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input-base w-full"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="section-header">Start Time (s)</label>
                  <input
                    type="number"
                    value={segmentStartTime}
                    onChange={(e) => {
                      const newStart = parseFloat(e.target.value) || 0
                      setSegmentStartTime(Math.max(0, Math.min(newStart, endTime - 0.5)))
                    }}
                    step="0.5"
                    min={0}
                    max={endTime - 0.5}
                    className="input-base w-full font-mono"
                  />
                </div>
                <div>
                  <label className="section-header">End Time (s)</label>
                  <input
                    type="number"
                    value={endTime}
                    onChange={(e) => {
                      const newEnd = parseFloat(e.target.value) || segmentStartTime + 0.5
                      setEndTime(Math.max(segmentStartTime + 0.5, Math.min(newEnd, videoDuration)))
                    }}
                    step="0.5"
                    min={segmentStartTime + 0.5}
                    max={videoDuration}
                    className="input-base w-full font-mono"
                  />
                </div>
                <div>
                  <label className="section-header">Duration</label>
                  <div className="input-base w-full font-mono text-text-muted bg-terminal-bg/50">
                    {(endTime - segmentStartTime).toFixed(1)}s
                  </div>
                </div>
              </div>

              {/* Overlap warning */}
              {!isMultiVideo && overlappingSegments.length > 0 && (
                <div className="p-3 rounded bg-red-500/10 border border-red-500/50">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    <div className="text-sm">
                      <span className="text-red-500 font-medium">Overlap detected!</span>
                      <span className="text-text-muted ml-1">
                        This segment will overlap with:
                      </span>
                      <ul className="mt-1 space-y-1">
                        {overlappingSegments.map(s => (
                          <li key={s.id} className="text-text-muted">
                            <span className="text-text-primary">{s.name}</span>
                            <span className="text-text-muted/70 text-xs ml-1">
                              ({s.start_time.toFixed(1)}s - {s.end_time.toFixed(1)}s)
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Existing segments reference */}
              {existingSegments.length > 0 && (
                <div className="text-xs text-text-muted border border-terminal-border rounded p-2 bg-terminal-bg/50">
                  <div className="font-medium mb-1">Existing segments on this video:</div>
                  <div className="flex flex-wrap gap-1">
                    {existingSegments.slice(0, 5).map(s => (
                      <span key={s.id} className="px-1.5 py-0.5 bg-terminal-elevated rounded text-[10px]">
                        {s.name} ({s.start_time.toFixed(1)}-{s.end_time.toFixed(1)}s)
                      </span>
                    ))}
                    {existingSegments.length > 5 && (
                      <span className="px-1.5 py-0.5 text-[10px]">+{existingSegments.length - 5} more</span>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Script Section */}
            <div className="border border-terminal-border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <label className="section-header mb-0">Script</label>
                <div className="flex items-center gap-2 p-1 rounded bg-terminal-bg border border-terminal-border">
                  <button
                    onClick={() => setShowAIGenerate(false)}
                    className={clsx(
                      'py-1 px-3 rounded text-xs transition-colors',
                      !showAIGenerate
                        ? 'bg-accent-red text-white'
                        : 'text-text-muted hover:text-text-primary'
                    )}
                  >
                    Manual
                  </button>
                  <button
                    onClick={() => setShowAIGenerate(true)}
                    className={clsx(
                      'py-1 px-3 rounded text-xs transition-colors flex items-center gap-1',
                      showAIGenerate
                        ? 'bg-accent-red text-white'
                        : 'text-text-muted hover:text-text-primary'
                    )}
                  >
                    <Sparkles className="w-3 h-3" />
                    AI
                  </button>
                </div>
              </div>

              {showAIGenerate ? (
                <div className="space-y-3">
                  <AIProviderSelector
                    provider={aiProvider}
                    model={aiModel}
                    apiKey={aiApiKey}
                    onProviderChange={setAiProvider}
                    onModelChange={setAiModel}
                    onApiKeyChange={setAiApiKey}
                    azureEndpoint={azureEndpoint}
                    azureDeployment={azureDeployment}
                    azureApiVersion={azureApiVersion}
                    onAzureEndpointChange={setAzureEndpoint}
                    onAzureDeploymentChange={setAzureDeployment}
                    onAzureApiVersionChange={setAzureApiVersion}
                    awsRegion={awsRegion}
                    awsAccessKeyId={awsAccessKeyId}
                    awsSecretAccessKey={awsSecretAccessKey}
                    onAwsRegionChange={setAwsRegion}
                    onAwsAccessKeyIdChange={setAwsAccessKeyId}
                    onAwsSecretAccessKeyChange={setAwsSecretAccessKey}
                    hfInferenceProvider={hfInferenceProvider}
                    onHfInferenceProviderChange={setHfInferenceProvider}
                    customEndpoint={customEndpoint}
                    onCustomEndpointChange={setCustomEndpoint}
                  />

                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Describe this segment</label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={2}
                      className="input-base w-full resize-none text-sm"
                      placeholder="Describe what happens in this segment..."
                    />
                  </div>

                  <button
                    onClick={generateScript}
                    disabled={isGenerating || !description.trim() || !aiModel}
                    className="btn-secondary w-full flex items-center justify-center gap-2"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Generating with {aiModel}...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        Generate Script
                      </>
                    )}
                  </button>

                  {text && (
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">Generated Script</label>
                      <textarea
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        rows={3}
                        className="input-base w-full resize-none text-sm"
                      />
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={3}
                    className="input-base w-full resize-none"
                    placeholder="Enter the narration text... (can be added later)"
                  />
                </div>
              )}

              {/* Duration estimation */}
              {text.trim() && estimatedDuration && (
                <div className="text-xs text-text-muted flex items-center gap-2">
                  <span>Estimated audio duration: {estimatedDuration.toFixed(1)}s</span>
                  {estimatedDuration > (endTime - segmentStartTime) && (
                    <span className="text-amber-400">
                      (exceeds segment by {(estimatedDuration - (endTime - segmentStartTime)).toFixed(1)}s)
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Voice & Audio Section */}
            <div className="border border-terminal-border rounded-lg">
              <button
                onClick={() => setVoiceSectionExpanded(!voiceSectionExpanded)}
                className="w-full flex items-center justify-between p-3 hover:bg-terminal-bg/50 transition-colors"
              >
                <div className="flex items-center gap-2 text-sm">
                  <Mic className="w-4 h-4 text-accent-primary" />
                  <span className="font-medium">Voice & Audio</span>
                  {voiceId && (
                    <span className="text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded">
                      {voiceId.split('-').slice(-1)[0]}
                    </span>
                  )}
                </div>
                {voiceSectionExpanded ? (
                  <ChevronUp className="w-4 h-4 text-text-muted" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-text-muted" />
                )}
              </button>

              {voiceSectionExpanded && (
                <div className="p-4 mt-2 border-t border-terminal-border space-y-4">
                  {/* TTS Privacy Warning - only shown for cloud providers */}
                  <TTSWarningBanner compact provider={activeProvider} />

                  {/* Language & Voice Selection */}
                  <VoiceSelector
                    language={language}
                    voiceId={voiceId}
                    onLanguageChange={setLanguage}
                    onVoiceChange={setVoiceId}
                    text={text}
                    rate={rate}
                    volume={volume}
                    pitch={pitch}
                    onPreview={handlePreview}
                    isPreviewPlaying={isPreviewPlaying}
                    onStopPreview={stopPreview}
                    provider={activeProvider}
                  />

                  {/* Voice Parameters - hidden for Coqui (local) which doesn't support these */}
                  <VoiceParameters
                    rate={rate}
                    volume={volume}
                    pitch={pitch}
                    onRateChange={setRate}
                    onVolumeChange={setVolume}
                    onPitchChange={setPitch}
                    collapsible={true}
                    defaultExpanded={false}
                    provider={activeProvider}
                  />

                  {/* Voice Cloning - Only show for Coqui TTS */}
                  {activeProvider === 'coqui' && (
                    <VoiceCloning
                      onSelectSample={setSelectedVoiceSample}
                      selectedSampleId={selectedVoiceSample?.id}
                      language={language}
                      compact={true}
                    />
                  )}

                  {/* Full Audio Preview */}
                  {text.trim() && voiceId && (
                    <button
                      onClick={isPreviewPlaying ? stopPreview : generateFullPreview}
                      disabled={isLoadingPreview}
                      className="btn-secondary w-full flex items-center justify-center gap-2"
                    >
                      {isLoadingPreview ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Generating preview...
                        </>
                      ) : isPreviewPlaying ? (
                        <>
                          <StopCircle className="w-4 h-4" />
                          Stop Preview
                        </>
                      ) : (
                        <>
                          <PlayCircle className="w-4 h-4" />
                          Preview Full Audio
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Subtitle Settings Section */}
            <SubtitleStyler
              enabled={subtitleEnabled}
              onEnabledChange={setSubtitleEnabled}
              font={subtitleFont}
              size={subtitleSize}
              color={subtitleColor}
              position={subtitlePosition}
              borderEnabled={subtitleBorderEnabled}
              borderStyle={subtitleBorderStyle}
              outlineWidth={subtitleOutlineWidth}
              outlineColor={subtitleOutlineColor}
              shadow={subtitleShadow}
              shadowColor={subtitleShadowColor}
              onFontChange={setSubtitleFont}
              onSizeChange={setSubtitleSize}
              onColorChange={setSubtitleColor}
              onPositionChange={setSubtitlePosition}
              onBorderEnabledChange={setSubtitleBorderEnabled}
              onBorderStyleChange={setSubtitleBorderStyle}
              onOutlineWidthChange={setSubtitleOutlineWidth}
              onOutlineColorChange={setSubtitleOutlineColor}
              onShadowChange={setSubtitleShadow}
              onShadowColorChange={setSubtitleShadowColor}
              text={text || getSampleText(language)}
              language={language}
              collapsible={true}
              defaultExpanded={true}
              showPreview={true}
            />
          </div>
        </div>

        {/* Fixed footer */}
        <div className="p-6 pt-4 shrink-0 border-t border-terminal-border bg-terminal-surface">
          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || isGenerating || endTime <= segmentStartTime}
              className="btn-primary flex items-center gap-2"
              title={endTime <= segmentStartTime ? 'End time must be after start time' : undefined}
            >
              {createMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
              Create Segment
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
