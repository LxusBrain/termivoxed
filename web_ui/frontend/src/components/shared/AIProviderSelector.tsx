/**
 * AIProviderSelector - Shared component for selecting AI providers and models
 */

import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Check } from 'lucide-react'
import { llmApi } from '../../api/client'
import { AI_PROVIDER_CONFIG, AIProviderType, AI_PROVIDER_TYPES } from '../../constants/aiProviders'

interface AIProviderSelectorProps {
  provider: AIProviderType
  model: string
  apiKey: string
  onProviderChange: (provider: AIProviderType) => void
  onModelChange: (model: string) => void
  onApiKeyChange: (apiKey: string) => void

  // Azure-specific
  azureEndpoint?: string
  azureDeployment?: string
  azureApiVersion?: string
  onAzureEndpointChange?: (endpoint: string) => void
  onAzureDeploymentChange?: (deployment: string) => void
  onAzureApiVersionChange?: (version: string) => void

  // AWS-specific
  awsRegion?: string
  awsAccessKeyId?: string
  awsSecretAccessKey?: string
  onAwsRegionChange?: (region: string) => void
  onAwsAccessKeyIdChange?: (keyId: string) => void
  onAwsSecretAccessKeyChange?: (secret: string) => void

  // HuggingFace-specific
  hfInferenceProvider?: string
  onHfInferenceProviderChange?: (provider: string) => void

  // Custom endpoint
  customEndpoint?: string
  onCustomEndpointChange?: (endpoint: string) => void
}

