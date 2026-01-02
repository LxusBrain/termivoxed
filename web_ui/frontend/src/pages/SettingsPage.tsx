import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Settings,
  Server,
  Database,
  Trash2,
  Check,
  Loader2,
  HardDrive,
  Cpu,
  Save,
  AlertTriangle,
  X,
  RotateCcw,
  Cloud,
  Monitor,
  Shield,
  Mic,
  FolderOpen,
  RefreshCw,
  Folder,
  ChevronUp,
  Circle,
} from 'lucide-react'
import { settingsApi, llmApi, ttsApi, exportApi, modelsApi, type TTSProviderInfo, type VoiceCloningModel, type ModelDownloadProgress, type AppConfigUpdate } from '../api/client'
import { useConsentStore } from '../stores/consentStore'
import { useDebugStore } from '../stores/debugStore'
import { Bug, Download, Terminal } from 'lucide-react'
import toast from 'react-hot-toast'
import clsx from 'clsx'

// Track which fields have unsaved changes
interface DirtyFields {
  openaiKey: boolean
  anthropicKey: boolean
  googleKey: boolean
  huggingfaceKey: boolean
  ollamaEndpoint: boolean
  azureKey: boolean
  azureEndpoint: boolean
  azureDeployment: boolean
  azureApiVersion: boolean
  awsAccessKey: boolean
  awsSecretKey: boolean
  awsRegion: boolean
  customEndpoint: boolean
  customApiKey: boolean
  defaultModel: boolean
}

function SettingsSection({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: React.ComponentType<{ className?: string }>
  children: React.ReactNode
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="console-card overflow-hidden"
    >
      <div className="flex items-center gap-2 p-4 border-b border-terminal-border bg-terminal-bg/50">
        <Icon className="w-5 h-5 text-accent-red" />
        <h3 className="font-medium">{title}</h3>
      </div>
      <div className="p-4">{children}</div>
    </motion.div>
  )
}

