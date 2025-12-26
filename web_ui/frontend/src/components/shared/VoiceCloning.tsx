/**
 * VoiceCloning - Component for managing voice samples and cloning
 *
 * Features:
 * - Upload voice samples (5-30 seconds of clear speech recommended)
 * - List and manage uploaded samples
 * - Preview cloned voice
 * - Select cloned voice for TTS generation
 *
 * Note: Voice cloning only works with Coqui TTS (local provider)
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload,
  Mic,
  Trash2,
  Play,
  Pause,
  Check,
  Loader2,
  User,
  Clock,
  FileAudio,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'

import { ttsApi, modelsApi, VoiceSample } from '../../api/client'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Settings } from 'lucide-react'

interface CloneProgress {
  stage: string
  message: string
  progress: number
  status: string
  audio_url?: string
  duration?: number
}

interface VoiceCloningProps {
  onSelectSample?: (sample: VoiceSample | null) => void
  selectedSampleId?: string | null
  language?: string
  disabled?: boolean
  compact?: boolean
}

export default function VoiceCloning({
  onSelectSample,
  selectedSampleId,
  language = 'en',
  disabled = false,
  compact = false,
}: VoiceCloningProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  const [isExpanded, setIsExpanded] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadName, setUploadName] = useState('')
  const [showUploadForm, setShowUploadForm] = useState(false)
  const [playingSampleId, setPlayingSampleId] = useState<string | null>(null)
  const [previewingSampleId, setPreviewingSampleId] = useState<string | null>(null)
  const [cloneProgress, setCloneProgress] = useState<CloneProgress | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Check if voice cloning model is downloaded
  const { data: modelStatusData, isLoading: isCheckingModel } = useQuery({
    queryKey: ['voice-cloning-model-check'],
    queryFn: () => modelsApi.checkModel('xtts_v2'),
    staleTime: 60 * 1000, // Cache for 1 minute
    retry: 1,
  })

  const isModelReady = modelStatusData?.data?.ready || false

  // Fetch voice samples
  const { data: samplesData, isLoading } = useQuery({
    queryKey: ['voice-samples'],
    queryFn: () => ttsApi.getVoiceSamples(),
    staleTime: 30 * 1000,
  })

  const samples = samplesData?.data?.samples || []

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async ({ file, name }: { file: File; name: string }) => {
      return ttsApi.uploadVoiceSample(file, name, language)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['voice-samples'] })
      toast.success('Voice sample uploaded successfully')
      setShowUploadForm(false)
      setUploadName('')
    },
    onError: (error: Error) => {
      toast.error(`Upload failed: ${error.message}`)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (sampleId: string) => ttsApi.deleteVoiceSample(sampleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['voice-samples'] })
      toast.success('Voice sample deleted')
    },
    onError: (error: Error) => {
      toast.error(`Delete failed: ${error.message}`)
    },
  })

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // Connect to WebSocket for clone progress
  const connectToCloneProgress = useCallback((cloneId: string) => {
    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/api/v1/tts/clone-voice/progress/${cloneId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log(`[VoiceClone] WebSocket connected for ${cloneId}`)
    }

    ws.onmessage = (event) => {
      try {
        // Handle ping/pong
        if (event.data === 'ping') {
          ws.send('pong')
          return
        }

        const data = JSON.parse(event.data) as CloneProgress
        console.log('[VoiceClone] Progress:', data)
        setCloneProgress(data)

        // Check for completion
        if (data.status === 'completed' && data.audio_url) {
          console.log(`[VoiceClone] Completed: ${data.audio_url}`)
          // Play the audio
          if (audioRef.current) {
            audioRef.current.src = data.audio_url
            audioRef.current.play()
          }
          // Clean up after a short delay to show completion
          setTimeout(() => {
            setPreviewingSampleId(null)
            setCloneProgress(null)
            ws.close()
          }, 1500)
        } else if (data.status === 'failed' || data.stage === 'error') {
          // Handle error - check both status and stage for backwards compatibility
          toast.error(data.message || 'Voice cloning failed')
          // Keep progress visible briefly to show error
          setTimeout(() => {
            setPreviewingSampleId(null)
            setCloneProgress(null)
            ws.close()
          }, 3000)
        }
      } catch (e) {
        console.error('[VoiceClone] Failed to parse message:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('[VoiceClone] WebSocket error:', error)
    }

    ws.onclose = () => {
      console.log(`[VoiceClone] WebSocket closed for ${cloneId}`)
    }
  }, [])

  // Preview mutation - starts the clone job and returns immediately
  const previewMutation = useMutation({
    mutationFn: ({ sampleId, text }: { sampleId: string; text?: string }) =>
      ttsApi.previewClonedVoice(sampleId, text, language),
    onSuccess: (response) => {
      const cloneId = response.data.clone_id
      if (cloneId) {
        setCloneProgress({
          stage: 'initializing',
          message: 'Starting voice cloning...',
          progress: 0,
          status: 'queued'
        })
        // Connect to WebSocket for progress updates
        connectToCloneProgress(cloneId)
      }
    },
    onError: (error: Error) => {
      toast.error(`Preview failed: ${error.message}`)
      setPreviewingSampleId(null)
      setCloneProgress(null)
    },
  })

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    const validTypes = ['audio/wav', 'audio/mpeg', 'audio/mp3', 'audio/flac', 'audio/ogg', 'audio/m4a', 'audio/x-m4a']
    if (!validTypes.some((t) => file.type.includes(t.split('/')[1]))) {
      toast.error('Please upload a valid audio file (WAV, MP3, FLAC, OGG, or M4A)')
      return
    }

    // Check file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      toast.error('File too large. Maximum size is 10MB.')
      return
    }

    // Show upload form to get name
    setUploadName(file.name.replace(/\.[^/.]+$/, ''))
    setShowUploadForm(true)
  }

  const handleUpload = async () => {
    const file = fileInputRef.current?.files?.[0]
    if (!file || !uploadName.trim()) {
      toast.error('Please provide a name for the voice sample')
      return
    }

    setIsUploading(true)
    try {
      await uploadMutation.mutateAsync({ file, name: uploadName.trim() })
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handlePlaySample = (sample: VoiceSample) => {
    if (playingSampleId === sample.id) {
      // Stop playing
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
      }
      setPlayingSampleId(null)
    } else {
      // Play sample
      if (audioRef.current) {
        audioRef.current.src = sample.audio_url
        audioRef.current.play()
        setPlayingSampleId(sample.id)
      }
    }
  }

  const handlePreviewClone = async (sample: VoiceSample) => {
    setPreviewingSampleId(sample.id)
    try {
      await previewMutation.mutateAsync({
        sampleId: sample.id,
        text: 'Hello, this is a preview of my cloned voice. How does it sound?',
      })
      // Note: previewingSampleId is cleared in the WebSocket handler when clone completes or fails
    } catch (error) {
      // Only clear on immediate error (not WebSocket errors which are handled separately)
      setPreviewingSampleId(null)
      throw error
    }
  }

  const handleSelectSample = (sample: VoiceSample) => {
    if (selectedSampleId === sample.id) {
      onSelectSample?.(null)
    } else {
      onSelectSample?.(sample)
    }
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Audio event handlers
  const handleAudioEnded = () => {
    setPlayingSampleId(null)
  }

  if (compact) {
    return (
      <div className="border border-terminal-border rounded-lg">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between p-3 hover:bg-terminal-bg/50 transition-colors"
          disabled={disabled}
        >
          <div className="flex items-center gap-2 text-sm">
            <Mic className="w-4 h-4 text-accent-primary" />
            <span>Voice Cloning</span>
            {selectedSampleId && (
              <span className="text-xs text-accent-primary bg-accent-primary/10 px-2 py-0.5 rounded">
                Custom voice selected
              </span>
            )}
            {samples.length > 0 && !selectedSampleId && (
              <span className="text-xs text-text-muted">({samples.length} samples)</span>
            )}
          </div>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-text-muted" />
          ) : (
            <ChevronDown className="w-4 h-4 text-text-muted" />
          )}
        </button>

        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="border-t border-terminal-border overflow-hidden"
            >
              <div className="p-3">{renderContent()}</div>
            </motion.div>
          )}
        </AnimatePresence>

        <audio ref={audioRef} onEnded={handleAudioEnded} className="hidden" />
      </div>
    )
  }

  function renderContent() {
    // Show loading state while checking model
    if (isCheckingModel) {
      return (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-text-muted" />
          <span className="ml-2 text-sm text-text-muted">Checking model status...</span>
        </div>
      )
    }

    // Show model download prompt if not ready
    if (!isModelReady) {
      return (
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-500 mb-1">Model Required</p>
              <p className="text-xs text-text-muted mb-3">
                Voice cloning requires downloading the XTTS model (~2GB). This is a one-time download that enables high-quality voice cloning.
              </p>
              <button
                onClick={() => navigate('/settings')}
                className="btn-primary text-sm flex items-center gap-2"
              >
                <Settings className="w-4 h-4" />
                Download Model in Settings
              </button>
            </div>
          </div>
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {/* Info banner */}
        <div className="flex items-start gap-2 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs text-blue-400">
          <Info className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium mb-1">Clone Your Voice</p>
            <p className="text-blue-400/80">
              Upload 5-30 seconds of clear speech. Single speaker, minimal background noise works
              best.
            </p>
          </div>
        </div>

        {/* Upload area */}
        <div className="space-y-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".wav,.mp3,.flac,.ogg,.m4a,audio/*"
            onChange={handleFileSelect}
            className="hidden"
          />

          {!showUploadForm ? (
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || isUploading}
              className={clsx(
                'w-full p-4 border-2 border-dashed rounded-lg transition-colors',
                'flex flex-col items-center gap-2 text-sm',
                disabled
                  ? 'border-terminal-border/50 text-text-muted/50 cursor-not-allowed'
                  : 'border-terminal-border hover:border-accent-primary hover:bg-accent-primary/5 cursor-pointer'
              )}
            >
              <Upload className="w-6 h-6 text-text-muted" />
              <span>Upload Voice Sample</span>
              <span className="text-xs text-text-muted">WAV, MP3, FLAC, OGG, M4A (max 10MB)</span>
            </button>
          ) : (
            <div className="p-4 border border-terminal-border rounded-lg space-y-3">
              <div>
                <label className="block text-xs text-text-muted mb-1">Voice Sample Name</label>
                <input
                  type="text"
                  value={uploadName}
                  onChange={(e) => setUploadName(e.target.value)}
                  placeholder="e.g., My Voice, John's Voice"
                  className="input-primary w-full text-sm"
                  autoFocus
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleUpload}
                  disabled={isUploading || !uploadName.trim()}
                  className="btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      Upload
                    </>
                  )}
                </button>
                <button
                  onClick={() => {
                    setShowUploadForm(false)
                    setUploadName('')
                    if (fileInputRef.current) fileInputRef.current.value = ''
                  }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Voice samples list */}
        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-5 h-5 animate-spin text-text-muted" />
          </div>
        ) : samples.length === 0 ? (
          <div className="text-center py-4 text-text-muted text-sm">
            <User className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No voice samples yet</p>
            <p className="text-xs mt-1">Upload a voice sample to clone</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            <h4 className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-2">
              Your Voice Samples
            </h4>
            {samples.map((sample) => (
              <div
                key={sample.id}
                className={clsx(
                  'px-2.5 py-2 border rounded transition-all cursor-pointer',
                  selectedSampleId === sample.id
                    ? 'border-accent-primary bg-accent-primary/10'
                    : 'border-terminal-border hover:border-accent-primary/50'
                )}
                onClick={() => handleSelectSample(sample)}
              >
                <div className="flex items-center gap-2">
                  {/* Avatar */}
                  <div
                    className={clsx(
                      'w-7 h-7 rounded-full flex items-center justify-center shrink-0',
                      selectedSampleId === sample.id
                        ? 'bg-accent-primary text-white'
                        : 'bg-terminal-border text-text-muted'
                    )}
                  >
                    <User className="w-3.5 h-3.5" />
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium text-sm truncate">{sample.name}</span>
                      {selectedSampleId === sample.id && (
                        <Check className="w-3.5 h-3.5 text-accent-primary shrink-0" />
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-text-muted">
                      <span className="flex items-center gap-0.5">
                        <Clock className="w-2.5 h-2.5" />
                        {formatDuration(sample.duration)}
                      </span>
                      <span className="flex items-center gap-0.5">
                        <FileAudio className="w-2.5 h-2.5" />
                        {formatFileSize(sample.file_size)}
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => handlePlaySample(sample)}
                      className="p-1.5 hover:bg-terminal-border rounded transition-colors"
                      title="Play original"
                    >
                      {playingSampleId === sample.id ? (
                        <Pause className="w-3.5 h-3.5 text-accent-primary" />
                      ) : (
                        <Play className="w-3.5 h-3.5 text-text-muted" />
                      )}
                    </button>
                    <button
                      onClick={() => handlePreviewClone(sample)}
                      disabled={previewingSampleId !== null}
                      className="p-1.5 hover:bg-terminal-border rounded transition-colors"
                      title="Preview clone"
                    >
                      {previewingSampleId === sample.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-primary" />
                      ) : (
                        <Mic className="w-3.5 h-3.5 text-text-muted" />
                      )}
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`Delete "${sample.name}"?`)) {
                          deleteMutation.mutate(sample.id)
                          if (selectedSampleId === sample.id) {
                            onSelectSample?.(null)
                          }
                        }
                      }}
                      className="p-1.5 hover:bg-red-500/10 rounded transition-colors text-text-muted hover:text-red-400"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Voice cloning progress */}
        <AnimatePresence>
          {cloneProgress && previewingSampleId && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className={clsx(
                "p-4 border rounded-lg",
                cloneProgress.stage === 'error' || cloneProgress.status === 'failed'
                  ? 'bg-red-500/10 border-red-500/30'
                  : cloneProgress.status === 'completed'
                    ? 'bg-green-500/10 border-green-500/30'
                    : 'bg-purple-500/10 border-purple-500/30'
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {cloneProgress.status === 'completed' ? (
                    <Check className="w-4 h-4 text-green-400" />
                  ) : cloneProgress.stage === 'error' || cloneProgress.status === 'failed' ? (
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                  ) : (
                    <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                  )}
                  <span className={clsx(
                    "text-sm font-medium",
                    cloneProgress.stage === 'error' || cloneProgress.status === 'failed'
                      ? 'text-red-400'
                      : cloneProgress.status === 'completed'
                        ? 'text-green-400'
                        : 'text-purple-400'
                  )}>
                    {cloneProgress.stage === 'error' ? 'Error' :
                     cloneProgress.stage === 'loading' ? 'Loading Model' :
                     cloneProgress.stage === 'generating' ? 'Generating Audio' :
                     cloneProgress.stage === 'converting' ? 'Converting Audio' :
                     cloneProgress.stage === 'completed' ? 'Completed' :
                     cloneProgress.stage === 'initializing' ? 'Initializing' :
                     'Voice Cloning'}
                  </span>
                </div>
                {cloneProgress.stage !== 'error' && (
                  <span className="text-xs text-text-muted">{cloneProgress.progress}%</span>
                )}
              </div>
              {cloneProgress.stage !== 'error' && cloneProgress.status !== 'failed' && (
                <div className="w-full bg-terminal-border rounded-full h-2 mb-2">
                  <motion.div
                    className={clsx(
                      "h-2 rounded-full",
                      cloneProgress.status === 'completed' ? 'bg-green-400' : 'bg-purple-500'
                    )}
                    initial={{ width: 0 }}
                    animate={{ width: `${cloneProgress.progress}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              )}
              <p className={clsx(
                "text-xs",
                cloneProgress.stage === 'error' || cloneProgress.status === 'failed'
                  ? 'text-red-400'
                  : 'text-text-muted'
              )}>
                {cloneProgress.message}
              </p>
              {cloneProgress.stage === 'loading' && (
                <p className="text-xs text-purple-400/70 mt-1">
                  First-time model loading may take 1-2 minutes...
                </p>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Selected sample info */}
        {selectedSampleId && !cloneProgress && (
          <div className="p-3 bg-accent-primary/10 border border-accent-primary/30 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-accent-primary">
              <Check className="w-4 h-4" />
              <span>
                Using cloned voice:{' '}
                <strong>{samples.find((s) => s.id === selectedSampleId)?.name}</strong>
              </span>
            </div>
            <p className="text-xs text-text-muted mt-1">
              This voice will be used instead of the selected TTS voice.
            </p>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {renderContent()}
      <audio ref={audioRef} onEnded={handleAudioEnded} className="hidden" />
    </div>
  )
}

/**
 * VoiceCloningBanner - Small banner to show when Coqui is active
 */
export function VoiceCloningBanner({ provider }: { provider?: string }) {
  if (provider?.toLowerCase() !== 'coqui') {
    return null
  }

  return (
    <div className="flex items-center gap-2 p-2 bg-purple-500/10 border border-purple-500/20 rounded text-xs text-purple-400">
      <Mic className="w-3.5 h-3.5" />
      <span>Voice cloning available with Coqui TTS</span>
    </div>
  )
}