export default function AIProviderSelector({
  provider,
  model,
  apiKey,
  onProviderChange,
  onModelChange,
  onApiKeyChange,
  azureEndpoint = '',
  azureDeployment = '',
  azureApiVersion = '2024-05-01-preview',
  onAzureEndpointChange,
  onAzureDeploymentChange,
  onAzureApiVersionChange,
  awsRegion = 'us-east-1',
  awsAccessKeyId = '',
  awsSecretAccessKey = '',
  onAwsRegionChange,
  onAwsAccessKeyIdChange,
  onAwsSecretAccessKeyChange,
  hfInferenceProvider = 'auto',
  onHfInferenceProviderChange,
  customEndpoint = '',
  onCustomEndpointChange,
}: AIProviderSelectorProps) {
  // Fetch Ollama models
  const { data: ollamaData } = useQuery({
    queryKey: ['ollama-models'],
    queryFn: () => llmApi.listOllamaModels(),
    enabled: provider === 'ollama',
  })

  const ollamaModels = ollamaData?.data?.models || []
  const ollamaConnected = ollamaData?.data?.connected ?? false

  // Get models for current provider
  const providerConfig = AI_PROVIDER_CONFIG[provider]
  const availableModels: { id: string; name: string }[] =
    provider === 'ollama'
      ? ollamaModels.map((m: { name: string }) => ({ id: m.name, name: m.name }))
      : providerConfig.models

  // Auto-select first model when provider changes
  useEffect(() => {
    if (provider === 'ollama' && ollamaModels.length > 0 && !model) {
      onModelChange(ollamaModels[0].name)
    } else if (provider !== 'ollama' && provider !== 'custom' && availableModels.length > 0 && !model) {
      onModelChange(availableModels[0].id)
    }
  }, [provider, ollamaModels, model, availableModels, onModelChange])

  return (
    <div className="space-y-4">
      {/* Provider Selection Grid */}
      <div>
        <label className="block text-sm font-medium text-text-secondary mb-2">AI Provider</label>
        <div className="grid grid-cols-4 gap-2">
          {AI_PROVIDER_TYPES.map((p) => {
            const config = AI_PROVIDER_CONFIG[p]
            const isSelected = provider === p

            return (
              <button
                key={p}
                onClick={() => {
                  onProviderChange(p)
                  onModelChange('') // Reset model when provider changes
                }}
                className={`p-2 rounded-lg border text-center transition-all ${
                  isSelected
                    ? 'border-accent-primary bg-accent-primary/10'
                    : 'border-terminal-border hover:border-text-muted'
                }`}
              >
                <div className="text-sm font-medium">{config.name}</div>
                <div className="text-xs text-text-muted">{config.description}</div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Ollama Connection Status */}
      {provider === 'ollama' && (
        <div
          className={`flex items-center gap-2 p-2 rounded-lg text-sm ${
            ollamaConnected ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          }`}
        >
          {ollamaConnected ? (
            <>
              <Check className="w-4 h-4" />
              Ollama connected • {ollamaModels.length} models available
            </>
          ) : (
            <>
              <AlertCircle className="w-4 h-4" />
              Ollama not running. Start with: ollama serve
            </>
          )}
        </div>
      )}

      {/* Model Selection */}
      {provider !== 'custom' && (
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">Model</label>
          <select
            value={model}
            onChange={(e) => onModelChange(e.target.value)}
            className="console-input w-full"
            disabled={provider === 'ollama' && !ollamaConnected}
          >
            <option value="">Select a model</option>
            {availableModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* API Key (for providers that require it) */}
      {providerConfig.requiresApiKey && provider !== 'aws_bedrock' && (
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            {provider === 'huggingface' ? 'HuggingFace Token' : 'API Key'}
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => onApiKeyChange(e.target.value)}
            className="console-input w-full"
            placeholder={`Enter your ${providerConfig.name} API key`}
          />
        </div>
      )}

      {/* Azure-specific fields */}
      {provider === 'azure_openai' && (
        <div className="space-y-3 p-3 bg-terminal-bg/50 rounded-lg">
          <div>
            <label className="block text-xs text-text-muted mb-1">Azure Endpoint</label>
            <input
              type="text"
              value={azureEndpoint}
              onChange={(e) => onAzureEndpointChange?.(e.target.value)}
              className="console-input w-full text-sm"
              placeholder="https://your-resource.openai.azure.com"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-text-muted mb-1">Deployment Name</label>
              <input
                type="text"
                value={azureDeployment}
                onChange={(e) => onAzureDeploymentChange?.(e.target.value)}
                className="console-input w-full text-sm"
                placeholder="gpt-4"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">API Version</label>
              <input
                type="text"
                value={azureApiVersion}
                onChange={(e) => onAzureApiVersionChange?.(e.target.value)}
                className="console-input w-full text-sm"
                placeholder="2024-05-01-preview"
              />
            </div>
          </div>
        </div>
      )}

      {/* AWS Bedrock-specific fields */}
      {provider === 'aws_bedrock' && (
        <div className="space-y-3 p-3 bg-terminal-bg/50 rounded-lg">
          <div>
            <label className="block text-xs text-text-muted mb-1">AWS Region</label>
            <select
              value={awsRegion}
              onChange={(e) => onAwsRegionChange?.(e.target.value)}
              className="console-input w-full text-sm"
            >
              <option value="us-east-1">US East (N. Virginia)</option>
              <option value="us-west-2">US West (Oregon)</option>
              <option value="eu-west-1">Europe (Ireland)</option>
              <option value="ap-northeast-1">Asia Pacific (Tokyo)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Access Key ID</label>
            <input
              type="password"
              value={awsAccessKeyId}
              onChange={(e) => onAwsAccessKeyIdChange?.(e.target.value)}
              className="console-input w-full text-sm"
              placeholder="AKIA..."
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Secret Access Key</label>
            <input
              type="password"
              value={awsSecretAccessKey}
              onChange={(e) => onAwsSecretAccessKeyChange?.(e.target.value)}
              className="console-input w-full text-sm"
              placeholder="Secret key"
            />
          </div>
        </div>
      )}

      {/* HuggingFace-specific fields */}
      {provider === 'huggingface' && (
        <div className="p-3 bg-terminal-bg/50 rounded-lg">
          <label className="block text-xs text-text-muted mb-1">Inference Provider</label>
          <select
            value={hfInferenceProvider}
            onChange={(e) => onHfInferenceProviderChange?.(e.target.value)}
            className="console-input w-full text-sm"
          >
            <option value="auto">Auto</option>
            <option value="hyperbolic">Hyperbolic</option>
            <option value="nebius">Nebius</option>
            <option value="together">Together AI</option>
          </select>
        </div>
      )}

      {/* Custom endpoint fields */}
      {provider === 'custom' && (
        <div className="space-y-3 p-3 bg-terminal-bg/50 rounded-lg">
          <div>
            <label className="block text-xs text-text-muted mb-1">Endpoint URL</label>
            <input
              type="text"
              value={customEndpoint}
              onChange={(e) => onCustomEndpointChange?.(e.target.value)}
              className="console-input w-full text-sm"
              placeholder="http://localhost:1234/v1"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Model Name</label>
            <input
              type="text"
              value={model}
              onChange={(e) => onModelChange(e.target.value)}
              className="console-input w-full text-sm"
              placeholder="Enter model name"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">API Key (optional)</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => onApiKeyChange(e.target.value)}
              className="console-input w-full text-sm"
              placeholder="Optional API key"
            />
          </div>
        </div>
      )}
    </div>
  )
}
