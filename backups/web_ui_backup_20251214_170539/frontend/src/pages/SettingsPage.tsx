import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Settings,
  Server,
  Database,
  Trash2,
  Check,
  Loader2,
  HardDrive,
  Cpu,
  Key,
} from 'lucide-react'
import { settingsApi, llmApi, ttsApi } from '../api/client'
import toast from 'react-hot-toast'
import clsx from 'clsx'

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

  // State for editable fields
  const [openaiKey, setOpenaiKey] = useState('')
  const [anthropicKey, setAnthropicKey] = useState('')
  const [ollamaEndpoint, setOllamaEndpoint] = useState('http://localhost:11434')

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
            <span className="font-mono">{system?.platform}</span>
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

      {/* LLM Providers */}
      <SettingsSection title="AI/LLM Providers" icon={Cpu}>
        <div className="space-y-4">
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
              <input
                type="text"
                value={ollamaEndpoint}
                onChange={(e) => setOllamaEndpoint(e.target.value)}
                className="input-base w-full font-mono"
              />
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
                {llmSettings?.openai_api_key && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">GPT-4, GPT-3.5</span>
            </div>

            <div>
              <label className="section-header">API Key</label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder={llmSettings?.openai_api_key ? '••••••••' : 'Enter API key'}
                  className="input-base flex-1 font-mono"
                />
                <button
                  onClick={() =>
                    updateLLMMutation.mutate({ openai_api_key: openaiKey })
                  }
                  disabled={!openaiKey}
                  className="btn-secondary px-3"
                >
                  <Key className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Anthropic */}
          <div className="console-card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">Anthropic</span>
                {llmSettings?.anthropic_api_key && (
                  <Check className="w-4 h-4 text-green-500" />
                )}
              </div>
              <span className="text-xs text-text-muted">Claude 3</span>
            </div>

            <div>
              <label className="section-header">API Key</label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  placeholder={llmSettings?.anthropic_api_key ? '••••••••' : 'Enter API key'}
                  className="input-base flex-1 font-mono"
                />
                <button
                  onClick={() =>
                    updateLLMMutation.mutate({ anthropic_api_key: anthropicKey })
                  }
                  disabled={!anthropicKey}
                  className="btn-secondary px-3"
                >
                  <Key className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </SettingsSection>

      {/* Storage Management */}
      <SettingsSection title="Storage Management" icon={Database}>
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

        <div className="mt-4 p-3 bg-terminal-bg rounded text-xs font-mono text-text-muted">
          Storage path: {system?.storage_path}
        </div>
      </SettingsSection>

      {/* About */}
      <SettingsSection title="About" icon={Settings}>
        <div className="text-center py-4">
          <div className="inline-flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded bg-accent-red flex items-center justify-center shadow-glow-red-sm">
              <Cpu className="w-5 h-5 text-white" />
            </div>
            <span className="font-mono font-bold text-xl">
              <span className="text-accent-red">Termi</span>
              <span className="text-white">Voxed</span>
            </span>
          </div>
          <p className="text-sm text-text-muted mb-4">
            AI Voice-Over Dubbing Tool for Content Creators
          </p>
          <div className="flex items-center justify-center gap-4 text-xs text-text-muted">
            <span>Version 1.0.0</span>
            <span className="text-terminal-border">•</span>
            <a href="#" className="text-accent-red hover:underline">
              Documentation
            </a>
            <span className="text-terminal-border">•</span>
            <a href="#" className="text-accent-red hover:underline">
              GitHub
            </a>
          </div>
        </div>
      </SettingsSection>
    </div>
  )
}