export default function SettingsPage() {
  const queryClient = useQueryClient()

  // Fetch settings
  useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })

  const { data: llmSettingsData } = useQuery({
    queryKey: ['llm-settings'],
    queryFn: () => settingsApi.getLLM(),
  })

  const { data: systemData } = useQuery({
    queryKey: ['system-info'],
    queryFn: () => settingsApi.getSystem(),
  })

  const { data: llmHealth } = useQuery({
    queryKey: ['llm-health'],
    queryFn: () => llmApi.checkHealth(),
  })

  const { data: ttsStatus } = useQuery({
    queryKey: ['tts-status'],
    queryFn: () => ttsApi.checkConnectivity(),
  })

  // TTS Providers query
  const { data: ttsProvidersData, isLoading: isLoadingProviders } = useQuery({
    queryKey: ['tts-providers'],
    queryFn: () => ttsApi.getProviders(),
  })

  // Consent store for TTS privacy settings
  const { hasTTSConsent, openTTSConsentModal, ttsConsentStatus } = useConsentStore()

  // Set default TTS provider mutation
  const setDefaultProviderMutation = useMutation({
    mutationFn: (provider: string) => ttsApi.setDefaultProvider(provider),
    onSuccess: (_, provider) => {
      toast.success(`Default TTS provider set to ${provider}`)
      queryClient.invalidateQueries({ queryKey: ['tts-providers'] })
    },
    onError: () => {
      toast.error('Failed to set TTS provider')
    },
  })

  // State for editable fields
  const [openaiKey, setOpenaiKey] = useState('')
  const [anthropicKey, setAnthropicKey] = useState('')
  const [googleKey, setGoogleKey] = useState('')
  const [huggingfaceKey, setHuggingfaceKey] = useState('')
  const [huggingfaceProvider, setHuggingfaceProvider] = useState('auto')
  const [ollamaEndpoint, setOllamaEndpoint] = useState('http://localhost:11434')

  // Azure OpenAI state
  const [azureKey, setAzureKey] = useState('')
  const [azureEndpoint, setAzureEndpoint] = useState('')
  const [azureDeployment, setAzureDeployment] = useState('')
  const [azureApiVersion, setAzureApiVersion] = useState('2024-05-01-preview')

  // AWS Bedrock state
  const [awsAccessKey, setAwsAccessKey] = useState('')
  const [awsSecretKey, setAwsSecretKey] = useState('')
  const [awsRegion, setAwsRegion] = useState('us-east-1')

  // Custom endpoint state
  const [customEndpoint, setCustomEndpoint] = useState('')
  const [customApiKey, setCustomApiKey] = useState('')

  // Default provider state
  const [defaultProvider, setDefaultProvider] = useState('ollama')
  const [defaultModel, setDefaultModel] = useState('')

  // Voice Cloning Model Download state
  const [activeDownloadId, setActiveDownloadId] = useState<string | null>(null)
  const [downloadProgress, setDownloadProgress] = useState<ModelDownloadProgress | null>(null)
  const [downloadWs, setDownloadWs] = useState<WebSocket | null>(null)

  // Fetch voice cloning models
  const { data: voiceCloningModelsData, refetch: refetchModels } = useQuery({
    queryKey: ['voice-cloning-models'],
    queryFn: () => modelsApi.getVoiceCloningModels(),
    staleTime: 30 * 1000,
  })

  const voiceCloningModels: VoiceCloningModel[] = voiceCloningModelsData?.data?.models || []

  // Start model download
  const startModelDownload = async (modelId: string) => {
    try {
      const response = await modelsApi.startDownload(modelId)
      const { download_id } = response.data

      setActiveDownloadId(download_id)
      setDownloadProgress({
        type: 'progress',
        stage: 'initializing',
        message: 'Starting download...',
        progress: 0,
      })

      // Connect to WebSocket for progress
      const ws = modelsApi.createProgressWebSocket(download_id)

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'progress' || data.type === 'status') {
            setDownloadProgress(data as ModelDownloadProgress)
          } else if (data.type === 'complete') {
            setDownloadProgress({
              type: 'complete',
              stage: 'complete',
              message: 'Model downloaded successfully!',
              progress: 100,
            })
            toast.success('Voice cloning model downloaded successfully!')
            refetchModels()
            setTimeout(() => {
              setActiveDownloadId(null)
              setDownloadProgress(null)
            }, 2000)
          } else if (data.type === 'error') {
            setDownloadProgress({
              type: 'error',
              stage: 'error',
              message: data.message || 'Download failed',
              progress: 0,
              details: data.details,
            })
            toast.error(data.message || 'Model download failed')
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      ws.onerror = () => {
        toast.error('Connection error during download')
        setDownloadProgress({
          type: 'error',
          stage: 'error',
          message: 'Connection lost',
          progress: 0,
        })
      }

      ws.onclose = () => {
        setDownloadWs(null)
        refetchModels()
      }

      setDownloadWs(ws)
    } catch (error) {
      toast.error('Failed to start model download')
      console.error('Download error:', error)
    }
  }

  // Cancel model download
  const cancelModelDownload = async () => {
    if (activeDownloadId) {
      try {
        await modelsApi.cancelDownload(activeDownloadId)
        toast.success('Download cancelled')
      } catch (error) {
        console.error('Failed to cancel download:', error)
      }
    }
    if (downloadWs) {
      downloadWs.close()
    }
    setActiveDownloadId(null)
    setDownloadProgress(null)
    refetchModels()
  }

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (downloadWs) {
        downloadWs.close()
      }
    }
  }, [downloadWs])

  // Track dirty (unsaved) fields
  const [dirtyFields, setDirtyFields] = useState<DirtyFields>({
    openaiKey: false,
    anthropicKey: false,
    googleKey: false,
    huggingfaceKey: false,
    ollamaEndpoint: false,
    azureKey: false,
    azureEndpoint: false,
    azureDeployment: false,
    azureApiVersion: false,
    awsAccessKey: false,
    awsSecretKey: false,
    awsRegion: false,
    customEndpoint: false,
    customApiKey: false,
    defaultModel: false,
  })

  // Mark field as dirty when user changes it
  const markDirty = (field: keyof DirtyFields) => {
    setDirtyFields(prev => ({ ...prev, [field]: true }))
  }

  // Clear dirty flag for a field
  const clearDirty = (field: keyof DirtyFields) => {
    setDirtyFields(prev => ({ ...prev, [field]: false }))
  }

  // Clear multiple dirty flags
  const clearDirtyFields = (fields: (keyof DirtyFields)[]) => {
    setDirtyFields(prev => {
      const updated = { ...prev }
      fields.forEach(f => updated[f] = false)
      return updated
    })
  }

  // Check if any field has unsaved changes
  const hasUnsavedChanges = useMemo(() => {
    return Object.values(dirtyFields).some(v => v)
  }, [dirtyFields])

  // Get list of unsaved field names for display
  const unsavedFieldNames = useMemo(() => {
    const names: string[] = []
    if (dirtyFields.openaiKey) names.push('OpenAI API Key')
    if (dirtyFields.anthropicKey) names.push('Anthropic API Key')
    if (dirtyFields.googleKey) names.push('Google API Key')
    if (dirtyFields.huggingfaceKey) names.push('HuggingFace Token')
    if (dirtyFields.ollamaEndpoint) names.push('Ollama Endpoint')
    if (dirtyFields.azureKey) names.push('Azure API Key')
    if (dirtyFields.azureEndpoint) names.push('Azure Endpoint')
    if (dirtyFields.azureDeployment) names.push('Azure Deployment')
    if (dirtyFields.azureApiVersion) names.push('Azure API Version')
    if (dirtyFields.awsAccessKey) names.push('AWS Access Key')
    if (dirtyFields.awsSecretKey) names.push('AWS Secret Key')
    if (dirtyFields.awsRegion) names.push('AWS Region')
    if (dirtyFields.customEndpoint) names.push('Custom Endpoint')
    if (dirtyFields.customApiKey) names.push('Custom API Key')
    if (dirtyFields.defaultModel) names.push('Default Model')
    return names
  }, [dirtyFields])

  // Discard changes for a specific field
  const discardField = (field: keyof DirtyFields) => {
    switch (field) {
      case 'openaiKey': setOpenaiKey(''); break
      case 'anthropicKey': setAnthropicKey(''); break
      case 'googleKey': setGoogleKey(''); break
      case 'huggingfaceKey': setHuggingfaceKey(''); break
      case 'ollamaEndpoint': setOllamaEndpoint(llmSettings?.ollama_endpoint || 'http://localhost:11434'); break
      case 'azureKey': setAzureKey(''); break
      case 'azureEndpoint': setAzureEndpoint(''); break
      case 'azureDeployment': setAzureDeployment(''); break
      case 'azureApiVersion': setAzureApiVersion('2024-05-01-preview'); break
      case 'awsAccessKey': setAwsAccessKey(''); break
      case 'awsSecretKey': setAwsSecretKey(''); break
      case 'awsRegion': setAwsRegion(llmSettings?.aws_region || 'us-east-1'); break
      case 'customEndpoint': setCustomEndpoint(''); break
      case 'customApiKey': setCustomApiKey(''); break
      case 'defaultModel': setDefaultModel(''); break
    }
    clearDirty(field)
  }

  // Discard all unsaved changes
  const discardAllChanges = () => {
    setOpenaiKey('')
    setAnthropicKey('')
    setGoogleKey('')
    setHuggingfaceKey('')
    setOllamaEndpoint(llmSettings?.ollama_endpoint || 'http://localhost:11434')
    setAzureKey('')
    setAzureEndpoint('')
    setAzureDeployment('')
    setAzureApiVersion('2024-05-01-preview')
    setAwsAccessKey('')
    setAwsSecretKey('')
    setAwsRegion(llmSettings?.aws_region || 'us-east-1')
    setCustomEndpoint('')
    setCustomApiKey('')
    setDefaultModel('')
    setDirtyFields({
      openaiKey: false,
      anthropicKey: false,
      googleKey: false,
      huggingfaceKey: false,
      ollamaEndpoint: false,
      azureKey: false,
      azureEndpoint: false,
      azureDeployment: false,
      azureApiVersion: false,
      awsAccessKey: false,
      awsSecretKey: false,
      awsRegion: false,
      customEndpoint: false,
      customApiKey: false,
      defaultModel: false,
    })
    toast.success('All changes discarded')
  }

  // Warn user before leaving page with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault()
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?'
        return e.returnValue
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedChanges])

  // Mutations
  const updateLLMMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => settingsApi.updateLLM(data),
    onSuccess: () => {
      toast.success('LLM settings updated')
      queryClient.invalidateQueries({ queryKey: ['llm-settings'] })
    },
    onError: () => {
      toast.error('Failed to update settings')
    },
  })

  const clearCacheMutation = useMutation({
    mutationFn: () => settingsApi.clearCache(),
    onSuccess: (response) => {
      toast.success(`Cache cleared: ${response.data.space_freed_mb}MB freed`)
      queryClient.invalidateQueries({ queryKey: ['system-info'] })
    },
  })

  const clearTempMutation = useMutation({
    mutationFn: () => settingsApi.clearTemp(),
    onSuccess: (response) => {
      toast.success(`Temp files cleared: ${response.data.space_freed_mb}MB freed`)
      queryClient.invalidateQueries({ queryKey: ['system-info'] })
    },
  })

  const llmSettings = llmSettingsData?.data
  const system = systemData?.data
  const health = llmHealth?.data
  const tts = ttsStatus?.data

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-text-muted text-sm mt-1">
          Configure TermiVoxed preferences and integrations
        </p>
      </div>

      {/* Unsaved Changes Banner */}
      <AnimatePresence>
        {hasUnsavedChanges && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-yellow-500/90 text-black px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 max-w-xl"
          >
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-sm">Unsaved Changes</p>
              <p className="text-xs opacity-80">
                {unsavedFieldNames.slice(0, 3).join(', ')}
                {unsavedFieldNames.length > 3 && ` +${unsavedFieldNames.length - 3} more`}
              </p>
            </div>
            <button
              onClick={discardAllChanges}
              className="p-1.5 hover:bg-black/10 rounded transition-colors"
              title="Discard all changes"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={() => {
                // Close banner without discarding
                toast('Save each field using the save button next to it')
              }}
              className="p-1.5 hover:bg-black/10 rounded transition-colors"
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* System Status */}
      <SettingsSection title="System Status" icon={Server}>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="console-card-elevated p-3">
            <div className="flex items-center gap-2 mb-2">
              <div
                className={clsx(
                  'status-dot',
                  system?.ffmpeg_available ? 'status-dot-success' : 'status-dot-error'
                )}
              />
              <span className="text-sm font-medium">FFmpeg</span>
            </div>
            <p className="text-xs text-text-muted">
              {system?.ffmpeg_available ? 'Available' : 'Not found'}
            </p>
          </div>

          <div className="console-card-elevated p-3">
            <div className="flex items-center gap-2 mb-2">
              <div
                className={clsx(
                  'status-dot',
                  health?.ollama_available ? 'status-dot-success' : 'status-dot-error'
                )}
              />
              <span className="text-sm font-medium">Ollama</span>
            </div>
            <p className="text-xs text-text-muted">
              {health?.ollama_available
                ? `${health.ollama_models?.length || 0} models`
                : 'Not running'}
            </p>
          </div>

          <div className="console-card-elevated p-3">
            <div className="flex items-center gap-2 mb-2">
              <div
                className={clsx(
                  'status-dot',
                  tts?.direct_connection || tts?.proxy_connection
                    ? 'status-dot-success'
                    : 'status-dot-error'
                )}
              />
              <span className="text-sm font-medium">TTS Service</span>
            </div>
            <p className="text-xs text-text-muted">
              {tts?.direct_connection
                ? 'Direct connection'
                : tts?.proxy_connection
                ? 'Via proxy'
                : 'Unavailable'}
            </p>
          </div>

          <div className="console-card-elevated p-3">
            <div className="flex items-center gap-2 mb-2">
              <HardDrive className="w-4 h-4 text-text-muted" />
              <span className="text-sm font-medium">Storage</span>
            </div>
            <p className="text-xs text-text-muted">
              {system?.disk_free_gb?.toFixed(1)}GB free of {system?.disk_total_gb?.toFixed(0)}GB
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-text-muted">Platform:</span>{' '}
            <span className="font-mono">{system?.platform === 'Darwin' ? 'macOS' : system?.platform}</span>
          </div>
          <div>
            <span className="text-text-muted">Python:</span>{' '}
            <span className="font-mono">{system?.python_version}</span>
          </div>
          <div>
            <span className="text-text-muted">Projects:</span>{' '}
            <span className="font-mono">{system?.project_count}</span>
          </div>
        </div>
      </SettingsSection>

      {/* TTS Providers */}
      <SettingsSection title="Text-to-Speech Providers" icon={Mic}>
        <div className="space-y-4">
          {/* Provider Selection */}
          <div className="grid grid-cols-2 gap-4">
            {isLoadingProviders ? (
              <div className="col-span-2 flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-accent-red" />
              </div>
            ) : (
              ttsProvidersData?.data?.providers?.map((provider: TTSProviderInfo) => (
                <div
                  key={provider.name}
                  className={clsx(
                    'console-card-elevated p-4 cursor-pointer transition-all',
                    provider.is_default
                      ? 'ring-1 ring-accent-red/60 border-accent-red/40 shadow-[0_0_12px_rgba(239,68,68,0.25)]'
                      : 'hover:border-accent-red/50'
                  )}
                  onClick={() => {
                    if (!provider.is_default) {
                      setDefaultProviderMutation.mutate(provider.name)
                    }
                  }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {provider.is_local ? (
                        <Monitor className="w-5 h-5 text-text-secondary" />
                      ) : (
                        <Cloud className="w-5 h-5 text-text-secondary" />
                      )}
                      <span className="font-medium">{provider.display_name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {provider.is_default && (
                        <span className="px-2 py-0.5 text-xs bg-accent-red text-white rounded">
                          Default
                        </span>
                      )}
                      <div
                        className={clsx(
                          'status-dot',
                          provider.available ? 'status-dot-success' : 'status-dot-error'
                        )}
                      />
                    </div>
                  </div>

                  <p className="text-xs text-text-muted mb-3">{provider.description}</p>

                  <div className="flex flex-wrap gap-1.5">
                    {provider.is_local ? (
                      <span className="px-2 py-0.5 text-xs bg-terminal-bg border border-terminal-border text-text-secondary rounded font-mono">
                        LOCAL
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-xs bg-terminal-bg border border-terminal-border text-text-secondary rounded font-mono">
                        CLOUD
                      </span>
                    )}
                    {provider.requires_consent && (
                      <span className="px-2 py-0.5 text-xs bg-terminal-bg border border-terminal-border text-text-muted rounded font-mono">
                        CONSENT
                      </span>
                    )}
                    {provider.supports_word_timing && (
                      <span className="px-2 py-0.5 text-xs bg-terminal-bg border border-terminal-border text-text-muted rounded font-mono">
                        WORD-TIMING
                      </span>
                    )}
                    {provider.supports_voice_cloning && (
                      <span className="px-2 py-0.5 text-xs bg-accent-red/10 border border-accent-red/30 text-accent-red rounded font-mono">
                        VOICE-CLONE
                      </span>
                    )}
                    {!provider.available && (
                      <span className="px-2 py-0.5 text-xs bg-terminal-bg border border-red-500/30 text-red-400 rounded font-mono">
                        UNAVAILABLE
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Privacy Consent Status */}
          <div className="console-card-elevated p-4 border-l-2 border-l-accent-red/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-text-secondary" />
                <span className="font-medium">TTS Privacy Consent</span>
              </div>
              <span
                className={clsx(
                  'px-2 py-0.5 text-xs rounded font-mono',
                  hasTTSConsent
                    ? 'bg-terminal-bg border border-terminal-border text-text-secondary'
                    : ttsConsentStatus === 'denied'
                    ? 'bg-terminal-bg border border-red-500/30 text-red-400'
                    : 'bg-terminal-bg border border-terminal-border text-text-muted'
                )}
              >
                {hasTTSConsent ? 'GRANTED' : ttsConsentStatus === 'denied' ? 'DECLINED' : 'PENDING'}
              </span>
            </div>
            <p className="text-xs text-text-muted mb-3">
              Cloud TTS providers (like Microsoft Edge TTS) send your script text to external servers.
              You can use local providers like Coqui TTS for complete privacy.
            </p>
            <button
              onClick={() => openTTSConsentModal()}
              className="btn-secondary text-sm"
            >
              {hasTTSConsent ? 'Review Consent Settings' : 'Configure Consent'}
            </button>
          </div>

          {/* Provider Info */}
          <div className="text-xs text-text-muted font-mono">
            <p>
              <span className="text-text-secondary">Edge TTS:</span> High-quality Microsoft voices with word timing. Requires internet.
            </p>
            <p className="mt-1">
              <span className="text-text-secondary">Coqui TTS:</span> Local processing, no data leaves your device. GPU recommended.
            </p>
          </div>
        </div>
      </SettingsSection>

      {/* Voice Cloning Models */}
      <SettingsSection title="Voice Cloning Models" icon={Download}>
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            Voice cloning requires downloading AI models. These are large files (~2GB) but only need to be downloaded once.
          </p>

          {voiceCloningModels.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-accent-red" />
            </div>
          ) : (
            voiceCloningModels.map((model) => (
              <div
                key={model.model_id}
                className="console-card-elevated p-4"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{model.name}</span>
                      {model.recommended && (
                        <span className="px-2 py-0.5 text-xs bg-accent-red/10 border border-accent-red/30 text-accent-red rounded">
                          Recommended
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-text-muted mt-1">{model.description}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {model.downloaded ? (
                      <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-500 rounded font-mono">
                        READY
                      </span>
                    ) : model.downloading ? (
                      <span className="px-2 py-0.5 text-xs bg-accent-red/20 text-accent-red rounded font-mono">
                        DOWNLOADING
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-xs bg-terminal-bg border border-terminal-border text-text-muted rounded font-mono">
                        NOT INSTALLED
                      </span>
                    )}
                  </div>
                </div>

                {/* Model Info */}
                <div className="flex flex-wrap gap-2 mb-3 text-xs">
                  <span className="px-2 py-0.5 bg-terminal-bg border border-terminal-border text-text-secondary rounded font-mono">
                    {model.size_mb} MB
                  </span>
                  <span className="px-2 py-0.5 bg-terminal-bg border border-terminal-border text-text-secondary rounded font-mono">
                    {model.languages.length} languages
                  </span>
                </div>

                {/* Download Progress */}
                {(model.downloading || (activeDownloadId && downloadProgress)) && (
                  <div className="mb-3">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-text-muted font-mono">
                        {downloadProgress?.stage || 'downloading'}: {downloadProgress?.message || 'Processing...'}
                      </span>
                      <span className="text-text-secondary font-mono">
                        {downloadProgress?.progress || 0}%
                      </span>
                    </div>
                    <div className="w-full bg-terminal-bg rounded-full h-2 overflow-hidden">
                      <motion.div
                        className={clsx(
                          'h-full rounded-full',
                          downloadProgress?.type === 'error' ? 'bg-red-500' : 'bg-accent-red'
                        )}
                        initial={{ width: 0 }}
                        animate={{ width: `${downloadProgress?.progress || 0}%` }}
                        transition={{ duration: 0.3 }}
                      />
                    </div>
                    {downloadProgress?.speed_mbps && (
                      <div className="flex justify-between text-xs text-text-muted mt-1 font-mono">
                        <span>{downloadProgress.downloaded_mb?.toFixed(1)} / {downloadProgress.total_mb?.toFixed(1)} MB</span>
                        <span>{downloadProgress.speed_mbps?.toFixed(1)} MB/s</span>
                        {downloadProgress.eta_seconds && (
                          <span>ETA: {Math.round(downloadProgress.eta_seconds)}s</span>
                        )}
                      </div>
                    )}
                    {downloadProgress?.type === 'error' && (
                      <p className="text-xs text-red-400 mt-1 font-mono">
                        {downloadProgress.details || downloadProgress.message}
                      </p>
                    )}
                  </div>
                )}

                {/* Error Message */}
                {model.error && !model.downloading && (
                  <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded">
                    <p className="text-xs text-red-400 font-mono">{model.error}</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  {model.downloaded ? (
                    <button
                      className="btn-secondary text-sm flex items-center gap-1"
                      disabled
                    >
                      <Check className="w-4 h-4" />
                      Installed
                    </button>
                  ) : model.downloading || activeDownloadId ? (
                    <button
                      onClick={cancelModelDownload}
                      className="btn-secondary text-sm flex items-center gap-1 text-red-400 border-red-400/30 hover:bg-red-500/10"
                    >
                      <X className="w-4 h-4" />
                      Cancel
                    </button>
                  ) : (
                    <button
                      onClick={() => startModelDownload(model.model_id)}
                      className="btn-primary text-sm flex items-center gap-1"
                    >
                      <Download className="w-4 h-4" />
                      Download ({model.size_mb} MB)
                    </button>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Info */}
          <div className="text-xs text-text-muted font-mono">
            <p>
              <span className="text-text-secondary">Note:</span> Models are stored locally and persist across sessions.
            </p>
            <p className="mt-1">
              <span className="text-text-secondary">Tip:</span> Use a stable internet connection for large downloads.
            </p>
          </div>
        </div>
      </SettingsSection>

      {/* LLM Providers */}
      <SettingsSection title="AI/LLM Providers" icon={Cpu}>
        <div className="space-y-4">
          {/* Provider Status Overview */}
          <div className="grid grid-cols-4 gap-2 mb-4">
            <div className={clsx('p-2 rounded text-center text-xs flex items-center justify-center gap-1', health?.ollama_available ? 'bg-green-500/20 text-green-500' : 'bg-terminal-bg text-text-muted')}>
              Ollama {health?.ollama_available ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </div>
            <div className={clsx('p-2 rounded text-center text-xs flex items-center justify-center gap-1', health?.openai_configured ? 'bg-green-500/20 text-green-500' : 'bg-terminal-bg text-text-muted')}>
              OpenAI {health?.openai_configured ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </div>
            <div className={clsx('p-2 rounded text-center text-xs flex items-center justify-center gap-1', health?.anthropic_configured ? 'bg-green-500/20 text-green-500' : 'bg-terminal-bg text-text-muted')}>
              Anthropic {health?.anthropic_configured ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </div>
            <div className={clsx('p-2 rounded text-center text-xs flex items-center justify-center gap-1', health?.azure_openai_configured ? 'bg-green-500/20 text-green-500' : 'bg-terminal-bg text-text-muted')}>
              Azure {health?.azure_openai_configured ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </div>
            <div className={clsx('p-2 rounded text-center text-xs flex items-center justify-center gap-1', health?.google_configured ? 'bg-green-500/20 text-green-500' : 'bg-terminal-bg text-text-muted')}>
              Google {health?.google_configured ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </div>
            <div className={clsx('p-2 rounded text-center text-xs flex items-center justify-center gap-1', health?.aws_bedrock_configured ? 'bg-green-500/20 text-green-500' : 'bg-terminal-bg text-text-muted')}>
              AWS {health?.aws_bedrock_configured ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </div>
            <div className={clsx('p-2 rounded text-center text-xs flex items-center justify-center gap-1', health?.huggingface_configured ? 'bg-green-500/20 text-green-500' : 'bg-terminal-bg text-text-muted')}>
              HuggingFace {health?.huggingface_configured ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </div>
            <div className={clsx('p-2 rounded text-center text-xs flex items-center justify-center gap-1', health?.langchain_available ? 'bg-blue-500/20 text-blue-500' : 'bg-terminal-bg text-text-muted')}>
              LangChain {health?.langchain_available ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </div>
          </div>

          {/* Ollama */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">Ollama (Local)</span>
                <div
                  className={clsx(
                    'status-dot',
                    health?.ollama_available ? 'status-dot-success' : 'status-dot-error'
                  )}
                />
              </div>
              <span className="text-xs text-text-muted">Free, runs locally</span>
            </div>

            <div>
              <label className="section-header">Endpoint</label>
              <div className="relative">
                <input
                  type="text"
                  value={ollamaEndpoint}
                  onChange={(e) => {
                    setOllamaEndpoint(e.target.value)
                    markDirty('ollamaEndpoint')
                  }}
                  className={clsx(
                    'input-base w-full font-mono pr-20',
                    dirtyFields.ollamaEndpoint && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
                {dirtyFields.ollamaEndpoint && (
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                    <button
                      onClick={() => {
                        updateLLMMutation.mutate(
                          { ollama_endpoint: ollamaEndpoint },
                          { onSuccess: () => clearDirty('ollamaEndpoint') }
                        )
                      }}
                      className="p-1 bg-green-500 hover:bg-green-600 rounded text-white"
                      title="Save"
                    >
                      <Save className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => discardField('ollamaEndpoint')}
                      className="p-1 bg-red-500/80 hover:bg-red-600 rounded text-white"
                      title="Discard"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            </div>

            {health?.ollama_models && health.ollama_models.length > 0 && (
              <div className="mt-3">
                <span className="section-header">Available Models</span>
                <div className="flex flex-wrap gap-2 mt-1">
                  {health.ollama_models.map((model: string) => (
                    <span
                      key={model}
                      className="text-xs bg-terminal-bg px-2 py-1 rounded font-mono"
                    >
                      {model}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* OpenAI */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">OpenAI</span>
                {health?.openai_configured && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">GPT-4o, GPT-4, GPT-3.5</span>
            </div>

            <div>
              <label className="section-header">API Key</label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => {
                    setOpenaiKey(e.target.value)
                    markDirty('openaiKey')
                  }}
                  placeholder={llmSettings?.openai_api_key ? '••••••••' : 'Enter API key'}
                  className={clsx(
                    'input-base flex-1 font-mono',
                    dirtyFields.openaiKey && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
                <button
                  onClick={() => {
                    updateLLMMutation.mutate(
                      { openai_api_key: openaiKey },
                      { onSuccess: () => { clearDirty('openaiKey'); setOpenaiKey('') } }
                    )
                  }}
                  disabled={!openaiKey}
                  className={clsx(
                    'btn-secondary px-3',
                    dirtyFields.openaiKey && 'bg-yellow-500/20 border-yellow-500 text-yellow-500'
                  )}
                >
                  <Save className="w-4 h-4" />
                </button>
                {dirtyFields.openaiKey && (
                  <button
                    onClick={() => discardField('openaiKey')}
                    className="btn-secondary px-3 bg-red-500/20 border-red-500 text-red-500"
                    title="Discard"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Anthropic */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">Anthropic</span>
                {health?.anthropic_configured && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">Claude 3.5, Claude 3</span>
            </div>

            <div>
              <label className="section-header">API Key</label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => {
                    setAnthropicKey(e.target.value)
                    markDirty('anthropicKey')
                  }}
                  placeholder={llmSettings?.anthropic_api_key ? '••••••••' : 'Enter API key'}
                  className={clsx(
                    'input-base flex-1 font-mono',
                    dirtyFields.anthropicKey && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
                <button
                  onClick={() => {
                    updateLLMMutation.mutate(
                      { anthropic_api_key: anthropicKey },
                      { onSuccess: () => { clearDirty('anthropicKey'); setAnthropicKey('') } }
                    )
                  }}
                  disabled={!anthropicKey}
                  className={clsx(
                    'btn-secondary px-3',
                    dirtyFields.anthropicKey && 'bg-yellow-500/20 border-yellow-500 text-yellow-500'
                  )}
                >
                  <Save className="w-4 h-4" />
                </button>
                {dirtyFields.anthropicKey && (
                  <button
                    onClick={() => discardField('anthropicKey')}
                    className="btn-secondary px-3 bg-red-500/20 border-red-500 text-red-500"
                    title="Discard"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Google */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">Google</span>
                {health?.google_configured && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">Gemini Pro, Flash</span>
            </div>

            <div>
              <label className="section-header">API Key</label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={googleKey}
                  onChange={(e) => {
                    setGoogleKey(e.target.value)
                    markDirty('googleKey')
                  }}
                  placeholder={llmSettings?.google_api_key ? '••••••••' : 'Enter API key'}
                  className={clsx(
                    'input-base flex-1 font-mono',
                    dirtyFields.googleKey && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
                <button
                  onClick={() => {
                    updateLLMMutation.mutate(
                      { google_api_key: googleKey },
                      { onSuccess: () => { clearDirty('googleKey'); setGoogleKey('') } }
                    )
                  }}
                  disabled={!googleKey}
                  className={clsx(
                    'btn-secondary px-3',
                    dirtyFields.googleKey && 'bg-yellow-500/20 border-yellow-500 text-yellow-500'
                  )}
                >
                  <Save className="w-4 h-4" />
                </button>
                {dirtyFields.googleKey && (
                  <button
                    onClick={() => discardField('googleKey')}
                    className="btn-secondary px-3 bg-red-500/20 border-red-500 text-red-500"
                    title="Discard"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* HuggingFace */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">HuggingFace</span>
                {health?.huggingface_configured && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">Open models</span>
            </div>

            <div className="space-y-3">
              <div>
                <label className="section-header">API Token</label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={huggingfaceKey}
                    onChange={(e) => {
                      setHuggingfaceKey(e.target.value)
                      markDirty('huggingfaceKey')
                    }}
                    placeholder={llmSettings?.huggingface_api_key ? '••••••••' : 'Enter API token (hf_...)'}
                    className={clsx(
                      'input-base flex-1 font-mono',
                      dirtyFields.huggingfaceKey && 'ring-2 ring-yellow-500 border-yellow-500'
                    )}
                  />
                  <button
                    onClick={() => {
                      updateLLMMutation.mutate(
                        { huggingface_api_key: huggingfaceKey },
                        { onSuccess: () => { clearDirty('huggingfaceKey'); setHuggingfaceKey('') } }
                      )
                    }}
                    disabled={!huggingfaceKey}
                    className={clsx(
                      'btn-secondary px-3',
                      dirtyFields.huggingfaceKey && 'bg-yellow-500/20 border-yellow-500 text-yellow-500'
                    )}
                  >
                    <Save className="w-4 h-4" />
                  </button>
                  {dirtyFields.huggingfaceKey && (
                    <button
                      onClick={() => discardField('huggingfaceKey')}
                      className="btn-secondary px-3 bg-red-500/20 border-red-500 text-red-500"
                      title="Discard"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
              <div>
                <label className="section-header">Inference Provider</label>
                <select
                  value={huggingfaceProvider}
                  onChange={(e) => {
                    setHuggingfaceProvider(e.target.value)
                    updateLLMMutation.mutate({ huggingface_inference_provider: e.target.value })
                  }}
                  className="input-base w-full"
                >
                  <option value="auto">Auto (Best available)</option>
                  <option value="hf-inference">HF Inference API</option>
                  <option value="together">Together AI</option>
                  <option value="fireworks">Fireworks AI</option>
                  <option value="nebius">Nebius</option>
                </select>
              </div>
            </div>
          </div>

          {/* Azure OpenAI */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">Azure OpenAI</span>
                {health?.azure_openai_configured && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">Enterprise GPT</span>
            </div>

            <div className="space-y-3">
              <div>
                <label className="section-header">API Key</label>
                <input
                  type="password"
                  value={azureKey}
                  onChange={(e) => {
                    setAzureKey(e.target.value)
                    markDirty('azureKey')
                  }}
                  placeholder={llmSettings?.azure_openai_api_key ? '••••••••' : 'Enter Azure API key'}
                  className={clsx(
                    'input-base w-full font-mono',
                    dirtyFields.azureKey && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
              </div>
              <div>
                <label className="section-header">Endpoint URL</label>
                <input
                  type="text"
                  value={azureEndpoint}
                  onChange={(e) => {
                    setAzureEndpoint(e.target.value)
                    markDirty('azureEndpoint')
                  }}
                  placeholder={llmSettings?.azure_openai_endpoint || 'https://your-resource.openai.azure.com'}
                  className={clsx(
                    'input-base w-full font-mono',
                    dirtyFields.azureEndpoint && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="section-header">Deployment Name</label>
                  <input
                    type="text"
                    value={azureDeployment}
                    onChange={(e) => {
                      setAzureDeployment(e.target.value)
                      markDirty('azureDeployment')
                    }}
                    placeholder={llmSettings?.azure_openai_deployment || 'gpt-4o'}
                    className={clsx(
                      'input-base w-full font-mono',
                      dirtyFields.azureDeployment && 'ring-2 ring-yellow-500 border-yellow-500'
                    )}
                  />
                </div>
                <div>
                  <label className="section-header">API Version</label>
                  <input
                    type="text"
                    value={azureApiVersion}
                    onChange={(e) => {
                      setAzureApiVersion(e.target.value)
                      markDirty('azureApiVersion')
                    }}
                    placeholder="2024-05-01-preview"
                    className={clsx(
                      'input-base w-full font-mono',
                      dirtyFields.azureApiVersion && 'ring-2 ring-yellow-500 border-yellow-500'
                    )}
                  />
                </div>
              </div>
              {(dirtyFields.azureKey || dirtyFields.azureEndpoint || dirtyFields.azureDeployment || dirtyFields.azureApiVersion) && (
                <div className="flex gap-2 p-2 bg-yellow-500/10 rounded border border-yellow-500/30">
                  <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                  <span className="text-xs text-yellow-500">Unsaved Azure changes</span>
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    updateLLMMutation.mutate(
                      {
                        azure_openai_api_key: azureKey || undefined,
                        azure_openai_endpoint: azureEndpoint || undefined,
                        azure_openai_deployment: azureDeployment || undefined,
                        azure_openai_api_version: azureApiVersion || undefined,
                      },
                      {
                        onSuccess: () => {
                          clearDirtyFields(['azureKey', 'azureEndpoint', 'azureDeployment', 'azureApiVersion'])
                          setAzureKey('')
                        }
                      }
                    )
                  }}
                  disabled={!azureKey && !azureEndpoint && !azureDeployment && !azureApiVersion}
                  className={clsx(
                    'btn-secondary flex-1 flex items-center justify-center',
                    (dirtyFields.azureKey || dirtyFields.azureEndpoint || dirtyFields.azureDeployment || dirtyFields.azureApiVersion) &&
                    'bg-yellow-500/20 border-yellow-500 text-yellow-500'
                  )}
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save Azure Settings
                </button>
                {(dirtyFields.azureKey || dirtyFields.azureEndpoint || dirtyFields.azureDeployment || dirtyFields.azureApiVersion) && (
                  <button
                    onClick={() => {
                      discardField('azureKey')
                      discardField('azureEndpoint')
                      discardField('azureDeployment')
                      discardField('azureApiVersion')
                    }}
                    className="btn-secondary px-3 bg-red-500/20 border-red-500 text-red-500"
                    title="Discard all Azure changes"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* AWS Bedrock */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">AWS Bedrock</span>
                {health?.aws_bedrock_configured && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">Claude, Llama on AWS</span>
            </div>

            <div className="space-y-3">
              <div>
                <label className="section-header">AWS Access Key ID</label>
                <input
                  type="password"
                  value={awsAccessKey}
                  onChange={(e) => {
                    setAwsAccessKey(e.target.value)
                    markDirty('awsAccessKey')
                  }}
                  placeholder={llmSettings?.aws_access_key_id ? '••••••••' : 'AKIA...'}
                  className={clsx(
                    'input-base w-full font-mono',
                    dirtyFields.awsAccessKey && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
              </div>
              <div>
                <label className="section-header">AWS Secret Access Key</label>
                <input
                  type="password"
                  value={awsSecretKey}
                  onChange={(e) => {
                    setAwsSecretKey(e.target.value)
                    markDirty('awsSecretKey')
                  }}
                  placeholder={llmSettings?.aws_secret_access_key ? '••••••••' : 'Secret key'}
                  className={clsx(
                    'input-base w-full font-mono',
                    dirtyFields.awsSecretKey && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
              </div>
              <div>
                <label className="section-header">AWS Region</label>
                <select
                  value={awsRegion}
                  onChange={(e) => {
                    setAwsRegion(e.target.value)
                    markDirty('awsRegion')
                  }}
                  className={clsx(
                    'input-base w-full',
                    dirtyFields.awsRegion && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                >
                  <option value="us-east-1">US East (N. Virginia)</option>
                  <option value="us-west-2">US West (Oregon)</option>
                  <option value="eu-west-1">EU (Ireland)</option>
                  <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
                  <option value="ap-northeast-1">Asia Pacific (Tokyo)</option>
                </select>
              </div>
              {(dirtyFields.awsAccessKey || dirtyFields.awsSecretKey || dirtyFields.awsRegion) && (
                <div className="flex gap-2 p-2 bg-yellow-500/10 rounded border border-yellow-500/30">
                  <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                  <span className="text-xs text-yellow-500">Unsaved AWS changes</span>
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    updateLLMMutation.mutate(
                      {
                        aws_access_key_id: awsAccessKey || undefined,
                        aws_secret_access_key: awsSecretKey || undefined,
                        aws_region: awsRegion,
                      },
                      {
                        onSuccess: () => {
                          clearDirtyFields(['awsAccessKey', 'awsSecretKey', 'awsRegion'])
                          setAwsAccessKey('')
                          setAwsSecretKey('')
                        }
                      }
                    )
                  }}
                  disabled={!awsAccessKey && !awsSecretKey && !dirtyFields.awsRegion}
                  className={clsx(
                    'btn-secondary flex-1 flex items-center justify-center',
                    (dirtyFields.awsAccessKey || dirtyFields.awsSecretKey || dirtyFields.awsRegion) &&
                    'bg-yellow-500/20 border-yellow-500 text-yellow-500'
                  )}
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save AWS Settings
                </button>
                {(dirtyFields.awsAccessKey || dirtyFields.awsSecretKey || dirtyFields.awsRegion) && (
                  <button
                    onClick={() => {
                      discardField('awsAccessKey')
                      discardField('awsSecretKey')
                      discardField('awsRegion')
                    }}
                    className="btn-secondary px-3 bg-red-500/20 border-red-500 text-red-500"
                    title="Discard all AWS changes"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Custom Endpoint */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">Custom Endpoint</span>
                {llmSettings?.custom_endpoint && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">OpenAI-compatible</span>
            </div>

            <div className="space-y-3">
              <div>
                <label className="section-header">Endpoint URL</label>
                <input
                  type="text"
                  value={customEndpoint}
                  onChange={(e) => {
                    setCustomEndpoint(e.target.value)
                    markDirty('customEndpoint')
                  }}
                  placeholder={llmSettings?.custom_endpoint || 'https://api.example.com/v1'}
                  className={clsx(
                    'input-base w-full font-mono',
                    dirtyFields.customEndpoint && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
              </div>
              <div>
                <label className="section-header">API Key (optional)</label>
                <input
                  type="password"
                  value={customApiKey}
                  onChange={(e) => {
                    setCustomApiKey(e.target.value)
                    markDirty('customApiKey')
                  }}
                  placeholder={llmSettings?.custom_api_key ? '••••••••' : 'API key if required'}
                  className={clsx(
                    'input-base w-full font-mono',
                    dirtyFields.customApiKey && 'ring-2 ring-yellow-500 border-yellow-500'
                  )}
                />
              </div>
              {(dirtyFields.customEndpoint || dirtyFields.customApiKey) && (
                <div className="flex gap-2 p-2 bg-yellow-500/10 rounded border border-yellow-500/30">
                  <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                  <span className="text-xs text-yellow-500">Unsaved custom endpoint changes</span>
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    updateLLMMutation.mutate(
                      {
                        custom_endpoint: customEndpoint || undefined,
                        custom_api_key: customApiKey || undefined,
                      },
                      {
                        onSuccess: () => {
                          clearDirtyFields(['customEndpoint', 'customApiKey'])
                          setCustomApiKey('')
                        }
                      }
                    )
                  }}
                  disabled={!customEndpoint && !customApiKey}
                  className={clsx(
                    'btn-secondary flex-1 flex items-center justify-center',
                    (dirtyFields.customEndpoint || dirtyFields.customApiKey) &&
                    'bg-yellow-500/20 border-yellow-500 text-yellow-500'
                  )}
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save Custom Endpoint
                </button>
                {(dirtyFields.customEndpoint || dirtyFields.customApiKey) && (
                  <button
                    onClick={() => {
                      discardField('customEndpoint')
                      discardField('customApiKey')
                    }}
                    className="btn-secondary px-3 bg-red-500/20 border-red-500 text-red-500"
                    title="Discard custom endpoint changes"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Default Provider */}
          <div className="console-card-elevated p-4 border-t-2 border-t-accent-red">
            <div className="flex items-center justify-between mb-3">
              <span className="font-medium">Default AI Provider</span>
              <span className="text-xs text-text-muted">Used when creating new scripts</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="section-header">Provider</label>
                <select
                  value={defaultProvider}
                  onChange={(e) => {
                    setDefaultProvider(e.target.value)
                    updateLLMMutation.mutate({ default_provider: e.target.value })
                  }}
                  className="input-base w-full"
                >
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="google">Google Gemini</option>
                  <option value="azure_openai">Azure OpenAI</option>
                  <option value="aws_bedrock">AWS Bedrock</option>
                  <option value="huggingface">HuggingFace</option>
                  <option value="custom">Custom Endpoint</option>
                </select>
              </div>
              <div>
                <label className="section-header">Default Model</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={defaultModel}
                    onChange={(e) => {
                      setDefaultModel(e.target.value)
                      markDirty('defaultModel')
                    }}
                    placeholder={llmSettings?.default_model || 'e.g., gpt-4o, llama3.2:3b'}
                    className={clsx(
                      'input-base flex-1 font-mono',
                      dirtyFields.defaultModel && 'ring-2 ring-yellow-500 border-yellow-500'
                    )}
                  />
                  {dirtyFields.defaultModel && (
                    <>
                      <button
                        onClick={() => {
                          updateLLMMutation.mutate(
                            { default_model: defaultModel },
                            { onSuccess: () => clearDirty('defaultModel') }
                          )
                        }}
                        className="btn-secondary px-3 bg-yellow-500/20 border-yellow-500 text-yellow-500"
                        title="Save"
                      >
                        <Save className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => discardField('defaultModel')}
                        className="btn-secondary px-3 bg-red-500/20 border-red-500 text-red-500"
                        title="Discard"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
            <p className="text-xs text-text-muted mt-2">
              These settings will be used as defaults when generating AI scripts. You can still change the provider per-project.
            </p>
          </div>
        </div>
      </SettingsSection>

      {/* Storage Management */}
      <SettingsSection title="Storage Management" icon={Database}>
        {/* Storage Location */}
        <StorageLocationSection />

        <div className="grid grid-cols-2 gap-4">
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">TTS Cache</span>
              <span className="text-xs text-text-muted">
                {system?.cache_size_mb?.toFixed(1)}MB
              </span>
            </div>
            <p className="text-xs text-text-muted mb-3">
              Cached audio files for faster generation
            </p>
            <button
              onClick={() => clearCacheMutation.mutate()}
              disabled={clearCacheMutation.isPending}
              className="btn-secondary w-full flex items-center justify-center gap-2"
            >
              {clearCacheMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              Clear Cache
            </button>
          </div>

          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">Temp Files</span>
              <span className="text-xs text-text-muted">Processing files</span>
            </div>
            <p className="text-xs text-text-muted mb-3">
              Temporary files from video processing
            </p>
            <button
              onClick={() => clearTempMutation.mutate()}
              disabled={clearTempMutation.isPending}
              className="btn-secondary w-full flex items-center justify-center gap-2"
            >
              {clearTempMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              Clear Temp
            </button>
          </div>
        </div>
      </SettingsSection>

      {/* Application Configuration */}
      <AppConfigurationSection />

      {/* About */}
      <SettingsSection title="About" icon={Settings}>
        <div className="text-center py-4">
          <div className="inline-flex items-center justify-center mb-2">
            <img
              src="/assets/Horizontal_Logo.svg"
              alt="TermiVoxed"
              className="h-10 w-auto"
            />
          </div>
          <p className="text-sm text-text-muted mb-4">
            AI Voice-Over Dubbing Tool for Content Creators
          </p>
          <div className="flex items-center justify-center gap-4 text-xs text-text-muted">
            <span>Version 1.0.0</span>
          </div>
        </div>
      </SettingsSection>

      {/* Developer Tools */}
      <DeveloperToolsSection />
    </div>
  )
}

// Directory browser state interface
interface DirectoryBrowserState {
  currentPath: string
  parentPath: string | null
  directories: string[]
  canGoUp: boolean
}

// Storage Location Section Component
function StorageLocationSection() {
  const queryClient = useQueryClient()

  // Directory browser state
  const [showDirectoryBrowser, setShowDirectoryBrowser] = useState(false)
  const [directoryState, setDirectoryState] = useState<DirectoryBrowserState | null>(null)
  const [isLoadingDirs, setIsLoadingDirs] = useState(false)

  // Fetch storage settings
  const { data: storageData, isLoading } = useQuery({
    queryKey: ['storage-settings'],
    queryFn: () => settingsApi.getStorage(),
  })

  const storage = storageData?.data

  // Update storage path mutation
  const updateStorageMutation = useMutation({
    mutationFn: (newPath: string) => settingsApi.updateStorage(newPath),
    onSuccess: () => {
      toast.success('Storage path updated')
      setShowDirectoryBrowser(false)
      queryClient.invalidateQueries({ queryKey: ['storage-settings'] })
      queryClient.invalidateQueries({ queryKey: ['system-info'] })
    },
    onError: (error: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(error.response?.data?.detail || 'Failed to update storage path')
    },
  })

  // Reset storage path mutation
  const resetStorageMutation = useMutation({
    mutationFn: () => settingsApi.resetStorage(),
    onSuccess: () => {
      toast.success('Storage path reset to default')
      queryClient.invalidateQueries({ queryKey: ['storage-settings'] })
      queryClient.invalidateQueries({ queryKey: ['system-info'] })
    },
    onError: () => {
      toast.error('Failed to reset storage path')
    },
  })

  // Load directory contents
  const browseDirectory = async (path?: string) => {
    // Only show loading spinner if request takes longer than 150ms
    const loadingTimeout = setTimeout(() => setIsLoadingDirs(true), 150)
    try {
      const response = await exportApi.browseDirectories(path)
      setDirectoryState({
        currentPath: response.data.current_path,
        parentPath: response.data.parent_path,
        directories: response.data.directories,
        canGoUp: response.data.can_go_up,
      })
    } catch {
      toast.error('Failed to browse directories')
    } finally {
      clearTimeout(loadingTimeout)
      setIsLoadingDirs(false)
    }
  }

  // Open directory browser
  const openDirectoryBrowser = () => {
    setShowDirectoryBrowser(true)
    browseDirectory(storage?.storage_path)
  }

  // Select current directory
  const selectDirectory = () => {
    if (directoryState && directoryState.currentPath !== storage?.storage_path) {
      updateStorageMutation.mutate(directoryState.currentPath)
    } else {
      setShowDirectoryBrowser(false)
    }
  }

  const handleReset = () => {
    if (confirm('Reset storage path to default? This will require a server restart.')) {
      resetStorageMutation.mutate()
    }
  }

  if (isLoading) {
    return (
      <div className="console-card-elevated p-4 mb-4 flex items-center justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-accent-red" />
      </div>
    )
  }

  return (
    <div className="console-card-elevated p-4 mb-4 relative">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <FolderOpen className="w-4 h-4 text-accent-red" />
          <span className="font-medium">Storage Location</span>
        </div>
        <div className="flex items-center gap-2">
          {storage?.is_default ? (
            <span className="px-2 py-0.5 text-xs bg-terminal-bg border border-terminal-border text-text-secondary rounded font-mono">
              DEFAULT
            </span>
          ) : (
            <span className="px-2 py-0.5 text-xs bg-accent-red/10 border border-accent-red/30 text-accent-red rounded font-mono">
              CUSTOM
            </span>
          )}
          {storage?.path_exists && storage?.path_writable && (
            <div className="status-dot status-dot-success" title="Path exists and is writable" />
          )}
        </div>
      </div>

      {/* Storage Path Display with Browse Button */}
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 p-3 bg-terminal-bg rounded border border-terminal-border">
            <p className="text-sm font-mono text-text-primary break-all">
              {storage?.storage_path}
            </p>
          </div>
          <button
            onClick={openDirectoryBrowser}
            className="btn-secondary px-3 flex items-center gap-2"
          >
            <FolderOpen className="w-4 h-4" />
            Browse
          </button>
        </div>

        {/* Info & Actions */}
        <div className="flex items-center justify-between">
          <div className="text-xs text-text-muted space-y-1">
            <p>
              <span className="text-text-secondary">Platform:</span>{' '}
              {storage?.platform === 'Darwin' ? 'macOS' : storage?.platform}
            </p>
            <p>
              <span className="text-text-secondary">Default:</span>{' '}
              <span className="font-mono">{storage?.default_path}</span>
            </p>
          </div>

          {!storage?.is_default && (
            <button
              onClick={handleReset}
              disabled={resetStorageMutation.isPending}
              className="btn-secondary text-xs flex items-center gap-1.5"
              title="Reset to default path"
            >
              {resetStorageMutation.isPending ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <RefreshCw className="w-3 h-3" />
              )}
              Reset to Default
            </button>
          )}
        </div>
      </div>

      {/* Help text */}
      <div className="mt-3 p-3 bg-terminal-bg/50 rounded border border-terminal-border text-xs text-text-muted">
        <p>
          All projects, exports, cache, and temporary files are stored in this location.
        </p>
      </div>

      {/* Directory Browser Modal */}
      {showDirectoryBrowser && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-terminal-surface border border-terminal-border rounded-lg p-4 w-full max-w-lg mx-4 max-h-[70vh] flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-medium flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-accent-red" />
                Select Storage Directory
              </h4>
              <button
                onClick={() => setShowDirectoryBrowser(false)}
                className="text-text-muted hover:text-text-primary"
              >
                Cancel
              </button>
            </div>

            {/* Current path display */}
            <div className="p-2 rounded bg-terminal-bg border border-terminal-border mb-3 font-mono text-xs break-all">
              {directoryState?.currentPath || 'Loading...'}
            </div>

            {/* Directory listing */}
            <div className="flex-1 overflow-y-auto border border-terminal-border rounded bg-terminal-bg min-h-[200px] max-h-[300px]">
              {isLoadingDirs ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-accent-red" />
                </div>
              ) : (
                <div className="divide-y divide-terminal-border">
                  {/* Go up button */}
                  {directoryState?.canGoUp && (
                    <button
                      onClick={() => browseDirectory(directoryState.parentPath || undefined)}
                      className="w-full p-2 text-left hover:bg-terminal-elevated flex items-center gap-2 text-sm"
                    >
                      <ChevronUp className="w-4 h-4 text-text-muted" />
                      <span className="text-text-muted">..</span>
                    </button>
                  )}

                  {/* Directory items */}
                  {directoryState?.directories.map((dir) => (
                    <button
                      key={dir}
                      onClick={() => browseDirectory(`${directoryState.currentPath}/${dir}`)}
                      className="w-full p-2 text-left hover:bg-terminal-elevated flex items-center gap-2 text-sm"
                    >
                      <Folder className="w-4 h-4 text-accent-red" />
                      <span>{dir}</span>
                    </button>
                  ))}

                  {directoryState?.directories.length === 0 && (
                    <div className="p-4 text-center text-text-muted text-sm">
                      No subdirectories
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Action buttons */}
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => setShowDirectoryBrowser(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={selectDirectory}
                disabled={updateStorageMutation.isPending}
                className="btn-primary flex items-center gap-2"
              >
                {updateStorageMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                Select This Directory
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Application Configuration Section Component
function AppConfigurationSection() {
  const queryClient = useQueryClient()

  // Fetch app config
  const { data: configData, isLoading, error: fetchError } = useQuery({
    queryKey: ['app-config'],
    queryFn: () => settingsApi.getAppConfig(),
  })

  // Fetch defaults for reference (prefetch for reset functionality)
  useQuery({
    queryKey: ['app-config-defaults'],
    queryFn: () => settingsApi.getAppConfigDefaults(),
  })

  const config = configData?.data

  // Local state for form fields
  const [ttsCacheEnabled, setTtsCacheEnabled] = useState(true)
  const [maxConcurrentTts, setMaxConcurrentTts] = useState(2)
  const [ttsProxyEnabled, setTtsProxyEnabled] = useState(false)
  const [ttsProxyUrl, setTtsProxyUrl] = useState('')
  const [defaultVideoCodec, setDefaultVideoCodec] = useState<'libx264' | 'libx265' | 'libvpx-vp9'>('libx264')
  const [defaultAudioCodec, setDefaultAudioCodec] = useState<'aac' | 'mp3' | 'opus'>('aac')
  const [defaultCrf, setDefaultCrf] = useState(23)
  const [defaultPreset, setDefaultPreset] = useState<'ultrafast' | 'superfast' | 'veryfast' | 'faster' | 'fast' | 'medium' | 'slow' | 'slower' | 'veryslow'>('medium')
  const [ttsVolumeBoost, setTtsVolumeBoost] = useState(3)
  const [bgmVolumeReduction, setBgmVolumeReduction] = useState(16)
  const [fadeDuration, setFadeDuration] = useState(3.0)
  const [logLevel, setLogLevel] = useState<'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'>('INFO')

  // Track dirty fields
  const [dirtyFields, setDirtyFields] = useState<Set<string>>(new Set())

  // Sync local state with fetched config
  useEffect(() => {
    if (config) {
      setTtsCacheEnabled(config.tts_cache_enabled)
      setMaxConcurrentTts(config.max_concurrent_tts)
      setTtsProxyEnabled(config.tts_proxy_enabled)
      setTtsProxyUrl(config.tts_proxy_url || '')
      setDefaultVideoCodec(config.default_video_codec)
      setDefaultAudioCodec(config.default_audio_codec)
      setDefaultCrf(config.default_crf)
      setDefaultPreset(config.default_preset)
      setTtsVolumeBoost(config.tts_volume_boost)
      setBgmVolumeReduction(config.bgm_volume_reduction)
      setFadeDuration(config.fade_duration)
      setLogLevel(config.log_level)
      setDirtyFields(new Set())
    }
  }, [config])

  // Mark field as dirty
  const markDirty = (field: string) => {
    setDirtyFields(prev => new Set(prev).add(field))
  }

  // Update mutation
  const updateConfigMutation = useMutation({
    mutationFn: (data: AppConfigUpdate) => settingsApi.updateAppConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['app-config'] })
      setDirtyFields(new Set())
      toast.success('Configuration saved successfully')
    },
    onError: (error: Error) => {
      toast.error(`Failed to save configuration: ${error.message}`)
    },
  })

  // Reset mutation
  const resetConfigMutation = useMutation({
    mutationFn: () => settingsApi.resetAppConfig(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['app-config'] })
      toast.success('Configuration reset to defaults')
    },
    onError: (error: Error) => {
      toast.error(`Failed to reset configuration: ${error.message}`)
    },
  })

  // Save all changes
  const handleSaveAll = () => {
    updateConfigMutation.mutate({
      tts_cache_enabled: ttsCacheEnabled,
      max_concurrent_tts: maxConcurrentTts,
      tts_proxy_enabled: ttsProxyEnabled,
      tts_proxy_url: ttsProxyUrl || null,
      default_video_codec: defaultVideoCodec,
      default_audio_codec: defaultAudioCodec,
      default_crf: defaultCrf,
      default_preset: defaultPreset,
      tts_volume_boost: ttsVolumeBoost,
      bgm_volume_reduction: bgmVolumeReduction,
      fade_duration: fadeDuration,
      log_level: logLevel,
    })
  }

  // Discard changes
  const handleDiscardAll = () => {
    if (config) {
      setTtsCacheEnabled(config.tts_cache_enabled)
      setMaxConcurrentTts(config.max_concurrent_tts)
      setTtsProxyEnabled(config.tts_proxy_enabled)
      setTtsProxyUrl(config.tts_proxy_url || '')
      setDefaultVideoCodec(config.default_video_codec)
      setDefaultAudioCodec(config.default_audio_codec)
      setDefaultCrf(config.default_crf)
      setDefaultPreset(config.default_preset)
      setTtsVolumeBoost(config.tts_volume_boost)
      setBgmVolumeReduction(config.bgm_volume_reduction)
      setFadeDuration(config.fade_duration)
      setLogLevel(config.log_level)
      setDirtyFields(new Set())
      toast('Changes discarded')
    }
  }

  const hasDirtyFields = dirtyFields.size > 0

  if (isLoading) {
    return (
      <SettingsSection title="Application Configuration" icon={Settings}>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-text-muted" />
        </div>
      </SettingsSection>
    )
  }

  if (fetchError) {
    return (
      <SettingsSection title="Application Configuration" icon={Settings}>
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load configuration: {(fetchError as Error).message}</span>
        </div>
      </SettingsSection>
    )
  }

  return (
    <SettingsSection title="Application Configuration" icon={Settings}>
      {/* Unsaved Changes Banner */}
      <AnimatePresence>
        {hasDirtyFields && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-amber-400 text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>You have unsaved changes ({dirtyFields.size} field{dirtyFields.size > 1 ? 's' : ''})</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleDiscardAll}
                  className="px-3 py-1 text-xs bg-terminal-elevated border border-terminal-border rounded hover:bg-terminal-border transition-colors"
                >
                  Discard
                </button>
                <button
                  onClick={handleSaveAll}
                  disabled={updateConfigMutation.isPending}
                  className="px-3 py-1 text-xs bg-accent-red text-white rounded hover:bg-accent-red/80 transition-colors flex items-center gap-1"
                >
                  {updateConfigMutation.isPending ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Save className="w-3 h-3" />
                  )}
                  Save All
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="space-y-6">
        {/* TTS Settings */}
        <div>
          <h4 className="text-sm font-medium text-text-secondary mb-3 flex items-center gap-2">
            <Mic className="w-4 h-4" />
            TTS Settings
          </h4>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-terminal-bg/50 rounded border border-terminal-border">
              <div>
                <span className="text-sm">Enable TTS Caching</span>
                <p className="text-[10px] text-text-muted">Cache generated audio for faster regeneration</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={ttsCacheEnabled}
                  onChange={(e) => { setTtsCacheEnabled(e.target.checked); markDirty('tts_cache_enabled') }}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-terminal-border rounded-full peer peer-checked:bg-accent-red transition-colors"></div>
                <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4"></div>
              </label>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-text-muted mb-1">Max Concurrent TTS Jobs</label>
                <input
                  type="number"
                  value={maxConcurrentTts}
                  onChange={(e) => { setMaxConcurrentTts(parseInt(e.target.value) || 2); markDirty('max_concurrent_tts') }}
                  min={1}
                  max={10}
                  className={clsx(
                    "input-base w-full text-sm",
                    dirtyFields.has('max_concurrent_tts') && "ring-1 ring-amber-500/50"
                  )}
                />
              </div>
              <div className="flex items-center justify-between p-3 bg-terminal-bg/50 rounded border border-terminal-border">
                <div>
                  <span className="text-sm">Enable Proxy</span>
                  <p className="text-[10px] text-text-muted">For corporate networks</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={ttsProxyEnabled}
                    onChange={(e) => { setTtsProxyEnabled(e.target.checked); markDirty('tts_proxy_enabled') }}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-terminal-border rounded-full peer peer-checked:bg-accent-red transition-colors"></div>
                  <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4"></div>
                </label>
              </div>
            </div>

            {ttsProxyEnabled && (
              <div>
                <label className="block text-xs text-text-muted mb-1">Proxy URL</label>
                <input
                  type="text"
                  value={ttsProxyUrl}
                  onChange={(e) => { setTtsProxyUrl(e.target.value); markDirty('tts_proxy_url') }}
                  className={clsx(
                    "input-base w-full text-sm",
                    dirtyFields.has('tts_proxy_url') && "ring-1 ring-amber-500/50"
                  )}
                  placeholder="http://proxy.example.com:8080"
                />
              </div>
            )}
          </div>
        </div>

        {/* Video Export Settings */}
        <div>
          <h4 className="text-sm font-medium text-text-secondary mb-3 flex items-center gap-2">
            <HardDrive className="w-4 h-4" />
            Video Export Settings
          </h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-text-muted mb-1">Video Codec</label>
              <select
                value={defaultVideoCodec}
                onChange={(e) => { setDefaultVideoCodec(e.target.value as typeof defaultVideoCodec); markDirty('default_video_codec') }}
                className={clsx(
                  "input-base w-full text-sm",
                  dirtyFields.has('default_video_codec') && "ring-1 ring-amber-500/50"
                )}
              >
                <option value="libx264">H.264 (libx264) - Most Compatible</option>
                <option value="libx265">H.265 (libx265) - Better Compression</option>
                <option value="libvpx-vp9">VP9 (libvpx-vp9) - Web Optimized</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Audio Codec</label>
              <select
                value={defaultAudioCodec}
                onChange={(e) => { setDefaultAudioCodec(e.target.value as typeof defaultAudioCodec); markDirty('default_audio_codec') }}
                className={clsx(
                  "input-base w-full text-sm",
                  dirtyFields.has('default_audio_codec') && "ring-1 ring-amber-500/50"
                )}
              >
                <option value="aac">AAC - Most Compatible</option>
                <option value="mp3">MP3 - Universal</option>
                <option value="opus">Opus - Best Quality</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Quality (CRF: {defaultCrf})</label>
              <input
                type="range"
                value={defaultCrf}
                onChange={(e) => { setDefaultCrf(parseInt(e.target.value)); markDirty('default_crf') }}
                min={0}
                max={51}
                className="w-full"
              />
              <div className="flex justify-between text-[10px] text-text-muted">
                <span>Lossless</span>
                <span>Balanced</span>
                <span>Smallest</span>
              </div>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Encoding Preset</label>
              <select
                value={defaultPreset}
                onChange={(e) => { setDefaultPreset(e.target.value as typeof defaultPreset); markDirty('default_preset') }}
                className={clsx(
                  "input-base w-full text-sm",
                  dirtyFields.has('default_preset') && "ring-1 ring-amber-500/50"
                )}
              >
                <option value="ultrafast">Ultra Fast (Largest)</option>
                <option value="superfast">Super Fast</option>
                <option value="veryfast">Very Fast</option>
                <option value="faster">Faster</option>
                <option value="fast">Fast</option>
                <option value="medium">Medium (Recommended)</option>
                <option value="slow">Slow</option>
                <option value="slower">Slower</option>
                <option value="veryslow">Very Slow (Smallest)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Audio Mixing */}
        <div>
          <h4 className="text-sm font-medium text-text-secondary mb-3 flex items-center gap-2">
            <Mic className="w-4 h-4" />
            Audio Mixing
          </h4>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-text-muted mb-1">TTS Volume Boost: {ttsVolumeBoost} dB</label>
              <input
                type="range"
                value={ttsVolumeBoost}
                onChange={(e) => { setTtsVolumeBoost(parseInt(e.target.value)); markDirty('tts_volume_boost') }}
                min={0}
                max={30}
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">BGM Reduction: {bgmVolumeReduction} dB</label>
              <input
                type="range"
                value={bgmVolumeReduction}
                onChange={(e) => { setBgmVolumeReduction(parseInt(e.target.value)); markDirty('bgm_volume_reduction') }}
                min={0}
                max={40}
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Fade Duration: {fadeDuration.toFixed(1)}s</label>
              <input
                type="range"
                value={fadeDuration * 10}
                onChange={(e) => { setFadeDuration(parseInt(e.target.value) / 10); markDirty('fade_duration') }}
                min={0}
                max={100}
                className="w-full"
              />
            </div>
          </div>
        </div>

        {/* Logging */}
        <div>
          <h4 className="text-sm font-medium text-text-secondary mb-3 flex items-center gap-2">
            <Terminal className="w-4 h-4" />
            Logging
          </h4>
          <div>
            <label className="block text-xs text-text-muted mb-1">Log Level</label>
            <select
              value={logLevel}
              onChange={(e) => { setLogLevel(e.target.value as typeof logLevel); markDirty('log_level') }}
              className={clsx(
                "input-base w-full text-sm",
                dirtyFields.has('log_level') && "ring-1 ring-amber-500/50"
              )}
            >
              <option value="DEBUG">Debug (Verbose)</option>
              <option value="INFO">Info (Standard)</option>
              <option value="WARNING">Warning (Errors + Warnings)</option>
              <option value="ERROR">Error (Errors Only)</option>
            </select>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-4 border-t border-terminal-border">
          <button
            onClick={() => resetConfigMutation.mutate()}
            disabled={resetConfigMutation.isPending}
            className="btn-secondary text-sm flex items-center gap-2"
          >
            {resetConfigMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RotateCcw className="w-4 h-4" />
            )}
            Reset to Defaults
          </button>

          <div className="flex gap-2">
            {hasDirtyFields && (
              <button
                onClick={handleDiscardAll}
                className="btn-secondary text-sm"
              >
                Discard Changes
              </button>
            )}
            <button
              onClick={handleSaveAll}
              disabled={!hasDirtyFields || updateConfigMutation.isPending}
              className={clsx(
                "px-4 py-2 rounded text-sm flex items-center gap-2 transition-colors",
                hasDirtyFields
                  ? "bg-accent-red text-white hover:bg-accent-red/80"
                  : "bg-terminal-elevated text-text-muted cursor-not-allowed"
              )}
            >
              {updateConfigMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save Configuration
            </button>
          </div>
        </div>
      </div>
    </SettingsSection>
  )
}

// Developer Tools Section Component
function DeveloperToolsSection() {
  const { logs, generateCrashReport, openPanel, clearLogs } = useDebugStore()
  const [copied, setCopied] = useState(false)

  const errorCount = logs.filter(l => l.level === 'error').length
  const warningCount = logs.filter(l => l.level === 'warn').length

  const handleDownloadReport = () => {
    const report = generateCrashReport()
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `debug-report-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success('Debug report downloaded')
  }

  const handleCopyReport = async () => {
    try {
      const report = generateCrashReport()
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      toast.success('Debug report copied to clipboard')
    } catch {
      toast.error('Failed to copy report')
    }
  }

  return (
    <SettingsSection title="Developer Tools" icon={Bug}>
      <div className="space-y-4">
        {/* Debug Console Status */}
        <div className="console-card-elevated p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Terminal className="w-5 h-5 text-accent-red" />
              <span className="font-medium">Debug Console</span>
            </div>
            <div className="flex items-center gap-2">
              {errorCount > 0 && (
                <span className="px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded">
                  {errorCount} errors
                </span>
              )}
              {warningCount > 0 && (
                <span className="px-2 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded">
                  {warningCount} warnings
                </span>
              )}
              <span className="text-xs text-text-muted">
                {logs.length} logs
              </span>
            </div>
          </div>

          <p className="text-xs text-text-muted mb-4">
            The debug console collects errors, warnings, and user actions to help diagnose issues.
            Press <kbd className="px-1.5 py-0.5 bg-terminal-bg rounded border border-terminal-border font-mono text-[10px]">Ctrl+Shift+D</kbd> to open the debug panel at any time.
          </p>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={openPanel}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <Terminal className="w-4 h-4" />
              Open Debug Panel
            </button>

            <button
              onClick={handleDownloadReport}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <Download className="w-4 h-4" />
              Download Report
            </button>

            <button
              onClick={handleCopyReport}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-green-500" />
                  Copied!
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Copy Report
                </>
              )}
            </button>

            {logs.length > 0 && (
              <button
                onClick={() => {
                  clearLogs()
                  toast.success('Debug logs cleared')
                }}
                className="btn-secondary flex items-center gap-2 text-sm text-red-400 hover:text-red-300"
              >
                <Trash2 className="w-4 h-4" />
                Clear Logs
              </button>
            )}
          </div>
        </div>

        {/* Crash Reporting Info */}
        <div className="p-4 bg-terminal-bg rounded border border-terminal-border">
          <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-500" />
            Crash Reporting
          </h4>
          <p className="text-xs text-text-muted mb-3">
            If you encounter an issue or the application crashes, the debug report contains:
          </p>
          <ul className="text-xs text-text-muted space-y-1 list-disc list-inside">
            <li>Recent errors and warnings</li>
            <li>User actions leading up to the issue</li>
            <li>System information (browser, viewport, memory)</li>
            <li>Current session and project context</li>
          </ul>
          <p className="text-xs text-text-muted mt-3">
            This information helps developers diagnose and fix issues. No personal data or video content is included.
          </p>
        </div>
      </div>
    </SettingsSection>
  )
}
